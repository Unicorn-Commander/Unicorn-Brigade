"""Canonical portrait paths for Brigade's built-in shared roster.

Brigade owns agent identity.  The corresponding WebP files live in the
Brigade frontend's public ``/avatars`` directory and are served by the same
public Brigade origin as the API.  Keeping the registry here gives the seed
loader, migrations, tests, and downstream consumers one explicit contract.

Status variants (``-thinking``, ``-success``, ``-alert``) are presentation
assets.  ``avatarUrl`` always points at the stable primary portrait.
"""

from __future__ import annotations


CORE_AGENT_AVATAR_IDS: tuple[str, ...] = (
    "the-general",
    "gunny",
    "sgt-cipher",
    "cpt-fullstack",
    "maj-devops",
    "col-finance",
    "lt-taxstrat",
    "judge-advocate",
    "doc-medresearch",
    "detective-holmes",
    "prof-datasci",
    "support-agent",
    "code-reviewer",
    "sql-analyst",
    "sgt-scribe",
    "maj-leadgen",
    "lt-docanalyst",
)

# Approved external identity masters imported into Brigade's runtime catalog.
# Brand-Ops remains the artwork source; Brigade owns the binding and served URL.
MASTERED_AGENT_AVATAR_IDS: tuple[str, ...] = CORE_AGENT_AVATAR_IDS + (
    "iris",
    "perry",
    "prudence",
    "cpl.-colophon",
)


def canonical_avatar_path(agent_id: str) -> str | None:
    """Return the same-origin primary portrait for a verified agent mapping."""

    if agent_id not in MASTERED_AGENT_AVATAR_IDS:
        return None
    return f"/avatars/{agent_id}.webp"
