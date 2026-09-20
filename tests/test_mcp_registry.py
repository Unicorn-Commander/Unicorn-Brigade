# Executed by Grok (headless lane)
"""
Tests for MCP Server Registry

Tests coverage for:
- 18 total MCP servers (10 baseline + 4 Phase 1 + 4 Phase 2)
- Server lifecycle management
- Tool invocation
- Configuration validation
"""

import subprocess
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from app.mcp.registry import (
    MCPRegistry,
    MCPServer,
    MCPTransport,
    mcp_registry,
)


def _fake_mcp_client() -> MagicMock:
    """MCPClient stand-in so lifecycle tests never spawn npx."""
    client = MagicMock()
    client._connected = True
    client.get_tools.return_value = []
    client.connect = AsyncMock()
    client.disconnect = AsyncMock()
    process = MagicMock()
    process.pid = 12345
    process.poll.return_value = None
    client._process = process
    return client


class TestMCPServerConfiguration:
    """Test MCP server configuration and registration"""

    def test_total_server_count(self):
        """Exact npx-verified MCP set from 0d83ea89a903cbb7b2664855f4f76928371d2d99.

        That commit pruned the registry 46→11 npm-verified servers. A floor
        would accept a silent drop or an accidental re-add.
        """
        expected_servers = (
            "github",
            "filesystem",
            "postgres",
            "playwright",
            "slack",
            "memory",
            "brave-search",
            "google-drive",
            "puppeteer",
            "stripe",
            "notion",
        )
        actual = tuple(sorted(s["name"] for s in mcp_registry.list_available()))
        assert actual == tuple(sorted(expected_servers))
        assert len(actual) == 11

    def test_baseline_servers_registered(self):
        """Verify the 9 remaining baseline MCP servers from 0d83ea8."""
        baseline_servers = [
            "github",
            "playwright",
            "slack",
            "postgres",
            "filesystem",
            "memory",
            "brave-search",
            "google-drive",
            "puppeteer",
        ]

        for name in baseline_servers:
            server = mcp_registry.get_server(name)
            assert server is not None, f"Baseline server '{name}' should be registered"
            assert isinstance(server, MCPServer)
            assert server.name == name
            assert server.enabled is True
        # fetch was in the pre-0d83ea8 baseline and was pruned.
        assert mcp_registry.get_server("fetch") is None

    def test_phase1_servers_registered(self):
        """Verify npx-verified Phase 1 MCP servers from 0d83ea8."""
        phase1_servers = ["stripe", "notion"]

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
        """Verify Stripe server matches 0d83ea8 (@stripe/mcp, STRIPE_SECRET_KEY)."""
        server = mcp_registry.get_server("stripe")

        assert server is not None
        assert server.display_name == "Stripe Payments"
        assert server.args == ["-y", "@stripe/mcp", "--tools=all"]
        assert server.env == {"STRIPE_SECRET_KEY": "${STRIPE_API_KEY}"}
        assert server.capabilities == [
            "create_customer", "list_customers",
            "create_product", "list_products",
            "create_price", "list_prices",
            "create_payment_link",
            "create_invoice", "create_invoice_item", "finalize_invoice",
            "list_payment_intents", "list_subscriptions",
            "update_subscription", "cancel_subscription",
            "create_refund", "retrieve_balance",
        ]

    def test_linear_server_not_in_npx_verified_set(self):
        """0d83ea8 pruned linear; it must not reappear as an unverified server."""
        assert mcp_registry.get_server("linear") is None

    def test_git_server_not_in_npx_verified_set(self):
        """0d83ea8 pruned git; it must not reappear as an unverified server."""
        assert mcp_registry.get_server("git") is None

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
    @patch("app.mcp.registry.MCPClient")
    async def test_start_server_success(self, mock_client_cls, fresh_registry):
        """Test successfully starting an MCP server"""
        mock_client_cls.return_value = _fake_mcp_client()

        test_server = MCPServer(
            name="test-start",
            display_name="Test Start",
            command="node",
            args=["server.js"],
            capabilities=["test"],
            description="Test"
        )
        fresh_registry.register_server(test_server)

        result = await fresh_registry.start_server("test-start")

        assert result is True
        assert fresh_registry.is_running("test-start")
        mock_client_cls.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_nonexistent_server(self, fresh_registry):
        """Test starting a server that doesn't exist"""
        result = await fresh_registry.start_server("nonexistent-server")
        assert result is False

    @pytest.mark.asyncio
    @patch("app.mcp.registry.MCPClient")
    async def test_stop_server(self, mock_client_cls, fresh_registry):
        """Test stopping a running MCP server"""
        client = _fake_mcp_client()
        mock_client_cls.return_value = client

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

        result = await fresh_registry.stop_server("test-stop")

        assert result is True
        assert not fresh_registry.is_running("test-stop")
        client.disconnect.assert_awaited()

    @pytest.mark.asyncio
    @patch("app.mcp.registry.MCPClient")
    async def test_server_already_running(self, mock_client_cls, fresh_registry):
        """Test starting a server that's already running"""
        mock_client_cls.return_value = _fake_mcp_client()

        test_server = MCPServer(
            name="test-double-start",
            display_name="Test Double Start",
            command="node",
            args=["server.js"],
            capabilities=["test"],
            description="Test"
        )
        fresh_registry.register_server(test_server)

        result1 = await fresh_registry.start_server("test-double-start")
        result2 = await fresh_registry.start_server("test-double-start")

        assert result1 is True
        assert result2 is True
        assert mock_client_cls.call_count == 1

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
    @patch("app.mcp.registry.MCPClient")
    async def test_call_tool_stdio_transport(self, mock_client_cls, fresh_registry):
        """Test calling a tool via STDIO transport"""
        client = _fake_mcp_client()
        client.call_tool = AsyncMock(return_value={"success": True})
        mock_client_cls.return_value = client

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

        github = mcp_registry.get_server("github")
        assert github is not None
        assert github.name == "github"

        db_names = {
            s["name"]
            for s in servers
            if any(
                cap in {"query", "list_tables"}
                for cap in s["capabilities"]
            )
        }
        assert db_names == {"postgres"}

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
