"""BR-4 reliability tests: bounded retry, circuit breaker, tool degradation.

No real network or DB: the LLM HTTP layer is stubbed and time is injected, so
the suite runs deterministically and instantly. These exercise the reliability
primitives in isolation (which is the point) plus the real
``execute_tool_loop`` tool-error / per-tool-timeout path.
"""

from __future__ import annotations

import asyncio

import httpx
import pytest

from app.reliability.retry import (
    RetryConfig,
    default_is_transient,
    is_transient_http_status,
    retry_async,
)
from app.reliability.circuit import (
    CircuitBreaker,
    CircuitOpenError,
    CircuitState,
)
from app.llm.ops_center_client import (
    OpsCenterLLMClient,
    ToolDefinition,
)


# ── helpers ────────────────────────────────────────────────────────────────

def _http_status_error(status: int) -> httpx.HTTPStatusError:
    req = httpx.Request("POST", "http://test.invalid/v1/chat/completions")
    resp = httpx.Response(status, request=req)
    return httpx.HTTPStatusError(f"HTTP {status}", request=req, response=resp)


async def _no_sleep(_delay: float) -> None:
    """Injected into retry_async so backoff sleeps are instant in tests."""
    return None


def _tool_call_response(name: str, call_id: str) -> dict:
    """An OpenAI-format response that asks for a single tool call."""
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": call_id,
                            "type": "function",
                            "function": {"name": name, "arguments": "{}"},
                        }
                    ],
                }
            }
        ]
    }


def _final_response(text: str) -> dict:
    return {"choices": [{"message": {"role": "assistant", "content": text}}]}


# ── (a) retry helper ────────────────────────────────────────────────────────

def test_transient_classification():
    assert is_transient_http_status(503) is True
    assert is_transient_http_status(500) is True
    assert is_transient_http_status(429) is True
    assert is_transient_http_status(400) is False
    assert is_transient_http_status(404) is False

    assert default_is_transient(_http_status_error(503)) is True
    assert default_is_transient(_http_status_error(429)) is True
    assert default_is_transient(_http_status_error(400)) is False
    assert default_is_transient(httpx.ConnectError("down")) is True
    assert default_is_transient(httpx.ReadTimeout("slow")) is True
    assert default_is_transient(ValueError("bug")) is False


@pytest.mark.asyncio
async def test_retry_retries_on_503_then_succeeds():
    calls = {"n": 0}

    async def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise _http_status_error(503)
        return "ok"

    result = await retry_async(
        flaky,
        config=RetryConfig(max_attempts=3, base_delay=0.0, jitter=0.0),
        sleep=_no_sleep,
    )
    assert result == "ok"
    assert calls["n"] == 3  # failed twice, succeeded on the third


@pytest.mark.asyncio
async def test_retry_does_not_retry_on_400():
    calls = {"n": 0}

    async def bad_request():
        calls["n"] += 1
        raise _http_status_error(400)

    with pytest.raises(httpx.HTTPStatusError) as exc:
        await retry_async(
            bad_request,
            config=RetryConfig(max_attempts=5, base_delay=0.0, jitter=0.0),
            sleep=_no_sleep,
        )
    assert exc.value.response.status_code == 400
    assert calls["n"] == 1  # NOT retried — deterministic client error


@pytest.mark.asyncio
async def test_retry_exhausts_then_reraises_original():
    calls = {"n": 0}

    async def always_503():
        calls["n"] += 1
        raise _http_status_error(503)

    with pytest.raises(httpx.HTTPStatusError) as exc:
        await retry_async(
            always_503,
            config=RetryConfig(max_attempts=3, base_delay=0.0, jitter=0.0),
            sleep=_no_sleep,
        )
    assert exc.value.response.status_code == 503
    assert calls["n"] == 3  # exactly max_attempts tries, then gives up


# ── (b) circuit breaker ─────────────────────────────────────────────────────

class _Clock:
    """Injectable monotonic clock for deterministic cooldown tests."""

    def __init__(self):
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


@pytest.mark.asyncio
async def test_circuit_opens_after_threshold_and_fails_fast():
    clock = _Clock()
    breaker = CircuitBreaker(
        name="t", failure_threshold=2, cooldown_seconds=10.0, clock=clock
    )
    invoked = {"n": 0}

    async def boom():
        invoked["n"] += 1
        raise RuntimeError("backend down")

    # Two counted failures open the breaker.
    for _ in range(2):
        with pytest.raises(RuntimeError):
            await breaker.call(boom)
    assert breaker.state == CircuitState.OPEN
    assert invoked["n"] == 2

    # While OPEN, calls fail fast WITHOUT invoking the wrapped fn.
    with pytest.raises(CircuitOpenError):
        await breaker.call(boom)
    assert invoked["n"] == 2  # not incremented — fast-failed


@pytest.mark.asyncio
async def test_circuit_half_opens_then_closes_on_success():
    clock = _Clock()
    breaker = CircuitBreaker(
        name="t", failure_threshold=1, cooldown_seconds=10.0, clock=clock
    )

    async def boom():
        raise RuntimeError("down")

    async def ok():
        return "recovered"

    with pytest.raises(RuntimeError):
        await breaker.call(boom)
    assert breaker.state == CircuitState.OPEN

    # Still within cooldown -> fast fail.
    with pytest.raises(CircuitOpenError):
        await breaker.call(ok)

    # Cooldown elapses -> HALF_OPEN probe allowed -> success closes the breaker.
    clock.advance(11.0)
    result = await breaker.call(ok)
    assert result == "recovered"
    assert breaker.state == CircuitState.CLOSED
    assert breaker.failure_count == 0


@pytest.mark.asyncio
async def test_circuit_half_open_failure_reopens():
    clock = _Clock()
    breaker = CircuitBreaker(
        name="t", failure_threshold=1, cooldown_seconds=5.0, clock=clock
    )

    async def boom():
        raise RuntimeError("still down")

    with pytest.raises(RuntimeError):
        await breaker.call(boom)
    assert breaker.state == CircuitState.OPEN

    clock.advance(6.0)  # into HALF_OPEN window
    with pytest.raises(RuntimeError):
        await breaker.call(boom)  # probe fails
    assert breaker.state == CircuitState.OPEN  # reopened


@pytest.mark.asyncio
async def test_circuit_ignores_non_counted_failures():
    """A 4xx must never trip the breaker (is_failure=default_is_transient)."""
    breaker = CircuitBreaker(
        name="llm",
        failure_threshold=2,
        cooldown_seconds=10.0,
        is_failure=default_is_transient,
    )

    async def client_error():
        raise _http_status_error(400)

    for _ in range(5):
        with pytest.raises(httpx.HTTPStatusError):
            await breaker.call(client_error)

    # 4xx errors are not health signals -> breaker stayed CLOSED.
    assert breaker.state == CircuitState.CLOSED
    assert breaker.failure_count == 0


# ── (c) graceful tool degradation in execute_tool_loop ──────────────────────

@pytest.mark.asyncio
async def test_tool_exception_yields_structured_error():
    client = OpsCenterLLMClient(ops_center_url="http://test.invalid")
    try:
        calls = {"n": 0}

        async def fake_completion(*args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                return _tool_call_response("boom_tool", "call_1")
            return _final_response("Sorry, that tool failed — let me try another way.")

        # Stub the (resilient) LLM call so no network is touched.
        client.chat_completion_with_tools = fake_completion

        async def boom_handler(**kwargs):
            raise RuntimeError("kaboom")

        boom_tool = ToolDefinition(
            name="boom_tool", description="always raises", parameters=[], handler=boom_handler
        )

        captured: list = []
        result = await client.execute_tool_loop(
            messages=[{"role": "user", "content": "do the thing"}],
            tools=[boom_tool],
            on_tool_result=lambda r: captured.append(r),
        )

        # One tool result, carrying a STRUCTURED error (not a crash).
        assert len(captured) == 1
        assert captured[0].error is not None
        assert "kaboom" in captured[0].error
        assert captured[0].result is None
        # The loop recovered and returned the model's final answer.
        assert client.get_response_content(result).startswith("Sorry, that tool failed")
        assert calls["n"] == 2  # tool-call turn, then recovery turn
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_hung_tool_times_out_with_structured_error():
    client = OpsCenterLLMClient(ops_center_url="http://test.invalid")
    try:
        calls = {"n": 0}

        async def fake_completion(*args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                return _tool_call_response("hang_tool", "call_1")
            return _final_response("The tool did not respond in time.")

        client.chat_completion_with_tools = fake_completion

        async def hang_handler(**kwargs):
            await asyncio.sleep(30)  # would hang the turn without the guard
            return "never"

        hang_tool = ToolDefinition(
            name="hang_tool", description="hangs forever", parameters=[], handler=hang_handler
        )

        captured: list = []
        # Tiny per-tool timeout: the whole test must finish well under 30s.
        result = await asyncio.wait_for(
            client.execute_tool_loop(
                messages=[{"role": "user", "content": "call the slow tool"}],
                tools=[hang_tool],
                on_tool_result=lambda r: captured.append(r),
                tool_timeout=0.05,
            ),
            timeout=5.0,
        )

        assert len(captured) == 1
        assert captured[0].error is not None
        assert "timed out" in captured[0].error.lower()
        assert client.get_response_content(result) == "The tool did not respond in time."
    finally:
        await client.close()
