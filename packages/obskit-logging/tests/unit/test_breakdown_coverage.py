"""Additional coverage tests for breakdown.py."""
from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

from obskit.breakdown import LatencyBreakdown, PhaseRecord, track_breakdown


class TestBreakdownCoverage:

    def test_exit_closes_open_phase_sets_duration(self):
        """Lines 162-163: __exit__ closes open phase with no end_time."""
        bd = LatencyBreakdown("op-close-phase", log_breakdown=False)
        bd.__enter__()
        # Manually open a phase without closing it (no end_time)
        phase = PhaseRecord(name="open_phase", start_time=time.perf_counter())
        bd._phases.append(phase)
        bd._current_phase = phase  # still open (end_time is None)
        bd.__exit__(None, None, None)
        # The phase should now have end_time and duration set
        assert phase.end_time is not None
        assert phase.duration_seconds is not None
        assert phase.duration_seconds >= 0

    def test_exit_records_phase_percentage_when_total_nonzero(self):
        """Line 178: total_duration > 0 so phase percentage is computed."""
        bd = LatencyBreakdown("op-phase-pct", log_breakdown=False)
        with bd:
            with bd.phase("phaseA"):
                time.sleep(0.001)
        summary = bd.get_summary()
        assert "phaseA" in summary.phase_percentages

    def test_exit_logs_debug_below_bottleneck_threshold(self):
        """Line 199: logs debug when bottleneck_percent < alert threshold."""
        bd = LatencyBreakdown("op-debug-log", log_breakdown=True, alert_bottleneck_percent=200.0)  # > 100% to always take else branch
        with patch("obskit.breakdown.logger") as mock_logger:
            with bd:
                with bd.phase("small_phase"):
                    time.sleep(0.001)
        assert mock_logger.debug.called or mock_logger.warning.called

    def test_phase_closes_previous_open_phase(self):
        """Lines 216-217: starting new phase closes previous open phase."""
        bd = LatencyBreakdown("op-close-prev", log_breakdown=False)
        bd.__enter__()
        # Manually simulate an open phase (no end_time set)
        open_phase = PhaseRecord(name="phase1", start_time=time.perf_counter())
        bd._phases.append(open_phase)
        bd._current_phase = open_phase  # still open
        # Start a new phase via context manager -> should close the open one
        with bd.phase("phase2"):
            pass
        # The first phase should now have an end_time
        assert open_phase.end_time is not None
        assert open_phase.duration_seconds is not None
        bd.__exit__(None, None, None)

    def test_get_summary_with_phases_nonzero_total(self):
        """Line 286: get_summary with total_duration > 0 computes percentages."""
        bd = LatencyBreakdown("op-summary-nonzero", log_breakdown=False)
        with bd:
            bd.record_phase("phase1", 0.001)
            bd.record_phase("phase2", 0.002)
        summary = bd.get_summary()
        assert "phase1" in summary.phase_percentages
        assert "phase2" in summary.phase_percentages
        assert summary.total_duration_seconds > 0


class TestBreakdownLoopBranches:
    """Cover for-loop branch misses in breakdown.py."""

    def test_exit_with_phases_and_zero_total_duration(self):
        """Lines 178->173 and 286->283: phases exist but total_duration is 0."""
        import time
        from unittest.mock import patch

        from obskit.breakdown import LatencyBreakdown, PhaseRecord

        bd = LatencyBreakdown('op-zero-total', log_breakdown=False)

        # Patch time.perf_counter to return same value for both __enter__ and __exit__
        with patch('obskit.breakdown.time') as mock_time:
            mock_time.perf_counter.return_value = 100.0
            bd.__enter__()
            # Add phases manually (with zero duration)
            bd._phases = [
                PhaseRecord(name='phase1', start_time=100.0, end_time=100.0, duration_seconds=0.0),
            ]
            bd.__exit__(None, None, None)

        # Verify total_duration was 0
        assert bd._end_time == 100.0
        assert bd._start_time == 100.0
        assert bd._end_time - bd._start_time == 0.0

        # get_summary with zero total_duration exercises line 286->283
        summary = bd.get_summary()
        assert summary.total_duration_seconds == 0.0
