"""
Combined Resilience Patterns
============================

Combines retry and circuit breaker patterns for robust external calls.

Example
-------
>>> from obskit.resilience.combined import resilient_call, ResilientExecutor
>>>
>>> # Simple usage
>>> result = await resilient_call(
...     func=external_api.get_user,
...     args=(user_id,),
...     circuit_breaker="user_api",
...     max_retries=3,
... )
>>>
>>> # Using executor
>>> executor = ResilientExecutor(
...     circuit_breaker="payment_api",
...     max_retries=3,
...     backoff="exponential",
... )
>>> result = await executor.execute(payment_api.charge, amount)
"""

from __future__ import annotations

import asyncio
import random
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from functools import wraps
from typing import TypeVar

from obskit.logging import get_logger
from obskit.resilience.circuit_breaker import CircuitBreaker, CircuitOpenError
from obskit.resilience.factory import CircuitBreakerPreset, get_circuit_breaker

logger = get_logger("obskit.resilience.combined")

T = TypeVar("T")


class BackoffStrategy(Enum):
    """Backoff strategies for retries."""

    CONSTANT = "constant"
    LINEAR = "linear"
    EXPONENTIAL = "exponential"
    EXPONENTIAL_JITTER = "exponential_jitter"


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    backoff: BackoffStrategy = BackoffStrategy.EXPONENTIAL_JITTER
    retryable_exceptions: tuple[type, ...] = (Exception,)

    def get_delay(self, attempt: int) -> float:
        """Calculate delay for a given attempt."""
        if self.backoff == BackoffStrategy.CONSTANT:
            delay = self.base_delay
        elif self.backoff == BackoffStrategy.LINEAR:
            delay = self.base_delay * attempt
        elif self.backoff == BackoffStrategy.EXPONENTIAL:
            delay = self.base_delay * (2 ** (attempt - 1))
        elif self.backoff == BackoffStrategy.EXPONENTIAL_JITTER:
            delay = self.base_delay * (2 ** (attempt - 1))
            delay = delay * (0.5 + random.random())  # Add jitter
        else:
            delay = self.base_delay

        return min(delay, self.max_delay)


class ResilientExecutor:
    """
    Executor that combines circuit breaker and retry patterns.

    Example
    -------
    >>> executor = ResilientExecutor(
    ...     circuit_breaker="external_api",
    ...     max_retries=3,
    ...     backoff="exponential",
    ... )
    >>>
    >>> # Sync execution
    >>> result = executor.execute_sync(api.call, arg1, arg2)
    >>>
    >>> # Async execution
    >>> result = await executor.execute(api.call_async, arg1, arg2)
    """

    def __init__(
        self,
        circuit_breaker: str | CircuitBreaker | None = None,
        circuit_breaker_preset: CircuitBreakerPreset | None = None,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        backoff: str | BackoffStrategy = BackoffStrategy.EXPONENTIAL_JITTER,
        retryable_exceptions: tuple[type, ...] = (Exception,),
        on_retry: Callable[[int, Exception], None] | None = None,
        on_circuit_open: Callable[[], None] | None = None,
    ):
        """
        Initialize resilient executor.

        Parameters
        ----------
        circuit_breaker : str or CircuitBreaker, optional
            Circuit breaker name or instance.
        circuit_breaker_preset : CircuitBreakerPreset, optional
            Preset for circuit breaker if creating new.
        max_retries : int
            Maximum retry attempts (default: 3).
        base_delay : float
            Base delay between retries in seconds (default: 1.0).
        max_delay : float
            Maximum delay between retries (default: 60.0).
        backoff : str or BackoffStrategy
            Backoff strategy (default: exponential_jitter).
        retryable_exceptions : tuple of types
            Exceptions that trigger retry (default: all).
        on_retry : callable, optional
            Callback called on each retry (attempt, exception).
        on_circuit_open : callable, optional
            Callback called when circuit opens.
        """
        # Set up circuit breaker
        if isinstance(circuit_breaker, str):
            self._circuit_breaker = get_circuit_breaker(
                circuit_breaker,
                preset=circuit_breaker_preset,
            )
        elif isinstance(circuit_breaker, CircuitBreaker):
            self._circuit_breaker = circuit_breaker
        else:
            self._circuit_breaker = None

        # Set up retry config
        if isinstance(backoff, str):
            backoff = BackoffStrategy(backoff)

        self._retry_config = RetryConfig(
            max_retries=max_retries,
            base_delay=base_delay,
            max_delay=max_delay,
            backoff=backoff,
            retryable_exceptions=retryable_exceptions,
        )

        self._on_retry = on_retry
        self._on_circuit_open = on_circuit_open

    async def execute(
        self,
        func: Callable[..., T],
        *args,
        **kwargs,
    ) -> T:
        """
        Execute function with retry and circuit breaker (async).

        Parameters
        ----------
        func : callable
            Function to execute (can be sync or async).
        *args
            Positional arguments for function.
        **kwargs
            Keyword arguments for function.

        Returns
        -------
        T
            Function result.

        Raises
        ------
        Exception
            If all retries fail or circuit is open.
        """
        last_exception: Exception | None = None

        for attempt in range(1, self._retry_config.max_retries + 1):
            try:
                # Check circuit breaker
                if self._circuit_breaker:
                    # Check if circuit is open
                    state = getattr(self._circuit_breaker, "state", None)
                    if state and hasattr(state, "name") and state.name == "OPEN":
                        if self._on_circuit_open:
                            self._on_circuit_open()
                        from obskit import CircuitOpenError

                        raise CircuitOpenError(
                            breaker_name=getattr(self._circuit_breaker, "name", "unknown"),
                            time_until_retry=0.0,
                        )

                # Execute with circuit breaker
                if self._circuit_breaker:
                    with self._circuit_breaker:
                        if asyncio.iscoroutinefunction(func):
                            result = await func(*args, **kwargs)
                        else:
                            result = func(*args, **kwargs)
                else:
                    if asyncio.iscoroutinefunction(func):
                        result = await func(*args, **kwargs)
                    else:
                        result = func(*args, **kwargs)

                return result

            except self._retry_config.retryable_exceptions as e:
                last_exception = e

                # Don't retry on circuit open
                if "Circuit" in type(e).__name__:
                    raise

                if attempt < self._retry_config.max_retries:
                    delay = self._retry_config.get_delay(attempt)

                    logger.warning(
                        "retry_attempt",
                        attempt=attempt,
                        max_retries=self._retry_config.max_retries,
                        delay=delay,
                        error=str(e),
                    )

                    if self._on_retry:
                        self._on_retry(attempt, e)

                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        "all_retries_failed",
                        attempts=attempt,
                        error=str(e),
                    )
                    raise

        if last_exception is not None:
            raise last_exception
        raise RuntimeError("Resilient executor completed without returning a result")

    def execute_sync(
        self,
        func: Callable[..., T],
        *args,
        **kwargs,
    ) -> T:
        """
        Execute function with retry and circuit breaker (sync).

        Parameters
        ----------
        func : callable
            Synchronous function to execute.
        *args
            Positional arguments.
        **kwargs
            Keyword arguments.

        Returns
        -------
        T
            Function result.
        """
        last_exception: Exception | None = None

        for attempt in range(1, self._retry_config.max_retries + 1):
            try:
                if self._circuit_breaker:
                    with self._circuit_breaker:
                        result = func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)

                return result

            except self._retry_config.retryable_exceptions as e:
                last_exception = e

                if "Circuit" in type(e).__name__:
                    raise

                if attempt < self._retry_config.max_retries:
                    delay = self._retry_config.get_delay(attempt)

                    logger.warning(
                        "retry_attempt",
                        attempt=attempt,
                        delay=delay,
                        error=str(e),
                    )

                    if self._on_retry:
                        self._on_retry(attempt, e)

                    time.sleep(delay)
                else:
                    raise

        if last_exception is not None:
            raise last_exception
        raise RuntimeError("Resilient executor completed without returning a result")


async def resilient_call(
    func: Callable[..., T],
    args: tuple = (),
    kwargs: dict | None = None,
    circuit_breaker: str | CircuitBreaker | None = None,
    circuit_breaker_preset: CircuitBreakerPreset | None = None,
    max_retries: int = 3,
    backoff: str = "exponential_jitter",
) -> T:
    """
    Execute a function with retry and circuit breaker protection.

    Convenience function for one-off resilient calls.

    Parameters
    ----------
    func : callable
        Function to execute.
    args : tuple
        Positional arguments.
    kwargs : dict, optional
        Keyword arguments.
    circuit_breaker : str or CircuitBreaker, optional
        Circuit breaker to use.
    circuit_breaker_preset : CircuitBreakerPreset, optional
        Preset for new circuit breaker.
    max_retries : int
        Maximum retries (default: 3).
    backoff : str
        Backoff strategy (default: exponential_jitter).

    Returns
    -------
    T
        Function result.

    Example
    -------
    >>> result = await resilient_call(
    ...     api.get_user,
    ...     args=(user_id,),
    ...     circuit_breaker="user_api",
    ...     max_retries=3,
    ... )
    """
    executor = ResilientExecutor(
        circuit_breaker=circuit_breaker,
        circuit_breaker_preset=circuit_breaker_preset,
        max_retries=max_retries,
        backoff=backoff,
    )
    return await executor.execute(func, *args, **(kwargs or {}))


def resilient_call_sync(
    func: Callable[..., T],
    args: tuple = (),
    kwargs: dict | None = None,
    circuit_breaker: str | CircuitBreaker | None = None,
    max_retries: int = 3,
    backoff: str = "exponential_jitter",
) -> T:
    """Synchronous version of resilient_call."""
    executor = ResilientExecutor(
        circuit_breaker=circuit_breaker,
        max_retries=max_retries,
        backoff=backoff,
    )
    return executor.execute_sync(func, *args, **(kwargs or {}))


def with_resilience(
    circuit_breaker: str | None = None,
    circuit_breaker_preset: CircuitBreakerPreset | None = None,
    max_retries: int = 3,
    backoff: str = "exponential_jitter",
):
    """
    Decorator for adding resilience to a function.

    Example
    -------
    >>> @with_resilience(circuit_breaker="payment_api", max_retries=3)
    >>> async def charge_payment(amount):
    ...     return await payment_api.charge(amount)
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        executor = ResilientExecutor(
            circuit_breaker=circuit_breaker,
            circuit_breaker_preset=circuit_breaker_preset,
            max_retries=max_retries,
            backoff=backoff,
        )

        if asyncio.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                return await executor.execute(func, *args, **kwargs)

            return async_wrapper
        else:

            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                return executor.execute_sync(func, *args, **kwargs)

            return sync_wrapper

    return decorator


__all__ = [
    "BackoffStrategy",
    "RetryConfig",
    "ResilientExecutor",
    "resilient_call",
    "resilient_call_sync",
    "with_resilience",
]
