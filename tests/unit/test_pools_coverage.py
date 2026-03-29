"""Tests to cover remaining branch misses in pools.py."""

from __future__ import annotations

from unittest.mock import patch
import pytest


class TestPoolsBranchCoverage:
    """Cover remaining branch misses in pools.py."""

    def test_track_size_exhausted_without_callback(self):
        """Line 260->exit: on_exhausted is None when pool is exhausted."""
        from obskit.pools import ConnectionPoolTracker, PoolType

        tracker = ConnectionPoolTracker(
            pool_name="pools-no-cb-exhaust",
            pool_type=PoolType.DATABASE,
            max_size=1,
            alert_threshold=0.1,  # very low to trigger check
            on_exhausted=None,  # No callback - covers 260->exit
        )

        # Trigger exhaustion: active=1, max_size=1 -> utilization=1.0 >= 1.0
        tracker.set_pool_size(active=1)  # Should complete without calling callback

    def test_get_stats_with_max_size_zero(self):
        """Lines 355->358: get_stats with max_size=0 returns zero utilization."""
        from obskit.pools import ConnectionPoolTracker, PoolType

        tracker = ConnectionPoolTracker(
            pool_name="pools-zero-size-stats",
            pool_type=PoolType.DATABASE,
            max_size=0,  # Zero max size
        )
        stats = tracker.get_stats()
        assert stats.utilization == pytest.approx(0.0)

    def test_get_pool_tracker_inner_lock_branch(self):
        """Lines 414->421: inner lock branch when pool tracker already exists."""
        import obskit.pools as module
        from obskit.pools import ConnectionPoolTracker, PoolType

        pool_name = "__inner_lock_pool_test__"
        pool_type = PoolType.DATABASE
        key = f"{pool_name}:{pool_type.value}"
        module._pools.pop(key, None)

        class _FakeDict(dict):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self._first_call_done = False
                self._target_key = None

            def __contains__(self, item):
                if item == self._target_key and not self._first_call_done:
                    self._first_call_done = True
                    return False
                return super().__contains__(item)

        existing_tracker = ConnectionPoolTracker(
            pool_name=pool_name,
            pool_type=pool_type,
        )

        fake_dict = _FakeDict()
        fake_dict._target_key = key
        fake_dict[key] = existing_tracker

        original_dict = module._pools
        module._pools = fake_dict
        try:
            result = module.get_pool_tracker(pool_name, pool_type)
            assert result is existing_tracker
        finally:
            module._pools = original_dict
            module._pools.pop(key, None)
