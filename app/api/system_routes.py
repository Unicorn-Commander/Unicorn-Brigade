"""
System-level routes: stats, model catalog, providers.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
import logging
import time

from app.db.database import get_session
from app.db.repositories import AgentRepository
from app.stores.model_catalog import ModelCatalog
from app.llm.ops_center_client import OpsCenterLLMClient

logger = logging.getLogger(__name__)
router = APIRouter()

# Injected during startup
model_catalog: ModelCatalog = None
llm_client: OpsCenterLLMClient = None
_start_time = time.time()


def init_system_routes(catalog: ModelCatalog, client: OpsCenterLLMClient):
    global model_catalog, llm_client
    model_catalog = catalog
    llm_client = client


@router.get("/stats")
async def get_stats(session: AsyncSession = Depends(get_session)):
    """System stats for the Dashboard."""
    uptime = time.time() - _start_time

    repo = AgentRepository(session)
    total_agents = await repo.count()
    active_agents = await repo.count_active()

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
        "totalTools": 7,
        "uptime_seconds": round(uptime, 1),
        "status": "operational",
        "version": "1.0.0",
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
    """List LLM providers (Ops-Center handles routing)."""
    return {
        "providers": [
            {
                "id": "ops-center",
                "name": "Ops-Center (UC-Cloud)",
                "type": "gateway",
                "endpoint": "https://unicorncommander.ai",
                "status": "active",
                "isDefault": True,
                "description": "UC-Cloud inference gateway routing to 70+ models via vLLM, OpenRouter, and BYOK keys.",
                "supported_providers": ["openai", "anthropic", "google", "meta", "mistral", "deepseek"],
                "icon": "🦄",
            },
            {
                "id": "local-vllm",
                "name": "Local vLLM",
                "type": "local",
                "endpoint": "http://ops-center-direct:8084",
                "status": "active",
                "isDefault": False,
                "description": "Local GPU inference via vLLM. Zero cost, full privacy.",
                "icon": "🖥️",
            },
        ],
        "count": 2,
    }
