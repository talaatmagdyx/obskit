"""Tests for obskit.logging.async_ring."""

import threading
import time
from unittest.mock import patch

from obskit.logging.async_ring import AsyncLogRing


class TestAsyncLogRing:
    """Unit tests for AsyncLogRing."""

    def test_enqueue_returns_true_when_not_full(self):
        ring = AsyncLogRing(maxsize=10)
        result = ring.enqueue({"event": "test"})
        assert result is True

    def test_enqueue_returns_false_when_full(self):
        ring = AsyncLogRing(maxsize=2)
        ring.enqueue({"event": "1"})
        ring.enqueue({"event": "2"})
        # Buffer is now full
        result = ring.enqueue({"event": "3"})
        assert result is False
        assert ring.dropped == 1

    def test_dropped_counter_increments(self):
        ring = AsyncLogRing(maxsize=1)
        ring.enqueue({"event": "a"})
        ring.enqueue({"event": "b"})  # dropped
        ring.enqueue({"event": "c"})  # dropped
        assert ring.dropped == 2

    def test_qsize_reflects_queue_depth(self):
        ring = AsyncLogRing(maxsize=100)
        ring.enqueue({"event": "a"})
        ring.enqueue({"event": "b"})
        assert ring.qsize >= 1  # at least 1 pending

    def test_emit_fn_called_for_each_record(self):
        emitted: list[dict] = []
        ring = AsyncLogRing(maxsize=100)
        ring.start(emit_fn=emitted.append)

        ring.enqueue({"event": "e1"})
        ring.enqueue({"event": "e2"})

        time.sleep(0.1)
        ring.stop()

        events = [r.get("event") for r in emitted]
        assert "e1" in events
        assert "e2" in events

    def test_stop_flushes_remaining_records(self):
        emitted: list[dict] = []
        ring = AsyncLogRing(maxsize=1000)
        ring.start(emit_fn=emitted.append)

        for i in range(50):
            ring.enqueue({"event": f"e{i}"})

        ring.stop()  # blocks until drain is done

        assert len(emitted) == 50

    def test_start_is_idempotent(self):
        ring = AsyncLogRing(maxsize=100)
        ring.start(emit_fn=lambda r: None)
        t1 = ring._drain_thread
        ring.start(emit_fn=lambda r: None)  # second call is a no-op
        t2 = ring._drain_thread
        assert t1 is t2
        ring.stop()

    def test_emit_fn_exception_does_not_crash_drainer(self):
        """An exception in emit_fn must not kill the drain thread."""
        call_count = [0]

        def flaky_emit(r):
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("emit error")

        ring = AsyncLogRing(maxsize=100)
        ring.start(emit_fn=flaky_emit)

        ring.enqueue({"event": "a"})
        ring.enqueue({"event": "b"})

        time.sleep(0.1)
        ring.stop()

        assert call_count[0] >= 2  # drainer survived the first exception

    def test_multithreaded_enqueue(self):
        """Concurrent enqueue from multiple threads is safe."""
        emitted: list[dict] = []
        lock = threading.Lock()

        def safe_emit(r):
            with lock:
                emitted.append(r)

        ring = AsyncLogRing(maxsize=10_000)
        ring.start(emit_fn=safe_emit)

        n_threads = 10
        per_thread = 100

        def worker():
            for i in range(per_thread):
                ring.enqueue({"event": f"t{i}"})

        threads = [threading.Thread(target=worker) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        time.sleep(0.2)
        ring.stop()

        # All records should have been emitted (queue is large enough)
        assert len(emitted) == n_threads * per_thread

    def test_no_emit_fn_before_start(self):
        """Calling stop before start does not raise."""
        ring = AsyncLogRing(maxsize=10)
        ring.enqueue({"event": "orphan"})
        ring.stop()  # should not raise

    def test_drop_warning_logged_every_1000(self):
        """A stdlib warning is emitted on every 1000th dropped record."""
        import logging

        ring = AsyncLogRing(maxsize=1)
        ring.enqueue({"event": "fill"})  # fills the single slot
        with patch("obskit.logging.async_ring._ring_logger") as mock_log:
            for _ in range(1000):
                ring.enqueue({"event": "drop"})
            assert ring.dropped == 1000
            mock_log.warning.assert_called_once()
