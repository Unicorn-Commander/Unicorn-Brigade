"""BR-3.4 unified metering primitive — the ONE place an execution path records
that it consumed LLM/tool resources, keyed on the caller's ORG (BR-3.1).

Before BR-3 only two paths metered (agent chat + the non-streaming openai-compat
shim), each hand-rolling its own Lago calls; A2A invoke, MCP tool calls,
hierarchical workflows, scheduled runs, orchestration missions, and the
STREAMING shim recorded nothing. This module gives every path a single call —
``meter_usage(...)`` — that:

  1. writes ONE durable ``usage_events`` row (the cap-authoritative record, keyed
     on org) via ``app.db.usage_ledger.record_usage``; and
  2. emits the existing best-effort Lago events (COGS ``ai_api_call`` for
     local-GPU token cost + per-agent ``agent_work`` value), now keyed on the org
     as ``external_customer_id``.

Exactly ONE ledger row is written per metered call (carrying the billable
tokens+cost the BR-3.6 cap sums); ``agent_work`` stays a Lago-only value signal
so the cap is never double-counted. Best-effort + LOUD-but-swallowed: a metering
failure is logged, never raised — a billing hiccup must not turn a user's
request into a 500.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

logger = logging.getLogger(__name__)


def _is_admin_role(user: Any) -> bool:
    """True when ``user``'s role is admin — duck-typed so this dependency-light
    module never imports app.auth (keeping it importable under a minimal
    interpreter, like the billing proof / the RLS proof's app.db import)."""
    role = getattr(user, "role", None)
    val = getattr(role, "value", role)
    return str(val).lower() == "admin"


async def enforce_org_cap_or_402(user: Any) -> None:
    """BR-3.6: raise ``402`` when the caller's ORG is over its monthly usage
    ceiling. The per-ORG half of the chat/exec preflight (the per-USER credits
    check lives in agent_routes). Sums the durable ``usage_events`` ledger for the
    org's current period vs its configured cap (``org_billing_config`` or the env
    default) via ``org_over_cap``. Admins never trip; an unlimited cap or
    ``hard_stop=False`` never trips; and a metering-DB blip fails OPEN
    (``org_over_cap`` returns ``over=False`` on error) so a hiccup can't wall a
    paying org.

    Lives HERE (not in agent_routes) so it is importable without agent_routes'
    heavy optional deps — every preflight site (agent chat, MLX, the openai-compat
    passthrough/dual-layer, and the streaming shim BR-3.5) calls this same
    function, and the BR-3 proof drives it directly."""
    from app.db.usage_ledger import org_over_cap

    if not user or _is_admin_role(user):
        return
    org_id = getattr(user, "org_id", None)
    if not org_id:
        return
    decision = await org_over_cap(str(org_id))
    if decision.get("over"):
        usage = decision.get("usage") or {}
        cap = decision.get("cap") or {}
        raise HTTPException(
            status_code=402,
            detail={
                "error": "org_cap_reached",
                "message": (
                    "Your organization has reached its usage cap for this period. "
                    "Raise the cap or wait for the next period to continue."
                ),
                "reason": decision.get("reason"),
                "usage": usage,
                "monthly_token_cap": cap.get("monthly_token_cap"),
                "monthly_cost_cap": cap.get("monthly_cost_cap"),
                "scope": "org",
            },
        )


def approx_tokens(*texts: Optional[str]) -> int:
    """Rough token estimate (~4 chars/token) for paths where the upstream did not
    report ``usage`` — notably streamed responses without an include_usage tail.
    Deliberately conservative + cheap; real usage is preferred when present."""
    total_chars = sum(len(t) for t in texts if t)
    return max(0, total_chars // 4)


async def meter_usage(
    *,
    org_id: Optional[str],
    user: Optional[str] = None,
    source: str,
    model: Optional[str] = None,
    tokens: int = 0,
    cost: Optional[float] = None,
    agent_id: Optional[str] = None,
    agent_name: Optional[str] = None,
    agent_domain: Optional[str] = None,
    tools_used: Optional[List[str]] = None,
    used_rag: Optional[bool] = None,
    rate_tier: Optional[str] = None,
    rate_multiplier: float = 1.0,
    outcome: str = "success",
    event_type: Optional[str] = None,
    is_local: Optional[bool] = None,
    provider: Optional[str] = None,
    emit_value: bool = True,
    meta: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """Record one metered unit of work against ``org_id``. Returns the durable
    ledger row id (or None). NEVER raises.

    * ``cost`` — when None it is derived from ``tokens`` for local-GPU routes
      (``estimate_local_cost``); cloud/gateway routes cost 0 here (they meter
      their own COGS upstream).
    * ``is_local`` — whether this was a local-GPU call (COGS billable here). When
      None it is inferred from ``provider``/``model`` via ``is_local_route``.
    * ``event_type`` — defaults to 'ai_api_call' when tokens>0 else 'tool_call'.
    """
    # Lazy imports keep this module import-light + cycle-free (routes import us).
    from app.db.usage_ledger import record_usage
    from app.integrations.lago import (
        emit_agent_work,
        emit_ai_api_call,
        estimate_local_cost,
        is_local_route,
        rag_used,
    )

    tools_used = [t for t in (tools_used or []) if t]
    if used_rag is None:
        used_rag = rag_used(tools_used)
    if is_local is None:
        is_local = is_local_route(provider, model)
    if cost is None:
        cost = estimate_local_cost(tokens) if (is_local and tokens > 0) else 0.0
    if event_type is None:
        event_type = "ai_api_call" if tokens > 0 else "tool_call"

    ledger_meta: Dict[str, Any] = dict(meta or {})
    if tools_used:
        ledger_meta.setdefault("tools_used", tools_used)
    if provider:
        ledger_meta.setdefault("provider", provider)

    # 1) Durable, cap-authoritative ledger row (keyed on org). Source of truth.
    row_id = None
    try:
        row_id = await record_usage(
            org_id=org_id,
            user_id=user,
            event_type=event_type,
            source=source,
            agent_id=agent_id,
            model=model,
            tokens=int(tokens or 0),
            cost=float(cost or 0.0),
            rate_tier=rate_tier,
            rate_multiplier=rate_multiplier,
            outcome=outcome,
            meta=ledger_meta or None,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("meter_usage ledger write failed (source=%s): %s", source, exc)

    # 2) Best-effort Lago legs (unchanged semantics; now keyed on org). Only when
    #    we have a user handle (Lago customers are keyed by the human today) —
    #    the durable ledger above already captured the org attribution regardless.
    if user:
        # COGS — local-GPU token cost, mirrored to the deduction webhook.
        if is_local and tokens > 0:
            try:
                await emit_ai_api_call(
                    user=user, model=model or "unknown", tokens=int(tokens),
                    cost=float(cost or estimate_local_cost(tokens)),
                    agent_id=agent_id, agent_name=agent_name, agent_domain=agent_domain,
                    tools_used=tools_used or None, used_rag=used_rag,
                    rate_tier=rate_tier, rate_multiplier=rate_multiplier,
                    org_id=org_id,
                )
            except Exception as exc:  # noqa: BLE001
                logger.debug("meter_usage COGS emit skipped (source=%s): %s", source, exc)
        # Per-agent VALUE event (no webhook; charges nothing until a plan exists).
        if emit_value and agent_id:
            try:
                await emit_agent_work(
                    user=user, agent_id=agent_id, model=model, tokens=int(tokens or 0),
                    outcome=outcome, agent_name=agent_name, agent_domain=agent_domain,
                    tools_used=tools_used or None, used_rag=used_rag,
                    rate_tier=rate_tier or "standard", rate_multiplier=rate_multiplier,
                    org_id=org_id,
                )
            except Exception as exc:  # noqa: BLE001
                logger.debug("meter_usage value emit skipped (source=%s): %s", source, exc)

    return row_id
