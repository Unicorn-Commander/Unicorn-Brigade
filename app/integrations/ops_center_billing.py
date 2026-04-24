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

_UNKNOWN: Dict[str, object] = {
    "paid": False,
    "subscription_tier": None,
    "credits_remaining": 0.0,
    "as_of": None,
}


async def get_billing_state(user_email: str) -> Dict[str, object]:
    """Return the billing state dict for ``user_email``. Cached 30s."""
    if not user_email:
        return dict(_UNKNOWN)

    now = time.monotonic()
    cached = _cache.get(user_email)
    if cached and (now - cached[0]) < _CACHE_TTL:
        return cached[1]

    if not BRIGADE_SERVICE_KEY:
        logger.debug("BRIGADE_SERVICE_KEY not set; billing preflight disabled")
        return dict(_UNKNOWN)

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
            _cache[user_email] = (now, data)
            return data
        logger.warning(
            f"billing/state returned {r.status_code} for {user_email}: "
            f"{r.text[:200]}"
        )
    except Exception as e:
        logger.warning(f"billing/state lookup failed for {user_email}: {e}")

    return dict(_UNKNOWN)


def invalidate(user_email: str) -> None:
    """Drop the cached entry for ``user_email`` (e.g. after a known credit change)."""
    _cache.pop(user_email, None)
