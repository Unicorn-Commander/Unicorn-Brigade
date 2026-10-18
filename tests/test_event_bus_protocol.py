import pytest

from app.orchestration.event_bus import emit_agent_invocation, event_bus


@pytest.mark.asyncio
async def test_agent_invocation_emits_paid_and_normalizes_legacy_ap2(monkeypatch):
    published = []

    async def capture(event):
        published.append(event)

    monkeypatch.setattr(event_bus, "publish", capture)

    common = {
        "agent_id": "source",
        "agent_name": "Source",
        "target_agent_id": "target",
        "target_agent_name": "Target",
        "purpose": "paid external lookup",
    }
    await emit_agent_invocation(**common, protocol="paid")
    await emit_agent_invocation(**common, protocol="ap2")

    assert [event.data["protocol"] for event in published] == ["paid", "paid"]
