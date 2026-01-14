"""Tests for obskit.slo.tracker module."""

import pytest
from datetime import datetime, timedelta, UTC
from unittest.mock import patch

from obskit.slo.tracker import (
    SLOTracker,
    get_slo_tracker,
    track_slo,
    reset_slo_tracker,
)
from obskit.slo.types import SLOType, SLOMeasurement, SLOTarget, SLOStatus, ErrorBudget


class TestSLOTracker:
    """Tests for SLOTracker class."""

    def setup_method(self):
        """Reset state before each test."""
        reset_slo_tracker()

    def teardown_method(self):
        """Clean up after each test."""
        reset_slo_tracker()

    def test_init(self):
        """Test SLOTracker initialization."""
        tracker = SLOTracker()
        
        assert tracker._targets == {}
        assert tracker._measurements == {}

    def test_register_slo_availability(self):
        """Test registering an availability SLO."""
        tracker = SLOTracker()
        
        tracker.register_slo(
            name="api_availability",
            slo_type=SLOType.AVAILABILITY,
            target_value=0.999,
        )
        
        assert "api_availability" in tracker._targets
        assert tracker._targets["api_availability"].target_value == 0.999
        assert tracker._targets["api_availability"].slo_type == SLOType.AVAILABILITY

    def test_register_slo_latency(self):
        """Test registering a latency SLO."""
        tracker = SLOTracker()
        
        tracker.register_slo(
            name="api_latency",
            slo_type=SLOType.LATENCY,
            target_value=0.5,
            percentile=95,
        )
        
        assert "api_latency" in tracker._targets
        assert tracker._targets["api_latency"].percentile == 95

    def test_register_slo_error_rate(self):
        """Test registering an error rate SLO."""
        tracker = SLOTracker()
        
        tracker.register_slo(
            name="api_errors",
            slo_type=SLOType.ERROR_RATE,
            target_value=0.01,
        )
        
        assert "api_errors" in tracker._targets

    def test_register_slo_throughput(self):
        """Test registering a throughput SLO."""
        tracker = SLOTracker()
        
        tracker.register_slo(
            name="api_throughput",
            slo_type=SLOType.THROUGHPUT,
            target_value=100.0,
        )
        
        assert "api_throughput" in tracker._targets

    def test_record_measurement(self):
        """Test recording a measurement."""
        tracker = SLOTracker()
        tracker.register_slo(
            name="test_slo",
            slo_type=SLOType.AVAILABILITY,
            target_value=0.99,
        )
        
        tracker.record_measurement("test_slo", 1.0, success=True)
        
        assert len(tracker._measurements["test_slo"]) == 1
        assert tracker._measurements["test_slo"][0].success is True

    def test_record_measurement_unregistered(self):
        """Test recording measurement for unregistered SLO."""
        tracker = SLOTracker()
        
        # Should not raise, just log warning
        tracker.record_measurement("nonexistent", 1.0, success=True)

    def test_record_measurement_cleans_old(self):
        """Test that old measurements are cleaned."""
        tracker = SLOTracker()
        tracker.register_slo(
            name="test_slo",
            slo_type=SLOType.AVAILABILITY,
            target_value=0.99,
            window_seconds=60,  # 1 minute window
        )
        
        # Add an old measurement
        old_measurement = SLOMeasurement(
            timestamp=datetime.now() - timedelta(seconds=120),
            value=1.0,
            success=True,
        )
        tracker._measurements["test_slo"] = [old_measurement]
        
        # Record new measurement
        tracker.record_measurement("test_slo", 1.0, success=True)
        
        # Old measurement should be cleaned
        assert len(tracker._measurements["test_slo"]) == 1
        assert tracker._measurements["test_slo"][0].timestamp > datetime.now() - timedelta(seconds=61)

    def test_get_status_unregistered(self):
        """Test getting status for unregistered SLO."""
        tracker = SLOTracker()
        
        status = tracker.get_status("nonexistent")
        
        assert status is None

    def test_get_status_no_measurements(self):
        """Test getting status with no measurements."""
        tracker = SLOTracker()
        tracker.register_slo(
            name="test_slo",
            slo_type=SLOType.AVAILABILITY,
            target_value=0.99,
        )
        
        status = tracker.get_status("test_slo")
        
        assert status is not None
        assert status.current_value == 1.0
        assert status.compliance is True
        assert status.measurement_count == 0

    def test_get_status_availability_compliant(self):
        """Test availability SLO status when compliant."""
        tracker = SLOTracker()
        tracker.register_slo(
            name="test_slo",
            slo_type=SLOType.AVAILABILITY,
            target_value=0.99,
        )
        
        # Record 100% success
        for _ in range(100):
            tracker.record_measurement("test_slo", 1.0, success=True)
        
        status = tracker.get_status("test_slo")
        
        assert status.current_value == 1.0
        assert status.compliance is True

    def test_get_status_availability_non_compliant(self):
        """Test availability SLO status when non-compliant."""
        tracker = SLOTracker()
        tracker.register_slo(
            name="test_slo",
            slo_type=SLOType.AVAILABILITY,
            target_value=0.99,
        )
        
        # Record 90% success
        for _ in range(90):
            tracker.record_measurement("test_slo", 1.0, success=True)
        for _ in range(10):
            tracker.record_measurement("test_slo", 0.0, success=False)
        
        status = tracker.get_status("test_slo")
        
        assert status.current_value == 0.9
        assert status.compliance is False

    def test_get_status_error_rate_compliant(self):
        """Test error rate SLO status when compliant."""
        tracker = SLOTracker()
        tracker.register_slo(
            name="test_slo",
            slo_type=SLOType.ERROR_RATE,
            target_value=0.05,  # 5% max error rate
        )
        
        # Record 2% error rate
        for _ in range(98):
            tracker.record_measurement("test_slo", 1.0, success=True)
        for _ in range(2):
            tracker.record_measurement("test_slo", 0.0, success=False)
        
        status = tracker.get_status("test_slo")
        
        assert status.current_value == 0.02
        assert status.compliance is True

    def test_get_status_error_rate_non_compliant(self):
        """Test error rate SLO status when non-compliant."""
        tracker = SLOTracker()
        tracker.register_slo(
            name="test_slo",
            slo_type=SLOType.ERROR_RATE,
            target_value=0.01,  # 1% max error rate
        )
        
        # Record 10% error rate
        for _ in range(90):
            tracker.record_measurement("test_slo", 1.0, success=True)
        for _ in range(10):
            tracker.record_measurement("test_slo", 0.0, success=False)
        
        status = tracker.get_status("test_slo")
        
        assert status.current_value == 0.1
        assert status.compliance is False

    def test_get_status_latency(self):
        """Test latency SLO status."""
        tracker = SLOTracker()
        tracker.register_slo(
            name="test_slo",
            slo_type=SLOType.LATENCY,
            target_value=0.5,  # 500ms
            percentile=95,
        )
        
        # Record latencies
        for i in range(100):
            latency = 0.1 + (i * 0.005)  # 0.1 to 0.595
            tracker.record_measurement("test_slo", latency, success=True)
        
        status = tracker.get_status("test_slo")
        
        # P95 should be around 0.575
        assert status.current_value > 0.5
        assert status.current_value < 0.6

    def test_get_status_latency_compliant(self):
        """Test latency SLO compliant status."""
        tracker = SLOTracker()
        tracker.register_slo(
            name="test_slo",
            slo_type=SLOType.LATENCY,
            target_value=1.0,  # 1000ms
            percentile=95,
        )
        
        # Record fast latencies
        for _ in range(100):
            tracker.record_measurement("test_slo", 0.1, success=True)
        
        status = tracker.get_status("test_slo")
        
        assert status.compliance is True

    def test_get_status_throughput(self):
        """Test throughput SLO status."""
        tracker = SLOTracker()
        tracker.register_slo(
            name="test_slo",
            slo_type=SLOType.THROUGHPUT,
            target_value=10.0,  # 10 req/s
        )
        
        # Record measurements with timestamps (oldest first for proper throughput calculation)
        now = datetime.now()
        for i in range(10):
            m = SLOMeasurement(
                timestamp=now - timedelta(seconds=(10 - i) * 0.1),  # Oldest first
                value=1.0,
                success=True,
            )
            tracker._measurements["test_slo"].append(m)
        
        status = tracker.get_status("test_slo")
        
        # Should calculate throughput
        assert status.current_value > 0

    def test_get_status_throughput_single_measurement(self):
        """Test throughput with single measurement."""
        tracker = SLOTracker()
        tracker.register_slo(
            name="test_slo",
            slo_type=SLOType.THROUGHPUT,
            target_value=10.0,
        )
        
        tracker.record_measurement("test_slo", 1.0, success=True)
        
        status = tracker.get_status("test_slo")
        
        # With single measurement, throughput is 0
        assert status.current_value == 0.0

    def test_get_all_status(self):
        """Test getting status for all SLOs."""
        tracker = SLOTracker()
        tracker.register_slo("slo1", SLOType.AVAILABILITY, 0.99)
        tracker.register_slo("slo2", SLOType.ERROR_RATE, 0.01)
        
        all_status = tracker.get_all_status()
        
        assert "slo1" in all_status
        assert "slo2" in all_status

    def test_get_status_empty_measurements(self):
        """Test get_status with no measurements returns default value."""
        tracker = SLOTracker()
        tracker.register_slo("empty_slo", SLOType.AVAILABILITY, 0.99)
        
        # Get status without any measurements
        status = tracker.get_status("empty_slo")
        
        # For availability with no measurements, default is 1.0 (100%)
        assert status.current_value == 1.0
        assert status.measurement_count == 0

    def test_to_dict(self):
        """Test exporting to dictionary."""
        tracker = SLOTracker()
        tracker.register_slo("slo1", SLOType.AVAILABILITY, 0.99)
        
        result = tracker.to_dict()
        
        assert "slo1" in result
        assert isinstance(result["slo1"], dict)

    def test_error_budget_availability(self):
        """Test error budget calculation for availability."""
        tracker = SLOTracker()
        tracker.register_slo(
            name="test_slo",
            slo_type=SLOType.AVAILABILITY,
            target_value=0.99,  # 99% target, 1% budget
        )
        
        # Record 99.5% availability
        for _ in range(995):
            tracker.record_measurement("test_slo", 1.0, success=True)
        for _ in range(5):
            tracker.record_measurement("test_slo", 0.0, success=False)
        
        status = tracker.get_status("test_slo")
        
        # 0.5% used, 0.5% remaining of 1% budget
        assert status.error_budget_remaining > 0
        assert status.error_budget_burn_rate < 1.0

    def test_error_budget_error_rate(self):
        """Test error budget calculation for error rate."""
        tracker = SLOTracker()
        tracker.register_slo(
            name="test_slo",
            slo_type=SLOType.ERROR_RATE,
            target_value=0.05,  # 5% budget
        )
        
        # Record 2% error rate
        for _ in range(98):
            tracker.record_measurement("test_slo", 1.0, success=True)
        for _ in range(2):
            tracker.record_measurement("test_slo", 0.0, success=False)
        
        status = tracker.get_status("test_slo")
        
        # 2% used, 3% remaining of 5% budget
        assert status.error_budget_remaining > 0
        assert status.error_budget_burn_rate < 1.0


class TestGlobalFunctions:
    """Tests for global tracker functions."""

    def setup_method(self):
        """Reset state before each test."""
        reset_slo_tracker()

    def teardown_method(self):
        """Clean up after each test."""
        reset_slo_tracker()

    def test_get_slo_tracker_creates_instance(self):
        """Test get_slo_tracker creates instance."""
        tracker = get_slo_tracker()
        
        assert tracker is not None
        assert isinstance(tracker, SLOTracker)

    def test_get_slo_tracker_returns_same(self):
        """Test get_slo_tracker returns same instance."""
        tracker1 = get_slo_tracker()
        tracker2 = get_slo_tracker()
        
        assert tracker1 is tracker2

    def test_track_slo(self):
        """Test track_slo function."""
        tracker = get_slo_tracker()
        tracker.register_slo("test_slo", SLOType.AVAILABILITY, 0.99)
        
        track_slo("test_slo", 1.0, success=True)
        
        assert len(tracker._measurements["test_slo"]) == 1

    def test_reset_slo_tracker(self):
        """Test reset_slo_tracker clears global instance."""
        tracker1 = get_slo_tracker()
        
        reset_slo_tracker()
        
        tracker2 = get_slo_tracker()
        
        assert tracker1 is not tracker2


class TestSLOTypes:
    """Tests for SLO type classes."""

    def test_slo_target_latency_requires_percentile(self):
        """Test latency SLO requires percentile."""
        with pytest.raises(ValueError, match="Latency SLO requires percentile"):
            SLOTarget(
                slo_type=SLOType.LATENCY,
                target_value=0.5,
                # percentile not provided
            )

    def test_slo_target_availability_invalid_range(self):
        """Test availability SLO must be 0-1."""
        with pytest.raises(ValueError, match="Availability/Error rate must be between 0 and 1"):
            SLOTarget(
                slo_type=SLOType.AVAILABILITY,
                target_value=1.5,  # Invalid: > 1
            )

    def test_slo_target_error_rate_invalid_range(self):
        """Test error rate SLO must be 0-1."""
        with pytest.raises(ValueError, match="Availability/Error rate must be between 0 and 1"):
            SLOTarget(
                slo_type=SLOType.ERROR_RATE,
                target_value=-0.1,  # Invalid: < 0
            )

    def test_slo_target_valid_latency(self):
        """Test valid latency SLO."""
        target = SLOTarget(
            slo_type=SLOType.LATENCY,
            target_value=0.5,
            percentile=95,
        )
        assert target.percentile == 95

    def test_slo_status_to_dict(self):
        """Test SLOStatus to_dict."""
        target = SLOTarget(
            slo_type=SLOType.AVAILABILITY,
            target_value=0.99,
        )
        now = datetime.now(UTC)
        status = SLOStatus(
            slo_type=SLOType.AVAILABILITY,
            target=target,
            current_value=0.995,
            compliance=True,
            error_budget_remaining=0.5,
            error_budget_burn_rate=0.1,
            window_start=now - timedelta(hours=1),
            window_end=now,
            measurement_count=100,
        )
        
        d = status.to_dict()
        
        assert d["slo_type"] == "availability"
        assert d["compliance"] is True
        assert "current_value" in d

    def test_error_budget_remaining_calculation(self):
        """Test ErrorBudget remaining calculation."""
        budget = ErrorBudget(
            total_budget=100.0,
            consumed=30.0,
        )
        
        assert budget.remaining == 70.0

    def test_error_budget_remaining_non_negative(self):
        """Test ErrorBudget remaining is never negative."""
        budget = ErrorBudget(
            total_budget=100.0,
            consumed=150.0,  # Over-consumed
        )
        
        assert budget.remaining == 0.0

    def test_error_budget_remaining_percentage(self):
        """Test ErrorBudget remaining_percentage."""
        budget = ErrorBudget(
            total_budget=100.0,
            consumed=30.0,
        )
        
        assert budget.remaining_percentage == 70.0

    def test_error_budget_remaining_percentage_zero_total(self):
        """Test ErrorBudget remaining_percentage with zero total."""
        budget = ErrorBudget(
            total_budget=0.0,
            consumed=0.0,
        )
        
        assert budget.remaining_percentage == 0.0

    def test_error_budget_is_exhausted(self):
        """Test ErrorBudget is_exhausted property."""
        exhausted = ErrorBudget(
            total_budget=100.0,
            consumed=100.0,
        )
        assert exhausted.is_exhausted is True
        
        not_exhausted = ErrorBudget(
            total_budget=100.0,
            consumed=50.0,
        )
        assert not_exhausted.is_exhausted is False
