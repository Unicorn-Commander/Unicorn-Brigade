"""
Authentication and Authorization Module

Provides:
- API key authentication
- Role-based access control
- Route protection decorators
"""

from app.auth.middleware import (
    get_current_user,
    get_current_user_optional,
    require_api_key,
    require_admin,
    AuthUser,
    AUTH_HEADER,
)
from app.auth.roles import UserRole, ADMIN_ONLY_PATHS, PROTECTED_PATHS

__all__ = [
    "get_current_user",
    "get_current_user_optional",
    "require_api_key",
    "require_admin",
    "AuthUser",
    "AUTH_HEADER",
    "UserRole",
    "ADMIN_ONLY_PATHS",
    "PROTECTED_PATHS",
]
