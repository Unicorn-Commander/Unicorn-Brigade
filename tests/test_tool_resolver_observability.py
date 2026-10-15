"""Observability tests for agent tool resolution."""

from __future__ import annotations

import logging

import app.llm.tool_resolver as resolver


def test_unresolved_tools_warn_once_per_agent(caplog):
    """Dropped names are visible once, even when the agent is resolved repeatedly."""
    resolver._UNRESOLVED_LOGGED_AGENTS.clear()
    agent = {
        "id": "fake-agent",
        "name": "Fake Agent",
        "tools": ["datetime", "missing_b", "missing_a", "missing_a"],
    }

    with caplog.at_level(logging.WARNING, logger="app.llm.tool_resolver"):
        assert [tool.name for tool in resolver.get_tools_for_agent(agent)] == ["datetime"]
        assert [tool.name for tool in resolver.get_tools_for_agent(agent)] == ["datetime"]

    records = [record for record in caplog.records if record.name == "app.llm.tool_resolver"]
    assert [record.message for record in records] == [
        "agent.tools.unresolved agent=fake-agent missing=['missing_a', 'missing_b']"
    ]
