"""
Memory allocation benchmarks using tracemalloc.

These are NOT pytest-benchmark tests — they run standalone and print
allocation deltas.  Run directly:

    python benchmarks/bench_memory.py

Covers:
  - Per-call allocation of the with_observability decorator
  - SLOTracker._measurements growth and eviction
  - Logger bind() allocation (creates a new BoundLogger dict each call)
  - Prometheus label cardinality (each unique label set → new TimeSeries object)
  - Global object count after N requests (leak detector)

Install extras for richer profiling:
    pip install memray          # binary allocation tracing, flamegraphs
    pip install fil-profile     # peak RSS tracking
    pip install scalene         # CPU + memory line-level profiling
"""

from __future__ import annotations

import gc
import io
import sys
import tracemalloc
from collections.abc import Generator
from contextlib import contextmanager

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@contextmanager
def measure_allocs(label: str, top_n: int = 5) -> Generator[None, None, None]:
    """Context manager: prints peak allocation and top N call sites."""
    gc.collect()
    tracemalloc.start(10)        # 10-frame traceback depth
    snapshot_before = tracemalloc.take_snapshot()

    yield

    snapshot_after = tracemalloc.take_snapshot()
    tracemalloc.stop()

    stats = snapshot_after.compare_to(snapshot_before, "lineno")
    total = sum(s.size_diff for s in stats)
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"  Net allocation: {total / 1024:.1f} KiB")
    print(f"  Top {top_n} allocation sites:")
    for stat in stats[:top_n]:
        if stat.size_diff > 0:
            print(f"    +{stat.size_diff:>8} B  {stat.traceback.format()[0].strip()}")


def _quiet_stderr() -> tuple[io.StringIO, object]:
    buf = io.StringIO()
    orig = sys.stderr
    sys.stderr = buf
    return buf, orig


def _restore_stderr(orig: object) -> None:
    sys.stderr = orig  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Scenario 1 — per-call allocation for with_observability
# ---------------------------------------------------------------------------

def bench_decorator_alloc(n: int = 1_000) -> None:
    from obskit.config import configure, reset_settings
    from obskit.decorators.combined import with_observability
    from obskit.metrics.registry import reset_registry

    reset_settings()
    configure(service_name="mem-bench", log_level="WARNING", log_format="json")
    reset_registry()
    _, orig = _quiet_stderr()

    @with_observability(component="bench")
    def noop() -> int:
        return 42

    # Warmup (fills caches, avoids import allocations)
    for _ in range(100):
        noop()
    gc.collect()

    with measure_allocs(f"with_observability decorator — {n} calls"):
        for _ in range(n):
            noop()

    _restore_stderr(orig)
    reset_settings()
    reset_registry()


# ---------------------------------------------------------------------------
# Scenario 2 — SLOTracker window growth and eviction
# ---------------------------------------------------------------------------

def bench_slo_memory(n: int = 10_000) -> None:
    from obskit.config import reset_settings
    from obskit.slo.tracker import SLOTracker, SLOType

    reset_settings()
    tracker = SLOTracker()
    tracker.register_slo(
        name="lat",
        slo_type=SLOType.LATENCY,
        target_value=0.99,
        window_seconds=3600,   # 1-hour window → measurements accumulate
    )

    gc.collect()
    with measure_allocs(f"SLOTracker.record_measurement × {n} (1-hour window, no eviction)"):
        for _ in range(n):
            tracker.record_measurement("lat", 0.050, True)

    # Now measure with aggressive eviction (0-second window)
    tracker2 = SLOTracker()
    tracker2.register_slo(
        name="lat",
        slo_type=SLOType.LATENCY,
        target_value=0.99,
        window_seconds=0,         # everything evicted immediately
    )
    gc.collect()
    with measure_allocs(f"SLOTracker.record_measurement × {n} (0s window, full eviction)"):
        for _ in range(n):
            tracker2.record_measurement("lat", 0.050, True)

    reset_settings()


# ---------------------------------------------------------------------------
# Scenario 3 — structlog BoundLogger allocation
# ---------------------------------------------------------------------------

def bench_logger_bind_alloc(n: int = 1_000) -> None:
    from obskit.config import configure, reset_settings
    from obskit.logging import get_logger

    reset_settings()
    configure(service_name="mem-bench", log_level="WARNING")
    _, orig = _quiet_stderr()

    logger = get_logger("bench")

    gc.collect()
    with measure_allocs(f"logger.bind() + .info() × {n}"):
        for i in range(n):
            logger.bind(request_id=f"req-{i}", user_id="u1").info("event")

    _restore_stderr(orig)
    reset_settings()


# ---------------------------------------------------------------------------
# Scenario 4 — Prometheus label cardinality (new label set = new TimeSeries)
# ---------------------------------------------------------------------------

def bench_prometheus_cardinality(n_tenants: int = 500) -> None:
    """Each new (operation, tenant_id) pair allocates a Prometheus TimeSeries."""
    try:
        from obskit.metrics.red import REDMetrics, reset_red_metrics
        from obskit.metrics.registry import reset_registry
    except ImportError:
        print("prometheus_client not installed — skipping cardinality bench")
        return

    reset_red_metrics()
    reset_registry()

    metrics = REDMetrics(name="cardinality_bench")

    gc.collect()
    with measure_allocs(f"Prometheus label explosion — {n_tenants} distinct tenant IDs"):
        for i in range(n_tenants):
            metrics.observe_request(
                operation=f"tenant_{i}",   # unique label → new TimeSeries
                duration_seconds=0.050,
                status="success",
            )

    reset_red_metrics()
    reset_registry()


# ---------------------------------------------------------------------------
# Scenario 5 — Leak detector (object count after N requests)
# ---------------------------------------------------------------------------

def bench_leak_detector(n: int = 5_000) -> None:
    """Assert that object count does not grow linearly with request count.

    If obskit leaks per-request objects (e.g. never-evicted lists, growing
    dicts) the delta will be proportional to n.  A well-behaved system should
    have a near-constant object count after warmup.
    """
    from obskit.config import configure, reset_settings
    from obskit.decorators.combined import with_observability
    from obskit.metrics.registry import reset_registry

    reset_settings()
    configure(service_name="leak-bench", log_level="WARNING", log_format="json")
    reset_registry()
    _, orig = _quiet_stderr()

    @with_observability(component="bench")
    def noop() -> int:
        return 42

    # Warmup
    for _ in range(200):
        noop()
    gc.collect()

    count_before = len(gc.get_objects())

    for _ in range(n):
        noop()

    gc.collect()
    count_after = len(gc.get_objects())
    delta = count_after - count_before

    print(f"\n{'='*60}")
    print(f"  Leak detector — {n} requests")
    print(f"  Objects before: {count_before:,}")
    print(f"  Objects after:  {count_after:,}")
    print(f"  Delta:          {delta:+,}")
    threshold = n * 0.05   # allow max 5% of n as new live objects
    status = "PASS" if delta < threshold else "FAIL (possible leak)"
    print(f"  Result: {status}  (threshold: <{threshold:.0f} new objects)")

    _restore_stderr(orig)
    reset_settings()
    reset_registry()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("obskit memory allocation benchmarks")
    print("tracemalloc backend; install 'memray' for production-grade profiling\n")

    bench_decorator_alloc(n=1_000)
    bench_slo_memory(n=10_000)
    bench_logger_bind_alloc(n=1_000)
    bench_prometheus_cardinality(n_tenants=500)
    bench_leak_detector(n=5_000)

    print("\nDone.")
