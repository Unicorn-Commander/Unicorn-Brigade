"""
Phase 7.1 — Minimal async Lago client for Brigade.

Brigade chat endpoints bypass LiteLLM (they hit the local GPU router
directly), so LiteLLM's own ``success_callback: lago`` doesn't cover them.
This module plugs that gap: after a chat completes we emit a single
``ai_api_call`` event matching the shape LiteLLM would have sent.

Emission is best-effort: errors are logged and swallowed so a transient
Lago hiccup never turns into a 500 for the user.

Event shape (top-level schema mirrors lago_integration.record_usage in
ops-center, so events are filed consistently regardless of producer):

    {
      "event": {
        "transaction_id": "brigade-<uuid>",
        "external_customer_id": "<user>",
        "code": "ai_api_call",
        "timestamp": <unix>,
        "properties": {
            "model":  "<model name>",
            "tokens": "<total_tokens>",
            "cost":   "<dollars, 8dp>",
            "user":   "<user>"
        }
      }
    }
"""

import logging
import os
import uuid as _uuid
from datetime import datetime
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

LAGO_API_URL = os.getenv("LAGO_API_URL", "").rstrip("/")
LAGO_API_KEY = os.getenv("LAGO_API_KEY", "")

# Ops-Center webhook mirror target. Phase 7b.1 routes per-event credit
# deduction through the same webhook handler Lago (eventually) will use, so
# deductions land immediately rather than waiting for Lago to aggregate into
# an invoice. When OPS_CENTER_URL isn't set (dev/tests), mirroring is a no-op.
OPS_CENTER_URL = os.getenv("OPS_CENTER_URL", "").rstrip("/")

# Flat local-GPU rate used for MVP metering. Cloud-routed calls are NOT
# metered here — LiteLLM emits its own ai_api_call events for those.
LOCAL_COST_PER_1K_TOKENS = 0.0001


def estimate_local_cost(tokens: int) -> float:
    """Cost in USD for ``tokens`` tokens on the local GPU path."""
    if tokens <= 0:
        return 0.0
    return round((tokens / 1000.0) * LOCAL_COST_PER_1K_TOKENS, 8)


def is_local_route(provider: Optional[str], model: Optional[str]) -> bool:
    """Decide whether a given chat response represents a local-GPU call.

    We meter locally when the response came from a non-LiteLLM, non-OpenRouter
    path. Anything that went through ops-center → LiteLLM is already metered.
    """
    prov = (provider or "").lower()
    if prov in ("ops-center", "litellm", "openrouter", "openai"):
        return False
    if model:
        m = model.lower()
        if m.startswith(("local/", "midboy1/", "mlx/")):
            return True
    # Prod Brigade sets OPS_CENTER_LLM_ENDPOINT to the local llama-router, so
    # "direct" and unknown providers are effectively local.
    if os.getenv("OPS_CENTER_LLM_ENDPOINT"):
        return True
    return False


# Tools whose use signals SPECIALIZED knowledge / RAG and should bill at a
# higher value tier. This is the policy knob for the RAG surcharge — extend it
# as new knowledge/RAG/specialist tools are added. (Agent-level specialization
# is better expressed via the agent's billing_tier; this catches a generic
# agent that reaches for specialized knowledge mid-task.)
KNOWLEDGE_TOOLS = {
    "knowledge_query", "knowledge_store", "agentic_rag",
    "cdr_search", "cdr_quick_answer", "cdr_deep_research", "deep_research", "quick_answer",
    "stable_knowledge_search",
}


def rag_used(tools_used) -> bool:
    """True when the chat used a specialized knowledge/RAG tool."""
    return any(name in KNOWLEDGE_TOOLS for name in (tools_used or []))


def classify_rate_tier(agent: Optional[dict], used_rag: bool) -> str:
    """The value tier for a chat. An explicit per-agent billing_tier wins;
    otherwise specialized-knowledge use bumps the tier. Default 'standard'.
    Dollar rates for each tier live in the Lago plan, not here."""
    agent = agent or {}
    tier = (agent.get("billingTier") or agent.get("billing_tier") or "").strip().lower()
    if tier:
        return tier
    return "specialized" if used_rag else "standard"


def _now_ts() -> int:
    return int(datetime.utcnow().timestamp())


def _envelope(code: str, user: str, properties: dict, transaction_id: str) -> dict:
    return {
        "event": {
            "transaction_id": transaction_id,
            "external_customer_id": user,
            "code": code,
            "timestamp": _now_ts(),
            "properties": properties,
        }
    }


def _value_dims(
    agent_id=None, agent_name=None, agent_domain=None,
    tools_used=None, used_rag=False, rate_tier=None, rate_multiplier=None,
) -> dict:
    """Optional per-agent / value dimensions for an event's properties. All
    optional + string-valued, so Lago and downstream consumers stay
    backward-compatible (they ignore unknown keys)."""
    p = {}
    if agent_id:
        p["agent_id"] = agent_id
    if agent_name:
        p["agent_name"] = agent_name
    if agent_domain:
        p["agent_domain"] = agent_domain
    if tools_used:
        p["tools_used"] = ",".join(tools_used)
        p["tool_count"] = str(len(tools_used))
    if used_rag:
        p["rag_used"] = "true"
    if rate_tier:
        p["rate_tier"] = rate_tier
    if rate_multiplier is not None:
        p["rate_multiplier"] = f"{rate_multiplier}"
    return p


async def _mirror_to_ops_center_webhook(envelope: dict) -> bool:
    """POST the same event envelope into Ops-Center's webhook handler.

    Phase 7b.1: Lago in this deployment doesn't fire per-event webhooks, so
    we trigger the deduction path directly with the same shape the webhook
    would deliver. Handler dedups by ``transaction_id`` so this is safe even
    if Lago later re-emits the same event.
    """
    if not OPS_CENTER_URL:
        return False
    payload = {
        "webhook_type": "event.emitted",
        "source": "brigade-mirror",
        **envelope,
    }
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.post(
                f"{OPS_CENTER_URL}/api/v1/webhooks/lago",
                json=payload,
                headers={"Content-Type": "application/json"},
            )
        if r.status_code < 400:
            return True
        logger.warning(
            f"Ops-Center webhook mirror failed: {r.status_code} {r.text[:200]}"
        )
        return False
    except Exception as e:
        logger.warning(f"Ops-Center webhook mirror error: {e}")
        return False


async def _post_event(envelope: dict, mirror: bool) -> bool:
    """POST an event to Lago (best-effort) and, when ``mirror`` is set, also to
    the Ops-Center deduction webhook. Returns True if Lago accepted it. Never
    raises."""
    user = envelope["event"].get("external_customer_id")
    lago_ok = False
    if LAGO_API_URL and LAGO_API_KEY:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.post(
                    f"{LAGO_API_URL}/api/v1/events",
                    headers={
                        "Authorization": f"Bearer {LAGO_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json=envelope,
                )
            if r.status_code in (200, 201, 204):
                lago_ok = True
            elif r.status_code == 422:
                # No matching Lago customer — common for free-tier users.
                logger.debug(f"Lago 422 for user={user} (likely unknown customer)")
            else:
                logger.warning(f"Lago event POST failed: {r.status_code} {r.text[:200]}")
        except Exception as e:
            logger.warning(f"Lago event emission failed: {e}")
    else:
        logger.debug("Lago not configured; skipping Lago leg")

    if mirror:
        # Fire-and-forget-ish; we await but don't fail-out on mirror errors.
        await _mirror_to_ops_center_webhook(envelope)
    return lago_ok


async def emit_ai_api_call(
    user: str,
    model: str,
    tokens: int,
    cost: float,
    transaction_id: Optional[str] = None,
    byok: bool = False,
    agent_id: Optional[str] = None,
    agent_name: Optional[str] = None,
    agent_domain: Optional[str] = None,
    tools_used: Optional[list] = None,
    used_rag: bool = False,
    rate_tier: Optional[str] = None,
    rate_multiplier: Optional[float] = None,
) -> bool:
    """Emit the LLM-cost (COGS) ``ai_api_call`` event and trigger credit
    deduction. Billing behavior is unchanged — still only the local-GPU token
    cost, still mirrored to the deduction webhook. The optional value dimensions
    (agent_id, tools_used, rag_used, rate_tier, ...) are added to ``properties``
    for visibility/analytics and are backward-compatible.
    """
    if not user or tokens <= 0:
        return False
    tx = transaction_id or f"brigade-{_uuid.uuid4()}"
    props = {
        "model": model or "unknown",
        "tokens": str(tokens),
        "cost": f"{cost:.8f}",
        "user": user,
    }
    if byok:
        props["byok"] = True
    props.update(_value_dims(agent_id, agent_name, agent_domain, tools_used,
                             used_rag, rate_tier, rate_multiplier))
    return await _post_event(_envelope("ai_api_call", user, props, tx), mirror=True)


async def emit_agent_work(
    user: str,
    agent_id: str,
    model: Optional[str] = None,
    tokens: int = 0,
    outcome: str = "success",
    agent_name: Optional[str] = None,
    agent_domain: Optional[str] = None,
    tools_used: Optional[list] = None,
    used_rag: bool = False,
    rate_tier: str = "standard",
    rate_multiplier: float = 1.0,
    transaction_id: Optional[str] = None,
) -> bool:
    """Emit the per-agent VALUE event — the unit a customer is billed for: the
    work an agent delivered, not raw LLM tokens. Carries user + agent + tools +
    rag + outcome so usage is attributable per-agent AND per-user — notably for
    ``uc/``-gateway routes, where the LLM-cost path is skipped and the end user
    would otherwise be invisible.

    Recorded to Lago for visibility/aggregation but deliberately NOT mirrored to
    the immediate-deduction webhook: this event charges nothing until a Lago
    billable-metric + plan is configured for ``agent_work``. So emitting it is
    additive and changes nothing about what's billed today.
    """
    if not user or not agent_id:
        return False
    tx = transaction_id or f"brigade-work-{_uuid.uuid4()}"
    props = {
        "user": user,
        "agent_id": agent_id,
        "model": model or "unknown",
        "tokens": str(tokens),
        "outcome": outcome,
    }
    props.update(_value_dims(None, agent_name, agent_domain, tools_used,
                             used_rag, rate_tier, rate_multiplier))
    return await _post_event(_envelope("agent_work", user, props, tx), mirror=False)
