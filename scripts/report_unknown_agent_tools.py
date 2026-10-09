#!/usr/bin/env python3
"""Read-only report of agent records containing unknown executable tool names.

Usage:
    ./.venv/bin/python scripts/report_unknown_agent_tools.py

The command only reads the agent roster. It does not repair, normalize, or
otherwise write agent records.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Iterable


def build_report(
    agents: Iterable[dict],
    known_tool_names: set[str],
) -> list[dict[str, object]]:
    """Build a deterministic report without mutating the supplied records."""
    report = []
    for agent in agents:
        unknown = sorted({
            str(name)
            for name in (agent.get("tools") or [])
            if str(name) not in known_tool_names
        })
        if unknown:
            report.append({
                "id": agent.get("id"),
                "name": agent.get("name") or agent.get("displayName"),
                "unknown_tools": unknown,
                "unknownTools": unknown,
            })
    return sorted(report, key=lambda item: str(item.get("id") or ""))


async def _read_report() -> list[dict[str, object]]:
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from app.db.database import admin_session
    from app.db.repositories import AgentRepository
    from app.llm.tool_resolver import TOOL_REGISTRY

    async with admin_session() as session:
        agents = await AgentRepository(session).list_all()
    return build_report(agents, set(TOOL_REGISTRY))


def main() -> int:
    try:
        report = asyncio.run(_read_report())
    except Exception:
        # Do not echo a database DSN or another potentially sensitive exception.
        print("unable to read the agent roster", file=sys.stderr)
        return 1

    print(json.dumps({"agents": report, "count": len(report)}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
