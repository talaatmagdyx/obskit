"""
Extended tests for obskit.slo.tracker module — SLOTracker gaps.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta

import pytest

from obskit.slo.tracker import (
    SLOTracker,
    get_slo_tracker,
    reset_slo_tracker,
    track_slo,
    with_slo_tracking,
    with_slo_tracking_sync,
)
from obskit.slo.types import SLOStatus, SLOTarget, SLOType


# =============================================================================
# SLOTracker Extended Tests
# =============================================================================


class TestSLOTrackerExtended:
    def setup_method(self):
        self.tracker = SLOTracker()

    def test_get_all_status_empty(self):
        result = self.tracker.get_all_status()
        assert result == {}

    def test_to_dict_empty(self):
        result = self.tracker.to_dict()
        assert result == {}

    def test_get_all_status_multiple_slos(self):
        self.tracker.register_slo("slo1", SLOType.AVAILABILITY, 0.99)
        self.tracker.register_slo("slo2", SLOType.ERROR_RATE, 0.01)
        self.tracker.record_measurement("slo1", 1.0, success=True)
        self.tracker.record_measurement("slo2", 0.0, success=True)
        result = self.tracker.get_all_status()
        assert "slo1" in result
        assert "slo2" in result

    def test_to_dict_with_slos(self):
        self.tracker.register_slo("dict_slo", SLOType.AVAILABILITY, 0.99)
        self.tracker.record_measurement("dict_slo", 1.0, success=True)
        d = self.tracker.to_dict()
        assert "dict_slo" in d
        assert "current_value" in d["dict_slo"]

    def test_error_rate_slo_compliance(self):
        self.tracker.register_slo("error_slo", SLOType.ERROR_RATE, 0.01)
        # Record 1% error rate (compliant)
        for _ in range(99):
            self.tracker.record_measurement("error_slo", 0.0, success=True)
        self.tracker.record_measurement("error_slo", 0.0, success=False)
        status = self.tracker.get_status("error_slo")
        assert status.compliance is True

    def test_error_rate_slo_non_compliance(self):
        self.tracker.register_slo("error_slo2", SLOType.ERROR_RATE, 0.01)
        # Record 10% error rate (non-compliant)
        for _ in range(90):
            self.tracker.record_measurement("error_slo2", 0.0, success=True)
        for _ in range(10):
            self.tracker.record_measurement("error_slo2", 0.0, success=False)
        status = self.tracker.get_status("error_slo2")
        assert status.compliance is False

    def test_latency_slo_with_percentile(self):
        self.tracker.register_slo("latency_slo", SLOType.LATENCY, 0.5, percentile=95)
        # All latencies under 500ms
        for i in range(100):
            self.tracker.record_measurement("latency_slo", 0.1 + i * 0.001, success=True)
        status = self.tracker.get_status("latency_slo")
        assert status is not None
        assert status.current_value > 0

    def test_latency_slo_compliant(self):
        self.tracker.register_slo("latency_ok", SLOType.LATENCY, 1.0, percentile=95)
        # All latencies under 1 second
        for _ in range(100):
            self.tracker.record_measurement("latency_ok", 0.1, success=True)
        status = self.tracker.get_status("latency_ok")
        assert status.compliance is True

    def test_latency_slo_non_compliant(self):
        self.tracker.register_slo("latency_fail", SLOType.LATENCY, 0.05, percentile=95)
        # All latencies 100ms (above 50ms threshold)
        for _ in range(100):
            self.tracker.record_measurement("latency_fail", 0.1, success=True)
        status = self.tracker.get_status("latency_fail")
        assert status.compliance is False

    def test_throughput_slo_single_measurement(self):
        self.tracker.register_slo("throughput_slo", SLOType.THROUGHPUT, 10.0)
        self.tracker.record_measurement("throughput_slo", 1.0, success=True)
        status = self.tracker.get_status("throughput_slo")
        assert status is not None
        # Single measurement returns 0 throughput
        assert status.current_value == 0.0

    def test_throughput_slo_multiple_measurements(self):
        self.tracker.register_slo("throughput_multi", SLOType.THROUGHPUT, 1.0)
        # Record several measurements with small time span
        for _ in range(5):
            self.tracker.record_measurement("throughput_multi", 1.0, success=True)
        status = self.tracker.get_status("throughput_multi")
        # Should have calculated throughput
        assert status is not None

    def test_window_eviction(self):
        """Test that old measurements are evicted."""
        tracker = SLOTracker()
        tracker.register_slo("window_test", SLOType.AVAILABILITY, 0.99, window_seconds=1)
        # Record measurements
        tracker.record_measurement("window_test", 1.0, success=True)
        # Manually age the measurement
        tracker._measurements["window_test"][0].timestamp = datetime.now() - timedelta(seconds=10)
        # New recording triggers eviction
        tracker.record_measurement("window_test", 1.0, success=True)
        # The old measurement should be evicted
        assert len(tracker._measurements["window_test"]) == 1

    def test_record_measurement_unregistered_slo(self):
        """Recording to unregistered SLO should not raise."""
        self.tracker.record_measurement("nonexistent_slo", 1.0, success=True)
        # No exception raised

    def test_get_status_returns_none_for_unknown(self):
        status = self.tracker.get_status("nonexistent")
        assert status is None

    def test_error_budget_calculation_availability(self):
        self.tracker.register_slo("budget_avail", SLOType.AVAILABILITY, 0.99)
        # Perfect availability
        for _ in range(100):
            self.tracker.record_measurement("budget_avail", 1.0, success=True)
        status = self.tracker.get_status("budget_avail")
        # Error budget = 1 - target = 0.01
        # Used = 1 - current = 0
        assert status.error_budget_remaining == pytest.approx(0.01, abs=0.001)

    def test_error_budget_calculation_partial_use(self):
        self.tracker.register_slo("budget_partial", SLOType.AVAILABILITY, 0.99)
        for _ in range(95):
            self.tracker.record_measurement("budget_partial", 1.0, success=True)
        for _ in range(5):
            self.tracker.record_measurement("budget_partial", 1.0, success=False)
        status = self.tracker.get_status("budget_partial")
        assert status.error_budget_remaining >= 0.0

    def test_error_budget_calculation_error_rate(self):
        self.tracker.register_slo("budget_err", SLOType.ERROR_RATE, 0.05)
        # 2% error rate (under budget of 5%)
        for _ in range(98):
            self.tracker.record_measurement("budget_err", 0.0, success=True)
        for _ in range(2):
            self.tracker.record_measurement("budget_err", 0.0, success=False)
        status = self.tracker.get_status("budget_err")
        assert status.error_budget_remaining > 0.0
        assert status.error_budget_burn_rate < 1.0

    def test_empty_status_defaults(self):
        """Test SLO status with no measurements."""
        self.tracker.register_slo("empty_slo", SLOType.AVAILABILITY, 0.99)
        status = self.tracker.get_status("empty_slo")
        assert status.current_value == 1.0  # Default for availability
        assert status.compliance is True
        assert status.measurement_count == 0


# =============================================================================
# with_slo_tracking Tests
# =============================================================================


class TestWithSloTracking:
    def setup_method(self):
        reset_slo_tracker()

    def teardown_method(self):
        reset_slo_tracker()

    def test_sync_function_success(self):
        tracker = get_slo_tracker()
        tracker.register_slo("test_avail", SLOType.AVAILABILITY, 0.99)

        @with_slo_tracking("test_avail")
        def my_func():
            return "ok"

        result = my_func()
        assert result == "ok"

        status = tracker.get_status("test_avail")
        # After 1 success, should have 1 measurement
        assert status.measurement_count == 1

    def test_sync_function_failure_tracked(self):
        reset_slo_tracker()
        tracker = get_slo_tracker()
        tracker.register_slo("test_avail_fail", SLOType.AVAILABILITY, 0.99)

        @with_slo_tracking("test_avail_fail")
        def failing_func():
            raise ValueError("test error")

        with pytest.raises(ValueError):
            failing_func()

        status = tracker.get_status("test_avail_fail")
        assert status.measurement_count == 1
        assert status.current_value < 1.0  # Should reflect failure

    @pytest.mark.asyncio
    async def test_async_function_success(self):
        reset_slo_tracker()
        tracker = get_slo_tracker()
        tracker.register_slo("async_avail", SLOType.AVAILABILITY, 0.99)

        @with_slo_tracking("async_avail")
        async def async_func():
            return "async_ok"

        result = await async_func()
        assert result == "async_ok"

        status = tracker.get_status("async_avail")
        assert status.measurement_count == 1

    @pytest.mark.asyncio
    async def test_async_function_failure(self):
        reset_slo_tracker()
        tracker = get_slo_tracker()
        tracker.register_slo("async_fail_slo", SLOType.AVAILABILITY, 0.99)

        @with_slo_tracking("async_fail_slo")
        async def failing_async():
            raise RuntimeError("async error")

        with pytest.raises(RuntimeError):
            await failing_async()

        status = tracker.get_status("async_fail_slo")
        assert status.measurement_count == 1

    def test_with_latency_tracking(self):
        reset_slo_tracker()
        tracker = get_slo_tracker()
        tracker.register_slo("latency_slo_track", SLOType.AVAILABILITY, 0.99)
        tracker.register_slo("latency_slo_track_latency", SLOType.LATENCY, 1.0, percentile=95)

        @with_slo_tracking("latency_slo_track", track_latency=True)
        def func_with_latency():
            return "ok"

        func_with_latency()
        status = tracker.get_status("latency_slo_track_latency")
        assert status is not None
        assert status.measurement_count == 1

    def test_custom_latency_slo_name(self):
        reset_slo_tracker()
        tracker = get_slo_tracker()
        tracker.register_slo("my_slo", SLOType.AVAILABILITY, 0.99)
        tracker.register_slo("custom_lat", SLOType.LATENCY, 1.0, percentile=95)

        @with_slo_tracking("my_slo", track_latency=True, latency_slo_name="custom_lat")
        def func():
            return "result"

        func()
        status = tracker.get_status("custom_lat")
        assert status is not None

    @pytest.mark.asyncio
    async def test_async_with_latency_tracking(self):
        reset_slo_tracker()
        tracker = get_slo_tracker()
        tracker.register_slo("async_lat_slo", SLOType.AVAILABILITY, 0.99)
        tracker.register_slo("async_lat_slo_latency", SLOType.LATENCY, 1.0, percentile=95)

        @with_slo_tracking("async_lat_slo", track_latency=True)
        async def async_func():
            return "ok"

        await async_func()
        status = tracker.get_status("async_lat_slo_latency")
        assert status is not None


# =============================================================================
# with_slo_tracking_sync Tests
# =============================================================================


class TestWithSloTrackingSync:
    def setup_method(self):
        reset_slo_tracker()

    def teardown_method(self):
        reset_slo_tracker()

    def test_sync_function_success(self):
        tracker = get_slo_tracker()
        tracker.register_slo("sync_dec_slo", SLOType.AVAILABILITY, 0.99)

        @with_slo_tracking_sync("sync_dec_slo")
        def my_func():
            return "sync_result"

        result = my_func()
        assert result == "sync_result"
        status = tracker.get_status("sync_dec_slo")
        assert status.measurement_count == 1

    def test_sync_function_failure(self):
        tracker = get_slo_tracker()
        tracker.register_slo("sync_fail_dec", SLOType.AVAILABILITY, 0.99)

        @with_slo_tracking_sync("sync_fail_dec")
        def failing_func():
            raise IOError("IO error")

        with pytest.raises(IOError):
            failing_func()

        status = tracker.get_status("sync_fail_dec")
        assert status.measurement_count == 1

    def test_with_latency_tracking(self):
        tracker = get_slo_tracker()
        tracker.register_slo("sync_lat_dec", SLOType.AVAILABILITY, 0.99)
        tracker.register_slo("sync_lat_dec_latency", SLOType.LATENCY, 1.0, percentile=95)

        @with_slo_tracking_sync("sync_lat_dec", track_latency=True)
        def func():
            return "ok"

        func()
        status = tracker.get_status("sync_lat_dec_latency")
        assert status is not None

    def test_custom_latency_name(self):
        tracker = get_slo_tracker()
        tracker.register_slo("custom_sync", SLOType.AVAILABILITY, 0.99)
        tracker.register_slo("my_custom_latency", SLOType.LATENCY, 1.0, percentile=95)

        @with_slo_tracking_sync("custom_sync", track_latency=True, latency_slo_name="my_custom_latency")
        def func():
            return "ok"

        func()
        status = tracker.get_status("my_custom_latency")
        assert status is not None


# =============================================================================
# Global Functions Tests
# =============================================================================


class TestGlobalTrackerFunctions:
    def setup_method(self):
        reset_slo_tracker()

    def teardown_method(self):
        reset_slo_tracker()

    def test_get_slo_tracker_returns_instance(self):
        tracker = get_slo_tracker()
        assert isinstance(tracker, SLOTracker)

    def test_get_slo_tracker_singleton(self):
        t1 = get_slo_tracker()
        t2 = get_slo_tracker()
        assert t1 is t2

    def test_reset_slo_tracker(self):
        t1 = get_slo_tracker()
        reset_slo_tracker()
        t2 = get_slo_tracker()
        assert t1 is not t2

    def test_track_slo_global(self):
        tracker = get_slo_tracker()
        tracker.register_slo("global_track_slo", SLOType.AVAILABILITY, 0.99)
        track_slo("global_track_slo", value=1.0, success=True)
        status = tracker.get_status("global_track_slo")
        assert status.measurement_count == 1
