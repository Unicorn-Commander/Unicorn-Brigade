"""Tests for the tenant-scoped per-agent usage surface."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.api import agent_routes
from app.auth.tool_scope import ToolOrgScope
from app.db.repositories import AgentRepository


def _query_result(rows):
    result = MagicMock()
    result.all.return_value = rows
    return result


@pytest.mark.asyncio
async def test_agent_stats_uses_one_query_per_metric_and_omits_unbacked_tasks():
    session = MagicMock()
    session.execute = AsyncMock(
        side_effect=[
            _query_result([("alpha", 7)]),
            _query_result([("alpha", 2)]),
            _query_result([("alpha", 3, datetime(2026, 10, 26, 12, 34, 56))]),
        ]
    )

    stats = await AgentRepository(session).get_stats_for_agents(["alpha", "beta"])

    assert stats == {
        "alpha": {
            "messages": 7,
            "conversations": 2,
            "apiKeys": 3,
            "lastUsedAt": "2026-10-26T12:34:56",
        },
        "beta": {
            "messages": 0,
            "conversations": 0,
            "apiKeys": 0,
            "lastUsedAt": None,
        },
    }
    assert session.execute.await_count == 3
    key_query = str(session.execute.await_args_list[2].args[0])
    assert "api_keys" in key_query
    assert "current_org_id()" in key_query


@pytest.mark.asyncio
async def test_agent_stats_route_checks_access_and_returns_flat_contract(monkeypatch):
    access_check = MagicMock()
    user = object()

    class Repository:
        def __init__(self, session):
            self.session = session

        async def get(self, agent_id):
            return {"id": agent_id}

        async def get_stats(self, agent_id):
            return {
                "messages": 4,
                "conversations": 2,
                "apiKeys": 1,
                "lastUsedAt": "2026-10-26T12:34:56",
            }

    monkeypatch.setattr(agent_routes, "_ensure_agent_access", access_check)
    monkeypatch.setattr(agent_routes, "AgentRepository", Repository)

    result = await agent_routes.get_agent_stats("alpha", object(), user)

    access_check.assert_called_once_with(user, "alpha")
    assert result == {
        "agentId": "alpha",
        "messages": 4,
        "conversations": 2,
        "apiKeys": 1,
        "lastUsedAt": "2026-10-26T12:34:56",
    }


@pytest.mark.asyncio
async def test_list_agents_does_not_invent_usage_counts(monkeypatch):
    class Repository:
        def __init__(self, session):
            self.session = session

        async def list_all(self):
            return [
                {"id": "alpha", "tools": []},
                {"id": "beta", "tools": []},
            ]

    async def no_catalog(_session):
        return {}

    async def global_tools(*_args, **_kwargs):
        return ToolOrgScope()

    monkeypatch.setattr(agent_routes, "AgentRepository", Repository)
    monkeypatch.setattr(agent_routes, "_load_tool_catalog", no_catalog)
    monkeypatch.setattr(agent_routes, "load_tool_org_scope", global_tools)

    result = await agent_routes.list_agents(object(), None)

    assert all("_count" not in agent for agent in result["agents"])
    assert all("lastUsedAt" not in agent for agent in result["agents"])


@pytest.mark.asyncio
async def test_agent_stats_route_returns_not_found_after_access_check(monkeypatch):
    class Repository:
        def __init__(self, session):
            self.session = session

        async def get(self, _agent_id):
            return None

    monkeypatch.setattr(agent_routes, "AgentRepository", Repository)
    monkeypatch.setattr(agent_routes, "_ensure_agent_access", MagicMock())

    with pytest.raises(HTTPException) as exc_info:
        await agent_routes.get_agent_stats("missing", object(), object())

    assert exc_info.value.status_code == 404
