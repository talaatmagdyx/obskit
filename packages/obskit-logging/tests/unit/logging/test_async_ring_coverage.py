"""Tests for async_ring.py branch coverage."""
from __future__ import annotations

import threading
import time

from obskit.logging.async_ring import AsyncLogRing


class TestAsyncRingBranchCoverage:
    """Cover remaining branches in async_ring.py."""

    def test_drain_loop_with_non_empty_queue(self):
        """Line 153->150: queue NOT empty, so loop back without wait.
        
        drain_batch defaults to 500. If we put 1001 items, after the first
        drain_once call there are still 501 items left (queue NOT empty),
        so the loop goes back to line 150 without the wait at line 154.
        """
        emitted = []
        ring = AsyncLogRing(maxsize=100000, drain_batch=500)
        ring.start(emit_fn=emitted.append)

        # Enqueue more than drain_batch items so queue is non-empty after one drain
        for i in range(1001):
            ring.enqueue({"event": f"item-{i}"})

        # Give drain loop time to process
        time.sleep(0.5)
        ring.stop()

        # All items should be drained
        assert len(emitted) == 1001
