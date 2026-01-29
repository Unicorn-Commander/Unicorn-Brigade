"""
Observability Layer for Unicorn Brigade

Provides comprehensive monitoring, metrics, and tracing:
- Metrics: Counters, gauges, histograms for performance monitoring
- Tracing: Distributed tracing with spans and context
- Logging: Structured logging with correlation IDs
- Health Checks: Service health and dependency status

Compatible with:
- Prometheus (metrics export)
- OpenTelemetry (tracing)
- JSON structured logging
"""

import asyncio
import json
import logging
import time
import uuid
from typing import (
    Dict, Any, List, Optional, Callable, Union,
    ContextManager, TypeVar, Generic
)
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from contextlib import contextmanager, asynccontextmanager
from functools import wraps
import threading

logger = logging.getLogger(__name__)

T = TypeVar('T')


# ============== Metrics ==============

class MetricType(str, Enum):
    """Types of metrics"""
    COUNTER = "counter"  # Only increments
    GAUGE = "gauge"  # Can go up or down
    HISTOGRAM = "histogram"  # Distribution of values
    SUMMARY = "summary"  # Quantiles over time


@dataclass
class MetricLabels:
    """Labels for a metric"""
    values: Dict[str, str] = field(default_factory=dict)

    def key(self) -> str:
        """Get a unique key for this label set"""
        if not self.values:
            return ""
        return "|".join(f"{k}={v}" for k, v in sorted(self.values.items()))


@dataclass
class MetricValue:
    """Value of a metric with timestamp"""
    value: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    labels: MetricLabels = field(default_factory=MetricLabels)


class Counter:
    """Counter metric - only increments"""

    def __init__(self, name: str, description: str = "", labels: List[str] = None):
        self.name = name
        self.description = description
        self.label_names = labels or []
        self._values: Dict[str, float] = {}
        self._lock = threading.Lock()

    def inc(self, value: float = 1, labels: Optional[Dict[str, str]] = None):
        """Increment the counter"""
        key = MetricLabels(labels or {}).key()
        with self._lock:
            self._values[key] = self._values.get(key, 0) + value

    def get(self, labels: Optional[Dict[str, str]] = None) -> float:
        """Get the counter value"""
        key = MetricLabels(labels or {}).key()
        return self._values.get(key, 0)

    def reset(self):
        """Reset the counter"""
        with self._lock:
            self._values.clear()


class Gauge:
    """Gauge metric - can go up or down"""

    def __init__(self, name: str, description: str = "", labels: List[str] = None):
        self.name = name
        self.description = description
        self.label_names = labels or []
        self._values: Dict[str, float] = {}
        self._lock = threading.Lock()

    def set(self, value: float, labels: Optional[Dict[str, str]] = None):
        """Set the gauge value"""
        key = MetricLabels(labels or {}).key()
        with self._lock:
            self._values[key] = value

    def inc(self, value: float = 1, labels: Optional[Dict[str, str]] = None):
        """Increment the gauge"""
        key = MetricLabels(labels or {}).key()
        with self._lock:
            self._values[key] = self._values.get(key, 0) + value

    def dec(self, value: float = 1, labels: Optional[Dict[str, str]] = None):
        """Decrement the gauge"""
        self.inc(-value, labels)

    def get(self, labels: Optional[Dict[str, str]] = None) -> float:
        """Get the gauge value"""
        key = MetricLabels(labels or {}).key()
        return self._values.get(key, 0)


class Histogram:
    """Histogram metric - distribution of values"""

    DEFAULT_BUCKETS = [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10]

    def __init__(
        self,
        name: str,
        description: str = "",
        labels: List[str] = None,
        buckets: List[float] = None,
    ):
        self.name = name
        self.description = description
        self.label_names = labels or []
        self.buckets = sorted(buckets or self.DEFAULT_BUCKETS)
        self._counts: Dict[str, Dict[float, int]] = {}
        self._sums: Dict[str, float] = {}
        self._totals: Dict[str, int] = {}
        self._lock = threading.Lock()

    def observe(self, value: float, labels: Optional[Dict[str, str]] = None):
        """Observe a value"""
        key = MetricLabels(labels or {}).key()
        with self._lock:
            if key not in self._counts:
                self._counts[key] = {b: 0 for b in self.buckets + [float('inf')]}
                self._sums[key] = 0
                self._totals[key] = 0

            self._sums[key] += value
            self._totals[key] += 1

            for bucket in self.buckets + [float('inf')]:
                if value <= bucket:
                    self._counts[key][bucket] += 1

    def get_buckets(self, labels: Optional[Dict[str, str]] = None) -> Dict[float, int]:
        """Get bucket counts"""
        key = MetricLabels(labels or {}).key()
        return self._counts.get(key, {})

    def get_sum(self, labels: Optional[Dict[str, str]] = None) -> float:
        """Get sum of observed values"""
        key = MetricLabels(labels or {}).key()
        return self._sums.get(key, 0)

    def get_count(self, labels: Optional[Dict[str, str]] = None) -> int:
        """Get count of observations"""
        key = MetricLabels(labels or {}).key()
        return self._totals.get(key, 0)

    @contextmanager
    def time(self, labels: Optional[Dict[str, str]] = None):
        """Context manager to measure duration"""
        start = time.time()
        try:
            yield
        finally:
            self.observe(time.time() - start, labels)


# ============== Metrics Registry ==============

class MetricsRegistry:
    """
    Global registry for all metrics.
    Singleton pattern for application-wide metrics.
    """

    _instance: Optional["MetricsRegistry"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._metrics: Dict[str, Union[Counter, Gauge, Histogram]] = {}
        return cls._instance

    def counter(
        self,
        name: str,
        description: str = "",
        labels: List[str] = None,
    ) -> Counter:
        """Get or create a counter"""
        if name not in self._metrics:
            self._metrics[name] = Counter(name, description, labels)
        return self._metrics[name]

    def gauge(
        self,
        name: str,
        description: str = "",
        labels: List[str] = None,
    ) -> Gauge:
        """Get or create a gauge"""
        if name not in self._metrics:
            self._metrics[name] = Gauge(name, description, labels)
        return self._metrics[name]

    def histogram(
        self,
        name: str,
        description: str = "",
        labels: List[str] = None,
        buckets: List[float] = None,
    ) -> Histogram:
        """Get or create a histogram"""
        if name not in self._metrics:
            self._metrics[name] = Histogram(name, description, labels, buckets)
        return self._metrics[name]

    def get_all_metrics(self) -> Dict[str, Any]:
        """Get all metrics as a dictionary"""
        result = {}
        for name, metric in self._metrics.items():
            if isinstance(metric, Counter):
                result[name] = {
                    "type": "counter",
                    "values": metric._values,
                }
            elif isinstance(metric, Gauge):
                result[name] = {
                    "type": "gauge",
                    "values": metric._values,
                }
            elif isinstance(metric, Histogram):
                result[name] = {
                    "type": "histogram",
                    "buckets": metric._counts,
                    "sums": metric._sums,
                    "totals": metric._totals,
                }
        return result

    def to_prometheus(self) -> str:
        """Export metrics in Prometheus format"""
        lines = []
        for name, metric in self._metrics.items():
            if isinstance(metric, Counter):
                lines.append(f"# HELP {name} {metric.description}")
                lines.append(f"# TYPE {name} counter")
                for labels_key, value in metric._values.items():
                    labels_str = f"{{{labels_key}}}" if labels_key else ""
                    lines.append(f"{name}{labels_str} {value}")

            elif isinstance(metric, Gauge):
                lines.append(f"# HELP {name} {metric.description}")
                lines.append(f"# TYPE {name} gauge")
                for labels_key, value in metric._values.items():
                    labels_str = f"{{{labels_key}}}" if labels_key else ""
                    lines.append(f"{name}{labels_str} {value}")

            elif isinstance(metric, Histogram):
                lines.append(f"# HELP {name} {metric.description}")
                lines.append(f"# TYPE {name} histogram")
                for labels_key in metric._counts:
                    labels_str = f",{labels_key}" if labels_key else ""
                    for bucket, count in metric._counts[labels_key].items():
                        le = "+Inf" if bucket == float('inf') else bucket
                        lines.append(f'{name}_bucket{{le="{le}"{labels_str}}} {count}')
                    lines.append(f"{name}_sum{{{labels_key}}} {metric._sums.get(labels_key, 0)}")
                    lines.append(f"{name}_count{{{labels_key}}} {metric._totals.get(labels_key, 0)}")

        return "\n".join(lines)


# Global registry
metrics = MetricsRegistry()


# ============== Tracing ==============

@dataclass
class SpanContext:
    """Context for distributed tracing"""
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    span_id: str = field(default_factory=lambda: str(uuid.uuid4())[:16])
    parent_span_id: Optional[str] = None
    baggage: Dict[str, str] = field(default_factory=dict)


@dataclass
class Span:
    """A single span in a trace"""
    name: str
    context: SpanContext
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    status: str = "ok"  # ok, error
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def duration_ms(self) -> float:
        """Get duration in milliseconds"""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds() * 1000
        return 0

    def set_attribute(self, key: str, value: Any):
        """Set an attribute on the span"""
        self.attributes[key] = value

    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None):
        """Add an event to the span"""
        self.events.append({
            "name": name,
            "timestamp": datetime.utcnow().isoformat(),
            "attributes": attributes or {},
        })

    def set_error(self, error: Exception):
        """Mark span as error"""
        self.status = "error"
        self.attributes["error.type"] = type(error).__name__
        self.attributes["error.message"] = str(error)

    def end(self):
        """End the span"""
        self.end_time = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for export"""
        return {
            "name": self.name,
            "trace_id": self.context.trace_id,
            "span_id": self.context.span_id,
            "parent_span_id": self.context.parent_span_id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "attributes": self.attributes,
            "events": self.events,
        }


class Tracer:
    """
    Distributed tracing implementation.
    Thread-local storage for current span context.
    """

    _instance: Optional["Tracer"] = None
    _local = threading.local()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._spans: List[Span] = []
            cls._instance._exporters: List[Callable[[Span], None]] = []
        return cls._instance

    def _get_current_context(self) -> Optional[SpanContext]:
        """Get current span context from thread-local storage"""
        return getattr(self._local, 'context', None)

    def _set_current_context(self, context: Optional[SpanContext]):
        """Set current span context in thread-local storage"""
        self._local.context = context

    @contextmanager
    def start_span(
        self,
        name: str,
        attributes: Optional[Dict[str, Any]] = None,
    ):
        """Start a new span as context manager"""
        parent_context = self._get_current_context()

        context = SpanContext(
            trace_id=parent_context.trace_id if parent_context else str(uuid.uuid4()),
            parent_span_id=parent_context.span_id if parent_context else None,
        )

        span = Span(
            name=name,
            context=context,
            attributes=attributes or {},
        )

        # Set as current
        self._set_current_context(context)

        try:
            yield span
        except Exception as e:
            span.set_error(e)
            raise
        finally:
            span.end()
            self._spans.append(span)

            # Export
            for exporter in self._exporters:
                try:
                    exporter(span)
                except Exception as e:
                    logger.warning(f"Span export failed: {e}")

            # Restore parent context
            if parent_context:
                self._set_current_context(parent_context)
            else:
                self._set_current_context(None)

    @asynccontextmanager
    async def start_async_span(
        self,
        name: str,
        attributes: Optional[Dict[str, Any]] = None,
    ):
        """Start a new span for async operations"""
        with self.start_span(name, attributes) as span:
            yield span

    def add_exporter(self, exporter: Callable[[Span], None]):
        """Add a span exporter"""
        self._exporters.append(exporter)

    def get_recent_spans(self, limit: int = 100) -> List[Span]:
        """Get recent spans"""
        return self._spans[-limit:]

    def get_trace(self, trace_id: str) -> List[Span]:
        """Get all spans for a trace"""
        return [s for s in self._spans if s.context.trace_id == trace_id]


# Global tracer
tracer = Tracer()


# ============== Structured Logging ==============

@dataclass
class LogContext:
    """Context for structured logging"""
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    user_id: Optional[str] = None
    task_id: Optional[str] = None
    span_id: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)


class StructuredLogger:
    """
    Structured logging with JSON output and context.
    """

    _context = threading.local()

    def __init__(self, name: str):
        self.name = name
        self._logger = logging.getLogger(name)

    @classmethod
    def get_context(cls) -> Optional[LogContext]:
        """Get current log context"""
        return getattr(cls._context, 'log_context', None)

    @classmethod
    def set_context(cls, context: LogContext):
        """Set current log context"""
        cls._context.log_context = context

    @classmethod
    @contextmanager
    def with_context(cls, **kwargs):
        """Context manager for temporary log context"""
        old_context = cls.get_context()
        new_context = LogContext(**kwargs)
        cls.set_context(new_context)
        try:
            yield new_context
        finally:
            if old_context:
                cls.set_context(old_context)
            else:
                cls._context.log_context = None

    def _format_message(
        self,
        level: str,
        message: str,
        extra: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Format message as JSON"""
        context = self.get_context()

        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": level,
            "logger": self.name,
            "message": message,
        }

        if context:
            log_entry["correlation_id"] = context.correlation_id
            if context.user_id:
                log_entry["user_id"] = context.user_id
            if context.task_id:
                log_entry["task_id"] = context.task_id
            if context.span_id:
                log_entry["span_id"] = context.span_id
            if context.extra:
                log_entry.update(context.extra)

        if extra:
            log_entry.update(extra)

        return json.dumps(log_entry)

    def debug(self, message: str, **kwargs):
        """Log debug message"""
        self._logger.debug(self._format_message("DEBUG", message, kwargs))

    def info(self, message: str, **kwargs):
        """Log info message"""
        self._logger.info(self._format_message("INFO", message, kwargs))

    def warning(self, message: str, **kwargs):
        """Log warning message"""
        self._logger.warning(self._format_message("WARNING", message, kwargs))

    def error(self, message: str, **kwargs):
        """Log error message"""
        self._logger.error(self._format_message("ERROR", message, kwargs))


# ============== Health Checks ==============

class HealthStatus(str, Enum):
    """Health check status"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class HealthCheckResult:
    """Result of a health check"""
    name: str
    status: HealthStatus
    message: str = ""
    latency_ms: float = 0
    details: Dict[str, Any] = field(default_factory=dict)


class HealthChecker:
    """
    Health check system for service dependencies.
    """

    def __init__(self):
        self._checks: Dict[str, Callable[[], HealthCheckResult]] = {}
        self._async_checks: Dict[str, Callable[[], Any]] = {}  # Coroutine functions

    def register_check(
        self,
        name: str,
        check_fn: Callable[[], HealthCheckResult],
    ):
        """Register a synchronous health check"""
        self._checks[name] = check_fn

    def register_async_check(
        self,
        name: str,
        check_fn: Callable[[], Any],  # Async coroutine function
    ):
        """Register an async health check"""
        self._async_checks[name] = check_fn

    def check(self, name: str) -> HealthCheckResult:
        """Run a single health check"""
        if name not in self._checks:
            return HealthCheckResult(
                name=name,
                status=HealthStatus.UNHEALTHY,
                message=f"Unknown check: {name}",
            )

        start = time.time()
        try:
            result = self._checks[name]()
            result.latency_ms = (time.time() - start) * 1000
            return result
        except Exception as e:
            return HealthCheckResult(
                name=name,
                status=HealthStatus.UNHEALTHY,
                message=str(e),
                latency_ms=(time.time() - start) * 1000,
            )

    async def check_async(self, name: str) -> HealthCheckResult:
        """Run a single async health check"""
        if name in self._async_checks:
            start = time.time()
            try:
                result = await self._async_checks[name]()
                result.latency_ms = (time.time() - start) * 1000
                return result
            except Exception as e:
                return HealthCheckResult(
                    name=name,
                    status=HealthStatus.UNHEALTHY,
                    message=str(e),
                    latency_ms=(time.time() - start) * 1000,
                )
        elif name in self._checks:
            return self.check(name)
        else:
            return HealthCheckResult(
                name=name,
                status=HealthStatus.UNHEALTHY,
                message=f"Unknown check: {name}",
            )

    def check_all(self) -> Dict[str, HealthCheckResult]:
        """Run all synchronous health checks"""
        return {name: self.check(name) for name in self._checks}

    async def check_all_async(self) -> Dict[str, HealthCheckResult]:
        """Run all health checks (sync and async)"""
        results = {}

        # Run sync checks
        for name in self._checks:
            results[name] = self.check(name)

        # Run async checks
        for name in self._async_checks:
            results[name] = await self.check_async(name)

        return results

    def get_overall_status(self) -> HealthStatus:
        """Get overall health status"""
        results = self.check_all()

        if all(r.status == HealthStatus.HEALTHY for r in results.values()):
            return HealthStatus.HEALTHY
        elif any(r.status == HealthStatus.UNHEALTHY for r in results.values()):
            return HealthStatus.UNHEALTHY
        else:
            return HealthStatus.DEGRADED


# Global health checker
health_checker = HealthChecker()


# ============== Pre-defined Metrics ==============

# LLM metrics
llm_requests_total = metrics.counter(
    "unicorn_llm_requests_total",
    "Total LLM requests",
    ["model", "status"],
)

llm_request_duration = metrics.histogram(
    "unicorn_llm_request_duration_seconds",
    "LLM request duration",
    ["model"],
    buckets=[0.1, 0.5, 1, 2, 5, 10, 30, 60],
)

llm_tokens_total = metrics.counter(
    "unicorn_llm_tokens_total",
    "Total LLM tokens used",
    ["model", "type"],
)

# Workflow metrics
workflow_executions_total = metrics.counter(
    "unicorn_workflow_executions_total",
    "Total workflow executions",
    ["status"],
)

workflow_duration = metrics.histogram(
    "unicorn_workflow_duration_seconds",
    "Workflow execution duration",
    ["workflow_name"],
)

workflow_steps_total = metrics.counter(
    "unicorn_workflow_steps_total",
    "Total workflow steps executed",
    ["tool", "status"],
)

# Agent metrics
agent_tasks_total = metrics.counter(
    "unicorn_agent_tasks_total",
    "Total agent tasks",
    ["agent", "status"],
)

active_agents = metrics.gauge(
    "unicorn_active_agents",
    "Currently active agents",
)

# Tool metrics
tool_executions_total = metrics.counter(
    "unicorn_tool_executions_total",
    "Total tool executions",
    ["tool", "status"],
)

tool_execution_duration = metrics.histogram(
    "unicorn_tool_execution_duration_seconds",
    "Tool execution duration",
    ["tool"],
)


# ============== Decorators ==============

def trace(name: Optional[str] = None):
    """Decorator to trace function execution"""
    def decorator(func):
        span_name = name or func.__name__

        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                async with tracer.start_async_span(span_name) as span:
                    span.set_attribute("function", func.__name__)
                    return await func(*args, **kwargs)
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                with tracer.start_span(span_name) as span:
                    span.set_attribute("function", func.__name__)
                    return func(*args, **kwargs)
            return sync_wrapper

    return decorator


def timed(histogram: Histogram, labels: Optional[Dict[str, str]] = None):
    """Decorator to measure function execution time"""
    def decorator(func):
        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                start = time.time()
                try:
                    return await func(*args, **kwargs)
                finally:
                    histogram.observe(time.time() - start, labels)
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                start = time.time()
                try:
                    return func(*args, **kwargs)
                finally:
                    histogram.observe(time.time() - start, labels)
            return sync_wrapper
    return decorator


def counted(counter: Counter, labels: Optional[Dict[str, str]] = None):
    """Decorator to count function calls"""
    def decorator(func):
        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                counter.inc(1, labels)
                return await func(*args, **kwargs)
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                counter.inc(1, labels)
                return func(*args, **kwargs)
            return sync_wrapper
    return decorator
