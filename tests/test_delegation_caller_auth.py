"""Delegation runs AS THE CALLER (Project-Ops 2e350195).

delegate_to_agent calls Brigade's own chat endpoint for the target agent. It
used to authenticate with the master-admin key, which always binds the shared
default org, so a person in another org (an orchestrator in the "majiks" org
handing off to its catalog specialist) got a 404. It also ran every delegated
agent with admin rights. The chat route now keeps the request's own credential,
and the delegation replays it: same identity, same org, same role. Paths
without a caller credential, such as the scheduler, still use the master key.
"""
from __future__ import annotations

import inspect

from fastapi import Request

import app.api.agent_routes as agent_routes
import app.llm.delegation_tools as delegation
from app.auth.middleware import AUTH_HEADER, OIDC_SESSION_COOKIE


def test_the_forwarded_credential_names_match_the_middleware():
    assert AUTH_HEADER == "X-API-Key"
    assert OIDC_SESSION_COOKIE == delegation.SESSION_COOKIE


def test_forwardable_auth_keeps_only_credentials_and_the_org():
    headers = {"authorization": "Bearer tok", "x-api-key": "k", "x-org-id": "org-9", "host": "x", "cookie": "a=b"}
    cookies = {"brigade_session": "s", "other": "o"}
    assert delegation.forwardable_auth(headers, cookies) == {
        "Authorization": "Bearer tok", "X-API-Key": "k", "Cookie": "brigade_session=s", "X-Org-Id": "org-9",
    }


def test_no_credential_means_nothing_to_forward():
    assert delegation.forwardable_auth({"host": "x"}, {}) is None
    assert delegation.forwardable_auth({"x-org-id": "org-9"}, {}) is None  # an org alone is not a credential
    assert delegation.forwardable_auth({"Authorization": "", "X-API-Key": ""}) is None


def _fake_http(monkeypatch, sent):
    class _Resp:
        status_code = 200
        text = ""

        def json(self):
            return {"content": "done"}

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def post(self, url, headers=None, json=None):
            sent.update(url=url, headers=headers, json=json)
            return _Resp()

    monkeypatch.setattr(delegation.httpx, "AsyncClient", _Client)
    monkeypatch.setattr(delegation, "BRIGADE_API_KEY", "MASTER-SENTINEL")


async def test_a_delegation_replays_the_callers_credential_not_the_master_key(monkeypatch):
    sent = {}
    _fake_http(monkeypatch, sent)
    token = delegation._CALLER_AUTH.set({"Authorization": "Bearer person-token", "X-Org-Id": "majiks-org"})
    try:
        out = await delegation.delegate_to_agent_handler(agent_id="majik-catalog", task="find the stems", caller_user_id="u-1")
    finally:
        delegation._CALLER_AUTH.reset(token)
    assert out["success"] is True
    assert sent["headers"]["Authorization"] == "Bearer person-token"
    assert sent["headers"]["X-Org-Id"] == "majiks-org"
    assert "MASTER-SENTINEL" not in str(sent["headers"])
    assert sent["headers"]["X-Delegate-User"] == "u-1"


async def test_without_a_caller_credential_the_master_key_is_used(monkeypatch):
    sent = {}
    _fake_http(monkeypatch, sent)
    assert delegation._CALLER_AUTH.get() is None
    await delegation.delegate_to_agent_handler(agent_id="the-general", task="plan")
    assert sent["headers"]["X-API-Key"] == "MASTER-SENTINEL"
    assert "Authorization" not in sent["headers"]


def test_both_chat_paths_carry_the_caller_credential():
    params = inspect.signature(agent_routes.chat_with_agent).parameters
    assert params["http_request"].annotation in (Request, "Request")
    assert "caller_auth" in inspect.signature(agent_routes._stream_chat).parameters
