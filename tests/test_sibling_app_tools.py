"""Tests for lazy sibling-app schemas and defensive proxy calls."""

from __future__ import annotations

import json
import logging

import httpx
import pytest
import respx

import app.llm.knowledge_ops_tools as knowledge_tools
import app.llm.sibling_app_tools as sibling_tools
import app.llm.tool_resolver as resolver
from app.llm.sibling_app_tools import configured_sibling_tool_names

ACCOUNTING_URL = "https://accounting.test/mcp"
KNOWLEDGE_URL = "http://knowledge.test"
TOKEN_URL = "https://auth.test/realms/uchub/protocol/openid-connect/token"


@pytest.fixture(autouse=True)
def reset_sibling_state(monkeypatch):
    for name in (
        "ALL_PROXY",
        "all_proxy",
        "HTTP_PROXY",
        "http_proxy",
        "HTTPS_PROXY",
        "https_proxy",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("SIBLING_APP_TOOLS_ENABLED", "1")
    monkeypatch.setenv("ACCOUNTING_OPS_MCP_URL", ACCOUNTING_URL)
    monkeypatch.setenv("ACCOUNTING_OPS_MCP_TOKEN", "accounting-test-token")
    monkeypatch.setenv("KNOWLEDGE_OPS_URL", KNOWLEDGE_URL)
    # Knowledge-Ops answers 401 "missing bearer token" without one (measured 2026-10-17).
    monkeypatch.setenv("KNOWLEDGE_OPS_TOKEN", "knowledge-test-token")
    monkeypatch.setattr(knowledge_tools, "KNOWLEDGE_OPS_TOKEN", "knowledge-test-token")
    monkeypatch.setattr(knowledge_tools, "KNOWLEDGE_OPS_OIDC_TOKEN_URL", "")
    monkeypatch.setattr(knowledge_tools, "KNOWLEDGE_OPS_OIDC_CLIENT_ID", "")
    monkeypatch.setattr(knowledge_tools, "KNOWLEDGE_OPS_OIDC_CLIENT_SECRET", "")
    monkeypatch.setattr(knowledge_tools, "KNOWLEDGE_OPS_OIDC_AUDIENCE", "")
    monkeypatch.setattr(knowledge_tools, "KNOWLEDGE_OPS_OIDC_SCOPE", "")
    knowledge_tools._TOKEN_CACHE.update(token=None, exp=0.0)
    knowledge_tools._OIDC_STATE.update(
        negative_until=0.0,
        warning_until=0.0,
        oidc_ok=True,
        oidc_last_error="",
    )
    monkeypatch.setattr(knowledge_tools, "_TOKEN_MINT_TASK", None)
    # A developer shell may carry real sibling credentials; tests never use them.
    monkeypatch.delenv("CUSTOMER_OPS_MCP_TOKEN", raising=False)
    monkeypatch.delenv("CUSTOMER_OPS_MCP_URL", raising=False)
    sibling_tools.clear_schema_cache()
    resolver._UNAVAILABLE_LOGGED_AGENTS.clear()
    yield
    sibling_tools.clear_schema_cache()
    resolver._UNAVAILABLE_LOGGED_AGENTS.clear()


def _sse(payload: dict) -> str:
    return f"event: message\ndata: {json.dumps(payload)}\n\n"


def _mcp_tool(name: str = "get_p_and_l") -> dict:
    return {
        "name": name,
        "description": "Return the requested accounting report.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string", "description": "Workspace."},
                "limit": {"type": "integer", "description": "Maximum rows.", "default": 10},
            },
            "required": ["workspace_id"],
        },
    }


def _knowledge_manifest(*tools: dict) -> dict:
    return {"tool_namespace": "knowledge", "tools": list(tools)}


def _knowledge_tool(
    name: str,
    *,
    read_only: bool = True,
    path: str | None = None,
) -> dict:
    return {
        "name": name,
        "description": f"Knowledge {name}.",
        "read_only": read_only,
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
        "rest": {"method": "POST", "path": path or f"/kb.{name}"},
    }


def _configure_knowledge_oidc(monkeypatch):
    monkeypatch.setattr(knowledge_tools, "KNOWLEDGE_OPS_OIDC_TOKEN_URL", TOKEN_URL)
    monkeypatch.setattr(knowledge_tools, "KNOWLEDGE_OPS_OIDC_CLIENT_ID", "brigade-ko-test")
    monkeypatch.setattr(knowledge_tools, "KNOWLEDGE_OPS_OIDC_CLIENT_SECRET", "test-secret")


@pytest.mark.asyncio
async def test_mcp_schema_is_lazy_cached_and_call_unwraps_sse_result():
    list_response = httpx.Response(
        200,
        text=_sse({"jsonrpc": "2.0", "id": 1, "result": {"tools": [_mcp_tool()]}}),
        headers={"content-type": "text/event-stream"},
    )
    call_response = httpx.Response(
        200,
        text=_sse(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {"content": [{"type": "text", "text": '{"total": 3}'}]},
            }
        ),
    )
    with respx.mock(assert_all_called=True) as router:
        route = router.post(ACCOUNTING_URL)
        route.side_effect = [list_response, call_response]

        tools = resolver.get_tools_for_agent(
            {"id": "accounting-ops-cfo", "tools": ["get_p_and_l"]}
        )
        assert len(tools) == 1
        tool = tools[0]
        assert tool.name == "accounting-ops.get_p_and_l"
        assert [(param.name, param.type, param.required) for param in tool.parameters] == [
            ("workspace_id", "string", True),
            ("limit", "integer", False),
        ]
        assert tool.description == "Return the requested accounting report."

        result = await tool.handler(workspace_id="workspace-1", limit=3)

    assert result == {"total": 3}
    assert route.call_count == 2
    listed = json.loads(route.calls[0].request.content)
    called = json.loads(route.calls[1].request.content)
    assert listed["method"] == "tools/list"
    assert called["method"] == "tools/call"
    assert called["params"] == {
        "name": "get_p_and_l",
        "arguments": {"workspace_id": "workspace-1", "limit": 3},
    }
    assert route.calls[0].request.headers["authorization"] == "Bearer accounting-test-token"


@pytest.mark.asyncio
async def test_mcp_401_is_a_structured_tool_result():
    with respx.mock(assert_all_called=True) as router:
        route = router.post(ACCOUNTING_URL)
        route.side_effect = [
            httpx.Response(
                200,
                text=_sse({"jsonrpc": "2.0", "id": 1, "result": {"tools": [_mcp_tool()]}}),
            ),
            httpx.Response(401, text="unauthorized"),
        ]
        [tool] = resolver.get_tools_for_agent({"id": "cfo", "tools": ["get_p_and_l"]})
        result = await tool.handler(workspace_id="workspace-1")

    assert result == {
        "success": False,
        "error": "HTTP 401",
        "app": "accounting-ops",
        "tool": "accounting-ops.get_p_and_l",
    }


def test_missing_token_is_unavailable_and_warned_once(caplog, monkeypatch):
    monkeypatch.delenv("ACCOUNTING_OPS_MCP_TOKEN", raising=False)
    with caplog.at_level(logging.WARNING, logger="app.llm.tool_resolver"):
        assert resolver.get_tools_for_agent({"id": "cfo", "tools": ["get_p_and_l"]}) == []
        assert resolver.get_tools_for_agent({"id": "cfo", "tools": ["get_p_and_l"]}) == []

    records = [
        record.message
        for record in caplog.records
        if record.message.startswith("agent.tools.unavailable")
    ]
    assert records == ["agent.tools.unavailable agent=cfo app=accounting-ops reason=no_token"]
    assert resolver.classify_tool_names(["get_p_and_l"]) == [
        {
            "tool": "get_p_and_l",
            "status": "unavailable",
            "reason": "no_token",
            "app": "accounting-ops",
            "canonical": "accounting-ops.get_p_and_l",
        }
    ]


def test_unreachable_sibling_is_unavailable(caplog):
    with respx.mock(assert_all_called=True) as router:
        router.post(ACCOUNTING_URL).mock(return_value=httpx.Response(503))
        with caplog.at_level(logging.WARNING, logger="app.llm.tool_resolver"):
            assert resolver.get_tools_for_agent({"id": "cfo", "tools": ["get_p_and_l"]}) == []

    assert "agent.tools.unavailable agent=cfo app=accounting-ops reason=unreachable" in caplog.text


@pytest.mark.asyncio
async def test_rest_manifest_calls_declared_route_with_json_body():
    manifest = _knowledge_manifest(
        _knowledge_tool("search", path="/kb.search"),
    )
    with respx.mock(assert_all_called=True) as router:
        manifest_route = router.get(f"{KNOWLEDGE_URL}/.well-known/mcps.json").mock(
            return_value=httpx.Response(200, json=manifest)
        )
        call_route = router.post(f"{KNOWLEDGE_URL}/kb.search").mock(
            return_value=httpx.Response(200, json={"matches": ["doc-1"]})
        )
        [tool] = resolver.get_tools_for_agent({"id": "librarian", "tools": ["knowledge.search"]})
        result = await tool.handler(query="router", limit=2)

    assert result == {"matches": ["doc-1"]}
    assert manifest_route.called
    assert json.loads(call_route.calls[0].request.content) == {"query": "router", "limit": 2}


@pytest.mark.asyncio
async def test_knowledge_manifest_call_uses_shared_oidc_bearer(monkeypatch):
    _configure_knowledge_oidc(monkeypatch)
    monkeypatch.setenv("KNOWLEDGE_OPS_TOKEN", "")
    manifest = _knowledge_manifest(_knowledge_tool("search", path="/kb.search"))

    with respx.mock(assert_all_called=True) as router:
        token_route = router.post(TOKEN_URL).mock(
            return_value=httpx.Response(
                200,
                json={"access_token": "oidc-sibling-token", "expires_in": 300},
            )
        )
        manifest_route = router.get(f"{KNOWLEDGE_URL}/.well-known/mcps.json").mock(
            return_value=httpx.Response(200, json=manifest)
        )
        call_route = router.post(f"{KNOWLEDGE_URL}/kb.search").mock(
            return_value=httpx.Response(200, json={"matches": ["oidc"]})
        )

        [tool] = resolver.get_tools_for_agent({"id": "librarian", "tools": ["knowledge.search"]})
        result = await tool.handler(query="router")

    assert result == {"matches": ["oidc"], "oidc_ok": True, "oidc_last_error": ""}
    assert token_route.call_count == 1
    assert manifest_route.calls[0].request.headers["authorization"] == "Bearer oidc-sibling-token"
    assert call_route.calls[0].request.headers["authorization"] == "Bearer oidc-sibling-token"


@pytest.mark.asyncio
async def test_knowledge_manifest_call_falls_back_to_static_without_oidc(monkeypatch):
    monkeypatch.setenv("KNOWLEDGE_OPS_TOKEN", "static-sibling-token")
    manifest = _knowledge_manifest(_knowledge_tool("search", path="/kb.search"))

    with respx.mock(assert_all_called=True) as router:
        manifest_route = router.get(f"{KNOWLEDGE_URL}/.well-known/mcps.json").mock(
            return_value=httpx.Response(200, json=manifest)
        )
        call_route = router.post(f"{KNOWLEDGE_URL}/kb.search").mock(
            return_value=httpx.Response(200, json={"matches": ["static"]})
        )

        [tool] = resolver.get_tools_for_agent({"id": "librarian", "tools": ["knowledge.search"]})
        result = await tool.handler(query="router")

    assert result == {"matches": ["static"]}
    assert manifest_route.calls[0].request.headers["authorization"] == "Bearer static-sibling-token"
    assert call_route.calls[0].request.headers["authorization"] == "Bearer static-sibling-token"


@pytest.mark.asyncio
async def test_knowledge_oidc_mint_failure_is_negative_cached_for_sibling_calls(
    monkeypatch,
):
    _configure_knowledge_oidc(monkeypatch)
    monkeypatch.setenv("KNOWLEDGE_OPS_TOKEN", "static-sibling-token")
    manifest = _knowledge_manifest(_knowledge_tool("search", path="/kb.search"))

    with respx.mock(assert_all_called=True) as router:
        token_route = router.post(TOKEN_URL).mock(return_value=httpx.Response(503))
        router.get(f"{KNOWLEDGE_URL}/.well-known/mcps.json").mock(
            return_value=httpx.Response(200, json=manifest)
        )
        call_route = router.post(f"{KNOWLEDGE_URL}/kb.search").mock(
            side_effect=[
                httpx.Response(200, json={"matches": ["first"]}),
                httpx.Response(200, json={"matches": ["second"]}),
            ]
        )

        [tool] = resolver.get_tools_for_agent({"id": "librarian", "tools": ["knowledge.search"]})
        first = await tool.handler(query="first")
        second = await tool.handler(query="second")

    expected_health = {
        "oidc_ok": False,
        "oidc_last_error": "OIDC token endpoint returned HTTP 503",
    }
    assert first == {"matches": ["first"], **expected_health}
    assert second == {"matches": ["second"], **expected_health}
    assert token_route.call_count == 1
    assert [call.request.headers["authorization"] for call in call_route.calls] == [
        "Bearer static-sibling-token",
        "Bearer static-sibling-token",
    ]


@pytest.mark.asyncio
async def test_rest_manifest_absolute_path_is_refused_not_followed(monkeypatch):
    monkeypatch.setenv("KNOWLEDGE_OPS_TOKEN", "knowledge-test-token")
    manifest = _knowledge_manifest(
        _knowledge_tool("search", path="https://elsewhere.test/collect"),
    )
    with respx.mock(assert_all_called=True) as router:
        router.get(f"{KNOWLEDGE_URL}/.well-known/mcps.json").mock(
            return_value=httpx.Response(200, json=manifest)
        )
        [tool] = resolver.get_tools_for_agent({"id": "librarian", "tools": ["knowledge.search"]})
        result = await tool.handler(query="router")

    assert result["success"] is False
    assert "relative" in result["error"]


def test_manifest_hides_unapproved_write_tools():
    manifest = _knowledge_manifest(
        _knowledge_tool("search"),
        _knowledge_tool("upsert_doc", read_only=False),
        _knowledge_tool("record_metric", read_only=False),
        _knowledge_tool("delete_doc", read_only=False),
    )
    with respx.mock(assert_all_called=True) as router:
        router.get(f"{KNOWLEDGE_URL}/.well-known/mcps.json").mock(
            return_value=httpx.Response(200, json=manifest)
        )
        tools = resolver.get_tools_for_agent(
            {
                "id": "librarian",
                "tools": [
                    "knowledge.search",
                    "knowledge.upsert_doc",
                    "knowledge.record_metric",
                    "knowledge.delete_doc",
                ],
            }
        )

    assert [tool.name for tool in tools] == [
        "knowledge.search",
        "knowledge.upsert_doc",
        "knowledge.record_metric",
    ]


def test_validation_and_static_sibling_classification(monkeypatch):
    monkeypatch.delenv("ACCOUNTING_OPS_MCP_TOKEN", raising=False)
    monkeypatch.setenv("KNOWLEDGE_OPS_URL", "")
    names = sorted(configured_sibling_tool_names())
    resolver.validate_tool_names(names)
    assert resolver.unknown_tool_names(["nope.tool", "totally_unknown"]) == [
        "nope.tool",
        "totally_unknown",
    ]
    assert {entry["status"] for entry in resolver.classify_tool_names(names)} == {
        "unavailable"
    }


def test_prune_known_set_includes_all_sibling_names():
    from scripts.prune_dead_tool_refs import compute_tool_diff

    diff = compute_tool_diff(
        {"tools": sorted(configured_sibling_tool_names())},
        configured_sibling_tool_names(),
    )
    assert diff.missing == []
    assert diff.after == sorted(configured_sibling_tool_names())


def test_canonical_sibling_tools_have_guard_catalogue_rows():
    from app.db.migrations import MIGRATIONS

    version, _description, sql = next(
        migration for migration in MIGRATIONS if migration[0] == "20261017_01_sibling_tool_catalogue"
    )
    assert version == "20261017_01_sibling_tool_catalogue"
    canonical_names = {name for name in configured_sibling_tool_names() if "." in name}
    assert all(f"'{name}'" in sql for name in canonical_names)
    assert "'knowledge.delete_doc'" not in sql


def test_knowledge_ops_without_token_is_unavailable_not_resolved(monkeypatch):
    monkeypatch.delenv("KNOWLEDGE_OPS_TOKEN", raising=False)
    [status] = resolver.classify_tool_names(["knowledge.search"])
    assert status["status"] == "unavailable"
    assert status["reason"] == "no_token"
