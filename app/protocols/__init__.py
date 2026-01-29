"""
Protocol Support for Unicorn Brigade

Implements support for:
- A2A (Agent-to-Agent) - Linux Foundation standard
- MCP (Model Context Protocol) - Anthropic's tool integration standard
- UCP (Universal Commerce Protocol) - Google's commerce layer
- A2UI (Agent Interface Protocol) - Agent-to-UI communication
"""

from app.protocols.a2a import (
    # Main Protocol Class (backward compatible)
    A2AProtocol,

    # Agent Card Schema
    AgentCard,
    AgentCapability,
    AgentEndpoint,
    AgentMetadata,
    AuthConfig,
    PricingConfig,
    RateLimitConfig,

    # Invocation Protocol
    A2AInvokeRequest,
    A2AInvokeResponse,
    A2AStreamChunk,
    A2ATaskStatus,
    A2AToolCall,
    A2AToolResult,

    # Authentication
    A2ACredentials,
    APIKeyManager,
    APIKeyRecord,
    CapabilityAccessControl,

    # Registry and Discovery
    AgentRegistry,
    DiscoveryService,

    # Client and Server
    A2AClient,
    A2AServer,

    # Rate Limiting
    RateLimiter,
    RateLimitBucket,

    # Enums
    AuthType,
    AgentStatus,
    InvocationStatus,
    PricingModel,
    TaskPriority,

    # Factory Functions
    create_agent_card,

    # Global Instances
    agent_registry,
    discovery_service,
    api_key_manager,
    rate_limiter,
    access_control,
    a2a_server,
    a2a_client,
)
from app.protocols.mcp import MCPServer, MCPTool
from app.protocols.ucp import UCPPayment, CommerceSession

__all__ = [
    # A2A Protocol
    "A2AProtocol",
    "AgentCard",
    "AgentCapability",
    "AgentEndpoint",
    "AgentMetadata",
    "AuthConfig",
    "PricingConfig",
    "RateLimitConfig",
    "A2AInvokeRequest",
    "A2AInvokeResponse",
    "A2AStreamChunk",
    "A2ATaskStatus",
    "A2AToolCall",
    "A2AToolResult",
    "A2ACredentials",
    "APIKeyManager",
    "APIKeyRecord",
    "CapabilityAccessControl",
    "AgentRegistry",
    "DiscoveryService",
    "A2AClient",
    "A2AServer",
    "RateLimiter",
    "RateLimitBucket",
    "AuthType",
    "AgentStatus",
    "InvocationStatus",
    "PricingModel",
    "TaskPriority",
    "create_agent_card",
    "agent_registry",
    "discovery_service",
    "api_key_manager",
    "rate_limiter",
    "access_control",
    "a2a_server",
    "a2a_client",

    # MCP Protocol
    "MCPServer",
    "MCPTool",

    # UCP Protocol
    "UCPPayment",
    "CommerceSession",
]
