from unittest.mock import MagicMock, call

import pytest

import app.observability.langfuse_client as langfuse_client


@pytest.fixture(autouse=True)
def reset_langfuse_state(monkeypatch):
    """Keep SDK state and environment isolated between fail-safe tests."""
    monkeypatch.delenv("LANGFUSE_ENABLED", raising=False)
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_HOST", raising=False)
    monkeypatch.setattr(langfuse_client, "_langfuse_client", None)
    monkeypatch.setattr(langfuse_client, "LANGFUSE_ENABLED", True)
    monkeypatch.setattr(langfuse_client, "LANGFUSE_PUBLIC_KEY", "test-public")
    monkeypatch.setattr(langfuse_client, "LANGFUSE_SECRET_KEY", "test-secret")


def _sdk_fixture(monkeypatch):
    client = MagicMock(name="langfuse_client")
    root = MagicMock(name="root_span")
    child_span = MagicMock(name="child_span")
    generation = MagicMock(name="generation")
    trace_context = MagicMock(name="trace_context")
    trace_context.__enter__.return_value = root
    trace_attributes = MagicMock(name="trace_attributes")
    root.start_observation.side_effect = [child_span, generation]

    propagate_attributes = MagicMock(return_value=trace_attributes)
    monkeypatch.setattr(langfuse_client, "_get_langfuse", lambda: client)
    monkeypatch.setattr("langfuse.propagate_attributes", propagate_attributes)
    client.start_as_current_observation.return_value = trace_context
    return client, root, child_span, generation, trace_context, trace_attributes, propagate_attributes


def test_traced_chat_emits_v4_trace_tool_and_generation_calls(monkeypatch):
    (
        client,
        root,
        child_span,
        generation,
        trace_context,
        trace_attributes,
        propagate_attributes,
    ) = _sdk_fixture(monkeypatch)

    tracer = langfuse_client.get_tracer(
        agent_id="agent-1",
        session_id="session-1",
        user_id="user-1",
    )
    tracer.start_trace(
        name="chat:agent-1",
        input_data={"message": "hello"},
        metadata={"agent_name": "Scout"},
        tags=["chat", "general"],
    )
    tracer.log_tool_call(
        tool_name="search",
        tool_input={"query": "hello"},
        tool_output={"matches": 1},
    )
    tracer.log_generation(
        name="chat_completion",
        model="test-model",
        input_messages=[{"role": "user", "content": "hello"}],
        output="world",
        usage={"input": 12, "output": 5},
        model_parameters={"temperature": 0.2},
        metadata={"tool_calls": 1},
    )
    tracer.end_trace(output={"content": "world"}, status="success")

    client.start_as_current_observation.assert_called_once_with(
        name="chat:agent-1",
        as_type="span",
        input={"message": "hello"},
        metadata={"agent_id": "agent-1", "agent_name": "Scout"},
        end_on_exit=False,
    )
    propagate_attributes.assert_called_once_with(
        user_id="user-1",
        session_id="session-1",
        metadata={"agent_id": "agent-1", "agent_name": "Scout"},
        tags=["chat", "general"],
        trace_name="chat:agent-1",
    )
    assert root.start_observation.call_args_list == [
        call(
            name="tool:search",
            as_type="tool",
            input={"query": "hello"},
            output={"matches": 1},
            metadata={"success": True, "duration_ms": None},
            level="DEFAULT",
        ),
        call(
            name="chat_completion",
            as_type="generation",
            model="test-model",
            input=[{"role": "user", "content": "hello"}],
            output="world",
            usage_details={
                "prompt_tokens": 12,
                "completion_tokens": 5,
                "total_tokens": 17,
            },
            model_parameters={"temperature": 0.2},
            metadata={"tool_calls": 1},
        ),
    ]
    child_span.end.assert_called_once_with()
    generation.end.assert_called_once_with()
    root.update.assert_called_once_with(
        output={"content": "world"},
        metadata={"status": "success"},
    )
    root.end.assert_called_once_with()
    trace_attributes.__exit__.assert_called_once_with(None, None, None)
    trace_context.__exit__.assert_called_once_with(None, None, None)


def test_unconfigured_langfuse_is_a_noop(monkeypatch):
    monkeypatch.setattr(langfuse_client, "LANGFUSE_PUBLIC_KEY", "")
    monkeypatch.setattr(langfuse_client, "LANGFUSE_SECRET_KEY", "")
    tracer = langfuse_client.get_tracer(agent_id="agent-1")

    tracer.start_trace("chat")
    tracer.start_span("child")
    tracer.log_generation("generation", "model", [], output="answer", usage={"input": 1})
    tracer.end_trace(output="answer")

    assert tracer._trace is None


def test_langfuse_errors_are_swallowed_and_logged(monkeypatch, caplog):
    client = MagicMock(name="raising_langfuse_client")
    client.start_as_current_observation.side_effect = RuntimeError("transport unavailable")
    monkeypatch.setattr(langfuse_client, "_get_langfuse", lambda: client)

    tracer = langfuse_client.get_tracer(agent_id="agent-1")
    with caplog.at_level("WARNING", logger=langfuse_client.logger.name):
        tracer.start_trace("chat")

    assert tracer._trace is None
    assert "Langfuse start_trace failed (RuntimeError)" in caplog.text


@pytest.mark.asyncio
async def test_lifespan_flushes_and_shutdown_closes_client(monkeypatch):
    client = MagicMock(name="langfuse_client")
    monkeypatch.setattr(langfuse_client, "_langfuse_client", client)
    monkeypatch.setattr(langfuse_client, "_get_langfuse", lambda: client)

    async with langfuse_client.langfuse_lifespan():
        pass
    langfuse_client.flush()
    langfuse_client.shutdown()

    assert client.flush.call_count == 3
    client.shutdown.assert_called_once_with()
    assert langfuse_client._langfuse_client is None
