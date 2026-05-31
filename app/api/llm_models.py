"""LLM model catalog proxy routes."""

import os
import time
from typing import Any, Dict, List

import httpx
from fastapi import APIRouter, Depends

from app.auth.middleware import AuthUser, require_admin

router = APIRouter()

OPS_CENTER_MODELS_URL = "http://ops-center-direct:8084/api/v1/llm/models"
CACHE_TTL_SECONDS = 300

_cache: Dict[str, Any] = {"expires_at": 0.0, "payload": None}


FALLBACK_MODELS = {
    "models": [
        {
            "id": "claude-3.5-haiku",
            "display_name": "Claude 3.5 Haiku",
            "provider": "Anthropic",
            "input_price": 0.25,
            "output_price": 1.25,
            "category": "anthropic",
        },
        {
            "id": "claude-sonnet-4",
            "display_name": "Claude Sonnet 4",
            "provider": "Anthropic",
            "input_price": 3,
            "output_price": 15,
            "category": "anthropic",
        },
        {
            "id": "Qwen3-30B-Q4_K_M",
            "display_name": "Qwen3 30B Q4_K_M",
            "provider": "Local",
            "input_price": 0,
            "output_price": 0,
            "category": "local",
        },
    ],
    "count": 3,
    "source": "fallback",
}


def _model_id(model: Dict[str, Any]) -> str:
    return str(
        model.get("id")
        or model.get("model")
        or model.get("name")
        or model.get("slug")
        or ""
    )


def _price_value(model: Dict[str, Any], keys: List[str]) -> float | None:
    pricing = model.get("pricing") if isinstance(model.get("pricing"), dict) else {}
    for key in keys:
        value = model.get(key)
        if value is None:
            value = pricing.get(key)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _is_free(model: Dict[str, Any]) -> bool:
    input_price = _price_value(
        model,
        ["input", "input_price", "inputPrice", "prompt_price", "promptPrice", "input_cost_per_1m", "inputCostPer1M"],
    )
    output_price = _price_value(
        model,
        ["output", "output_price", "outputPrice", "completion_price", "completionPrice", "output_cost_per_1m", "outputCostPer1M"],
    )
    if input_price is None and output_price is None:
        price = str(model.get("price") or model.get("cost") or "").lower()
        return price in {"", "0", "free", "$0", "$0/$0"}
    return (input_price or 0) == 0 and (output_price or 0) == 0


def _category_for(model: Dict[str, Any]) -> str:
    provider = str(model.get("provider") or model.get("source") or "").lower()
    model_id = _model_id(model).lower()

    if "anthropic" in provider or "claude" in model_id:
        return "anthropic"
    if "openrouter" in provider or model_id.startswith("openrouter/") or "/" in model_id:
        return "openrouter"
    if _is_free(model):
        return "local"
    return "other"


def _enrich_payload(payload: Any) -> Any:
    if isinstance(payload, list):
        models = payload
        enriched = [_enrich_model(model) for model in models if isinstance(model, dict)]
        return {"models": enriched, "count": len(enriched)}

    if not isinstance(payload, dict):
        return FALLBACK_MODELS

    models = payload.get("models") or payload.get("data") or []
    if not isinstance(models, list):
        return payload

    enriched = [_enrich_model(model) for model in models if isinstance(model, dict)]
    return {
        **payload,
        "models": enriched,
        "count": payload.get("count", len(enriched)),
    }


def _enrich_model(model: Dict[str, Any]) -> Dict[str, Any]:
    if model.get("category"):
        return model
    return {**model, "category": _category_for(model)}


async def _fetch_ops_center_models() -> Any:
    service_key = os.getenv("BRIGADE_SERVICE_KEY", "sk-brigade-service-key-2025")
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            OPS_CENTER_MODELS_URL,
            headers={"Authorization": f"Bearer {service_key}"},
        )
    if response.status_code != 200:
        return FALLBACK_MODELS
    return _enrich_payload(response.json())


@router.get("/llm/models")
async def list_llm_models(
    user: AuthUser = Depends(require_admin),
):
    """Return the ops-center LLM catalog with a short in-memory cache."""
    now = time.monotonic()
    if _cache["payload"] is not None and now < _cache["expires_at"]:
        return _cache["payload"]

    try:
        payload = await _fetch_ops_center_models()
    except Exception:
        payload = FALLBACK_MODELS

    _cache["payload"] = payload
    _cache["expires_at"] = now + CACHE_TTL_SECONDS
    return payload
