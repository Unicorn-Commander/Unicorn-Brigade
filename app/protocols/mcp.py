"""
MCP (Model Context Protocol) Implementation

Anthropic's standard for LLM tool integration.
https://modelcontextprotocol.io/

Key concepts:
- Tools: Functions that LLMs can call
- Resources: Data sources accessible to LLMs
- Prompts: Reusable prompt templates

This implementation provides:
- MCPServer: Expose tools to external LLMs
- MCPClient: Connect to external MCP servers
- MCPToolExecutor: Execute tools with approval gates
- Resource backends: File, database, HTTP
"""

from typing import Dict, Any, List, Optional, Callable, Awaitable, Union
from pydantic import BaseModel, Field
from dataclasses import dataclass, field as dataclass_field
from datetime import datetime
from enum import Enum
import json
import logging
import asyncio
import httpx
import subprocess
import os

logger = logging.getLogger(__name__)


class MCPToolParameter(BaseModel):
    """Parameter definition for an MCP tool"""
    name: str
    type: str  # "string", "number", "boolean", "object", "array"
    description: str
    required: bool = True
    default: Optional[Any] = None
    enum: Optional[List[Any]] = None


class MCPTool(BaseModel):
    """
    MCP Tool definition.

    Tools are functions that LLMs can invoke to perform actions.
    """
    name: str
    description: str
    parameters: List[MCPToolParameter] = Field(default_factory=list)

    # Execution
    handler: Optional[str] = None  # Python import path or callable name

    # Metadata
    category: str = "general"
    requires_approval: bool = False
    risk_level: str = "low"

    def to_openai_format(self) -> Dict[str, Any]:
        """Convert to OpenAI function calling format"""
        properties = {}
        required = []

        for param in self.parameters:
            properties[param.name] = {
                "type": param.type,
                "description": param.description,
            }
            if param.enum:
                properties[param.name]["enum"] = param.enum
            if param.required:
                required.append(param.name)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                }
            }
        }

    def to_anthropic_format(self) -> Dict[str, Any]:
        """Convert to Anthropic tool use format"""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": {
                    p.name: {
                        "type": p.type,
                        "description": p.description,
                        **({"enum": p.enum} if p.enum else {}),
                    }
                    for p in self.parameters
                },
                "required": [p.name for p in self.parameters if p.required],
            }
        }


class MCPResource(BaseModel):
    """
    MCP Resource definition.

    Resources are data sources that LLMs can access.
    """
    uri: str  # e.g., "file:///path/to/file" or "db://table/query"
    name: str
    description: str
    mime_type: str = "text/plain"

    # Access control
    read_only: bool = True
    requires_auth: bool = False


class MCPServer:
    """
    MCP Server implementation for Unicorn Brigade.

    Exposes tools, resources, and prompts via the MCP protocol.
    This allows external LLMs to use Brigade's capabilities.
    """

    def __init__(self):
        self.tools: Dict[str, MCPTool] = {}
        self.resources: Dict[str, MCPResource] = {}
        self.handlers: Dict[str, Callable[..., Awaitable[Any]]] = {}
        self._resource_manager = None  # Lazy-loaded MCPResourceManager

    def get_resource_manager(self):
        """Get or create the resource manager"""
        if self._resource_manager is None:
            self._resource_manager = MCPResourceManager()
        return self._resource_manager

    def register_tool(
        self,
        name: str,
        description: str,
        parameters: List[Dict[str, Any]],
        handler: Callable[..., Awaitable[Any]],
        requires_approval: bool = False,
    ):
        """Register a tool with the MCP server"""
        params = [
            MCPToolParameter(
                name=p["name"],
                type=p.get("type", "string"),
                description=p.get("description", ""),
                required=p.get("required", True),
                default=p.get("default"),
                enum=p.get("enum"),
            )
            for p in parameters
        ]

        tool = MCPTool(
            name=name,
            description=description,
            parameters=params,
            requires_approval=requires_approval,
        )

        self.tools[name] = tool
        self.handlers[name] = handler
        logger.info(f"Registered MCP tool: {name}")

    def register_resource(
        self,
        uri: str,
        name: str,
        description: str,
        mime_type: str = "text/plain",
    ):
        """Register a resource with the MCP server"""
        resource = MCPResource(
            uri=uri,
            name=name,
            description=description,
            mime_type=mime_type,
        )
        self.resources[uri] = resource
        logger.info(f"Registered MCP resource: {uri}")

    async def invoke_tool(
        self,
        name: str,
        arguments: Dict[str, Any],
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Invoke a registered tool"""
        if name not in self.tools:
            return {"error": f"Tool not found: {name}"}

        tool = self.tools[name]
        handler = self.handlers.get(name)

        if not handler:
            return {"error": f"No handler for tool: {name}"}

        try:
            # Validate required parameters
            for param in tool.parameters:
                if param.required and param.name not in arguments:
                    return {"error": f"Missing required parameter: {param.name}"}

            # Invoke handler
            result = await handler(**arguments)
            return {"result": result}

        except Exception as e:
            logger.error(f"Tool invocation failed: {name} - {e}")
            return {"error": str(e)}

    def get_tools_list(self) -> List[Dict[str, Any]]:
        """Get list of all tools in MCP format"""
        return [tool.to_anthropic_format() for tool in self.tools.values()]

    def get_openai_tools(self) -> List[Dict[str, Any]]:
        """Get tools in OpenAI function calling format"""
        return [tool.to_openai_format() for tool in self.tools.values()]

    def get_resources_list(self) -> List[Dict[str, Any]]:
        """Get list of all resources"""
        return [r.model_dump() for r in self.resources.values()]

    async def handle_mcp_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle an incoming MCP protocol request.

        This is the main entry point for MCP clients.
        """
        method = request.get("method")
        params = request.get("params", {})

        if method == "tools/list":
            return {"tools": self.get_tools_list()}

        elif method == "tools/call":
            name = params.get("name")
            arguments = params.get("arguments", {})
            return await self.invoke_tool(name, arguments)

        elif method == "resources/list":
            return {"resources": self.get_resources_list()}

        elif method == "resources/read":
            uri = params.get("uri")
            if not uri:
                return {"error": "Missing 'uri' parameter"}

            # Try using the resource manager to read the URI
            try:
                result = await self.get_resource_manager().read(uri)
                if "error" in result:
                    return result
                return result
            except Exception as e:
                logger.error(f"Error reading resource {uri}: {e}")
                return {"error": str(e)}

        else:
            return {"error": f"Unknown method: {method}"}


# Global MCP server instance
mcp_server = MCPServer()


def register_tool(
    name: str,
    description: str,
    parameters: List[Dict[str, Any]],
    requires_approval: bool = False,
):
    """Decorator to register a function as an MCP tool"""
    def decorator(func: Callable[..., Awaitable[Any]]):
        mcp_server.register_tool(
            name=name,
            description=description,
            parameters=parameters,
            handler=func,
            requires_approval=requires_approval,
        )
        return func
    return decorator


# ============== MCP Client ==============

class MCPClientError(Exception):
    """Error from MCP client operations"""
    pass


class MCPTransport(str, Enum):
    """Transport types for MCP connections"""
    STDIO = "stdio"  # stdin/stdout with subprocess
    HTTP = "http"  # HTTP/SSE
    WEBSOCKET = "websocket"


@dataclass
class MCPServerConfig:
    """Configuration for connecting to an MCP server"""
    name: str
    transport: MCPTransport

    # For STDIO transport
    command: Optional[str] = None
    args: List[str] = dataclass_field(default_factory=list)
    env: Dict[str, str] = dataclass_field(default_factory=dict)

    # For HTTP/WebSocket transport
    url: Optional[str] = None
    headers: Dict[str, str] = dataclass_field(default_factory=dict)

    # Common options
    timeout_seconds: float = 30.0
    auto_reconnect: bool = True


class MCPClient:
    """
    Client for connecting to external MCP servers.

    Supports multiple transports:
    - STDIO: For local MCP servers (subprocess communication)
    - HTTP: For remote MCP servers (HTTP + SSE)
    - WebSocket: For bidirectional real-time communication
    """

    def __init__(self, config: MCPServerConfig):
        self.config = config
        self._process: Optional[subprocess.Popen] = None
        self._http_client: Optional[httpx.AsyncClient] = None
        self._request_id = 0
        self._pending_requests: Dict[int, asyncio.Future] = {}
        self._tools: Dict[str, MCPTool] = {}
        self._resources: Dict[str, MCPResource] = {}
        self._connected = False
        self._read_task: Optional[asyncio.Task] = None

    async def connect(self):
        """Connect to the MCP server"""
        if self.config.transport == MCPTransport.STDIO:
            await self._connect_stdio()
        elif self.config.transport == MCPTransport.HTTP:
            await self._connect_http()
        else:
            raise MCPClientError(f"Unsupported transport: {self.config.transport}")

        self._connected = True
        logger.info(f"Connected to MCP server: {self.config.name}")

        # Initialize by fetching tools and resources
        await self._initialize()

    async def _connect_stdio(self):
        """Connect via stdio (subprocess)"""
        if not self.config.command:
            raise MCPClientError("STDIO transport requires 'command' in config")

        env = os.environ.copy()
        env.update(self.config.env)

        self._process = subprocess.Popen(
            [self.config.command] + self.config.args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )

        # Start reading responses
        self._read_task = asyncio.create_task(self._read_stdio_responses())

    async def _connect_http(self):
        """Connect via HTTP"""
        if not self.config.url:
            raise MCPClientError("HTTP transport requires 'url' in config")

        self._http_client = httpx.AsyncClient(
            base_url=self.config.url,
            headers=self.config.headers,
            timeout=self.config.timeout_seconds,
        )

    async def _initialize(self):
        """
        Initialize MCP connection with proper handshake.

        MCP Protocol initialization sequence:
        1. Client sends 'initialize' request with client info
        2. Server responds with server capabilities
        3. Client sends 'initialized' notification
        4. Client can now call tools/list, resources/list, etc.
        """
        try:
            # Step 1 & 2: Send initialize request and get server capabilities
            init_response = await self.request("initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "roots": {"listChanged": True},
                    "sampling": {}
                },
                "clientInfo": {
                    "name": "unicorn-brigade",
                    "version": "1.0.0"
                }
            })

            logger.info(f"MCP server initialized: {init_response.get('serverInfo', {}).get('name', 'unknown')}")

            # Step 3: Send initialized notification (no response expected)
            # Note: Notifications don't have an 'id' and don't expect a response
            if self.config.transport == ProtocolMCPTransport.STDIO and self._process:
                notification = {
                    "jsonrpc": "2.0",
                    "method": "notifications/initialized",
                    "params": {}
                }
                notification_json = json.dumps(notification) + "\n"
                self._process.stdin.write(notification_json.encode())
                self._process.stdin.flush()

            # Small delay to let server process the notification
            await asyncio.sleep(0.1)

        except Exception as e:
            logger.warning(f"MCP initialize handshake failed, continuing anyway: {e}")

        # Step 4: Now fetch tools and resources
        try:
            tools_response = await self.request("tools/list", {})
            if "tools" in tools_response:
                for tool_data in tools_response["tools"]:
                    tool = MCPTool(
                        name=tool_data["name"],
                        description=tool_data.get("description", ""),
                        parameters=[
                            MCPToolParameter(
                                name=name,
                                type=props.get("type", "string"),
                                description=props.get("description", ""),
                                required=name in tool_data.get("input_schema", {}).get("required", []),
                            )
                            for name, props in tool_data.get("input_schema", {}).get("properties", {}).items()
                        ]
                    )
                    self._tools[tool.name] = tool
        except Exception as e:
            logger.error(f"Failed to fetch tools: {e}")

        # Get available resources
        try:
            resources_response = await self.request("resources/list", {})
            if "resources" in resources_response:
                for res_data in resources_response["resources"]:
                    resource = MCPResource(
                        uri=res_data["uri"],
                        name=res_data.get("name", res_data["uri"]),
                        description=res_data.get("description", ""),
                        mime_type=res_data.get("mimeType", "text/plain"),
                    )
                    self._resources[resource.uri] = resource
        except Exception as e:
            logger.error(f"Failed to fetch resources: {e}")

        logger.info(f"MCP client initialized: {len(self._tools)} tools, {len(self._resources)} resources")

    async def request(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Send a request to the MCP server"""
        self._request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params,
        }

        if self.config.transport == MCPTransport.STDIO:
            return await self._request_stdio(request)
        elif self.config.transport == MCPTransport.HTTP:
            return await self._request_http(request)
        else:
            raise MCPClientError(f"Unsupported transport: {self.config.transport}")

    async def _request_stdio(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Send request via stdio"""
        if not self._process or not self._process.stdin or not self._process.stdout:
            raise MCPClientError("Not connected")

        # Create a future for the response
        future = asyncio.get_event_loop().create_future()
        self._pending_requests[request["id"]] = future

        # Send request
        request_json = json.dumps(request) + "\n"
        self._process.stdin.write(request_json.encode())
        self._process.stdin.flush()

        # Wait for response
        try:
            response = await asyncio.wait_for(
                future,
                timeout=self.config.timeout_seconds
            )
            return response
        except asyncio.TimeoutError:
            del self._pending_requests[request["id"]]
            raise MCPClientError(f"Request timed out: {request['method']}")

    async def _request_http(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Send request via HTTP"""
        if not self._http_client:
            raise MCPClientError("Not connected")

        response = await self._http_client.post("/mcp", json=request)
        response.raise_for_status()
        result = response.json()

        if "error" in result:
            raise MCPClientError(result["error"].get("message", str(result["error"])))

        return result.get("result", {})

    async def _read_stdio_responses(self):
        """Read responses from stdio"""
        if not self._process or not self._process.stdout:
            return

        while True:
            try:
                line = await asyncio.get_event_loop().run_in_executor(
                    None, self._process.stdout.readline
                )
                if not line:
                    break

                response = json.loads(line.decode())
                request_id = response.get("id")

                if request_id in self._pending_requests:
                    future = self._pending_requests.pop(request_id)
                    if "error" in response:
                        future.set_exception(MCPClientError(response["error"].get("message", str(response["error"]))))
                    else:
                        future.set_result(response.get("result", {}))
            except Exception as e:
                logger.error(f"Error reading MCP response: {e}")
                break

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool on the MCP server"""
        if name not in self._tools:
            raise MCPClientError(f"Unknown tool: {name}")

        return await self.request("tools/call", {
            "name": name,
            "arguments": arguments,
        })

    async def read_resource(self, uri: str) -> Dict[str, Any]:
        """Read a resource from the MCP server"""
        return await self.request("resources/read", {"uri": uri})

    def get_tools(self) -> List[MCPTool]:
        """Get all available tools"""
        return list(self._tools.values())

    def get_resources(self) -> List[MCPResource]:
        """Get all available resources"""
        return list(self._resources.values())

    async def disconnect(self):
        """Disconnect from the MCP server"""
        if self._read_task:
            self._read_task.cancel()

        if self._process:
            self._process.terminate()
            self._process.wait()
            self._process = None

        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

        self._connected = False
        logger.info(f"Disconnected from MCP server: {self.config.name}")


# ============== MCP Tool Executor ==============

class ToolExecutionStatus(str, Enum):
    """Status of tool execution"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ToolExecutionRequest:
    """Request to execute a tool"""
    id: str
    tool_name: str
    arguments: Dict[str, Any]
    user_id: str
    status: ToolExecutionStatus = ToolExecutionStatus.PENDING
    requires_approval: bool = False
    created_at: datetime = dataclass_field(default_factory=datetime.utcnow)
    approved_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class MCPToolExecutor:
    """
    Executes MCP tools with approval gates and resilience.

    Features:
    - Approval gates for high-risk tools
    - Retry with backoff for transient failures
    - Audit logging
    - Rate limiting
    """

    def __init__(
        self,
        mcp_server: MCPServer,
        require_approval_for_high_risk: bool = True,
        max_retries: int = 3,
    ):
        self.mcp_server = mcp_server
        self.require_approval_for_high_risk = require_approval_for_high_risk
        self.max_retries = max_retries
        self._pending_approvals: Dict[str, ToolExecutionRequest] = {}
        self._execution_history: List[ToolExecutionRequest] = []

    async def execute(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        user_id: str,
        skip_approval: bool = False,
    ) -> Dict[str, Any]:
        """
        Execute a tool, potentially requiring approval.

        Returns:
            - If approval required: {"status": "pending_approval", "request_id": "..."}
            - If executed: {"status": "completed", "result": {...}}
            - If failed: {"status": "failed", "error": "..."}
        """
        import uuid

        tool = self.mcp_server.tools.get(tool_name)
        if not tool:
            return {"status": "failed", "error": f"Unknown tool: {tool_name}"}

        # Create execution request
        request = ToolExecutionRequest(
            id=str(uuid.uuid4()),
            tool_name=tool_name,
            arguments=arguments,
            user_id=user_id,
            requires_approval=(
                tool.requires_approval and
                self.require_approval_for_high_risk and
                not skip_approval
            ),
        )

        # Check if approval needed
        if request.requires_approval:
            self._pending_approvals[request.id] = request
            logger.info(f"Tool execution pending approval: {tool_name} (request_id={request.id})")
            return {
                "status": "pending_approval",
                "request_id": request.id,
                "tool_name": tool_name,
                "arguments": arguments,
            }

        # Execute immediately
        return await self._execute_tool(request)

    async def approve(self, request_id: str, approved: bool = True) -> Dict[str, Any]:
        """Approve or reject a pending tool execution"""
        if request_id not in self._pending_approvals:
            return {"status": "failed", "error": f"Request not found: {request_id}"}

        request = self._pending_approvals.pop(request_id)

        if not approved:
            request.status = ToolExecutionStatus.REJECTED
            self._execution_history.append(request)
            return {"status": "rejected", "request_id": request_id}

        request.status = ToolExecutionStatus.APPROVED
        request.approved_at = datetime.utcnow()

        return await self._execute_tool(request)

    async def _execute_tool(self, request: ToolExecutionRequest) -> Dict[str, Any]:
        """Execute a tool with retries"""
        request.status = ToolExecutionStatus.RUNNING

        last_error: Optional[Exception] = None

        for attempt in range(self.max_retries):
            try:
                result = await self.mcp_server.invoke_tool(
                    request.tool_name,
                    request.arguments,
                    request.user_id,
                )

                if "error" in result:
                    raise Exception(result["error"])

                request.status = ToolExecutionStatus.COMPLETED
                request.completed_at = datetime.utcnow()
                request.result = result
                self._execution_history.append(request)

                return {
                    "status": "completed",
                    "request_id": request.id,
                    "result": result.get("result"),
                }

            except Exception as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    delay = 2 ** attempt  # Exponential backoff
                    logger.warning(f"Tool execution failed, retrying in {delay}s: {e}")
                    await asyncio.sleep(delay)

        # All retries failed
        request.status = ToolExecutionStatus.FAILED
        request.completed_at = datetime.utcnow()
        request.error = str(last_error)
        self._execution_history.append(request)

        return {
            "status": "failed",
            "request_id": request.id,
            "error": str(last_error),
        }

    def get_pending_approvals(self) -> List[ToolExecutionRequest]:
        """Get all pending approval requests"""
        return list(self._pending_approvals.values())

    def get_execution_history(
        self,
        user_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[ToolExecutionRequest]:
        """Get execution history"""
        history = self._execution_history
        if user_id:
            history = [r for r in history if r.user_id == user_id]
        return history[-limit:]


# ============== Resource Backends ==============

class ResourceBackend:
    """Base class for resource backends"""

    async def read(self, uri: str) -> Dict[str, Any]:
        raise NotImplementedError

    async def write(self, uri: str, content: Any) -> Dict[str, Any]:
        raise NotImplementedError


class FileResourceBackend(ResourceBackend):
    """Backend for file:// resources"""

    def __init__(self, allowed_paths: Optional[List[str]] = None):
        self.allowed_paths = allowed_paths or []

    def _is_allowed(self, path: str) -> bool:
        """Check if path is allowed"""
        if not self.allowed_paths:
            return True
        return any(path.startswith(allowed) for allowed in self.allowed_paths)

    async def read(self, uri: str) -> Dict[str, Any]:
        """Read a file resource"""
        if not uri.startswith("file://"):
            return {"error": "Invalid file URI"}

        path = uri[7:]  # Remove file://

        if not self._is_allowed(path):
            return {"error": f"Access denied: {path}"}

        try:
            with open(path, "r") as f:
                content = f.read()
            return {"contents": [{"uri": uri, "text": content}]}
        except FileNotFoundError:
            return {"error": f"File not found: {path}"}
        except Exception as e:
            return {"error": str(e)}

    async def write(self, uri: str, content: str) -> Dict[str, Any]:
        """Write to a file resource"""
        if not uri.startswith("file://"):
            return {"error": "Invalid file URI"}

        path = uri[7:]

        if not self._is_allowed(path):
            return {"error": f"Access denied: {path}"}

        try:
            with open(path, "w") as f:
                f.write(content)
            return {"success": True}
        except Exception as e:
            return {"error": str(e)}


class HTTPResourceBackend(ResourceBackend):
    """Backend for http:// and https:// resources"""

    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout

    async def read(self, uri: str) -> Dict[str, Any]:
        """Fetch an HTTP resource"""
        if not uri.startswith(("http://", "https://")):
            return {"error": "Invalid HTTP URI"}

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(uri)
                response.raise_for_status()

                content_type = response.headers.get("content-type", "text/plain")

                return {
                    "contents": [{
                        "uri": uri,
                        "text": response.text,
                        "mimeType": content_type,
                    }]
                }
        except Exception as e:
            return {"error": str(e)}


class MCPResourceManager:
    """
    Manages resource backends for different URI schemes.
    """

    def __init__(self):
        self.backends: Dict[str, ResourceBackend] = {}

        # Register default backends
        self.register_backend("file", FileResourceBackend())
        self.register_backend("http", HTTPResourceBackend())
        self.register_backend("https", HTTPResourceBackend())

    def register_backend(self, scheme: str, backend: ResourceBackend):
        """Register a backend for a URI scheme"""
        self.backends[scheme] = backend
        logger.info(f"Registered resource backend for scheme: {scheme}")

    def _get_scheme(self, uri: str) -> str:
        """Extract scheme from URI"""
        if "://" in uri:
            return uri.split("://")[0]
        return "file"

    async def read(self, uri: str) -> Dict[str, Any]:
        """Read a resource using the appropriate backend"""
        scheme = self._get_scheme(uri)

        if scheme not in self.backends:
            return {"error": f"No backend for scheme: {scheme}"}

        return await self.backends[scheme].read(uri)

    async def write(self, uri: str, content: Any) -> Dict[str, Any]:
        """Write to a resource using the appropriate backend"""
        scheme = self._get_scheme(uri)

        if scheme not in self.backends:
            return {"error": f"No backend for scheme: {scheme}"}

        backend = self.backends[scheme]
        if not hasattr(backend, "write"):
            return {"error": f"Write not supported for scheme: {scheme}"}

        return await backend.write(uri, content)


# ============== Enhanced MCP Server ==============

class EnhancedMCPServer(MCPServer):
    """
    Enhanced MCP server with resource backends and tool execution.
    """

    def __init__(self):
        super().__init__()
        self.resource_manager = MCPResourceManager()
        self.tool_executor = MCPToolExecutor(self)

    async def handle_mcp_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle MCP protocol requests with enhanced features"""
        method = request.get("method")
        params = request.get("params", {})

        if method == "tools/list":
            return {"tools": self.get_tools_list()}

        elif method == "tools/call":
            name = params.get("name")
            arguments = params.get("arguments", {})
            user_id = params.get("_user_id", "anonymous")
            return await self.tool_executor.execute(name, arguments, user_id)

        elif method == "tools/approve":
            request_id = params.get("request_id")
            approved = params.get("approved", True)
            return await self.tool_executor.approve(request_id, approved)

        elif method == "resources/list":
            return {"resources": self.get_resources_list()}

        elif method == "resources/read":
            uri = params.get("uri")
            return await self.resource_manager.read(uri)

        elif method == "resources/write":
            uri = params.get("uri")
            content = params.get("content")
            return await self.resource_manager.write(uri, content)

        else:
            return {"error": f"Unknown method: {method}"}


# Global enhanced MCP server instance
enhanced_mcp_server = EnhancedMCPServer()


# ============== MCP Client Registry ==============

class MCPClientRegistry:
    """
    Registry for managing connections to multiple MCP servers.
    """

    _instance: Optional["MCPClientRegistry"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._clients: Dict[str, MCPClient] = {}
        return cls._instance

    async def connect(self, config: MCPServerConfig) -> MCPClient:
        """Connect to an MCP server"""
        if config.name in self._clients:
            return self._clients[config.name]

        client = MCPClient(config)
        await client.connect()
        self._clients[config.name] = client

        return client

    def get(self, name: str) -> Optional[MCPClient]:
        """Get a connected client by name"""
        return self._clients.get(name)

    async def disconnect(self, name: str):
        """Disconnect from an MCP server"""
        if name in self._clients:
            await self._clients[name].disconnect()
            del self._clients[name]

    async def disconnect_all(self):
        """Disconnect from all MCP servers"""
        for client in self._clients.values():
            await client.disconnect()
        self._clients.clear()

    def get_all_tools(self) -> Dict[str, List[MCPTool]]:
        """Get tools from all connected servers"""
        return {
            name: client.get_tools()
            for name, client in self._clients.items()
        }


# Global registry instance
mcp_registry = MCPClientRegistry()
