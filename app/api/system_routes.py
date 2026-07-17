"""
System-level routes: stats, model catalog, providers.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated, Optional
import asyncio
import logging
import os
import time

import httpx

from app.db.database import get_session
from app.db.models import Conversation, Message
from app.db.repositories import AgentRepository
# BR-1.4: /stats counts org-scoped tables (agents shared-catalog, conversations +
# messages are FORCE-RLS). Bind the caller's org so the dashboard reflects THEIR
# org's counts; anonymous callers see global agents + zero private conversations.
from app.auth.middleware import get_current_user_optional, AuthUser
from app.llm.tool_resolver import TOOL_REGISTRY
from app.stores.model_catalog import ModelCatalog
from app.llm.ops_center_client import OpsCenterLLMClient

logger = logging.getLogger(__name__)
router = APIRouter()

# Injected during startup
model_catalog: ModelCatalog = None
llm_client: OpsCenterLLMClient = None
_start_time = time.time()

API_VERSION = os.getenv("API_VERSION", "1.17.0")

# Short timeout for provider/service reachability probes: these run inline
# in request handlers, so a dead upstream must fail fast, not hang the page.
PROBE_TIMEOUT_SECONDS = 2.0


def init_system_routes(catalog: ModelCatalog, client: OpsCenterLLMClient):
    global model_catalog, llm_client
    model_catalog = catalog
    llm_client = client


def ops_center_base_url() -> str:
    """The Ops-Center gateway base URL actually used for LLM routing."""
    if llm_client is not None and llm_client.ops_center_url:
        return llm_client.ops_center_url.rstrip("/")
    return os.getenv("OPS_CENTER_URL", "https://unicorncommander.ai").rstrip("/")


def local_llm_base_url() -> str:
    """The local OpenAI-compatible LLM router (llama.cpp router)."""
    return os.getenv("LOCAL_LLM_URL", "http://unicorn-llama-router:8080").rstrip("/")


async def probe_http(url: str, timeout: float = PROBE_TIMEOUT_SECONDS) -> dict:
    """
    GET a URL and report reachability. Never raises.

    Any HTTP response below 500 (even a 404) proves the service is up and
    answering; only transport-level failures (connection refused, DNS,
    timeout) or 5xx count as unreachable.
    """
    start = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url)
        return {
            "ok": resp.status_code < 500,
            "latency_ms": round((time.monotonic() - start) * 1000, 1),
            "detail": f"HTTP {resp.status_code}",
        }
    except Exception as e:
        return {
            "ok": False,
            "latency_ms": round((time.monotonic() - start) * 1000, 1),
            "detail": (str(e) or type(e).__name__)[:200],
        }


@router.get("/stats")
async def get_stats(
    session: AsyncSession = Depends(get_session),
    _user: Annotated[Optional[AuthUser], Depends(get_current_user_optional)] = None,
):
    """System stats for the Dashboard (org-scoped when the caller is authenticated)."""
    uptime = time.time() - _start_time

    repo = AgentRepository(session)
    total_agents = await repo.count()
    active_agents = await repo.count_active()

    # Real usage counts straight from the database (never estimated).
    total_conversations = 0
    total_messages = 0
    try:
        total_conversations = (
            await session.execute(select(func.count(Conversation.id)))
        ).scalar() or 0
        total_messages = (
            await session.execute(select(func.count(Message.id)))
        ).scalar() or 0
    except Exception as e:
        logger.warning(f"Failed to count conversations/messages: {e}")

    # Try to get system resources
    resources = {}
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        resources = {
            "cpu_percent": cpu,
            "memory_percent": mem.percent,
            "memory_used_gb": round(mem.used / (1024**3), 2),
            "memory_total_gb": round(mem.total / (1024**3), 2),
            "disk_percent": disk.percent,
        }
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"Failed to get system resources: {e}")

    return {
        "totalAgents": total_agents,
        "activeAgents": active_agents,
        "totalModels": model_catalog.count() if model_catalog else 0,
        # The real tool registry, not a hardcoded count.
        "totalTools": len(TOOL_REGISTRY),
        "totalConversations": total_conversations,
        "totalMessages": total_messages,
        "uptime_seconds": round(uptime, 1),
        "status": "operational",
        "version": API_VERSION,
        "resources": resources,
    }


@router.get("/chat/models")
async def list_models():
    """List models with speed/quality/cost metadata."""
    if model_catalog and llm_client:
        await model_catalog.enrich_with_live_data(llm_client)

    models = model_catalog.list_all() if model_catalog else []

    # Group by category
    categories = {}
    for m in models:
        cat = m.get("category", "unknown")
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(m)

    return {
        "models": models,
        "count": len(models),
        "categories": categories,
    }


@router.get("/providers")
async def list_providers():
    """
    List LLM providers with live connectivity status.

    Each provider is probed with a short-timeout HTTP GET; status is
    "connected"/"disconnected" plus latency_ms. Never raises — probe
    failures simply report the provider as disconnected.
    """
    ops_base = ops_center_base_url()
    local_base = local_llm_base_url()

    ops_probe, local_probe = await asyncio.gather(
        probe_http(f"{ops_base}/health"),
        probe_http(f"{local_base}/v1/models"),
    )

    providers = [
        {
            "id": "ops-center",
            "name": "Ops-Center (UC-Cloud)",
            "type": "gateway",
            "endpoint": ops_base,
            "status": "connected" if ops_probe["ok"] else "disconnected",
            "latency_ms": ops_probe["latency_ms"],
            "detail": ops_probe["detail"],
            "isDefault": True,
            "description": "UC-Cloud inference gateway routing to 70+ models via vLLM, OpenRouter, and BYOK keys.",
            "supported_providers": ["openai", "anthropic", "google", "meta", "mistral", "deepseek"],
            "icon": "🦄",
        },
        {
            "id": "local-vllm",
            "name": "Local LLM Router",
            "type": "local",
            "endpoint": local_base,
            "status": "connected" if local_probe["ok"] else "disconnected",
            "latency_ms": local_probe["latency_ms"],
            "detail": local_probe["detail"],
            "isDefault": False,
            "description": "Local GPU inference via the llama.cpp router. Zero cost, full privacy.",
            "icon": "🖥️",
        },
    ]
    return {"providers": providers, "count": len(providers)}
