"""
Tests for Observability Layer (app/engine/observability.py)

Tests:
- Metrics (Counter, Gauge, Histogram)
- Metrics Registry and Prometheus export
- Distributed Tracing (Span, Tracer)
- Structured Logging
- Health Checks
- Decorators (@trace, @timed, @counted)
"""

import pytest
import asyncio
import time
import threading
from datetime import datetime

from app.engine.observability import (
    # Metrics
    MetricType,
    MetricLabels,
    MetricValue,
    Counter,
    Gauge,
    Histogram,
    MetricsRegistry,
    # Tracing
    SpanContext,
    Span,
    Tracer,
    # Logging
    LogContext,
    StructuredLogger,
    # Health
    HealthStatus,
    HealthCheckResult,
    HealthChecker,
    # Decorators
    trace,
    timed,
    counted,
    # Pre-defined metrics
    metrics,
    tracer,
    health_checker,
)


# ============== Counter Tests ==============

class TestCounter:
    """Test counter metric"""

    def test_counter_creation(self):
        """Should create counter with name"""
        counter = Counter("test_counter", "Test description")

        assert counter.name == "test_counter"
        assert counter.description == "Test description"
        assert counter.get() == 0

    def test_counter_increment(self):
        """Should increment counter"""
        counter = Counter("test")

        counter.inc()
        assert counter.get() == 1

        counter.inc(5)
        assert counter.get() == 6

    def test_counter_with_labels(self):
        """Should track separate values for different labels"""
        counter = Counter("requests", "Request count", labels=["method", "status"])

        counter.inc(1, {"method": "GET", "status": "200"})
        counter.inc(1, {"method": "POST", "status": "200"})
        counter.inc(1, {"method": "GET", "status": "200"})
        counter.inc(1, {"method": "GET", "status": "500"})

        assert counter.get({"method": "GET", "status": "200"}) == 2
        assert counter.get({"method": "POST", "status": "200"}) == 1
        assert counter.get({"method": "GET", "status": "500"}) == 1

    def test_counter_reset(self):
        """Should reset counter to zero"""
        counter = Counter("test")

        counter.inc(10)
        assert counter.get() == 10

        counter.reset()
        assert counter.get() == 0

    def test_counter_thread_safety(self):
        """Should be thread-safe"""
        counter = Counter("concurrent")
        threads = []

        def increment():
            for _ in range(1000):
                counter.inc()

        for _ in range(10):
            t = threading.Thread(target=increment)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert counter.get() == 10000


# ============== Gauge Tests ==============

class TestGauge:
    """Test gauge metric"""

    def test_gauge_creation(self):
        """Should create gauge with name"""
        gauge = Gauge("test_gauge", "Test gauge")

        assert gauge.name == "test_gauge"
        assert gauge.get() == 0

    def test_gauge_set(self):
        """Should set gauge value"""
        gauge = Gauge("test")

        gauge.set(42)
        assert gauge.get() == 42

        gauge.set(10)
        assert gauge.get() == 10

    def test_gauge_increment_decrement(self):
        """Should increment and decrement gauge"""
        gauge = Gauge("test")

        gauge.set(10)
        gauge.inc(5)
        assert gauge.get() == 15

        gauge.dec(3)
        assert gauge.get() == 12

    def test_gauge_with_labels(self):
        """Should track separate values for labels"""
        gauge = Gauge("active_connections", labels=["server"])

        gauge.set(10, {"server": "server1"})
        gauge.set(20, {"server": "server2"})

        assert gauge.get({"server": "server1"}) == 10
        assert gauge.get({"server": "server2"}) == 20


# ============== Histogram Tests ==============

class TestHistogram:
    """Test histogram metric"""

    def test_histogram_creation(self):
        """Should create histogram with buckets"""
        histogram = Histogram(
            "response_time",
            "Response time distribution",
            buckets=[0.1, 0.5, 1.0, 5.0]
        )

        assert histogram.name == "response_time"
        assert 0.1 in histogram.buckets
        assert 5.0 in histogram.buckets

    def test_histogram_observe(self):
        """Should observe values into buckets"""
        histogram = Histogram("test", buckets=[1, 5, 10])

        histogram.observe(0.5)  # Goes into bucket 1
        histogram.observe(3)    # Goes into bucket 5
        histogram.observe(7)    # Goes into bucket 10
        histogram.observe(15)   # Goes into +Inf

        buckets = histogram.get_buckets()
        assert buckets.get(1, 0) >= 1
        assert buckets.get(5, 0) >= 2
        assert buckets.get(10, 0) >= 3

    def test_histogram_sum_and_count(self):
        """Should track sum and count"""
        histogram = Histogram("test")

        histogram.observe(1)
        histogram.observe(2)
        histogram.observe(3)

        assert histogram.get_sum() == 6
        assert histogram.get_count() == 3

    def test_histogram_time_context_manager(self):
        """Should measure time with context manager"""
        histogram = Histogram("duration")

        with histogram.time():
            time.sleep(0.05)

        assert histogram.get_count() == 1
        assert histogram.get_sum() >= 0.05

    def test_histogram_with_labels(self):
        """Should track separate distributions for labels"""
        histogram = Histogram("api_latency", labels=["endpoint"])

        histogram.observe(0.1, {"endpoint": "/users"})
        histogram.observe(0.2, {"endpoint": "/users"})
        histogram.observe(0.5, {"endpoint": "/orders"})

        assert histogram.get_count({"endpoint": "/users"}) == 2
        assert histogram.get_count({"endpoint": "/orders"}) == 1


# ============== Metrics Registry Tests ==============

class TestMetricsRegistry:
    """Test metrics registry"""

    def test_registry_counter(self, metrics_registry):
        """Should create and retrieve counter"""
        counter = metrics_registry.counter("test_counter", "Test")

        assert counter is not None
        assert counter.name == "test_counter"

        # Same name should return same counter
        same_counter = metrics_registry.counter("test_counter")
        assert same_counter is counter

    def test_registry_gauge(self, metrics_registry):
        """Should create and retrieve gauge"""
        gauge = metrics_registry.gauge("test_gauge", "Test")

        assert gauge is not None
        assert gauge.name == "test_gauge"

    def test_registry_histogram(self, metrics_registry):
        """Should create and retrieve histogram"""
        histogram = metrics_registry.histogram(
            "test_histogram",
            "Test",
            buckets=[1, 5, 10]
        )

        assert histogram is not None
        assert histogram.name == "test_histogram"

    def test_registry_get_all_metrics(self, metrics_registry):
        """Should get all registered metrics"""
        metrics_registry.counter("c1")
        metrics_registry.gauge("g1")
        metrics_registry.histogram("h1")

        all_metrics = metrics_registry.get_all_metrics()

        assert "c1" in all_metrics
        assert "g1" in all_metrics
        assert "h1" in all_metrics
        assert all_metrics["c1"]["type"] == "counter"
        assert all_metrics["g1"]["type"] == "gauge"
        assert all_metrics["h1"]["type"] == "histogram"

    def test_registry_prometheus_export(self, metrics_registry):
        """Should export metrics in Prometheus format"""
        counter = metrics_registry.counter("http_requests_total", "Total HTTP requests")
        counter.inc(10)

        gauge = metrics_registry.gauge("active_sessions", "Active sessions")
        gauge.set(5)

        prometheus_output = metrics_registry.to_prometheus()

        assert "http_requests_total" in prometheus_output
        assert "active_sessions" in prometheus_output
        assert "# TYPE" in prometheus_output
        assert "# HELP" in prometheus_output


# ============== Span Tests ==============

class TestSpan:
    """Test tracing span"""

    def test_span_creation(self):
        """Should create span with context"""
        span = Span(
            name="test_operation",
            context=SpanContext()
        )

        assert span.name == "test_operation"
        assert span.context.trace_id is not None
        assert span.context.span_id is not None
        assert span.status == "ok"

    def test_span_attributes(self):
        """Should set and track attributes"""
        span = Span(name="test", context=SpanContext())

        span.set_attribute("user_id", "123")
        span.set_attribute("request_size", 1024)

        assert span.attributes["user_id"] == "123"
        assert span.attributes["request_size"] == 1024

    def test_span_events(self):
        """Should add events to span"""
        span = Span(name="test", context=SpanContext())

        span.add_event("cache_miss", {"key": "user:123"})
        span.add_event("retry", {"attempt": 2})

        assert len(span.events) == 2
        assert span.events[0]["name"] == "cache_miss"
        assert span.events[1]["name"] == "retry"

    def test_span_error(self):
        """Should mark span as error"""
        span = Span(name="test", context=SpanContext())

        error = ValueError("Something went wrong")
        span.set_error(error)

        assert span.status == "error"
        assert span.attributes["error.type"] == "ValueError"
        assert "went wrong" in span.attributes["error.message"]

    def test_span_duration(self):
        """Should calculate duration"""
        span = Span(name="test", context=SpanContext())
        time.sleep(0.05)
        span.end()

        assert span.duration_ms >= 50

    def test_span_to_dict(self):
        """Should convert to dictionary"""
        span = Span(
            name="test",
            context=SpanContext(trace_id="trace123", span_id="span456")
        )
        span.set_attribute("key", "value")
        span.end()

        data = span.to_dict()

        assert data["name"] == "test"
        assert data["trace_id"] == "trace123"
        assert data["span_id"] == "span456"
        assert "key" in data["attributes"]
        assert data["end_time"] is not None


# ============== Tracer Tests ==============

class TestTracer:
    """Test distributed tracer"""

    def test_start_span(self, tracer):
        """Should create and manage spans"""
        with tracer.start_span("test_operation") as span:
            span.set_attribute("test", True)
            assert span.name == "test_operation"

        # Span should be ended
        recent_spans = tracer.get_recent_spans()
        assert len(recent_spans) >= 1

    def test_nested_spans(self, tracer):
        """Should create parent-child relationships"""
        with tracer.start_span("parent") as parent:
            with tracer.start_span("child") as child:
                assert child.context.parent_span_id == parent.context.span_id
                assert child.context.trace_id == parent.context.trace_id

    def test_span_error_handling(self, tracer):
        """Should handle errors in span"""
        with pytest.raises(ValueError):
            with tracer.start_span("error_span") as span:
                raise ValueError("Test error")

        recent = tracer.get_recent_spans()
        error_span = recent[-1]
        assert error_span.status == "error"
        assert "ValueError" in error_span.attributes.get("error.type", "")

    def test_span_exporter(self, tracer):
        """Should call exporters on span end"""
        exported_spans = []

        def exporter(span):
            exported_spans.append(span)

        tracer.add_exporter(exporter)

        with tracer.start_span("exported_span"):
            pass

        assert len(exported_spans) >= 1

    def test_get_trace(self, tracer):
        """Should retrieve all spans for a trace"""
        # Clear previous
        tracer._spans.clear()

        with tracer.start_span("root") as root:
            trace_id = root.context.trace_id
            with tracer.start_span("child1"):
                pass
            with tracer.start_span("child2"):
                pass

        trace_spans = tracer.get_trace(trace_id)
        assert len(trace_spans) == 3

    @pytest.mark.asyncio
    async def test_async_span(self, tracer):
        """Should work with async operations"""
        async with tracer.start_async_span("async_operation") as span:
            await asyncio.sleep(0.01)
            span.set_attribute("async", True)

        recent = tracer.get_recent_spans()
        assert any(s.name == "async_operation" for s in recent)


# ============== Structured Logger Tests ==============

class TestStructuredLogger:
    """Test structured logging"""

    def test_logger_creation(self):
        """Should create logger with name"""
        logger = StructuredLogger("test.module")

        assert logger.name == "test.module"

    def test_log_context(self):
        """Should use log context"""
        with StructuredLogger.with_context(
            correlation_id="corr123",
            user_id="user456"
        ) as ctx:
            assert ctx.correlation_id == "corr123"
            assert ctx.user_id == "user456"

            # Context should be available
            current = StructuredLogger.get_context()
            assert current.correlation_id == "corr123"

    def test_format_message(self):
        """Should format message as JSON"""
        logger = StructuredLogger("test")

        with StructuredLogger.with_context(
            correlation_id="test123",
            user_id="user1"
        ):
            message = logger._format_message("INFO", "Test message", {"extra": "data"})

        import json
        parsed = json.loads(message)

        assert parsed["level"] == "INFO"
        assert parsed["message"] == "Test message"
        assert parsed["correlation_id"] == "test123"
        assert parsed["extra"] == "data"


# ============== Health Check Tests ==============

class TestHealthChecker:
    """Test health check system"""

    def test_register_check(self, health_checker):
        """Should register health check"""
        def my_check():
            return HealthCheckResult(
                name="database",
                status=HealthStatus.HEALTHY,
                message="Connected"
            )

        health_checker.register_check("database", my_check)

        result = health_checker.check("database")
        assert result.status == HealthStatus.HEALTHY
        assert result.name == "database"

    def test_check_with_latency(self, health_checker):
        """Should measure check latency"""
        def slow_check():
            time.sleep(0.05)
            return HealthCheckResult(
                name="slow",
                status=HealthStatus.HEALTHY
            )

        health_checker.register_check("slow", slow_check)

        result = health_checker.check("slow")
        assert result.latency_ms >= 50

    def test_check_error_handling(self, health_checker):
        """Should handle check errors gracefully"""
        def failing_check():
            raise Exception("Database connection failed")

        health_checker.register_check("failing", failing_check)

        result = health_checker.check("failing")
        assert result.status == HealthStatus.UNHEALTHY
        assert "failed" in result.message

    def test_unknown_check(self, health_checker):
        """Should return unhealthy for unknown check"""
        result = health_checker.check("nonexistent")

        assert result.status == HealthStatus.UNHEALTHY
        assert "Unknown" in result.message

    def test_check_all(self, health_checker):
        """Should run all registered checks"""
        health_checker.register_check("check1", lambda: HealthCheckResult(
            name="check1", status=HealthStatus.HEALTHY
        ))
        health_checker.register_check("check2", lambda: HealthCheckResult(
            name="check2", status=HealthStatus.HEALTHY
        ))

        results = health_checker.check_all()

        assert "check1" in results
        assert "check2" in results

    def test_overall_status_healthy(self, health_checker):
        """Should return HEALTHY when all checks pass"""
        health_checker.register_check("a", lambda: HealthCheckResult(
            name="a", status=HealthStatus.HEALTHY
        ))
        health_checker.register_check("b", lambda: HealthCheckResult(
            name="b", status=HealthStatus.HEALTHY
        ))

        status = health_checker.get_overall_status()
        assert status == HealthStatus.HEALTHY

    def test_overall_status_unhealthy(self, health_checker):
        """Should return UNHEALTHY if any check fails"""
        health_checker.register_check("good", lambda: HealthCheckResult(
            name="good", status=HealthStatus.HEALTHY
        ))
        health_checker.register_check("bad", lambda: HealthCheckResult(
            name="bad", status=HealthStatus.UNHEALTHY
        ))

        status = health_checker.get_overall_status()
        assert status == HealthStatus.UNHEALTHY

    def test_overall_status_degraded(self, health_checker):
        """Should return DEGRADED if any check is degraded"""
        health_checker.register_check("good", lambda: HealthCheckResult(
            name="good", status=HealthStatus.HEALTHY
        ))
        health_checker.register_check("degraded", lambda: HealthCheckResult(
            name="degraded", status=HealthStatus.DEGRADED
        ))

        status = health_checker.get_overall_status()
        assert status == HealthStatus.DEGRADED

    @pytest.mark.asyncio
    async def test_async_health_check(self, health_checker):
        """Should handle async health checks"""
        async def async_check():
            await asyncio.sleep(0.01)
            return HealthCheckResult(
                name="async",
                status=HealthStatus.HEALTHY
            )

        health_checker.register_async_check("async", async_check)

        result = await health_checker.check_async("async")
        assert result.status == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_check_all_async(self, health_checker):
        """Should run all sync and async checks"""
        health_checker.register_check("sync", lambda: HealthCheckResult(
            name="sync", status=HealthStatus.HEALTHY
        ))

        async def async_check():
            return HealthCheckResult(name="async", status=HealthStatus.HEALTHY)

        health_checker.register_async_check("async", async_check)

        results = await health_checker.check_all_async()

        assert "sync" in results
        assert "async" in results


# ============== Decorator Tests ==============

class TestDecorators:
    """Test observability decorators"""

    @pytest.mark.asyncio
    async def test_trace_decorator(self):
        """@trace should create span for function"""
        # Use the global tracer since @trace uses it
        from app.engine.observability import tracer as global_tracer
        global_tracer._spans.clear()

        @trace("custom_operation")
        async def my_async_func():
            await asyncio.sleep(0.01)
            return "result"

        result = await my_async_func()

        assert result == "result"
        # Should have created a span
        recent = global_tracer.get_recent_spans()
        assert any(s.name == "custom_operation" for s in recent)

    def test_trace_decorator_sync(self):
        """@trace should work with sync functions"""
        # Use the global tracer since @trace uses it
        from app.engine.observability import tracer as global_tracer
        global_tracer._spans.clear()

        @trace("sync_operation")
        def my_sync_func():
            return "sync_result"

        result = my_sync_func()

        assert result == "sync_result"
        recent = global_tracer.get_recent_spans()
        assert any(s.name == "sync_operation" for s in recent)

    @pytest.mark.asyncio
    async def test_timed_decorator(self):
        """@timed should measure execution time"""
        histogram = Histogram("test_duration")

        @timed(histogram)
        async def slow_func():
            await asyncio.sleep(0.05)
            return "done"

        result = await slow_func()

        assert result == "done"
        assert histogram.get_count() == 1
        assert histogram.get_sum() >= 0.05

    def test_timed_decorator_sync(self):
        """@timed should work with sync functions"""
        histogram = Histogram("sync_duration")

        @timed(histogram)
        def slow_sync():
            time.sleep(0.05)
            return "done"

        result = slow_sync()

        assert result == "done"
        assert histogram.get_count() == 1

    @pytest.mark.asyncio
    async def test_counted_decorator(self):
        """@counted should count function calls"""
        counter = Counter("call_count")

        @counted(counter)
        async def counted_func():
            return "result"

        await counted_func()
        await counted_func()
        await counted_func()

        assert counter.get() == 3

    def test_counted_decorator_with_labels(self):
        """@counted should support labels"""
        counter = Counter("labeled_count", labels=["type"])

        @counted(counter, labels={"type": "api"})
        def api_func():
            return "api"

        api_func()
        api_func()

        assert counter.get({"type": "api"}) == 2


# ============== Pre-defined Metrics Tests ==============

class TestPredefinedMetrics:
    """Test pre-defined metrics"""

    def test_llm_metrics_exist(self):
        """Should have LLM metrics defined"""
        from app.engine.observability import (
            llm_requests_total,
            llm_request_duration,
            llm_tokens_total,
        )

        assert llm_requests_total is not None
        assert llm_request_duration is not None
        assert llm_tokens_total is not None

    def test_workflow_metrics_exist(self):
        """Should have workflow metrics defined"""
        from app.engine.observability import (
            workflow_executions_total,
            workflow_duration,
            workflow_steps_total,
        )

        assert workflow_executions_total is not None
        assert workflow_duration is not None
        assert workflow_steps_total is not None

    def test_agent_metrics_exist(self):
        """Should have agent metrics defined"""
        from app.engine.observability import (
            agent_tasks_total,
            active_agents,
        )

        assert agent_tasks_total is not None
        assert active_agents is not None

    def test_tool_metrics_exist(self):
        """Should have tool metrics defined"""
        from app.engine.observability import (
            tool_executions_total,
            tool_execution_duration,
        )

        assert tool_executions_total is not None
        assert tool_execution_duration is not None


# ============== Integration Tests ==============

class TestObservabilityIntegration:
    """Integration tests for observability"""

    @pytest.mark.asyncio
    async def test_full_request_tracing(self, metrics_registry):
        """Should trace complete request flow"""
        # Use global tracer since @trace decorator uses it
        from app.engine.observability import tracer as global_tracer

        request_counter = metrics_registry.counter("requests")
        request_duration = metrics_registry.histogram("request_duration")

        global_tracer._spans.clear()

        @trace("handle_request")
        @timed(request_duration)
        @counted(request_counter)
        async def handle_request(data):
            with global_tracer.start_span("process") as span:
                span.set_attribute("data_size", len(str(data)))
                await asyncio.sleep(0.01)

            with global_tracer.start_span("save"):
                await asyncio.sleep(0.01)

            return {"status": "ok"}

        result = await handle_request({"key": "value"})

        assert result["status"] == "ok"
        assert request_counter.get() == 1
        assert request_duration.get_count() == 1

        # Should have multiple spans
        recent = global_tracer.get_recent_spans()
        span_names = [s.name for s in recent]
        assert "handle_request" in span_names
        assert "process" in span_names
        assert "save" in span_names

    def test_metrics_and_health_integration(self, metrics_registry, health_checker):
        """Should integrate metrics with health checks"""
        error_counter = metrics_registry.counter("errors")

        def check_error_rate():
            error_count = error_counter.get()
            if error_count > 100:
                return HealthCheckResult(
                    name="error_rate",
                    status=HealthStatus.UNHEALTHY,
                    message=f"High error rate: {error_count}"
                )
            elif error_count > 50:
                return HealthCheckResult(
                    name="error_rate",
                    status=HealthStatus.DEGRADED,
                    message=f"Elevated error rate: {error_count}"
                )
            return HealthCheckResult(
                name="error_rate",
                status=HealthStatus.HEALTHY,
                message="Error rate normal"
            )

        health_checker.register_check("error_rate", check_error_rate)

        # Low errors - healthy
        assert health_checker.check("error_rate").status == HealthStatus.HEALTHY

        # Elevated errors - degraded
        error_counter.inc(60)
        assert health_checker.check("error_rate").status == HealthStatus.DEGRADED

        # High errors - unhealthy
        error_counter.inc(50)
        assert health_checker.check("error_rate").status == HealthStatus.UNHEALTHY
