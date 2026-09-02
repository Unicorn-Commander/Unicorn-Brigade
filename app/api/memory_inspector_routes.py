"""Memory inspector endpoints — customer-facing view of what agents remember."""

from typing import List, Optional
import hmac
import logging
import os

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_session
from app.db.repositories import AgentRepository

logger = logging.getLogger(__name__)
router = APIRouter()

# Injected at startup
memory_manager = None


def init_memory_routes(mm):
    global memory_manager
    memory_manager = mm


def _verify_admin_key(x_api_key: Optional[str], authorization: Optional[str]) -> None:
    """Admin gate for the memory inspector (RLS-exempt cross-tenant read/delete).

    S2 (HIGH) fix — FAIL CLOSED. These endpoints run on the RLS-exempt
    ``admin_session`` and can enumerate/read/delete ANY tenant's memory, so an
    unconfigured gate must never be an open door. When ``BRIGADE_ADMIN_KEY`` is
    unset we now refuse with 503 (mirroring
    ``app/api/admin_keys_routes.py::require_service_key``) instead of returning
    (which previously allowed the request through). The header comparison uses
    ``hmac.compare_digest`` on the encoded bytes for constant-time matching (no
    timing side-channel, and no ASCII-only TypeError on odd input).
    """
    admin_key = os.getenv("BRIGADE_ADMIN_KEY", "") or ""
    if not admin_key:
        logger.error(
            "BRIGADE_ADMIN_KEY is not configured; refusing memory-inspector "
            "requests (fail closed)"
        )
        raise HTTPException(
            status_code=503,
            detail="Memory inspection is not configured on this Brigade instance",
        )
    provided = x_api_key
    if not provided and authorization and authorization.startswith("Bearer "):
        provided = authorization[len("Bearer "):]
    if not provided or not hmac.compare_digest(provided.encode(), admin_key.encode()):
        raise HTTPException(status_code=401, detail="Invalid API key")


class MemoryItem(BaseModel):
    memory: str
    uuid: Optional[str] = None


@router.get("/api/v1/agents/{agent_id}/memories")
async def get_agent_memories(
    agent_id: str,
    user_id: str = "anonymous",
    query: str = "*",
    limit: int = 50,
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    """What does this agent know about this user?

    Example: GET /api/v1/agents/judge-advocate/memories?user_id=aaron&query=contract
    """
    _verify_admin_key(x_api_key, authorization)
    if memory_manager is None:
        raise HTTPException(status_code=503, detail="Memory manager not initialized")
    # BR-1.4: admin-key-gated cross-tenant inspection. Resolve the agent on the
    # owner/admin session so an org-scoped agent (any tenant's) is found — the
    # RLS-subject request session with no bound org would only see global agents.
    from app.db.database import admin_session
    async with admin_session() as admin_sess:
        agent = await AgentRepository(admin_sess).get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")
    memories = await memory_manager.retrieve(
        user_id=user_id, query=query, agent_id=agent_id, limit=limit
    )
    return {
        "agent_id": agent_id,
        "user_id": user_id,
        "query": query,
        "count": len(memories),
        "memories": memories,
    }


@router.get("/api/v1/users/{user_id}/memories")
async def get_all_user_memories(
    user_id: str,
    query: str = "*",
    limit: int = 100,
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    """All memories a user has accumulated across all agents (admin)."""
    _verify_admin_key(x_api_key, authorization)
    if memory_manager is None:
        raise HTTPException(status_code=503, detail="Memory manager not initialized")
    memories = await memory_manager.get_all(user_id=user_id)
    return {"user_id": user_id, "count": len(memories), "memories": memories}


@router.delete("/api/v1/agents/{agent_id}/memories")
async def delete_agent_memories_for_user(
    agent_id: str,
    user_id: str,
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    """Forget everything this agent knows about this user.

    Drops the FalkorDB graph `{user_id}__{agent_id}` entirely.
    Useful for GDPR / right-to-forget.
    """
    _verify_admin_key(x_api_key, authorization)
    try:
        from graphiti_core.driver.falkordb_driver import FalkorDriver
        import os
        host = os.getenv("FALKORDB_HOST", "unicorn-falkordb")
        port = int(os.getenv("FALKORDB_PORT", "6379"))
        import re
        def _slug(s):
            return re.sub(r"[^A-Za-z0-9]", "_", s or "anon")
        group_id = f"{_slug(user_id)}__{_slug(agent_id)}"
        # FalkorDB GRAPH.DELETE via a raw redis command
        import redis.asyncio as aredis
        r = aredis.Redis(host=host, port=port, password=os.getenv("FALKORDB_PASSWORD") or None, decode_responses=True)
        try:
            await r.execute_command("GRAPH.DELETE", group_id)
        finally:
            await r.aclose()
        return {"deleted_graph": group_id, "user_id": user_id, "agent_id": agent_id}
    except Exception as e:
        logger.error(f"Failed to delete memory graph: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/v1/memory/graphs")
async def list_memory_graphs(
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    """List all per-user-per-agent memory graphs (admin)."""
    _verify_admin_key(x_api_key, authorization)
    try:
        import os
        host = os.getenv("FALKORDB_HOST", "unicorn-falkordb")
        port = int(os.getenv("FALKORDB_PORT", "6379"))
        import redis.asyncio as aredis
        r = aredis.Redis(host=host, port=port, password=os.getenv("FALKORDB_PASSWORD") or None, decode_responses=True)
        try:
            graphs = await r.execute_command("GRAPH.LIST")
        finally:
            await r.aclose()
        return {"count": len(graphs), "graphs": graphs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/v1/memory/stats")
async def memory_stats(
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    """Summary of the memory subsystem."""
    _verify_admin_key(x_api_key, authorization)
    if memory_manager is None:
        raise HTTPException(status_code=503, detail="Memory manager not initialized")
    return memory_manager.get_stats()
