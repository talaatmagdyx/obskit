"""Additional coverage tests for executor.py."""
from __future__ import annotations

from obskit.executor import ExecutorTracker


class TestExecutorCoverage:
    def test_check_saturation_with_max_workers_zero(self):
        """Line 254: _check_saturation returns early when max_workers == 0."""
        tracker = ExecutorTracker(executor_name="zero-workers-test", max_workers=0)
        # Should not raise, should return immediately
        tracker._check_saturation()


class TestExecutorBranchCoverage:
    def test_update_utilization_with_max_workers_zero(self):
        """Line 247->exit: _update_utilization exits when max_workers == 0."""
        from obskit.executor import ExecutorTracker

        tracker = ExecutorTracker(executor_name="util-zero-test", max_workers=0)
        # Should return early without computing utilization
        tracker._update_utilization()  # Should not raise

    def test_check_saturation_on_saturated_not_called_when_none(self):
        """Line 270->exit: _check_saturation when on_saturated is None."""
        from obskit.executor import ExecutorTracker

        tracker = ExecutorTracker(
            executor_name="sat-no-cb",
            max_workers=1,
            saturation_threshold=0.1,  # low threshold to trigger saturation check
            on_saturated=None,  # no callback
        )
        tracker._active_tasks = 1  # 100% utilization -> >= 0.1 threshold
        # Should complete without calling callback
        tracker._check_saturation()

    def test_get_stats_with_max_workers_zero(self):
        """Lines 309->312: get_stats returns stats with zero utilization when max_workers==0."""
        from obskit.executor import ExecutorTracker

        tracker = ExecutorTracker(executor_name="stats-zero", max_workers=0)
        stats = tracker.get_stats()
        assert stats.utilization == 0.0

    def test_tracked_executor_shutdown_no_shutdown_method(self):
        """Line 381->exit: shutdown when executor has no shutdown method."""
        from obskit.executor import ExecutorTracker, TrackedExecutor

        class MockExecutorNoShutdown:
            def submit(self, fn, *args, **kwargs):
                import concurrent.futures
                f = concurrent.futures.Future()
                f.set_result(None)
                return f

        tracker = ExecutorTracker(executor_name="no-shutdown-test", max_workers=1)
        mock_executor = MockExecutorNoShutdown()
        tracked = TrackedExecutor(mock_executor, tracker)

        # Should not raise even though mock executor has no shutdown method
        tracked.shutdown(wait=False)

    def test_get_executor_tracker_singleton_inner_branch(self):
        """Lines 412-413: inner lock branch in get_executor_tracker."""
        import obskit.executor as module

        unique_name = "__cov_tracker_inner_branch__"
        module._trackers.pop(unique_name, None)

        tracker1 = module.get_executor_tracker(unique_name)
        tracker2 = module.get_executor_tracker(unique_name)
        assert tracker1 is tracker2
        module._trackers.pop(unique_name, None)
