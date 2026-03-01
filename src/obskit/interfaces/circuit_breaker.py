"""
Circuit Breaker Interface - Abstract Base Class for Circuit Breakers
=====================================================================

This module defines the contract for circuit breaker implementations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from types import TracebackType


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation, requests pass through
    OPEN = "open"  # Failing, requests are rejected
    HALF_OPEN = "half_open"  # Testing recovery


class CircuitBreakerInterface(ABC):
    """
    Abstract base class for circuit breakers.

    Circuit breakers prevent cascading failures by detecting when a service
    is failing and temporarily stopping requests to it.

    Attributes
    ----------
    name : str
        Unique name for the circuit breaker.
    state : CircuitState
        Current state of the circuit.
    failure_count : int
        Number of consecutive failures.
    is_closed : bool
        Whether the circuit is closed (normal operation).
    is_open : bool
        Whether the circuit is open (failing fast).

    Example
    -------
    >>> class MyCircuitBreaker(CircuitBreakerInterface):
    ...     async def __aenter__(self):
    ...         if self.is_open:
    ...             raise CircuitOpenError("Circuit is open")
    ...         return self
    ...
    ...     async def __aexit__(self, exc_type, exc_val, exc_tb):
    ...         if exc_val:
    ...             self._record_failure()
    ...         else:
    ...             self._record_success()
    ...         return False
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Get the circuit breaker name."""

    @property
    @abstractmethod
    def state(self) -> CircuitState:
        """Get the current circuit state."""

    @property
    @abstractmethod
    def failure_count(self) -> int:
        """Get the current failure count."""

    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed (normal operation)."""
        return self.state == CircuitState.CLOSED

    @property
    def is_open(self) -> bool:
        """Check if circuit is open (failing fast)."""
        return self.state == CircuitState.OPEN

    @property
    def is_half_open(self) -> bool:
        """Check if circuit is half-open (testing recovery)."""
        return self.state == CircuitState.HALF_OPEN

    @abstractmethod
    async def __aenter__(self) -> CircuitBreakerInterface:
        """
        Enter the circuit breaker context.

        Raises
        ------
        CircuitOpenError
            If the circuit is open.

        Returns
        -------
        CircuitBreakerInterface
            Self for use in async with statement.
        """

    @abstractmethod
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool:
        """
        Exit the circuit breaker context.

        Records success or failure based on whether an exception occurred.

        Parameters
        ----------
        exc_type : type[BaseException] | None
            Exception type if an exception was raised.
        exc_val : BaseException | None
            Exception instance if an exception was raised.
        exc_tb : TracebackType | None
            Traceback if an exception was raised.

        Returns
        -------
        bool
            False to propagate exceptions.
        """

    @abstractmethod
    def reset(self) -> None:
        """
        Reset the circuit breaker to closed state.

        Clears failure counts and resets state to CLOSED.
        """

    @abstractmethod
    def get_stats(self) -> dict[str, Any]:
        """
        Get circuit breaker statistics.

        Returns
        -------
        dict[str, Any]
            Statistics including state, failure count, last failure time, etc.
        """
