"""Route truth and bounded upstream budget handling for the LLM client."""

import logging
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx

import app.llm.ops_center_client as client_module
from app.llm.ops_center_client import (
    OpsCenterLLMClient,
    ToolDefinition,
    UpstreamBudgetExhausted,
    describe_route,
)


@pytest.fixture(autouse=True)
def _disable_environment_proxies(monkeypatch):
    """The supplied test venv has httpx but not the optional SOCKS transport."""
    for name in (
        "ALL_PROXY",
        "all_proxy",
        "HTTP_PROXY",
        "http_proxy",
        "HTTPS_PROXY",
        "https_proxy",
    ):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def route_environment(monkeypatch):
    monkeypatch.setattr(client_module, "OPENROUTER_API_KEY", "")
    monkeypatch.setattr(client_module, "UC_GATEWAY_URL", "")
    monkeypatch.setattr(client_module, "OPENAI_DIRECT_KEY", "")
    monkeypatch.setattr(client_module, "DASHSCOPE_API_KEY", "")
    monkeypatch.setattr(client_module, "OPS_CENTER_LLM_ENDPOINT", "")
    monkeypatch.setattr(client_module, "LOCAL_LLM_URL", "http://llama.test:8080")
    monkeypatch.setattr(client_module, "DEFAULT_EXTERNAL_URL", "https://ops.test")
    monkeypatch.delenv("OPS_CENTER_URL", raising=False)


def _success_response() -> dict:
    return {
        "choices": [
            {
                "message": {"role": "assistant", "content": "ok"},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }


def _budget_response(
    status_code: int,
    reason: str = "in_flight_budget_exhausted",
    retry_after: str = "120",
):
    return httpx.Response(
        status_code,
        json={"error": {"metadata": {"reason": reason}}},
        headers={"Retry-After": retry_after},
    )


def _make_client() -> OpsCenterLLMClient:
    return OpsCenterLLMClient(ops_center_url="https://ops.test", service_key="x" * 32)


def test_describe_route_reports_explicit_openrouter_only(
    route_environment, monkeypatch
):
    models = {
        "anthropic/claude-sonnet-4.6": ("ops-center", "ops.test"),
        "local/qwen3.6-35b": ("local", "llama.test"),
        "openrouter/vendor/model": ("ops-center", "ops.test"),
    }

    without_key = {model: describe_route(model) for model in models}
    for model, (route_type, host) in models.items():
        assert without_key[model]["route_type"] == route_type
        assert without_key[model]["target_host"] == host
        assert without_key[model]["model_requested"] == model

    monkeypatch.setattr(client_module, "OPENROUTER_API_KEY", "test-key")
    with_key = {model: describe_route(model) for model in models}
    assert with_key["anthropic/claude-sonnet-4.6"]["route_type"] == "ops-center"
    assert with_key["local/qwen3.6-35b"]["route_type"] == "local"
    assert with_key["openrouter/vendor/model"]["route_type"] == "openrouter"
    assert with_key["openrouter/vendor/model"]["model_resolved"] == "vendor/model"


@pytest.mark.asyncio
async def test_402_then_200_retries_once_and_logs_route_and_retry(
    route_environment, monkeypatch, caplog
):
    monkeypatch.setattr(client_module, "OPENROUTER_API_KEY", "test-key")
    with respx.mock(assert_all_called=True) as router:
        upstream = router.post("https://openrouter.ai/api/v1/chat/completions")
        upstream.side_effect = [
            _budget_response(402),
            httpx.Response(200, json=_success_response()),
        ]
        client = _make_client()
        try:
            with (
                patch("app.llm.ops_center_client.asyncio.sleep", new=AsyncMock()) as sleep,
                caplog.at_level(logging.INFO, logger=client_module.__name__),
            ):
                response = await client.chat_completion(
                    messages=[{"role": "user", "content": "hello"}],
                    model="openrouter/vendor/model",
                )
        finally:
            await client.close()

    assert response["choices"][0]["message"]["content"] == "ok"
    assert upstream.call_count == 2
    sleep.assert_awaited_once_with(30.0)
    assert "llm.route model=openrouter/vendor/model" in caplog.text
    assert "llm.upstream_retry status=402 route=openrouter" in caplog.text


@pytest.mark.asyncio
async def test_repeated_402_returns_typed_exhaustion_payload_and_two_calls(
    route_environment, monkeypatch
):
    monkeypatch.setattr(client_module, "OPENROUTER_API_KEY", "test-key")
    with respx.mock(assert_all_called=True) as router:
        upstream = router.post("https://openrouter.ai/api/v1/chat/completions")
        upstream.side_effect = [_budget_response(402), _budget_response(402)]
        client = _make_client()
        try:
            with patch("app.llm.ops_center_client.asyncio.sleep", new=AsyncMock()):
                with pytest.raises(UpstreamBudgetExhausted) as raised:
                    await client.chat_completion(
                        messages=[{"role": "user", "content": "hello"}],
                        model="openrouter/vendor/model",
                    )
        finally:
            await client.close()

    assert upstream.call_count == 2
    assert raised.value.as_dict() == {
        "error": "upstream_budget_exhausted",
        "route": "openrouter",
        "retry_after": 30.0,
        "reason": "in_flight_budget_exhausted",
    }


@pytest.mark.asyncio
async def test_429_uses_retry_after_seconds_and_waits_once(route_environment, monkeypatch):
    monkeypatch.setattr(client_module, "OPENROUTER_API_KEY", "test-key")
    with respx.mock(assert_all_called=True) as router:
        upstream = router.post("https://openrouter.ai/api/v1/chat/completions")
        upstream.side_effect = [
            _budget_response(429, reason="rate_limited", retry_after="2"),
            httpx.Response(200, json=_success_response()),
        ]
        client = _make_client()
        try:
            with patch("app.llm.ops_center_client.asyncio.sleep", new=AsyncMock()) as sleep:
                await client.chat_completion(
                    messages=[{"role": "user", "content": "hello"}],
                    model="openrouter/vendor/model",
                )
        finally:
            await client.close()

    assert upstream.call_count == 2
    sleep.assert_awaited_once_with(2.0)


@pytest.mark.asyncio
async def test_500_remains_http_status_error_without_budget_retry(route_environment, monkeypatch):
    monkeypatch.setattr(client_module, "OPENROUTER_API_KEY", "test-key")
    with respx.mock(assert_all_called=True) as router:
        upstream = router.post("https://openrouter.ai/api/v1/chat/completions")
        upstream.mock(return_value=httpx.Response(500, text="provider failed"))
        client = _make_client()
        try:
            with pytest.raises(httpx.HTTPStatusError) as raised:
                await client._chat_completion_once(
                    messages=[{"role": "user", "content": "hello"}],
                    model="openrouter/vendor/model",
                )
        finally:
            await client.close()

    assert upstream.call_count == 1
    assert raised.value.response.status_code == 500


@pytest.mark.asyncio
async def test_stream_500_preserves_http_status_error_without_budget_retry(
    route_environment, monkeypatch
):
    monkeypatch.setattr(client_module, "OPENROUTER_API_KEY", "test-key")
    with respx.mock(assert_all_called=True) as router:
        upstream = router.post("https://openrouter.ai/api/v1/chat/completions")
        upstream.mock(return_value=httpx.Response(500, text="provider failed"))
        client = _make_client()
        try:
            stream = client.chat_completion_stream(
                messages=[{"role": "user", "content": "hello"}],
                model="openrouter/vendor/model",
            )
            with pytest.raises(httpx.HTTPStatusError) as raised:
                await anext(stream)
        finally:
            await client.close()

    assert upstream.call_count == 1
    assert raised.value.response.status_code == 500


@pytest.mark.asyncio
async def test_tool_completion_uses_the_shared_budget_retry_path(route_environment, monkeypatch):
    monkeypatch.setattr(client_module, "OPENROUTER_API_KEY", "test-key")
    with respx.mock(assert_all_called=True) as router:
        upstream = router.post("https://openrouter.ai/api/v1/chat/completions")
        upstream.side_effect = [
            _budget_response(402),
            httpx.Response(200, json=_success_response()),
        ]
        client = _make_client()
        try:
            with patch("app.llm.ops_center_client.asyncio.sleep", new=AsyncMock()):
                response = await client.chat_completion_with_tools(
                    messages=[{"role": "user", "content": "hello"}],
                    tools=[ToolDefinition(name="noop", description="no-op")],
                    model="openrouter/vendor/model",
                )
        finally:
            await client.close()

    assert response["choices"][0]["message"]["content"] == "ok"
    assert upstream.call_count == 2


@pytest.mark.asyncio
async def test_stream_budget_exhaustion_is_raised_before_first_data(route_environment, monkeypatch):
    monkeypatch.setattr(client_module, "OPENROUTER_API_KEY", "test-key")
    with respx.mock(assert_all_called=True) as router:
        upstream = router.post("https://openrouter.ai/api/v1/chat/completions")
        upstream.side_effect = [_budget_response(402), _budget_response(402)]
        client = _make_client()
        try:
            with patch("app.llm.ops_center_client.asyncio.sleep", new=AsyncMock()):
                stream = client.chat_completion_stream(
                    messages=[{"role": "user", "content": "hello"}],
                    model="openrouter/vendor/model",
                )
                with pytest.raises(UpstreamBudgetExhausted):
                    await anext(stream)
        finally:
            await client.close()

    assert upstream.call_count == 2
