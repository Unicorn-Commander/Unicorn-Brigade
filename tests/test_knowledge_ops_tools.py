"""Tests for the direct Knowledge-Ops HTTP tools and their credentials."""

from __future__ import annotations

import logging
from urllib.parse import parse_qs

import httpx
import pytest
import respx

import app.llm.knowledge_ops_tools as knowledge_tools

TOKEN_URL = "https://auth.test/realms/uchub/protocol/openid-connect/token"
KNOWLEDGE_URL = "http://knowledge.test"


@pytest.fixture(autouse=True)
def reset_knowledge_state(monkeypatch):
    monkeypatch.setattr(knowledge_tools, "KNOWLEDGE_OPS_URL", KNOWLEDGE_URL)
    monkeypatch.setattr(knowledge_tools, "KNOWLEDGE_OPS_TOKEN", "")
    monkeypatch.setattr(knowledge_tools, "KNOWLEDGE_OPS_OIDC_TOKEN_URL", "")
    monkeypatch.setattr(knowledge_tools, "KNOWLEDGE_OPS_OIDC_CLIENT_ID", "")
    monkeypatch.setattr(knowledge_tools, "KNOWLEDGE_OPS_OIDC_CLIENT_SECRET", "")
    monkeypatch.setattr(knowledge_tools, "KNOWLEDGE_OPS_OIDC_AUDIENCE", "")
    monkeypatch.setattr(knowledge_tools, "KNOWLEDGE_OPS_OIDC_SCOPE", "")
    knowledge_tools._TOKEN_CACHE.update(token=None, exp=0.0)
    yield
    knowledge_tools._TOKEN_CACHE.update(token=None, exp=0.0)


def _configure_oidc(monkeypatch):
    monkeypatch.setattr(knowledge_tools, "KNOWLEDGE_OPS_OIDC_TOKEN_URL", TOKEN_URL)
    monkeypatch.setattr(knowledge_tools, "KNOWLEDGE_OPS_OIDC_CLIENT_ID", "brigade-ko-test")
    monkeypatch.setattr(knowledge_tools, "KNOWLEDGE_OPS_OIDC_CLIENT_SECRET", "test-secret")


@pytest.mark.asyncio
async def test_oidc_token_is_minted_once_and_reused(monkeypatch):
    _configure_oidc(monkeypatch)
    monkeypatch.setattr(knowledge_tools, "KNOWLEDGE_OPS_OIDC_AUDIENCE", "knowledge-ops")
    monkeypatch.setattr(knowledge_tools, "KNOWLEDGE_OPS_OIDC_SCOPE", "knowledge-reader")

    with respx.mock(assert_all_called=True) as router:
        token_route = router.post(TOKEN_URL).mock(
            return_value=httpx.Response(200, json={"access_token": "oidc-token-1", "expires_in": 300})
        )
        knowledge_route = router.post(f"{KNOWLEDGE_URL}/kb.search").mock(
            side_effect=[httpx.Response(200, json={"matches": ["one"]}), httpx.Response(200, json={"matches": ["two"]})]
        )

        first = await knowledge_tools._search_handler("one")
        second = await knowledge_tools._search_handler("two")

    assert first == {"matches": ["one"]}
    assert second == {"matches": ["two"]}
    assert token_route.call_count == 1
    assert parse_qs(token_route.calls[0].request.content.decode()) == {
        "grant_type": ["client_credentials"],
        "client_id": ["brigade-ko-test"],
        "client_secret": ["test-secret"],
        "audience": ["knowledge-ops"],
        "scope": ["knowledge-reader"],
    }
    assert token_route.calls[0].request.headers["user-agent"] == "unicorn-brigade-ko-client/1.0"
    assert all(
        request.request.headers["authorization"] == "Bearer oidc-token-1"
        and request.request.headers["user-agent"] == "unicorn-brigade-ko-client/1.0"
        for request in knowledge_route.calls
    )


@pytest.mark.asyncio
async def test_oidc_token_refreshes_after_the_early_expiry_window(monkeypatch):
    _configure_oidc(monkeypatch)
    clock = {"now": 100.0}
    monkeypatch.setattr(knowledge_tools.time, "monotonic", lambda: clock["now"])

    with respx.mock(assert_all_called=True) as router:
        token_route = router.post(TOKEN_URL).mock(
            side_effect=[
                httpx.Response(200, json={"access_token": "oidc-token-1", "expires_in": 60}),
                httpx.Response(200, json={"access_token": "oidc-token-2", "expires_in": 60}),
            ]
        )
        knowledge_route = router.post(f"{KNOWLEDGE_URL}/kb.search").mock(
            side_effect=[httpx.Response(200, json={"ok": 1}), httpx.Response(200, json={"ok": 2})]
        )

        assert await knowledge_tools._search_handler("first") == {"ok": 1}
        clock["now"] = 131.0
        assert await knowledge_tools._search_handler("second") == {"ok": 2}

    assert token_route.call_count == 2
    assert [call.request.headers["authorization"] for call in knowledge_route.calls] == [
        "Bearer oidc-token-1",
        "Bearer oidc-token-2",
    ]


@pytest.mark.asyncio
async def test_oidc_401_refreshes_once_then_returns_clean_error(caplog, monkeypatch):
    _configure_oidc(monkeypatch)

    with respx.mock(assert_all_called=True) as router:
        token_route = router.post(TOKEN_URL).mock(
            side_effect=[
                httpx.Response(200, json={"access_token": "oidc-token-1", "expires_in": 300}),
                httpx.Response(200, json={"access_token": "oidc-token-2", "expires_in": 300}),
            ]
        )
        knowledge_route = router.post(f"{KNOWLEDGE_URL}/kb.search").mock(
            side_effect=[
                httpx.Response(401, text="sensitive upstream body one"),
                httpx.Response(401, text="sensitive upstream body two"),
            ]
        )

        with caplog.at_level(logging.WARNING, logger=knowledge_tools.logger.name):
            result = await knowledge_tools._search_handler("protected")

    assert result == {"error": "knowledge-ops rejected the credential (401)"}
    assert token_route.call_count == 2
    assert knowledge_route.call_count == 2
    assert [call.request.headers["authorization"] for call in knowledge_route.calls] == [
        "Bearer oidc-token-1",
        "Bearer oidc-token-2",
    ]
    warnings = [record for record in caplog.records if record.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert warnings[0].message == "knowledge-ops credential rejected route=kb.search"
    assert "sensitive upstream body" not in caplog.text


@pytest.mark.asyncio
async def test_static_token_path_is_preserved(monkeypatch):
    monkeypatch.setattr(knowledge_tools, "KNOWLEDGE_OPS_TOKEN", "static-token")

    with respx.mock(assert_all_called=True) as router:
        route = router.post(f"{KNOWLEDGE_URL}/kb.search").mock(
            return_value=httpx.Response(200, json={"matches": ["static"]})
        )
        result = await knowledge_tools._search_handler("static")

    assert result == {"matches": ["static"]}
    assert route.calls[0].request.headers["authorization"] == "Bearer static-token"


@pytest.mark.asyncio
async def test_unset_credentials_send_no_authorization_header():
    with respx.mock(assert_all_called=True) as router:
        route = router.post(f"{KNOWLEDGE_URL}/kb.search").mock(
            return_value=httpx.Response(200, json={"matches": ["open"]})
        )
        result = await knowledge_tools._search_handler("open")

    assert result == {"matches": ["open"]}
    assert "authorization" not in route.calls[0].request.headers


@pytest.mark.asyncio
async def test_403_is_sanitized_and_logged_once(caplog):
    with respx.mock(assert_all_called=True) as router:
        route = router.post(f"{KNOWLEDGE_URL}/kb.search").mock(
            return_value=httpx.Response(403, text="sensitive forbidden body")
        )
        with caplog.at_level(logging.WARNING, logger=knowledge_tools.logger.name):
            result = await knowledge_tools._search_handler("forbidden")

    assert result == {"error": "knowledge-ops rejected the credential (403)"}
    assert route.call_count == 1
    warnings = [record for record in caplog.records if record.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert warnings[0].message == "knowledge-ops credential rejected route=kb.search"
    assert "sensitive forbidden body" not in caplog.text
