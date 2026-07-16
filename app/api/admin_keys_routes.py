"""
Service-delegation routes for user API key management.

These endpoints let a trusted service (Ops Center, CLI tools) manage Brigade
user API keys on behalf of a user identified by email. Authentication is via
the BRIGADE_SERVICE_KEY shared secret in the X-API-Key header.

Users are auto-provisioned in the Brigade users table on first key creation.
The user's email and role are refreshed on every call to keep Brigade in sync
with the upstream identity provider (Keycloak via Ops Center).

Distinct from:
- app/api/user_routes.py  -- self-service endpoints (JWT/session required)
- app/api/apikey_routes.py -- agent-bound keys
"""

import hmac
import logging
import os
from datetime import datetime
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_session
from app.db.models import User, UserApiKey
from app.db.repositories import UserApiKeyRepository, UserRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/admin/user-keys", tags=["admin-user-keys"])

_SERVICE_KEY_ENV = "BRIGADE_SERVICE_KEY"
_NON_LOGIN_PASSWORD_HASH = "NOLOGIN-SSO-ONLY"  # fails every bcrypt.checkpw
_VALID_ROLES = {"admin", "operator", "viewer"}

# Known-bad default that shipped in the codebase/committed .env. Treated as
# "unconfigured" so a deploy that forgot to set a real secret fails closed
# instead of accepting the public literal.
_KNOWN_BAD_SERVICE_KEY = "sk-brigade-service-key-2025"


# ── Auth dependency ─────────────────────────────────────────────

def require_service_key(
    x_api_key: Annotated[Optional[str], Header(alias="X-API-Key")] = None,
) -> str:
    """Verify the X-API-Key header matches the configured service key.

    Fails closed: if BRIGADE_SERVICE_KEY is unset (or still set to the known
    public default), service delegation is refused with 503 rather than
    authenticating callers against a guessable secret. The header comparison
    uses hmac.compare_digest for constant-time matching.
    """
    expected = os.getenv(_SERVICE_KEY_ENV, "") or ""
    if not expected or hmac.compare_digest(expected, _KNOWN_BAD_SERVICE_KEY):
        logger.error(
            "BRIGADE_SERVICE_KEY is not configured (unset or set to the known "
            "default); refusing service-delegation requests"
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service delegation is not configured on this Brigade instance",
        )
    if not x_api_key or not hmac.compare_digest(x_api_key, expected):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Service key required",
        )
    return x_api_key


# ── Request/response models ─────────────────────────────────────

class CreateUserKeyRequest(BaseModel):
    email: EmailStr
    role: str = Field("operator", description="Role to apply: admin, operator, or viewer")
    display_name: Optional[str] = Field(None, description="Full name for new user rows")
    name: str = Field(..., min_length=1, max_length=255, description="Key label")
    permissions: Optional[List[str]] = None
    rate_limit: Optional[int] = Field(None, description="Requests per minute")
    expires_in_days: Optional[int] = Field(90, description="Days until the key expires; null for no expiry")
    apps: Optional[List[str]] = Field(None, description="Brigade-consumer apps this user is a member of (e.g., ['crisis-ops','librechat']). Merged into user.apps; existing apps are preserved.")


class KeyResponse(BaseModel):
    id: str
    user_id: str
    email: str
    name: str
    key_prefix: str
    permissions: List[str]
    rate_limit: Optional[int] = None
    expires_at: Optional[str] = None
    last_used_at: Optional[str] = None
    usage_count: int = 0
    is_active: bool = True
    created_at: Optional[str] = None
    created_via: Optional[str] = None
    key: Optional[str] = Field(None, description="Full raw key; present only on create")


# ── Helpers ─────────────────────────────────────────────────────

async def _upsert_user(
    session: AsyncSession,
    email: str,
    role: str,
    display_name: Optional[str],
    apps: Optional[List[str]] = None,
) -> User:
    """Find-or-create a Brigade users row and refresh role/name from the caller."""
    if role not in _VALID_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role '{role}'. Must be one of: {sorted(_VALID_ROLES)}",
        )

    email = email.lower().strip()
    result = await session.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            email=email,
            name=display_name or email.split("@")[0],
            password_hash=_NON_LOGIN_PASSWORD_HASH,
            role=role,
            apps=sorted(set(apps or [])),
            is_active=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        logger.info(f"Auto-provisioned Brigade user {email} (role={role}) via service delegation")
        return user

    changed = False
    if user.role != role:
        user.role = role
        changed = True
    if display_name and user.name != display_name:
        user.name = display_name
        changed = True
    if not user.is_active:
        user.is_active = True
        changed = True
    if apps:
        existing_apps = set(user.apps or [])
        merged = sorted(existing_apps.union(apps))
        if list(merged) != list(user.apps or []):
            user.apps = merged
            changed = True
    if changed:
        user.updated_at = datetime.utcnow()
        await session.commit()
        await session.refresh(user)
        logger.info(f"Refreshed Brigade user {email} (role={role}, apps={user.apps}) via service delegation")

    return user


def _permissions_for_role(role: str) -> List[str]:
    if role == "admin":
        return ["admin", "write", "chat", "read"]
    if role == "operator":
        return ["write", "chat", "read"]
    return ["read"]


def _serialize(key: UserApiKey, email: str, raw_key: Optional[str] = None) -> dict:
    return {
        "id": key.id,
        "user_id": str(key.user_id),
        "email": email,
        "name": key.name,
        "key_prefix": key.key_prefix,
        "permissions": key.permissions or ["chat", "read"],
        "rate_limit": key.rate_limit,
        "expires_at": key.expires_at.isoformat() + "Z" if key.expires_at else None,
        "last_used_at": key.last_used_at.isoformat() + "Z" if key.last_used_at else None,
        "usage_count": key.usage_count or 0,
        "is_active": key.is_active,
        "created_at": key.created_at.isoformat() + "Z" if key.created_at else None,
        "created_via": getattr(key, "created_via", None),
        "key": raw_key,
    }


# ── Endpoints ───────────────────────────────────────────────────

@router.post("", status_code=201, response_model=KeyResponse)
async def create_user_api_key(
    body: CreateUserKeyRequest,
    session: AsyncSession = Depends(get_session),
    _auth: str = Depends(require_service_key),
):
    """Create a Brigade user API key on behalf of a user identified by email.

    The user row is auto-provisioned if missing and role/name are refreshed
    from the caller on every call.
    """
    user = await _upsert_user(session, body.email, body.role, body.display_name, body.apps)

    permissions = body.permissions or _permissions_for_role(user.role)
    key_data = {
        "name": body.name,
        "permissions": permissions,
        "rateLimit": body.rate_limit if body.rate_limit is not None else 100,
        "expiresInDays": body.expires_in_days,
        "createdVia": "ops-center",
    }

    repo = UserApiKeyRepository(session)
    result = await repo.generate(str(user.id), key_data)

    # Refetch to get the ORM object with created_via populated
    q = await session.execute(select(UserApiKey).where(UserApiKey.id == result["id"]))
    key = q.scalar_one()
    logger.info(
        f"Service-delegated key created: user={user.email} name={body.name} "
        f"prefix={key.key_prefix} via=ops-center"
    )
    return _serialize(key, user.email, raw_key=result["key"])


@router.get("", response_model=List[KeyResponse])
async def list_user_api_keys(
    email: str,
    session: AsyncSession = Depends(get_session),
    _auth: str = Depends(require_service_key),
):
    """List active Brigade API keys for the user identified by email."""
    email = email.lower().strip()
    user_q = await session.execute(select(User).where(User.email == email))
    user = user_q.scalar_one_or_none()
    if not user:
        return []
    keys_q = await session.execute(
        select(UserApiKey)
        .where(UserApiKey.user_id == user.id, UserApiKey.is_active == True)  # noqa: E712
        .order_by(UserApiKey.created_at.desc())
    )
    keys = keys_q.scalars().all()
    return [_serialize(k, user.email) for k in keys]


@router.delete("/{key_id}")
async def revoke_user_api_key(
    key_id: str,
    email: str,
    session: AsyncSession = Depends(get_session),
    _auth: str = Depends(require_service_key),
):
    """Revoke a Brigade user API key. The email must match the key's owner."""
    email = email.lower().strip()
    user_q = await session.execute(select(User).where(User.email == email))
    user = user_q.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    repo = UserApiKeyRepository(session)
    ok = await repo.revoke(str(user.id), key_id)
    if not ok:
        raise HTTPException(status_code=404, detail="API key not found")

    logger.info(f"Service-delegated key revoked: user={user.email} key_id={key_id}")
    return {"message": "API key revoked", "id": key_id}
