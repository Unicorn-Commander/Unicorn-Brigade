"""
Tool Resolver — Maps agent tool names to ToolDefinition objects.

Agents store tool references as string names (e.g., ["web_search", "calculator"]).
This module resolves those names to executable ToolDefinition instances from builtin_tools.
"""

import os
import logging
from typing import Dict, List, Any

from app.llm.ops_center_client import ToolDefinition

logger = logging.getLogger(__name__)
from app.llm.builtin_tools import (
    WEB_SEARCH_TOOL,
    HTTP_REQUEST_TOOL,
    CALCULATOR_TOOL,
    DATETIME_TOOL,
    JSON_TOOL,
    SHELL_TOOL,
    MEMORY_TOOL,
)
from app.llm.extended_tools import (
    EMAIL_TOOL,
    FILE_TOOL,
    CODE_TOOL,
    TEXT_TOOL,
    IMAGE_TOOL,
    DATABASE_TOOL,
    NOTIFY_TOOL,
    QRCODE_TOOL,
)
from app.llm.analytics_tools import ANALYTICS_SQL_TOOL
from app.llm.advanced_tools import (
    BROWSER_TOOL,
    CODE_SANDBOX_TOOL,
    SANDBOX_SESSION_TOOL,
    SCREENSHOT_TOOL,
    PDF_EXTRACT_TOOL,
    DOC_GENERATE_TOOL,
    DATA_ANALYZE_TOOL,
    URL_PREVIEW_TOOL,
    KG_QUERY_TOOL,
)
from app.llm.knowledge_tools import (
    KNOWLEDGE_STORE_TOOL,
    KNOWLEDGE_QUERY_TOOL,
)
from app.llm.slack_tools import (
    SLACK_TOOL,
)
from app.llm.business_tools import (
    CSV_TOOL,
    RSS_TOOL,
    TRANSLATE_TOOL,
    WEATHER_TOOL,
    SCHEDULE_TOOL,
    COMPANY_TOOL,
)
from app.llm.delegation_tools import (
    DELEGATE_TO_AGENT_TOOL,
)
from app.llm.crisis_mcp_tools import CRISIS_MCP_TOOLS
from app.llm.projectops_mcp_tools import PROJECT_OPS_MCP_TOOLS
from app.llm.centerdeep_mcp_tools import CENTERDEEP_MCP_TOOLS
from app.llm.stable_canvas_tools import STABLE_CANVAS_TOOLS
from app.llm.stable_knowledge_tools import STABLE_KNOWLEDGE_TOOLS

# Registry mapping tool names to their definitions
TOOL_REGISTRY: Dict[str, ToolDefinition] = {
    # Core tools
    "web_search": WEB_SEARCH_TOOL,
    "http_request": HTTP_REQUEST_TOOL,
    "calculator": CALCULATOR_TOOL,
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
            HA_LIST_ENTITIES_TOOL,
            HA_GET_ENTITY_STATE_TOOL,
            HA_CALL_SERVICE_TOOL,
            HA_SEARCH_ENTITIES_TOOL,
            HA_GET_HISTORY_TOOL,
            HA_LIST_AREAS_TOOL,
            HA_GET_SERVICES_TOOL,
        )
        TOOL_REGISTRY.update({
            "ha_list_entities": HA_LIST_ENTITIES_TOOL,
            "ha_get_entity_state": HA_GET_ENTITY_STATE_TOOL,
            "ha_call_service": HA_CALL_SERVICE_TOOL,
            "ha_search_entities": HA_SEARCH_ENTITIES_TOOL,
            "ha_get_history": HA_GET_HISTORY_TOOL,
            "ha_list_areas": HA_LIST_AREAS_TOOL,
            "ha_get_services": HA_GET_SERVICES_TOOL,
        })
        logger.info("Home Assistant tools registered (HOMEASSISTANT_TOKEN/URL configured)")
    except ImportError:
        logger.warning("Home Assistant tools not available (ha_tools.py not found)")
else:
    logger.info("Home Assistant tools skipped (HOMEASSISTANT_TOKEN/URL not set)")


def get_tools_for_agent(agent: Dict[str, Any]) -> List[ToolDefinition]:
    """
    Resolve an agent's tool names to executable ToolDefinition objects.

    Args:
        agent: Agent dict with optional "tools" field (list of tool name strings)

    Returns:
        List of ToolDefinition objects the agent can use
    """
    tool_names = agent.get("tools") or []
    tools = []
    for name in tool_names:
        tool_def = TOOL_REGISTRY.get(name)
        if tool_def:
            tools.append(tool_def)
    return tools


def get_tool_by_name(name: str) -> ToolDefinition:
    """Get a single tool definition by name."""
    return TOOL_REGISTRY.get(name)


def get_tools_by_names(names: List[str]) -> List[ToolDefinition]:
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
    return tools
