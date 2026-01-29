"""
Tool listing and metadata routes.
Exposes the built-in tools in a format the frontend expects.
"""

from fastapi import APIRouter
from typing import List
import logging

from app.llm.builtin_tools import get_default_tools, get_safe_tools

logger = logging.getLogger(__name__)
router = APIRouter()

# Display metadata for each built-in tool
TOOL_META = {
    "web_search": {
        "icon": "🔍",
        "type": "Python",
        "domain": "general",
        "provider": "Built-in",
        "capabilities": ["Real-time web search", "Multi-provider support", "Result filtering"],
    },
    "http_request": {
        "icon": "🌐",
        "type": "Python",
        "domain": "general",
        "provider": "Built-in",
        "capabilities": ["REST API calls", "Multiple HTTP methods", "JSON parsing", "Custom headers"],
    },
    "calculator": {
        "icon": "🧮",
        "type": "Python",
        "domain": "general",
        "provider": "Built-in",
        "capabilities": ["Arithmetic", "Trigonometry", "Scientific functions", "Safe evaluation"],
    },
    "datetime": {
        "icon": "🕐",
        "type": "Python",
        "domain": "general",
        "provider": "Built-in",
        "capabilities": ["Current time", "Timezone conversion", "Date formatting", "Time math"],
    },
    "json": {
        "icon": "📋",
        "type": "Python",
        "domain": "technology",
        "provider": "Built-in",
        "capabilities": ["Parse JSON", "Stringify", "JSONPath access", "Schema validation"],
    },
    "shell": {
        "icon": "💻",
        "type": "Python",
        "domain": "technology",
        "provider": "Built-in",
        "capabilities": ["Shell command execution", "Sandboxed environment", "Timeout support"],
    },
    "memory": {
        "icon": "🧠",
        "type": "Python",
        "domain": "general",
        "provider": "Built-in",
        "capabilities": ["Key-value storage", "Session persistence", "Conversation memory"],
    },
}


def _format_tool(tool) -> dict:
    """Format a ToolDefinition for the frontend."""
    meta = TOOL_META.get(tool.name, {})
    return {
        "id": tool.name,
        "name": tool.name.replace("_", " ").title(),
        "description": tool.description,
        "type": meta.get("type", "Python"),
        "domain": meta.get("domain", "general"),
        "icon": meta.get("icon", "🔧"),
        "provider": meta.get("provider", "Built-in"),
        "parameters": [p.name for p in tool.parameters],
        "capabilities": meta.get("capabilities", []),
        "status": "active",
        "schema": tool.to_openai_format(),
    }


@router.get("/tools")
async def list_tools():
    """List all available tools."""
    tools = get_default_tools()
    result = [_format_tool(t) for t in tools]
    return {"tools": result, "count": len(result)}


@router.get("/tools/available")
async def list_available_tools(permission_level: str = "public"):
    """List tools filtered by permission level."""
    tools = get_safe_tools() if permission_level in ("public", "authenticated") else get_default_tools()
    result = [_format_tool(t) for t in tools]
    return {"tools": result, "count": len(result), "permission_level": permission_level}
