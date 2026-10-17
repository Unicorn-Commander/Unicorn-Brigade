# Executed by Grok (headless lane)
"""
Tool Resolver — Maps agent tool names to ToolDefinition objects.

Agents store tool references as string names (e.g., ["web_search", "calculator"]).
This module resolves those names to executable ToolDefinition instances from builtin_tools.
"""

import logging
import os
from typing import Any

from app.llm.advanced_tools import (
    BROWSER_TOOL,
    CODE_SANDBOX_TOOL,
    DATA_ANALYZE_TOOL,
    DOC_GENERATE_TOOL,
    KG_QUERY_TOOL,
    PDF_EXTRACT_TOOL,
    SANDBOX_SESSION_TOOL,
    SCREENSHOT_TOOL,
    URL_PREVIEW_TOOL,
)
from app.llm.analytics_tools import ANALYTICS_SQL_TOOL
from app.llm.builtin_tools import (
    CALCULATOR_TOOL,
    COLONEL_FACTS_TOOL,
    DATETIME_TOOL,
    HTTP_REQUEST_TOOL,
    JSON_TOOL,
    MEMORY_TOOL,
    SHELL_TOOL,
    WEB_SEARCH_TOOL,
)
from app.llm.business_tools import (
    COMPANY_TOOL,
    CSV_TOOL,
    RSS_TOOL,
    SCHEDULE_TOOL,
    TRANSLATE_TOOL,
    WEATHER_TOOL,
)
from app.llm.centerdeep_mcp_tools import CENTERDEEP_MCP_TOOLS
from app.llm.crisis_mcp_tools import CRISIS_MCP_TOOLS
from app.llm.delegation_tools import (
    DELEGATE_TO_AGENT_TOOL,
)
from app.llm.extended_tools import (
    AGENTIC_RAG_TOOL,
    CODE_TOOL,
    DATABASE_TOOL,
    EMAIL_TOOL,
    FILE_TOOL,
    IMAGE_TOOL,
    NOTIFY_TOOL,
    QRCODE_TOOL,
    TEXT_TOOL,
)
from app.llm.knowledge_tools import (
    KNOWLEDGE_QUERY_TOOL,
    KNOWLEDGE_STORE_TOOL,
)
from app.llm.ops_center_client import ToolDefinition
from app.llm.projectops_mcp_tools import PROJECT_OPS_MCP_TOOLS
from app.llm.sibling_app_tools import (
    classify_tool_names as classify_sibling_tool_names,
)
from app.llm.sibling_app_tools import (
    configured_sibling_tool_names,
    resolve_sibling_tool,
)
from app.llm.slack_tools import (
    SLACK_TOOL,
)
from app.llm.stable_canvas_tools import STABLE_CANVAS_TOOLS
from app.llm.stable_knowledge_tools import STABLE_KNOWLEDGE_TOOLS

logger = logging.getLogger(__name__)

# Keep unresolved-reference warnings useful without turning every agent
# invocation into a repeated warning. The process-local key is the agent's
# stable id/slug, not the missing tool set, so one warning covers the record's
# advertised unresolved names for the lifetime of this process.
_UNRESOLVED_LOGGED_AGENTS: set[str] = set()
_UNAVAILABLE_LOGGED_AGENTS: set[tuple[str, str]] = set()


class UnknownToolNamesError(ValueError):
    """Raised when an agent payload names a tool absent from the executable registry."""

    def __init__(self, unknown_names: list[str]):
        self.unknown_names = sorted(set(unknown_names))
        super().__init__(f"unknown tool names: {', '.join(self.unknown_names)}")


# Registry mapping tool names to their definitions
TOOL_REGISTRY: dict[str, ToolDefinition] = {
    # Core tools
    "web_search": WEB_SEARCH_TOOL,
    "http_request": HTTP_REQUEST_TOOL,
    "calculator": CALCULATOR_TOOL,
    # Fixed-URL fleet snapshot. Attached to The Colonel by his agent tool list,
    # not by the global default/safe/research sets.
    "colonel_facts": COLONEL_FACTS_TOOL,
    "datetime": DATETIME_TOOL,
    "json": JSON_TOOL,
    "shell": SHELL_TOOL,
    "memory": MEMORY_TOOL,
    # Extended tools
    "email": EMAIL_TOOL,
    "file": FILE_TOOL,
    "code": CODE_TOOL,
    "text": TEXT_TOOL,
    "image": IMAGE_TOOL,
    "database": DATABASE_TOOL,
    "notify": NOTIFY_TOOL,
    "qrcode": QRCODE_TOOL,
    "agentic_rag": AGENTIC_RAG_TOOL,
    "analytics_sql": ANALYTICS_SQL_TOOL,
    # Advanced tools (cutting-edge capabilities)
    "browser": BROWSER_TOOL,
    "code_sandbox": CODE_SANDBOX_TOOL,
    "sandbox_session": SANDBOX_SESSION_TOOL,
    "screenshot": SCREENSHOT_TOOL,
    "pdf_extract": PDF_EXTRACT_TOOL,
    "doc_generate": DOC_GENERATE_TOOL,
    "data_analyze": DATA_ANALYZE_TOOL,
    "url_preview": URL_PREVIEW_TOOL,
    "kg_query": KG_QUERY_TOOL,
    # Knowledge graph tools (FalkorDB)
    "knowledge_store": KNOWLEDGE_STORE_TOOL,
    "knowledge_query": KNOWLEDGE_QUERY_TOOL,
    # Slack integration
    "slack": SLACK_TOOL,
    # Business tools
    "csv": CSV_TOOL,
    "rss": RSS_TOOL,
    "translate": TRANSLATE_TOOL,
    "weather": WEATHER_TOOL,
    "schedule": SCHEDULE_TOOL,
    "company": COMPANY_TOOL,
    # Inter-agent delegation
    "delegate_to_agent": DELEGATE_TO_AGENT_TOOL,
}

# Crisis-case MCP tools (proxied to crisis-mcp service via JSON-RPC)
TOOL_REGISTRY.update(CRISIS_MCP_TOOLS)

# Project-Ops MCP tools (proxied to Project-Ops MCP via JSON-RPC over Streamable HTTP)
TOOL_REGISTRY.update(PROJECT_OPS_MCP_TOOLS)

# Center Deep Research MCP tools (proxied to CD's FastMCP via JSON-RPC over
# Streamable HTTP, authed with a uchub client_credentials bearer)
TOOL_REGISTRY.update(CENTERDEEP_MCP_TOOLS)

# Stable canvas tools (author artifacts into a Stable room's canvas via the
# Stable backend's internal artifact API; room/agent identity is server-injected
# via ToolDefinition.needs_room_context, not exposed to the model)
TOOL_REGISTRY.update(STABLE_CANVAS_TOOLS)

# Stable knowledge tool (search the knowledge bases attached to a Stable
# room via the Stable backend's internal knowledge-search API; room/agent
# identity is server-injected via ToolDefinition.needs_room_context, not
# exposed to the model)
TOOL_REGISTRY.update(STABLE_KNOWLEDGE_TOOLS)

# ── Optional integrations (loaded when configured) ─────────────────
# Home Assistant tools — only available when HA is configured
if os.getenv("HOMEASSISTANT_TOKEN") or os.getenv("HOMEASSISTANT_URL"):
    try:
        from app.llm.ha_tools import (
            HA_CALL_SERVICE_TOOL,
            HA_GET_ENTITY_STATE_TOOL,
            HA_GET_HISTORY_TOOL,
            HA_GET_SERVICES_TOOL,
            HA_LIST_AREAS_TOOL,
            HA_LIST_ENTITIES_TOOL,
            HA_SEARCH_ENTITIES_TOOL,
        )

        TOOL_REGISTRY.update(
            {
                "ha_list_entities": HA_LIST_ENTITIES_TOOL,
                "ha_get_entity_state": HA_GET_ENTITY_STATE_TOOL,
                "ha_call_service": HA_CALL_SERVICE_TOOL,
                "ha_search_entities": HA_SEARCH_ENTITIES_TOOL,
                "ha_get_history": HA_GET_HISTORY_TOOL,
                "ha_list_areas": HA_LIST_AREAS_TOOL,
                "ha_get_services": HA_GET_SERVICES_TOOL,
            }
        )
        logger.info("Home Assistant tools registered (HOMEASSISTANT_TOKEN/URL configured)")
    except ImportError:
        logger.warning("Home Assistant tools not available (ha_tools.py not found)")
else:
    logger.info("Home Assistant tools skipped (HOMEASSISTANT_TOKEN/URL not set)")

# Glitter Mane medical tools — only when the medical platform is configured.
# The agent lives on the medical platform; Brigade registers its tools (glitter_*)
# so a scoped agent can call them via the platform's per-user REST API (per-user
# token = RLS). See glittermane_mcp_tools.
if os.getenv("GLITTERMANE_API_URL"):
    try:
        from app.llm.glittermane_mcp_tools import GLITTERMANE_MCP_TOOLS

        TOOL_REGISTRY.update(GLITTERMANE_MCP_TOOLS)
        logger.info(f"Glitter Mane medical tools registered ({len(GLITTERMANE_MCP_TOOLS)} tools)")
    except ImportError as exc:
        logger.warning(f"Glitter Mane tools not available: {exc}")
else:
    logger.info("Glitter Mane tools skipped (GLITTERMANE_API_URL not set)")

# iLO / Redfish BMC tools — only when iLO targets are configured. Let an
# out-of-band specialist (CWO Lights-Out) operate server BMCs directly over
# Redfish (firmware / power / thermal). Reads run live; mutations (flash, power)
# preview by default and stay dormant until a human arms ILO_ALLOW_MUTATE. See
# ilo_redfish_tools.
if os.getenv("ILO_TARGETS"):
    try:
        from app.llm.ilo_redfish_tools import ILO_REDFISH_TOOLS

        TOOL_REGISTRY.update(ILO_REDFISH_TOOLS)
        logger.info(f"iLO Redfish BMC tools registered ({len(ILO_REDFISH_TOOLS)} tools)")
    except ImportError as exc:
        logger.warning(f"iLO Redfish tools not available: {exc}")
else:
    logger.info("iLO Redfish tools skipped (ILO_TARGETS not set)")

# Knowledge-Ops grounding tools — only when the internal KB is configured. Let any
# agent ground answers in the fleet's internal SOPs/runbooks/hardware docs instead
# of hallucinating company/infra facts. See knowledge_ops_tools.
if os.getenv("KNOWLEDGE_OPS_URL"):
    try:
        from app.llm.knowledge_ops_tools import KNOWLEDGE_OPS_TOOLS

        TOOL_REGISTRY.update(KNOWLEDGE_OPS_TOOLS)
        logger.info(f"Knowledge-Ops tools registered ({len(KNOWLEDGE_OPS_TOOLS)} tools)")
    except ImportError as exc:
        logger.warning(f"Knowledge-Ops tools not available: {exc}")
else:
    logger.info("Knowledge-Ops tools skipped (KNOWLEDGE_OPS_URL not set)")

# uc-browser tools — only when the browser gate is configured. Proxies into
# the uc-browser MCP gate (Playwright MCP driving a real Chrome) over JSON-RPC
# / Streamable HTTP, authed with the same uchub client_credentials bearer as
# Center-Deep. See ucbrowser_mcp_tools.
if os.getenv("UC_BROWSER_MCP_URL"):
    try:
        from app.llm.ucbrowser_mcp_tools import UC_BROWSER_MCP_TOOLS

        TOOL_REGISTRY.update(UC_BROWSER_MCP_TOOLS)
        logger.info(f"uc-browser tools registered ({len(UC_BROWSER_MCP_TOOLS)} tools)")
    except ImportError as exc:
        logger.warning(f"uc-browser tools not available: {exc}")
else:
    logger.info("uc-browser tools skipped (UC_BROWSER_MCP_URL not set)")


def unknown_tool_names(names: list[str] | None) -> list[str]:
    """Return sorted names that cannot resolve to executable tool definitions."""
    known = set(TOOL_REGISTRY) | configured_sibling_tool_names()
    return sorted({str(name) for name in (names or []) if str(name) not in known})


def classify_tool_names(names: list[str] | None) -> list[dict[str, str]]:
    """Report each name as resolved, unavailable(reason), or unknown."""
    return classify_sibling_tool_names(names, known_names=TOOL_REGISTRY)


def validate_tool_names(names: list[str] | None) -> None:
    """Reject an agent tool list that would otherwise be silently dropped at run time."""
    unknown = unknown_tool_names(names)
    if unknown:
        raise UnknownToolNamesError(unknown)


def _agent_slug(agent: dict[str, Any]) -> str:
    """Return the stable roster identifier used in unresolved-tool logs."""
    return str(agent.get("slug") or agent.get("id") or agent.get("name") or "<unknown>")


def _log_unavailable_once(agent_slug: str, app: str, reason: str) -> None:
    key = (agent_slug, app)
    if key in _UNAVAILABLE_LOGGED_AGENTS:
        return
    logger.warning(
        "agent.tools.unavailable agent=%s app=%s reason=%s",
        agent_slug,
        app,
        reason,
    )
    _UNAVAILABLE_LOGGED_AGENTS.add(key)


def get_tools_for_agent(agent: dict[str, Any]) -> list[ToolDefinition]:
    """
    Resolve an agent's tool names to executable ToolDefinition objects.

    Args:
        agent: Agent dict with optional "tools" field (list of tool name strings)

    Returns:
        List of ToolDefinition objects the agent can use
    """
    tool_names = [str(name) for name in (agent.get("tools") or [])]
    missing = unknown_tool_names(tool_names)
    if missing:
        slug = _agent_slug(agent)
        if slug not in _UNRESOLVED_LOGGED_AGENTS:
            logger.warning("agent.tools.unresolved agent=%s missing=%s", slug, missing)
            _UNRESOLVED_LOGGED_AGENTS.add(slug)

    tools = []
    slug = _agent_slug(agent)
    for name in tool_names:
        tool_def = TOOL_REGISTRY.get(name)
        if tool_def:
            tools.append(tool_def)
            continue

        sibling_tool, status = resolve_sibling_tool(name)
        if sibling_tool:
            tools.append(sibling_tool)
        elif status.app:
            _log_unavailable_once(slug, status.app, status.reason or "unknown_tool")
    return tools


def get_tool_by_name(name: str) -> ToolDefinition:
    """Get a single tool definition by name."""
    tool_def = TOOL_REGISTRY.get(name)
    if tool_def:
        return tool_def
    sibling_tool, _ = resolve_sibling_tool(name)
    return sibling_tool


def get_tools_by_names(names: list[str]) -> list[ToolDefinition]:
    """
    Get multiple tool definitions by their names.

    Args:
        names: List of tool name strings

    Returns:
        List of ToolDefinition objects (only includes tools that exist)
    """
    tools = []
    for name in names:
        tool_def = TOOL_REGISTRY.get(name)
        if tool_def:
            tools.append(tool_def)
            continue
        sibling_tool, _ = resolve_sibling_tool(name)
        if sibling_tool:
            tools.append(sibling_tool)
    return tools
