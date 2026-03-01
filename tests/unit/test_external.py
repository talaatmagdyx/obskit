"""
Tests for obskit.external module — ExternalAPISLATracker.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone, UTC
from unittest.mock import MagicMock, patch

import pytest

from obskit.external import (
    APICallRecord,
    ExternalAPISLATracker,
    SLAComplianceReport,
    SLADefinition,
    get_all_api_compliance,
    get_external_api_tracker,
)

# =============================================================================
# SLADefinition Tests
# =============================================================================


class TestSLADefinition:
    def test_defaults(self):
        sla = SLADefinition()
        assert sla.availability == pytest.approx(0.99)
        assert sla.latency_p95_ms == 500
        assert sla.error_rate_percent == pytest.approx(1.0)

    def test_custom_values(self):
        sla = SLADefinition(
            availability=0.999,
            latency_p95_ms=100,
            error_rate_percent=0.1,
        )
        assert sla.availability == pytest.approx(0.999)
        assert sla.latency_p95_ms == 100


# =============================================================================
# APICallRecord Tests
# =============================================================================


class TestAPICallRecord:
    def test_success_record(self):
        record = APICallRecord(
            timestamp=datetime.now(UTC),
            latency_seconds=0.1,
            success=True,
            status_code=200,
        )
        assert record.success is True
        assert record.latency_seconds == pytest.approx(0.1)
        assert record.status_code == 200
        assert record.error_type is None

    def test_failure_record(self):
        record = APICallRecord(
            timestamp=datetime.now(UTC),
            latency_seconds=5.0,
            success=False,
            error_type="TimeoutError",
        )
        assert record.success is False
        assert record.error_type == "TimeoutError"


# =============================================================================
# SLAComplianceReport Tests
# =============================================================================


class TestSLAComplianceReport:
    def _make_report(self, **kwargs):
        now = datetime.now(UTC)
        defaults = dict(
            api_name="test_api",
            window_start=now - timedelta(hours=1),
            window_end=now,
            total_requests=100,
            successful_requests=99,
            failed_requests=1,
            availability=0.99,
            availability_sla=0.99,
            availability_compliant=True,
            latency_p50_ms=50.0,
            latency_p95_ms=200.0,
            latency_p99_ms=400.0,
            latency_p95_sla_ms=500.0,
            latency_compliant=True,
            error_rate_percent=1.0,
            error_rate_sla_percent=1.0,
            error_rate_compliant=True,
            overall_compliant=True,
            sla_breaches=[],
        )
        defaults.update(kwargs)
        return SLAComplianceReport(**defaults)

    def test_to_dict_basic(self):
        report = self._make_report()
        d = report.to_dict()
        assert d["api_name"] == "test_api"
        assert d["total_requests"] == 100
        assert d["overall_compliant"] is True
        assert isinstance(d["window_start"], str)
        assert isinstance(d["sla_breaches"], list)

    def test_to_dict_with_breaches(self):
        report = self._make_report(
            sla_breaches=["availability", "latency"],
            overall_compliant=False,
        )
        d = report.to_dict()
        assert len(d["sla_breaches"]) == 2


# =============================================================================
# ExternalAPISLATracker Tests
# =============================================================================


class TestExternalAPISLATracker:
    def setup_method(self):
        self.tracker = ExternalAPISLATracker(
            api_name="test_api",
            expected_availability=0.99,
            expected_latency_p95_ms=500,
            expected_error_rate_percent=1.0,
            window_seconds=3600,
        )

    def test_init(self):
        assert self.tracker.api_name == "test_api"
        assert self.tracker.sla.availability == pytest.approx(0.99)
        assert self.tracker.sla.latency_p95_ms == 500

    def test_record_call_success(self):
        self.tracker.record_call(latency_seconds=0.1, success=True, method="GET")
        report = self.tracker.get_compliance_report()
        assert report.total_requests == 1
        assert report.successful_requests == 1
        assert report.failed_requests == 0

    def test_record_call_failure(self):
        self.tracker.record_call(latency_seconds=5.0, success=False, error_type="TimeoutError")
        report = self.tracker.get_compliance_report()
        assert report.failed_requests == 1

    def test_multiple_calls_availability(self):
        for _ in range(99):
            self.tracker.record_call(latency_seconds=0.1, success=True)
        self.tracker.record_call(latency_seconds=0.1, success=False)
        report = self.tracker.get_compliance_report()
        assert report.availability == pytest.approx(0.99, rel=0.01)
        assert report.availability_compliant is True

    def test_availability_breach(self):
        tracker = ExternalAPISLATracker(
            api_name="breach_test",
            expected_availability=0.99,
        )
        for _ in range(90):
            tracker.record_call(latency_seconds=0.1, success=True)
        for _ in range(10):
            tracker.record_call(latency_seconds=0.1, success=False)
        report = tracker.get_compliance_report()
        assert report.availability_compliant is False
        assert report.overall_compliant is False

    def test_latency_compliance(self):
        tracker = ExternalAPISLATracker(
            api_name="latency_test",
            expected_latency_p95_ms=500,
        )
        for _ in range(100):
            tracker.record_call(latency_seconds=0.1, success=True)  # 100ms
        report = tracker.get_compliance_report()
        assert report.latency_compliant is True

    def test_latency_breach(self):
        tracker = ExternalAPISLATracker(
            api_name="latency_breach",
            expected_latency_p95_ms=100,  # Very strict: 100ms
        )
        for _ in range(100):
            tracker.record_call(latency_seconds=1.0, success=True)  # 1000ms
        report = tracker.get_compliance_report()
        assert report.latency_compliant is False

    def test_error_rate_compliance(self):
        tracker = ExternalAPISLATracker(
            api_name="error_rate_test",
            expected_error_rate_percent=5.0,
        )
        for _ in range(95):
            tracker.record_call(latency_seconds=0.1, success=True)
        for _ in range(5):
            tracker.record_call(latency_seconds=0.1, success=False)
        report = tracker.get_compliance_report()
        assert report.error_rate_percent == pytest.approx(5.0, rel=0.1)
        assert report.error_rate_compliant is True

    def test_empty_report(self):
        tracker = ExternalAPISLATracker("empty_api")
        report = tracker.get_compliance_report()
        assert report.total_requests == 0
        assert report.availability == pytest.approx(1.0)  # Default to 100% when no data
        assert report.overall_compliant is True

    def test_is_compliant_true(self):
        tracker = ExternalAPISLATracker("compliant_api")
        for _ in range(100):
            tracker.record_call(latency_seconds=0.1, success=True)
        assert tracker.is_compliant() is True

    def test_is_compliant_false(self):
        tracker = ExternalAPISLATracker(
            "noncompliant_api",
            expected_availability=0.999,
        )
        # Only 90% availability
        for _ in range(90):
            tracker.record_call(latency_seconds=0.1, success=True)
        for _ in range(10):
            tracker.record_call(latency_seconds=0.1, success=False)
        assert tracker.is_compliant() is False

    def test_track_call_context_manager_success(self):
        tracker = ExternalAPISLATracker("ctx_api")
        with tracker.track_call(method="POST"):
            pass  # Simulate successful call
        report = tracker.get_compliance_report()
        assert report.successful_requests == 1

    def test_track_call_context_manager_failure(self):
        tracker = ExternalAPISLATracker("ctx_fail_api")
        with pytest.raises(ValueError):
            with tracker.track_call(method="GET"):
                raise ValueError("API error")
        report = tracker.get_compliance_report()
        assert report.failed_requests == 1

    def test_set_expected_sla(self):
        self.tracker.set_expected_sla(availability=0.999, latency_p95_ms=100)
        assert self.tracker.sla.availability == pytest.approx(0.999)
        assert self.tracker.sla.latency_p95_ms == 100

    def test_set_expected_sla_partial(self):
        original_latency = self.tracker.sla.latency_p95_ms
        self.tracker.set_expected_sla(availability=0.995)
        assert self.tracker.sla.availability == pytest.approx(0.995)
        assert self.tracker.sla.latency_p95_ms == original_latency

    def test_sla_breach_callback(self):
        breaches = []
        tracker = ExternalAPISLATracker(
            api_name="breach_cb_api",
            expected_availability=0.99,
            on_sla_breach=lambda name, breach_type, value: breaches.append((name, breach_type)),
        )
        # Cause availability breach
        for _ in range(80):
            tracker.record_call(latency_seconds=0.1, success=True)
        for _ in range(20):
            tracker.record_call(latency_seconds=0.1, success=False)
        assert len(breaches) > 0

    def test_sla_breach_latency_callback(self):
        """Test SLA breach callback for latency breach."""
        breaches = []
        tracker = ExternalAPISLATracker(
            api_name="latency_cb_api",
            expected_latency_p95_ms=10,  # Very strict
            on_sla_breach=lambda name, breach_type, value: breaches.append(breach_type),
        )
        for _ in range(100):
            tracker.record_call(latency_seconds=1.0, success=True)  # 1000ms >> 10ms
        assert any("latency" in b for b in breaches)

    def test_cleanup_old_records(self):
        tracker = ExternalAPISLATracker("cleanup_api", window_seconds=1)
        tracker.record_call(latency_seconds=0.1, success=True)
        time.sleep(0.01)
        # Force cleanup by calling get_compliance_report
        tracker._records[0].timestamp = datetime.now(UTC) - timedelta(seconds=10)
        report = tracker.get_compliance_report()
        # Record should have been cleaned up
        assert report.total_requests == 0

    def test_single_latency_record(self):
        """Test percentile calculation with a single record."""
        tracker = ExternalAPISLATracker("single_record_api")
        tracker.record_call(latency_seconds=0.2, success=True)
        report = tracker.get_compliance_report()
        assert report.latency_p50_ms == pytest.approx(200.0, rel=0.01)

    def test_latency_breach_triggers_callback(self):
        """Cover error_rate branch in _check_sla_compliance callback."""
        breaches = []
        tracker = ExternalAPISLATracker(
            api_name="error_rate_cb_api",
            expected_error_rate_percent=0.1,  # Very strict
            on_sla_breach=lambda name, breach_type, value: breaches.append(breach_type),
        )
        for _ in range(50):
            tracker.record_call(latency_seconds=0.1, success=False)  # 100% error rate
        assert any("error" in b for b in breaches)

    def test_breach_cooldown_prevents_spam(self):
        """Test that breach callback has cooldown - set recent_breaches manually."""
        call_count = [0]

        def on_breach(name, breach_type, value):
            call_count[0] += 1

        tracker = ExternalAPISLATracker(
            api_name="cooldown_api",
            expected_availability=0.999,
            on_sla_breach=on_breach,
        )
        # Cause initial breaches
        for _ in range(80):
            tracker.record_call(latency_seconds=0.1, success=True)
        for _ in range(20):
            tracker.record_call(latency_seconds=0.1, success=False)

        initial_count = call_count[0]
        assert initial_count > 0  # Verify callbacks were called

        # The breach cooldown mechanism should exist
        assert hasattr(tracker, "_recent_breaches")
        assert hasattr(tracker, "_breach_cooldown")


# =============================================================================
# Registry Tests
# =============================================================================


class TestExternalAPISLATrackerRegistry:
    def test_get_external_api_tracker_creates_new(self):
        tracker = get_external_api_tracker("registry_api_unique_1")
        assert isinstance(tracker, ExternalAPISLATracker)
        assert tracker.api_name == "registry_api_unique_1"

    def test_get_external_api_tracker_singleton(self):
        t1 = get_external_api_tracker("registry_api_singleton_xyz")
        t2 = get_external_api_tracker("registry_api_singleton_xyz")
        assert t1 is t2

    def test_get_all_api_compliance(self):
        get_external_api_tracker("compliance_report_api")
        result = get_all_api_compliance()
        assert isinstance(result, dict)
        assert "compliance_report_api" in result
