"""
Prometheus Pushgateway Support
===============================

This module provides support for pushing metrics to a Prometheus Pushgateway,
which is useful for batch jobs and short-lived processes that don't expose
HTTP endpoints.

When to Use Pushgateway
-----------------------
- Batch jobs that run and exit
- Cron jobs
- Lambda functions
- CLI tools
- Short-lived processes

When NOT to Use Pushgateway
----------------------------
- Long-running services (use scraping instead)
- Services with HTTP endpoints
- High-frequency metric updates

Installation
------------
.. code-block:: bash

    pip install obskit[pushgateway]

Example - Basic Usage
---------------------
.. code-block:: python

    from obskit.metrics.pushgateway import PushgatewayExporter

    exporter = PushgatewayExporter(
        gateway_url="http://pushgateway:9091",
        job_name="my_batch_job",
    )

    # Record metrics
    from prometheus_client import Counter
    counter = Counter("batch_processed_total", "Items processed")
    counter.inc(100)

    # Push to gateway
    exporter.push()

Example - Batch Job Pattern
----------------------------
.. code-block:: python

    from obskit.metrics.pushgateway import PushgatewayExporter

    exporter = PushgatewayExporter(
        gateway_url="http://pushgateway:9091",
        job_name="daily_report",
    )

    try:
        # Run batch job
        items = process_daily_report()

        # Record success metrics
        exporter.record_gauge("batch_items_processed", len(items))
        exporter.record_gauge("batch_status", 1)  # 1 = success

        # Push results
        exporter.push(grouping_key={"date": "2024-01-15"})

    except Exception as e:
        # Record failure
        exporter.record_gauge("batch_status", 0)  # 0 = failure
        exporter.push(grouping_key={"date": "2024-01-15"})
        raise

    finally:
        # Optional: Delete metrics after job completes
        # exporter.delete(grouping_key={"date": "2024-01-15"})

Example - Context Manager
--------------------------
.. code-block:: python

    from obskit.metrics.pushgateway import batch_job_metrics

    with batch_job_metrics(
        gateway_url="http://pushgateway:9091",
        job_name="etl_job",
    ) as exporter:
        # Process data
        count = run_etl()

        # Record metrics
        exporter.record_gauge("etl_rows_processed", count)

    # Metrics are automatically pushed on exit
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

from obskit.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Generator

logger = get_logger("obskit.metrics.pushgateway")

# Check for prometheus_client
PUSHGATEWAY_AVAILABLE: bool
REGISTRY: Any
CollectorRegistry: Any
Counter: Any
Gauge: Any
Histogram: Any
push_to_gateway: Any
pushadd_to_gateway: Any
delete_from_gateway: Any

try:
    from prometheus_client import REGISTRY as _REGISTRY
    from prometheus_client import CollectorRegistry as _CollectorRegistry
    from prometheus_client import Counter as _Counter
    from prometheus_client import Gauge as _Gauge
    from prometheus_client import Histogram as _Histogram
    from prometheus_client import delete_from_gateway as _delete_from_gateway
    from prometheus_client import push_to_gateway as _push_to_gateway
    from prometheus_client import pushadd_to_gateway as _pushadd_to_gateway

    PUSHGATEWAY_AVAILABLE = True
    REGISTRY = _REGISTRY
    CollectorRegistry = _CollectorRegistry
    Counter = _Counter
    Gauge = _Gauge
    Histogram = _Histogram
    push_to_gateway = _push_to_gateway
    pushadd_to_gateway = _pushadd_to_gateway
    delete_from_gateway = _delete_from_gateway
except ImportError:  # pragma: no cover
    PUSHGATEWAY_AVAILABLE = False
    REGISTRY = None
    CollectorRegistry = None
    Counter = None
    Gauge = None
    Histogram = None
    push_to_gateway = None
    pushadd_to_gateway = None
    delete_from_gateway = None


class PushgatewayExporter:
    """
    Export metrics to Prometheus Pushgateway.

    This exporter is designed for batch jobs and short-lived processes
    that need to push metrics to a Prometheus Pushgateway.

    Parameters
    ----------
    gateway_url : str
        URL of the Pushgateway (e.g., "http://pushgateway:9091").

    job_name : str
        Job name for grouping metrics.

    registry : CollectorRegistry, optional
        Prometheus registry to use. Default: global REGISTRY

    use_add : bool, optional
        Use pushadd_to_gateway instead of push_to_gateway.
        pushadd adds to existing metrics, push replaces them.
        Default: False (replace)

    timeout : float, optional
        HTTP timeout in seconds. Default: 30.0

    Example
    -------
    >>> exporter = PushgatewayExporter(
    ...     gateway_url="http://pushgateway:9091",
    ...     job_name="my_batch_job",
    ... )
    >>> exporter.push()
    """

    def __init__(
        self,
        gateway_url: str,
        job_name: str,
        registry: Any | None = None,
        use_add: bool = False,
        timeout: float = 30.0,
    ) -> None:
        if not PUSHGATEWAY_AVAILABLE:  # pragma: no cover
            raise ImportError(
                "prometheus_client is not installed. Install with: pip install prometheus-client"
            )

        self.gateway_url = gateway_url.rstrip("/")
        self.job_name = job_name
        self.registry = registry or REGISTRY
        self.use_add = use_add
        self.timeout = timeout

        # Track created metrics for this job
        self._gauges: dict[str, Any] = {}
        self._counters: dict[str, Any] = {}
        self._histograms: dict[str, Any] = {}

        # Create a dedicated registry for this job if not provided
        if registry is None:
            self.registry = CollectorRegistry()
            self._own_registry = True
        else:
            self._own_registry = False

        # Add job metadata
        self._job_start_time = time.time()

        logger.debug(
            "pushgateway_exporter_init",
            gateway_url=gateway_url,
            job_name=job_name,
        )

    def push(self, grouping_key: dict[str, str] | None = None) -> None:
        """
        Push metrics to the Pushgateway.

        Parameters
        ----------
        grouping_key : dict, optional
            Additional labels for grouping.

        Raises
        ------
        Exception
            If push fails.

        Example
        -------
        >>> exporter.push(grouping_key={"instance": "worker-1"})
        """
        try:
            push_func = pushadd_to_gateway if self.use_add else push_to_gateway

            push_func(
                self.gateway_url,
                job=self.job_name,
                registry=self.registry,
                grouping_key=grouping_key or {},
                timeout=self.timeout,
            )

            logger.info(
                "pushgateway_push_success",
                gateway_url=self.gateway_url,
                job_name=self.job_name,
                grouping_key=grouping_key,
            )

        except Exception as e:
            logger.error(
                "pushgateway_push_failed",
                error=str(e),
                error_type=type(e).__name__,
                gateway_url=self.gateway_url,
                job_name=self.job_name,
            )
            raise

    def delete(self, grouping_key: dict[str, str] | None = None) -> None:
        """
        Delete metrics from the Pushgateway.

        Use this to clean up metrics after a job completes.

        Parameters
        ----------
        grouping_key : dict, optional
            Labels to identify metrics to delete.

        Example
        -------
        >>> exporter.delete(grouping_key={"instance": "worker-1"})
        """
        try:
            delete_from_gateway(
                self.gateway_url,
                job=self.job_name,
                grouping_key=grouping_key or {},
                timeout=self.timeout,
            )

            logger.info(
                "pushgateway_delete_success",
                gateway_url=self.gateway_url,
                job_name=self.job_name,
                grouping_key=grouping_key,
            )

        except Exception as e:
            logger.error(
                "pushgateway_delete_failed",
                error=str(e),
                error_type=type(e).__name__,
                gateway_url=self.gateway_url,
                job_name=self.job_name,
            )
            raise

    def record_gauge(
        self,
        name: str,
        value: float,
        description: str = "",
        labels: dict[str, str] | None = None,
    ) -> None:
        """
        Record a gauge metric.

        Parameters
        ----------
        name : str
            Metric name.
        value : float
            Gauge value.
        description : str, optional
            Metric description.
        labels : dict, optional
            Metric labels.

        Example
        -------
        >>> exporter.record_gauge("batch_items_count", 1500)
        """
        label_names = list(labels.keys()) if labels else []

        if name not in self._gauges:  # pragma: no branch
            self._gauges[name] = Gauge(
                name,
                description or f"{name} gauge",
                labelnames=label_names,
                registry=self.registry,
            )

        gauge = self._gauges[name]
        if labels:
            gauge.labels(**labels).set(value)
        else:
            gauge.set(value)

    def record_counter(
        self,
        name: str,
        value: float = 1,
        description: str = "",
        labels: dict[str, str] | None = None,
    ) -> None:
        """
        Record a counter metric.

        Parameters
        ----------
        name : str
            Metric name.
        value : float
            Amount to increment.
        description : str, optional
            Metric description.
        labels : dict, optional
            Metric labels.

        Example
        -------
        >>> exporter.record_counter("batch_errors_total", 1)
        """
        label_names = list(labels.keys()) if labels else []

        if name not in self._counters:  # pragma: no branch
            self._counters[name] = Counter(
                name,
                description or f"{name} counter",
                labelnames=label_names,
                registry=self.registry,
            )

        counter = self._counters[name]
        if labels:
            counter.labels(**labels).inc(value)
        else:
            counter.inc(value)

    def record_histogram(
        self,
        name: str,
        value: float,
        description: str = "",
        labels: dict[str, str] | None = None,
        buckets: tuple[float, ...] | None = None,
    ) -> None:
        """
        Record a histogram observation.

        Parameters
        ----------
        name : str
            Metric name.
        value : float
            Observation value.
        description : str, optional
            Metric description.
        labels : dict, optional
            Metric labels.
        buckets : tuple, optional
            Histogram buckets.

        Example
        -------
        >>> exporter.record_histogram("batch_duration_seconds", 45.2)
        """
        label_names = list(labels.keys()) if labels else []

        if name not in self._histograms:  # pragma: no branch
            kwargs: dict[str, Any] = {
                "name": name,
                "documentation": description or f"{name} histogram",
                "labelnames": label_names,
                "registry": self.registry,
            }
            if buckets:
                kwargs["buckets"] = buckets

            self._histograms[name] = Histogram(**kwargs)

        histogram = self._histograms[name]
        if labels:
            histogram.labels(**labels).observe(value)
        else:
            histogram.observe(value)

    def record_job_duration(self) -> None:
        """
        Record job duration gauge.

        Call this at the end of a job to record how long it took.
        """
        duration = time.time() - self._job_start_time
        self.record_gauge(
            f"{self.job_name}_duration_seconds",
            duration,
            description="Duration of job execution in seconds",
        )

    def record_job_timestamp(self) -> None:
        """
        Record job completion timestamp.

        Call this at the end of a job to record when it finished.
        """
        self.record_gauge(
            f"{self.job_name}_last_success_timestamp",
            time.time(),
            description="Timestamp of last successful job completion",
        )


@contextmanager
def batch_job_metrics(
    gateway_url: str,
    job_name: str,
    grouping_key: dict[str, str] | None = None,
    record_duration: bool = True,
    record_timestamp: bool = True,
    delete_on_success: bool = False,
) -> Generator[PushgatewayExporter, None, None]:
    """
    Context manager for batch job metrics.

    Automatically pushes metrics when the context exits.

    Parameters
    ----------
    gateway_url : str
        Pushgateway URL.
    job_name : str
        Job name.
    grouping_key : dict, optional
        Grouping labels.
    record_duration : bool, optional
        Record job duration. Default: True
    record_timestamp : bool, optional
        Record completion timestamp. Default: True
    delete_on_success : bool, optional
        Delete metrics after successful completion. Default: False

    Yields
    ------
    PushgatewayExporter
        The exporter instance.

    Example
    -------
    >>> with batch_job_metrics(
    ...     gateway_url="http://pushgateway:9091",
    ...     job_name="etl",
    ... ) as exporter:
    ...     count = run_etl()
    ...     exporter.record_gauge("etl_rows", count)
    """
    exporter = PushgatewayExporter(
        gateway_url=gateway_url,
        job_name=job_name,
    )

    success = False
    try:
        yield exporter
        success = True
    finally:
        try:
            if record_duration:  # pragma: no branch
                exporter.record_job_duration()

            if record_timestamp and success:  # pragma: no branch
                exporter.record_job_timestamp()

            exporter.record_gauge(
                f"{job_name}_success",
                1.0 if success else 0.0,
                description="Whether job succeeded (1) or failed (0)",
            )

            exporter.push(grouping_key=grouping_key)

            if delete_on_success and success:
                exporter.delete(grouping_key=grouping_key)

        except Exception as e:
            logger.error(
                "batch_job_metrics_push_failed",
                error=str(e),
                job_name=job_name,
            )


__all__ = [
    "PushgatewayExporter",
    "batch_job_metrics",
    "PUSHGATEWAY_AVAILABLE",
]
