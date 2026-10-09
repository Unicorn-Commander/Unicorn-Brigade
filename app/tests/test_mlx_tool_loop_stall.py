"""The MLX tool loop must not end a turn on a DESCRIBED tool call either.

app/llm/mlx_provider.py carries a second tool loop with the same contract as
OpsCenterLLMClient.execute_tool_loop, and the same structural-only done-check.
It uses the native tool protocol (so it never seeds the imitable "I'll use the
following tools" ack), but a model can still narrate a call instead of emitting
one — and then the turn used to end with the narration as the answer.

Run with:
    python3 -m pytest app/tests/test_mlx_tool_loop_stall.py -v
"""

import pytest

from app.llm.mlx_provider import MLXLLMClient
from app.llm.ops_center_client import TOOL_NUDGE, ToolDefinition


class _ScriptedMLX(MLXLLMClient):
    """Replays canned completions and records what the loop sent back."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.sent = []

    async def chat_completion_with_tools(self, messages, **kwargs):
        self.sent.append(list(messages))
        return self._responses.pop(0)


def _text(content):
    return {"choices": [{"message": {"role": "assistant", "content": content}}]}


def _call(name):
    return {"choices": [{"message": {"role": "assistant", "content": "", "tool_calls": [
        {"id": "c1", "type": "function",
         "function": {"name": name, "arguments": "{}"}}]}}]}


async def _timeline():
    return {"result": "last visit 2026-09-04"}


TIMELINE_TOOL = ToolDefinition(
    name="glitter_get_timeline", description="timeline", handler=_timeline,
)


@pytest.mark.asyncio
async def test_a_described_call_is_nudged_and_the_turn_continues():
    client = _ScriptedMLX([
        _text("Let me check glitter_get_timeline for that date."),
        _call("glitter_get_timeline"),
        _text("Your last appointment on record was 2026-09-04."),
    ])
    out = await client.execute_tool_loop(
        messages=[{"role": "user", "content": "when was my last appointment?"}],
        tools=[TIMELINE_TOOL],
    )
    assert client.get_response_content(out) == (
        "Your last appointment on record was 2026-09-04."
    )
    assert client.sent[1][-1] == {"role": "user", "content": TOOL_NUDGE}


@pytest.mark.asyncio
async def test_only_one_nudge_per_stall_so_the_turn_still_terminates():
    stall = "Let me check glitter_get_timeline for that date."
    client = _ScriptedMLX([_text(stall), _text(stall)])
    out = await client.execute_tool_loop(
        messages=[{"role": "user", "content": "when was my last appointment?"}],
        tools=[TIMELINE_TOOL],
        max_iterations=6,
    )
    assert client.get_response_content(out) == stall
    assert len(client.sent) == 2


@pytest.mark.asyncio
async def test_a_plain_answer_still_completes_without_an_extra_round():
    client = _ScriptedMLX([_text("No appointments are on record.")])
    out = await client.execute_tool_loop(
        messages=[{"role": "user", "content": "when was my last appointment?"}],
        tools=[TIMELINE_TOOL],
    )
    assert client.get_response_content(out) == "No appointments are on record."
    assert len(client.sent) == 1
