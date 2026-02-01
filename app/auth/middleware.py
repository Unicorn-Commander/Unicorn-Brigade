"""
Authentication Middleware

Provides FastAPI dependencies for route protection:
- API key authentication
- Role-based authorization
- Optional auth for mixed endpoints
"""

import os
import hashlib
import logging
from typing import Optional, Annotated
from dataclasses import dataclass
from datetime import datetime

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.database import get_session
from app.db.models import ApiKey, UserApiKey, User
from app.auth.roles import UserRole, is_admin_path, is_public_path, get_minimum_role_for_method

logger = logging.getLogger(__name__)

# Header name for API key
AUTH_HEADER = "X-API-Key"

# API key header security scheme
api_key_header = APIKeyHeader(name=AUTH_HEADER, auto_error=False)

# Environment variable for master admin key (for development/bootstrap)
MASTER_ADMIN_KEY = os.getenv("BRIGADE_ADMIN_KEY", "")

# Allow auth bypass in development mode (DANGEROUS - never in production)
AUTH_BYPASS_FLAG = os.getenv("AUTH_BYPASS", "false").lower() == "true"
AUTH_BYPASS_ENABLED = AUTH_BYPASS_FLAG and os.getenv("ENVIRONMENT", "production").lower() == "development"


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
        )

    except Exception as e:
        logger.error(f"Error validating API key: {e}")
        return None


async def get_current_user(
    request: Request,
    api_key: Annotated[Optional[str], Depends(api_key_header)],
    session: AsyncSession = Depends(get_session),
) -> AuthUser:
    """
    Get the current authenticated user. Raises 401 if not authenticated.

    Use this dependency for protected routes.
    """
    path = request.url.path
    method = request.method

    # Allow public paths without auth
    if is_public_path(path):
        return AuthUser(id="anonymous", role=UserRole.VIEWER)

    # Development bypass (DANGEROUS)
    if AUTH_BYPASS_ENABLED:
        logger.warning("⚠️ AUTH BYPASS ENABLED - DEVELOPMENT MODE ONLY")
        return AuthUser(id="dev-bypass", role=UserRole.ADMIN)
    if AUTH_BYPASS_FLAG:
        logger.error("❌ AUTH_BYPASS=true but ENVIRONMENT!=development - IGNORING")

    # Validate the API key
    user = await validate_api_key(api_key, session)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": f"ApiKey realm=\"{AUTH_HEADER}\""},
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
    session: AsyncSession = Depends(get_session),
) -> Optional[AuthUser]:
    """
    Get the current user if authenticated, otherwise return None.

    Use this for endpoints that behave differently based on auth status.
    """
    if AUTH_BYPASS_ENABLED:
        logger.warning("⚠️ AUTH BYPASS ENABLED - DEVELOPMENT MODE ONLY")
        return AuthUser(id="dev-bypass", role=UserRole.ADMIN)
    if AUTH_BYPASS_FLAG:
        logger.error("❌ AUTH_BYPASS=true but ENVIRONMENT!=development - IGNORING")

    if not api_key:
        return None

    return await validate_api_key(api_key, session)


def require_api_key(
    user: Annotated[AuthUser, Depends(get_current_user)]
) -> AuthUser:
    """Dependency that requires a valid API key"""
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
