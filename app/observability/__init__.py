"""
Observability Module

Provides tracing, logging, monitoring, and code attribution for agent operations.
Includes Langfuse for LLM observability and Agent Trace for code attribution.
"""

from app.observability.langfuse_client import (
    LangfuseTracer,
    get_tracer,
    trace_llm_call,
    trace_tool_call,
    trace_agent_run,
    langfuse_lifespan,
    flush,
    shutdown,
)

from app.observability.agent_trace import (
    AgentTraceRecorder,
    CodeContribution,
    CodeLocation,
    CodeChangeType,
    Attribution,
    TraceSession,
    CodeExtractor,
    AGENT_TRACE_ENABLED,
)

from app.observability.trace_repository import TraceRepository

from app.observability.logging_config import (
    configure_logging,
    request_id_middleware,
    RequestContextFilter,
    JsonFormatter,
    request_id_ctx,
    mission_id_ctx,
    agent_id_ctx,
    REQUEST_ID_HEADER,
)

__all__ = [
    # Langfuse tracing
    "LangfuseTracer",
    "get_tracer",
    "trace_llm_call",
    "trace_tool_call",
    "trace_agent_run",
    "langfuse_lifespan",
    "flush",
    "shutdown",
    # Agent Trace
    "AgentTraceRecorder",
    "CodeContribution",
    "CodeLocation",
    "CodeChangeType",
    "Attribution",
    "TraceSession",
    "CodeExtractor",
    "TraceRepository",
    "AGENT_TRACE_ENABLED",
    # Structured logging + request-id correlation
    "configure_logging",
    "request_id_middleware",
    "RequestContextFilter",
    "JsonFormatter",
    "request_id_ctx",
    "mission_id_ctx",
    "agent_id_ctx",
    "REQUEST_ID_HEADER",
]
