"""
User registration and authentication routes.

Provides endpoints for:
- User registration (public, rate limited)
- User login (returns API key)
- Profile management (authenticated)
- User API key management
"""

import os
import re
import time
import logging
from collections import defaultdict
from datetime import datetime
from typing import Optional, List, Annotated

from fastapi import APIRouter, HTTPException, Depends, Request, status
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_session
from app.db.repositories import UserRepository, UserApiKeyRepository
from app.db.models import User
from app.auth.keycloak import keycloak_enabled
from app.auth.middleware import get_current_user, AuthUser
from app.auth.roles import UserRole

logger = logging.getLogger(__name__)
router = APIRouter()


def native_register_enabled() -> bool:
    """Whether native email/password signup is allowed.

    Mirrors GET /auth/config (oidc_routes.auth_config): explicit
    BRIGADE_ALLOW_NATIVE_REGISTER wins; otherwise native register defaults
    OFF whenever Keycloak SSO owns identity, so /users/register can't mint
    shadow accounts that bypass SSO.
    """
    sso = keycloak_enabled()
    return os.getenv(
        "BRIGADE_ALLOW_NATIVE_REGISTER", "false" if sso else "true"
    ).lower() == "true"


async def _resolve_db_user_id(session: AsyncSession, current_user: AuthUser) -> Optional[str]:
    """Map an AuthUser onto its ``users`` row id, or None if it has none.

    Personal API keys FK onto users.id, but AuthUser.id is only that id for
    native logins. Keycloak principals carry the *Keycloak sub* (a different
    UUID from the auto-provisioned users row, which is keyed by email), and
    the master admin key is the literal string "admin" — both would otherwise
    500 as an invalid UUID / FK violation.
    """
    from uuid import UUID as _UUID
    from sqlalchemy import select

    candidate = str(current_user.id or "")
    try:
        _UUID(candidate)
        row = await session.execute(select(User.id).where(User.id == candidate))
        if row.scalar_one_or_none():
            return candidate
    except ValueError:
        pass

    if current_user.email:
        row = await session.execute(
            select(User.id).where(User.email == current_user.email.lower())
        )
        found = row.scalar_one_or_none()
        if found:
            return str(found)

    return None


def _no_db_user_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=(
            "Personal API keys require a user account. Sign in via SSO "
            "(service and master-admin keys have no personal key store)."
        ),
    )

# ---- Password Hashing with bcrypt directly ----
# NOTE: Using bcrypt directly instead of passlib due to passlib+bcrypt>=4.1 incompatibility
import bcrypt as _bcrypt

def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    salt = _bcrypt.gensalt(rounds=12)
    return _bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a bcrypt hash"""
    try:
        return _bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return False


# ---- Rate Limiting ----

class RateLimiter:
    """Simple in-memory rate limiter for registration endpoint"""

    def __init__(self, max_requests: int = 5, window_seconds: int = 3600):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: dict = defaultdict(list)

    def is_allowed(self, identifier: str) -> bool:
        """Check if request is allowed for this identifier (IP or email)"""
        now = time.time()
        window_start = now - self.window_seconds

        # Clean old requests
        self.requests[identifier] = [
            ts for ts in self.requests[identifier] if ts > window_start
        ]

        # Check limit
        if len(self.requests[identifier]) >= self.max_requests:
            return False

        # Record this request
        self.requests[identifier].append(now)
        return True

    def get_retry_after(self, identifier: str) -> int:
        """Get seconds until next allowed request"""
        if not self.requests[identifier]:
            return 0
        oldest = min(self.requests[identifier])
        return max(0, int(oldest + self.window_seconds - time.time()))


# Rate limiter: 5 registrations per IP per hour
registration_limiter = RateLimiter(max_requests=5, window_seconds=3600)


# ---- Request/Response Models ----

class UserRegisterRequest(BaseModel):
    """User registration request"""
    email: EmailStr
    password: str
    name: str

    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password strength"""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not re.search(r'[A-Za-z]', v):
            raise ValueError('Password must contain at least one letter')
        if not re.search(r'[0-9]', v):
            raise ValueError('Password must contain at least one number')
        return v

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate name"""
        v = v.strip()
        if len(v) < 2:
            raise ValueError('Name must be at least 2 characters long')
        if len(v) > 100:
            raise ValueError('Name must be at most 100 characters long')
        return v


class UserLoginRequest(BaseModel):
    """User login request"""
    email: EmailStr
    password: str


class UserUpdateRequest(BaseModel):
    """User profile update request"""
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    current_password: Optional[str] = None
    new_password: Optional[str] = None

    @field_validator('new_password')
    @classmethod
    def validate_new_password(cls, v: Optional[str]) -> Optional[str]:
        """Validate new password strength"""
        if v is None:
            return v
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not re.search(r'[A-Za-z]', v):
            raise ValueError('Password must contain at least one letter')
        if not re.search(r'[0-9]', v):
            raise ValueError('Password must contain at least one number')
        return v


class CreateApiKeyRequest(BaseModel):
    """Create API key request"""
    name: str
    permissions: Optional[List[str]] = ["chat", "read"]
    rateLimit: Optional[int] = 100
    expiresInDays: Optional[int] = 90


class UserResponse(BaseModel):
    """User response (no password hash)"""
    id: str
    email: str
    name: str
    role: str
    isActive: bool
    createdAt: Optional[str] = None
    updatedAt: Optional[str] = None


class LoginResponse(BaseModel):
    """Login response with API key"""
    user: UserResponse
    apiKey: str
    keyPrefix: str


# ---- Helper Functions ----

def get_client_ip(request: Request) -> str:
    """Get client IP from request, handling proxies"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# ---- Endpoints ----

@router.post("/users/register", response_model=UserResponse, status_code=201)
async def register_user(
    request: Request,
    body: UserRegisterRequest,
    session: AsyncSession = Depends(get_session),
):
    """
    Register a new user account.

    - **email**: Valid email address (unique)
    - **password**: At least 8 characters with letters and numbers
    - **name**: Display name (2-100 characters)

    Rate limited to 5 registrations per IP per hour.

    Returns 403 when native registration is disabled (SSO-managed deployments).
    """
    if not native_register_enabled():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account creation is managed by your organization's SSO",
        )

    # Rate limit by IP
    client_ip = get_client_ip(request)
    if not registration_limiter.is_allowed(client_ip):
        retry_after = registration_limiter.get_retry_after(client_ip)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many registration attempts. Try again in {retry_after} seconds.",
            headers={"Retry-After": str(retry_after)},
        )

    repo = UserRepository(session)

    # Check if email already exists
    if await repo.email_exists(body.email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    # Hash password and create user
    password_hash = hash_password(body.password)
    user_data = {
        "email": body.email,
        "password_hash": password_hash,
        "name": body.name,
        "role": "operator",  # Default role
    }

    user = await repo.create(user_data)
    logger.info(f"New user registered: {user['email']} (ID: {user['id']})")

    return UserResponse(**user)


@router.post("/users/login", response_model=LoginResponse)
async def login_user(
    body: UserLoginRequest,
    session: AsyncSession = Depends(get_session),
):
    """
    Authenticate user and return an API key.

    - **email**: Registered email address
    - **password**: Account password

    Returns user profile and a new API key for authentication.
    """
    repo = UserRepository(session)
    key_repo = UserApiKeyRepository(session)

    # Get user by email (returns ORM object for password check)
    user = await repo.get_by_email(body.email)

    if not user:
        # Use same error message to prevent email enumeration
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Verify password
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    # Generate a new API key for this login session
    key_data = {
        "name": f"Login session - {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}",
        "permissions": _get_permissions_for_role(user.role),
        "rateLimit": 1000,
        "expiresInDays": 30,
    }
    api_key = await key_repo.generate(str(user.id), key_data)

    logger.info(f"User logged in: {user.email} (ID: {user.id})")

    return LoginResponse(
        user=UserResponse(**user.to_dict()),
        apiKey=api_key["key"],
        keyPrefix=api_key["keyPrefix"],
    )


@router.get("/users/me", response_model=UserResponse)
async def get_current_user_profile(
    session: AsyncSession = Depends(get_session),
    current_user: Annotated[AuthUser, Depends(get_current_user)] = None,
):
    """
    Get the current authenticated user's profile.

    Requires authentication via API key.
    """
    if not current_user or current_user.id in ("anonymous", "dev-bypass"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    # The legacy admin X-API-Key authenticates as a synthetic AuthUser with
    # id="admin" — there's no row in the users table for it, so a UUID
    # lookup against `users.id` would 500 on the asyncpg side. Return a
    # virtual profile so the frontend can show "logged in as admin" without
    # the route blowing up.
    if current_user.id == "admin":
        return UserResponse(
            id="admin",
            email=getattr(current_user, "email", "") or "admin@brigade.local",
            name="Brigade Admin",
            role="admin",
            isActive=True,
        )

    repo = UserRepository(session)
    # SSO principals carry the Keycloak sub, not the email-keyed users.id, so
    # resolve to the real row id the same way the API-key endpoints do.
    db_user_id = await _resolve_db_user_id(session, current_user)
    user = await repo.get_by_id(db_user_id) if db_user_id else None

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return UserResponse(**user)


@router.put("/users/me", response_model=UserResponse)
async def update_current_user_profile(
    body: UserUpdateRequest,
    session: AsyncSession = Depends(get_session),
    current_user: Annotated[AuthUser, Depends(get_current_user)] = None,
):
    """
    Update the current authenticated user's profile.

    - **name**: New display name (optional)
    - **email**: New email address (optional)
    - **current_password**: Required if changing password
    - **new_password**: New password (optional)

    Requires authentication via API key.
    """
    if not current_user or current_user.id in ("anonymous", "dev-bypass"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    repo = UserRepository(session)

    # Resolve the real users-row id (SSO principals carry the Keycloak sub,
    # which isn't the email-keyed users.id — same resolution the API-key
    # endpoints use).
    db_user_id = await _resolve_db_user_id(session, current_user)

    # Get current user from DB (need ORM object for password verification)
    user_dict = await repo.get_by_id(db_user_id) if db_user_id else None
    if not user_dict:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # For password change, we need the ORM object
    db_user = await repo.get_by_email(user_dict["email"])
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    updates = {}

    # Update name if provided
    if body.name is not None:
        name = body.name.strip()
        if len(name) < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Name must be at least 2 characters",
            )
        updates["name"] = name

    # Update email if provided
    if body.email is not None and body.email.lower() != db_user.email:
        # Check if new email is taken
        if await repo.email_exists(body.email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already in use",
            )
        updates["email"] = body.email

    # Update password if provided
    if body.new_password is not None:
        # SSO-provisioned accounts have no local password to change.
        if (db_user.password_hash or "").startswith("NOLOGIN-SSO"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password is managed by your SSO provider",
            )
        if body.current_password is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password required to change password",
            )
        if not verify_password(body.current_password, db_user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Current password is incorrect",
            )
        updates["password_hash"] = hash_password(body.new_password)

    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No updates provided",
        )

    updated_user = await repo.update(db_user_id, updates)
    logger.info(f"User profile updated: {db_user_id}")

    return UserResponse(**updated_user)


@router.post("/users/me/api-keys", status_code=201)
async def create_user_api_key(
    body: CreateApiKeyRequest,
    session: AsyncSession = Depends(get_session),
    current_user: Annotated[AuthUser, Depends(get_current_user)] = None,
):
    """
    Create a new API key for the current user.

    - **name**: Descriptive name for the key
    - **permissions**: List of permissions (default: ["chat", "read"])
    - **rateLimit**: Requests per minute (default: 100)
    - **expiresInDays**: Days until expiration (default: 90)

    The full API key is only returned once - store it securely!
    """
    if not current_user or current_user.id in ("anonymous", "dev-bypass"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    db_user_id = await _resolve_db_user_id(session, current_user)
    if not db_user_id:
        raise _no_db_user_error()

    repo = UserApiKeyRepository(session)
    result = await repo.generate(db_user_id, body.model_dump())

    logger.info(f"User {db_user_id} created API key: {result['keyPrefix']}...")

    return result


@router.get("/users/me/api-keys")
async def list_user_api_keys(
    session: AsyncSession = Depends(get_session),
    current_user: Annotated[AuthUser, Depends(get_current_user)] = None,
):
    """
    List all API keys for the current user.

    Keys are returned without the full key value (only prefix shown).
    """
    if not current_user or current_user.id in ("anonymous", "dev-bypass"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    db_user_id = await _resolve_db_user_id(session, current_user)
    if not db_user_id:
        raise _no_db_user_error()

    repo = UserApiKeyRepository(session)
    keys = await repo.list_for_user(db_user_id)

    return {"keys": keys}


@router.delete("/users/me/api-keys/{key_id}")
async def revoke_user_api_key(
    key_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: Annotated[AuthUser, Depends(get_current_user)] = None,
):
    """
    Revoke (deactivate) one of the current user's API keys.
    """
    if not current_user or current_user.id in ("anonymous", "dev-bypass"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    db_user_id = await _resolve_db_user_id(session, current_user)
    if not db_user_id:
        raise _no_db_user_error()

    repo = UserApiKeyRepository(session)
    success = await repo.revoke(db_user_id, key_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )

    logger.info(f"User {current_user.id} revoked API key: {key_id}")

    return {"message": "API key revoked", "id": key_id}


# ---- Helper Functions ----

def _get_permissions_for_role(role: str) -> List[str]:
    """Get default permissions based on user role"""
    if role == "admin":
        return ["admin", "write", "chat", "read"]
    elif role == "operator":
        return ["write", "chat", "read"]
    else:  # viewer
        return ["read"]
