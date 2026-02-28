"""
OTLP Metrics Exporter
======================

This module provides OpenTelemetry Protocol (OTLP) metrics export functionality,
enabling obskit to send metrics directly to OTLP-compatible backends like:

- OpenTelemetry Collector
- Grafana Cloud
- Honeycomb
- Datadog (via OTLP)
- New Relic (via OTLP)

Installation
------------
.. code-block:: bash

    pip install obskit[otlp-metrics]

Example - Basic Usage
---------------------
.. code-block:: python

    from obskit.metrics.otlp import OTLPMetricsExporter

    exporter = OTLPMetricsExporter(
        endpoint="http://localhost:4317",
        service_name="my-service",
        export_interval=60.0,
    )

    # Start periodic export
    exporter.start()

    # ... your application runs ...

    # Shutdown on exit
    exporter.shutdown()

Example - With Resource Attributes
-----------------------------------
.. code-block:: python

    from obskit.metrics.otlp import OTLPMetricsExporter

    exporter = OTLPMetricsExporter(
        endpoint="http://localhost:4317",
        service_name="my-service",
        service_version="1.0.0",
        environment="production",
        resource_attributes={
            "deployment.environment": "production",
            "service.namespace": "orders",
        },
    )

Example - gRPC with TLS
------------------------
.. code-block:: python

    from obskit.metrics.otlp import OTLPMetricsExporter

    exporter = OTLPMetricsExporter(
        endpoint="https://otlp.example.com:4317",
        service_name="my-service",
        use_grpc=True,
        insecure=False,
        headers={"Authorization": "Bearer <token>"},
    )

Example - HTTP (JSON/Protobuf)
-------------------------------
.. code-block:: python

    from obskit.metrics.otlp import OTLPMetricsExporter

    exporter = OTLPMetricsExporter(
        endpoint="http://localhost:4318/v1/metrics",
        service_name="my-service",
        use_grpc=False,  # Use HTTP
    )
"""

from __future__ import annotations

import atexit
import threading
from typing import Any

from obskit.logging import get_logger

logger = get_logger("obskit.metrics.otlp")

# Check for OpenTelemetry metrics dependencies
try:
    from opentelemetry import metrics as otel_metrics
    from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
        OTLPMetricExporter as GRPCMetricExporter,
    )
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import Resource

    OTLP_METRICS_AVAILABLE = True
except ImportError:  # pragma: no cover
    OTLP_METRICS_AVAILABLE = False
    GRPCMetricExporter = None  # type: ignore[misc, assignment]
    MeterProvider = None  # type: ignore[misc, assignment]
    PeriodicExportingMetricReader = None  # type: ignore[misc, assignment]
    Resource = None  # type: ignore[misc, assignment]
    otel_metrics = None  # type: ignore[assignment]

# Try HTTP exporter as fallback
try:
    from opentelemetry.exporter.otlp.proto.http.metric_exporter import (
        OTLPMetricExporter as HTTPMetricExporter,
    )

    HTTP_EXPORTER_AVAILABLE = True
except ImportError:  # pragma: no cover
    HTTP_EXPORTER_AVAILABLE = False
    HTTPMetricExporter = None  # type: ignore[misc, assignment]


class OTLPMetricsExporter:
    """
    Export metrics via OpenTelemetry Protocol (OTLP).

    This exporter sends metrics to OTLP-compatible backends, enabling
    integration with modern observability platforms.

    Parameters
    ----------
    endpoint : str
        OTLP endpoint URL.
        - gRPC: "http://localhost:4317" or "https://otlp.example.com:4317"
        - HTTP: "http://localhost:4318/v1/metrics"

    service_name : str
        Name of the service (added to resource attributes).

    service_version : str, optional
        Version of the service. Default: "0.0.0"

    environment : str, optional
        Deployment environment. Default: "development"

    export_interval : float, optional
        Interval between exports in seconds. Default: 60.0

    use_grpc : bool, optional
        Use gRPC transport (True) or HTTP (False). Default: True

    insecure : bool, optional
        Use insecure connection (no TLS). Default: True

    headers : dict, optional
        Additional headers for authentication.

    resource_attributes : dict, optional
        Additional resource attributes.

    timeout : float, optional
        Export timeout in seconds. Default: 10.0

    Example
    -------
    >>> exporter = OTLPMetricsExporter(
    ...     endpoint="http://localhost:4317",
    ...     service_name="order-service",
    ...     export_interval=60.0,
    ... )
    >>> exporter.start()
    >>> # ... application runs ...
    >>> exporter.shutdown()
    """

    def __init__(
        self,
        endpoint: str,
        service_name: str,
        service_version: str = "0.0.0",
        environment: str = "development",
        export_interval: float = 60.0,
        use_grpc: bool = True,
        insecure: bool = True,
        headers: dict[str, str] | None = None,
        resource_attributes: dict[str, str] | None = None,
        timeout: float = 10.0,
    ) -> None:
        if not OTLP_METRICS_AVAILABLE:  # pragma: no cover
            raise ImportError(
                "OpenTelemetry metrics exporter is not installed. "
                "Install with: pip install obskit[otlp-metrics]"
            )

        self.endpoint = endpoint
        self.service_name = service_name
        self.service_version = service_version
        self.environment = environment
        self.export_interval = export_interval
        self.use_grpc = use_grpc
        self.insecure = insecure
        self.headers = headers or {}
        self.timeout = timeout

        # Build resource attributes
        self._resource_attributes = {
            "service.name": service_name,
            "service.version": service_version,
            "deployment.environment": environment,
        }
        if resource_attributes:
            self._resource_attributes.update(resource_attributes)

        # Initialize components
        self._meter_provider: Any = None
        self._exporter: Any = None
        self._reader: Any = None
        self._started = False
        self._lock = threading.Lock()

        logger.debug(
            "otlp_metrics_exporter_init",
            endpoint=endpoint,
            service_name=service_name,
            use_grpc=use_grpc,
            export_interval=export_interval,
        )

    def _create_exporter(self) -> Any:
        """Create the appropriate OTLP exporter."""
        if self.use_grpc:
            if GRPCMetricExporter is None:  # pragma: no cover
                raise ImportError("gRPC metric exporter not available")

            return GRPCMetricExporter(
                endpoint=self.endpoint,
                insecure=self.insecure,
                headers=self.headers or None,
                timeout=int(self.timeout),
            )
        else:
            if not HTTP_EXPORTER_AVAILABLE or HTTPMetricExporter is None:  # pragma: no cover
                raise ImportError(
                    "HTTP metric exporter not available. "
                    "Install with: pip install opentelemetry-exporter-otlp-proto-http"
                )

            return HTTPMetricExporter(
                endpoint=self.endpoint,
                headers=self.headers or None,
                timeout=int(self.timeout),
            )

    def start(self) -> None:
        """
        Start the metrics exporter.

        Creates the OpenTelemetry meter provider and begins periodic export.
        """
        with self._lock:
            if self._started:
                logger.warning("otlp_metrics_exporter_already_started")
                return

            # Create resource
            resource = Resource.create(self._resource_attributes)

            # Create exporter
            self._exporter = self._create_exporter()

            # Create reader with export interval
            self._reader = PeriodicExportingMetricReader(
                exporter=self._exporter,
                export_interval_millis=int(self.export_interval * 1000),
            )

            # Create and set meter provider
            self._meter_provider = MeterProvider(
                resource=resource,
                metric_readers=[self._reader],
            )

            # Set as global meter provider
            otel_metrics.set_meter_provider(self._meter_provider)

            self._started = True

            # Register shutdown handler
            atexit.register(self.shutdown)

            logger.info(
                "otlp_metrics_exporter_started",
                endpoint=self.endpoint,
                export_interval=self.export_interval,
            )

    def shutdown(self) -> None:
        """
        Shutdown the metrics exporter.

        Flushes pending metrics and stops the exporter.
        """
        with self._lock:
            if not self._started:
                return

            try:
                if self._meter_provider:  # pragma: no branch
                    self._meter_provider.shutdown()

                self._started = False

                logger.info("otlp_metrics_exporter_shutdown")
            except Exception as e:
                logger.error(
                    "otlp_metrics_exporter_shutdown_error",
                    error=str(e),
                    error_type=type(e).__name__,
                )

    def force_flush(self, timeout_millis: int = 10000) -> bool:
        """
        Force flush pending metrics.

        Parameters
        ----------
        timeout_millis : int
            Timeout in milliseconds.

        Returns
        -------
        bool
            True if flush was successful.
        """
        with self._lock:
            if not self._started or not self._meter_provider:
                return False

            try:
                result: bool = self._meter_provider.force_flush(timeout_millis)
                return result
            except Exception as e:
                logger.error(
                    "otlp_metrics_force_flush_error",
                    error=str(e),
                    error_type=type(e).__name__,
                )
                return False

    def get_meter(self, name: str, version: str = "0.0.0") -> Any:
        """
        Get an OpenTelemetry meter.

        Parameters
        ----------
        name : str
            Meter name (typically module/package name).
        version : str
            Meter version.

        Returns
        -------
        Meter
            OpenTelemetry meter instance.

        Example
        -------
        >>> meter = exporter.get_meter("my_module")
        >>> counter = meter.create_counter("requests_total")
        >>> counter.add(1, {"method": "GET"})
        """
        if not self._started:
            raise RuntimeError("Exporter not started. Call start() first.")

        return otel_metrics.get_meter(name, version)

    @property
    def is_started(self) -> bool:
        """Check if exporter is running."""
        return self._started


__all__ = [
    "OTLPMetricsExporter",
    "OTLP_METRICS_AVAILABLE",
    "HTTP_EXPORTER_AVAILABLE",
]
