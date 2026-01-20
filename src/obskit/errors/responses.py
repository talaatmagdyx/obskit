"""
Structured Error Responses
==========================

Standardized error responses with trace context for debugging.

Example
-------
>>> from obskit.errors import (
...     create_error_response,
...     ObservableError,
...     format_exception,
... )
>>>
>>> # Create structured error response
>>> try:
...     process_order(data)
... except Exception as e:
...     response = create_error_response(e, include_trace_id=True)
...     # {'error': 'Invalid order', 'error_type': 'ValidationError',
...     #  'trace_id': 'abc123', 'correlation_id': 'xyz789'}
>>>
>>> # Use ObservableError for custom errors
>>> raise ObservableError(
...     message="Payment failed",
...     code="PAYMENT_FAILED",
...     details={"amount": 100},
... )
"""

from __future__ import annotations

import traceback
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from obskit.core import get_correlation_id


@dataclass
class ErrorResponse:
    """Structured error response."""

    error: str
    error_type: str
    code: str | None = None
    details: dict[str, Any] | None = None
    trace_id: str | None = None
    span_id: str | None = None
    correlation_id: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    stack_trace: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary, excluding None values."""
        result = {
            "error": self.error,
            "error_type": self.error_type,
        }

        if self.code:
            result["code"] = self.code
        if self.details:
            result["details"] = self.details
        if self.trace_id:
            result["trace_id"] = self.trace_id
        if self.span_id:
            result["span_id"] = self.span_id
        if self.correlation_id:
            result["correlation_id"] = self.correlation_id
        if self.timestamp:
            result["timestamp"] = self.timestamp
        if self.stack_trace:
            result["stack_trace"] = self.stack_trace

        return result


class ObservableError(Exception):
    """
    Base exception class with observability support.

    Use this as a base for custom exceptions that should include
    trace context and structured error information.

    Example
    -------
    >>> class PaymentError(ObservableError):
    ...     pass
    >>>
    >>> raise PaymentError(
    ...     message="Payment declined",
    ...     code="PAYMENT_DECLINED",
    ...     details={"reason": "insufficient_funds"},
    ...     http_status=402,
    ... )
    """

    def __init__(
        self,
        message: str,
        code: str | None = None,
        details: dict[str, Any] | None = None,
        http_status: int = 500,
        cause: Exception | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code or type(self).__name__.upper()
        self.details = details or {}
        self.http_status = http_status
        self.cause = cause

        # Capture trace context at creation time
        self.trace_id = self._get_trace_id()
        self.span_id = self._get_span_id()
        self.correlation_id = get_correlation_id()

    def _get_trace_id(self) -> str | None:
        try:
            from opentelemetry import trace

            span = trace.get_current_span()
            if span and span.get_span_context().is_valid:
                return format(span.get_span_context().trace_id, "032x")
        except Exception:
            pass  # OpenTelemetry not available or no active span
        return None

    def _get_span_id(self) -> str | None:
        try:
            from opentelemetry import trace

            span = trace.get_current_span()
            if span and span.get_span_context().is_valid:
                return format(span.get_span_context().span_id, "016x")
        except Exception:
            pass  # OpenTelemetry not available or no active span
        return None

    def to_response(
        self,
        include_stack_trace: bool = False,
    ) -> ErrorResponse:
        """Convert to ErrorResponse."""
        return ErrorResponse(
            error=self.message,
            error_type=type(self).__name__,
            code=self.code,
            details=self.details,
            trace_id=self.trace_id,
            span_id=self.span_id,
            correlation_id=self.correlation_id,
            stack_trace=traceback.format_exception(type(self), self, self.__traceback__)
            if include_stack_trace
            else None,
        )

    def to_dict(self, include_stack_trace: bool = False) -> dict[str, Any]:
        """Convert to dictionary."""
        return self.to_response(include_stack_trace).to_dict()


# Common error classes
class ValidationError(ObservableError):
    """Error for validation failures."""

    def __init__(self, message: str, field: str | None = None, **kwargs):
        details = kwargs.pop("details", {})
        if field:
            details["field"] = field
        super().__init__(
            message, code="VALIDATION_ERROR", details=details, http_status=400, **kwargs
        )


class NotFoundError(ObservableError):
    """Error for resource not found."""

    def __init__(self, resource: str, identifier: Any = None, **kwargs):
        message = f"{resource} not found"
        if identifier:
            message = f"{resource} '{identifier}' not found"
        details = kwargs.pop("details", {})
        details["resource"] = resource
        if identifier:
            details["identifier"] = str(identifier)
        super().__init__(message, code="NOT_FOUND", details=details, http_status=404, **kwargs)


class AuthenticationError(ObservableError):
    """Error for authentication failures."""

    def __init__(self, message: str = "Authentication required", **kwargs):
        super().__init__(message, code="AUTHENTICATION_ERROR", http_status=401, **kwargs)


class AuthorizationError(ObservableError):
    """Error for authorization failures."""

    def __init__(self, message: str = "Access denied", **kwargs):
        super().__init__(message, code="AUTHORIZATION_ERROR", http_status=403, **kwargs)


class RateLimitError(ObservableError):
    """Error for rate limit exceeded."""

    def __init__(
        self, message: str = "Rate limit exceeded", retry_after: int | None = None, **kwargs
    ):
        details = kwargs.pop("details", {})
        if retry_after:
            details["retry_after"] = retry_after
        super().__init__(
            message, code="RATE_LIMIT_EXCEEDED", details=details, http_status=429, **kwargs
        )


class ServiceUnavailableError(ObservableError):
    """Error for service unavailable."""

    def __init__(self, message: str = "Service temporarily unavailable", **kwargs):
        super().__init__(message, code="SERVICE_UNAVAILABLE", http_status=503, **kwargs)


class CircuitOpenError(ObservableError):
    """Error when circuit breaker is open."""

    def __init__(self, service: str = "service", **kwargs):
        message = f"Circuit breaker open for {service}"
        details = kwargs.pop("details", {})
        details["service"] = service
        super().__init__(message, code="CIRCUIT_OPEN", details=details, http_status=503, **kwargs)


def create_error_response(
    exception: Exception,
    include_trace_id: bool = True,
    include_correlation_id: bool = True,
    include_stack_trace: bool = False,
    code: str | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Create a structured error response from an exception.

    Parameters
    ----------
    exception : Exception
        The exception to convert.
    include_trace_id : bool
        Include trace ID (default: True).
    include_correlation_id : bool
        Include correlation ID (default: True).
    include_stack_trace : bool
        Include stack trace (default: False, for security).
    code : str, optional
        Override error code.
    details : dict, optional
        Additional details.

    Returns
    -------
    dict
        Structured error response.

    Example
    -------
    >>> try:
    ...     process_order(data)
    ... except Exception as e:
    ...     response = create_error_response(e)
    ...     return jsonify(response), 500
    """
    # Handle ObservableError specially
    if isinstance(exception, ObservableError):
        response = exception.to_response(include_stack_trace)
        if code:
            response.code = code
        if details:
            response.details = {**(response.details or {}), **details}
        return response.to_dict()

    # Build response for regular exceptions
    error_type = type(exception).__name__
    error_message = str(exception) or error_type

    response = ErrorResponse(
        error=error_message,
        error_type=error_type,
        code=code or error_type.upper(),
        details=details,
    )

    # Add trace ID
    if include_trace_id:
        try:
            from opentelemetry import trace

            span = trace.get_current_span()
            if span and span.get_span_context().is_valid:
                response.trace_id = format(span.get_span_context().trace_id, "032x")
                response.span_id = format(span.get_span_context().span_id, "016x")
        except Exception:
            pass  # OpenTelemetry not available or no active span

    # Add correlation ID
    if include_correlation_id:
        response.correlation_id = get_correlation_id()

    # Add stack trace
    if include_stack_trace:
        response.stack_trace = traceback.format_exception(
            type(exception), exception, exception.__traceback__
        )

    return response.to_dict()


def format_exception(
    exception: Exception,
    max_frames: int = 10,
) -> str:
    """
    Format exception with trace context for logging.

    Parameters
    ----------
    exception : Exception
        Exception to format.
    max_frames : int
        Maximum stack frames to include.

    Returns
    -------
    str
        Formatted exception string.
    """
    lines = []

    # Add trace context
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        if span and span.get_span_context().is_valid:
            trace_id = format(span.get_span_context().trace_id, "032x")
            lines.append(f"[trace_id={trace_id}]")
    except Exception:
        pass  # OpenTelemetry not available or no active span

    correlation_id = get_correlation_id()
    if correlation_id:
        lines.append(f"[correlation_id={correlation_id}]")

    # Add exception info
    lines.append(f"{type(exception).__name__}: {exception}")

    # Add stack trace
    tb_lines = traceback.format_exception(type(exception), exception, exception.__traceback__)
    if max_frames and len(tb_lines) > max_frames:
        tb_lines = tb_lines[:max_frames] + ["... truncated ..."]
    lines.extend(tb_lines)

    return "\n".join(lines)


__all__ = [
    # Response types
    "ErrorResponse",
    # Base error
    "ObservableError",
    # Common errors
    "ValidationError",
    "NotFoundError",
    "AuthenticationError",
    "AuthorizationError",
    "RateLimitError",
    "ServiceUnavailableError",
    "CircuitOpenError",
    # Functions
    "create_error_response",
    "format_exception",
]
