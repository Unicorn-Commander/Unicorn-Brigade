# Executed by Grok (headless lane)
"""FastAPI TestClient auth overrides that do not touch product auth logic."""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import FastAPI

from app.auth.middleware import (
    AuthUser,
    get_current_user,
    require_admin,
    require_api_key,
    require_operator,
)
from app.auth.roles import UserRole
from app.db.database import get_session


async def _dummy_session() -> Iterator[object]:
    class DummySession:
        pass

    yield DummySession()


def install_test_auth(
    app: FastAPI,
    *,
    user_id: str = "test-user",
    role: UserRole = UserRole.ADMIN,
) -> None:
    """Override auth + DB session dependencies on a FastAPI app.

    Protected routes bind FastAPI Depends at import time, so patching the
    middleware names does not authenticate TestClient calls. Overrides stay on
    the app object and never change production auth or RLS.
    """

    async def _current_user() -> AuthUser:
        return AuthUser(
            id=user_id,
            role=role,
            user_id=user_id,
            key_name="CI test key",
            permissions=["admin", "chat", "read", "write"],
        )

    app.dependency_overrides[get_current_user] = _current_user
    app.dependency_overrides[require_api_key] = _current_user
    app.dependency_overrides[require_operator] = _current_user
    app.dependency_overrides[require_admin] = _current_user
    app.dependency_overrides[get_session] = _dummy_session
