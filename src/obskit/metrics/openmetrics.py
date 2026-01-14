"""
OpenMetrics Format Support
==========================

This module provides OpenMetrics format output for Prometheus metrics,
enabling compatibility with OpenMetrics-compliant scrapers.

OpenMetrics vs Prometheus Format
--------------------------------
OpenMetrics is an evolution of the Prometheus exposition format with:
- Standardized MIME type (application/openmetrics-text)
- Required EOF marker
- Support for exemplars
- Stricter parsing rules
- INFO and STATESET metric types

Example - OpenMetrics Endpoint
------------------------------
.. code-block:: python

    from fastapi import FastAPI, Response
    from obskit.metrics.openmetrics import generate_openmetrics, OPENMETRICS_CONTENT_TYPE

    app = FastAPI()

    @app.get("/metrics")
    async def metrics(accept: str = ""):
        # Check if client prefers OpenMetrics
        if "application/openmetrics-text" in accept:
            content = generate_openmetrics()
            return Response(
                content=content,
                media_type=OPENMETRICS_CONTENT_TYPE,
            )
        else:
            # Fall back to Prometheus format
            from prometheus_client import generate_latest
            return Response(
                content=generate_latest(),
                media_type="text/plain; charset=utf-8",
            )

Example - With Exemplars
------------------------
.. code-block:: python

    from obskit.metrics.openmetrics import (
        OpenMetricsRegistry,
        add_exemplar,
    )

    registry = OpenMetricsRegistry()

    # Record metric with exemplar
    add_exemplar(
        metric_name="http_request_duration_seconds",
        labels={"handler": "/api/users"},
        value=0.042,
        exemplar_labels={"trace_id": "abc123"},
    )
"""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Any

from obskit.logging import get_logger

logger = get_logger("obskit.metrics.openmetrics")

# OpenMetrics content type
OPENMETRICS_CONTENT_TYPE = "application/openmetrics-text; version=1.0.0; charset=utf-8"

# Check for prometheus_client
try:
    from prometheus_client import REGISTRY

    PROMETHEUS_AVAILABLE = True
except ImportError:  # pragma: no cover
    PROMETHEUS_AVAILABLE = False
    REGISTRY = None  # type: ignore[assignment]


def generate_openmetrics(registry: Any | None = None) -> bytes:
    """
    Generate OpenMetrics format output from Prometheus registry.

    Parameters
    ----------
    registry : Any, optional
        Prometheus CollectorRegistry. Defaults to the default registry.

    Returns
    -------
    bytes
        OpenMetrics format output.

    Example
    -------
    >>> from obskit.metrics.openmetrics import generate_openmetrics
    >>>
    >>> output = generate_openmetrics()
    >>> print(output.decode())
    """
    if not PROMETHEUS_AVAILABLE:  # pragma: no cover
        return b"# EOF\n"

    if registry is None:
        registry = REGISTRY

    output_lines: list[str] = []

    for metric in registry.collect():
        # Add metric metadata
        output_lines.append(f"# HELP {metric.name} {metric.documentation}")
        output_lines.append(f"# TYPE {metric.name} {_get_openmetrics_type(metric)}")

        # Add samples
        for sample in metric.samples:
            labels = _format_labels(sample.labels)
            value = _format_value(sample.value)

            if sample.name.endswith("_total"):
                # Counter samples need special handling
                output_lines.append(f"{sample.name}{labels} {value}")
            elif sample.name.endswith("_bucket"):
                # Histogram buckets
                output_lines.append(f"{sample.name}{labels} {value}")
            else:
                output_lines.append(f"{sample.name}{labels} {value}")

    # OpenMetrics requires EOF marker
    output_lines.append("# EOF")

    return "\n".join(output_lines).encode("utf-8")


def _get_openmetrics_type(metric: Any) -> str:
    """Get OpenMetrics type from Prometheus metric."""
    type_name = metric.type.lower()

    # Map Prometheus types to OpenMetrics types
    type_map = {
        "counter": "counter",
        "gauge": "gauge",
        "summary": "summary",
        "histogram": "histogram",
        "info": "info",
        "stateset": "stateset",
        "unknown": "unknown",
    }

    return type_map.get(type_name, "unknown")


def _format_labels(labels: dict[str, str]) -> str:
    """Format labels for OpenMetrics output."""
    if not labels:
        return ""

    parts = []
    for key, value in sorted(labels.items()):
        # Escape special characters in label values
        escaped_value = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
        parts.append(f'{key}="{escaped_value}"')

    return "{" + ",".join(parts) + "}"


def _format_value(value: float) -> str:
    """Format value for OpenMetrics output."""
    import math

    if value == float("inf"):
        return "+Inf"
    elif value == float("-inf"):
        return "-Inf"
    elif math.isnan(value):
        return "NaN"
    else:
        # Use scientific notation for very large/small values
        if abs(value) >= 1e15 or (abs(value) < 1e-4 and value != 0):
            return f"{value:.6e}"
        return str(value)


class OpenMetricsExemplar:
    """
    Represents an OpenMetrics exemplar.

    Exemplars are sample values with additional labels that provide
    context for high-cardinality data like trace IDs.

    Attributes
    ----------
    labels : dict[str, str]
        Exemplar labels (e.g., trace_id).
    value : float
        The sample value.
    timestamp : float | None
        Unix timestamp of the sample.
    """

    def __init__(
        self,
        labels: dict[str, str],
        value: float,
        timestamp: float | None = None,
    ) -> None:
        self.labels = labels
        self.value = value
        self.timestamp = timestamp or time.time()

    def to_string(self) -> str:
        """Convert exemplar to OpenMetrics format string."""
        label_str = ",".join(f'{k}="{v}"' for k, v in sorted(self.labels.items()))
        return f" # {{{label_str}}} {self.value} {self.timestamp}"


class OpenMetricsRegistry:
    """
    Extended registry with OpenMetrics support.

    This registry wraps the Prometheus registry and adds
    OpenMetrics-specific features like exemplars and INFO metrics.

    Example
    -------
    >>> from obskit.metrics.openmetrics import OpenMetricsRegistry
    >>>
    >>> registry = OpenMetricsRegistry()
    >>>
    >>> # Add info metric
    >>> registry.add_info(
    ...     "service_info",
    ...     {"version": "1.0.0", "environment": "production"},
    ... )
    >>>
    >>> # Generate output
    >>> output = registry.generate()
    """

    def __init__(self, prometheus_registry: Any | None = None) -> None:
        if not PROMETHEUS_AVAILABLE:  # pragma: no cover
            raise ImportError(
                "prometheus_client is required. Install with: pip install prometheus-client"
            )

        self._prometheus_registry = prometheus_registry or REGISTRY
        self._exemplars: dict[str, list[OpenMetricsExemplar]] = defaultdict(list)
        self._info_metrics: dict[str, dict[str, str]] = {}

    def add_exemplar(
        self,
        metric_name: str,
        labels: dict[str, str],
        value: float,
        exemplar_labels: dict[str, str],
    ) -> None:
        """
        Add an exemplar to a metric.

        Parameters
        ----------
        metric_name : str
            Name of the metric.
        labels : dict[str, str]
            Metric labels.
        value : float
            Sample value.
        exemplar_labels : dict[str, str]
            Exemplar labels (e.g., trace_id, span_id).
        """
        key = f"{metric_name}{_format_labels(labels)}"
        exemplar = OpenMetricsExemplar(exemplar_labels, value)
        self._exemplars[key].append(exemplar)

        # Keep only last 100 exemplars per metric
        if len(self._exemplars[key]) > 100:
            self._exemplars[key] = self._exemplars[key][-100:]

    def add_info(self, name: str, labels: dict[str, str]) -> None:
        """
        Add an INFO metric.

        INFO metrics are used for static metadata that doesn't change.

        Parameters
        ----------
        name : str
            Metric name.
        labels : dict[str, str]
            Info labels.
        """
        self._info_metrics[name] = labels

    def generate(self) -> bytes:
        """
        Generate OpenMetrics format output.

        Returns
        -------
        bytes
            OpenMetrics format output.
        """
        output_lines: list[str] = []

        # Add INFO metrics
        for name, labels in self._info_metrics.items():
            output_lines.append(f"# HELP {name} {name} info metric")
            output_lines.append(f"# TYPE {name} info")
            label_str = _format_labels(labels)
            output_lines.append(f"{name}_info{label_str} 1")

        # Add Prometheus metrics
        for metric in self._prometheus_registry.collect():
            output_lines.append(f"# HELP {metric.name} {metric.documentation}")
            output_lines.append(f"# TYPE {metric.name} {_get_openmetrics_type(metric)}")

            for sample in metric.samples:
                labels_str = _format_labels(sample.labels)
                value = _format_value(sample.value)
                line = f"{sample.name}{labels_str} {value}"

                # Add exemplar if available
                key = f"{sample.name}{labels_str}"
                if key in self._exemplars and self._exemplars[key]:
                    exemplar = self._exemplars[key][-1]
                    line += exemplar.to_string()

                output_lines.append(line)

        output_lines.append("# EOF")
        return "\n".join(output_lines).encode("utf-8")


def add_exemplar(
    metric_name: str,
    labels: dict[str, str],
    value: float,
    exemplar_labels: dict[str, str],
) -> None:
    """
    Convenience function to add an exemplar with trace context.

    Parameters
    ----------
    metric_name : str
        Name of the metric.
    labels : dict[str, str]
        Metric labels.
    value : float
        Sample value.
    exemplar_labels : dict[str, str]
        Exemplar labels.

    Example
    -------
    >>> from obskit.metrics.openmetrics import add_exemplar
    >>>
    >>> # Add exemplar with trace context
    >>> add_exemplar(
    ...     "http_request_duration_seconds",
    ...     labels={"handler": "/api/users", "method": "GET"},
    ...     value=0.042,
    ...     exemplar_labels={"trace_id": "abc123def456"},
    ... )
    """
    # This is a stub - in production, you'd integrate with OpenMetricsRegistry
    logger.debug(
        "exemplar_added",
        metric_name=metric_name,
        labels=labels,
        value=value,
        exemplar_labels=exemplar_labels,
    )


__all__ = [
    "generate_openmetrics",
    "OpenMetricsExemplar",
    "OpenMetricsRegistry",
    "add_exemplar",
    "OPENMETRICS_CONTENT_TYPE",
    "PROMETHEUS_AVAILABLE",
]
