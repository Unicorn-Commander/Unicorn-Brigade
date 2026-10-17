#!/usr/bin/env python3
"""Report or remove agent tool references absent from Brigade's known names.

The default mode is read-only. ``--apply`` changes only ``agents.tools`` for
records with references absent from both the executable registry and the
database tool catalog.

Usage:
    ./.venv-brigade/bin/python scripts/prune_dead_tool_refs.py
    ./.venv-brigade/bin/python scripts/prune_dead_tool_refs.py --apply
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass
from typing import Collection, Mapping


@dataclass(frozen=True)
class ToolRefDiff:
    """The ordered tool-list change for one agent."""

    before: list[str]
    missing: list[str]
    after: list[str]


def _tool_names(value: object) -> list[str]:
    """Read the JSON shapes accepted by the Agent model without mutating them."""
    if not value:
        return []
    if isinstance(value, dict):
        return [str(name) for name, enabled in value.items() if enabled]
    if isinstance(value, list | tuple):
        return [str(name) for name in value]
    return [str(value)]


def compute_tool_diff(
    agent: Mapping[str, object],
    known_tool_names: Collection[str],
) -> ToolRefDiff:
    """Compute only the unresolved-reference removal for an agent record."""
    before = _tool_names(agent.get("tools"))
    known = {str(name) for name in known_tool_names}
    missing = sorted({name for name in before if name not in known})
    after = [name for name in before if name not in missing]
    return ToolRefDiff(before=before, missing=missing, after=after)


async def _run(*, apply: bool) -> int:
    """Read the roster and optionally commit only tool-list removals."""
    from sqlalchemy import select, text

    from app.db.database import admin_session
    from app.db.models import Agent
    from app.llm.sibling_app_tools import configured_sibling_tool_names
    from app.llm.tool_resolver import TOOL_REGISTRY, classify_tool_names

    async with admin_session() as session:
        catalog_rows = await session.execute(text("SELECT name FROM tool_catalog"))
        catalog_names = {str(row[0]) for row in catalog_rows if row[0] is not None}
        # Sibling names are statically valid even when their app is offline or
        # credentials are not mounted in this process.  Pruning them would
        # destroy the honest unavailable state that the resolver reports.
        known_tool_names = set(TOOL_REGISTRY) | catalog_names | configured_sibling_tool_names()

        result = await session.execute(select(Agent).order_by(Agent.id))
        changed = 0
        for agent in result.scalars().all():
            diff = compute_tool_diff({"tools": agent.tools}, known_tool_names)
            if not diff.missing:
                continue

            prefix = "APPLY" if apply else "DRY-RUN"
            statuses = classify_tool_names(diff.before)
            print(
                f"{prefix} agent={agent.id} before={diff.before!r} "
                f"status={statuses!r} missing={diff.missing!r} after={diff.after!r}"
            )
            changed += 1
            if apply:
                agent.tools = diff.after

        if apply:
            await session.commit()
        return changed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="commit removal of references absent from TOOL_REGISTRY and tool_catalog",
    )
    args = parser.parse_args(argv)

    try:
        changed = asyncio.run(_run(apply=args.apply))
    except Exception:
        # Avoid echoing a database DSN or another potentially sensitive error.
        print("unable to read or update the agent roster", file=sys.stderr)
        return 1

    mode = "applied" if args.apply else "would change"
    print(f"{mode} {changed} agent(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
