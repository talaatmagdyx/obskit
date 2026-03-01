"""
Benchmarks for SLO tracker hot paths.

SLOTracker.record_measurement is called on every instrumented request,
so its overhead directly adds to tail latency.
"""

from __future__ import annotations

import random
from collections.abc import Generator
from typing import Any

import pytest

from obskit.config import reset_settings
from obskit.slo.tracker import SLOTracker, SLOType


def _make_tracker(window_seconds: float = 60.0, max_measurements: int = 1000) -> SLOTracker:
    tracker = SLOTracker()
    tracker.register_slo(
        name="latency",
        slo_type=SLOType.LATENCY,
        target_value=0.95,
        window_seconds=int(window_seconds),
    )
    tracker.register_slo(
        name="availability",
        slo_type=SLOType.AVAILABILITY,
        target_value=0.999,
        window_seconds=int(window_seconds),
    )
    return tracker


class TestSLOTrackerMicrobenchmarks:
    """Microbenchmarks for SLO tracker primitives."""

    tracker: SLOTracker

    @pytest.fixture(autouse=True)
    def setup(self) -> Generator[None, None, None]:
        reset_settings()
        self.tracker = _make_tracker()
        yield
        reset_settings()

    # ------------------------------------------------------------------
    # record_measurement  (hot path — called per request)
    # ------------------------------------------------------------------

    @pytest.mark.benchmark(group="slo")
    def test_record_latency_fast(self, benchmark: Any) -> None:
        """Record a fast (within-SLO) latency measurement."""
        benchmark(self.tracker.record_measurement, "latency", 0.05, True)

    @pytest.mark.benchmark(group="slo")
    def test_record_latency_slow(self, benchmark: Any) -> None:
        """Record a slow (breaching-SLO) latency measurement."""
        benchmark(self.tracker.record_measurement, "latency", 0.500, True)

    @pytest.mark.benchmark(group="slo")
    def test_record_availability_success(self, benchmark: Any) -> None:
        """Record a successful availability check."""
        benchmark(self.tracker.record_measurement, "availability", 0.001, True)

    @pytest.mark.benchmark(group="slo")
    def test_record_availability_failure(self, benchmark: Any) -> None:
        """Record a failed availability check."""
        benchmark(self.tracker.record_measurement, "availability", 0.001, False)

    # ------------------------------------------------------------------
    # get_status  (called by /health, dashboards, alert checks)
    # ------------------------------------------------------------------

    @pytest.mark.benchmark(group="slo")
    def test_get_status_empty_window(self, benchmark: Any) -> None:
        """get_status on empty measurement window."""
        benchmark(self.tracker.get_status, "latency")

    @pytest.mark.benchmark(group="slo")
    def test_get_status_full_window(self, benchmark: Any) -> None:
        """get_status after filling the window with 1 000 measurements."""
        # Pre-fill window
        rng = random.Random(42)
        for _ in range(1000):
            self.tracker.record_measurement(
                "latency", rng.lognormvariate(-3.0, 0.5), True
            )
        benchmark(self.tracker.get_status, "latency")


class TestSLOWindowEviction:
    """Benchmark the window-eviction path (worst case: entire window stale)."""

    @pytest.fixture(autouse=True)
    def setup(self) -> Generator[None, None, None]:
        reset_settings()
        # Very short window so the first record_measurement triggers eviction
        self.tracker = _make_tracker(window_seconds=0.0)
        yield
        reset_settings()

    @pytest.mark.benchmark(group="slo_eviction")
    def test_record_with_full_eviction(self, benchmark: Any) -> None:
        """Record when all existing measurements are outside the window."""
        for _ in range(500):
            self.tracker.record_measurement("latency", 0.050, True)

        benchmark(self.tracker.record_measurement, "latency", 0.050, True)


class TestSLOConcurrentRecording:
    """Throughput under thread contention — simulates N workers sharing one tracker."""

    @pytest.fixture(autouse=True)
    def setup(self) -> Generator[None, None, None]:
        reset_settings()
        self.tracker = _make_tracker()
        yield
        reset_settings()

    @pytest.mark.benchmark(group="slo_concurrent")
    def test_record_from_16_threads(self, benchmark: Any) -> None:
        """Contended recording from 16 threads."""
        import concurrent.futures

        def batch() -> None:
            with concurrent.futures.ThreadPoolExecutor(max_workers=16) as ex:
                futs = [
                    ex.submit(self.tracker.record_measurement, "latency", 0.050, True)
                    for _ in range(16)
                ]
                for f in futs:
                    f.result()

        benchmark(batch)
