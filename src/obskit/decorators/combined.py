"""
Combined Observability Decorators Implementation
================================================

This module implements the observability decorators that combine multiple
concerns (logging, metrics, error tracking) into reusable function decorators.

The main benefit is that your business logic stays clean while getting
comprehensive observability automatically.

Before (without decorators):

    async def create_order(order_data: dict) -> Order:
        start_time = time.perf_counter()
        logger.info("operation_started", operation="create_order")

        try:
            order = await Order.create(**order_data)
            duration = time.perf_counter() - start_time

            logger.info("operation_completed", operation="create_order", duration_ms=duration*1000)
            metrics.observe_duration("create_order", duration)
            metrics.inc_request("create_order", status="success")

            return order
        except Exception as e:
            duration = time.perf_counter() - start_time

            logger.error("operation_failed", operation="create_order", error=str(e))
            metrics.inc_error("create_order", type(e).__name__)
            metrics.inc_request("create_order", status="failure")

            raise

After (with decorators):

    @with_observability(component="OrderService")
    async def create_order(order_data: dict) -> Order:
        return await Order.create(**order_data)

Implementation Details
----------------------
The decorators use these obskit components internally:

1. **Logging** (obskit.logging):
   - log_operation() for start/completion/failure
   - log_performance() for timing with thresholds
   - log_error() for detailed error context

2. **Metrics** (obskit.metrics.red):
   - REDMetrics.observe_request() for rate and duration
   - REDMetrics.observe_error() for error tracking

3. **Context** (obskit.core.context):
   - correlation_context() for ID propagation
   - get_correlation_id() for reading current ID
"""

from __future__ import annotations

import time
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from functools import wraps
from typing import Any, ParamSpec, TypeVar

from obskit.core.context import async_correlation_context, get_correlation_id
from obskit.logging import get_logger, log_error, log_operation, log_performance
from obskit.metrics.red import get_red_metrics

# Type variables for generic decorator typing
P = ParamSpec("P")  # Preserves parameter types
T = TypeVar("T")  # Return type

# Module logger
logger = get_logger(__name__)


def with_observability(
    component: str | None = None,
    operation: str | None = None,
    threshold_ms: float | None = None,
    track_metrics: bool = True,
    log_start: bool = False,
    **default_context: Any,
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """
    Comprehensive observability decorator for async functions.

    This decorator automatically adds logging, metrics tracking, and
    error handling to any async function. It's the recommended way to
    add observability to your business logic.

    Parameters
    ----------
    component : str, optional
        Name of the component/service. Used in logs and metrics.
        If not provided, uses the function's module name.
        Example: "OrderService", "PaymentProcessor", "UserRepository"

    operation : str, optional
        Name of the operation. Used in logs and metrics.
        If not provided, uses the function name.
        Example: "create_order", "process_payment", "find_user"

    threshold_ms : float, optional
        Performance threshold in milliseconds. If the operation
        takes longer than this, a warning is logged.
        Example: 500.0 for half-second threshold

    track_metrics : bool, default=True
        Whether to record Prometheus metrics (rate, errors, duration).
        Set to False if you only want logging.

    log_start : bool, default=False
        Whether to log when the operation starts.
        Useful for long-running operations or debugging.

    **default_context : Any
        Additional context to include in all log entries.
        Example: user_id="123", tenant_id="abc"

    Returns
    -------
    Callable
        Decorator function that wraps the target function.

    Example - Basic Usage
    ---------------------
    >>> from obskit.decorators import with_observability
    >>>
    >>> @with_observability(component="OrderService")
    ... async def create_order(order_data: dict) -> Order:
    ...     '''Create a new order.'''
    ...     return await Order.create(**order_data)
    >>>
    >>> # When called:
    >>> order = await create_order({"item": "widget", "quantity": 5})
    >>>
    >>> # Logs produced:
    >>> # {"event": "operation_completed", "component": "OrderService",
    >>> #  "operation": "create_order", "duration_ms": 45.2, "status": "success"}
    >>>
    >>> # Metrics recorded:
    >>> # order_service_requests_total{operation="create_order",status="success"} 1
    >>> # order_service_request_duration_seconds{operation="create_order"} 0.0452

    Example - With Performance Threshold
    ------------------------------------
    >>> @with_observability(
    ...     component="SearchService",
    ...     threshold_ms=200.0,  # Warn if slower than 200ms
    ... )
    ... async def search(query: str) -> SearchResults:
    ...     return await search_engine.query(query)
    >>>
    >>> # If search takes 350ms, additional log:
    >>> # {"event": "slow_operation", "component": "SearchService",
    >>> #  "operation": "search", "duration_ms": 350.0,
    >>> #  "threshold_ms": 200.0, "exceeded_by_ms": 150.0}

    Example - With Default Context
    ------------------------------
    >>> @with_observability(
    ...     component="TenantService",
    ...     tenant_id="tenant-123",  # Added to all logs
    ...     region="us-east-1",
    ... )
    ... async def get_tenant_data():
    ...     return await fetch_data()
    >>>
    >>> # All logs include: {"tenant_id": "tenant-123", "region": "us-east-1", ...}

    Example - Error Handling
    ------------------------
    >>> @with_observability(component="PaymentService")
    ... async def charge(amount: float):
    ...     if amount <= 0:
    ...         raise ValueError("Amount must be positive")
    ...     return await gateway.charge(amount)
    >>>
    >>> # On error:
    >>> # {"event": "operation_failed", "component": "PaymentService",
    >>> #  "operation": "charge", "error": "Amount must be positive",
    >>> #  "error_type": "ValueError", "duration_ms": 1.2}
    >>> #
    >>> # Metrics:
    >>> # payment_service_errors_total{operation="charge",error_type="ValueError"} 1

    Notes
    -----
    - The original exception is always re-raised after logging/metrics
    - Correlation IDs are automatically propagated if present in kwargs
    - Duration is measured using time.perf_counter() for precision

    See Also
    --------
    with_observability_sync : Same decorator for synchronous functions
    track_operation : Lightweight logging-only alternative
    track_metrics_only : Metrics-only alternative for high-frequency operations
    """

    def decorator(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        # Determine component and operation names
        # Use provided values or derive from function metadata
        comp = component or func.__module__.split(".")[-1]
        op = operation or func.__name__

        @wraps(func)  # Preserves function metadata (__name__, __doc__, etc.)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            # =================================================================
            # Step 1: Build context dictionary
            # =================================================================
            # Start with default context provided to decorator
            context = default_context.copy()

            # Extract known context keys from kwargs if present
            # These are commonly passed for request tracing
            if "correlation_id" in kwargs:  # pragma: no cover
                context["correlation_id"] = kwargs["correlation_id"]
            if "request_id" in kwargs:  # pragma: no cover
                context["request_id"] = kwargs["request_id"]

            # =================================================================
            # Step 2: Set up correlation context
            # =================================================================
            # Get existing correlation ID or let context manager generate one
            correlation_id = get_correlation_id()

            # Use async context manager for proper correlation ID propagation
            async with _async_null_context() if correlation_id else async_correlation_context():
                # =============================================================
                # Step 3: Start timing
                # =============================================================
                start_time = time.perf_counter()

                # =============================================================
                # Step 4: Log operation start (optional)
                # =============================================================
                if log_start:  # pragma: no cover
                    logger.debug(
                        "operation_started",
                        component=comp,
                        operation=op,
                        **context,
                    )

                try:
                    # =========================================================
                    # Step 5: Execute the wrapped function
                    # =========================================================
                    result = await func(*args, **kwargs)

                    # =========================================================
                    # Step 6: Calculate duration on success
                    # =========================================================
                    duration_ms = (time.perf_counter() - start_time) * 1000

                    # =========================================================
                    # Step 7: Log performance (with threshold check)
                    # =========================================================
                    log_performance(
                        operation=op,
                        component=comp,
                        duration_ms=duration_ms,
                        threshold_ms=threshold_ms,
                        **context,
                    )

                    # =========================================================
                    # Step 8: Record metrics (if enabled)
                    # =========================================================
                    if track_metrics:  # pragma: no branch
                        red = get_red_metrics()
                        red.observe_request(
                            operation=op,
                            duration_seconds=duration_ms / 1000.0,
                            status="success",
                        )

                    # =========================================================
                    # Step 9: Log operation completion
                    # =========================================================
                    log_operation(
                        operation=op,
                        component=comp,
                        status="success",
                        duration_ms=duration_ms,
                        **context,
                    )

                    return result

                except Exception as e:
                    # =========================================================
                    # Step 10: Handle errors - calculate duration
                    # =========================================================
                    duration_ms = (time.perf_counter() - start_time) * 1000

                    # =========================================================
                    # Step 11: Log detailed error information
                    # =========================================================
                    log_error(
                        error=e,
                        component=comp,
                        operation=op,
                        context=context,
                    )

                    # =========================================================
                    # Step 12: Record error metrics (if enabled)
                    # =========================================================
                    if track_metrics:
                        red = get_red_metrics()
                        red.observe_request(
                            operation=op,
                            duration_seconds=duration_ms / 1000.0,
                            status="failure",
                            error_type=type(e).__name__,
                        )

                    # =========================================================
                    # Step 13: Log operation failure
                    # =========================================================
                    log_operation(
                        operation=op,
                        component=comp,
                        status="failure",
                        duration_ms=duration_ms,
                        error=str(e),
                        error_type=type(e).__name__,
                        **context,
                    )

                    # =========================================================
                    # Step 14: Re-raise the exception
                    # =========================================================
                    # We don't suppress errors - just observe them
                    raise

        return wrapper

    return decorator


def with_observability_sync(
    component: str | None = None,
    operation: str | None = None,
    threshold_ms: float | None = None,
    track_metrics: bool = True,
    log_start: bool = False,
    **default_context: Any,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """
    Comprehensive observability decorator for synchronous functions.

    This is the synchronous version of with_observability(). Use this
    for regular (non-async) functions.

    Parameters
    ----------
    component : str, optional
        Name of the component/service.
    operation : str, optional
        Name of the operation.
    threshold_ms : float, optional
        Performance threshold in milliseconds.
    track_metrics : bool, default=True
        Whether to record Prometheus metrics.
    log_start : bool, default=False
        Whether to log operation start.
    **default_context : Any
        Additional context for log entries.

    Returns
    -------
    Callable
        Decorator function.

    Example
    -------
    >>> from obskit.decorators.combined import with_observability_sync
    >>>
    >>> @with_observability_sync(component="FileProcessor")
    ... def process_file(filepath: str) -> ProcessResult:
    ...     '''Process a file synchronously.'''
    ...     with open(filepath, 'r') as f:
    ...         data = f.read()
    ...     return process_data(data)
    >>>
    >>> # Usage:
    >>> result = process_file("/path/to/file.txt")

    See Also
    --------
    with_observability : Async version of this decorator
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        comp = component or func.__module__.split(".")[-1]
        op = operation or func.__name__

        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            # Build context
            context = default_context.copy()
            if "correlation_id" in kwargs:  # pragma: no cover
                context["correlation_id"] = kwargs["correlation_id"]

            # Start timing
            start_time = time.perf_counter()

            # Log start if requested
            if log_start:  # pragma: no cover
                logger.debug(
                    "operation_started",
                    component=comp,
                    operation=op,
                    **context,
                )

            try:
                # Execute function
                result = func(*args, **kwargs)
                duration_ms = (time.perf_counter() - start_time) * 1000

                # Log and record metrics on success
                log_performance(
                    operation=op,
                    component=comp,
                    duration_ms=duration_ms,
                    threshold_ms=threshold_ms,
                    **context,
                )

                if track_metrics:  # pragma: no branch
                    red = get_red_metrics()
                    red.observe_request(
                        operation=op,
                        duration_seconds=duration_ms / 1000.0,
                        status="success",
                    )

                log_operation(
                    operation=op,
                    component=comp,
                    status="success",
                    duration_ms=duration_ms,
                    **context,
                )

                return result

            except Exception as e:
                duration_ms = (time.perf_counter() - start_time) * 1000

                # Log error
                log_error(
                    error=e,
                    component=comp,
                    operation=op,
                    context=context,
                )

                # Record error metrics
                if track_metrics:
                    red = get_red_metrics()
                    red.observe_request(
                        operation=op,
                        duration_seconds=duration_ms / 1000.0,
                        status="failure",
                        error_type=type(e).__name__,
                    )

                log_operation(
                    operation=op,
                    component=comp,
                    status="failure",
                    duration_ms=duration_ms,
                    **context,
                )

                raise

        return wrapper

    return decorator


# Alias for backwards compatibility and discoverability
with_observability_async = with_observability


def track_operation(
    component: str | None = None,
    operation: str | None = None,
    **default_context: Any,
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """
    Lightweight operation tracking decorator (logging only).

    Use this decorator when you want operation logging but don't need
    metrics. This is useful for:

    - Internal helper functions
    - Operations that don't need SLO tracking
    - Debugging during development

    This decorator is much lighter than with_observability() because
    it only logs start/completion/failure without recording metrics.

    Parameters
    ----------
    component : str, optional
        Name of the component.
    operation : str, optional
        Name of the operation.
    **default_context : Any
        Additional context for log entries.

    Returns
    -------
    Callable
        Decorator function.

    Example
    -------
    >>> from obskit.decorators import track_operation
    >>>
    >>> @track_operation(component="DataTransformer")
    ... async def transform_response(data: dict) -> dict:
    ...     '''Transform API response format.'''
    ...     return {
    ...         "id": data["user_id"],
    ...         "name": data["full_name"],
    ...         "email": data["email_address"],
    ...     }
    >>>
    >>> # Logs on success:
    >>> # {"event": "operation_started", "component": "DataTransformer", "operation": "transform_response"}
    >>> # {"event": "operation_completed", "component": "DataTransformer", "operation": "transform_response"}
    >>>
    >>> # Logs on failure:
    >>> # {"event": "operation_failed", "component": "DataTransformer",
    >>> #  "operation": "transform_response", "error": "...", "error_type": "..."}

    See Also
    --------
    with_observability : Full observability with metrics
    track_metrics_only : Metrics without logging
    """

    def decorator(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        comp = component or func.__module__.split(".")[-1]
        op = operation or func.__name__

        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            context = default_context.copy()

            # Log operation start
            logger.debug(
                "operation_started",
                component=comp,
                operation=op,
                **context,
            )

            try:
                # Execute function
                result = await func(*args, **kwargs)

                # Log completion
                logger.debug(
                    "operation_completed",
                    component=comp,
                    operation=op,
                    **context,
                )
                return result

            except Exception as e:
                # Log error with full details
                logger.error(
                    "operation_failed",
                    component=comp,
                    operation=op,
                    error=str(e),
                    error_type=type(e).__name__,
                    **context,
                    exc_info=True,  # Include stack trace
                )
                raise

        return wrapper

    return decorator


def track_metrics_only(
    component: str | None = None,
    operation: str | None = None,
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """
    Metrics-only decorator (no logging).

    Use this decorator for high-frequency operations where logging
    would create too much noise, but you still want metrics.

    Common use cases:

    - Cache lookups (get/set operations)
    - Database connection pool operations
    - Authentication token validation
    - Rate limit checks

    Parameters
    ----------
    component : str, optional
        Name of the component.
    operation : str, optional
        Name of the operation.

    Returns
    -------
    Callable
        Decorator function.

    Example
    -------
    >>> from obskit.decorators import track_metrics_only
    >>>
    >>> @track_metrics_only(component="CacheService")
    ... async def get_from_cache(key: str) -> Optional[str]:
    ...     '''
    ...     Get value from cache.
    ...
    ...     Called thousands of times per second, so we don't want logging.
    ...     But we do want to track cache latency and error rates.
    ...     '''
    ...     return await cache.get(key)
    >>>
    >>> # Records metrics (no logs):
    >>> # cache_service_requests_total{operation="get_from_cache",status="success"}
    >>> # cache_service_request_duration_seconds{operation="get_from_cache"}

    Example - Monitoring Cache Performance
    --------------------------------------
    >>> @track_metrics_only(component="CacheService")
    ... async def cache_get(key: str):
    ...     return await redis.get(key)
    >>>
    >>> @track_metrics_only(component="CacheService")
    ... async def cache_set(key: str, value: str, ttl: int = 3600):
    ...     return await redis.setex(key, ttl, value)
    >>>
    >>> # Now you can monitor in Prometheus/Grafana:
    >>> # - Cache operation latency (P50, P95, P99)
    >>> # - Cache error rates
    >>> # - Cache throughput (operations/second)

    See Also
    --------
    with_observability : Full observability with logging
    track_operation : Logging without metrics
    """

    def decorator(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        component or func.__module__.split(".")[-1]
        op = operation or func.__name__

        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            # Start timing
            start_time = time.perf_counter()

            try:
                # Execute function
                result = await func(*args, **kwargs)

                # Record success metrics
                duration_seconds = time.perf_counter() - start_time
                red = get_red_metrics()
                red.observe_request(
                    operation=op,
                    duration_seconds=duration_seconds,
                    status="success",
                )

                return result

            except Exception as e:
                # Record failure metrics
                duration_seconds = time.perf_counter() - start_time
                red = get_red_metrics()
                red.observe_request(
                    operation=op,
                    duration_seconds=duration_seconds,
                    status="failure",
                    error_type=type(e).__name__,
                )

                raise

        return wrapper

    return decorator


# =============================================================================
# Internal Utilities
# =============================================================================


class _AsyncNullContext:
    """
    Async null context manager that does nothing.

    Used when we don't need to create a new correlation context
    (because one already exists).
    """

    async def __aenter__(self) -> None:
        """Enter context (no-op)."""
        pass

    async def __aexit__(self, *args: Any) -> None:
        """Exit context (no-op)."""
        pass


@asynccontextmanager
async def _async_null_context() -> AsyncGenerator[None, None]:
    """
    Async context manager that does nothing.

    This is used when a correlation ID already exists and we don't
    need to create a new correlation context.
    """
    yield  # pragma: no cover
