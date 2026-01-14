"""
Structured Logging for obskit
==============================

This module provides structured logging capabilities using structlog,
with automatic correlation ID injection and configurable output formats.

Why Structured Logging?
-----------------------
Traditional logs are strings that are hard to parse and query:

.. code-block:: text

    ERROR 2024-01-15 10:30:45 OrderService - Failed to create order for user 123

Structured logs are key-value pairs that are easily searchable:

.. code-block:: json

    {
        "timestamp": "2024-01-15T10:30:45.123Z",
        "level": "error",
        "event": "order_creation_failed",
        "component": "OrderService",
        "user_id": "123",
        "error": "Insufficient inventory",
        "error_type": "InventoryError",
        "correlation_id": "abc-123-def"
    }

With structured logs, you can:
- Filter: `level:error AND component:OrderService`
- Aggregate: Count errors by `error_type`
- Trace: Find all logs with `correlation_id:abc-123-def`

Features
--------
- **Automatic correlation IDs**: Logs include the current correlation ID
- **JSON output**: Machine-readable format for log aggregators
- **Console output**: Human-readable colored output for development
- **Context binding**: Add context that persists across log calls
- **Performance helpers**: Track operation timing with thresholds

Quick Start
-----------
.. code-block:: python

    from obskit import get_logger, configure

    # Configure logging
    configure(
        service_name="order-service",
        log_level="INFO",
        log_format="json",  # or "console" for development
    )

    # Get a logger
    logger = get_logger(__name__)

    # Log with structured data
    logger.info(
        "order_created",
        order_id="12345",
        user_id="user-abc",
        total=99.99,
    )

Output Formats
--------------
**JSON Format** (for production):

.. code-block:: json

    {
        "timestamp": "2024-01-15T10:30:45.123456Z",
        "level": "info",
        "event": "order_created",
        "service": "order-service",
        "order_id": "12345",
        "user_id": "user-abc",
        "total": 99.99,
        "correlation_id": "abc-123"
    }

**Console Format** (for development):

.. code-block:: text

    2024-01-15 10:30:45 [info     ] order_created    order_id=12345 user_id=user-abc total=99.99

Example - Bound Context
-----------------------
.. code-block:: python

    from obskit import get_logger

    logger = get_logger(__name__)

    # Bind context that persists across log calls
    log = logger.bind(
        request_id="req-123",
        user_id="user-abc",
    )

    # All these logs include request_id and user_id
    log.info("processing_started")
    log.info("validation_complete")
    log.info("processing_finished")

Example - Error Logging
-----------------------
.. code-block:: python

    from obskit import get_logger
    from obskit.logging import log_error

    logger = get_logger(__name__)

    try:
        process_order(order_data)
    except Exception as e:
        # Detailed error logging with stack trace
        log_error(
            error=e,
            component="OrderProcessor",
            operation="process_order",
            context={"order_id": order_data.get("id")},
        )
        raise

Example - Performance Logging
-----------------------------
.. code-block:: python

    from obskit.logging import log_performance

    # Log performance with threshold warning
    log_performance(
        operation="create_order",
        component="OrderService",
        duration_ms=350.0,
        threshold_ms=200.0,  # Warn if > 200ms
    )
    # Logs: {"event": "slow_operation", "duration_ms": 350.0, ...}

See Also
--------
obskit.core.context : Correlation ID management
obskit.decorators : Automatic logging via decorators
"""

# Import adapter system
from obskit.logging.adapters import LoggerAdapter
from obskit.logging.factory import (
    configure_logging_backend,
    get_available_backends,
    get_logger_from_factory,
    register_backend,
    reset_logging_factory,
)
from obskit.logging.logger import (
    configure_logging,
    get_logger,
    log_error,
    log_operation,
    log_performance,
)

__all__ = [
    # ==========================================================================
    # Logger Functions
    # ==========================================================================
    # Get a structlog logger instance
    "get_logger",
    # Configure the logging system
    "configure_logging",
    # ==========================================================================
    # Logging Helpers
    # ==========================================================================
    # Log operation start/completion
    "log_operation",
    # Log performance with threshold warnings
    "log_performance",
    # Log errors with full context
    "log_error",
    # ==========================================================================
    # Pluggable Logging Backend System
    # ==========================================================================
    # Base adapter class
    "LoggerAdapter",
    # Configure logging backend (structlog, loguru, auto)
    "configure_logging_backend",
    # Get available backends
    "get_available_backends",
    # Get logger from configured backend
    "get_logger_from_factory",
    # Register custom backend
    "register_backend",
    # Reset factory (for testing)
    "reset_logging_factory",
]
