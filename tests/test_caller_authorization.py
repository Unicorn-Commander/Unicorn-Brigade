"""BR-6.4 per-caller authorization tests.

Covers the confused-deputy fix end to end at the unit/loop level (hermetic —
no DB, no network):

  * no-policy passthrough (agents without ``user_policy`` behave exactly as
    before);
  * ``accessPolicy.user_policy`` allow/deny against the EFFECTIVE END-USER
    (allowlist by forwarded id / email, min_role, admin bypass);
  * missing-user deny on policy-bearing agents (no anonymous privilege) and
    the explicit ``allow_service`` opt-out for userless service callers;
  * tool-tier refusal MID-RUN: a tool above the caller's privilege level is
    refused with a model-visible error while the run continues to a normal
    final response;
  * service-caller exemption for the tool guard (userless machine credentials
    keep full privilege by default; the anonymous floor applies to everyone
    else);
  * end-user resolution rules (non-admin humans cannot spoof, admins may
    delegate, the OpenAI-compat shim's backfilled key-id is not an end user).
"""

import pytest

from app.auth.caller_authz import (
    EndUser,
    ToolPermissionGuard,
    build_tool_guard,
    evaluate_user_policy,
    is_service_caller,
    resolve_caller_tool_level,
    resolve_end_user,
    tool_catalog_fail_closed,
    user_policy_denial_detail,
)
from app.auth.middleware import AuthUser
from app.auth.roles import UserRole


def _human(
    role=UserRole.OPERATOR,
    user_id="11111111-1111-1111-1111-111111111111",
    email="human@example.com",
    **kw,
):
    return AuthUser(
        id=user_id, role=role, user_id=user_id, email=email, auth_source="api_key", **kw
    )


def _service_key(key_id="svc-key-1", agent_id="the-colonel", role=UserRole.ADMIN):
    # An agents/api_keys credential: no bound human (no user_id / email).
    return AuthUser(
        id=key_id,
        role=role,
        agent_id=agent_id,
        key_id=key_id,
        key_name="stable-runtime",
        auth_source="api_key",
    )


def _master_admin():
    return AuthUser(
        id="admin", role=UserRole.ADMIN, key_name="Master Admin Key", auth_source="api_key"
    )


# ---------------------------------------------------------------------------
# Service-caller classification
# ---------------------------------------------------------------------------


def test_service_caller_classification():
    assert is_service_caller(_service_key()) is True
    assert is_service_caller(_master_admin()) is True
    assert is_service_caller(_human()) is False
    kc = AuthUser(
        id="u1", role=UserRole.VIEWER, user_id="u1", email="v@example.com", auth_source="keycloak"
    )
    assert is_service_caller(kc) is False


# ---------------------------------------------------------------------------
# End-user resolution
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_non_admin_human_is_always_the_end_user():
    """A non-admin human transport cannot act as anyone else."""
    user = _human(role=UserRole.OPERATOR)
    end_user, service = await resolve_end_user(user, "someone-else", session=None)
    assert service is False
    assert end_user is not None and end_user.resolved
    assert end_user.user_id == user.user_id
    assert end_user.source == "caller"


@pytest.mark.asyncio
async def test_admin_human_may_delegate_a_forwarded_user():
    user = _human(
        role=UserRole.ADMIN,
        user_id="22222222-2222-2222-2222-222222222222",
        email="boss@example.com",
    )
    end_user, service = await resolve_end_user(user, "stable-user-9", session=None)
    assert service is False
    assert end_user is not None
    assert end_user.raw_id == "stable-user-9"
    assert end_user.resolved is False  # no DB session -> unresolved forwarded id
    assert end_user.source == "delegated"


@pytest.mark.asyncio
async def test_service_transport_forwarded_user_and_userless():
    svc = _service_key()
    end_user, service = await resolve_end_user(svc, "stable-user-9", session=None)
    assert service is True
    assert end_user is not None and end_user.raw_id == "stable-user-9"

    none_user, service2 = await resolve_end_user(svc, None, session=None)
    assert none_user is None and service2 is True

    # The OpenAI-compat shim backfills auth_user.id when the client sent no
    # ``user`` — that is the transport itself, not a forwarded human.
    self_user, service3 = await resolve_end_user(svc, svc.id, session=None)
    assert self_user is None and service3 is True

    # Placeholder ids never become end users.
    for placeholder in ("", "admin", "anonymous", "dev-bypass", "opencode"):
        eu, _ = await resolve_end_user(svc, placeholder, session=None)
        assert eu is None


@pytest.mark.asyncio
async def test_anonymous_public_identity_asserts_nobody():
    """A public/anonymous AuthUser is neither an end user nor allowed to
    forward one — only service credentials and admin humans may delegate."""
    anon = AuthUser(id="anonymous", role=UserRole.VIEWER, auth_source="public")
    eu, service = await resolve_end_user(anon, None, session=None)
    assert eu is None and service is False
    eu, service = await resolve_end_user(anon, "vip@example.com", session=None)
    assert eu is None and service is False


# ---------------------------------------------------------------------------
# Agent-level user_policy
# ---------------------------------------------------------------------------


def test_no_user_policy_is_passthrough():
    someone = EndUser(raw_id="u-1", resolved=False)
    for policy in (None, {}, {"users": ["x"]}, {"key_names": ["crisis-ops"]}):
        allowed, reason = evaluate_user_policy(policy, someone, False)
        assert allowed, policy
        assert reason == "no-user-policy"
    # ... even with NO end user at all: policy-less agents keep today's behavior.
    allowed, _ = evaluate_user_policy({"public": True}, None, False)
    assert allowed


def test_user_policy_allowlist_allows_by_raw_id_email_and_sub():
    policy = {"user_policy": {"users": ["stable-user-9", "vip@example.com", "KC-SUB-1"]}}
    assert evaluate_user_policy(policy, EndUser(raw_id="stable-user-9"), False)[0]
    assert evaluate_user_policy(
        policy,
        EndUser(raw_id="u-2", email="VIP@example.com", resolved=True, role="viewer"),
        False,
    )[0]
    assert evaluate_user_policy(policy, EndUser(raw_id="u-3", keycloak_id="kc-sub-1"), False)[0]


def test_user_policy_denies_unlisted_user_with_machine_readable_detail():
    policy = {"user_policy": {"users": ["vip@example.com"]}}
    low = EndUser(raw_id="stable-user-9", resolved=True, role="viewer", email="low@example.com")
    allowed, reason = evaluate_user_policy(policy, low, False)
    assert not allowed and reason == "user-not-allowed"
    detail = user_policy_denial_detail("the-colonel", reason, low)
    assert detail["code"] == "agent_user_policy_denied"
    assert detail["agentId"] == "the-colonel"
    assert detail["userId"] == "stable-user-9"


def test_user_policy_min_role_and_admin_bypass():
    policy = {"user_policy": {"min_role": "operator"}}
    op = EndUser(raw_id="u-1", resolved=True, role="operator")
    viewer = EndUser(raw_id="u-2", resolved=True, role="viewer")
    admin = EndUser(raw_id="u-3", resolved=True, role="admin")
    unresolved = EndUser(raw_id="mystery", resolved=False)
    assert evaluate_user_policy(policy, op, False) == (True, "min-role")
    assert evaluate_user_policy(policy, viewer, False)[0] is False
    assert evaluate_user_policy(policy, admin, False) == (True, "user-admin")
    # An unresolved forwarded id can never satisfy min_role.
    assert evaluate_user_policy(policy, unresolved, False)[0] is False


def test_user_policy_missing_user_denied_and_service_opt_in():
    policy = {"user_policy": {"users": ["vip@example.com"]}}
    # Missing/empty user on a policy-bearing agent -> reject (no anonymous
    # privilege) — including for service callers by default.
    allowed, reason = evaluate_user_policy(policy, None, False)
    assert not allowed and reason == "missing-user"
    allowed, reason = evaluate_user_policy(policy, None, True)
    assert not allowed and reason == "missing-user"
    detail = user_policy_denial_detail("the-colonel", reason, None)
    assert detail["code"] == "agent_user_policy_missing_user"
    # Explicit per-agent opt-in for userless machine automations.
    policy_svc = {"user_policy": {"users": ["vip@example.com"], "allow_service": True}}
    assert evaluate_user_policy(policy_svc, None, True) == (True, "service-exempt")
    # ... but a NON-service caller without a user is still denied.
    assert evaluate_user_policy(policy_svc, None, False)[0] is False


# ---------------------------------------------------------------------------
# Caller privilege level resolution
# ---------------------------------------------------------------------------


def test_caller_level_from_role_and_defaults(monkeypatch):
    monkeypatch.delenv("BRIGADE_USER_TOOL_LEVELS", raising=False)
    monkeypatch.delenv("BRIGADE_USER_TOOL_LEVELS_FILE", raising=False)
    monkeypatch.delenv("BRIGADE_ROLE_TOOL_LEVELS", raising=False)
    assert resolve_caller_tool_level(EndUser(raw_id="a", resolved=True, role="admin"), False) == (
        5,
        "role:admin",
    )
    assert resolve_caller_tool_level(
        EndUser(raw_id="o", resolved=True, role="operator"), False
    ) == (3, "role:operator")
    assert resolve_caller_tool_level(EndUser(raw_id="v", resolved=True, role="viewer"), False) == (
        1,
        "role:viewer",
    )
    # Forwarded id that matched no users row -> unknown-user default (2).
    level, basis = resolve_caller_tool_level(EndUser(raw_id="mystery"), False)
    assert (level, basis) == (2, "unknown-user")


def test_caller_level_service_exemption_and_anonymous_floor(monkeypatch):
    monkeypatch.delenv("BRIGADE_SERVICE_CALLER_TOOL_LEVEL", raising=False)
    monkeypatch.delenv("BRIGADE_NO_USER_TOOL_LEVEL", raising=False)
    # Service caller with no end user keeps full privilege by default...
    assert resolve_caller_tool_level(None, True) == (5, "service")
    # ...and can be capped by config.
    monkeypatch.setenv("BRIGADE_SERVICE_CALLER_TOOL_LEVEL", "2")
    assert resolve_caller_tool_level(None, True) == (2, "service")
    # Everyone else with no user context gets the floor (<=1 tools only).
    assert resolve_caller_tool_level(None, False) == (1, "no-user")


def test_caller_level_per_user_override(monkeypatch):
    monkeypatch.setenv("BRIGADE_USER_TOOL_LEVELS", '{"vip@example.com": 4, "stable-user-9": 3}')
    assert resolve_caller_tool_level(
        EndUser(raw_id="u-1", email="VIP@example.com", resolved=True, role="viewer"),
        False,
    ) == (4, "override")
    assert resolve_caller_tool_level(EndUser(raw_id="stable-user-9"), False) == (3, "override")


# ---------------------------------------------------------------------------
# Tool guard behavior
# ---------------------------------------------------------------------------


def _guard(level, levels=None, mode="enforce"):
    return ToolPermissionGuard(
        caller_level=level,
        caller_basis="test",
        levels=levels or {},
        agent_id="the-colonel",
        end_user_id="stable-user-9",
        transport="api_key:stable-runtime",
        mode=mode,
    )


def test_guard_allows_at_or_below_level_and_refuses_above():
    guard = _guard(2, {"search": 1, "create_task": 2, "database": 4})
    assert guard.check("search") is None
    assert guard.check("create_task") is None
    denial = guard.check("database")
    assert denial and "permission_denied" in denial and "level 4" in denial


def test_missing_catalogue_rows_fail_closed_and_are_logged_once(caplog):
    guard = _guard(5, {"known": 1})

    first = guard.check("never-seen-tool")
    second = guard.check("never-seen-tool")

    assert first and "tool_catalog_missing" in first
    assert second == first
    missing = [r for r in caplog.records if "tool_catalog_missing" in r.message]
    assert len(missing) == 1


def test_catalogue_fail_open_escape_hatch_restores_legacy_level(monkeypatch):
    monkeypatch.setenv("BRIGADE_TOOL_CATALOG_FAIL_CLOSED", "false")
    assert tool_catalog_fail_closed() is False
    guard = _guard(1, {})
    assert guard.check("late-seeded-tool") is None


def test_catalogue_fail_closed_defaults_on_invalid_value(monkeypatch):
    monkeypatch.setenv("BRIGADE_TOOL_CATALOG_FAIL_CLOSED", "not-a-boolean")
    assert tool_catalog_fail_closed() is True


def test_guard_log_mode_audits_but_allows():
    guard = _guard(1, {"database": 4}, mode="log")
    assert guard.check("database") is None


@pytest.mark.asyncio
async def test_build_tool_guard_off_mode_returns_none(monkeypatch):
    monkeypatch.setenv("BRIGADE_TOOL_PERMISSION_ENFORCEMENT", "off")
    guard = await build_tool_guard(None, {"id": "a"}, _human(), None, False)
    assert guard is None
    monkeypatch.setenv("BRIGADE_TOOL_PERMISSION_ENFORCEMENT", "enforce")
    guard = await build_tool_guard(None, {"id": "a"}, _human(), None, False)
    assert guard is not None and guard.mode == "enforce"


# ---------------------------------------------------------------------------
# Tool-tier refusal MID-RUN (execute_tool_loop integration)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tool_tier_refusal_mid_run_continues_the_run(monkeypatch):
    """A refused tool yields a model-visible error result; the loop then feeds
    it back to the LLM and completes normally — the run is NOT killed."""
    from app.llm.ops_center_client import OpsCenterLLMClient, ToolDefinition

    client = OpsCenterLLMClient(ops_center_url="http://test.invalid", service_key="x")

    executed = []

    async def low_handler(**kwargs):
        executed.append("search")
        return {"ok": True}

    async def high_handler(**kwargs):
        executed.append("database")
        return {"ok": True}

    tools = [
        ToolDefinition(name="search", description="d", handler=low_handler),
        ToolDefinition(name="database", description="d", handler=high_handler),
    ]

    responses = [
        {  # LLM asks for BOTH tools: one allowed, one above the caller's level
            "choices": [
                {
                    "message": {
                        "tool_calls": [
                            {
                                "id": "c1",
                                "type": "function",
                                "function": {"name": "search", "arguments": "{}"},
                            },
                            {
                                "id": "c2",
                                "type": "function",
                                "function": {"name": "database", "arguments": "{}"},
                            },
                        ]
                    }
                }
            ],
        },
        {  # terminal answer after seeing the tool results
            "choices": [{"message": {"content": "done"}}],
            "usage": {"total_tokens": 1},
        },
    ]

    async def fake_chat_completion_with_tools(**kwargs):
        return responses.pop(0)

    monkeypatch.setattr(client, "chat_completion_with_tools", fake_chat_completion_with_tools)

    results = []
    response = await client.execute_tool_loop(
        messages=[{"role": "user", "content": "go"}],
        tools=tools,
        tool_guard=_guard(1, {"search": 1, "database": 4}),
        on_tool_result=lambda tr: results.append(tr),
    )

    # Run completed with the terminal LLM answer.
    assert client.get_response_content(response) == "done"
    # The allowed tool executed; the high-tier tool did NOT.
    assert executed == ["search"]
    by_name = {r.name: r for r in results}
    assert by_name["search"].error is None
    assert by_name["database"].error and "permission_denied" in by_name["database"].error


@pytest.mark.asyncio
async def test_no_guard_keeps_existing_behavior(monkeypatch):
    """Internal/service callsites pass no guard — everything executes as before."""
    from app.llm.ops_center_client import OpsCenterLLMClient, ToolDefinition

    client = OpsCenterLLMClient(ops_center_url="http://test.invalid", service_key="x")
    executed = []

    async def high_handler(**kwargs):
        executed.append("database")
        return {"ok": True}

    responses = [
        {
            "choices": [
                {
                    "message": {
                        "tool_calls": [
                            {
                                "id": "c1",
                                "type": "function",
                                "function": {"name": "database", "arguments": "{}"},
                            },
                        ]
                    }
                }
            ]
        },
        {"choices": [{"message": {"content": "done"}}]},
    ]

    async def fake_chat(**kwargs):
        return responses.pop(0)

    monkeypatch.setattr(client, "chat_completion_with_tools", fake_chat)
    response = await client.execute_tool_loop(
        messages=[{"role": "user", "content": "go"}],
        tools=[ToolDefinition(name="database", description="d", handler=high_handler)],
    )
    assert client.get_response_content(response) == "done"
    assert executed == ["database"]


# ---------------------------------------------------------------------------
# Chat-entry helper (_authorize_caller): 403 shape + guard construction
# ---------------------------------------------------------------------------


class _NoDbSession:
    """Session stand-in whose every DB call fails — exercises the best-effort
    paths (_lookup_user_row / catalog load / rbac_denials insert all degrade
    without breaking the request)."""

    async def execute(self, *a, **k):
        raise RuntimeError("no database in unit tests")

    async def commit(self):
        raise RuntimeError("no database in unit tests")


@pytest.mark.asyncio
async def test_authorize_caller_denies_low_priv_user_on_policied_agent(monkeypatch):
    from fastapi import HTTPException

    from app.api.agent_routes import _authorize_caller

    monkeypatch.setenv("BRIGADE_TOOL_PERMISSION_ENFORCEMENT", "enforce")
    agent = {
        "id": "the-colonel",
        "accessPolicy": {"user_policy": {"users": ["vip@example.com"]}},
    }
    svc = _service_key()

    # Confused-deputy scenario: privileged service transport forwards a
    # low-privilege human -> the AGENT-level policy now denies the human even
    # though the transport key is admin-scoped.
    with pytest.raises(HTTPException) as exc:
        await _authorize_caller(_NoDbSession(), svc, agent, "stable-user-9")
    assert exc.value.status_code == 403
    assert exc.value.detail["code"] == "agent_user_policy_denied"

    # Missing user on the same agent -> machine-readable missing-user denial.
    with pytest.raises(HTTPException) as exc:
        await _authorize_caller(_NoDbSession(), svc, agent, None)
    assert exc.value.detail["code"] == "agent_user_policy_missing_user"

    # The allowlisted user passes and receives a guard at the unknown-user
    # level (the forwarded id resolves to no users row here).
    end_user, service_caller, guard = await _authorize_caller(
        _NoDbSession(), svc, {"id": "a", "accessPolicy": None}, "stable-user-9"
    )
    assert service_caller is True
    assert end_user is not None and end_user.raw_id == "stable-user-9"
    assert guard is not None and guard.caller_basis == "unknown-user"


@pytest.mark.asyncio
async def test_authorize_caller_no_policy_passthrough_for_service_flow(monkeypatch):
    """Service caller, no end user, agent without user_policy: allowed, and the
    guard carries the service exemption level."""
    from app.api.agent_routes import _authorize_caller

    monkeypatch.setenv("BRIGADE_TOOL_PERMISSION_ENFORCEMENT", "enforce")
    monkeypatch.delenv("BRIGADE_SERVICE_CALLER_TOOL_LEVEL", raising=False)
    end_user, service_caller, guard = await _authorize_caller(
        _NoDbSession(), _service_key(), {"id": "a", "accessPolicy": {}}, None
    )
    assert end_user is None and service_caller is True
    assert guard is not None
    assert (guard.caller_level, guard.caller_basis) == (5, "service")
    # Full privilege: even a level-5 tool passes for the service flow.
    guard.levels = {"delegate_to_agent": 5}
    assert guard.check("delegate_to_agent") is None
