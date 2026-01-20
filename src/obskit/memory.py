"""
Memory and GC Metrics
=====================

Track Python memory usage and garbage collection.

Features:
- Memory usage (RSS, heap, etc.)
- GC collection tracking
- Memory leak detection
- Object count tracking

Example:
    from obskit.memory import MemoryTracker, start_memory_tracking

    # Start background tracking
    start_memory_tracking(interval_seconds=30)

    # Or manual tracking
    tracker = MemoryTracker()
    stats = tracker.collect()
    print(f"Memory: {stats.rss_mb} MB")
"""

import gc
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from prometheus_client import Counter, Gauge, Histogram

from obskit.logging import get_logger

logger = get_logger(__name__)

# Try to import psutil for detailed memory info
try:
    import psutil

    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


# =============================================================================
# Prometheus Metrics (Lazy Initialization)
# =============================================================================

_metrics_initialized = False
MEMORY_RSS_BYTES: Gauge | None = None
MEMORY_VMS_BYTES: Gauge | None = None
MEMORY_HEAP_BYTES: Gauge | None = None
MEMORY_PERCENT: Gauge | None = None
GC_COLLECTIONS_TOTAL: Counter | None = None
GC_COLLECTED_OBJECTS: Counter | None = None
GC_UNCOLLECTABLE_OBJECTS: Gauge | None = None
GC_DURATION_SECONDS: Histogram | None = None
OBJECT_COUNT: Gauge | None = None


def _init_metrics() -> None:
    """Initialize Prometheus metrics lazily."""
    global _metrics_initialized
    global MEMORY_RSS_BYTES, MEMORY_VMS_BYTES, MEMORY_HEAP_BYTES, MEMORY_PERCENT
    global GC_COLLECTIONS_TOTAL, GC_COLLECTED_OBJECTS, GC_UNCOLLECTABLE_OBJECTS
    global GC_DURATION_SECONDS, OBJECT_COUNT

    if _metrics_initialized:
        return

    try:
        MEMORY_RSS_BYTES = Gauge("process_memory_rss_bytes", "Resident Set Size in bytes")
        MEMORY_VMS_BYTES = Gauge("process_memory_vms_bytes", "Virtual Memory Size in bytes")
        MEMORY_HEAP_BYTES = Gauge("python_memory_heap_bytes", "Python heap memory usage")
        MEMORY_PERCENT = Gauge("process_memory_percent", "Memory usage percentage")
        GC_COLLECTIONS_TOTAL = Counter(
            "python_gc_collections_total", "Total garbage collections", ["generation"]
        )
        GC_COLLECTED_OBJECTS = Counter(
            "python_gc_collected_objects_total", "Total objects collected by GC", ["generation"]
        )
        GC_UNCOLLECTABLE_OBJECTS = Gauge(
            "python_gc_uncollectable_objects", "Number of uncollectable objects"
        )
        GC_DURATION_SECONDS = Histogram(
            "python_gc_duration_seconds",
            "GC pause duration",
            ["generation"],
            buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
        )
        OBJECT_COUNT = Gauge(
            "python_objects_count", "Number of Python objects by type", ["object_type"]
        )
        _metrics_initialized = True
    except ValueError:
        # Metrics already registered (happens in tests)
        _metrics_initialized = True


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class MemoryStats:
    """Memory statistics."""

    rss_bytes: int = 0
    vms_bytes: int = 0
    heap_bytes: int = 0
    rss_mb: float = 0.0
    vms_mb: float = 0.0
    heap_mb: float = 0.0
    percent: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rss_bytes": self.rss_bytes,
            "vms_bytes": self.vms_bytes,
            "heap_bytes": self.heap_bytes,
            "rss_mb": self.rss_mb,
            "vms_mb": self.vms_mb,
            "heap_mb": self.heap_mb,
            "percent": self.percent,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class GCStats:
    """Garbage collection statistics."""

    collections: dict[int, int] = field(default_factory=dict)
    collected: dict[int, int] = field(default_factory=dict)
    uncollectable: int = 0
    thresholds: tuple = (700, 10, 10)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "collections": self.collections,
            "collected": self.collected,
            "uncollectable": self.uncollectable,
            "thresholds": self.thresholds,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class ObjectStats:
    """Object count statistics."""

    total_objects: int = 0
    by_type: dict[str, int] = field(default_factory=dict)
    top_types: list[tuple] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_objects": self.total_objects,
            "by_type": self.by_type,
            "top_types": self.top_types,
            "timestamp": self.timestamp.isoformat(),
        }


# =============================================================================
# Memory Tracker
# =============================================================================


class MemoryTracker:
    """
    Track memory and GC metrics.

    Parameters
    ----------
    track_objects : bool
        Whether to track object counts (expensive)
    top_object_types : int
        Number of top object types to track
    """

    def __init__(
        self,
        track_objects: bool = False,
        top_object_types: int = 10,
    ):
        self.track_objects = track_objects
        self.top_object_types = top_object_types

        self._last_gc_counts = gc.get_count()
        self._gc_callbacks_registered = False

        # Initialize metrics lazily
        _init_metrics()

    def collect_memory(self) -> MemoryStats:
        """Collect memory statistics."""
        stats = MemoryStats()

        if HAS_PSUTIL:
            process = psutil.Process()
            mem_info = process.memory_info()

            stats.rss_bytes = mem_info.rss
            stats.vms_bytes = mem_info.vms
            stats.rss_mb = mem_info.rss / (1024 * 1024)
            stats.vms_mb = mem_info.vms / (1024 * 1024)
            stats.percent = process.memory_percent()

        # Python heap size estimation
        stats.heap_bytes = sys.getsizeof(gc.get_objects())
        stats.heap_mb = stats.heap_bytes / (1024 * 1024)

        # Update Prometheus metrics
        if MEMORY_RSS_BYTES is not None:
            MEMORY_RSS_BYTES.set(stats.rss_bytes)
        if MEMORY_VMS_BYTES is not None:
            MEMORY_VMS_BYTES.set(stats.vms_bytes)
        if MEMORY_HEAP_BYTES is not None:
            MEMORY_HEAP_BYTES.set(stats.heap_bytes)
        if MEMORY_PERCENT is not None:
            MEMORY_PERCENT.set(stats.percent)

        return stats

    def collect_gc(self) -> GCStats:
        """Collect GC statistics."""
        stats = GCStats()

        # Get current counts
        gc_stats = gc.get_stats()

        for gen, gen_stats in enumerate(gc_stats):
            stats.collections[gen] = gen_stats.get("collections", 0)
            stats.collected[gen] = gen_stats.get("collected", 0)

            # Update Prometheus
            if GC_COLLECTIONS_TOTAL is not None:
                GC_COLLECTIONS_TOTAL.labels(generation=str(gen))._value.set(
                    gen_stats.get("collections", 0)
                )
            if GC_COLLECTED_OBJECTS is not None:
                GC_COLLECTED_OBJECTS.labels(generation=str(gen))._value.set(
                    gen_stats.get("collected", 0)
                )

        stats.uncollectable = len(gc.garbage)
        stats.thresholds = gc.get_threshold()

        if GC_UNCOLLECTABLE_OBJECTS is not None:
            GC_UNCOLLECTABLE_OBJECTS.set(stats.uncollectable)

        return stats

    def collect_objects(self) -> ObjectStats:
        """Collect object count statistics."""
        stats = ObjectStats()

        if not self.track_objects:
            return stats

        # Count objects by type
        type_counts: dict[str, int] = {}
        all_objects = gc.get_objects()
        stats.total_objects = len(all_objects)

        for obj in all_objects:
            type_name = type(obj).__name__
            type_counts[type_name] = type_counts.get(type_name, 0) + 1

        # Get top types
        sorted_types = sorted(type_counts.items(), key=lambda x: x[1], reverse=True)
        stats.top_types = sorted_types[: self.top_object_types]
        stats.by_type = dict(sorted_types[:50])  # Limit stored types

        # Update Prometheus for top types
        if OBJECT_COUNT is not None:
            for type_name, count in stats.top_types:
                OBJECT_COUNT.labels(object_type=type_name).set(count)

        return stats

    def collect(self) -> dict[str, Any]:
        """Collect all statistics."""
        return {
            "memory": self.collect_memory().to_dict(),
            "gc": self.collect_gc().to_dict(),
            "objects": self.collect_objects().to_dict() if self.track_objects else None,
        }

    def register_gc_callbacks(self):
        """Register GC callbacks for timing."""
        if self._gc_callbacks_registered:
            return

        self._gc_start_time: dict[int, float] = {}

        def gc_callback(phase: str, info: dict):
            generation = info.get("generation", 0)

            if phase == "start":
                self._gc_start_time[generation] = time.perf_counter()
            elif phase == "stop":
                if generation in self._gc_start_time:
                    duration = time.perf_counter() - self._gc_start_time[generation]
                    if GC_DURATION_SECONDS is not None:
                        GC_DURATION_SECONDS.labels(generation=str(generation)).observe(duration)
                    del self._gc_start_time[generation]

        gc.callbacks.append(gc_callback)
        self._gc_callbacks_registered = True

    def force_gc(self) -> dict[str, int]:
        """Force garbage collection and return collected counts."""
        collected = {}
        for gen in range(3):
            start_time = time.perf_counter()
            count = gc.collect(gen)
            duration = time.perf_counter() - start_time

            collected[gen] = count
            if GC_DURATION_SECONDS is not None:
                GC_DURATION_SECONDS.labels(generation=str(gen)).observe(duration)

        return collected


# =============================================================================
# Background Tracker
# =============================================================================

_background_tracker: threading.Thread | None = None
_stop_tracking = threading.Event()


def start_memory_tracking(
    interval_seconds: float = 30.0,
    track_objects: bool = False,
    on_high_memory: Callable[[MemoryStats], None] | None = None,
    high_memory_threshold_percent: float = 80.0,
):
    """
    Start background memory tracking.

    Parameters
    ----------
    interval_seconds : float
        Collection interval
    track_objects : bool
        Whether to track object counts
    on_high_memory : callable, optional
        Callback when memory exceeds threshold
    high_memory_threshold_percent : float
        Memory percentage threshold for alerts
    """
    global _background_tracker

    if _background_tracker and _background_tracker.is_alive():
        return

    _stop_tracking.clear()
    tracker = MemoryTracker(track_objects=track_objects)
    tracker.register_gc_callbacks()

    def tracking_loop():
        while not _stop_tracking.is_set():
            try:
                stats = tracker.collect_memory()
                tracker.collect_gc()

                if track_objects:
                    tracker.collect_objects()

                if on_high_memory and stats.percent >= high_memory_threshold_percent:
                    logger.warning(
                        "high_memory_usage",
                        percent=stats.percent,
                        rss_mb=stats.rss_mb,
                        threshold=high_memory_threshold_percent,
                    )
                    on_high_memory(stats)

            except Exception as e:
                logger.error("memory_tracking_error", error=str(e))

            _stop_tracking.wait(interval_seconds)

    _background_tracker = threading.Thread(target=tracking_loop, daemon=True)
    _background_tracker.start()

    logger.info("memory_tracking_started", interval_seconds=interval_seconds)


def stop_memory_tracking():
    """Stop background memory tracking."""
    _stop_tracking.set()
    if _background_tracker:
        _background_tracker.join(timeout=5)
    logger.info("memory_tracking_stopped")


def get_memory_tracker() -> MemoryTracker:
    """Get a memory tracker instance."""
    return MemoryTracker()
