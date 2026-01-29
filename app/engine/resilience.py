"""
Resilience Patterns for Unicorn Brigade

Implements production-grade error recovery:
- Circuit Breaker: Prevents cascade failures
- Retry with Exponential Backoff: Smart retry logic
- Bulkhead: Resource isolation
- Fallback: Graceful degradation
- Error Classification: Categorize and handle errors appropriately

Based on patterns from Netflix Hystrix, resilience4j, and Polly.
"""

import asyncio
import logging
import time
from typing import (
    Dict, Any, List, Optional, Callable, TypeVar, Generic,
    Awaitable, Union
)
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from functools import wraps
import random
import traceback

logger = logging.getLogger(__name__)

T = TypeVar('T')


# ============== Error Classification ==============

class ErrorCategory(str, Enum):
    """Categories for error classification"""
    TRANSIENT = "transient"  # Network timeouts, rate limits - retry
    PERMANENT = "permanent"  # Invalid input, not found - don't retry
    RESOURCE = "resource"  # Out of memory, quota - backoff and retry
    UPSTREAM = "upstream"  # External service failure - circuit breaker
    INTERNAL = "internal"  # Bug in code - escalate
    UNKNOWN = "unknown"  # Unclassified - conservative retry


@dataclass
class ClassifiedError:
    """Error with classification metadata"""
    original_error: Exception
    category: ErrorCategory
    is_retryable: bool
    suggested_delay: float = 0.0
    context: Dict[str, Any] = field(default_factory=dict)

    @property
    def message(self) -> str:
        return str(self.original_error)


class ErrorClassifier:
    """Classifies errors into categories for appropriate handling"""

    TRANSIENT_PATTERNS = [
        "timeout", "timed out", "connection reset", "connection refused",
        "rate limit", "too many requests", "429", "503", "502", "504",
        "temporarily unavailable", "retry later", "busy",
    ]

    PERMANENT_PATTERNS = [
        "not found", "404", "invalid", "unauthorized", "403", "401",
        "bad request", "400", "unprocessable", "422", "forbidden",
        "does not exist", "no such",
    ]

    RESOURCE_PATTERNS = [
        "out of memory", "quota exceeded", "limit exceeded", "disk full",
        "resource exhausted", "insufficient", "capacity",
    ]

    def classify(self, error: Exception) -> ClassifiedError:
        """Classify an error"""
        error_str = str(error).lower()
        error_type = type(error).__name__.lower()

        # Check transient patterns
        for pattern in self.TRANSIENT_PATTERNS:
            if pattern in error_str or pattern in error_type:
                return ClassifiedError(
                    original_error=error,
                    category=ErrorCategory.TRANSIENT,
                    is_retryable=True,
                    suggested_delay=1.0,
                )

        # Check permanent patterns
        for pattern in self.PERMANENT_PATTERNS:
            if pattern in error_str or pattern in error_type:
                return ClassifiedError(
                    original_error=error,
                    category=ErrorCategory.PERMANENT,
                    is_retryable=False,
                )

        # Check resource patterns
        for pattern in self.RESOURCE_PATTERNS:
            if pattern in error_str or pattern in error_type:
                return ClassifiedError(
                    original_error=error,
                    category=ErrorCategory.RESOURCE,
                    is_retryable=True,
                    suggested_delay=5.0,
                )

        # Check for connection/network errors (transient)
        if any(x in error_type for x in ['connection', 'network', 'http', 'socket']):
            return ClassifiedError(
                original_error=error,
                category=ErrorCategory.TRANSIENT,
                is_retryable=True,
                suggested_delay=2.0,
            )

        # Default to unknown with conservative retry
        return ClassifiedError(
            original_error=error,
            category=ErrorCategory.UNKNOWN,
            is_retryable=True,
            suggested_delay=3.0,
        )


# ============== Circuit Breaker ==============

class CircuitState(str, Enum):
    """Circuit breaker states"""
    CLOSED = "closed"  # Normal operation, requests pass through
    OPEN = "open"  # Failing, requests blocked
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker"""
    failure_threshold: int = 5  # Failures before opening
    success_threshold: int = 3  # Successes to close from half-open
    timeout_seconds: float = 30.0  # Time before half-open
    excluded_exceptions: List[type] = field(default_factory=list)

    # Advanced settings
    failure_rate_threshold: float = 0.5  # 50% failure rate
    slow_call_threshold: float = 5.0  # Seconds for slow call
    slow_call_rate_threshold: float = 0.5  # 50% slow calls


@dataclass
class CircuitMetrics:
    """Metrics for circuit breaker"""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    slow_calls: int = 0
    rejected_calls: int = 0
    last_failure_time: Optional[datetime] = None
    consecutive_failures: int = 0
    consecutive_successes: int = 0


class CircuitBreaker:
    """
    Circuit breaker pattern implementation.

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Circuit is broken, requests fail fast
    - HALF_OPEN: Testing if service recovered

    Transitions:
    - CLOSED -> OPEN: After failure_threshold failures
    - OPEN -> HALF_OPEN: After timeout_seconds
    - HALF_OPEN -> CLOSED: After success_threshold successes
    - HALF_OPEN -> OPEN: On any failure
    """

    def __init__(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None,
        on_state_change: Optional[Callable[[CircuitState, CircuitState], None]] = None,
    ):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.metrics = CircuitMetrics()
        self.opened_at: Optional[datetime] = None
        self.on_state_change = on_state_change
        self._lock = asyncio.Lock()

        logger.info(f"CircuitBreaker '{name}' initialized (threshold={self.config.failure_threshold})")

    async def call(
        self,
        func: Callable[..., Awaitable[T]],
        *args,
        fallback: Optional[Callable[..., T]] = None,
        **kwargs,
    ) -> T:
        """Execute function through circuit breaker"""

        # Check if we should allow the call
        if not await self._should_allow_call():
            self.metrics.rejected_calls += 1
            logger.warning(f"CircuitBreaker '{self.name}' rejected call (state={self.state})")

            if fallback:
                return await self._execute_fallback(fallback, *args, **kwargs)

            raise CircuitOpenError(f"Circuit '{self.name}' is open")

        # Execute the call
        start_time = time.time()
        try:
            result = await func(*args, **kwargs)
            duration = time.time() - start_time
            await self._on_success(duration)
            return result

        except Exception as e:
            # Check if this exception should be excluded
            if any(isinstance(e, exc_type) for exc_type in self.config.excluded_exceptions):
                raise

            await self._on_failure(e)

            if fallback:
                return await self._execute_fallback(fallback, *args, **kwargs)

            raise

    async def _should_allow_call(self) -> bool:
        """Check if call should be allowed based on circuit state"""
        async with self._lock:
            if self.state == CircuitState.CLOSED:
                return True

            if self.state == CircuitState.OPEN:
                # Check if timeout has passed
                if self.opened_at:
                    elapsed = (datetime.utcnow() - self.opened_at).total_seconds()
                    if elapsed >= self.config.timeout_seconds:
                        await self._transition_to(CircuitState.HALF_OPEN)
                        return True
                return False

            if self.state == CircuitState.HALF_OPEN:
                # Allow limited calls to test
                return True

            return False

    async def _on_success(self, duration: float):
        """Handle successful call"""
        async with self._lock:
            self.metrics.total_calls += 1
            self.metrics.successful_calls += 1
            self.metrics.consecutive_successes += 1
            self.metrics.consecutive_failures = 0

            # Track slow calls
            if duration >= self.config.slow_call_threshold:
                self.metrics.slow_calls += 1

            # Check state transitions
            if self.state == CircuitState.HALF_OPEN:
                if self.metrics.consecutive_successes >= self.config.success_threshold:
                    await self._transition_to(CircuitState.CLOSED)

    async def _on_failure(self, error: Exception):
        """Handle failed call"""
        async with self._lock:
            self.metrics.total_calls += 1
            self.metrics.failed_calls += 1
            self.metrics.consecutive_failures += 1
            self.metrics.consecutive_successes = 0
            self.metrics.last_failure_time = datetime.utcnow()

            logger.warning(f"CircuitBreaker '{self.name}' failure: {error}")

            # Check state transitions
            if self.state == CircuitState.CLOSED:
                if self.metrics.consecutive_failures >= self.config.failure_threshold:
                    await self._transition_to(CircuitState.OPEN)

            elif self.state == CircuitState.HALF_OPEN:
                # Any failure in half-open goes back to open
                await self._transition_to(CircuitState.OPEN)

    async def _transition_to(self, new_state: CircuitState):
        """Transition to new state"""
        old_state = self.state
        self.state = new_state

        if new_state == CircuitState.OPEN:
            self.opened_at = datetime.utcnow()
            logger.warning(f"CircuitBreaker '{self.name}': OPEN (failures={self.metrics.consecutive_failures})")
        elif new_state == CircuitState.HALF_OPEN:
            logger.info(f"CircuitBreaker '{self.name}': HALF_OPEN (testing recovery)")
        elif new_state == CircuitState.CLOSED:
            self.metrics.consecutive_failures = 0
            self.opened_at = None
            logger.info(f"CircuitBreaker '{self.name}': CLOSED (recovered)")

        if self.on_state_change:
            self.on_state_change(old_state, new_state)

    async def _execute_fallback(
        self,
        fallback: Callable[..., T],
        *args,
        **kwargs,
    ) -> T:
        """Execute fallback function"""
        try:
            if asyncio.iscoroutinefunction(fallback):
                return await fallback(*args, **kwargs)
            return fallback(*args, **kwargs)
        except Exception as e:
            logger.error(f"CircuitBreaker '{self.name}' fallback failed: {e}")
            raise

    def get_metrics(self) -> Dict[str, Any]:
        """Get circuit breaker metrics"""
        return {
            "name": self.name,
            "state": self.state.value,
            "total_calls": self.metrics.total_calls,
            "successful_calls": self.metrics.successful_calls,
            "failed_calls": self.metrics.failed_calls,
            "slow_calls": self.metrics.slow_calls,
            "rejected_calls": self.metrics.rejected_calls,
            "failure_rate": (
                self.metrics.failed_calls / self.metrics.total_calls
                if self.metrics.total_calls > 0 else 0
            ),
            "consecutive_failures": self.metrics.consecutive_failures,
        }

    def reset(self):
        """Reset circuit breaker to closed state"""
        self.state = CircuitState.CLOSED
        self.metrics = CircuitMetrics()
        self.opened_at = None
        logger.info(f"CircuitBreaker '{self.name}' reset")


class CircuitOpenError(Exception):
    """Raised when circuit is open and call is rejected"""
    pass


# ============== Retry with Backoff ==============

@dataclass
class RetryConfig:
    """Configuration for retry logic"""
    max_retries: int = 3
    base_delay: float = 1.0  # Seconds
    max_delay: float = 60.0  # Maximum backoff
    exponential_base: float = 2.0
    jitter: bool = True  # Add randomness to prevent thundering herd
    retry_on: List[type] = field(default_factory=list)  # Retry only these
    retry_on_result: Optional[Callable[[Any], bool]] = None  # Retry based on result


class RetryStrategy:
    """
    Retry with exponential backoff and jitter.

    Delay formula: min(max_delay, base_delay * (exponential_base ** attempt)) + jitter
    """

    def __init__(self, config: Optional[RetryConfig] = None):
        self.config = config or RetryConfig()
        self.classifier = ErrorClassifier()

    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for retry attempt"""
        delay = self.config.base_delay * (
            self.config.exponential_base ** attempt
        )
        delay = min(delay, self.config.max_delay)

        if self.config.jitter:
            # Add up to 50% jitter
            jitter = delay * random.uniform(0, 0.5)
            delay += jitter

        return delay

    def should_retry(self, error: Exception, attempt: int) -> bool:
        """Determine if we should retry"""
        if attempt >= self.config.max_retries:
            return False

        # Check if error type is in retry list
        if self.config.retry_on:
            return any(isinstance(error, exc_type) for exc_type in self.config.retry_on)

        # Use error classification
        classified = self.classifier.classify(error)
        return classified.is_retryable

    async def execute(
        self,
        func: Callable[..., Awaitable[T]],
        *args,
        on_retry: Optional[Callable[[int, Exception, float], None]] = None,
        **kwargs,
    ) -> T:
        """Execute function with retries"""
        last_error: Optional[Exception] = None

        for attempt in range(self.config.max_retries + 1):
            try:
                result = await func(*args, **kwargs)

                # Check if result should trigger retry
                if (
                    self.config.retry_on_result
                    and self.config.retry_on_result(result)
                    and attempt < self.config.max_retries
                ):
                    delay = self.calculate_delay(attempt)
                    logger.info(f"Retry {attempt + 1}: result triggered retry, waiting {delay:.2f}s")
                    await asyncio.sleep(delay)
                    continue

                return result

            except Exception as e:
                last_error = e

                if not self.should_retry(e, attempt):
                    raise

                if attempt < self.config.max_retries:
                    delay = self.calculate_delay(attempt)
                    logger.info(
                        f"Retry {attempt + 1}/{self.config.max_retries}: "
                        f"{type(e).__name__}, waiting {delay:.2f}s"
                    )

                    if on_retry:
                        on_retry(attempt + 1, e, delay)

                    await asyncio.sleep(delay)

        raise last_error


# ============== Bulkhead ==============

class Bulkhead:
    """
    Bulkhead pattern for resource isolation.

    Limits concurrent calls to prevent resource exhaustion and
    isolate failures in one component from affecting others.
    """

    def __init__(
        self,
        name: str,
        max_concurrent: int = 10,
        max_wait_seconds: float = 0,  # 0 = fail fast
    ):
        self.name = name
        self.max_concurrent = max_concurrent
        self.max_wait_seconds = max_wait_seconds
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._active_count = 0
        self._rejected_count = 0
        self._lock = asyncio.Lock()

        logger.info(f"Bulkhead '{name}' initialized (max_concurrent={max_concurrent})")

    async def call(
        self,
        func: Callable[..., Awaitable[T]],
        *args,
        **kwargs,
    ) -> T:
        """Execute function within bulkhead limits"""

        try:
            acquired = await asyncio.wait_for(
                self._semaphore.acquire(),
                timeout=self.max_wait_seconds if self.max_wait_seconds > 0 else None,
            )
        except asyncio.TimeoutError:
            async with self._lock:
                self._rejected_count += 1
            raise BulkheadFullError(
                f"Bulkhead '{self.name}' is full ({self._active_count}/{self.max_concurrent})"
            )

        async with self._lock:
            self._active_count += 1

        try:
            return await func(*args, **kwargs)
        finally:
            self._semaphore.release()
            async with self._lock:
                self._active_count -= 1

    def get_metrics(self) -> Dict[str, Any]:
        """Get bulkhead metrics"""
        return {
            "name": self.name,
            "max_concurrent": self.max_concurrent,
            "active_count": self._active_count,
            "available": self.max_concurrent - self._active_count,
            "rejected_count": self._rejected_count,
        }


class BulkheadFullError(Exception):
    """Raised when bulkhead is at capacity"""
    pass


# ============== Combined Resilience Wrapper ==============

class ResiliencePolicy:
    """
    Combined resilience policy with multiple patterns.

    Execution order:
    1. Bulkhead (limit concurrency)
    2. Circuit Breaker (fail fast if service is down)
    3. Retry (with exponential backoff)
    """

    def __init__(
        self,
        name: str,
        circuit_breaker: Optional[CircuitBreaker] = None,
        retry_strategy: Optional[RetryStrategy] = None,
        bulkhead: Optional[Bulkhead] = None,
        fallback: Optional[Callable[..., Any]] = None,
    ):
        self.name = name
        self.circuit_breaker = circuit_breaker
        self.retry_strategy = retry_strategy
        self.bulkhead = bulkhead
        self.fallback = fallback

        logger.info(f"ResiliencePolicy '{name}' initialized")

    async def execute(
        self,
        func: Callable[..., Awaitable[T]],
        *args,
        **kwargs,
    ) -> T:
        """Execute function with full resilience policy"""

        async def _inner():
            # Apply retry if configured
            if self.retry_strategy:
                return await self.retry_strategy.execute(func, *args, **kwargs)
            return await func(*args, **kwargs)

        async def _with_circuit_breaker():
            # Apply circuit breaker if configured
            if self.circuit_breaker:
                return await self.circuit_breaker.call(_inner, fallback=self.fallback)
            return await _inner()

        # Apply bulkhead if configured
        if self.bulkhead:
            return await self.bulkhead.call(_with_circuit_breaker)

        return await _with_circuit_breaker()

    def get_metrics(self) -> Dict[str, Any]:
        """Get combined metrics"""
        metrics = {"policy_name": self.name}

        if self.circuit_breaker:
            metrics["circuit_breaker"] = self.circuit_breaker.get_metrics()
        if self.bulkhead:
            metrics["bulkhead"] = self.bulkhead.get_metrics()

        return metrics


# ============== Decorator Interface ==============

def with_resilience(
    circuit_breaker: Optional[CircuitBreaker] = None,
    retry_config: Optional[RetryConfig] = None,
    bulkhead: Optional[Bulkhead] = None,
    fallback: Optional[Callable] = None,
):
    """
    Decorator to apply resilience patterns to async functions.

    Usage:
        @with_resilience(
            circuit_breaker=CircuitBreaker("my_service"),
            retry_config=RetryConfig(max_retries=3),
        )
        async def call_external_service():
            ...
    """
    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        policy = ResiliencePolicy(
            name=func.__name__,
            circuit_breaker=circuit_breaker,
            retry_strategy=RetryStrategy(retry_config) if retry_config else None,
            bulkhead=bulkhead,
            fallback=fallback,
        )

        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await policy.execute(func, *args, **kwargs)

        return wrapper
    return decorator


# ============== Circuit Breaker Registry ==============

class CircuitBreakerRegistry:
    """
    Global registry for circuit breakers.

    Allows monitoring and management of all circuit breakers in the system.
    """

    _instance: Optional["CircuitBreakerRegistry"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._breakers: Dict[str, CircuitBreaker] = {}
        return cls._instance

    def register(self, breaker: CircuitBreaker):
        """Register a circuit breaker"""
        self._breakers[breaker.name] = breaker

    def get(self, name: str) -> Optional[CircuitBreaker]:
        """Get a circuit breaker by name"""
        return self._breakers.get(name)

    def get_or_create(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None,
    ) -> CircuitBreaker:
        """Get existing or create new circuit breaker"""
        if name not in self._breakers:
            breaker = CircuitBreaker(name, config)
            self.register(breaker)
        return self._breakers[name]

    def get_all_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Get metrics for all circuit breakers"""
        return {
            name: breaker.get_metrics()
            for name, breaker in self._breakers.items()
        }

    def reset_all(self):
        """Reset all circuit breakers"""
        for breaker in self._breakers.values():
            breaker.reset()


# ============== Pre-configured Policies ==============

def create_llm_policy(name: str = "llm") -> ResiliencePolicy:
    """Create resilience policy for LLM calls"""
    return ResiliencePolicy(
        name=name,
        circuit_breaker=CircuitBreaker(
            name=f"{name}_circuit",
            config=CircuitBreakerConfig(
                failure_threshold=5,
                timeout_seconds=60,
                slow_call_threshold=30,
            ),
        ),
        retry_strategy=RetryStrategy(
            RetryConfig(
                max_retries=3,
                base_delay=2.0,
                max_delay=30.0,
            )
        ),
        bulkhead=Bulkhead(
            name=f"{name}_bulkhead",
            max_concurrent=20,
            max_wait_seconds=10,
        ),
    )


def create_http_policy(name: str = "http") -> ResiliencePolicy:
    """Create resilience policy for HTTP calls"""
    return ResiliencePolicy(
        name=name,
        circuit_breaker=CircuitBreaker(
            name=f"{name}_circuit",
            config=CircuitBreakerConfig(
                failure_threshold=3,
                timeout_seconds=30,
            ),
        ),
        retry_strategy=RetryStrategy(
            RetryConfig(
                max_retries=2,
                base_delay=1.0,
                max_delay=10.0,
            )
        ),
    )


def create_database_policy(name: str = "database") -> ResiliencePolicy:
    """Create resilience policy for database calls"""
    return ResiliencePolicy(
        name=name,
        circuit_breaker=CircuitBreaker(
            name=f"{name}_circuit",
            config=CircuitBreakerConfig(
                failure_threshold=3,
                timeout_seconds=15,
            ),
        ),
        retry_strategy=RetryStrategy(
            RetryConfig(
                max_retries=2,
                base_delay=0.5,
                max_delay=5.0,
            )
        ),
        bulkhead=Bulkhead(
            name=f"{name}_bulkhead",
            max_concurrent=50,
        ),
    )
