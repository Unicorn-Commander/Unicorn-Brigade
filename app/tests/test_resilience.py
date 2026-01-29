"""
Tests for Resilience Patterns (app/engine/resilience.py)

Tests:
- Circuit Breaker state transitions and behavior
- Retry with exponential backoff
- Bulkhead concurrency limiting
- Error classification
- Combined resilience policy
"""

import pytest
import asyncio
import time
from datetime import datetime, timedelta

from app.engine.resilience import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
    CircuitOpenError,
    RetryStrategy,
    RetryConfig,
    Bulkhead,
    BulkheadFullError,
    ErrorClassifier,
    ErrorCategory,
    ClassifiedError,
    ResiliencePolicy,
    CircuitBreakerRegistry,
    with_resilience,
    create_llm_policy,
    create_http_policy,
)


# ============== Circuit Breaker Tests ==============

class TestCircuitBreaker:
    """Test circuit breaker pattern"""

    @pytest.mark.asyncio
    async def test_circuit_starts_closed(self, circuit_breaker):
        """Circuit breaker should start in CLOSED state"""
        assert circuit_breaker.state == CircuitState.CLOSED
        assert circuit_breaker.metrics.total_calls == 0
        assert circuit_breaker.metrics.consecutive_failures == 0

    @pytest.mark.asyncio
    async def test_successful_calls_stay_closed(self, circuit_breaker):
        """Successful calls should keep circuit CLOSED"""
        async def success_func():
            return "success"

        for _ in range(5):
            result = await circuit_breaker.call(success_func)
            assert result == "success"

        assert circuit_breaker.state == CircuitState.CLOSED
        assert circuit_breaker.metrics.successful_calls == 5
        assert circuit_breaker.metrics.failed_calls == 0

    @pytest.mark.asyncio
    async def test_failures_open_circuit(self, circuit_breaker):
        """Consecutive failures should OPEN circuit"""
        async def failing_func():
            raise Exception("Test failure")

        # Should fail but circuit stays closed
        for i in range(circuit_breaker.config.failure_threshold):
            with pytest.raises(Exception, match="Test failure"):
                await circuit_breaker.call(failing_func)

        # After threshold failures, circuit should be OPEN
        assert circuit_breaker.state == CircuitState.OPEN
        assert circuit_breaker.metrics.consecutive_failures >= circuit_breaker.config.failure_threshold

    @pytest.mark.asyncio
    async def test_open_circuit_rejects_calls(self, circuit_breaker):
        """OPEN circuit should reject calls immediately"""
        async def failing_func():
            raise Exception("Test failure")

        # Open the circuit
        for _ in range(circuit_breaker.config.failure_threshold):
            try:
                await circuit_breaker.call(failing_func)
            except Exception:
                pass

        assert circuit_breaker.state == CircuitState.OPEN

        # Next call should be rejected
        with pytest.raises(CircuitOpenError):
            await circuit_breaker.call(failing_func)

        # Rejected calls are tracked
        assert circuit_breaker.metrics.rejected_calls >= 1

    @pytest.mark.asyncio
    async def test_open_to_half_open_after_timeout(self, circuit_breaker):
        """Circuit should transition to HALF_OPEN after timeout"""
        async def failing_func():
            raise Exception("Test failure")

        # Open the circuit
        for _ in range(circuit_breaker.config.failure_threshold):
            try:
                await circuit_breaker.call(failing_func)
            except Exception:
                pass

        assert circuit_breaker.state == CircuitState.OPEN

        # Wait for timeout
        await asyncio.sleep(circuit_breaker.config.timeout_seconds + 0.1)

        # Next call should be allowed (half-open test)
        async def success_func():
            return "recovered"

        result = await circuit_breaker.call(success_func)
        assert result == "recovered"
        # State should be HALF_OPEN or CLOSED depending on success
        assert circuit_breaker.state in [CircuitState.HALF_OPEN, CircuitState.CLOSED]

    @pytest.mark.asyncio
    async def test_half_open_to_closed_on_success(self, circuit_breaker_config):
        """HALF_OPEN should transition to CLOSED on consecutive successes"""
        breaker = CircuitBreaker("test", CircuitBreakerConfig(
            failure_threshold=2,
            success_threshold=2,
            timeout_seconds=0.1,
        ))

        async def failing_func():
            raise Exception("fail")

        async def success_func():
            return "ok"

        # Open circuit
        for _ in range(2):
            try:
                await breaker.call(failing_func)
            except Exception:
                pass

        assert breaker.state == CircuitState.OPEN

        # Wait for timeout
        await asyncio.sleep(0.15)

        # Success should transition to HALF_OPEN
        await breaker.call(success_func)

        # More successes to close
        await breaker.call(success_func)

        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_half_open_to_open_on_failure(self, circuit_breaker_config):
        """HALF_OPEN should transition back to OPEN on failure"""
        breaker = CircuitBreaker("test", CircuitBreakerConfig(
            failure_threshold=2,
            success_threshold=2,
            timeout_seconds=0.1,
        ))

        async def failing_func():
            raise Exception("fail")

        # Open circuit
        for _ in range(2):
            try:
                await breaker.call(failing_func)
            except Exception:
                pass

        # Wait for timeout to enter half-open
        await asyncio.sleep(0.15)

        # Failure in half-open should re-open
        try:
            await breaker.call(failing_func)
        except Exception:
            pass

        assert breaker.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_fallback_on_open_circuit(self, circuit_breaker):
        """Fallback should be called when circuit is OPEN"""
        async def failing_func():
            raise Exception("fail")

        async def fallback_func():
            return "fallback_result"

        # Open circuit
        for _ in range(circuit_breaker.config.failure_threshold):
            try:
                await circuit_breaker.call(failing_func)
            except Exception:
                pass

        assert circuit_breaker.state == CircuitState.OPEN

        # Call with fallback
        result = await circuit_breaker.call(failing_func, fallback=fallback_func)
        assert result == "fallback_result"

    @pytest.mark.asyncio
    async def test_excluded_exceptions(self):
        """Excluded exceptions should not affect circuit state"""
        class IgnorableError(Exception):
            pass

        breaker = CircuitBreaker("test", CircuitBreakerConfig(
            failure_threshold=2,
            excluded_exceptions=[IgnorableError],
        ))

        async def func():
            raise IgnorableError("should be ignored")

        # These should not count as failures
        for _ in range(5):
            with pytest.raises(IgnorableError):
                await breaker.call(func)

        assert breaker.state == CircuitState.CLOSED
        assert breaker.metrics.consecutive_failures == 0

    @pytest.mark.asyncio
    async def test_circuit_reset(self, circuit_breaker):
        """Reset should restore circuit to initial state"""
        async def failing_func():
            raise Exception("fail")

        # Open circuit
        for _ in range(circuit_breaker.config.failure_threshold):
            try:
                await circuit_breaker.call(failing_func)
            except Exception:
                pass

        assert circuit_breaker.state == CircuitState.OPEN

        # Reset
        circuit_breaker.reset()

        assert circuit_breaker.state == CircuitState.CLOSED
        assert circuit_breaker.metrics.total_calls == 0
        assert circuit_breaker.metrics.consecutive_failures == 0

    def test_get_metrics(self, circuit_breaker):
        """Should return correct metrics dictionary"""
        metrics = circuit_breaker.get_metrics()

        assert "name" in metrics
        assert "state" in metrics
        assert "total_calls" in metrics
        assert "successful_calls" in metrics
        assert "failed_calls" in metrics
        assert "rejected_calls" in metrics
        assert "failure_rate" in metrics

    @pytest.mark.asyncio
    async def test_state_change_callback(self):
        """State change callback should be invoked"""
        state_changes = []

        def on_state_change(old_state, new_state):
            state_changes.append((old_state, new_state))

        breaker = CircuitBreaker(
            "test",
            CircuitBreakerConfig(failure_threshold=2, timeout_seconds=0.1),
            on_state_change=on_state_change
        )

        async def failing_func():
            raise Exception("fail")

        # Open circuit
        for _ in range(2):
            try:
                await breaker.call(failing_func)
            except Exception:
                pass

        # Should have recorded state change
        assert len(state_changes) >= 1
        assert state_changes[-1][1] == CircuitState.OPEN


# ============== Retry Strategy Tests ==============

class TestRetryStrategy:
    """Test retry with backoff"""

    @pytest.mark.asyncio
    async def test_successful_call_no_retry(self, retry_strategy):
        """Successful call should not retry"""
        call_count = 0

        async def success_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await retry_strategy.execute(success_func)

        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retry_on_transient_error(self, retry_config):
        """Should retry on transient errors"""
        strategy = RetryStrategy(retry_config)
        call_count = 0

        async def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Connection timeout")
            return "success"

        result = await strategy.execute(flaky_func)

        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self, retry_config):
        """Should raise after max retries"""
        strategy = RetryStrategy(retry_config)

        async def always_fail():
            raise Exception("timeout")

        with pytest.raises(Exception, match="timeout"):
            await strategy.execute(always_fail)

    @pytest.mark.asyncio
    async def test_no_retry_on_permanent_error(self):
        """Should not retry permanent errors"""
        config = RetryConfig(max_retries=3, base_delay=0.01)
        strategy = RetryStrategy(config)
        call_count = 0

        async def permanent_fail():
            nonlocal call_count
            call_count += 1
            raise Exception("Resource not found - 404")

        with pytest.raises(Exception, match="404"):
            await strategy.execute(permanent_fail)

        # Should not retry permanent errors
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_exponential_backoff(self):
        """Delay should increase exponentially"""
        config = RetryConfig(
            max_retries=4,
            base_delay=0.1,
            exponential_base=2.0,
            jitter=False,
            max_delay=10.0
        )
        strategy = RetryStrategy(config)

        delays = []
        for attempt in range(4):
            delay = strategy.calculate_delay(attempt)
            delays.append(delay)

        # Delays should be: 0.1, 0.2, 0.4, 0.8
        assert delays[0] == pytest.approx(0.1, rel=0.01)
        assert delays[1] == pytest.approx(0.2, rel=0.01)
        assert delays[2] == pytest.approx(0.4, rel=0.01)
        assert delays[3] == pytest.approx(0.8, rel=0.01)

    @pytest.mark.asyncio
    async def test_max_delay_cap(self):
        """Delay should be capped at max_delay"""
        config = RetryConfig(
            max_retries=10,
            base_delay=1.0,
            exponential_base=2.0,
            max_delay=5.0,
            jitter=False
        )
        strategy = RetryStrategy(config)

        # After many attempts, delay should not exceed max
        delay = strategy.calculate_delay(10)
        assert delay <= 5.0

    @pytest.mark.asyncio
    async def test_retry_callback(self, retry_config):
        """On_retry callback should be called"""
        strategy = RetryStrategy(retry_config)
        retry_calls = []

        def on_retry(attempt, error, delay):
            retry_calls.append({
                "attempt": attempt,
                "error": str(error),
                "delay": delay
            })

        call_count = 0

        async def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("timeout")
            return "ok"

        await strategy.execute(flaky_func, on_retry=on_retry)

        assert len(retry_calls) == 2  # Retried twice
        assert retry_calls[0]["attempt"] == 1
        assert retry_calls[1]["attempt"] == 2

    @pytest.mark.asyncio
    async def test_retry_on_specific_exceptions(self):
        """Should only retry specified exception types"""
        class RetryableError(Exception):
            pass

        class NonRetryableError(Exception):
            pass

        config = RetryConfig(
            max_retries=3,
            base_delay=0.01,
            retry_on=[RetryableError]
        )
        strategy = RetryStrategy(config)
        call_count = 0

        async def func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RetryableError("retry me")
            return "ok"

        result = await strategy.execute(func)
        assert result == "ok"
        assert call_count == 3

        # Non-retryable should not be retried
        call_count = 0

        async def non_retryable_func():
            nonlocal call_count
            call_count += 1
            raise NonRetryableError("don't retry")

        with pytest.raises(NonRetryableError):
            await strategy.execute(non_retryable_func)

        assert call_count == 1


# ============== Bulkhead Tests ==============

class TestBulkhead:
    """Test bulkhead pattern"""

    @pytest.mark.asyncio
    async def test_allows_concurrent_up_to_limit(self, bulkhead):
        """Should allow concurrent calls up to limit"""
        active_calls = 0
        max_active = 0

        async def slow_func():
            nonlocal active_calls, max_active
            active_calls += 1
            max_active = max(max_active, active_calls)
            await asyncio.sleep(0.1)
            active_calls -= 1
            return "done"

        # Launch 3 concurrent calls (equal to limit)
        tasks = [bulkhead.call(slow_func) for _ in range(3)]
        results = await asyncio.gather(*tasks)

        assert all(r == "done" for r in results)
        assert max_active <= 3

    @pytest.mark.asyncio
    async def test_rejects_over_limit_with_short_wait(self):
        """Should reject calls over limit after short wait timeout"""
        # Use a very short wait to simulate fail-fast behavior
        bulkhead = Bulkhead("test_reject", max_concurrent=1, max_wait_seconds=0.05)

        hold_event = asyncio.Event()

        async def blocking_func():
            await hold_event.wait()
            return "done"

        # Fill up the single slot
        task1 = asyncio.create_task(bulkhead.call(blocking_func))
        await asyncio.sleep(0.01)  # Let task1 acquire the semaphore

        # Second call should fail after timeout since slot is taken
        with pytest.raises(BulkheadFullError):
            await bulkhead.call(blocking_func)

        # Cleanup
        hold_event.set()
        await task1

    @pytest.mark.asyncio
    async def test_waits_for_slot_with_wait_time(self):
        """Should wait for slot when max_wait > 0"""
        bulkhead = Bulkhead("test", max_concurrent=1, max_wait_seconds=1.0)

        async def quick_func():
            await asyncio.sleep(0.05)
            return "done"

        # First call takes the slot
        task1 = asyncio.create_task(bulkhead.call(quick_func))

        # Second call should wait and succeed
        start = time.time()
        result = await bulkhead.call(quick_func)
        elapsed = time.time() - start

        assert result == "done"
        assert elapsed >= 0.04  # Had to wait for first to complete

        await task1

    @pytest.mark.asyncio
    async def test_metrics(self, bulkhead):
        """Should track metrics correctly"""
        async def func():
            return "done"

        await bulkhead.call(func)

        metrics = bulkhead.get_metrics()
        assert metrics["name"] == "test_bulkhead"
        assert metrics["max_concurrent"] == 3
        assert metrics["active_count"] == 0  # Call completed
        assert metrics["available"] == 3


# ============== Error Classification Tests ==============

class TestErrorClassifier:
    """Test error classification"""

    def test_classify_transient_errors(self):
        """Should classify transient errors correctly"""
        classifier = ErrorClassifier()

        transient_errors = [
            Exception("Connection timeout"),
            Exception("Too many requests - 429"),
            Exception("Service temporarily unavailable"),
            Exception("502 Bad Gateway"),
        ]

        for error in transient_errors:
            result = classifier.classify(error)
            assert result.category == ErrorCategory.TRANSIENT
            assert result.is_retryable is True

    def test_classify_permanent_errors(self):
        """Should classify permanent errors correctly"""
        classifier = ErrorClassifier()

        permanent_errors = [
            Exception("Resource not found - 404"),
            Exception("Invalid input - 400 Bad Request"),
            Exception("Unauthorized - 401"),
            Exception("Forbidden - 403"),
        ]

        for error in permanent_errors:
            result = classifier.classify(error)
            assert result.category == ErrorCategory.PERMANENT
            assert result.is_retryable is False

    def test_classify_resource_errors(self):
        """Should classify resource errors correctly"""
        classifier = ErrorClassifier()

        resource_errors = [
            Exception("Out of memory"),
            Exception("Quota exceeded"),
            Exception("Disk full"),
            Exception("Resource exhausted"),
        ]

        for error in resource_errors:
            result = classifier.classify(error)
            assert result.category == ErrorCategory.RESOURCE
            assert result.is_retryable is True

    def test_classify_unknown_errors(self):
        """Unknown errors should be classified as UNKNOWN"""
        classifier = ErrorClassifier()

        result = classifier.classify(Exception("Something weird happened"))

        assert result.category == ErrorCategory.UNKNOWN
        assert result.is_retryable is True  # Conservative default


# ============== Resilience Policy Tests ==============

class TestResiliencePolicy:
    """Test combined resilience policy"""

    @pytest.mark.asyncio
    async def test_policy_with_all_patterns(self):
        """Policy should apply all patterns in order"""
        policy = ResiliencePolicy(
            name="test_policy",
            circuit_breaker=CircuitBreaker(
                "test_cb",
                CircuitBreakerConfig(failure_threshold=5, timeout_seconds=1)
            ),
            retry_strategy=RetryStrategy(
                RetryConfig(max_retries=2, base_delay=0.01)
            ),
            bulkhead=Bulkhead("test_bh", max_concurrent=10),
        )

        async def success_func():
            return "success"

        result = await policy.execute(success_func)
        assert result == "success"

    @pytest.mark.asyncio
    async def test_policy_retries_before_circuit_break(self):
        """Retries should be attempted before circuit opens"""
        policy = ResiliencePolicy(
            name="test",
            circuit_breaker=CircuitBreaker(
                "cb",
                CircuitBreakerConfig(failure_threshold=3, timeout_seconds=1)
            ),
            retry_strategy=RetryStrategy(
                RetryConfig(max_retries=2, base_delay=0.01, jitter=False)
            ),
        )

        call_count = 0

        async def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("timeout")
            return "ok"

        result = await policy.execute(flaky_func)
        assert result == "ok"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_policy_fallback(self):
        """Fallback should be used on failure"""
        async def fallback():
            return "fallback"

        policy = ResiliencePolicy(
            name="test",
            circuit_breaker=CircuitBreaker(
                "cb",
                CircuitBreakerConfig(failure_threshold=2, timeout_seconds=1)
            ),
            fallback=fallback,
        )

        async def fail():
            raise Exception("fail")

        # Open circuit
        for _ in range(2):
            try:
                await policy.execute(fail)
            except Exception:
                pass

        # Should use fallback
        result = await policy.execute(fail)
        assert result == "fallback"

    def test_policy_metrics(self):
        """Should provide combined metrics"""
        policy = ResiliencePolicy(
            name="test",
            circuit_breaker=CircuitBreaker("cb"),
            bulkhead=Bulkhead("bh", max_concurrent=10),
        )

        metrics = policy.get_metrics()
        assert metrics["policy_name"] == "test"
        assert "circuit_breaker" in metrics
        assert "bulkhead" in metrics


# ============== Registry Tests ==============

class TestCircuitBreakerRegistry:
    """Test circuit breaker registry"""

    def test_singleton(self):
        """Registry should be singleton"""
        r1 = CircuitBreakerRegistry()
        r2 = CircuitBreakerRegistry()
        assert r1 is r2

    def test_register_and_get(self):
        """Should register and retrieve breakers"""
        registry = CircuitBreakerRegistry()
        registry.reset_all()  # Clean state

        breaker = CircuitBreaker("test_breaker_reg")
        registry.register(breaker)

        retrieved = registry.get("test_breaker_reg")
        assert retrieved is breaker

    def test_get_or_create(self):
        """Should create breaker if not exists"""
        registry = CircuitBreakerRegistry()

        breaker = registry.get_or_create("new_breaker")
        assert breaker is not None
        assert breaker.name == "new_breaker"

        # Second call should return same breaker
        same = registry.get_or_create("new_breaker")
        assert same is breaker

    def test_get_all_metrics(self):
        """Should return metrics for all breakers"""
        registry = CircuitBreakerRegistry()
        registry.reset_all()

        registry.register(CircuitBreaker("breaker1"))
        registry.register(CircuitBreaker("breaker2"))

        metrics = registry.get_all_metrics()
        assert "breaker1" in metrics
        assert "breaker2" in metrics


# ============== Decorator Tests ==============

class TestResilienceDecorator:
    """Test @with_resilience decorator"""

    @pytest.mark.asyncio
    async def test_decorator_applies_retry(self):
        """Decorator should apply retry logic"""
        call_count = 0

        @with_resilience(retry_config=RetryConfig(max_retries=2, base_delay=0.01))
        async def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("timeout")
            return "ok"

        result = await flaky_func()
        assert result == "ok"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_decorator_applies_circuit_breaker(self):
        """Decorator should apply circuit breaker"""
        @with_resilience(
            circuit_breaker=CircuitBreaker(
                "decorator_test",
                CircuitBreakerConfig(failure_threshold=2, timeout_seconds=1)
            )
        )
        async def fail_func():
            raise Exception("fail")

        # Open circuit
        for _ in range(2):
            try:
                await fail_func()
            except Exception:
                pass

        # Should reject
        with pytest.raises(CircuitOpenError):
            await fail_func()


# ============== Pre-configured Policy Tests ==============

class TestPreConfiguredPolicies:
    """Test pre-configured policy factories"""

    def test_create_llm_policy(self):
        """LLM policy should have appropriate config"""
        policy = create_llm_policy("test_llm")

        assert policy.circuit_breaker is not None
        assert policy.retry_strategy is not None
        assert policy.bulkhead is not None

    def test_create_http_policy(self):
        """HTTP policy should have appropriate config"""
        policy = create_http_policy("test_http")

        assert policy.circuit_breaker is not None
        assert policy.retry_strategy is not None
        # HTTP policy doesn't include bulkhead by default
