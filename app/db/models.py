"""
SQLAlchemy ORM models for Unicorn Brigade.
"""
import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Text, Float, Integer, Boolean, DateTime,
    ForeignKey, JSON, Index
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.database import Base


def gen_uuid():
    return str(uuid.uuid4())


class Agent(Base):
    __tablename__ = "agents"

    id = Column(String(255), primary_key=True)
    name = Column(String(255), nullable=False)
    display_name = Column(String(255))
    title = Column(String(255))
    rank = Column(String(50))
    avatar = Column(String(50), default="🦄")
    bio = Column(Text)
    persona = Column(Text)
    system_prompt = Column(Text)
    domain = Column(String(100), default="general")
    subdomain = Column(String(100))
    status = Column(String(50), default="active")
    type = Column(String(50), default="individual")
    agent_type = Column(String(50), default="analysis")
    capabilities = Column(JSON, default=list)
    model = Column(String(255), default="openai/gpt-4o-mini")
    temperature = Column(Float, default=0.7)
    max_tokens = Column(Integer, default=2000)
    tools = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    conversations = relationship("Conversation", back_populates="agent", cascade="all, delete-orphan")
    api_keys = relationship("ApiKey", back_populates="agent", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_agents_domain", "domain"),
        Index("ix_agents_status", "status"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "displayName": self.display_name,
            "title": self.title,
            "rank": self.rank,
            "avatar": self.avatar,
            "bio": self.bio,
            "persona": self.persona,
            "systemPrompt": self.system_prompt,
            "domain": self.domain,
            "subdomain": self.subdomain,
            "status": self.status,
            "type": self.type,
            "agentType": self.agent_type,
            "capabilities": self.capabilities or [],
            "model": self.model,
            "temperature": self.temperature,
            "maxTokens": self.max_tokens,
            "tools": self.tools or [],
            "createdAt": self.created_at.isoformat() + "Z" if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() + "Z" if self.updated_at else None,
        }


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    agent_id = Column(String(255), ForeignKey("agents.id", ondelete="SET NULL"), nullable=True)
    user_id = Column(String(255), default="anonymous")
    title = Column(String(500))
    model = Column(String(255))
    status = Column(String(50), default="active")
    message_count = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    agent = relationship("Agent", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan",
                          order_by="Message.created_at")

    __table_args__ = (
        Index("ix_conversations_user_id", "user_id"),
        Index("ix_conversations_agent_id", "agent_id"),
        Index("ix_conversations_created_at", "created_at"),
    )

    def to_dict(self, include_messages=False):
        d = {
            "id": str(self.id),
            "agent_id": self.agent_id,
            "user_id": self.user_id,
            "title": self.title,
            "model": self.model,
            "status": self.status,
            "message_count": self.message_count,
            "total_tokens": self.total_tokens,
            "created_at": self.created_at.isoformat() + "Z" if self.created_at else None,
            "updated_at": self.updated_at.isoformat() + "Z" if self.updated_at else None,
        }
        if self.agent:
            d["agent"] = {
                "id": self.agent.id,
                "name": self.agent.name,
                "displayName": self.agent.display_name,
                "avatar": self.agent.avatar,
            }
        if include_messages:
            d["messages"] = [m.to_dict() for m in (self.messages or [])]
        return d


class Message(Base):
    __tablename__ = "messages"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    conversation_id = Column(UUID(as_uuid=False), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(50), nullable=False)  # user, assistant, system, tool
    content = Column(Text, nullable=False)
    model = Column(String(255))
    tokens_used = Column(Integer, default=0)
    tool_calls = Column(JSON)
    tool_results = Column(JSON)
    metadata_ = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    conversation = relationship("Conversation", back_populates="messages")

    __table_args__ = (
        Index("ix_messages_conversation_id", "conversation_id"),
    )

    def to_dict(self):
        return {
            "id": str(self.id),
            "conversation_id": str(self.conversation_id),
            "role": self.role,
            "content": self.content,
            "model": self.model,
            "tokens_used": self.tokens_used,
            "tool_calls": self.tool_calls,
            "tool_results": self.tool_results,
            "metadata": self.metadata_,
            "created_at": self.created_at.isoformat() + "Z" if self.created_at else None,
        }


class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(String(255), primary_key=True, default=lambda: uuid.uuid4().hex[:16])
    agent_id = Column(String(255), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    key_prefix = Column(String(20), nullable=False)
    key_hash = Column(String(255), nullable=False)
    permissions = Column(JSON, default=lambda: ["chat", "read"])
    rate_limit = Column(Integer, default=100)
    expires_at = Column(DateTime, nullable=True)
    last_used_at = Column(DateTime, nullable=True)
    usage_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    agent = relationship("Agent", back_populates="api_keys")

    __table_args__ = (
        Index("ix_api_keys_agent_id", "agent_id"),
        Index("ix_api_keys_key_hash", "key_hash"),
    )

    def to_dict(self, include_hash=False):
        d = {
            "id": self.id,
            "agentId": self.agent_id,
            "name": self.name,
            "keyPrefix": self.key_prefix,
            "permissions": self.permissions or ["chat", "read"],
            "rateLimit": self.rate_limit,
            "expiresAt": self.expires_at.isoformat() if self.expires_at else None,
            "lastUsedAt": self.last_used_at.isoformat() if self.last_used_at else None,
            "usageCount": self.usage_count,
            "isActive": self.is_active,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }
        if include_hash:
            d["keyHash"] = self.key_hash
        return d


class BuilderSession(Base):
    __tablename__ = "builder_sessions"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    user_id = Column(String(255), default="anonymous")
    messages = Column(JSON, default=list)
    agent_config = Column(JSON)
    status = Column(String(50), default="in_progress")  # in_progress, completed, abandoned
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id": str(self.id),
            "user_id": self.user_id,
            "messages": self.messages or [],
            "agent_config": self.agent_config,
            "status": self.status,
            "created_at": self.created_at.isoformat() + "Z" if self.created_at else None,
            "updated_at": self.updated_at.isoformat() + "Z" if self.updated_at else None,
        }


class ToolExecution(Base):
    __tablename__ = "tool_executions"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    conversation_id = Column(UUID(as_uuid=False), ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True)
    message_id = Column(UUID(as_uuid=False), nullable=True)
    agent_id = Column(String(255), ForeignKey("agents.id", ondelete="SET NULL"), nullable=True)
    tool_name = Column(String(255), nullable=False)
    input = Column(JSON)
    output = Column(JSON)
    status = Column(String(50), default="pending")  # pending, running, completed, failed
    duration_ms = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_tool_executions_conversation_id", "conversation_id"),
        Index("ix_tool_executions_agent_id", "agent_id"),
    )

    def to_dict(self):
        return {
            "id": str(self.id),
            "conversation_id": str(self.conversation_id) if self.conversation_id else None,
            "message_id": str(self.message_id) if self.message_id else None,
            "agent_id": self.agent_id,
            "tool_name": self.tool_name,
            "input": self.input,
            "output": self.output,
            "status": self.status,
            "duration_ms": self.duration_ms,
            "created_at": self.created_at.isoformat() + "Z" if self.created_at else None,
        }
