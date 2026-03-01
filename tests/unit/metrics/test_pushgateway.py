"""Tests for obskit.metrics.pushgateway module."""

from unittest.mock import MagicMock, patch

import pytest


class TestPushgatewayExporter:
    """Tests for PushgatewayExporter class."""

    def setup_method(self):
        """Reset state before each test."""

    @patch("obskit.metrics.pushgateway.PUSHGATEWAY_AVAILABLE", True)
    @patch("obskit.metrics.pushgateway.CollectorRegistry")
    def test_init(self, mock_registry):
        """Test PushgatewayExporter initialization."""
        from obskit.metrics.pushgateway import PushgatewayExporter

        mock_registry.return_value = MagicMock()

        exporter = PushgatewayExporter(
            gateway_url="http://pushgateway:9091",
            job_name="test_job",
        )

        assert exporter.gateway_url == "http://pushgateway:9091"
        assert exporter.job_name == "test_job"
        assert exporter.use_add is False
        assert exporter.timeout == pytest.approx(30.0)

    @patch("obskit.metrics.pushgateway.PUSHGATEWAY_AVAILABLE", True)
    @patch("obskit.metrics.pushgateway.CollectorRegistry")
    def test_init_with_custom_params(self, mock_registry):
        """Test initialization with custom parameters."""
        from obskit.metrics.pushgateway import PushgatewayExporter

        mock_registry.return_value = MagicMock()
        custom_registry = MagicMock()

        exporter = PushgatewayExporter(
            gateway_url="http://pushgateway:9091/",
            job_name="test_job",
            registry=custom_registry,
            use_add=True,
            timeout=60.0,
        )

        assert exporter.gateway_url == "http://pushgateway:9091"  # Trailing slash removed
        assert exporter.use_add is True
        assert exporter.timeout == pytest.approx(60.0)

    @patch("obskit.metrics.pushgateway.PUSHGATEWAY_AVAILABLE", True)
    @patch("obskit.metrics.pushgateway.CollectorRegistry")
    @patch("obskit.metrics.pushgateway.push_to_gateway")
    def test_push(self, mock_push, mock_registry):
        """Test pushing metrics."""
        from obskit.metrics.pushgateway import PushgatewayExporter

        mock_registry_instance = MagicMock()
        mock_registry.return_value = mock_registry_instance

        exporter = PushgatewayExporter(
            gateway_url="http://pushgateway:9091",
            job_name="test_job",
        )

        exporter.push()

        mock_push.assert_called_once_with(
            "http://pushgateway:9091",
            job="test_job",
            registry=mock_registry_instance,
            grouping_key={},
            timeout=30.0,
        )

    @patch("obskit.metrics.pushgateway.PUSHGATEWAY_AVAILABLE", True)
    @patch("obskit.metrics.pushgateway.CollectorRegistry")
    @patch("obskit.metrics.pushgateway.pushadd_to_gateway")
    def test_push_with_add(self, mock_pushadd, mock_registry):
        """Test pushing metrics with use_add=True."""
        from obskit.metrics.pushgateway import PushgatewayExporter

        mock_registry_instance = MagicMock()
        mock_registry.return_value = mock_registry_instance

        exporter = PushgatewayExporter(
            gateway_url="http://pushgateway:9091",
            job_name="test_job",
            use_add=True,
        )

        exporter.push(grouping_key={"instance": "worker-1"})

        mock_pushadd.assert_called_once()

    @patch("obskit.metrics.pushgateway.PUSHGATEWAY_AVAILABLE", True)
    @patch("obskit.metrics.pushgateway.CollectorRegistry")
    @patch("obskit.metrics.pushgateway.push_to_gateway")
    def test_push_failure(self, mock_push, mock_registry):
        """Test push failure handling."""
        from obskit.metrics.pushgateway import PushgatewayExporter

        mock_registry.return_value = MagicMock()
        mock_push.side_effect = Exception("Connection refused")

        exporter = PushgatewayExporter(
            gateway_url="http://pushgateway:9091",
            job_name="test_job",
        )

        with pytest.raises(Exception, match="Connection refused"):
            exporter.push()

    @patch("obskit.metrics.pushgateway.PUSHGATEWAY_AVAILABLE", True)
    @patch("obskit.metrics.pushgateway.CollectorRegistry")
    @patch("obskit.metrics.pushgateway.delete_from_gateway")
    def test_delete(self, mock_delete, mock_registry):
        """Test deleting metrics."""
        from obskit.metrics.pushgateway import PushgatewayExporter

        mock_registry.return_value = MagicMock()

        exporter = PushgatewayExporter(
            gateway_url="http://pushgateway:9091",
            job_name="test_job",
        )

        exporter.delete(grouping_key={"instance": "worker-1"})

        mock_delete.assert_called_once()

    @patch("obskit.metrics.pushgateway.PUSHGATEWAY_AVAILABLE", True)
    @patch("obskit.metrics.pushgateway.CollectorRegistry")
    @patch("obskit.metrics.pushgateway.delete_from_gateway")
    def test_delete_failure(self, mock_delete, mock_registry):
        """Test delete failure handling."""
        from obskit.metrics.pushgateway import PushgatewayExporter

        mock_registry.return_value = MagicMock()
        mock_delete.side_effect = Exception("Not found")

        exporter = PushgatewayExporter(
            gateway_url="http://pushgateway:9091",
            job_name="test_job",
        )

        with pytest.raises(Exception, match="Not found"):
            exporter.delete()

    @patch("obskit.metrics.pushgateway.PUSHGATEWAY_AVAILABLE", True)
    @patch("obskit.metrics.pushgateway.CollectorRegistry")
    @patch("obskit.metrics.pushgateway.Gauge")
    def test_record_gauge(self, mock_gauge_class, mock_registry):
        """Test recording gauge metric."""
        from obskit.metrics.pushgateway import PushgatewayExporter

        mock_registry.return_value = MagicMock()
        mock_gauge = MagicMock()
        mock_gauge_class.return_value = mock_gauge

        exporter = PushgatewayExporter(
            gateway_url="http://pushgateway:9091",
            job_name="test_job",
        )

        exporter.record_gauge("test_metric", 42.0, "Test metric")

        mock_gauge.set.assert_called_once_with(42.0)

    @patch("obskit.metrics.pushgateway.PUSHGATEWAY_AVAILABLE", True)
    @patch("obskit.metrics.pushgateway.CollectorRegistry")
    @patch("obskit.metrics.pushgateway.Gauge")
    def test_record_gauge_with_labels(self, mock_gauge_class, mock_registry):
        """Test recording gauge metric with labels."""
        from obskit.metrics.pushgateway import PushgatewayExporter

        mock_registry.return_value = MagicMock()
        mock_gauge = MagicMock()
        mock_labeled_gauge = MagicMock()
        mock_gauge.labels.return_value = mock_labeled_gauge
        mock_gauge_class.return_value = mock_gauge

        exporter = PushgatewayExporter(
            gateway_url="http://pushgateway:9091",
            job_name="test_job",
        )

        exporter.record_gauge(
            "test_metric",
            42.0,
            labels={"env": "prod"},
        )

        mock_gauge.labels.assert_called_once_with(env="prod")
        mock_labeled_gauge.set.assert_called_once_with(42.0)

    @patch("obskit.metrics.pushgateway.PUSHGATEWAY_AVAILABLE", True)
    @patch("obskit.metrics.pushgateway.CollectorRegistry")
    @patch("obskit.metrics.pushgateway.Counter")
    def test_record_counter(self, mock_counter_class, mock_registry):
        """Test recording counter metric."""
        from obskit.metrics.pushgateway import PushgatewayExporter

        mock_registry.return_value = MagicMock()
        mock_counter = MagicMock()
        mock_counter_class.return_value = mock_counter

        exporter = PushgatewayExporter(
            gateway_url="http://pushgateway:9091",
            job_name="test_job",
        )

        exporter.record_counter("test_counter", 5)

        mock_counter.inc.assert_called_once_with(5)

    @patch("obskit.metrics.pushgateway.PUSHGATEWAY_AVAILABLE", True)
    @patch("obskit.metrics.pushgateway.CollectorRegistry")
    @patch("obskit.metrics.pushgateway.Counter")
    def test_record_counter_with_labels(self, mock_counter_class, mock_registry):
        """Test recording counter metric with labels."""
        from obskit.metrics.pushgateway import PushgatewayExporter

        mock_registry.return_value = MagicMock()
        mock_counter = MagicMock()
        mock_labeled = MagicMock()
        mock_counter.labels.return_value = mock_labeled
        mock_counter_class.return_value = mock_counter

        exporter = PushgatewayExporter(
            gateway_url="http://pushgateway:9091",
            job_name="test_job",
        )

        exporter.record_counter("test_counter", 5, labels={"env": "prod"})

        mock_counter.labels.assert_called_once_with(env="prod")
        mock_labeled.inc.assert_called_once_with(5)

    @patch("obskit.metrics.pushgateway.PUSHGATEWAY_AVAILABLE", True)
    @patch("obskit.metrics.pushgateway.CollectorRegistry")
    @patch("obskit.metrics.pushgateway.Histogram")
    def test_record_histogram(self, mock_histogram_class, mock_registry):
        """Test recording histogram metric."""
        from obskit.metrics.pushgateway import PushgatewayExporter

        mock_registry.return_value = MagicMock()
        mock_histogram = MagicMock()
        mock_histogram_class.return_value = mock_histogram

        exporter = PushgatewayExporter(
            gateway_url="http://pushgateway:9091",
            job_name="test_job",
        )

        exporter.record_histogram("test_histogram", 0.5)

        mock_histogram.observe.assert_called_once_with(0.5)

    @patch("obskit.metrics.pushgateway.PUSHGATEWAY_AVAILABLE", True)
    @patch("obskit.metrics.pushgateway.CollectorRegistry")
    @patch("obskit.metrics.pushgateway.Histogram")
    def test_record_histogram_with_labels(self, mock_histogram_class, mock_registry):
        """Test recording histogram metric with labels."""
        from obskit.metrics.pushgateway import PushgatewayExporter

        mock_registry.return_value = MagicMock()
        mock_histogram = MagicMock()
        mock_labeled = MagicMock()
        mock_histogram.labels.return_value = mock_labeled
        mock_histogram_class.return_value = mock_histogram

        exporter = PushgatewayExporter(
            gateway_url="http://pushgateway:9091",
            job_name="test_job",
        )

        exporter.record_histogram("test_histogram", 0.5, labels={"env": "prod"})

        mock_histogram.labels.assert_called_once_with(env="prod")
        mock_labeled.observe.assert_called_once_with(0.5)

    @patch("obskit.metrics.pushgateway.PUSHGATEWAY_AVAILABLE", True)
    @patch("obskit.metrics.pushgateway.CollectorRegistry")
    @patch("obskit.metrics.pushgateway.Histogram")
    def test_record_histogram_with_buckets(self, mock_histogram_class, mock_registry):
        """Test recording histogram metric with custom buckets."""
        from obskit.metrics.pushgateway import PushgatewayExporter

        mock_registry.return_value = MagicMock()
        mock_histogram = MagicMock()
        mock_histogram_class.return_value = mock_histogram

        exporter = PushgatewayExporter(
            gateway_url="http://pushgateway:9091",
            job_name="test_job",
        )

        custom_buckets = (0.1, 0.5, 1.0, 5.0)
        exporter.record_histogram("test_histogram", 0.5, buckets=custom_buckets)

        # Verify buckets were passed to Histogram
        call_kwargs = mock_histogram_class.call_args.kwargs
        assert call_kwargs.get("buckets") == custom_buckets

    @patch("obskit.metrics.pushgateway.PUSHGATEWAY_AVAILABLE", True)
    @patch("obskit.metrics.pushgateway.CollectorRegistry")
    @patch("obskit.metrics.pushgateway.Gauge")
    def test_record_job_duration(self, mock_gauge_class, mock_registry):
        """Test recording job duration."""
        from obskit.metrics.pushgateway import PushgatewayExporter

        mock_registry.return_value = MagicMock()
        mock_gauge = MagicMock()
        mock_gauge_class.return_value = mock_gauge

        exporter = PushgatewayExporter(
            gateway_url="http://pushgateway:9091",
            job_name="test_job",
        )

        exporter.record_job_duration()

        mock_gauge.set.assert_called_once()

    @patch("obskit.metrics.pushgateway.PUSHGATEWAY_AVAILABLE", True)
    @patch("obskit.metrics.pushgateway.CollectorRegistry")
    @patch("obskit.metrics.pushgateway.Gauge")
    def test_record_job_timestamp(self, mock_gauge_class, mock_registry):
        """Test recording job timestamp."""
        from obskit.metrics.pushgateway import PushgatewayExporter

        mock_registry.return_value = MagicMock()
        mock_gauge = MagicMock()
        mock_gauge_class.return_value = mock_gauge

        exporter = PushgatewayExporter(
            gateway_url="http://pushgateway:9091",
            job_name="test_job",
        )

        exporter.record_job_timestamp()

        mock_gauge.set.assert_called_once()


class TestBatchJobMetrics:
    """Tests for batch_job_metrics context manager."""

    @patch("obskit.metrics.pushgateway.PUSHGATEWAY_AVAILABLE", True)
    @patch("obskit.metrics.pushgateway.CollectorRegistry")
    @patch("obskit.metrics.pushgateway.push_to_gateway")
    @patch("obskit.metrics.pushgateway.Gauge")
    def test_context_manager_success(self, mock_gauge_class, mock_push, mock_registry):
        """Test context manager with successful job."""
        from obskit.metrics.pushgateway import batch_job_metrics

        mock_registry.return_value = MagicMock()
        mock_gauge = MagicMock()
        mock_gauge_class.return_value = mock_gauge

        with batch_job_metrics(
            gateway_url="http://pushgateway:9091",
            job_name="test_job",
        ) as exporter:
            exporter.record_gauge("items_processed", 100)

        # Should push on exit
        mock_push.assert_called_once()

    @patch("obskit.metrics.pushgateway.PUSHGATEWAY_AVAILABLE", True)
    @patch("obskit.metrics.pushgateway.CollectorRegistry")
    @patch("obskit.metrics.pushgateway.push_to_gateway")
    @patch("obskit.metrics.pushgateway.Gauge")
    def test_context_manager_failure(self, mock_gauge_class, mock_push, mock_registry):
        """Test context manager with failed job."""
        from obskit.metrics.pushgateway import batch_job_metrics

        mock_registry.return_value = MagicMock()
        mock_gauge = MagicMock()
        mock_gauge_class.return_value = mock_gauge

        with pytest.raises(ValueError):
            with batch_job_metrics(
                gateway_url="http://pushgateway:9091",
                job_name="test_job",
            ):
                raise ValueError("Job failed")

        # Should still push on failure
        mock_push.assert_called_once()

    @patch("obskit.metrics.pushgateway.PUSHGATEWAY_AVAILABLE", True)
    @patch("obskit.metrics.pushgateway.CollectorRegistry")
    @patch("obskit.metrics.pushgateway.push_to_gateway")
    @patch("obskit.metrics.pushgateway.delete_from_gateway")
    @patch("obskit.metrics.pushgateway.Gauge")
    def test_context_manager_delete_on_success(
        self, mock_gauge_class, mock_delete, mock_push, mock_registry
    ):
        """Test context manager with delete_on_success."""
        from obskit.metrics.pushgateway import batch_job_metrics

        mock_registry.return_value = MagicMock()
        mock_gauge = MagicMock()
        mock_gauge_class.return_value = mock_gauge

        with batch_job_metrics(
            gateway_url="http://pushgateway:9091",
            job_name="test_job",
            delete_on_success=True,
        ):
            pass  # NOSONAR

        mock_push.assert_called_once()
        mock_delete.assert_called_once()
