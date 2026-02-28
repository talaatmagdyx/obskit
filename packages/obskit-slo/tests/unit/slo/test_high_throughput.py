"""Tests for obskit.slo.high_throughput.HighThroughputSLOTracker."""

import threading
from datetime import datetime, timedelta

from obskit.slo.high_throughput import HighThroughputSLOTracker, measurements_in_window
from obskit.slo.types import SLOMeasurement, SLOType


class TestHighThroughputSLOTrackerRegistration:
    """Tests for SLO registration."""

    def test_register_and_get_status_empty(self):
        """Registered SLO with no measurements returns compliance=True."""
        tracker = HighThroughputSLOTracker()
        tracker.register_slo("avail", SLOType.AVAILABILITY, 0.999)
        status = tracker.get_status("avail")
        assert status is not None
        assert status.compliance is True
        assert status.measurement_count == 0

    def test_get_status_unregistered_returns_none(self):
        tracker = HighThroughputSLOTracker()
        assert tracker.get_status("nonexistent") is None

    def test_register_overwrites_existing(self):
        tracker = HighThroughputSLOTracker()
        tracker.register_slo("slo", SLOType.AVAILABILITY, 0.99)
        tracker.register_slo("slo", SLOType.AVAILABILITY, 0.95)
        status = tracker.get_status("slo")
        assert status.target.target_value == 0.95


class TestHighThroughputSLOTrackerRecording:
    """Tests for record_measurement hot path."""

    def test_record_single_success(self):
        tracker = HighThroughputSLOTracker()
        tracker.register_slo("avail", SLOType.AVAILABILITY, 0.999)
        tracker.record_measurement("avail", 1.0, success=True)
        status = tracker.get_status("avail")
        assert status.measurement_count == 1
        assert status.current_value == 1.0

    def test_record_all_failures(self):
        tracker = HighThroughputSLOTracker()
        tracker.register_slo("avail", SLOType.AVAILABILITY, 0.999)
        for _ in range(10):
            tracker.record_measurement("avail", 1.0, success=False)
        status = tracker.get_status("avail")
        assert status.current_value == 0.0
        assert status.compliance is False

    def test_record_mixed_availability(self):
        tracker = HighThroughputSLOTracker()
        tracker.register_slo("avail", SLOType.AVAILABILITY, 0.5)
        for _ in range(3):
            tracker.record_measurement("avail", 1.0, success=True)
        for _ in range(7):
            tracker.record_measurement("avail", 1.0, success=False)
        status = tracker.get_status("avail")
        assert abs(status.current_value - 0.3) < 1e-9

    def test_record_unregistered_slo_does_not_raise(self):
        """Recording to an unknown SLO silently creates a deque entry."""
        tracker = HighThroughputSLOTracker()
        tracker.record_measurement("unknown", 1.0, success=True)  # should not raise

    def test_window_eviction_via_maxlen(self):
        """Measurements beyond maxlen are dropped by the deque."""
        tracker = HighThroughputSLOTracker(max_measurements_per_thread=5)
        tracker.register_slo("avail", SLOType.AVAILABILITY, 0.999, window_seconds=86400)
        for _ in range(10):
            tracker.record_measurement("avail", 1.0, success=True)
        status = tracker.get_status("avail")
        # maxlen=5 → at most 5 measurements retained
        assert status.measurement_count <= 5

    def test_time_window_filter(self):
        """Old measurements (outside the window) are excluded from status."""
        tracker = HighThroughputSLOTracker()
        tracker.register_slo("avail", SLOType.AVAILABILITY, 0.999, window_seconds=1)

        # Register in local buffer directly with old timestamp
        local = tracker._get_local()
        local.deques.setdefault("avail", __import__("collections").deque(maxlen=50_000))
        old_ts = datetime.now() - timedelta(seconds=10)
        local.deques["avail"].appendleft(
            SLOMeasurement(timestamp=old_ts, value=1.0, success=False)
        )
        # Fresh success
        tracker.record_measurement("avail", 1.0, success=True)

        status = tracker.get_status("avail")
        # Only the recent success should be in window
        assert status.current_value == 1.0


class TestHighThroughputSLOTrackerLatency:
    """Tests for LATENCY SLO type."""

    def test_latency_percentile(self):
        tracker = HighThroughputSLOTracker()
        tracker.register_slo("latency", SLOType.LATENCY, 0.200, percentile=99)
        # 100 measurements: 99 fast, 1 slow
        for _ in range(99):
            tracker.record_measurement("latency", 0.05, success=True)
        tracker.record_measurement("latency", 0.500, success=True)
        status = tracker.get_status("latency")
        # p99 should be ~0.500 (within last 1 % of 100 items)
        assert status.current_value <= 0.500
        assert status.current_value >= 0.05

    def test_latency_compliance_pass(self):
        tracker = HighThroughputSLOTracker()
        tracker.register_slo("latency", SLOType.LATENCY, 0.200, percentile=99)
        for _ in range(100):
            tracker.record_measurement("latency", 0.1, success=True)
        assert tracker.get_status("latency").compliance is True

    def test_latency_compliance_fail(self):
        tracker = HighThroughputSLOTracker()
        tracker.register_slo("latency", SLOType.LATENCY, 0.100, percentile=50)
        for _ in range(100):
            tracker.record_measurement("latency", 0.5, success=True)
        assert tracker.get_status("latency").compliance is False


class TestHighThroughputSLOTrackerConcurrency:
    """Concurrency tests — verify no data corruption under parallel writes."""

    def test_concurrent_record_measurement(self):
        tracker = HighThroughputSLOTracker()
        tracker.register_slo("avail", SLOType.AVAILABILITY, 0.99)

        n_threads = 16
        per_thread = 200

        def worker():
            for _ in range(per_thread):
                tracker.record_measurement("avail", 1.0, success=True)

        threads = [threading.Thread(target=worker) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        status = tracker.get_status("avail")
        assert status is not None
        # All measurements should be successes
        assert status.current_value == 1.0

    def test_get_all_status_returns_all_registered(self):
        tracker = HighThroughputSLOTracker()
        tracker.register_slo("a", SLOType.AVAILABILITY, 0.99)
        tracker.register_slo("b", SLOType.ERROR_RATE, 0.01)
        tracker.record_measurement("a", 1.0, success=True)
        tracker.record_measurement("b", 1.0, success=False)
        all_status = tracker.get_all_status()
        assert set(all_status.keys()) == {"a", "b"}

    def test_to_dict_returns_serialisable_output(self):
        tracker = HighThroughputSLOTracker()
        tracker.register_slo("avail", SLOType.AVAILABILITY, 0.999)
        tracker.record_measurement("avail", 1.0, success=True)
        d = tracker.to_dict()
        assert "avail" in d
        assert isinstance(d["avail"], dict)


class TestMeasurementsInWindow:
    """Tests for the measurements_in_window binary-search helper."""

    def _make_measurement(self, offset_s: float) -> SLOMeasurement:
        return SLOMeasurement(
            timestamp=datetime.now() + timedelta(seconds=offset_s),
            value=1.0,
            success=True,
        )

    def test_all_in_window(self):
        measurements = [self._make_measurement(i) for i in range(5)]
        measurements.sort(key=lambda m: m.timestamp)
        window_start = datetime.now() - timedelta(seconds=10)
        result = measurements_in_window(measurements, window_start)
        assert len(result) == 5

    def test_none_in_window(self):
        measurements = [self._make_measurement(-100 + i) for i in range(5)]
        measurements.sort(key=lambda m: m.timestamp)
        window_start = datetime.now()  # all are in the past
        result = measurements_in_window(measurements, window_start)
        assert len(result) == 0

    def test_partial_window(self):
        measurements = (
            [self._make_measurement(-10 + i) for i in range(3)]  # old
            + [self._make_measurement(i) for i in range(3)]       # recent
        )
        measurements.sort(key=lambda m: m.timestamp)
        window_start = datetime.now() - timedelta(seconds=1)
        result = measurements_in_window(measurements, window_start)
        # Only the recent ones should be included
        assert 0 < len(result) <= 3
