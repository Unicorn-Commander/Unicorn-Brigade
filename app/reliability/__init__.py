"""BR-4 reliability primitives: bounded retry + circuit breaker + HTTP timeout
defaults. Dependency-free and independently unit-testable.
"""

from app.reliability.retry import (
    DEFAULT_CONNECT_TIMEOUT,
    DEFAULT_LLM_TIMEOUT,
    DEFAULT_TOOL_TIMEOUT,
    RetryConfig,
    RetryExhaustedError,
    compute_backoff,
    default_is_transient,
    is_transient_http_status,
    retry_async,
)
from app.reliability.circuit import (
    CircuitBreaker,
    CircuitOpenError,
    CircuitState,
)

__all__ = [
    # retry
    "retry_async",
    "RetryConfig",
    "RetryExhaustedError",
    "default_is_transient",
    "is_transient_http_status",
    "compute_backoff",
    # circuit
    "CircuitBreaker",
    "CircuitOpenError",
    "CircuitState",
    # timeouts
    "DEFAULT_CONNECT_TIMEOUT",
    "DEFAULT_LLM_TIMEOUT",
    "DEFAULT_TOOL_TIMEOUT",
]
