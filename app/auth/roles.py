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

    # Org lifecycle (BR-2.1): the GLOBAL gate only requires authentication — the
    # real authorization is the PER-ORG role (owner/admin/member) enforced inside
    # app/api/org_routes against org_memberships. Without this, the default
    # POST->OPERATOR rule below would block a global-VIEWER invitee from ever
    # accepting an invite or creating their own org.
    if path.startswith("/api/v1/orgs"):
        return UserRole.VIEWER

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


# ---------------------------------------------------------------------------
# Agent-level RBAC
# ---------------------------------------------------------------------------


def derive_user_tier(user_email: str, user_role) -> str:
    """Derive a coarse tier from email + role.

    Returns one of: "admin", "gpu-enabled", "cloud-only".
    ``LOCAL_GPU_ALLOWED_USERS`` env var controls the gpu-enabled allowlist.
    """
    import os
    role_val = user_role.value if hasattr(user_role, "value") else str(user_role)
    if role_val == UserRole.ADMIN.value:
        return "admin"
    email_lc = (user_email or "").lower()
    allowed = set(
        e.strip().lower() for e in os.getenv(
            "LOCAL_GPU_ALLOWED_USERS",
            "aaron@magicunicorn.tech,shafenkhan@users.noreply.github.com",
        ).split(",")
        if e.strip()
    )
    if email_lc and email_lc in allowed:
        return "gpu-enabled"
    return "cloud-only"


def evaluate_agent_access(
    user_email: str,
    user_role,
    user_tier: str,
    access_policy,
    user_attrs=None,
) -> tuple:
    """Evaluate a per-agent access_policy. Returns ``(allowed, reason)``.

    Admins always pass. An absent/empty policy means public. Otherwise the
    allowlists are additive (OR semantics): user passes if ANY rule matches.
    ``require_mfa`` is a GATE — if set and unmet, denies even when allowlists
    would pass.

    Supported policy fields (all optional):
      - public: bool        -> {"public": true} => anyone
      - users: [email]      -> email allowlist
      - tiers: [str]        -> tier allowlist ("admin","gpu-enabled","cloud-only")
      - orgs: [org_id]      -> org membership (requires user_attrs["orgs"])
      - paid_only: bool     -> {"paid_only": true} requires user_attrs["paid"]
      - require_mfa: bool   -> {"require_mfa": true} requires user_attrs["mfa"]

    ``user_attrs`` is an optional dict of extra signals: {"orgs": [...], "paid": bool, "mfa": bool}.
    """
    role_val = user_role.value if hasattr(user_role, "value") else str(user_role)
    if role_val == UserRole.ADMIN.value:
        return True, "admin"

    if not access_policy or not isinstance(access_policy, dict):
        return True, "no-policy"

    attrs = user_attrs or {}

    # MFA gate — if required but missing, deny outright
    if access_policy.get("require_mfa") is True and not attrs.get("mfa"):
        return False, "require-mfa"

    if access_policy.get("public") is True:
        return True, "public"

    email_lc = (user_email or "").lower()
    allowed_users = access_policy.get("users") or []
    if email_lc and email_lc in [str(u).lower() for u in allowed_users]:
        return True, "user-allowlist"

    allowed_tiers = access_policy.get("tiers") or []
    if user_tier and user_tier in allowed_tiers:
        return True, "tier-allowlist"

    allowed_orgs = access_policy.get("orgs") or []
    user_orgs = set(attrs.get("orgs") or [])
    if allowed_orgs and user_orgs.intersection(allowed_orgs):
        return True, "org-membership"

    if access_policy.get("paid_only") is True and attrs.get("paid") is True:
        return True, "paid"

    # Service-key-name allowlist: agents reserved for users provisioned by a
    # specific upstream service (Crisis Ops, etc.) check this. The auth_user
    # carries key_name from the API key record, threaded through user_attrs.
    allowed_key_names = access_policy.get("key_names") or []
    user_key_name = (attrs.get("key_name") or "").lower()
    if user_key_name and user_key_name in [str(k).lower() for k in allowed_key_names]:
        return True, "key-name-allowlist"

    # App membership: agent.accessPolicy.apps is a list of Brigade-consumer
    # apps this agent is offered through. User passes if they're a member of
    # at least one. user.apps is sourced from the DB on each chat call.
    allowed_apps = access_policy.get("apps") or []
    user_apps = set(str(a).lower() for a in (attrs.get("apps") or []))
    if user_apps and user_apps.intersection(set(str(a).lower() for a in allowed_apps)):
        return True, "app-membership"

    return False, "no-match"


def can_user_access_agent(
    user_email: str,
    user_role,
    user_tier: str,
    access_policy,
    user_attrs=None,
) -> bool:
    """Backwards-compatible boolean wrapper around evaluate_agent_access."""
    allowed, _ = evaluate_agent_access(
        user_email, user_role, user_tier, access_policy, user_attrs
    )
    return allowed
