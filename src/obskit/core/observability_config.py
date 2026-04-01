"""
Structured configuration for the new ``configure_observability()`` API.

This module defines frozen dataclasses that group the flat
:class:`~obskit.config.ObskitSettings` fields into logical sections.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:  # pragma: no cover
    from obskit.config import ObskitSettings


@dataclass(frozen=True)
class ServiceConfig:
    """Service identification."""

    name: str = "unknown"
    environment: str = "development"
    version: str = "0.0.0"


@dataclass(frozen=True)
class TracingConfig:
    """OpenTelemetry tracing settings."""

    enabled: bool = True
    otlp_endpoint: str = "http://localhost:4317"
    otlp_insecure: bool = False
    sample_rate: float = 1.0
    export_queue_size: int = 2048
    export_batch_size: int = 512
    export_timeout: float = 30.0


@dataclass(frozen=True)
class MetricsConfig:
    """Prometheus metrics settings."""

    enabled: bool = True
    port: int = 9090
    path: str = "/metrics"
    use_histogram: bool = True
    use_summary: bool = False
    sample_rate: float = 1.0


@dataclass(frozen=True)
class LoggingConfig:
    """Structured logging settings."""

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    format: Literal["json", "console"] = "json"
    include_timestamp: bool = True
    sample_rate: float = 1.0


@dataclass(frozen=True)
class HealthConfig:
    """Health-check settings."""

    check_timeout: float = 5.0


@dataclass(frozen=True)
class ObservabilityConfig:
    """Immutable, structured configuration for obskit.

    Prefer creating instances via the :meth:`from_settings` or
    :meth:`from_kwargs` factory methods rather than calling the
    constructor directly.
    """

    service: ServiceConfig = field(default_factory=ServiceConfig)
    tracing: TracingConfig = field(default_factory=TracingConfig)
    metrics: MetricsConfig = field(default_factory=MetricsConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    health: HealthConfig = field(default_factory=HealthConfig)

    # ── Factory methods ───────────────────────────────────────────────

    @classmethod
    def from_settings(cls, settings: ObskitSettings) -> ObservabilityConfig:
        """Build an :class:`ObservabilityConfig` from a flat :class:`ObskitSettings`."""
        return cls(
            service=ServiceConfig(
                name=settings.service_name,
                environment=settings.environment,
                version=settings.version,
            ),
            tracing=TracingConfig(
                enabled=settings.tracing_enabled,
                otlp_endpoint=settings.otlp_endpoint,
                otlp_insecure=settings.otlp_insecure,
                sample_rate=settings.trace_sample_rate,
                export_queue_size=settings.trace_export_queue_size,
                export_batch_size=settings.trace_export_batch_size,
                export_timeout=settings.trace_export_timeout,
            ),
            metrics=MetricsConfig(
                enabled=settings.metrics_enabled,
                port=settings.metrics_port,
                path=settings.metrics_path,
                use_histogram=settings.use_histogram,
                use_summary=settings.use_summary,
                sample_rate=settings.metrics_sample_rate,
            ),
            logging=LoggingConfig(
                level=settings.log_level,
                format=settings.log_format,
                include_timestamp=settings.log_include_timestamp,
                sample_rate=settings.log_sample_rate,
            ),
            health=HealthConfig(
                check_timeout=settings.health_check_timeout,
            ),
        )

    @classmethod
    def from_kwargs(cls, **kwargs: object) -> ObservabilityConfig:
        """Build from flat keyword arguments (same names as :class:`ObskitSettings`)."""
        from obskit.config import ObskitSettings

        settings = ObskitSettings(**kwargs)  # type: ignore[arg-type]
        return cls.from_settings(settings)
