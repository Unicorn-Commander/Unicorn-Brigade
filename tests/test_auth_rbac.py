"""Auth/RBAC behavior tests."""

import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.auth.middleware import AuthUser, get_current_user
from app.auth.roles import UserRole
from app.db.database import get_session
from app.security import rate_limit as rate_limit_module
from app.mcp.sandbox_executor import ExecutionResult, sandbox_executor


client = TestClient(app)


async def _override_get_session():
    class DummySession:
        pass
    yield DummySession()


@pytest.fixture(autouse=True)
def _clear_overrides():
    app.dependency_overrides = {}
    yield
    app.dependency_overrides = {}


def _set_user(role: UserRole, user_id: str = "user-1", agent_id: str = None):
    async def _override_get_current_user():
        return AuthUser(id=user_id, role=role, agent_id=agent_id)
    app.dependency_overrides[get_current_user] = _override_get_current_user
    app.dependency_overrides[get_session] = _override_get_session


def test_admin_endpoint_rejects_operator():
    _set_user(UserRole.OPERATOR, user_id="operator-1")
    response = client.post(
        "/api/v1/orchestration/agents/create",
        json={"description": "test agent"},
    )
    assert response.status_code == 403


def test_ownership_blocks_cross_user_conversation(monkeypatch):
    from app.db.repositories import ConversationRepository

    async def _fake_get(self, conv_id, include_messages=False):
        return {
            "id": conv_id,
            "user_id": "user-b",
            "status": "active",
            "message_count": 0,
            "total_tokens": 0,
        }

    monkeypatch.setattr(ConversationRepository, "get", _fake_get)
    _set_user(UserRole.OPERATOR, user_id="user-a")

    response = client.get("/api/v1/conversations/test-conv")
    assert response.status_code == 403


def test_rate_limit_returns_429(monkeypatch):
    async def _fake_execute(*args, **kwargs):
        return ExecutionResult(
            stdout="ok",
            stderr="",
            success=True,
            exit_code=0,
            execution_time=0.01,
            sandbox_type="docker",
        )

    monkeypatch.setattr(sandbox_executor, "execute", _fake_execute)
    rate_limit_module._requests.clear()
    _set_user(UserRole.ADMIN, user_id="admin-1")

    headers = {"X-API-Key": "admin-key"}
    payload = {"code": "echo test", "language": "bash"}

    # Limit is 10/min for sandbox execute
    for _ in range(10):
        resp = client.post("/api/v1/mcp/registry/sandbox/execute", headers=headers, json=payload)
        assert resp.status_code == 200

    resp = client.post("/api/v1/mcp/registry/sandbox/execute", headers=headers, json=payload)
    assert resp.status_code == 429


def test_size_limit_chat_completions_returns_413():
    _set_user(UserRole.OPERATOR, user_id="operator-1")
    big_content = "x" * (100 * 1024 + 1)
    payload = {"messages": [{"role": "user", "content": big_content}]}

    resp = client.post("/api/v1/chat/completions", json=payload)
    assert resp.status_code == 413


def test_size_limit_sandbox_execute_returns_413(monkeypatch):
    async def _fake_execute(*args, **kwargs):
        return ExecutionResult(
            stdout="ok",
            stderr="",
            success=True,
            exit_code=0,
            execution_time=0.01,
            sandbox_type="docker",
        )

    monkeypatch.setattr(sandbox_executor, "execute", _fake_execute)
    _set_user(UserRole.ADMIN, user_id="admin-1")

    big_code = "a" * (1024 * 1024 + 10)
    resp = client.post(
        "/api/v1/mcp/registry/sandbox/execute",
        json={"code": big_code, "language": "python"},
    )
    assert resp.status_code == 413


def test_size_limit_agent_import_returns_413():
    _set_user(UserRole.OPERATOR, user_id="operator-1")
    big_name = "x" * (5 * 1024 * 1024 + 1)
    payload = [{"name": big_name, "domain": "general"}]

    resp = client.post("/api/v1/agents/import/json", json=payload)
    assert resp.status_code == 413
