"""
Role-Based Access Control Configuration

Defines user roles and path-based access rules.
"""

from enum import Enum
from typing import Set


class UserRole(str, Enum):
    """User roles for authorization"""
    ADMIN = "admin"      # Full access - can manage servers, execute code, etc.
    OPERATOR = "operator"  # Can interact with agents, create missions
    VIEWER = "viewer"    # Read-only access to public endpoints
    SERVICE = "service"  # Machine-to-machine (A2A, webhooks)


# Paths that require admin role
ADMIN_ONLY_PATHS: Set[str] = {
    # MCP Registry - Server management (RCE risk)
    "/api/v1/mcp/registry/servers",  # POST (register)
    "/api/v1/mcp/registry/servers/",  # DELETE, start, stop, restart

    # Code Sandbox - Direct code execution (RCE)
    "/api/v1/mcp/registry/sandbox/execute",
    "/api/v1/mcp/registry/sandbox/execute/fallback",

    # MCP tool calls (potential RCE via shell, filesystem, etc.)
    "/api/v1/mcp/registry/tools/call",

    # Agent creation/deletion
    "/api/v1/orchestration/agents/create",

    # Slack webhook configuration
    "/api/v1/slack/test",
}

# Paths that allow more permissive verbs but still need authentication
PROTECTED_PATHS: Set[str] = {
    # Agent chat - requires at least viewer role
    "/api/v1/agents/",  # GET (list/detail) - viewer+
                         # POST (chat) - operator+
                         # PUT/DELETE - admin only

    # Orchestration
    "/api/v1/orchestration/command",  # operator+
    "/api/v1/orchestration/missions",  # operator+

    # Conversations - user's own data
    "/api/v1/conversations",

    # API key management
    "/api/v1/agents/*/api-keys",

    # Knowledge graph mutations
    "/api/v1/knowledge/entities",  # POST/DELETE
    "/api/v1/knowledge/relationships",  # POST/DELETE

    # Voice rooms
    "/api/v1/voice/rooms",

    # Langflow flows
    "/api/v1/langflow/flows",
}

# Paths that are always public (no auth required)
PUBLIC_PATHS: Set[str] = {
    "/",
    "/ping",
    "/docs",
    "/openapi.json",
    "/redoc",

    # Health checks
    "/api/v1/health",
    "/api/v1/mcp/registry/health",
    "/api/v1/voice/health",
    "/api/v1/langflow/health",
    "/api/v1/slack/health",

    # User registration and login (public)
    "/api/v1/users/register",
    "/api/v1/users/login",

    # A2A discovery (intentionally public for federation)
    "/api/v1/a2a/info",
    "/api/v1/a2a/agents",
    "/api/v1/a2a/discover",

    # MCP info (public for protocol compliance)
    "/api/v1/mcp/info",
    "/api/v1/mcp/tools/list",

    # Read-only stats
    "/api/v1/stats",
    "/api/v1/models",

    # Slack webhooks (verify via signing secret instead)
    "/api/v1/slack/events",
    "/api/v1/slack/interactions",
    "/api/v1/slack/commands",
}


def is_admin_path(path: str) -> bool:
    """Check if a path requires admin access"""
    # Exact match
    if path in ADMIN_ONLY_PATHS:
        return True

    # Prefix match for paths with parameters
    for admin_path in ADMIN_ONLY_PATHS:
        if admin_path.endswith("/") and path.startswith(admin_path):
            return True
        # Handle paths like /servers/{name}/start
        if "/servers/" in path and any(
            action in path for action in ["/start", "/stop", "/restart"]
        ):
            return True

    return False


def is_public_path(path: str) -> bool:
    """Check if a path is public (no auth required)"""
    # Exact match
    if path in PUBLIC_PATHS:
        return True

    # Prefix match only for explicit prefixes (avoid matching "/" for everything)
    for public_path in PUBLIC_PATHS:
        if public_path != "/" and public_path.endswith("/") and path.startswith(public_path):
            return True

    return False


def get_minimum_role_for_method(path: str, method: str) -> UserRole:
    """Get the minimum role required for a path/method combination"""
    # Admin paths always require admin
    if is_admin_path(path):
        return UserRole.ADMIN

    # Agent routes
    if "/agents" in path:
        if method in ("DELETE", "PUT"):
            return UserRole.ADMIN
        if method == "POST" and "/chat" in path:
            return UserRole.OPERATOR
        return UserRole.VIEWER

    # Orchestration
    if "/orchestration" in path:
        if method == "POST":
            return UserRole.OPERATOR
        return UserRole.VIEWER

    # Knowledge graph
    if "/knowledge" in path:
        if method in ("POST", "DELETE"):
            return UserRole.OPERATOR
        return UserRole.VIEWER

    # Default: viewer for GET, operator for mutations
    if method == "GET":
        return UserRole.VIEWER

    return UserRole.OPERATOR


# ---------------------------------------------------------------------------
# Keycloak realm role mapping
# ---------------------------------------------------------------------------

# Mapping from Keycloak realm/client role name -> Brigade UserRole.
# Defined in priority order — the first match in this order wins.
KEYCLOAK_ROLE_MAP = [
    ("admin", UserRole.ADMIN),
    ("investigator", UserRole.OPERATOR),
    ("operator", UserRole.OPERATOR),
    ("client", UserRole.VIEWER),
    ("viewer", UserRole.VIEWER),
]


def map_keycloak_roles(roles: list) -> UserRole:
    """
    Map a list of Keycloak role names to a Brigade UserRole.

    Picks the highest-privilege matching role from ``KEYCLOAK_ROLE_MAP``.
    Defaults to ``UserRole.VIEWER`` when no role matches.
    """
    if not roles:
        return UserRole.VIEWER
    role_set = {r.lower() for r in roles if isinstance(r, str)}
    for kc_role, brigade_role in KEYCLOAK_ROLE_MAP:
        if kc_role in role_set:
            return brigade_role
    return UserRole.VIEWER
