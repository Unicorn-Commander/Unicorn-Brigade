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
import logging
from typing import Optional, Annotated
from dataclasses import dataclass
from datetime import datetime

from fastapi import Depends, HTTPException, Query, Request, status
from fastapi.security import APIKeyHeader, HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.database import get_session
from app.db.models import ApiKey, UserApiKey, User
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
    auth_source: str = "api_key"  # api_key | keycloak | session | bypass | public

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

    # Check master admin key first (for bootstrap/development)
    if MASTER_ADMIN_KEY and api_key == MASTER_ADMIN_KEY:
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


async def _sync_user_apps_from_keycloak(email, kc_sub, derived_apps, realm_role):
    """Find-or-create the Brigade User row by email and sync apps + role.

    Apps are merged additively (provisioned apps from upstream services and
    apps from Keycloak both contribute). role is updated to match the
    Keycloak-derived role on every login so changes propagate.
    """
    if not email:
        return
    try:
        from app.db.database import async_session
        from app.db.models import User as _User
        from sqlalchemy import select as _select
        from datetime import datetime as _dt
        async with async_session() as s:
            r = await s.execute(_select(_User).where(_User.email == email.lower()))
            user = r.scalar_one_or_none()
            if user is None:
                # Auto-provision on first SSO login
                user = _User(
                    email=email.lower(),
                    name=email.split("@")[0],
                    password_hash="NOLOGIN-SSO-ONLY",
                    role=realm_role.value if hasattr(realm_role, "value") else str(realm_role),
                    apps=list(derived_apps),
                    is_active=True,
                )
                s.add(user)
                await s.commit()
                logger.info(f"SSO auto-provisioned Brigade user {email} apps={derived_apps}")
                return
            # Merge apps additively + sync role
            existing = set(user.apps or [])
            merged = sorted(existing.union(derived_apps))
            new_role = realm_role.value if hasattr(realm_role, "value") else str(realm_role)
            changed = False
            if list(merged) != list(user.apps or []):
                user.apps = merged
                changed = True
            if user.role != new_role:
                user.role = new_role
                changed = True
            if changed:
                user.updated_at = _dt.utcnow()
                await s.commit()
                logger.info(f"SSO synced Brigade user {email} role={user.role} apps={user.apps}")
    except Exception as exc:  # noqa: BLE001 — never break auth on a sync failure
        logger.warning(f"Keycloak->User.apps sync failed for {email}: {exc}")


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

    # Derive apps from app:* roles and persist to the Brigade User row so
    # subsequent API-key calls see the same apps. Best-effort — never breaks
    # auth on sync failure.
    derived_apps = _derive_apps_from_roles(all_roles)
    await _sync_user_apps_from_keycloak(kc_user.email, kc_user.sub, derived_apps, role)

    return AuthUser(
        id=kc_user.sub,
        role=role,
        user_id=kc_user.sub,
        email=kc_user.email,
        key_name=kc_user.preferred_username or kc_user.email,
        permissions=all_roles,
        auth_source="keycloak",
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

    return await _resolve_user(request, api_key, creds, session)


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
