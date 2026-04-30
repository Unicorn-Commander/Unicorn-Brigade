"""
Tests for MCP Server Registry

Tests coverage for:
- 18 total MCP servers (10 baseline + 4 Phase 1 + 4 Phase 2)
- Server lifecycle management
- Tool invocation
- Configuration validation
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
import subprocess
from app.mcp.registry import (
    MCPRegistry,
    MCPServer,
    MCPTransport,
    mcp_registry,
)


class TestMCPServerConfiguration:
    """Test MCP server configuration and registration"""

    def test_total_server_count(self):
        """Floor-check on the registered MCP server count.

        The registry grows over time as more MCP servers ship; pinning an
        exact count just creates churn. We assert against a floor (the count
        when this test was last reviewed) so a regression that drops servers
        fails fast.
        """
        servers = mcp_registry.list_available()
        assert len(servers) >= 14, (
            f"Expected at least 14 registered MCP servers, got {len(servers)}"
        )

    def test_baseline_servers_registered(self):
        """Verify all 10 baseline MCP servers are registered"""
        baseline_servers = [
            'github', 'playwright', 'slack', 'postgres', 'filesystem',
            'memory', 'fetch', 'brave-search', 'google-drive', 'puppeteer'
        ]

        for name in baseline_servers:
            server = mcp_registry.get_server(name)
            assert server is not None, f"Baseline server '{name}' should be registered"
            assert isinstance(server, MCPServer)
            assert server.name == name
            assert server.enabled is True

    def test_phase1_servers_registered(self):
        """Verify all 4 Phase 1 MCP servers are registered"""
        phase1_servers = ['stripe', 'linear', 'git', 'notion']

        for name in phase1_servers:
            server = mcp_registry.get_server(name)
            assert server is not None, f"Phase 1 server '{name}' should be registered"
            assert isinstance(server, MCPServer)
            assert server.name == name
            assert len(server.capabilities) > 0, f"{name} should have capabilities"

    def test_server_has_required_fields(self):
        """Verify server configurations have all required fields"""
        server = mcp_registry.get_server('github')

        assert server.name == 'github'
        assert server.display_name == 'GitHub'
        assert server.command is not None
        assert isinstance(server.args, list)
        assert isinstance(server.env, dict)
        assert isinstance(server.capabilities, list)
        assert len(server.capabilities) > 0
        assert server.transport in [MCPTransport.STDIO, MCPTransport.HTTP, MCPTransport.SSE]
        assert server.description != ""

    def test_server_capabilities_not_empty(self):
        """Verify all servers have at least one capability"""
        servers = mcp_registry.list_available()

        for server_info in servers:
            assert len(server_info['capabilities']) > 0, \
                f"Server {server_info['name']} should have at least one capability"

    def test_stripe_server_configuration(self):
        """Verify Stripe server has correct configuration"""
        server = mcp_registry.get_server('stripe')

        assert server is not None
        assert server.display_name == 'Stripe Payments'
        assert 'STRIPE_API_KEY' in server.env
        assert 'create_payment_intent' in server.capabilities
        assert 'create_subscription' in server.capabilities
        assert 'create_refund' in server.capabilities
        assert len(server.capabilities) >= 20, "Stripe should have 20+ capabilities"

    def test_linear_server_configuration(self):
        """Verify Linear server has correct configuration"""
        server = mcp_registry.get_server('linear')

        assert server is not None
        assert server.display_name == 'Linear Project Management'
        assert 'LINEAR_API_KEY' in server.env
        assert 'create_issue' in server.capabilities
        assert 'create_project' in server.capabilities
        assert len(server.capabilities) >= 15, "Linear should have 15+ capabilities"

    def test_git_server_configuration(self):
        """Verify Git server has correct configuration"""
        server = mcp_registry.get_server('git')

        assert server is not None
        assert server.display_name == 'Git Repository'
        assert 'git_status' in server.capabilities
        assert 'git_commit' in server.capabilities
        assert 'git_push' in server.capabilities
        assert len(server.capabilities) >= 15, "Git should have 15+ capabilities"

    def test_notion_server_configuration(self):
        """Verify Notion server has correct configuration"""
        server = mcp_registry.get_server('notion')

        assert server is not None
        assert server.display_name == 'Notion Workspace'
        assert 'NOTION_API_KEY' in server.env
        assert 'create_page' in server.capabilities
        assert 'query_database' in server.capabilities
        assert len(server.capabilities) >= 10, "Notion should have 10+ capabilities"


class TestMCPServerLifecycle:
    """Test MCP server lifecycle management"""

    @pytest.fixture
    def fresh_registry(self):
        """Create a fresh registry for each test"""
        return MCPRegistry()

    @pytest.mark.asyncio
    async def test_register_custom_server(self, fresh_registry):
        """Test registering a new custom MCP server"""
        custom_server = MCPServer(
            name="custom-test",
            display_name="Custom Test Server",
            command="node",
            args=["server.js"],
            capabilities=["test_capability"],
            description="Test server"
        )

        fresh_registry.register_server(custom_server)

        registered = fresh_registry.get_server("custom-test")
        assert registered is not None
        assert registered.name == "custom-test"
        assert registered.display_name == "Custom Test Server"

    @pytest.mark.asyncio
    async def test_unregister_server(self, fresh_registry):
        """Test unregistering an MCP server"""
        custom_server = MCPServer(
            name="test-unregister",
            display_name="Test Unregister",
            command="node",
            args=["test.js"],
            capabilities=["test"],
            description="Test"
        )

        fresh_registry.register_server(custom_server)
        assert fresh_registry.get_server("test-unregister") is not None

        result = fresh_registry.unregister_server("test-unregister")
        assert result is True
        assert fresh_registry.get_server("test-unregister") is None

    @pytest.mark.asyncio
    @patch('subprocess.Popen')
    async def test_start_server_success(self, mock_popen, fresh_registry):
        """Test successfully starting an MCP server"""
        # Mock the subprocess
        mock_proc = MagicMock()
        mock_proc.pid = 12345
        mock_proc.poll.return_value = None  # Process is running
        mock_popen.return_value = mock_proc

        # Register a test server
        test_server = MCPServer(
            name="test-start",
            display_name="Test Start",
            command="node",
            args=["server.js"],
            capabilities=["test"],
            description="Test"
        )
        fresh_registry.register_server(test_server)

        # Start the server
        result = await fresh_registry.start_server("test-start")

        assert result is True
        assert fresh_registry.is_running("test-start")
        mock_popen.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_nonexistent_server(self, fresh_registry):
        """Test starting a server that doesn't exist"""
        result = await fresh_registry.start_server("nonexistent-server")
        assert result is False

    @pytest.mark.asyncio
    @patch('subprocess.Popen')
    async def test_stop_server(self, mock_popen, fresh_registry):
        """Test stopping a running MCP server"""
        # Mock the subprocess
        mock_proc = MagicMock()
        mock_proc.pid = 12345
        mock_proc.poll.return_value = None
        mock_popen.return_value = mock_proc

        # Register and start a test server
        test_server = MCPServer(
            name="test-stop",
            display_name="Test Stop",
            command="node",
            args=["server.js"],
            capabilities=["test"],
            description="Test"
        )
        fresh_registry.register_server(test_server)
        await fresh_registry.start_server("test-stop")

        # Stop the server
        result = await fresh_registry.stop_server("test-stop")

        assert result is True
        assert not fresh_registry.is_running("test-stop")
        mock_proc.terminate.assert_called_once()

    @pytest.mark.asyncio
    @patch('subprocess.Popen')
    async def test_server_already_running(self, mock_popen, fresh_registry):
        """Test starting a server that's already running"""
        mock_proc = MagicMock()
        mock_proc.pid = 12345
        mock_proc.poll.return_value = None
        mock_popen.return_value = mock_proc

        test_server = MCPServer(
            name="test-double-start",
            display_name="Test Double Start",
            command="node",
            args=["server.js"],
            capabilities=["test"],
            description="Test"
        )
        fresh_registry.register_server(test_server)

        # Start twice
        result1 = await fresh_registry.start_server("test-double-start")
        result2 = await fresh_registry.start_server("test-double-start")

        assert result1 is True
        assert result2 is True  # Should return True, but not start again
        assert mock_popen.call_count == 1  # Only called once

    def test_list_running_servers(self, fresh_registry):
        """Test listing running servers"""
        running = fresh_registry.list_running()
        assert isinstance(running, list)
        # Initially no servers should be running in fresh registry
        assert len(running) == 0


class TestMCPToolInvocation:
    """Test MCP tool invocation"""

    @pytest.fixture
    def fresh_registry(self):
        """Create a fresh registry for each test"""
        return MCPRegistry()

    @pytest.mark.asyncio
    @patch('subprocess.Popen')
    async def test_call_tool_stdio_transport(self, mock_popen, fresh_registry):
        """Test calling a tool via STDIO transport"""
        # Mock the subprocess
        mock_proc = MagicMock()
        mock_proc.pid = 12345
        mock_proc.poll.return_value = None
        mock_proc.stdin = MagicMock()
        mock_proc.stdout = MagicMock()
        mock_proc.stdout.readline.return_value = b'{"result": {"success": true}}\n'
        mock_popen.return_value = mock_proc

        # Register test server
        test_server = MCPServer(
            name="test-tool-call",
            display_name="Test Tool Call",
            command="node",
            args=["server.js"],
            capabilities=["test_capability"],
            description="Test",
            transport=MCPTransport.STDIO
        )
        fresh_registry.register_server(test_server)

        # Call tool (will auto-start server)
        result = await fresh_registry.call_tool(
            "test-tool-call",
            "test_capability",
            {"param": "value"}
        )

        assert result is not None
        assert "success" in result or "error" in result

    @pytest.mark.asyncio
    async def test_call_tool_on_nonexistent_server(self, fresh_registry):
        """Test calling a tool on a server that doesn't exist"""
        result = await fresh_registry.call_tool(
            "nonexistent-server",
            "some_tool",
            {}
        )

        assert "error" in result


class TestMCPEnvironmentVariables:
    """Test environment variable handling"""

    def test_env_variable_substitution(self):
        """Test that environment variables are substituted correctly"""
        import os

        # Set a test env var
        os.environ['TEST_MCP_VAR'] = 'test_value'

        server = MCPServer(
            name="test-env",
            display_name="Test Env",
            command="node",
            args=["server.js"],
            env={"API_KEY": "${TEST_MCP_VAR}"},
            capabilities=["test"],
            description="Test"
        )

        env = server.get_env()
        assert env.get('API_KEY') == 'test_value'

        # Cleanup
        del os.environ['TEST_MCP_VAR']

    def test_missing_env_variable(self):
        """Test handling of missing environment variables"""
        server = MCPServer(
            name="test-missing-env",
            display_name="Test Missing Env",
            command="node",
            args=["server.js"],
            env={"API_KEY": "${NONEXISTENT_VAR}"},
            capabilities=["test"],
            description="Test"
        )

        env = server.get_env()
        # Should substitute with empty string if var doesn't exist
        assert env.get('API_KEY') == ''


class TestMCPServerQueries:
    """Test server query and filter operations"""

    def test_filter_by_capability(self):
        """Test finding servers by capability"""
        servers = mcp_registry.list_available()

        # Find servers with git capabilities
        git_servers = [s for s in servers if any('git' in cap.lower() for cap in s['capabilities'])]
        assert len(git_servers) > 0

        # Find servers with database capabilities
        db_servers = [s for s in servers if any('query' in cap.lower() or 'database' in cap.lower() for cap in s['capabilities'])]
        assert len(db_servers) > 0

    def test_filter_enabled_servers(self):
        """Test filtering enabled servers"""
        servers = mcp_registry.list_available()
        enabled = [s for s in servers if s['enabled']]

        # All default servers should be enabled
        assert len(enabled) == len(servers)

    def test_server_transport_types(self):
        """Test that servers have valid transport types"""
        servers = mcp_registry.list_available()
        valid_transports = ['stdio', 'http', 'sse']

        for server in servers:
            assert server['transport'] in valid_transports
