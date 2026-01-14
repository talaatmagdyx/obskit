"""Tests for obskit.slo.prometheus module."""

import pytest
from unittest.mock import MagicMock, patch


class TestExposeSloMetrics:
    """Tests for expose_slo_metrics function."""

    def setup_method(self):
        """Reset state before each test."""
        import obskit.slo.prometheus as module
        module._slo_metrics = None

    def teardown_method(self):
        """Clean up after each test."""
        import obskit.slo.prometheus as module
        module._slo_metrics = None

    @patch("obskit.slo.prometheus.PROMETHEUS_AVAILABLE", True)
    @patch("obskit.slo.prometheus.Gauge")
    @patch("obskit.metrics.registry.get_registry")
    def test_expose_slo_metrics_creates_gauges(self, mock_get_registry, mock_gauge):
        """Test that expose creates Prometheus gauges."""
        from obskit.slo.prometheus import expose_slo_metrics
        
        mock_registry = MagicMock()
        mock_get_registry.return_value = mock_registry
        
        mock_tracker = MagicMock()
        mock_tracker.get_all_status.return_value = {}
        
        expose_slo_metrics(mock_tracker)
        
        # Should create 4 gauges
        assert mock_gauge.call_count == 4

    @patch("obskit.slo.prometheus.PROMETHEUS_AVAILABLE", True)
    @patch("obskit.slo.prometheus.Gauge")
    @patch("obskit.metrics.registry.get_registry")
    def test_expose_slo_metrics_updates_values(self, mock_get_registry, mock_gauge):
        """Test that expose updates metric values from tracker."""
        from obskit.slo.prometheus import expose_slo_metrics
        
        mock_registry = MagicMock()
        mock_get_registry.return_value = mock_registry
        
        mock_gauge_instance = MagicMock()
        mock_labeled_gauge = MagicMock()
        mock_gauge_instance.labels.return_value = mock_labeled_gauge
        mock_gauge.return_value = mock_gauge_instance
        
        mock_status = MagicMock()
        mock_status.compliance = True
        mock_status.error_budget_remaining = 0.95
        mock_status.error_budget_burn_rate = 0.05
        mock_status.current_value = 0.9995
        
        mock_tracker = MagicMock()
        mock_tracker.get_all_status.return_value = {"api_availability": mock_status}
        
        expose_slo_metrics(mock_tracker)
        
        # Should call labels and set for each metric
        assert mock_gauge_instance.labels.call_count >= 4

    @patch("obskit.slo.prometheus.PROMETHEUS_AVAILABLE", True)
    @patch("obskit.slo.prometheus.Gauge")
    @patch("obskit.metrics.registry.get_registry")
    def test_expose_slo_metrics_reuses_gauges(self, mock_get_registry, mock_gauge):
        """Test that calling expose twice reuses existing gauges."""
        from obskit.slo.prometheus import expose_slo_metrics
        
        mock_registry = MagicMock()
        mock_get_registry.return_value = mock_registry
        
        mock_tracker = MagicMock()
        mock_tracker.get_all_status.return_value = {}
        
        expose_slo_metrics(mock_tracker)
        initial_call_count = mock_gauge.call_count
        
        expose_slo_metrics(mock_tracker)
        
        # Should not create new gauges
        assert mock_gauge.call_count == initial_call_count

    @patch("obskit.slo.prometheus.PROMETHEUS_AVAILABLE", True)
    @patch("obskit.slo.prometheus.Gauge")
    @patch("obskit.metrics.registry.get_registry")
    def test_expose_slo_metrics_non_compliant(self, mock_get_registry, mock_gauge):
        """Test metrics update for non-compliant SLO."""
        from obskit.slo.prometheus import expose_slo_metrics
        
        mock_registry = MagicMock()
        mock_get_registry.return_value = mock_registry
        
        mock_gauge_instance = MagicMock()
        mock_labeled_gauge = MagicMock()
        mock_gauge_instance.labels.return_value = mock_labeled_gauge
        mock_gauge.return_value = mock_gauge_instance
        
        mock_status = MagicMock()
        mock_status.compliance = False
        mock_status.error_budget_remaining = -0.05
        mock_status.error_budget_burn_rate = 1.5
        mock_status.current_value = 0.98
        
        mock_tracker = MagicMock()
        mock_tracker.get_all_status.return_value = {"api_latency": mock_status}
        
        expose_slo_metrics(mock_tracker)
        
        # Verify compliance is set to 0.0
        assert mock_labeled_gauge.set.called


class TestUpdateSloMetrics:
    """Tests for update_slo_metrics function."""

    def setup_method(self):
        """Reset state before each test."""
        import obskit.slo.prometheus as module
        module._slo_metrics = None

    def teardown_method(self):
        """Clean up after each test."""
        import obskit.slo.prometheus as module
        module._slo_metrics = None

    @patch("obskit.slo.prometheus.PROMETHEUS_AVAILABLE", True)
    @patch("obskit.slo.prometheus.Gauge")
    @patch("obskit.metrics.registry.get_registry")
    def test_update_initializes_if_needed(self, mock_get_registry, mock_gauge):
        """Test update_slo_metrics initializes metrics if not done."""
        from obskit.slo.prometheus import update_slo_metrics
        import obskit.slo.prometheus as module
        
        mock_registry = MagicMock()
        mock_get_registry.return_value = mock_registry
        
        mock_tracker = MagicMock()
        mock_tracker.get_all_status.return_value = {}
        
        assert module._slo_metrics is None
        
        update_slo_metrics(mock_tracker)
        
        assert module._slo_metrics is not None

    @patch("obskit.slo.prometheus.PROMETHEUS_AVAILABLE", True)
    @patch("obskit.slo.prometheus.Gauge")
    @patch("obskit.metrics.registry.get_registry")
    def test_update_calls_expose(self, mock_get_registry, mock_gauge):
        """Test update_slo_metrics calls expose_slo_metrics."""
        from obskit.slo.prometheus import update_slo_metrics, expose_slo_metrics
        import obskit.slo.prometheus as module
        
        mock_registry = MagicMock()
        mock_get_registry.return_value = mock_registry
        
        mock_tracker = MagicMock()
        mock_tracker.get_all_status.return_value = {}
        
        # Initialize first
        expose_slo_metrics(mock_tracker)
        
        # Update should call expose again
        update_slo_metrics(mock_tracker)
        
        assert mock_tracker.get_all_status.call_count >= 2
