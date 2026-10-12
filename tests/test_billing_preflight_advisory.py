# Executed by Grok (headless lane)
"""Pins advisory billing-preflight behavior.

A non-200 from Ops-Center is fail-open: one WARNING per caller per interval,
never an ERROR on the chat path, and the request is allowed. An authoritative
empty balance is still a 402. Native chat and the OpenAI-compat paths call
the same gate.
"""

import ast
import json
import logging
from pathlib import Path

import httpx
import pytest
from fastapi import HTTPException

from app.api import agent_routes
from app.auth.middleware import AuthUser
from app.auth.roles import UserRole
from app.integrations import ops_center_billing as billing

EMAIL = "deploy-smoke@magicunicorn.tech"
TEST_SERVICE_KEY = "test-service-key-" + "x" * 32
_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _reset_billing(monkeypatch):
    billing._cache.clear()
    billing._advisory_logged_at.clear()
    monkeypatch.setattr(billing, "BRIGADE_SERVICE_KEY", TEST_SERVICE_KEY)
    monkeypatch.setattr(billing, "OPS_CENTER_URL", "http://ops-center.test")
    monkeypatch.setattr(agent_routes, "_BILLING_STRICT", False)
    yield
    billing._cache.clear()
    billing._advisory_logged_at.clear()


class _Resp:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        if isinstance(payload, str):
            self.text = payload
        else:
            self.text = json.dumps(payload)
        self._payload = payload

    def json(self):
        if isinstance(self._payload, str):
            return json.loads(self._payload)
        return self._payload


class _Client:
    def __init__(self, handler):
        self._handler = handler

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, url, headers=None):
        return await self._handler(url, headers)


def _install(monkeypatch, handler):
    monkeypatch.setattr(billing.httpx, "AsyncClient", lambda *a, **k: _Client(handler))


def _operator(email=EMAIL):
    return AuthUser(id="user-1", role=UserRole.OPERATOR, email=email, key_name="deploy-smoke")


def _warnings(caplog):
    return [
        r for r in caplog.records
        if r.levelno == logging.WARNING
        and r.name.startswith("app.integrations.ops_center_billing")
    ]


def _errors(caplog):
    return [
        r for r in caplog.records
        if r.levelno >= logging.ERROR
        and (
            r.name.startswith("app.integrations.ops_center_billing")
            or r.name.startswith("app.api.agent_routes")
        )
    ]


async def test_401_is_fail_open_and_warns_once_per_caller(monkeypatch, caplog):
    caplog.set_level(logging.DEBUG, logger="app.integrations.ops_center_billing")
    calls = []

    async def handler(url, headers):
        calls.append((url, dict(headers or {})))
        return _Resp(401, {"detail": "Not authenticated"})

    _install(monkeypatch, handler)
    user = _operator()

    state = await billing.get_billing_state(EMAIL)
    agent_routes._enforce_billing_or_402(user, state)

    assert state["lookup"] == "unavailable"
    assert state["lookup_error"] == "HTTP 401"
    assert calls[0][0] == "http://ops-center.test/api/v1/billing/state"
    assert calls[0][1]["X-Service-Key"] == TEST_SERVICE_KEY
    assert calls[0][1]["X-User-ID"] == EMAIL
    assert "Authorization" not in calls[0][1]

    # Cached miss: no second connection. The gate shares the warning window.
    state2 = await billing.get_billing_state(EMAIL)
    agent_routes._enforce_billing_or_402(user, state2)
    assert len(calls) == 1

    billing._cache.clear()
    await billing.get_billing_state(EMAIL)
    agent_routes._enforce_billing_or_402(
        user, {"lookup": "unavailable", "lookup_error": "HTTP 401"},
    )
    assert len(calls) == 2
    assert len(_warnings(caplog)) == 1
    assert _errors(caplog) == []
    message = _warnings(caplog)[0].getMessage()
    assert "401" in message
    assert "fail-open" in message


async def test_advisory_window_reopens_and_is_per_caller(monkeypatch, caplog):
    caplog.set_level(logging.DEBUG, logger="app.integrations.ops_center_billing")

    async def handler(url, headers):
        return _Resp(401, {"detail": "Not authenticated"})

    _install(monkeypatch, handler)
    await billing.get_billing_state(EMAIL)
    billing._cache.clear()
    await billing.get_billing_state("other@magicunicorn.tech")
    assert len(_warnings(caplog)) == 2

    # 0.0 is far outside the window relative to time.monotonic().
    billing._advisory_logged_at[EMAIL] = 0.0
    billing._cache.clear()
    await billing.get_billing_state(EMAIL)
    assert len(_warnings(caplog)) == 3
    assert _errors(caplog) == []


async def test_authoritative_empty_balance_still_402s(monkeypatch, caplog):
    caplog.set_level(logging.DEBUG, logger="app.integrations.ops_center_billing")

    async def handler(url, headers):
        return _Resp(200, {
            "paid": False,
            "credits_remaining": 0,
            "subscription_tier": "trial",
        })

    _install(monkeypatch, handler)
    state = await billing.get_billing_state(EMAIL)
    assert state["lookup"] == "ok"
    with pytest.raises(HTTPException) as exc:
        agent_routes._enforce_billing_or_402(_operator(), state)
    assert exc.value.status_code == 402
    assert _warnings(caplog) == []
    assert _errors(caplog) == []

    agent_routes._enforce_billing_or_402(
        _operator(),
        {"lookup": "ok", "paid": True, "credits_remaining": 0},
    )


def test_strict_mode_turns_a_miss_into_503(monkeypatch, caplog):
    caplog.set_level(logging.DEBUG, logger="app.integrations.ops_center_billing")
    monkeypatch.setattr(agent_routes, "_BILLING_STRICT", True)
    with pytest.raises(HTTPException) as exc:
        agent_routes._enforce_billing_or_402(
            _operator(),
            {"lookup": "unavailable", "lookup_error": "HTTP 401"},
        )
    assert exc.value.status_code == 503
    assert len(_warnings(caplog)) == 1
    assert _errors(caplog) == []


def test_admin_skips_the_gate(caplog):
    caplog.set_level(logging.DEBUG, logger="app.integrations.ops_center_billing")
    agent_routes._enforce_billing_or_402(
        AuthUser(id="admin", role=UserRole.ADMIN, email=EMAIL),
        {"lookup": "unavailable", "lookup_error": "HTTP 401"},
    )
    assert _warnings(caplog) == []
    assert _errors(caplog) == []


async def test_missing_service_key_does_not_call_out(monkeypatch, caplog):
    caplog.set_level(logging.DEBUG, logger="app.integrations.ops_center_billing")
    monkeypatch.setattr(billing, "BRIGADE_SERVICE_KEY", "")
    called = {"n": 0}

    async def handler(url, headers):
        called["n"] += 1
        return _Resp(200, {"paid": True, "credits_remaining": 1})

    _install(monkeypatch, handler)
    state = await billing.get_billing_state(EMAIL)
    assert called["n"] == 0
    assert state["lookup"] == "unavailable"
    assert "BRIGADE_SERVICE_KEY" in state["lookup_error"]
    agent_routes._enforce_billing_or_402(_operator(), state)
    assert len(_warnings(caplog)) == 1
    assert _errors(caplog) == []


async def test_weak_service_key_does_not_call_out(monkeypatch, caplog):
    caplog.set_level(logging.DEBUG, logger="app.integrations.ops_center_billing")
    monkeypatch.setattr(billing, "BRIGADE_SERVICE_KEY", "1234567")
    called = {"n": 0}

    async def handler(url, headers):
        called["n"] += 1
        return _Resp(200, {"paid": True, "credits_remaining": 1})

    _install(monkeypatch, handler)
    state = await billing.get_billing_state(EMAIL)

    assert called["n"] == 0
    assert state["lookup"] == "unavailable"
    assert "weak" in state["lookup_error"]
    assert len(_warnings(caplog)) == 1


async def test_transport_error_is_cached_and_advisory(monkeypatch, caplog):
    caplog.set_level(logging.DEBUG, logger="app.integrations.ops_center_billing")
    calls = {"n": 0}

    async def handler(url, headers):
        calls["n"] += 1
        raise httpx.ConnectError("connection refused")

    _install(monkeypatch, handler)
    state = await billing.get_billing_state(EMAIL)
    again = await billing.get_billing_state(EMAIL)
    assert calls["n"] == 1
    assert state["lookup"] == "unavailable"
    assert again["lookup"] == "unavailable"
    assert "ConnectError" in state["lookup_error"]
    assert len(_warnings(caplog)) == 1
    assert _errors(caplog) == []


def test_openai_compat_and_native_chat_call_the_same_gate():
    def _calls(path, names):
        tree = ast.parse(path.read_text())
        found = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef) and node.name in names:
                found[node.name] = "_enforce_billing_or_402" in ast.dump(node)
        return found

    assert _calls(
        _ROOT / "app/api/openai_compat_routes.py",
        {"_passthrough_chat", "_dual_layer_chat", "_enhanced_stream_chat"},
    ) == {
        "_passthrough_chat": True,
        "_dual_layer_chat": True,
        "_enhanced_stream_chat": True,
    }
    assert _calls(
        _ROOT / "app/api/agent_routes.py",
        {"chat_with_agent", "chat_with_agent_local"},
    ) == {
        "chat_with_agent": True,
        "chat_with_agent_local": True,
    }
