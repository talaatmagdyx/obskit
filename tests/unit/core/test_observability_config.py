"""Tests for ObservabilityConfig dataclasses."""

from __future__ import annotations

import pytest

from obskit.config import ObskitSettings
from obskit.core.observability_config import (
    HealthConfig,
    LoggingConfig,
    MetricsConfig,
    ObservabilityConfig,
    ServiceConfig,
    TracingConfig,
)


class TestServiceConfig:
    def test_defaults(self) -> None:
        cfg = ServiceConfig()
        assert cfg.name == "unknown"
        assert cfg.environment == "development"
        assert cfg.version == "0.0.0"

    def test_custom(self) -> None:
        cfg = ServiceConfig(name="my-svc", environment="prod", version="1.2.3")
        assert cfg.name == "my-svc"

    def test_frozen(self) -> None:
        cfg = ServiceConfig()
        with pytest.raises(AttributeError):
            cfg.name = "oops"  # type: ignore[misc]


class TestTracingConfig:
    def test_defaults(self) -> None:
        cfg = TracingConfig()
        assert cfg.enabled is True
        assert cfg.otlp_endpoint == "http://localhost:4317"
        assert cfg.otlp_insecure is False
        assert cfg.sample_rate == 1.0
        assert cfg.export_queue_size == 2048
        assert cfg.export_batch_size == 512
        assert cfg.export_timeout == 30.0


class TestMetricsConfig:
    def test_defaults(self) -> None:
        cfg = MetricsConfig()
        assert cfg.enabled is True
        assert cfg.port == 9090
        assert cfg.path == "/metrics"
        assert cfg.use_histogram is True
        assert cfg.use_summary is False
        assert cfg.sample_rate == 1.0


class TestLoggingConfig:
    def test_defaults(self) -> None:
        cfg = LoggingConfig()
        assert cfg.level == "INFO"
        assert cfg.format == "json"
        assert cfg.include_timestamp is True
        assert cfg.sample_rate == 1.0


class TestHealthConfig:
    def test_defaults(self) -> None:
        cfg = HealthConfig()
        assert cfg.check_timeout == 5.0


class TestObservabilityConfig:
    def test_defaults(self) -> None:
        cfg = ObservabilityConfig()
        assert cfg.service.name == "unknown"
        assert cfg.tracing.enabled is True
        assert cfg.metrics.enabled is True
        assert cfg.logging.level == "INFO"
        assert cfg.health.check_timeout == 5.0

    def test_frozen(self) -> None:
        cfg = ObservabilityConfig()
        with pytest.raises(AttributeError):
            cfg.service = ServiceConfig(name="changed")  # type: ignore[misc]

    def test_from_settings(self) -> None:
        settings = ObskitSettings(
            service_name="test-svc",
            environment="staging",
            version="2.0.0",
            tracing_enabled=False,
            otlp_endpoint="http://tempo:4317",
            otlp_insecure=True,
            trace_sample_rate=0.5,
            trace_export_queue_size=1024,
            trace_export_batch_size=256,
            trace_export_timeout=10.0,
            metrics_enabled=True,
            metrics_port=8080,
            metrics_path="/prom",
            use_histogram=False,
            use_summary=True,
            metrics_sample_rate=0.9,
            log_level="DEBUG",
            log_format="console",
            log_include_timestamp=False,
            log_sample_rate=0.5,
            health_check_timeout=10.0,
        )
        cfg = ObservabilityConfig.from_settings(settings)

        assert cfg.service.name == "test-svc"
        assert cfg.service.environment == "staging"
        assert cfg.service.version == "2.0.0"

        assert cfg.tracing.enabled is False
        assert cfg.tracing.otlp_endpoint == "http://tempo:4317"
        assert cfg.tracing.otlp_insecure is True
        assert cfg.tracing.sample_rate == 0.5
        assert cfg.tracing.export_queue_size == 1024
        assert cfg.tracing.export_batch_size == 256
        assert cfg.tracing.export_timeout == 10.0

        assert cfg.metrics.enabled is True
        assert cfg.metrics.port == 8080
        assert cfg.metrics.path == "/prom"
        assert cfg.metrics.use_histogram is False
        assert cfg.metrics.use_summary is True
        assert cfg.metrics.sample_rate == 0.9

        assert cfg.logging.level == "DEBUG"
        assert cfg.logging.format == "console"
        assert cfg.logging.include_timestamp is False
        assert cfg.logging.sample_rate == 0.5

        assert cfg.health.check_timeout == 10.0

    def test_from_kwargs(self) -> None:
        cfg = ObservabilityConfig.from_kwargs(
            service_name="kwarg-svc",
            environment="production",
            log_level="ERROR",
        )
        assert cfg.service.name == "kwarg-svc"
        assert cfg.service.environment == "production"
        assert cfg.logging.level == "ERROR"
