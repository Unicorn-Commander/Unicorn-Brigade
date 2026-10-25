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
from sqlalchemy.exc import IntegrityError

from app.db.database import get_session, _clear_org_context
from app.db.models import ApiKey, UserApiKey, User, Organization
from app.auth.roles import (
    AUTONOMY_REPORT_PERMISSION,
    UserRole,
    has_autonomy_report_scope,
    is_admin_path,
    is_autonomy_report_request,
    is_public_path,
    is_reporter_only_credential,
    get_minimum_role_for_method,
    map_keycloak_roles,
    role_from_permissions,
    mfa_satisfied,
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
    # BR-2.1 per-org role (owner | admin | member) in the ACTIVE org bound above.
    # Populated by _bind_org_context for a resolved human; None for keyless/service
    # identities on the shared fallback org. This is the per-org authz layer that
    # sits ON TOP OF the global ``role`` (UserRole) — a user can be a global
    # operator yet the owner of their org, or a member of someone else's.
    org_role: Optional[str] = None
    # BR-2.4 per-key org binding (closes finding H1). The org a keyless SERVICE /
    # AGENT API key is bound to (``api_keys.org_id``), set by ``validate_api_key``
    # for an agent key. ``_bind_org_context`` binds the request's RLS org to THIS
    # when the key has no human tenant, so two customers' keys are isolated instead
    # of collapsing onto the shared 'early-access' org. None for the master-admin
    # key, for user API keys (which resolve the human's own home org), and for
    # legacy keys with a NULL org_id (→ early-access fallback).
    key_org_id: Optional[str] = None
    auth_source: str = "api_key"  # api_key | keycloak | session | bypass | public
    # BR-2.6: whether this session authenticated with a genuine SECOND factor,
    # derived from the OIDC token's acr/amr claims (see roles.mfa_satisfied).
    # Feeds the ``require_mfa`` gate in evaluate_agent_access. False for API-key /
    # service identities (no interactive login) and single-factor logins.
    mfa: bool = False
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

            # Determine role from the user's stored role + key scopes (BR-2.6:
            # canonical derivation, formerly inlined here and drifting).
            permissions = user_key.permissions or []
            role = role_from_permissions(permissions, base_role=user.role)

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

        # Determine role from key scopes only — an agent/service key has no
        # backing user row (BR-2.6: canonical derivation, base_role=None).
        permissions = db_key.permissions or []
        role = role_from_permissions(permissions)

        return AuthUser(
            id=str(db_key.id),
            role=role,
            agent_id=db_key.agent_id,
            key_id=str(db_key.id),
            key_name=db_key.name,
            permissions=permissions,
            auth_source="api_key",
            # BR-2.4 (H1 fix): carry the key's OWN org binding so _bind_org_context
            # scopes this service/agent key to its customer's org instead of the
            # shared 'early-access' org. None for legacy keys with a NULL org_id →
            # they still fall back to early-access.
            key_org_id=str(db_key.org_id) if db_key.org_id else None,
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

    # BR-2.1 founder-default: an SSO principal on first login gets a personal org
    # (owner). Idempotent — a returning user (already has a membership) is left
    # untouched. Runs on the admin session (this whole function does), which is
    # RLS-exempt; organizations/org_memberships carry no RLS anyway.
    try:
        from app.db.org_service import ensure_personal_org
        await ensure_personal_org(session, local_id, name=user.name, email=user.email)
    except Exception as exc:  # noqa: BLE001 — never break auth on provisioning
        logger.warning("BR-2.1 personal-org provisioning failed for %s: %s", email_norm, exc)

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
        # BR-2.6: multi-factor signal from the token's acr/amr (raw claims).
        mfa=mfa_satisfied(kc_user.raw),
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


# Header a caller sends to act under a specific org they belong to (BR-2.1
# active-org selection). Validated against membership in _bind_org_context.
ORG_HEADER = "X-Org-Id"


def _extract_requested_org_id(request: Request) -> Optional[str]:
    """Read the requested active org from the ``X-Org-Id`` header, if present."""
    val = request.headers.get(ORG_HEADER) or request.headers.get(ORG_HEADER.lower())
    val = (val or "").strip()
    return val or None


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
    # Parenthesized so the admin-bypass condition is explicit (``and`` already
    # binds tighter than ``or``, but the intent must be unmistakable): the
    # master-admin key, OR a keyless admin identity (an admin AuthUser with no
    # bound email — a service/bootstrap token, not a human tenant).
    if user.id == "admin" or (user.role == UserRole.ADMIN and not user.email):
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
    """The shared 'early-access' bootstrap org id (created on first need).

    H1 / BR-2.4 (CLOSED): this is now only the FALLBACK org for a keyless identity
    that has neither a bound human NOR a per-key org binding — the master-admin key,
    and legacy service/agent keys minted before BR-2.4 added ``api_keys.org_id``
    (backfilled to early-access). As of BR-2.4 a NEW service/agent key carries its
    own ``org_id`` and binds THAT here instead of this shared org (see the
    ``key_org_id`` branch in ``_bind_org_context``), so per-customer keys are
    isolated and multi-customer key issuance is safe. Admin cross-org reach is
    unchanged: trusted system work runs on the RLS-exempt ``admin_session``.
    """
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
        try:
            await session.commit()
            await session.refresh(org)
        except IntegrityError:
            # C7 cold-start race: a concurrent keyless request created 'early-access'
            # first (organizations.slug is UNIQUE). Roll back our losing INSERT and
            # refetch the winner rather than 500 — the bootstrap org exists now.
            await session.rollback()
            org = (await session.execute(
                select(Organization).where(Organization.slug == "early-access")
            )).scalar_one_or_none()
            if org is None:
                raise  # truly unexpected — surface it rather than mask
    return str(org.id)


async def _bind_org_context(
    user: AuthUser,
    session: AsyncSession,
    requested_org_id: Optional[str] = None,
) -> None:
    """Resolve the user's ACTIVE org and bind it into the Postgres RLS GUC
    (``app.current_org_id``) that every org-isolation policy filters on.

    BR-1.1 alignment: ``user.user_id`` is the CANONICAL local ``users.id`` —
    resolved, claimed, and provisioned by ``resolve_canonical_user_id`` during
    auth — NOT a raw Keycloak sub. We key org membership on that canonical id and
    NEVER auto-provision a *user* row here (that is BR-1.1's job).

    BR-2.1 org resolution (this is the change from the early-access default):
      * A resolved human is auto-guaranteed a PERSONAL org (owner) via
        ``ensure_personal_org`` — a new user gets one on first bind; an existing
        user backfilled into 'early-access' keeps that as their home (we don't
        mint a second org that would hide their data).
      * ACTIVE-org selection: when the request carries a valid ``X-Org-Id`` for an
        org the user BELONGS TO, we act under that org; anything they don't belong
        to is refused (403). With no header we default to their home org
        (personal-preferred, else earliest membership).
      * ``user.org_role`` is set to the caller's per-org role in the bound org.

    Fallback (documented): a caller with NO bound human — the master-admin key
    ("admin"), an agent SERVICE key, or a degraded keycloak token whose sub matches
    no users row — has no personal org. BR-2.4 (H1 CLOSED): a service/agent key
    now binds the org named by its OWN ``api_keys.org_id`` (carried as
    ``user.key_org_id``), so per-customer keys are isolated; only the master-admin
    key and legacy NULL-org keys still bind the shared 'early-access' org
    (``_default_org_id``). An ``X-Org-Id`` from such a caller is ignored (there is
    no membership to validate it against — the key's own org_id is authoritative).
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
        # Keyless/service/admin/degraded identity.
        #
        # H1 / BR-2.4 (CLOSED): a service/agent API key now carries its OWN org
        # binding (``api_keys.org_id``, surfaced as ``user.key_org_id``). We bind
        # the request's RLS org to THAT, so two customers' keys are isolated — the
        # per-key org scoping that H1 was blocked on. This is the fix that makes
        # multi-customer service/agent key issuance safe.
        #
        # The master-admin key (no ``key_org_id``) and any legacy key with a NULL
        # org_id still fall back to the shared 'early-access' bootstrap org. Admin
        # cross-org reach is unchanged: trusted system work (scheduler, identity
        # remap) runs on the RLS-exempt ``admin_session``, not this per-request
        # app-role bind — so binding the master-admin key to early-access here does
        # not constrain it.
        if getattr(user, "key_org_id", None):
            org_id = user.key_org_id
        else:
            org_id = await _default_org_id(session)
        org_role = None
    else:
        from app.db.org_service import (
            ensure_personal_org,
            get_membership_role,
            resolve_home_org,
        )
        # Founder-default: guarantee a personal org exists (idempotent).
        await ensure_personal_org(
            session, str(local_user.id),
            name=local_user.name, email=local_user.email,
        )

        if requested_org_id:
            # Active-org selection — validate the caller actually belongs to it.
            # Guard the UUID shape first so a malformed header is a clean 400, not
            # an asyncpg cast 500 deep in the membership query.
            from uuid import UUID as _UUID
            try:
                _UUID(str(requested_org_id))
            except (ValueError, TypeError):
                await session.rollback()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Malformed X-Org-Id (expected a UUID)",
                )
            org_role = await get_membership_role(session, str(local_user.id), requested_org_id)
            if org_role is None:
                await session.rollback()
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You are not a member of the requested organization (X-Org-Id)",
                )
            org_id = requested_org_id
        else:
            home = await resolve_home_org(session, str(local_user.id))
            # ensure_personal_org guarantees at least one membership, so home is
            # non-None here; the guard keeps us honest if that ever changes.
            if home is None:
                org_id = await _default_org_id(session)
                org_role = None
            else:
                org_id, org_role = home
        await session.commit()

    user.org_id = org_id
    user.org_role = org_role
    await session.execute(
        text("SELECT set_config('app.current_org_id', :org_id, false)"),
        {"org_id": org_id},
    )
    # M4: mirror the bound org into the per-task orchestration context so any
    # orchestration events emitted while handling this request are stamped with
    # it, and the SSE stream can filter them to the caller's own org.
    from app.orchestration.event_bus import current_org_id_var
    current_org_id_var.set(org_id)


async def _clear_org_context_safe(session: AsyncSession) -> None:
    """B1 companion (defense-in-depth): positively clear the org RLS GUC for a
    request that resolves NO bound user, so it can NEVER inherit a stale org from
    a reused pooled connection regardless of pool timing. Never raises — auth must
    not break if the clear fails; ``get_session``'s teardown is the backstop (it
    invalidates the connection on a failed clear so a stale org can't be pooled)."""
    try:
        await _clear_org_context(session)
    except Exception:  # noqa: BLE001 — never break the request on a clear failure
        logger.warning(
            "Failed to positively clear org context for an unbound request",
            exc_info=True,
        )


REPORTER_KEY_CONFINED_DETAIL = (
    f"This key carries only the {AUTONOMY_REPORT_PERMISSION} permission. It can register "
    "a job (PUT /api/v1/autonomy/jobs/{key}) and report its runs "
    "(POST /api/v1/autonomy/jobs/{key}/runs), nothing else."
)


def _reporter_key_is_off_its_path(user: Optional[AuthUser], path: str, method: str) -> bool:
    """P-00092: a credential whose ONLY scope is ``autonomy:report`` exists to report
    autonomous runs from an unattended script. Anywhere else it carries no rights —
    it must not read the roster, the knowledge graph or the event stream with the
    VIEWER role every authenticated key otherwise gets."""
    return (
        user is not None
        and is_reporter_only_credential(user.permissions)
        and not is_autonomy_report_request(path, method)
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

    # Allow public paths without auth. A public request resolves NO bound user, so
    # positively clear the org GUC (B1 companion): otherwise a public handler that
    # reads on a reused pooled connection could inherit a previous tenant's org.
    if is_public_path(path):
        await _clear_org_context_safe(session)
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
    if _reporter_key_is_off_its_path(user, path, method):
        logger.warning(
            "Reporter key %s refused off its reporting path: %s %s", user.id, method, path
        )
        # No org is bound for a refused request — positively clear the GUC (B1).
        await _clear_org_context_safe(session)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=REPORTER_KEY_CONFINED_DETAIL,
        )
    await _bind_org_context(user, session, _extract_requested_org_id(request))

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
    if _reporter_key_is_off_its_path(user, request.url.path, request.method):
        # P-00092: a reporter key is anonymous everywhere but its two endpoints.
        user = None
    if user is not None:
        await _bind_org_context(user, session, _extract_requested_org_id(request))
    else:
        # No resolved user → positively clear the org GUC (B1 companion) so an
        # anonymous caller on a reused pooled connection can't inherit a stale org.
        await _clear_org_context_safe(session)
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


def require_autonomy_reporter(
    user: Annotated[AuthUser, Depends(get_current_user)]
) -> AuthUser:
    """P-00092: who may register an outside job and report its runs.

    An operator or admin, OR any credential carrying the ``autonomy:report``
    permission. That permission grants nothing else: it leaves the key at the
    VIEWER role (``role_from_permissions``), so it never passes
    ``require_operator``, and a key with only that scope is confined to the two
    reporting endpoints by ``get_current_user``.
    """
    if user.role in (UserRole.ADMIN, UserRole.OPERATOR):
        return user
    if has_autonomy_report_scope(user.permissions):
        return user
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=(
            "Reporting an autonomous job needs operator access or a key with the "
            f"{AUTONOMY_REPORT_PERMISSION} permission"
        ),
    )


async def require_sse_access(
    request: Request,
    ticket: Annotated[Optional[str], Query()] = None,
    user_via_headers: Annotated[Optional[AuthUser], Depends(get_current_user_optional)] = None,
    session: AsyncSession = Depends(get_session),
) -> AuthUser:
    """Auth dependency for browser ``EventSource`` (SSE) endpoints.

    ``EventSource`` cannot send ``Authorization``/``X-API-Key`` headers, so in
    addition to the normal header/cookie auth this accepts a short-lived,
    single-use ``?ticket=<t>`` minted via an authenticated POST (see
    ``app.auth.sse_ticket``). It is purely additive: header/cookie callers are
    resolved exactly as before, and the same minimum-role check the path would
    otherwise enforce is still applied to whichever user we end up with — so the
    ticket can never grant more than its holder already has.

    The ``session`` dependency is the SAME cached ``get_session`` instance
    ``get_current_user_optional`` already resolved (FastAPI dependency caching),
    so it pins no extra connection; it exists only so the B1 companion can
    positively clear the org GUC for an unbound SSE identity.
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
        # No resolved SSE user → clear the org GUC (B1 companion) before failing.
        await _clear_org_context_safe(session)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing credentials (X-API-Key, Bearer token, or SSE ticket)",
            headers={"WWW-Authenticate": f"Bearer, ApiKey realm=\"{AUTH_HEADER}\""},
        )

    # An SSE stream never reads org-scoped rows via RLS (it fans out the in-memory
    # event bus and filters by org in Python — see stream_events / M4). A ticket
    # user carries the org bound at mint time on ``user.org_id``; a caller with no
    # bound org must not ride a stale org on the pooled connection, so clear it.
    if getattr(user, "org_id", None) is None:
        await _clear_org_context_safe(session)

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
