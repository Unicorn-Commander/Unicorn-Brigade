"""
A2A (Agent-to-Agent) Protocol Implementation

Linux Foundation standard for agent discovery and invocation.
https://github.com/google/A2A

This implementation provides:
- Agent Card Schema: JSON schema for agent discovery
- Agent Registry: Local and federated agent discovery
- Invocation Protocol: Standard request/response with streaming support
- Authentication: API key, OAuth2, capability-based access control
- Discovery Service: Query agents by capability, domain, or name

Based on the Linux Foundation A2A Protocol specification and patterns from
Google's A2A reference implementation.
"""

from typing import Dict, Any, List, Optional, Set, Callable, Awaitable, AsyncGenerator, Union
from pydantic import BaseModel, Field, field_validator
from dataclasses import dataclass, field as dataclass_field
from datetime import datetime, timedelta
from enum import Enum
from abc import ABC, abstractmethod
import asyncio
import hashlib
import hmac
import os
import secrets
import json
import logging
import httpx
import uuid
import time

logger = logging.getLogger(__name__)

# Bound the detached async A2A callback POST so a slow or hostile callback sink
# cannot hang the background task indefinitely.
A2A_CALLBACK_TIMEOUT_SECONDS: float = float(os.getenv("A2A_CALLBACK_TIMEOUT_SECONDS", "15") or 15)


# ============== Enums ==============

class AuthType(str, Enum):
    """Authentication types supported by A2A"""
    NONE = "none"
    API_KEY = "api_key"
    BEARER = "bearer"
    OAUTH2 = "oauth2"
    MTLS = "mtls"


class AgentStatus(str, Enum):
    """Agent availability status"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    MAINTENANCE = "maintenance"
    DEPRECATED = "deprecated"


class InvocationStatus(str, Enum):
    """Status of an agent invocation"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class PricingModel(str, Enum):
    """Pricing models for agents"""
    FREE = "free"
    PER_CALL = "per_call"
    PER_TOKEN = "per_token"
    SUBSCRIPTION = "subscription"
    CUSTOM = "custom"


class TaskPriority(str, Enum):
    """Priority levels for tasks"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


# ============== Agent Card Schema ==============

class AgentCapability(BaseModel):
    """
    A capability that an agent provides.

    Capabilities describe what an agent can do, enabling discovery
    by functionality rather than just name.
    """
    name: str = Field(..., description="Capability identifier (e.g., 'code_review', 'data_analysis')")
    description: str = Field(..., description="Human-readable description of the capability")
    version: str = Field(default="1.0.0", description="Semantic version of this capability")

    # Input/Output Schema
    input_schema: Dict[str, Any] = Field(
        default_factory=dict,
        description="JSON Schema for capability input"
    )
    output_schema: Dict[str, Any] = Field(
        default_factory=dict,
        description="JSON Schema for capability output"
    )

    # Metadata
    domains: List[str] = Field(default_factory=list, description="Domains this capability applies to")
    tags: List[str] = Field(default_factory=list, description="Searchable tags")
    examples: List[Dict[str, Any]] = Field(default_factory=list, description="Example invocations")

    # Constraints
    requires_auth: bool = Field(default=False, description="Whether this capability requires authentication")
    max_input_size: Optional[int] = Field(default=None, description="Maximum input size in bytes")
    estimated_latency_ms: Optional[int] = Field(default=None, description="Estimated response time")


class AgentEndpoint(BaseModel):
    """Endpoint configuration for an agent"""
    invoke_url: str = Field(..., description="URL for synchronous invocation")
    stream_url: Optional[str] = Field(default=None, description="URL for streaming responses")
    async_url: Optional[str] = Field(default=None, description="URL for async task submission")
    status_url: Optional[str] = Field(default=None, description="URL for checking task status")
    cancel_url: Optional[str] = Field(default=None, description="URL for cancelling tasks")
    card_url: Optional[str] = Field(default=None, description="URL to fetch this agent card")


class RateLimitConfig(BaseModel):
    """Rate limiting configuration"""
    requests_per_minute: int = Field(default=60, description="Max requests per minute")
    requests_per_hour: int = Field(default=1000, description="Max requests per hour")
    requests_per_day: int = Field(default=10000, description="Max requests per day")
    burst_limit: int = Field(default=10, description="Max burst requests")
    concurrent_limit: int = Field(default=5, description="Max concurrent requests")


class AuthConfig(BaseModel):
    """Authentication configuration for an agent"""
    auth_type: AuthType = Field(default=AuthType.NONE, description="Primary authentication method")
    supported_auth_types: List[AuthType] = Field(
        default_factory=lambda: [AuthType.NONE],
        description="All supported auth methods"
    )
    auth_url: Optional[str] = Field(default=None, description="OAuth2 authorization URL")
    token_url: Optional[str] = Field(default=None, description="OAuth2 token URL")
    scopes: List[str] = Field(default_factory=list, description="Required OAuth2 scopes")
    api_key_header: str = Field(default="X-API-Key", description="Header name for API key")

    # Security
    requires_https: bool = Field(default=True, description="Whether HTTPS is required")
    allowed_origins: List[str] = Field(default_factory=list, description="CORS allowed origins")


class PricingConfig(BaseModel):
    """Pricing configuration for an agent"""
    model: PricingModel = Field(default=PricingModel.FREE, description="Pricing model")
    currency: str = Field(default="USD", description="Currency for prices")
    price_per_call: Optional[float] = Field(default=None, description="Price per invocation")
    price_per_1k_tokens: Optional[float] = Field(default=None, description="Price per 1K tokens")
    subscription_price: Optional[float] = Field(default=None, description="Monthly subscription price")
    free_tier_calls: int = Field(default=0, description="Free calls per month")
    billing_url: Optional[str] = Field(default=None, description="Billing information URL")


class AgentMetadata(BaseModel):
    """Additional metadata for an agent"""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: Optional[str] = Field(default=None, description="Creator user/org ID")
    organization: Optional[str] = Field(default=None, description="Organization name")
    website: Optional[str] = Field(default=None, description="Agent documentation website")
    support_email: Optional[str] = Field(default=None, description="Support contact email")
    logo_url: Optional[str] = Field(default=None, description="Agent logo URL")
    terms_url: Optional[str] = Field(default=None, description="Terms of service URL")
    privacy_url: Optional[str] = Field(default=None, description="Privacy policy URL")


class AgentCard(BaseModel):
    """
    A2A Agent Card - Standard metadata format for agent discovery.

    This follows the Linux Foundation A2A Protocol specification and provides
    all information needed for clients to discover and invoke an agent.
    """
    # Identity
    id: str = Field(..., description="Unique agent identifier (UUID)")
    name: str = Field(..., description="Human-readable agent name")
    description: str = Field(..., description="Detailed description of agent functionality")
    version: str = Field(default="1.0.0", description="Agent version (semver)")

    # Endpoints
    endpoints: AgentEndpoint = Field(..., description="Agent endpoint configuration")

    # Capabilities
    capabilities: List[AgentCapability] = Field(
        default_factory=list,
        description="List of capabilities this agent provides"
    )

    # Classification
    domain: Optional[str] = Field(default=None, description="Primary domain (e.g., 'engineering', 'research')")
    subdomain: Optional[str] = Field(default=None, description="Subdomain specialization")
    tags: List[str] = Field(default_factory=list, description="Searchable tags")

    # Configuration
    auth: AuthConfig = Field(default_factory=AuthConfig, description="Authentication configuration")
    rate_limits: RateLimitConfig = Field(default_factory=RateLimitConfig, description="Rate limiting")
    pricing: PricingConfig = Field(default_factory=PricingConfig, description="Pricing configuration")

    # Status
    status: AgentStatus = Field(default=AgentStatus.ACTIVE, description="Current status")
    health_check_url: Optional[str] = Field(default=None, description="Health check endpoint")

    # Metadata
    metadata: AgentMetadata = Field(default_factory=AgentMetadata, description="Additional metadata")
    provider: str = Field(default="Unicorn Brigade", description="Provider name")

    # Protocol
    a2a_version: str = Field(default="1.0.0", description="A2A protocol version")
    supported_protocols: List[str] = Field(
        default_factory=lambda: ["a2a/1.0"],
        description="Supported protocol versions"
    )

    def to_json(self) -> str:
        """Serialize to JSON"""
        return self.model_dump_json(indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "AgentCard":
        """Deserialize from JSON"""
        return cls.model_validate_json(json_str)

    def get_capability(self, name: str) -> Optional[AgentCapability]:
        """Get a capability by name"""
        for cap in self.capabilities:
            if cap.name == name:
                return cap
        return None

    def has_capability(self, name: str) -> bool:
        """Check if agent has a capability"""
        return self.get_capability(name) is not None

    def matches_query(self, query: str) -> bool:
        """Check if agent matches a search query"""
        query_lower = query.lower()
        return (
            query_lower in self.name.lower() or
            query_lower in self.description.lower() or
            any(query_lower in tag.lower() for tag in self.tags) or
            any(query_lower in cap.name.lower() for cap in self.capabilities) or
            (self.domain and query_lower in self.domain.lower())
        )


# ============== Invocation Protocol ==============

class A2AInvokeRequest(BaseModel):
    """
    Standard A2A invocation request.

    This is the canonical format for invoking an agent via A2A protocol.
    """
    # Task specification
    task: str = Field(..., description="Task description or prompt")
    capability: Optional[str] = Field(default=None, description="Specific capability to invoke")

    # Context
    context: Dict[str, Any] = Field(default_factory=dict, description="Additional context")
    input_data: Optional[Dict[str, Any]] = Field(default=None, description="Structured input data")

    # Session management
    session_id: Optional[str] = Field(default=None, description="Session ID for conversation continuity")
    conversation_history: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Previous messages in the conversation"
    )

    # User identification
    user_id: Optional[str] = Field(default=None, description="Invoking user ID")
    organization_id: Optional[str] = Field(default=None, description="Invoking organization ID")

    # Execution options
    priority: TaskPriority = Field(default=TaskPriority.NORMAL, description="Task priority")
    timeout_seconds: int = Field(default=120, description="Max execution time")
    stream: bool = Field(default=False, description="Whether to stream response")

    # Callback for async
    callback_url: Optional[str] = Field(default=None, description="Webhook for async response")
    callback_headers: Dict[str, str] = Field(default_factory=dict, description="Headers for callback")

    # Metadata
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique request ID")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Request timestamp")

    # Tool use
    tools: List[Dict[str, Any]] = Field(default_factory=list, description="Tools available to agent")
    tool_choice: str = Field(default="auto", description="Tool selection strategy")


class A2AToolCall(BaseModel):
    """A tool call made during agent execution"""
    id: str = Field(..., description="Tool call ID")
    name: str = Field(..., description="Tool name")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Tool arguments")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class A2AToolResult(BaseModel):
    """Result from a tool call"""
    tool_call_id: str = Field(..., description="Corresponding tool call ID")
    result: Any = Field(default=None, description="Tool execution result")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    duration_ms: Optional[int] = Field(default=None, description="Execution time")


class A2AInvokeResponse(BaseModel):
    """
    Standard A2A invocation response.

    Contains the result of an agent invocation with comprehensive metadata.
    """
    # Status
    status: InvocationStatus = Field(..., description="Invocation status")

    # Result
    result: Optional[Any] = Field(default=None, description="Primary result")
    output_data: Optional[Dict[str, Any]] = Field(default=None, description="Structured output")

    # Error handling
    error: Optional[str] = Field(default=None, description="Error message if failed")
    error_code: Optional[str] = Field(default=None, description="Error code for programmatic handling")
    error_details: Optional[Dict[str, Any]] = Field(default=None, description="Additional error context")

    # Task tracking
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Task ID for tracking")
    request_id: Optional[str] = Field(default=None, description="Original request ID")

    # Tool usage
    tool_calls: List[A2AToolCall] = Field(default_factory=list, description="Tools called during execution")
    tool_results: List[A2AToolResult] = Field(default_factory=list, description="Tool results")

    # Usage metrics
    tokens_used: Dict[str, int] = Field(
        default_factory=dict,
        description="Token usage: {'input': N, 'output': M}"
    )
    duration_seconds: float = Field(default=0.0, description="Total execution time")

    # Metadata
    agent_id: Optional[str] = Field(default=None, description="Responding agent ID")
    agent_version: Optional[str] = Field(default=None, description="Agent version used")
    model_used: Optional[str] = Field(default=None, description="LLM model used")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Pagination for large results
    has_more: bool = Field(default=False, description="Whether more results available")
    next_cursor: Optional[str] = Field(default=None, description="Cursor for pagination")


class A2AStreamChunk(BaseModel):
    """A chunk in a streaming response"""
    chunk_id: int = Field(..., description="Sequential chunk ID")
    task_id: str = Field(..., description="Task ID")
    content: str = Field(default="", description="Content chunk")
    tool_call: Optional[A2AToolCall] = Field(default=None, description="Tool call if any")
    is_final: bool = Field(default=False, description="Whether this is the last chunk")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class A2ATaskStatus(BaseModel):
    """Status of an async task"""
    task_id: str = Field(..., description="Task ID")
    status: InvocationStatus = Field(..., description="Current status")
    progress: float = Field(default=0.0, description="Progress 0-100")
    message: Optional[str] = Field(default=None, description="Status message")
    result: Optional[A2AInvokeResponse] = Field(default=None, description="Result if completed")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    estimated_completion: Optional[datetime] = Field(default=None)


# ============== Authentication & Authorization ==============

class A2ACredentials(BaseModel):
    """Credentials for A2A authentication"""
    auth_type: AuthType
    api_key: Optional[str] = None
    bearer_token: Optional[str] = None
    oauth_token: Optional[str] = None
    refresh_token: Optional[str] = None
    expires_at: Optional[datetime] = None
    scopes: List[str] = Field(default_factory=list)


@dataclass
class APIKeyRecord:
    """Record of an API key in the registry"""
    key_hash: str
    key_prefix: str  # First 8 chars for identification
    agent_id: str
    user_id: str
    name: str
    permissions: Set[str]
    rate_limit: RateLimitConfig
    created_at: datetime
    expires_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
    usage_count: int = 0
    is_active: bool = True


class APIKeyManager:
    """
    Manages API keys for A2A authentication.

    Provides secure key generation, validation, and lifecycle management.
    """

    def __init__(self):
        self._keys: Dict[str, APIKeyRecord] = {}  # prefix -> record
        self._hash_to_prefix: Dict[str, str] = {}  # hash -> prefix

    def generate_key(
        self,
        agent_id: str,
        user_id: str,
        name: str,
        permissions: Optional[Set[str]] = None,
        rate_limit: Optional[RateLimitConfig] = None,
        expires_in_days: Optional[int] = None,
    ) -> tuple[str, APIKeyRecord]:
        """
        Generate a new API key.

        Returns:
            Tuple of (raw_key, record) - raw key is only returned once
        """
        # Generate cryptographically secure key
        raw_key = f"a2a_{secrets.token_urlsafe(32)}"
        key_hash = self._hash_key(raw_key)
        key_prefix = raw_key[:12]

        expires_at = None
        if expires_in_days:
            expires_at = datetime.utcnow() + timedelta(days=expires_in_days)

        record = APIKeyRecord(
            key_hash=key_hash,
            key_prefix=key_prefix,
            agent_id=agent_id,
            user_id=user_id,
            name=name,
            permissions=permissions or {"invoke"},
            rate_limit=rate_limit or RateLimitConfig(),
            created_at=datetime.utcnow(),
            expires_at=expires_at,
        )

        self._keys[key_prefix] = record
        self._hash_to_prefix[key_hash] = key_prefix

        logger.info(f"Generated API key {key_prefix}... for agent {agent_id}")
        return raw_key, record

    def validate_key(self, raw_key: str) -> Optional[APIKeyRecord]:
        """
        Validate an API key.

        Returns:
            APIKeyRecord if valid, None otherwise
        """
        if not raw_key or len(raw_key) < 12:
            return None

        key_hash = self._hash_key(raw_key)
        prefix = self._hash_to_prefix.get(key_hash)

        if not prefix:
            return None

        record = self._keys.get(prefix)
        if not record:
            return None

        # Check if active
        if not record.is_active:
            logger.warning(f"Attempt to use deactivated key {prefix}...")
            return None

        # Check expiration
        if record.expires_at and datetime.utcnow() > record.expires_at:
            logger.warning(f"Attempt to use expired key {prefix}...")
            return None

        # Update usage
        record.last_used_at = datetime.utcnow()
        record.usage_count += 1

        return record

    def revoke_key(self, key_prefix: str) -> bool:
        """Revoke an API key by prefix"""
        if key_prefix in self._keys:
            self._keys[key_prefix].is_active = False
            logger.info(f"Revoked API key {key_prefix}...")
            return True
        return False

    def get_keys_for_user(self, user_id: str) -> List[APIKeyRecord]:
        """Get all keys for a user"""
        return [r for r in self._keys.values() if r.user_id == user_id]

    def get_keys_for_agent(self, agent_id: str) -> List[APIKeyRecord]:
        """Get all keys for an agent"""
        return [r for r in self._keys.values() if r.agent_id == agent_id]

    @staticmethod
    def _hash_key(raw_key: str) -> str:
        """Hash an API key using SHA-256"""
        return hashlib.sha256(raw_key.encode()).hexdigest()


class CapabilityAccessControl:
    """
    Capability-based access control for A2A.

    Controls which capabilities a user/key can access.
    """

    def __init__(self):
        self._capability_permissions: Dict[str, Set[str]] = {}  # capability -> required permissions
        self._user_permissions: Dict[str, Set[str]] = {}  # user_id -> granted permissions

    def define_capability_permissions(self, capability: str, required_permissions: Set[str]):
        """Define which permissions are required for a capability"""
        self._capability_permissions[capability] = required_permissions
        logger.info(f"Defined permissions for capability {capability}: {required_permissions}")

    def grant_permissions(self, user_id: str, permissions: Set[str]):
        """Grant permissions to a user"""
        if user_id not in self._user_permissions:
            self._user_permissions[user_id] = set()
        self._user_permissions[user_id].update(permissions)
        logger.info(f"Granted permissions to {user_id}: {permissions}")

    def revoke_permissions(self, user_id: str, permissions: Set[str]):
        """Revoke permissions from a user"""
        if user_id in self._user_permissions:
            self._user_permissions[user_id] -= permissions
            logger.info(f"Revoked permissions from {user_id}: {permissions}")

    def check_access(
        self,
        user_id: str,
        capability: str,
        api_key_permissions: Optional[Set[str]] = None,
    ) -> bool:
        """
        Check if user/key has access to a capability.

        Args:
            user_id: User ID
            capability: Capability name
            api_key_permissions: Permissions from API key (if using key auth)

        Returns:
            True if access granted
        """
        required = self._capability_permissions.get(capability, set())

        if not required:
            return True  # No permissions required

        # Combine user permissions and key permissions
        user_perms = self._user_permissions.get(user_id, set())
        key_perms = api_key_permissions or set()
        all_perms = user_perms | key_perms

        return required.issubset(all_perms)

    def get_accessible_capabilities(
        self,
        user_id: str,
        api_key_permissions: Optional[Set[str]] = None,
    ) -> Set[str]:
        """Get all capabilities accessible by user"""
        user_perms = self._user_permissions.get(user_id, set())
        key_perms = api_key_permissions or set()
        all_perms = user_perms | key_perms

        accessible = set()
        for cap, required in self._capability_permissions.items():
            if required.issubset(all_perms):
                accessible.add(cap)

        return accessible


# ============== Rate Limiting ==============

@dataclass
class RateLimitBucket:
    """Token bucket for rate limiting"""
    tokens: float
    max_tokens: float
    refill_rate: float  # tokens per second
    last_refill: float  # timestamp

    def consume(self, tokens: int = 1) -> bool:
        """Try to consume tokens, returns True if successful"""
        now = time.time()

        # Refill tokens based on time elapsed
        elapsed = now - self.last_refill
        self.tokens = min(self.max_tokens, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False


class RateLimiter:
    """
    Rate limiter for A2A invocations.

    Uses token bucket algorithm with multiple time windows.
    """

    def __init__(self):
        self._minute_buckets: Dict[str, RateLimitBucket] = {}
        self._hour_buckets: Dict[str, RateLimitBucket] = {}
        self._day_buckets: Dict[str, RateLimitBucket] = {}
        self._concurrent: Dict[str, int] = {}

    def check_rate_limit(
        self,
        key: str,
        config: RateLimitConfig,
    ) -> tuple[bool, Optional[str]]:
        """
        Check if request is allowed under rate limits.

        Args:
            key: Rate limit key (e.g., user_id or api_key_prefix)
            config: Rate limit configuration

        Returns:
            Tuple of (allowed, error_message)
        """
        # Initialize buckets if needed
        if key not in self._minute_buckets:
            self._minute_buckets[key] = RateLimitBucket(
                tokens=config.requests_per_minute,
                max_tokens=config.requests_per_minute,
                refill_rate=config.requests_per_minute / 60.0,
                last_refill=time.time(),
            )

        if key not in self._hour_buckets:
            self._hour_buckets[key] = RateLimitBucket(
                tokens=config.requests_per_hour,
                max_tokens=config.requests_per_hour,
                refill_rate=config.requests_per_hour / 3600.0,
                last_refill=time.time(),
            )

        if key not in self._day_buckets:
            self._day_buckets[key] = RateLimitBucket(
                tokens=config.requests_per_day,
                max_tokens=config.requests_per_day,
                refill_rate=config.requests_per_day / 86400.0,
                last_refill=time.time(),
            )

        # Check concurrent limit
        current_concurrent = self._concurrent.get(key, 0)
        if current_concurrent >= config.concurrent_limit:
            return False, f"Concurrent limit exceeded ({config.concurrent_limit})"

        # Check minute limit
        if not self._minute_buckets[key].consume():
            return False, f"Per-minute rate limit exceeded ({config.requests_per_minute}/min)"

        # Check hour limit
        if not self._hour_buckets[key].consume():
            return False, f"Per-hour rate limit exceeded ({config.requests_per_hour}/hour)"

        # Check day limit
        if not self._day_buckets[key].consume():
            return False, f"Per-day rate limit exceeded ({config.requests_per_day}/day)"

        return True, None

    def acquire_concurrent(self, key: str) -> None:
        """Acquire a concurrent slot"""
        self._concurrent[key] = self._concurrent.get(key, 0) + 1

    def release_concurrent(self, key: str) -> None:
        """Release a concurrent slot"""
        if key in self._concurrent and self._concurrent[key] > 0:
            self._concurrent[key] -= 1

    def get_remaining(self, key: str) -> Dict[str, int]:
        """Get remaining limits for a key"""
        return {
            "minute": int(self._minute_buckets.get(key, RateLimitBucket(60, 60, 1, 0)).tokens),
            "hour": int(self._hour_buckets.get(key, RateLimitBucket(1000, 1000, 0.28, 0)).tokens),
            "day": int(self._day_buckets.get(key, RateLimitBucket(10000, 10000, 0.12, 0)).tokens),
            "concurrent": self._concurrent.get(key, 0),
        }


# ============== Agent Registry ==============

class AgentRegistry:
    """
    Registry for discovering and managing A2A agents.

    Provides:
    - Agent registration and deregistration
    - Query by capability, domain, name, or tags
    - Health status tracking
    - Federation with remote registries
    """

    def __init__(self):
        self._agents: Dict[str, AgentCard] = {}  # id -> card
        self._health_status: Dict[str, Dict[str, Any]] = {}  # id -> status
        self._capability_index: Dict[str, Set[str]] = {}  # capability -> agent_ids
        self._domain_index: Dict[str, Set[str]] = {}  # domain -> agent_ids
        self._tag_index: Dict[str, Set[str]] = {}  # tag -> agent_ids
        self._federated_registries: List[str] = []  # Remote registry URLs
        self._http_client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client"""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=30.0)
        return self._http_client

    def register(self, card: AgentCard) -> None:
        """
        Register an agent with the registry.

        Args:
            card: Agent card to register
        """
        self._agents[card.id] = card

        # Update indexes
        for cap in card.capabilities:
            if cap.name not in self._capability_index:
                self._capability_index[cap.name] = set()
            self._capability_index[cap.name].add(card.id)

        if card.domain:
            if card.domain not in self._domain_index:
                self._domain_index[card.domain] = set()
            self._domain_index[card.domain].add(card.id)

        for tag in card.tags:
            if tag not in self._tag_index:
                self._tag_index[tag] = set()
            self._tag_index[tag].add(card.id)

        self._health_status[card.id] = {
            "status": "unknown",
            "last_check": None,
            "latency_ms": None,
        }

        logger.info(f"Registered agent: {card.name} ({card.id})")

    def unregister(self, agent_id: str) -> bool:
        """
        Unregister an agent from the registry.

        Args:
            agent_id: Agent ID to unregister

        Returns:
            True if agent was registered, False otherwise
        """
        if agent_id not in self._agents:
            return False

        card = self._agents[agent_id]

        # Remove from indexes
        for cap in card.capabilities:
            if cap.name in self._capability_index:
                self._capability_index[cap.name].discard(agent_id)

        if card.domain and card.domain in self._domain_index:
            self._domain_index[card.domain].discard(agent_id)

        for tag in card.tags:
            if tag in self._tag_index:
                self._tag_index[tag].discard(agent_id)

        del self._agents[agent_id]
        del self._health_status[agent_id]

        logger.info(f"Unregistered agent: {card.name} ({agent_id})")
        return True

    def get(self, agent_id: str) -> Optional[AgentCard]:
        """Get an agent by ID"""
        return self._agents.get(agent_id)

    def list_all(self, include_inactive: bool = False) -> List[AgentCard]:
        """List all registered agents"""
        if include_inactive:
            return list(self._agents.values())
        return [a for a in self._agents.values() if a.status == AgentStatus.ACTIVE]

    def query_by_capability(
        self,
        capability: str,
        include_inactive: bool = False,
    ) -> List[AgentCard]:
        """Query agents by capability"""
        agent_ids = self._capability_index.get(capability, set())
        agents = [self._agents[aid] for aid in agent_ids if aid in self._agents]

        if not include_inactive:
            agents = [a for a in agents if a.status == AgentStatus.ACTIVE]

        return agents

    def query_by_domain(
        self,
        domain: str,
        include_inactive: bool = False,
    ) -> List[AgentCard]:
        """Query agents by domain"""
        agent_ids = self._domain_index.get(domain, set())
        agents = [self._agents[aid] for aid in agent_ids if aid in self._agents]

        if not include_inactive:
            agents = [a for a in agents if a.status == AgentStatus.ACTIVE]

        return agents

    def query_by_tags(
        self,
        tags: List[str],
        match_all: bool = False,
        include_inactive: bool = False,
    ) -> List[AgentCard]:
        """Query agents by tags"""
        if not tags:
            return []

        if match_all:
            # Intersection of all tag sets
            agent_id_sets = [self._tag_index.get(tag, set()) for tag in tags]
            if not agent_id_sets:
                return []
            agent_ids = agent_id_sets[0].intersection(*agent_id_sets[1:])
        else:
            # Union of all tag sets
            agent_ids = set()
            for tag in tags:
                agent_ids.update(self._tag_index.get(tag, set()))

        agents = [self._agents[aid] for aid in agent_ids if aid in self._agents]

        if not include_inactive:
            agents = [a for a in agents if a.status == AgentStatus.ACTIVE]

        return agents

    def search(
        self,
        query: str,
        limit: int = 20,
        include_inactive: bool = False,
    ) -> List[AgentCard]:
        """Free-text search across agents"""
        results = []
        for card in self._agents.values():
            if not include_inactive and card.status != AgentStatus.ACTIVE:
                continue
            if card.matches_query(query):
                results.append(card)
        return results[:limit]

    async def check_health(self, agent_id: str) -> Dict[str, Any]:
        """Check health status of an agent"""
        card = self._agents.get(agent_id)
        if not card:
            return {"status": "unknown", "error": "Agent not found"}

        if not card.health_check_url:
            return {"status": "unknown", "error": "No health check URL"}

        try:
            client = await self._get_client()
            start = time.time()
            response = await client.get(card.health_check_url)
            latency = (time.time() - start) * 1000

            status = {
                "status": "healthy" if response.status_code == 200 else "unhealthy",
                "last_check": datetime.utcnow().isoformat(),
                "latency_ms": latency,
                "status_code": response.status_code,
            }

            self._health_status[agent_id] = status
            return status

        except Exception as e:
            status = {
                "status": "unhealthy",
                "last_check": datetime.utcnow().isoformat(),
                "error": str(e),
            }
            self._health_status[agent_id] = status
            return status

    async def check_all_health(self) -> Dict[str, Dict[str, Any]]:
        """Check health of all agents"""
        tasks = [self.check_health(aid) for aid in self._agents.keys()]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return {
            aid: results[i] if not isinstance(results[i], Exception) else {"error": str(results[i])}
            for i, aid in enumerate(self._agents.keys())
        }

    def get_health_status(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get cached health status"""
        return self._health_status.get(agent_id)

    # Federation support

    def add_federated_registry(self, registry_url: str) -> None:
        """Add a remote registry for federation"""
        if registry_url not in self._federated_registries:
            self._federated_registries.append(registry_url)
            logger.info(f"Added federated registry: {registry_url}")

    def remove_federated_registry(self, registry_url: str) -> bool:
        """Remove a federated registry"""
        if registry_url in self._federated_registries:
            self._federated_registries.remove(registry_url)
            logger.info(f"Removed federated registry: {registry_url}")
            return True
        return False

    async def query_federated(
        self,
        capability: Optional[str] = None,
        domain: Optional[str] = None,
        query: Optional[str] = None,
    ) -> List[AgentCard]:
        """Query federated registries for agents"""
        all_agents = []
        client = await self._get_client()

        for registry_url in self._federated_registries:
            try:
                params = {}
                if capability:
                    params["capability"] = capability
                if domain:
                    params["domain"] = domain
                if query:
                    params["query"] = query

                response = await client.get(
                    f"{registry_url}/api/v1/a2a/agents/discover",
                    params=params,
                )
                response.raise_for_status()

                for agent_data in response.json().get("agents", []):
                    try:
                        card = AgentCard.model_validate(agent_data)
                        all_agents.append(card)
                    except Exception as e:
                        logger.warning(f"Failed to parse agent card from {registry_url}: {e}")

            except Exception as e:
                logger.error(f"Failed to query federated registry {registry_url}: {e}")

        return all_agents

    async def close(self):
        """Close HTTP client"""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None


# ============== Discovery Service ==============

class DiscoveryService:
    """
    Service for discovering A2A agents.

    Combines local registry with federated discovery and intelligent matching.
    """

    def __init__(self, local_registry: AgentRegistry):
        self.local_registry = local_registry
        self._capability_synonyms: Dict[str, List[str]] = {}  # capability -> synonyms

    def add_capability_synonyms(self, capability: str, synonyms: List[str]) -> None:
        """Add synonyms for a capability to improve matching"""
        self._capability_synonyms[capability] = synonyms

    def _expand_capability(self, capability: str) -> List[str]:
        """Expand a capability to include synonyms"""
        capabilities = [capability]

        # Check if this is a synonym
        for cap, synonyms in self._capability_synonyms.items():
            if capability in synonyms:
                capabilities.append(cap)
            elif capability == cap:
                capabilities.extend(synonyms)

        return list(set(capabilities))

    async def discover(
        self,
        capability: Optional[str] = None,
        domain: Optional[str] = None,
        tags: Optional[List[str]] = None,
        query: Optional[str] = None,
        include_federated: bool = True,
        include_inactive: bool = False,
        limit: int = 50,
    ) -> List[AgentCard]:
        """
        Discover agents matching the given criteria.

        Args:
            capability: Required capability
            domain: Required domain
            tags: Required tags (any match)
            query: Free-text search query
            include_federated: Whether to search federated registries
            include_inactive: Whether to include inactive agents
            limit: Maximum results

        Returns:
            List of matching agent cards, sorted by relevance
        """
        results: List[AgentCard] = []
        seen_ids: Set[str] = set()

        # Local search
        if capability:
            # Expand capability to include synonyms
            for cap in self._expand_capability(capability):
                for agent in self.local_registry.query_by_capability(cap, include_inactive):
                    if agent.id not in seen_ids:
                        results.append(agent)
                        seen_ids.add(agent.id)

        if domain:
            for agent in self.local_registry.query_by_domain(domain, include_inactive):
                if agent.id not in seen_ids:
                    results.append(agent)
                    seen_ids.add(agent.id)

        if tags:
            for agent in self.local_registry.query_by_tags(tags, include_inactive=include_inactive):
                if agent.id not in seen_ids:
                    results.append(agent)
                    seen_ids.add(agent.id)

        if query:
            for agent in self.local_registry.search(query, include_inactive=include_inactive):
                if agent.id not in seen_ids:
                    results.append(agent)
                    seen_ids.add(agent.id)

        # If no criteria provided, return all
        if not any([capability, domain, tags, query]):
            results = self.local_registry.list_all(include_inactive)

        # Federated search
        if include_federated:
            try:
                federated_agents = await self.local_registry.query_federated(
                    capability=capability,
                    domain=domain,
                    query=query,
                )
                for agent in federated_agents:
                    if agent.id not in seen_ids:
                        results.append(agent)
                        seen_ids.add(agent.id)
            except Exception as e:
                logger.warning(f"Federated discovery failed: {e}")

        # Sort by relevance (active first, then by name)
        results.sort(key=lambda a: (
            0 if a.status == AgentStatus.ACTIVE else 1,
            a.name.lower(),
        ))

        return results[:limit]

    async def find_best_agent(
        self,
        task: str,
        required_capability: Optional[str] = None,
        preferred_domain: Optional[str] = None,
    ) -> Optional[AgentCard]:
        """
        Find the best agent for a given task.

        Uses capability matching and health status to select the best agent.
        """
        candidates = await self.discover(
            capability=required_capability,
            domain=preferred_domain,
            query=task,
            include_federated=True,
        )

        if not candidates:
            return None

        # Score candidates
        scored = []
        for agent in candidates:
            score = 0

            # Active agents get higher score
            if agent.status == AgentStatus.ACTIVE:
                score += 10

            # Health check
            health = self.local_registry.get_health_status(agent.id)
            if health and health.get("status") == "healthy":
                score += 5
                # Prefer lower latency
                latency = health.get("latency_ms", 1000)
                score += max(0, 5 - latency / 200)

            # Capability match
            if required_capability and agent.has_capability(required_capability):
                score += 10

            # Domain match
            if preferred_domain and agent.domain == preferred_domain:
                score += 5

            # Free agents get slight preference for cost optimization
            if agent.pricing.model == PricingModel.FREE:
                score += 2

            scored.append((score, agent))

        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[0][1] if scored else None


# ============== Agent Invocation Client ==============

class A2AClient:
    """
    Client for invoking A2A agents.

    Provides:
    - Synchronous and asynchronous invocation
    - Streaming support
    - Automatic retry with backoff
    - Authentication handling
    """

    def __init__(
        self,
        default_timeout: float = 120.0,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        self.default_timeout = default_timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._http_client: Optional[httpx.AsyncClient] = None
        self._credentials: Dict[str, A2ACredentials] = {}  # agent_id -> credentials

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client"""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=self.default_timeout)
        return self._http_client

    def set_credentials(self, agent_id: str, credentials: A2ACredentials) -> None:
        """Set credentials for an agent"""
        self._credentials[agent_id] = credentials

    def _build_headers(
        self,
        agent: AgentCard,
        credentials: Optional[A2ACredentials] = None,
    ) -> Dict[str, str]:
        """Build authentication headers for request"""
        headers = {"Content-Type": "application/json"}

        creds = credentials or self._credentials.get(agent.id)
        if not creds:
            return headers

        if creds.auth_type == AuthType.API_KEY and creds.api_key:
            headers[agent.auth.api_key_header] = creds.api_key
        elif creds.auth_type == AuthType.BEARER and creds.bearer_token:
            headers["Authorization"] = f"Bearer {creds.bearer_token}"
        elif creds.auth_type == AuthType.OAUTH2 and creds.oauth_token:
            headers["Authorization"] = f"Bearer {creds.oauth_token}"

        return headers

    async def invoke(
        self,
        agent: AgentCard,
        request: A2AInvokeRequest,
        credentials: Optional[A2ACredentials] = None,
    ) -> A2AInvokeResponse:
        """
        Invoke an agent synchronously.

        Args:
            agent: Agent card
            request: Invocation request
            credentials: Optional credentials (uses stored if not provided)

        Returns:
            Invocation response
        """
        client = await self._get_client()
        headers = self._build_headers(agent, credentials)

        last_error: Optional[Exception] = None

        for attempt in range(self.max_retries):
            try:
                start_time = time.time()

                response = await client.post(
                    agent.endpoints.invoke_url,
                    json=request.model_dump(mode="json"),
                    headers=headers,
                    timeout=request.timeout_seconds,
                )

                duration = time.time() - start_time

                if response.status_code == 429:
                    # Rate limited - wait and retry
                    retry_after = int(response.headers.get("Retry-After", self.retry_delay * (2 ** attempt)))
                    logger.warning(f"Rate limited, retrying in {retry_after}s")
                    await asyncio.sleep(retry_after)
                    continue

                response.raise_for_status()
                data = response.json()

                return A2AInvokeResponse(
                    status=InvocationStatus(data.get("status", "completed")),
                    result=data.get("result"),
                    output_data=data.get("output_data"),
                    error=data.get("error"),
                    error_code=data.get("error_code"),
                    task_id=data.get("task_id", str(uuid.uuid4())),
                    request_id=request.request_id,
                    tool_calls=[A2AToolCall(**tc) for tc in data.get("tool_calls", [])],
                    tokens_used=data.get("tokens_used", {}),
                    duration_seconds=duration,
                    agent_id=agent.id,
                    agent_version=agent.version,
                    model_used=data.get("model_used"),
                )

            except httpx.HTTPStatusError as e:
                last_error = e
                if e.response.status_code >= 500:
                    # Server error - retry
                    await asyncio.sleep(self.retry_delay * (2 ** attempt))
                else:
                    # Client error - don't retry
                    return A2AInvokeResponse(
                        status=InvocationStatus.FAILED,
                        error=str(e),
                        error_code=f"HTTP_{e.response.status_code}",
                        request_id=request.request_id,
                        agent_id=agent.id,
                    )

            except Exception as e:
                last_error = e
                await asyncio.sleep(self.retry_delay * (2 ** attempt))

        # All retries failed
        return A2AInvokeResponse(
            status=InvocationStatus.FAILED,
            error=str(last_error) if last_error else "Unknown error",
            error_code="MAX_RETRIES_EXCEEDED",
            request_id=request.request_id,
            agent_id=agent.id,
        )

    async def invoke_async(
        self,
        agent: AgentCard,
        request: A2AInvokeRequest,
        credentials: Optional[A2ACredentials] = None,
    ) -> A2ATaskStatus:
        """
        Submit an async task.

        Args:
            agent: Agent card
            request: Invocation request
            credentials: Optional credentials

        Returns:
            Task status with task_id for polling
        """
        if not agent.endpoints.async_url:
            raise ValueError(f"Agent {agent.id} does not support async invocation")

        client = await self._get_client()
        headers = self._build_headers(agent, credentials)

        response = await client.post(
            agent.endpoints.async_url,
            json=request.model_dump(mode="json"),
            headers=headers,
        )
        response.raise_for_status()
        data = response.json()

        return A2ATaskStatus(
            task_id=data["task_id"],
            status=InvocationStatus(data.get("status", "pending")),
            progress=data.get("progress", 0),
            message=data.get("message"),
        )

    async def get_task_status(
        self,
        agent: AgentCard,
        task_id: str,
        credentials: Optional[A2ACredentials] = None,
    ) -> A2ATaskStatus:
        """Get status of an async task"""
        if not agent.endpoints.status_url:
            raise ValueError(f"Agent {agent.id} does not support status checking")

        client = await self._get_client()
        headers = self._build_headers(agent, credentials)

        response = await client.get(
            f"{agent.endpoints.status_url}/{task_id}",
            headers=headers,
        )
        response.raise_for_status()
        data = response.json()

        result = None
        if data.get("result"):
            result = A2AInvokeResponse(**data["result"])

        return A2ATaskStatus(
            task_id=task_id,
            status=InvocationStatus(data["status"]),
            progress=data.get("progress", 0),
            message=data.get("message"),
            result=result,
        )

    async def cancel_task(
        self,
        agent: AgentCard,
        task_id: str,
        credentials: Optional[A2ACredentials] = None,
    ) -> bool:
        """Cancel an async task"""
        if not agent.endpoints.cancel_url:
            raise ValueError(f"Agent {agent.id} does not support task cancellation")

        client = await self._get_client()
        headers = self._build_headers(agent, credentials)

        response = await client.post(
            f"{agent.endpoints.cancel_url}/{task_id}",
            headers=headers,
        )
        return response.status_code == 200

    async def invoke_stream(
        self,
        agent: AgentCard,
        request: A2AInvokeRequest,
        credentials: Optional[A2ACredentials] = None,
    ) -> AsyncGenerator[A2AStreamChunk, None]:
        """
        Invoke an agent with streaming response.

        Yields:
            Stream chunks as they arrive
        """
        if not agent.endpoints.stream_url:
            raise ValueError(f"Agent {agent.id} does not support streaming")

        request.stream = True
        client = await self._get_client()
        headers = self._build_headers(agent, credentials)

        async with client.stream(
            "POST",
            agent.endpoints.stream_url,
            json=request.model_dump(mode="json"),
            headers=headers,
        ) as response:
            response.raise_for_status()

            chunk_id = 0
            task_id = str(uuid.uuid4())

            async for line in response.aiter_lines():
                if not line:
                    continue

                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        yield A2AStreamChunk(
                            chunk_id=chunk_id,
                            task_id=task_id,
                            is_final=True,
                        )
                        break

                    try:
                        chunk_data = json.loads(data)
                        yield A2AStreamChunk(
                            chunk_id=chunk_id,
                            task_id=task_id,
                            content=chunk_data.get("content", ""),
                            tool_call=A2AToolCall(**chunk_data["tool_call"]) if chunk_data.get("tool_call") else None,
                        )
                        chunk_id += 1
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse stream chunk: {data}")

    async def wait_for_completion(
        self,
        agent: AgentCard,
        task_id: str,
        credentials: Optional[A2ACredentials] = None,
        poll_interval: float = 1.0,
        timeout: float = 300.0,
    ) -> A2AInvokeResponse:
        """
        Wait for an async task to complete.

        Args:
            agent: Agent card
            task_id: Task ID from invoke_async
            credentials: Optional credentials
            poll_interval: Seconds between status checks
            timeout: Max seconds to wait

        Returns:
            Final invocation response
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            status = await self.get_task_status(agent, task_id, credentials)

            if status.status == InvocationStatus.COMPLETED:
                return status.result or A2AInvokeResponse(
                    status=InvocationStatus.COMPLETED,
                    task_id=task_id,
                    agent_id=agent.id,
                )

            if status.status in (InvocationStatus.FAILED, InvocationStatus.CANCELLED):
                return A2AInvokeResponse(
                    status=status.status,
                    error=status.message or f"Task {status.status}",
                    task_id=task_id,
                    agent_id=agent.id,
                )

            await asyncio.sleep(poll_interval)

        return A2AInvokeResponse(
            status=InvocationStatus.TIMEOUT,
            error=f"Task did not complete within {timeout}s",
            task_id=task_id,
            agent_id=agent.id,
        )

    async def close(self) -> None:
        """Close HTTP client"""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None


# ============== A2A Protocol Server ==============

class A2AServer:
    """
    Server-side implementation for exposing agents via A2A protocol.

    Integrates with the agent registry and handles invocation routing.
    """

    def __init__(
        self,
        registry: AgentRegistry,
        api_key_manager: Optional[APIKeyManager] = None,
        rate_limiter: Optional[RateLimiter] = None,
        access_control: Optional[CapabilityAccessControl] = None,
    ):
        self.registry = registry
        self.api_key_manager = api_key_manager or APIKeyManager()
        self.rate_limiter = rate_limiter or RateLimiter()
        self.access_control = access_control or CapabilityAccessControl()

        # Agent handlers
        self._handlers: Dict[str, Callable[[A2AInvokeRequest], Awaitable[A2AInvokeResponse]]] = {}
        self._stream_handlers: Dict[str, Callable[[A2AInvokeRequest], AsyncGenerator[A2AStreamChunk, None]]] = {}

        # Async task tracking
        self._async_tasks: Dict[str, A2ATaskStatus] = {}

    def register_handler(
        self,
        agent_id: str,
        handler: Callable[[A2AInvokeRequest], Awaitable[A2AInvokeResponse]],
        stream_handler: Optional[Callable[[A2AInvokeRequest], AsyncGenerator[A2AStreamChunk, None]]] = None,
    ) -> None:
        """Register a handler for an agent"""
        self._handlers[agent_id] = handler
        if stream_handler:
            self._stream_handlers[agent_id] = stream_handler
        logger.info(f"Registered handler for agent {agent_id}")

    async def authenticate(
        self,
        agent_id: str,
        headers: Dict[str, str],
    ) -> tuple[bool, Optional[str], Optional[APIKeyRecord]]:
        """
        Authenticate a request.

        Returns:
            Tuple of (authenticated, user_id, api_key_record)
        """
        agent = self.registry.get(agent_id)
        if not agent:
            return False, None, None

        if agent.auth.auth_type == AuthType.NONE:
            return True, None, None

        # Check API key
        api_key = headers.get(agent.auth.api_key_header) or headers.get("Authorization", "").replace("Bearer ", "")

        if not api_key:
            return False, None, None

        key_record = self.api_key_manager.validate_key(api_key)
        if not key_record:
            return False, None, None

        return True, key_record.user_id, key_record

    async def invoke(
        self,
        agent_id: str,
        request: A2AInvokeRequest,
        headers: Dict[str, str],
    ) -> A2AInvokeResponse:
        """
        Handle an invocation request.

        Performs authentication, rate limiting, and routes to handler.
        """
        # Get agent
        agent = self.registry.get(agent_id)
        if not agent:
            return A2AInvokeResponse(
                status=InvocationStatus.FAILED,
                error=f"Agent not found: {agent_id}",
                error_code="AGENT_NOT_FOUND",
                request_id=request.request_id,
            )

        if agent.status != AgentStatus.ACTIVE:
            return A2AInvokeResponse(
                status=InvocationStatus.FAILED,
                error=f"Agent is not active: {agent.status}",
                error_code="AGENT_INACTIVE",
                request_id=request.request_id,
            )

        # Authenticate
        authenticated, user_id, key_record = await self.authenticate(agent_id, headers)
        if not authenticated:
            return A2AInvokeResponse(
                status=InvocationStatus.FAILED,
                error="Authentication failed",
                error_code="AUTH_FAILED",
                request_id=request.request_id,
            )

        # Check capability access
        if request.capability:
            key_perms = key_record.permissions if key_record else None
            if not self.access_control.check_access(user_id or "anonymous", request.capability, key_perms):
                return A2AInvokeResponse(
                    status=InvocationStatus.FAILED,
                    error=f"Access denied for capability: {request.capability}",
                    error_code="ACCESS_DENIED",
                    request_id=request.request_id,
                )

        # Check rate limits
        rate_key = key_record.key_prefix if key_record else (user_id or "anonymous")
        rate_config = key_record.rate_limit if key_record else agent.rate_limits

        allowed, error_msg = self.rate_limiter.check_rate_limit(rate_key, rate_config)
        if not allowed:
            return A2AInvokeResponse(
                status=InvocationStatus.FAILED,
                error=error_msg,
                error_code="RATE_LIMITED",
                request_id=request.request_id,
            )

        # Get handler
        handler = self._handlers.get(agent_id)
        if not handler:
            return A2AInvokeResponse(
                status=InvocationStatus.FAILED,
                error=f"No handler registered for agent: {agent_id}",
                error_code="NO_HANDLER",
                request_id=request.request_id,
            )

        # Acquire concurrent slot
        self.rate_limiter.acquire_concurrent(rate_key)

        try:
            # Execute handler
            start_time = time.time()
            response = await asyncio.wait_for(
                handler(request),
                timeout=request.timeout_seconds,
            )
            response.duration_seconds = time.time() - start_time
            response.request_id = request.request_id
            response.agent_id = agent_id
            response.agent_version = agent.version
            return response

        except asyncio.TimeoutError:
            return A2AInvokeResponse(
                status=InvocationStatus.TIMEOUT,
                error=f"Request timed out after {request.timeout_seconds}s",
                error_code="TIMEOUT",
                request_id=request.request_id,
                agent_id=agent_id,
            )

        except Exception as e:
            logger.error(f"Handler error for {agent_id}: {e}")
            return A2AInvokeResponse(
                status=InvocationStatus.FAILED,
                error=str(e),
                error_code="HANDLER_ERROR",
                request_id=request.request_id,
                agent_id=agent_id,
            )

        finally:
            self.rate_limiter.release_concurrent(rate_key)

    async def invoke_stream(
        self,
        agent_id: str,
        request: A2AInvokeRequest,
        headers: Dict[str, str],
    ) -> AsyncGenerator[A2AStreamChunk, None]:
        """Handle a streaming invocation request"""
        # Authentication and rate limiting (same as invoke)
        agent = self.registry.get(agent_id)
        if not agent:
            yield A2AStreamChunk(
                chunk_id=0,
                task_id="error",
                content=f"Agent not found: {agent_id}",
                is_final=True,
            )
            return

        authenticated, user_id, key_record = await self.authenticate(agent_id, headers)
        if not authenticated:
            yield A2AStreamChunk(
                chunk_id=0,
                task_id="error",
                content="Authentication failed",
                is_final=True,
            )
            return

        stream_handler = self._stream_handlers.get(agent_id)
        if not stream_handler:
            yield A2AStreamChunk(
                chunk_id=0,
                task_id="error",
                content="Streaming not supported",
                is_final=True,
            )
            return

        async for chunk in stream_handler(request):
            yield chunk

    async def submit_async(
        self,
        agent_id: str,
        request: A2AInvokeRequest,
        headers: Dict[str, str],
    ) -> A2ATaskStatus:
        """Submit an async task"""
        task_id = str(uuid.uuid4())

        status = A2ATaskStatus(
            task_id=task_id,
            status=InvocationStatus.PENDING,
        )
        self._async_tasks[task_id] = status

        # Start task in background
        asyncio.create_task(self._run_async_task(agent_id, request, headers, task_id))

        return status

    async def _run_async_task(
        self,
        agent_id: str,
        request: A2AInvokeRequest,
        headers: Dict[str, str],
        task_id: str,
    ) -> None:
        """Run an async task in background"""
        self._async_tasks[task_id].status = InvocationStatus.RUNNING
        self._async_tasks[task_id].updated_at = datetime.utcnow()

        try:
            response = await self.invoke(agent_id, request, headers)
            self._async_tasks[task_id].status = response.status
            self._async_tasks[task_id].result = response

            # Send callback if configured (SSRF-guarded + timeout-bounded).
            if request.callback_url:
                await self._post_callback(
                    request.callback_url,
                    response.model_dump(mode="json"),
                    request.callback_headers,
                )

        except Exception as e:
            self._async_tasks[task_id].status = InvocationStatus.FAILED
            self._async_tasks[task_id].message = str(e)

        self._async_tasks[task_id].updated_at = datetime.utcnow()

    async def _post_callback(
        self,
        callback_url: str,
        payload: Dict[str, Any],
        headers: Optional[Dict[str, str]],
    ) -> bool:
        """POST an async-task callback, guarded against SSRF and bounded by a timeout.

        The ``callback_url`` is caller-supplied, so an authenticated client must
        not be able to use it as an SSRF / arbitrary-POST vector against internal
        services (localhost, RFC1918, the 169.254.169.254 metadata endpoint). We
        reuse the egress guard from ``builtin_tools`` to validate the host AND pin
        the connection to the resolved public IP (DNS-rebinding TOCTOU fix), keep
        redirects off, and cap the request with an explicit total timeout.

        Returns ``True`` if the callback was sent, ``False`` if blocked or failed.
        """
        # Lazy import to avoid any import-order coupling between protocol + llm layers.
        from app.llm.builtin_tools import build_egress_guarded_transport

        transport, block_reason = build_egress_guarded_transport(callback_url)
        if transport is None:
            logger.warning(
                f"A2A callback blocked by SSRF guard: {callback_url} ({block_reason})"
            )
            return False

        try:
            timeout = httpx.Timeout(
                A2A_CALLBACK_TIMEOUT_SECONDS,
                connect=min(10.0, A2A_CALLBACK_TIMEOUT_SECONDS),
            )
            async with httpx.AsyncClient(
                timeout=timeout, follow_redirects=False, transport=transport
            ) as client:
                await client.post(callback_url, json=payload, headers=headers)
            return True
        except Exception as e:
            logger.error(f"Failed to send callback: {e}")
            return False

    def get_task_status(self, task_id: str) -> Optional[A2ATaskStatus]:
        """Get status of an async task"""
        return self._async_tasks.get(task_id)

    async def cancel_task(self, task_id: str) -> bool:
        """Cancel an async task"""
        if task_id in self._async_tasks:
            self._async_tasks[task_id].status = InvocationStatus.CANCELLED
            self._async_tasks[task_id].updated_at = datetime.utcnow()
            return True
        return False


# ============== Factory Functions ==============

def create_agent_card(
    agent_id: str,
    name: str,
    description: str,
    base_url: str,
    capabilities: List[Dict[str, Any]],
    domain: Optional[str] = None,
    tags: Optional[List[str]] = None,
    auth_type: AuthType = AuthType.NONE,
    pricing_model: PricingModel = PricingModel.FREE,
) -> AgentCard:
    """
    Factory function to create an AgentCard with sensible defaults.

    Args:
        agent_id: Unique agent identifier
        name: Human-readable name
        description: Detailed description
        base_url: Base URL for agent endpoints
        capabilities: List of capability definitions
        domain: Primary domain
        tags: Searchable tags
        auth_type: Authentication type
        pricing_model: Pricing model

    Returns:
        Configured AgentCard
    """
    caps = [
        AgentCapability(
            name=c.get("name", ""),
            description=c.get("description", ""),
            version=c.get("version", "1.0.0"),
            input_schema=c.get("input_schema", {}),
            output_schema=c.get("output_schema", {}),
            domains=c.get("domains", []),
            tags=c.get("tags", []),
        )
        for c in capabilities
    ]

    return AgentCard(
        id=agent_id,
        name=name,
        description=description,
        endpoints=AgentEndpoint(
            invoke_url=f"{base_url}/api/v1/a2a/agents/{agent_id}/invoke",
            stream_url=f"{base_url}/api/v1/a2a/agents/{agent_id}/stream",
            async_url=f"{base_url}/api/v1/a2a/agents/{agent_id}/async",
            status_url=f"{base_url}/api/v1/a2a/agents/{agent_id}/status",
            cancel_url=f"{base_url}/api/v1/a2a/agents/{agent_id}/cancel",
            card_url=f"{base_url}/api/v1/a2a/agents/{agent_id}/card",
        ),
        capabilities=caps,
        domain=domain,
        tags=tags or [],
        auth=AuthConfig(auth_type=auth_type, supported_auth_types=[auth_type]),
        pricing=PricingConfig(model=pricing_model),
        health_check_url=f"{base_url}/api/v1/a2a/agents/{agent_id}/health",
    )


# ============== Global Instances ==============

# Global agent registry
agent_registry = AgentRegistry()

# Global discovery service
discovery_service = DiscoveryService(agent_registry)

# Global API key manager
api_key_manager = APIKeyManager()

# Global rate limiter
rate_limiter = RateLimiter()

# Global access control
access_control = CapabilityAccessControl()

# Global A2A server
a2a_server = A2AServer(
    registry=agent_registry,
    api_key_manager=api_key_manager,
    rate_limiter=rate_limiter,
    access_control=access_control,
)

# Global A2A client
a2a_client = A2AClient()


# ============== Backward Compatibility ==============

# Maintain backward compatibility with existing code
class A2AProtocol:
    """
    A2A Protocol client and server implementation.

    Provides backward compatibility with the original simple implementation
    while using the new comprehensive implementation under the hood.
    """

    def __init__(self, base_url: str = "http://localhost:8100"):
        self.base_url = base_url
        self.client = A2AClient()
        self.registry = AgentRegistry()

    def generate_card(
        self,
        agent_id: str,
        name: str,
        description: str,
        capabilities: List[Dict[str, Any]],
        domain: Optional[str] = None,
        pricing_model: str = "free",
        price_per_call: Optional[float] = None,
    ) -> AgentCard:
        """Generate an A2A Agent Card for an agent"""
        return create_agent_card(
            agent_id=agent_id,
            name=name,
            description=description,
            base_url=self.base_url,
            capabilities=capabilities,
            domain=domain,
            pricing_model=PricingModel(pricing_model),
        )

    async def invoke_remote_agent(
        self,
        agent_card: AgentCard,
        task: str,
        context: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> A2AInvokeResponse:
        """Invoke a remote agent using A2A protocol"""
        if api_key:
            self.client.set_credentials(
                agent_card.id,
                A2ACredentials(auth_type=AuthType.API_KEY, api_key=api_key),
            )

        request = A2AInvokeRequest(
            task=task,
            context=context or {},
            user_id=user_id,
        )

        return await self.client.invoke(agent_card, request)

    async def discover_agents(
        self,
        registry_url: str,
        capability: Optional[str] = None,
        domain: Optional[str] = None,
    ) -> List[AgentCard]:
        """Discover agents from an A2A registry"""
        # Add the registry as a federated registry temporarily
        self.registry.add_federated_registry(registry_url)

        service = DiscoveryService(self.registry)
        agents = await service.discover(
            capability=capability,
            domain=domain,
            include_federated=True,
        )

        return agents

    async def close(self):
        """Close HTTP client"""
        await self.client.close()
        await self.registry.close()
