"""BR-3.1/3.4/3.6/3.8 durable per-ORG usage ledger + per-org cap accounting.

Before BR-3 the ONLY metering Brigade did was a best-effort, fire-and-forget
Lago event (``app/integrations/lago.py``) keyed on the USER email — nothing
durable, nothing keyed on the org, and multi-replica-incorrect (there was no
shared cost-control state at all; the only in-memory counters were the pre-auth
flood-cap buckets in ``app/security/ratelimit.py``, a deliberate per-process
follow-up, NOT the billing ledger). This module is the durable cost-control
ledger BR-3.8 asks for: every metered execution path writes a ``usage_events``
row here, keyed on ``org_id`` (BR-3.1), and the per-org cap preflight (BR-3.6)
sums it.

It DELIBERATELY mirrors ``app/db/execution_store.py`` (the BR-4 durable-state
pattern): DEPENDENCY-LIGHT, lives in ``app.db`` so importing it never drags in
the heavy ``app.workflows`` / route stack, operates on plain scalars, and every
function is best-effort + LOUD — a transient DB error is logged, never raised,
so a metering hiccup can never turn a user's chat into a 500. The one exception
is the cap READ used by the preflight, which returns a safe default on error
(fail-OPEN on lookup failure — a DB blip must not wall every paying org; the
separate credits preflight already fails CLOSED).

Tenancy: writes use the RLS-exempt ``admin_session`` with an EXPLICIT ``org_id``
(metering frequently runs in a background task with no bound request-org — same
reason execution_store uses admin_session). The ``usage_events`` table itself
carries FULL RLS (see the 20260720_01 migration) so any request-session reader
(the future usage UI) is auto-scoped to its own org; this module's admin reads
pass an explicit ``org_id`` filter so they are correct regardless of the bound
GUC.
"""

from __future__ import annotations

import logging
import os
import uuid as _uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select

from app.db.database import admin_session
from app.db.models import OrgBillingConfig, UsageEvent

logger = logging.getLogger(__name__)


def _month_start(now: Optional[datetime] = None) -> datetime:
    """UTC calendar-month start — the default billing period boundary."""
    now = now or datetime.utcnow()
    return datetime(now.year, now.month, 1)


def _env_int(name: str) -> Optional[int]:
    raw = os.getenv(name, "").strip()
    if not raw:
        return None
    try:
        v = int(float(raw))
        return v if v > 0 else None
    except (TypeError, ValueError):
        return None


def _env_float(name: str) -> Optional[float]:
    raw = os.getenv(name, "").strip()
    if not raw:
        return None
    try:
        v = float(raw)
        return v if v > 0 else None
    except (TypeError, ValueError):
        return None


async def record_usage(
    *,
    org_id: Optional[str],
    user_id: Optional[str] = None,
    event_type: str = "ai_api_call",
    source: str = "unknown",
    agent_id: Optional[str] = None,
    model: Optional[str] = None,
    tokens: int = 0,
    cost: float = 0.0,
    rate_tier: Optional[str] = None,
    rate_multiplier: float = 1.0,
    outcome: Optional[str] = None,
    transaction_id: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """Append one durable ``usage_events`` row keyed on ``org_id``. Loud + safe.

    Returns the row id, or None if it couldn't be written (no org, or DB error).
    ``external_customer_id`` is set to ``org_id`` — the BR-3.1 billing subject.
    Metering without an org is a no-op: an event we can't attribute to a tenant
    is not billable and must never be filed against a shared/global identity.
    """
    if not org_id:
        logger.debug("record_usage: no org_id (source=%s) — skipping durable ledger", source)
        return None
    row_id = str(_uuid.uuid4())
    try:
        async with admin_session() as session:
            session.add(
                UsageEvent(
                    id=row_id,
                    org_id=str(org_id),
                    external_customer_id=str(org_id),  # BR-3.1
                    user_id=user_id,
                    event_type=event_type,
                    source=source,
                    agent_id=agent_id,
                    model=model,
                    tokens=int(tokens or 0),
                    cost=float(cost or 0.0),
                    rate_tier=rate_tier,
                    rate_multiplier=float(rate_multiplier or 1.0),
                    outcome=outcome,
                    transaction_id=transaction_id,
                    meta=meta or None,
                )
            )
            await session.commit()
        return row_id
    except Exception as exc:  # noqa: BLE001
        logger.error("BR-3 record_usage(org=%s, source=%s) failed: %s", org_id, source, exc)
        return None


async def org_period_usage(
    org_id: str,
    *,
    since: Optional[datetime] = None,
) -> Dict[str, float]:
    """Sum this org's usage since ``since`` (default: start of the UTC month).

    Returns ``{"tokens": int, "cost": float, "events": int, "since": iso}``.
    On any DB error returns zeros (so the cap check treats a lookup failure as
    "under cap" — fail-OPEN, see module docstring). Uses an EXPLICIT org filter
    on the admin (RLS-exempt) session so it is correct with no bound GUC.
    """
    period_start = since or _month_start()
    zero = {"tokens": 0, "cost": 0.0, "events": 0, "since": period_start.isoformat() + "Z"}
    if not org_id:
        return zero
    try:
        async with admin_session() as session:
            row = (
                await session.execute(
                    select(
                        func.coalesce(func.sum(UsageEvent.tokens), 0),
                        func.coalesce(func.sum(UsageEvent.cost), 0.0),
                        func.count(UsageEvent.id),
                    ).where(
                        UsageEvent.org_id == str(org_id),
                        UsageEvent.created_at >= period_start,
                    )
                )
            ).one()
        return {
            "tokens": int(row[0] or 0),
            "cost": float(row[1] or 0.0),
            "events": int(row[2] or 0),
            "since": period_start.isoformat() + "Z",
        }
    except Exception as exc:  # noqa: BLE001
        logger.error("BR-3 org_period_usage(org=%s) failed: %s", org_id, exc)
        return zero


async def get_org_cap(org_id: str) -> Dict[str, Any]:
    """Return this org's effective caps: its ``org_billing_config`` row if present,
    else the env defaults (``BRIGADE_DEFAULT_ORG_MONTHLY_TOKEN_CAP`` /
    ``BRIGADE_DEFAULT_ORG_MONTHLY_COST_CAP``; unset/0 => unlimited).

    Shape: ``{"monthly_token_cap": int|None, "monthly_cost_cap": float|None,
    "hard_stop": bool, "source": "config"|"env-default"}``. NULL cap = unlimited.
    """
    default = {
        "monthly_token_cap": _env_int("BRIGADE_DEFAULT_ORG_MONTHLY_TOKEN_CAP"),
        "monthly_cost_cap": _env_float("BRIGADE_DEFAULT_ORG_MONTHLY_COST_CAP"),
        "hard_stop": True,
        "source": "env-default",
    }
    if not org_id:
        return default
    try:
        async with admin_session() as session:
            cfg = await session.get(OrgBillingConfig, str(org_id))
            if cfg is None:
                return default
            return {
                "monthly_token_cap": int(cfg.monthly_token_cap) if cfg.monthly_token_cap else None,
                "monthly_cost_cap": float(cfg.monthly_cost_cap) if cfg.monthly_cost_cap else None,
                "hard_stop": bool(cfg.hard_stop),
                "source": "config",
            }
    except Exception as exc:  # noqa: BLE001
        logger.error("BR-3 get_org_cap(org=%s) failed: %s", org_id, exc)
        return default


async def org_over_cap(org_id: str) -> Dict[str, Any]:
    """Decide whether ``org_id`` is over its ceiling this period (BR-3.6).

    Returns ``{"over": bool, "reason": str|None, "usage": {...}, "cap": {...}}``.
    ``over`` is True only when a hard-stop cap is configured AND this period's
    usage meets/exceeds it. Unlimited caps (None) or ``hard_stop=False`` never
    trip. Fail-OPEN on error (never wall a tenant on a metering DB blip).
    """
    result = {"over": False, "reason": None, "usage": None, "cap": None}
    if not org_id:
        return result
    cap = await get_org_cap(org_id)
    result["cap"] = cap
    if not cap.get("hard_stop", True):
        return result
    token_cap = cap.get("monthly_token_cap")
    cost_cap = cap.get("monthly_cost_cap")
    if not token_cap and not cost_cap:
        return result  # unlimited
    usage = await org_period_usage(org_id)
    result["usage"] = usage
    if token_cap and usage["tokens"] >= token_cap:
        result["over"] = True
        result["reason"] = (
            f"monthly token cap reached: {usage['tokens']} >= {token_cap}"
        )
    elif cost_cap and usage["cost"] >= cost_cap:
        result["over"] = True
        result["reason"] = (
            f"monthly cost cap reached: ${usage['cost']:.4f} >= ${cost_cap:.4f}"
        )
    return result


async def set_org_cap(
    org_id: str,
    *,
    monthly_token_cap: Optional[int] = None,
    monthly_cost_cap: Optional[float] = None,
    hard_stop: bool = True,
    notes: Optional[str] = None,
) -> bool:
    """Upsert an org's cap config (ops / admin helper; also used by the proof).
    Loud + safe; returns True on success."""
    if not org_id:
        return False
    try:
        async with admin_session() as session:
            cfg = await session.get(OrgBillingConfig, str(org_id))
            if cfg is None:
                session.add(
                    OrgBillingConfig(
                        org_id=str(org_id),
                        monthly_token_cap=monthly_token_cap,
                        monthly_cost_cap=monthly_cost_cap,
                        hard_stop=hard_stop,
                        notes=notes,
                    )
                )
            else:
                cfg.monthly_token_cap = monthly_token_cap
                cfg.monthly_cost_cap = monthly_cost_cap
                cfg.hard_stop = hard_stop
                if notes is not None:
                    cfg.notes = notes
            await session.commit()
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error("BR-3 set_org_cap(org=%s) failed: %s", org_id, exc)
        return False


async def list_org_usage(
    org_id: str,
    *,
    limit: int = 100,
    since: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    """Return recent usage rows for an org (newest first) — feeds the usage UI /
    admin introspection. Explicit org filter on the admin session."""
    if not org_id:
        return []
    try:
        async with admin_session() as session:
            q = select(UsageEvent).where(UsageEvent.org_id == str(org_id))
            if since is not None:
                q = q.where(UsageEvent.created_at >= since)
            q = q.order_by(UsageEvent.created_at.desc()).limit(limit)
            rows = (await session.execute(q)).scalars().all()
        return [r.to_dict() for r in rows]
    except Exception as exc:  # noqa: BLE001
        logger.error("BR-3 list_org_usage(org=%s) failed: %s", org_id, exc)
        return []
