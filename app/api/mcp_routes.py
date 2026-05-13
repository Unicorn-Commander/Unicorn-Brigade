"""
MCP (Model Context Protocol) API Routes

Exposes Brigade's tools via the MCP protocol for external LLMs and clients.
Enables Claude Desktop, other AI assistants, and MCP clients to use Brigade's capabilities.

Endpoints:
- GET /mcp/info - Server info and capabilities
- GET /mcp/tools/list - List available tools
- POST /mcp/tools/call - Invoke a tool
- GET /mcp/resources/list - List available resources
- POST /mcp/request - Handle raw MCP protocol requests
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, List, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
import logging
import os

_PUBLIC_BASE_URL = os.environ.get("BRIGADE_URL") or os.environ.get("BRIGADE_PUBLIC_URL") or "http://localhost:8100"

from app.db.database import get_session
from app.protocols.mcp import mcp_server, MCPTool, MCPToolParameter
from app.llm.tool_resolver import TOOL_REGISTRY, get_tool_by_name
from app.llm.ops_center_client import ToolDefinition

logger = logging.getLogger(__name__)
router = APIRouter()

# Flag to track if tools are registered
_tools_registered = False


def _ensure_tools_registered():
    """Register Brigade's built-in tools with the MCP server (once)."""
    global _tools_registered
    if _tools_registered:
        return

    for name, tool_def in TOOL_REGISTRY.items():
        if name not in mcp_server.tools:
            # Convert ToolDefinition parameters to MCP format
            params = [
                {
                    "name": p.name,
                    "type": p.type,
                    "description": p.description,
                    "required": p.required,
                    "default": p.default,
                    "enum": p.enum,
                }
                for p in tool_def.parameters
            ]

            mcp_server.register_tool(
                name=tool_def.name,
                description=tool_def.description,
                parameters=params,
                handler=tool_def.handler,
                requires_approval=False,
            )

    _tools_registered = True
    logger.info(f"Registered {len(TOOL_REGISTRY)} built-in tools with MCP server")


# ---- Request/Response Models ----

class MCPToolCallRequest(BaseModel):
    """Request to invoke an MCP tool."""
    name: str
    arguments: Dict[str, Any] = {}


class MCPProtocolRequest(BaseModel):
    """Raw MCP protocol request."""
    method: str
    params: Dict[str, Any] = {}


# ---- Endpoints ----

@router.get("/mcp/info")
async def get_mcp_info():
    """Get MCP server info and capabilities."""
    _ensure_tools_registered()

    return {
        "name": "Unicorn Brigade",
        "version": "1.0.0",
        "protocol": "mcp",
        "description": "AI Agent Factory with enterprise-grade tools",
        "capabilities": {
            "tools": True,
            "resources": True,
            "prompts": False,
        },
        "toolCount": len(mcp_server.tools),
        "resourceCount": len(mcp_server.resources),
    }


@router.get("/mcp/tools/list")
async def list_mcp_tools():
    """List all available MCP tools."""
    _ensure_tools_registered()

    tools = []
    for tool in mcp_server.tools.values():
        tools.append({
            "name": tool.name,
            "description": tool.description,
            "parameters": [
                {
                    "name": p.name,
                    "type": p.type,
                    "description": p.description,
                    "required": p.required,
                    "default": p.default,
                    "enum": p.enum,
                }
                for p in tool.parameters
            ],
            "requires_approval": tool.requires_approval,
        })

    return {"tools": tools, "count": len(tools)}


@router.get("/mcp/tools/openai")
async def list_mcp_tools_openai_format():
    """List tools in OpenAI function calling format."""
    _ensure_tools_registered()

    return {
        "tools": mcp_server.get_openai_tools(),
        "count": len(mcp_server.tools),
    }


@router.get("/mcp/tools/anthropic")
async def list_mcp_tools_anthropic_format():
    """List tools in Anthropic tool use format."""
    _ensure_tools_registered()

    return {
        "tools": mcp_server.get_tools_list(),
        "count": len(mcp_server.tools),
    }


@router.post("/mcp/tools/call")
async def call_mcp_tool(request: MCPToolCallRequest):
    """Invoke an MCP tool by name with arguments."""
    _ensure_tools_registered()

    if request.name not in mcp_server.tools:
        raise HTTPException(status_code=404, detail=f"Tool not found: {request.name}")

    logger.info(f"MCP tool call: {request.name}({request.arguments})")

    result = await mcp_server.invoke_tool(
        name=request.name,
        arguments=request.arguments,
    )

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return {
        "tool": request.name,
        "result": result.get("result"),
        "success": True,
    }


@router.get("/mcp/resources/list")
async def list_mcp_resources():
    """List available MCP resources."""
    _ensure_tools_registered()

    return {
        "resources": mcp_server.get_resources_list(),
        "count": len(mcp_server.resources),
    }


@router.post("/mcp/request")
async def handle_mcp_request(request: MCPProtocolRequest):
    """
    Handle a raw MCP protocol request.

    This is the main MCP protocol endpoint for external clients.
    Supports methods: tools/list, tools/call, resources/list, resources/read
    """
    _ensure_tools_registered()

    logger.info(f"MCP protocol request: {request.method}")

    response = await mcp_server.handle_mcp_request({
        "method": request.method,
        "params": request.params,
    })

    return response


# ---- Claude Desktop / MCP Server Configuration ----

@router.get("/mcp/config")
async def get_mcp_config():
    """
    Get MCP server configuration for Claude Desktop.

    Returns the configuration needed to add Brigade as an MCP server in Claude Desktop.
    """
    _ensure_tools_registered()

    return {
        "instruction": "Add this configuration to your Claude Desktop settings",
        "configPath": {
            "macos": "~/Library/Application Support/Claude/claude_desktop_config.json",
            "windows": "%APPDATA%\\Claude\\claude_desktop_config.json",
        },
        "config": {
            "mcpServers": {
                "unicorn-brigade": {
                    "transport": "http",
                    "url": f"{_PUBLIC_BASE_URL}/api/v1/mcp/request",
                    "description": "Unicorn Brigade AI Agent Factory",
                }
            }
        },
        "availableTools": [t.name for t in mcp_server.tools.values()],
    }
