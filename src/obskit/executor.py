"""
Thread Pool Executor Metrics
============================

Track ThreadPoolExecutor and ProcessPoolExecutor metrics.

Features:
- Task submission/completion tracking
- Queue size monitoring
- Active thread count
- Saturation alerting

Example:
    from obskit.executor import ExecutorTracker, wrap_executor
    from concurrent.futures import ThreadPoolExecutor

    # Option 1: Wrap existing executor
    executor = ThreadPoolExecutor(max_workers=10)
    tracked = wrap_executor(executor, "widget_executor")

    # Option 2: Use tracker directly
    tracker = ExecutorTracker("widget_executor", max_workers=10)
    executor = tracker.wrap(ThreadPoolExecutor(max_workers=10))

    # Submit tasks as normal
    future = executor.submit(process_widget, params)
"""

import threading
import time
from collections.abc import Callable
from concurrent.futures import Executor, Future, ProcessPoolExecutor, ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from functools import wraps
from typing import Any, TypeVar

from prometheus_client import Counter, Gauge, Histogram

from obskit.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


# =============================================================================
# Prometheus Metrics
# =============================================================================

EXECUTOR_TASKS_SUBMITTED = Counter(
    "executor_tasks_submitted_total", "Total tasks submitted to executor", ["executor_name"]
)

EXECUTOR_TASKS_COMPLETED = Counter(
    "executor_tasks_completed_total", "Total tasks completed", ["executor_name", "status"]
)

EXECUTOR_TASKS_ACTIVE = Gauge("executor_tasks_active", "Currently active tasks", ["executor_name"])

EXECUTOR_QUEUE_SIZE = Gauge("executor_queue_size", "Tasks waiting in queue", ["executor_name"])

EXECUTOR_WORKERS_ACTIVE = Gauge(
    "executor_workers_active", "Active workers/threads", ["executor_name"]
)

EXECUTOR_WORKERS_MAX = Gauge(
    "executor_workers_max", "Maximum workers configured", ["executor_name"]
)

EXECUTOR_UTILIZATION = Gauge(
    "executor_utilization_ratio", "Worker utilization (active/max)", ["executor_name"]
)

EXECUTOR_TASK_LATENCY = Histogram(
    "executor_task_latency_seconds",
    "Task execution latency",
    ["executor_name"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60, 120),
)

EXECUTOR_QUEUE_WAIT_TIME = Histogram(
    "executor_queue_wait_seconds",
    "Time tasks wait in queue before execution",
    ["executor_name"],
    buckets=(0.001, 0.01, 0.05, 0.1, 0.5, 1, 5, 10, 30),
)

EXECUTOR_SATURATION_EVENTS = Counter(
    "executor_saturation_events_total", "Times executor was saturated", ["executor_name"]
)


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class ExecutorStats:
    """Statistics for an executor."""

    executor_name: str
    max_workers: int
    active_tasks: int = 0
    queue_size: int = 0
    tasks_submitted: int = 0
    tasks_completed: int = 0
    tasks_failed: int = 0
    utilization: float = 0.0
    avg_task_latency_ms: float = 0.0
    avg_queue_wait_ms: float = 0.0
    last_updated: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "executor_name": self.executor_name,
            "max_workers": self.max_workers,
            "active_tasks": self.active_tasks,
            "queue_size": self.queue_size,
            "tasks_submitted": self.tasks_submitted,
            "tasks_completed": self.tasks_completed,
            "tasks_failed": self.tasks_failed,
            "utilization": self.utilization,
            "avg_task_latency_ms": self.avg_task_latency_ms,
            "avg_queue_wait_ms": self.avg_queue_wait_ms,
            "last_updated": self.last_updated.isoformat(),
        }


# =============================================================================
# Executor Tracker
# =============================================================================


class ExecutorTracker:
    """
    Track executor metrics.

    Parameters
    ----------
    executor_name : str
        Name of the executor
    max_workers : int
        Maximum workers
    saturation_threshold : float
        Utilization threshold for saturation alert (default: 0.9)
    on_saturated : callable, optional
        Callback when executor is saturated
    """

    def __init__(
        self,
        executor_name: str,
        max_workers: int = 10,
        saturation_threshold: float = 0.9,
        on_saturated: Callable[[str], None] | None = None,
    ):
        self.executor_name = executor_name
        self.max_workers = max_workers
        self.saturation_threshold = saturation_threshold
        self.on_saturated = on_saturated

        self._active_tasks = 0
        self._queue_size = 0
        self._tasks_submitted = 0
        self._tasks_completed = 0
        self._tasks_failed = 0
        self._task_latencies: list[float] = []
        self._queue_waits: list[float] = []
        self._lock = threading.Lock()

        # Initialize metrics
        EXECUTOR_WORKERS_MAX.labels(executor_name=executor_name).set(max_workers)

    def wrap(self, executor: Executor) -> "TrackedExecutor":
        """
        Wrap an executor with tracking.

        Parameters
        ----------
        executor : Executor
            The executor to wrap

        Returns
        -------
        TrackedExecutor
            Wrapped executor with metrics
        """
        return TrackedExecutor(executor, self)

    def task_submitted(self):
        """Record a task submission."""
        with self._lock:
            self._tasks_submitted += 1
            self._queue_size += 1

        EXECUTOR_TASKS_SUBMITTED.labels(executor_name=self.executor_name).inc()
        EXECUTOR_QUEUE_SIZE.labels(executor_name=self.executor_name).set(self._queue_size)

        self._check_saturation()

    def task_started(self, queue_wait_time: float):
        """Record a task starting execution."""
        with self._lock:
            self._queue_size = max(0, self._queue_size - 1)
            self._active_tasks += 1
            self._queue_waits.append(queue_wait_time)

            if len(self._queue_waits) > 1000:
                self._queue_waits = self._queue_waits[-1000:]

        EXECUTOR_QUEUE_SIZE.labels(executor_name=self.executor_name).set(self._queue_size)
        EXECUTOR_TASKS_ACTIVE.labels(executor_name=self.executor_name).set(self._active_tasks)
        EXECUTOR_WORKERS_ACTIVE.labels(executor_name=self.executor_name).set(self._active_tasks)

        EXECUTOR_QUEUE_WAIT_TIME.labels(executor_name=self.executor_name).observe(queue_wait_time)

        self._update_utilization()

    def task_completed(self, execution_time: float, success: bool = True):
        """Record a task completion."""
        with self._lock:
            self._active_tasks = max(0, self._active_tasks - 1)
            if success:
                self._tasks_completed += 1
            else:
                self._tasks_failed += 1

            self._task_latencies.append(execution_time)
            if len(self._task_latencies) > 1000:
                self._task_latencies = self._task_latencies[-1000:]

        status = "success" if success else "error"

        EXECUTOR_TASKS_COMPLETED.labels(executor_name=self.executor_name, status=status).inc()

        EXECUTOR_TASKS_ACTIVE.labels(executor_name=self.executor_name).set(self._active_tasks)
        EXECUTOR_WORKERS_ACTIVE.labels(executor_name=self.executor_name).set(self._active_tasks)

        EXECUTOR_TASK_LATENCY.labels(executor_name=self.executor_name).observe(execution_time)

        self._update_utilization()

    def _update_utilization(self):
        """Update utilization metric."""
        if self.max_workers > 0:
            utilization = self._active_tasks / self.max_workers
            EXECUTOR_UTILIZATION.labels(executor_name=self.executor_name).set(utilization)

    def _check_saturation(self):
        """Check for saturation and alert if needed."""
        if self.max_workers == 0:
            return

        utilization = self._active_tasks / self.max_workers

        if utilization >= self.saturation_threshold:
            EXECUTOR_SATURATION_EVENTS.labels(executor_name=self.executor_name).inc()

            logger.warning(
                "executor_saturated",
                executor_name=self.executor_name,
                utilization=utilization,
                active_tasks=self._active_tasks,
                max_workers=self.max_workers,
                queue_size=self._queue_size,
            )

            if self.on_saturated:
                self.on_saturated(self.executor_name)

    def set_stats(
        self,
        active_tasks: int | None = None,
        queue_size: int | None = None,
        max_workers: int | None = None,
    ):
        """Manually set executor stats (for external monitoring)."""
        with self._lock:
            if active_tasks is not None:
                self._active_tasks = active_tasks
                EXECUTOR_TASKS_ACTIVE.labels(executor_name=self.executor_name).set(active_tasks)
                EXECUTOR_WORKERS_ACTIVE.labels(executor_name=self.executor_name).set(active_tasks)

            if queue_size is not None:
                self._queue_size = queue_size
                EXECUTOR_QUEUE_SIZE.labels(executor_name=self.executor_name).set(queue_size)

            if max_workers is not None:
                self.max_workers = max_workers
                EXECUTOR_WORKERS_MAX.labels(executor_name=self.executor_name).set(max_workers)

        self._update_utilization()
        self._check_saturation()

    def get_stats(self) -> ExecutorStats:
        """Get current executor statistics."""
        with self._lock:
            avg_latency = 0.0
            if self._task_latencies:
                avg_latency = sum(self._task_latencies) / len(self._task_latencies) * 1000

            avg_wait = 0.0
            if self._queue_waits:
                avg_wait = sum(self._queue_waits) / len(self._queue_waits) * 1000

            utilization = 0.0
            if self.max_workers > 0:
                utilization = self._active_tasks / self.max_workers

            return ExecutorStats(
                executor_name=self.executor_name,
                max_workers=self.max_workers,
                active_tasks=self._active_tasks,
                queue_size=self._queue_size,
                tasks_submitted=self._tasks_submitted,
                tasks_completed=self._tasks_completed,
                tasks_failed=self._tasks_failed,
                utilization=utilization,
                avg_task_latency_ms=avg_latency,
                avg_queue_wait_ms=avg_wait,
            )

    def is_saturated(self) -> bool:
        """Check if executor is saturated."""
        if self.max_workers == 0:
            return False
        return (self._active_tasks / self.max_workers) >= self.saturation_threshold


# =============================================================================
# Tracked Executor Wrapper
# =============================================================================


class TrackedExecutor:
    """
    Executor wrapper that tracks metrics.

    This wraps any concurrent.futures.Executor and tracks:
    - Task submissions
    - Queue wait time
    - Execution time
    - Success/failure
    """

    def __init__(self, executor: Executor, tracker: ExecutorTracker):
        self._executor = executor
        self._tracker = tracker

    def submit(self, fn: Callable[..., T], *args, **kwargs) -> Future:
        """Submit a task with tracking."""
        submit_time = time.perf_counter()
        self._tracker.task_submitted()

        @wraps(fn)
        def tracked_fn(*a, **kw):
            start_time = time.perf_counter()
            queue_wait = start_time - submit_time
            self._tracker.task_started(queue_wait)

            try:
                result = fn(*a, **kw)
                execution_time = time.perf_counter() - start_time
                self._tracker.task_completed(execution_time, success=True)
                return result
            except Exception:
                execution_time = time.perf_counter() - start_time
                self._tracker.task_completed(execution_time, success=False)
                raise

        return self._executor.submit(tracked_fn, *args, **kwargs)

    def map(self, fn: Callable, *iterables, timeout=None, chunksize=1):
        """Map function with tracking."""
        return self._executor.map(fn, *iterables, timeout=timeout, chunksize=chunksize)

    def shutdown(self, wait: bool = True, *, cancel_futures: bool = False) -> None:
        """Shutdown executor."""
        if hasattr(self._executor, "shutdown"):
            self._executor.shutdown(wait=wait, cancel_futures=cancel_futures)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown(wait=True)
        return False

    @property
    def tracker(self) -> ExecutorTracker:
        """Get the tracker."""
        return self._tracker


# =============================================================================
# Factory Functions
# =============================================================================

_trackers: dict[str, ExecutorTracker] = {}
_trackers_lock = threading.Lock()


def get_executor_tracker(
    executor_name: str,
    **kwargs,
) -> ExecutorTracker:
    """Get or create an executor tracker."""
    if executor_name not in _trackers:
        with _trackers_lock:
            if executor_name not in _trackers:
                _trackers[executor_name] = ExecutorTracker(executor_name, **kwargs)

    return _trackers[executor_name]


def wrap_executor(
    executor: Executor,
    name: str,
    max_workers: int | None = None,
    **kwargs,
) -> TrackedExecutor:
    """
    Wrap an executor with tracking.

    Parameters
    ----------
    executor : Executor
        The executor to wrap
    name : str
        Name for tracking
    max_workers : int, optional
        Max workers (auto-detected if possible)
    **kwargs
        Additional tracker options

    Returns
    -------
    TrackedExecutor
        Wrapped executor
    """
    # Try to auto-detect max_workers
    if max_workers is None:
        if hasattr(executor, "_max_workers"):
            max_workers = executor._max_workers
        else:
            max_workers = 10

    tracker = get_executor_tracker(name, max_workers=max_workers, **kwargs)
    return TrackedExecutor(executor, tracker)


def create_tracked_executor(
    name: str,
    max_workers: int = 10,
    executor_type: str = "thread",
    **kwargs,
) -> TrackedExecutor:
    """
    Create a new tracked executor.

    Parameters
    ----------
    name : str
        Executor name
    max_workers : int
        Maximum workers
    executor_type : str
        "thread" or "process"
    **kwargs
        Additional tracker options

    Returns
    -------
    TrackedExecutor
        New tracked executor
    """
    if executor_type == "thread":
        executor = ThreadPoolExecutor(max_workers=max_workers)
    elif executor_type == "process":
        executor = ProcessPoolExecutor(max_workers=max_workers)
    else:
        raise ValueError(f"Unknown executor type: {executor_type}")

    return wrap_executor(executor, name, max_workers=max_workers, **kwargs)


def get_all_executor_stats() -> dict[str, ExecutorStats]:
    """Get stats for all tracked executors."""
    return {name: tracker.get_stats() for name, tracker in _trackers.items()}
