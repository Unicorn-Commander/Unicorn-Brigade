"""Key-scope ceiling (P-00092, Project-Ops 42d214cc).

A caller may grant a NEW API key only scopes at or below its own role, and an
unknown scope is refused. Before this, a key's scopes were stored exactly as sent
and its role is derived from them, so an operator-level credential could mint
itself an "admin" key on either mint endpoint.

The pure rules are tested first. The route tests mount the REAL agent-key and
user-key routers behind the REAL ``get_current_user`` (only credential
resolution, the org bind and the repositories are stubbed), because the gate has
to hold in the wiring, before anything is written.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.api.apikey_routes as apikey_routes
import app.api.user_routes as user_routes
import app.auth.middleware as middleware
from app.auth.middleware import AuthUser
from app.auth.roles import (
    ADMIN_ONLY_SCOPES,
    AUTONOMY_REPORT_PERMISSION,
    KNOWN_KEY_SCOPES,
    OPERATOR_GRANTABLE_SCOPES,
    UserRole,
    check_key_scope_grant,
    grantable_scopes,
    normalize_key_scopes,
    permissions_for_role,
    role_from_permissions,
)
from app.db.database import get_session

# ---------------------------------------------------------------- pure rules

def test_an_operator_cannot_grant_admin():
    assert check_key_scope_grant(UserRole.OPERATOR, ["admin"]) == ([], ["admin"])
    assert check_key_scope_grant(UserRole.OPERATOR, ["read", "admin", "write"]) == ([], ["admin"])


def test_case_and_whitespace_do_not_get_admin_past_the_ceiling():
    for spelled in (["Admin"], [" ADMIN "], ["admin", "Admin"]):
        assert check_key_scope_grant(UserRole.OPERATOR, spelled) == ([], ["admin"])


def test_an_operator_can_grant_every_operator_scope():
    scopes = ["read", "chat", "write", "invoke", "modify", AUTONOMY_REPORT_PERMISSION]
    assert check_key_scope_grant(UserRole.OPERATOR, scopes) == ([], [])


def test_an_admin_can_grant_every_known_scope():
    assert check_key_scope_grant(UserRole.ADMIN, sorted(KNOWN_KEY_SCOPES)) == ([], [])


def test_a_viewer_can_grant_read_only():
    assert check_key_scope_grant(UserRole.VIEWER, ["read"]) == ([], [])
    assert check_key_scope_grant(UserRole.VIEWER, ["chat", "read"]) == ([], ["chat"])


def test_unknown_scopes_are_refused_for_every_role():
    for role in UserRole:
        unknown, _ = check_key_scope_grant(role, ["read", "root", "superuser"])
        assert unknown == ["root", "superuser"]


def test_an_empty_or_missing_scope_list_is_allowed():
    for role in UserRole:
        assert check_key_scope_grant(role, []) == ([], [])
        assert check_key_scope_grant(role, None) == ([], [])


def test_normalize_lowercases_strips_dedupes_and_keeps_order():
    assert normalize_key_scopes([" Read", "chat", "READ", "", "  ", "Write"]) == ["read", "chat", "write"]
    assert normalize_key_scopes(None) == []


def test_every_scope_that_raises_a_role_is_classified():
    # role_from_permissions turns "admin" into ADMIN and "write"/"chat" into OPERATOR;
    # each of those must sit in the right tier of the ceiling.
    assert "admin" in ADMIN_ONLY_SCOPES and "admin" not in OPERATOR_GRANTABLE_SCOPES
    assert {"write", "chat"} <= OPERATOR_GRANTABLE_SCOPES
    for scope in KNOWN_KEY_SCOPES:
        role = role_from_permissions([scope])
        assert scope in grantable_scopes(role) or role == UserRole.VIEWER


def test_a_role_can_grant_its_own_default_scopes():
    for role in UserRole:
        assert set(permissions_for_role(role)) <= grantable_scopes(role)


def test_the_ui_dialog_and_request_defaults_are_known_scopes():
    # GenerateApiKeyModal offers read / invoke / modify; both request models default to chat + read.
    assert {"read", "invoke", "modify", "chat"} <= KNOWN_KEY_SCOPES
    assert apikey_routes.GenerateKeyRequest(name="x").permissions == ["chat", "read"]
    assert user_routes.CreateApiKeyRequest(name="x").permissions == ["chat", "read"]


# ---------------------------------------------------------------- the wiring

CREDENTIALS = {
    "viewer-key": lambda: AuthUser(id="viewer", role=UserRole.VIEWER, permissions=["read"]),
    "operator-key": lambda: AuthUser(id="op", role=UserRole.OPERATOR, permissions=["write", "chat", "read"]),
    "admin-key": lambda: AuthUser(id="admin", role=UserRole.ADMIN, permissions=[]),
}


@pytest.fixture
def api(monkeypatch):
    calls = {"agent_keys": [], "user_keys": []}

    async def _resolve_user(request, api_key, creds, session):
        make = CREDENTIALS.get(api_key or "")
        return make() if make else None

    async def _bind(user, session, requested_org_id=None):
        user.org_id = "org-a"

    async def _noop(*_args, **_kwargs):
        return None

    monkeypatch.setattr(middleware, "AUTH_BYPASS_ENABLED", False)
    monkeypatch.delenv("BRIGADE_ALLOWED_EMAILS", raising=False)
    monkeypatch.setattr(middleware, "_resolve_user", _resolve_user)
    monkeypatch.setattr(middleware, "_bind_org_context", _bind)
    monkeypatch.setattr(middleware, "_clear_org_context_safe", _noop)

    class _Agents:
        def __init__(self, session):
            pass

        async def get(self, agent_id):
            return {"id": agent_id} if agent_id == "agent-1" else None

    class _AgentKeys:
        def __init__(self, session):
            pass

        async def generate(self, agent_id, data, org_id=None):
            calls["agent_keys"].append({"agent_id": agent_id, **data})
            return {"id": "k1", "agentId": agent_id, "permissions": data["permissions"], "keyPrefix": "ubk-test"}

    class _UserKeys:
        def __init__(self, session):
            pass

        async def generate(self, user_id, data):
            calls["user_keys"].append({"user_id": user_id, **data})
            return {"id": "u1", "userId": user_id, "permissions": data["permissions"], "keyPrefix": "ubk-test"}

    async def _db_user(session, current_user):
        return "user-1"

    monkeypatch.setattr(apikey_routes, "AgentRepository", _Agents)
    monkeypatch.setattr(apikey_routes, "ApiKeyRepository", _AgentKeys)
    monkeypatch.setattr(user_routes, "UserApiKeyRepository", _UserKeys)
    monkeypatch.setattr(user_routes, "_resolve_db_user_id", _db_user)

    app = FastAPI()
    app.include_router(apikey_routes.router, prefix="/api/v1")
    app.include_router(user_routes.router, prefix="/api/v1")

    async def _session():
        yield object()

    app.dependency_overrides[get_session] = _session
    client = TestClient(app)
    client.calls = calls
    return client


def _mint(api, path, key, **body):
    return api.post(path, headers={"X-API-Key": key}, json={"name": "test key", **body})


AGENT_KEYS = "/api/v1/agents/agent-1/api-keys"
USER_KEYS = "/api/v1/users/me/api-keys"


@pytest.mark.parametrize("path", [AGENT_KEYS, USER_KEYS])
def test_an_operator_cannot_mint_an_admin_key(api, path):
    r = _mint(api, path, "operator-key", permissions=["admin"])
    assert r.status_code == 403
    assert "Not allowed: admin" in r.json()["detail"]
    assert api.calls == {"agent_keys": [], "user_keys": []}  # nothing was written


@pytest.mark.parametrize("path", [AGENT_KEYS, USER_KEYS])
def test_spelling_admin_differently_does_not_help(api, path):
    r = _mint(api, path, "operator-key", permissions=["read", " Admin "])
    assert r.status_code == 403
    assert api.calls == {"agent_keys": [], "user_keys": []}


@pytest.mark.parametrize("path", [AGENT_KEYS, USER_KEYS])
def test_an_unknown_scope_is_a_422(api, path):
    r = _mint(api, path, "operator-key", permissions=["read", "root"])
    assert r.status_code == 422
    assert "Unknown permission: root" in r.json()["detail"]
    assert api.calls == {"agent_keys": [], "user_keys": []}


@pytest.mark.parametrize("path,bucket", [(AGENT_KEYS, "agent_keys"), (USER_KEYS, "user_keys")])
def test_an_operator_can_mint_operator_scopes_normalized(api, path, bucket):
    r = _mint(api, path, "operator-key", permissions=["Write", "chat", "READ", "read", AUTONOMY_REPORT_PERMISSION])
    assert r.status_code == 201, r.text
    assert api.calls[bucket][0]["permissions"] == ["write", "chat", "read", AUTONOMY_REPORT_PERMISSION]


@pytest.mark.parametrize("path,bucket", [(AGENT_KEYS, "agent_keys"), (USER_KEYS, "user_keys")])
def test_the_default_scopes_still_work_for_an_operator(api, path, bucket):
    r = api.post(path, headers={"X-API-Key": "operator-key"}, json={"name": "default scopes"})
    assert r.status_code == 201, r.text
    assert api.calls[bucket][0]["permissions"] == ["chat", "read"]


@pytest.mark.parametrize("path,bucket", [(AGENT_KEYS, "agent_keys"), (USER_KEYS, "user_keys")])
def test_an_admin_can_still_mint_an_admin_key(api, path, bucket):
    r = _mint(api, path, "admin-key", permissions=["admin", "write", "chat", "read"])
    assert r.status_code == 201, r.text
    assert api.calls[bucket][0]["permissions"] == ["admin", "write", "chat", "read"]


def test_the_ui_dialog_scopes_still_mint_for_an_operator(api):
    r = _mint(api, AGENT_KEYS, "operator-key", permissions=["read", "invoke", "modify"])
    assert r.status_code == 201, r.text


@pytest.mark.parametrize("path", [AGENT_KEYS, USER_KEYS])
def test_a_viewer_still_cannot_mint_at_all(api, path):
    r = _mint(api, path, "viewer-key", permissions=["read"])
    assert r.status_code == 403
    assert api.calls == {"agent_keys": [], "user_keys": []}


def test_the_ceiling_fails_closed_without_a_caller():
    with pytest.raises(Exception) as exc:
        middleware.enforce_key_scope_ceiling(None, ["read"])
    assert getattr(exc.value, "status_code", None) == 403
