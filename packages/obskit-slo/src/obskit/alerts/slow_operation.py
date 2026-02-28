"""
Slow Operation Detection and Alerting
======================================

Automatic detection and alerting for operations that exceed defined thresholds.

Example
-------
>>> from obskit.alerts.slow_operation import SlowOperationDetector
>>>
>>> # Create detector with Alertmanager integration
>>> detector = SlowOperationDetector(
...     threshold_ms=5000,
...     alertmanager_url="http://alertmanager:9093",
... )
>>>
>>> # Track operation
>>> with detector.track("process_order"):
...     result = process_order(order_data)
>>>
>>> # Or use decorator
>>> @detector.monitor("fetch_user_data", threshold_ms=2000)
>>> def fetch_user_data(user_id):
...     return db.get_user(user_id)
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from functools import wraps
from typing import Any, TypeVar

from obskit.logging import get_logger
from obskit.metrics import REDMetrics

logger = get_logger("obskit.alerts.slow_operation")

T = TypeVar("T")

# Try to import Alertmanager webhook
try:
    from obskit.slo.alertmanager import SyncAlertmanagerWebhook

    ALERTMANAGER_AVAILABLE = True
except ImportError:
    ALERTMANAGER_AVAILABLE = False


@dataclass
class SlowOperationEvent:
    """Represents a slow operation event."""

    operation: str
    duration_ms: float
    threshold_ms: float
    timestamp: datetime
    alert_id: str
    component: str | None = None
    tenant_id: str | None = None
    context: dict[str, Any] | None = None


class SlowOperationDetector:
    """
    Detects and alerts on slow operations.

    Features:
    - Configurable thresholds per operation
    - Alertmanager integration
    - Metrics recording
    - Event history

    Example
    -------
    >>> detector = SlowOperationDetector(
    ...     threshold_ms=5000,
    ...     alertmanager_url="http://alertmanager:9093",
    ... )
    >>>
    >>> with detector.track("process_order"):
    ...     process_order(data)
    """

    def __init__(
        self,
        threshold_ms: float = 5000.0,
        alertmanager_url: str | None = None,
        component: str = "service",
        enable_metrics: bool = True,
        history_size: int = 100,
    ):
        """
        Initialize slow operation detector.

        Parameters
        ----------
        threshold_ms : float
            Default threshold for slow operation detection (default: 5000ms).
        alertmanager_url : str, optional
            Alertmanager URL for sending alerts.
        component : str
            Component name for metrics and alerts.
        enable_metrics : bool
            Whether to record metrics (default: True).
        history_size : int
            Number of slow events to keep in history (default: 100).
        """
        self.default_threshold_ms = threshold_ms
        self.alertmanager_url = alertmanager_url
        self.component = component
        self.enable_metrics = enable_metrics
        self.history_size = history_size

        # History of slow operations
        self._history: list[SlowOperationEvent] = []

        # Metrics
        if enable_metrics:
            self._metrics = REDMetrics(name=f"{component}_slow_operations")
        else:
            self._metrics = None

        # Alertmanager webhook
        self._webhook = None
        if alertmanager_url and ALERTMANAGER_AVAILABLE:
            self._webhook = SyncAlertmanagerWebhook(alertmanager_url=alertmanager_url)

    @contextmanager
    def track(
        self,
        operation: str,
        threshold_ms: float | None = None,
        tenant_id: str | None = None,
        context: dict[str, Any] | None = None,
        send_alert: bool = True,
    ) -> Generator[None, None, None]:
        """
        Track an operation and alert if it's slow.

        Parameters
        ----------
        operation : str
            Name of the operation.
        threshold_ms : float, optional
            Override threshold for this operation.
        tenant_id : str, optional
            Tenant ID for context.
        context : dict, optional
            Additional context for alerts.
        send_alert : bool
            Whether to send alert if slow (default: True).

        Yields
        ------
        None

        Example
        -------
        >>> with detector.track("process_order", threshold_ms=3000):
        ...     process_order(data)
        """
        start_time = time.perf_counter()
        threshold = threshold_ms or self.default_threshold_ms

        try:
            yield
        finally:
            duration_ms = (time.perf_counter() - start_time) * 1000

            if duration_ms > threshold:
                alert_id = self._handle_slow_operation(
                    operation=operation,
                    duration_ms=duration_ms,
                    threshold_ms=threshold,
                    tenant_id=tenant_id,
                    context=context,
                    send_alert=send_alert,
                )

                if alert_id:
                    logger.warning(
                        "slow_operation_alert_sent",
                        operation=operation,
                        alert_id=alert_id,
                        duration_ms=round(duration_ms, 2),
                        threshold_ms=threshold,
                    )

    def monitor(
        self,
        operation: str,
        threshold_ms: float | None = None,
        send_alert: bool = True,
    ):
        """
        Decorator for monitoring function execution time.

        Parameters
        ----------
        operation : str
            Name of the operation.
        threshold_ms : float, optional
            Override threshold.
        send_alert : bool
            Whether to send alert if slow.

        Example
        -------
        >>> @detector.monitor("fetch_data", threshold_ms=2000)
        >>> def fetch_data(user_id):
        ...     return db.get(user_id)
        """

        def decorator(func: Callable[..., T]) -> Callable[..., T]:
            @wraps(func)
            def wrapper(*args, **kwargs) -> T:
                with self.track(operation, threshold_ms=threshold_ms, send_alert=send_alert):
                    return func(*args, **kwargs)

            return wrapper

        return decorator

    def _handle_slow_operation(
        self,
        operation: str,
        duration_ms: float,
        threshold_ms: float,
        tenant_id: str | None = None,
        context: dict[str, Any] | None = None,
        send_alert: bool = True,
    ) -> str | None:
        """Handle a detected slow operation."""
        alert_id = str(uuid.uuid4())[:8]

        # Create event
        event = SlowOperationEvent(
            operation=operation,
            duration_ms=round(duration_ms, 2),
            threshold_ms=threshold_ms,
            timestamp=datetime.utcnow(),
            alert_id=alert_id,
            component=self.component,
            tenant_id=tenant_id,
            context=context,
        )

        # Add to history
        self._history.append(event)
        if len(self._history) > self.history_size:
            self._history.pop(0)

        # Record metrics
        if self._metrics:
            self._metrics.observe_request(
                operation=f"slow_{operation}",
                duration_seconds=duration_ms / 1000,
                status="slow",
            )

        # Log warning
        logger.warning(
            "slow_operation_detected",
            operation=operation,
            component=self.component,
            duration_ms=round(duration_ms, 2),
            threshold_ms=threshold_ms,
            tenant_id=tenant_id,
            alert_id=alert_id,
        )

        # Send Alertmanager alert
        if send_alert and self._webhook:
            try:
                self._webhook.fire_alert(
                    alertname="SlowOperation",
                    labels={
                        "operation": operation,
                        "component": self.component,
                        "severity": "warning",
                    },
                    annotations={
                        "summary": f"Slow operation: {operation}",
                        "description": f"Operation {operation} took {duration_ms:.0f}ms (threshold: {threshold_ms}ms)",
                        "duration_ms": str(round(duration_ms, 2)),
                        "threshold_ms": str(threshold_ms),
                        "tenant_id": tenant_id or "unknown",
                    },
                )
                return alert_id
            except Exception as e:
                logger.error("alertmanager_send_failed", error=str(e))

        return alert_id

    def get_history(self, limit: int = 10) -> list[SlowOperationEvent]:
        """Get recent slow operation events."""
        return list(reversed(self._history[-limit:]))

    def get_stats(self) -> dict[str, Any]:
        """Get statistics about slow operations."""
        if not self._history:
            return {
                "total_events": 0,
                "operations": {},
            }

        # Group by operation
        by_operation: dict[str, list[float]] = {}
        for event in self._history:
            if event.operation not in by_operation:
                by_operation[event.operation] = []
            by_operation[event.operation].append(event.duration_ms)

        return {
            "total_events": len(self._history),
            "operations": {
                op: {
                    "count": len(durations),
                    "avg_ms": sum(durations) / len(durations),
                    "max_ms": max(durations),
                    "min_ms": min(durations),
                }
                for op, durations in by_operation.items()
            },
        }

    def clear_history(self):
        """Clear the event history."""
        self._history.clear()


# Convenience function for quick detection
def check_slow_operation(
    operation: str,
    duration_seconds: float,
    threshold_ms: float = 5000.0,
    alertmanager_url: str | None = None,
    component: str = "service",
    tenant_id: str | None = None,
    context: dict[str, Any] | None = None,
) -> str | None:
    """
    Check if an operation was slow and optionally send alert.

    Parameters
    ----------
    operation : str
        Name of the operation.
    duration_seconds : float
        Actual duration in seconds.
    threshold_ms : float
        Threshold in milliseconds.
    alertmanager_url : str, optional
        Alertmanager URL.
    component : str
        Component name.
    tenant_id : str, optional
        Tenant ID.
    context : dict, optional
        Additional context.

    Returns
    -------
    str or None
        Alert ID if slow, None otherwise.

    Example
    -------
    >>> start = time.time()
    >>> process_order()
    >>> duration = time.time() - start
    >>> alert_id = check_slow_operation("process_order", duration, threshold_ms=5000)
    """
    duration_ms = duration_seconds * 1000

    if duration_ms <= threshold_ms:
        return None

    alert_id = str(uuid.uuid4())[:8]

    logger.warning(
        "slow_operation_detected",
        operation=operation,
        component=component,
        duration_ms=round(duration_ms, 2),
        threshold_ms=threshold_ms,
        tenant_id=tenant_id,
        alert_id=alert_id,
    )

    # Send alert if URL provided
    if alertmanager_url and ALERTMANAGER_AVAILABLE:
        try:
            webhook = SyncAlertmanagerWebhook(alertmanager_url=alertmanager_url)
            webhook.fire_alert(
                alert_name="SlowOperation",
                labels={
                    "operation": operation,
                    "component": component,
                },
                annotations={
                    "summary": f"Slow operation: {operation}",
                    "description": f"Operation {operation} took {duration_ms:.0f}ms",
                },
                severity="warning",
            )
        except Exception as e:
            logger.error("alertmanager_send_failed", error=str(e))

    return alert_id


__all__ = [
    "SlowOperationDetector",
    "SlowOperationEvent",
    "check_slow_operation",
]
