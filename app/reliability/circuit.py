"""Minimal, dependency-free async circuit breaker (BR-4 reliability).

Wraps outbound calls (the LLM client) so a struggling backend fails fast
instead of piling up hung requests.

States
------
CLOSED     Calls flow through; consecutive *counted* failures accumulate.
OPEN       Calls are rejected immediately with ``CircuitOpenError`` until the
           cooldown elapses.
HALF_OPEN  A single trial call is allowed through. Success closes the breaker;
           failure re-opens it for another cooldown. Concurrent calls during
           HALF_OPEN are fast-failed so only one probe runs at a time.

Only failures that ``is_failure(exc)`` accepts count toward opening the
breaker. The LLM client passes ``default_is_transient`` so deterministic
client errors (HTTP 4xx) never trip it — those are the caller's problem, not a
backend-health signal.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from enum import Enum
from typing import Awaitable, Callable, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(Exception):
    """Raised when a call is rejected because the breaker is OPEN."""

    def __init__(self, name: str, retry_after: float):
        self.name = name
        self.retry_after = retry_after
        super().__init__(
            f"circuit '{name}' is OPEN; retry in {retry_after:.1f}s"
        )


class CircuitBreaker:
    """Async circuit breaker with a CLOSED → OPEN → HALF_OPEN → CLOSED cycle."""

    def __init__(
        self,
        name: str = "default",
        failure_threshold: int = 5,
        cooldown_seconds: float = 30.0,
        is_failure: Optional[Callable[[BaseException], bool]] = None,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.name = name
        self.failure_threshold = max(1, int(failure_threshold))
        self.cooldown_seconds = float(cooldown_seconds)
        self._is_failure = is_failure
        self._clock = clock

        self._state = CircuitState.CLOSED
        self._failures = 0
        self._opened_at = 0.0
        self._probe_in_flight = False
        self._lock = asyncio.Lock()

    @classmethod
    def from_env(
        cls,
        name: str = "default",
        is_failure: Optional[Callable[[BaseException], bool]] = None,
        **overrides,
    ) -> "CircuitBreaker":
        def _int(env: str, default: int) -> int:
            try:
                raw = os.getenv(env)
                return int(raw) if raw not in (None, "") else default
            except (TypeError, ValueError):
                return default

        def _float(env: str, default: float) -> float:
            try:
                raw = os.getenv(env)
                return float(raw) if raw not in (None, "") else default
            except (TypeError, ValueError):
                return default

        cfg = dict(
            failure_threshold=_int("LLM_CIRCUIT_FAILURE_THRESHOLD", 5),
            cooldown_seconds=_float("LLM_CIRCUIT_COOLDOWN_SECONDS", 30.0),
        )
        cfg.update(overrides)
        return cls(name=name, is_failure=is_failure, **cfg)

    # ── introspection ─────────────────────────────────────────
    @property
    def state(self) -> CircuitState:
        return self._state

    @property
    def failure_count(self) -> int:
        return self._failures

    def _seconds_until_half_open(self) -> float:
        return max(0.0, self.cooldown_seconds - (self._clock() - self._opened_at))

    # ── gate + transitions ────────────────────────────────────
    async def _before_call(self) -> None:
        async with self._lock:
            if self._state == CircuitState.OPEN:
                if self._seconds_until_half_open() <= 0:
                    # Cooldown elapsed — let exactly one probe through.
                    self._state = CircuitState.HALF_OPEN
                    self._probe_in_flight = True
                    logger.info("circuit '%s' -> HALF_OPEN (probing recovery)", self.name)
                    return
                raise CircuitOpenError(self.name, self._seconds_until_half_open())

            if self._state == CircuitState.HALF_OPEN:
                if self._probe_in_flight:
                    # A probe is already testing recovery; reject the rest.
                    raise CircuitOpenError(self.name, self._seconds_until_half_open())
                self._probe_in_flight = True
            # CLOSED: allow through.

    async def _on_success(self) -> None:
        async with self._lock:
            if self._state != CircuitState.CLOSED:
                logger.info("circuit '%s' -> CLOSED (recovered)", self.name)
            self._state = CircuitState.CLOSED
            self._failures = 0
            self._probe_in_flight = False

    async def _on_failure(self) -> None:
        async with self._lock:
            self._failures += 1
            self._probe_in_flight = False
            if self._state == CircuitState.HALF_OPEN:
                # Probe failed — straight back to OPEN for another cooldown.
                self._state = CircuitState.OPEN
                self._opened_at = self._clock()
                logger.warning("circuit '%s' -> OPEN (recovery probe failed)", self.name)
            elif self._failures >= self.failure_threshold:
                self._state = CircuitState.OPEN
                self._opened_at = self._clock()
                logger.warning(
                    "circuit '%s' -> OPEN after %d consecutive failures",
                    self.name,
                    self._failures,
                )

    def _counts_as_failure(self, exc: BaseException) -> bool:
        if self._is_failure is None:
            return True
        try:
            return bool(self._is_failure(exc))
        except Exception:  # pragma: no cover - predicate must not break the breaker
            return True

    async def call(self, fn: Callable[[], Awaitable[T]]) -> T:
        """Run ``fn`` under the breaker.

        Raises ``CircuitOpenError`` immediately when OPEN. Otherwise runs
        ``fn``; a counted failure advances the breaker toward OPEN, a success
        resets it. Non-counted exceptions (e.g. client 4xx) propagate without
        affecting breaker state.
        """
        await self._before_call()
        try:
            result = await fn()
        except Exception as exc:  # noqa: BLE001 - excludes CancelledError; re-raised below
            if self._counts_as_failure(exc):
                await self._on_failure()
            else:
                # Neither a health failure nor a success — release the probe
                # slot without changing failure counters.
                async with self._lock:
                    self._probe_in_flight = False
            raise
        else:
            await self._on_success()
            return result
