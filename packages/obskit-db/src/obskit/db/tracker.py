"""
Database Query Tracker
======================

This module provides comprehensive tracking for database queries with:
- RED metrics (Rate, Errors, Duration)
- Distributed tracing (OpenTelemetry)
- SLO tracking (latency objectives)
- Tenant/company context
- Slow query detection
"""

from __future__ import annotations

import time
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from obskit.logging import get_logger
from obskit.metrics.red import get_red_metrics

logger = get_logger("obskit.db.tracker")

# Lazy imports to avoid circular dependencies
_tracer = None
_slo_tracker = None


def _get_tracer():
    """Get tracer lazily."""
    global _tracer
    if _tracer is None:
        try:
            from obskit.tracing import get_tracer

            _tracer = get_tracer()
        except Exception:
            _tracer = None
    return _tracer


def _get_slo_tracker():
    """Get SLO tracker lazily."""
    global _slo_tracker
    if _slo_tracker is None:
        try:
            from obskit.slo import get_slo_tracker

            _slo_tracker = get_slo_tracker()
        except Exception:
            _slo_tracker = None
    return _slo_tracker


class DatabaseTracker:
    """
    Tracks database operations with full observability.

    Features:
    - RED metrics (Rate, Errors, Duration)
    - Distributed tracing with OpenTelemetry
    - SLO tracking for query latency
    - Tenant/company context for multi-tenant apps
    - Slow query detection and alerting

    Example
    -------
    >>> from obskit.db import DatabaseTracker
    >>>
    >>> tracker = DatabaseTracker("user_db")
    >>>
    >>> # Simple usage
    >>> with tracker.track_query("get_user", query="SELECT * FROM users"):
    ...     result = db.execute(query)
    >>>
    >>> # With tenant context and SLO
    >>> with tracker.track_query(
    ...     "get_orders",
    ...     tenant_id="company_123",
    ...     slo_name="query_latency_p95",
    ... ):
    ...     result = db.execute(query)
    """

    def __init__(
        self,
        database_name: str,
        default_slo_name: str | None = None,
        default_slow_threshold_ms: float = 1000.0,
    ) -> None:
        """
        Initialize database tracker.

        Parameters
        ----------
        database_name : str
            Name of the database (e.g., "postgres", "mysql", "mongodb").
        default_slo_name : str, optional
            Default SLO name for latency tracking.
        default_slow_threshold_ms : float, optional
            Default slow query threshold in milliseconds.
        """
        self.database_name = database_name
        self.default_slo_name = default_slo_name
        self.default_slow_threshold_ms = default_slow_threshold_ms
        self.red_metrics = get_red_metrics()

    @contextmanager
    def track_query(
        self,
        operation: str,
        query: str | None = None,
        slow_query_threshold_ms: float | None = None,
        tenant_id: str | None = None,
        slo_name: str | None = None,
        attributes: dict[str, Any] | None = None,
        enable_tracing: bool = True,
        enable_slo: bool = True,
    ) -> Generator[None, None, None]:
        """
        Track a database query with full observability.

        Parameters
        ----------
        operation : str
            Operation name (e.g., "get_user", "create_order").
        query : str, optional
            SQL query string (for logging, will be truncated).
        slow_query_threshold_ms : float, optional
            Threshold for slow query detection in milliseconds.
            Default: uses instance default or 1000ms.
        tenant_id : str, optional
            Tenant/company ID for multi-tenant context.
        slo_name : str, optional
            SLO name for latency tracking.
        attributes : dict, optional
            Additional attributes for tracing span.
        enable_tracing : bool, optional
            Whether to create a tracing span. Default: True.
        enable_slo : bool, optional
            Whether to record SLO measurement. Default: True.

        Yields
        ------
        None

        Example
        -------
        >>> with tracker.track_query(
        ...     "get_user",
        ...     query="SELECT * FROM users WHERE id = ?",
        ...     tenant_id="company_123",
        ...     slo_name="query_latency_p95",
        ... ):
        ...     result = db.execute(query, user_id)
        """
        start_time = time.perf_counter()
        full_operation = f"{self.database_name}.{operation}"
        threshold_ms = slow_query_threshold_ms or self.default_slow_threshold_ms
        slo = slo_name or self.default_slo_name

        # Build span attributes
        span_attributes = {
            "db.system": self.database_name,
            "db.operation": operation,
        }
        if tenant_id:
            span_attributes["tenant.id"] = tenant_id
        if query:
            # Truncate query for safety
            span_attributes["db.statement"] = query[:500] if len(query) > 500 else query
        if attributes:
            span_attributes.update(attributes)

        # Get tracer for distributed tracing
        tracer = _get_tracer() if enable_tracing else None
        slo_tracker = _get_slo_tracker() if enable_slo and slo else None

        # Create tracing context
        trace_context = None
        if tracer:
            try:
                from obskit.tracing import trace_span

                trace_context = trace_span(
                    name=f"db.{operation}",
                    component=self.database_name,
                    operation=operation,
                    attributes=span_attributes,
                )
            except Exception:
                trace_context = None

        try:
            # Enter trace span if available
            if trace_context:
                trace_context.__enter__()

            logger.debug(
                "db_query_started",
                database=self.database_name,
                operation=operation,
                tenant_id=tenant_id,
            )

            yield

            duration_seconds = time.perf_counter() - start_time
            duration_ms = duration_seconds * 1000

            # Record RED metrics
            self.red_metrics.observe_request(
                operation=full_operation,
                duration_seconds=duration_seconds,
                status="success",
            )

            # Record SLO measurement
            if slo_tracker and slo:
                try:
                    slo_tracker.record_measurement(slo, value=duration_seconds, success=True)
                except Exception:
                    pass  # SLO tracking failure should not affect query result

            # Log slow queries
            if duration_ms > threshold_ms:
                logger.warning(
                    "slow_query_detected",
                    database=self.database_name,
                    operation=operation,
                    duration_ms=round(duration_ms, 2),
                    threshold_ms=threshold_ms,
                    tenant_id=tenant_id,
                )
            else:
                logger.debug(
                    "db_query_completed",
                    database=self.database_name,
                    operation=operation,
                    duration_ms=round(duration_ms, 2),
                    tenant_id=tenant_id,
                )

        except Exception as e:
            duration_seconds = time.perf_counter() - start_time

            # Record error metrics
            self.red_metrics.observe_request(
                operation=full_operation,
                duration_seconds=duration_seconds,
                status="failure",
                error_type=type(e).__name__,
            )

            # Record SLO failure
            if slo_tracker and slo:
                try:
                    slo_tracker.record_measurement(slo, value=duration_seconds, success=False)
                except Exception:
                    pass  # SLO tracking failure should not affect error propagation

            logger.error(
                "db_query_failed",
                database=self.database_name,
                operation=operation,
                error=str(e),
                error_type=type(e).__name__,
                tenant_id=tenant_id,
                exc_info=True,
            )

            raise

        finally:
            # Exit trace span if available
            if trace_context:
                try:
                    trace_context.__exit__(None, None, None)
                except Exception:
                    pass  # Span cleanup failure should not affect application

    def record_query(
        self,
        operation: str,
        duration_seconds: float,
        success: bool = True,
        error_type: str | None = None,
        tenant_id: str | None = None,
        slo_name: str | None = None,
    ) -> None:
        """
        Record query metrics without context manager (for manual tracking).

        Parameters
        ----------
        operation : str
            Operation name.
        duration_seconds : float
            Query duration in seconds.
        success : bool, optional
            Whether query succeeded. Default: True.
        error_type : str, optional
            Error type if failed.
        tenant_id : str, optional
            Tenant ID for context.
        slo_name : str, optional
            SLO name for latency tracking.
        """
        full_operation = f"{self.database_name}.{operation}"
        status = "success" if success else "failure"
        slo = slo_name or self.default_slo_name

        # Record RED metrics
        self.red_metrics.observe_request(
            operation=full_operation,
            duration_seconds=duration_seconds,
            status=status,
            error_type=error_type,
        )

        # Record SLO measurement
        if slo:
            slo_tracker = _get_slo_tracker()
            if slo_tracker:
                try:
                    slo_tracker.record_measurement(slo, value=duration_seconds, success=success)
                except Exception:
                    pass  # SLO tracking failure should not affect application

        # Log
        if success:
            logger.debug(
                "db_query_recorded",
                database=self.database_name,
                operation=operation,
                duration_ms=round(duration_seconds * 1000, 2),
                tenant_id=tenant_id,
            )
        else:
            logger.warning(
                "db_query_failure_recorded",
                database=self.database_name,
                operation=operation,
                duration_ms=round(duration_seconds * 1000, 2),
                error_type=error_type,
                tenant_id=tenant_id,
            )


@contextmanager
def track_query(
    operation: str,
    database_name: str = "database",
    query: str | None = None,
    slow_query_threshold_ms: float = 1000.0,
    tenant_id: str | None = None,
    slo_name: str | None = None,
    attributes: dict[str, Any] | None = None,
    enable_tracing: bool = True,
    enable_slo: bool = True,
) -> Generator[None, None, None]:
    """
    Track a database query with full observability (convenience function).

    This is a convenience wrapper around DatabaseTracker.track_query().

    Parameters
    ----------
    operation : str
        Operation name.
    database_name : str, optional
        Database name. Default: "database".
    query : str, optional
        SQL query string.
    slow_query_threshold_ms : float, optional
        Slow query threshold in milliseconds. Default: 1000ms.
    tenant_id : str, optional
        Tenant/company ID for multi-tenant context.
    slo_name : str, optional
        SLO name for latency tracking.
    attributes : dict, optional
        Additional attributes for tracing span.
    enable_tracing : bool, optional
        Whether to create a tracing span. Default: True.
    enable_slo : bool, optional
        Whether to record SLO measurement. Default: True.

    Example
    -------
    >>> from obskit.db import track_query
    >>>
    >>> # Simple usage
    >>> with track_query("get_user", query="SELECT * FROM users"):
    ...     result = db.execute(query)
    >>>
    >>> # With tenant and SLO
    >>> with track_query(
    ...     "get_orders",
    ...     database_name="postgresql",
    ...     tenant_id="company_123",
    ...     slo_name="query_latency_p95",
    ... ):
    ...     result = db.execute(query)
    """
    tracker = DatabaseTracker(database_name)
    with tracker.track_query(
        operation=operation,
        query=query,
        slow_query_threshold_ms=slow_query_threshold_ms,
        tenant_id=tenant_id,
        slo_name=slo_name,
        attributes=attributes,
        enable_tracing=enable_tracing,
        enable_slo=enable_slo,
    ):
        yield


__all__ = ["DatabaseTracker", "track_query"]
