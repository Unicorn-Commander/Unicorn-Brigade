"""Context injection must match every tool handler's signature.

ops_center_client injects caller_user_id (and caller_email whenever the caller
has an email, i.e. a person) into tools registered with needs_caller_context,
and caller_room_id / caller_room_name / caller_agent_id into tools registered
with needs_room_context. A handler that does not accept one of those fails at
call time with "unexpected keyword argument". delegate_to_agent did exactly
that for every human caller (Project-Ops e8b0097f, 2026-10-25), which stopped a
Brigade orchestrator from handing work to its specialists.
"""
from __future__ import annotations

import inspect

import pytest

import app.llm.delegation_tools as delegation
from app.llm.tool_resolver import TOOL_REGISTRY

CALLER_FIELDS = ("caller_user_id", "caller_email")
ROOM_FIELDS = ("caller_room_id", "caller_room_name", "caller_agent_id")


def _accepts(fn, name: str) -> bool:
    params = inspect.signature(fn).parameters.values()
    return any(p.name == name for p in params) or any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params)


def _tools(flag: str):
    return sorted(
        (name, tool) for name, tool in TOOL_REGISTRY.items()
        if getattr(tool, flag, False) and getattr(tool, "handler", None)
    )


@pytest.mark.parametrize("name,tool", _tools("needs_caller_context"), ids=lambda v: v if isinstance(v, str) else "")
def test_caller_context_tools_accept_every_injected_field(name, tool):
    missing = [f for f in CALLER_FIELDS if not _accepts(tool.handler, f)]
    assert not missing, f"{name} is injected {missing} but its handler does not accept them"


@pytest.mark.parametrize("name,tool", _tools("needs_room_context"), ids=lambda v: v if isinstance(v, str) else "")
def test_room_context_tools_accept_every_injected_field(name, tool):
    missing = [f for f in ROOM_FIELDS if not _accepts(tool.handler, f)]
    assert not missing, f"{name} is injected {missing} but its handler does not accept them"


def test_delegate_to_agent_is_caller_context_and_registered():
    assert TOOL_REGISTRY["delegate_to_agent"].needs_caller_context is True


async def test_a_human_caller_can_delegate(monkeypatch):
    sent = {}

    class _Resp:
        status_code = 200
        text = ""

        def json(self):
            return {"content": "plan ready"}

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def post(self, url, headers=None, json=None):
            sent.update(url=url, headers=headers, json=json)
            return _Resp()

    monkeypatch.setattr(delegation.httpx, "AsyncClient", _Client)
    out = await delegation.delegate_to_agent_handler(
        agent_id="the-general", task="draft a plan", caller_user_id="user-1", caller_email="person@example.com",
    )
    assert out == {"success": True, "agent_id": "the-general", "response": "plan ready"}
    assert sent["json"]["user_id"] == "user-1"
    assert "caller_email" not in sent["json"] and "person@example.com" not in str(sent["json"])
    assert sent["headers"]["X-Delegate-User"] == "user-1"
