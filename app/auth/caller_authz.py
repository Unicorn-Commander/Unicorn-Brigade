"""Per-CALLER authorization for agent chat/run entry points (BR-6.4).

Closes the confused-deputy gap: Brigade consumers (Unicorn Stable's runtime,
Crisis Ops, OpenClient SDKs) authenticate with ONE privileged service key and
forward the HUMAN on whose behalf they act (``user`` on the OpenAI-compatible
payload, ``user_id`` on native ChatRequest). Before this module, that forwarded
identity fed ONLY memory isolation and metering — every agent-access decision
was made against the TRANSPORT credential (the service key, frequently
admin-scoped → always allowed), and per-tool ``tool_catalog.permission_level``
was never consulted at execution time at all. Net effect: a low-privilege human
chatting with a high-privilege agent executed config-changing tools with the
agent's full privileges.

Two enforcement layers, both ADDITIVE and fail-compatible:

1. **Agent-level** — ``accessPolicy.user_policy`` (new, optional): evaluated
   against the EFFECTIVE END-USER (the forwarded human, or the authenticated
   human when the caller IS a human), not the transport key. Agents without a
   ``user_policy`` keep today's behavior exactly.

2. **Tool-level** — every caller resolves to a PRIVILEGE LEVEL (1..5, same
   scale as ``tool_catalog.permission_level``). At tool-execution time a tool
   whose required level exceeds the caller's is refused for that run: the agent
   receives a structured tool-error result it can verbalize and the run
   continues (the turn is not killed).

Caller-privilege resolution (first match wins):
  * explicit per-user override — ``BRIGADE_USER_TOOL_LEVELS`` (JSON object,
    user-id-or-email → level) and/or ``BRIGADE_USER_TOOL_LEVELS_FILE`` (path to
    a JSON file with the same shape; the file is the operator-maintained map,
    env wins on conflict). This is the v1 per-user store beyond role defaults.
  * the end user's ROLE → level via ``BRIGADE_ROLE_TOOL_LEVELS``
    (default admin=5, operator=3, viewer=1). For a human caller the role is the
    AuthUser role (already key-scope-derived, so a read-only personal key stays
    low); for a service-forwarded user it is ``users.role`` from the DB.
  * forwarded user that matches NO users row → ``BRIGADE_UNKNOWN_USER_TOOL_LEVEL``
    (default 2: standard tools, never config-changing 3+).
  * no end-user at all:
      - identified SERVICE caller (machine credential with no bound human:
        the master-admin key or an agent/service ``api_keys`` row) →
        ``BRIGADE_SERVICE_CALLER_TOOL_LEVEL`` (default 5 — service-to-service
        flows keep today's full privilege; lower it to cap them).
      - anyone else → ``BRIGADE_NO_USER_TOOL_LEVEL`` (default 1 — the
        anonymous floor: basic util/read tools only).

``BRIGADE_TOOL_PERMISSION_ENFORCEMENT`` = enforce (default) | log | off.
``log`` evaluates + audits but allows — the staged-rollout dry run. Organization
availability is always enforced, including log/off and privileged service keys.

Internal engine callers (scheduler, workflow engine,
agentic_rag) call ``execute_tool_loop`` WITHOUT a guard and are intentionally
unchanged — they are service-originated by definition. Enforcement rides only
the consumer-facing chat entry points, which construct a guard via
``build_tool_guard``. A2A and direct MCP routes apply the same org availability
check without changing their existing privilege rules.

Denials audit two ways: a structured JSON event on the ``brigade.authz`` logger
(both layers) and, for agent-level denials, a row in ``rbac_denials`` via the
existing ``_log_rbac_denial`` helper (the chat routes own that call — this
module stays session-free for the pure parts so it is trivially testable).
"""

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Optional

from app.auth.roles import UserRole
from app.auth.tool_scope import ToolOrgScope, load_tool_org_scope

logger = logging.getLogger(__name__)

# Dedicated audit channel: structured, single-line JSON events. Ships through
# the same logging pipeline as everything else but is grep/ship-able by name.
audit_logger = logging.getLogger("brigade.authz")

# Sentinel "user ids" that mean "no real end user was named". Mirrors the
# placeholder set the memory-isolation code already special-cases.
_PLACEHOLDER_USER_IDS = {"", "admin", "dev-bypass", "anonymous", "opencode"}

# users.role / AuthUser.role string ordering for user_policy.min_role.
_ROLE_ORDER = {"viewer": 1, "operator": 2, "admin": 3}

DEFAULT_ROLE_TOOL_LEVELS = {"admin": 5, "operator": 3, "viewer": 1}


# ---------------------------------------------------------------------------
# Config (env-driven; parsed per call — these are cheap and hot-reloadable)
# ---------------------------------------------------------------------------


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, "") or default)
    except (TypeError, ValueError):
        return default


def enforcement_mode() -> str:
    """enforce (default) | log (audit privileges) | off (org-only guard)."""
    mode = (
        (os.getenv("BRIGADE_TOOL_PERMISSION_ENFORCEMENT", "enforce") or "enforce").strip().lower()
    )
    return mode if mode in ("enforce", "log", "off") else "enforce"


def role_tool_levels() -> dict[str, int]:
    """Role → tool level map. ``BRIGADE_ROLE_TOOL_LEVELS`` (JSON) overrides
    individual entries; unknown/garbage input falls back to the defaults."""
    levels = dict(DEFAULT_ROLE_TOOL_LEVELS)
    raw = os.getenv("BRIGADE_ROLE_TOOL_LEVELS", "")
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                for k, v in parsed.items():
                    levels[str(k).lower()] = int(v)
        except (ValueError, TypeError) as exc:
            logger.warning(f"BRIGADE_ROLE_TOOL_LEVELS unparseable, using defaults: {exc}")
    return levels


def user_tool_level_overrides() -> dict[str, int]:
    """Explicit per-user levels, keyed by user id OR email (lowercased).

    Sources merge in this order (later wins): the JSON FILE named by
    ``BRIGADE_USER_TOOL_LEVELS_FILE`` (operator-maintained map — the v1
    per-user store), then the ``BRIGADE_USER_TOOL_LEVELS`` env JSON. Both are
    best-effort: unreadable/unparseable sources are logged and skipped, never
    fatal to a chat call.
    """
    overrides: dict[str, int] = {}
    path = (os.getenv("BRIGADE_USER_TOOL_LEVELS_FILE", "") or "").strip()
    if path:
        try:
            with open(path, encoding="utf-8") as fh:
                parsed = json.load(fh)
            if isinstance(parsed, dict):
                for k, v in parsed.items():
                    overrides[str(k).strip().lower()] = int(v)
        except (OSError, ValueError, TypeError) as exc:
            logger.warning(f"BRIGADE_USER_TOOL_LEVELS_FILE unreadable ({path}): {exc}")
    raw = os.getenv("BRIGADE_USER_TOOL_LEVELS", "")
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                for k, v in parsed.items():
                    overrides[str(k).strip().lower()] = int(v)
        except (ValueError, TypeError) as exc:
            logger.warning(f"BRIGADE_USER_TOOL_LEVELS unparseable: {exc}")
    return overrides


def service_caller_tool_level() -> int:
    """Level for an identified service caller running with NO end-user.

    Default 5 (full) — service-to-service flows (Stable's worker jobs, cron,
    Ops-Center automations) keep today's behavior. Lower it to cap what
    userless machine runs may execute.
    """
    return _int_env("BRIGADE_SERVICE_CALLER_TOOL_LEVEL", 5)


def no_user_tool_level() -> int:
    """The anonymous floor: a run with no end-user from a NON-service caller.
    Default 1 = basic util/read tools only."""
    return _int_env("BRIGADE_NO_USER_TOOL_LEVEL", 1)


def unknown_user_tool_level() -> int:
    """Level for a forwarded end-user that matches no ``users`` row (a consumer
    app id Brigade has never seen). Default 2: standard tools, nothing
    config-changing. Raise per user via the override map once known."""
    return _int_env("BRIGADE_UNKNOWN_USER_TOOL_LEVEL", 2)


def unknown_tool_permission_level() -> int:
    """Fallback level used only when the catalogue fail-open escape hatch is on.

    The normal, safe behavior is ``tool_catalog_fail_closed()``: an executable
    tool with no catalogue row is refused before its handler runs. Operators can
    temporarily set ``BRIGADE_TOOL_CATALOG_FAIL_CLOSED=false`` for one restart
    when a seed is late; this preserves the old configurable level fallback.
    """
    return _int_env("BRIGADE_UNKNOWN_TOOL_PERMISSION_LEVEL", 1)


def tool_catalog_fail_closed() -> bool:
    """Whether missing ``tool_catalog`` rows refuse tool execution.

    Invalid values deliberately resolve to the safe default (enabled). The
    setting is read when a per-run guard is built, so an operator can change it
    for one restart without changing persisted agent records or catalogue rows.
    """
    raw = (os.getenv("BRIGADE_TOOL_CATALOG_FAIL_CLOSED", "true") or "true").strip().lower()
    return raw not in {"0", "false", "no", "off"}


# ---------------------------------------------------------------------------
# End-user resolution
# ---------------------------------------------------------------------------


@dataclass
class EndUser:
    """The resolved EFFECTIVE END-USER of a chat/run call.

    ``raw_id`` is whatever identifier the request carried (or the transport
    human's id) — it participates in allowlist matching even when it resolves
    to no local users row, so a consumer-side id can be allowlisted verbatim.
    ``resolved`` says whether a local ``users`` row (or the transport's own
    bound human) backs this identity; only resolved users have a trustworthy
    ``role``.
    """

    raw_id: str
    user_id: Optional[str] = None  # canonical users.id when resolved
    email: Optional[str] = None
    role: Optional[str] = None  # "admin" | "operator" | "viewer" when resolved
    keycloak_id: Optional[str] = None
    resolved: bool = False
    source: str = "forwarded"  # "caller" | "delegated" | "forwarded"


def is_service_caller(auth_user: Any) -> bool:
    """True for a MACHINE credential with no bound human: the master-admin key
    (id="admin", no user row) or an agent/service ``api_keys`` credential.
    A human's personal API key / Keycloak session carries user_id+email and is
    NOT a service caller. This is the "service key class" that service-flow
    exemptions key on."""
    if auth_user is None:
        return False
    if getattr(auth_user, "user_id", None) or getattr(auth_user, "email", None):
        return False
    src = getattr(auth_user, "auth_source", "") or ""
    return src in ("api_key", "bypass")


def _role_str(role: Any) -> str:
    return (role.value if hasattr(role, "value") else str(role or "")).lower()


async def _lookup_user_row(session, requested: str):
    """Find a users row by canonical id, Keycloak sub, or email. Best-effort:
    returns None on any failure (a missing row is a normal outcome — consumer
    apps forward their own ids)."""
    if session is None or not requested:
        return None
    try:
        from uuid import UUID as _UUID

        from sqlalchemy import or_, select

        from app.db.models import User as _User

        conds = [_User.keycloak_id == requested]
        if "@" in requested:
            conds.append(_User.email == requested.strip().lower())
        try:
            _UUID(str(requested))
            conds.append(_User.id == requested)
        except (ValueError, TypeError):
            pass  # not a UUID — comparing would make asyncpg raise a cast error
        result = await session.execute(select(_User).where(or_(*conds)))
        return result.scalars().first()
    except Exception as exc:  # noqa: BLE001 — resolution must never break chat
        logger.debug(f"end-user lookup failed for {requested!r}: {exc}")
        return None


async def resolve_end_user(
    auth_user: Any,
    requested_user_id: Optional[str],
    session=None,
) -> tuple[Optional[EndUser], bool]:
    """Resolve ``(end_user, service_caller)`` for a chat/run call.

    Mirrors the memory-isolation identity rules exactly:
      * a NON-ADMIN human transport IS the end user (it cannot spoof another);
      * an ADMIN human transport may delegate — a forwarded id names the end
        user (looked up in ``users``), otherwise the admin themselves;
      * a service transport's forwarded id names the end user; no forwarded id
        → no end user (``None``) — the service-flow case.
    """
    service = is_service_caller(auth_user)
    requested = str(requested_user_id).strip() if requested_user_id is not None else ""
    if requested in _PLACEHOLDER_USER_IDS:
        requested = ""

    own_id = (
        getattr(auth_user, "user_id", None) or getattr(auth_user, "id", None) if auth_user else None
    )
    if (
        auth_user is not None
        and not service
        and own_id
        and str(own_id) not in _PLACEHOLDER_USER_IDS  # "anonymous"/public is nobody
    ):
        role = _role_str(getattr(auth_user, "role", None))
        if role != UserRole.ADMIN.value or not requested or requested == str(own_id):
            # The human themselves (non-admins can never act as anyone else).
            return EndUser(
                raw_id=str(own_id),
                user_id=getattr(auth_user, "user_id", None) or str(own_id),
                email=(getattr(auth_user, "email", None) or None),
                role=role or None,
                keycloak_id=getattr(auth_user, "keycloak_id", None),
                resolved=True,
                source="caller",
            ), False
        # Admin delegation: the forwarded id is the end user.
        row = await _lookup_user_row(session, requested)
        if row is not None:
            return EndUser(
                raw_id=requested,
                user_id=str(row.id),
                email=row.email,
                role=_role_str(row.role) or None,
                keycloak_id=getattr(row, "keycloak_id", None),
                resolved=True,
                source="delegated",
            ), False
        return EndUser(raw_id=requested, resolved=False, source="delegated"), False

    # Only a SERVICE credential (or an admin human, handled above) may assert a
    # forwarded end user. An anonymous/public identity that somehow reaches a
    # chat surface asserts nobody.
    if not service:
        return None, False

    # Service transport. A "user" equal to the credential's OWN id/key-id is
    # the transport talking about itself, not a forwarded human — the
    # OpenAI-compat shim backfills auth_user.id into user_id when the client
    # sent no ``user``, and that must not masquerade as an end user.
    own_ids = {
        str(getattr(auth_user, "id", "") or ""),
        str(getattr(auth_user, "key_id", "") or ""),
        str(getattr(auth_user, "agent_id", "") or ""),
    }
    if not requested or requested in own_ids:
        return None, service
    row = await _lookup_user_row(session, requested)
    if row is not None:
        return EndUser(
            raw_id=requested,
            user_id=str(row.id),
            email=row.email,
            role=_role_str(row.role) or None,
            keycloak_id=getattr(row, "keycloak_id", None),
            resolved=True,
            source="forwarded",
        ), service
    return EndUser(raw_id=requested, resolved=False, source="forwarded"), service


# ---------------------------------------------------------------------------
# Agent-level user policy (accessPolicy.user_policy)
# ---------------------------------------------------------------------------


def evaluate_user_policy(
    access_policy: Any,
    end_user: Optional[EndUser],
    service_caller: bool = False,
) -> tuple[bool, str]:
    """Evaluate ``accessPolicy.user_policy`` against the EFFECTIVE END-USER.

    Returns ``(allowed, reason)``. No policy (or an empty one) → allow —
    agents without a user policy keep today's behavior byte-for-byte.

    Policy shape (all fields optional, additive to the existing accessPolicy):
      {"user_policy": {
          "users": ["<users.id | keycloak sub | email | consumer-side id>"],
          "min_role": "operator",       # minimum RESOLVED users.role
          "allow_service": true          # userless service callers may run it
      }}

    Semantics:
      * A RESOLVED end user with role "admin" always passes (matches the
        admin-bypass convention of ``evaluate_agent_access``).
      * ``users`` matches the raw forwarded id, canonical id, email (ci), or
        Keycloak sub — so consumer-side ids can be allowlisted verbatim.
      * ``min_role`` passes when the end user RESOLVED to a users row whose
        role meets the bar (viewer < operator < admin). An unresolved
        forwarded id can never satisfy it.
      * NO end user: denied ("missing-user" — no anonymous privilege), unless
        the caller is an identified SERVICE credential and the policy opts in
        with ``allow_service: true`` (machine automations on a locked agent).
      * A user_policy carrying NO users/min_role rule is an explicit lockdown:
        only admin end-users (and opted-in service callers) pass.
    """
    if not access_policy or not isinstance(access_policy, dict):
        return True, "no-user-policy"
    policy = access_policy.get("user_policy")
    if not policy or not isinstance(policy, dict):
        return True, "no-user-policy"

    if end_user is None:
        if service_caller and policy.get("allow_service") is True:
            return True, "service-exempt"
        return False, "missing-user"

    if end_user.resolved and (end_user.role or "") == "admin":
        return True, "user-admin"

    allowed_users = policy.get("users") or []
    if allowed_users:
        needles = {
            s
            for s in (
                (end_user.raw_id or "").lower(),
                (end_user.user_id or "").lower(),
                (end_user.email or "").lower(),
                (end_user.keycloak_id or "").lower(),
            )
            if s
        }
        haystack = {str(u).strip().lower() for u in allowed_users if str(u).strip()}
        if needles & haystack:
            return True, "user-allowlist"

    min_role = str(policy.get("min_role") or "").strip().lower()
    if min_role and end_user.resolved:
        have = _ROLE_ORDER.get((end_user.role or "").lower(), 0)
        need = _ROLE_ORDER.get(min_role, 0)
        if need and have >= need:
            return True, "min-role"

    return False, "user-not-allowed"


def user_policy_denial_detail(
    agent_id: str,
    reason: str,
    end_user: Optional[EndUser],
) -> dict[str, Any]:
    """Machine-readable 403 body for a user_policy denial. The ``code`` is the
    stable contract consumers (Stable's runtime) branch on to surface a clean
    message; everything else is context."""
    code = (
        "agent_user_policy_missing_user"
        if reason in ("missing-user",)
        else "agent_user_policy_denied"
    )
    return {
        "message": f"Agent '{agent_id}' is not available to this user",
        "code": code,
        "reason": reason,
        "agentId": agent_id,
        "userId": (end_user.raw_id if end_user else None),
    }


def log_agent_access_denied(
    agent_id: str,
    reason: str,
    end_user: Optional[EndUser],
    auth_user: Any = None,
    request_path: str = "",
) -> None:
    """Structured audit event for an agent-level per-user denial."""
    try:
        audit_logger.warning(
            json.dumps(
                {
                    "event": "agent_access_denied",
                    "layer": "user_policy",
                    "ts": datetime.now(UTC).isoformat(),
                    "agent_id": agent_id,
                    "reason": reason,
                    "end_user": (end_user.raw_id if end_user else None),
                    "end_user_resolved": bool(end_user and end_user.resolved),
                    "transport_id": str(getattr(auth_user, "id", "") or ""),
                    "transport_key": getattr(auth_user, "key_name", None),
                    "transport_role": _role_str(getattr(auth_user, "role", None)),
                    "auth_source": getattr(auth_user, "auth_source", None),
                    "path": request_path,
                }
            )
        )
    except Exception:  # noqa: BLE001 — auditing must never break the request
        logger.debug("agent_access_denied audit emit failed", exc_info=True)


# ---------------------------------------------------------------------------
# Tool-level permission guard
# ---------------------------------------------------------------------------


def resolve_caller_tool_level(
    end_user: Optional[EndUser],
    service_caller: bool = False,
) -> tuple[int, str]:
    """The privilege LEVEL a caller's tools run at, plus the basis for it
    (override / role:<r> / unknown-user / service / no-user) for audit."""
    if end_user is not None:
        overrides = user_tool_level_overrides()
        for key in (end_user.user_id, end_user.raw_id, end_user.email):
            k = str(key).strip().lower() if key else ""
            if k and k in overrides:
                return overrides[k], "override"
        if end_user.resolved:
            levels = role_tool_levels()
            role = (end_user.role or "").lower()
            if role in levels:
                return levels[role], f"role:{role}"
        return unknown_user_tool_level(), "unknown-user"
    if service_caller:
        return service_caller_tool_level(), "service"
    return no_user_tool_level(), "no-user"


@dataclass
class ToolPermissionGuard:
    """Per-run tool gate handed into ``execute_tool_loop`` (duck-typed — the
    loop only calls ``check``). ``check`` returns None to allow, or the
    model-visible refusal string; refusals are audited here so every execution
    site gets auditing for free."""

    caller_level: int
    caller_basis: str
    levels: dict[str, int] = field(default_factory=dict)
    agent_id: str = ""
    end_user_id: Optional[str] = None
    transport: str = ""
    mode: str = "enforce"
    fail_closed: bool = field(default_factory=tool_catalog_fail_closed)
    org_scope: ToolOrgScope = field(default_factory=ToolOrgScope)
    _missing_catalogue_logged: set[str] = field(default_factory=set, init=False, repr=False)

    def required_level(self, tool_name: str) -> int:
        try:
            return int(self.levels.get(tool_name, unknown_tool_permission_level()))
        except (TypeError, ValueError):
            return unknown_tool_permission_level()

    def check(self, tool_name: str) -> Optional[str]:
        if denial := self.org_scope.check(tool_name):
            return denial
        if self.mode == "off":
            return None
        if tool_name not in self.levels:
            if self.fail_closed:
                self._audit_catalogue_missing(tool_name)
                return (
                    f"tool_catalog_missing: tool '{tool_name}' has no catalogue "
                    "row, so it was NOT executed. Seed tool_catalog before "
                    "enabling this tool."
                )
        required = self.required_level(tool_name)
        if self.caller_level >= required:
            return None
        self._audit(tool_name, required)
        if self.mode == "log":
            return None  # dry run: audited, not blocked
        return (
            f"permission_denied: tool '{tool_name}' requires permission level "
            f"{required}, but this request is authorized at level "
            f"{self.caller_level}. The tool was NOT executed. Explain that this "
            "action needs elevated access and continue helping without it."
        )

    def _audit(self, tool_name: str, required: int) -> None:
        try:
            audit_logger.warning(
                json.dumps(
                    {
                        "event": "tool_permission_denied",
                        "layer": "tool_permission",
                        "ts": datetime.now(UTC).isoformat(),
                        "agent_id": self.agent_id,
                        "tool": tool_name,
                        "required_level": required,
                        "caller_level": self.caller_level,
                        "caller_basis": self.caller_basis,
                        "end_user": self.end_user_id,
                        "transport": self.transport,
                        "mode": self.mode,
                    }
                )
            )
        except Exception:  # noqa: BLE001
            logger.debug("tool_permission_denied audit emit failed", exc_info=True)

    def _audit_catalogue_missing(self, tool_name: str) -> None:
        """Emit one structured warning per missing tool name for this run."""
        if tool_name in self._missing_catalogue_logged:
            return
        self._missing_catalogue_logged.add(tool_name)
        try:
            audit_logger.error(
                json.dumps(
                    {
                        "event": "tool_catalog_missing",
                        "layer": "tool_permission",
                        "ts": datetime.now(UTC).isoformat(),
                        "agent_id": self.agent_id,
                        "tool": tool_name,
                        "caller_level": self.caller_level,
                        "caller_basis": self.caller_basis,
                        "end_user": self.end_user_id,
                        "transport": self.transport,
                        "fail_closed": True,
                    }
                )
            )
        except Exception:  # noqa: BLE001
            logger.debug("tool_catalog_missing audit emit failed", exc_info=True)


async def load_tool_permission_levels(session) -> dict[str, int]:
    """Load ``tool_catalog`` name → permission level.

    An unavailable or pre-migration catalogue returns ``{}``; with the safe
    default guard setting this makes every guarded tool call fail closed rather
    than silently treating every name as level 1.
    """
    if session is None:
        return {}
    try:
        from sqlalchemy import text as _text

        rows = await session.execute(_text("SELECT name, permission_level FROM tool_catalog"))
        return {r[0]: int(r[1] or 1) for r in rows}
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            f"tool_catalog unavailable; guarded tools will fail closed "
            f"unless BRIGADE_TOOL_CATALOG_FAIL_CLOSED=false: {exc}"
        )
        return {}


async def build_tool_guard(
    session,
    agent: Optional[dict[str, Any]],
    auth_user: Any,
    end_user: Optional[EndUser],
    service_caller: bool,
) -> ToolPermissionGuard:
    """Construct the per-run guard. Org isolation also applies in off/log mode."""
    mode = enforcement_mode()
    org_scope = await load_tool_org_scope(session, getattr(auth_user, "org_id", None))
    level, basis = resolve_caller_tool_level(end_user, service_caller)
    levels = await load_tool_permission_levels(session) if mode != "off" else {}
    return ToolPermissionGuard(
        caller_level=level,
        caller_basis=basis,
        levels=levels,
        agent_id=str((agent or {}).get("id") or ""),
        end_user_id=(end_user.raw_id if end_user else None),
        transport=(
            f"{getattr(auth_user, 'auth_source', '')}:"
            f"{getattr(auth_user, 'key_name', None) or getattr(auth_user, 'id', '')}"
        ),
        mode=mode,
        fail_closed=tool_catalog_fail_closed(),
        org_scope=org_scope,
    )
