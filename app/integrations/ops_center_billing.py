"""
Phase 7.2/7.3 — Brigade-side client for Ops-Center's ``/api/v1/billing/state``.

Chat endpoints use this to:
  * decide whether to 402 a non-admin user who's out of credits
  * populate ``user_attrs["paid"]`` for per-agent RBAC policies

The client caches per-user for ``_CACHE_TTL`` seconds so a single turn of a
chat (which hits RBAC + preflight + potentially more) doesn't trigger three
round-trips to ops-center.

On any network / auth failure we return an "unknown" state (paid=False,
credits=0). The caller (``agent_routes``) then treats that as
"no-credits, no-paid-subscription" — which blocks non-admins the same as
a confirmed empty balance. That's the correct fail-safe: if billing is
unreachable, pausing free-tier chat is better than giving away inference.
"""

import logging
import os
import time
from typing import Dict, Tuple

import httpx

logger = logging.getLogger(__name__)

OPS_CENTER_URL = os.getenv("OPS_CENTER_URL", "http://ops-center-direct:8084").rstrip("/")
BRIGADE_SERVICE_KEY = os.getenv("BRIGADE_SERVICE_KEY", "")

_CACHE_TTL = 30.0
_cache: Dict[str, Tuple[float, Dict[str, object]]] = {}

# ``lookup`` is the load-bearing field: "ok" means Ops-Center ANSWERED and this
# is its authoritative view of the account. "unavailable" means we never got an
# answer — unreachable, timeout, 5xx, 401, or the route does not exist. The two
# must never be conflated, because "you have zero credits" and "we could not ask
# whether you have credits" are opposite facts about a paying customer.
_UNKNOWN: Dict[str, object] = {
    "paid": False,
    "subscription_tier": None,
    "credits_remaining": 0.0,
    "as_of": None,
    "lookup": "unavailable",
}


def _unknown(reason: str) -> Dict[str, object]:
    d = dict(_UNKNOWN)
    d["lookup_error"] = reason
    return d


async def get_billing_state(user_email: str) -> Dict[str, object]:
    """Return the billing state dict for ``user_email``. Cached 30s."""
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
        # Any non-200 is an INFRASTRUCTURE failure, not a verdict on this account.
        # ERROR, not warning: as of 2026-08-11 this route has never existed in
        # Ops-Center (the billing router has /plans,/invoices,/cycle,/summary and
        # no /state), so the 401 from its global auth gate is really a masked 404
        # and EVERY non-admin caller was being told they were out of credits.
        logger.error(
            "BILLING LOOKUP UNAVAILABLE — billing/state returned %s for %s: %s. "
            "Not blocking the caller: an unreachable billing service is not "
            "evidence of an empty balance.",
            r.status_code, user_email, r.text[:200],
        )
        _record_unavailable(str(r.status_code))
        return _unknown(f"HTTP {r.status_code}")
    except Exception as e:
        logger.error(
            "BILLING LOOKUP UNAVAILABLE — billing/state lookup failed for %s: %s. "
            "Not blocking the caller.", user_email, e,
        )
        _record_unavailable(type(e).__name__)
        return _unknown(f"{type(e).__name__}: {e}")


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
