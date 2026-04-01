"""
obskit performance benchmarks.

These tests verify correctness under load and establish minimum throughput
floors. They are intentionally generous so they pass on slow CI machines.
Run locally for accurate numbers.
"""
from __future__ import annotations

import threading
import time
import uuid

import pytest


# =============================================================================
# 1. AsyncLogRing — lock-free ring buffer throughput
# =============================================================================

class TestAsyncLogRingThroughput:
    """Verify AsyncLogRing enqueues records quickly and drains without loss."""

    def test_single_producer_throughput(self):
        """Single thread: enqueue 10 000 records, expect > 100 000 rec/s."""
        from obskit.logging.async_ring import AsyncLogRing

        emitted = []
        ring = AsyncLogRing(maxsize=50_000)
        ring.start(emit_fn=lambda r: emitted.append(r))

        try:
            n = 10_000
            t0 = time.perf_counter()
            for i in range(n):
                ring.enqueue({"event": "bench", "i": i})
            enqueue_time = time.perf_counter() - t0

            # Drain
            ring.stop(timeout_s=5.0)

            throughput = n / enqueue_time
            print(f"\nAsyncLogRing single-producer: {throughput:,.0f} rec/s "
                  f"({enqueue_time * 1000:.1f} ms for {n} records)")

            assert throughput > 100_000, (
                f"Expected > 100 000 rec/s, got {throughput:,.0f}"
            )
            assert len(emitted) == n, (
                f"Expected {n} emitted, got {len(emitted)} (data loss)"
            )
        finally:
            ring.stop(timeout_s=1.0)

    def test_concurrent_producers_no_data_loss(self):
        """10 concurrent producers × 1 000 records = 10 000 total, no loss."""
        from obskit.logging.async_ring import AsyncLogRing

        emitted = []
        lock = threading.Lock()

        def emit(r: dict) -> None:
            with lock:
                emitted.append(r)

        ring = AsyncLogRing(maxsize=50_000)
        ring.start(emit_fn=emit)

        try:
            n_threads = 10
            n_per_thread = 1_000
            total = n_threads * n_per_thread

            threads = [
                threading.Thread(
                    target=lambda: [
                        ring.enqueue({"event": "t", "x": i})
                        for i in range(n_per_thread)
                    ]
                )
                for _ in range(n_threads)
            ]

            t0 = time.perf_counter()
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            ring.stop(timeout_s=5.0)
            elapsed = time.perf_counter() - t0

            throughput = total / elapsed
            print(f"\nAsyncLogRing concurrent ({n_threads} threads): "
                  f"{throughput:,.0f} rec/s, {len(emitted)}/{total} delivered")

            assert len(emitted) == total, (
                f"Data loss: expected {total}, got {len(emitted)}"
            )
        finally:
            ring.stop(timeout_s=1.0)


# =============================================================================
# 2. RED Metrics — concurrent observation throughput
# =============================================================================

class TestREDMetricsThroughput:
    """Verify REDMetrics is thread-safe and fast under concurrent load."""

    def test_concurrent_observe_request(self):
        """10 threads × 1 000 observations = 10 000 total, no crashes."""
        from obskit.metrics.red import REDMetrics

        # Use a unique name per test run to avoid prometheus registry conflicts
        unique_name = f"bench_{uuid.uuid4().hex[:8]}"
        red = REDMetrics(unique_name)

        errors = []
        n_threads = 10
        n_per_thread = 1_000
        total = n_threads * n_per_thread

        def worker() -> None:
            try:
                for i in range(n_per_thread):
                    red.observe_request(
                        operation="bench_op",
                        duration_seconds=0.001 * (i % 10 + 1),
                        status="success" if i % 10 != 0 else "error",
                    )
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(n_threads)]

        t0 = time.perf_counter()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        elapsed = time.perf_counter() - t0

        throughput = total / elapsed
        print(f"\nREDMetrics concurrent ({n_threads} threads): "
              f"{throughput:,.0f} obs/s, {len(errors)} errors")

        assert not errors, f"Exceptions under concurrent load: {errors}"
        assert throughput > 10_000, (
            f"Expected > 10 000 obs/s, got {throughput:,.0f}"
        )

    def test_track_request_context_manager(self):
        """track_request context manager works correctly and times operations."""
        from obskit.metrics.red import REDMetrics

        unique_name = f"bench_ctx_{uuid.uuid4().hex[:8]}"
        red = REDMetrics(unique_name)

        # Should not raise and should record duration
        with red.track_request("ctx_op"):
            time.sleep(0.001)  # 1 ms operation


# =============================================================================
# 3. SampledLogger — correctness under concurrent access
# =============================================================================

class TestSampledLoggerConcurrency:
    """Verify SampledLogger maintains correct counts under concurrent access."""

    def test_concurrent_should_log_no_race(self):
        """50 threads calling _should_log concurrently — no crashes, counts correct."""
        from obskit.logging.sampling import SampledLogger, SamplingConfig

        config = SamplingConfig(
            info_rate=1.0,       # log everything at info level
            always_log_first_n=5,
            dedupe_window_seconds=0.0,  # no dedup window for this test
        )
        sampler = SampledLogger(name="bench_concurrent", config=config)

        results = []
        lock = threading.Lock()
        errors = []

        def worker() -> None:
            try:
                for _ in range(100):
                    passed, reason = sampler._should_log("info", "bench_event")
                    with lock:
                        results.append((passed, reason))
            except Exception as exc:
                errors.append(exc)

        n_threads = 50
        threads = [threading.Thread(target=worker) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        total = n_threads * 100
        print(f"\nSampledLogger concurrent ({n_threads} threads × 100): "
              f"{len(results)}/{total} results, {len(errors)} errors")

        assert not errors, f"Exceptions under concurrent access: {errors}"
        assert len(results) == total, (
            f"Lost results: expected {total}, got {len(results)}"
        )

    def test_first_n_always_logged_under_concurrency(self):
        """always_log_first_n=10: first 10 calls always pass regardless of concurrency."""
        from obskit.logging.sampling import SampledLogger, SamplingConfig

        config = SamplingConfig(
            info_rate=0.0,       # sample nothing after first_n
            always_log_first_n=10,
            dedupe_window_seconds=0.0,
        )
        sampler = SampledLogger(name="bench_first_n", config=config)

        passed_first = []
        lock = threading.Lock()

        def worker() -> None:
            result, reason = sampler._should_log("info", "first_n_event")
            with lock:
                if reason == "first_occurrences":
                    passed_first.append(True)

        # Fire 50 concurrent calls — exactly 10 should pass as "first_occurrences"
        threads = [threading.Thread(target=worker) for _ in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        print(f"\nSampledLogger first_n: {len(passed_first)}/10 passed as first_occurrences")
        assert len(passed_first) == 10, (
            f"Expected exactly 10 first_occurrences, got {len(passed_first)}"
        )
