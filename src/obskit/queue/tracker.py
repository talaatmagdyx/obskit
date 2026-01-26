"""
Queue Message Tracker
=====================

This module provides tracking for message queue operations with
support for business context and comprehensive metrics.

Features:
- RED metrics (Rate, Errors, Duration) for queue operations
- Business context tracking (tenant_id, company_id)
- Message metadata tracking (redelivered, message_age)
- Queue depth monitoring via Golden Signals
"""

from __future__ import annotations

import time
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

from prometheus_client import Counter

from obskit.logging import get_logger
from obskit.metrics.golden import get_golden_signals
from obskit.metrics.red import get_red_metrics

logger = get_logger("obskit.queue.tracker")


# Additional metrics for queue tracking
QUEUE_MESSAGES_RECEIVED = Counter(
    "obskit_queue_messages_received_total",
    "Total messages received from queue",
    ["queue", "redelivered"],
)

QUEUE_MESSAGES_ACKED = Counter(
    "obskit_queue_messages_acked_total",
    "Total messages acknowledged",
    ["queue"],
)

QUEUE_MESSAGES_NACKED = Counter(
    "obskit_queue_messages_nacked_total",
    "Total messages negatively acknowledged",
    ["queue", "requeue"],
)


@dataclass
class MessageContext:
    """
    Context for message processing with business data.

    Use this to pass business context through message processing
    for enriched logging and metrics.

    Example
    -------
    >>> ctx = MessageContext(
    ...     message_id="msg-123",
    ...     tenant_id="company-456",
    ...     correlation_id="corr-789",
    ... )
    >>> with tracker.track_message("process", context=ctx):
    ...     process_message(message)
    """

    message_id: str | None = None
    correlation_id: str | None = None
    tenant_id: str | None = None
    redelivered: bool = False
    message_age_ms: float | None = None
    delivery_tag: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for logging (filters None values)."""
        result = {
            "message_id": self.message_id,
            "correlation_id": self.correlation_id,
            "tenant_id": self.tenant_id,
            "redelivered": self.redelivered,
            "message_age_ms": self.message_age_ms,
            "delivery_tag": self.delivery_tag,
        }
        result.update(self.extra)
        return {k: v for k, v in result.items() if v is not None}


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
    def track_message(
        self,
        operation: str,
        context: MessageContext | None = None,
    ) -> Generator[MessageContext, None, None]:
        """
        Track message processing with full business context.

        Enhanced version of track_message_processing that supports
        business context and yields a mutable context object.

        Parameters
        ----------
        operation : str
            Operation name (e.g., "process_order", "upload_media").
        context : MessageContext, optional
            Business context for the message.

        Yields
        ------
        MessageContext
            The context object (can be modified during processing).

        Example
        -------
        >>> tracker = QueueTracker("orders")
        >>> ctx = MessageContext(message_id="123", tenant_id="company-456")
        >>> with tracker.track_message("process_order", ctx) as context:
        ...     # context can be enriched during processing
        ...     context.extra["order_id"] = order.id
        ...     process_order(order)
        """
        ctx = context or MessageContext()
        start_time = time.perf_counter()
        full_operation = f"{self.queue_name}.{operation}"

        logger.info(
            "queue_message_started",
            queue=self.queue_name,
            operation=operation,
            **ctx.to_dict(),
        )

        try:
            yield ctx

            duration_seconds = time.perf_counter() - start_time
            duration_ms = duration_seconds * 1000

            # Record success metrics
            self.red_metrics.observe_request(
                operation=full_operation,
                duration_seconds=duration_seconds,
                status="success",
            )

            logger.info(
                "queue_message_completed",
                queue=self.queue_name,
                operation=operation,
                duration_ms=round(duration_ms, 2),
                success=True,
                **ctx.to_dict(),
            )

        except Exception as e:
            duration_seconds = time.perf_counter() - start_time
            duration_ms = duration_seconds * 1000

            # Record failure metrics
            self.red_metrics.observe_request(
                operation=full_operation,
                duration_seconds=duration_seconds,
                status="failure",
                error_type=type(e).__name__,
            )

            logger.error(
                "queue_message_failed",
                queue=self.queue_name,
                operation=operation,
                duration_ms=round(duration_ms, 2),
                error=str(e),
                error_type=type(e).__name__,
                success=False,
                **ctx.to_dict(),
            )

            raise

    def track_message_received(
        self,
        message_size_bytes: int | None = None,
        redelivered: bool = False,
        message_age_ms: float | None = None,
        delivery_tag: int | None = None,
        **extra: Any,
    ) -> None:
        """
        Log when a message is received from queue.

        Parameters
        ----------
        message_size_bytes : int, optional
            Size of the message in bytes.
        redelivered : bool
            Whether this is a redelivered message.
        message_age_ms : float, optional
            Age of the message since published.
        delivery_tag : int, optional
            Broker-specific delivery tag.
        **extra
            Additional context fields.
        """
        QUEUE_MESSAGES_RECEIVED.labels(
            queue=self.queue_name,
            redelivered=str(redelivered).lower(),
        ).inc()

        logger.info(
            "queue_message_received",
            queue=self.queue_name,
            message_size_bytes=message_size_bytes,
            redelivered=redelivered,
            message_age_ms=message_age_ms,
            delivery_tag=delivery_tag,
            **extra,
        )

        if redelivered:
            logger.warning(
                "queue_message_redelivered",
                queue=self.queue_name,
                delivery_tag=delivery_tag,
            )

    def track_message_acked(self, delivery_tag: int | None = None) -> None:
        """
        Log when a message is acknowledged.

        Parameters
        ----------
        delivery_tag : int, optional
            Broker-specific delivery tag.
        """
        QUEUE_MESSAGES_ACKED.labels(queue=self.queue_name).inc()

        logger.debug(
            "queue_message_acked",
            queue=self.queue_name,
            delivery_tag=delivery_tag,
        )

    def track_message_nacked(
        self,
        delivery_tag: int | None = None,
        requeue: bool = False,
        reason: str | None = None,
    ) -> None:
        """
        Log when a message is negatively acknowledged.

        Parameters
        ----------
        delivery_tag : int, optional
            Broker-specific delivery tag.
        requeue : bool
            Whether the message will be requeued.
        reason : str, optional
            Reason for the nack.
        """
        QUEUE_MESSAGES_NACKED.labels(
            queue=self.queue_name,
            requeue=str(requeue).lower(),
        ).inc()

        logger.warning(
            "queue_message_nacked",
            queue=self.queue_name,
            delivery_tag=delivery_tag,
            requeue=requeue,
            reason=reason,
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


__all__ = [
    "MessageContext",
    "QueueTracker",
    "track_message_processing",
]
