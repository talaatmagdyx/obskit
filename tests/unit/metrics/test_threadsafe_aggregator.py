"""Tests for obskit.metrics.threadsafe_aggregator."""

import threading
import time

from obskit.metrics.threadsafe_aggregator import ThreadLocalAggregator


class TestThreadLocalAggregator:
    """Unit tests for ThreadLocalAggregator."""

    def test_record_request_increments_count(self):
        """A recorded request shows up in pending counts."""
        agg = ThreadLocalAggregator(flush_interval_s=10.0)
        agg.record_request("op_a", duration_s=0.01, success=True)
        counts = agg.get_pending_counts()
        assert counts.get(("op_a", "success"), 0) == 1

    def test_record_failure_uses_failure_status(self):
        """Failed requests are keyed as 'failure'."""
        agg = ThreadLocalAggregator(flush_interval_s=10.0)
        agg.record_request("op_b", duration_s=0.5, success=False)
        counts = agg.get_pending_counts()
        assert counts.get(("op_b", "failure"), 0) == 1

    def test_multiple_records_same_thread(self):
        """Multiple records on the same thread accumulate correctly."""
        agg = ThreadLocalAggregator(flush_interval_s=10.0)
        for _ in range(5):
            agg.record_request("op_c", duration_s=0.01, success=True)
        counts = agg.get_pending_counts()
        assert counts[("op_c", "success")] == 5

    def test_flush_calls_on_flush_callback(self):
        """Background flush calls the on_flush callback with merged data."""
        received: list[dict] = []

        def on_flush(counts, durations):
            received.append({"counts": counts, "durations": durations})

        agg = ThreadLocalAggregator(flush_interval_s=0.05, on_flush=on_flush)
        agg.start()
        agg.record_request("op_d", duration_s=0.01, success=True)
        # Wait for at least one flush cycle
        time.sleep(0.2)
        agg.stop()

        assert any(("op_d", "success") in r["counts"] for r in received)

    def test_flush_clears_pending_counts(self):
        """After flush, pending counts are reset to zero."""
        flushed = {}

        def on_flush(counts, durations):
            flushed.update(counts)

        agg = ThreadLocalAggregator(flush_interval_s=0.05, on_flush=on_flush)
        agg.start()
        agg.record_request("op_e", duration_s=0.01, success=True)
        time.sleep(0.2)
        agg.stop()

        # After stop() calls _flush_once, pending counts should be empty
        remaining = agg.get_pending_counts()
        assert remaining.get(("op_e", "success"), 0) == 0

    def test_multithreaded_records_merged(self):
        """Records from multiple threads are all captured."""
        merged_counts: dict = {}

        def on_flush(counts, durations):
            for k, v in counts.items():
                merged_counts[k] = merged_counts.get(k, 0) + v

        agg = ThreadLocalAggregator(flush_interval_s=0.05, on_flush=on_flush)
        agg.start()

        n_threads = 8
        per_thread = 10

        def worker():
            for _ in range(per_thread):
                agg.record_request("op_mt", duration_s=0.001, success=True)

        threads = [threading.Thread(target=worker) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        time.sleep(0.3)
        agg.stop()

        total = merged_counts.get(("op_mt", "success"), 0)
        assert total == n_threads * per_thread

    def test_start_is_idempotent(self):
        """Calling start() twice does not spawn a second thread."""
        agg = ThreadLocalAggregator(flush_interval_s=10.0)
        agg.start()
        thread1 = agg._flush_thread
        agg.start()
        thread2 = agg._flush_thread
        assert thread1 is thread2
        agg.stop()

    def test_stop_performs_final_flush(self):
        """stop() flushes remaining records before returning."""
        received: list[dict] = []

        def on_flush(counts, durations):
            received.append(counts)

        agg = ThreadLocalAggregator(flush_interval_s=60.0, on_flush=on_flush)
        agg.start()
        agg.record_request("op_final", duration_s=0.01, success=True)
        agg.stop()

        total = sum(r.get(("op_final", "success"), 0) for r in received)
        assert total >= 1

    def test_no_flush_callback_is_noop(self):
        """Without on_flush, flush silently succeeds without error."""
        agg = ThreadLocalAggregator(flush_interval_s=0.05)
        agg.start()
        agg.record_request("op_noop", duration_s=0.01, success=True)
        time.sleep(0.1)
        agg.stop()  # should not raise
