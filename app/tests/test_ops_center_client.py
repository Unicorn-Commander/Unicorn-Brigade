"""Route truth and bounded upstream budget handling for the LLM client."""

import json
import logging
import socket
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
from app.llm.org_gateway import clear_org_gateway_cache
from app.reliability.circuit import CircuitOpenError, CircuitState
from app.reliability.retry import default_is_transient


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
    monkeypatch.delenv("UC_GATEWAY_PER_ORG_KEYS_ENABLED", raising=False)
    monkeypatch.setenv("LLM_CIRCUIT_FAILURE_THRESHOLD", "5")
    monkeypatch.setenv("LLM_CIRCUIT_COOLDOWN_SECONDS", "30")
    monkeypatch.setenv("LLM_RETRY_BASE_DELAY", "0")
    monkeypatch.setenv("LLM_RETRY_JITTER", "0")
    monkeypatch.setenv("LLM_RETRY_MAX_ATTEMPTS", "3")


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


async def _complete(client, mode, model):
    messages = [{"role": "user", "content": "hello"}]
    if mode == "tools":
        return await client.chat_completion_with_tools(messages, [], model)
    if mode == "stream":
        chunks = [chunk async for chunk in client.chat_completion_stream(messages, model)]
        return json.loads(chunks[0])
    return await client.chat_completion(messages, model)


def _completion_response(mode):
    if mode == "stream":
        return httpx.Response(
            200,
            text=f"data: {json.dumps(_success_response())}\n\ndata: [DONE]\n\n",
            headers={"Content-Type": "text/event-stream"},
        )
    return httpx.Response(200, json=_success_response())


@pytest.mark.parametrize("mode", ["chat", "tools", "stream"])
@pytest.mark.parametrize("per_org", [False, True])
async def test_local_models_use_authenticated_gateway(
    route_environment, monkeypatch, mode, per_org
):
    monkeypatch.setattr(client_module, "LOCAL_LLM_URL", "")
    monkeypatch.setattr(client_module, "UC_GATEWAY_URL", "https://gateway.test/v1")
    monkeypatch.setattr(client_module, "UC_GATEWAY_KEY", "fixture-shared-key")
    if per_org:
        monkeypatch.setenv("UC_GATEWAY_PER_ORG_KEYS_ENABLED", "1")
        monkeypatch.setenv("UC_GATEWAY_ORG_KEYS_JSON", '{"org-a":"fixture-org-key"}')
    clear_org_gateway_cache()
    model = "local/Qwen_Qwen3.6-35B-A3B-Q4_K_M"
    assert describe_route(model) == {
        "model_requested": model,
        "model_resolved": model,
        "route_type": "gateway",
        "target_host": "gateway.test",
    }
    client = _make_client()
    try:
        with respx.mock(assert_all_called=True) as router:
            upstream = router.post("https://gateway.test/v1/chat/completions")
            upstream.respond(200, json=_success_response())
            kwargs = {
                "messages": [{"role": "user", "content": "hello"}],
                "model": model,
                "org_id": "org-a",
                "user_id": "user-a",
            }
            if mode == "tools":
                await client.chat_completion_with_tools(tools=[], **kwargs)
            elif mode == "stream":
                upstream.mock(return_value=_completion_response(mode))
                assert [chunk async for chunk in client.chat_completion_stream(**kwargs)]
            else:
                await client.chat_completion(**kwargs)
    finally:
        await client.close()
        clear_org_gateway_cache()

    assert upstream.call_count == 1
    request = upstream.calls[0].request
    assert request.headers["Authorization"] == (
        "Bearer fixture-org-key" if per_org else "Bearer fixture-shared-key"
    )
    assert request.headers["X-Org-ID"] == "org-a"
    assert request.headers["X-User-ID"] == "user-a"
    payload = json.loads(request.content)
    assert payload["model"] == model
    assert payload["user"] == "user-a"


@pytest.mark.parametrize("mode", ["chat", "tools", "stream"])
@pytest.mark.parametrize("gateway_url", ["", "https://gateway.test/v1"])
async def test_explicit_local_override_keeps_direct_request(
    route_environment, monkeypatch, mode, gateway_url
):
    monkeypatch.setattr(client_module, "UC_GATEWAY_URL", gateway_url)
    monkeypatch.setattr(client_module, "UC_GATEWAY_KEY", "fixture-shared-key")
    client = _make_client()
    try:
        with respx.mock(assert_all_called=True) as router:
            upstream = router.post("http://llama.test:8080/v1/chat/completions")
            upstream.mock(return_value=_completion_response(mode))
            await _complete(client, mode, "local/qwen-test")
    finally:
        await client.close()

    assert upstream.call_count == 1
    request = upstream.calls[0].request
    assert "Authorization" not in request.headers
    assert json.loads(request.content)["model"] == "qwen-test"


@pytest.mark.parametrize("mode", ["chat", "tools"])
@pytest.mark.parametrize(
    "healthy_model,healthy_base",
    [
        ("midboy1/healthy", "http://second.test:8080"),
        ("midboy1/healthy", "http://llama.test:8080/another-backend"),
        ("uc/healthy", "https://gateway.test/v1"),
    ],
)
async def test_upstream_failure_opens_only_its_route_breaker(
    route_environment, monkeypatch, mode, healthy_model, healthy_base
):
    monkeypatch.setattr(client_module, "MIDBOY1_LLM_URL", healthy_base)
    monkeypatch.setattr(client_module, "UC_GATEWAY_URL", "https://gateway.test/v1")
    monkeypatch.setattr(client_module, "UC_GATEWAY_KEY", "fixture-key")
    monkeypatch.setattr(client_module, "DEFAULT_MODEL", "local/broken")
    healthy_endpoint = healthy_base + (
        "/chat/completions" if healthy_model.startswith("uc/") else "/v1/chat/completions"
    )
    client = _make_client()
    try:
        with respx.mock(assert_all_called=True) as router:
            broken = router.post("http://llama.test:8080/v1/chat/completions").respond(503)
            healthy = router.post(healthy_endpoint).respond(200, json=_success_response())
            for model in ("local/broken", "default", "auto", "local/another-model", "local/broken"):
                with pytest.raises(httpx.HTTPStatusError):
                    await _complete(client, mode, model)
            breaker = client._llm_breakers[("local", "http://llama.test:8080")]
            assert breaker.failure_threshold == 5
            assert breaker.cooldown_seconds == 30.0
            assert breaker.state == CircuitState.OPEN
            assert breaker.failure_count == 5
            assert broken.call_count == 15  # Three attempts per failed completion.

            # Plain and tool completions share this backend's breaker.
            other_mode = "tools" if mode == "chat" else "chat"
            with pytest.raises(CircuitOpenError):
                await _complete(client, other_mode, "local/yet-another-model")
            assert broken.call_count == 15
            assert await _complete(client, other_mode, healthy_model) == _success_response()
            assert healthy.call_count == 1
            assert len(client._llm_breakers) == 2
            assert breaker.state == CircuitState.OPEN
    finally:
        await client.close()


def _dns_error(kind):
    if kind == "raw":
        return socket.gaierror(socket.EAI_NONAME, "Name or service not known")
    if kind == "wrapped":
        error = httpx.ConnectError("All connection attempts failed")
        intermediate = OSError("connection failed")
        intermediate.__context__ = socket.gaierror(socket.EAI_NONAME, "resolver failed")
        error.__cause__ = intermediate
        return error
    return httpx.ConnectError(kind)


@pytest.mark.parametrize("mode", ["chat", "tools"])
@pytest.mark.parametrize(
    "kind",
    [
        "raw",
        "wrapped",
        "[Errno -2] Name or service not known",
        "[Errno 8] nodename nor servname provided, or not known",
        "[Errno -3] Temporary failure in name resolution",
        "[Errno 11001] getaddrinfo failed",
        "No address associated with hostname",
    ],
)
async def test_dns_failure_is_not_retried_or_counted(route_environment, mode, kind):
    error = _dns_error(kind)
    requests = []

    def transport(request):
        requests.append(request)
        if len(requests) <= 3:
            return httpx.Response(503)
        # MockTransport preserves __cause__; respx replaces it with its own
        # SideEffectError, hiding the resolver exception this test exercises.
        raise error

    client = _make_client()
    await client.client.aclose()
    client.client = httpx.AsyncClient(transport=httpx.MockTransport(transport))
    try:
        # Excluded failures must preserve an existing failure count, not reset it.
        with pytest.raises(httpx.HTTPStatusError):
            await _complete(client, mode, "local/test")
        assert len(requests) == 3
        breaker = client._llm_breakers[("local", "http://llama.test:8080")]
        assert breaker.failure_count == 1

        for _ in range(6):
            with pytest.raises(type(error)) as raised:
                await _complete(client, mode, "local/test")
            assert raised.value is error
        assert len(requests) == 9  # Six DNS errors, one attempt each.
        assert breaker.failure_count == 1
        assert breaker.state == CircuitState.CLOSED
    finally:
        await client.close()


@pytest.mark.parametrize("mode", ["chat", "tools", "stream"])
async def test_local_model_requires_explicit_route_configuration(
    route_environment, monkeypatch, mode
):
    monkeypatch.setattr(client_module, "LOCAL_LLM_URL", "")
    client = _make_client()
    try:
        with patch.object(client.client, "stream") as request:
            with pytest.raises(client_module.ConfigError, match="UC_GATEWAY_URL or LOCAL_LLM_URL"):
                await _complete(client, mode, "local/test")
        request.assert_not_called()
        assert client._llm_breakers == {}
    finally:
        await client.close()


@pytest.mark.parametrize("mode", ["chat", "tools"])
@pytest.mark.parametrize(
    "error",
    [
        httpx.InvalidURL("invalid URL"),
        httpx.UnsupportedProtocol("URL must use http or https"),
        client_module.ConfigError("missing configuration"),
    ],
)
async def test_configuration_error_is_not_retried_or_counted(
    route_environment, monkeypatch, mode, error
):
    client = _make_client()
    method = "_chat_completion_once" if mode == "chat" else "_chat_completion_with_tools_once"
    attempt = AsyncMock(side_effect=error)
    monkeypatch.setattr(client, method, attempt)
    try:
        for _ in range(6):
            with pytest.raises(type(error)) as raised:
                await _complete(client, mode, "local/test")
            assert raised.value is error
        assert attempt.await_count == 6
        breaker = client._llm_breakers[("local", "http://llama.test:8080")]
        assert breaker.failure_count == 0
        assert breaker.state == CircuitState.CLOSED
    finally:
        await client.close()


@pytest.mark.parametrize("error", [httpx.ConnectError("Connection refused"), httpx.ReadTimeout("slow")])
async def test_transient_transport_errors_still_retry_and_count(route_environment, error):
    client = _make_client()
    try:
        with respx.mock(assert_all_called=True) as router:
            upstream = router.post("http://llama.test:8080/v1/chat/completions")
            upstream.side_effect = error
            with pytest.raises(type(error)):
                await _complete(client, "chat", "local/test")
        assert upstream.call_count == 3
        breaker = client._llm_breakers[("local", "http://llama.test:8080")]
        assert breaker.failure_count == 1
        assert breaker.state == CircuitState.CLOSED
    finally:
        await client.close()


def test_dns_classification_handles_cyclic_exception_chains():
    error = httpx.ConnectError("connection failed")
    error.__cause__ = error
    assert default_is_transient(error) is True
    error.__context__ = socket.gaierror(socket.EAI_AGAIN, "resolver failed")
    assert default_is_transient(error) is False


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
