# Executed by Grok (headless lane)
"""
Phase 7.2/7.3 — Brigade-side client for Ops-Center's ``/api/v1/billing/state``.

Chat endpoints use this to:
  * decide whether to 402 a non-admin user who's out of credits
  * populate ``user_attrs["paid"]`` for per-agent RBAC policies

The client caches per-user for ``_CACHE_TTL`` seconds, hits and misses alike,
so one chat turn does not open a connection per gate.

On any network / auth failure we return an "unknown" state
(``lookup="unavailable"``). The chat gate (``_enforce_billing_or_402``) fails
open on that state: it does not 402. It logs one advisory WARNING per caller
per ``_ADVISORY_LOG_INTERVAL`` instead of an error on every request.
``BRIGADE_BILLING_STRICT=true`` is the opt-in that turns the same state into
a 503. An authoritative ``lookup="ok"`` with no credits and no paid plan is
still a 402.
"""

import logging
import os
import time

import httpx

logger = logging.getLogger(__name__)

OPS_CENTER_URL = os.getenv("OPS_CENTER_URL", "http://ops-center-direct:8084").rstrip("/")
BRIGADE_SERVICE_KEY = os.getenv("BRIGADE_SERVICE_KEY", "")

_CACHE_TTL = 30.0
_cache: dict[str, tuple[float, dict[str, object]]] = {}

# Advisory (fail-open) misses are WARNING at most once per caller per window.
# A dead preflight must not paint every chat line as an error. The Prometheus
# counter still increments on each real lookup attempt.
_ADVISORY_LOG_INTERVAL = 600.0
_advisory_logged_at: dict[str, float] = {}

# ``lookup`` is the load-bearing field: "ok" means Ops-Center ANSWERED and this
# is its authoritative view of the account. "unavailable" means we never got an
# answer — unreachable, timeout, 5xx, 401, or the route does not exist. The two
# must never be conflated, because "you have zero credits" and "we could not ask
# whether you have credits" are opposite facts about a paying customer.
_UNKNOWN: dict[str, object] = {
    "paid": False,
    "subscription_tier": None,
    "credits_remaining": 0.0,
    "as_of": None,
    "lookup": "unavailable",
}


def _unknown(reason: str) -> dict[str, object]:
    d = dict(_UNKNOWN)
    d["lookup_error"] = reason
    return d


def _log_advisory(caller: str, message: str, *args: object) -> None:
    """WARNING once per caller per interval; suppressed repeats are DEBUG.

    Never ERROR. On the fail-open path a billing miss is not a failed chat.
    The dedupe key is case-folded so the HTTP client and the chat gate share
    one window for the same email.
    """
    now = time.monotonic()
    key = (caller or "<unknown>").strip().lower()
    last = _advisory_logged_at.get(key)
    if last is not None and (now - last) < _ADVISORY_LOG_INTERVAL:
        logger.debug(message, *args)
        return
    _advisory_logged_at[key] = now
    logger.warning(message, *args)


async def get_billing_state(user_email: str) -> dict[str, object]:
    """Return the billing state dict for ``user_email``. Cached 30s.

    Failures are cached for the same TTL as a hit. A 401 or a timeout is an
    infrastructure fact about this caller, not something that changes between
    messages in a turn.
    """
    if not user_email:
        return _unknown("no user email on the request")

    now = time.monotonic()
    cached = _cache.get(user_email)
    if cached and (now - cached[0]) < _CACHE_TTL:
        return cached[1]

    if not BRIGADE_SERVICE_KEY:
        logger.debug("BRIGADE_SERVICE_KEY not set; billing preflight disabled")
        return _unknown("BRIGADE_SERVICE_KEY not configured")

    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(
                f"{OPS_CENTER_URL}/api/v1/billing/state",
                headers={
                    "X-Service-Key": BRIGADE_SERVICE_KEY,
                    "X-User-ID": user_email,
                },
            )
        if r.status_code == 200:
            data = r.json()
            # Ops-Center answered. Mark it authoritative unless it said otherwise.
            data.setdefault("lookup", "ok")
            _cache[user_email] = (now, data)
            return data
        # Non-200 is an infrastructure miss, not a verdict on this account.
        # The chat gate fails open. One WARNING per caller per interval — an
        # ERROR on every chat hides real errors. Cached like a hit.
        result = _unknown(f"HTTP {r.status_code}")
        _cache[user_email] = (now, result)
        _record_unavailable(str(r.status_code))
        _log_advisory(
            user_email,
            "BILLING LOOKUP ADVISORY — billing/state returned %s for %s: %s. "
            "Not blocking the caller (fail-open): an unreachable billing "
            "service is not evidence of an empty balance. Repeats for this "
            "caller are debug-only for %ss.",
            r.status_code,
            user_email,
            r.text[:200],
            int(_ADVISORY_LOG_INTERVAL),
        )
        return result
    except Exception as e:
        result = _unknown(f"{type(e).__name__}: {e}")
        _cache[user_email] = (now, result)
        _record_unavailable(type(e).__name__)
        _log_advisory(
            user_email,
            "BILLING LOOKUP ADVISORY — billing/state lookup failed for %s: %s. "
            "Not blocking the caller (fail-open). Repeats for this caller are "
            "debug-only for %ss.",
            user_email,
            e,
            int(_ADVISORY_LOG_INTERVAL),
        )
        return result


def _record_unavailable(reason: str) -> None:
    """Count billing-lookup outages so a dead dependency is visible on the
    dashboard instead of quietly waving every caller through (or, before this
    change, quietly 402-ing every caller)."""
    try:
        from app.observability.metrics import billing_lookup_unavailable
        billing_lookup_unavailable.labels(reason=reason).inc()
    except Exception:  # noqa: BLE001 - metrics must never break a chat
        pass


def invalidate(user_email: str) -> None:
    """Drop the cached entry for ``user_email`` (e.g. after a known credit change)."""
    _cache.pop(user_email, None)
