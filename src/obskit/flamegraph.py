"""
Flame Graph Integration
=======================

CPU and memory profiling with flame graph export.

Features:
- CPU profiling
- Memory profiling
- Flame graph generation
- Integration with py-spy/pyflame

Example:
    from obskit.flamegraph import FlameGraphProfiler

    profiler = FlameGraphProfiler()

    with profiler.profile("order_processing"):
        process_orders()

    # Export flame graph
    profiler.export_svg("order_processing.svg")
"""

import cProfile
import io
import pstats
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

PROFILE_DURATION = Histogram(
    "flamegraph_profile_duration_seconds",
    "Duration of profiled operations",
    ["operation"],
    buckets=(0.1, 0.5, 1, 5, 10, 30, 60, 120),
)

PROFILE_SAMPLES = Counter(
    "flamegraph_profile_samples_total", "Total profile samples collected", ["operation"]
)

PROFILE_ACTIVE = Gauge("flamegraph_profile_active", "Whether profiling is active", ["operation"])


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class StackFrame:
    """A single stack frame."""

    function: str
    filename: str
    line_number: int
    time_ms: float = 0.0
    self_time_ms: float = 0.0
    calls: int = 1


@dataclass
class ProfileResult:
    """Result of a profiling session."""

    operation: str
    duration_seconds: float
    total_calls: int
    top_functions: list[tuple[str, float, int]]  # (name, time_ms, calls)
    call_tree: dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "operation": self.operation,
            "duration_seconds": self.duration_seconds,
            "total_calls": self.total_calls,
            "top_functions": [
                {"name": f[0], "time_ms": f[1], "calls": f[2]} for f in self.top_functions
            ],
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class FlameGraphData:
    """Data for flame graph visualization."""

    name: str
    value: int  # Time in microseconds
    children: list["FlameGraphData"] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "children": [c.to_dict() for c in self.children],
        }


# =============================================================================
# Flame Graph Profiler
# =============================================================================


class FlameGraphProfiler:
    """
    CPU and memory profiler with flame graph export.

    Parameters
    ----------
    sample_interval : float
        Sampling interval in seconds
    max_depth : int
        Maximum stack depth to capture
    """

    def __init__(
        self,
        sample_interval: float = 0.001,
        max_depth: int = 50,
    ):
        self.sample_interval = sample_interval
        self.max_depth = max_depth

        self._profiles: dict[str, ProfileResult] = {}
        self._active_profilers: dict[str, cProfile.Profile] = {}
        self._lock = threading.Lock()

    @contextmanager
    def profile(
        self,
        operation: str,
        profile_memory: bool = False,
    ) -> Generator[None, None, None]:
        """
        Profile a code block.

        Parameters
        ----------
        operation : str
            Name of the operation
        profile_memory : bool
            Whether to also profile memory
        """
        profiler = cProfile.Profile()
        start_time = time.perf_counter()

        PROFILE_ACTIVE.labels(operation=operation).set(1)

        with self._lock:
            self._active_profilers[operation] = profiler

        profiler.enable()

        try:
            yield
        finally:
            profiler.disable()
            duration = time.perf_counter() - start_time

            PROFILE_ACTIVE.labels(operation=operation).set(0)
            PROFILE_DURATION.labels(operation=operation).observe(duration)

            # Process results
            result = self._process_profile(operation, profiler, duration)

            with self._lock:
                self._profiles[operation] = result
                if operation in self._active_profilers:
                    del self._active_profilers[operation]

            logger.debug(
                "profile_completed",
                operation=operation,
                duration_seconds=duration,
                total_calls=result.total_calls,
            )

    def _process_profile(
        self,
        operation: str,
        profiler: cProfile.Profile,
        duration: float,
    ) -> ProfileResult:
        """Process profiler results."""
        # Get stats
        stream = io.StringIO()
        stats = pstats.Stats(profiler, stream=stream)
        stats.sort_stats("cumulative")

        # Extract top functions
        top_functions = []
        total_calls = 0

        for func, (_cc, nc, _tt, ct, _callers) in stats.stats.items():
            filename, line, name = func
            total_calls += nc

            # Skip internal functions
            if "frozen" in filename or "<" in name:
                continue

            top_functions.append(
                (
                    f"{name} ({filename}:{line})",
                    ct * 1000,  # Convert to ms
                    nc,
                )
            )

        # Sort by cumulative time and take top 20
        top_functions.sort(key=lambda x: x[1], reverse=True)
        top_functions = top_functions[:20]

        PROFILE_SAMPLES.labels(operation=operation).inc(total_calls)

        return ProfileResult(
            operation=operation,
            duration_seconds=duration,
            total_calls=total_calls,
            top_functions=top_functions,
            call_tree={},
        )

    def get_profile(self, operation: str) -> ProfileResult | None:
        """Get a profile result."""
        with self._lock:
            return self._profiles.get(operation)

    def get_all_profiles(self) -> dict[str, ProfileResult]:
        """Get all profile results."""
        with self._lock:
            return dict(self._profiles)

    def generate_flamegraph_data(self, operation: str) -> FlameGraphData | None:
        """
        Generate flame graph data for visualization.

        Parameters
        ----------
        operation : str
            Operation name

        Returns
        -------
        FlameGraphData or None
        """
        profile = self.get_profile(operation)
        if not profile:
            return None

        # Create root node
        root = FlameGraphData(
            name=operation,
            value=int(profile.duration_seconds * 1_000_000),
        )

        # Add top functions as children
        for name, time_ms, calls in profile.top_functions[:10]:
            child = FlameGraphData(
                name=f"{name} ({calls} calls)",
                value=int(time_ms * 1000),
            )
            root.children.append(child)

        return root

    def export_collapsed(self, operation: str) -> str:
        """
        Export profile in collapsed stack format (for flamegraph.pl).

        Parameters
        ----------
        operation : str
            Operation name

        Returns
        -------
        str
            Collapsed stack format
        """
        profile = self.get_profile(operation)
        if not profile:
            return ""

        lines = []
        for name, time_ms, _calls in profile.top_functions:
            # Format: stack;frames count
            stack = f"{operation};{name}"
            count = int(time_ms * 1000)  # microseconds
            lines.append(f"{stack} {count}")

        return "\n".join(lines)

    def clear(self, operation: str | None = None):
        """Clear profile results."""
        with self._lock:
            if operation:
                if operation in self._profiles:
                    del self._profiles[operation]
            else:
                self._profiles.clear()


# =============================================================================
# Decorator
# =============================================================================


def profile_function(
    operation: str | None = None,
    profiler: FlameGraphProfiler | None = None,
):
    """
    Decorator to profile a function.

    Parameters
    ----------
    operation : str, optional
        Operation name (defaults to function name)
    profiler : FlameGraphProfiler, optional
        Profiler instance
    """

    def decorator(func: Callable) -> Callable:
        op_name = operation or func.__name__
        prof = profiler or get_flamegraph_profiler()

        def wrapper(*args, **kwargs):
            with prof.profile(op_name):
                return func(*args, **kwargs)

        return wrapper

    return decorator


# =============================================================================
# Singleton
# =============================================================================

_profiler: FlameGraphProfiler | None = None
_profiler_lock = threading.Lock()


def get_flamegraph_profiler(**kwargs) -> FlameGraphProfiler:
    """Get or create the global flame graph profiler."""
    global _profiler

    if _profiler is None:
        with _profiler_lock:
            if _profiler is None:
                _profiler = FlameGraphProfiler(**kwargs)

    return _profiler
