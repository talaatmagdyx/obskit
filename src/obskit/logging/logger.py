"""
Logger Implementation
=====================

This module implements structured logging using structlog with:
- Automatic correlation ID injection
- Configurable JSON/console output
- Performance tracking helpers
- Error logging with context

structlog Overview
------------------
structlog is a structured logging library that provides:

1. **Processors**: Transform log events (add timestamp, format output)
2. **Loggers**: Interfaces for emitting log events
3. **Context**: Bound variables that persist across log calls

The processing pipeline looks like:

.. code-block:: text

    logger.info("event", key=value)
           │
           ▼
    ┌─────────────────┐
    │ Processor 1     │  (add timestamp)
    └────────┬────────┘
             │
             ▼
    ┌─────────────────┐
    │ Processor 2     │  (add correlation_id)
    └────────┬────────┘
             │
             ▼
    ┌─────────────────┐
    │ Processor 3     │  (format as JSON)
    └────────┬────────┘
             │
             ▼
    Output to stdout/stderr
"""

from __future__ import annotations

import logging
import random
import sys
from typing import Any

import structlog
from structlog.types import EventDict, WrappedLogger

from obskit.config import get_settings
from obskit.core.context import get_correlation_id

# =============================================================================
# Configuration State
# =============================================================================

_logging_configured: bool = False


def reset_logging() -> None:
    """Reset logging configuration for testing."""
    global _logging_configured
    _logging_configured = False


# =============================================================================
# Custom Processors
# =============================================================================


def sample_log(
    logger: WrappedLogger,
    method_name: str,
    event_dict: EventDict,
) -> EventDict | None:
    """
    Processor that samples logs based on log_sample_rate setting.

    Always logs errors (ERROR, CRITICAL) regardless of sample rate.
    Other log levels are sampled based on configuration.

    Parameters
    ----------
    logger : WrappedLogger
        The wrapped logger instance.
    method_name : str
        The name of the log method (info, error, etc.).
    event_dict : EventDict
        The event dictionary being processed.

    Returns
    -------
    EventDict or None
        The event dictionary if log should be emitted, None to drop.
    """
    settings = get_settings()

    # Always log errors (not sampled)
    if method_name in ("error", "critical", "exception"):
        return event_dict

    # Apply sampling for other log levels
    # nosec B311 - random is used for log sampling, not security
    if (
        settings.log_sample_rate < 1.0 and random.random() > settings.log_sample_rate  # nosec B311
    ):  # pragma: no branch
        return None  # Drop this log entry  # pragma: no cover

    return event_dict


def add_correlation_id(
    logger: WrappedLogger,
    method_name: str,
    event_dict: EventDict,
) -> EventDict:
    """
    Processor that adds the current correlation ID to log events.

    This processor retrieves the correlation ID from the context
    and adds it to every log entry automatically.

    Parameters
    ----------
    logger : WrappedLogger
        The wrapped logger instance.
    method_name : str
        The name of the log method (info, error, etc.).
    event_dict : EventDict
        The event dictionary being processed.

    Returns
    -------
    EventDict
        The event dictionary with correlation_id added.

    Example
    -------
    >>> # This processor is added automatically during configure_logging()
    >>> # It adds correlation_id to every log entry:
    >>> # {"event": "test", "correlation_id": "abc-123", ...}
    """
    # Get correlation ID from context (thread/task-safe)
    correlation_id = get_correlation_id()

    # Only add if we have one
    if correlation_id is not None:  # pragma: no branch
        event_dict["correlation_id"] = correlation_id  # pragma: no cover

    return event_dict


def add_service_info(
    logger: WrappedLogger,
    method_name: str,
    event_dict: EventDict,
) -> EventDict:
    """
    Processor that adds service information to log events.

    Adds service_name, environment, and version from settings.

    Parameters
    ----------
    logger : WrappedLogger
        The wrapped logger instance.
    method_name : str
        The name of the log method.
    event_dict : EventDict
        The event dictionary being processed.

    Returns
    -------
    EventDict
        The event dictionary with service info added.
    """
    settings = get_settings()

    event_dict["service"] = settings.service_name
    event_dict["environment"] = settings.environment
    event_dict["version"] = settings.version

    return event_dict


def add_log_level(
    logger: WrappedLogger,
    method_name: str,
    event_dict: EventDict,
) -> EventDict:
    """
    Processor that adds a clean log level field.

    Adds 'level' with lowercase log level name.

    Parameters
    ----------
    logger : WrappedLogger
        The wrapped logger instance.
    method_name : str
        The name of the log method (info, error, etc.).
    event_dict : EventDict
        The event dictionary being processed.

    Returns
    -------
    EventDict
        The event dictionary with level added.
    """
    event_dict["level"] = method_name.lower()
    return event_dict


# =============================================================================
# Configuration
# =============================================================================


def configure_logging() -> None:
    """
    Configure the structlog logging system.

    This function sets up structlog with appropriate processors
    based on the current settings. It should be called once at
    application startup, typically via obskit.configure().

    Configuration options (from settings):

    - **log_level**: Minimum log level (DEBUG, INFO, WARNING, ERROR)
    - **log_format**: Output format ("json" or "console")
    - **log_include_timestamp**: Whether to add timestamps

    Example
    -------
    >>> from obskit.logging.logger import configure_logging
    >>>
    >>> # Usually called automatically by obskit.configure()
    >>> configure_logging()
    >>>
    >>> # Now logging is configured
    >>> logger = get_logger(__name__)
    >>> logger.info("test")

    Notes
    -----
    - Called automatically by obskit.configure()
    - Can be called multiple times safely (idempotent)
    - Must be called before logging for proper formatting
    """
    global _logging_configured

    settings = get_settings()

    # =================================================================
    # Build processor chain
    # =================================================================
    # Processors are applied in order to each log event

    processors: list[Any] = [
        # Add log level as a field
        add_log_level,
        # Add service information
        add_service_info,
        # Add correlation ID from context
        add_correlation_id,
        # Apply log sampling (must be after correlation ID for context)
        sample_log,
        # Handle exception info
        structlog.processors.format_exc_info,
        # Add timestamp if enabled
        *(
            [structlog.processors.TimeStamper(fmt="iso")] if settings.log_include_timestamp else []
        ),  # pragma: no branch
        # Stack info for exceptions
        structlog.processors.StackInfoRenderer(),
        # Unicode handling
        structlog.processors.UnicodeDecoder(),
    ]

    # =================================================================
    # Add format-specific final processor
    # =================================================================
    if settings.log_format == "json":
        # JSON format for production/log aggregation
        processors.append(structlog.processors.JSONRenderer())
    else:  # pragma: no cover
        # Console format for development
        processors.append(structlog.dev.ConsoleRenderer(colors=True))

    # =================================================================
    # Configure structlog
    # =================================================================
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.log_level.upper())
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # =================================================================
    # Configure standard library logging (for third-party libs)
    # =================================================================
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level.upper()),
    )

    _logging_configured = True


def get_logger(name: str | None = None) -> Any:
    """
    Get a structured logger instance.

    Returns a structlog BoundLogger that provides structured logging
    with automatic correlation ID injection and configured formatting.

    Parameters
    ----------
    name : str, optional
        Logger name, typically __name__.
        If not provided, uses "obskit".

    Returns
    -------
    structlog.BoundLogger
        A configured structured logger.

    Example - Basic Usage
    ---------------------
    >>> from obskit import get_logger
    >>>
    >>> logger = get_logger(__name__)
    >>>
    >>> # Simple log
    >>> logger.info("user_logged_in", user_id="123")
    >>>
    >>> # With multiple fields
    >>> logger.info(
    ...     "order_created",
    ...     order_id="ord-456",
    ...     user_id="123",
    ...     total=99.99,
    ...     items=["widget", "gadget"],
    ... )

    Example - Bound Context
    -----------------------
    >>> logger = get_logger(__name__)
    >>>
    >>> # Create logger with bound context
    >>> request_logger = logger.bind(
    ...     request_id="req-abc",
    ...     user_id="user-123",
    ... )
    >>>
    >>> # All logs include request_id and user_id
    >>> request_logger.info("processing_started")
    >>> request_logger.info("validation_complete")
    >>> request_logger.debug("cache_miss", key="user:123")
    >>> request_logger.info("processing_complete")

    Example - Error Logging
    -----------------------
    >>> logger = get_logger(__name__)
    >>>
    >>> try:
    ...     result = process_data(data)
    ... except Exception as e:
    ...     logger.error(
    ...         "processing_failed",
    ...         error=str(e),
    ...         error_type=type(e).__name__,
    ...         exc_info=True,  # Include stack trace
    ...     )
    ...     raise

    Example - Different Log Levels
    ------------------------------
    >>> logger = get_logger(__name__)
    >>>
    >>> # Debug: Detailed debugging info
    >>> logger.debug("cache_lookup", key="user:123", hit=False)
    >>>
    >>> # Info: General operational info
    >>> logger.info("user_logged_in", user_id="123")
    >>>
    >>> # Warning: Something unexpected
    >>> logger.warning("rate_limit_approaching", current=95, limit=100)
    >>>
    >>> # Error: Something failed
    >>> logger.error("payment_failed", order_id="456", reason="declined")
    >>>
    >>> # Critical: System-level failure
    >>> logger.critical("database_connection_lost", host="db.example.com")

    Notes
    -----
    - Logger is configured automatically on first use
    - Correlation IDs are injected automatically
    - Use .bind() to add persistent context
    - Use exc_info=True to include stack traces
    """
    # Ensure logging is configured
    if not _logging_configured:
        configure_logging()

    # Get or create logger
    return structlog.get_logger(name or "obskit")


# =============================================================================
# Logging Helper Functions
# =============================================================================


def log_operation(
    operation: str,
    component: str,
    status: str = "success",
    duration_ms: float | None = None,
    **context: Any,
) -> None:
    """
    Log an operation completion with status and timing.

    This helper provides a consistent format for logging operation
    outcomes across your application.

    Parameters
    ----------
    operation : str
        Name of the operation (e.g., "create_order").

    component : str
        Component that performed the operation (e.g., "OrderService").

    status : str, default="success"
        Operation status ("success" or "failure").

    duration_ms : float, optional
        Operation duration in milliseconds.

    **context : Any
        Additional context to include in the log.

    Example
    -------
    >>> from obskit.logging import log_operation
    >>>
    >>> # Log successful operation
    >>> log_operation(
    ...     operation="create_order",
    ...     component="OrderService",
    ...     status="success",
    ...     duration_ms=45.2,
    ...     order_id="ord-123",
    ... )
    >>>
    >>> # Log failed operation
    >>> log_operation(
    ...     operation="create_order",
    ...     component="OrderService",
    ...     status="failure",
    ...     duration_ms=12.5,
    ...     error="Validation failed",
    ... )
    """
    logger = get_logger("obskit.operations")

    log_data = {
        "operation": operation,
        "component": component,
        "status": status,
        **context,
    }

    if duration_ms is not None:
        log_data["duration_ms"] = round(duration_ms, 3)

    if status == "success":
        logger.info("operation_completed", **log_data)
    else:
        logger.warning("operation_failed", **log_data)


def log_performance(
    operation: str,
    component: str,
    duration_ms: float,
    threshold_ms: float | None = None,
    **context: Any,
) -> None:
    """
    Log performance metrics with optional threshold warnings.

    This helper logs operation timing and warns when duration
    exceeds the specified threshold.

    Parameters
    ----------
    operation : str
        Name of the operation.

    component : str
        Component that performed the operation.

    duration_ms : float
        Operation duration in milliseconds.

    threshold_ms : float, optional
        Performance threshold in milliseconds.
        If duration exceeds this, a warning is logged.

    **context : Any
        Additional context to include.

    Example
    -------
    >>> from obskit.logging import log_performance
    >>>
    >>> # Log performance (no warning)
    >>> log_performance(
    ...     operation="search",
    ...     component="SearchService",
    ...     duration_ms=45.0,
    ...     threshold_ms=200.0,
    ... )
    >>> # Output: {"event": "performance", "duration_ms": 45.0, ...}
    >>>
    >>> # Log slow operation (triggers warning)
    >>> log_performance(
    ...     operation="search",
    ...     component="SearchService",
    ...     duration_ms=350.0,
    ...     threshold_ms=200.0,
    ... )
    >>> # Output: {"event": "slow_operation", "duration_ms": 350.0,
    >>> #          "threshold_ms": 200.0, "exceeded_by_ms": 150.0, ...}
    """
    logger = get_logger("obskit.performance")

    log_data = {
        "operation": operation,
        "component": component,
        "duration_ms": round(duration_ms, 3),
        **context,
    }

    # Check threshold
    if threshold_ms is not None and duration_ms > threshold_ms:
        log_data["threshold_ms"] = threshold_ms
        log_data["exceeded_by_ms"] = round(duration_ms - threshold_ms, 3)
        logger.warning("slow_operation", **log_data)
    else:
        logger.debug("performance", **log_data)


def log_error(
    error: Exception,
    component: str,
    operation: str,
    context: dict[str, Any] | None = None,
) -> None:
    """
    Log an error with full context and stack trace.

    This helper provides comprehensive error logging including:
    - Error message and type
    - Component and operation that failed
    - Full stack trace
    - Additional context

    Parameters
    ----------
    error : Exception
        The exception that occurred.

    component : str
        Component where the error occurred.

    operation : str
        Operation that was being performed.

    context : dict, optional
        Additional context to include.

    Example
    -------
    >>> from obskit.logging import log_error
    >>>
    >>> try:
    ...     result = process_payment(payment_data)
    ... except PaymentError as e:
    ...     log_error(
    ...         error=e,
    ...         component="PaymentService",
    ...         operation="process_payment",
    ...         context={
    ...             "payment_id": payment_data.get("id"),
    ...             "amount": payment_data.get("amount"),
    ...         },
    ...     )
    ...     raise
    >>>
    >>> # Output:
    >>> # {
    >>> #   "event": "operation_error",
    >>> #   "component": "PaymentService",
    >>> #   "operation": "process_payment",
    >>> #   "error": "Card declined",
    >>> #   "error_type": "PaymentError",
    >>> #   "payment_id": "pay-123",
    >>> #   "amount": 99.99,
    >>> #   "exc_info": "Traceback (most recent call last):..."
    >>> # }
    """
    logger = get_logger("obskit.errors")

    log_data = {
        "component": component,
        "operation": operation,
        "error": str(error),
        "error_type": type(error).__name__,
        **(context or {}),
    }

    logger.error(
        "operation_error",
        exc_info=True,  # Include full stack trace
        **log_data,
    )
