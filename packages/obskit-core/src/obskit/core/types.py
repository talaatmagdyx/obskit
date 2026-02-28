"""
Type Definitions for obskit
============================

This module defines common types, type aliases, and enumerations used
throughout the obskit package. Using consistent types improves:

1. **Type safety**: Catch errors at development time with mypy/pyright
2. **Documentation**: Types serve as inline documentation
3. **IDE support**: Better autocomplete and refactoring
4. **Consistency**: Same types used across all modules

Type Aliases
------------
Type aliases provide semantic meaning to string parameters:

.. code-block:: python

    from obskit.core.types import Component, Operation, ErrorType

    def track_operation(
        component: Component,    # e.g., "OrderService"
        operation: Operation,    # e.g., "create_order"
        error_type: ErrorType,   # e.g., "ValidationError"
    ) -> None:
        ...

Enumerations
------------
Enums provide type-safe options with IDE autocomplete:

.. code-block:: python

    from obskit.core.types import MetricsMethod, Status

    # Type-safe status
    status: Status = Status.SUCCESS

    # Type-safe metrics method selection
    method: MetricsMethod = MetricsMethod.RED
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal, NewType

# MetricsMethod lives in config.py (the lowest-level module with no obskit
# imports) to avoid a circular import: config → core → __init__ → config.
# Re-export it here so `from obskit.core.types import MetricsMethod` still works.
from obskit.config import MetricsMethod as MetricsMethod

# =============================================================================
# Type Aliases
# =============================================================================
# These provide semantic meaning to string parameters while maintaining
# string compatibility for JSON serialization and logging.

# Component name (e.g., "OrderService", "PaymentProcessor", "UserRepository")
# Components represent logical parts of your application.
Component = NewType("Component", str)

# Operation name (e.g., "create_order", "process_payment", "find_user")
# Operations represent specific actions within a component.
Operation = NewType("Operation", str)

# Error type name (e.g., "ValidationError", "TimeoutError", "NotFoundError")
# Typically the exception class name.
ErrorType = NewType("ErrorType", str)


# =============================================================================
# Status Types
# =============================================================================


class Status(StrEnum):
    """
    Operation status enumeration.

    Represents the outcome of an operation for metrics and logging.
    Inherits from str for JSON serialization compatibility.

    Attributes
    ----------
    SUCCESS : str
        Operation completed successfully.

    FAILURE : str
        Operation failed with an error.

    Example
    -------
    >>> from obskit.core.types import Status
    >>>
    >>> # Use in function signature
    >>> def record_outcome(status: Status) -> None:
    ...     print(f"Operation {status.value}")
    >>>
    >>> record_outcome(Status.SUCCESS)  # "Operation success"
    >>> record_outcome(Status.FAILURE)  # "Operation failure"
    >>>
    >>> # String compatibility for JSON
    >>> import json
    >>> json.dumps({"status": Status.SUCCESS})  # '{"status": "success"}'
    """

    SUCCESS = "success"
    """Operation completed successfully."""

    FAILURE = "failure"
    """Operation failed with an error."""


# Literal type for status (alternative to enum)
StatusLiteral = Literal["success", "failure"]


# =============================================================================
# Metrics Method Types
# =============================================================================
# MetricsMethod is imported from config.py at the top of this file.
# See the import statement above for the rationale.

# =============================================================================
# Log Level Types
# =============================================================================


class LogLevel(StrEnum):
    """
    Log level enumeration.

    Standard Python logging levels as an enum for type safety.

    Attributes
    ----------
    DEBUG : str
        Detailed debugging information.
    INFO : str
        General operational information.
    WARNING : str
        Something unexpected happened.
    ERROR : str
        An error occurred.
    CRITICAL : str
        A critical failure occurred.

    Example
    -------
    >>> from obskit.core.types import LogLevel
    >>>
    >>> level = LogLevel.INFO
    >>> print(level.value)  # "INFO"
    """

    DEBUG = "DEBUG"
    """Detailed debugging information."""

    INFO = "INFO"
    """General operational information."""

    WARNING = "WARNING"
    """Something unexpected happened, or indicative of some problem."""

    ERROR = "ERROR"
    """A more serious problem has occurred."""

    CRITICAL = "CRITICAL"
    """A very serious error, program may be unable to continue."""


# Literal type for log level (alternative to enum)
LogLevelLiteral = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


# =============================================================================
# Health Status Types
# =============================================================================


class HealthStatus(StrEnum):
    """
    Health check status enumeration.

    Represents the health status of a service or component.

    Attributes
    ----------
    HEALTHY : str
        All health checks passed.
    UNHEALTHY : str
        One or more health checks failed.
    DEGRADED : str
        Some non-critical checks failed.
    UNKNOWN : str
        Health status cannot be determined.

    Example
    -------
    >>> from obskit.core.types import HealthStatus
    >>>
    >>> def check_health() -> HealthStatus:
    ...     if all_checks_pass():
    ...         return HealthStatus.HEALTHY
    ...     elif critical_checks_pass():
    ...         return HealthStatus.DEGRADED
    ...     else:
    ...         return HealthStatus.UNHEALTHY
    """

    HEALTHY = "healthy"
    """All health checks passed. Service is fully operational."""

    UNHEALTHY = "unhealthy"
    """One or more critical health checks failed."""

    DEGRADED = "degraded"
    """Some non-critical checks failed. Service is partially operational."""

    UNKNOWN = "unknown"
    """Health status cannot be determined."""


# =============================================================================
# Circuit Breaker State Types
# =============================================================================


class CircuitState(StrEnum):
    """
    Circuit breaker state enumeration.

    Represents the current state of a circuit breaker.

    Attributes
    ----------
    CLOSED : str
        Normal operation. Requests are allowed through.
    OPEN : str
        Circuit is open. Requests are blocked.
    HALF_OPEN : str
        Testing recovery. Limited requests allowed.

    State Transitions
    -----------------
    .. code-block:: text

        CLOSED ──[failures exceed threshold]──→ OPEN
           ↑                                      │
           │                           [recovery timeout]
           │                                      ↓
           └──[test requests succeed]────── HALF_OPEN
                                               │
                              [test request fails]
                                               ↓
                                             OPEN

    Example
    -------
    >>> from obskit.core.types import CircuitState
    >>>
    >>> state = CircuitState.CLOSED
    >>>
    >>> if state == CircuitState.OPEN:
    ...     raise CircuitOpenError("Circuit is open")
    """

    CLOSED = "closed"
    """
    Normal operation state.

    The circuit breaker allows all requests through.
    Failures are counted toward the threshold.
    """

    OPEN = "open"
    """
    Open/tripped state.

    The circuit breaker blocks all requests immediately.
    This prevents cascading failures to downstream services.
    After the recovery timeout, the circuit transitions to HALF_OPEN.
    """

    HALF_OPEN = "half_open"
    """
    Testing recovery state.

    A limited number of test requests are allowed through.
    If they succeed, the circuit closes.
    If any fail, the circuit opens again.
    """


# =============================================================================
# SLO Types
# =============================================================================


class SLOType(StrEnum):
    """
    Service Level Objective type enumeration.

    Represents different types of SLOs that can be tracked.

    Attributes
    ----------
    AVAILABILITY : str
        Percentage of successful requests.
    LATENCY : str
        Percentage of requests within latency threshold.
    ERROR_RATE : str
        Percentage of requests without errors.
    THROUGHPUT : str
        Minimum requests per second.

    Example
    -------
    >>> from obskit.core.types import SLOType
    >>>
    >>> slo_type = SLOType.LATENCY
    >>> target = 0.95  # 95% of requests under threshold
    """

    AVAILABILITY = "availability"
    """
    Availability SLO.

    Measures the percentage of successful requests.
    Example: 99.9% of requests should succeed.
    """

    LATENCY = "latency"
    """
    Latency SLO.

    Measures the percentage of requests completing within a threshold.
    Example: 95% of requests should complete within 200ms.
    """

    ERROR_RATE = "error_rate"
    """
    Error rate SLO.

    Measures the percentage of requests without errors.
    Example: Error rate should be below 0.1%.
    """

    THROUGHPUT = "throughput"
    """
    Throughput SLO.

    Measures the minimum requests per second.
    Example: System should handle at least 1000 RPS.
    """
