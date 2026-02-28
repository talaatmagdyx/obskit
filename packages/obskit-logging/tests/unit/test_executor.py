"""Unit tests for obskit.executor — thread/process pool executor metrics."""

from __future__ import annotations

import time
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from obskit.executor import (
    ExecutorStats,
    ExecutorTracker,
    TrackedExecutor,
    create_tracked_executor,
    get_all_executor_stats,
    get_executor_tracker,
    wrap_executor,
)


# =============================================================================
# ExecutorStats
# =============================================================================


class TestExecutorStats:
    def test_basic_creation(self):
        stats = ExecutorStats(executor_name="test_exec", max_workers=10)
        assert stats.executor_name == "test_exec"
        assert stats.max_workers == 10

    def test_default_values(self):
        stats = ExecutorStats(executor_name="exec", max_workers=5)
        assert stats.active_tasks == 0
        assert stats.queue_size == 0
        assert stats.tasks_submitted == 0
        assert stats.tasks_completed == 0
        assert stats.tasks_failed == 0
        assert stats.utilization == 0.0

    def test_to_dict(self):
        stats = ExecutorStats(executor_name="exec", max_workers=4)
        d = stats.to_dict()
        assert d["executor_name"] == "exec"
        assert d["max_workers"] == 4
        assert "active_tasks" in d
        assert "utilization" in d
        assert "last_updated" in d


# =============================================================================
# ExecutorTracker
# =============================================================================


class TestExecutorTrackerInit:
    def test_basic_init(self):
        tracker = ExecutorTracker("test_tracker", max_workers=5)
        assert tracker.executor_name == "test_tracker"
        assert tracker.max_workers == 5

    def test_default_saturation_threshold(self):
        tracker = ExecutorTracker("tracker")
        assert tracker.saturation_threshold == 0.9

    def test_custom_saturation_threshold(self):
        tracker = ExecutorTracker("tracker", saturation_threshold=0.8)
        assert tracker.saturation_threshold == 0.8

    def test_on_saturated_callback_stored(self):
        callback = MagicMock()
        tracker = ExecutorTracker("tracker", on_saturated=callback)
        assert tracker.on_saturated is callback

    def test_initial_counters_zero(self):
        tracker = ExecutorTracker("tracker")
        assert tracker._active_tasks == 0
        assert tracker._queue_size == 0
        assert tracker._tasks_submitted == 0
        assert tracker._tasks_completed == 0
        assert tracker._tasks_failed == 0


class TestExecutorTrackerTaskLifecycle:
    def test_task_submitted_increments_submitted_count(self):
        tracker = ExecutorTracker("exec_test_submit")
        tracker.task_submitted()
        assert tracker._tasks_submitted == 1

    def test_task_submitted_increments_queue_size(self):
        tracker = ExecutorTracker("exec_test_queue")
        tracker.task_submitted()
        assert tracker._queue_size == 1

    def test_task_started_decrements_queue(self):
        tracker = ExecutorTracker("exec_test_start")
        tracker.task_submitted()
        tracker.task_started(0.01)
        assert tracker._queue_size == 0

    def test_task_started_increments_active(self):
        tracker = ExecutorTracker("exec_test_active")
        tracker.task_submitted()
        tracker.task_started(0.01)
        assert tracker._active_tasks == 1

    def test_task_started_records_queue_wait(self):
        tracker = ExecutorTracker("exec_test_wait")
        tracker.task_submitted()
        tracker.task_started(0.05)
        assert len(tracker._queue_waits) == 1
        assert tracker._queue_waits[0] == 0.05

    def test_task_completed_success_increments_completed(self):
        tracker = ExecutorTracker("exec_test_complete")
        tracker.task_submitted()
        tracker.task_started(0.0)
        tracker.task_completed(0.1, success=True)
        assert tracker._tasks_completed == 1
        assert tracker._tasks_failed == 0

    def test_task_completed_failure_increments_failed(self):
        tracker = ExecutorTracker("exec_test_fail")
        tracker.task_submitted()
        tracker.task_started(0.0)
        tracker.task_completed(0.1, success=False)
        assert tracker._tasks_completed == 0
        assert tracker._tasks_failed == 1

    def test_task_completed_decrements_active(self):
        tracker = ExecutorTracker("exec_test_dec")
        tracker.task_submitted()
        tracker.task_started(0.0)
        assert tracker._active_tasks == 1
        tracker.task_completed(0.1, success=True)
        assert tracker._active_tasks == 0

    def test_task_latency_recorded(self):
        tracker = ExecutorTracker("exec_test_latency")
        tracker.task_submitted()
        tracker.task_started(0.0)
        tracker.task_completed(0.5, success=True)
        assert len(tracker._task_latencies) == 1
        assert tracker._task_latencies[0] == 0.5

    def test_queue_waits_trimmed_at_1000(self):
        tracker = ExecutorTracker("exec_test_trim")
        tracker._queue_waits = list(range(1000))
        tracker.task_submitted()
        tracker.task_started(0.01)
        assert len(tracker._queue_waits) == 1000

    def test_task_latencies_trimmed_at_1000(self):
        tracker = ExecutorTracker("exec_test_trim2")
        tracker._task_latencies = list(range(1000))
        tracker.task_submitted()
        tracker.task_started(0.0)
        tracker.task_completed(0.1, success=True)
        assert len(tracker._task_latencies) == 1000


class TestExecutorTrackerSaturation:
    def test_not_saturated_initially(self):
        tracker = ExecutorTracker("exec_sat", max_workers=10)
        assert not tracker.is_saturated()

    def test_saturated_when_fully_loaded(self):
        tracker = ExecutorTracker("exec_sat2", max_workers=2, saturation_threshold=0.9)
        tracker._active_tasks = 2
        assert tracker.is_saturated()

    def test_not_saturated_with_zero_max_workers(self):
        tracker = ExecutorTracker("exec_zero", max_workers=0)
        assert not tracker.is_saturated()

    def test_saturation_callback_called_when_saturated(self):
        callback = MagicMock()
        tracker = ExecutorTracker(
            "exec_sat_cb",
            max_workers=2,
            saturation_threshold=0.5,
            on_saturated=callback,
        )
        tracker._active_tasks = 2  # 100% utilization, above 50% threshold
        tracker.task_submitted()  # triggers _check_saturation
        callback.assert_called_once_with("exec_sat_cb")

    def test_no_saturation_callback_when_not_saturated(self):
        callback = MagicMock()
        tracker = ExecutorTracker(
            "exec_no_sat",
            max_workers=10,
            saturation_threshold=0.9,
            on_saturated=callback,
        )
        tracker.task_submitted()
        callback.assert_not_called()


class TestExecutorTrackerGetStats:
    def test_get_stats_returns_executor_stats(self):
        tracker = ExecutorTracker("exec_stats", max_workers=5)
        stats = tracker.get_stats()
        assert isinstance(stats, ExecutorStats)

    def test_get_stats_reflects_current_state(self):
        tracker = ExecutorTracker("exec_state", max_workers=10)
        tracker.task_submitted()
        tracker.task_started(0.01)
        tracker.task_completed(0.2, success=True)

        stats = tracker.get_stats()
        assert stats.tasks_submitted == 1
        assert stats.tasks_completed == 1
        assert stats.avg_task_latency_ms == pytest.approx(200.0, abs=1.0)

    def test_get_stats_avg_queue_wait(self):
        tracker = ExecutorTracker("exec_queue_wait", max_workers=5)
        tracker.task_submitted()
        tracker.task_started(0.1)  # 100ms wait

        stats = tracker.get_stats()
        assert stats.avg_queue_wait_ms == pytest.approx(100.0, abs=1.0)

    def test_get_stats_zero_avg_when_no_tasks(self):
        tracker = ExecutorTracker("exec_no_tasks")
        stats = tracker.get_stats()
        assert stats.avg_task_latency_ms == 0.0
        assert stats.avg_queue_wait_ms == 0.0

    def test_get_stats_utilization_calculated(self):
        tracker = ExecutorTracker("exec_util", max_workers=10)
        tracker._active_tasks = 5
        stats = tracker.get_stats()
        assert stats.utilization == pytest.approx(0.5, abs=0.01)


class TestExecutorTrackerSetStats:
    def test_set_active_tasks(self):
        tracker = ExecutorTracker("exec_set", max_workers=10)
        tracker.set_stats(active_tasks=5)
        assert tracker._active_tasks == 5

    def test_set_queue_size(self):
        tracker = ExecutorTracker("exec_set_q", max_workers=10)
        tracker.set_stats(queue_size=3)
        assert tracker._queue_size == 3

    def test_set_max_workers(self):
        tracker = ExecutorTracker("exec_set_mw", max_workers=5)
        tracker.set_stats(max_workers=20)
        assert tracker.max_workers == 20

    def test_set_stats_none_values_no_change(self):
        tracker = ExecutorTracker("exec_set_none", max_workers=10)
        tracker._active_tasks = 3
        tracker.set_stats()  # All None
        assert tracker._active_tasks == 3


class TestExecutorTrackerWrap:
    def test_wrap_returns_tracked_executor(self):
        tracker = ExecutorTracker("exec_wrap", max_workers=2)
        executor = ThreadPoolExecutor(max_workers=2)
        tracked = tracker.wrap(executor)
        assert isinstance(tracked, TrackedExecutor)
        executor.shutdown(wait=False)


# =============================================================================
# TrackedExecutor
# =============================================================================


class TestTrackedExecutor:
    def _make_tracked_executor(self, name="tracked_test"):
        executor = ThreadPoolExecutor(max_workers=2)
        tracker = ExecutorTracker(name, max_workers=2)
        return TrackedExecutor(executor, tracker), executor

    def test_submit_runs_function(self):
        tracked, executor = self._make_tracked_executor("tracked_run")
        future = tracked.submit(lambda: "hello")
        result = future.result(timeout=5)
        assert result == "hello"
        executor.shutdown(wait=True)

    def test_submit_passes_args(self):
        tracked, executor = self._make_tracked_executor("tracked_args")
        future = tracked.submit(lambda a, b: a + b, 3, 4)
        assert future.result(timeout=5) == 7
        executor.shutdown(wait=True)

    def test_submit_tracks_submission(self):
        tracked, executor = self._make_tracked_executor("tracked_track")
        future = tracked.submit(lambda: None)
        future.result(timeout=5)
        assert tracked._tracker._tasks_submitted == 1
        executor.shutdown(wait=True)

    def test_submit_tracks_completion(self):
        tracked, executor = self._make_tracked_executor("tracked_comp")
        future = tracked.submit(lambda: None)
        future.result(timeout=5)
        time.sleep(0.05)  # Allow tracking to complete
        assert tracked._tracker._tasks_completed == 1
        executor.shutdown(wait=True)

    def test_submit_tracks_failure(self):
        def failing():
            raise ValueError("task error")

        tracked, executor = self._make_tracked_executor("tracked_fail")
        future = tracked.submit(failing)
        with pytest.raises(ValueError, match="task error"):
            future.result(timeout=5)
        time.sleep(0.05)
        assert tracked._tracker._tasks_failed == 1
        executor.shutdown(wait=True)

    def test_tracker_property(self):
        tracked, executor = self._make_tracked_executor("tracked_prop")
        assert isinstance(tracked.tracker, ExecutorTracker)
        executor.shutdown(wait=True)

    def test_context_manager_usage(self):
        executor = ThreadPoolExecutor(max_workers=2)
        tracker = ExecutorTracker("tracked_ctx", max_workers=2)
        with TrackedExecutor(executor, tracker) as tracked:
            future = tracked.submit(lambda: "result")
            assert future.result(timeout=5) == "result"

    def test_map_delegates_to_underlying_executor(self):
        tracked, executor = self._make_tracked_executor("tracked_map")
        results = list(tracked.map(lambda x: x * 2, [1, 2, 3]))
        assert sorted(results) == [2, 4, 6]
        executor.shutdown(wait=True)

    def test_shutdown_delegates_to_underlying_executor(self):
        executor = MagicMock()
        executor.shutdown = MagicMock()
        tracker = ExecutorTracker("tracked_shutdown", max_workers=2)
        tracked = TrackedExecutor(executor, tracker)
        tracked.shutdown(wait=True)
        executor.shutdown.assert_called_once_with(wait=True, cancel_futures=False)


# =============================================================================
# Factory functions
# =============================================================================


class TestGetExecutorTracker:
    def test_returns_executor_tracker(self):
        tracker = get_executor_tracker("get_test_exec_tracker")
        assert isinstance(tracker, ExecutorTracker)

    def test_same_instance_for_same_name(self):
        name = "same_tracker_test_get"
        t1 = get_executor_tracker(name)
        t2 = get_executor_tracker(name)
        assert t1 is t2


class TestWrapExecutor:
    def test_wraps_thread_pool_executor(self):
        executor = ThreadPoolExecutor(max_workers=4)
        tracked = wrap_executor(executor, "wrap_test_exec")
        assert isinstance(tracked, TrackedExecutor)
        executor.shutdown(wait=False)

    def test_auto_detects_max_workers(self):
        executor = ThreadPoolExecutor(max_workers=7)
        tracked = wrap_executor(executor, "wrap_auto_detect")
        assert tracked._tracker.max_workers == 7
        executor.shutdown(wait=False)

    def test_uses_default_max_workers_when_not_detectable(self):
        executor = MagicMock(spec=[])  # No _max_workers attribute
        tracked = wrap_executor(executor, "wrap_no_detect", max_workers=None)
        assert tracked._tracker.max_workers == 10


class TestCreateTrackedExecutor:
    def test_creates_thread_executor(self):
        tracked = create_tracked_executor("create_thread_test", max_workers=2, executor_type="thread")
        assert isinstance(tracked, TrackedExecutor)
        tracked.shutdown(wait=True)

    def test_creates_process_executor(self):
        tracked = create_tracked_executor("create_proc_test", max_workers=1, executor_type="process")
        assert isinstance(tracked, TrackedExecutor)
        tracked.shutdown(wait=True)

    def test_raises_for_unknown_executor_type(self):
        with pytest.raises(ValueError, match="Unknown executor type"):
            create_tracked_executor("invalid_test", executor_type="unknown")


class TestGetAllExecutorStats:
    def test_returns_dict(self):
        # Ensure at least one tracker exists
        get_executor_tracker("all_stats_test")
        stats = get_all_executor_stats()
        assert isinstance(stats, dict)
        assert "all_stats_test" in stats

    def test_values_are_executor_stats(self):
        get_executor_tracker("all_stats_values_test")
        stats = get_all_executor_stats()
        for value in stats.values():
            assert isinstance(value, ExecutorStats)
