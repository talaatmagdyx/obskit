"""
Benchmarks for the with_observability decorator — the primary user-facing hot path.

This is the most important benchmark in the suite.  Every instrumented endpoint
pays this cost, so any regression here appears directly in service tail latency.

Breakdown of what with_observability does per call:
  1. get_settings()                → double-checked lock + object access
  2. get_correlation_id()          → ContextVar.get
  3. CircuitBreaker.__enter__      → RLock + state check
  4. REDMetrics.observe_request()  → Counter.labels().inc() + Histogram.observe()
  5. SLOTracker.record_measurement → Lock + list.append + eviction check
  6. logger.info / logger.error    → structlog pipeline (2× per call: start + end)
  7. time.perf_counter()           → 2× per call

Targets (see go_no_go.md for rationale):
  sync  noop function  < 50 µs
  async noop function  < 50 µs
"""

from __future__ import annotations

import asyncio
import io
import sys
from collections.abc import Generator
from typing import Any

import pytest

from obskit.config import configure, reset_settings
from obskit.decorators.combined import with_observability
from obskit.metrics.registry import reset_registry
from obskit.resilience.circuit_breaker import reset_all_circuit_breakers
from obskit.slo.tracker import SLOTracker


class TestWithObservabilityMicro:
    """Microbenchmarks: decorator overhead on a no-op function."""

    @pytest.fixture(autouse=True)
    def setup(self) -> Generator[None, None, None]:
        reset_settings()
        configure(
            service_name="bench-service",
            environment="production",
            log_format="json",
            log_level="WARNING",   # suppress noise; decorator still runs full pipeline
        )
        reset_registry()
        reset_all_circuit_breakers()
        # Suppress stdout/stderr so log I/O doesn't pollute timing
        self._orig_stderr = sys.stderr
        sys.stderr = io.StringIO()
        yield
        sys.stderr = self._orig_stderr
        reset_settings()
        reset_registry()
        reset_all_circuit_breakers()

    @pytest.mark.benchmark(group="observability")
    def test_sync_noop(self, benchmark: Any) -> None:
        """Overhead of @with_observability on a sync noop function."""

        @with_observability(component="bench")
        def noop() -> int:
            return 42

        benchmark(noop)

    @pytest.mark.benchmark(group="observability")
    def test_async_noop(self, benchmark: Any) -> None:
        """Overhead of @with_observability on an async noop function."""

        @with_observability(component="bench")
        async def noop() -> int:
            return 42

        def run() -> None:
            asyncio.run(noop())

        benchmark(run)

    @pytest.mark.benchmark(group="observability")
    def test_sync_with_threshold_exceeded(self, benchmark: Any) -> None:
        """When threshold_ms is exceeded the decorator logs a warning — measure that path."""
        import time

        @with_observability(component="bench", threshold_ms=0.0)
        def slow() -> int:
            time.sleep(0.001)
            return 42

        benchmark(slow)

    @pytest.mark.benchmark(group="observability")
    def test_sync_with_exception(self, benchmark: Any) -> None:
        """Overhead of the failure path (exception recorded + re-raised)."""

        @with_observability(component="bench")
        def failing() -> None:
            raise ValueError("bench error")

        def run_ignoring() -> None:
            try:
                failing()
            except ValueError:
                pass

        benchmark(run_ignoring)

    @pytest.mark.benchmark(group="observability")
    def test_decorator_stack_depth_3(self, benchmark: Any) -> None:
        """Three nested @with_observability decorators — measures stacking cost."""

        @with_observability(component="outer")
        def outer() -> int:
            return middle()

        @with_observability(component="middle")
        def middle() -> int:
            return inner()

        @with_observability(component="inner")
        def inner() -> int:
            return 42

        benchmark(outer)


class TestObservabilityVsBaseline:
    """Compare decorator overhead to a raw undecorated baseline.

    The delta between baseline and decorated is the pure obskit overhead.
    """

    @pytest.fixture(autouse=True)
    def setup(self) -> Generator[None, None, None]:
        reset_settings()
        configure(service_name="bench", log_level="WARNING", log_format="json")
        reset_registry()
        self._orig_stderr = sys.stderr
        sys.stderr = io.StringIO()
        yield
        sys.stderr = self._orig_stderr
        reset_settings()
        reset_registry()

    @pytest.mark.benchmark(group="observability_baseline")
    def test_raw_function_call(self, benchmark: Any) -> None:
        """Undecorated baseline — pure Python function call cost."""

        def noop() -> int:
            return 42

        benchmark(noop)

    @pytest.mark.benchmark(group="observability_baseline")
    def test_decorated_function_call(self, benchmark: Any) -> None:
        """Decorated function — subtract raw baseline to get obskit overhead."""

        @with_observability(component="bench")
        def noop() -> int:
            return 42

        benchmark(noop)


class TestObservabilityWithSLO:
    """with_observability composed with SLO tracking."""

    @pytest.fixture(autouse=True)
    def setup(self) -> Generator[None, None, None]:
        from obskit.slo.tracker import SLOType

        reset_settings()
        configure(service_name="bench", log_level="WARNING", log_format="json")
        reset_registry()
        self.slo_tracker = SLOTracker()
        self.slo_tracker.register_slo(
            name="bench_latency",
            target=0.99,
            threshold=0.100,
            slo_type=SLOType.LATENCY,
        )
        self._orig_stderr = sys.stderr
        sys.stderr = io.StringIO()
        yield
        sys.stderr = self._orig_stderr
        reset_settings()
        reset_registry()

    @pytest.mark.benchmark(group="observability_slo")
    def test_with_slo_tracking(self, benchmark: Any) -> None:
        """Full stack: with_observability + manual SLO record per call."""

        @with_observability(component="bench")
        def noop() -> int:
            return 42

        def run() -> None:
            import time

            t = time.perf_counter()
            result = noop()
            elapsed = time.perf_counter() - t
            self.slo_tracker.record_measurement("bench_latency", elapsed, True)
            return result

        benchmark(run)
