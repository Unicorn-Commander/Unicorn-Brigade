"""API mapping for bounded upstream budget failures."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx

import app.llm.ops_center_client as client_module
from app.llm.ops_center_client import OpsCenterLLMClient


@pytest.fixture(autouse=True)
def _disable_environment_proxies(monkeypatch):
    for name in (
        "ALL_PROXY",
        "all_proxy",
        "HTTP_PROXY",
        "http_proxy",
        "HTTPS_PROXY",
        "https_proxy",
    ):
        monkeypatch.delenv(name, raising=False)


def _budget_response():
    return httpx.Response(
        402,
        json={"error": {"metadata": {"reason": "in_flight_budget_exhausted"}}},
        headers={"Retry-After": "120"},
    )


@pytest.mark.asyncio
async def test_repeated_402_maps_to_503_with_structured_body(monkeypatch):
    pytest.importorskip("fastapi")
    from app.main import upstream_budget_exhausted_handler

    monkeypatch.setattr(client_module, "OPENROUTER_API_KEY", "test-key")
    with respx.mock(assert_all_called=True) as router:
        upstream = router.post("https://openrouter.ai/api/v1/chat/completions")
        upstream.side_effect = [_budget_response(), _budget_response()]
        client = OpsCenterLLMClient(ops_center_url="https://ops.test", service_key="x" * 32)
        try:
            with patch("app.llm.ops_center_client.asyncio.sleep", new=AsyncMock()):
                with pytest.raises(client_module.UpstreamBudgetExhausted) as raised:
                    await client.chat_completion(
                        messages=[{"role": "user", "content": "hello"}],
                        model="openrouter/vendor/model",
                    )
        finally:
            await client.close()

    response = await upstream_budget_exhausted_handler(None, raised.value)
    assert response.status_code == 503
    assert response.body == (
        b'{"error":"upstream_budget_exhausted","route":"openrouter",'
        b'"retry_after":30.0,"reason":"in_flight_budget_exhausted"}'
    )
    assert upstream.call_count == 2
