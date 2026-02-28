"""
Dead Letter Queue Metrics
=========================

Track messages sent to dead letter queues.

Features:
- DLQ message counts by reason
- Message age tracking
- DLQ processing status
- Alerts on DLQ growth

Example:
    from obskit.dlq import DLQTracker

    dlq = DLQTracker("orders_dlq")

    # Track message sent to DLQ
    dlq.track_message_sent(
        original_queue="orders",
        reason="max_retries_exceeded",
        message_age_seconds=300,
        message_id="msg-123"
    )

    # Track DLQ processing
    with dlq.track_processing("msg-123"):
        reprocess_message()
"""

import threading
import time
from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from prometheus_client import Counter, Gauge, Histogram

from obskit.logging import get_logger

logger = get_logger(__name__)


# =============================================================================
# Prometheus Metrics
# =============================================================================

DLQ_MESSAGES_TOTAL = Counter(
    "dlq_messages_total", "Total messages sent to DLQ", ["dlq_name", "original_queue", "reason"]
)

DLQ_MESSAGE_AGE = Histogram(
    "dlq_message_age_seconds",
    "Age of messages when sent to DLQ",
    ["dlq_name", "original_queue"],
    buckets=(1, 5, 10, 30, 60, 300, 600, 1800, 3600, 7200, 86400),
)

DLQ_SIZE = Gauge("dlq_size", "Current number of messages in DLQ", ["dlq_name"])

DLQ_OLDEST_MESSAGE_AGE = Gauge(
    "dlq_oldest_message_age_seconds", "Age of oldest message in DLQ", ["dlq_name"]
)

DLQ_PROCESSING_TOTAL = Counter(
    "dlq_processing_total", "Total DLQ messages processed", ["dlq_name", "status"]
)

DLQ_PROCESSING_LATENCY = Histogram(
    "dlq_processing_latency_seconds",
    "DLQ message processing latency",
    ["dlq_name"],
    buckets=(0.1, 0.5, 1, 5, 10, 30, 60, 120, 300),
)

DLQ_REPROCESSED_TOTAL = Counter(
    "dlq_reprocessed_total", "Total messages reprocessed from DLQ", ["dlq_name", "success"]
)


# =============================================================================
# Enums and Data Classes
# =============================================================================


class DLQReason(Enum):
    """Reasons for sending to DLQ."""

    MAX_RETRIES = "max_retries_exceeded"
    PARSE_ERROR = "parse_error"
    VALIDATION_ERROR = "validation_error"
    HANDLER_ERROR = "handler_error"
    TIMEOUT = "timeout"
    REJECTED = "rejected"
    EXPIRED = "expired"
    UNKNOWN = "unknown"


@dataclass
class DLQMessage:
    """Represents a message in DLQ."""

    message_id: str
    original_queue: str
    reason: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    age_seconds: float = 0.0
    retry_count: int = 0
    error_message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "message_id": self.message_id,
            "original_queue": self.original_queue,
            "reason": self.reason,
            "timestamp": self.timestamp.isoformat(),
            "age_seconds": self.age_seconds,
            "retry_count": self.retry_count,
            "error_message": self.error_message,
            "metadata": self.metadata,
        }


@dataclass
class DLQStats:
    """Statistics for a DLQ."""

    dlq_name: str
    total_messages: int = 0
    current_size: int = 0
    oldest_message_age_seconds: float = 0.0
    messages_by_reason: dict[str, int] = field(default_factory=dict)
    messages_by_queue: dict[str, int] = field(default_factory=dict)
    processing_success_rate: float = 1.0
    avg_processing_time_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "dlq_name": self.dlq_name,
            "total_messages": self.total_messages,
            "current_size": self.current_size,
            "oldest_message_age_seconds": self.oldest_message_age_seconds,
            "messages_by_reason": self.messages_by_reason,
            "messages_by_queue": self.messages_by_queue,
            "processing_success_rate": self.processing_success_rate,
            "avg_processing_time_seconds": self.avg_processing_time_seconds,
        }


# =============================================================================
# DLQ Tracker
# =============================================================================


class DLQTracker:
    """
    Track Dead Letter Queue metrics.

    Parameters
    ----------
    dlq_name : str
        Name of the DLQ
    alert_threshold : int
        Number of messages that triggers alert
    on_threshold_exceeded : callable, optional
        Callback when threshold exceeded
    """

    def __init__(
        self,
        dlq_name: str,
        alert_threshold: int = 100,
        on_threshold_exceeded: Callable[[str, int], None] | None = None,
    ):
        self.dlq_name = dlq_name
        self.alert_threshold = alert_threshold
        self.on_threshold_exceeded = on_threshold_exceeded

        self._messages: dict[str, DLQMessage] = {}
        self._total_messages = 0
        self._processing_times: list[float] = []
        self._processing_success = 0
        self._processing_failure = 0
        self._lock = threading.Lock()

    def track_message_sent(
        self,
        original_queue: str,
        reason: str,
        message_id: str | None = None,
        message_age_seconds: float = 0.0,
        retry_count: int = 0,
        error_message: str | None = None,
        **metadata,
    ):
        """
        Track a message sent to DLQ.

        Parameters
        ----------
        original_queue : str
            Original queue the message came from
        reason : str
            Reason for DLQ (use DLQReason values)
        message_id : str, optional
            Message ID
        message_age_seconds : float
            How old the message was when sent to DLQ
        retry_count : int
            Number of retries before DLQ
        error_message : str, optional
            Error message
        **metadata
            Additional metadata
        """
        msg_id = message_id or f"dlq-{time.time()}"

        message = DLQMessage(
            message_id=msg_id,
            original_queue=original_queue,
            reason=reason,
            age_seconds=message_age_seconds,
            retry_count=retry_count,
            error_message=error_message,
            metadata=metadata,
        )

        with self._lock:
            self._messages[msg_id] = message
            self._total_messages += 1
            current_size = len(self._messages)

        # Update metrics
        DLQ_MESSAGES_TOTAL.labels(
            dlq_name=self.dlq_name, original_queue=original_queue, reason=reason
        ).inc()

        DLQ_MESSAGE_AGE.labels(dlq_name=self.dlq_name, original_queue=original_queue).observe(
            message_age_seconds
        )

        DLQ_SIZE.labels(dlq_name=self.dlq_name).set(current_size)

        # Update oldest message age
        self._update_oldest_age()

        # Log
        logger.warning(
            "message_sent_to_dlq",
            dlq_name=self.dlq_name,
            original_queue=original_queue,
            reason=reason,
            message_id=msg_id,
            message_age_seconds=message_age_seconds,
            retry_count=retry_count,
        )

        # Check threshold
        if current_size >= self.alert_threshold:
            logger.error(
                "dlq_threshold_exceeded",
                dlq_name=self.dlq_name,
                current_size=current_size,
                threshold=self.alert_threshold,
            )
            if self.on_threshold_exceeded:
                self.on_threshold_exceeded(self.dlq_name, current_size)

    @contextmanager
    def track_processing(
        self,
        message_id: str,
    ) -> Generator[None, None, None]:
        """
        Track processing of a DLQ message.

        Parameters
        ----------
        message_id : str
            ID of message being processed
        """
        start_time = time.perf_counter()
        success = True

        try:
            yield
        except Exception:
            success = False
            raise
        finally:
            duration = time.perf_counter() - start_time

            with self._lock:
                self._processing_times.append(duration)
                if len(self._processing_times) > 1000:
                    self._processing_times = self._processing_times[-1000:]

                if success:
                    self._processing_success += 1
                    # Remove from local tracking
                    if message_id in self._messages:
                        del self._messages[message_id]
                else:
                    self._processing_failure += 1

            status = "success" if success else "failure"

            DLQ_PROCESSING_TOTAL.labels(dlq_name=self.dlq_name, status=status).inc()

            DLQ_PROCESSING_LATENCY.labels(dlq_name=self.dlq_name).observe(duration)

            DLQ_REPROCESSED_TOTAL.labels(dlq_name=self.dlq_name, success=str(success).lower()).inc()

            # Update size
            DLQ_SIZE.labels(dlq_name=self.dlq_name).set(len(self._messages))

            logger.info(
                "dlq_message_processed",
                dlq_name=self.dlq_name,
                message_id=message_id,
                success=success,
                duration_seconds=duration,
            )

    def track_message_removed(self, message_id: str, reason: str = "processed"):
        """Track a message removed from DLQ."""
        with self._lock:
            if message_id in self._messages:
                del self._messages[message_id]

        DLQ_SIZE.labels(dlq_name=self.dlq_name).set(len(self._messages))
        self._update_oldest_age()

    def set_dlq_size(self, size: int):
        """Manually set DLQ size (from external source)."""
        DLQ_SIZE.labels(dlq_name=self.dlq_name).set(size)

    def set_oldest_message_age(self, age_seconds: float):
        """Manually set oldest message age."""
        DLQ_OLDEST_MESSAGE_AGE.labels(dlq_name=self.dlq_name).set(age_seconds)

    def _update_oldest_age(self):
        """Update oldest message age metric."""
        with self._lock:
            if not self._messages:
                DLQ_OLDEST_MESSAGE_AGE.labels(dlq_name=self.dlq_name).set(0)
                return

            oldest = min(self._messages.values(), key=lambda m: m.timestamp)
            age = (datetime.utcnow() - oldest.timestamp).total_seconds()
            DLQ_OLDEST_MESSAGE_AGE.labels(dlq_name=self.dlq_name).set(age)

    def get_stats(self) -> DLQStats:
        """Get current DLQ statistics."""
        with self._lock:
            messages_by_reason: dict[str, int] = {}
            messages_by_queue: dict[str, int] = {}

            for msg in self._messages.values():
                messages_by_reason[msg.reason] = messages_by_reason.get(msg.reason, 0) + 1
                messages_by_queue[msg.original_queue] = (
                    messages_by_queue.get(msg.original_queue, 0) + 1
                )

            oldest_age = 0.0
            if self._messages:
                oldest = min(self._messages.values(), key=lambda m: m.timestamp)
                oldest_age = (datetime.utcnow() - oldest.timestamp).total_seconds()

            total_processed = self._processing_success + self._processing_failure
            success_rate = 1.0
            if total_processed > 0:
                success_rate = self._processing_success / total_processed

            avg_processing = 0.0
            if self._processing_times:
                avg_processing = sum(self._processing_times) / len(self._processing_times)

            return DLQStats(
                dlq_name=self.dlq_name,
                total_messages=self._total_messages,
                current_size=len(self._messages),
                oldest_message_age_seconds=oldest_age,
                messages_by_reason=messages_by_reason,
                messages_by_queue=messages_by_queue,
                processing_success_rate=success_rate,
                avg_processing_time_seconds=avg_processing,
            )

    def get_messages(self, limit: int = 100) -> list[DLQMessage]:
        """Get messages currently in DLQ."""
        with self._lock:
            messages = list(self._messages.values())
            messages.sort(key=lambda m: m.timestamp)
            return messages[:limit]


# =============================================================================
# Registry
# =============================================================================

_dlq_trackers: dict[str, DLQTracker] = {}
_dlq_lock = threading.Lock()


def get_dlq_tracker(
    dlq_name: str,
    **kwargs,
) -> DLQTracker:
    """Get or create a DLQ tracker."""
    if dlq_name not in _dlq_trackers:
        with _dlq_lock:
            if dlq_name not in _dlq_trackers:
                _dlq_trackers[dlq_name] = DLQTracker(dlq_name, **kwargs)

    return _dlq_trackers[dlq_name]


def get_all_dlq_stats() -> dict[str, DLQStats]:
    """Get stats for all tracked DLQs."""
    return {name: tracker.get_stats() for name, tracker in _dlq_trackers.items()}
