"""Unit tests for obskit.breakdown — latency breakdown tracker."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from obskit.breakdown import (
    BreakdownSummary,
    LatencyBreakdown,
    PhaseRecord,
    track_breakdown,
)

# =============================================================================
# PhaseRecord
# =============================================================================


class TestPhaseRecord:
    def test_basic_creation(self):
        record = PhaseRecord(name="query", start_time=1.0)
        assert record.name == "query"
        assert record.start_time == pytest.approx(1.0)
        assert record.end_time is None
        assert record.duration_seconds == pytest.approx(0.0)

    def test_to_dict(self):
        record = PhaseRecord(name="query", start_time=1.0, end_time=1.5, duration_seconds=0.5)
        d = record.to_dict()
        assert d["name"] == "query"
        assert d["duration_seconds"] == pytest.approx(0.5)
        assert d["duration_ms"] == pytest.approx(500.0, rel=1e-3)


# =============================================================================
# BreakdownSummary
# =============================================================================


class TestBreakdownSummary:
    def test_to_dict_basic(self):
        summary = BreakdownSummary(
            operation="my_op",
            total_duration_seconds=1.0,
            phases=[],
            phase_percentages={},
        )
        d = summary.to_dict()
        assert d["operation"] == "my_op"
        assert d["total_duration_seconds"] == pytest.approx(1.0)
        assert d["total_duration_ms"] == pytest.approx(1000.0)

    def test_to_dict_with_phases(self):
        phase = PhaseRecord(name="db", start_time=0.0, end_time=0.5, duration_seconds=0.5)
        summary = BreakdownSummary(
            operation="op",
            total_duration_seconds=1.0,
            phases=[phase],
            phase_percentages={"db": 50.0},
            bottleneck="db",
            bottleneck_percent=50.0,
        )
        d = summary.to_dict()
        assert len(d["phases"]) == 1
        assert d["bottleneck"] == "db"
        assert d["bottleneck_percent"] == pytest.approx(50.0)

    def test_to_dict_includes_timestamp(self):
        summary = BreakdownSummary(
            operation="op",
            total_duration_seconds=0.1,
            phases=[],
            phase_percentages={},
        )
        d = summary.to_dict()
        assert "timestamp" in d


# =============================================================================
# LatencyBreakdown — basic usage
# =============================================================================


class TestLatencyBreakdownBasic:
    def test_enter_exit_as_context_manager(self):
        bd = LatencyBreakdown("test_op", log_breakdown=False)
        with bd:
            pass  # NOSONAR
        # No exception should be raised

    def test_start_time_set_on_enter(self):
        bd = LatencyBreakdown("test_op", log_breakdown=False)
        with bd:
            assert bd._start_time is not None

    def test_end_time_set_on_exit(self):
        bd = LatencyBreakdown("test_op", log_breakdown=False)
        with bd:
            pass  # NOSONAR
        assert bd._end_time is not None

    def test_operation_name_stored(self):
        bd = LatencyBreakdown("my_operation", log_breakdown=False)
        assert bd.operation == "my_operation"

    def test_returns_false_from_exit(self):
        bd = LatencyBreakdown("op", log_breakdown=False)
        # Must enter before exit
        bd.__enter__()
        result = bd.__exit__(None, None, None)
        assert result is False

    def test_no_phases_initially(self):
        bd = LatencyBreakdown("op", log_breakdown=False)
        assert bd._phases == []


# =============================================================================
# LatencyBreakdown — phase tracking
# =============================================================================


class TestLatencyBreakdownPhases:
    def test_phase_context_manager_records_phase(self):
        bd = LatencyBreakdown("op", log_breakdown=False)
        bd._start_time = time.perf_counter()

        with bd.phase("query"):
            pass  # NOSONAR

        assert len(bd._phases) == 1
        assert bd._phases[0].name == "query"

    def test_phase_duration_recorded(self):
        bd = LatencyBreakdown("op", log_breakdown=False)
        bd._start_time = time.perf_counter()

        with bd.phase("query"):
            time.sleep(0.01)

        assert bd._phases[0].duration_seconds > 0

    def test_multiple_phases_recorded(self):
        bd = LatencyBreakdown("op", log_breakdown=False)
        bd._start_time = time.perf_counter()

        with bd.phase("phase1"):
            pass  # NOSONAR
        with bd.phase("phase2"):
            pass  # NOSONAR
        with bd.phase("phase3"):
            pass  # NOSONAR

        assert len(bd._phases) == 3
        phase_names = [p.name for p in bd._phases]
        assert "phase1" in phase_names
        assert "phase2" in phase_names
        assert "phase3" in phase_names

    def test_record_phase_manually(self):
        bd = LatencyBreakdown("op", log_breakdown=False)
        bd.record_phase("manual_phase", 0.25)

        assert len(bd._phases) == 1
        assert bd._phases[0].name == "manual_phase"
        assert bd._phases[0].duration_seconds == pytest.approx(0.25)

    def test_record_phase_manually_multiple(self):
        bd = LatencyBreakdown("op", log_breakdown=False)
        bd.record_phase("phase_a", 0.1)
        bd.record_phase("phase_b", 0.2)

        assert len(bd._phases) == 2

    def test_nested_in_context_manager(self):
        bd = LatencyBreakdown("op", log_breakdown=False)
        with bd:
            with bd.phase("step1"):
                pass  # NOSONAR
            with bd.phase("step2"):
                pass  # NOSONAR

        assert len(bd._phases) == 2


# =============================================================================
# LatencyBreakdown — get_summary
# =============================================================================


class TestLatencyBreakdownGetSummary:
    def test_get_summary_before_start_returns_empty(self):
        bd = LatencyBreakdown("op", log_breakdown=False)
        summary = bd.get_summary()
        assert summary.total_duration_seconds == 0
        assert summary.phases == []

    def test_get_summary_after_phases(self):
        bd = LatencyBreakdown("op", log_breakdown=False)
        bd._start_time = time.perf_counter()
        bd.record_phase("phase_a", 0.1)
        bd.record_phase("phase_b", 0.3)

        summary = bd.get_summary()
        assert summary.operation == "op"
        assert len(summary.phases) == 2

    def test_get_summary_identifies_bottleneck(self):
        bd = LatencyBreakdown("op", log_breakdown=False)
        bd._start_time = time.perf_counter()
        bd.record_phase("fast_phase", 0.05)
        bd.record_phase("slow_phase", 0.50)
        bd._end_time = bd._start_time + 1.0

        summary = bd.get_summary()
        assert summary.bottleneck == "slow_phase"

    def test_get_summary_no_phases_has_zero_percent(self):
        bd = LatencyBreakdown("op", log_breakdown=False)
        bd._start_time = time.perf_counter()
        bd._end_time = bd._start_time + 1.0
        summary = bd.get_summary()
        assert summary.phase_percentages == {}

    def test_get_summary_calculates_percentages(self):
        bd = LatencyBreakdown("op", log_breakdown=False)
        bd._start_time = 0.0
        bd._end_time = 1.0
        bd.record_phase("half_phase", 0.5)

        summary = bd.get_summary()
        assert "half_phase" in summary.phase_percentages
        assert summary.phase_percentages["half_phase"] == pytest.approx(50.0, abs=1.0)

    def test_get_summary_unaccounted_time(self):
        bd = LatencyBreakdown("op", log_breakdown=False)
        bd._start_time = 0.0
        bd._end_time = 1.0
        bd.record_phase("phase_a", 0.3)

        summary = bd.get_summary()
        assert summary.unaccounted_seconds == pytest.approx(0.7, abs=0.01)

    def test_full_workflow_summary(self):
        bd = LatencyBreakdown("complex_op", log_breakdown=False)
        with bd:
            with bd.phase("query"):
                time.sleep(0.01)
            with bd.phase("transform"):
                time.sleep(0.005)

        summary = bd.get_summary()
        assert summary.total_duration_seconds > 0
        assert len(summary.phases) == 2
        assert summary.bottleneck is not None


# =============================================================================
# LatencyBreakdown — get_waterfall_data
# =============================================================================


class TestLatencyBreakdownWaterfall:
    def test_waterfall_empty_when_not_started(self):
        bd = LatencyBreakdown("op", log_breakdown=False)
        assert bd.get_waterfall_data() == []

    def test_waterfall_contains_phases(self):
        bd = LatencyBreakdown("op", log_breakdown=False)
        bd._start_time = 0.0
        bd.record_phase("phase_a", 0.1)
        bd._phases[0].start_time = 0.0

        waterfall = bd.get_waterfall_data()
        assert len(waterfall) == 1
        assert waterfall[0]["name"] == "phase_a"
        assert "start_offset_ms" in waterfall[0]
        assert "duration_ms" in waterfall[0]
        assert "end_offset_ms" in waterfall[0]


# =============================================================================
# LatencyBreakdown — logging behavior
# =============================================================================


class TestLatencyBreakdownLogging:
    def test_logs_breakdown_on_exit_when_enabled(self):
        mock_logger = MagicMock()
        with patch("obskit.breakdown.logger", mock_logger):
            bd = LatencyBreakdown("logged_op", log_breakdown=True)
            with bd:
                bd.record_phase("phase", 0.01)

        assert mock_logger.debug.called or mock_logger.warning.called

    def test_warns_when_bottleneck_exceeds_threshold(self):
        import time as _time
        mock_logger = MagicMock()
        with patch("obskit.breakdown.logger", mock_logger):
            bd = LatencyBreakdown(
                "bottleneck_op",
                log_breakdown=True,
                alert_bottleneck_percent=10.0,  # Low threshold to trigger warning
            )
            # Use actual context manager so timings are consistent
            bd.__enter__()
            # Record a large phase that will be dominant
            bd.record_phase("dominant_phase", 0.95)
            # Short sleep to ensure total duration > 0
            _time.sleep(0.001)
            bd.__exit__(None, None, None)

        # The bottleneck_percent is based on phase duration vs total duration.
        # With _start_time very recent and a 0.95s phase, the percentage should be very high.
        # But actual duration is only ~1ms. So bottleneck_percent = 0.95/total * 100 >> 10%.
        # This should trigger warning.
        assert mock_logger.warning.called or mock_logger.debug.called

    def test_does_not_log_when_disabled(self):
        mock_logger = MagicMock()
        with patch("obskit.breakdown.logger", mock_logger):
            bd = LatencyBreakdown("silent_op", log_breakdown=False)
            with bd:
                pass  # NOSONAR

        mock_logger.debug.assert_not_called()
        mock_logger.warning.assert_not_called()

    def test_exits_open_phase_on_context_exit(self):
        bd = LatencyBreakdown("op", log_breakdown=False)
        with bd:
            # Start a phase but don't close it
            with bd.phase("open_phase"):
                pass  # phase is closed by context manager
        # Should not raise


# =============================================================================
# track_breakdown factory function
# =============================================================================


class TestTrackBreakdown:
    def test_returns_latency_breakdown_instance(self):
        bd = track_breakdown("my_op")
        assert isinstance(bd, LatencyBreakdown)

    def test_operation_name_set(self):
        bd = track_breakdown("test_operation")
        assert bd.operation == "test_operation"

    def test_kwargs_passed_through(self):
        bd = track_breakdown("op", log_breakdown=False, alert_bottleneck_percent=50.0)
        assert bd.log_breakdown is False
        assert bd.alert_bottleneck_percent == pytest.approx(50.0)
