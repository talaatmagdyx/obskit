"""
Adaptive Retry with Backpressure.

Smarter retries that adapt to system load.
"""

import asyncio
import functools
import random
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any, TypeVar

from prometheus_client import Counter, Gauge, Histogram

from ..logging import get_logger

logger = get_logger(__name__)

# Metrics
ADAPTIVE_RETRY_ATTEMPTS = Counter(
    "adaptive_retry_attempts_total", "Total retry attempts", ["name", "status"]
)

ADAPTIVE_RETRY_DELAY = Histogram(
    "adaptive_retry_delay_seconds",
    "Retry delay distribution",
    ["name"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0],
)

ADAPTIVE_RETRY_ERROR_RATE = Gauge("adaptive_retry_error_rate", "Current error rate", ["name"])

ADAPTIVE_RETRY_BACKPRESSURE = Gauge(
    "adaptive_retry_backpressure_multiplier", "Current backpressure multiplier", ["name"]
)

ADAPTIVE_RETRY_CONCURRENCY = Gauge(
    "adaptive_retry_concurrent_requests", "Current concurrent requests", ["name"]
)

F = TypeVar("F", bound=Callable[..., Any])


class BackpressureStrategy(Enum):
    """Backpressure strategies."""

    NONE = "none"
    LINEAR = "linear"
    EXPONENTIAL = "exponential"
    ADAPTIVE = "adaptive"


@dataclass
class RetryConfig:
    """Configuration for adaptive retry."""

    max_retries: int = 3
    base_delay_seconds: float = 0.1
    max_delay_seconds: float = 60.0
    exponential_base: float = 2.0
    jitter_factor: float = 0.25

    # Backpressure settings
    backpressure_strategy: BackpressureStrategy = BackpressureStrategy.ADAPTIVE
    error_rate_threshold: float = 0.1  # 10% errors
    latency_threshold_seconds: float = 1.0

    # Adaptive settings
    window_size: int = 100
    min_samples: int = 10
    cooldown_seconds: float = 5.0

    # Concurrency limiting
    max_concurrent: int = 100
    min_concurrent: int = 1


@dataclass
class RetryState:
    """State for adaptive retry."""

    name: str
    attempt: int = 0
    last_error: Exception | None = None
    start_time: float = 0.0
    total_delay: float = 0.0
    backpressure_multiplier: float = 1.0


class AdaptiveRetry:
    """
    Retry mechanism that adapts to system load.

    Automatically adjusts retry delays based on error rate and latency.

    Example:
        retry = AdaptiveRetry(
            name="external_api",
            config=RetryConfig(
                max_retries=3,
                base_delay_seconds=0.1,
                backpressure_strategy=BackpressureStrategy.ADAPTIVE
            )
        )

        @retry.wrap
        async def call_api():
            return await external_api.call()

        # Or use directly
        result = await retry.execute(call_api)
    """

    def __init__(
        self,
        name: str,
        config: RetryConfig | None = None,
        retryable_exceptions: set[type] | None = None,
    ):
        """
        Initialize adaptive retry.

        Args:
            name: Name for metrics
            config: Retry configuration
            retryable_exceptions: Exceptions to retry on
        """
        self.name = name
        self.config = config or RetryConfig()
        self.retryable_exceptions = retryable_exceptions or {
            Exception,
            ConnectionError,
            TimeoutError,
        }

        # Tracking for adaptation
        self._results: deque = deque(maxlen=self.config.window_size)
        self._latencies: deque = deque(maxlen=self.config.window_size)
        self._current_concurrent = 0
        self._max_allowed_concurrent = self.config.max_concurrent
        self._last_adaptation = 0.0
        self._backpressure_multiplier = 1.0

        # Semaphore for concurrency limiting
        self._semaphore = asyncio.Semaphore(self.config.max_concurrent)

    def _is_retryable(self, exception: Exception) -> bool:
        """Check if exception is retryable."""
        return any(isinstance(exception, exc_type) for exc_type in self.retryable_exceptions)

    def _calculate_delay(self, attempt: int, state: RetryState) -> float:
        """Calculate delay for retry attempt."""
        # Base exponential backoff
        delay = self.config.base_delay_seconds * (self.config.exponential_base**attempt)

        # Apply backpressure
        delay *= state.backpressure_multiplier

        # Add jitter
        jitter = delay * self.config.jitter_factor * random.random()
        delay += jitter

        # Cap at max
        delay = min(delay, self.config.max_delay_seconds)

        return delay

    def _update_metrics(self, success: bool, latency: float):
        """Update tracking metrics."""
        self._results.append(success)
        self._latencies.append(latency)

        # Calculate current error rate
        if len(self._results) >= self.config.min_samples:
            error_rate = 1 - (sum(self._results) / len(self._results))
            ADAPTIVE_RETRY_ERROR_RATE.labels(name=self.name).set(error_rate)

            # Maybe adapt
            if time.time() - self._last_adaptation >= self.config.cooldown_seconds:
                self._adapt(error_rate)

    def _adapt(self, error_rate: float):
        """Adapt retry behavior based on metrics."""
        if self.config.backpressure_strategy == BackpressureStrategy.NONE:
            return

        avg_latency = sum(self._latencies) / len(self._latencies) if self._latencies else 0

        # Calculate backpressure multiplier
        if self.config.backpressure_strategy == BackpressureStrategy.LINEAR:
            if error_rate > self.config.error_rate_threshold:
                self._backpressure_multiplier = 1 + error_rate * 10
            else:
                self._backpressure_multiplier = 1.0

        elif self.config.backpressure_strategy == BackpressureStrategy.EXPONENTIAL:
            if error_rate > self.config.error_rate_threshold:
                self._backpressure_multiplier = 2 ** (error_rate * 10)
            else:
                self._backpressure_multiplier = 1.0

        elif self.config.backpressure_strategy == BackpressureStrategy.ADAPTIVE:
            # Combine error rate and latency
            error_factor = 1.0
            latency_factor = 1.0

            if error_rate > self.config.error_rate_threshold:
                error_factor = 1 + (error_rate / self.config.error_rate_threshold)

            if avg_latency > self.config.latency_threshold_seconds:
                latency_factor = avg_latency / self.config.latency_threshold_seconds

            self._backpressure_multiplier = error_factor * latency_factor

            # Adjust concurrency limit
            if error_rate > self.config.error_rate_threshold * 2:
                self._max_allowed_concurrent = max(
                    self.config.min_concurrent, int(self._max_allowed_concurrent * 0.8)
                )
            elif error_rate < self.config.error_rate_threshold * 0.5:
                self._max_allowed_concurrent = min(
                    self.config.max_concurrent, int(self._max_allowed_concurrent * 1.2)
                )

        # Cap multiplier
        self._backpressure_multiplier = min(self._backpressure_multiplier, 10.0)

        ADAPTIVE_RETRY_BACKPRESSURE.labels(name=self.name).set(self._backpressure_multiplier)

        self._last_adaptation = time.time()

        logger.debug(
            "adaptive_retry_adjusted",
            name=self.name,
            backpressure_multiplier=self._backpressure_multiplier,
            max_concurrent=self._max_allowed_concurrent,
            error_rate=error_rate,
            avg_latency=avg_latency,
        )

    async def execute(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with adaptive retry.

        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result
        """
        state = RetryState(name=self.name, start_time=time.time())

        # Acquire semaphore for concurrency limiting
        async with self._semaphore:
            self._current_concurrent += 1
            ADAPTIVE_RETRY_CONCURRENCY.labels(name=self.name).set(self._current_concurrent)

            try:
                return await self._execute_with_retry(func, state, *args, **kwargs)
            finally:
                self._current_concurrent -= 1
                ADAPTIVE_RETRY_CONCURRENCY.labels(name=self.name).set(self._current_concurrent)

    async def _execute_with_retry(self, func: Callable, state: RetryState, *args, **kwargs) -> Any:
        """Execute with retry logic."""
        last_exception = None

        for attempt in range(self.config.max_retries + 1):
            state.attempt = attempt
            state.backpressure_multiplier = self._backpressure_multiplier

            try:
                start = time.time()

                # Execute function
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)

                latency = time.time() - start

                # Record success
                ADAPTIVE_RETRY_ATTEMPTS.labels(name=self.name, status="success").inc()
                self._update_metrics(True, latency)

                return result

            except Exception as e:
                last_exception = e
                latency = time.time() - start

                # Check if retryable
                if not self._is_retryable(e):
                    ADAPTIVE_RETRY_ATTEMPTS.labels(name=self.name, status="non_retryable").inc()
                    self._update_metrics(False, latency)
                    raise

                # Check if max retries reached
                if attempt >= self.config.max_retries:
                    ADAPTIVE_RETRY_ATTEMPTS.labels(name=self.name, status="exhausted").inc()
                    self._update_metrics(False, latency)
                    raise

                # Calculate delay
                delay = self._calculate_delay(attempt, state)
                state.total_delay += delay

                ADAPTIVE_RETRY_ATTEMPTS.labels(name=self.name, status="retry").inc()
                ADAPTIVE_RETRY_DELAY.labels(name=self.name).observe(delay)
                self._update_metrics(False, latency)

                logger.debug(
                    "adaptive_retry_attempt",
                    name=self.name,
                    attempt=attempt + 1,
                    delay=delay,
                    backpressure=state.backpressure_multiplier,
                    error=str(e),
                )

                await asyncio.sleep(delay)

        # Should not reach here, but just in case
        raise last_exception or Exception("Retry exhausted without exception")

    def execute_sync(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function synchronously with adaptive retry.

        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result
        """
        state = RetryState(name=self.name, start_time=time.time())

        last_exception = None

        for attempt in range(self.config.max_retries + 1):
            state.attempt = attempt
            state.backpressure_multiplier = self._backpressure_multiplier

            try:
                start = time.time()
                result = func(*args, **kwargs)
                latency = time.time() - start

                ADAPTIVE_RETRY_ATTEMPTS.labels(name=self.name, status="success").inc()
                self._update_metrics(True, latency)

                return result

            except Exception as e:
                last_exception = e
                latency = time.time() - start

                if not self._is_retryable(e):
                    ADAPTIVE_RETRY_ATTEMPTS.labels(name=self.name, status="non_retryable").inc()
                    self._update_metrics(False, latency)
                    raise

                if attempt >= self.config.max_retries:
                    ADAPTIVE_RETRY_ATTEMPTS.labels(name=self.name, status="exhausted").inc()
                    self._update_metrics(False, latency)
                    raise

                delay = self._calculate_delay(attempt, state)
                state.total_delay += delay

                ADAPTIVE_RETRY_ATTEMPTS.labels(name=self.name, status="retry").inc()
                ADAPTIVE_RETRY_DELAY.labels(name=self.name).observe(delay)
                self._update_metrics(False, latency)

                time.sleep(delay)

        raise last_exception or Exception("Retry exhausted")

    def wrap(self, func: F) -> F:
        """
        Decorator to wrap function with adaptive retry.

        Example:
            @retry.wrap
            async def call_api():
                pass
        """

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            return await self.execute(func, *args, **kwargs)

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            return self.execute_sync(func, *args, **kwargs)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return sync_wrapper  # type: ignore

    def get_stats(self) -> dict[str, Any]:
        """Get current retry statistics."""
        error_rate = 1 - (sum(self._results) / len(self._results)) if self._results else 0
        avg_latency = sum(self._latencies) / len(self._latencies) if self._latencies else 0

        return {
            "name": self.name,
            "backpressure_multiplier": self._backpressure_multiplier,
            "error_rate": error_rate,
            "avg_latency": avg_latency,
            "current_concurrent": self._current_concurrent,
            "max_allowed_concurrent": self._max_allowed_concurrent,
            "samples": len(self._results),
        }


def adaptive_retry(
    name: str,
    max_retries: int = 3,
    base_delay: float = 0.1,
    backpressure: BackpressureStrategy = BackpressureStrategy.ADAPTIVE,
    **config_kwargs,
) -> Callable[[F], F]:
    """
    Decorator for adaptive retry.

    Example:
        @adaptive_retry("external_api", max_retries=3)
        async def call_api():
            pass
    """
    config = RetryConfig(
        max_retries=max_retries,
        base_delay_seconds=base_delay,
        backpressure_strategy=backpressure,
        **config_kwargs,
    )
    retry = AdaptiveRetry(name, config)
    return retry.wrap


__all__ = [
    "AdaptiveRetry",
    "RetryConfig",
    "RetryState",
    "BackpressureStrategy",
    "adaptive_retry",
    "ADAPTIVE_RETRY_ATTEMPTS",
    "ADAPTIVE_RETRY_DELAY",
    "ADAPTIVE_RETRY_ERROR_RATE",
    "ADAPTIVE_RETRY_BACKPRESSURE",
    "ADAPTIVE_RETRY_CONCURRENCY",
]
