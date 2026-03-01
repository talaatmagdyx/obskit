"""
Structured Error Codes
======================

This module defines structured error codes for obskit exceptions.
Error codes enable easier alerting, documentation, and debugging.

Error Code Format
-----------------
All error codes follow the format: OBSKIT_<COMPONENT>_<ERROR>

Components:
- CONFIG: Configuration errors
- CIRCUIT: Circuit breaker errors
- RETRY: Retry errors
- RATE: Rate limiting errors
- HEALTH: Health check errors
- METRICS: Metrics errors
- TRACE: Tracing errors
- SLO: SLO tracking errors

Example
-------
>>> try:
...     async with breaker:
...         result = await api.call()
... except CircuitOpenError as e:
...     print(f"Error code: {e.code}")  # OBSKIT_CIRCUIT_OPEN
...     print(f"Retry in: {e.time_until_retry}s")
"""

from __future__ import annotations

from typing import Any


class ObskitError(Exception):
    """
    Base exception for all obskit errors.

    All obskit exceptions inherit from this class and include
    a structured error code for easier alerting and debugging.

    Attributes
    ----------
    code : str
        Structured error code (e.g., "OBSKIT_CIRCUIT_OPEN").
    message : str
        Human-readable error message.
    details : dict
        Additional context about the error.

    Example
    -------
    >>> try:
    ...     raise ObskitError("Something went wrong", code="OBSKIT_UNKNOWN")
    ... except ObskitError as e:
    ...     print(f"Code: {e.code}")
    ...     print(f"Message: {e.message}")
    """

    code: str = "OBSKIT_UNKNOWN"

    def __init__(
        self,
        message: str,
        code: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.message = message
        if code:
            self.code = code
        self.details = details or {}
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        """
        Convert error to dictionary for JSON serialization.

        Returns
        -------
        dict
            Dictionary with error details.
        """
        return {
            "code": self.code,
            "message": self.message,
            "details": self.details,
        }


# =============================================================================
# Configuration Errors
# =============================================================================


class ConfigurationError(ObskitError):
    """Configuration validation or loading error."""

    code: str = "OBSKIT_CONFIG_ERROR"


class ConfigFileNotFoundError(ConfigurationError):
    """Configuration file not found."""

    code: str = "OBSKIT_CONFIG_FILE_NOT_FOUND"


class ConfigValidationError(ConfigurationError):
    """Configuration validation failed."""

    code: str = "OBSKIT_CONFIG_VALIDATION_ERROR"


# =============================================================================
# Circuit Breaker Errors
# =============================================================================


class CircuitBreakerError(ObskitError):
    """Base exception for circuit breaker errors."""

    code: str = "OBSKIT_CIRCUIT_ERROR"

    def __init__(
        self,
        message: str,
        breaker_name: str = "unknown",
        code: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.breaker_name = breaker_name
        details = details or {}
        details["breaker_name"] = breaker_name
        super().__init__(message, code, details)


class CircuitOpenError(CircuitBreakerError):
    """
    Raised when a call is attempted on an open circuit.

    Attributes
    ----------
    breaker_name : str
        Name of the circuit breaker.
    time_until_retry : float
        Seconds until the circuit may allow a test request.
    """

    code: str = "OBSKIT_CIRCUIT_OPEN"

    def __init__(
        self,
        breaker_name: str,
        time_until_retry: float,
    ) -> None:
        self.time_until_retry = time_until_retry
        message = f"Circuit '{breaker_name}' is open. Retry in {time_until_retry:.1f} seconds."
        super().__init__(
            message,
            breaker_name=breaker_name,
            details={"time_until_retry": time_until_retry},
        )


class CircuitHalfOpenError(CircuitBreakerError):
    """Raised when half-open circuit exceeds allowed test requests."""

    code: str = "OBSKIT_CIRCUIT_HALF_OPEN"


# =============================================================================
# Retry Errors
# =============================================================================


class RetryError(ObskitError):
    """
    Raised when all retry attempts are exhausted.

    Attributes
    ----------
    attempts : int
        Number of attempts made.
    last_exception : Exception | None
        The last exception that caused the retry.
    """

    code: str = "OBSKIT_RETRY_EXHAUSTED"

    def __init__(
        self,
        message: str,
        attempts: int = 0,
        last_exception: Exception | None = None,
    ) -> None:
        self.attempts = attempts
        self.last_exception = last_exception
        details: dict[str, Any] = {"attempts": attempts}
        if last_exception:
            details["last_error"] = str(last_exception)
            details["last_error_type"] = type(last_exception).__name__
        super().__init__(message, details=details)


# =============================================================================
# Rate Limiting Errors
# =============================================================================


class RateLimitError(ObskitError):
    """Base exception for rate limiting errors."""

    code: str = "OBSKIT_RATE_LIMIT_ERROR"


class RateLimitExceeded(RateLimitError):
    """
    Raised when rate limit is exceeded.

    Attributes
    ----------
    limit : int
        The rate limit that was exceeded.
    window_seconds : float
        The time window for the rate limit.
    retry_after : float | None
        Seconds until the rate limit resets.
    """

    code: str = "OBSKIT_RATE_LIMIT_EXCEEDED"

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        limit: int = 0,
        window_seconds: float = 0.0,
        retry_after: float | None = None,
    ) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self.retry_after = retry_after
        details = {
            "limit": limit,
            "window_seconds": window_seconds,
        }
        if retry_after is not None:
            details["retry_after"] = retry_after
        super().__init__(message, details=details)


# =============================================================================
# Health Check Errors
# =============================================================================


class HealthCheckError(ObskitError):
    """Base exception for health check errors."""

    code: str = "OBSKIT_HEALTH_ERROR"


class HealthCheckTimeoutError(HealthCheckError):
    """Health check timed out."""

    code: str = "OBSKIT_HEALTH_TIMEOUT"


class HealthCheckFailedError(HealthCheckError):
    """Health check failed."""

    code: str = "OBSKIT_HEALTH_FAILED"


# =============================================================================
# Metrics Errors
# =============================================================================


class MetricsError(ObskitError):
    """Base exception for metrics errors."""

    code: str = "OBSKIT_METRICS_ERROR"


class MetricsQueueFullError(MetricsError):
    """Metrics queue is full, metrics are being dropped."""

    code: str = "OBSKIT_METRICS_QUEUE_FULL"


class MetricsExportError(MetricsError):
    """Failed to export metrics."""

    code: str = "OBSKIT_METRICS_EXPORT_ERROR"


# =============================================================================
# Tracing Errors
# =============================================================================


class TracingError(ObskitError):
    """Base exception for tracing errors."""

    code: str = "OBSKIT_TRACE_ERROR"


class TracingExportError(TracingError):
    """Failed to export traces."""

    code: str = "OBSKIT_TRACE_EXPORT_ERROR"


class TracingNotConfiguredError(TracingError):
    """Tracing is not configured."""

    code: str = "OBSKIT_TRACE_NOT_CONFIGURED"


# =============================================================================
# SLO Errors
# =============================================================================


class SLOError(ObskitError):
    """Base exception for SLO errors."""

    code: str = "OBSKIT_SLO_ERROR"


class SLONotFoundError(SLOError):
    """SLO with the given name was not found."""

    code: str = "OBSKIT_SLO_NOT_FOUND"


class SLOBudgetExhaustedError(SLOError):
    """SLO error budget has been exhausted."""

    code: str = "OBSKIT_SLO_BUDGET_EXHAUSTED"


# =============================================================================
# Error Code Registry
# =============================================================================

ERROR_CODES: dict[str, type[ObskitError]] = {
    "OBSKIT_UNKNOWN": ObskitError,
    "OBSKIT_CONFIG_ERROR": ConfigurationError,
    "OBSKIT_CONFIG_FILE_NOT_FOUND": ConfigFileNotFoundError,
    "OBSKIT_CONFIG_VALIDATION_ERROR": ConfigValidationError,
    "OBSKIT_CIRCUIT_ERROR": CircuitBreakerError,
    "OBSKIT_CIRCUIT_OPEN": CircuitOpenError,
    "OBSKIT_CIRCUIT_HALF_OPEN": CircuitHalfOpenError,
    "OBSKIT_RETRY_EXHAUSTED": RetryError,
    "OBSKIT_RATE_LIMIT_ERROR": RateLimitError,
    "OBSKIT_RATE_LIMIT_EXCEEDED": RateLimitExceeded,
    "OBSKIT_HEALTH_ERROR": HealthCheckError,
    "OBSKIT_HEALTH_TIMEOUT": HealthCheckTimeoutError,
    "OBSKIT_HEALTH_FAILED": HealthCheckFailedError,
    "OBSKIT_METRICS_ERROR": MetricsError,
    "OBSKIT_METRICS_QUEUE_FULL": MetricsQueueFullError,
    "OBSKIT_METRICS_EXPORT_ERROR": MetricsExportError,
    "OBSKIT_TRACE_ERROR": TracingError,
    "OBSKIT_TRACE_EXPORT_ERROR": TracingExportError,
    "OBSKIT_TRACE_NOT_CONFIGURED": TracingNotConfiguredError,
    "OBSKIT_SLO_ERROR": SLOError,
    "OBSKIT_SLO_NOT_FOUND": SLONotFoundError,
    "OBSKIT_SLO_BUDGET_EXHAUSTED": SLOBudgetExhaustedError,
}


def get_error_class(code: str) -> type[ObskitError]:
    """
    Get the error class for a given error code.

    Parameters
    ----------
    code : str
        The error code.

    Returns
    -------
    type[ObskitError]
        The error class for the code.
    """
    return ERROR_CODES.get(code, ObskitError)
