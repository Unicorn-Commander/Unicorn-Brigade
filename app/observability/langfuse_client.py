"""
Langfuse Observability Client

Provides tracing, cost tracking, and evaluation for LLM operations.
Self-hosted Langfuse integration for Unicorn Brigade.
"""

import asyncio
import functools
import logging
import os
from contextlib import asynccontextmanager
from typing import Any, Callable, Optional, TypeVar

logger = logging.getLogger(__name__)

# Configuration from environment.  Keep these names aligned with the existing
# deployment contract; Langfuse v4 maps LANGFUSE_HOST to its base_url argument.
LANGFUSE_ENABLED = os.getenv("LANGFUSE_ENABLED", "true").lower() == "true"
LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY", "")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY", "")
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "http://localhost:3000")

# Lazy initialization: importing the application must not create an SDK client
# or start any OTel worker threads.
_langfuse_client = None


def _langfuse_configuration() -> tuple[bool, str, str, str]:
    """Read the Langfuse configuration while preserving import-time defaults."""
    enabled = os.getenv("LANGFUSE_ENABLED")
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    host = os.getenv("LANGFUSE_HOST")

    return (
        (enabled if enabled is not None else str(LANGFUSE_ENABLED)).lower() == "true",
        public_key if public_key is not None else LANGFUSE_PUBLIC_KEY,
        secret_key if secret_key is not None else LANGFUSE_SECRET_KEY,
        host if host is not None else LANGFUSE_HOST,
    )


def _log_langfuse_failure(operation: str, error: Exception) -> None:
    """Log SDK failures without putting request data or credentials in logs."""
    logger.warning("Langfuse %s failed (%s)", operation, type(error).__name__)


def _get_langfuse():
    """Get or create the v4 Langfuse client (lazily and fail-safe)."""
    global _langfuse_client

    enabled, public_key, secret_key, host = _langfuse_configuration()
    if not enabled or not public_key or not secret_key:
        return None

    if _langfuse_client is None:
        try:
            from langfuse import Langfuse

            _langfuse_client = Langfuse(
                public_key=public_key,
                secret_key=secret_key,
                base_url=host,
            )
            logger.info("Langfuse client initialized: %s", host)
        except ImportError:
            logger.warning("langfuse package not installed, observability disabled")
            return None
        except Exception as error:
            _log_langfuse_failure("client initialization", error)
            return None

    return _langfuse_client


def _normalise_usage(usage: Optional[dict[str, int]]) -> Optional[dict[str, int]]:
    """Translate Brigade's legacy token names to v4 usage_details names."""
    if not usage:
        return None

    aliases = {
        "input": "prompt_tokens",
        "output": "completion_tokens",
        "input_tokens": "prompt_tokens",
        "output_tokens": "completion_tokens",
        "total": "total_tokens",
    }
    normalised = {
        aliases.get(key, key): value
        for key, value in usage.items()
        if value is not None
    }

    if (
        "total_tokens" not in normalised
        and "prompt_tokens" in normalised
        and "completion_tokens" in normalised
    ):
        normalised["total_tokens"] = (
            normalised["prompt_tokens"] + normalised["completion_tokens"]
        )

    return normalised


def _close_context(context: Any, operation: str) -> None:
    """Close a synchronously entered v4 context manager without raising."""
    if context is None:
        return
    try:
        context.__exit__(None, None, None)
    except Exception as error:
        _log_langfuse_failure(operation, error)


class LangfuseTracer:
    """
    Tracer for Unicorn Brigade agent operations.

    The public facade is intentionally stable for Brigade callers.  Internally
    it uses Langfuse v4's OpenTelemetry observations instead of the removed v2
    trace/span/generation objects.
    """

    def __init__(
        self,
        agent_id: Optional[str] = None,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ):
        self.agent_id = agent_id
        self.session_id = session_id
        self.user_id = user_id
        self._trace = None
        self._trace_context = None
        self._attributes_context = None
        self._current_span = None

    def start_trace(
        self,
        name: str,
        input_data: Optional[dict[str, Any]] = None,
        metadata: Optional[dict[str, Any]] = None,
        tags: Optional[list] = None,
    ):
        """Start a root v4 span and propagate trace-level attributes."""
        client = _get_langfuse()
        if not client:
            return self

        trace_metadata = {
            "agent_id": self.agent_id,
            **(metadata or {}),
        }
        trace_context = None
        attributes_context = None

        try:
            # v4's generic observation API is the exact equivalent of the
            # older trace object.  Keep it current until end_trace() so child
            # observations created by this facade have the right parent.
            trace_context = client.start_as_current_observation(
                name=name,
                as_type="span",
                input=input_data,
                metadata=trace_metadata,
                end_on_exit=False,
            )
            trace = trace_context.__enter__()

            from langfuse import propagate_attributes

            attributes_context = propagate_attributes(
                user_id=self.user_id,
                session_id=self.session_id,
                metadata=trace_metadata,
                tags=tags or [],
                trace_name=name,
            )
            attributes_context.__enter__()

            self._trace = trace
            self._trace_context = trace_context
            self._attributes_context = attributes_context
        except Exception as error:
            if attributes_context is not None:
                _close_context(attributes_context, "trace attribute cleanup")
            if trace_context is not None:
                if "trace" in locals() and trace is not None:
                    try:
                        trace.end()
                    except Exception as end_error:
                        _log_langfuse_failure("trace cleanup", end_error)
                _close_context(trace_context, "trace cleanup")
            self._trace = None
            self._trace_context = None
            self._attributes_context = None
            _log_langfuse_failure("start_trace", error)

        return self

    def start_span(
        self,
        name: str,
        input_data: Optional[dict[str, Any]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ):
        """Start a child span within the current trace."""
        if not self._trace:
            return self

        try:
            self._current_span = self._trace.start_observation(
                name=name,
                as_type="span",
                input=input_data,
                metadata=metadata,
            )
        except Exception as error:
            self._current_span = None
            _log_langfuse_failure("start_span", error)

        return self

    def end_span(
        self,
        output: Optional[Any] = None,
        level: str = "DEFAULT",
    ):
        """Update and end the current child span."""
        span = self._current_span
        self._current_span = None
        if span is None:
            return self

        try:
            span.update(output=output, level=level)
        except Exception as error:
            _log_langfuse_failure("end_span update", error)
        finally:
            try:
                span.end()
            except Exception as error:
                _log_langfuse_failure("end_span", error)

        return self

    def log_generation(
        self,
        name: str,
        model: str,
        input_messages: list,
        output: Optional[str] = None,
        usage: Optional[dict[str, int]] = None,
        model_parameters: Optional[dict[str, Any]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ):
        """Create and end a v4 generation observation."""
        if not self._trace:
            return self

        generation = None
        try:
            generation = self._trace.start_observation(
                name=name,
                as_type="generation",
                model=model,
                input=input_messages,
                output=output,
                usage_details=_normalise_usage(usage),
                model_parameters=model_parameters,
                metadata=metadata,
            )
        except Exception as error:
            _log_langfuse_failure("log_generation", error)

        if generation is not None:
            try:
                generation.end()
            except Exception as error:
                _log_langfuse_failure("end_generation", error)

        return self

    def log_tool_call(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
        tool_output: Optional[Any] = None,
        success: bool = True,
        duration_ms: Optional[float] = None,
    ):
        """Create and end a v4 tool observation."""
        if not self._trace:
            return self

        tool = None
        try:
            tool = self._trace.start_observation(
                name=f"tool:{tool_name}",
                as_type="tool",
                input=tool_input,
                output=tool_output,
                metadata={
                    "success": success,
                    "duration_ms": duration_ms,
                },
                level="DEFAULT" if success else "WARNING",
            )
        except Exception as error:
            _log_langfuse_failure("log_tool_call", error)

        if tool is not None:
            try:
                tool.end()
            except Exception as error:
                _log_langfuse_failure("end_tool_call", error)

        return self

    def end_trace(
        self,
        output: Optional[Any] = None,
        status: str = "success",
        metadata: Optional[dict[str, Any]] = None,
    ):
        """Update and close the root observation."""
        trace = self._trace
        if trace is None:
            return self

        # Do not leave an unfinished child behind if a caller exits early.
        if self._current_span is not None:
            self.end_span()

        try:
            trace.update(
                output=output,
                metadata={
                    "status": status,
                    **(metadata or {}),
                },
            )
        except Exception as error:
            _log_langfuse_failure("end_trace update", error)
        finally:
            try:
                trace.end()
            except Exception as error:
                _log_langfuse_failure("end_trace", error)

            _close_context(self._attributes_context, "trace attribute cleanup")
            _close_context(self._trace_context, "trace cleanup")
            self._trace = None
            self._trace_context = None
            self._attributes_context = None

        return self

    def score(
        self,
        name: str,
        value: float,
        comment: Optional[str] = None,
    ):
        """Add a score to the current trace."""
        if not self._trace:
            return self

        try:
            self._trace.score_trace(
                name=name,
                value=value,
                comment=comment,
            )
        except Exception as error:
            _log_langfuse_failure("score", error)

        return self


def get_tracer(
    agent_id: Optional[str] = None,
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> LangfuseTracer:
    """Get a configured tracer instance."""
    return LangfuseTracer(
        agent_id=agent_id,
        session_id=session_id,
        user_id=user_id,
    )


# Type variable for decorator return types
F = TypeVar("F", bound=Callable[..., Any])


def _decorator_input(args: tuple, kwargs: dict) -> dict[str, Any]:
    """Build the same broad input shape for v4 decorator observations."""
    return {"args": list(args), "kwargs": kwargs}


def _run_observed_sync(
    func: Callable[..., Any],
    args: tuple,
    kwargs: dict,
    *,
    name: str,
    as_type: str,
    model: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
    tags: Optional[list] = None,
):
    """Run a sync function inside a fail-safe v4 observation."""
    client = _get_langfuse()
    if not client:
        return func(*args, **kwargs)

    context = None
    observation = None
    attributes_context = None
    try:
        context = client.start_as_current_observation(
            name=name,
            as_type=as_type,
            input=_decorator_input(args, kwargs),
            metadata=metadata,
            model=model,
            end_on_exit=False,
        )
        observation = context.__enter__()
        if metadata is not None or tags is not None:
            from langfuse import propagate_attributes

            attributes_context = propagate_attributes(
                metadata=metadata,
                tags=tags or [],
                trace_name=name,
            )
            attributes_context.__enter__()
    except Exception as error:
        if attributes_context is not None:
            _close_context(attributes_context, "decorator attribute cleanup")
        if observation is not None:
            try:
                observation.end()
            except Exception as end_error:
                _log_langfuse_failure("decorator cleanup", end_error)
        if context is not None:
            _close_context(context, "decorator cleanup")
        _log_langfuse_failure("decorator start", error)
        return func(*args, **kwargs)

    try:
        result = func(*args, **kwargs)
    except BaseException as error:
        if observation is not None:
            try:
                observation.update(
                    level="ERROR",
                    status_message=str(error) or type(error).__name__,
                )
            except Exception as update_error:
                _log_langfuse_failure("decorator error update", update_error)
        _close_context(attributes_context, "decorator attribute cleanup")
        try:
            context.__exit__(type(error), error, error.__traceback__)
        except Exception as exit_error:
            _log_langfuse_failure("decorator cleanup", exit_error)
        raise
    else:
        if observation is not None:
            try:
                observation.update(output=result)
            except Exception as error:
                _log_langfuse_failure("decorator output update", error)
        _close_context(attributes_context, "decorator attribute cleanup")
        try:
            context.__exit__(None, None, None)
        except Exception as error:
            _log_langfuse_failure("decorator cleanup", error)
        return result
    finally:
        if observation is not None:
            try:
                observation.end()
            except Exception as error:
                _log_langfuse_failure("decorator end", error)


async def _run_observed_async(
    func: Callable[..., Any],
    args: tuple,
    kwargs: dict,
    *,
    name: str,
    as_type: str,
    model: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
    tags: Optional[list] = None,
):
    """Run an async function inside a fail-safe v4 observation."""
    client = _get_langfuse()
    if not client:
        return await func(*args, **kwargs)

    context = None
    observation = None
    attributes_context = None
    try:
        context = client.start_as_current_observation(
            name=name,
            as_type=as_type,
            input=_decorator_input(args, kwargs),
            metadata=metadata,
            model=model,
            end_on_exit=False,
        )
        observation = context.__enter__()
        if metadata is not None or tags is not None:
            from langfuse import propagate_attributes

            attributes_context = propagate_attributes(
                metadata=metadata,
                tags=tags or [],
                trace_name=name,
            )
            attributes_context.__enter__()
    except Exception as error:
        if attributes_context is not None:
            _close_context(attributes_context, "decorator attribute cleanup")
        if observation is not None:
            try:
                observation.end()
            except Exception as end_error:
                _log_langfuse_failure("decorator cleanup", end_error)
        if context is not None:
            _close_context(context, "decorator cleanup")
        _log_langfuse_failure("decorator start", error)
        return await func(*args, **kwargs)

    try:
        result = await func(*args, **kwargs)
    except BaseException as error:
        if observation is not None:
            try:
                observation.update(
                    level="ERROR",
                    status_message=str(error) or type(error).__name__,
                )
            except Exception as update_error:
                _log_langfuse_failure("decorator error update", update_error)
        _close_context(attributes_context, "decorator attribute cleanup")
        try:
            context.__exit__(type(error), error, error.__traceback__)
        except Exception as exit_error:
            _log_langfuse_failure("decorator cleanup", exit_error)
        raise
    else:
        if observation is not None:
            try:
                observation.update(output=result)
            except Exception as error:
                _log_langfuse_failure("decorator output update", error)
        _close_context(attributes_context, "decorator attribute cleanup")
        try:
            context.__exit__(None, None, None)
        except Exception as error:
            _log_langfuse_failure("decorator cleanup", error)
        return result
    finally:
        if observation is not None:
            try:
                observation.end()
            except Exception as error:
                _log_langfuse_failure("decorator end", error)


def trace_llm_call(
    name: Optional[str] = None,
    model: Optional[str] = None,
) -> Callable[[F], F]:
    """
    Decorator to trace LLM calls as v4 generation observations.

    Usage:
        @trace_llm_call(name="chat_completion", model="gpt-4o")
        async def my_llm_call(messages: list) -> str:
            ...
    """

    def decorator(func: F) -> F:
        trace_name = name or func.__name__
        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                return await _run_observed_async(
                    func,
                    args,
                    kwargs,
                    name=trace_name,
                    as_type="generation",
                    model=model,
                )

            return async_wrapper  # type: ignore

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            return _run_observed_sync(
                func,
                args,
                kwargs,
                name=trace_name,
                as_type="generation",
                model=model,
            )

        return sync_wrapper  # type: ignore

    return decorator


def trace_tool_call(
    tool_name: Optional[str] = None,
) -> Callable[[F], F]:
    """Decorator to trace tool executions as v4 tool observations."""

    def decorator(func: F) -> F:
        observation_name = f"tool:{tool_name or func.__name__}"
        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                return await _run_observed_async(
                    func,
                    args,
                    kwargs,
                    name=observation_name,
                    as_type="tool",
                )

            return async_wrapper  # type: ignore

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            return _run_observed_sync(
                func,
                args,
                kwargs,
                name=observation_name,
                as_type="tool",
            )

        return sync_wrapper  # type: ignore

    return decorator


def trace_agent_run(
    agent_id: Optional[str] = None,
    operation: str = "chat",
) -> Callable[[F], F]:
    """Decorator to trace complete agent runs as v4 span observations."""

    def decorator(func: F) -> F:
        trace_name = f"agent:{agent_id or 'unknown'}:{operation}"
        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                return await _run_observed_async(
                    func,
                    args,
                    kwargs,
                    name=trace_name,
                    as_type="span",
                    metadata={"agent_id": agent_id, "operation": operation},
                    tags=["agent", operation],
                )

            return async_wrapper  # type: ignore

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            return _run_observed_sync(
                func,
                args,
                kwargs,
                name=trace_name,
                as_type="span",
                metadata={"agent_id": agent_id, "operation": operation},
                tags=["agent", operation],
            )

        return sync_wrapper  # type: ignore

    return decorator


@asynccontextmanager
async def langfuse_lifespan():
    """
    Async context manager for FastAPI lifespan.

    Startup is intentionally lazy.  The v4 client is created only when a trace
    is requested, and shutdown flushes any queued OTel spans best-effort.
    """
    logger.info("Langfuse observability ready")

    yield

    flush()


def flush():
    """Flush pending Langfuse v4 observations without affecting the app."""
    client = _get_langfuse()
    if client:
        try:
            client.flush()
        except Exception as error:
            _log_langfuse_failure("flush", error)


def shutdown():
    """Flush and shut down the Langfuse v4 client without raising."""
    global _langfuse_client
    client = _langfuse_client
    if client:
        try:
            client.flush()
        except Exception as error:
            _log_langfuse_failure("shutdown flush", error)
        try:
            client.shutdown()
        except Exception as error:
            _log_langfuse_failure("shutdown", error)
        finally:
            _langfuse_client = None
