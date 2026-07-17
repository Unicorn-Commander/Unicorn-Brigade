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

    # MCP catalog: NOT public. The protocol-compliant, customer-facing MCP
    # discovery surface is the key-authed federation gateway at /mcp
    # (federation_mcp_router). The legacy /api/v1/mcp/* catalog reads leak the
    # full tool inventory + parameter schemas, so on an internet-reachable prod
    # (FEDERATION_ONLY=false) they now require an api_key (BR-6.2 / BR-0.9).

    # Read-only stats
    "/api/v1/stats",
    "/api/v1/models",

    # Slack webhooks (verify via signing secret instead)
    "/api/v1/slack/events",
    "/api/v1/slack/interactions",
    "/api/v1/slack/commands",

    # ---- audit2 auth-surface pass ----
    # Health checks + static capability/reference lists for the feature routers
    # hardened in the audit2 pass. These handlers carry NO auth dependency and are
    # intentionally public; they are listed here so the public surface is EXPLICIT
    # (and stays public if a global auth gate is ever added). Everything else on
    # these routers now requires api_key/operator/admin per-route.
    "/api/v1/medical/health",
    "/api/v1/medical/models",           # static model/capability catalog
    "/api/v1/monitoring/health",
    "/api/v1/calendar/health",
    "/api/v1/crisis/health",
    "/api/v1/github/health",
    "/api/v1/ralph/health",
    "/api/v1/benchmarks/health",
    "/api/v1/benchmarks/configs",       # static model-config catalog
    "/api/v1/benchmarks/workflows",     # static workflow catalog
    "/api/v1/benchmarks/leaderboard",   # public leaderboard
    "/api/v1/documents/templates",      # static extraction-template catalog
    "/api/v1/documents/supported-types",  # static supported-file-type list
    "/api/v1/finance/categories",       # static expense-category enum
    "/api/v1/finance/currencies",       # static currency list
    "/api/v1/finance/transaction-types",  # static transaction-type enum
    "/api/v1/voice/providers",          # static STT/TTS provider catalog
    "/api/v1/voice/providers/stt",
    "/api/v1/voice/providers/tts",
    "/api/v1/voice/voices",             # available-voices list
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
# BR-2.6 — canonical permission derivation (single source of truth)
# ---------------------------------------------------------------------------
#
# Historically this logic was COPY-PASTED across ≥4 sites that drifted:
#   - admin_keys_routes._permissions_for_role
#   - user_routes._get_permissions_for_role
#   - two role-from-permissions blocks in auth/middleware.validate_api_key
# They now all delegate here so the role↔scope mapping cannot diverge.


def permissions_for_role(role) -> list:
    """Canonical DEFAULT API-key permission scopes for a coarse role.

    admin  -> ["admin","write","chat","read"]
    operator -> ["write","chat","read"]
    everything else (viewer) -> ["read"]
    """
    role_val = role.value if hasattr(role, "value") else str(role or "").lower()
    if role_val == UserRole.ADMIN.value:
        return ["admin", "write", "chat", "read"]
    if role_val == UserRole.OPERATOR.value:
        return ["write", "chat", "read"]
    return ["read"]


def role_from_permissions(permissions, base_role=None) -> UserRole:
    """Canonical coarse-role derivation from a credential's scopes.

    ADMIN    if ``base_role``=="admin" OR the "admin" scope is present.
    OPERATOR if ``base_role``=="operator" OR a "write"/"chat" scope is present.
    VIEWER   otherwise.

    ``base_role`` is the user's stored ``users.role`` string when the credential
    is a USER API key (so a stored operator/admin still resolves even with a
    read-only key). Pass ``None`` for an AGENT/SERVICE key that has no backing
    user row — then only the key's scopes decide. This reproduces the exact prior
    behavior of both middleware sites, byte-for-byte, now from one place.
    """
    perms = {str(p).lower() for p in (permissions or [])}
    br = (base_role.value if hasattr(base_role, "value") else str(base_role or "")).lower()
    if br == "admin" or "admin" in perms:
        return UserRole.ADMIN
    if br == "operator" or "write" in perms or "chat" in perms:
        return UserRole.OPERATOR
    return UserRole.VIEWER


# AMR (authentication-methods-references) values that denote a genuine SECOND
# factor. Deliberately EXCLUDES "pwd"/"cookie" (single-factor). Keycloak emits
# amr per configured authenticator; other IdPs use OIDC-standard tokens.
_MFA_AMR_METHODS = {
    "mfa", "otp", "totp", "hwk", "hardware", "sms", "webauthn",
    "u2f", "fido", "fido2", "duo", "push", "swk", "hotp",
}
# ACR (authentication-context-class-reference) values / LoA labels denoting >=2FA.
_MFA_ACR_VALUES = {"mfa", "aal2", "aal3", "loa2", "loa3", "gold", "silver"}


def mfa_satisfied(claims) -> bool:
    """Whether an OIDC token's ``acr``/``amr`` prove multi-factor authentication.

    True when ``amr`` lists a recognized second-factor method, when ``acr`` is a
    known multi-factor LoA label, or when ``acr`` is a numeric level >= 2 (the
    Keycloak "acr-to-LoA" convention where "1" = single, "2"+ = step-up). A
    password-only login (amr=["pwd"], acr="1") returns False.

    This is the signal that feeds the ``require_mfa`` gate in
    ``evaluate_agent_access`` (previously always False — a decorative gate).
    """
    if not isinstance(claims, dict):
        return False
    amr = claims.get("amr")
    if isinstance(amr, str):
        amr = [amr]
    methods = {str(m).lower() for m in (amr or [])}
    if methods & _MFA_AMR_METHODS:
        return True
    acr = str(claims.get("acr", "")).strip().lower()
    if acr in _MFA_ACR_VALUES:
        return True
    if acr.isdigit() and int(acr) >= 2:
        return True
    return False


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


# ---------------------------------------------------------------------------
# BR-2.5 — per-key MCP tool scopes (read / chat / write / admin)
# ---------------------------------------------------------------------------
#
# A single Brigade API key (the "one-key MCP" credential a customer wires into
# their MCP client) carries a subset of these scopes in ``ApiKey.permissions``
# (e.g. ["read"], ["chat","read"], ["write","chat","read"], ["admin",...]). The
# federation MCP gateway (app/federation/mcp_gateway.py) uses these helpers to
# gate each federated tool by the KEY's scope so a read-only key cannot invoke a
# write/exec tool. Ordered least→most privileged; higher levels subsume lower.
MCP_SCOPE_LEVELS = {"read": 1, "chat": 2, "write": 3, "admin": 4}


def mcp_scope_level(user_role, permissions) -> int:
    """Return the MCP access LEVEL a caller's credential grants (0 = none).

    Prefer the EXPLICIT per-key scopes in ``permissions`` — this is how Brigade
    API keys model read/chat/write/admin, and it is the authoritative signal for
    a scoped one-key credential. Only when the caller carries NONE of those named
    scopes (e.g. a Keycloak human whose ``permissions`` are realm/client role
    names, or the master-admin key with an empty list) do we fall back to the
    coarse ``UserRole``: ADMIN→admin, OPERATOR→write, VIEWER→read.

    Deriving from the explicit scopes first is what keeps a *chat* key (whose role
    resolves to OPERATOR because "chat" is present) from being treated as
    write-capable — the scope, not the derived role, decides tool access.
    """
    perms = [str(p).lower() for p in (permissions or [])]
    explicit = [MCP_SCOPE_LEVELS[p] for p in perms if p in MCP_SCOPE_LEVELS]
    if explicit:
        return max(explicit)

    role_val = user_role.value if hasattr(user_role, "value") else str(user_role)
    if role_val == UserRole.ADMIN.value:
        return MCP_SCOPE_LEVELS["admin"]
    if role_val == UserRole.OPERATOR.value:
        return MCP_SCOPE_LEVELS["write"]
    if role_val == UserRole.VIEWER.value:
        return MCP_SCOPE_LEVELS["read"]
    return 0


def mcp_tool_required_level(read_only: bool, scopes_required=None) -> int:
    """Minimum key scope LEVEL required to invoke a federated MCP tool.

    A tool the app declares ``read_only`` needs only ``read``; every other tool is
    treated as a write/exec tool and needs ``write`` (so read- and chat-scoped
    keys are refused). Tools that don't declare ``read_only`` default to write —
    fail-closed. ``scopes_required`` (the downstream app's own scope names) is
    accepted for future refinement but does not currently lower the bar.
    """
    return MCP_SCOPE_LEVELS["read"] if read_only else MCP_SCOPE_LEVELS["write"]


def key_permits_mcp_tool(user_role, permissions, *, read_only, scopes_required=None) -> bool:
    """True iff a credential's scope is sufficient to invoke the given MCP tool.

    read/chat keys → read_only tools only; write/admin keys → all tools.
    """
    return mcp_scope_level(user_role, permissions) >= mcp_tool_required_level(
        read_only, scopes_required
    )
