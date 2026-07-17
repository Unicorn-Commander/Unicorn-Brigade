"""
MCP Registry API Routes

Endpoints for managing MCP servers and executing code in sandboxes.

SECURITY: Most endpoints require admin authentication due to RCE risk.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional, Annotated

from app.mcp.registry import mcp_registry, MCPServer, MCPTransport
from app.mcp.sandbox_executor import sandbox_executor, ExecutionResult
from app.auth.middleware import require_admin, require_operator, require_api_key, AuthUser
from app.security.rate_limit import rate_limit
from app.security.request_limits import max_body_size

router = APIRouter(prefix="/mcp/registry", tags=["MCP Registry"])


# Request/Response Models

class MCPServerCreate(BaseModel):
    """Create a new MCP server configuration"""
    name: str = Field(..., description="Unique server name")
    display_name: str = Field(..., description="Human-readable name")
    command: str = Field(..., description="Command to run (e.g., 'npx')")
    args: List[str] = Field(default_factory=list, description="Command arguments")
    env: Dict[str, str] = Field(default_factory=dict, description="Environment variables")
    capabilities: List[str] = Field(default_factory=list, description="Tool capabilities")
    description: str = Field("", description="Server description")


class MCPToolCall(BaseModel):
    """Call a tool on an MCP server"""
    server_name: str = Field(..., description="MCP server name")
    tool_name: str = Field(..., description="Tool to call")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Tool arguments")


class CodeExecuteRequest(BaseModel):
    """Execute code in sandbox"""
    code: str = Field(..., description="Code to execute")
    language: str = Field("python", description="Programming language")
    timeout: Optional[int] = Field(None, description="Execution timeout in seconds")
    env: Optional[Dict[str, str]] = Field(None, description="Environment variables")
    packages: Optional[List[str]] = Field(None, description="Packages to install")


# Endpoints

@router.get("/servers")
async def list_servers(
    _auth: Annotated[AuthUser, Depends(require_api_key)],
):
    """List all available MCP servers (AUTH REQUIRED — server catalog is internal topology)"""
    return {"servers": mcp_registry.list_available()}


@router.get("/servers/running")
async def list_running_servers(
    _auth: Annotated[AuthUser, Depends(require_api_key)],
):
    """List currently running MCP servers (AUTH REQUIRED)"""
    return {"servers": mcp_registry.list_running()}


@router.get("/servers/{name}")
async def get_server(
    name: str,
    _auth: Annotated[AuthUser, Depends(require_api_key)],
):
    """Get details of a specific MCP server (AUTH REQUIRED — leaks command/env/capabilities)"""
    server = mcp_registry.get_server(name)
    if not server:
        raise HTTPException(404, f"Server not found: {name}")

    return {
        "name": server.name,
        "display_name": server.display_name,
        "description": server.description,
        "command": server.command,
        "args": server.args,
        "capabilities": server.capabilities,
        "transport": server.transport.value,
        "enabled": server.enabled,
        "running": mcp_registry.is_running(name),
    }


@router.post("/servers")
async def register_server(
    server_config: MCPServerCreate,
    admin: Annotated[AuthUser, Depends(require_admin)],
):
    """Register a new MCP server (ADMIN ONLY)"""
    server = MCPServer(
        name=server_config.name,
        display_name=server_config.display_name,
        command=server_config.command,
        args=server_config.args,
        env=server_config.env,
        capabilities=server_config.capabilities,
        description=server_config.description,
    )

    mcp_registry.register_server(server)

    return {
        "status": "registered",
        "server": server_config.name,
    }


@router.delete("/servers/{name}")
async def unregister_server(
    name: str,
    admin: Annotated[AuthUser, Depends(require_admin)],
):
    """Unregister an MCP server (ADMIN ONLY)"""
    # Stop if running
    if mcp_registry.is_running(name):
        await mcp_registry.stop_server(name)

    if mcp_registry.unregister_server(name):
        return {"status": "unregistered", "server": name}

    raise HTTPException(404, f"Server not found: {name}")


@router.post("/servers/{name}/start")
async def start_server(
    name: str,
    background_tasks: BackgroundTasks,
    admin: Annotated[AuthUser, Depends(require_admin)],
    _rl: Annotated[None, rate_limit("mcp_server_ops", 5, 60)] = None,
):
    """Start an MCP server (ADMIN ONLY)"""
    if mcp_registry.is_running(name):
        return {"status": "already_running", "server": name}

    success = await mcp_registry.start_server(name)
    if success:
        return {"status": "started", "server": name}

    raise HTTPException(500, f"Failed to start server: {name}")


@router.post("/servers/{name}/stop")
async def stop_server(
    name: str,
    admin: Annotated[AuthUser, Depends(require_admin)],
    _rl: Annotated[None, rate_limit("mcp_server_ops", 5, 60)] = None,
):
    """Stop an MCP server (ADMIN ONLY)"""
    if not mcp_registry.is_running(name):
        return {"status": "not_running", "server": name}

    success = await mcp_registry.stop_server(name)
    if success:
        return {"status": "stopped", "server": name}

    raise HTTPException(500, f"Failed to stop server: {name}")


@router.post("/servers/{name}/restart")
async def restart_server(
    name: str,
    admin: Annotated[AuthUser, Depends(require_admin)],
    _rl: Annotated[None, rate_limit("mcp_server_ops", 5, 60)] = None,
):
    """Restart an MCP server (ADMIN ONLY)"""
    await mcp_registry.stop_server(name)
    success = await mcp_registry.start_server(name)

    if success:
        return {"status": "restarted", "server": name}

    raise HTTPException(500, f"Failed to restart server: {name}")


@router.post("/tools/call")
async def call_tool(
    request: MCPToolCall,
    admin: Annotated[AuthUser, Depends(require_admin)],
):
    """Call a tool on an MCP server (ADMIN ONLY - RCE risk via shell/filesystem tools)"""
    result = await mcp_registry.call_tool(
        request.server_name,
        request.tool_name,
        request.arguments,
    )

    if "error" in result:
        raise HTTPException(500, result["error"])

    return {"result": result}


# Sandbox Endpoints

@router.get("/sandbox/status")
async def get_sandbox_status(
    _auth: Annotated[AuthUser, Depends(require_api_key)],
):
    """Get sandbox executor status (AUTH REQUIRED — reveals docker/e2b backend availability)"""
    status = sandbox_executor.get_status()

    # Check availability
    status["docker_available"] = await sandbox_executor.check_docker()
    status["e2b_available"] = await sandbox_executor.check_e2b()

    return status


@router.post("/sandbox/execute")
async def execute_code(
    request: CodeExecuteRequest,
    admin: Annotated[AuthUser, Depends(require_admin)],
    _rl: Annotated[None, rate_limit("mcp_sandbox_execute", 10, 60)] = None,
    _size: Annotated[None, max_body_size(1024 * 1024)] = None,
):
    """
    Execute code in sandbox (ADMIN ONLY).

    Supports Python, JavaScript, TypeScript, Bash.
    Uses Docker by default, E2B as fallback.
    """
    try:
        result = await sandbox_executor.execute(
            code=request.code,
            language=request.language,
            timeout=request.timeout,
            env=request.env,
            packages=request.packages,
        )

        return result.to_dict()

    except RuntimeError as e:
        raise HTTPException(503, str(e))
    except Exception as e:
        raise HTTPException(500, f"Execution failed: {str(e)}")


@router.post("/sandbox/execute/fallback")
async def execute_code_with_fallback(
    request: CodeExecuteRequest,
    admin: Annotated[AuthUser, Depends(require_admin)],
    _rl: Annotated[None, rate_limit("mcp_sandbox_execute", 10, 60)] = None,
    _size: Annotated[None, max_body_size(1024 * 1024)] = None,
):
    """
    Execute code with automatic fallback (ADMIN ONLY).

    Tries Docker first, automatically falls back to E2B if Docker fails.
    """
    try:
        result = await sandbox_executor.execute_with_fallback(
            code=request.code,
            language=request.language,
            timeout=request.timeout,
            env=request.env,
            packages=request.packages,
        )

        return result.to_dict()

    except Exception as e:
        raise HTTPException(500, f"Execution failed: {str(e)}")


# Health check for MCP subsystem
@router.get("/health")
async def mcp_health(
    _auth: Annotated[AuthUser, Depends(require_api_key)],
):
    """Health check for MCP registry and sandbox (AUTH REQUIRED — leaks server/running counts)"""
    docker_ok = await sandbox_executor.check_docker()
    e2b_ok = await sandbox_executor.check_e2b()
    running_servers = len(mcp_registry.list_running())

    return {
        "status": "healthy" if docker_ok or e2b_ok else "degraded",
        "docker_available": docker_ok,
        "e2b_available": e2b_ok,
        "registered_servers": len(mcp_registry.SERVERS),
        "running_servers": running_servers,
    }
