"""A model that DESCRIBES a tool call instead of emitting one must not end the turn.

Regression for the 2026-10-01 dr-glitter-mane turn: iteration 1 called
``glitter_get_visit_summary`` and it succeeded; iteration 2 replied, in prose,
"I'll use the following tools: glitter_get_timeline" with no structured call.
``has_tool_calls`` is purely structural, so the loop treated that as a finished
answer and handed the announcement to the user instead of an appointment date.

Run with:
    python3 -m pytest app/llm/test_tool_loop_stall.py -v
"""

import pytest

from app.llm.ops_center_client import (
    TOOL_NUDGE,
    OpsCenterLLMClient,
    ToolDefinition,
    announced_tool_without_calling,
)

TOOLS = ["glitter_get_timeline", "glitter_get_visit_summary"]


# --- the detector ----------------------------------------------------------

def test_the_exact_sentence_the_user_was_shown_is_detected():
    assert announced_tool_without_calling(
        "I'll use the following tools: glitter_get_timeline", TOOLS
    ) == "glitter_get_timeline"


@pytest.mark.parametrize("text", [
    "Let me check glitter_get_timeline for the date.",
    "I need to query glitter_get_timeline first.",
    "Next, I'll call glitter_get_timeline.",
])
def test_other_announcement_phrasings_are_detected(text):
    assert announced_tool_without_calling(text, TOOLS) == "glitter_get_timeline"


@pytest.mark.parametrize("text", [
    "",
    "There are no appointments on record.",
    # An answer that merely NAMES a tool is a real answer, not a stall.
    "Nothing is recorded. I can add one with glitter_get_timeline if you like.",
    # Intent to act, but no configured tool named: not actionable, leave it.
    "Let me check your record for that.",
])
def test_real_answers_are_left_alone(text):
    assert announced_tool_without_calling(text, TOOLS) is None


# --- the loop --------------------------------------------------------------

class _ScriptedClient(OpsCenterLLMClient):
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
    client = _ScriptedClient([
        _text("I'll use the following tools: glitter_get_timeline"),
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
    # The nudge went out as a USER turn: a trailing system message is rejected
    # by templates that require system-first.
    nudge = client.sent[1][-1]
    assert nudge == {"role": "user", "content": TOOL_NUDGE}


@pytest.mark.asyncio
async def test_only_one_nudge_per_stall_so_the_turn_still_terminates():
    stall = "I'll use the following tools: glitter_get_timeline"
    client = _ScriptedClient([_text(stall), _text(stall)])
    out = await client.execute_tool_loop(
        messages=[{"role": "user", "content": "when was my last appointment?"}],
        tools=[TIMELINE_TOOL],
        max_iterations=6,
    )
    assert client.get_response_content(out) == stall
    assert len(client.sent) == 2  # nudged once, then gave up


@pytest.mark.asyncio
async def test_a_plain_answer_still_completes_without_an_extra_round():
    client = _ScriptedClient([_text("No appointments are on record.")])
    out = await client.execute_tool_loop(
        messages=[{"role": "user", "content": "when was my last appointment?"}],
        tools=[TIMELINE_TOOL],
    )
    assert client.get_response_content(out) == "No appointments are on record."
    assert len(client.sent) == 1
