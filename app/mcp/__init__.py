"""
MCP (Model Context Protocol) Integration Module

Provides:
- MCPRegistry: Central registry for MCP servers
- SandboxExecutor: Hybrid Docker/E2B code execution
- GitHub, Playwright, Slack, Filesystem, PostgreSQL MCP integrations
"""

from app.mcp.registry import MCPRegistry, MCPServer
from app.mcp.sandbox_executor import SandboxExecutor, SandboxConfig

__all__ = [
    "MCPRegistry",
    "MCPServer",
    "SandboxExecutor",
    "SandboxConfig",
]
