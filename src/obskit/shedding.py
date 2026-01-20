"""
Load Shedding
=============

Graceful degradation under high load.

Features:
- Queue-based shedding
- Latency-based shedding
- Priority-based processing
- Adaptive shedding rates

Example:
    from obskit.shedding import LoadShedder, Priority

    shedder = LoadShedder(
        max_queue_size=1000,
        max_latency_ms=500,
        shed_percentage=0.1
    )

    if shedder.should_process(priority=Priority.HIGH):
        process_request()
    else:
        return service_unavailable()
"""

import random
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum
from typing import Any

from prometheus_client import Counter, Gauge

from obskit.logging import get_logger

logger = get_logger(__name__)


# =============================================================================
# Prometheus Metrics
# =============================================================================

SHEDDER_REQUESTS_TOTAL = Counter(
    "load_shedder_requests_total", "Total requests evaluated", ["shedder_name", "decision"]
)

SHEDDER_SHED_RATE = Gauge("load_shedder_shed_rate", "Current shedding rate (0-1)", ["shedder_name"])

SHEDDER_QUEUE_SIZE = Gauge("load_shedder_queue_size", "Current queue size", ["shedder_name"])

SHEDDER_LATENCY_MS = Gauge("load_shedder_latency_ms", "Current observed latency", ["shedder_name"])

SHEDDER_LOAD_LEVEL = Gauge("load_shedder_load_level", "Current load level (0-1)", ["shedder_name"])


# =============================================================================
# Enums and Data Classes
# =============================================================================


class Priority(IntEnum):
    """Request priority levels."""

    CRITICAL = 100  # Never shed
    HIGH = 75
    NORMAL = 50
    LOW = 25
    BACKGROUND = 0  # First to shed


@dataclass
class SheddingConfig:
    """Configuration for load shedding."""

    max_queue_size: int = 1000
    max_latency_ms: float = 500
    min_shed_rate: float = 0.0
    max_shed_rate: float = 0.9
    ramp_up_factor: float = 1.5
    ramp_down_factor: float = 0.9
    evaluation_window_seconds: float = 10.0
    priority_weights: dict[Priority, float] = field(
        default_factory=lambda: {
            Priority.CRITICAL: 0.0,  # Never shed
            Priority.HIGH: 0.1,
            Priority.NORMAL: 0.5,
            Priority.LOW: 0.8,
            Priority.BACKGROUND: 0.95,
        }
    )


@dataclass
class SheddingStats:
    """Statistics for load shedding."""

    shedder_name: str
    current_shed_rate: float
    current_queue_size: int
    current_latency_ms: float
    load_level: float
    requests_processed: int
    requests_shed: int
    shed_by_priority: dict[str, int]
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "shedder_name": self.shedder_name,
            "current_shed_rate": self.current_shed_rate,
            "current_queue_size": self.current_queue_size,
            "current_latency_ms": self.current_latency_ms,
            "load_level": self.load_level,
            "requests_processed": self.requests_processed,
            "requests_shed": self.requests_shed,
            "shed_by_priority": self.shed_by_priority,
            "timestamp": self.timestamp.isoformat(),
        }


# =============================================================================
# Load Shedder
# =============================================================================


class LoadShedder:
    """
    Load shedder for graceful degradation.

    Parameters
    ----------
    name : str
        Shedder name
    max_queue_size : int
        Maximum queue size before shedding
    max_latency_ms : float
        Maximum latency before shedding
    shed_percentage : float
        Base shedding percentage (0-1)
    adaptive : bool
        Enable adaptive shedding
    on_shed : callable, optional
        Callback when request is shed
    """

    def __init__(
        self,
        name: str = "default",
        max_queue_size: int = 1000,
        max_latency_ms: float = 500,
        shed_percentage: float = 0.1,
        adaptive: bool = True,
        on_shed: Callable[[Priority], None] | None = None,
    ):
        self.name = name
        self.config = SheddingConfig(
            max_queue_size=max_queue_size,
            max_latency_ms=max_latency_ms,
        )
        self.base_shed_rate = shed_percentage
        self.adaptive = adaptive
        self.on_shed = on_shed

        self._current_shed_rate = 0.0
        self._current_queue_size = 0
        self._current_latency_ms = 0.0
        self._latency_samples: list[float] = []
        self._requests_processed = 0
        self._requests_shed = 0
        self._shed_by_priority: dict[str, int] = {}
        self._lock = threading.Lock()
        self._last_evaluation = datetime.utcnow()

    def should_process(
        self,
        priority: Priority = Priority.NORMAL,
        queue_size: int | None = None,
        latency_ms: float | None = None,
    ) -> bool:
        """
        Check if request should be processed.

        Parameters
        ----------
        priority : Priority
            Request priority
        queue_size : int, optional
            Current queue size (for evaluation)
        latency_ms : float, optional
            Current latency (for evaluation)

        Returns
        -------
        bool
            Whether request should be processed
        """
        # Update metrics if provided
        if queue_size is not None:
            self._current_queue_size = queue_size
            SHEDDER_QUEUE_SIZE.labels(shedder_name=self.name).set(queue_size)

        if latency_ms is not None:
            with self._lock:
                self._latency_samples.append(latency_ms)
                if len(self._latency_samples) > 100:
                    self._latency_samples = self._latency_samples[-100:]
                self._current_latency_ms = sum(self._latency_samples) / len(self._latency_samples)
            SHEDDER_LATENCY_MS.labels(shedder_name=self.name).set(self._current_latency_ms)

        # Evaluate shedding rate
        if self.adaptive:
            self._evaluate_shed_rate()

        # Critical priority never shed
        if priority == Priority.CRITICAL:
            SHEDDER_REQUESTS_TOTAL.labels(shedder_name=self.name, decision="process").inc()
            self._requests_processed += 1
            return True

        # Get effective shed rate for this priority
        priority_weight = self.config.priority_weights.get(priority, 0.5)
        effective_shed_rate = self._current_shed_rate * priority_weight

        # Random decision based on shed rate
        should_shed = random.random() < effective_shed_rate

        if should_shed:
            SHEDDER_REQUESTS_TOTAL.labels(shedder_name=self.name, decision="shed").inc()
            self._requests_shed += 1

            priority_name = priority.name
            self._shed_by_priority[priority_name] = self._shed_by_priority.get(priority_name, 0) + 1

            logger.debug(
                "request_shed",
                shedder_name=self.name,
                priority=priority_name,
                shed_rate=self._current_shed_rate,
                effective_rate=effective_shed_rate,
            )

            if self.on_shed:
                self.on_shed(priority)

            return False
        else:
            SHEDDER_REQUESTS_TOTAL.labels(shedder_name=self.name, decision="process").inc()
            self._requests_processed += 1
            return True

    def _evaluate_shed_rate(self):
        """Evaluate and adjust shedding rate."""
        now = datetime.utcnow()

        # Only evaluate periodically
        if (now - self._last_evaluation).total_seconds() < self.config.evaluation_window_seconds:
            return

        self._last_evaluation = now

        # Calculate load level based on queue and latency
        queue_load = 0.0
        if self.config.max_queue_size > 0:
            queue_load = min(1.0, self._current_queue_size / self.config.max_queue_size)

        latency_load = 0.0
        if self.config.max_latency_ms > 0:
            latency_load = min(1.0, self._current_latency_ms / self.config.max_latency_ms)

        # Combined load level (max of the two)
        load_level = max(queue_load, latency_load)
        SHEDDER_LOAD_LEVEL.labels(shedder_name=self.name).set(load_level)

        # Adjust shed rate based on load
        if load_level > 0.8:
            # High load - increase shedding
            new_rate = min(
                self.config.max_shed_rate,
                self._current_shed_rate * self.config.ramp_up_factor + self.base_shed_rate,
            )
        elif load_level < 0.5:
            # Low load - decrease shedding
            new_rate = max(
                self.config.min_shed_rate, self._current_shed_rate * self.config.ramp_down_factor
            )
        else:
            # Medium load - maintain or slightly adjust
            new_rate = self._current_shed_rate

        self._current_shed_rate = new_rate
        SHEDDER_SHED_RATE.labels(shedder_name=self.name).set(new_rate)

        if new_rate > 0.1:
            logger.info(
                "shed_rate_adjusted",
                shedder_name=self.name,
                load_level=load_level,
                shed_rate=new_rate,
                queue_size=self._current_queue_size,
                latency_ms=self._current_latency_ms,
            )

    def set_queue_size(self, size: int):
        """Update current queue size."""
        self._current_queue_size = size
        SHEDDER_QUEUE_SIZE.labels(shedder_name=self.name).set(size)

    def record_latency(self, latency_ms: float):
        """Record a latency observation."""
        with self._lock:
            self._latency_samples.append(latency_ms)
            if len(self._latency_samples) > 100:
                self._latency_samples = self._latency_samples[-100:]
            self._current_latency_ms = sum(self._latency_samples) / len(self._latency_samples)
        SHEDDER_LATENCY_MS.labels(shedder_name=self.name).set(self._current_latency_ms)

    def force_shed_rate(self, rate: float):
        """Force a specific shed rate (disables adaptive)."""
        self._current_shed_rate = min(self.config.max_shed_rate, max(0, rate))
        SHEDDER_SHED_RATE.labels(shedder_name=self.name).set(self._current_shed_rate)

        logger.info(
            "shed_rate_forced",
            shedder_name=self.name,
            shed_rate=self._current_shed_rate,
        )

    def reset(self):
        """Reset shedding state."""
        self._current_shed_rate = 0.0
        self._latency_samples = []
        self._current_latency_ms = 0.0

        SHEDDER_SHED_RATE.labels(shedder_name=self.name).set(0)
        SHEDDER_LATENCY_MS.labels(shedder_name=self.name).set(0)

    def get_stats(self) -> SheddingStats:
        """Get current shedding statistics."""
        queue_load = 0.0
        if self.config.max_queue_size > 0:
            queue_load = min(1.0, self._current_queue_size / self.config.max_queue_size)

        latency_load = 0.0
        if self.config.max_latency_ms > 0:
            latency_load = min(1.0, self._current_latency_ms / self.config.max_latency_ms)

        return SheddingStats(
            shedder_name=self.name,
            current_shed_rate=self._current_shed_rate,
            current_queue_size=self._current_queue_size,
            current_latency_ms=self._current_latency_ms,
            load_level=max(queue_load, latency_load),
            requests_processed=self._requests_processed,
            requests_shed=self._requests_shed,
            shed_by_priority=dict(self._shed_by_priority),
        )


# =============================================================================
# Factory
# =============================================================================

_shedders: dict[str, LoadShedder] = {}
_shedders_lock = threading.Lock()


def get_load_shedder(name: str = "default", **kwargs) -> LoadShedder:
    """Get or create a load shedder."""
    if name not in _shedders:
        with _shedders_lock:
            if name not in _shedders:
                _shedders[name] = LoadShedder(name=name, **kwargs)

    return _shedders[name]
