"""Tests for the namespaced catalog + tier filter."""
from types import SimpleNamespace

from app.federation.catalog import (
    build_catalog,
    resolve_customer_rank,
    resolve_tool,
    tool_allowed,
)


def _app(namespace, audience, tools, status="active", endpoint="https://x.example.com/mcp"):
    return SimpleNamespace(
        namespace=namespace, expected_audience=audience, tools=tools,
        status=status, mcp_endpoint=endpoint,
    )


def _tool(name, tier="free", scopes=None, read_only=True):
    return {
        "name": name, "description": f"{name} desc", "input_schema": {"type": "object"},
        "scopes_required": scopes or [], "tier_required": tier, "read_only": read_only,
    }


def test_resolve_customer_rank():
    assert resolve_customer_rank(None) == 0          # fail-closed to free
    assert resolve_customer_rank("free") == 0
    assert resolve_customer_rank("pro") == 1
    assert resolve_customer_rank("Enterprise") == 2  # case-insensitive
    assert resolve_customer_rank("starter") == 1     # synonym -> pro
    assert resolve_customer_rank("business") == 2    # synonym -> enterprise
    assert resolve_customer_rank("wat-is-this") == 0 # unknown -> free, fail-closed


def test_tool_allowed():
    free, pro, ent = _tool("a", "free"), _tool("b", "pro"), _tool("c", "enterprise")
    assert tool_allowed(free, 0) and not tool_allowed(pro, 0) and not tool_allowed(ent, 0)
    assert tool_allowed(free, 1) and tool_allowed(pro, 1) and not tool_allowed(ent, 1)
    assert tool_allowed(free, 2) and tool_allowed(pro, 2) and tool_allowed(ent, 2)
    # unknown tool tier is hidden even for the top rank (fail-closed)
    assert not tool_allowed(_tool("x", "platinum"), 2)


def test_build_catalog_namespaces_and_filters():
    apps = [
        _app("project", "project-ops", [_tool("create_task", "free"), _tool("bulk_export", "pro")]),
        _app("meeting", "meeting-ops", [_tool("search_meetings", "free")]),
    ]
    free_cat = build_catalog(apps, customer_rank=0)
    names = sorted(t["name"] for t in free_cat)
    assert names == ["meeting.search_meetings", "project.create_task"]  # pro tool filtered out
    pro_cat = build_catalog(apps, customer_rank=1)
    assert "project.bulk_export" in {t["name"] for t in pro_cat}
    # routing metadata present
    entry = next(t for t in pro_cat if t["name"] == "project.bulk_export")
    assert entry["_app"] == "project-ops" and entry["_tool"] == "bulk_export"


def test_build_catalog_skips_inactive_and_dedupes():
    apps = [
        _app("project", "project-ops", [_tool("create_task")], status="disabled"),
        _app("meeting", "meeting-ops", [_tool("search_meetings")]),
    ]
    cat = build_catalog(apps, customer_rank=2)
    assert {t["name"] for t in cat} == {"meeting.search_meetings"}  # disabled app excluded


def test_resolve_tool():
    apps = [_app("project", "project-ops", [_tool("create_task", scopes=["write:tasks"])])]
    hit = resolve_tool(apps, "project.create_task")
    assert hit and hit["expected_audience"] == "project-ops"
    assert hit["tool_name"] == "create_task" and hit["scopes_required"] == ["write:tasks"]
    assert resolve_tool(apps, "project.nope") is None      # unknown tool
    assert resolve_tool(apps, "ghost.create_task") is None # unknown namespace
    assert resolve_tool(apps, "no-dot") is None            # malformed
