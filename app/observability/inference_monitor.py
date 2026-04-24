"""
Phase 7b.2 — Brigade-side monitoring for local inference backends.

Every LLM call from Brigade goes through an OpenAI-compatible endpoint
(``OPS_CENTER_LLM_ENDPOINT``, ``MIDBOY1_LLM_URL``, ``MEMORY_LLM_BASE_URL``,
…). When one of those starts connection-refusing, the user-facing symptom
is a chat 500. Without structured signal, nobody knows *which* backend
dropped until someone digs through logs.

This module is a tiny in-memory failure counter with jittered backoff on
the log emission so a hard-down endpoint doesn't spam warnings every
second while cron-scale callers hammer it.

Contract:
  observe(endpoint, success=True)              — on a successful call
  observe(endpoint, success=False, error=msg)  — on a failure

After three *consecutive* failures for the same endpoint we emit one
structured ``inference_backend_down`` WARNING. Further failures in the
same backoff window (grows exponentially 30s → 60s → 120s → ... capped)
are silent. A single success resets the counter.
"""

import logging
import os
import random
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("brigade.inference_monitor")

# How many consecutive failures before we log the first warning.
_FAIL_THRESHOLD = int(os.getenv("INFERENCE_MONITOR_FAIL_THRESHOLD", "3"))
# Initial backoff after first log (seconds). Doubles each subsequent log,
# capped at _MAX_BACKOFF.
_INITIAL_BACKOFF_S = float(os.getenv("INFERENCE_MONITOR_INITIAL_BACKOFF", "30"))
_MAX_BACKOFF_S = float(os.getenv("INFERENCE_MONITOR_MAX_BACKOFF", "900"))
_JITTER_S = 2.0


@dataclass
class _State:
    consecutive_failures: int = 0
    last_error: Optional[str] = None
    last_log_at: float = 0.0  # monotonic
    current_backoff_s: float = _INITIAL_BACKOFF_S
    ever_down: bool = False


_states: dict = {}
_lock = threading.Lock()


def _next_backoff(prev: float) -> float:
    return min(prev * 2.0, _MAX_BACKOFF_S)


def observe(endpoint: str, success: bool, error: Optional[str] = None) -> None:
    """Record an outcome against ``endpoint``.

    ``endpoint`` is the human-readable backend URL; use a stable form (e.g.
    base URL without query params) so counts aggregate.
    """
    if not endpoint:
        return

    now = time.monotonic()
    with _lock:
        st = _states.setdefault(endpoint, _State())

        if success:
            if st.consecutive_failures >= _FAIL_THRESHOLD and st.ever_down:
                logger.info(
                    "inference_backend_recovered endpoint=%s prior_failures=%d",
                    endpoint, st.consecutive_failures,
                )
            st.consecutive_failures = 0
            st.last_error = None
            st.current_backoff_s = _INITIAL_BACKOFF_S
            st.ever_down = False
            return

        st.consecutive_failures += 1
        st.last_error = error or "unknown"

        if st.consecutive_failures < _FAIL_THRESHOLD:
            return

        # Eligible to log. Respect backoff window.
        if (now - st.last_log_at) < st.current_backoff_s:
            return

        jitter = random.uniform(0, _JITTER_S)
        logger.warning(
            "inference_backend_down endpoint=%s error=%r consecutive_failures=%d "
            "backoff_s=%.1f (next check after ~%.1fs)",
            endpoint, st.last_error, st.consecutive_failures,
            st.current_backoff_s, st.current_backoff_s + jitter,
        )
        st.last_log_at = now + jitter  # effective next window starts now + jitter
        st.ever_down = True
        st.current_backoff_s = _next_backoff(st.current_backoff_s)


def snapshot() -> dict:
    """Return a copy of current state for introspection (tests / debug)."""
    with _lock:
        return {
            ep: {
                "consecutive_failures": st.consecutive_failures,
                "last_error": st.last_error,
                "current_backoff_s": st.current_backoff_s,
                "ever_down": st.ever_down,
            }
            for ep, st in _states.items()
        }


def reset(endpoint: Optional[str] = None) -> None:
    """Reset state. Pass an endpoint to clear just one, or None for all."""
    with _lock:
        if endpoint is None:
            _states.clear()
        else:
            _states.pop(endpoint, None)
