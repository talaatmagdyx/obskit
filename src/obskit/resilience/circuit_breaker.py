"""
Circuit Breaker Implementation
==============================

The Circuit Breaker pattern prevents cascading failures in distributed
systems by detecting when a service is failing and temporarily stopping
requests to it.

Why Circuit Breakers?
---------------------
Without circuit breakers:

1. Service A calls Service B (which is slow/failing)
2. Service A's threads/connections pile up waiting
3. Service A runs out of resources
4. Service A starts failing
5. Services that depend on A start failing
6. Cascading failure across the system

With circuit breakers:

1. Service A calls Service B (which is slow/failing)
2. Circuit breaker detects failures
3. Circuit opens → calls fail fast without waiting
4. Service A conserves resources
5. Service B has time to recover
6. Circuit closes → normal operation resumes

State Machine
-------------
The circuit breaker has three states:

.. code-block:: text

    ┌─────────────────────────────────────────────────────────────────┐
    │                                                                 │
    │  CLOSED                                                         │
    │  ├── All requests pass through                                  │
    │  ├── Failures are counted                                       │
    │  └── If failures >= threshold → OPEN                            │
    │                                                                 │
    └───────────────────────────┬─────────────────────────────────────┘
                                │
                    [failures >= threshold]
                                │
                                ▼
    ┌─────────────────────────────────────────────────────────────────┐
    │                                                                 │
    │  OPEN                                                           │
    │  ├── All requests fail immediately                              │
    │  ├── No calls to the protected service                          │
    │  └── After recovery_timeout → HALF_OPEN                         │
    │                                                                 │
    └───────────────────────────┬─────────────────────────────────────┘
                                │
                    [recovery_timeout elapsed]
                                │
                                ▼
    ┌─────────────────────────────────────────────────────────────────┐
    │                                                                 │
    │  HALF_OPEN                                                      │
    │  ├── Limited test requests allowed                              │
    │  ├── If test succeeds → CLOSED                                  │
    │  └── If test fails → OPEN                                       │
    │                                                                 │
    └─────────────────────────────────────────────────────────────────┘

Configuration Parameters
------------------------
- **failure_threshold**: Number of failures before opening (default: 5)
- **recovery_timeout**: Seconds before testing recovery (default: 30.0)
- **half_open_requests**: Test requests allowed in half-open (default: 3)
- **excluded_exceptions**: Exceptions that don't count as failures

Example - Basic Usage
---------------------
.. code-block:: python

    from obskit.resilience import CircuitBreaker

    # Create circuit breaker
    breaker = CircuitBreaker(
        name="payment_api",
        failure_threshold=5,
        recovery_timeout=30.0,
    )

    async def process_payment(amount: float):
        async with breaker:
            return await payment_api.charge(amount)

    # Or use as decorator
    @breaker
    async def process_payment(amount: float):
        return await payment_api.charge(amount)

Example - Handling Circuit Open
-------------------------------
.. code-block:: python

    from obskit.resilience import CircuitBreaker, CircuitOpenError

    breaker = CircuitBreaker("payment_api")

    async def process_payment(amount: float):
        try:
            async with breaker:
                return await payment_api.charge(amount)
        except CircuitOpenError:
            # Circuit is open - use fallback
            return await use_backup_payment_processor(amount)

Example - Excluded Exceptions
-----------------------------
.. code-block:: python

    from obskit.resilience import CircuitBreaker

    # These exceptions don't count as failures
    # (they're business logic, not service failures)
    breaker = CircuitBreaker(
        name="user_api",
        excluded_exceptions=[ValueError, KeyError],
    )

    @breaker
    async def get_user(user_id: str):
        user = await user_api.get(user_id)
        if not user:
            raise KeyError(f"User {user_id} not found")  # Won't trip circuit
        return user

Example - Monitoring State
--------------------------
.. code-block:: python

    breaker = CircuitBreaker("payment_api")

    # Check current state
    print(f"State: {breaker.state}")  # CLOSED, OPEN, or HALF_OPEN
    print(f"Failure count: {breaker.failure_count}")
    print(f"Is closed: {breaker.is_closed}")
    print(f"Is open: {breaker.is_open}")

    # Manual state control (for testing)
    breaker.reset()  # Force close the circuit
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import Enum
from functools import wraps
from typing import Any, ParamSpec, TypeVar

from obskit.config import get_settings
from obskit.logging import get_logger

# Type variables for generic typing
P = ParamSpec("P")
T = TypeVar("T")

# Logger for circuit breaker events
logger = get_logger("obskit.circuit_breaker")


class CircuitState(str, Enum):
    """
    Circuit breaker states.

    Attributes
    ----------
    CLOSED : str
        Normal operation - requests pass through.
    OPEN : str
        Circuit is open - requests fail immediately.
    HALF_OPEN : str
        Testing recovery - limited requests allowed.
    """

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerError(Exception):
    """
    Base exception for circuit breaker errors.

    Attributes
    ----------
    breaker_name : str
        Name of the circuit breaker that raised the error.
    """

    def __init__(self, message: str, breaker_name: str = "unknown") -> None:
        self.breaker_name = breaker_name
        super().__init__(message)


class CircuitOpenError(CircuitBreakerError):
    """
    Raised when a call is attempted on an open circuit.

    This error indicates that the circuit breaker has tripped
    and is preventing calls to the protected service.

    Example
    -------
    >>> try:
    ...     async with breaker:
    ...         result = await api.call()
    ... except CircuitOpenError as e:
    ...     print(f"Circuit {e.breaker_name} is open")
    ...     result = use_fallback()
    """

    def __init__(self, breaker_name: str, time_until_retry: float) -> None:
        self.time_until_retry = time_until_retry
        super().__init__(
            f"Circuit '{breaker_name}' is open. Retry in {time_until_retry:.1f} seconds.",
            breaker_name,
        )


@dataclass
class CircuitBreakerConfig:
    """
    Configuration for a circuit breaker.

    Attributes
    ----------
    failure_threshold : int
        Number of failures before opening the circuit.
    recovery_timeout : float
        Seconds to wait before testing recovery.
    half_open_requests : int
        Number of test requests allowed in half-open state.
    excluded_exceptions : tuple
        Exception types that don't count as failures.
    """

    failure_threshold: int = 5
    recovery_timeout: float = 30.0
    half_open_requests: int = 3
    excluded_exceptions: tuple[type[Exception], ...] = ()


class CircuitBreaker:
    """
    Circuit breaker for preventing cascading failures.

    The circuit breaker monitors failures and temporarily stops
    requests when a service is failing, giving it time to recover.

    Parameters
    ----------
    name : str
        Unique name for this circuit breaker.

    failure_threshold : int, optional
        Number of failures before opening.
        Default: from settings.

    recovery_timeout : float, optional
        Seconds before testing recovery.
        Default: from settings.

    half_open_requests : int, optional
        Test requests allowed in half-open state.
        Default: from settings.

    excluded_exceptions : tuple[type], optional
        Exceptions that don't count as failures.
        Default: empty.

    Attributes
    ----------
    name : str
        Name of this circuit breaker.

    state : CircuitState
        Current state (CLOSED, OPEN, HALF_OPEN).

    failure_count : int
        Number of consecutive failures.

    is_closed : bool
        True if circuit is closed (normal operation).

    is_open : bool
        True if circuit is open (failing fast).

    Example - Context Manager
    -------------------------
    >>> from obskit.resilience import CircuitBreaker, CircuitOpenError
    >>>
    >>> breaker = CircuitBreaker("payment_api")
    >>>
    >>> async def charge_card(amount: float):
    ...     try:
    ...         async with breaker:
    ...             return await payment_api.charge(amount)
    ...     except CircuitOpenError:
    ...         # Use fallback when circuit is open
    ...         return await backup_processor.charge(amount)

    Example - Decorator
    -------------------
    >>> breaker = CircuitBreaker("payment_api")
    >>>
    >>> @breaker
    ... async def charge_card(amount: float):
    ...     return await payment_api.charge(amount)
    >>>
    >>> # Multiple functions can share a circuit breaker
    >>> @breaker
    ... async def refund(payment_id: str):
    ...     return await payment_api.refund(payment_id)

    Example - With Excluded Exceptions
    ----------------------------------
    >>> # Don't trip circuit on validation errors
    >>> breaker = CircuitBreaker(
    ...     "user_api",
    ...     excluded_exceptions=(ValueError, KeyError),
    ... )
    >>>
    >>> @breaker
    ... async def get_user(user_id: str):
    ...     if not user_id:
    ...         raise ValueError("user_id required")  # Won't trip circuit
    ...     return await user_api.get(user_id)

    Example - Monitoring
    --------------------
    >>> breaker = CircuitBreaker("payment_api")
    >>>
    >>> # Check state
    >>> print(f"State: {breaker.state.value}")
    >>> print(f"Failures: {breaker.failure_count}")
    >>>
    >>> # State properties
    >>> if breaker.is_open:
    ...     print("Circuit is open - service is down")
    >>> elif breaker.is_closed:
    ...     print("Circuit is closed - normal operation")
    >>> else:
    ...     print("Circuit is half-open - testing recovery")

    Example - Manual Reset
    ----------------------
    >>> breaker = CircuitBreaker("payment_api")
    >>>
    >>> # Force close the circuit (e.g., after manual intervention)
    >>> breaker.reset()
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int | None = None,
        recovery_timeout: float | None = None,
        half_open_requests: int | None = None,
        excluded_exceptions: tuple[type[Exception], ...] = (),
    ) -> None:
        """
        Initialize the circuit breaker.

        Parameters
        ----------
        name : str
            Unique identifier for this circuit breaker.
        failure_threshold : int, optional
            Failures before opening. Uses settings if not provided.
        recovery_timeout : float, optional
            Recovery wait time in seconds.
        half_open_requests : int, optional
            Test requests in half-open state.
        excluded_exceptions : tuple, optional
            Exceptions that don't count as failures.
        """
        settings = get_settings()

        self.name = name
        self._failure_threshold = (
            failure_threshold
            if failure_threshold is not None
            else settings.circuit_breaker_failure_threshold
        )
        self._recovery_timeout = (
            recovery_timeout
            if recovery_timeout is not None
            else settings.circuit_breaker_recovery_timeout
        )
        self._half_open_requests = (
            half_open_requests
            if half_open_requests is not None
            else settings.circuit_breaker_half_open_requests
        )
        self._excluded_exceptions = excluded_exceptions

        # State tracking
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: float | None = None
        self._half_open_successes = 0

        # Lock for thread/async safety
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        """Get the current circuit state."""
        return self._state

    @property
    def failure_count(self) -> int:
        """Get the current failure count."""
        return self._failure_count

    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed (normal operation)."""
        return self._state == CircuitState.CLOSED

    @property
    def is_open(self) -> bool:
        """Check if circuit is open (failing fast)."""
        return self._state == CircuitState.OPEN

    @property
    def is_half_open(self) -> bool:
        """Check if circuit is half-open (testing)."""
        return self._state == CircuitState.HALF_OPEN

    def reset(self) -> None:
        """
        Reset the circuit breaker to closed state.

        This forces the circuit to close, clearing all failure counts.
        Use with caution - typically for manual intervention or testing.

        Example
        -------
        >>> breaker = CircuitBreaker("api")
        >>> # Force close after manual service restart
        >>> breaker.reset()
        """
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time = None
        self._half_open_successes = 0

        logger.info(
            "circuit_breaker_reset",
            breaker=self.name,
            new_state=self._state.value,
        )

    async def _should_allow_request(self) -> bool:
        """
        Check if a request should be allowed through.

        Returns
        -------
        bool
            True if request should proceed, False to fail fast.
        """
        async with self._lock:
            if self._state == CircuitState.CLOSED:
                return True

            if self._state == CircuitState.OPEN:
                # Check if recovery timeout has elapsed
                if self._last_failure_time is not None:  # pragma: no branch
                    elapsed = time.time() - self._last_failure_time
                    if elapsed >= self._recovery_timeout:
                        # Transition to half-open
                        self._state = CircuitState.HALF_OPEN
                        self._half_open_successes = 0

                        logger.info(
                            "circuit_breaker_half_open",
                            breaker=self.name,
                            elapsed_seconds=elapsed,
                        )
                        return True

                return False

            # HALF_OPEN - allow limited test requests
            return True

    def _get_time_until_retry(self) -> float:
        """Get seconds until next retry is allowed."""
        if self._last_failure_time is None:
            return 0.0

        elapsed = time.time() - self._last_failure_time
        return max(0.0, self._recovery_timeout - elapsed)

    async def _record_success(self) -> None:
        """Record a successful call."""
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._half_open_successes += 1

                # Check if enough successes to close
                if self._half_open_successes >= self._half_open_requests:
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0

                    logger.info(
                        "circuit_breaker_closed",
                        breaker=self.name,
                        half_open_successes=self._half_open_successes,
                    )

            elif self._state == CircuitState.CLOSED:  # pragma: no branch
                # Reset failure count on success
                self._failure_count = 0

    async def _record_failure(self, error: Exception) -> None:
        """Record a failed call."""
        async with self._lock:
            # Check if exception is excluded
            if isinstance(error, self._excluded_exceptions):
                logger.debug(
                    "circuit_breaker_excluded_exception",
                    breaker=self.name,
                    error_type=type(error).__name__,
                )
                return

            self._failure_count += 1
            self._last_failure_time = time.time()

            if self._state == CircuitState.HALF_OPEN:
                # Single failure in half-open reopens the circuit
                self._state = CircuitState.OPEN

                logger.warning(
                    "circuit_breaker_reopened",
                    breaker=self.name,
                    error=str(error),
                    error_type=type(error).__name__,
                )

            elif self._state == CircuitState.CLOSED:  # pragma: no branch
                if self._failure_count >= self._failure_threshold:
                    self._state = CircuitState.OPEN

                    logger.warning(
                        "circuit_breaker_opened",
                        breaker=self.name,
                        failure_count=self._failure_count,
                        threshold=self._failure_threshold,
                        error=str(error),
                        error_type=type(error).__name__,
                    )

    async def __aenter__(self) -> CircuitBreaker:
        """
        Enter the circuit breaker context.

        Raises
        ------
        CircuitOpenError
            If the circuit is open.
        """
        allowed = await self._should_allow_request()

        if not allowed:
            raise CircuitOpenError(
                breaker_name=self.name,
                time_until_retry=self._get_time_until_retry(),
            )

        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> bool:
        """
        Exit the circuit breaker context.

        Records success or failure based on whether an exception occurred.
        """
        if exc_val is None:
            await self._record_success()
        else:
            if isinstance(exc_val, Exception):  # pragma: no cover
                await self._record_failure(exc_val)

        # Don't suppress exceptions
        return False

    def __call__(
        self,
        func: Callable[P, Awaitable[T]],
    ) -> Callable[P, Awaitable[T]]:
        """
        Use as a decorator for async functions.

        Parameters
        ----------
        func : Callable
            The async function to protect.

        Returns
        -------
        Callable
            Wrapped function with circuit breaker protection.

        Example
        -------
        >>> breaker = CircuitBreaker("api")
        >>>
        >>> @breaker
        ... async def call_api():
        ...     return await api.request()
        """

        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            async with self:
                result = await func(*args, **kwargs)
            return result

        return wrapper


# =============================================================================
# Module-Level Circuit Breaker Registry
# =============================================================================

import threading

_circuit_breakers: dict[str, CircuitBreaker] = {}
_circuit_breakers_lock = threading.Lock()


def get_circuit_breaker(
    name: str,
    **kwargs: Any,
) -> CircuitBreaker:
    """
    Get or create a named circuit breaker.

    This factory function ensures each named circuit breaker is
    created only once, allowing you to share circuit breakers
    across modules.

    Parameters
    ----------
    name : str
        Unique name for the circuit breaker.
    **kwargs : Any
        Arguments to pass to CircuitBreaker if creating new.

    Returns
    -------
    CircuitBreaker
        The circuit breaker instance.

    Example
    -------
    >>> # In module A
    >>> breaker = get_circuit_breaker("payment_api")
    >>>
    >>> # In module B - same instance
    >>> breaker = get_circuit_breaker("payment_api")

    Thread Safety
    -------------
    This function is thread-safe using locks to protect dictionary access.
    """
    # Thread-safe dictionary access
    with _circuit_breakers_lock:
        if name not in _circuit_breakers:
            _circuit_breakers[name] = CircuitBreaker(name, **kwargs)

        return _circuit_breakers[name]


def reset_all_circuit_breakers() -> None:
    """
    Reset all circuit breakers.

    Primarily for testing.
    """
    for breaker in _circuit_breakers.values():
        breaker.reset()
