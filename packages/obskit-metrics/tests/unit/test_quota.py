"""
Tests for obskit.quota module.

Tests cover:
- QuotaPeriod enum
- QuotaLimit, TenantUsage, QuotaReport dataclasses
- QuotaTracker: set_limit, check_and_increment, get_usage, get_remaining
- QuotaTracker: is_over_quota, get_report, reset_usage
- QuotaTracker: _get_or_create_usage, _maybe_reset_period, _update_metrics, _maybe_warn
- Registry helper: get_quota_tracker
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, call, patch

import pytest

from obskit.quota import (
    QuotaLimit,
    QuotaPeriod,
    QuotaReport,
    QuotaTracker,
    TenantUsage,
    get_quota_tracker,
)

# =============================================================================
# QuotaPeriod enum
# =============================================================================


class TestQuotaPeriod:
    def test_all_periods_exist(self):
        assert QuotaPeriod.MINUTE.value == 60
        assert QuotaPeriod.HOUR.value == 3600
        assert QuotaPeriod.DAY.value == 86400
        assert QuotaPeriod.MONTH.value == 2592000

    def test_enum_count(self):
        assert len(list(QuotaPeriod)) == 4


# =============================================================================
# QuotaLimit dataclass
# =============================================================================


class TestQuotaLimit:
    def test_creation(self):
        ql = QuotaLimit(resource="requests", limit=1000, period=QuotaPeriod.HOUR)
        assert ql.resource == "requests"
        assert ql.limit == 1000
        assert ql.period == QuotaPeriod.HOUR
        assert ql.burst_limit is None
        assert ql.soft_limit_percent == 80.0

    def test_with_burst(self):
        ql = QuotaLimit(
            resource="api_calls",
            limit=500,
            period=QuotaPeriod.MINUTE,
            burst_limit=600,
        )
        assert ql.burst_limit == 600


# =============================================================================
# TenantUsage dataclass
# =============================================================================


class TestTenantUsage:
    def test_default_values(self):
        usage = TenantUsage(tenant_id="t1", resource="requests")
        assert usage.current_usage == 0
        assert usage.limit == 0
        assert usage.exceeded_count == 0
        assert usage.last_exceeded is None
        assert usage.period == QuotaPeriod.HOUR

    def test_usage_percent_with_zero_limit(self):
        usage = TenantUsage(tenant_id="t1", resource="requests", limit=0)
        assert usage.usage_percent == 0.0

    def test_usage_percent_calculated(self):
        usage = TenantUsage(
            tenant_id="t1",
            resource="requests",
            current_usage=50,
            limit=100,
        )
        assert usage.usage_percent == 50.0

    def test_remaining(self):
        usage = TenantUsage(
            tenant_id="t1",
            resource="requests",
            current_usage=30,
            limit=100,
        )
        assert usage.remaining == 70

    def test_remaining_at_zero_when_exceeded(self):
        usage = TenantUsage(
            tenant_id="t1",
            resource="requests",
            current_usage=110,
            limit=100,
        )
        assert usage.remaining == 0

    def test_to_dict(self):
        usage = TenantUsage(
            tenant_id="tenant-1",
            resource="api_calls",
            current_usage=75,
            limit=100,
            period=QuotaPeriod.HOUR,
            exceeded_count=2,
        )
        d = usage.to_dict()
        assert d["tenant_id"] == "tenant-1"
        assert d["resource"] == "api_calls"
        assert d["current_usage"] == 75
        assert d["limit"] == 100
        assert d["usage_percent"] == 75.0
        assert d["remaining"] == 25
        assert d["period"] == "HOUR"
        assert d["exceeded_count"] == 2
        assert d["last_exceeded"] is None
        assert "period_start" in d

    def test_to_dict_with_last_exceeded(self):
        usage = TenantUsage(
            tenant_id="t1",
            resource="r",
            last_exceeded=datetime.utcnow(),
        )
        d = usage.to_dict()
        assert d["last_exceeded"] is not None


# =============================================================================
# QuotaReport dataclass
# =============================================================================


class TestQuotaReport:
    def test_to_dict(self):
        usage = TenantUsage(tenant_id="t1", resource="req", current_usage=50, limit=100)
        report = QuotaReport(
            quota_name="api_requests",
            tenant_id="t1",
            usages=[usage],
            total_exceeded=0,
            is_over_quota=False,
        )
        d = report.to_dict()
        assert d["quota_name"] == "api_requests"
        assert d["tenant_id"] == "t1"
        assert len(d["usages"]) == 1
        assert d["total_exceeded"] == 0
        assert d["is_over_quota"] is False
        assert "timestamp" in d


# =============================================================================
# QuotaTracker initialization
# =============================================================================


class TestQuotaTrackerInit:
    def test_default_initialization(self):
        tracker = QuotaTracker("api_requests")
        assert tracker.quota_name == "api_requests"
        assert tracker.default_limit == 10000
        assert tracker.default_period == QuotaPeriod.HOUR
        assert tracker.on_exceeded is None
        assert tracker.on_warning is None

    def test_custom_initialization(self):
        callback = MagicMock()
        warning_cb = MagicMock()
        tracker = QuotaTracker(
            "api",
            default_limit=500,
            default_period=QuotaPeriod.MINUTE,
            on_exceeded=callback,
            on_warning=warning_cb,
        )
        assert tracker.default_limit == 500
        assert tracker.default_period == QuotaPeriod.MINUTE
        assert tracker.on_exceeded is callback
        assert tracker.on_warning is warning_cb


# =============================================================================
# QuotaTracker set_limit
# =============================================================================


class TestQuotaTrackerSetLimit:
    def test_set_limit_basic(self):
        tracker = QuotaTracker("ql_test_basic")
        tracker.set_limit("tenant-1", resource="requests", limit=5000)
        assert "tenant-1" in tracker._limits
        assert "requests" in tracker._limits["tenant-1"]
        assert tracker._limits["tenant-1"]["requests"].limit == 5000

    def test_set_limit_default_resource(self):
        tracker = QuotaTracker("ql_test_default_resource")
        tracker.set_limit("tenant-2")
        assert "requests" in tracker._limits["tenant-2"]

    def test_set_limit_uses_default_limit_when_none(self):
        tracker = QuotaTracker("ql_test_default_lim", default_limit=999)
        tracker.set_limit("tenant-3", limit=None)
        assert tracker._limits["tenant-3"]["requests"].limit == 999

    def test_set_limit_with_burst(self):
        tracker = QuotaTracker("ql_test_burst")
        tracker.set_limit("tenant-4", limit=1000, burst_limit=1500)
        assert tracker._limits["tenant-4"]["requests"].burst_limit == 1500

    def test_set_limit_multiple_resources(self):
        tracker = QuotaTracker("ql_test_multi_resources")
        tracker.set_limit("tenant-5", resource="api_calls", limit=100)
        tracker.set_limit("tenant-5", resource="storage_gb", limit=50)
        assert "api_calls" in tracker._limits["tenant-5"]
        assert "storage_gb" in tracker._limits["tenant-5"]


# =============================================================================
# QuotaTracker check_and_increment
# =============================================================================


class TestQuotaTrackerCheckAndIncrement:
    def test_allows_within_limit(self):
        tracker = QuotaTracker("check_inc_allow")
        tracker.set_limit("t1", limit=100)
        result = tracker.check_and_increment("t1")
        assert result is True

    def test_denies_when_over_limit(self):
        tracker = QuotaTracker("check_inc_deny")
        tracker.set_limit("t1", limit=2)
        tracker.check_and_increment("t1")
        tracker.check_and_increment("t1")
        # Third should fail
        result = tracker.check_and_increment("t1")
        assert result is False

    def test_increments_usage(self):
        tracker = QuotaTracker("check_inc_incr")
        tracker.set_limit("t1", limit=100)
        tracker.check_and_increment("t1", amount=5)
        usage = tracker.get_usage("t1")
        assert usage.current_usage == 5

    def test_calls_on_exceeded_callback(self):
        callback = MagicMock()
        tracker = QuotaTracker("check_inc_callback", on_exceeded=callback)
        tracker.set_limit("t1", limit=1)
        tracker.check_and_increment("t1")
        tracker.check_and_increment("t1")  # This should trigger callback
        callback.assert_called()

    def test_uses_burst_limit_when_allowed(self):
        tracker = QuotaTracker("check_inc_burst")
        tracker.set_limit("t1", limit=10, burst_limit=20)
        # Should allow up to burst_limit
        results = [tracker.check_and_increment("t1") for _ in range(20)]
        assert all(results)
        # 21st should fail
        result = tracker.check_and_increment("t1")
        assert result is False

    def test_does_not_use_burst_when_disabled(self):
        tracker = QuotaTracker("check_inc_no_burst")
        tracker.set_limit("t1", limit=5, burst_limit=10)
        for _ in range(5):
            tracker.check_and_increment("t1", allow_burst=False)
        # 6th without burst should fail (uses limit=5, not burst=10)
        result = tracker.check_and_increment("t1", allow_burst=False)
        assert result is False

    def test_increments_exceeded_count_on_denial(self):
        tracker = QuotaTracker("check_inc_exceeded_count")
        tracker.set_limit("t1", limit=1)
        tracker.check_and_increment("t1")
        tracker.check_and_increment("t1")  # denied
        tracker.check_and_increment("t1")  # denied
        usage = tracker.get_usage("t1")
        assert usage.exceeded_count == 2

    def test_auto_creates_usage_without_limit_set(self):
        tracker = QuotaTracker("check_inc_auto", default_limit=100)
        result = tracker.check_and_increment("new-tenant")
        assert result is True

    def test_calls_on_warning_at_soft_limit(self):
        warning_cb = MagicMock()
        tracker = QuotaTracker("check_inc_warn", on_warning=warning_cb)
        tracker.set_limit("t1", limit=100, soft_limit_percent=80.0)
        # Increment to 80 (exactly at soft limit)
        tracker.check_and_increment("t1", amount=80)
        warning_cb.assert_called()

    def test_period_reset_clears_usage(self):
        tracker = QuotaTracker("check_inc_reset_period", default_period=QuotaPeriod.MINUTE)
        tracker.set_limit("t1", limit=10, period=QuotaPeriod.MINUTE)
        # Fill up
        for _ in range(10):
            tracker.check_and_increment("t1")
        # Manually expire the period
        usage = tracker._usage["t1"]["requests"]
        usage.period_start = datetime.utcnow() - timedelta(seconds=70)
        # Now should reset and allow
        result = tracker.check_and_increment("t1")
        assert result is True


# =============================================================================
# QuotaTracker get_usage
# =============================================================================


class TestQuotaTrackerGetUsage:
    def test_get_usage_nonexistent_returns_none(self):
        tracker = QuotaTracker("get_usage_none")
        result = tracker.get_usage("nonexistent-tenant")
        assert result is None

    def test_get_usage_returns_existing(self):
        tracker = QuotaTracker("get_usage_exists")
        tracker.set_limit("t1", limit=100)
        tracker.check_and_increment("t1", amount=10)
        usage = tracker.get_usage("t1")
        assert usage is not None
        assert usage.current_usage == 10

    def test_get_usage_resets_period_if_expired(self):
        tracker = QuotaTracker("get_usage_reset")
        tracker.set_limit("t1", limit=100, period=QuotaPeriod.MINUTE)
        tracker.check_and_increment("t1", amount=50)
        # Expire the period
        tracker._usage["t1"]["requests"].period_start = (
            datetime.utcnow() - timedelta(seconds=70)
        )
        usage = tracker.get_usage("t1")
        assert usage.current_usage == 0  # Reset


# =============================================================================
# QuotaTracker get_remaining
# =============================================================================


class TestQuotaTrackerGetRemaining:
    def test_get_remaining_no_usage(self):
        tracker = QuotaTracker("get_remaining_none", default_limit=500)
        remaining = tracker.get_remaining("unknown-tenant")
        assert remaining == 500  # Returns default limit

    def test_get_remaining_with_usage(self):
        tracker = QuotaTracker("get_remaining_with")
        tracker.set_limit("t1", limit=100)
        tracker.check_and_increment("t1", amount=30)
        remaining = tracker.get_remaining("t1")
        assert remaining == 70


# =============================================================================
# QuotaTracker is_over_quota
# =============================================================================


class TestQuotaTrackerIsOverQuota:
    def test_not_over_quota_initially(self):
        tracker = QuotaTracker("over_quota_false")
        tracker.set_limit("t1", limit=100)
        assert tracker.is_over_quota("t1") is False

    def test_is_over_quota_when_at_limit(self):
        tracker = QuotaTracker("over_quota_true")
        tracker.set_limit("t1", limit=5)
        for _ in range(5):
            tracker.check_and_increment("t1")
        assert tracker.is_over_quota("t1") is True

    def test_nonexistent_tenant_not_over_quota(self):
        tracker = QuotaTracker("over_quota_nonexistent")
        assert tracker.is_over_quota("ghost-tenant") is False


# =============================================================================
# QuotaTracker get_report
# =============================================================================


class TestQuotaTrackerGetReport:
    def test_get_report_empty_tenant(self):
        tracker = QuotaTracker("report_empty")
        report = tracker.get_report("unknown-tenant")
        assert isinstance(report, QuotaReport)
        assert report.tenant_id == "unknown-tenant"
        assert report.usages == []
        assert report.total_exceeded == 0
        assert report.is_over_quota is False

    def test_get_report_with_usage(self):
        tracker = QuotaTracker("report_with_usage")
        tracker.set_limit("t1", limit=100)
        tracker.check_and_increment("t1", amount=50)
        report = tracker.get_report("t1")
        assert len(report.usages) == 1
        assert report.usages[0].current_usage == 50

    def test_get_report_is_over_quota_flag(self):
        tracker = QuotaTracker("report_over")
        tracker.set_limit("t1", limit=5)
        for _ in range(5):
            tracker.check_and_increment("t1")
        report = tracker.get_report("t1")
        assert report.is_over_quota is True

    def test_get_report_total_exceeded(self):
        tracker = QuotaTracker("report_exceeded")
        tracker.set_limit("t1", limit=2)
        tracker.check_and_increment("t1")
        tracker.check_and_increment("t1")
        tracker.check_and_increment("t1")  # exceeded
        tracker.check_and_increment("t1")  # exceeded
        report = tracker.get_report("t1")
        assert report.total_exceeded == 2

    def test_get_report_quota_name(self):
        tracker = QuotaTracker("my_quota_name")
        report = tracker.get_report("t1")
        assert report.quota_name == "my_quota_name"


# =============================================================================
# QuotaTracker reset_usage
# =============================================================================


class TestQuotaTrackerResetUsage:
    def test_reset_specific_resource(self):
        tracker = QuotaTracker("reset_specific")
        tracker.set_limit("t1", limit=100)
        tracker.check_and_increment("t1", amount=50)
        tracker.reset_usage("t1", resource="requests")
        usage = tracker.get_usage("t1")
        assert usage.current_usage == 0

    def test_reset_all_resources(self):
        tracker = QuotaTracker("reset_all")
        tracker.set_limit("t1", resource="api_calls", limit=100)
        tracker.set_limit("t1", resource="storage", limit=50)
        tracker.check_and_increment("t1", resource="api_calls", amount=30)
        tracker.check_and_increment("t1", resource="storage", amount=20)
        tracker.reset_usage("t1")  # Reset all
        assert tracker.get_usage("t1", "api_calls").current_usage == 0
        assert tracker.get_usage("t1", "storage").current_usage == 0

    def test_reset_nonexistent_tenant_no_error(self):
        tracker = QuotaTracker("reset_nonexistent")
        # Should not raise
        tracker.reset_usage("does-not-exist")

    def test_reset_nonexistent_resource_no_error(self):
        tracker = QuotaTracker("reset_nonexistent_resource")
        tracker.set_limit("t1", limit=100)
        # Should not raise
        tracker.reset_usage("t1", resource="nonexistent_resource")


# =============================================================================
# QuotaTracker _maybe_warn (cooldown)
# =============================================================================


class TestQuotaTrackerMaybeWarn:
    def test_warns_at_soft_limit(self):
        warning_cb = MagicMock()
        tracker = QuotaTracker("warn_soft", on_warning=warning_cb)
        tracker.set_limit("t1", limit=100, soft_limit_percent=80.0)
        usage = tracker._get_or_create_usage("t1", "requests")
        usage.current_usage = 80
        usage.limit = 100
        tracker._maybe_warn("t1", "requests", usage)
        warning_cb.assert_called_once()

    def test_cooldown_prevents_repeated_warning(self):
        warning_cb = MagicMock()
        tracker = QuotaTracker("warn_cooldown", on_warning=warning_cb)
        tracker.set_limit("t1", limit=100, soft_limit_percent=80.0)
        usage = tracker._get_or_create_usage("t1", "requests")
        usage.current_usage = 80
        usage.limit = 100
        tracker._maybe_warn("t1", "requests", usage)
        tracker._maybe_warn("t1", "requests", usage)  # Should be suppressed
        warning_cb.assert_called_once()

    def test_no_warning_callback_no_error(self):
        tracker = QuotaTracker("warn_no_cb")
        tracker.set_limit("t1", limit=100)
        usage = tracker._get_or_create_usage("t1", "requests")
        usage.current_usage = 80
        usage.limit = 100
        # Should not raise
        tracker._maybe_warn("t1", "requests", usage)


# =============================================================================
# Registry helper
# =============================================================================


class TestGetQuotaTracker:
    def setup_method(self):
        import obskit.quota as module
        module._trackers.clear()

    def test_creates_new_tracker(self):
        tracker = get_quota_tracker("new_quota")
        assert isinstance(tracker, QuotaTracker)
        assert tracker.quota_name == "new_quota"

    def test_returns_same_instance(self):
        t1 = get_quota_tracker("same_quota")
        t2 = get_quota_tracker("same_quota")
        assert t1 is t2

    def test_different_names_different_instances(self):
        t1 = get_quota_tracker("quota_a")
        t2 = get_quota_tracker("quota_b")
        assert t1 is not t2

    def test_custom_kwargs_passed_through(self):
        tracker = get_quota_tracker("quota_kwargs", default_limit=999)
        assert tracker.default_limit == 999
