"""Tests for obskit.metrics.otlp module."""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock


class TestOTLPMetricsExporter:
    """Tests for OTLPMetricsExporter class."""

    def setup_method(self):
        """Reset state before each test."""
        # Clear any cached modules
        pass

    @patch("obskit.metrics.otlp.OTLP_METRICS_AVAILABLE", True)
    @patch("obskit.metrics.otlp.Resource")
    @patch("obskit.metrics.otlp.GRPCMetricExporter")
    @patch("obskit.metrics.otlp.PeriodicExportingMetricReader")
    @patch("obskit.metrics.otlp.MeterProvider")
    @patch("obskit.metrics.otlp.otel_metrics")
    def test_init(self, mock_otel, mock_provider, mock_reader, mock_exporter, mock_resource):
        """Test OTLPMetricsExporter initialization."""
        from obskit.metrics.otlp import OTLPMetricsExporter
        
        exporter = OTLPMetricsExporter(
            endpoint="http://localhost:4317",
            service_name="test-service",
        )
        
        assert exporter.endpoint == "http://localhost:4317"
        assert exporter.service_name == "test-service"
        assert exporter.is_started is False

    @patch("obskit.metrics.otlp.OTLP_METRICS_AVAILABLE", True)
    @patch("obskit.metrics.otlp.Resource")
    @patch("obskit.metrics.otlp.GRPCMetricExporter")
    @patch("obskit.metrics.otlp.PeriodicExportingMetricReader")
    @patch("obskit.metrics.otlp.MeterProvider")
    @patch("obskit.metrics.otlp.otel_metrics")
    def test_init_with_custom_params(self, mock_otel, mock_provider, mock_reader, mock_exporter, mock_resource):
        """Test initialization with custom parameters."""
        from obskit.metrics.otlp import OTLPMetricsExporter
        
        exporter = OTLPMetricsExporter(
            endpoint="http://localhost:4317",
            service_name="test-service",
            service_version="1.0.0",
            environment="production",
            export_interval=30.0,
            use_grpc=True,
            insecure=False,
            headers={"Authorization": "Bearer token"},
            resource_attributes={"custom.attr": "value"},
            timeout=15.0,
        )
        
        assert exporter.service_version == "1.0.0"
        assert exporter.environment == "production"
        assert exporter.export_interval == 30.0
        assert exporter.use_grpc is True
        assert exporter.insecure is False
        assert exporter.timeout == 15.0

    @patch("obskit.metrics.otlp.OTLP_METRICS_AVAILABLE", True)
    @patch("obskit.metrics.otlp.Resource")
    @patch("obskit.metrics.otlp.GRPCMetricExporter")
    @patch("obskit.metrics.otlp.PeriodicExportingMetricReader")
    @patch("obskit.metrics.otlp.MeterProvider")
    @patch("obskit.metrics.otlp.otel_metrics")
    def test_start(self, mock_otel, mock_provider, mock_reader, mock_exporter, mock_resource):
        """Test starting the exporter."""
        from obskit.metrics.otlp import OTLPMetricsExporter
        
        mock_resource.create.return_value = MagicMock()
        mock_exporter_instance = MagicMock()
        mock_exporter.return_value = mock_exporter_instance
        mock_reader_instance = MagicMock()
        mock_reader.return_value = mock_reader_instance
        mock_provider_instance = MagicMock()
        mock_provider.return_value = mock_provider_instance
        
        exporter = OTLPMetricsExporter(
            endpoint="http://localhost:4317",
            service_name="test-service",
        )
        
        exporter.start()
        
        assert exporter.is_started is True
        mock_otel.set_meter_provider.assert_called_once()

    @patch("obskit.metrics.otlp.OTLP_METRICS_AVAILABLE", True)
    @patch("obskit.metrics.otlp.Resource")
    @patch("obskit.metrics.otlp.GRPCMetricExporter")
    @patch("obskit.metrics.otlp.PeriodicExportingMetricReader")
    @patch("obskit.metrics.otlp.MeterProvider")
    @patch("obskit.metrics.otlp.otel_metrics")
    def test_start_already_started(self, mock_otel, mock_provider, mock_reader, mock_exporter, mock_resource):
        """Test starting when already started."""
        from obskit.metrics.otlp import OTLPMetricsExporter
        
        mock_resource.create.return_value = MagicMock()
        
        exporter = OTLPMetricsExporter(
            endpoint="http://localhost:4317",
            service_name="test-service",
        )
        
        exporter.start()
        exporter.start()  # Should not raise, just warn
        
        assert exporter.is_started is True

    @patch("obskit.metrics.otlp.OTLP_METRICS_AVAILABLE", True)
    @patch("obskit.metrics.otlp.Resource")
    @patch("obskit.metrics.otlp.GRPCMetricExporter")
    @patch("obskit.metrics.otlp.PeriodicExportingMetricReader")
    @patch("obskit.metrics.otlp.MeterProvider")
    @patch("obskit.metrics.otlp.otel_metrics")
    def test_shutdown(self, mock_otel, mock_provider, mock_reader, mock_exporter, mock_resource):
        """Test shutdown."""
        from obskit.metrics.otlp import OTLPMetricsExporter
        
        mock_resource.create.return_value = MagicMock()
        mock_provider_instance = MagicMock()
        mock_provider.return_value = mock_provider_instance
        
        exporter = OTLPMetricsExporter(
            endpoint="http://localhost:4317",
            service_name="test-service",
        )
        
        exporter.start()
        exporter.shutdown()
        
        assert exporter.is_started is False
        mock_provider_instance.shutdown.assert_called_once()

    @patch("obskit.metrics.otlp.OTLP_METRICS_AVAILABLE", True)
    @patch("obskit.metrics.otlp.Resource")
    @patch("obskit.metrics.otlp.GRPCMetricExporter")
    @patch("obskit.metrics.otlp.PeriodicExportingMetricReader")
    @patch("obskit.metrics.otlp.MeterProvider")
    @patch("obskit.metrics.otlp.otel_metrics")
    def test_shutdown_not_started(self, mock_otel, mock_provider, mock_reader, mock_exporter, mock_resource):
        """Test shutdown when not started."""
        from obskit.metrics.otlp import OTLPMetricsExporter
        
        exporter = OTLPMetricsExporter(
            endpoint="http://localhost:4317",
            service_name="test-service",
        )
        
        exporter.shutdown()  # Should not raise
        assert exporter.is_started is False

    @patch("obskit.metrics.otlp.OTLP_METRICS_AVAILABLE", True)
    @patch("obskit.metrics.otlp.Resource")
    @patch("obskit.metrics.otlp.GRPCMetricExporter")
    @patch("obskit.metrics.otlp.PeriodicExportingMetricReader")
    @patch("obskit.metrics.otlp.MeterProvider")
    @patch("obskit.metrics.otlp.otel_metrics")
    def test_force_flush(self, mock_otel, mock_provider, mock_reader, mock_exporter, mock_resource):
        """Test force_flush."""
        from obskit.metrics.otlp import OTLPMetricsExporter
        
        mock_resource.create.return_value = MagicMock()
        mock_provider_instance = MagicMock()
        mock_provider_instance.force_flush.return_value = True
        mock_provider.return_value = mock_provider_instance
        
        exporter = OTLPMetricsExporter(
            endpoint="http://localhost:4317",
            service_name="test-service",
        )
        
        exporter.start()
        result = exporter.force_flush()
        
        assert result is True
        mock_provider_instance.force_flush.assert_called_once()

    @patch("obskit.metrics.otlp.OTLP_METRICS_AVAILABLE", True)
    @patch("obskit.metrics.otlp.Resource")
    @patch("obskit.metrics.otlp.GRPCMetricExporter")
    @patch("obskit.metrics.otlp.PeriodicExportingMetricReader")
    @patch("obskit.metrics.otlp.MeterProvider")
    @patch("obskit.metrics.otlp.otel_metrics")
    def test_force_flush_not_started(self, mock_otel, mock_provider, mock_reader, mock_exporter, mock_resource):
        """Test force_flush when not started."""
        from obskit.metrics.otlp import OTLPMetricsExporter
        
        exporter = OTLPMetricsExporter(
            endpoint="http://localhost:4317",
            service_name="test-service",
        )
        
        result = exporter.force_flush()
        
        assert result is False

    @patch("obskit.metrics.otlp.OTLP_METRICS_AVAILABLE", True)
    @patch("obskit.metrics.otlp.Resource")
    @patch("obskit.metrics.otlp.GRPCMetricExporter")
    @patch("obskit.metrics.otlp.PeriodicExportingMetricReader")
    @patch("obskit.metrics.otlp.MeterProvider")
    @patch("obskit.metrics.otlp.otel_metrics")
    def test_get_meter(self, mock_otel, mock_provider, mock_reader, mock_exporter, mock_resource):
        """Test get_meter."""
        from obskit.metrics.otlp import OTLPMetricsExporter
        
        mock_resource.create.return_value = MagicMock()
        mock_meter = MagicMock()
        mock_otel.get_meter.return_value = mock_meter
        
        exporter = OTLPMetricsExporter(
            endpoint="http://localhost:4317",
            service_name="test-service",
        )
        
        exporter.start()
        meter = exporter.get_meter("my_module", "1.0.0")
        
        mock_otel.get_meter.assert_called_with("my_module", "1.0.0")
        assert meter == mock_meter

    @patch("obskit.metrics.otlp.OTLP_METRICS_AVAILABLE", True)
    @patch("obskit.metrics.otlp.Resource")
    @patch("obskit.metrics.otlp.GRPCMetricExporter")
    @patch("obskit.metrics.otlp.PeriodicExportingMetricReader")
    @patch("obskit.metrics.otlp.MeterProvider")
    @patch("obskit.metrics.otlp.otel_metrics")
    def test_get_meter_not_started(self, mock_otel, mock_provider, mock_reader, mock_exporter, mock_resource):
        """Test get_meter when not started."""
        from obskit.metrics.otlp import OTLPMetricsExporter
        
        exporter = OTLPMetricsExporter(
            endpoint="http://localhost:4317",
            service_name="test-service",
        )
        
        with pytest.raises(RuntimeError, match="not started"):
            exporter.get_meter("my_module")

    @patch("obskit.metrics.otlp.OTLP_METRICS_AVAILABLE", True)
    @patch("obskit.metrics.otlp.HTTP_EXPORTER_AVAILABLE", True)
    @patch("obskit.metrics.otlp.Resource")
    @patch("obskit.metrics.otlp.HTTPMetricExporter")
    @patch("obskit.metrics.otlp.PeriodicExportingMetricReader")
    @patch("obskit.metrics.otlp.MeterProvider")
    @patch("obskit.metrics.otlp.otel_metrics")
    def test_http_exporter(self, mock_otel, mock_provider, mock_reader, mock_http_exporter, mock_resource):
        """Test using HTTP exporter instead of gRPC."""
        from obskit.metrics.otlp import OTLPMetricsExporter
        
        mock_resource.create.return_value = MagicMock()
        
        exporter = OTLPMetricsExporter(
            endpoint="http://localhost:4318/v1/metrics",
            service_name="test-service",
            use_grpc=False,
        )
        
        exporter.start()
        
        mock_http_exporter.assert_called_once()

