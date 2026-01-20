"""
Consumer Lag Tracking
=====================

Track message queue consumer lag for RabbitMQ, Kafka, etc.

Features:
- Lag tracking by queue/topic
- Lag growth rate
- Alerting on high lag
- Consumer velocity metrics

Example:
    from obskit.consumer_lag import ConsumerLagTracker, QueueType

    lag_tracker = ConsumerLagTracker("orders", queue_type=QueueType.RABBITMQ)

    # Update lag (typically from queue stats)
    lag_tracker.set_lag(messages=1000, bytes=5_000_000)

    # Track processing
    lag_tracker.message_consumed()
    lag_tracker.messages_consumed(count=10)
"""

import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from prometheus_client import Counter, Gauge

from obskit.logging import get_logger

logger = get_logger(__name__)


# =============================================================================
# Prometheus Metrics
# =============================================================================

CONSUMER_LAG_MESSAGES = Gauge(
    "consumer_lag_messages",
    "Number of messages behind",
    ["queue_name", "queue_type", "consumer_group"],
)

CONSUMER_LAG_BYTES = Gauge(
    "consumer_lag_bytes", "Bytes behind", ["queue_name", "queue_type", "consumer_group"]
)

CONSUMER_LAG_SECONDS = Gauge(
    "consumer_lag_seconds",
    "Estimated time to catch up",
    ["queue_name", "queue_type", "consumer_group"],
)

CONSUMER_LAG_GROWTH_RATE = Gauge(
    "consumer_lag_growth_rate",
    "Rate of lag change (positive = growing)",
    ["queue_name", "queue_type", "consumer_group"],
)

CONSUMER_VELOCITY = Gauge(
    "consumer_velocity_messages_per_second",
    "Messages consumed per second",
    ["queue_name", "queue_type", "consumer_group"],
)

CONSUMER_MESSAGES_TOTAL = Counter(
    "consumer_messages_total",
    "Total messages consumed",
    ["queue_name", "queue_type", "consumer_group"],
)

CONSUMER_LAG_HIGH_EVENTS = Counter(
    "consumer_lag_high_events_total",
    "Times lag exceeded threshold",
    ["queue_name", "queue_type", "consumer_group"],
)


# =============================================================================
# Enums and Data Classes
# =============================================================================


class QueueType(Enum):
    """Type of message queue."""

    RABBITMQ = "rabbitmq"
    KAFKA = "kafka"
    SQS = "sqs"
    REDIS = "redis"
    CUSTOM = "custom"


@dataclass
class LagSample:
    """A single lag measurement."""

    timestamp: datetime
    messages: int
    bytes: int = 0


@dataclass
class ConsumerLagStats:
    """Statistics for consumer lag."""

    queue_name: str
    queue_type: QueueType
    consumer_group: str
    current_lag_messages: int = 0
    current_lag_bytes: int = 0
    lag_growth_rate: float = 0.0  # messages/second
    consumer_velocity: float = 0.0  # messages/second
    estimated_catch_up_seconds: float = 0.0
    total_consumed: int = 0
    is_falling_behind: bool = False
    last_updated: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "queue_name": self.queue_name,
            "queue_type": self.queue_type.value,
            "consumer_group": self.consumer_group,
            "current_lag_messages": self.current_lag_messages,
            "current_lag_bytes": self.current_lag_bytes,
            "lag_growth_rate": self.lag_growth_rate,
            "consumer_velocity": self.consumer_velocity,
            "estimated_catch_up_seconds": self.estimated_catch_up_seconds,
            "total_consumed": self.total_consumed,
            "is_falling_behind": self.is_falling_behind,
            "last_updated": self.last_updated.isoformat(),
        }


# =============================================================================
# Consumer Lag Tracker
# =============================================================================


class ConsumerLagTracker:
    """
    Track consumer lag for a message queue.

    Parameters
    ----------
    queue_name : str
        Name of the queue/topic
    queue_type : QueueType
        Type of queue
    consumer_group : str
        Consumer group name
    lag_threshold : int
        Lag threshold for alerting
    window_seconds : int
        Window for rate calculations
    on_high_lag : callable, optional
        Callback when lag exceeds threshold
    """

    def __init__(
        self,
        queue_name: str,
        queue_type: QueueType = QueueType.RABBITMQ,
        consumer_group: str = "default",
        lag_threshold: int = 10000,
        window_seconds: int = 60,
        on_high_lag: Callable[[str, int], None] | None = None,
    ):
        self.queue_name = queue_name
        self.queue_type = queue_type
        self.consumer_group = consumer_group
        self.lag_threshold = lag_threshold
        self.window_seconds = window_seconds
        self.on_high_lag = on_high_lag

        self._current_lag = 0
        self._current_lag_bytes = 0
        self._lag_samples: list[LagSample] = []
        self._consumed_timestamps: list[datetime] = []
        self._total_consumed = 0
        self._lock = threading.Lock()

        # Cooldown for high lag alerts
        self._last_high_lag_alert: datetime | None = None
        self._alert_cooldown = timedelta(minutes=5)

    def set_lag(
        self,
        messages: int,
        bytes: int = 0,
    ):
        """
        Set current lag.

        Parameters
        ----------
        messages : int
            Number of messages behind
        bytes : int
            Bytes behind (optional)
        """
        now = datetime.utcnow()

        with self._lock:
            self._current_lag = messages
            self._current_lag_bytes = bytes

            # Record sample
            self._lag_samples.append(
                LagSample(
                    timestamp=now,
                    messages=messages,
                    bytes=bytes,
                )
            )

            # Cleanup old samples
            cutoff = now - timedelta(seconds=self.window_seconds)
            self._lag_samples = [s for s in self._lag_samples if s.timestamp > cutoff]

        # Update metrics
        labels = {
            "queue_name": self.queue_name,
            "queue_type": self.queue_type.value,
            "consumer_group": self.consumer_group,
        }

        CONSUMER_LAG_MESSAGES.labels(**labels).set(messages)
        CONSUMER_LAG_BYTES.labels(**labels).set(bytes)

        # Calculate growth rate
        growth_rate = self._calculate_growth_rate()
        CONSUMER_LAG_GROWTH_RATE.labels(**labels).set(growth_rate)

        # Calculate estimated catch-up time
        velocity = self._calculate_velocity()
        if velocity > 0 and messages > 0:
            catch_up = messages / velocity
            CONSUMER_LAG_SECONDS.labels(**labels).set(catch_up)

        # Check threshold
        self._check_threshold(messages)

    def message_consumed(self):
        """Record a single message consumed."""
        self.messages_consumed(1)

    def messages_consumed(self, count: int = 1):
        """
        Record messages consumed.

        Parameters
        ----------
        count : int
            Number of messages consumed
        """
        now = datetime.utcnow()

        with self._lock:
            self._total_consumed += count

            # Record timestamps for velocity calculation
            for _ in range(count):
                self._consumed_timestamps.append(now)

            # Cleanup old timestamps
            cutoff = now - timedelta(seconds=self.window_seconds)
            self._consumed_timestamps = [t for t in self._consumed_timestamps if t > cutoff]

        labels = {
            "queue_name": self.queue_name,
            "queue_type": self.queue_type.value,
            "consumer_group": self.consumer_group,
        }

        CONSUMER_MESSAGES_TOTAL.labels(**labels).inc(count)

        # Update velocity
        velocity = self._calculate_velocity()
        CONSUMER_VELOCITY.labels(**labels).set(velocity)

    def _calculate_growth_rate(self) -> float:
        """Calculate lag growth rate (messages/second)."""
        with self._lock:
            if len(self._lag_samples) < 2:
                return 0.0

            oldest = self._lag_samples[0]
            newest = self._lag_samples[-1]

            time_diff = (newest.timestamp - oldest.timestamp).total_seconds()
            if time_diff <= 0:
                return 0.0

            message_diff = newest.messages - oldest.messages
            return message_diff / time_diff

    def _calculate_velocity(self) -> float:
        """Calculate consumer velocity (messages/second)."""
        with self._lock:
            if not self._consumed_timestamps:
                return 0.0

            now = datetime.utcnow()
            cutoff = now - timedelta(seconds=self.window_seconds)
            recent = [t for t in self._consumed_timestamps if t > cutoff]

            if not recent:
                return 0.0

            time_span = (now - recent[0]).total_seconds()
            if time_span <= 0:
                return 0.0

            return len(recent) / time_span

    def _check_threshold(self, lag: int):
        """Check if lag exceeds threshold."""
        if lag < self.lag_threshold:
            return

        now = datetime.utcnow()

        # Check cooldown
        if self._last_high_lag_alert:
            if now - self._last_high_lag_alert < self._alert_cooldown:
                return

        self._last_high_lag_alert = now

        labels = {
            "queue_name": self.queue_name,
            "queue_type": self.queue_type.value,
            "consumer_group": self.consumer_group,
        }

        CONSUMER_LAG_HIGH_EVENTS.labels(**labels).inc()

        logger.warning(
            "consumer_lag_high",
            queue_name=self.queue_name,
            consumer_group=self.consumer_group,
            lag=lag,
            threshold=self.lag_threshold,
        )

        if self.on_high_lag:
            self.on_high_lag(self.queue_name, lag)

    def get_stats(self) -> ConsumerLagStats:
        """Get current lag statistics."""
        with self._lock:
            growth_rate = self._calculate_growth_rate()
            velocity = self._calculate_velocity()

            catch_up = 0.0
            if velocity > 0 and self._current_lag > 0:
                catch_up = self._current_lag / velocity

            is_falling_behind = growth_rate > 0

            return ConsumerLagStats(
                queue_name=self.queue_name,
                queue_type=self.queue_type,
                consumer_group=self.consumer_group,
                current_lag_messages=self._current_lag,
                current_lag_bytes=self._current_lag_bytes,
                lag_growth_rate=growth_rate,
                consumer_velocity=velocity,
                estimated_catch_up_seconds=catch_up,
                total_consumed=self._total_consumed,
                is_falling_behind=is_falling_behind,
            )

    def is_healthy(self) -> bool:
        """Check if consumer is healthy (not falling behind)."""
        stats = self.get_stats()
        return stats.current_lag_messages < self.lag_threshold and not stats.is_falling_behind


# =============================================================================
# Registry
# =============================================================================

_lag_trackers: dict[str, ConsumerLagTracker] = {}
_lag_lock = threading.Lock()


def get_consumer_lag_tracker(
    queue_name: str,
    consumer_group: str = "default",
    **kwargs,
) -> ConsumerLagTracker:
    """Get or create a consumer lag tracker."""
    key = f"{queue_name}:{consumer_group}"

    if key not in _lag_trackers:
        with _lag_lock:
            if key not in _lag_trackers:
                _lag_trackers[key] = ConsumerLagTracker(
                    queue_name,
                    consumer_group=consumer_group,
                    **kwargs,
                )

    return _lag_trackers[key]


def get_all_consumer_lag_stats() -> dict[str, ConsumerLagStats]:
    """Get stats for all tracked consumers."""
    return {name: tracker.get_stats() for name, tracker in _lag_trackers.items()}
