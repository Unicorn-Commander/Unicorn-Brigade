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


def _build_event_envelope(
    user: str,
    model: str,
    tokens: int,
    cost: float,
    transaction_id: str,
    byok: bool = False,
) -> dict:
    props = {
        "model": model or "unknown",
        "tokens": str(tokens),
        "cost": f"{cost:.8f}",
        "user": user,
    }
    if byok:
        props["byok"] = True
    return {
        "event": {
            "transaction_id": transaction_id,
            "external_customer_id": user,
            "code": "ai_api_call",
            "timestamp": int(datetime.utcnow().timestamp()),
            "properties": props,
        }
    }


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


async def emit_ai_api_call(
    user: str,
    model: str,
    tokens: int,
    cost: float,
    transaction_id: Optional[str] = None,
    byok: bool = False,
) -> bool:
    """Emit a single ``ai_api_call`` event and trigger credit deduction.

    Two-step, independent best-effort:
      1. POST to Lago /api/v1/events  (audit + billing aggregation)
      2. POST same envelope as a ``event.emitted`` webhook to Ops-Center
         so the credit balance decrements right now.

    Either leg failing won't break the other. Returns True if Lago accepted
    the event.
    """
    if not user or tokens <= 0:
        return False

    tx = transaction_id or f"brigade-{_uuid.uuid4()}"
    envelope = _build_event_envelope(user, model, tokens, cost, tx, byok=byok)

    # ---- 1. Lago emission ------------------------------------------------
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
                logger.warning(
                    f"Lago event POST failed: {r.status_code} {r.text[:200]}"
                )
        except Exception as e:
            logger.warning(f"Lago event emission failed: {e}")
    else:
        logger.debug("Lago not configured; skipping Lago leg")

    # ---- 2. Ops-Center mirror (deduction) --------------------------------
    # Fire-and-forget-ish; we await but don't fail-out on mirror errors.
    await _mirror_to_ops_center_webhook(envelope)

    return lago_ok
