"""
MCP Server Registry

Central management for all MCP (Model Context Protocol) servers.
Supports both subprocess-based servers (npm packages) and HTTP-based servers.

NOTE: Every entry in SERVERS must be a real, runnable package — startable via
`npx -y <pkg>` in the runtime image (the image ships node/npx only; no uvx).
`capabilities` lists are DECLARED, not discovered: they describe what the
upstream package is expected to expose. The authoritative tool list comes from
the server itself (tools/list) once it is started.
"""

import os
import asyncio
import subprocess
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum

# Import MCPClient for proper protocol handling
from app.protocols.mcp import (
    MCPClient,
    MCPServerConfig,
    MCPTransport as ProtocolMCPTransport
)

logger = logging.getLogger(__name__)


class MCPTransport(Enum):
    """MCP transport types (registry-level enum, maps to protocol enum)"""
    STDIO = "stdio"
    SSE = "sse"
    HTTP = "http"


@dataclass
class MCPServer:
    """MCP Server configuration"""
    name: str
    display_name: str
    command: str
    args: List[str]
    env: Dict[str, str] = field(default_factory=dict)
    capabilities: List[str] = field(default_factory=list)
    transport: MCPTransport = MCPTransport.STDIO
    port: Optional[int] = None
    description: str = ""
    enabled: bool = True

    def get_env(self) -> Dict[str, str]:
        """Get environment variables with substitutions"""
        result = {**os.environ}
        for key, value in self.env.items():
            if value.startswith("${") and value.endswith("}"):
                env_var = value[2:-1]
                result[key] = os.getenv(env_var, "")
            else:
                result[key] = value
        return result


class MCPRegistry:
    """
    Central registry for MCP servers.
    Manages lifecycle of MCP server processes.
    """

    # Built-in MCP server definitions.
    # Only verified, npx-runnable packages belong here; capabilities are
    # declared (see module docstring), so keep them short and realistic.
    SERVERS: Dict[str, MCPServer] = {
        "github": MCPServer(
            name="github",
            display_name="GitHub",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-github"],
            env={"GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_TOKEN}"},
            capabilities=[
                "create_repository", "create_branch", "create_or_update_file",
                "create_issue", "get_issue", "list_issues", "add_issue_comment",
                "create_pull_request", "get_pull_request", "list_pull_requests",
                "merge_pull_request", "search_code", "search_issues",
                "search_repositories", "get_file_contents", "list_commits"
            ],
            description="GitHub repository management - commits, PRs, issues, code search"
        ),

        "filesystem": MCPServer(
            name="filesystem",
            display_name="Filesystem",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-filesystem", "${WORKSPACE_PATH:-/workspace}"],
            capabilities=["read_file", "write_file", "list_directory", "search_files", "move_file", "get_file_info"],
            description="Local filesystem operations - read, write, search files"
        ),

        "postgres": MCPServer(
            name="postgres",
            display_name="PostgreSQL",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-postgres", "${DATABASE_URL}"],
            capabilities=["query", "list_tables", "describe_table", "list_schemas"],
            description="PostgreSQL database - schema inspection and read-only queries"
        ),

        "playwright": MCPServer(
            name="playwright",
            display_name="Playwright Browser",
            command="npx",
            args=["-y", "@playwright/mcp@latest", "--headless"],
            capabilities=[
                "browser_navigate", "browser_click", "browser_type", "browser_fill_form",
                "browser_snapshot", "browser_take_screenshot", "browser_select_option",
                "browser_hover", "browser_press_key", "browser_wait_for",
                "browser_evaluate", "browser_close"
            ],
            description="Browser automation via accessibility tree - fast, reliable"
        ),

        "slack": MCPServer(
            name="slack",
            display_name="Slack",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-slack"],
            env={
                "SLACK_BOT_TOKEN": "${SLACK_BOT_TOKEN}",
                "SLACK_TEAM_ID": "${SLACK_TEAM_ID}",
            },
            capabilities=[
                "slack_list_channels", "slack_post_message", "slack_reply_to_thread",
                "slack_add_reaction", "slack_get_channel_history",
                "slack_get_thread_replies", "slack_get_users", "slack_get_user_profile"
            ],
            description="Slack workspace - channels, messages, threads, reactions"
        ),

        "memory": MCPServer(
            name="memory",
            display_name="Memory",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-memory"],
            capabilities=[
                "create_entities", "create_relations", "add_observations",
                "delete_entities", "delete_observations", "delete_relations",
                "read_graph", "search_nodes", "open_nodes"
            ],
            description="Persistent knowledge-graph memory - entities, relations, observations"
        ),

        "brave-search": MCPServer(
            name="brave-search",
            display_name="Brave Search",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-brave-search"],
            env={"BRAVE_API_KEY": "${BRAVE_API_KEY}"},
            capabilities=["brave_web_search", "brave_local_search"],
            description="Brave Search API for web searches"
        ),

        "google-drive": MCPServer(
            name="google-drive",
            display_name="Google Drive",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-gdrive"],
            env={"GDRIVE_CREDENTIALS_PATH": "${GDRIVE_CREDENTIALS_PATH}"},
            capabilities=["search"],
            description="Google Drive - file search; file contents exposed as MCP resources"
        ),

        "puppeteer": MCPServer(
            name="puppeteer",
            display_name="Puppeteer",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-puppeteer"],
            capabilities=[
                "puppeteer_navigate", "puppeteer_screenshot", "puppeteer_click",
                "puppeteer_fill", "puppeteer_select", "puppeteer_hover", "puppeteer_evaluate"
            ],
            description="Puppeteer browser control (alternative to Playwright)"
        ),

        "stripe": MCPServer(
            name="stripe",
            display_name="Stripe Payments",
            command="npx",
            # @stripe/mcp is the runnable MCP server from Stripe's agent toolkit
            # (@stripe/agent-toolkit itself ships no executable).
            args=["-y", "@stripe/mcp", "--tools=all"],
            env={"STRIPE_SECRET_KEY": "${STRIPE_API_KEY}"},
            capabilities=[
                "create_customer", "list_customers",
                "create_product", "list_products",
                "create_price", "list_prices",
                "create_payment_link",
                "create_invoice", "create_invoice_item", "finalize_invoice",
                "list_payment_intents", "list_subscriptions",
                "update_subscription", "cancel_subscription",
                "create_refund", "retrieve_balance"
            ],
            description="Stripe payment processing - customers, products, invoices, subscriptions, refunds"
        ),

        "notion": MCPServer(
            name="notion",
            display_name="Notion Workspace",
            command="npx",
            args=["-y", "@notionhq/notion-mcp-server"],
            env={
                "NOTION_API_KEY": "${NOTION_API_KEY}",
                "NOTION_VERSION": "2022-06-28"
            },
            capabilities=[
                "create_page", "update_page", "retrieve_page",
                "create_database", "update_database", "query_database", "retrieve_database",
                "search", "list_users", "retrieve_user",
                "append_block_children", "retrieve_block_children",
                "create_comment", "retrieve_comments"
            ],
            description="Notion workspace - pages, databases, search, comments"
        ),
    }

    def __init__(self):
        self.running_servers: Dict[str, MCPClient] = {}  # Changed from subprocess.Popen to MCPClient
        self.server_outputs: Dict[str, List[str]] = {}
        self._lock = asyncio.Lock()

    def register_server(self, server: MCPServer) -> None:
        """Register a new MCP server"""
        self.SERVERS[server.name] = server
        logger.info(f"Registered MCP server: {server.name}")

    def unregister_server(self, name: str) -> bool:
        """Unregister an MCP server"""
        if name in self.SERVERS:
            del self.SERVERS[name]
            logger.info(f"Unregistered MCP server: {name}")
            return True
        return False

    async def start_server(self, name: str) -> bool:
        """Start an MCP server by name using MCPClient"""
        async with self._lock:
            if name not in self.SERVERS:
                logger.error(f"MCP server not found: {name}")
                return False

            if name in self.running_servers:
                logger.warning(f"MCP server already running: {name}")
                return True

            server = self.SERVERS[name]
            if not server.enabled:
                logger.warning(f"MCP server disabled: {name}")
                return False

            try:
                # Substitute environment variables in args
                args = []
                for arg in server.args:
                    if arg.startswith("${") and arg.endswith("}"):
                        # Handle default values: ${VAR:-default}
                        if ":-" in arg:
                            var_part, default = arg[2:-1].split(":-", 1)
                            args.append(os.getenv(var_part, default))
                        else:
                            args.append(os.getenv(arg[2:-1], ""))
                    else:
                        args.append(arg)

                # Convert registry MCPTransport to protocol MCPTransport
                if server.transport == MCPTransport.STDIO:
                    transport = ProtocolMCPTransport.STDIO
                elif server.transport == MCPTransport.HTTP or server.transport == MCPTransport.SSE:
                    transport = ProtocolMCPTransport.HTTP
                else:
                    transport = ProtocolMCPTransport.STDIO  # Default

                # Create MCPClient configuration
                config = MCPServerConfig(
                    name=server.name,
                    transport=transport,
                    command=server.command,
                    args=args,
                    env=server.get_env(),
                    url=f"http://localhost:{server.port}" if server.port else None,
                    timeout_seconds=60.0  # Increased timeout for npm package downloads on first run
                )

                # Create and connect MCPClient
                client = MCPClient(config)
                await client.connect()  # This will initialize and fetch tools

                self.running_servers[name] = client
                self.server_outputs[name] = []

                logger.info(f"Started MCP server: {name} ({len(client.get_tools())} tools available)")
                return True

            except Exception as e:
                logger.error(f"Failed to start MCP server {name}: {e}")
                return False

    async def stop_server(self, name: str) -> bool:
        """Stop a running MCP server"""
        async with self._lock:
            if name not in self.running_servers:
                return False

            client = self.running_servers[name]
            try:
                # Disconnect MCPClient (this will terminate the subprocess if STDIO)
                await client.disconnect()
            except Exception as e:
                logger.warning(f"Error disconnecting MCP server {name}: {e}")

            del self.running_servers[name]
            if name in self.server_outputs:
                del self.server_outputs[name]

            logger.info(f"Stopped MCP server: {name}")
            return True

    async def stop_all(self) -> None:
        """Stop all running MCP servers"""
        for name in list(self.running_servers.keys()):
            await self.stop_server(name)

    def is_running(self, name: str) -> bool:
        """Check if a server is running"""
        if name not in self.running_servers:
            return False
        client = self.running_servers[name]
        return client._connected  # Check if MCPClient is connected

    def list_available(self) -> List[Dict[str, Any]]:
        """List all available MCP servers"""
        return [
            {
                "name": name,
                "display_name": server.display_name,
                "description": server.description,
                "capabilities": server.capabilities,
                "transport": server.transport.value,
                "enabled": server.enabled,
                "running": self.is_running(name),
            }
            for name, server in self.SERVERS.items()
        ]

    def list_running(self) -> List[Dict[str, Any]]:
        """List running MCP servers"""
        running = []
        for name, client in self.running_servers.items():
            if not client._connected:
                continue
            # MCPClient holds a subprocess.Popen in _process for STDIO
            # transport (None for HTTP transport).
            process = client._process
            if process is not None and process.poll() is not None:
                continue  # subprocess has exited
            server = self.SERVERS.get(name)
            running.append({
                "name": name,
                "display_name": server.display_name if server else name,
                "pid": process.pid if process else None,
                "capabilities": server.capabilities if server else [],
            })
        return running

    def get_server(self, name: str) -> Optional[MCPServer]:
        """Get server configuration by name"""
        return self.SERVERS.get(name)

    async def call_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call a tool on an MCP server using MCPClient.

        The MCPClient handles all transport details (STDIO, HTTP, WebSocket)
        and implements proper MCP protocol (initialize, tools/list, tools/call).
        """
        if server_name not in self.running_servers:
            # Auto-start server if not running
            if not await self.start_server(server_name):
                return {"error": f"Failed to start server: {server_name}"}

        client = self.running_servers[server_name]

        try:
            # Use MCPClient's call_tool method (handles all transports)
            result = await client.call_tool(tool_name, arguments)
            return result
        except Exception as e:
            logger.error(f"Error calling tool {tool_name} on {server_name}: {e}")
            return {"error": str(e)}

    # Note: _call_stdio() and _call_http() removed - MCPClient handles all transports


# Global registry instance
mcp_registry = MCPRegistry()
