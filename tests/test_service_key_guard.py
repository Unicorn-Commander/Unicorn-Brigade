"""Regression tests for the fail-closed Brigade service-key guard."""

import pytest
from fastapi import HTTPException

from app.core import service_key

TEST_SERVICE_KEY = "test-service-key-" + "x" * 32


def _admin_keys_routes():
    pytest.importorskip("asyncpg")
    from app.api import admin_keys_routes

    return admin_keys_routes


def _ops_center_client():
    from app.llm import ops_center_client

    return ops_center_client


def test_strong_service_key_is_accepted(monkeypatch):
    monkeypatch.setenv("BRIGADE_SERVICE_KEY", TEST_SERVICE_KEY)

    assert service_key.is_strong_service_key(TEST_SERVICE_KEY)
    assert service_key.require_service_key("unit test") == TEST_SERVICE_KEY


@pytest.mark.parametrize(
    "value",
    ["1234567", service_key.KNOWN_BAD_SERVICE_KEYS[0]],
)
def test_short_and_known_placeholder_keys_are_rejected(value):
    assert not service_key.is_strong_service_key(value)


def test_service_key_validation_uses_constant_time_placeholder_compare(monkeypatch):
    calls = []
    original = service_key.hmac.compare_digest

    def compare_digest(left, right):
        calls.append((left, right))
        return original(left, right)

    monkeypatch.setattr(service_key.hmac, "compare_digest", compare_digest)

    assert service_key.is_strong_service_key(TEST_SERVICE_KEY)
    assert calls


def test_missing_required_service_key_names_env_and_rule(monkeypatch):
    monkeypatch.delenv("BRIGADE_SERVICE_KEY", raising=False)

    with pytest.raises(service_key.ConfigError) as exc_info:
        service_key.require_service_key("the federation-only public surface")

    message = str(exc_info.value)
    assert "BRIGADE_SERVICE_KEY" in message
    assert "32 characters" in message


@pytest.mark.asyncio
async def test_federation_startup_refuses_seven_character_key(monkeypatch):
    pytest.importorskip("asyncpg")
    from app import main

    monkeypatch.setattr(main, "FEDERATION_ONLY", True)
    monkeypatch.setenv("AUTH_BYPASS", "false")
    monkeypatch.setenv("BRIGADE_SERVICE_KEY", "1234567")

    with pytest.raises(service_key.ConfigError, match="BRIGADE_SERVICE_KEY"):
        async with main.lifespan(main.app):
            pass


def test_admin_service_key_rejects_placeholder(monkeypatch):
    admin_keys_routes = _admin_keys_routes()
    monkeypatch.setenv("BRIGADE_SERVICE_KEY", service_key.KNOWN_BAD_SERVICE_KEYS[0])

    with pytest.raises(HTTPException) as exc_info:
        admin_keys_routes.require_service_key("not-the-configured-key")

    assert exc_info.value.status_code == 503


def test_admin_service_key_match_uses_compare_digest(monkeypatch):
    admin_keys_routes = _admin_keys_routes()
    monkeypatch.setenv("BRIGADE_SERVICE_KEY", TEST_SERVICE_KEY)
    calls = []
    original = admin_keys_routes.hmac.compare_digest

    def compare_digest(left, right):
        calls.append((left, right))
        return original(left, right)

    monkeypatch.setattr(admin_keys_routes.hmac, "compare_digest", compare_digest)

    assert admin_keys_routes.require_service_key(TEST_SERVICE_KEY) == TEST_SERVICE_KEY
    assert calls


def test_ops_center_client_does_not_send_weak_brigade_key(monkeypatch):
    ops_center_client = _ops_center_client()
    monkeypatch.setattr(ops_center_client, "BRIGADE_SERVICE_KEY", "1234567")
    client = object.__new__(ops_center_client.OpsCenterLLMClient)
    client._uses_brigade_service_key = True
    client._service_key_enabled = False
    client.service_key = "1234567"

    with pytest.raises(service_key.ConfigError, match="BRIGADE_SERVICE_KEY"):
        client._endpoint_and_headers("ops-center", "http://ops.invalid")
