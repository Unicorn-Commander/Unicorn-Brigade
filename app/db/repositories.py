"""
Repository classes for database CRUD operations.
Each repository handles one entity type with async SQLAlchemy sessions.
"""
import hashlib
import secrets
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import select, func, delete, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Agent, Conversation, Message, ApiKey, BuilderSession, ToolExecution

logger = logging.getLogger(__name__)


# ── Agent Repository ──────────────────────────────────────────────

class AgentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_all(self) -> List[Dict]:
        result = await self.session.execute(
            select(Agent).order_by(Agent.domain, Agent.name)
        )
        return [a.to_dict() for a in result.scalars().all()]

    async def get(self, agent_id: str) -> Optional[Dict]:
        result = await self.session.execute(
            select(Agent).where(Agent.id == agent_id)
        )
        agent = result.scalar_one_or_none()
        return agent.to_dict() if agent else None

    async def create(self, data: Dict[str, Any]) -> Dict:
        agent = Agent(
            id=data.get("id") or data.get("name", "").lower().replace(" ", "-"),
            name=data["name"],
            display_name=data.get("displayName"),
            title=data.get("title"),
            rank=data.get("rank"),
            avatar=data.get("avatar", "🦄"),
            bio=data.get("bio"),
            persona=data.get("persona"),
            system_prompt=data.get("systemPrompt"),
            domain=data.get("domain", "general"),
            subdomain=data.get("subdomain"),
            status=data.get("status", "active"),
            type=data.get("type", "individual"),
            agent_type=data.get("agentType", "analysis"),
            capabilities=data.get("capabilities", []),
            model=data.get("model", "openai/gpt-4o-mini"),
            temperature=data.get("temperature", 0.7),
            max_tokens=data.get("maxTokens", 2000),
            tools=data.get("tools", []),
        )
        self.session.add(agent)
        await self.session.commit()
        await self.session.refresh(agent)
        return agent.to_dict()

    async def update(self, agent_id: str, updates: Dict[str, Any]) -> Optional[Dict]:
        result = await self.session.execute(
            select(Agent).where(Agent.id == agent_id)
        )
        agent = result.scalar_one_or_none()
        if not agent:
            return None

        field_map = {
            "displayName": "display_name", "systemPrompt": "system_prompt",
            "agentType": "agent_type", "maxTokens": "max_tokens",
        }
        for key, value in updates.items():
            attr = field_map.get(key, key)
            if hasattr(agent, attr):
                setattr(agent, attr, value)

        agent.updated_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(agent)
        return agent.to_dict()

    async def delete(self, agent_id: str) -> bool:
        result = await self.session.execute(
            select(Agent).where(Agent.id == agent_id)
        )
        agent = result.scalar_one_or_none()
        if not agent:
            return False
        await self.session.delete(agent)
        await self.session.commit()
        return True

    async def get_domains(self) -> List[Dict]:
        result = await self.session.execute(
            select(Agent.domain, func.count(Agent.id).label("count"))
            .group_by(Agent.domain)
            .order_by(Agent.domain)
        )
        return [{"name": row.domain, "count": row.count} for row in result.all()]

    async def count(self) -> int:
        result = await self.session.execute(select(func.count(Agent.id)))
        return result.scalar() or 0

    async def count_active(self) -> int:
        result = await self.session.execute(
            select(func.count(Agent.id)).where(Agent.status == "active")
        )
        return result.scalar() or 0


# ── Conversation Repository ───────────────────────────────────────

class ConversationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_for_user(self, user_id: str = "anonymous", limit: int = 50) -> List[Dict]:
        result = await self.session.execute(
            select(Conversation)
            .options(selectinload(Conversation.agent))
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.updated_at.desc())
            .limit(limit)
        )
        return [c.to_dict() for c in result.scalars().all()]

    async def get(self, conv_id: str, include_messages: bool = False) -> Optional[Dict]:
        query = select(Conversation).where(Conversation.id == conv_id)
        if include_messages:
            query = query.options(
                selectinload(Conversation.messages),
                selectinload(Conversation.agent),
            )
        else:
            query = query.options(selectinload(Conversation.agent))

        result = await self.session.execute(query)
        conv = result.scalar_one_or_none()
        return conv.to_dict(include_messages=include_messages) if conv else None

    async def create(self, data: Dict[str, Any]) -> Dict:
        conv = Conversation(
            agent_id=data.get("agent_id"),
            user_id=data.get("user_id", "anonymous"),
            title=data.get("title"),
            model=data.get("model"),
        )
        self.session.add(conv)
        await self.session.commit()
        await self.session.refresh(conv)
        # Reload with agent relationship
        return await self.get(str(conv.id))

    async def update(self, conv_id: str, updates: Dict[str, Any]) -> Optional[Dict]:
        result = await self.session.execute(
            select(Conversation).where(Conversation.id == conv_id)
        )
        conv = result.scalar_one_or_none()
        if not conv:
            return None
        for key, value in updates.items():
            if hasattr(conv, key):
                setattr(conv, key, value)
        conv.updated_at = datetime.utcnow()
        await self.session.commit()
        return await self.get(conv_id)

    async def delete(self, conv_id: str) -> bool:
        result = await self.session.execute(
            delete(Conversation).where(Conversation.id == conv_id)
        )
        await self.session.commit()
        return result.rowcount > 0

    async def add_message(self, conv_id: str, data: Dict[str, Any]) -> Dict:
        msg = Message(
            conversation_id=conv_id,
            role=data["role"],
            content=data["content"],
            model=data.get("model"),
            tokens_used=data.get("tokens_used", 0),
            tool_calls=data.get("tool_calls"),
            tool_results=data.get("tool_results"),
            metadata_=data.get("metadata", {}),
        )
        self.session.add(msg)

        # Update conversation counters
        result = await self.session.execute(
            select(Conversation).where(Conversation.id == conv_id)
        )
        conv = result.scalar_one_or_none()
        if conv:
            conv.message_count = (conv.message_count or 0) + 1
            conv.total_tokens = (conv.total_tokens or 0) + (data.get("tokens_used", 0))
            conv.updated_at = datetime.utcnow()
            # Auto-title from first user message
            if not conv.title and data["role"] == "user":
                conv.title = data["content"][:100]

        await self.session.commit()
        await self.session.refresh(msg)
        return msg.to_dict()


# ── API Key Repository ────────────────────────────────────────────

class ApiKeyRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def generate(self, agent_id: str, data: Dict[str, Any]) -> Dict:
        raw_key = f"ubk-{secrets.token_urlsafe(32)}"
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        key_prefix = raw_key[:8]

        expires_at = None
        if data.get("expiresInDays"):
            expires_at = datetime.utcnow() + timedelta(days=data["expiresInDays"])

        api_key = ApiKey(
            agent_id=agent_id,
            name=data["name"],
            key_prefix=key_prefix,
            key_hash=key_hash,
            permissions=data.get("permissions", ["chat", "read"]),
            rate_limit=data.get("rateLimit", 100),
            expires_at=expires_at,
        )
        self.session.add(api_key)
        await self.session.commit()
        await self.session.refresh(api_key)

        result = api_key.to_dict()
        result["key"] = raw_key  # Only returned on creation
        return result

    async def list_for_agent(self, agent_id: str) -> List[Dict]:
        result = await self.session.execute(
            select(ApiKey)
            .where(ApiKey.agent_id == agent_id, ApiKey.is_active == True)
            .order_by(ApiKey.created_at.desc())
        )
        return [k.to_dict() for k in result.scalars().all()]

    async def get(self, key_id: str) -> Optional[Dict]:
        result = await self.session.execute(
            select(ApiKey).where(ApiKey.id == key_id)
        )
        key = result.scalar_one_or_none()
        return key.to_dict() if key else None

    async def revoke(self, agent_id: str, key_id: str) -> bool:
        result = await self.session.execute(
            select(ApiKey).where(ApiKey.id == key_id, ApiKey.agent_id == agent_id)
        )
        key = result.scalar_one_or_none()
        if not key:
            return False
        key.is_active = False
        await self.session.commit()
        return True


# ── Builder Session Repository ────────────────────────────────────

class BuilderSessionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create(self, session_id: Optional[str] = None, user_id: str = "anonymous") -> Dict:
        if session_id:
            result = await self.session.execute(
                select(BuilderSession).where(BuilderSession.id == session_id)
            )
            bs = result.scalar_one_or_none()
            if bs:
                return bs.to_dict()

        bs = BuilderSession(user_id=user_id)
        self.session.add(bs)
        await self.session.commit()
        await self.session.refresh(bs)
        return bs.to_dict()

    async def add_messages(self, session_id: str, user_msg: str, assistant_msg: str) -> Dict:
        result = await self.session.execute(
            select(BuilderSession).where(BuilderSession.id == session_id)
        )
        bs = result.scalar_one_or_none()
        if not bs:
            return None

        msgs = list(bs.messages or [])
        msgs.append({"role": "user", "content": user_msg})
        msgs.append({"role": "assistant", "content": assistant_msg})
        bs.messages = msgs
        bs.updated_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(bs)
        return bs.to_dict()

    async def get(self, session_id: str) -> Optional[Dict]:
        result = await self.session.execute(
            select(BuilderSession).where(BuilderSession.id == session_id)
        )
        bs = result.scalar_one_or_none()
        return bs.to_dict() if bs else None

    async def set_agent_config(self, session_id: str, config: Dict) -> Optional[Dict]:
        result = await self.session.execute(
            select(BuilderSession).where(BuilderSession.id == session_id)
        )
        bs = result.scalar_one_or_none()
        if not bs:
            return None
        bs.agent_config = config
        bs.status = "completed"
        bs.updated_at = datetime.utcnow()
        await self.session.commit()
        return bs.to_dict()


# ── Tool Execution Repository ─────────────────────────────────────

class ToolExecutionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, data: Dict[str, Any]) -> Dict:
        te = ToolExecution(
            conversation_id=data.get("conversation_id"),
            message_id=data.get("message_id"),
            agent_id=data.get("agent_id"),
            tool_name=data["tool_name"],
            input=data.get("input"),
            status="pending",
        )
        self.session.add(te)
        await self.session.commit()
        await self.session.refresh(te)
        return te.to_dict()

    async def complete(self, exec_id: str, output: Any, duration_ms: int, status: str = "completed") -> Optional[Dict]:
        result = await self.session.execute(
            select(ToolExecution).where(ToolExecution.id == exec_id)
        )
        te = result.scalar_one_or_none()
        if not te:
            return None
        te.output = output
        te.duration_ms = duration_ms
        te.status = status
        await self.session.commit()
        await self.session.refresh(te)
        return te.to_dict()

    async def list_for_conversation(self, conv_id: str) -> List[Dict]:
        result = await self.session.execute(
            select(ToolExecution)
            .where(ToolExecution.conversation_id == conv_id)
            .order_by(ToolExecution.created_at)
        )
        return [te.to_dict() for te in result.scalars().all()]
