"""
Benchmarks for metrics hot paths.

These benchmarks measure the overhead of metric collection,
which is critical for high-throughput services.
"""

from __future__ import annotations

import uuid
from collections.abc import Generator
from typing import TYPE_CHECKING, Any

import pytest

from obskit.metrics.red import REDMetrics, reset_red_metrics
from obskit.metrics.registry import reset_registry

if TYPE_CHECKING:
    pass


class TestREDMetricsBenchmarks:
    """Benchmarks for REDMetrics operations."""

    metrics: REDMetrics

    @pytest.fixture(autouse=True)
    def setup(self) -> Generator[None, None, None]:
        """Reset metrics before each test."""
        reset_red_metrics()
        reset_registry()
        # Use unique name per test to avoid duplicate registration
        self.metrics = REDMetrics(name=f"bench_{uuid.uuid4().hex[:8]}")
        yield
        reset_red_metrics()
        reset_registry()

    @pytest.mark.benchmark(group="metrics")
    def test_observe_request_success(self, benchmark: Any) -> None:
        """Benchmark successful request observation."""
        benchmark(
            self.metrics.observe_request,
            operation="benchmark_op",
            duration_seconds=0.1,
            status="success",
        )

    @pytest.mark.benchmark(group="metrics")
    def test_observe_request_failure(self, benchmark: Any) -> None:
        """Benchmark failed request observation."""
        benchmark(
            self.metrics.observe_request,
            operation="benchmark_op",
            duration_seconds=0.1,
            status="failure",
            error_type="BenchmarkError",
        )

    @pytest.mark.benchmark(group="metrics")
    def test_track_request_context_manager(self, benchmark: Any) -> None:
        """Benchmark context manager for request tracking."""

        def track() -> None:
            with self.metrics.track_request("benchmark_op"):
                pass  # Simulates minimal work

        benchmark(track)

    @pytest.mark.benchmark(group="metrics")
    def test_track_request_with_work(self, benchmark: Any) -> None:
        """Benchmark context manager with simulated work."""

        def track_with_work() -> None:
            with self.metrics.track_request("benchmark_op"):
                # Simulate minimal CPU work
                _ = sum(range(100))

        benchmark(track_with_work)


class TestGaugeBenchmarks:
    """Benchmarks for Gauge operations."""

    gauge: Any

    @pytest.fixture(autouse=True)
    def setup(self) -> Generator[None, None, None]:
        """Set up gauge for benchmarking."""
        from obskit.metrics.types import Gauge

        reset_red_metrics()
        reset_registry()
        self.gauge = Gauge(f"bench_gauge_{uuid.uuid4().hex[:8]}", "Benchmark gauge")
        yield
        reset_red_metrics()
        reset_registry()

    @pytest.mark.benchmark(group="gauge")
    def test_gauge_set(self, benchmark: Any) -> None:
        """Benchmark gauge set operation."""
        benchmark(self.gauge.set, 42.0)

    @pytest.mark.benchmark(group="gauge")
    def test_gauge_inc(self, benchmark: Any) -> None:
        """Benchmark gauge increment."""
        benchmark(self.gauge.inc)

    @pytest.mark.benchmark(group="gauge")
    def test_gauge_dec(self, benchmark: Any) -> None:
        """Benchmark gauge decrement."""
        benchmark(self.gauge.dec)


class TestCounterBenchmarks:
    """Benchmarks for Counter operations."""

    counter: Any

    @pytest.fixture(autouse=True)
    def setup(self) -> Generator[None, None, None]:
        """Set up counter for benchmarking."""
        from obskit.metrics.types import Counter

        reset_red_metrics()
        reset_registry()
        self.counter = Counter(
            f"bench_counter_{uuid.uuid4().hex[:8]}", "Benchmark counter"
        )
        yield
        reset_red_metrics()
        reset_registry()

    @pytest.mark.benchmark(group="counter")
    def test_counter_inc(self, benchmark: Any) -> None:
        """Benchmark counter increment."""
        benchmark(self.counter.inc)

    @pytest.mark.benchmark(group="counter")
    def test_counter_inc_amount(self, benchmark: Any) -> None:
        """Benchmark counter increment with amount."""
        benchmark(self.counter.inc, 5)


class TestHistogramBenchmarks:
    """Benchmarks for Histogram operations."""

    histogram: Any

    @pytest.fixture(autouse=True)
    def setup(self) -> Generator[None, None, None]:
        """Set up histogram for benchmarking."""
        from obskit.metrics.types import Histogram

        reset_red_metrics()
        reset_registry()
        self.histogram = Histogram(
            f"bench_histogram_{uuid.uuid4().hex[:8]}", "Benchmark histogram"
        )
        yield
        reset_red_metrics()
        reset_registry()

    @pytest.mark.benchmark(group="histogram")
    def test_histogram_observe(self, benchmark: Any) -> None:
        """Benchmark histogram observation."""
        benchmark(self.histogram.observe, 0.1)

    @pytest.mark.benchmark(group="histogram")
    def test_histogram_observe_varied(self, benchmark: Any) -> None:
        """Benchmark histogram observation with varied values."""
        import random

        def observe_random() -> None:
            self.histogram.observe(random.random())

        benchmark(observe_random)

