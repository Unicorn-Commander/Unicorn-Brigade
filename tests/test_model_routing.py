"""Regression tests for OpsCenterLLMClient._resolve_local_model routing.

Guards the fix where a leading ``openrouter/`` prefix must be stripped before
hitting OpenRouter's native API (which expects bare/namespaced slugs such as
``anthropic/claude-sonnet-4.6`` and 400s on ``openrouter/anthropic/...``).
"""
import pytest

from app.llm import ops_center_client
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
