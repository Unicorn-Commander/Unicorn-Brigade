"""Per-org discovery and execution, using real routes/loops and an in-memory DB stand-in."""

from __future__ import annotations

import json
import sys
from contextlib import asynccontextmanager
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.api.a2a_routes as a2a_routes
import app.api.agent_routes as agent_routes
import app.api.mcp_routes as mcp_routes
import app.api.openai_compat_routes as openai_routes
import app.api.tool_routes as tool_routes
import app.auth.tool_scope as scoping
import app.db.migrations as migrations
import app.llm.sibling_app_tools as siblings
import app.llm.tool_resolver as resolver
from app.auth.caller_authz import build_tool_guard
from app.auth.middleware import (
    AuthUser,
    get_current_user_optional,
    require_admin,
    require_api_key,
    require_operator,
)
from app.auth.roles import UserRole
from app.db.database import get_session
from app.db.models import ToolCatalog
from app.llm.mlx_provider import MLXLLMClient
from app.llm.ops_center_client import OpsCenterLLMClient, ToolDefinition
from app.protocols.mcp import MCPServer

MAJIKS = "00000000-0000-0000-0000-000000000001"
OTHER = "00000000-0000-0000-0000-000000000002"
DEFAULT = "00000000-0000-0000-0000-000000000003"
PRIVATE = "majiks.query_majiks_catalog"
ALIAS = "legacy_majiks_catalog"
GLOBAL = "calculator"


class _Bind:
    pass


class Session:
    def __init__(self, scopes=None, *, bind=None):
        self.scopes = {PRIVATE: None, GLOBAL: None} if scopes is None else scopes
        self.orgs = [(MAJIKS, "majiks"), (OTHER, "other"), (DEFAULT, "early-access")]
        self.bind = bind or _Bind()
        self.queries = []
        self.fail_catalog = False
        self.fail_directory = False

    def get_bind(self):
        return self.bind

    async def execute(self, query, *args):
        sql = str(query)
        self.queries.append(sql)
        if "FROM organizations" in sql:
            if self.fail_directory:
                raise RuntimeError("offline")
            return self.orgs
        if "FROM tool_catalog" in sql:
            if self.fail_catalog:
                raise RuntimeError("offline")
            if "permission_level FROM" in sql:
                return [(name, 1) for name in self.scopes]
            if "display_name" in sql:
                return [(name, None, "free", 1, "test", False, scope) for name, scope in self.scopes.items()]
            return list(self.scopes.items())
        raise AssertionError(f"Unexpected query: {sql}")


def user(org_id=MAJIKS):
    return AuthUser(id="admin", role=UserRole.ADMIN, org_id=org_id)


@pytest.fixture(autouse=True)
def isolated_cache(monkeypatch):
    scoping.clear_org_scope_cache()
    monkeypatch.setenv("BRIGADE_TOOL_PERMISSION_ENFORCEMENT", "enforce")
    monkeypatch.setenv("BRIGADE_TOOL_CATALOG_FAIL_CLOSED", "true")
    monkeypatch.setattr(siblings, "SIBLING_APPS", ())
    yield
    scoping.clear_org_scope_cache()


@pytest.fixture
def sibling_app(monkeypatch):
    app = siblings.SiblingAppConfig(
        name="majiks", namespace="majiks", transport="mcp", url_env="TEST_MAJIKS_URL",
        default_url="", token_env=None, token_required=False, timeout=1,
        tools=frozenset([PRIVATE]), aliases={ALIAS: PRIVATE}, orgs=("majiks",),
    )
    monkeypatch.setattr(siblings, "SIBLING_APPS", (app,))
    monkeypatch.setattr(siblings, "_ALIASES", app.aliases)
    monkeypatch.setattr(siblings, "_CANONICAL_TO_APP", {PRIVATE: app})
    monkeypatch.setenv("SIBLING_APP_TOOLS_ENABLED", "1")
    return app


@pytest.fixture
def handlers(monkeypatch, sibling_app):
    calls, discoveries = [], []

    async def global_handler(**kwargs):
        calls.append(GLOBAL)
        return {"ok": True}

    async def invoke(app, spec, arguments):
        calls.append(spec.canonical_name)
        return {"ok": True}

    def schema(app):
        discoveries.append(app.name)
        return siblings._SchemaCacheEntry(
            fingerprint=("test", False, True), expires_at=1e12,
            specs={PRIVATE: siblings._SiblingToolSpec(PRIVATE, "Catalog", ())},
        )

    monkeypatch.setattr(siblings, "_load_schema", schema)
    monkeypatch.setattr(siblings, "_invoke", invoke)
    monkeypatch.setitem(resolver.TOOL_REGISTRY, GLOBAL, ToolDefinition(
        name=GLOBAL, description="Global tool", handler=global_handler,
    ))
    return calls, discoveries


@pytest.mark.parametrize("org_id, allowed", [
    (MAJIKS, True), (OTHER, False), (DEFAULT, False), (None, False),
])
@pytest.mark.parametrize("backend", ["ops", "mlx"])
async def test_model_listing_and_forced_execution_use_same_scope(monkeypatch, handlers, org_id, allowed, backend):
    calls, discoveries = handlers
    guard = await build_tool_guard(Session(), {"orgId": OTHER}, user(org_id), None, True)
    agent = {"tools": [ALIAS, GLOBAL]}
    tools = resolver.get_tools_for_agent(agent, org_scope=guard.org_scope)
    assert [t.name for t in tools] == ([PRIVATE, GLOBAL] if allowed else [GLOBAL])
    assert discoveries == (["majiks"] if allowed else [])
    assert agent["tools"] == [ALIAS, GLOBAL]

    # Supply both handlers directly too: the LLM loop must filter definitions,
    # and refuse a forced/stale tool call even though the model was not shown it.
    all_tools = resolver.get_tools_for_agent(agent)
    if backend == "ops":
        client = OpsCenterLLMClient(ops_center_url="http://test.invalid", service_key="test")
    else:
        client = MLXLLMClient(model_name="test")
    responses = [
        {"choices": [{"message": {"tool_calls": [
            {"id": name, "type": "function", "function": {"name": name, "arguments": "{}"}}
            for name in (PRIVATE, GLOBAL)
        ]}}]},
        {"choices": [{"message": {"content": "done"}}]},
    ]
    shown = []

    async def completion(**kwargs):
        shown.append([t.name for t in kwargs["tools"]])
        return responses.pop(0)

    monkeypatch.setattr(client, "chat_completion_with_tools", completion)
    results = []
    response = await client.execute_tool_loop(
        messages=[{"role": "user", "content": "go"}], tools=all_tools,
        tool_guard=guard, on_tool_result=results.append,
    )
    assert client.get_response_content(response) == "done"
    assert shown == [[t.name for t in tools]] * 2
    assert calls == ([PRIVATE, GLOBAL] if allowed else [GLOBAL])
    assert results[0].error == (None if allowed else f"Tool {PRIVATE} is not available in this organization.")
    assert results[1].error is None


@pytest.mark.parametrize("entry", [MAJIKS, "majiks"])
@pytest.mark.parametrize("bound_org", [MAJIKS, "majiks"])
async def test_catalog_id_and_slug_resolve_both_directions(entry, bound_org):
    scope = await scoping.load_tool_org_scope(Session({PRIVATE: [entry], GLOBAL: None}), bound_org)
    assert scope.allows(PRIVATE)
    assert scope.allows(GLOBAL)
    assert not replace(scope, org_id=OTHER).allows(PRIVATE)


@pytest.mark.parametrize("mode", ["off", "log", "enforce"])
async def test_admin_privilege_and_enforcement_modes_do_not_bypass_orgs(monkeypatch, sibling_app, mode):
    monkeypatch.setenv("BRIGADE_TOOL_PERMISSION_ENFORCEMENT", mode)
    guard = await build_tool_guard(Session(), {"orgId": MAJIKS}, user(DEFAULT), None, True)
    assert guard.caller_level == 5
    assert guard.check(PRIVATE) == f"Tool {PRIVATE} is not available in this organization."
    assert guard.check(GLOBAL) is None


async def test_bound_org_wins_over_agent_and_context_org(sibling_app):
    from app.orchestration.event_bus import current_org_id_var

    token = current_org_id_var.set(MAJIKS)
    try:
        guard = await build_tool_guard(Session(), {"orgId": MAJIKS}, user(OTHER), None, True)
    finally:
        current_org_id_var.reset(token)
    assert guard.org_scope.org_id == OTHER
    assert guard.check(PRIVATE)


async def test_default_org_can_be_explicitly_allowlisted(sibling_app, monkeypatch):
    monkeypatch.setattr(siblings, "SIBLING_APPS", (replace(sibling_app, orgs=("early-access",)),))
    scope = await scoping.load_tool_org_scope(Session(), DEFAULT)
    assert scope.allows(PRIVATE)


@pytest.mark.parametrize("catalog_name", [PRIVATE, ALIAS])
async def test_config_and_catalog_intersect_for_aliases(sibling_app, catalog_name):
    session = Session({catalog_name: [OTHER]})
    for org_id in (MAJIKS, OTHER):
        scope = await scoping.load_tool_org_scope(session, org_id)
        assert not scope.allows(PRIVATE)
        assert not scope.allows(ALIAS)
    session.scopes[catalog_name] = [MAJIKS, OTHER]
    scope = await scoping.load_tool_org_scope(session, MAJIKS)
    assert scope.allows(PRIVATE) and scope.allows(ALIAS)


async def test_unknown_entries_warn_and_never_make_a_scope_global(caplog):
    missing_id = "00000000-0000-0000-0000-000000000099"
    session = Session({PRIVATE: ["typo", missing_id, "majiks"]})
    scope = await scoping.load_tool_org_scope(session, MAJIKS)
    assert scope.allows(PRIVATE)
    assert "Unknown organization 'typo'" in caplog.text
    assert missing_id in caplog.text
    caplog.clear()
    await scoping.load_tool_org_scope(session, MAJIKS)
    assert not caplog.records  # warnings deduplicated within directory TTL
    session.scopes[PRIVATE] = ["typo", missing_id]
    scope = await scoping.load_tool_org_scope(session, MAJIKS)
    assert not scope.allows(PRIVATE)


@pytest.mark.parametrize("orgs", [[], "majiks", [None, 5], {}])
async def test_empty_or_malformed_scope_fails_closed(orgs):
    scope = await scoping.load_tool_org_scope(Session({PRIVATE: orgs, GLOBAL: None}), MAJIKS)
    assert not scope.allows(PRIVATE)
    assert scope.allows(GLOBAL)


async def test_only_directory_is_cached_and_it_expires(monkeypatch):
    now = [100.0]
    monkeypatch.setattr(scoping, "time", SimpleNamespace(monotonic=lambda: now[0]))
    session = Session({PRIVATE: ["majiks"]})
    assert (await scoping.load_tool_org_scope(session, MAJIKS)).allows(PRIVATE)
    other_session = Session({PRIVATE: ["majiks"]}, bind=session.bind)
    assert not (await scoping.load_tool_org_scope(other_session, OTHER)).allows(PRIVATE)
    assert not any("FROM organizations" in q for q in other_session.queries)
    session.scopes[PRIVATE] = ["other"]
    assert not (await scoping.load_tool_org_scope(session, MAJIKS)).allows(PRIVATE)
    assert (await scoping.load_tool_org_scope(session, OTHER)).allows(PRIVATE)
    assert sum("FROM organizations" in q for q in session.queries) == 1
    now[0] += scoping.ORG_CACHE_SECONDS + 1
    session.orgs = [(MAJIKS, "other")]
    assert (await scoping.load_tool_org_scope(session, MAJIKS)).allows(PRIVATE)
    assert sum("FROM organizations" in q for q in session.queries) == 2
    independent_db = Session({PRIVATE: ["other"]})
    assert not (await scoping.load_tool_org_scope(independent_db, MAJIKS)).allows(PRIVATE)


async def test_directory_failure_denies_scoped_tools_but_keeps_null_global():
    session = Session({PRIVATE: [MAJIKS], GLOBAL: None})
    session.fail_directory = True
    scope = await scoping.load_tool_org_scope(session, MAJIKS)
    assert not scope.allows(PRIVATE)
    assert scope.allows(GLOBAL)
    session.fail_directory = False
    assert (await scoping.load_tool_org_scope(session, MAJIKS)).allows(PRIVATE)


async def test_catalog_failure_cannot_grant_access():
    session = Session()
    session.fail_catalog = True
    scope = await scoping.load_tool_org_scope(session, MAJIKS)
    assert not scope.allows(PRIVATE)
    assert not scope.allows(GLOBAL)


@pytest.mark.parametrize("org_id, mixed", [(MAJIKS, False), (OTHER, False), (OTHER, True)])
async def test_openai_dual_loop_filters_and_refuses_without_forwarding_to_client(monkeypatch, handlers, org_id, mixed):
    calls, discoveries = handlers
    posted = []
    tool_calls = [{"id": "private", "type": "function", "function": {
        "name": PRIVATE, "arguments": "{}",
    }}]
    if mixed:
        tool_calls.append({"id": "client", "type": "function", "function": {
            "name": "client_tool", "arguments": "{}",
        }})
    replies = [
        {"choices": [{"message": {"tool_calls": tool_calls}}]},
        {"choices": [{"message": {"content": "done"}}]},
    ]

    async def post(endpoint, *, json, headers):
        posted.append(deepcopy(json))
        reply = replies.pop(0)
        return SimpleNamespace(json=lambda: reply, raise_for_status=lambda: None)

    async def attrs(*args, **kwargs):
        return {}, None

    async def noop(*args, **kwargs):
        pass

    monkeypatch.setitem(sys.modules, "app.main", SimpleNamespace(memory_manager=None))
    monkeypatch.setattr(agent_routes, "_fetch_user_attrs", attrs)
    monkeypatch.setattr(agent_routes, "_enforce_billing_or_402", lambda *args: None)
    monkeypatch.setattr(agent_routes, "_enforce_org_cap_or_402", noop)
    monkeypatch.setattr(agent_routes, "_meter_chat_to_lago", noop)
    monkeypatch.setattr(agent_routes, "llm_client", SimpleNamespace(
        _resolve_local_model=lambda model: ("http://model.invalid", "test", "local"),
        _endpoint_and_headers=lambda *args, **kwargs: ("http://model.invalid/chat", {}),
        client=SimpleNamespace(post=post),
    ))
    request = openai_routes.OpenAIChatRequest(
        model="test", messages=[{"role": "user", "content": "go"}],
        tools=[{"type": "function", "function": {"name": name}} for name in ("client_tool", PRIVATE)],
    )
    response = await openai_routes._dual_layer_chat(
        request, Session(), user(org_id), {"id": "test", "name": "test", "tools": [PRIVATE, GLOBAL]},
    )
    assert response["choices"][0]["message"]["content"] == "done"
    listed = [tool["function"]["name"] for tool in posted[0]["tools"]]
    assert (PRIVATE in listed) == (org_id == MAJIKS)
    assert GLOBAL in listed and "client_tool" in listed
    assert calls == ([PRIVATE] if org_id == MAJIKS else [])
    results = {m["name"]: json.loads(m["content"]) for m in posted[1]["messages"] if m["role"] == "tool"}
    if org_id == OTHER:
        assert discoveries == []
        assert results[PRIVATE]["error"] == f"Tool {PRIVATE} is not available in this organization."
    if mixed:
        assert "Retry it separately" in results["client_tool"]["error"]


@pytest.mark.parametrize("org_id, allowed", [(MAJIKS, True), (OTHER, False)])
async def test_delegated_call_uses_forwarded_caller_org(monkeypatch, sibling_app, org_id, allowed):
    import app.llm.delegation_tools as delegation

    guards = []

    class Client:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, *, headers, json):
            assert headers["Authorization"] == "Bearer fixture-caller"
            assert "X-API-Key" not in headers
            # Credential resolution binds the replayed org on the downstream
            # request. The target agent belongs to Majiks in both cases.
            _, _, guard = await agent_routes._authorize_caller(
                Session(), user(headers["X-Org-Id"]), {"id": "target", "orgId": MAJIKS}, None,
            )
            guards.append(guard)
            return SimpleNamespace(status_code=200, json=lambda: {"content": "done"})

    monkeypatch.setattr(delegation.httpx, "AsyncClient", Client)
    token = delegation._CALLER_AUTH.set({"Authorization": "Bearer fixture-caller", "X-Org-Id": org_id})
    try:
        result = await delegation.delegate_to_agent_handler(agent_id="target", task="query catalog")
    finally:
        delegation._CALLER_AUTH.reset(token)
    assert result["success"]
    assert (guards[0].check(PRIVATE) is None) == allowed


@pytest.mark.parametrize("org_id, expected", [(MAJIKS, [PRIVATE, GLOBAL]), (OTHER, [GLOBAL])])
def test_http_tool_lists_share_the_bound_org(monkeypatch, handlers, org_id, expected):
    session = Session()
    current_user = user(org_id)
    app = FastAPI()
    app.include_router(tool_routes.router)
    app.include_router(agent_routes.router)
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[require_api_key] = lambda: current_user
    tools = resolver.get_tools_for_agent({"tools": [PRIVATE, GLOBAL]})
    monkeypatch.setattr(tool_routes, "get_default_tools", lambda: tools)
    monkeypatch.setattr(tool_routes, "get_safe_tools", lambda: tools)
    stored_agent = {"id": "test", "tools": [PRIVATE, GLOBAL], "agentTools": [
        {"toolId": name} for name in (PRIVATE, GLOBAL)
    ]}

    class Repository:
        def __init__(self, session):
            pass

        async def get(self, agent_id):
            return deepcopy(stored_agent)

        async def list_all(self):
            return [deepcopy(stored_agent)]

    monkeypatch.setattr(agent_routes, "AgentRepository", Repository)
    client = TestClient(app)
    for path in ("/tools", "/tools/available", "/tool-catalog"):
        response = client.get(path)
        assert response.status_code == 200, response.text
        body = response.json()
        names = [t.get("id", t["name"]) for t in body["tools"]]
        assert (PRIVATE in names) == (PRIVATE in expected)
        assert GLOBAL in names
        if "count" in body:
            assert body["count"] == len(names)
    assert client.get("/agents/test/tools").json() == {
        "toolNames": expected, "tools": [{"toolId": name} for name in expected],
    }
    assert client.get("/agents/test").json()["tools"] == expected
    roster = client.get("/agents").json()["agents"][0]
    assert roster["tools"] == expected
    assert [t["name"] for t in roster["toolDetails"]] == expected
    assert stored_agent["tools"] == [PRIVATE, GLOBAL]


@pytest.mark.parametrize("org_id, allowed", [(MAJIKS, True), (OTHER, False)])
def test_mcp_list_formats_and_calls_cannot_bypass_catalog_scope(monkeypatch, org_id, allowed):
    server = MCPServer()
    calls = []

    async def handler():
        calls.append(PRIVATE)
        return "ok"

    async def no_meter(**kwargs):
        pass

    for name in (PRIVATE, GLOBAL):
        server.register_tool(name, "test", [], handler)
    monkeypatch.setattr(mcp_routes, "mcp_server", server)
    monkeypatch.setattr(mcp_routes, "_tools_registered", True)
    monkeypatch.setattr(mcp_routes, "meter_usage", no_meter)
    app = FastAPI()
    app.include_router(mcp_routes.router)
    app.dependency_overrides[get_session] = lambda: Session({PRIVATE: ["majiks"], GLOBAL: None})
    app.dependency_overrides[require_api_key] = lambda: user(org_id)
    app.dependency_overrides[require_admin] = lambda: user(org_id)
    client = TestClient(app)
    for path in ("/mcp/tools/list", "/mcp/tools/openai", "/mcp/tools/anthropic"):
        response = client.get(path)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["count"] == (2 if allowed else 1)
        assert (PRIVATE in str(body["tools"])) == allowed
    assert client.get("/mcp/info").json()["toolCount"] == (2 if allowed else 1)
    assert (PRIVATE in client.get("/mcp/config").json()["availableTools"]) == allowed
    listed = client.post("/mcp/request", json={"method": "tools/list"}).json()
    assert (PRIVATE in str(listed)) == allowed
    direct = client.post("/mcp/tools/call", json={"name": PRIVATE})
    assert direct.status_code == 200
    assert direct.json()["success"] is allowed
    raw = client.post("/mcp/request", json={"method": "tools/call", "params": {"name": PRIVATE}})
    assert raw.status_code == 200
    if not allowed:
        assert raw.json()["isError"] is True
        assert "not available in this organization" in raw.text
    assert calls == ([PRIVATE, PRIVATE] if allowed else [])


@pytest.mark.parametrize("org_id, allowed", [(MAJIKS, True), (OTHER, False), (None, False)])
def test_a2a_cards_and_invocation_share_org_scope(monkeypatch, handlers, org_id, allowed):
    agent = {"id": "test", "name": "test", "status": "active", "tools": [PRIVATE, GLOBAL]}
    loop_calls = []

    class Repository:
        def __init__(self, session):
            pass

        async def list_all(self):
            return [deepcopy(agent)]

        async def get(self, agent_id):
            return deepcopy(agent)

    async def noop(**kwargs):
        pass

    async def loop(**kwargs):
        loop_calls.append(kwargs)
        return {"choices": [{"message": {"content": "done"}}]}

    monkeypatch.setattr(a2a_routes, "AgentRepository", Repository)
    monkeypatch.setattr(a2a_routes, "emit_agent_invocation", noop)
    monkeypatch.setattr(a2a_routes, "meter_usage", noop)
    monkeypatch.setattr(a2a_routes, "llm_client", SimpleNamespace(
        execute_tool_loop=loop,
        get_response_content=lambda response: response["choices"][0]["message"]["content"],
    ))
    app = FastAPI()
    app.include_router(a2a_routes.router)
    app.dependency_overrides[get_session] = lambda: Session()
    app.dependency_overrides[get_current_user_optional] = lambda: user(org_id) if org_id else None
    app.dependency_overrides[require_operator] = lambda: user(org_id)
    client = TestClient(app)
    for path in ("/a2a/agents", "/a2a/agents/test/card"):
        response = client.get(path)
        assert response.status_code == 200, response.text
        assert (f"tool:{PRIVATE}" in response.text) == allowed
        assert f"tool:{GLOBAL}" in response.text
    discovery = client.post("/a2a/discover", json={"capability": PRIVATE})
    assert discovery.status_code == 200, discovery.text
    assert discovery.json()["count"] == int(allowed)
    result = client.post("/a2a/agents/test/invoke", json={"task": "go"})
    assert result.status_code == 200, result.text
    assert result.json()["result"] == "done"
    assert [t.name for t in loop_calls[0]["tools"]] == ([PRIVATE, GLOBAL] if allowed else [GLOBAL])
    assert (loop_calls[0]["tool_guard"].check(PRIVATE) is None) == allowed


def test_migration_is_additive_idempotent_and_null_is_global():
    entries = [m for m in migrations.MIGRATIONS if m[0] == "20261025_01_tool_org_scope"]
    assert len(entries) == 1
    assert entries[0][2] == "ALTER TABLE tool_catalog ADD COLUMN IF NOT EXISTS orgs json"
    column = ToolCatalog.__table__.c.orgs
    assert column.nullable and column.default is None and column.server_default is None
    assert ToolCatalog(name=GLOBAL).to_dict()["orgs"] is None


async def test_migration_runner_records_once_and_skips_second_run(monkeypatch):
    entry = next(m for m in migrations.MIGRATIONS if m[0] == "20261025_01_tool_org_scope")
    monkeypatch.setattr(migrations, "MIGRATIONS", [entry])
    applied, statements = set(), []

    class Engine:
        @asynccontextmanager
        async def begin(self):
            yield self

        async def execute(self, query, args=None):
            sql = str(query)
            statements.append(sql)
            if sql.startswith("SELECT version"):
                return [(version,) for version in applied]
            if sql.startswith("INSERT INTO schema_migrations"):
                applied.add(args["v"])
            return []

    engine = Engine()
    await migrations.run_additive_migrations(engine)
    await migrations.run_additive_migrations(engine)
    assert statements.count(entry[2]) == 1
    assert applied == {entry[0]}
