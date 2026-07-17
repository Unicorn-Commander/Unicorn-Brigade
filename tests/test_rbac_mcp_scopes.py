"""BR-2.3 / BR-2.5 — RBAC on admin surfaces + per-key scope on the one-key MCP.

BR-2.5: the federation MCP gateway (POST /mcp) gates each federated tool by the
caller's per-KEY scope (read/chat/write) carried in ApiKey.permissions — a read-
or chat-scoped key cannot invoke a write/exec tool; a write key can.

BR-2.3: the admin route surfaces declare require_admin / require_operator; those
dependencies reject a non-admin with 403.

These tests mount the real routers/dependencies on MINIMAL FastAPI apps so they
run without app.main's heavy import chain (langgraph et al.). The BR-2.3 tests
that exercise the *real* admin routes go through app.main and self-skip when its
optional deps are absent (they run in full-dependency CI).
"""

from typing import Annotated

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.auth.middleware import (
    AuthUser,
    get_current_user,
    require_admin,
    require_operator,
)
from app.auth.roles import UserRole, mcp_scope_level, key_permits_mcp_tool
from app.db.database import get_session
from app.federation.registry import FederatedAppRepository
from app.federation.mcp_gateway import router as gw_router
import app.federation.mcp_gateway as gw


# ── minimal apps (avoid app.main's langgraph-heavy import chain) ──

gw_app = FastAPI()
gw_app.include_router(gw_router)
gw_client = TestClient(gw_app)

# Mirrors how the real admin surfaces are gated: registry mutations + the
# Brigade-tools MCP tool-call use require_admin; api-key generate uses
# require_operator. Testing the deps directly proves the exact gate those
# routes declare.
admin_app = FastAPI()


@admin_app.post("/admin-only")
async def _admin_only(u: Annotated[AuthUser, Depends(require_admin)]):
    return {"ok": True}


@admin_app.post("/operator-only")
async def _operator_only(u: Annotated[AuthUser, Depends(require_operator)]):
    return {"ok": True}


admin_client = TestClient(admin_app)


async def _override_get_session():
    class DummySession:
        pass
    yield DummySession()


@pytest.fixture(autouse=True)
def _clear_overrides():
    gw_app.dependency_overrides = {}
    admin_app.dependency_overrides = {}
    yield
    gw_app.dependency_overrides = {}
    admin_app.dependency_overrides = {}


def _set_user(target_app, role: UserRole, permissions=None):
    async def _cur():
        return AuthUser(id="u", role=role, permissions=list(permissions or []))
    target_app.dependency_overrides[get_current_user] = _cur
    target_app.dependency_overrides[get_session] = _override_get_session


class _FakeApp:
    """Minimal FederatedApp stand-in for build_catalog / resolve_tool."""
    def __init__(self, namespace="acme", tools=None):
        self.namespace = namespace
        self.expected_audience = f"{namespace}-app"
        self.mcp_endpoint = "https://app.internal/mcp"
        self.status = "active"
        self.tools = tools if tools is not None else [
            {"name": "list_items", "description": "read", "read_only": True,
             "tier_required": "free", "input_schema": {"type": "object"},
             "scopes_required": []},
            {"name": "delete_item", "description": "write", "read_only": False,
             "tier_required": "free", "input_schema": {"type": "object"},
             "scopes_required": ["acme:write"]},
        ]


def _patch_gateway(monkeypatch, apps=None):
    fake_apps = apps if apps is not None else [_FakeApp()]

    async def _fake_list_active(self):
        return fake_apps

    async def _fake_ctx(user):
        # (sub, rank) — enterprise rank so the TIER filter never masks the
        # per-key SCOPE behavior under test.
        return "customer@example.com", 2

    monkeypatch.setattr(FederatedAppRepository, "list_active", _fake_list_active)
    monkeypatch.setattr(gw, "_customer_context", _fake_ctx)


def _mock_upstream_ok(monkeypatch):
    class _Resp:
        status_code = 200
        text = ""

        def json(self):
            return {"jsonrpc": "2.0", "id": 1, "result": {"ok": True}}

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **k):
            return _Resp()

    monkeypatch.setattr(gw, "mint_app_jwt", lambda **kw: "tok")
    monkeypatch.setattr(gw.httpx, "AsyncClient", _Client)


def _call(tool_name):
    return {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": tool_name, "arguments": {}}}


def _list():
    return {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}


# ── BR-2.5 unit: scope level + tool permission matrix ────────────

def test_scope_level_prefers_explicit_key_scopes():
    # A "chat" key resolves to OPERATOR role, but the explicit scope must win so
    # it is NOT treated as write-capable.
    assert mcp_scope_level(UserRole.OPERATOR, ["chat", "read"]) == 2
    assert mcp_scope_level(UserRole.OPERATOR, ["write", "chat", "read"]) == 3
    assert mcp_scope_level(UserRole.VIEWER, ["read"]) == 1
    assert mcp_scope_level(UserRole.ADMIN, ["admin", "write", "chat", "read"]) == 4


def test_scope_level_falls_back_to_role_when_no_named_scopes():
    # Keycloak humans carry realm-role names, not read/chat/write — fall back.
    assert mcp_scope_level(UserRole.ADMIN, ["some-realm-role"]) == 4
    assert mcp_scope_level(UserRole.OPERATOR, ["operator", "app:librechat"]) == 3
    assert mcp_scope_level(UserRole.VIEWER, []) == 1


def test_key_permits_matrix():
    # read tool (read_only=True): anyone with a scope may call it.
    assert key_permits_mcp_tool(UserRole.VIEWER, ["read"], read_only=True)
    assert key_permits_mcp_tool(UserRole.OPERATOR, ["chat", "read"], read_only=True)
    # write tool (read_only=False): only write/admin keys.
    assert not key_permits_mcp_tool(UserRole.VIEWER, ["read"], read_only=False)
    assert not key_permits_mcp_tool(UserRole.OPERATOR, ["chat", "read"], read_only=False)
    assert key_permits_mcp_tool(UserRole.OPERATOR, ["write", "chat", "read"], read_only=False)
    assert key_permits_mcp_tool(UserRole.ADMIN, ["admin"], read_only=False)


# ── BR-2.5 integration: federation /mcp gateway ──────────────────

def test_read_key_rejected_from_write_tool(monkeypatch):
    _patch_gateway(monkeypatch)
    _set_user(gw_app, UserRole.VIEWER, permissions=["read"])
    resp = gw_client.post("/mcp", json=_call("acme.delete_item"))
    assert resp.status_code == 403
    assert "scope" in resp.json()["error"]["message"].lower()


def test_chat_key_rejected_from_write_tool(monkeypatch):
    _patch_gateway(monkeypatch)
    _set_user(gw_app, UserRole.OPERATOR, permissions=["chat", "read"])
    resp = gw_client.post("/mcp", json=_call("acme.delete_item"))
    assert resp.status_code == 403


def test_write_key_allowed_on_write_tool(monkeypatch):
    _patch_gateway(monkeypatch)
    _mock_upstream_ok(monkeypatch)
    _set_user(gw_app, UserRole.OPERATOR, permissions=["write", "chat", "read"])
    resp = gw_client.post("/mcp", json=_call("acme.delete_item"))
    assert resp.status_code == 200
    assert resp.json().get("result") == {"ok": True}


def test_read_key_allowed_on_read_tool(monkeypatch):
    _patch_gateway(monkeypatch)
    _mock_upstream_ok(monkeypatch)
    _set_user(gw_app, UserRole.VIEWER, permissions=["read"])
    resp = gw_client.post("/mcp", json=_call("acme.list_items"))
    assert resp.status_code == 200
    assert resp.json().get("result") == {"ok": True}


def test_tools_list_filters_write_tools_for_read_key(monkeypatch):
    _patch_gateway(monkeypatch)
    _set_user(gw_app, UserRole.VIEWER, permissions=["read"])
    resp = gw_client.post("/mcp", json=_list())
    assert resp.status_code == 200
    names = {t["name"] for t in resp.json()["result"]["tools"]}
    assert "acme.list_items" in names       # read tool visible
    assert "acme.delete_item" not in names  # write tool hidden from a read key


def test_tools_list_shows_write_tools_for_write_key(monkeypatch):
    _patch_gateway(monkeypatch)
    _set_user(gw_app, UserRole.OPERATOR, permissions=["write", "chat", "read"])
    resp = gw_client.post("/mcp", json=_list())
    assert resp.status_code == 200
    names = {t["name"] for t in resp.json()["result"]["tools"]}
    assert {"acme.list_items", "acme.delete_item"} <= names


def test_unknown_tool_returns_jsonrpc_error_not_500(monkeypatch):
    # Regression: the denial-return contract must not KeyError on out["payload"].
    _patch_gateway(monkeypatch)
    _set_user(gw_app, UserRole.ADMIN, permissions=["admin"])
    resp = gw_client.post("/mcp", json=_call("acme.nope"))
    assert resp.status_code == 200
    assert resp.json()["error"]["code"] == -32602


# ── BR-2.3: the admin gate rejects non-admin ─────────────────────

def test_require_admin_rejects_operator():
    _set_user(admin_app, UserRole.OPERATOR, permissions=["write", "chat", "read"])
    assert admin_client.post("/admin-only").status_code == 403


def test_require_admin_rejects_viewer():
    _set_user(admin_app, UserRole.VIEWER, permissions=["read"])
    assert admin_client.post("/admin-only").status_code == 403


def test_require_admin_allows_admin():
    _set_user(admin_app, UserRole.ADMIN, permissions=["admin", "write", "chat", "read"])
    assert admin_client.post("/admin-only").status_code == 200


def test_require_operator_rejects_viewer():
    _set_user(admin_app, UserRole.VIEWER, permissions=["read"])
    assert admin_client.post("/operator-only").status_code == 403


def test_require_operator_allows_operator():
    _set_user(admin_app, UserRole.OPERATOR, permissions=["write", "chat", "read"])
    assert admin_client.post("/operator-only").status_code == 200


# ── BR-2.3: real admin routes (full-dependency CI only) ──────────

try:  # app.main pulls langgraph/mem0/etc.; skip these where absent.
    from app.main import app as _full_app
    _FULL_APP = True
except Exception:  # noqa: BLE001
    _full_app = None
    _FULL_APP = False


@pytest.mark.skipif(not _FULL_APP, reason="app.main optional deps not installed")
class TestRealAdminRoutes:
    def setup_method(self):
        _full_app.dependency_overrides = {}

    def teardown_method(self):
        _full_app.dependency_overrides = {}

    def _op(self):
        async def _cur():
            return AuthUser(id="op", role=UserRole.OPERATOR,
                            permissions=["write", "chat", "read"])
        _full_app.dependency_overrides[get_current_user] = _cur
        _full_app.dependency_overrides[get_session] = _override_get_session

    def test_registry_register_rejects_operator(self):
        self._op()
        c = TestClient(_full_app)
        r = c.post("/api/v1/mcp/registry/servers", json={
            "name": "x", "display_name": "X", "command": "npx", "args": [],
            "env": {}, "capabilities": [], "description": "",
        })
        assert r.status_code == 403

    def test_registry_start_rejects_operator(self):
        self._op()
        c = TestClient(_full_app)
        assert c.post("/api/v1/mcp/registry/servers/github/start").status_code == 403

    def test_mcp_tools_call_rejects_operator(self):
        self._op()
        c = TestClient(_full_app)
        r = c.post("/api/v1/mcp/tools/call", json={"name": "calculator", "arguments": {}})
        assert r.status_code == 403
