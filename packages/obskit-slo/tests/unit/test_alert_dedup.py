"""
Tests for obskit.alert_dedup module — AlertDeduplicator.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone, UTC
from unittest.mock import MagicMock, patch

import pytest

from obskit.alert_dedup import (
    AlertDeduplicator,
    AlertRecord,
    DeduplicationConfig,
    get_alert_deduplicator,
    should_alert,
)

# =============================================================================
# AlertRecord Tests
# =============================================================================


class TestAlertRecord:
    def _make_record(self, **kwargs):
        now = datetime.now(UTC)
        defaults = dict(
            alert_name="high_error_rate",
            severity="warning",
            first_seen=now,
            last_seen=now,
        )
        defaults.update(kwargs)
        return AlertRecord(**defaults)

    def test_to_dict_basic(self):
        record = self._make_record()
        d = record.to_dict()
        assert d["alert_name"] == "high_error_rate"
        assert d["severity"] == "warning"
        assert d["count"] == 1
        assert d["last_sent"] is None

    def test_to_dict_with_last_sent(self):
        now = datetime.now(UTC)
        record = self._make_record(last_sent=now)
        d = record.to_dict()
        assert d["last_sent"] is not None

    def test_to_dict_with_labels(self):
        record = self._make_record(labels={"service": "api", "region": "us-east"})
        d = record.to_dict()
        assert d["labels"]["service"] == "api"


# =============================================================================
# DeduplicationConfig Tests
# =============================================================================


class TestDeduplicationConfig:
    def test_defaults(self):
        config = DeduplicationConfig()
        assert config.window_minutes == 15
        assert config.max_alerts_per_window == 3
        assert "critical" in config.severity_cooldowns
        assert "warning" in config.severity_cooldowns

    def test_severity_cooldown_values(self):
        config = DeduplicationConfig()
        assert config.severity_cooldowns["critical"] == 5
        assert config.severity_cooldowns["warning"] == 15
        assert config.severity_cooldowns["info"] == 60


# =============================================================================
# AlertDeduplicator Tests
# =============================================================================


class TestAlertDeduplicator:
    def setup_method(self):
        self.dedup = AlertDeduplicator(
            window_minutes=15,
            max_alerts_per_window=3,
            severity_cooldowns={"critical": 5, "warning": 15, "info": 60},
        )

    def test_first_alert_passes(self):
        result = self.dedup.should_alert("test_alert_1", severity="warning")
        assert result is True

    def test_second_alert_within_cooldown_suppressed(self):
        self.dedup.should_alert("dup_alert_1", severity="warning")
        result = self.dedup.should_alert("dup_alert_1", severity="warning")
        assert result is False

    def test_different_alerts_both_pass(self):
        r1 = self.dedup.should_alert("alert_a", severity="warning")
        r2 = self.dedup.should_alert("alert_b", severity="warning")
        assert r1 is True
        assert r2 is True

    def test_force_send_bypasses_suppression(self):
        self.dedup.should_alert("force_alert_1", severity="warning")
        # Second time within cooldown
        result = self.dedup.should_alert("force_alert_1", severity="warning", force=True)
        assert result is True

    def test_labels_create_different_fingerprints(self):
        r1 = self.dedup.should_alert("alert_with_labels", labels={"service": "api"})
        r2 = self.dedup.should_alert("alert_with_labels", labels={"service": "worker"})
        assert r1 is True
        assert r2 is True

    def test_max_alerts_per_window_exceeded(self):
        """Test that max alerts per window is enforced once count is exceeded."""
        dedup = AlertDeduplicator(
            window_minutes=60,
            max_alerts_per_window=1,
            severity_cooldowns={"warning": 0},  # No cooldown
        )
        # First alert passes
        r1 = dedup.should_alert("max_test", severity="warning")
        assert r1 is True

        # Clear suppression window so the second call isn't suppressed by cooldown
        fp = list(dedup._alerts.keys())[0] if dedup._alerts else None
        if fp:
            dedup._suppression_windows.clear()

        # Second alert: count becomes 2, sent_count = 2 > max=1, should be suppressed
        r2 = dedup.should_alert("max_test", severity="warning")
        assert r2 is False

    def test_on_aggregated_callback(self):
        aggregated_records = []
        dedup = AlertDeduplicator(
            window_minutes=15,
            severity_cooldowns={"warning": 60},
            on_aggregated=aggregated_records.append,
        )
        dedup.should_alert("cb_alert", severity="warning")
        # Second one should be suppressed and callback called
        dedup.should_alert("cb_alert", severity="warning")
        assert len(aggregated_records) > 0

    def test_add_suppression_specific_severity(self):
        self.dedup.add_suppression("suppressed_alert", duration_minutes=60, severity="critical")
        result = self.dedup.should_alert("suppressed_alert", severity="critical")
        assert result is False

    def test_add_suppression_all_severities(self):
        self.dedup.add_suppression("suppressed_all", duration_minutes=60)
        r1 = self.dedup.should_alert("suppressed_all", severity="critical")
        r2 = self.dedup.should_alert("suppressed_all", severity="warning")
        r3 = self.dedup.should_alert("suppressed_all", severity="info")
        assert r1 is False
        assert r2 is False
        assert r3 is False

    def test_clear_suppression_specific_severity(self):
        self.dedup.add_suppression("clear_test", duration_minutes=60, severity="warning")
        self.dedup.clear_suppression("clear_test", severity="warning")
        result = self.dedup.should_alert("clear_test", severity="warning")
        assert result is True

    def test_clear_suppression_all_severities(self):
        self.dedup.add_suppression("clear_all_test", duration_minutes=60)
        self.dedup.clear_suppression("clear_all_test")
        result = self.dedup.should_alert("clear_all_test", severity="warning")
        assert result is True

    def test_clear_nonexistent_suppression(self):
        # Should not raise
        self.dedup.clear_suppression("nonexistent_alert", severity="warning")
        self.dedup.clear_suppression("nonexistent_alert")

    def test_get_active_alerts_empty(self):
        dedup = AlertDeduplicator()
        assert dedup.get_active_alerts() == []

    def test_get_active_alerts_returns_recent_alerts(self):
        dedup = AlertDeduplicator(window_minutes=15)
        dedup.should_alert("active_alert_1", severity="critical")
        alerts = dedup.get_active_alerts()
        assert len(alerts) >= 1
        names = [a.alert_name for a in alerts]
        assert "active_alert_1" in names

    def test_get_suppressed_alerts(self):
        dedup = AlertDeduplicator(severity_cooldowns={"critical": 60})
        dedup.should_alert("suppressed_query", severity="critical")
        suppressed = dedup.get_suppressed_alerts()
        assert len(suppressed) > 0

    def test_cleanup_removes_old_records(self):
        dedup = AlertDeduplicator(window_minutes=1)
        dedup.should_alert("old_alert", severity="warning")
        # Manually age the record
        fp = list(dedup._alerts.keys())[0]
        dedup._alerts[fp].last_seen = datetime.now(UTC) - timedelta(minutes=5)
        dedup._suppression_windows[fp] = datetime.now(UTC) - timedelta(minutes=5)
        dedup.cleanup()
        assert fp not in dedup._alerts

    def test_fingerprint_consistency(self):
        fp1 = self.dedup._create_fingerprint("alert", "critical", {"k": "v"})
        fp2 = self.dedup._create_fingerprint("alert", "critical", {"k": "v"})
        assert fp1 == fp2

    def test_fingerprint_differs_by_labels(self):
        fp1 = self.dedup._create_fingerprint("alert", "warning", {"env": "prod"})
        fp2 = self.dedup._create_fingerprint("alert", "warning", {"env": "staging"})
        assert fp1 != fp2

    def test_window_expired_resets_alert(self):
        """Test that alert in expired window is reset."""
        dedup = AlertDeduplicator(
            window_minutes=1,
            max_alerts_per_window=5,
            severity_cooldowns={"warning": 0},
        )
        # First alert
        dedup.should_alert("window_test", severity="warning")

        # Age the record beyond window
        fp = list(dedup._alerts.keys())[0]
        dedup._alerts[fp].first_seen = datetime.now(UTC) - timedelta(minutes=5)

        # Clear suppression so it doesn't block
        dedup._suppression_windows.clear()

        # New alert in fresh window
        result = dedup.should_alert("window_test", severity="warning")
        assert result is True


# =============================================================================
# Global Functions Tests
# =============================================================================


class TestGlobalAlertFunctions:
    def test_get_alert_deduplicator_returns_instance(self):
        d = get_alert_deduplicator()
        assert isinstance(d, AlertDeduplicator)

    def test_should_alert_helper(self):
        # Just ensure it runs without error
        result = should_alert("global_alert_test_xyz", severity="info")
        assert isinstance(result, bool)
