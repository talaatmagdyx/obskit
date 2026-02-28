"""
Async Metric Recording
======================

This module provides async (fire-and-forget) metric recording for
high-frequency operations where synchronous metric updates could cause
performance issues.

Example - Basic Usage
---------------------
.. code-block:: python

    from obskit.metrics.async_recording import AsyncREDMetrics
    from obskit.metrics import REDMetrics

    # Create async wrapper around regular metrics
    base_metrics = REDMetrics("service")
    async_metrics = AsyncREDMetrics(base_metrics)

    # Record metrics asynchronously (non-blocking)
    await async_metrics.observe_request(
        operation="high_freq_op",
        duration_seconds=0.001,
        status="success",
    )
"""

from __future__ import annotations

import asyncio
from typing import Literal

from obskit.logging import get_logger
from obskit.metrics.red import REDMetrics

logger = get_logger("obskit.metrics.async_recording")

# Global queue for async metric recording
_metric_queue: asyncio.Queue[dict[str, object]] | None = None
_metric_worker_task: asyncio.Task[None] | None = None
_queue_capacity: int = 10000


def _update_self_metrics() -> None:
    """Update self-monitoring metrics for queue state."""
    try:
        from obskit.metrics.self_metrics import update_queue_metrics

        if _metric_queue is not None:
            update_queue_metrics(_metric_queue.qsize(), _queue_capacity)
    except Exception:  # pragma: no cover  # nosec B110 - self-metrics are optional
        pass  # Don't fail if self-metrics unavailable


async def _metric_worker() -> None:
    """Background worker that processes metric queue."""
    global _metric_queue

    if _metric_queue is None:
        return

    while True:
        try:
            # Update self-metrics periodically
            _update_self_metrics()

            # Get metric from queue (with timeout to allow shutdown)
            try:
                metric_data = await asyncio.wait_for(_metric_queue.get(), timeout=1.0)
            except TimeoutError:
                continue

            # Process metric
            try:
                metrics_instance = metric_data["metrics"]
                method_name = metric_data["method"]
                args = metric_data.get("args", ())
                kwargs = metric_data.get("kwargs", {})

                # Call the metric method
                method = getattr(metrics_instance, str(method_name), None)
                if method is not None and callable(method):
                    method(*args, **kwargs)
                else:
                    logger.warning(
                        "async_metric_method_not_callable",
                        method=method_name,
                        metrics_instance=type(metrics_instance).__name__,
                    )

            except Exception as e:
                logger.error(
                    "async_metric_recording_failed",
                    error=str(e),
                    error_type=type(e).__name__,
                    method=method_name,
                )
                # Record error in self-metrics
                try:
                    from obskit.metrics.self_metrics import record_error

                    record_error("async_recording", type(e).__name__)
                except Exception:  # pragma: no cover  # nosec B110 - error recording is best-effort
                    pass  # Self-metrics recording failure is non-critical

            _metric_queue.task_done()

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(
                "metric_worker_error",
                error=str(e),
                error_type=type(e).__name__,
            )


async def _ensure_worker_started() -> None:
    """Ensure the metric worker is started."""
    global _metric_queue, _metric_worker_task, _queue_capacity

    if _metric_queue is None:
        # Get queue size from settings
        from obskit.config import get_settings

        settings = get_settings()
        _queue_capacity = settings.async_metric_queue_size
        _metric_queue = asyncio.Queue(maxsize=_queue_capacity)

    if _metric_worker_task is None or _metric_worker_task.done():
        _metric_worker_task = asyncio.create_task(_metric_worker())
        logger.debug("metric_worker_started")


class AsyncREDMetrics:
    """
    Async wrapper for REDMetrics that records metrics in background.

    This class wraps REDMetrics and records metrics asynchronously,
    reducing blocking on metric updates for high-frequency operations.

    Parameters
    ----------
    base_metrics : REDMetrics
        The underlying REDMetrics instance to use.

    queue_size : int, optional
        Maximum queue size. Default: 10000.
        If queue is full, metrics are dropped with a warning.

    Example
    -------
    >>> from obskit.metrics import REDMetrics
    >>> from obskit.metrics.async_recording import AsyncREDMetrics
    >>>
    >>> base = REDMetrics("service")
    >>> async_metrics = AsyncREDMetrics(base)
    >>>
    >>> # Non-blocking metric recording
    >>> await async_metrics.observe_request(
    ...     operation="high_freq",
    ...     duration_seconds=0.001,
    ...     status="success",
    ... )
    """

    def __init__(self, base_metrics: REDMetrics, queue_size: int = 10000) -> None:
        self._base = base_metrics
        self._queue_size = queue_size

    async def observe_request(
        self,
        operation: str,
        duration_seconds: float,
        status: Literal["success", "failure"] = "success",
        error_type: str | None = None,
    ) -> None:
        """
        Record a request observation asynchronously.

        This method queues the metric for background processing,
        returning immediately without blocking.

        Parameters
        ----------
        operation : str
            Operation name.
        duration_seconds : float
            Request duration.
        status : {"success", "failure"}
            Request status.
        error_type : str, optional
            Error type if status="failure".
        """
        await _ensure_worker_started()

        if _metric_queue is None:
            # Fallback to synchronous if queue not available
            self._base.observe_request(operation, duration_seconds, status, error_type)
            return

        # Try to add to queue
        try:
            await asyncio.wait_for(
                _metric_queue.put(
                    {
                        "metrics": self._base,
                        "method": "observe_request",
                        "args": (operation, duration_seconds),
                        "kwargs": {"status": status, "error_type": error_type},
                    }
                ),
                timeout=0.001,  # Very short timeout
            )
        except TimeoutError:  # pragma: no cover
            # Queue is full, drop metric with warning
            logger.warning(
                "metric_queue_full",
                operation=operation,
                queue_size=_metric_queue.qsize(),
            )
            # Record dropped metric in self-metrics
            try:
                from obskit.metrics.self_metrics import record_dropped_metric

                record_dropped_metric(operation, "queue_full")
            except Exception:  # nosec B110 - dropped metric recording is best-effort
                pass  # Self-metrics recording failure is non-critical
        except Exception as e:
            logger.error(
                "async_metric_queue_failed",
                error=str(e),
                error_type=type(e).__name__,
            )
            # Record error in self-metrics
            try:
                from obskit.metrics.self_metrics import record_error

                record_error("async_recording", type(e).__name__)
            except Exception:  # pragma: no cover  # nosec B110 - error recording is best-effort
                pass  # Self-metrics recording failure is non-critical
            # Fallback to synchronous
            self._base.observe_request(operation, duration_seconds, status, error_type)


async def shutdown_async_recording() -> None:
    """Shutdown async metric recording worker."""
    global _metric_worker_task, _metric_queue

    if _metric_worker_task:
        _metric_worker_task.cancel()
        # Await the cancelled task to ensure it completes cleanup
        # Suppress CancelledError as it's expected when cancelling a task
        # The await is necessary to ensure proper task cleanup, even though
        # the exception is suppressed
        try:
            await _metric_worker_task
        except asyncio.CancelledError:
            # Expected when cancelling a task - task cleanup is complete
            pass

    if _metric_queue:
        # Process remaining items
        while not _metric_queue.empty():
            try:
                metric_data = _metric_queue.get_nowait()
                metrics_instance = metric_data["metrics"]
                method_name = metric_data["method"]
                args = metric_data.get("args", ())
                kwargs = metric_data.get("kwargs", {})
                method = getattr(metrics_instance, str(method_name), None)
                if method is not None and callable(method):  # pragma: no branch
                    method(*args, **kwargs)
            except Exception:  # nosec B110 - shutdown cleanup errors are non-critical
                pass  # Ignore errors during shutdown cleanup - already logging errors above

    _metric_worker_task = None
    _metric_queue = None
