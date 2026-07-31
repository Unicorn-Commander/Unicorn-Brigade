import json

import pytest

from app.api import agent_routes


@pytest.mark.asyncio
async def test_stream_chat_passes_org_context_without_closing_empty(monkeypatch):
    seen = {}

    class FakeLLMClient:
        async def chat_completion_stream(self, **kwargs):
            seen.update(kwargs)
            yield json.dumps(
                {
                    "choices": [
                        {"delta": {"content": "working"}, "finish_reason": None}
                    ]
                }
            )

    async def noop(*args, **kwargs):
        return None

    monkeypatch.setattr(agent_routes, "llm_client", FakeLLMClient())
    monkeypatch.setattr(agent_routes, "emit_agent_started", noop)
    monkeypatch.setattr(agent_routes, "emit_agent_completed", noop)
    monkeypatch.setattr(agent_routes, "_meter_chat_to_lago", noop)

    frames = [
        frame
        async for frame in agent_routes._stream_chat(
            messages=[{"role": "user", "content": "hello"}],
            model="uc/chat-default-nothink",
            temperature=0.2,
            max_tokens=64,
            agent={"id": "majik", "name": "majik"},
            user_id="user-1",
            agent_tools=[],
            session=None,
            user_email="user@example.com",
            org_id="org-1",
        )
    ]

    assert seen["org_id"] == "org-1"
    assert any('"type": "token"' in frame and "working" in frame for frame in frames)
    assert any('"type": "complete"' in frame and "working" in frame for frame in frames)
    assert not any('"type": "error"' in frame for frame in frames)

