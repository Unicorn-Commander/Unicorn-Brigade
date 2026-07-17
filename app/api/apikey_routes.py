"""
API Key management routes.
Generates, lists, and revokes API keys for agents.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List, Annotated
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.db.database import get_session
from app.db.repositories import AgentRepository, ApiKeyRepository
from app.auth.middleware import require_api_key, require_operator, require_admin, AuthUser

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
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """Generate a new API key for an agent."""
    if user and not user.can_access_agent(agent_id):
        raise HTTPException(status_code=403, detail="Access to agent denied")
    agent_repo = AgentRepository(session)
    agent = await agent_repo.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")

    repo = ApiKeyRepository(session)
    # BR-2.4 (H1 fix): stamp the creating user's ACTIVE org onto the new key so it
    # binds to that org at auth time (per-customer key isolation). ``user.org_id``
    # is the org resolved by ``_bind_org_context`` during auth — it already honors
    # an ``X-Org-Id`` active-org header (validated against membership), else the
    # user's personal/home org. None only for the master-admin key, in which case
    # the ApiKey.org_id server_default (current_org_id()) tags the bound org.
    result = await repo.generate(
        agent_id, request.model_dump(), org_id=(user.org_id if user else None)
    )

    logger.info(
        f"Generated API key {result.get('keyPrefix', '???')}... for agent {agent_id} "
        f"in org {result.get('orgId')}"
    )
    return result


@router.get("/agents/{agent_id}/api-keys")
async def list_api_keys(
    agent_id: str,
    session: AsyncSession = Depends(get_session),
    user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """List all API keys for an agent (without full key values)."""
    if user and not user.can_access_agent(agent_id):
        raise HTTPException(status_code=403, detail="Access to agent denied")
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
    user: Annotated[AuthUser, Depends(require_admin)] = None,
):
    """Revoke (soft-delete) an API key."""
    if user and not user.can_access_agent(agent_id):
        raise HTTPException(status_code=403, detail="Access to agent denied")
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
    user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """Get details of a specific API key."""
    if user and not user.can_access_agent(agent_id):
        raise HTTPException(status_code=403, detail="Access to agent denied")
    repo = ApiKeyRepository(session)
    key = await repo.get(key_id)
    if not key or key.get("agentId") != agent_id:
        raise HTTPException(status_code=404, detail="API key not found")
    return key
