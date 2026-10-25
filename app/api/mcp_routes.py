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

import logging
import os
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.middleware import AuthUser, require_admin, require_api_key
from app.auth.tool_scope import load_tool_org_scope
from app.db.database import get_session
from app.integrations.metering import meter_usage
from app.llm.tool_resolver import TOOL_REGISTRY
from app.protocols.mcp import mcp_server

_PUBLIC_BASE_URL = os.environ.get("BRIGADE_URL") or os.environ.get("BRIGADE_PUBLIC_URL") or "http://localhost:8100"

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
    arguments: dict[str, Any] = {}


class MCPProtocolRequest(BaseModel):
    """Raw MCP protocol request."""
    method: str
    params: dict[str, Any] = {}


# ---- Endpoints ----

@router.get("/mcp/info")
async def get_mcp_info(
    _auth: Annotated[AuthUser, Depends(require_api_key)],
    session: AsyncSession = Depends(get_session),
):
    """Get MCP server info and capabilities (AUTH REQUIRED — internal catalog).

    NOTE: the customer-facing, protocol-compliant MCP discovery surface is the
    federation gateway at ``/mcp`` (federation_mcp_router, key-authed). These
    legacy ``/api/v1/mcp/*`` catalog reads leak the full tool inventory +
    parameter schemas, so on an internet-reachable prod they require a key.
    """
    _ensure_tools_registered()
    scope = await load_tool_org_scope(session, _auth.org_id)

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
        "toolCount": sum(scope.allows(name) for name in mcp_server.tools),
        "resourceCount": len(mcp_server.resources),
    }


@router.get("/mcp/tools/list")
async def list_mcp_tools(
    _auth: Annotated[AuthUser, Depends(require_api_key)],
    session: AsyncSession = Depends(get_session),
):
    """List all available MCP tools (AUTH REQUIRED — leaks tool inventory + schemas)."""
    _ensure_tools_registered()
    scope = await load_tool_org_scope(session, _auth.org_id)

    tools = []
    for tool in mcp_server.tools.values():
        if not scope.allows(tool.name):
            continue
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
async def list_mcp_tools_openai_format(
    _auth: Annotated[AuthUser, Depends(require_api_key)],
    session: AsyncSession = Depends(get_session),
):
    """List tools in OpenAI function calling format (AUTH REQUIRED)."""
    _ensure_tools_registered()
    scope = await load_tool_org_scope(session, _auth.org_id)
    tools = [t for t in mcp_server.get_openai_tools() if scope.allows(t["function"]["name"])]

    return {
        "tools": tools,
        "count": len(tools),
    }


@router.get("/mcp/tools/anthropic")
async def list_mcp_tools_anthropic_format(
    _auth: Annotated[AuthUser, Depends(require_api_key)],
    session: AsyncSession = Depends(get_session),
):
    """List tools in Anthropic tool use format (AUTH REQUIRED)."""
    _ensure_tools_registered()
    scope = await load_tool_org_scope(session, _auth.org_id)
    tools = [t for t in mcp_server.get_tools_list() if scope.allows(t["name"])]

    return {
        "tools": tools,
        "count": len(tools),
    }


@router.post("/mcp/tools/call")
async def call_mcp_tool(
    request: MCPToolCallRequest,
    admin: Annotated[AuthUser, Depends(require_admin)],
    session: AsyncSession = Depends(get_session),
):
    """Invoke an MCP tool by name with arguments (ADMIN ONLY - RCE risk via shell/filesystem tools)."""
    _ensure_tools_registered()
    scope = await load_tool_org_scope(session, admin.org_id)
    if denial := scope.check(request.name):
        return {"tool": request.name, "result": None, "success": False, "error": denial}

    if request.name not in mcp_server.tools:
        raise HTTPException(status_code=404, detail=f"Tool not found: {request.name}")

    logger.info(f"MCP tool call: {request.name}({request.arguments})")

    result = await mcp_server.invoke_tool(
        name=request.name,
        arguments=request.arguments,
    )

    # BR-3.4: meter the MCP tool invocation against the caller's ORG. Direct tool
    # execution carries no LLM tokens, but the path was previously UNMETERED — a
    # 'tool_call' event makes it attributable + visible to the per-org cap.
    try:
        await meter_usage(
            org_id=getattr(admin, "org_id", None),
            user=(getattr(admin, "email", "") or "").lower() or None,
            source="mcp_tool",
            event_type="tool_call",
            tokens=0,
            tools_used=[request.name],
            outcome="partial" if isinstance(result, dict) and result.get("error") else "success",
            emit_value=False,
        )
    except Exception as _me:
        logger.debug(f"MCP tool meter skipped: {_me}")

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return {
        "tool": request.name,
        "result": result.get("result"),
        "success": True,
    }


@router.get("/mcp/resources/list")
async def list_mcp_resources(
    _auth: Annotated[AuthUser, Depends(require_api_key)],
):
    """List available MCP resources (AUTH REQUIRED)."""
    _ensure_tools_registered()

    return {
        "resources": mcp_server.get_resources_list(),
        "count": len(mcp_server.resources),
    }


@router.post("/mcp/request")
async def handle_mcp_request(
    request: MCPProtocolRequest,
    admin: Annotated[AuthUser, Depends(require_admin)],
    session: AsyncSession = Depends(get_session),
):
    """
    Handle a raw MCP protocol request (ADMIN ONLY - dispatches tools/call, RCE risk).

    This is the main MCP protocol endpoint for external clients.
    Supports methods: tools/list, tools/call, resources/list, resources/read
    """
    _ensure_tools_registered()

    logger.info(f"MCP protocol request: {request.method}")

    if request.method in {"tools/list", "tools/call"}:
        scope = await load_tool_org_scope(session, admin.org_id)
        if request.method == "tools/list":
            return {"tools": [t for t in mcp_server.get_tools_list() if scope.allows(t["name"])]}
        if denial := scope.check(request.params.get("name", "")):
            return {"content": [{"type": "text", "text": denial}], "isError": True}

    response = await mcp_server.handle_mcp_request({
        "method": request.method,
        "params": request.params,
    })

    return response


# ---- Claude Desktop / MCP Server Configuration ----

@router.get("/mcp/config")
async def get_mcp_config(
    _auth: Annotated[AuthUser, Depends(require_api_key)],
    session: AsyncSession = Depends(get_session),
):
    """
    Get MCP server configuration for Claude Desktop (AUTH REQUIRED — lists availableTools).

    Returns the configuration needed to add Brigade as an MCP server in Claude Desktop.
    """
    _ensure_tools_registered()
    scope = await load_tool_org_scope(session, _auth.org_id)

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
        "availableTools": [name for name in mcp_server.tools if scope.allows(name)],
    }
