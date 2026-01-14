"""Tests for obskit self-monitoring metrics."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestObskitSelfMetrics:
    """Tests for ObskitSelfMetrics class."""

    def test_initialization(self) -> None:
        """Test self-metrics can be initialized."""
        from obskit.metrics.self_metrics import ObskitSelfMetrics, reset_self_metrics

        reset_self_metrics()
        metrics = ObskitSelfMetrics()
        assert metrics is not None
        assert metrics._version is not None

    def test_set_queue_depth(self) -> None:
        """Test setting queue depth."""
        from obskit.metrics.self_metrics import ObskitSelfMetrics, reset_self_metrics

        reset_self_metrics()
        metrics = ObskitSelfMetrics()
        metrics.set_queue_depth(100)
        # Should not raise

    def test_set_queue_capacity(self) -> None:
        """Test setting queue capacity."""
        from obskit.metrics.self_metrics import ObskitSelfMetrics, reset_self_metrics

        reset_self_metrics()
        metrics = ObskitSelfMetrics()
        metrics.set_queue_capacity(10000)
        # Should not raise

    def test_inc_dropped(self) -> None:
        """Test incrementing dropped counter."""
        from obskit.metrics.self_metrics import ObskitSelfMetrics, reset_self_metrics

        reset_self_metrics()
        metrics = ObskitSelfMetrics()
        metrics.inc_dropped("test_op", "queue_full")
        # Should not raise

    def test_inc_error(self) -> None:
        """Test incrementing error counter."""
        from obskit.metrics.self_metrics import ObskitSelfMetrics, reset_self_metrics

        reset_self_metrics()
        metrics = ObskitSelfMetrics()
        metrics.inc_error("async_recording", "TimeoutError")
        # Should not raise

    def test_get_snapshot(self) -> None:
        """Test getting metrics snapshot."""
        from obskit.metrics.self_metrics import ObskitSelfMetrics, reset_self_metrics

        reset_self_metrics()
        metrics = ObskitSelfMetrics()

        metrics.set_queue_depth(50)
        metrics.set_queue_capacity(1000)

        snapshot = metrics.get_snapshot()
        assert snapshot.queue_depth >= 0
        assert snapshot.queue_capacity >= 0
        assert snapshot.version is not None


class TestSelfMetricsFunctions:
    """Tests for self-metrics helper functions."""

    def test_get_self_metrics_singleton(self) -> None:
        """Test get_self_metrics returns singleton."""
        from obskit.metrics.self_metrics import get_self_metrics, reset_self_metrics

        reset_self_metrics()

        metrics1 = get_self_metrics()
        metrics2 = get_self_metrics()

        assert metrics1 is metrics2

    def test_record_dropped_metric(self) -> None:
        """Test record_dropped_metric helper."""
        from obskit.metrics.self_metrics import record_dropped_metric, reset_self_metrics

        reset_self_metrics()
        record_dropped_metric("test_operation", "queue_full")
        # Should not raise

    def test_record_dropped_metric_disabled(self) -> None:
        """Test record_dropped_metric when disabled."""
        from obskit.config import configure, reset_settings
        from obskit.metrics.self_metrics import record_dropped_metric, reset_self_metrics

        reset_settings()
        reset_self_metrics()

        configure(enable_self_metrics=False)
        record_dropped_metric("test_operation", "queue_full")
        # Should not raise

        reset_settings()

    def test_record_error(self) -> None:
        """Test record_error helper."""
        from obskit.metrics.self_metrics import record_error, reset_self_metrics

        reset_self_metrics()
        record_error("test_component", "TestError")
        # Should not raise

    def test_record_error_disabled(self) -> None:
        """Test record_error when disabled."""
        from obskit.config import configure, reset_settings
        from obskit.metrics.self_metrics import record_error, reset_self_metrics

        reset_settings()
        reset_self_metrics()

        configure(enable_self_metrics=False)
        record_error("test_component", "TestError")
        # Should not raise

        reset_settings()

    def test_update_queue_metrics(self) -> None:
        """Test update_queue_metrics helper."""
        from obskit.metrics.self_metrics import reset_self_metrics, update_queue_metrics

        reset_self_metrics()
        update_queue_metrics(depth=100, capacity=10000)
        # Should not raise

    def test_update_queue_metrics_disabled(self) -> None:
        """Test update_queue_metrics when disabled."""
        from obskit.config import configure, reset_settings
        from obskit.metrics.self_metrics import reset_self_metrics, update_queue_metrics

        reset_settings()
        reset_self_metrics()

        configure(enable_self_metrics=False)
        update_queue_metrics(depth=100, capacity=10000)
        # Should not raise

        reset_settings()

    def test_reset_self_metrics(self) -> None:
        """Test reset_self_metrics clears singleton."""
        from obskit.metrics.self_metrics import (
            _self_metrics,
            reset_self_metrics,
        )

        # Just verify reset doesn't raise and clears the global
        reset_self_metrics()
        # After reset, the module-level _self_metrics should be None
        import obskit.metrics.self_metrics as module

        assert module._self_metrics is None


class TestSelfMetricsWithoutPrometheus:
    """Test self-metrics when Prometheus is not available."""

    def test_metrics_without_prometheus(self) -> None:
        """Test self-metrics gracefully handles missing Prometheus."""
        from obskit.metrics.self_metrics import reset_self_metrics

        reset_self_metrics()

        with patch("obskit.metrics.self_metrics.PROMETHEUS_AVAILABLE", False):
            from obskit.metrics.self_metrics import ObskitSelfMetrics

            metrics = ObskitSelfMetrics()
            metrics.set_queue_depth(100)
            metrics.set_queue_capacity(10000)
            metrics.inc_dropped("test", "reason")
            metrics.inc_error("component", "error")

            snapshot = metrics.get_snapshot()
            assert snapshot.queue_depth == 0
            assert snapshot.queue_capacity == 0
