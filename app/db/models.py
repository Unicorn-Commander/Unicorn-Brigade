"""
SQLAlchemy ORM models for Unicorn Brigade.
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.timezones import BUSINESS_TIMEZONE
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
    # Explicit reporting line — the agent this one reports to. Brigade is the
    # registry for agent IDENTITY (name, rank, title, avatar), so it owns the
    # ORG CHART too: a consumer should read the chain of command, not re-derive
    # it. Before this column both Brigade's and Stable's org charts inferred
    # parentage from `rank` + `domain` in two separate implementations, which
    # meant two heuristics that could (and did) disagree about a chain of
    # command nobody had actually stated.
    #
    # NULL = the apex (reports to no one) OR "not stated yet" — a consumer that
    # sees no reporting line anywhere in the roster falls back to its own
    # rank/domain heuristic, so a stale Brigade degrades instead of flattening
    # the chart. ON DELETE SET NULL so removing a lead orphans its reports back
    # onto that fallback rather than cascading a whole subtree into oblivion.
    reports_to = Column(
        String(255),
        ForeignKey("agents.id", ondelete="SET NULL"),
        nullable=True,
    )
    status = Column(String(50), default="active")
    type = Column(String(50), default="individual")
    agent_type = Column(String(50), default="analysis")
    capabilities = Column(JSON, default=list)
    model = Column(String(255), default="uc/chat-default-nothink")
    temperature = Column(Float, default=0.7)
    max_tokens = Column(Integer, default=2000)
    tools = Column(JSON, default=list)
    # BR-1.4 shared-catalog tenancy: org_id stays NULLABLE — a NULL org_id is a
    # GLOBAL/shared agent visible to every org (seed roster). The server_default
    # mirrors the 8 sibling tables so a tenant-created agent auto-lands in the
    # caller's org (RLS WITH CHECK org_id = current_org_id() then passes) without
    # each call site setting org_id. The admin shared path inserts an explicit
    # NULL via the owner session (see app/api/agent_routes.create_agent).
    org_id = Column(UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, server_default=text("current_org_id()"))
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
        Index("ix_agents_org_id", "org_id"),
        # Org-chart reads walk children-of-a-lead; without this every expansion
        # of the tree is a seq scan over the roster.
        Index("ix_agents_reports_to", "reports_to"),
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
            "reportsTo": self.reports_to,
            "status": self.status,
            "type": self.type,
            "agentType": self.agent_type,
            "capabilities": self._as_str_list(self.capabilities),
            "model": self.model,
            "temperature": self.temperature,
            "maxTokens": self.max_tokens,
            "tools": self._as_str_list(self.tools),
            "orgId": str(self.org_id) if self.org_id else None,
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


class Organization(Base):
    __tablename__ = "organizations"

    # server_default so a raw INSERT that omits id (the migration's 'early-access'
    # bootstrap seed) still gets a uuid. create_all builds this table BEFORE the
    # migration runs, so the model — not the migration's CREATE TABLE — is what
    # actually defines the column; without the DB-side default the seed INSERT
    # NULLs the PK and the whole migration transaction rolls back.
    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid,
                server_default=text("gen_random_uuid()"))
    name = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, nullable=False)
    plan_tier = Column(String(50), nullable=False, server_default="free", default="free")
    api_calls_limit = Column(Integer, nullable=False, server_default="0", default=0)
    metadata_ = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    memberships = relationship("OrgMembership", back_populates="organization", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": str(self.id),
            "name": self.name,
            "slug": self.slug,
            "planTier": self.plan_tier,
            "apiCallsLimit": self.api_calls_limit,
            "metadata": self.metadata_ or {},
            "createdAt": self.created_at.isoformat() + "Z" if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() + "Z" if self.updated_at else None,
        }


class OrgMembership(Base):
    __tablename__ = "org_memberships"

    # server_default for the same reason as Organization.id: the migration's
    # backfill INSERT ... SELECT omits id and would otherwise NULL the PK.
    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid,
                server_default=text("gen_random_uuid()"))
    org_id = Column(UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(50), nullable=False, server_default="owner", default="owner")
    created_at = Column(DateTime, default=datetime.utcnow)

    organization = relationship("Organization", back_populates="memberships")

    __table_args__ = (
        UniqueConstraint("org_id", "user_id", name="uq_org_memberships_org_user"),
        Index("ix_org_memberships_user_id", "user_id"),
        Index("ix_org_memberships_org_id", "org_id"),
    )

    def to_dict(self):
        return {
            "id": str(self.id),
            "orgId": str(self.org_id),
            "userId": str(self.user_id),
            "role": self.role,
            "createdAt": self.created_at.isoformat() + "Z" if self.created_at else None,
        }


class Invitation(Base):
    """BR-2.1 invite-by-email: a bearer-token invitation to join an organization.

    The ``token`` is the capability — whoever holds it and is authenticated can
    accept, minting an ``OrgMembership`` for the accepting user (idempotent,
    expiry-checked). Invitations carry ``org_id`` and are RLS-isolated exactly
    like the tenant data tables (ENABLE + FORCE, ``org_id = current_org_id()``),
    so create/list/revoke on the RLS-subject request session only ever touch the
    caller's active org. ACCEPT is the one inherently cross-tenant step (the
    invitee is not yet a member of the org, so their GUC is bound elsewhere) and
    runs on the RLS-exempt ``admin_session`` — the same precedent the scheduler
    uses for its cross-org enumeration. The ``current_org_id()`` server_default
    mirrors the data tables so a request-session INSERT that omits org_id
    auto-tags the caller's active org and passes WITH CHECK.
    """
    __tablename__ = "invitations"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid,
                server_default=text("gen_random_uuid()"))
    org_id = Column(UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"),
                    nullable=False, server_default=text("current_org_id()"))
    email = Column(String(255), nullable=False)
    # Role granted on acceptance. owner is never invitable (an org has exactly the
    # owner who created it); the service clamps anything unexpected to 'member'.
    role = Column(String(50), nullable=False, server_default="member", default="member")
    token = Column(String(255), nullable=False, unique=True)
    # pending | accepted | revoked | expired
    status = Column(String(50), nullable=False, server_default="pending", default="pending")
    invited_by = Column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    accepted_by = Column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    expires_at = Column(DateTime, nullable=True)
    accepted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_invitations_org_id", "org_id"),
        Index("ix_invitations_email", "email"),
    )

    def to_dict(self, include_token=False):
        d = {
            "id": str(self.id),
            "orgId": str(self.org_id),
            "email": self.email,
            "role": self.role,
            "status": self.status,
            "invitedBy": str(self.invited_by) if self.invited_by else None,
            "acceptedBy": str(self.accepted_by) if self.accepted_by else None,
            "expiresAt": self.expires_at.isoformat() + "Z" if self.expires_at else None,
            "acceptedAt": self.accepted_at.isoformat() + "Z" if self.accepted_at else None,
            "createdAt": self.created_at.isoformat() + "Z" if self.created_at else None,
        }
        # The token is a secret capability. Only returned to the owner/admin who
        # created the invite (so they can hand it to the invitee out-of-band).
        if include_token:
            d["token"] = self.token
        return d


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    agent_id = Column(String(255), ForeignKey("agents.id", ondelete="SET NULL"), nullable=True)
    user_id = Column(String(255), default="anonymous")
    org_id = Column(UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, server_default=text("current_org_id()"))
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
        Index("ix_conversations_org_id", "org_id"),
        Index("ix_conversations_agent_id", "agent_id"),
        Index("ix_conversations_created_at", "created_at"),
    )

    def to_dict(self, include_messages=False):
        d = {
            "id": str(self.id),
            "agent_id": self.agent_id,
            "user_id": self.user_id,
            "org_id": str(self.org_id) if self.org_id else None,
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
    org_id = Column(UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, server_default=text("current_org_id()"))
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
        Index("ix_messages_org_id", "org_id"),
    )

    def to_dict(self):
        return {
            "id": str(self.id),
            "conversation_id": str(self.conversation_id),
            "org_id": str(self.org_id) if self.org_id else None,
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
    # (conversations, builder sessions, personal API keys, and per-user agent
    # memory) stops forking by how they signed in. See
    # app/auth/middleware.resolve_canonical_user_id.
    #
    # Not every store is relabeled the same way. Conversations + builder sessions
    # are SQL rows remapped in place. Per-user agent MEMORY (Graphiti/FalkorDB)
    # is different: episodes were stored under a group_id of `{user_id}__{agent}`,
    # so pre-cutover memory sits under `{sub}__{agent}`. That graph store is NOT
    # relabeled by any SQL remap; instead the retrieval path DUAL-READS the legacy
    # namespace via this keycloak_id while writes stay canonical. See
    # app/memory/graphiti_manager `_read_group_ids`.
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
    # BR-2.4 per-key org binding (closes finding H1). The org this service/agent
    # key acts as. The auth middleware (``_bind_org_context``) binds the request's
    # RLS org (``app.current_org_id``) to THIS value for a keyless service/agent
    # key, so two customers' keys are isolated instead of both collapsing onto the
    # shared 'early-access' org. NULLABLE + server_default current_org_id() exactly
    # like the tenant data tables: a key created by a bound request auto-tags the
    # caller's active org (also stamped explicitly in apikey_routes), and a legacy
    # key with a NULL org_id falls back to 'early-access' in the middleware so
    # nothing breaks on cutover. NOTE: api_keys deliberately carries NO RLS — the
    # key lookup in ``validate_api_key`` runs BEFORE any org is bound (empty GUC),
    # so FORCE RLS here would hide every key and break all auth. org_id is a binding
    # POINTER used to CHOOSE the org, not an RLS-isolated data column (mirrors how
    # users / organizations / org_memberships carry no RLS).
    org_id = Column(UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, server_default=text("current_org_id()"))
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
        Index("ix_api_keys_org_id", "org_id"),
    )

    def to_dict(self, include_hash=False):
        d = {
            "id": self.id,
            "agentId": self.agent_id,
            "orgId": str(self.org_id) if self.org_id else None,
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
    org_id = Column(UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, server_default=text("current_org_id()"))
    messages = Column(JSON, default=list)
    agent_config = Column(JSON)
    status = Column(String(50), default="in_progress")  # in_progress, completed, abandoned
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id": str(self.id),
            "user_id": self.user_id,
            "org_id": str(self.org_id) if self.org_id else None,
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
    org_id = Column(UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, server_default=text("current_org_id()"))
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
        Index("ix_tool_executions_org_id", "org_id"),
        Index("ix_tool_executions_agent_id", "agent_id"),
    )

    def to_dict(self):
        return {
            "id": str(self.id),
            "conversation_id": str(self.conversation_id) if self.conversation_id else None,
            "org_id": str(self.org_id) if self.org_id else None,
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
    org_id = Column(UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, server_default=text("current_org_id()"))
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    embedding = Column(JSON, nullable=False)        # 256-dim float list
    enrollment_count = Column(Integer, default=1)
    preferences = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_speaker_profiles_name", "name"),
        Index("ix_speaker_profiles_org_id", "org_id"),
    )

    def to_dict(self):
        return {
            "id": str(self.id),
            "name": self.name,
            "orgId": str(self.org_id) if self.org_id else None,
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
    org_id = Column(UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, server_default=text("current_org_id()"))
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
            "orgId": str(self.org_id) if self.org_id else None,
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
    org_id = Column(UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, server_default=text("current_org_id()"))
    agent_id = Column(String(255), ForeignKey("agents.id", ondelete="CASCADE"),
                      nullable=False, index=True)
    prompt = Column(Text, nullable=False)
    cron = Column(String(120), nullable=False)  # standard 5-field cron
    timezone = Column(String(64), nullable=False, default=BUSINESS_TIMEZONE)
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
    # P-00092: what this schedule is responsible for, in one or two plain
    # sentences. Shown as the ``responsibility`` of its autonomy-catalogue item.
    description = Column(Text, nullable=True)
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
            "orgId": str(self.org_id) if self.org_id else None,
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
            "description": self.description,
            "createdAt": self.created_at.isoformat() + "Z" if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() + "Z" if self.updated_at else None,
        }


class WorkflowExecutionRecord(Base):
    """BR-4 durable state: persisted snapshot of a hierarchical WorkflowExecution.

    The 3-tier workflow engine (app/workflows/engine.py) kept every
    ``WorkflowExecution`` — including HITL checkpoint state — only in an
    in-memory ``dict``, so an execution (and any pending human-approval
    checkpoint) was LOST on process restart and INVISIBLE to a second replica.
    This table is the write-through durable mirror: the engine upserts the full
    ``WorkflowExecution`` (as JSON) on each state transition and rehydrates
    in-flight rows on startup. The indexed columns (``state``, ``workflow_id``)
    are denormalised from ``data`` purely so rehydration can cheaply select the
    non-terminal set without deserialising every blob.

    Tenancy note (mirrors the scheduler / api_keys precedent): the workflow
    engine is a trusted cross-org SYSTEM component that reads via the
    RLS-exempt ``admin_session`` and intentionally exposes executions globally
    (preserving the pre-existing in-memory behaviour — the routes never filtered
    by org). ``org_id`` here is therefore a best-effort attribution POINTER, not
    an RLS isolation boundary, so this table deliberately carries NO RLS (like
    api_keys / users / organizations). Nullable because a background-task
    execution may have lost the request's org ContextVar.
    """
    __tablename__ = "workflow_executions"

    id = Column(String(64), primary_key=True)
    # Indexes are declared once, in __table_args__ below (not via index= on the
    # column) — declaring both would emit a duplicate CREATE INDEX in create_all.
    workflow_id = Column(String(255), nullable=False)
    workflow_name = Column(String(500))
    org_id = Column(UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"),
                    nullable=True, server_default=text("current_org_id()"))
    # pending | running | waiting_checkpoint | paused | completed | failed | cancelled
    state = Column(String(50), nullable=False, default="pending")
    current_step = Column(String(255), nullable=True)
    pending_checkpoint = Column(String(255), nullable=True)
    mission_id = Column(String(255), nullable=True)
    # Full WorkflowExecution.model_dump(mode="json") — the source of truth used
    # to reconstruct the pydantic object on rehydrate (WorkflowExecution
    # .model_validate(data)).
    data = Column(JSON, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_workflow_executions_state", "state"),
        Index("ix_workflow_executions_workflow_id", "workflow_id"),
        Index("ix_workflow_executions_org_id", "org_id"),
    )


class RalphExecutionRecord(Base):
    """BR-4 durable state: persisted snapshot of a Ralph self-correction run.

    ``RalphWorkflowState`` was persisted only to a per-process ``.ralph/*.json``
    file (local disk), so it was WRONG with two replicas (each has its own disk)
    and the in-memory ``_active_executions`` registry was LOST on restart. This
    table is the shared, durable store: the Ralph engine upserts its state (as
    JSON) at every iteration boundary and the routes rehydrate the active
    (non-complete) set on startup. Same tenancy posture as
    ``workflow_executions`` above — cross-org system bookkeeping via
    ``admin_session``, ``org_id`` a best-effort pointer, NO RLS.
    """
    __tablename__ = "ralph_executions"

    execution_id = Column(String(255), primary_key=True)
    # Indexes declared once, in __table_args__ below (see WorkflowExecutionRecord).
    workflow_id = Column(String(255), nullable=False)
    org_id = Column(UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"),
                    nullable=True, server_default=text("current_org_id()"))
    is_complete = Column(Boolean, nullable=False, default=False)
    is_paused = Column(Boolean, nullable=False, default=False)
    final_outcome = Column(String(50), nullable=True)
    # Full RalphWorkflowState.model_dump(mode="json").
    data = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_ralph_executions_is_complete", "is_complete"),
        Index("ix_ralph_executions_workflow_id", "workflow_id"),
        Index("ix_ralph_executions_org_id", "org_id"),
    )


class ScheduledRunHistory(Base):
    """One row per fired execution of a ScheduledRun."""
    __tablename__ = "scheduled_run_history"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    scheduled_run_id = Column(UUID(as_uuid=False),
                              ForeignKey("scheduled_runs.id", ondelete="CASCADE"),
                              nullable=False, index=True)
    org_id = Column(UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, server_default=text("current_org_id()"))
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    finished_at = Column(DateTime, nullable=True)
    status = Column(String(32), nullable=False, default="running")
    trigger = Column(
        String(16), nullable=False, default="schedule", server_default="schedule"
    )
    actor = Column(
        String(255), nullable=False, default="scheduler", server_default="scheduler"
    )
    output_summary = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    tool_calls_count = Column(Integer, nullable=False, default=0)

    scheduled_run = relationship("ScheduledRun", back_populates="history")

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "scheduledRunId": str(self.scheduled_run_id),
            "orgId": str(self.org_id) if self.org_id else None,
            "startedAt": self.started_at.isoformat() + "Z" if self.started_at else None,
            "finishedAt": self.finished_at.isoformat() + "Z" if self.finished_at else None,
            "status": self.status,
            "trigger": self.trigger,
            "actor": self.actor,
            "outputSummary": self.output_summary,
            "error": self.error,
            "toolCallsCount": self.tool_calls_count,
        }


def _iso_z(value):
    """Naive-UTC timestamp -> ISO 8601 with a trailing Z (the house JSON shape)."""
    return value.isoformat() + "Z" if value else None


class AutonomousJob(Base):
    """P-00092: an agent job that runs on its own OUTSIDE Brigade's scheduler.

    Cron on bigboy, a systemd timer on commander, a LaunchAgent on the Mac
    Studio, a Claude Code routine, a continuous watcher. The loop registers
    itself (``PUT /api/v1/autonomy/jobs/{key}``) and reports every run
    (``POST /api/v1/autonomy/jobs/{key}/runs``); the ``last_*`` columns mirror
    its latest report so the catalogue reads one row per job.

    Tenant data, RLS-isolated exactly like ``scheduled_runs``: ``org_id``
    defaults to the request's bound org and the
    ``autonomous_jobs_org_isolation`` policy (migration
    20261024_01_autonomy_catalogue) filters on ``org_id = current_org_id()``.
    ``key`` is unique per org, not globally.
    """
    __tablename__ = "autonomous_jobs"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid,
                server_default=text("gen_random_uuid()"))
    org_id = Column(UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"),
                    nullable=False, server_default=text("current_org_id()"))
    key = Column(String(120), nullable=False)
    name = Column(String(255), nullable=False)
    agent_id = Column(String(255), ForeignKey("agents.id", ondelete="SET NULL"), nullable=True)
    responsibility = Column(Text, nullable=False)
    host = Column(String(120), nullable=False)
    # cron | systemd | launchd | claude-routine | continuous | other
    runner = Column(String(32), nullable=False)
    schedule = Column(String(120), nullable=True)  # 5-field cron, standard semantics
    timezone = Column(String(64), nullable=False, default="UTC", server_default="UTC")
    schedule_note = Column(String(255), nullable=True)
    command = Column(String(500), nullable=True)  # script path / entry point, never a secret
    runbook_url = Column(String(500), nullable=True)
    owner = Column(String(255), nullable=True)
    # Free-text observations about the job (an audit's "BROKEN: script missing
    # since ...; found in: bigboy crontab line 7"). Never a secret.
    notes = Column(Text, nullable=True)
    enabled = Column(Boolean, nullable=False, default=True, server_default=text("true"))
    last_run_at = Column(DateTime, nullable=True)
    last_status = Column(String(16), nullable=True)  # running | success | error | timeout | skipped
    last_summary = Column(Text, nullable=True)
    last_error = Column(Text, nullable=True)  # cleared on a success
    last_duration_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow,
                        server_default=text("timezone('utc', now())"))
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow,
                        server_default=text("timezone('utc', now())"))

    __table_args__ = (
        UniqueConstraint("org_id", "key", name="uq_autonomous_jobs_org_key"),
        Index("ix_autonomous_jobs_org_id", "org_id"),
        Index("ix_autonomous_jobs_agent_id", "agent_id"),
    )

    def to_dict(self) -> dict:
        return {
            "id": str(self.id) if self.id else None,
            "orgId": str(self.org_id) if self.org_id else None,
            "key": self.key,
            "name": self.name,
            "agentId": self.agent_id,
            "responsibility": self.responsibility,
            "host": self.host,
            "runner": self.runner,
            "schedule": self.schedule,
            "timezone": self.timezone,
            "scheduleNote": self.schedule_note,
            "command": self.command,
            "runbookUrl": self.runbook_url,
            "owner": self.owner,
            "notes": self.notes,
            "enabled": self.enabled,
            "lastRunAt": _iso_z(self.last_run_at),
            "lastStatus": self.last_status,
            "lastSummary": self.last_summary,
            "lastError": self.last_error,
            "lastDurationMs": self.last_duration_ms,
            "createdAt": _iso_z(self.created_at),
            "updatedAt": _iso_z(self.updated_at),
        }


class AutonomousJobRun(Base):
    """P-00092: one reported run of an ``AutonomousJob`` (at most 200 kept per job).

    ``run_id`` is the CLIENT's idempotency key: a ``running`` report and the
    terminal report that follows it with the same run_id land on one row.
    RLS-isolated like ``scheduled_run_history``, including the WITH CHECK that
    the parent job belongs to the same org.
    """
    __tablename__ = "autonomous_job_runs"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid,
                server_default=text("gen_random_uuid()"))
    org_id = Column(UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"),
                    nullable=False, server_default=text("current_org_id()"))
    job_id = Column(UUID(as_uuid=False), ForeignKey("autonomous_jobs.id", ondelete="CASCADE"),
                    nullable=False)
    run_id = Column(String(120), nullable=True)
    status = Column(String(16), nullable=False)
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    summary = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow,
                        server_default=text("timezone('utc', now())"))

    __table_args__ = (
        Index("ix_autonomous_job_runs_org_id", "org_id"),
    )

    def to_dict(self) -> dict:
        return {
            "id": str(self.id) if self.id else None,
            "runId": self.run_id,
            "status": self.status,
            "startedAt": _iso_z(self.started_at),
            "finishedAt": _iso_z(self.finished_at),
            "durationMs": self.duration_ms,
            "summary": self.summary,
            "error": self.error,
        }


# Newest-first run history per job (the runs listing and the prune both walk it).
# Declared outside __table_args__ because it needs a DESC column expression.
Index(
    "ix_autonomous_job_runs_job_started",
    AutonomousJobRun.job_id,
    AutonomousJobRun.started_at.desc(),
)


class UsageEvent(Base):
    """BR-3.1/3.4/3.8 durable per-ORG usage ledger.

    Before BR-3 the ONLY metering was a best-effort fire-and-forget Lago event
    (``app/integrations/lago.py``) keyed on the USER email as
    ``external_customer_id`` — nothing durable, nothing per-org, and half the
    execution paths (A2A, MCP, hierarchical, scheduled, orchestration, the
    streaming shim) emitted no event at all. This table is the write-through
    durable ledger every metered path now appends to (see
    ``app/db/usage_ledger.py``): it is the source of truth for per-org usage
    aggregation AND the substrate the per-org cap preflight (BR-3.6) sums.

    Tenancy: this IS tenant data (a customer's usage must be invisible to other
    tenants), so — UNLIKE the BR-4 system-bookkeeping tables — it carries FULL
    RLS (ENABLE + FORCE + org-isolation policy, see the 20260720_01 migration),
    exactly like conversations / messages / tool_executions. ``org_id`` is the
    billing subject (BR-3.1): ``external_customer_id`` mirrors it so a row is
    self-describing against Lago. ``user_id`` is retained for per-user
    attribution WITHIN an org, never as the billing key. Writes come from the
    RLS-exempt ``admin_session`` with an explicit ``org_id`` (metering can run in
    a background task with no bound request org — mirrors execution_store), while
    the RLS policy guarantees any request-session READER (the future usage UI)
    only ever sees its own org.
    """
    __tablename__ = "usage_events"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    org_id = Column(UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"),
                    nullable=False, server_default=text("current_org_id()"))
    # BR-3.1: the billing subject. Stored explicitly (= org_id) so the row is
    # self-describing and matches the Lago event's external_customer_id.
    external_customer_id = Column(String(255), nullable=True)
    # Per-user attribution WITHIN the org (email / users.id). NOT the billing key.
    user_id = Column(String(255), nullable=True)
    # 'ai_api_call' (LLM COGS) | 'agent_work' (per-agent value) | 'tool_call' | 'workflow'
    event_type = Column(String(50), nullable=False, default="ai_api_call")
    # Which execution path produced it: agent_chat | openai_stream | openai_passthrough |
    # openai_dual | mlx | a2a | mcp_tool | hierarchical | scheduled_run | orchestration
    source = Column(String(50), nullable=False, default="unknown")
    agent_id = Column(String(255), nullable=True)
    model = Column(String(255), nullable=True)
    tokens = Column(Integer, nullable=False, default=0)
    cost = Column(Float, nullable=False, default=0.0)
    rate_tier = Column(String(50), nullable=True)
    rate_multiplier = Column(Float, nullable=False, default=1.0)
    outcome = Column(String(32), nullable=True)
    # The Lago transaction_id this event was emitted under (cross-ref + dedup).
    transaction_id = Column(String(255), nullable=True)
    # tools_used, byok, and any other backward-compatible dimensions.
    meta = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_usage_events_org_id", "org_id"),
        # Composite for the cap preflight's period sum (WHERE org_id AND created_at >= period_start).
        Index("ix_usage_events_org_created", "org_id", "created_at"),
        Index("ix_usage_events_event_type", "event_type"),
        Index("ix_usage_events_created_at", "created_at"),
    )

    def to_dict(self):
        return {
            "id": str(self.id),
            "orgId": str(self.org_id) if self.org_id else None,
            "externalCustomerId": self.external_customer_id,
            "userId": self.user_id,
            "eventType": self.event_type,
            "source": self.source,
            "agentId": self.agent_id,
            "model": self.model,
            "tokens": self.tokens,
            "cost": self.cost,
            "rateTier": self.rate_tier,
            "rateMultiplier": self.rate_multiplier,
            "outcome": self.outcome,
            "transactionId": self.transaction_id,
            "meta": self.meta or {},
            "createdAt": self.created_at.isoformat() + "Z" if self.created_at else None,
        }


class OrgBillingConfig(Base):
    """BR-3.6 per-org billing configuration — the ceiling the preflight enforces.

    One row per org. A NULL cap means "unlimited" (fall back to the env default
    ``BRIGADE_DEFAULT_ORG_MONTHLY_TOKEN_CAP`` / ``..._COST_CAP``, 0/absent =
    unlimited). ``hard_stop`` gates whether hitting the ceiling actually 402s
    (True) or is soft/observe-only (False).

    NO RLS — deliberately, and like ``organizations`` / ``api_keys``: this is a
    config/pointer table keyed BY org, read+written by the RLS-exempt
    ``admin_session`` in the preflight (which runs before/around a request and
    must read an arbitrary org's cap by id, not only the bound one). It holds no
    cross-tenant-sensitive rows — just the caps — so it stays out of the RLS
    isolation surface (the usage_events table above is where isolation matters).
    """
    __tablename__ = "org_billing_config"

    org_id = Column(UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"),
                    primary_key=True)
    monthly_token_cap = Column(BigInteger, nullable=True)   # NULL / 0 => unlimited
    monthly_cost_cap = Column(Float, nullable=True)         # NULL / 0 => unlimited
    hard_stop = Column(Boolean, nullable=False, default=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            "orgId": str(self.org_id),
            "monthlyTokenCap": int(self.monthly_token_cap) if self.monthly_token_cap else None,
            "monthlyCostCap": float(self.monthly_cost_cap) if self.monthly_cost_cap else None,
            "hardStop": bool(self.hard_stop),
            "notes": self.notes,
            "createdAt": self.created_at.isoformat() + "Z" if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() + "Z" if self.updated_at else None,
        }
