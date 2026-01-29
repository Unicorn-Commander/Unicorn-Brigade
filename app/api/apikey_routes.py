"""
API Key management routes.
Generates, lists, and revokes API keys for agents.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.db.database import get_session
from app.db.repositories import AgentRepository, ApiKeyRepository

logger = logging.getLogger(__name__)
router = APIRouter()


# ---- Models ----

class GenerateKeyRequest(BaseModel):
    name: str
    permissions: Optional[List[str]] = ["chat", "read"]
    rateLimit: Optional[int] = 100
    expiresInDays: Optional[int] = 90


# ---- Endpoints ----

@router.post("/agents/{agent_id}/api-keys", status_code=201)
async def generate_api_key(
    agent_id: str,
    request: GenerateKeyRequest,
    session: AsyncSession = Depends(get_session),
):
    """Generate a new API key for an agent."""
    agent_repo = AgentRepository(session)
    agent = await agent_repo.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")

    repo = ApiKeyRepository(session)
    result = await repo.generate(agent_id, request.model_dump())

    logger.info(f"Generated API key {result.get('keyPrefix', '???')}... for agent {agent_id}")
    return result


@router.get("/agents/{agent_id}/api-keys")
async def list_api_keys(
    agent_id: str,
    session: AsyncSession = Depends(get_session),
):
    """List all API keys for an agent (without full key values)."""
    agent_repo = AgentRepository(session)
    agent = await agent_repo.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")

    repo = ApiKeyRepository(session)
    keys = await repo.list_for_agent(agent_id)
    return {"keys": keys}


@router.delete("/agents/{agent_id}/api-keys/{key_id}")
async def revoke_api_key(
    agent_id: str,
    key_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Revoke (soft-delete) an API key."""
    repo = ApiKeyRepository(session)
    success = await repo.revoke(agent_id, key_id)
    if not success:
        raise HTTPException(status_code=404, detail="API key not found")

    logger.info(f"Revoked API key {key_id} for agent {agent_id}")
    return {"message": "API key revoked", "id": key_id}


@router.get("/agents/{agent_id}/api-keys/{key_id}")
async def get_api_key(
    agent_id: str,
    key_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Get details of a specific API key."""
    repo = ApiKeyRepository(session)
    key = await repo.get(key_id)
    if not key or key.get("agentId") != agent_id:
        raise HTTPException(status_code=404, detail="API key not found")
    return key
