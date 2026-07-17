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
    # Optional image avatar (absolute or site-relative URL). When set, UIs
    # prefer it over the /avatars/<id>.webp convention and the emoji fallback.
    avatar_url = Column(Text, nullable=True)
    bio = Column(Text)
    persona = Column(Text)
    system_prompt = Column(Text)
    domain = Column(String(100), default="general")
    subdomain = Column(String(100))
    status = Column(String(50), default="active")
    type = Column(String(50), default="individual")
    agent_type = Column(String(50), default="analysis")
    capabilities = Column(JSON, default=list)
    model = Column(String(255), default="uc/chat-default-nothink")
    temperature = Column(Float, default=0.7)
    max_tokens = Column(Integer, default=2000)
    tools = Column(JSON, default=list)
    # Per-agent value-billing (additive; neutral defaults = no change to what's
    # charged today). billing_tier feeds the rate_tier dimension on the
    # agent_work event; rate_multiplier + base_price_per_call let a Lago plan
    # price an agent's delivered work above raw LLM cost.
    billing_tier = Column(String(50), nullable=False, server_default="standard", default="standard")
    rate_multiplier = Column(Float, nullable=False, server_default="1.0", default=1.0)
    base_price_per_call = Column(Float, nullable=True)
    # Workforce classification (additive; nullable = honestly unset). Surfaced to
    # the roster so both Brigade and Stable can colour-code who is an employee
    # (local model we own) vs frontier (metered API) vs contractor/third_party.
    # Best-guessed from `model` on first migrate; operator corrects in place.
    #   employee | contractor | third_party | frontier
    affiliation = Column(String(32), nullable=True)
    # RBAC access policy. Shape (all fields optional; OR semantics, admins always pass):
    #   {"public": true}                         -- anyone can access (default)
    #   {"users": ["alice@x.com", "bob@y.com"]}  -- allowlist by email
    #   {"tiers": ["admin", "gpu-enabled"]}      -- allowlist by user tier
    # An absent/null policy = public. Mix fields to widen access.
    access_policy = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    conversations = relationship("Conversation", back_populates="agent", cascade="all, delete-orphan")
    api_keys = relationship("ApiKey", back_populates="agent", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_agents_domain", "domain"),
        Index("ix_agents_status", "status"),
    )

    @staticmethod
    def _as_str_list(value):
        """JSON columns written by different clients hold lists, dicts
        ({"cap": true}) or bare strings; the API contract is List[str]."""
        if not value:
            return []
        if isinstance(value, list):
            return [str(v) for v in value]
        if isinstance(value, dict):
            return [str(k) for k, v in value.items() if v]
        return [str(value)]

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "displayName": self.display_name,
            "title": self.title,
            "rank": self.rank,
            "avatar": self.avatar,
            "avatarUrl": self.avatar_url,
            "bio": self.bio,
            "persona": self.persona,
            "systemPrompt": self.system_prompt,
            "domain": self.domain,
            "subdomain": self.subdomain,
            "status": self.status,
            "type": self.type,
            "agentType": self.agent_type,
            "capabilities": self._as_str_list(self.capabilities),
            "model": self.model,
            "temperature": self.temperature,
            "maxTokens": self.max_tokens,
            "tools": self._as_str_list(self.tools),
            "billingTier": self.billing_tier,
            "rateMultiplier": self.rate_multiplier,
            "basePricePerCall": self.base_price_per_call,
            "affiliation": self.affiliation,
            "accessPolicy": self.access_policy,
            "createdAt": self.created_at.isoformat() + "Z" if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() + "Z" if self.updated_at else None,
        }


class ToolCatalog(Base):
    """Cost/permission metadata for the tool names agents reference in `tools`.

    Seeded with a best-guess catalog (see app/db/migrations.py) and meant to be
    corrected in place by an operator. `cost_tier` flags tools that cost money
    (paid / subscription); `permission_level` (1..5) gates a tool behind agent
    rank/capability; `external` marks tools that reach outside our infra.
    """
    __tablename__ = "tool_catalog"

    name = Column(String(100), primary_key=True)
    display_name = Column(String(150))
    description = Column(Text)
    cost_tier = Column(String(20), nullable=False, server_default="free", default="free")
    permission_level = Column(Integer, nullable=False, server_default="1", default=1)
    provider = Column(String(50))
    external = Column(Boolean, nullable=False, server_default="false", default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "name": self.name,
            "displayName": self.display_name,
            "description": self.description,
            "costTier": self.cost_tier,
            "permissionLevel": self.permission_level,
            "provider": self.provider,
            "external": self.external,
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


class User(Base):
    """User account model for authentication"""
    __tablename__ = "users"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    email = Column(String(255), unique=True, nullable=False)  # unique implies index
    # Canonical Keycloak binding (BR-1.1). The Keycloak `sub` claim is the stable
    # per-human identifier across every auth method. Nullable because native /
    # legacy rows predate SSO and only learn their sub on first Keycloak login;
    # unique so two users rows can never claim the same sub. Once set, ALL auth
    # paths resolve this same local `users.id` for the human, so their data
    # (conversations, builder sessions, personal API keys) stops forking by how
    # they signed in. See app/auth/middleware.resolve_canonical_user_id.
    keycloak_id = Column(String(255), unique=True, nullable=True, index=True)
    password_hash = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)
    role = Column(String(50), default="operator", index=True)  # admin, operator, viewer
    apps = Column(JSON, default=list)  # which Brigade-consumer apps this user is a member of
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    api_keys = relationship("UserApiKey", back_populates="user", cascade="all, delete-orphan")

    def to_dict(self):
        """Convert to dictionary without exposing password hash"""
        return {
            "id": str(self.id),
            "email": self.email,
            "keycloakId": self.keycloak_id,
            "name": self.name,
            "role": self.role,
            "isActive": self.is_active,
            "createdAt": self.created_at.isoformat() + "Z" if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() + "Z" if self.updated_at else None,
        }


class UserApiKey(Base):
    """API keys owned by users (not agents)"""
    __tablename__ = "user_api_keys"

    id = Column(String(255), primary_key=True, default=lambda: uuid.uuid4().hex[:16])
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
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
    created_via = Column(String(50), nullable=True)

    # Relationships
    user = relationship("User", back_populates="api_keys")

    __table_args__ = (
        Index("ix_user_api_keys_user_id", "user_id"),
        Index("ix_user_api_keys_key_hash", "key_hash"),
    )

    def to_dict(self, include_hash=False):
        d = {
            "id": self.id,
            "userId": str(self.user_id),
            "name": self.name,
            "keyPrefix": self.key_prefix,
            "permissions": self.permissions or ["chat", "read"],
            "rateLimit": self.rate_limit,
            "expiresAt": self.expires_at.isoformat() if self.expires_at else None,
            "lastUsedAt": self.last_used_at.isoformat() if self.last_used_at else None,
            "usageCount": self.usage_count,
            "isActive": self.is_active,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "createdVia": self.created_via,
        }
        if include_hash:
            d["keyHash"] = self.key_hash
        return d


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


class SpeakerProfile(Base):
    """Voice speaker profile for speaker identification."""
    __tablename__ = "speaker_profiles"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    name = Column(String(255), nullable=False)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    embedding = Column(JSON, nullable=False)        # 256-dim float list
    enrollment_count = Column(Integer, default=1)
    preferences = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_speaker_profiles_name", "name"),
    )

    def to_dict(self):
        return {
            "id": str(self.id),
            "name": self.name,
            "userId": str(self.user_id) if self.user_id else None,
            "embedding": self.embedding,
            "enrollmentCount": self.enrollment_count,
            "preferences": self.preferences or {},
            "createdAt": self.created_at.isoformat() + "Z" if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() + "Z" if self.updated_at else None,
        }


class CodeAttribution(Base):
    """
    Code attribution tracking for agent-generated code.

    Implements the Agent Trace spec (https://agent-trace.dev/) for tracking
    which AI agents/models generated which code.
    """
    __tablename__ = "code_attributions"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    session_id = Column(String(255), nullable=False, index=True)  # Conversation or session ID
    agent_id = Column(String(255), ForeignKey("agents.id", ondelete="SET NULL"), nullable=True, index=True)
    agent_name = Column(String(255), nullable=False)
    model = Column(String(255), nullable=False)
    file_path = Column(String(1000), nullable=False, index=True)
    start_line = Column(Integer, nullable=False)
    end_line = Column(Integer, nullable=False)
    change_type = Column(String(50), nullable=False, default="generation")  # generation, edit, deletion
    code_hash = Column(String(32), nullable=False, index=True)  # SHA-256 hash (first 16 chars)
    prompt = Column(Text, nullable=True)  # User prompt that generated this code
    generated_code = Column(Text, nullable=False)  # The actual generated code
    metadata_ = Column("metadata", JSON, default=dict)  # Tool calls, tokens, language, etc.
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Indexes already created via index=True on each Column above

    def to_dict(self):
        return {
            "id": str(self.id),
            "sessionId": self.session_id,
            "agentId": self.agent_id,
            "agentName": self.agent_name,
            "model": self.model,
            "filePath": self.file_path,
            "startLine": self.start_line,
            "endLine": self.end_line,
            "changeType": self.change_type,
            "codeHash": self.code_hash,
            "prompt": self.prompt,
            "generatedCode": self.generated_code,
            "metadata": self.metadata_,
            "createdAt": self.created_at.isoformat() + "Z" if self.created_at else None,
        }


class ScheduledRun(Base):
    """
    Persistent cron-style scheduled invocations of Brigade agents.

    Owned source-of-truth for the Brigade scheduler. APScheduler is used
    only as the in-memory cron engine; on every restart the runtime reads
    these rows and (re)registers triggers. This keeps schedule storage
    explicit and inspectable, instead of pickled inside an APScheduler
    job-store.
    """
    __tablename__ = "scheduled_runs"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    name = Column(String(255), nullable=False)
    agent_id = Column(String(255), ForeignKey("agents.id", ondelete="CASCADE"),
                      nullable=False, index=True)
    prompt = Column(Text, nullable=False)
    cron = Column(String(120), nullable=False)  # standard 5-field cron
    timezone = Column(String(64), nullable=False, default="UTC")
    # Free-form opaque user identifier. NOT a FK to users.id, because
    # scheduled runs frequently target a downstream service's user namespace
    # (e.g. Project-Ops user uuids) — that id is passed straight through as
    # the `user_id` on the chat call, where downstream tools mint per-user
    # JWTs from it. Validating against Brigade's local users table here would
    # break that pass-through.
    owner_user_id = Column(UUID(as_uuid=False), nullable=True, index=True)
    enabled = Column(Boolean, nullable=False, default=True, index=True)
    max_runtime_seconds = Column(Integer, nullable=False, default=300)
    last_run_at = Column(DateTime, nullable=True)
    last_status = Column(String(32), nullable=True)  # success | error | timeout | skipped
    last_result_summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    history = relationship(
        "ScheduledRunHistory",
        back_populates="scheduled_run",
        cascade="all, delete-orphan",
        order_by="desc(ScheduledRunHistory.started_at)",
    )

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "name": self.name,
            "agentId": self.agent_id,
            "prompt": self.prompt,
            "cron": self.cron,
            "timezone": self.timezone,
            "ownerUserId": str(self.owner_user_id) if self.owner_user_id else None,
            "enabled": self.enabled,
            "maxRuntimeSeconds": self.max_runtime_seconds,
            "lastRunAt": self.last_run_at.isoformat() + "Z" if self.last_run_at else None,
            "lastStatus": self.last_status,
            "lastResultSummary": self.last_result_summary,
            "createdAt": self.created_at.isoformat() + "Z" if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() + "Z" if self.updated_at else None,
        }


class ScheduledRunHistory(Base):
    """One row per fired execution of a ScheduledRun."""
    __tablename__ = "scheduled_run_history"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    scheduled_run_id = Column(UUID(as_uuid=False),
                              ForeignKey("scheduled_runs.id", ondelete="CASCADE"),
                              nullable=False, index=True)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    finished_at = Column(DateTime, nullable=True)
    status = Column(String(32), nullable=False, default="running")
    output_summary = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    tool_calls_count = Column(Integer, nullable=False, default=0)

    scheduled_run = relationship("ScheduledRun", back_populates="history")

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "scheduledRunId": str(self.scheduled_run_id),
            "startedAt": self.started_at.isoformat() + "Z" if self.started_at else None,
            "finishedAt": self.finished_at.isoformat() + "Z" if self.finished_at else None,
            "status": self.status,
            "outputSummary": self.output_summary,
            "error": self.error,
            "toolCallsCount": self.tool_calls_count,
        }
