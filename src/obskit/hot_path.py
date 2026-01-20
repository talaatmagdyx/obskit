"""
Hot Path Detector
=================

Identify and optimize critical code paths.

Features:
- Automatic hot path detection
- Call frequency tracking
- Latency impact analysis
- Optimization suggestions

Example:
    from obskit.hot_path import HotPathDetector

    detector = HotPathDetector()

    # Track calls
    with detector.track("database_query"):
        execute_query()

    # Get hot paths
    hot_paths = detector.get_hot_paths()
"""

import threading
import time
from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from prometheus_client import Counter, Gauge, Histogram

from obskit.logging import get_logger

logger = get_logger(__name__)


# =============================================================================
# Prometheus Metrics
# =============================================================================

HOT_PATH_CALLS = Counter("hot_path_calls_total", "Total calls to tracked paths", ["path"])

HOT_PATH_LATENCY = Histogram(
    "hot_path_latency_seconds",
    "Latency of hot paths",
    ["path"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5),
)

HOT_PATH_IMPACT = Gauge("hot_path_impact_score", "Impact score (calls * avg_latency)", ["path"])


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class PathStats:
    """Statistics for a tracked path."""

    path: str
    call_count: int = 0
    total_time_ms: float = 0.0
    min_time_ms: float = float("inf")
    max_time_ms: float = 0.0
    error_count: int = 0
    last_called: datetime | None = None
    callers: dict[str, int] = field(default_factory=dict)

    @property
    def avg_time_ms(self) -> float:
        return self.total_time_ms / self.call_count if self.call_count > 0 else 0.0

    @property
    def impact_score(self) -> float:
        """Impact = calls * avg_time (higher = more impactful)."""
        return self.call_count * self.avg_time_ms

    @property
    def error_rate(self) -> float:
        return self.error_count / self.call_count if self.call_count > 0 else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "call_count": self.call_count,
            "total_time_ms": self.total_time_ms,
            "avg_time_ms": self.avg_time_ms,
            "min_time_ms": self.min_time_ms if self.min_time_ms != float("inf") else 0,
            "max_time_ms": self.max_time_ms,
            "error_count": self.error_count,
            "error_rate": self.error_rate,
            "impact_score": self.impact_score,
            "last_called": self.last_called.isoformat() if self.last_called else None,
            "top_callers": dict(sorted(self.callers.items(), key=lambda x: x[1], reverse=True)[:5]),
        }


@dataclass
class HotPath:
    """A detected hot path."""

    path: str
    impact_score: float
    call_count: int
    avg_latency_ms: float
    suggestions: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "impact_score": self.impact_score,
            "call_count": self.call_count,
            "avg_latency_ms": self.avg_latency_ms,
            "suggestions": self.suggestions,
        }


# =============================================================================
# Hot Path Detector
# =============================================================================


class HotPathDetector:
    """
    Detect and analyze hot code paths.

    Parameters
    ----------
    hot_path_threshold : int
        Minimum calls to be considered hot
    impact_threshold : float
        Minimum impact score for suggestions
    window_minutes : int
        Analysis window in minutes
    """

    def __init__(
        self,
        hot_path_threshold: int = 100,
        impact_threshold: float = 1000.0,
        window_minutes: int = 60,
    ):
        self.hot_path_threshold = hot_path_threshold
        self.impact_threshold = impact_threshold
        self.window_minutes = window_minutes

        self._paths: dict[str, PathStats] = {}
        self._call_stack: list[str] = []
        self._lock = threading.Lock()
        self._local = threading.local()

    @contextmanager
    def track(
        self,
        path: str,
        caller: str | None = None,
    ) -> Generator[None, None, None]:
        """
        Track a code path.

        Parameters
        ----------
        path : str
            Path identifier
        caller : str, optional
            Calling path (for call graph)
        """
        # Track caller from local stack
        if not hasattr(self._local, "stack"):
            self._local.stack = []

        if not caller and self._local.stack:
            caller = self._local.stack[-1]

        self._local.stack.append(path)

        start_time = time.perf_counter()
        error_occurred = False

        try:
            yield
        except Exception:
            error_occurred = True
            raise
        finally:
            duration_ms = (time.perf_counter() - start_time) * 1000
            self._local.stack.pop()

            self._record_call(path, duration_ms, error_occurred, caller)

    def _record_call(
        self,
        path: str,
        duration_ms: float,
        has_error: bool,
        caller: str | None,
    ):
        """Record a call to a path."""
        with self._lock:
            if path not in self._paths:
                self._paths[path] = PathStats(path=path)

            stats = self._paths[path]
            stats.call_count += 1
            stats.total_time_ms += duration_ms
            stats.min_time_ms = min(stats.min_time_ms, duration_ms)
            stats.max_time_ms = max(stats.max_time_ms, duration_ms)
            stats.last_called = datetime.utcnow()

            if has_error:
                stats.error_count += 1

            if caller:
                stats.callers[caller] = stats.callers.get(caller, 0) + 1

        HOT_PATH_CALLS.labels(path=path).inc()
        HOT_PATH_LATENCY.labels(path=path).observe(duration_ms / 1000)

        # Update impact score periodically
        if stats.call_count % 100 == 0:
            HOT_PATH_IMPACT.labels(path=path).set(stats.impact_score)

    def record(
        self,
        path: str,
        duration_ms: float,
        has_error: bool = False,
        caller: str | None = None,
    ):
        """
        Manually record a call.

        Parameters
        ----------
        path : str
            Path identifier
        duration_ms : float
            Call duration
        has_error : bool
            Whether call resulted in error
        caller : str, optional
            Calling path
        """
        self._record_call(path, duration_ms, has_error, caller)

    def get_hot_paths(self, limit: int = 10) -> list[HotPath]:
        """
        Get the hottest paths.

        Parameters
        ----------
        limit : int
            Maximum paths to return

        Returns
        -------
        list
            Hot paths sorted by impact
        """
        with self._lock:
            # Filter by threshold
            hot_stats = [s for s in self._paths.values() if s.call_count >= self.hot_path_threshold]

            # Sort by impact
            hot_stats.sort(key=lambda s: s.impact_score, reverse=True)

            hot_paths = []
            for stats in hot_stats[:limit]:
                suggestions = self._generate_suggestions(stats)
                hot_paths.append(
                    HotPath(
                        path=stats.path,
                        impact_score=stats.impact_score,
                        call_count=stats.call_count,
                        avg_latency_ms=stats.avg_time_ms,
                        suggestions=suggestions,
                    )
                )

            return hot_paths

    def _generate_suggestions(self, stats: PathStats) -> list[str]:
        """Generate optimization suggestions for a path."""
        suggestions = []

        if stats.impact_score > self.impact_threshold:
            # High impact - needs optimization
            if stats.avg_time_ms > 100:
                suggestions.append(
                    f"High average latency ({stats.avg_time_ms:.1f}ms). Consider caching or async processing."
                )

            if stats.call_count > 10000:
                suggestions.append(
                    f"Very high call count ({stats.call_count}). Consider batching requests."
                )

            if stats.max_time_ms > stats.avg_time_ms * 10:
                suggestions.append(
                    f"High latency variance (max {stats.max_time_ms:.1f}ms). Investigate outliers."
                )

            if stats.error_rate > 0.01:
                suggestions.append(
                    f"Error rate {stats.error_rate:.1%}. Add error handling or circuit breaker."
                )

        # Analyze call patterns
        if stats.callers:
            top_caller = max(stats.callers.items(), key=lambda x: x[1])
            if top_caller[1] > stats.call_count * 0.5:
                suggestions.append(f"50%+ calls from '{top_caller[0]}'. Consider consolidating.")

        return suggestions

    def get_path_stats(self, path: str) -> PathStats | None:
        """Get statistics for a specific path."""
        with self._lock:
            return self._paths.get(path)

    def get_all_stats(self) -> list[PathStats]:
        """Get all path statistics."""
        with self._lock:
            return list(self._paths.values())

    def get_call_graph(self) -> dict[str, dict[str, int]]:
        """
        Get the call graph.

        Returns
        -------
        dict
            Mapping of path -> {caller -> count}
        """
        with self._lock:
            return {
                path: dict(stats.callers) for path, stats in self._paths.items() if stats.callers
            }

    def get_summary(self) -> dict[str, Any]:
        """Get summary of all paths."""
        with self._lock:
            total_calls = sum(s.call_count for s in self._paths.values())
            total_time = sum(s.total_time_ms for s in self._paths.values())

            return {
                "total_paths": len(self._paths),
                "total_calls": total_calls,
                "total_time_ms": total_time,
                "hot_paths_count": len(
                    [s for s in self._paths.values() if s.call_count >= self.hot_path_threshold]
                ),
                "top_by_calls": sorted(
                    [(s.path, s.call_count) for s in self._paths.values()],
                    key=lambda x: x[1],
                    reverse=True,
                )[:5],
                "top_by_latency": sorted(
                    [(s.path, s.avg_time_ms) for s in self._paths.values()],
                    key=lambda x: x[1],
                    reverse=True,
                )[:5],
            }

    def clear(self):
        """Clear all statistics."""
        with self._lock:
            self._paths.clear()


# =============================================================================
# Decorator
# =============================================================================


def track_path(
    path: str | None = None,
    detector: HotPathDetector | None = None,
):
    """
    Decorator to track function as a hot path.

    Parameters
    ----------
    path : str, optional
        Path name (defaults to function name)
    detector : HotPathDetector, optional
        Detector instance
    """

    def decorator(func: Callable) -> Callable:
        p = path or func.__name__
        d = detector or get_hot_path_detector()

        def wrapper(*args, **kwargs):
            with d.track(p):
                return func(*args, **kwargs)

        return wrapper

    return decorator


# =============================================================================
# Singleton
# =============================================================================

_detector: HotPathDetector | None = None
_detector_lock = threading.Lock()


def get_hot_path_detector(**kwargs) -> HotPathDetector:
    """Get or create the global hot path detector."""
    global _detector

    if _detector is None:
        with _detector_lock:
            if _detector is None:
                _detector = HotPathDetector(**kwargs)

    return _detector
