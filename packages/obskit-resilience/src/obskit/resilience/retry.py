"""
Retry Pattern Implementation
============================

The retry pattern handles transient failures by automatically retrying
operations with exponential backoff and optional jitter.

Why Retry?
----------
Transient errors are temporary failures that resolve on their own:

- Network blips (packet loss, connection reset)
- Temporary service overload (503 responses)
- Database connection pool exhaustion
- Rate limit brief exceedances

Without retry, these cause immediate failures. With retry, your
application handles them gracefully.

Exponential Backoff
-------------------
Exponential backoff increases the delay between retries:

.. code-block:: text

    Attempt 1: Immediate
    Attempt 2: Wait 1 second
    Attempt 3: Wait 2 seconds
    Attempt 4: Wait 4 seconds
    Attempt 5: Wait 8 seconds
    ...

This prevents retry storms where thousands of clients simultaneously
retry, overwhelming an already struggling service.

Jitter
------
Jitter adds randomness to backoff delays to prevent thundering herd:

.. code-block:: text

    Without jitter:
    Client A: Wait 1s → Retry
    Client B: Wait 1s → Retry
    Client C: Wait 1s → Retry
    → All clients retry at the same time!

    With jitter:
    Client A: Wait 0.7s → Retry
    Client B: Wait 1.2s → Retry
    Client C: Wait 0.9s → Retry
    → Retries are spread out

Example - Basic Usage
---------------------
.. code-block:: python

    from obskit.resilience import retry

    @retry(max_attempts=3)
    async def fetch_data():
        return await api.get("/data")

Example - Custom Configuration
------------------------------
.. code-block:: python

    @retry(
        max_attempts=5,
        base_delay=0.5,
        max_delay=30.0,
        exponential_base=2.0,
        jitter=True,
    )
    async def fetch_data():
        return await api.get("/data")

Example - Retry Specific Exceptions
-----------------------------------
.. code-block:: python

    import httpx

    @retry(
        max_attempts=3,
        retry_on=(httpx.TimeoutException, httpx.NetworkError),
    )
    async def fetch_data():
        async with httpx.AsyncClient() as client:
            response = await client.get("https://api.example.com")
            return response.json()

Example - Don't Retry Certain Exceptions
----------------------------------------
.. code-block:: python

    @retry(
        max_attempts=3,
        no_retry_on=(ValueError, KeyError),  # Business logic errors
    )
    async def process_data(data: dict):
        if "id" not in data:
            raise KeyError("id required")  # Won't retry
        return await api.process(data)
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from functools import wraps
from typing import ParamSpec, TypeVar

from obskit.config import get_settings
from obskit.logging import get_logger

# Type variables
P = ParamSpec("P")
T = TypeVar("T")

# Logger
logger = get_logger("obskit.retry")


class RetryError(Exception):
    """
    Raised when all retry attempts have been exhausted.

    Attributes
    ----------
    last_exception : Exception
        The exception from the last attempt.
    attempts : int
        Total number of attempts made.
    total_delay : float
        Total time spent waiting between retries.

    Example
    -------
    >>> try:
    ...     await fetch_data()  # Will retry 3 times
    ... except RetryError as e:
    ...     print(f"Failed after {e.attempts} attempts")
    ...     print(f"Last error: {e.last_exception}")
    """

    def __init__(
        self,
        message: str,
        last_exception: Exception,
        attempts: int,
        total_delay: float,
    ) -> None:
        self.last_exception = last_exception
        self.attempts = attempts
        self.total_delay = total_delay
        super().__init__(message)


@dataclass
class RetryConfig:
    """
    Configuration for retry behavior.

    Attributes
    ----------
    max_attempts : int
        Maximum number of attempts (including first).

    base_delay : float
        Initial delay in seconds.

    max_delay : float
        Maximum delay cap in seconds.

    exponential_base : float
        Base for exponential backoff (default 2.0).

    jitter : bool
        Whether to add random jitter.

    retry_on : tuple[type[Exception], ...]
        Exceptions to retry on (default: all).

    no_retry_on : tuple[type[Exception], ...]
        Exceptions to never retry on.

    Example
    -------
    >>> config = RetryConfig(
    ...     max_attempts=5,
    ...     base_delay=1.0,
    ...     max_delay=60.0,
    ...     jitter=True,
    ... )
    """

    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    retry_on: tuple[type[Exception], ...] = (Exception,)
    no_retry_on: tuple[type[Exception], ...] = ()

    @classmethod
    def from_settings(cls) -> RetryConfig:
        """
        Create config from obskit settings.

        Returns
        -------
        RetryConfig
            Configuration from environment/settings.
        """
        settings = get_settings()
        return cls(
            max_attempts=settings.retry_max_attempts,
            base_delay=settings.retry_base_delay,
            max_delay=settings.retry_max_delay,
            exponential_base=settings.retry_exponential_base,
            jitter=True,
        )


def calculate_delay(
    attempt: int,
    config: RetryConfig,
) -> float:
    """
    Calculate the delay before the next retry attempt.

    Uses exponential backoff with optional jitter.

    Parameters
    ----------
    attempt : int
        Current attempt number (1-indexed).
    config : RetryConfig
        Retry configuration.

    Returns
    -------
    float
        Delay in seconds before next attempt.

    Example
    -------
    >>> config = RetryConfig(base_delay=1.0, exponential_base=2.0)
    >>> calculate_delay(1, config)  # ~1.0 second
    >>> calculate_delay(2, config)  # ~2.0 seconds
    >>> calculate_delay(3, config)  # ~4.0 seconds
    """
    # Calculate exponential delay
    # delay = base_delay * (exponential_base ^ (attempt - 1))
    delay = config.base_delay * (config.exponential_base ** (attempt - 1))

    # Cap at max_delay
    delay = min(delay, config.max_delay)

    # Add jitter if enabled
    if config.jitter:
        # Full jitter: random value between 0 and delay
        # nosec B311 - random is used for retry jitter timing, not security
        delay = random.uniform(0, delay)  # nosec B311

    return delay


def should_retry(
    exception: Exception,
    config: RetryConfig,
) -> bool:
    """
    Determine if an exception should trigger a retry.

    Parameters
    ----------
    exception : Exception
        The exception that occurred.
    config : RetryConfig
        Retry configuration.

    Returns
    -------
    bool
        True if should retry, False otherwise.
    """
    # Never retry on excluded exceptions
    if isinstance(exception, config.no_retry_on):
        return False

    # Only retry on included exceptions
    return bool(isinstance(exception, config.retry_on))


def retry(
    max_attempts: int | None = None,
    base_delay: float | None = None,
    max_delay: float | None = None,
    exponential_base: float | None = None,
    jitter: bool = True,
    retry_on: tuple[type[Exception], ...] = (Exception,),
    no_retry_on: tuple[type[Exception], ...] = (),
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """
    Decorator for retrying async functions with exponential backoff.

    Automatically retries the decorated function when it raises an
    exception, using exponential backoff between attempts.

    Parameters
    ----------
    max_attempts : int, optional
        Maximum number of attempts. Default: from settings.

    base_delay : float, optional
        Initial delay in seconds. Default: from settings.

    max_delay : float, optional
        Maximum delay cap. Default: from settings.

    exponential_base : float, optional
        Base for exponential calculation. Default: from settings.

    jitter : bool, default=True
        Whether to add random jitter to delays.

    retry_on : tuple[type], default=(Exception,)
        Only retry on these exception types.

    no_retry_on : tuple[type], default=()
        Never retry on these exception types.

    Returns
    -------
    Callable
        Decorated function with retry logic.

    Raises
    ------
    RetryError
        When all attempts are exhausted.

    Example - Basic Usage
    ---------------------
    >>> from obskit.resilience import retry
    >>>
    >>> @retry(max_attempts=3)
    ... async def fetch_data():
    ...     return await api.get("/data")

    Example - Full Configuration
    ----------------------------
    >>> @retry(
    ...     max_attempts=5,
    ...     base_delay=0.5,
    ...     max_delay=30.0,
    ...     exponential_base=2.0,
    ...     jitter=True,
    ...     retry_on=(ConnectionError, TimeoutError),
    ...     no_retry_on=(ValueError,),
    ... )
    ... async def fetch_data():
    ...     return await api.get("/data")

    Example - With HTTP Client
    --------------------------
    >>> import httpx
    >>>
    >>> @retry(
    ...     max_attempts=3,
    ...     retry_on=(httpx.TimeoutException, httpx.NetworkError),
    ... )
    ... async def call_api(endpoint: str):
    ...     async with httpx.AsyncClient(timeout=10.0) as client:
    ...         response = await client.get(endpoint)
    ...         response.raise_for_status()
    ...         return response.json()

    Example - Handling RetryError
    -----------------------------
    >>> from obskit.resilience import retry, RetryError
    >>>
    >>> @retry(max_attempts=3)
    ... async def fetch_data():
    ...     return await api.get("/data")
    >>>
    >>> try:
    ...     result = await fetch_data()
    ... except RetryError as e:
    ...     print(f"Failed after {e.attempts} attempts")
    ...     print(f"Last error: {e.last_exception}")
    ...     print(f"Total delay: {e.total_delay:.1f}s")

    Notes
    -----
    - The first attempt is immediate (no delay)
    - Delays are calculated with exponential backoff
    - Jitter spreads out retries to prevent thundering herd
    - Logs each retry attempt at DEBUG level
    """
    # Build config from parameters or settings
    settings = get_settings()

    config = RetryConfig(
        max_attempts=max_attempts if max_attempts is not None else settings.retry_max_attempts,
        base_delay=base_delay if base_delay is not None else settings.retry_base_delay,
        max_delay=max_delay if max_delay is not None else settings.retry_max_delay,
        exponential_base=exponential_base
        if exponential_base is not None
        else settings.retry_exponential_base,
        jitter=jitter,
        retry_on=retry_on,
        no_retry_on=no_retry_on,
    )

    def decorator(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            last_exception: Exception | None = None
            total_delay: float = 0.0

            for attempt in range(1, config.max_attempts + 1):
                try:
                    return await func(*args, **kwargs)

                except Exception as e:
                    last_exception = e

                    # Check if we should retry
                    if not should_retry(e, config):
                        logger.debug(
                            "retry_not_retryable",
                            function=func.__name__,
                            attempt=attempt,
                            error=str(e),
                            error_type=type(e).__name__,
                        )
                        raise

                    # Check if we have attempts remaining
                    if attempt >= config.max_attempts:
                        logger.warning(
                            "retry_exhausted",
                            function=func.__name__,
                            attempts=attempt,
                            total_delay_seconds=total_delay,
                            error=str(e),
                            error_type=type(e).__name__,
                        )
                        raise RetryError(
                            message=f"All {attempt} retry attempts exhausted for {func.__name__}",
                            last_exception=e,
                            attempts=attempt,
                            total_delay=total_delay,
                        ) from e

                    # Calculate and wait for delay
                    delay = calculate_delay(attempt, config)
                    total_delay += delay

                    logger.debug(
                        "retry_attempt",
                        function=func.__name__,
                        attempt=attempt,
                        max_attempts=config.max_attempts,
                        delay_seconds=delay,
                        error=str(e),
                        error_type=type(e).__name__,
                    )

                    await asyncio.sleep(delay)

            # Should never reach here, but satisfy type checker
            raise RetryError(  # pragma: no cover
                message=f"Unexpected retry loop exit for {func.__name__}",
                last_exception=last_exception or Exception("Unknown error"),
                attempts=config.max_attempts,
                total_delay=total_delay,
            )

        return wrapper

    return decorator


# Alias for clarity
retry_async = retry


def retry_sync(
    max_attempts: int | None = None,
    base_delay: float | None = None,
    max_delay: float | None = None,
    exponential_base: float | None = None,
    jitter: bool = True,
    retry_on: tuple[type[Exception], ...] = (Exception,),
    no_retry_on: tuple[type[Exception], ...] = (),
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """
    Decorator for retrying synchronous functions.

    Same as retry() but for non-async functions. Uses time.sleep()
    instead of asyncio.sleep() for delays.

    Parameters
    ----------
    See retry() for parameter documentation.

    Example
    -------
    >>> from obskit.resilience.retry import retry_sync
    >>>
    >>> @retry_sync(max_attempts=3)
    ... def fetch_data():
    ...     return requests.get("/data").json()
    """
    import time

    settings = get_settings()

    config = RetryConfig(
        max_attempts=max_attempts if max_attempts is not None else settings.retry_max_attempts,
        base_delay=base_delay if base_delay is not None else settings.retry_base_delay,
        max_delay=max_delay if max_delay is not None else settings.retry_max_delay,
        exponential_base=exponential_base
        if exponential_base is not None
        else settings.retry_exponential_base,
        jitter=jitter,
        retry_on=retry_on,
        no_retry_on=no_retry_on,
    )

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            last_exception: Exception | None = None
            total_delay: float = 0.0

            for attempt in range(1, config.max_attempts + 1):
                try:
                    return func(*args, **kwargs)

                except Exception as e:
                    last_exception = e

                    if not should_retry(e, config):
                        raise

                    if attempt >= config.max_attempts:
                        raise RetryError(
                            message=f"All {attempt} retry attempts exhausted",
                            last_exception=e,
                            attempts=attempt,
                            total_delay=total_delay,
                        ) from e

                    delay = calculate_delay(attempt, config)
                    total_delay += delay
                    time.sleep(delay)

            raise RetryError(  # pragma: no cover
                message="Unexpected retry loop exit",
                last_exception=last_exception or Exception("Unknown"),
                attempts=config.max_attempts,
                total_delay=total_delay,
            )

        return wrapper

    return decorator
