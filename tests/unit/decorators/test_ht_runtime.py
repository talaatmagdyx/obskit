"""Tests for obskit.decorators.ht_runtime._HTPipeline singleton."""

import warnings
from unittest.mock import MagicMock

from obskit.decorators.ht_runtime import (
    _HTPipeline,
    configure_ht_pipeline,
    get_ht_pipeline,
    reset_ht_pipeline,
)


class TestHTPipelineSingleton:
    """Tests for the module-level singleton behaviour."""

    def setup_method(self):
        reset_ht_pipeline()

    def teardown_method(self):
        reset_ht_pipeline()

    def test_get_ht_pipeline_returns_instance(self):
        """get_ht_pipeline returns an _HTPipeline object."""
        assert isinstance(get_ht_pipeline(), _HTPipeline)

    def test_get_ht_pipeline_returns_same_object(self):
        """Repeated calls return the same singleton."""
        assert get_ht_pipeline() is get_ht_pipeline()

    def test_reset_creates_new_instance(self):
        """After reset, get_ht_pipeline returns a fresh object."""
        p1 = get_ht_pipeline()
        reset_ht_pipeline()
        p2 = get_ht_pipeline()
        assert p1 is not p2

    def test_pipeline_is_lazy_before_first_record(self):
        """Pipeline is not started until record() is called."""
        p = get_ht_pipeline()
        assert p.started is False

    def test_stop_is_idempotent(self):
        """Calling stop() multiple times does not raise."""
        p = get_ht_pipeline()
        p.stop()
        p.stop()  # second call should be a no-op


class TestHTPipelineRecord:
    """Tests for _HTPipeline.record() hot-path method."""

    def setup_method(self):
        reset_ht_pipeline()

    def teardown_method(self):
        reset_ht_pipeline()

    def test_record_starts_pipeline(self):
        """First record() call starts the daemon threads."""
        p = get_ht_pipeline()
        assert p.started is False
        p.record("op", "comp", 0.01, True, {})
        assert p.started is True

    def test_record_success_buffers_metric(self):
        """A successful record appears in the pending counts."""
        p = get_ht_pipeline()
        p.record("create_order", "OrderService", 0.045, True, {})
        counts = p._agg.get_pending_counts()
        assert counts.get(("create_order", "success"), 0) == 1

    def test_record_failure_buffers_metric(self):
        """A failed record is counted as 'failure'."""
        p = get_ht_pipeline()
        p.record("create_order", "OrderService", 0.1, False, {})
        counts = p._agg.get_pending_counts()
        assert counts.get(("create_order", "failure"), 0) == 1

    def test_record_enqueues_log(self):
        """record() puts a log record into the ring buffer."""
        p = get_ht_pipeline()
        p.record("search", "SearchService", 0.012, True, {})
        assert p._ring.qsize >= 1

    def test_record_with_error_enqueues_error_info(self):
        """record() with error includes error/error_type in log record."""
        p = get_ht_pipeline()
        exc = ValueError("test error")
        p.record("search", "SearchService", 0.012, False, {}, error=exc)
        # Queue has a record; we can't inspect it directly but ring.qsize confirms it
        assert p._ring.qsize >= 1

    def test_record_multiple_ops(self):
        """Multiple different operations are tracked independently."""
        p = get_ht_pipeline()
        p.record("op_a", "Svc", 0.01, True, {})
        p.record("op_b", "Svc", 0.02, True, {})
        p.record("op_a", "Svc", 0.01, False, {})
        counts = p._agg.get_pending_counts()
        assert counts[("op_a", "success")] == 1
        assert counts[("op_b", "success")] == 1
        assert counts[("op_a", "failure")] == 1

    def test_record_with_context(self):
        """context dict fields are passed through without raising."""
        p = get_ht_pipeline()
        p.record("op", "comp", 0.01, True, {"tenant_id": "t-123", "region": "us"})
        assert p._ring.qsize >= 1

    def test_stop_after_record_is_clean(self):
        """stop() after records have been buffered does not raise."""
        p = get_ht_pipeline()
        p.record("op", "comp", 0.01, True, {})
        p.stop()  # should not raise
        assert p.started is False


class TestHTPipelineConfigure:
    """Tests for _HTPipeline.configure() and configure_ht_pipeline()."""

    def setup_method(self):
        reset_ht_pipeline()

    def teardown_method(self):
        reset_ht_pipeline()

    def test_configure_sets_statsd(self):
        """configure() stores the provided StatsDEmitter."""
        mock_statsd = MagicMock()
        p = get_ht_pipeline()
        p.configure(statsd=mock_statsd)
        assert p._statsd is mock_statsd

    def test_configure_sets_slo_tracker(self):
        """configure() stores the provided HighThroughputSLOTracker."""
        mock_tracker = MagicMock()
        p = get_ht_pipeline()
        p.configure(slo_tracker=mock_tracker)
        assert p._slo_tracker is mock_tracker

    def test_configure_after_start_warns(self):
        """Calling configure() after pipeline has started issues RuntimeWarning."""
        p = get_ht_pipeline()
        p.record("op", "comp", 0.01, True, {})  # starts the pipeline
        assert p.started is True
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            p.configure(statsd=MagicMock())
        assert len(caught) == 1
        assert issubclass(caught[0].category, RuntimeWarning)
        assert "already started" in str(caught[0].message)

    def test_record_calls_slo_tracker(self):
        """record() forwards measurements to the attached SLO tracker."""
        mock_tracker = MagicMock()
        p = get_ht_pipeline()
        p.configure(slo_tracker=mock_tracker)
        p.record("my_op", "MySvc", 0.05, True, {})
        mock_tracker.record_measurement.assert_called_once_with("my_op", 0.05, success=True)

    def test_record_calls_slo_tracker_on_failure(self):
        """record() passes success=False to SLO tracker on failure path."""
        mock_tracker = MagicMock()
        p = get_ht_pipeline()
        p.configure(slo_tracker=mock_tracker)
        p.record("my_op", "MySvc", 0.1, False, {})
        mock_tracker.record_measurement.assert_called_once_with("my_op", 0.1, success=False)

    def test_record_without_slo_tracker_is_safe(self):
        """record() works correctly when no SLO tracker is attached."""
        p = get_ht_pipeline()
        p.record("op", "comp", 0.01, True, {})  # must not raise
        assert p.started is True

    def test_configure_ht_pipeline_module_level(self):
        """configure_ht_pipeline() sets attributes on the module singleton."""
        mock_statsd = MagicMock()
        mock_tracker = MagicMock()
        configure_ht_pipeline(statsd=mock_statsd, slo_tracker=mock_tracker)
        p = get_ht_pipeline()
        assert p._statsd is mock_statsd
        assert p._slo_tracker is mock_tracker

    def test_statsd_emitted_on_flush(self):
        """After pipeline flushes, emit_counter is called on attached StatsD emitter."""
        import time

        mock_statsd = MagicMock()
        p = get_ht_pipeline()
        p.configure(statsd=mock_statsd)
        p.record("flush_op", "Svc", 0.02, True, {})
        # Wait slightly longer than flush_interval_s (1.0 s) for the aggregator to flush
        time.sleep(1.5)
        mock_statsd.emit_counter.assert_called()



class TestHTPipelineStopBranches:
    """Tests for _HTPipeline.stop() branches (lines 176->178, 178->180)."""

    def setup_method(self):
        reset_ht_pipeline()

    def teardown_method(self):
        reset_ht_pipeline()

    def test_stop_when_agg_is_none(self):
        """stop() skips _agg.stop() when _agg is None (branch 176->178).

        This covers the case where _agg is manually set to None before stop().
        """
        p = get_ht_pipeline()
        # Start the pipeline
        p.record("op", "comp", 0.01, True, {})
        assert p.started is True
        # Manually set _agg to None to simulate the branch
        p._agg = None
        # stop() should not raise even with _agg=None
        p.stop()
        assert p.started is False

    def test_stop_when_ring_is_none(self):
        """stop() skips _ring.stop() when _ring is None (branch 178->180).

        This covers the case where _ring is manually set to None before stop().
        """
        p = get_ht_pipeline()
        # Start the pipeline
        p.record("op", "comp", 0.01, True, {})
        assert p.started is True
        # Manually set _ring to None to simulate the branch
        p._ring = None
        # stop() should not raise even with _ring=None
        p.stop()
        assert p.started is False

    def test_stop_when_both_agg_and_ring_are_none(self):
        """stop() handles both _agg and _ring being None."""
        p = get_ht_pipeline()
        p.record("op", "comp", 0.01, True, {})
        assert p.started is True
        p._agg = None
        p._ring = None
        p.stop()
        assert p.started is False


class TestHTPipelineEnsureStartedInnerBranch:
    """Tests for _ensure_started inner double-checked lock branch (line 194)."""

    def setup_method(self):
        reset_ht_pipeline()

    def teardown_method(self):
        reset_ht_pipeline()

    def test_ensure_started_inner_check_skips_do_start(self):
        """_ensure_started inner if branch: started=True inside lock skips _do_start.

        Line 194: the inner if self._started: return inside the lock.
        This is the double-checked locking pattern: another thread started the
        pipeline between our outer check and acquiring the lock.
        """
        p = get_ht_pipeline()
        original_lock = p._lock

        class RaceConditionLock:
            """Simulates another thread starting pipeline while we waited for lock."""
            def __enter__(self):
                # Simulate another thread calling _do_start while we waited
                p._started = True
                return self

            def __exit__(self, *args):
                return False

        # Ensure _started is False so outer check (line 190) passes
        p._started = False
        p._lock = RaceConditionLock()
        try:
            p._ensure_started()
            # _started was set to True inside the lock, so _do_start was skipped
            assert p._started is True
        finally:
            p._lock = original_lock
            reset_ht_pipeline()
