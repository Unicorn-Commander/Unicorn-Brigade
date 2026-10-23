"""Tests for the direct Knowledge-Ops HTTP tools and their credentials."""

from __future__ import annotations

import asyncio
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
    knowledge_tools._OIDC_STATE.update(
        negative_until=0.0,
        warning_until=0.0,
        oidc_ok=True,
        oidc_last_error="",
    )
    monkeypatch.setattr(knowledge_tools, "_TOKEN_MINT_TASK", None)
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

    assert first == {"matches": ["one"], "oidc_ok": True, "oidc_last_error": ""}
    assert second == {"matches": ["two"], "oidc_ok": True, "oidc_last_error": ""}
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
@pytest.mark.parametrize(
    ("expiry_fields", "case"),
    [({}, "missing"), ({"expires_in": 0}, "zero"), ({"expires_in": "invalid"}, "invalid")],
)
async def test_invalid_oidc_expiry_is_not_cached_and_logs_once_per_mint(
    caplog, monkeypatch, expiry_fields, case
):
    _configure_oidc(monkeypatch)

    with respx.mock(assert_all_called=True) as router:
        token_route = router.post(TOKEN_URL).mock(
            side_effect=[
                httpx.Response(200, json={"access_token": "oidc-token-1", **expiry_fields}),
                httpx.Response(200, json={"access_token": "oidc-token-2", **expiry_fields}),
            ]
        )
        knowledge_route = router.post(f"{KNOWLEDGE_URL}/kb.search").mock(
            side_effect=[httpx.Response(200, json={"ok": 1}), httpx.Response(200, json={"ok": 2})]
        )

        with caplog.at_level(logging.WARNING, logger=knowledge_tools.logger.name):
            assert await knowledge_tools._search_handler(f"{case}-one") == {
                "ok": 1,
                "oidc_ok": True,
                "oidc_last_error": "",
            }
            assert await knowledge_tools._search_handler(f"{case}-two") == {
                "ok": 2,
                "oidc_ok": True,
                "oidc_last_error": "",
            }

    assert token_route.call_count == 2
    assert [call.request.headers["authorization"] for call in knowledge_route.calls] == [
        "Bearer oidc-token-1",
        "Bearer oidc-token-2",
    ]
    expiry_warnings = [
        record for record in caplog.records if "invalid expires_in" in record.message
    ]
    assert len(expiry_warnings) == 2


@pytest.mark.asyncio
async def test_concurrent_oidc_misses_share_one_mint(monkeypatch):
    _configure_oidc(monkeypatch)
    mint_started = asyncio.Event()
    release_mint = asyncio.Event()
    mint_calls = 0

    async def mint(_request):
        nonlocal mint_calls
        mint_calls += 1
        mint_started.set()
        await release_mint.wait()
        return httpx.Response(200, json={"access_token": "oidc-token-1", "expires_in": 300})

    with respx.mock(assert_all_called=True) as router:
        token_route = router.post(TOKEN_URL).mock(side_effect=mint)
        first = asyncio.create_task(knowledge_tools._get_oidc_token())
        second = None
        try:
            await asyncio.wait_for(mint_started.wait(), timeout=1)
            second = asyncio.create_task(knowledge_tools._get_oidc_token())
            await asyncio.sleep(0)
            assert mint_calls == 1
        finally:
            release_mint.set()
            tasks = [first] if second is None else [first, second]
            await asyncio.gather(*tasks, return_exceptions=True)

        assert await first == "oidc-token-1"
        assert await second == "oidc-token-1"
        assert token_route.call_count == 1


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

        assert await knowledge_tools._search_handler("first") == {
            "ok": 1,
            "oidc_ok": True,
            "oidc_last_error": "",
        }
        clock["now"] = 131.0
        assert await knowledge_tools._search_handler("second") == {
            "ok": 2,
            "oidc_ok": True,
            "oidc_last_error": "",
        }

    assert token_route.call_count == 2
    assert [call.request.headers["authorization"] for call in knowledge_route.calls] == [
        "Bearer oidc-token-1",
        "Bearer oidc-token-2",
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("rejection_status", [401, 403])
async def test_oidc_401_or_403_refreshes_once_then_returns_clean_error(
    caplog, monkeypatch, rejection_status
):
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
                httpx.Response(rejection_status, text="sensitive upstream body one"),
                httpx.Response(rejection_status, text="sensitive upstream body two"),
            ]
        )

        with caplog.at_level(logging.WARNING, logger=knowledge_tools.logger.name):
            result = await knowledge_tools._search_handler("protected")

    assert result == {
        "error": f"knowledge-ops rejected the credential ({rejection_status})",
        "oidc_ok": True,
        "oidc_last_error": "",
    }
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
async def test_oidc_mint_exception_logs_type_without_client_secret(caplog, monkeypatch):
    _configure_oidc(monkeypatch)
    client_secret = "client-secret-for-log-test"
    monkeypatch.setattr(knowledge_tools, "KNOWLEDGE_OPS_OIDC_CLIENT_SECRET", client_secret)

    with respx.mock(assert_all_called=True) as router:
        router.post(TOKEN_URL).mock(side_effect=RuntimeError(client_secret))
        with caplog.at_level(logging.ERROR, logger=knowledge_tools.logger.name):
            result = await knowledge_tools._search_handler("mint-failure")

    assert result == {
        "error": "knowledge-ops could not obtain an OIDC credential",
        "oidc_ok": False,
        "oidc_last_error": "OIDC token mint failed (RuntimeError)",
    }
    assert "RuntimeError" in caplog.text
    assert client_secret not in caplog.text


@pytest.mark.asyncio
async def test_oidc_mint_failure_negative_cache_falls_back_once_per_window(
    caplog, monkeypatch
):
    _configure_oidc(monkeypatch)
    monkeypatch.setattr(knowledge_tools, "KNOWLEDGE_OPS_TOKEN", "static-token")

    with respx.mock(assert_all_called=True) as router:
        token_route = router.post(TOKEN_URL).mock(return_value=httpx.Response(503))
        knowledge_route = router.post(f"{KNOWLEDGE_URL}/kb.search").mock(
            side_effect=[
                httpx.Response(200, json={"matches": ["fallback-one"]}),
                httpx.Response(200, json={"matches": ["fallback-two"]}),
            ]
        )
        with caplog.at_level(logging.WARNING, logger=knowledge_tools.logger.name):
            first = await knowledge_tools._search_handler("fallback-one")
            second = await knowledge_tools._search_handler("fallback-two")

    assert first == {
        "matches": ["fallback-one"],
        "oidc_ok": False,
        "oidc_last_error": "OIDC token endpoint returned HTTP 503",
    }
    assert second == {
        "matches": ["fallback-two"],
        "oidc_ok": False,
        "oidc_last_error": "OIDC token endpoint returned HTTP 503",
    }
    assert token_route.call_count == 1
    assert [call.request.headers["authorization"] for call in knowledge_route.calls] == [
        "Bearer static-token",
        "Bearer static-token",
    ]
    fallback_warnings = [
        record
        for record in caplog.records
        if record.levelno == logging.WARNING and "falling back to static token" in record.message
    ]
    assert len(fallback_warnings) == 1
    assert "route=kb.search" in fallback_warnings[0].message


@pytest.mark.asyncio
async def test_oidc_negative_cache_retries_after_window_expiry(caplog, monkeypatch):
    _configure_oidc(monkeypatch)
    monkeypatch.setattr(knowledge_tools, "KNOWLEDGE_OPS_TOKEN", "static-token")
    monkeypatch.setattr(knowledge_tools, "KNOWLEDGE_OPS_OIDC_NEGATIVE_CACHE_TTL", 60.0)
    clock = {"now": 100.0}
    monkeypatch.setattr(knowledge_tools.time, "monotonic", lambda: clock["now"])

    with respx.mock(assert_all_called=True) as router:
        token_route = router.post(TOKEN_URL).mock(
            side_effect=[
                httpx.Response(503),
                httpx.Response(200, json={"access_token": "oidc-token-2", "expires_in": 300}),
            ]
        )
        knowledge_route = router.post(f"{KNOWLEDGE_URL}/kb.search").mock(
            side_effect=[
                httpx.Response(200, json={"matches": ["fallback"]}),
                httpx.Response(200, json={"matches": ["oidc"]}),
            ]
        )
        with caplog.at_level(logging.WARNING, logger=knowledge_tools.logger.name):
            first = await knowledge_tools._search_handler("first")
            clock["now"] = 161.0
            second = await knowledge_tools._search_handler("second")

    assert first["oidc_ok"] is False
    assert first["oidc_last_error"] == "OIDC token endpoint returned HTTP 503"
    assert second == {"matches": ["oidc"], "oidc_ok": True, "oidc_last_error": ""}
    assert token_route.call_count == 2
    assert [call.request.headers["authorization"] for call in knowledge_route.calls] == [
        "Bearer static-token",
        "Bearer oidc-token-2",
    ]
    assert len([record for record in caplog.records if record.levelno == logging.WARNING]) == 1


@pytest.mark.asyncio
async def test_slow_oidc_refresh_does_not_block_read_using_cached_token(monkeypatch):
    _configure_oidc(monkeypatch)
    knowledge_tools._TOKEN_CACHE.update(
        token="oidc-token-old", exp=knowledge_tools.time.monotonic() + 10_000.0
    )
    mint_started = asyncio.Event()
    release_mint = asyncio.Event()

    async def mint(_request):
        mint_started.set()
        await release_mint.wait()
        return httpx.Response(200, json={"access_token": "oidc-token-new", "expires_in": 300})

    with respx.mock(assert_all_called=True) as router:
        token_route = router.post(TOKEN_URL).mock(side_effect=mint)
        knowledge_route = router.post(f"{KNOWLEDGE_URL}/kb.search").mock(
            return_value=httpx.Response(200, json={"matches": ["cached"]})
        )
        refresh = asyncio.create_task(
            knowledge_tools._get_oidc_token(force_refresh=True, route="kb.search")
        )
        await asyncio.wait_for(mint_started.wait(), timeout=1)

        await asyncio.wait_for(knowledge_tools._TOKEN_CACHE_LOCK.acquire(), timeout=0.1)
        knowledge_tools._TOKEN_CACHE_LOCK.release()
        result = await asyncio.wait_for(
            knowledge_tools._search_handler("unrelated-read"), timeout=0.1
        )

        assert result == {"matches": ["cached"], "oidc_ok": True, "oidc_last_error": ""}
        assert knowledge_route.calls[0].request.headers["authorization"] == "Bearer oidc-token-old"
        release_mint.set()
        assert await refresh == "oidc-token-new"

    assert token_route.call_count == 1


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
