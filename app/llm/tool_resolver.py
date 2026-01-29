"""
Tool Resolver — Maps agent tool names to ToolDefinition objects.

Agents store tool references as string names (e.g., ["web_search", "calculator"]).
This module resolves those names to executable ToolDefinition instances from builtin_tools.
"""

from typing import Dict, List, Any

from app.llm.ops_center_client import ToolDefinition
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
}


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
