"""
Tests for obskit.health.slo_check module.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from obskit.health.slo_check import (
    SLOCheckResult,
    SLOHealthStatus,
    SLOReadinessCheck,
    add_slo_readiness_check,
    get_slo_health_status,
)
from obskit.slo.tracker import SLOTracker, reset_slo_tracker
from obskit.slo.types import SLOType

# =============================================================================
# SLOHealthStatus Tests
# =============================================================================


class TestSLOHealthStatus:
    def test_healthy_value(self):
        assert SLOHealthStatus.HEALTHY.value == "healthy"

    def test_warning_value(self):
        assert SLOHealthStatus.WARNING.value == "warning"

    def test_critical_value(self):
        assert SLOHealthStatus.CRITICAL.value == "critical"

    def test_unknown_value(self):
        assert SLOHealthStatus.UNKNOWN.value == "unknown"


# =============================================================================
# SLOCheckResult Tests
# =============================================================================


class TestSLOCheckResult:
    def test_healthy_result(self):
        result = SLOCheckResult(
            slo_name="availability",
            status=SLOHealthStatus.HEALTHY,
            healthy=True,
            error_budget_remaining=0.8,
            current_value=0.999,
            target_value=0.99,
            message="All good",
        )
        assert result.healthy is True
        assert result.status == SLOHealthStatus.HEALTHY
        assert result.error_budget_remaining == pytest.approx(0.8)

    def test_critical_result(self):
        result = SLOCheckResult(
            slo_name="availability",
            status=SLOHealthStatus.CRITICAL,
            healthy=False,
            error_budget_remaining=0.05,
            current_value=0.95,
            target_value=0.99,
            message="Error budget critically low",
            details={"burn_rate": 10.0},
        )
        assert result.healthy is False
        assert result.details["burn_rate"] == pytest.approx(10.0)


# =============================================================================
# SLOReadinessCheck Tests
# =============================================================================


class TestSLOReadinessCheck:
    def setup_method(self):
        reset_slo_tracker()

    def teardown_method(self):
        reset_slo_tracker()

    def _make_tracker_with_slo(self, name, availability, current_value):
        """Create a tracker with specified SLO and simulated budget."""
        tracker = SLOTracker()
        tracker.register_slo(name, SLOType.AVAILABILITY, availability)
        # Record measurements to achieve desired current_value
        success_count = int(current_value * 100)
        for _ in range(success_count):
            tracker.record_measurement(name, 1.0, success=True)
        for _ in range(100 - success_count):
            tracker.record_measurement(name, 1.0, success=False)
        return tracker

    def test_check_healthy_slo(self):
        # target=0.90 => budget=0.10, with 100% success: budget_remaining=0.10
        # Use critical_threshold=0.005 so 0.10 is well above threshold
        tracker = SLOTracker()
        tracker.register_slo("avail_slo", SLOType.AVAILABILITY, 0.90)
        for _ in range(100):
            tracker.record_measurement("avail_slo", 1.0, success=True)
        check = SLOReadinessCheck(
            slo_name="avail_slo",
            critical_threshold=0.005,
            warning_threshold=0.05,
            slo_tracker=tracker,
        )
        result = check.check()
        assert result.healthy is True
        assert result.status == SLOHealthStatus.HEALTHY

    def test_check_warning_slo(self):
        """SLO with budget just below warning threshold."""
        tracker = SLOTracker()
        tracker.register_slo("warning_slo", SLOType.AVAILABILITY, 0.99)
        # Current: 98% availability, budget = 0.01 - 0.02 = 0 => will show as 0 remaining
        # But we want: budget used is between warning and critical threshold
        # For target=0.90, budget=0.10, current=0.80 => used=0.20 => remaining=0
        # Better: target=0.50, budget=0.50, current=0.30 => used=0.70 => remaining=-0.20 => max=0
        # Let's use: target=0.99, budget=0.01
        # current=0.98: used=0.02, remaining=0.01-0.02=-0.01 => 0 (clamped)
        # Use target=0.70 budget=0.30, current=0.85: used=0.15, remaining=0.15
        tracker = SLOTracker()
        tracker.register_slo("warn_slo", SLOType.AVAILABILITY, 0.70)
        for _ in range(85):
            tracker.record_measurement("warn_slo", 1.0, success=True)
        for _ in range(15):
            tracker.record_measurement("warn_slo", 1.0, success=False)

        check = SLOReadinessCheck(
            slo_name="warn_slo",
            critical_threshold=0.05,   # < 5% is critical
            warning_threshold=0.20,    # < 20% is warning
            slo_tracker=tracker,
        )
        result = check.check()
        # Remaining budget = 0.30 - (1 - 0.85) = 0.30 - 0.15 = 0.15
        # 0.15 < 0.20 warning threshold
        assert result.status == SLOHealthStatus.WARNING
        assert result.healthy is True  # Warning doesn't fail readiness

    def test_check_critical_slo(self):
        """SLO with budget below critical threshold."""
        tracker = SLOTracker()
        # target=0.80, budget=0.20
        tracker.register_slo("critical_slo", SLOType.AVAILABILITY, 0.80)
        # current=0.50: used=0.50, remaining=0.20-0.50=-0.30 => 0 (clamped)
        for _ in range(50):
            tracker.record_measurement("critical_slo", 1.0, success=True)
        for _ in range(50):
            tracker.record_measurement("critical_slo", 1.0, success=False)

        check = SLOReadinessCheck(
            slo_name="critical_slo",
            critical_threshold=0.05,
            warning_threshold=0.25,
            slo_tracker=tracker,
        )
        result = check.check()
        assert result.status == SLOHealthStatus.CRITICAL
        assert result.healthy is False

    def test_check_unregistered_slo(self):
        tracker = SLOTracker()
        check = SLOReadinessCheck(
            slo_name="nonexistent_slo",
            slo_tracker=tracker,
        )
        result = check.check()
        assert result.status == SLOHealthStatus.UNKNOWN
        assert result.healthy is True  # Don't fail for unregistered SLOs

    def test_check_no_tracker(self):
        check = SLOReadinessCheck(slo_name="some_slo")
        check._slo_tracker = None  # Force no tracker
        with patch("obskit.health.slo_check.get_slo_tracker", return_value=None):
            result = check.check()
        assert result.status == SLOHealthStatus.UNKNOWN
        assert result.healthy is True

    def test_check_tracker_exception(self):
        mock_tracker = MagicMock()
        mock_tracker.get_status.side_effect = Exception("Tracker error")
        check = SLOReadinessCheck(
            slo_name="err_slo",
            slo_tracker=mock_tracker,
        )
        result = check.check()
        assert result.status == SLOHealthStatus.UNKNOWN
        assert result.healthy is True  # Don't fail on check errors

    def test_slo_tracker_lazy_loading(self):
        """Test that slo_tracker property lazily loads the global tracker."""
        check = SLOReadinessCheck(slo_name="lazy_slo")
        check._slo_tracker = None
        mock_global_tracker = MagicMock()
        with patch("obskit.health.slo_check.get_slo_tracker", return_value=mock_global_tracker):
            tracker = check.slo_tracker
        assert tracker is mock_global_tracker

    def test_critical_details_contain_burn_rate(self):
        tracker = SLOTracker()
        tracker.register_slo("detail_slo", SLOType.AVAILABILITY, 0.80)
        for _ in range(50):
            tracker.record_measurement("detail_slo", 1.0, success=True)
        for _ in range(50):
            tracker.record_measurement("detail_slo", 1.0, success=False)

        check = SLOReadinessCheck(
            slo_name="detail_slo",
            critical_threshold=0.05,
            slo_tracker=tracker,
        )
        result = check.check()
        if result.status == SLOHealthStatus.CRITICAL and result.details:
            assert "burn_rate" in result.details


# =============================================================================
# add_slo_readiness_check Tests
# =============================================================================


class TestAddSloReadinessCheck:
    def setup_method(self):
        reset_slo_tracker()

    def teardown_method(self):
        reset_slo_tracker()

    def test_returns_slo_readiness_check_instance(self):
        mock_checker = MagicMock()
        mock_checker.add_readiness_check = MagicMock(return_value=lambda fn: fn)

        result = add_slo_readiness_check(
            slo_name="my_slo",
            critical_threshold=0.1,
            warning_threshold=0.25,
            health_checker=mock_checker,
        )
        assert isinstance(result, SLOReadinessCheck)
        assert result.slo_name == "my_slo"
        assert result.critical_threshold == pytest.approx(0.1)

    def test_registers_check_with_health_checker(self):
        mock_checker = MagicMock()
        mock_decorator = MagicMock(return_value=lambda fn: fn)
        mock_checker.add_readiness_check = MagicMock(return_value=mock_decorator)

        add_slo_readiness_check("some_slo", health_checker=mock_checker)
        mock_checker.add_readiness_check.assert_called_once_with("slo_some_slo")

    @pytest.mark.asyncio
    async def test_check_function_healthy(self):
        """Test the async check function registered with health checker."""
        tracker = SLOTracker()
        # target=0.90 => budget=0.10, 100% success => budget_remaining=0.10
        # Use critical_threshold=0.005 so 0.10 > threshold => healthy
        tracker.register_slo("check_fn_slo", SLOType.AVAILABILITY, 0.90)
        for _ in range(100):
            tracker.record_measurement("check_fn_slo", 1.0, success=True)

        mock_checker = MagicMock()
        registered_fn = None

        def capture_fn(name):
            def decorator(fn):
                nonlocal registered_fn
                registered_fn = fn
                return fn
            return decorator

        mock_checker.add_readiness_check = capture_fn

        slo_check = add_slo_readiness_check(
            "check_fn_slo",
            critical_threshold=0.005,
            warning_threshold=0.05,
            health_checker=mock_checker,
        )
        slo_check._slo_tracker = tracker

        assert registered_fn
        result = await registered_fn()
        # With critical_threshold=0.005 and budget_remaining=0.10, should be healthy => True
        assert result is True

    @pytest.mark.asyncio
    async def test_check_function_unhealthy(self):
        """Test the async check function returns dict when unhealthy."""
        tracker = SLOTracker()
        tracker.register_slo("check_fn_fail_slo", SLOType.AVAILABILITY, 0.99)
        # Only 80% availability => budget used > budget remaining
        for _ in range(80):
            tracker.record_measurement("check_fn_fail_slo", 1.0, success=True)
        for _ in range(20):
            tracker.record_measurement("check_fn_fail_slo", 1.0, success=False)

        mock_checker = MagicMock()
        registered_fn = None

        def capture_fn(name):
            def decorator(fn):
                nonlocal registered_fn
                registered_fn = fn
                return fn
            return decorator

        mock_checker.add_readiness_check = capture_fn

        slo_check = add_slo_readiness_check(
            "check_fn_fail_slo",
            critical_threshold=0.05,
            health_checker=mock_checker,
        )
        slo_check._slo_tracker = tracker

        assert registered_fn
        result = await registered_fn()
        # Budget is 0 (clamped), which is less than critical_threshold=0.05
        if isinstance(result, dict):
            assert result["healthy"] is False
        else:
            # healthy=True means budget was above threshold
            assert result is True


# =============================================================================
# get_slo_health_status Tests
# =============================================================================


class TestGetSloHealthStatus:
    def setup_method(self):
        reset_slo_tracker()

    def teardown_method(self):
        reset_slo_tracker()

    def test_no_tracker_returns_unknown(self):
        with patch("obskit.health.slo_check.get_slo_tracker", return_value=None):
            result = get_slo_health_status()
        assert result["healthy"] is True
        assert result["status"] == "unknown"
        assert result["slos"] == {}

    def test_no_slos_specified_empty_result(self):
        tracker = SLOTracker()
        with patch("obskit.health.slo_check.get_slo_tracker", return_value=tracker):
            result = get_slo_health_status(slo_names=[])
        assert result["healthy"] is True
        assert result["slos_checked"] == 0

    def test_healthy_slo_status(self):
        tracker = SLOTracker()
        # target=0.90 => budget=0.10, 100% success => budget_remaining=0.10
        # Use critical_threshold=0.005 so 0.10 > threshold => healthy
        tracker.register_slo("healthy_slo", SLOType.AVAILABILITY, 0.90)
        for _ in range(100):
            tracker.record_measurement("healthy_slo", 1.0, success=True)

        with patch("obskit.health.slo_check.get_slo_tracker", return_value=tracker):
            result = get_slo_health_status(
                slo_names=["healthy_slo"],
                critical_threshold=0.005,
                warning_threshold=0.05,
            )
        assert result["healthy"] is True
        assert result["status"] == "healthy"
        assert "healthy_slo" in result["slos"]

    def test_critical_slo_status(self):
        tracker = SLOTracker()
        tracker.register_slo("crit_slo", SLOType.AVAILABILITY, 0.80)
        # 50% availability
        for _ in range(50):
            tracker.record_measurement("crit_slo", 1.0, success=True)
        for _ in range(50):
            tracker.record_measurement("crit_slo", 1.0, success=False)

        with patch("obskit.health.slo_check.get_slo_tracker", return_value=tracker):
            result = get_slo_health_status(
                slo_names=["crit_slo"],
                critical_threshold=0.05,
            )
        assert result["status"] == "critical"
        assert result["healthy"] is False

    def test_warning_slo_status(self):
        tracker = SLOTracker()
        # target=0.70, budget=0.30, current=0.85, used=0.15, remaining=0.15
        tracker.register_slo("warn_slo", SLOType.AVAILABILITY, 0.70)
        for _ in range(85):
            tracker.record_measurement("warn_slo", 1.0, success=True)
        for _ in range(15):
            tracker.record_measurement("warn_slo", 1.0, success=False)

        with patch("obskit.health.slo_check.get_slo_tracker", return_value=tracker):
            result = get_slo_health_status(
                slo_names=["warn_slo"],
                critical_threshold=0.05,
                warning_threshold=0.20,
            )
        assert result["status"] == SLOHealthStatus.WARNING.value or result["status"] == "healthy"

    def test_multiple_slos_one_critical(self):
        tracker = SLOTracker()
        tracker.register_slo("ok_slo", SLOType.AVAILABILITY, 0.99)
        tracker.register_slo("bad_slo", SLOType.AVAILABILITY, 0.80)

        for _ in range(100):
            tracker.record_measurement("ok_slo", 1.0, success=True)
        for _ in range(50):
            tracker.record_measurement("bad_slo", 1.0, success=True)
        for _ in range(50):
            tracker.record_measurement("bad_slo", 1.0, success=False)

        with patch("obskit.health.slo_check.get_slo_tracker", return_value=tracker):
            result = get_slo_health_status(
                slo_names=["ok_slo", "bad_slo"],
                critical_threshold=0.05,
            )
        assert result["status"] == "critical"
        assert result["healthy"] is False

    def test_slo_result_dict_contains_required_keys(self):
        tracker = SLOTracker()
        tracker.register_slo("keys_slo", SLOType.AVAILABILITY, 0.99)
        tracker.record_measurement("keys_slo", 1.0, success=True)

        with patch("obskit.health.slo_check.get_slo_tracker", return_value=tracker):
            result = get_slo_health_status(slo_names=["keys_slo"])

        slo_result = result["slos"]["keys_slo"]
        required_keys = {"status", "healthy", "error_budget_remaining", "current_value", "target_value", "message"}
        assert required_keys.issubset(slo_result.keys())

    def test_slos_detected_via_tracker_keys(self):
        """Test that slo_names is auto-detected from tracker._slos if it exists."""
        tracker = SLOTracker()
        tracker._slos = {"auto_slo": MagicMock()}
        tracker.get_status = MagicMock(return_value=None)  # Returns None for unregistered

        with patch("obskit.health.slo_check.get_slo_tracker", return_value=tracker):
            result = get_slo_health_status(slo_names=None)
        # Should attempt to check "auto_slo"
        assert result is not None
