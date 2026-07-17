"""
Authentication Middleware

Provides FastAPI dependencies for route protection:
- API key authentication (X-API-Key header)
- Keycloak OIDC bearer JWT authentication (Authorization: Bearer ...)
- Role-based authorization
- Optional auth for mixed endpoints

Both auth sources return a unified ``AuthUser`` object.
"""

import os
import hashlib
import hmac
import logging
from typing import Optional, Annotated
from dataclasses import dataclass
from datetime import datetime

from fastapi import Depends, HTTPException, Query, Request, status
from fastapi.security import APIKeyHeader, HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from app.db.database import get_session
from app.db.models import ApiKey, UserApiKey, User, Organization, OrgMembership
from app.auth.roles import (
    UserRole,
    is_admin_path,
    is_public_path,
    get_minimum_role_for_method,
    map_keycloak_roles,
)
from app.auth.keycloak import (
    KeycloakValidationError,
    keycloak_enabled,
    validate_token as kc_validate_token,
)

logger = logging.getLogger(__name__)

# Header name for API key
AUTH_HEADER = "X-API-Key"

# API key header security scheme
api_key_header = APIKeyHeader(name=AUTH_HEADER, auto_error=False)

# Bearer token security scheme for Keycloak JWTs
bearer_scheme = HTTPBearer(auto_error=False, bearerFormat="JWT")

# Environment variable for master admin key (for development/bootstrap)
MASTER_ADMIN_KEY = os.getenv("BRIGADE_ADMIN_KEY", "")

# Allow auth bypass in development mode (DANGEROUS - never in production)
AUTH_BYPASS_FLAG = os.getenv("AUTH_BYPASS", "false").lower() == "true"
AUTH_BYPASS_ENABLED = AUTH_BYPASS_FLAG and os.getenv("ENVIRONMENT", "production").lower() == "development"

# Session cookie name set by the OIDC callback route.
OIDC_SESSION_COOKIE = "brigade_session"

EARLY_ACCESS_PATH_PREFIXES = (
    "/api/v1/agents",
    "/api/v1/chat",
    "/api/v1/conversations",
    "/api/v1/orchestration",
    "/api/v1/openai",
)


@dataclass
class AuthUser:
    """Authenticated user context"""
    id: str
    role: UserRole
    agent_id: Optional[str] = None  # If authenticated via agent API key
    key_id: Optional[str] = None
    key_name: Optional[str] = None
    permissions: list = None
    user_id: Optional[str] = None  # User ID if authenticated via user API key
    email: Optional[str] = None  # User email if authenticated via user API key
    org_id: Optional[str] = None
    auth_source: str = "api_key"  # api_key | keycloak | session | bypass | public
    # Legacy pre-BR-1.1 identity key: the Keycloak ``sub``. BR-1.1 made
    # ``user_id`` the canonical local users.id, but per-user AGENT MEMORY groups
    # in Graphiti were keyed by whatever id the request carried — for SSO users
    # pre-cutover that was the raw sub. Carrying it here lets the chat path
    # DUAL-READ the legacy ``{sub}__{agent}`` memory namespace (see
    # app/memory/graphiti_manager._read_group_ids) so old memory stays reachable.
    # None for master-admin / agent keys with no bound sub; when it equals
    # ``user_id`` the alias is a no-op (no legacy namespace to read).
    keycloak_id: Optional[str] = None

    def __post_init__(self):
        if self.permissions is None:
            self.permissions = []

    def has_permission(self, permission: str) -> bool:
        """Check if user has a specific permission"""
        if self.role == UserRole.ADMIN:
            return True
        return permission in self.permissions

    def can_access_agent(self, agent_id: str) -> bool:
        """Check if user can access a specific agent"""
        if self.role == UserRole.ADMIN:
            return True
        # Service keys bound to specific agents
        if self.agent_id:
            return self.agent_id == agent_id
        # Operators can access all agents
        return self.role in (UserRole.OPERATOR, UserRole.VIEWER)


async def validate_api_key(
    api_key: str,
    session: AsyncSession,
) -> Optional[AuthUser]:
    """Validate an API key and return the authenticated user"""
    if not api_key:
        return None

    # Check master admin key first (for bootstrap/development).
    # Constant-time compare (bytes) to avoid a timing side-channel that could
    # leak the master key, and to sidestep str-compare_digest's ASCII rule.
    if MASTER_ADMIN_KEY and hmac.compare_digest(api_key.encode(), MASTER_ADMIN_KEY.encode()):
        logger.debug("Authenticated via master admin key")
        return AuthUser(
            id="admin",
            role=UserRole.ADMIN,
            key_name="Master Admin Key",
            auth_source="api_key",
        )

    # Hash the key for database lookup
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()

    # Look up in database - first try user API keys
    try:
        # Check user API keys first
        result = await session.execute(
            select(UserApiKey).where(
                UserApiKey.key_hash == key_hash,
                UserApiKey.is_active == True,  # noqa: E712
            )
        )
        user_key = result.scalar_one_or_none()

        if user_key:
            # Check expiration
            if user_key.expires_at and user_key.expires_at < datetime.utcnow():
                logger.warning(f"Expired user API key used: {user_key.id}")
                return None

            # Get the user to check if active and get their role
            user_result = await session.execute(
                select(User).where(User.id == user_key.user_id)
            )
            user = user_result.scalar_one_or_none()

            if not user or not user.is_active:
                logger.warning(f"User API key for inactive/missing user: {user_key.id}")
                return None

            # Update usage stats
            user_key.last_used_at = datetime.utcnow()
            user_key.usage_count = (user_key.usage_count or 0) + 1
            await session.commit()

            # Determine role from user's role
            permissions = user_key.permissions or []
            if user.role == "admin" or "admin" in permissions:
                role = UserRole.ADMIN
            elif user.role == "operator" or "write" in permissions or "chat" in permissions:
                role = UserRole.OPERATOR
            else:
                role = UserRole.VIEWER

            return AuthUser(
                id=str(user.id),
                role=role,
                key_id=str(user_key.id),
                key_name=user_key.name,
                permissions=permissions,
                user_id=str(user.id),
                email=user.email,
                auth_source="api_key",
                # Their bound Keycloak sub (or None). Lets an API-key session
                # dual-read memory this human accreted while signing in via SSO
                # pre-BR-1.1. None when they never logged in via Keycloak.
                keycloak_id=user.keycloak_id,
            )

        # Fall back to agent API keys
        result = await session.execute(
            select(ApiKey).where(
                ApiKey.key_hash == key_hash,
                ApiKey.is_active == True,  # noqa: E712
            )
        )
        db_key = result.scalar_one_or_none()

        if not db_key:
            logger.warning(f"Invalid API key attempted: {api_key[:8]}...")
            return None

        # Check expiration
        if db_key.expires_at and db_key.expires_at < datetime.utcnow():
            logger.warning(f"Expired API key used: {db_key.id}")
            return None

        # Update usage stats
        db_key.last_used_at = datetime.utcnow()
        db_key.usage_count = (db_key.usage_count or 0) + 1
        await session.commit()

        # Determine role from key permissions
        permissions = db_key.permissions or []
        if "admin" in permissions:
            role = UserRole.ADMIN
        elif "write" in permissions or "chat" in permissions:
            role = UserRole.OPERATOR
        else:
            role = UserRole.VIEWER

        return AuthUser(
            id=str(db_key.id),
            role=role,
            agent_id=db_key.agent_id,
            key_id=str(db_key.id),
            key_name=db_key.name,
            permissions=permissions,
            auth_source="api_key",
        )

    except Exception as e:
        logger.error(f"Error validating API key: {e}")
        return None




# ── Keycloak role -> apps derivation ───────────────────────────
# Realm or client roles matching pattern "app:<slug>" become
# user.apps = [<slug>, ...]. Lets a single Keycloak admin change
# ("grant Bob access to LibreChat") propagate to Brigade automatically.
def _derive_apps_from_roles(roles):
    apps = set()
    for r in roles or []:
        s = (r or "").strip().lower()
        if s.startswith("app:") and len(s) > 4:
            apps.add(s[4:])
    return sorted(apps)


# Tables whose free-form ``user_id`` column the pre-BR-1.1 Keycloak-bearer path
# wrote the raw Keycloak ``sub`` into (it set AuthUser.id = sub). These RELATIONAL
# rows are relabeled in place by the batch + lazy remap. Every OTHER *relational*
# user-scoped column is either a UUID FK onto users.id (already canonical) or an
# opaque downstream pass-through (ScheduledRun.owner_user_id) that must NOT be
# rewritten.
#
# CORRECTION (adversarial-review finding): one NON-relational store was ALSO
# sub-keyed and is NOT covered here — per-user Graphiti/FalkorDB AGENT MEMORY,
# whose group_id is ``{user_id}__{agent}`` (see app/memory/graphiti_manager).
# Moving those graph nodes would be out-of-band FalkorDB surgery, so instead the
# memory RETRIEVAL path dual-reads the legacy ``{sub}__{agent}`` namespace via
# AuthUser.keycloak_id while writes stay canonical — no data movement, and this
# SQL remap deliberately leaves memory alone.
# Keep this in sync with app/db/migrations.remap_forked_keycloak_rows.
_KEYCLOAK_REMAP_TABLES = ("conversations", "builder_sessions")


async def _remap_user_rows(session, from_id: str, to_id: str) -> None:
    """Relabel rows owned by ``from_id`` (a raw Keycloak sub) to the canonical
    local ``to_id``. Targeted + idempotent: after the first pass no row still
    carries the sub, so subsequent logins match zero rows. 'anonymous'/NULL and
    downstream pass-through ids never equal a sub, so they are untouched."""
    from sqlalchemy import text as _text
    for table in _KEYCLOAK_REMAP_TABLES:
        await session.execute(
            _text(f"UPDATE {table} SET user_id = :to_id WHERE user_id = :from_id"),
            {"to_id": to_id, "from_id": from_id},
        )


async def resolve_canonical_user_id(session, kc_sub, email, derived_apps, realm_role):
    """Resolve the canonical LOCAL ``users.id`` for a Keycloak principal.

    This is the core of BR-1.1: every auth method must converge on one id per
    human. Resolution order:
      1. Match by ``keycloak_id`` (the durable binding once learned).
      2. Fall back to ``email`` — and *claim* that row for this sub by stamping
         ``keycloak_id`` when it is still unset (the legacy email-keyed rows that
         auto-provisioned before BR-1.1). If the row is already bound to a
         DIFFERENT sub, keep the existing binding (two Keycloak identities
         colliding on one email) — log and reuse the row.
      3. Auto-provision a fresh row (needs an email — ``users.email`` is NOT
         NULL UNIQUE).

    Also merges apps additively + syncs role (unchanged behavior), and lazily
    remaps any rows written under the raw sub to the local id (see
    _remap_user_rows). Returns the local ``users.id`` as a str, or None when it
    cannot resolve (no keycloak_id match AND no email) — the caller then keeps
    the sub, a degraded but honest fallback.
    """
    from app.db.models import User as _User
    from sqlalchemy import select as _select
    from datetime import datetime as _dt

    new_role = realm_role.value if hasattr(realm_role, "value") else str(realm_role)
    email_norm = email.lower() if email else None

    user = None
    if kc_sub:
        r = await session.execute(_select(_User).where(_User.keycloak_id == kc_sub))
        user = r.scalar_one_or_none()

    claimed = False
    if user is None and email_norm:
        r = await session.execute(_select(_User).where(_User.email == email_norm))
        user = r.scalar_one_or_none()
        if user is not None and kc_sub:
            if not user.keycloak_id:
                # Claim the legacy email-keyed row for this sub — the BR-1.1 unify.
                user.keycloak_id = kc_sub
                claimed = True
                logger.info("BR-1.1 bound users.id=%s email=%s to keycloak sub=%s",
                            user.id, email_norm, kc_sub)
            elif user.keycloak_id != kc_sub:
                logger.warning(
                    "Keycloak sub %s presents email %s already bound to sub %s; "
                    "reusing existing row (not overwriting)",
                    kc_sub, email_norm, user.keycloak_id,
                )

    if user is None:
        if not email_norm:
            # No keycloak_id match and no email → cannot mint a row.
            return None
        user = _User(
            email=email_norm,
            name=email_norm.split("@")[0],
            password_hash="NOLOGIN-SSO-ONLY",
            role=new_role,
            apps=list(derived_apps or []),
            is_active=True,
            keycloak_id=kc_sub or None,
        )
        session.add(user)
        await session.flush()  # populate user.id
        logger.info("SSO auto-provisioned Brigade user %s id=%s kc_sub=%s apps=%s",
                    email_norm, user.id, kc_sub, derived_apps)

    # Merge apps additively + sync role on every login.
    existing = set(user.apps or [])
    merged = sorted(existing.union(derived_apps or []))
    changed = False
    if list(merged) != list(user.apps or []):
        user.apps = merged
        changed = True
    if new_role and user.role != new_role:
        user.role = new_role
        changed = True
    if claimed or changed:
        user.updated_at = _dt.utcnow()

    local_id = str(user.id)

    # Lazy identity remap: relabel any pre-BR-1.1 rows keyed on the raw sub to
    # the canonical local id. Only when the sub actually differs from the id.
    if kc_sub and kc_sub != local_id:
        await _remap_user_rows(session, kc_sub, local_id)

    await session.commit()
    return local_id


async def _resolve_and_sync_keycloak_user(email, kc_sub, derived_apps, realm_role):
    """Open a session and resolve the canonical local ``users.id`` for a
    Keycloak principal. Best-effort — never breaks auth: on any failure returns
    None and the caller falls back to the sub.

    Uses the ADMIN (owner) session, not the RLS-subject app-role session. Identity
    resolution is trusted, pre-org, cross-tenant work: it creates/claims the global
    ``users`` row (no org yet) and — via resolve_canonical_user_id → _remap_user_rows
    — relabels a human's pre-cutover ``conversations``/``builder_sessions`` to their
    canonical id. Those two tables are RLS-protected under BR-1.2, and no
    ``app.current_org_id`` is bound this early, so on the app-role connection that
    UPDATE would silently match zero rows and the BR-1.1 remap would quietly stop
    working. The admin connection is RLS-exempt, so the remap still fires; it only
    rewrites ownership (user_id), never org_id, so isolation is unaffected."""
    try:
        from app.db.database import admin_session
        async with admin_session() as s:
            return await resolve_canonical_user_id(
                s, kc_sub, email, derived_apps, realm_role
            )
    except Exception as exc:  # noqa: BLE001 — never break auth on a sync failure
        logger.warning(f"Keycloak->User resolve/sync failed for {email}: {exc}")
        return None


async def validate_bearer_token(token: str) -> Optional[AuthUser]:
    """
    Validate a Keycloak-issued JWT Bearer token.

    Returns a unified ``AuthUser`` on success, or ``None`` when the token is
    invalid. Does not raise - callers decide whether to 401.
    """
    if not token:
        return None
    if not keycloak_enabled():
        logger.debug("Bearer token presented but BRIGADE_USE_KEYCLOAK is disabled")
        return None
    try:
        kc_user = await kc_validate_token(token)
    except KeycloakValidationError as exc:
        logger.warning(f"Keycloak token rejected: {exc}")
        return None
    except Exception as exc:  # noqa: BLE001 - defensive
        logger.error(f"Unexpected error validating Keycloak token: {exc}")
        return None

    # Combine realm + client roles, realm takes priority in mapping order.
    all_roles = kc_user.realm_roles + kc_user.client_roles
    role = map_keycloak_roles(all_roles)

    # Resolve the CANONICAL local users.id for this Keycloak principal, creating
    # /claiming the row and syncing apps + role. This is the BR-1.1 unify: the
    # id returned here is the same local id the API-key path yields for the same
    # human, so their data stops forking by auth method. Best-effort — on a DB
    # failure we fall back to the raw sub (degraded, matches pre-BR-1.1).
    derived_apps = _derive_apps_from_roles(all_roles)
    canonical_id = await _resolve_and_sync_keycloak_user(
        kc_user.email, kc_user.sub, derived_apps, role
    )
    if canonical_id is None:
        canonical_id = kc_user.sub

    return AuthUser(
        id=canonical_id,
        role=role,
        user_id=canonical_id,
        email=kc_user.email,
        key_name=kc_user.preferred_username or kc_user.email,
        permissions=all_roles,
        auth_source="keycloak",
        # The raw sub — the pre-BR-1.1 memory key. When resolution succeeded this
        # differs from ``canonical_id`` (the local users.id) and enables the
        # legacy-memory dual-read; in the degraded fallback where canonical_id IS
        # the sub, keycloak_id == user_id and the alias self-disables.
        keycloak_id=kc_user.sub,
    )


def _extract_bearer_token(request: Request, creds: Optional[HTTPAuthorizationCredentials]) -> Optional[str]:
    """Extract a Bearer token from either the security scheme or a raw header.

    FastAPI's HTTPBearer only parses standard "Bearer" prefix, which is what
    Keycloak issues. We also fall back to the raw header for robustness.
    """
    if creds and creds.scheme and creds.scheme.lower() == "bearer" and creds.credentials:
        return creds.credentials
    auth = request.headers.get("Authorization") or request.headers.get("authorization")
    if auth and auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()
    return None


def _allowed_early_access_emails() -> set[str]:
    raw = os.getenv("BRIGADE_ALLOWED_EMAILS", "")
    return {email.strip().lower() for email in raw.split(",") if email.strip()}


def _requires_early_access(path: str) -> bool:
    return any(path.startswith(prefix) for prefix in EARLY_ACCESS_PATH_PREFIXES)


def _enforce_early_access(user: AuthUser, path: str) -> None:
    allowed = _allowed_early_access_emails()
    if not allowed or not _requires_early_access(path):
        return

    # Keep service/admin keys usable for bootstrap and federation operations.
    if user.id == "admin" or user.role == UserRole.ADMIN and not user.email:
        return

    email = (user.email or "").lower()
    if email in allowed:
        return

    logger.warning(
        "Early access denied: user %s email=%s source=%s path=%s",
        user.id,
        email or "<none>",
        user.auth_source,
        path,
    )
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Brigade early access is not enabled for this account",
    )


async def _resolve_user(
    request: Request,
    api_key: Optional[str],
    creds: Optional[HTTPAuthorizationCredentials],
    session: AsyncSession,
) -> Optional[AuthUser]:
    """Try Bearer JWT first, then X-API-Key, then session cookie."""
    token = _extract_bearer_token(request, creds)
    if token:
        user = await validate_bearer_token(token)
        if user is not None:
            return user
        # Keycloak rejected it. If the token doesn't look like a JWT (JWTs have
        # exactly two dots separating three base64 segments), treat it as an
        # API key so OpenAI-compatible clients can send `Authorization: Bearer
        # ubk-...` against Brigade's openai-compat endpoints.
        if token.count(".") < 2:
            user = await validate_api_key(token, session)
            if user is not None:
                return user

    if api_key:
        user = await validate_api_key(api_key, session)
        if user is not None:
            return user

    # Session cookie fallback (set by OIDC callback). The cookie stores the
    # Keycloak access token directly.
    cookie_token = request.cookies.get(OIDC_SESSION_COOKIE)
    if cookie_token:
        user = await validate_bearer_token(cookie_token)
        if user is not None:
            user.auth_source = "session"
            return user

    return None


async def _default_org_id(session: AsyncSession) -> str:
    result = await session.execute(
        select(Organization).where(Organization.slug == "early-access")
    )
    org = result.scalar_one_or_none()
    if org is None:
        org = Organization(
            name="Early Access",
            slug="early-access",
            plan_tier="free",
            api_calls_limit=0,
            metadata_={"bootstrap": True},
        )
        session.add(org)
        await session.commit()
        await session.refresh(org)
    return str(org.id)


async def _bind_org_context(user: AuthUser, session: AsyncSession) -> None:
    """Resolve the user's active org and bind it into the Postgres RLS GUC
    (``app.current_org_id``) that every org-isolation policy filters on.

    BR-1.1 alignment (the whole point of building on feat/br-1.1): ``user.user_id``
    is the CANONICAL local ``users.id`` — resolved, claimed, and provisioned by
    ``resolve_canonical_user_id`` during auth — NOT a raw Keycloak sub. So we key
    org membership on that canonical id and NEVER auto-provision a user row here.
    The stale substrate looked up by email-first and minted a second
    ``NOLOGIN-SSO-ONLY`` user on a miss, which would re-fork a human's identity by
    auth method — exactly the bug BR-1.1 fixed. Provisioning is BR-1.1's job; this
    function only reads the already-canonical user and maps it to an org.

    Tenant model (Phase 2b): existing users were backfilled into the shared
    ``early-access`` org by migration 20260626_01; a genuinely new user with no
    membership yet gets a personal free org. Callers with no bound human
    (agent/admin/service keys, or a degraded keycloak fallback whose sub matches no
    row) fall back to the early-access org.
    """
    if user.auth_source == "public":
        return

    local_user = None
    # Canonical local users.id first (set for keycloak / session / user-API-key
    # auth; the row already exists thanks to BR-1.1 resolution).
    if user.user_id:
        result = await session.execute(select(User).where(User.id == user.user_id))
        local_user = result.scalar_one_or_none()
    # Fallback: match an existing row by email. We do NOT create one — that would
    # re-fork identity. A miss here just means "no bound human" → early-access.
    if local_user is None and user.email:
        result = await session.execute(select(User).where(User.email == user.email.lower()))
        local_user = result.scalar_one_or_none()

    if local_user is None:
        org_id = await _default_org_id(session)
    else:
        result = await session.execute(
            select(OrgMembership)
            .where(OrgMembership.user_id == local_user.id)
            .order_by(OrgMembership.created_at.asc())
            .limit(1)
        )
        membership = result.scalar_one_or_none()
        if membership is None:
            org = Organization(
                name=f"{local_user.name or local_user.email}'s Brigade",
                slug=f"personal-{local_user.id}",
                plan_tier="free",
                api_calls_limit=0,
                metadata_={"personal": True},
            )
            session.add(org)
            await session.flush()
            membership = OrgMembership(org_id=org.id, user_id=local_user.id, role="owner")
            session.add(membership)
            await session.commit()
            org_id = str(org.id)
        else:
            org_id = str(membership.org_id)

    user.org_id = org_id
    await session.execute(
        text("SELECT set_config('app.current_org_id', :org_id, false)"),
        {"org_id": org_id},
    )


async def get_current_user(
    request: Request,
    api_key: Annotated[Optional[str], Depends(api_key_header)],
    creds: Annotated[Optional[HTTPAuthorizationCredentials], Depends(bearer_scheme)],
    session: AsyncSession = Depends(get_session),
) -> AuthUser:
    """
    Get the current authenticated user. Raises 401 if not authenticated.

    Accepts either ``X-API-Key`` or ``Authorization: Bearer <jwt>`` (Keycloak).
    Use this dependency for protected routes.
    """
    path = request.url.path
    method = request.method

    # Allow public paths without auth
    if is_public_path(path):
        return AuthUser(id="anonymous", role=UserRole.VIEWER, auth_source="public")

    # Development bypass (DANGEROUS)
    if AUTH_BYPASS_ENABLED:
        logger.warning("⚠️ AUTH BYPASS ENABLED - DEVELOPMENT MODE ONLY")
        return AuthUser(id="dev-bypass", role=UserRole.ADMIN, auth_source="bypass")
    if AUTH_BYPASS_FLAG:
        logger.error("❌ AUTH_BYPASS=true but ENVIRONMENT!=development - IGNORING")

    user = await _resolve_user(request, api_key, creds, session)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing credentials (X-API-Key or Bearer token)",
            headers={"WWW-Authenticate": f"Bearer, ApiKey realm=\"{AUTH_HEADER}\""},
        )

    _enforce_early_access(user, path)
    await _bind_org_context(user, session)

    # Check role authorization
    required_role = get_minimum_role_for_method(path, method)
    role_hierarchy = [UserRole.VIEWER, UserRole.OPERATOR, UserRole.ADMIN]

    user_level = role_hierarchy.index(user.role) if user.role in role_hierarchy else -1
    required_level = role_hierarchy.index(required_role) if required_role in role_hierarchy else 0

    if user_level < required_level:
        logger.warning(
            f"Authorization denied: user {user.id} ({user.role}) "
            f"tried to access {method} {path} (requires {required_role})"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Insufficient permissions. Required role: {required_role.value}",
        )

    return user


async def get_current_user_optional(
    request: Request,
    api_key: Annotated[Optional[str], Depends(api_key_header)],
    creds: Annotated[Optional[HTTPAuthorizationCredentials], Depends(bearer_scheme)],
    session: AsyncSession = Depends(get_session),
) -> Optional[AuthUser]:
    """
    Get the current user if authenticated, otherwise return None.

    Use this for endpoints that behave differently based on auth status.
    """
    if AUTH_BYPASS_ENABLED:
        logger.warning("⚠️ AUTH BYPASS ENABLED - DEVELOPMENT MODE ONLY")
        return AuthUser(id="dev-bypass", role=UserRole.ADMIN, auth_source="bypass")
    if AUTH_BYPASS_FLAG:
        logger.error("❌ AUTH_BYPASS=true but ENVIRONMENT!=development - IGNORING")

    user = await _resolve_user(request, api_key, creds, session)
    if user is not None:
        await _bind_org_context(user, session)
    return user


def require_api_key(
    user: Annotated[AuthUser, Depends(get_current_user)]
) -> AuthUser:
    """Dependency that requires a valid API key or Bearer token."""
    return user


def require_admin(
    user: Annotated[AuthUser, Depends(get_current_user)]
) -> AuthUser:
    """Dependency that requires admin role"""
    if user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user


def require_operator(
    user: Annotated[AuthUser, Depends(get_current_user)]
) -> AuthUser:
    """Dependency that requires at least operator role"""
    if user.role not in (UserRole.ADMIN, UserRole.OPERATOR):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operator access required",
        )
    return user


async def require_sse_access(
    request: Request,
    ticket: Annotated[Optional[str], Query()] = None,
    user_via_headers: Annotated[Optional[AuthUser], Depends(get_current_user_optional)] = None,
) -> AuthUser:
    """Auth dependency for browser ``EventSource`` (SSE) endpoints.

    ``EventSource`` cannot send ``Authorization``/``X-API-Key`` headers, so in
    addition to the normal header/cookie auth this accepts a short-lived,
    single-use ``?ticket=<t>`` minted via an authenticated POST (see
    ``app.auth.sse_ticket``). It is purely additive: header/cookie callers are
    resolved exactly as before, and the same minimum-role check the path would
    otherwise enforce is still applied to whichever user we end up with — so the
    ticket can never grant more than its holder already has.
    """
    from app.auth import sse_ticket  # local import keeps sse_ticket dependency-free

    # The ticket may arrive as ?ticket= or, preferably, in the HttpOnly cookie
    # the mint endpoint set (keeps it out of the URL/access logs). Either way it
    # is single-use and consumed here.
    ticket_val = ticket or request.cookies.get(sse_ticket.SSE_TICKET_COOKIE)
    user: Optional[AuthUser] = sse_ticket.consume_ticket(ticket_val) if ticket_val else None
    if user is None:
        user = user_via_headers
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing credentials (X-API-Key, Bearer token, or SSE ticket)",
            headers={"WWW-Authenticate": f"Bearer, ApiKey realm=\"{AUTH_HEADER}\""},
        )

    # Apply the same path/method minimum-role check as get_current_user.
    required_role = get_minimum_role_for_method(request.url.path, request.method)
    role_hierarchy = [UserRole.VIEWER, UserRole.OPERATOR, UserRole.ADMIN]
    user_level = role_hierarchy.index(user.role) if user.role in role_hierarchy else -1
    required_level = role_hierarchy.index(required_role) if required_role in role_hierarchy else 0
    if user_level < required_level:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Insufficient permissions. Required role: {required_role.value}",
        )
    return user
