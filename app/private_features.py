"""Parts of Brigade that exist only in Magic Unicorn's own deployment.

The crisis investigation feature (three agents, their routes and the crisis MCP
tools) was built for one legal matter. The production core seed
(app/data/seed_agents_prod_core.json) describes the operator's own crew and
infrastructure. Both stay in the private source and run on Magic Unicorn's
systems, but the public GitHub mirror removes these paths from its whole
history, so the public build must start and test cleanly without them.

A feature counts as installed when its files exist. This is checked by path,
not by catching ImportError, so a real error inside an installed module still
fails loudly instead of quietly switching the feature off. A partial install
(some files present, some missing) is an error for the same reason.
"""

from __future__ import annotations

from pathlib import Path

_APP = Path(__file__).resolve().parent

CRISIS_FEATURE_FILES = (
    _APP / "agents" / "evidence_correlator.py",
    _APP / "agents" / "gap_analyzer.py",
    _APP / "agents" / "timeline_builder.py",
    _APP / "agents" / "crisis_registration.py",
    _APP / "api" / "crisis_routes.py",
    _APP / "llm" / "crisis_mcp_tools.py",
)


def crisis_feature_present(files=CRISIS_FEATURE_FILES) -> bool:
    """True when every crisis feature file is installed, False when none is."""
    present = [f for f in files if f.is_file()]
    if not present:
        return False
    if len(present) != len(files):
        missing = sorted(str(f) for f in files if not f.is_file())
        raise RuntimeError(f"The crisis feature is only partly installed; missing: {', '.join(missing)}")
    return True
