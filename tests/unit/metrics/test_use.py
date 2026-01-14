"""Tests for obskit.metrics.use module."""

import pytest
from unittest.mock import MagicMock, patch


class TestUSEMetrics:
    """Tests for USEMetrics class."""

    def setup_method(self):
        """Reset state before each test."""
        from obskit.metrics.use import reset_use_metrics
        reset_use_metrics()

    def teardown_method(self):
        """Clean up after each test."""
        from obskit.metrics.use import reset_use_metrics
        reset_use_metrics()

    @patch("obskit.metrics.use.get_registry")
    @patch("obskit.metrics.use.Gauge")
    @patch("obskit.metrics.use.Counter")
    def test_init(self, mock_counter, mock_gauge, mock_registry):
        """Test USEMetrics initialization."""
        from obskit.metrics.use import USEMetrics
        
        mock_registry.return_value = MagicMock()
        
        metrics = USEMetrics("server")
        
        assert metrics.name == "server"
        # Should create 2 gauges (utilization, saturation) and 1 counter (errors)
        assert mock_gauge.call_count == 2
        assert mock_counter.call_count == 1

    @patch("obskit.metrics.use.get_registry")
    @patch("obskit.metrics.use.Gauge")
    @patch("obskit.metrics.use.Counter")
    def test_set_utilization(self, mock_counter, mock_gauge, mock_registry):
        """Test setting utilization metric."""
        from obskit.metrics.use import USEMetrics
        
        mock_registry.return_value = MagicMock()
        mock_gauge_instance = MagicMock()
        mock_labeled_gauge = MagicMock()
        mock_gauge_instance.labels.return_value = mock_labeled_gauge
        mock_gauge.return_value = mock_gauge_instance
        
        metrics = USEMetrics("server")
        metrics.set_utilization("cpu", 0.75)
        
        mock_gauge_instance.labels.assert_called_with(resource="cpu")
        mock_labeled_gauge.set.assert_called_with(0.75)

    @patch("obskit.metrics.use.get_registry")
    @patch("obskit.metrics.use.Gauge")
    @patch("obskit.metrics.use.Counter")
    def test_set_saturation(self, mock_counter, mock_gauge, mock_registry):
        """Test setting saturation metric."""
        from obskit.metrics.use import USEMetrics
        
        mock_registry.return_value = MagicMock()
        mock_gauge_instance = MagicMock()
        mock_labeled_gauge = MagicMock()
        mock_gauge_instance.labels.return_value = mock_labeled_gauge
        mock_gauge.return_value = mock_gauge_instance
        
        metrics = USEMetrics("server")
        metrics.set_saturation("cpu", 5)
        
        mock_labeled_gauge.set.assert_called_with(5)

    @patch("obskit.metrics.use.get_registry")
    @patch("obskit.metrics.use.Gauge")
    @patch("obskit.metrics.use.Counter")
    def test_inc_error(self, mock_counter, mock_gauge, mock_registry):
        """Test incrementing error counter."""
        from obskit.metrics.use import USEMetrics
        
        mock_registry.return_value = MagicMock()
        mock_counter_instance = MagicMock()
        mock_labeled_counter = MagicMock()
        mock_counter_instance.labels.return_value = mock_labeled_counter
        mock_counter.return_value = mock_counter_instance
        
        metrics = USEMetrics("server")
        metrics.inc_error("disk", "read_error", 3)
        
        mock_counter_instance.labels.assert_called_with(resource="disk", error_type="read_error")
        mock_labeled_counter.inc.assert_called_with(3)

    @patch("obskit.metrics.use.get_registry")
    @patch("obskit.metrics.use.Gauge")
    @patch("obskit.metrics.use.Counter")
    def test_inc_error_default_count(self, mock_counter, mock_gauge, mock_registry):
        """Test incrementing error counter with default count."""
        from obskit.metrics.use import USEMetrics
        
        mock_registry.return_value = MagicMock()
        mock_counter_instance = MagicMock()
        mock_labeled_counter = MagicMock()
        mock_counter_instance.labels.return_value = mock_labeled_counter
        mock_counter.return_value = mock_counter_instance
        
        metrics = USEMetrics("server")
        metrics.inc_error("network", "timeout")
        
        mock_labeled_counter.inc.assert_called_with(1)

    @patch("obskit.metrics.use.get_registry")
    @patch("obskit.metrics.use.Gauge")
    @patch("obskit.metrics.use.Counter")
    def test_observe_all(self, mock_counter, mock_gauge, mock_registry):
        """Test observing all metrics at once."""
        from obskit.metrics.use import USEMetrics
        
        mock_registry.return_value = MagicMock()
        mock_gauge_instance = MagicMock()
        mock_labeled_gauge = MagicMock()
        mock_gauge_instance.labels.return_value = mock_labeled_gauge
        mock_gauge.return_value = mock_gauge_instance
        
        mock_counter_instance = MagicMock()
        mock_labeled_counter = MagicMock()
        mock_counter_instance.labels.return_value = mock_labeled_counter
        mock_counter.return_value = mock_counter_instance
        
        metrics = USEMetrics("database_pool")
        metrics.observe_all(
            resource="connections",
            utilization=0.80,
            saturation=3,
            errors={"timeout": 1, "connection_failed": 2},
        )
        
        # Should call set on gauges and inc on counter for each error type
        assert mock_labeled_gauge.set.call_count >= 2
        assert mock_labeled_counter.inc.call_count == 2

    @patch("obskit.metrics.use.get_registry")
    @patch("obskit.metrics.use.Gauge")
    @patch("obskit.metrics.use.Counter")
    def test_observe_all_partial(self, mock_counter, mock_gauge, mock_registry):
        """Test observing some metrics."""
        from obskit.metrics.use import USEMetrics
        
        mock_registry.return_value = MagicMock()
        mock_gauge_instance = MagicMock()
        mock_labeled_gauge = MagicMock()
        mock_gauge_instance.labels.return_value = mock_labeled_gauge
        mock_gauge.return_value = mock_gauge_instance
        
        metrics = USEMetrics("server")
        metrics.observe_all(
            resource="cpu",
            utilization=0.50,
        )
        
        mock_labeled_gauge.set.assert_called_once_with(0.50)


class TestCreateSystemMetrics:
    """Tests for create_system_metrics function."""

    def setup_method(self):
        """Reset state before each test."""
        from obskit.metrics.use import reset_use_metrics
        reset_use_metrics()

    @patch("obskit.metrics.use.get_registry")
    @patch("obskit.metrics.use.Gauge")
    @patch("obskit.metrics.use.Counter")
    def test_create_system_metrics(self, mock_counter, mock_gauge, mock_registry):
        """Test creating system metrics."""
        from obskit.metrics.use import create_system_metrics
        
        mock_registry.return_value = MagicMock()
        
        metrics = create_system_metrics()
        
        assert "cpu" in metrics
        assert "memory" in metrics
        assert "disk" in metrics
        assert "network" in metrics


class TestGetUseMetrics:
    """Tests for get_use_metrics function."""

    def setup_method(self):
        """Reset state before each test."""
        from obskit.metrics.use import reset_use_metrics
        reset_use_metrics()

    def teardown_method(self):
        """Clean up after each test."""
        from obskit.metrics.use import reset_use_metrics
        reset_use_metrics()

    @patch("obskit.metrics.use.get_registry")
    @patch("obskit.metrics.use.Gauge")
    @patch("obskit.metrics.use.Counter")
    def test_get_use_metrics_creates_new(self, mock_counter, mock_gauge, mock_registry):
        """Test getting metrics creates new instance."""
        from obskit.metrics.use import get_use_metrics
        
        mock_registry.return_value = MagicMock()
        
        metrics = get_use_metrics("test_resource")
        
        assert metrics is not None
        assert metrics.name == "test_resource"

    @patch("obskit.metrics.use.get_registry")
    @patch("obskit.metrics.use.Gauge")
    @patch("obskit.metrics.use.Counter")
    def test_get_use_metrics_returns_same(self, mock_counter, mock_gauge, mock_registry):
        """Test getting metrics returns same instance."""
        from obskit.metrics.use import get_use_metrics
        
        mock_registry.return_value = MagicMock()
        
        metrics1 = get_use_metrics("test_resource")
        metrics2 = get_use_metrics("test_resource")
        
        assert metrics1 is metrics2


class TestResetUseMetrics:
    """Tests for reset_use_metrics function."""

    @patch("obskit.metrics.use.get_registry")
    @patch("obskit.metrics.use.Gauge")
    @patch("obskit.metrics.use.Counter")
    def test_reset_clears_cache(self, mock_counter, mock_gauge, mock_registry):
        """Test reset clears the metrics cache."""
        from obskit.metrics.use import get_use_metrics, reset_use_metrics
        
        mock_registry.return_value = MagicMock()
        
        metrics1 = get_use_metrics("test_resource")
        reset_use_metrics()
        metrics2 = get_use_metrics("test_resource")
        
        # After reset, should get a new instance
        assert metrics1 is not metrics2

