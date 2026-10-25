"""Seed-agent definitions must reference executable tool names."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.llm.tool_resolver import TOOL_REGISTRY

SEED_FILES = (
    Path("app/data/seed_agents.json"),
    Path("app/data/seed_agents_prod_core.json"),
)


@pytest.mark.parametrize("seed_path", SEED_FILES, ids=lambda path: path.name)
def test_seed_agent_tools_resolve_in_tool_registry(seed_path):
    """A new default-seed reference must fail CI instead of disappearing at run time."""
    if not seed_path.exists():
        # The production core seed is private to Magic Unicorn's deployment and is
        # absent from the public build (app/private_features.py).
        pytest.skip(f"{seed_path} is not part of this build")
    agents = json.loads(seed_path.read_text())
    references = {str(tool_name) for agent in agents for tool_name in (agent.get("tools") or [])}

    assert not (references - set(TOOL_REGISTRY)), (
        f"{seed_path} contains non-executable tool references: "
        f"{sorted(references - set(TOOL_REGISTRY))}"
    )
