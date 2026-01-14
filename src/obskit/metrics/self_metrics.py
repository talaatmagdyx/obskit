"""
Self-Monitoring Metrics for obskit
==================================

This module provides metrics about obskit's own performance and health.
These metrics help operators monitor the observability toolkit itself.

Metrics Exposed
---------------
- ``obskit_async_queue_depth``: Current depth of async metric queue
- ``obskit_async_queue_capacity``: Maximum capacity of async metric queue
- ``obskit_metrics_dropped_total``: Total metrics dropped due to full queue
- ``obskit_errors_total``: Total errors in obskit operations
- ``obskit_info``: Build/version information gauge

Example - Using Self-Metrics
----------------------------
.. code-block:: python

    from obskit.metrics.self_metrics import (
        get_self_metrics,
        record_dropped_metric,
        record_error,
    )

    # Get current metrics
    metrics = get_self_metrics()
    print(f"Queue depth: {metrics.queue_depth}")
    print(f"Dropped metrics: {metrics.dropped_total}")

    # Record a dropped metric
    record_dropped_metric(operation="high_freq_op", reason="queue_full")

    # Record an error
    record_error(component="async_recording", error_type="TimeoutError")
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING

from obskit.logging import get_logger

logger = get_logger("obskit.metrics.self_metrics")

# Check for Prometheus availability
try:
    from prometheus_client import Counter, Gauge, Info

    PROMETHEUS_AVAILABLE = True
except ImportError:  # pragma: no cover
    PROMETHEUS_AVAILABLE = False
    Counter = None  # type: ignore[assignment, misc]
    Gauge = None  # type: ignore[assignment, misc]
    Info = None  # type: ignore[assignment, misc]

if TYPE_CHECKING:
    from prometheus_client import Counter as CounterType
    from prometheus_client import Gauge as GaugeType
    from prometheus_client import Info as InfoType


# =============================================================================
# Self-Metrics Singleton
# =============================================================================

_self_metrics: ObskitSelfMetrics | None = None
_self_metrics_lock = threading.Lock()


@dataclass
class SelfMetricsSnapshot:
    """Snapshot of obskit's internal metrics."""

    queue_depth: int
    queue_capacity: int
    dropped_total: int
    errors_total: int
    version: str


class ObskitSelfMetrics:
    """
    Self-monitoring metrics for obskit.

    This class tracks obskit's own performance and health metrics,
    exposing them via Prometheus for monitoring.

    Attributes
    ----------
    queue_depth : Gauge
        Current depth of async metric queue.
    queue_capacity : Gauge
        Maximum capacity of async metric queue.
    dropped_total : Counter
        Total metrics dropped due to full queue.
    errors_total : Counter
        Total errors in obskit operations.
    info : Info
        Build/version information.
    """

    def __init__(self) -> None:
        """Initialize self-monitoring metrics."""
        from obskit._version import __version__

        self._version = __version__

        if not PROMETHEUS_AVAILABLE:  # pragma: no cover
            self._queue_depth: GaugeType | None = None
            self._queue_capacity: GaugeType | None = None
            self._dropped_total: CounterType | None = None
            self._errors_total: CounterType | None = None
            self._info: InfoType | None = None
            return

        # Queue metrics
        self._queue_depth = Gauge(
            "obskit_async_queue_depth",
            "Current depth of obskit async metric queue",
        )

        self._queue_capacity = Gauge(
            "obskit_async_queue_capacity",
            "Maximum capacity of obskit async metric queue",
        )

        # Dropped metrics counter
        self._dropped_total = Counter(
            "obskit_metrics_dropped_total",
            "Total metrics dropped by obskit due to full queue",
            ["operation", "reason"],
        )

        # Error counter
        self._errors_total = Counter(
            "obskit_errors_total",
            "Total errors in obskit operations",
            ["component", "error_type"],
        )

        # Version info
        self._info = Info(
            "obskit",
            "obskit build information",
        )
        self._info.info({"version": __version__})

        logger.debug("self_metrics_initialized", version=__version__)

    def set_queue_depth(self, depth: int) -> None:
        """Update the current queue depth."""
        if self._queue_depth is not None:
            self._queue_depth.set(depth)

    def set_queue_capacity(self, capacity: int) -> None:
        """Update the queue capacity."""
        if self._queue_capacity is not None:
            self._queue_capacity.set(capacity)

    def inc_dropped(self, operation: str, reason: str = "queue_full") -> None:
        """Increment dropped metrics counter."""
        if self._dropped_total is not None:
            self._dropped_total.labels(operation=operation, reason=reason).inc()

    def inc_error(self, component: str, error_type: str) -> None:
        """Increment error counter."""
        if self._errors_total is not None:
            self._errors_total.labels(component=component, error_type=error_type).inc()

    def get_snapshot(self) -> SelfMetricsSnapshot:
        """Get a snapshot of current metrics."""
        queue_depth = 0
        queue_capacity = 0
        dropped_total = 0
        errors_total = 0

        if PROMETHEUS_AVAILABLE:
            if self._queue_depth is not None:
                queue_depth = int(self._queue_depth._value.get())
            if self._queue_capacity is not None:
                queue_capacity = int(self._queue_capacity._value.get())
            # Note: Counters don't expose total easily, use 0 as placeholder
            # Real values are available via Prometheus scrape

        return SelfMetricsSnapshot(
            queue_depth=queue_depth,
            queue_capacity=queue_capacity,
            dropped_total=dropped_total,
            errors_total=errors_total,
            version=self._version,
        )


def get_self_metrics() -> ObskitSelfMetrics:
    """
    Get the global self-metrics instance.

    Returns
    -------
    ObskitSelfMetrics
        The self-metrics instance.

    Example
    -------
    >>> from obskit.metrics.self_metrics import get_self_metrics
    >>>
    >>> metrics = get_self_metrics()
    >>> metrics.set_queue_depth(42)
    >>> metrics.inc_dropped("my_operation", "queue_full")
    """
    global _self_metrics

    if _self_metrics is None:
        with _self_metrics_lock:
            if _self_metrics is None:  # pragma: no branch
                _self_metrics = ObskitSelfMetrics()

    return _self_metrics


def record_dropped_metric(operation: str, reason: str = "queue_full") -> None:
    """
    Record that a metric was dropped.

    Parameters
    ----------
    operation : str
        The operation that the dropped metric was for.
    reason : str
        Reason for dropping (default: "queue_full").
    """
    from obskit.config import get_settings

    settings = get_settings()
    if settings.enable_self_metrics:
        get_self_metrics().inc_dropped(operation, reason)


def record_error(component: str, error_type: str) -> None:
    """
    Record an obskit internal error.

    Parameters
    ----------
    component : str
        The component where the error occurred.
    error_type : str
        Type of error (e.g., exception class name).
    """
    from obskit.config import get_settings

    settings = get_settings()
    if settings.enable_self_metrics:
        get_self_metrics().inc_error(component, error_type)


def update_queue_metrics(depth: int, capacity: int) -> None:
    """
    Update queue metrics.

    Parameters
    ----------
    depth : int
        Current queue depth.
    capacity : int
        Maximum queue capacity.
    """
    from obskit.config import get_settings

    settings = get_settings()
    if settings.enable_self_metrics:
        metrics = get_self_metrics()
        metrics.set_queue_depth(depth)
        metrics.set_queue_capacity(capacity)


def reset_self_metrics() -> None:
    """Reset self-metrics (for testing)."""
    global _self_metrics
    with _self_metrics_lock:
        _self_metrics = None


__all__ = [
    "ObskitSelfMetrics",
    "SelfMetricsSnapshot",
    "get_self_metrics",
    "record_dropped_metric",
    "record_error",
    "update_queue_metrics",
    "reset_self_metrics",
]
