"""Regression tests for OpsCenterLLMClient._resolve_local_model routing.

Guards the fix where a leading ``openrouter/`` prefix must be stripped before
hitting OpenRouter's native API (which expects bare/namespaced slugs such as
``anthropic/claude-sonnet-4.6`` and 400s on ``openrouter/anthropic/...``).
"""
import pytest

from app.llm import ops_center_client
from app.llm.org_gateway import (
    clear_org_gateway_cache,
    gateway_headers,
    get_org_gateway_credential,
)
from app.llm.ops_center_client import OpsCenterLLMClient


@pytest.fixture
def client():
    # Pass an explicit URL so __init__ skips network-based _detect_url().
    return OpsCenterLLMClient(ops_center_url="http://test-ops-center")


def test_openrouter_prefix_is_stripped(client, monkeypatch):
    """openrouter/<slug> must route to OpenRouter as the bare <slug>."""
    monkeypatch.setattr(ops_center_client, "OPENROUTER_API_KEY", "sk-test")
    monkeypatch.setattr(ops_center_client, "UC_GATEWAY_URL", "")
    url, resolved, route = client._resolve_local_model(
        "openrouter/anthropic/claude-sonnet-4.6"
    )
    assert route == "openrouter"
    assert resolved == "anthropic/claude-sonnet-4.6"
    assert url == ops_center_client.OPENROUTER_URL


@pytest.mark.parametrize(
    "model,expected",
    [
        ("openrouter/anthropic/claude-haiku-4.5", "anthropic/claude-haiku-4.5"),
        ("openrouter/moonshotai/kimi-k2.5", "moonshotai/kimi-k2.5"),
        ("deepseek-v4-flash", "deepseek-v4-flash"),  # no prefix -> unchanged
        ("anthropic/claude-sonnet-4.6", "anthropic/claude-sonnet-4.6"),
    ],
)
def test_openrouter_slug_resolution(client, monkeypatch, model, expected):
    monkeypatch.setattr(ops_center_client, "OPENROUTER_API_KEY", "sk-test")
    monkeypatch.setattr(ops_center_client, "UC_GATEWAY_URL", "")
    _, resolved, route = client._resolve_local_model(model)
    assert route == "openrouter"
    assert resolved == expected


def test_only_leading_prefix_stripped(client, monkeypatch):
    """A non-leading 'openrouter/' must not be touched."""
    monkeypatch.setattr(ops_center_client, "OPENROUTER_API_KEY", "sk-test")
    monkeypatch.setattr(ops_center_client, "UC_GATEWAY_URL", "")
    _, resolved, _ = client._resolve_local_model("vendor/openrouter/model")
    assert resolved == "vendor/openrouter/model"


def test_uc_prefix_goes_to_gateway_unstripped(client, monkeypatch):
    """uc/-prefixed ids take gateway precedence and keep their full name."""
    monkeypatch.setattr(ops_center_client, "UC_GATEWAY_URL", "http://gw/v1")
    monkeypatch.setattr(ops_center_client, "OPENROUTER_API_KEY", "sk-test")
    url, resolved, route = client._resolve_local_model("uc/chat-local-p40")
    assert route == "gateway"
    assert resolved == "uc/chat-local-p40"
    assert url == "http://gw/v1"


def test_gateway_headers_use_shared_key_when_org_mapping_disabled(monkeypatch):
    monkeypatch.delenv("UC_GATEWAY_PER_ORG_KEYS_ENABLED", raising=False)
    monkeypatch.setenv(
        "UC_GATEWAY_ORG_KEYS_JSON",
        '{"org-a":{"api_key":"sk-org-a","key_alias":"org-a","max_budget":50}}',
    )
    clear_org_gateway_cache()

    headers = gateway_headers(shared_key="sk-shared", org_id="org-a", user_id="user-a")

    assert headers["Authorization"] == "Bearer sk-shared"
    assert headers["X-Org-ID"] == "org-a"
    assert headers["X-User-ID"] == "user-a"
    assert "X-UC-Gateway-Key-Alias" not in headers


def test_gateway_headers_use_org_key_and_budget_when_enabled(monkeypatch):
    monkeypatch.setenv("UC_GATEWAY_PER_ORG_KEYS_ENABLED", "true")
    monkeypatch.setenv(
        "UC_GATEWAY_ORG_KEYS_JSON",
        '{"org-a":{"api_key":"sk-org-a","key_alias":"org-a","max_budget":50}}',
    )
    clear_org_gateway_cache()

    credential = get_org_gateway_credential("org-a")
    headers = gateway_headers(shared_key="sk-shared", org_id="org-a", user_id="user-a")

    assert credential is not None
    assert credential.api_key == "sk-org-a"
    assert credential.max_budget == 50.0
    assert headers["Authorization"] == "Bearer sk-org-a"
    assert headers["X-Org-ID"] == "org-a"
    assert headers["X-User-ID"] == "user-a"
    assert headers["X-UC-Gateway-Key-Alias"] == "org-a"
    assert headers["X-UC-Gateway-Max-Budget"] == "50.0"


def test_gateway_headers_fail_closed_for_unmapped_org_when_enabled(monkeypatch):
    monkeypatch.setenv("UC_GATEWAY_PER_ORG_KEYS_ENABLED", "1")
    monkeypatch.setenv("UC_GATEWAY_ORG_KEYS_JSON", '{"org-a":"sk-org-a"}')
    clear_org_gateway_cache()

    with pytest.raises(RuntimeError, match="no UC gateway key configured for org org-b"):
        gateway_headers(shared_key="sk-shared", org_id="org-b", user_id="user-b")


def test_gateway_headers_allow_shared_key_for_unscoped_system_call(monkeypatch):
    monkeypatch.setenv("UC_GATEWAY_PER_ORG_KEYS_ENABLED", "1")
    monkeypatch.setenv("UC_GATEWAY_ORG_KEYS_JSON", '{"org-a":"sk-org-a"}')
    clear_org_gateway_cache()

    headers = gateway_headers(shared_key="sk-shared", org_id=None, user_id=None)

    assert headers == {
        "Authorization": "Bearer sk-shared",
        "Content-Type": "application/json",
    }
