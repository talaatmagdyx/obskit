"""
Tests for obskit.alerts.slow_operation module.
"""

from __future__ import annotations

import time
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from obskit.alerts.slow_operation import (
    SlowOperationDetector,
    SlowOperationEvent,
    check_slow_operation,
)


# =============================================================================
# SlowOperationEvent Tests
# =============================================================================


class TestSlowOperationEvent:
    def test_init(self):
        event = SlowOperationEvent(
            operation="fetch_data",
            duration_ms=6000.0,
            threshold_ms=5000.0,
            timestamp=datetime.utcnow(),
            alert_id="abc123",
            component="api",
        )
        assert event.operation == "fetch_data"
        assert event.duration_ms == 6000.0
        assert event.threshold_ms == 5000.0
        assert event.component == "api"
        assert event.tenant_id is None
        assert event.context is None


# =============================================================================
# SlowOperationDetector Tests
# =============================================================================


class TestSlowOperationDetector:
    def setup_method(self):
        self.detector = SlowOperationDetector(
            threshold_ms=100.0,
            component="test_service",
            enable_metrics=False,
        )

    def test_init_defaults(self):
        detector = SlowOperationDetector()
        assert detector.default_threshold_ms == 5000.0
        assert detector.component == "service"

    def test_init_no_metrics(self):
        detector = SlowOperationDetector(enable_metrics=False)
        assert detector._metrics is None

    def test_init_with_metrics(self):
        detector = SlowOperationDetector(enable_metrics=True)
        assert detector._metrics is not None

    def test_track_fast_operation_no_alert(self):
        with self.detector.track("fast_op", threshold_ms=10000):
            pass  # Instant, well under threshold
        history = self.detector.get_history()
        assert len(history) == 0

    def test_track_slow_operation_recorded_in_history(self):
        # Make threshold very low to force detection
        with self.detector.track("slow_op", threshold_ms=0.001):
            time.sleep(0.01)  # 10ms > 0.001ms threshold
        history = self.detector.get_history()
        assert len(history) > 0
        assert history[0].operation == "slow_op"

    def test_track_slow_operation_with_context(self):
        with self.detector.track(
            "op_with_context",
            threshold_ms=0.001,
            tenant_id="tenant-123",
            context={"key": "value"},
        ):
            time.sleep(0.01)
        history = self.detector.get_history()
        assert len(history) > 0
        event = history[0]
        assert event.tenant_id == "tenant-123"
        assert event.context == {"key": "value"}

    def test_track_does_not_send_alert_when_disabled(self):
        """Track with send_alert=False should still record in history but not send alert."""
        with self.detector.track("op_no_alert", threshold_ms=0.001, send_alert=False):
            time.sleep(0.01)
        history = self.detector.get_history()
        assert len(history) > 0

    def test_history_size_limit(self):
        detector = SlowOperationDetector(
            threshold_ms=0.001,
            history_size=5,
            enable_metrics=False,
        )
        for i in range(10):
            with detector.track(f"op_{i}"):
                time.sleep(0.01)
        assert len(detector._history) <= 5

    def test_get_history_limit(self):
        detector = SlowOperationDetector(threshold_ms=0.001, enable_metrics=False)
        for i in range(15):
            with detector.track(f"op_{i}"):
                time.sleep(0.01)
        history = detector.get_history(limit=5)
        assert len(history) <= 5

    def test_get_stats_empty(self):
        detector = SlowOperationDetector(enable_metrics=False)
        stats = detector.get_stats()
        assert stats["total_events"] == 0
        assert stats["operations"] == {}

    def test_get_stats_with_events(self):
        detector = SlowOperationDetector(threshold_ms=0.001, enable_metrics=False)
        with detector.track("process_order"):
            time.sleep(0.01)
        with detector.track("process_order"):
            time.sleep(0.01)
        with detector.track("other_op"):
            time.sleep(0.01)
        stats = detector.get_stats()
        assert stats["total_events"] == 3
        assert "process_order" in stats["operations"]
        assert stats["operations"]["process_order"]["count"] == 2
        assert "max_ms" in stats["operations"]["process_order"]
        assert "min_ms" in stats["operations"]["process_order"]
        assert "avg_ms" in stats["operations"]["process_order"]

    def test_clear_history(self):
        detector = SlowOperationDetector(threshold_ms=0.001, enable_metrics=False)
        with detector.track("op"):
            time.sleep(0.01)
        assert len(detector._history) > 0
        detector.clear_history()
        assert len(detector._history) == 0

    def test_monitor_decorator_success(self):
        """Test that the monitor decorator wraps function correctly."""

        @self.detector.monitor("test_decorated_op", threshold_ms=10000)
        def fast_func():
            return "result"

        result = fast_func()
        assert result == "result"

    def test_monitor_decorator_slow_operation(self):
        """Test that the monitor decorator detects slow operations."""
        detector = SlowOperationDetector(threshold_ms=0.001, enable_metrics=False)

        @detector.monitor("decorated_slow_op")
        def slow_func():
            time.sleep(0.01)
            return "done"

        result = slow_func()
        assert result == "done"
        assert len(detector._history) > 0
        assert detector._history[0].operation == "decorated_slow_op"

    def test_monitor_decorator_preserves_args(self):
        @self.detector.monitor("arg_func", threshold_ms=10000)
        def add(x, y):
            return x + y

        result = add(3, 4)
        assert result == 7

    def test_handle_slow_operation_returns_alert_id(self):
        alert_id = self.detector._handle_slow_operation(
            operation="test_op",
            duration_ms=6000.0,
            threshold_ms=5000.0,
        )
        assert alert_id is not None
        assert isinstance(alert_id, str)

    def test_handle_slow_operation_with_webhook(self):
        """Test that webhook is called when configured."""
        mock_webhook = MagicMock()
        detector = SlowOperationDetector(enable_metrics=False)
        detector._webhook = mock_webhook
        detector._handle_slow_operation(
            operation="webhook_op",
            duration_ms=6000.0,
            threshold_ms=5000.0,
        )
        mock_webhook.fire_alert.assert_called_once()

    def test_handle_slow_operation_webhook_failure_handled(self):
        """Test that webhook failure is handled gracefully."""
        mock_webhook = MagicMock()
        mock_webhook.fire_alert.side_effect = Exception("Connection refused")
        detector = SlowOperationDetector(enable_metrics=False)
        detector._webhook = mock_webhook
        # Should not raise
        alert_id = detector._handle_slow_operation(
            operation="failing_webhook_op",
            duration_ms=6000.0,
            threshold_ms=5000.0,
        )
        assert alert_id is not None

    def test_default_threshold_used_when_no_override(self):
        """Test that default threshold is used when not overriding."""
        detector = SlowOperationDetector(threshold_ms=0.001, enable_metrics=False)
        with detector.track("default_threshold_op"):
            time.sleep(0.01)
        assert len(detector._history) > 0

    def test_with_metrics_enabled_records_metrics(self):
        """Test that metrics are recorded when enabled."""
        detector = SlowOperationDetector(
            threshold_ms=0.001,
            enable_metrics=True,
            component="metrics_test",
        )
        with patch.object(detector._metrics, "observe_request") as mock_observe:
            with detector.track("metrics_op"):
                time.sleep(0.01)
            mock_observe.assert_called_once()


# =============================================================================
# check_slow_operation Tests
# =============================================================================


class TestCheckSlowOperation:
    def test_fast_operation_returns_none(self):
        result = check_slow_operation("fast_op", duration_seconds=0.1, threshold_ms=5000)
        assert result is None

    def test_slow_operation_returns_alert_id(self):
        result = check_slow_operation("slow_op", duration_seconds=10.0, threshold_ms=5000)
        assert result is not None
        assert isinstance(result, str)

    def test_exactly_at_threshold_not_slow(self):
        result = check_slow_operation("boundary_op", duration_seconds=5.0, threshold_ms=5000)
        assert result is None  # 5000ms <= 5000ms threshold

    def test_just_above_threshold_is_slow(self):
        result = check_slow_operation(
            "just_above_op", duration_seconds=5.001, threshold_ms=5000
        )
        assert result is not None

    def test_with_tenant_id(self):
        result = check_slow_operation(
            "tenant_op",
            duration_seconds=10.0,
            threshold_ms=5000,
            tenant_id="tenant-xyz",
        )
        assert result is not None

    def test_with_context(self):
        result = check_slow_operation(
            "ctx_op",
            duration_seconds=10.0,
            threshold_ms=5000,
            context={"order_id": "123"},
        )
        assert result is not None

    def test_different_components(self):
        r1 = check_slow_operation("op", duration_seconds=10.0, component="api")
        r2 = check_slow_operation("op", duration_seconds=10.0, component="worker")
        # Both should return alert IDs
        assert r1 is not None
        assert r2 is not None
