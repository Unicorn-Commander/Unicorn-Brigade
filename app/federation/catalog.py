"""
Brigade federation: namespaced tool catalog + tier filter.

Assembles the unified tool list a customer's MCP client sees: the union of
tools across the customer's registered apps, each prepended with the app's
`{namespace}.`, filtered to the tools the customer's tier allows. Also resolves
a namespaced tool name back to (app, original tool) for the /mcp invoke path.

Tier handling adapts at THIS boundary. Brigade's own tier signals are not the
manifest's {free,pro,enterprise} scale (derive_user_tier is a compute-access
tier; ops-center billing's subscription_tier is a separate, externally-defined
string). So we map whatever subscription_tier Brigade has onto an integer rank
on the manifest scale, fail-closed to `free` when the tier is None/unknown, and
never refactor Brigade's tier model to fit.
"""
from __future__ import annotations

import logging
from typing import Iterable, Optional

logger = logging.getLogger(__name__)

# Manifest tool-tier scale (ordered).
TIER_RANK = {"free": 0, "pro": 1, "enterprise": 2}
_DEFAULT_TOOL_RANK = max(TIER_RANK.values()) + 1  # unknown tool tier -> hidden (fail-closed)

# Map ops-center / external subscription_tier strings onto the manifest scale.
# Unknown or None falls through to `free` (rank 0): an unconfirmed customer sees
# only free tools, never paid ones.
_SUBSCRIPTION_TO_SCALE = {
    "free": "free", "none": "free", "trial": "free", "viewer": "free",
    "starter": "pro", "basic": "pro", "standard": "pro", "plus": "pro",
    "pro": "pro", "professional": "pro", "gpu-enabled": "pro",
    "enterprise": "enterprise", "business": "enterprise", "team": "enterprise",
    "admin": "enterprise",
}


def resolve_customer_rank(subscription_tier: Optional[str]) -> int:
    """Map a Brigade/ops-center tier string to a rank on the manifest scale.

    Fail-closed: None or an unrecognized value resolves to `free` (rank 0).
    """
    if not subscription_tier:
        return TIER_RANK["free"]
    key = str(subscription_tier).strip().lower()
    scale = _SUBSCRIPTION_TO_SCALE.get(key)
    if scale is None:
        logger.warning(
            "Unknown subscription_tier %r; treating as free (fail-closed). "
            "Add it to _SUBSCRIPTION_TO_SCALE once the ops-center vocabulary is confirmed.",
            subscription_tier,
        )
        return TIER_RANK["free"]
    return TIER_RANK[scale]


def _tool_rank(tool: dict) -> int:
    return TIER_RANK.get(str(tool.get("tier_required", "")).strip().lower(), _DEFAULT_TOOL_RANK)


def tool_allowed(tool: dict, customer_rank: int) -> bool:
    """A tool is visible/invocable iff the customer's rank meets its required tier."""
    return customer_rank >= _tool_rank(tool)


def _namespaced(namespace: str, tool: dict, app_audience: str) -> dict:
    """Render one tool for the unified catalog, namespaced + routing metadata."""
    original = tool.get("name", "")
    return {
        "name": f"{namespace}.{original}",
        "description": tool.get("description", ""),
        "input_schema": tool.get("input_schema", {"type": "object"}),
        "read_only": bool(tool.get("read_only", False)),
        # Routing metadata for the /mcp invoke path (kept under _-prefixed keys
        # so they are easy to strip before returning to the MCP client).
        "_app": app_audience,
        "_namespace": namespace,
        "_tool": original,
        "_scopes_required": tool.get("scopes_required", []),
        "_tier_required": tool.get("tier_required", "free"),
    }


def build_catalog(apps: Iterable, customer_rank: int) -> list[dict]:
    """
    Union of namespaced, tier-filtered tools across the given active apps.

    apps           iterable of FederatedApp rows (each has .namespace,
                   .expected_audience, .tools, .status)
    customer_rank  from resolve_customer_rank(subscription_tier)
    """
    catalog: list[dict] = []
    seen: set[str] = set()
    for app in apps:
        if getattr(app, "status", "active") != "active":
            continue
        namespace = app.namespace
        audience = app.expected_audience
        for tool in (app.tools or []):
            if not tool.get("name"):
                continue
            if not tool_allowed(tool, customer_rank):
                continue
            entry = _namespaced(namespace, tool, audience)
            if entry["name"] in seen:
                logger.warning("Duplicate namespaced tool %s; skipping the later one", entry["name"])
                continue
            seen.add(entry["name"])
            catalog.append(entry)
    return catalog


def resolve_tool(apps: Iterable, namespaced_name: str) -> Optional[dict]:
    """
    Map an invoked `namespace.tool` back to its app + original tool entry.

    Returns {app, namespace, tool_name, tool, expected_audience, scopes_required,
    tier_required} or None if no active app/tool matches.
    """
    if "." not in namespaced_name:
        return None
    namespace, _, tool_name = namespaced_name.partition(".")
    for app in apps:
        if getattr(app, "status", "active") != "active":
            continue
        if app.namespace != namespace:
            continue
        for tool in (app.tools or []):
            if tool.get("name") == tool_name:
                return {
                    "app": app,
                    "namespace": namespace,
                    "tool_name": tool_name,
                    "tool": tool,
                    "expected_audience": app.expected_audience,
                    "mcp_endpoint": app.mcp_endpoint,
                    "scopes_required": tool.get("scopes_required", []),
                    "tier_required": tool.get("tier_required", "free"),
                }
    return None
