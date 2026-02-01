"""
Langfuse Observability Client

Provides tracing, cost tracking, and evaluation for LLM operations.
Self-hosted Langfuse integration for Unicorn Brigade.
"""

import os
import logging
import functools
from typing import Any, Callable, Dict, Optional, TypeVar
from datetime import datetime
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

# Configuration from environment
LANGFUSE_ENABLED = os.getenv("LANGFUSE_ENABLED", "true").lower() == "true"
LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY", "")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY", "")
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "http://localhost:3000")

# Lazy initialization
_langfuse_client = None


def _get_langfuse():
    """Get or create Langfuse client (lazy initialization)."""
    global _langfuse_client

    if not LANGFUSE_ENABLED:
        return None

    if _langfuse_client is None:
        try:
            from langfuse import Langfuse

            _langfuse_client = Langfuse(
                public_key=LANGFUSE_PUBLIC_KEY or None,
                secret_key=LANGFUSE_SECRET_KEY or None,
                host=LANGFUSE_HOST,
            )
            logger.info(f"Langfuse client initialized: {LANGFUSE_HOST}")
        except ImportError:
            logger.warning("langfuse package not installed, observability disabled")
            return None
        except Exception as e:
            logger.error(f"Failed to initialize Langfuse: {e}")
            return None

    return _langfuse_client


class LangfuseTracer:
    """
    Tracer for Unicorn Brigade agent operations.

    Wraps Langfuse functionality with Brigade-specific conventions.
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
        self._current_span = None

    def start_trace(
        self,
        name: str,
        input_data: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[list] = None,
    ):
        """Start a new trace for an operation."""
        client = _get_langfuse()
        if not client:
            return self

        trace_metadata = {
            "agent_id": self.agent_id,
            **(metadata or {}),
        }

        self._trace = client.trace(
            name=name,
            input=input_data,
            session_id=self.session_id,
            user_id=self.user_id,
            metadata=trace_metadata,
            tags=tags or [],
        )

        return self

    def start_span(
        self,
        name: str,
        input_data: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Start a new span within the current trace."""
        if not self._trace:
            return self

        self._current_span = self._trace.span(
            name=name,
            input=input_data,
            metadata=metadata,
        )

        return self

    def end_span(
        self,
        output: Optional[Any] = None,
        level: str = "DEFAULT",
    ):
        """End the current span."""
        if self._current_span:
            self._current_span.end(
                output=output,
                level=level,
            )
            self._current_span = None

        return self

    def log_generation(
        self,
        name: str,
        model: str,
        input_messages: list,
        output: Optional[str] = None,
        usage: Optional[Dict[str, int]] = None,
        model_parameters: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Log an LLM generation (call)."""
        if not self._trace:
            return self

        self._trace.generation(
            name=name,
            model=model,
            input=input_messages,
            output=output,
            usage=usage,
            model_parameters=model_parameters,
            metadata=metadata,
        )

        return self

    def log_tool_call(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        tool_output: Optional[Any] = None,
        success: bool = True,
        duration_ms: Optional[float] = None,
    ):
        """Log a tool execution."""
        if not self._trace:
            return self

        metadata = {
            "success": success,
            "duration_ms": duration_ms,
        }

        self._trace.span(
            name=f"tool:{tool_name}",
            input=tool_input,
            output=tool_output,
            metadata=metadata,
            level="WARNING" if not success else "DEFAULT",
        )

        return self

    def end_trace(
        self,
        output: Optional[Any] = None,
        status: str = "success",
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """End the current trace."""
        if self._trace:
            final_metadata = {
                "status": status,
                **(metadata or {}),
            }
            self._trace.update(
                output=output,
                metadata=final_metadata,
            )
            self._trace = None

        return self

    def score(
        self,
        name: str,
        value: float,
        comment: Optional[str] = None,
    ):
        """Add a score to the current trace."""
        if self._trace:
            self._trace.score(
                name=name,
                value=value,
                comment=comment,
            )

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
F = TypeVar('F', bound=Callable[..., Any])


def trace_llm_call(
    name: Optional[str] = None,
    model: Optional[str] = None,
) -> Callable[[F], F]:
    """
    Decorator to trace LLM calls.

    Usage:
        @trace_llm_call(name="chat_completion", model="gpt-4o")
        async def my_llm_call(messages: list) -> str:
            ...
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            client = _get_langfuse()
            if not client:
                return await func(*args, **kwargs)

            trace_name = name or func.__name__
            start_time = datetime.utcnow()

            try:
                # Try to use langfuse's @observe decorator if available
                from langfuse import observe
                observed_func = observe(name=trace_name, as_type="generation")(func)
                return await observed_func(*args, **kwargs)
            except ImportError:
                # Fallback to manual tracing
                result = await func(*args, **kwargs)
                return result

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            client = _get_langfuse()
            if not client:
                return func(*args, **kwargs)

            trace_name = name or func.__name__

            try:
                from langfuse import observe
                observed_func = observe(name=trace_name, as_type="generation")(func)
                return observed_func(*args, **kwargs)
            except ImportError:
                return func(*args, **kwargs)

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return sync_wrapper  # type: ignore

    return decorator


def trace_tool_call(
    tool_name: Optional[str] = None,
) -> Callable[[F], F]:
    """
    Decorator to trace tool executions.

    Usage:
        @trace_tool_call(tool_name="web_search")
        async def web_search_handler(query: str) -> dict:
            ...
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            client = _get_langfuse()
            if not client:
                return await func(*args, **kwargs)

            name = tool_name or func.__name__
            start_time = datetime.utcnow()

            try:
                from langfuse import observe
                observed_func = observe(name=f"tool:{name}")(func)
                return await observed_func(*args, **kwargs)
            except ImportError:
                return await func(*args, **kwargs)

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            client = _get_langfuse()
            if not client:
                return func(*args, **kwargs)

            name = tool_name or func.__name__

            try:
                from langfuse import observe
                observed_func = observe(name=f"tool:{name}")(func)
                return observed_func(*args, **kwargs)
            except ImportError:
                return func(*args, **kwargs)

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return sync_wrapper  # type: ignore

    return decorator


def trace_agent_run(
    agent_id: Optional[str] = None,
    operation: str = "chat",
) -> Callable[[F], F]:
    """
    Decorator to trace complete agent runs.

    Usage:
        @trace_agent_run(agent_id="col-finance", operation="chat")
        async def agent_chat(message: str) -> str:
            ...
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            client = _get_langfuse()
            if not client:
                return await func(*args, **kwargs)

            trace_name = f"agent:{agent_id or 'unknown'}:{operation}"

            try:
                from langfuse import observe, langfuse_context

                @observe(name=trace_name)
                async def traced_func(*a, **kw):
                    # Update trace with agent metadata
                    langfuse_context.update_current_trace(
                        name=trace_name,
                        metadata={
                            "agent_id": agent_id,
                            "operation": operation,
                        },
                        tags=["agent", operation],
                    )
                    return await func(*a, **kw)

                return await traced_func(*args, **kwargs)
            except ImportError:
                return await func(*args, **kwargs)

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            client = _get_langfuse()
            if not client:
                return func(*args, **kwargs)

            trace_name = f"agent:{agent_id or 'unknown'}:{operation}"

            try:
                from langfuse import observe
                observed_func = observe(name=trace_name)(func)
                return observed_func(*args, **kwargs)
            except ImportError:
                return func(*args, **kwargs)

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return sync_wrapper  # type: ignore

    return decorator


@asynccontextmanager
async def langfuse_lifespan():
    """
    Async context manager for FastAPI lifespan.

    Usage in main.py:
        from app.observability import langfuse_lifespan

        @asynccontextmanager
        async def lifespan(app):
            async with langfuse_lifespan():
                yield
    """
    # Startup - client is lazily initialized
    logger.info("Langfuse observability ready")

    yield

    # Shutdown - flush pending events
    client = _get_langfuse()
    if client:
        try:
            client.flush()
            logger.info("Langfuse events flushed")
        except Exception as e:
            logger.warning(f"Error flushing Langfuse: {e}")


def flush():
    """Manually flush pending Langfuse events."""
    client = _get_langfuse()
    if client:
        client.flush()


def shutdown():
    """Shutdown Langfuse client."""
    global _langfuse_client
    if _langfuse_client:
        try:
            _langfuse_client.flush()
            _langfuse_client.shutdown()
        except Exception as e:
            logger.warning(f"Error shutting down Langfuse: {e}")
        finally:
            _langfuse_client = None
