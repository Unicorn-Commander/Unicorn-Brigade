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

from app.db.models import Agent, Conversation, Message, ApiKey, BuilderSession, ToolExecution, User, UserApiKey, CodeAttribution, SpeakerProfile
from app.db.database import ensure_org_context

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
        # BR-RLS: a prior commit in this request may have released the connection;
        # re-assert the org GUC so this write cannot be silently rejected by RLS.
        await ensure_org_context(self.session)
        agent = Agent(
            id=data.get("id") or data.get("name", "").lower().replace(" ", "-"),
            name=data["name"],
            display_name=data.get("displayName"),
            title=data.get("title"),
            rank=data.get("rank"),
            avatar=data.get("avatar", "🦄"),
            avatar_url=data.get("avatarUrl"),
            bio=data.get("bio"),
            persona=data.get("persona"),
            system_prompt=data.get("systemPrompt"),
            domain=data.get("domain", "general"),
            subdomain=data.get("subdomain"),
            # Registration-time reporting line: an agent states who it reports
            # to when it joins the roster, the same way it states its avatar,
            # instead of leaving every consumer to guess from rank + domain.
            reports_to=data.get("reportsTo"),
            status=data.get("status", "active"),
            type=data.get("type", "individual"),
            agent_type=data.get("agentType", "analysis"),
            capabilities=data.get("capabilities", []),
            model=data.get("model", "openai/gpt-4o-mini"),
            temperature=data.get("temperature", 0.7),
            max_tokens=data.get("maxTokens", 2000),
            tools=data.get("tools", []),
            billing_tier=data.get("billingTier", "standard"),
            rate_multiplier=data.get("rateMultiplier", 1.0),
            base_price_per_call=data.get("basePricePerCall"),
        )
        # BR-1.4: only set org_id when the caller explicitly provides it. When the
        # key is ABSENT we leave the attribute unset so the DB server_default
        # (current_org_id()) tags the row with the caller's bound org and the RLS
        # WITH CHECK passes. An explicit None is the admin SHARED-agent path (a
        # global NULL-org row) and must be inserted via the owner/admin session.
        if "org_id" in data:
            agent.org_id = data["org_id"]
        self.session.add(agent)
        # BR-1.4 (RLS): FLUSH (not a post-commit refresh) to materialise the row.
        # The INSERT emits ``... RETURNING agents.org_id``, so the server_default
        # ``current_org_id()`` is evaluated and read back INSIDE the caller's
        # transaction — where the ``app.current_org_id`` GUC is bound and the RLS
        # WITH CHECK is enforced — fully populating the ORM object.
        #
        # We must NOT ``refresh()`` AFTER commit: refresh issues a fresh by-PK
        # SELECT that the agents SELECT policy filters by
        # ``org_id IS NULL OR org_id = current_org_id()``. If the org GUC is not
        # present on the connection at that instant (a per-request session-scope
        # GUC that was never committed, or was reverted/cleared — e.g. the pooled
        # connection's org context between transactions), the just-inserted row is
        # invisible and SQLAlchemy raises "Could not refresh instance" → a 500 on
        # the normal per-org create. ``expire_on_commit=False`` (see
        # app/db/database.py) keeps the flushed attributes valid after commit, so
        # ``to_dict()`` needs no second SELECT. Isolation is unchanged: the write
        # still ran on the RLS-subject request session and WITH CHECK still bound
        # the row to the caller's org.
        await self.session.flush()
        await self.session.commit()
        return agent.to_dict()

    async def update(self, agent_id: str, updates: Dict[str, Any]) -> Optional[Dict]:
        # BR-RLS: a prior commit in this request may have released the connection;
        # re-assert the org GUC so this write cannot be silently rejected by RLS.
        await ensure_org_context(self.session)
        result = await self.session.execute(
            select(Agent).where(Agent.id == agent_id)
        )
        agent = result.scalar_one_or_none()
        if not agent:
            return None

        # Tenancy hardening (audit-2 F1): org assignment + primary key are INTERNAL
        # concerns, never client-settable through an update payload. A shared
        # (NULL-org) agent is mutated via the RLS-EXEMPT owner session (see
        # ``app.api.agent_routes._agent_writer``), which has NO ``WITH CHECK`` to
        # stop an org_id reassignment — so a raw ``org_id`` (or its camelCase alias
        # ``orgId``) in the payload could relocate/claim any of the shared seed
        # agents fleet-wide, and an ``id`` could re-map the primary key. Strip all
        # three here UNCONDITIONALLY (defense in depth beneath the route-level
        # import whitelist). Org assignment happens only at ``create()`` — via the
        # DB default ``current_org_id()`` or the explicit admin shared-agent path.
        updates = {
            k: v for k, v in updates.items()
            if k not in ("org_id", "orgId", "id")
        }

        field_map = {
            "displayName": "display_name", "systemPrompt": "system_prompt",
            "avatarUrl": "avatar_url",
            "agentType": "agent_type", "maxTokens": "max_tokens",
            "accessPolicy": "access_policy", "reportsTo": "reports_to",
            "billingTier": "billing_tier", "rateMultiplier": "rate_multiplier",
            "basePricePerCall": "base_price_per_call",
        }
        for key, value in updates.items():
            attr = field_map.get(key, key)
            if hasattr(agent, attr):
                setattr(agent, attr, value)

        agent.updated_at = datetime.utcnow()
        # BR-1.4 (RLS): NO post-commit refresh. ``agents`` is FORCE-RLS; a by-PK
        # refresh() after commit issues a SELECT the org policy filters, and if the
        # ``app.current_org_id`` GUC is not bound at that instant the just-updated
        # row is invisible → "Could not refresh instance" → 500. The row is already
        # loaded + mutated in this GUC-bound transaction; flush the UPDATE, commit,
        # and return — ``expire_on_commit=False`` keeps the attributes valid.
        await self.session.flush()
        await self.session.commit()
        return agent.to_dict()

    async def delete(self, agent_id: str) -> bool:
        # BR-RLS: a prior commit in this request may have released the connection;
        # re-assert the org GUC so this write cannot be silently rejected by RLS.
        await ensure_org_context(self.session)
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
        # BR-RLS: a prior commit in this request may have released the connection;
        # re-assert the org GUC so this write cannot be silently rejected by RLS.
        await ensure_org_context(self.session)
        conv = Conversation(
            agent_id=data.get("agent_id"),
            user_id=data.get("user_id", "anonymous"),
            title=data.get("title"),
            model=data.get("model"),
        )
        self.session.add(conv)
        # BR-1.4 (RLS): flush emits INSERT ... RETURNING org_id so the
        # server_default current_org_id() is evaluated INSIDE this GUC-bound
        # transaction, then load the agent relationship for the response via
        # self.get() WHILE STILL in that transaction — where the row is visible.
        # We must NOT commit first and reload after: ``conversations`` is FORCE-RLS,
        # and a post-commit by-PK SELECT the org policy filters can miss the
        # just-written row if the GUC is not bound at that instant (refresh →
        # "Could not refresh instance", or a None reload → 500). self.get() returns
        # a plain dict materialised before commit; expire_on_commit=False keeps it.
        await self.session.flush()
        result = await self.get(str(conv.id))
        await self.session.commit()
        return result

    async def update(self, conv_id: str, updates: Dict[str, Any]) -> Optional[Dict]:
        # BR-RLS: a prior commit in this request may have released the connection;
        # re-assert the org GUC so this write cannot be silently rejected by RLS.
        await ensure_org_context(self.session)
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
        # BR-1.4 (RLS): read the updated row back via self.get() BEFORE commit, while
        # the app.current_org_id GUC is bound and the row is visible in this
        # transaction. ``conversations`` is FORCE-RLS, so a post-commit reload could
        # be filtered out if the GUC is not present at that instant. flush the
        # UPDATE first so the SELECT sees it; commit after (dict already materialised).
        await self.session.flush()
        result = await self.get(conv_id)
        await self.session.commit()
        return result

    async def delete(self, conv_id: str) -> bool:
        # BR-RLS: a prior commit in this request may have released the connection;
        # re-assert the org GUC so this write cannot be silently rejected by RLS.
        await ensure_org_context(self.session)
        result = await self.session.execute(
            delete(Conversation).where(Conversation.id == conv_id)
        )
        await self.session.commit()
        return result.rowcount > 0

    async def add_message(self, conv_id: str, data: Dict[str, Any]) -> Dict:
        # BR-RLS: a prior commit in this request may have released the connection;
        # re-assert the org GUC so this write cannot be silently rejected by RLS.
        await ensure_org_context(self.session)
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

        # BR-1.4 (RLS): NO post-commit refresh. ``messages`` is FORCE-RLS; flush
        # emits INSERT ... RETURNING org_id (server_default current_org_id()) inside
        # this GUC-bound transaction, fully populating ``msg`` (and the conversation
        # counter UPDATE). A refresh() after commit would re-SELECT under the org
        # policy and 500 with "Could not refresh instance" if the GUC is unbound.
        await self.session.flush()
        await self.session.commit()
        return msg.to_dict()


# ── API Key Repository ────────────────────────────────────────────

class ApiKeyRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def generate(self, agent_id: str, data: Dict[str, Any], org_id: Optional[str] = None) -> Dict:
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
        # BR-2.4 (H1 fix): bind the new key to the creating user's ACTIVE org so it
        # resolves to that org at auth time. When org_id is None we leave the column
        # unset so the server_default (current_org_id() = the caller's bound org on
        # the request session) applies — never send an explicit NULL that would
        # bypass the default.
        if org_id is not None:
            api_key.org_id = org_id
        self.session.add(api_key)
        await self.session.commit()
        await self.session.refresh(api_key)

        result = api_key.to_dict()
        result["key"] = raw_key  # Only returned on creation
        return result

    async def list_for_agent(self, agent_id: str) -> List[Dict]:
        # S9: org-scope key metadata even on a SHARED (NULL-org) agent. api_keys
        # carries NO RLS (the key lookup in validate_api_key must run before any
        # org is bound), so key rows are not policy-isolated on their own — for a
        # global agent, ANY org's caller would otherwise list ANOTHER org's key
        # metadata. Filter by ``org_id = current_org_id()`` (the caller's bound org
        # GUC, set by _bind_org_context) so keys stay org-scoped regardless of the
        # agent's own org.
        result = await self.session.execute(
            select(ApiKey)
            .where(
                ApiKey.agent_id == agent_id,
                ApiKey.is_active == True,
                ApiKey.org_id == func.current_org_id(),
            )
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
        # S9: org-scope revoke too (see list_for_agent). Without the org predicate,
        # an admin of org B could revoke org A's key on a shared (NULL-org) agent.
        result = await self.session.execute(
            select(ApiKey).where(
                ApiKey.id == key_id,
                ApiKey.agent_id == agent_id,
                ApiKey.org_id == func.current_org_id(),
            )
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
        # BR-RLS: a prior commit in this request may have released the connection;
        # re-assert the org GUC so this write cannot be silently rejected by RLS.
        await ensure_org_context(self.session)
        if session_id:
            result = await self.session.execute(
                select(BuilderSession).where(BuilderSession.id == session_id)
            )
            bs = result.scalar_one_or_none()
            if bs:
                return bs.to_dict()

        bs = BuilderSession(user_id=user_id)
        self.session.add(bs)
        # BR-1.4 (RLS): flush → INSERT ... RETURNING org_id (server_default
        # current_org_id()) inside the GUC-bound transaction; NO post-commit
        # refresh. ``builder_sessions`` is FORCE-RLS, so a by-PK refresh() after
        # commit could be filtered → "Could not refresh instance" → 500.
        await self.session.flush()
        await self.session.commit()
        return bs.to_dict()

    async def add_messages(self, session_id: str, user_msg: str, assistant_msg: str) -> Dict:
        # BR-RLS: a prior commit in this request may have released the connection;
        # re-assert the org GUC so this write cannot be silently rejected by RLS.
        await ensure_org_context(self.session)
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
        # BR-1.4 (RLS): row already loaded + mutated in this GUC-bound transaction;
        # flush the UPDATE and commit, NO post-commit refresh (FORCE-RLS re-SELECT
        # could 500 if the org GUC is unbound). expire_on_commit=False keeps attrs.
        await self.session.flush()
        await self.session.commit()
        return bs.to_dict()

    async def get(self, session_id: str) -> Optional[Dict]:
        result = await self.session.execute(
            select(BuilderSession).where(BuilderSession.id == session_id)
        )
        bs = result.scalar_one_or_none()
        return bs.to_dict() if bs else None

    async def set_agent_config(self, session_id: str, config: Dict) -> Optional[Dict]:
        # BR-RLS: a prior commit in this request may have released the connection;
        # re-assert the org GUC so this write cannot be silently rejected by RLS.
        await ensure_org_context(self.session)
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


# ── User Repository ───────────────────────────────────────────────

class UserRepository:
    """Repository for User CRUD operations"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, user_id: str) -> Optional[Dict]:
        """Get user by ID"""
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        return user.to_dict() if user else None

    async def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email (returns ORM object for password verification)"""
        result = await self.session.execute(
            select(User).where(User.email == email.lower())
        )
        return result.scalar_one_or_none()

    async def email_exists(self, email: str) -> bool:
        """Check if email is already registered"""
        result = await self.session.execute(
            select(func.count(User.id)).where(User.email == email.lower())
        )
        return (result.scalar() or 0) > 0

    async def create(self, data: Dict[str, Any]) -> Dict:
        """Create a new user"""
        user = User(
            email=data["email"].lower(),
            password_hash=data["password_hash"],
            name=data["name"],
            role=data.get("role", "operator"),
            is_active=data.get("is_active", True),
        )
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user.to_dict()

    async def update(self, user_id: str, updates: Dict[str, Any]) -> Optional[Dict]:
        """Update user profile"""
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            return None

        # Only allow updating safe fields
        allowed_fields = {"name", "email", "password_hash"}
        for key, value in updates.items():
            if key in allowed_fields and hasattr(user, key):
                if key == "email":
                    value = value.lower()
                setattr(user, key, value)

        user.updated_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(user)
        return user.to_dict()

    async def deactivate(self, user_id: str) -> bool:
        """Deactivate user account"""
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            return False
        user.is_active = False
        user.updated_at = datetime.utcnow()
        await self.session.commit()
        return True

    async def count(self) -> int:
        """Count total users"""
        result = await self.session.execute(select(func.count(User.id)))
        return result.scalar() or 0


# ── User API Key Repository ───────────────────────────────────────

class UserApiKeyRepository:
    """Repository for user API key operations"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def generate(self, user_id: str, data: Dict[str, Any]) -> Dict:
        """Generate a new API key for a user"""
        raw_key = f"ubk-{secrets.token_urlsafe(32)}"
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        key_prefix = raw_key[:8]

        expires_at = None
        if data.get("expiresInDays"):
            expires_at = datetime.utcnow() + timedelta(days=data["expiresInDays"])

        api_key = UserApiKey(
            user_id=user_id,
            name=data["name"],
            key_prefix=key_prefix,
            key_hash=key_hash,
            permissions=data.get("permissions", ["chat", "read"]),
            rate_limit=data.get("rateLimit", 100),
            expires_at=expires_at,
            created_via=data.get("createdVia"),
        )
        self.session.add(api_key)
        await self.session.commit()
        await self.session.refresh(api_key)

        result = api_key.to_dict()
        result["key"] = raw_key  # Only returned on creation
        return result

    async def list_for_user(self, user_id: str) -> List[Dict]:
        """List all API keys for a user"""
        result = await self.session.execute(
            select(UserApiKey)
            .where(UserApiKey.user_id == user_id, UserApiKey.is_active == True)
            .order_by(UserApiKey.created_at.desc())
        )
        return [k.to_dict() for k in result.scalars().all()]

    async def get(self, key_id: str) -> Optional[Dict]:
        """Get API key by ID"""
        result = await self.session.execute(
            select(UserApiKey).where(UserApiKey.id == key_id)
        )
        key = result.scalar_one_or_none()
        return key.to_dict() if key else None

    async def revoke(self, user_id: str, key_id: str) -> bool:
        """Revoke an API key"""
        result = await self.session.execute(
            select(UserApiKey).where(UserApiKey.id == key_id, UserApiKey.user_id == user_id)
        )
        key = result.scalar_one_or_none()
        if not key:
            return False
        key.is_active = False
        await self.session.commit()
        return True

    async def validate_key(self, api_key: str) -> Optional[UserApiKey]:
        """Validate an API key and return the key object if valid"""
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        result = await self.session.execute(
            select(UserApiKey).where(
                UserApiKey.key_hash == key_hash,
                UserApiKey.is_active == True,
            )
        )
        db_key = result.scalar_one_or_none()

        if not db_key:
            return None

        # Check expiration
        if db_key.expires_at and db_key.expires_at < datetime.utcnow():
            return None

        # Update usage stats
        db_key.last_used_at = datetime.utcnow()
        db_key.usage_count = (db_key.usage_count or 0) + 1
        await self.session.commit()

        return db_key


# ── Tool Execution Repository ─────────────────────────────────────

class ToolExecutionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, data: Dict[str, Any]) -> Dict:
        # BR-RLS: a prior commit in this request may have released the connection;
        # re-assert the org GUC so this write cannot be silently rejected by RLS.
        await ensure_org_context(self.session)
        te = ToolExecution(
            conversation_id=data.get("conversation_id"),
            message_id=data.get("message_id"),
            agent_id=data.get("agent_id"),
            tool_name=data["tool_name"],
            input=data.get("input"),
            status="pending",
        )
        self.session.add(te)
        # BR-1.4 (RLS): flush → INSERT ... RETURNING org_id inside the GUC-bound
        # transaction; NO post-commit refresh. ``tool_executions`` is FORCE-RLS, so
        # a by-PK refresh() after commit could be filtered → 500 if the GUC is unbound.
        await self.session.flush()
        await self.session.commit()
        return te.to_dict()

    async def complete(self, exec_id: str, output: Any, duration_ms: int, status: str = "completed") -> Optional[Dict]:
        # BR-RLS: a prior commit in this request may have released the connection;
        # re-assert the org GUC so this write cannot be silently rejected by RLS.
        await ensure_org_context(self.session)
        result = await self.session.execute(
            select(ToolExecution).where(ToolExecution.id == exec_id)
        )
        te = result.scalar_one_or_none()
        if not te:
            return None
        te.output = output
        te.duration_ms = duration_ms
        te.status = status
        # BR-1.4 (RLS): row loaded + mutated in this GUC-bound transaction; flush +
        # commit, NO post-commit refresh (FORCE-RLS re-SELECT could 500 unbound).
        await self.session.flush()
        await self.session.commit()
        return te.to_dict()

    async def list_for_conversation(self, conv_id: str) -> List[Dict]:
        result = await self.session.execute(
            select(ToolExecution)
            .where(ToolExecution.conversation_id == conv_id)
            .order_by(ToolExecution.created_at)
        )
        return [te.to_dict() for te in result.scalars().all()]


# ── Code Attribution Repository (Agent Trace) ─────────────────────

class CodeAttributionRepository:
    """Repository for code attribution tracking"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, data: Dict[str, Any]) -> Dict:
        """Record a code attribution"""
        # BR-RLS: a prior commit in this request may have released the connection;
        # re-assert the org GUC so this write cannot be silently rejected by RLS.
        await ensure_org_context(self.session)
        import hashlib

        # Generate code hash (first 32 chars of SHA-256)
        code_hash = hashlib.sha256(data["generated_code"].encode()).hexdigest()[:32]

        attribution = CodeAttribution(
            session_id=data["session_id"],
            agent_id=data.get("agent_id"),
            agent_name=data["agent_name"],
            model=data["model"],
            file_path=data["file_path"],
            start_line=data["start_line"],
            end_line=data["end_line"],
            change_type=data.get("change_type", "generation"),
            code_hash=code_hash,
            prompt=data.get("prompt"),
            generated_code=data["generated_code"],
            metadata_=data.get("metadata", {}),
        )
        self.session.add(attribution)
        # BR-1.4 (RLS): flush → INSERT ... RETURNING org_id inside the GUC-bound
        # transaction; NO post-commit refresh. ``code_attributions`` is FORCE-RLS.
        await self.session.flush()
        await self.session.commit()
        return attribution.to_dict()

    async def get_by_file(
        self,
        file_path: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict]:
        """Get all attributions for a specific file"""
        # Normalize file path to handle both /path and path formats
        normalized_path = file_path if file_path.startswith("/") else f"/{file_path}"
        result = await self.session.execute(
            select(CodeAttribution)
            .where(CodeAttribution.file_path == normalized_path)
            .order_by(CodeAttribution.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return [a.to_dict() for a in result.scalars().all()]

    async def get_by_agent(
        self,
        agent_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict]:
        """Get all code attributions by a specific agent"""
        result = await self.session.execute(
            select(CodeAttribution)
            .where(CodeAttribution.agent_id == agent_id)
            .order_by(CodeAttribution.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return [a.to_dict() for a in result.scalars().all()]

    async def get_by_session(
        self,
        session_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict]:
        """Get all code attributions in a session"""
        result = await self.session.execute(
            select(CodeAttribution)
            .where(CodeAttribution.session_id == session_id)
            .order_by(CodeAttribution.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return [a.to_dict() for a in result.scalars().all()]

    async def get_recent(
        self,
        days: int = 1,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict]:
        """Get recent attributions within the last N days"""
        cutoff = datetime.utcnow() - timedelta(days=days)
        result = await self.session.execute(
            select(CodeAttribution)
            .where(CodeAttribution.created_at >= cutoff)
            .order_by(CodeAttribution.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return [a.to_dict() for a in result.scalars().all()]

    async def get_stats(self) -> Dict[str, Any]:
        """Get attribution statistics"""
        # Total lines of code
        total_lines_result = await self.session.execute(
            select(func.sum(CodeAttribution.end_line - CodeAttribution.start_line + 1))
        )
        total_lines = total_lines_result.scalar() or 0

        # Total attributions
        total_attributions_result = await self.session.execute(
            select(func.count(CodeAttribution.id))
        )
        total_attributions = total_attributions_result.scalar() or 0

        # Unique agents
        unique_agents_result = await self.session.execute(
            select(func.count(func.distinct(CodeAttribution.agent_id)))
        )
        unique_agents = unique_agents_result.scalar() or 0

        # Unique files
        unique_files_result = await self.session.execute(
            select(func.count(func.distinct(CodeAttribution.file_path)))
        )
        unique_files = unique_files_result.scalar() or 0

        # By change type (operation)
        operations_result = await self.session.execute(
            select(
                CodeAttribution.change_type,
                func.count(CodeAttribution.id).label("count")
            )
            .group_by(CodeAttribution.change_type)
        )
        operations = {row.change_type: row.count for row in operations_result.all()}

        # Top agents by lines of code
        top_agents_result = await self.session.execute(
            select(
                CodeAttribution.agent_name,
                func.sum(CodeAttribution.end_line - CodeAttribution.start_line + 1).label("total_lines"),
                func.count(CodeAttribution.id).label("attribution_count")
            )
            .group_by(CodeAttribution.agent_name)
            .order_by(func.sum(CodeAttribution.end_line - CodeAttribution.start_line + 1).desc())
            .limit(10)
        )
        top_agents = [
            {
                "agentName": row.agent_name,
                "totalLines": int(row.total_lines or 0),
                "attributionCount": row.attribution_count
            }
            for row in top_agents_result.all()
        ]

        # Top files by attribution count
        top_files_result = await self.session.execute(
            select(
                CodeAttribution.file_path,
                func.count(CodeAttribution.id).label("attribution_count"),
                func.sum(CodeAttribution.end_line - CodeAttribution.start_line + 1).label("total_lines")
            )
            .group_by(CodeAttribution.file_path)
            .order_by(func.count(CodeAttribution.id).desc())
            .limit(10)
        )
        top_files = [
            {
                "filePath": row.file_path,
                "attributionCount": row.attribution_count,
                "totalLines": int(row.total_lines or 0)
            }
            for row in top_files_result.all()
        ]

        return {
            "totalLines": int(total_lines),
            "totalAttributions": total_attributions,
            "uniqueAgents": unique_agents,
            "uniqueFiles": unique_files,
            "byOperation": operations,
            "topAgents": top_agents,
            "topFiles": top_files,
        }

    async def search(
        self,
        agent_id: Optional[str] = None,
        file_path: Optional[str] = None,
        operation: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict]:
        """Search attributions with filters"""
        query = select(CodeAttribution)

        if agent_id:
            query = query.where(CodeAttribution.agent_id == agent_id)
        if file_path:
            query = query.where(CodeAttribution.file_path.like(f"%{file_path}%"))
        if operation:
            query = query.where(CodeAttribution.change_type == operation)
        if start_date:
            query = query.where(CodeAttribution.created_at >= start_date)
        if end_date:
            query = query.where(CodeAttribution.created_at <= end_date)

        query = query.order_by(CodeAttribution.created_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(query)
        return [a.to_dict() for a in result.scalars().all()]


# ── Speaker Profile Repository ────────────────────────────────────

class SpeakerProfileRepository:
    """Repository for speaker voice profiles (speaker identification)."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_all(self) -> List[Dict]:
        result = await self.session.execute(
            select(SpeakerProfile).order_by(SpeakerProfile.name)
        )
        return [p.to_dict() for p in result.scalars().all()]

    async def get(self, profile_id: str) -> Optional[Dict]:
        result = await self.session.execute(
            select(SpeakerProfile).where(SpeakerProfile.id == profile_id)
        )
        profile = result.scalar_one_or_none()
        return profile.to_dict() if profile else None

    async def get_by_name(self, name: str) -> Optional[Dict]:
        result = await self.session.execute(
            select(SpeakerProfile).where(SpeakerProfile.name == name)
        )
        profile = result.scalar_one_or_none()
        return profile.to_dict() if profile else None

    async def create(self, data: Dict[str, Any]) -> Dict:
        # BR-RLS: a prior commit in this request may have released the connection;
        # re-assert the org GUC so this write cannot be silently rejected by RLS.
        await ensure_org_context(self.session)
        profile = SpeakerProfile(
            name=data["name"],
            user_id=data.get("user_id"),
            embedding=data["embedding"],
            enrollment_count=data.get("enrollment_count", 1),
            preferences=data.get("preferences", {}),
        )
        self.session.add(profile)
        # BR-1.4 (RLS): flush → INSERT ... RETURNING org_id inside the GUC-bound
        # transaction; NO post-commit refresh. ``speaker_profiles`` is FORCE-RLS.
        await self.session.flush()
        await self.session.commit()
        return profile.to_dict()

    async def update(self, profile_id: str, updates: Dict[str, Any]) -> Optional[Dict]:
        # BR-RLS: a prior commit in this request may have released the connection;
        # re-assert the org GUC so this write cannot be silently rejected by RLS.
        await ensure_org_context(self.session)
        result = await self.session.execute(
            select(SpeakerProfile).where(SpeakerProfile.id == profile_id)
        )
        profile = result.scalar_one_or_none()
        if not profile:
            return None

        for key, value in updates.items():
            if hasattr(profile, key):
                setattr(profile, key, value)

        profile.updated_at = datetime.utcnow()
        # BR-1.4 (RLS): row loaded + mutated in this GUC-bound transaction; flush +
        # commit, NO post-commit refresh (FORCE-RLS re-SELECT could 500 unbound).
        await self.session.flush()
        await self.session.commit()
        return profile.to_dict()

    async def delete(self, profile_id: str) -> bool:
        # BR-RLS: a prior commit in this request may have released the connection;
        # re-assert the org GUC so this write cannot be silently rejected by RLS.
        await ensure_org_context(self.session)
        result = await self.session.execute(
            select(SpeakerProfile).where(SpeakerProfile.id == profile_id)
        )
        profile = result.scalar_one_or_none()
        if not profile:
            return False
        await self.session.delete(profile)
        await self.session.commit()
        return True
