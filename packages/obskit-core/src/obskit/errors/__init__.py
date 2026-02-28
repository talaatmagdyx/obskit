"""
Structured Error Responses
==========================

Standardized error responses with trace context.

Example
-------
>>> from obskit.errors import create_error_response, ObservableError
>>>
>>> # Create error response from exception
>>> try:
...     do_something()
... except Exception as e:
...     response = create_error_response(e, include_trace_id=True)
>>>
>>> # Use ObservableError for custom errors
>>> raise ValidationError("Invalid email", field="email")
"""

from obskit.errors.responses import (
    AuthenticationError,
    AuthorizationError,
    CircuitOpenError,
    # Response types
    ErrorResponse,
    NotFoundError,
    # Base error
    ObservableError,
    RateLimitError,
    ServiceUnavailableError,
    # Common errors
    ValidationError,
    # Functions
    create_error_response,
    format_exception,
)

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
