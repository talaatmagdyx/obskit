"""
Core Module for obskit
======================

This module provides fundamental utilities used across the obskit package:

- **Context Propagation**: Correlation ID management using contextvars
- **Type Definitions**: Common types and protocols
- **Constants**: Shared constants and defaults

Context Propagation
-------------------
Context propagation ensures that correlation IDs and other contextual
information flow through your application, even across async boundaries.

.. code-block:: python

    from obskit.core import correlation_context, get_correlation_id

    async def handle_request(request):
        # Create a new correlation context for this request
        async with correlation_context():
            # All logs and traces within this context share the same ID
            correlation_id = get_correlation_id()
            print(f"Processing request with correlation_id: {correlation_id}")

            # Call other functions - they'll have the same correlation ID
            await process_data(request.data)
            await send_notification()

How Correlation IDs Work
------------------------
Correlation IDs link all logs, traces, and metrics for a single request:

.. code-block:: text

    Request arrives → Generate correlation ID (e.g., "req-abc123")
                   ↓
    ┌─────────────────────────────────────────────────────────┐
    │ All operations within this request use "req-abc123"     │
    │                                                         │
    │ Log 1: {"correlation_id": "req-abc123", "event": "..."}│
    │ Log 2: {"correlation_id": "req-abc123", "event": "..."}│
    │ Trace span: trace_id=..., correlation_id="req-abc123"  │
    │ Downstream API call: X-Correlation-ID: req-abc123      │
    └─────────────────────────────────────────────────────────┘

Example - Full Request Tracing
------------------------------
.. code-block:: python

    from obskit.core import (
        correlation_context,
        get_correlation_id,
        set_correlation_id,
    )
    from obskit import get_logger

    logger = get_logger(__name__)

    async def handle_request(request):
        # Check if client provided a correlation ID
        client_correlation_id = request.headers.get("X-Correlation-ID")

        async with correlation_context(client_correlation_id):
            logger.info("request_started", path=request.path)

            # Process the request
            result = await business_logic(request)

            # Include correlation ID in response
            response.headers["X-Correlation-ID"] = get_correlation_id()

            logger.info("request_completed", status=200)
            return response

    async def business_logic(request):
        # Same correlation ID is automatically available here
        logger.info("processing_business_logic")

        # Pass to downstream services
        response = await http_client.get(
            "https://api.example.com/data",
            headers={"X-Correlation-ID": get_correlation_id()},
        )

        return response.json()

See Also
--------
obskit.logging : Structured logging with automatic correlation ID injection
obskit.tracing : Distributed tracing with correlation ID support
"""

from typing import Any

from obskit.core.context import (
    async_correlation_context,
    correlation_context,
    get_correlation_id,
    set_correlation_id,
)
from obskit.core.types import (
    Component,
    ErrorType,
    MetricsMethod,
    Operation,
    Status,
)

# Note: batch_context, deprecation, and errors are imported lazily to avoid
# circular imports. They are exported from the main obskit package.

__all__ = [
    # ==========================================================================
    # Context Propagation
    # ==========================================================================
    "get_correlation_id",
    "set_correlation_id",
    "correlation_context",
    "async_correlation_context",
    # ==========================================================================
    # Type Definitions
    # ==========================================================================
    "Component",
    "Operation",
    "Status",
    "ErrorType",
    "MetricsMethod",
]


def __getattr__(name: str) -> Any:
    """Lazy loading for modules that might cause circular imports."""
    if name in (
        "batch_job_context",
        "capture_context",
        "create_task_with_context",
        "get_batch_job_context",
        "propagate_to_executor",
        "propagate_to_task",
        "restore_context",
    ):
        from obskit.core import batch_context

        return getattr(batch_context, name)

    if name in (
        "deprecated",
        "deprecated_class",
        "deprecated_parameter",
        "warn_deprecated",
        "ObskitDeprecationWarning",
    ):
        from obskit.core import deprecation

        return getattr(deprecation, name)

    if name in (
        "ObskitError",
        "ConfigurationError",
        "ConfigFileNotFoundError",
        "ConfigValidationError",
        "CircuitBreakerError",
        "CircuitOpenError",
        "RetryError",
        "RateLimitError",
        "RateLimitExceeded",
        "HealthCheckError",
        "MetricsError",
        "TracingError",
        "SLOError",
    ):
        from obskit.core import errors

        return getattr(errors, name)

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
