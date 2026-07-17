"""BR-3.7 — usage / billing surface for the UI.

The BR-3.1/3.4/3.6/3.8 billing CORE (durable per-org usage ledger + per-org caps
+ Ops-Center credits) already exists in ``app/db/usage_ledger.py`` and
``app/integrations/ops_center_billing.py`` — but nothing exposed it to a customer.
This router closes that gap so a paying org can SEE its spend and so the frontend
can turn the backend's carefully-built 402 (``credits_remaining`` + ``tier``) into
an upgrade path instead of a dead-end generic error.

Two endpoints, both scoped to the CALLER's active org (``user.org_id``, bound by
``_bind_org_context``); a caller with no bound org (master/service key) gets an
empty-but-valid shape rather than another tenant's numbers:

- GET /api/v1/billing/usage              — this period's spend + caps + recent rows
- GET /api/v1/billing/upgrade-requirements — real data for the UpgradePrompt / 402
"""

import logging
import os
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query

from app.auth.middleware import require_api_key, AuthUser
from app.auth.roles import UserRole, derive_user_tier
from app.db.usage_ledger import (
    org_period_usage,
    get_org_cap,
    org_over_cap,
    list_org_usage,
)
from app.integrations.ops_center_billing import get_billing_state

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["billing"])


def _ops_center_base() -> str:
    """PUBLIC, browser-reachable base URL of Ops-Center (where checkout / plans live).

    Deliberately does NOT fall back to ``OPS_CENTER_URL`` — that is the
    server-to-server URL (e.g. an internal ``http://ops-center-direct:8084``) a
    customer's browser cannot reach. The upgrade CTA must be a public URL, so we
    use ``OPS_CENTER_PUBLIC_URL`` when set and otherwise the public marketing host.
    """
    return (
        os.getenv("OPS_CENTER_PUBLIC_URL")
        or "https://unicorncommander.ai"
    ).rstrip("/")


def _checkout_url(feature: Optional[str] = None) -> str:
    """Deep-link into the Ops-Center upgrade/checkout flow.

    ``BRIGADE_UPGRADE_URL`` overrides the whole URL; otherwise we build one off
    the Ops-Center base. ``feature`` (when present) is passed through so the
    checkout page can highlight what the user was trying to unlock.
    """
    override = os.getenv("BRIGADE_UPGRADE_URL", "").strip()
    base = override or f"{_ops_center_base()}/plans.html"
    if feature:
        sep = "&" if "?" in base else "?"
        return f"{base}{sep}feature={feature}"
    return base


async def _billing_for(user: AuthUser) -> dict:
    """Ops-Center credits/tier for this user (admins are effectively unlimited)."""
    if user and user.role == UserRole.ADMIN:
        return {"paid": True, "credits_remaining": None, "subscription_tier": "admin"}
    email = (getattr(user, "email", "") or "").lower()
    if not email:
        return {"paid": False, "credits_remaining": 0.0, "subscription_tier": None}
    return await get_billing_state(email)


@router.get("/usage")
async def get_usage(
    user: Annotated[AuthUser, Depends(require_api_key)],
    limit: int = Query(50, ge=1, le=200),
):
    """This org's current-period usage, effective caps, and recent events.

    RLS-scoped by construction: the numbers are the caller's OWN org
    (``user.org_id``); a keyless/service identity with no bound org gets zeros.
    """
    org_id = getattr(user, "org_id", None)
    billing = await _billing_for(user)

    if not org_id:
        # No tenant bound (master/service key). Return a valid empty shape rather
        # than leaking or erroring — the UI renders "no org / no usage".
        return {
            "org_id": None,
            "period": {"tokens": 0, "cost": 0.0, "events": 0, "since": None},
            "cap": await get_org_cap(""),
            "over_cap": False,
            "over_cap_reason": None,
            "recent": [],
            "billing": billing,
        }

    period = await org_period_usage(org_id)
    cap = await get_org_cap(org_id)
    over = await org_over_cap(org_id)
    recent = await list_org_usage(org_id, limit=limit)

    return {
        "org_id": str(org_id),
        "period": period,
        "cap": cap,
        "over_cap": bool(over.get("over")),
        "over_cap_reason": over.get("reason"),
        "recent": recent,
        "billing": billing,
    }


@router.get("/upgrade-requirements")
async def get_upgrade_requirements(
    user: Annotated[AuthUser, Depends(require_api_key)],
    feature: Optional[str] = Query(None),
):
    """Real data for the UpgradePrompt / 402 interceptor (replaces the FE mock).

    Surfaces the user's current tier + credits and a deep-link into the
    Ops-Center checkout so the highest willingness-to-pay moment (a 402 or a
    locked feature) resolves into an actual upgrade, not a dead end.
    """
    billing = await _billing_for(user)
    tier = derive_user_tier((getattr(user, "email", "") or ""), user.role if user else None)
    return {
        "feature": feature,
        "currentTier": billing.get("subscription_tier") or tier,
        "paid": bool(billing.get("paid")),
        "creditsRemaining": billing.get("credits_remaining"),
        "requiredTier": "professional",
        "benefits": [
            "Higher monthly usage limits",
            "Priority model routing",
            "Full agent + workflow access",
            "Priority support",
        ],
        "upgradeUrl": _checkout_url(feature),
        "opsCenterUrl": _ops_center_base(),
    }
