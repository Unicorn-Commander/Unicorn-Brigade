"""
Conversation persistence routes.
Provides CRUD for conversations and messages.
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, List, Optional, Annotated
import logging

from app.db.database import get_session, AsyncSession
from app.db.repositories import ConversationRepository
from app.auth.middleware import require_api_key, require_operator, require_admin, AuthUser
from app.auth.roles import UserRole

logger = logging.getLogger(__name__)
router = APIRouter()


# ---- Models ----

class CreateConversationRequest(BaseModel):
    agent_id: Optional[str] = None
    user_id: Optional[str] = "anonymous"
    title: Optional[str] = None
    model: Optional[str] = None


class AddMessageRequest(BaseModel):
    role: str  # user, assistant, system, tool
    content: str
    model: Optional[str] = None
    tokens_used: Optional[int] = 0
    tool_calls: Optional[List[Dict]] = None
    tool_results: Optional[List[Dict]] = None
    metadata: Optional[Dict] = None


class UpdateConversationRequest(BaseModel):
    title: Optional[str] = None
    status: Optional[str] = None
    model: Optional[str] = None


# ---- Endpoints ----

@router.get("/conversations")
async def list_conversations(
    user_id: str = "anonymous",
    limit: int = 50,
    session: AsyncSession = Depends(get_session),
    user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """List conversations for a user."""
    if user and user.role != UserRole.ADMIN:
        user_id = user.id
    repo = ConversationRepository(session)
    conversations = await repo.list_for_user(user_id=user_id, limit=limit)
    return {"conversations": conversations}


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    session: AsyncSession = Depends(get_session),
    user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """Get a conversation with all messages."""
    repo = ConversationRepository(session)
    conv = await repo.get(conversation_id, include_messages=True)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if user and user.role != UserRole.ADMIN and conv.get("user_id") != user.id:
        raise HTTPException(status_code=403, detail="Access to conversation denied")
    return conv


@router.post("/conversations", status_code=201)
async def create_conversation(
    request: CreateConversationRequest,
    session: AsyncSession = Depends(get_session),
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """Create a new conversation."""
    repo = ConversationRepository(session)
    data = request.model_dump()
    if user and user.role != UserRole.ADMIN:
        data["user_id"] = user.id
    conv = await repo.create(data)
    return conv


@router.patch("/conversations/{conversation_id}")
async def update_conversation(
    conversation_id: str,
    request: UpdateConversationRequest,
    session: AsyncSession = Depends(get_session),
    user: Annotated[AuthUser, Depends(require_admin)] = None,
):
    """Update conversation metadata."""
    repo = ConversationRepository(session)
    conv = await repo.get(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if user and user.role != UserRole.ADMIN and conv.get("user_id") != user.id:
        raise HTTPException(status_code=403, detail="Access to conversation denied")
    updates = request.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    conv = await repo.update(conversation_id, updates)
    return conv


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    session: AsyncSession = Depends(get_session),
    user: Annotated[AuthUser, Depends(require_admin)] = None,
):
    """Delete a conversation and all its messages."""
    repo = ConversationRepository(session)
    conv = await repo.get(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if user and user.role != UserRole.ADMIN and conv.get("user_id") != user.id:
        raise HTTPException(status_code=403, detail="Access to conversation denied")
    success = await repo.delete(conversation_id)
    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"message": "Conversation deleted"}


@router.post("/conversations/{conversation_id}/messages", status_code=201)
async def add_message(
    conversation_id: str,
    request: AddMessageRequest,
    session: AsyncSession = Depends(get_session),
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """Add a message to a conversation."""
    repo = ConversationRepository(session)

    # Verify conversation exists
    conv = await repo.get(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if user and user.role != UserRole.ADMIN and conv.get("user_id") != user.id:
        raise HTTPException(status_code=403, detail="Access to conversation denied")

    msg = await repo.add_message(conversation_id, request.model_dump())
    return msg
