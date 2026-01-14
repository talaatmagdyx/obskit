"""
Queue Message Tracker
=====================

This module provides tracking for message queue operations.
"""

from __future__ import annotations

import time
from collections.abc import Generator
from contextlib import contextmanager

from obskit.logging import get_logger
from obskit.metrics.golden import get_golden_signals
from obskit.metrics.red import get_red_metrics

logger = get_logger("obskit.queue.tracker")


class QueueTracker:
    """
    Tracks message queue operations with metrics and logging.

    Example
    -------
    >>> from obskit.queue import QueueTracker
    >>>
    >>> tracker = QueueTracker("orders_queue")
    >>>
    >>> async with tracker.track_message_processing("process_order"):
    ...     await process_order(message)
    """

    def __init__(self, queue_name: str) -> None:
        """
        Initialize queue tracker.

        Parameters
        ----------
        queue_name : str
            Name of the queue (e.g., "orders", "notifications").
        """
        self.queue_name = queue_name
        self.red_metrics = get_red_metrics()
        self.golden = get_golden_signals()

    @contextmanager
    def track_message_processing(
        self,
        operation: str,
        message_id: str | None = None,
    ) -> Generator[None, None, None]:
        """
        Track message processing with metrics and logging.

        Parameters
        ----------
        operation : str
            Operation name (e.g., "process_order", "send_notification").

        message_id : str, optional
            Message ID for correlation.

        Yields
        ------
        None
        """
        start_time = time.perf_counter()
        full_operation = f"{self.queue_name}.{operation}"

        try:
            logger.debug(
                "queue_message_processing_started",
                queue=self.queue_name,
                operation=operation,
                message_id=message_id,
            )

            yield

            duration_seconds = time.perf_counter() - start_time

            # Record metrics
            self.red_metrics.observe_request(
                operation=full_operation,
                duration_seconds=duration_seconds,
                status="success",
            )

            logger.debug(
                "queue_message_processing_completed",
                queue=self.queue_name,
                operation=operation,
                duration_ms=duration_seconds * 1000,
                message_id=message_id,
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

            logger.error(
                "queue_message_processing_failed",
                queue=self.queue_name,
                operation=operation,
                error=str(e),
                error_type=type(e).__name__,
                message_id=message_id,
                exc_info=True,
            )

            raise

    def set_queue_depth(self, depth: int) -> None:
        """
        Update queue depth metric.

        Parameters
        ----------
        depth : int
            Current queue depth (number of messages waiting).
        """
        self.golden.set_queue_depth(self.queue_name, depth)
        logger.debug(
            "queue_depth_updated",
            queue=self.queue_name,
            depth=depth,
        )


@contextmanager
def track_message_processing(
    operation: str,
    queue_name: str = "queue",
    message_id: str | None = None,
) -> Generator[None, None, None]:
    """
    Track message processing (convenience function).

    Parameters
    ----------
    operation : str
        Operation name.

    queue_name : str, optional
        Queue name. Default: "queue".

    message_id : str, optional
        Message ID for correlation.

    Example
    -------
    >>> from obskit.queue import track_message_processing
    >>>
    >>> async with track_message_processing("process_order", queue_name="orders"):
    ...     await process_order(message)
    """
    tracker = QueueTracker(queue_name)
    with tracker.track_message_processing(operation, message_id):
        yield


__all__ = ["QueueTracker", "track_message_processing"]
