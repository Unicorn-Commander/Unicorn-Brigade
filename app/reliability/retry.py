"""Bounded async retry with exponential backoff + jitter (dependency-free).

BR-4 reliability. Used by the LLM client to transparently retry *transient*
outbound failures (connection errors, timeouts, HTTP 5xx, HTTP 429) while
NEVER retrying deterministic client errors (4xx other than 429). Hand-rolled
on purpose — no tenacity/backoff dependency — and small enough to unit-test.

The retry helper re-raises the ORIGINAL exception (not a wrapper) when a
failure is non-transient or attempts are exhausted, so existing callers keep
their current ``except httpx.HTTPStatusError`` / 4xx-fallback handling intact.
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


def _env_float(name: str, default: float) -> float:
    try:
        raw = os.getenv(name)
        return float(raw) if raw not in (None, "") else float(default)
    except (TypeError, ValueError):
        return float(default)


def _env_int(name: str, default: int) -> int:
    try:
        raw = os.getenv(name)
        return int(raw) if raw not in (None, "") else int(default)
    except (TypeError, ValueError):
        return int(default)


# ── Default outbound HTTP timeouts (seconds) ───────────────────────────────
# Every outbound client should carry an explicit total timeout. ``connect`` is
# deliberately short so an unreachable host fails fast instead of hanging the
# whole request; ``read`` is longer to accommodate slow token streaming.
# All configurable via env so a deploy can tune without a code change.
DEFAULT_CONNECT_TIMEOUT: float = _env_float("HTTP_CONNECT_TIMEOUT_SECONDS", 10.0)
DEFAULT_LLM_TIMEOUT: float = _env_float("LLM_HTTP_TIMEOUT_SECONDS", 120.0)
DEFAULT_TOOL_TIMEOUT: float = _env_float("TOOL_HTTP_TIMEOUT_SECONDS", 30.0)


class RetryExhaustedError(Exception):
    """Raised only when the caller opts into wrapping (unused by default).

    ``retry_async`` re-raises the original error by default; this type exists
    for callers that prefer an explicit "all attempts failed" signal.
    """

    def __init__(self, attempts: int, last_exception: BaseException):
        self.attempts = attempts
        self.last_exception = last_exception
        super().__init__(
            f"retry exhausted after {attempts} attempt(s): {last_exception!r}"
        )


@dataclass
class RetryConfig:
    """Bounded retry policy. ``max_attempts`` counts the FIRST try too."""

    max_attempts: int = 3
    base_delay: float = 0.5       # seconds before the first retry
    max_delay: float = 8.0        # per-sleep cap
    backoff_factor: float = 2.0   # exponential multiplier
    jitter: float = 0.5           # +/- fraction of the computed delay

    @classmethod
    def from_env(cls, prefix: str = "LLM_RETRY") -> "RetryConfig":
        return cls(
            max_attempts=max(1, _env_int(f"{prefix}_MAX_ATTEMPTS", 3)),
            base_delay=_env_float(f"{prefix}_BASE_DELAY", 0.5),
            max_delay=_env_float(f"{prefix}_MAX_DELAY", 8.0),
            backoff_factor=_env_float(f"{prefix}_BACKOFF_FACTOR", 2.0),
            jitter=_env_float(f"{prefix}_JITTER", 0.5),
        )


def is_transient_http_status(status_code: int) -> bool:
    """5xx and 429 are transient/retryable; every other 4xx is not."""
    return status_code >= 500 or status_code == 429


def default_is_transient(exc: BaseException) -> bool:
    """Decide whether ``exc`` is worth retrying.

    Retryable: connection errors, timeouts, HTTP 5xx, HTTP 429.
    Not retryable: HTTP 4xx (except 429) and anything else (programming
    errors, ``ModelUnavailableError``, etc.) — those propagate immediately.
    """
    try:
        import httpx
    except Exception:  # pragma: no cover - httpx always present in this app
        httpx = None  # type: ignore

    if httpx is not None:
        # Explicit HTTP status errors: retry only 5xx / 429.
        if isinstance(exc, httpx.HTTPStatusError):
            try:
                return is_transient_http_status(exc.response.status_code)
            except Exception:
                return False
        # Network / protocol level failures are transient.
        if isinstance(
            exc,
            (
                httpx.TimeoutException,
                httpx.ConnectError,
                httpx.ReadError,
                httpx.WriteError,
                httpx.RemoteProtocolError,
                httpx.PoolTimeout,
                httpx.NetworkError,
            ),
        ):
            return True

    # asyncio timeouts and low-level socket/connection errors.
    if isinstance(exc, (asyncio.TimeoutError, ConnectionError, OSError)):
        return True
    return False


def compute_backoff(attempt: int, config: RetryConfig) -> float:
    """Exponential backoff with symmetric jitter, capped at ``max_delay``.

    ``attempt`` is 1-based: attempt=1 is the delay after the first failure.
    """
    raw = config.base_delay * (config.backoff_factor ** (attempt - 1))
    raw = min(raw, config.max_delay)
    if config.jitter:
        delta = raw * config.jitter
        raw = raw + random.uniform(-delta, delta)
    return max(0.0, raw)


async def retry_async(
    fn: Callable[[], Awaitable[T]],
    *,
    config: Optional[RetryConfig] = None,
    is_transient: Callable[[BaseException], bool] = default_is_transient,
    on_retry: Optional[Callable[[int, BaseException, float], None]] = None,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> T:
    """Call the zero-arg async ``fn``, retrying transient failures.

    - At most ``config.max_attempts`` total attempts.
    - Retries only when ``is_transient(exc)`` is True.
    - Sleeps exponential-backoff-with-jitter between attempts (``sleep`` is
      injectable so tests run instantly).
    - Re-raises the ORIGINAL exception on a non-transient failure or once
      attempts are exhausted. ``asyncio.CancelledError`` (a ``BaseException``,
      not ``Exception``) is never caught, so cancellation propagates cleanly.
    """
    cfg = config or RetryConfig()
    attempt = 0
    last_exc: Optional[BaseException] = None

    while attempt < cfg.max_attempts:
        attempt += 1
        try:
            return await fn()
        except Exception as exc:  # noqa: BLE001 - re-raised below; excludes CancelledError
            last_exc = exc
            transient = False
            try:
                transient = bool(is_transient(exc))
            except Exception:  # pragma: no cover - predicate must not break retry
                transient = False

            if not transient or attempt >= cfg.max_attempts:
                raise

            delay = compute_backoff(attempt, cfg)
            logger.warning(
                "retry_async: attempt %d/%d failed (%s); backing off %.2fs",
                attempt,
                cfg.max_attempts,
                type(exc).__name__,
                delay,
            )
            if on_retry is not None:
                try:
                    on_retry(attempt, exc, delay)
                except Exception:  # pragma: no cover - callback must not break retry
                    pass
            await sleep(delay)

    # Defensive: loop always returns or raises above.
    if last_exc is not None:  # pragma: no cover
        raise last_exc
    raise RuntimeError("retry_async: no attempts were made")  # pragma: no cover
