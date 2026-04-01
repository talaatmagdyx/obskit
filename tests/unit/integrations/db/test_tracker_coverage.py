"""Additional tests for obskit.integrations.db.tracker module to achieve 100% coverage."""

import uuid
from unittest.mock import MagicMock, patch

import pytest

import obskit.integrations.db.tracker as tracker_module
from obskit.integrations.db.tracker import DatabaseTracker, _get_slo_tracker, _get_tracer, track_query


class TestGetTracerLazy:
    """Tests for _get_tracer lazy initialization."""

    def test_get_tracer_import_exception_sets_none(self):
        """Test _get_tracer sets _tracer to None when import raises Exception (lines 38-39)."""
        original_tracer = tracker_module._tracer
        tracker_module._tracer = None
        try:
            import builtins

            original_import = builtins.__import__

            def bad_import(name, *args, **kwargs):
                if name == "obskit.tracing":
                    raise RuntimeError("tracing unavailable")
                return original_import(name, *args, **kwargs)

            with patch("builtins.__import__", side_effect=bad_import):
                result = _get_tracer()
                assert result is None
        finally:
            tracker_module._tracer = original_tracer

    def test_get_tracer_returns_cached(self):
        """Test _get_tracer returns cached tracer without re-importing."""
        original_tracer = tracker_module._tracer
        mock_tracer = MagicMock()
        tracker_module._tracer = mock_tracer
        try:
            result = _get_tracer()
            assert result is mock_tracer
        finally:
            tracker_module._tracer = original_tracer

    def test_get_tracer_successful_import(self):
        """Test _get_tracer successfully imports and sets _tracer (lines 35-37)."""
        original_tracer = tracker_module._tracer
        tracker_module._tracer = None
        try:
            mock_tracer_instance = MagicMock()
            mock_tracing_module = MagicMock()
            mock_tracing_module.get_tracer = MagicMock(return_value=mock_tracer_instance)

            with patch.dict("sys.modules", {"obskit.tracing": mock_tracing_module}):
                # Force re-evaluation by ensuring _tracer is None
                tracker_module._tracer = None
                result = _get_tracer()
                # Should have called get_tracer and set _tracer
                assert result is not None
        finally:
            tracker_module._tracer = original_tracer


class TestGetSloTrackerLazy:
    """Tests for _get_slo_tracker lazy initialization."""

    def test_get_slo_tracker_successful_import(self):
        """Test _get_slo_tracker successfully sets _slo_tracker (line 50)."""
        original_slo = tracker_module._slo_tracker
        tracker_module._slo_tracker = None
        try:
            # obskit.slo is available, so this should succeed
            result = _get_slo_tracker()
            assert result is not None
            assert tracker_module._slo_tracker is not None
        finally:
            tracker_module._slo_tracker = original_slo

    def test_get_slo_tracker_import_exception_sets_none(self):
        """Test _get_slo_tracker sets _slo_tracker to None on import failure (lines 51-52)."""
        original_slo = tracker_module._slo_tracker
        tracker_module._slo_tracker = None
        try:
            import builtins

            original_import = builtins.__import__

            def bad_import(name, *args, **kwargs):
                if name == "obskit.slo":
                    raise RuntimeError("slo unavailable")
                return original_import(name, *args, **kwargs)

            with patch("builtins.__import__", side_effect=bad_import):
                result = _get_slo_tracker()
                assert result is None
        finally:
            tracker_module._slo_tracker = original_slo

    def test_get_slo_tracker_returns_cached(self):
        """Test _get_slo_tracker returns cached value."""
        original_slo = tracker_module._slo_tracker
        mock_slo = MagicMock()
        tracker_module._slo_tracker = mock_slo
        try:
            result = _get_slo_tracker()
            assert result is mock_slo
        finally:
            tracker_module._slo_tracker = original_slo


class TestDatabaseTrackerWithTracing:
    """Tests covering tracing-related branches in DatabaseTracker."""

    def test_track_query_with_tenant_id(self):
        """Test track_query adds tenant_id to span attributes (line 169)."""
        tracker = DatabaseTracker(database_name=f"test_{uuid.uuid4().hex[:8]}")
        with tracker.track_query(
            operation="SELECT",
            query="SELECT * FROM users",
            tenant_id="company_123",
        ):
            pass  # NOSONAR

    def test_track_query_with_long_query_truncated(self):
        """Test track_query truncates long query (line 172)."""
        tracker = DatabaseTracker(database_name=f"test_{uuid.uuid4().hex[:8]}")
        long_query = "SELECT * FROM users WHERE " + "a" * 600  # >500 chars
        with tracker.track_query(
            operation="SELECT",
            query=long_query,
        ):
            pass  # NOSONAR

    def test_track_query_with_attributes(self):
        """Test track_query with extra attributes (line 174)."""
        tracker = DatabaseTracker(database_name=f"test_{uuid.uuid4().hex[:8]}")
        with tracker.track_query(
            operation="SELECT",
            attributes={"custom": "value", "another": "attr"},
        ):
            pass  # NOSONAR

    def test_track_query_enable_tracing_false(self):
        """Test track_query with enable_tracing=False skips tracer (branch 182->195)."""
        tracker = DatabaseTracker(database_name=f"test_{uuid.uuid4().hex[:8]}")
        with tracker.track_query(operation="SELECT", enable_tracing=False):
            pass  # NOSONAR

    def test_track_query_with_trace_context_enter_and_exit(self):
        """Test trace_context __enter__ and __exit__ are called (lines 197-200, 277-281)."""
        tracker = DatabaseTracker(database_name=f"test_{uuid.uuid4().hex[:8]}")

        mock_context = MagicMock()
        mock_context.__enter__ = MagicMock(return_value=None)
        mock_context.__exit__ = MagicMock(return_value=False)

        def patched_get_tracer():
            return MagicMock()

        def patched_trace_span(**kwargs):
            return mock_context

        with patch("obskit.integrations.db.tracker._get_tracer", patched_get_tracer):
            mock_tracing_module = MagicMock()
            mock_tracing_module.trace_span = patched_trace_span

            with patch.dict("sys.modules", {"obskit.tracing": mock_tracing_module}):
                with tracker.track_query(operation="SELECT", enable_tracing=True):
                    pass  # NOSONAR

        mock_context.__enter__.assert_called_once()
        mock_context.__exit__.assert_called_once_with(None, None, None)

    def test_track_query_trace_exit_exception_handled(self):
        """Test that trace_context.__exit__ exception is swallowed (lines 280-281)."""
        tracker = DatabaseTracker(database_name=f"test_{uuid.uuid4().hex[:8]}")

        mock_context = MagicMock()
        mock_context.__enter__ = MagicMock(return_value=None)
        mock_context.__exit__ = MagicMock(side_effect=RuntimeError("span cleanup failed"))

        def patched_get_tracer():
            return MagicMock()

        def patched_trace_span(**kwargs):
            return mock_context

        with patch("obskit.integrations.db.tracker._get_tracer", patched_get_tracer):
            mock_tracing_module = MagicMock()
            mock_tracing_module.trace_span = patched_trace_span

            with patch.dict("sys.modules", {"obskit.tracing": mock_tracing_module}):
                # Should not raise even though __exit__ raises
                with tracker.track_query(operation="SELECT", enable_tracing=True):
                    pass  # NOSONAR

    def test_track_query_trace_span_exception_sets_context_none(self):
        """Test trace_span call exception sets trace_context to None (lines 192-193)."""
        tracker = DatabaseTracker(database_name=f"test_{uuid.uuid4().hex[:8]}")

        def patched_get_tracer():
            return MagicMock()

        # Make trace_span raise when called
        def bad_trace_span(**kwargs):
            raise RuntimeError("trace_span failed")

        with patch("obskit.integrations.db.tracker._get_tracer", patched_get_tracer):
            mock_tracing_module = MagicMock()
            mock_tracing_module.trace_span = bad_trace_span

            with patch.dict("sys.modules", {"obskit.tracing": mock_tracing_module}):
                with tracker.track_query(operation="SELECT", enable_tracing=True):
                    pass  # NOSONAR


class TestDatabaseTrackerSLO:
    """Tests covering SLO-related branches in DatabaseTracker."""

    def test_track_query_with_slo_success(self):
        """Test SLO measurement recorded on success (lines 221-224)."""
        mock_slo_tracker = MagicMock()
        original_slo = tracker_module._slo_tracker
        tracker_module._slo_tracker = mock_slo_tracker

        try:
            tracker = DatabaseTracker(
                database_name=f"test_{uuid.uuid4().hex[:8]}",
                default_slo_name="query_latency",
            )
            with tracker.track_query(operation="SELECT", enable_slo=True):
                pass  # NOSONAR

            mock_slo_tracker.record_measurement.assert_called_once()
            call_kwargs = mock_slo_tracker.record_measurement.call_args
            assert call_kwargs[1]["success"] is True
        finally:
            tracker_module._slo_tracker = original_slo

    def test_track_query_with_slo_record_raises_exception(self):
        """Test SLO record_measurement exception is swallowed on success (lines 223-224)."""
        mock_slo_tracker = MagicMock()
        mock_slo_tracker.record_measurement.side_effect = RuntimeError("SLO failed")
        original_slo = tracker_module._slo_tracker
        tracker_module._slo_tracker = mock_slo_tracker

        try:
            tracker = DatabaseTracker(
                database_name=f"test_{uuid.uuid4().hex[:8]}",
                default_slo_name="query_latency",
            )
            with tracker.track_query(operation="SELECT", enable_slo=True):
                pass  # NOSONAR
        finally:
            tracker_module._slo_tracker = original_slo

    def test_track_query_with_slo_failure(self):
        """Test SLO measurement recorded on query failure (lines 258-261)."""
        mock_slo_tracker = MagicMock()
        original_slo = tracker_module._slo_tracker
        tracker_module._slo_tracker = mock_slo_tracker

        try:
            tracker = DatabaseTracker(
                database_name=f"test_{uuid.uuid4().hex[:8]}",
                default_slo_name="query_latency",
            )
            with pytest.raises(ValueError):
                with tracker.track_query(operation="SELECT", enable_slo=True):
                    raise ValueError("DB error")

            mock_slo_tracker.record_measurement.assert_called_once()
            call_kwargs = mock_slo_tracker.record_measurement.call_args
            assert call_kwargs[1]["success"] is False
        finally:
            tracker_module._slo_tracker = original_slo

    def test_track_query_slo_failure_record_raises_exception(self):
        """Test SLO record_measurement exception swallowed on query failure (lines 260-261)."""
        mock_slo_tracker = MagicMock()
        mock_slo_tracker.record_measurement.side_effect = RuntimeError("SLO record failed")
        original_slo = tracker_module._slo_tracker
        tracker_module._slo_tracker = mock_slo_tracker

        try:
            tracker = DatabaseTracker(
                database_name=f"test_{uuid.uuid4().hex[:8]}",
                default_slo_name="query_latency",
            )
            with pytest.raises(ValueError):
                with tracker.track_query(operation="SELECT", enable_slo=True):
                    raise ValueError("query failed")
        finally:
            tracker_module._slo_tracker = original_slo


class TestRecordQuery:
    """Tests for DatabaseTracker.record_query method (lines 310-341)."""

    def test_record_query_success(self):
        """Test record_query with successful query (lines 310-339)."""
        tracker = DatabaseTracker(database_name=f"test_{uuid.uuid4().hex[:8]}")
        tracker.record_query(
            operation="SELECT",
            duration_seconds=0.05,
            success=True,
            tenant_id="company_123",
        )

    def test_record_query_failure(self):
        """Test record_query with failed query logs warning (lines 340-348)."""
        tracker = DatabaseTracker(database_name=f"test_{uuid.uuid4().hex[:8]}")
        tracker.record_query(
            operation="INSERT",
            duration_seconds=0.1,
            success=False,
            error_type="IntegrityError",
            tenant_id="company_456",
        )

    def test_record_query_with_slo(self):
        """Test record_query with SLO tracking (lines 322-329)."""
        mock_slo_tracker = MagicMock()
        original_slo = tracker_module._slo_tracker
        tracker_module._slo_tracker = mock_slo_tracker

        try:
            tracker = DatabaseTracker(
                database_name=f"test_{uuid.uuid4().hex[:8]}",
                default_slo_name="query_slo",
            )
            tracker.record_query(
                operation="SELECT",
                duration_seconds=0.05,
                success=True,
            )
            mock_slo_tracker.record_measurement.assert_called_once()
        finally:
            tracker_module._slo_tracker = original_slo

    def test_record_query_with_slo_override(self):
        """Test record_query with explicit slo_name overrides default."""
        mock_slo_tracker = MagicMock()
        original_slo = tracker_module._slo_tracker
        tracker_module._slo_tracker = mock_slo_tracker

        try:
            tracker = DatabaseTracker(database_name=f"test_{uuid.uuid4().hex[:8]}")
            tracker.record_query(
                operation="SELECT",
                duration_seconds=0.05,
                success=True,
                slo_name="explicit_slo",
            )
            mock_slo_tracker.record_measurement.assert_called_once()
            args = mock_slo_tracker.record_measurement.call_args
            assert args[0][0] == "explicit_slo"
        finally:
            tracker_module._slo_tracker = original_slo

    def test_record_query_slo_record_exception_swallowed(self):
        """Test record_query swallows SLO tracking exceptions (lines 328-329)."""
        mock_slo_tracker = MagicMock()
        mock_slo_tracker.record_measurement.side_effect = RuntimeError("SLO error")
        original_slo = tracker_module._slo_tracker
        tracker_module._slo_tracker = mock_slo_tracker

        try:
            tracker = DatabaseTracker(
                database_name=f"test_{uuid.uuid4().hex[:8]}",
                default_slo_name="query_slo",
            )
            tracker.record_query(
                operation="SELECT",
                duration_seconds=0.05,
                success=True,
            )
        finally:
            tracker_module._slo_tracker = original_slo

    def test_record_query_no_slo(self):
        """Test record_query without SLO tracking (no slo set)."""
        tracker = DatabaseTracker(database_name=f"test_{uuid.uuid4().hex[:8]}")
        tracker.record_query(
            operation="DELETE",
            duration_seconds=0.01,
            success=True,
        )

    def test_record_query_with_slo_but_tracker_returns_none(self):
        """Test record_query when slo is set but _get_slo_tracker returns None (line 325)."""
        original_slo = tracker_module._slo_tracker
        tracker_module._slo_tracker = None

        try:
            with patch("obskit.integrations.db.tracker._get_slo_tracker", return_value=None):
                tracker = DatabaseTracker(
                    database_name=f"test_{uuid.uuid4().hex[:8]}",
                    default_slo_name="query_slo",
                )
                tracker.record_query(
                    operation="SELECT",
                    duration_seconds=0.05,
                    success=True,
                )
        finally:
            tracker_module._slo_tracker = original_slo
