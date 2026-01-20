"""
Prometheus Metric Type Wrappers
===============================

This module provides wrapper classes for Prometheus metric types that
gracefully handle the case when prometheus_client is not installed.

Design Philosophy
-----------------
obskit makes Prometheus metrics optional. If prometheus_client is installed,
these wrappers delegate to real Prometheus metrics. Otherwise, they act as
no-ops, allowing code to run without changes.

This enables:
1. Using obskit core features without heavy dependencies
2. Gradual adoption of metrics in existing projects
3. Testing without Prometheus infrastructure

Metric Types
------------

**Counter**
    A monotonically increasing value.
    Use for: requests, errors, completed tasks

    ```python
    requests = Counter("http_requests_total", "Total HTTP requests", ["method"])
    requests.labels(method="GET").inc()
    ```

**Gauge**
    A value that can go up and down.
    Use for: temperature, queue size, active connections

    ```python
    queue_size = Gauge("queue_size", "Current queue size")
    queue_size.set(42)
    queue_size.inc()
    queue_size.dec()
    ```

**Histogram**
    Distribution of values in configurable buckets.
    Use for: request duration, response size

    ```python
    latency = Histogram(
        "request_latency_seconds",
        "Request latency",
        buckets=[0.1, 0.5, 1.0, 5.0],
    )
    latency.observe(0.45)
    ```

**Summary**
    Pre-calculated percentiles (not aggregatable).
    Use for: exact percentiles on single instance

    ```python
    latency = Summary(
        "request_latency_seconds",
        "Request latency",
    )
    latency.observe(0.45)
    ```

See Also
--------
prometheus_client : The underlying Prometheus client library
obskit.metrics.red : RED method implementation
obskit.metrics.golden : Four Golden Signals implementation
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

# Check if prometheus_client is available
try:
    import prometheus_client

    PROMETHEUS_AVAILABLE = True
    if TYPE_CHECKING:
        # Only import for type checking - used in docstring type annotations
        from prometheus_client import CollectorRegistry
except ImportError:  # pragma: no cover
    PROMETHEUS_AVAILABLE = False
    CollectorRegistry = None  # type: ignore[assignment]


class Counter:
    """
    Counter metric wrapper.

    A counter is a cumulative metric that represents a single monotonically
    increasing counter whose value can only increase or be reset to zero.

    Parameters
    ----------
    name : str
        Metric name. Should follow Prometheus naming conventions.

    documentation : str
        Help text describing the metric.

    labelnames : Sequence[str], optional
        Label names for this metric.

    registry : CollectorRegistry, optional
        Registry to register the metric with.

    Example
    -------
    >>> from obskit.metrics.types import Counter
    >>>
    >>> # Counter without labels
    >>> errors = Counter("errors_total", "Total errors")
    >>> errors.inc()
    >>>
    >>> # Counter with labels
    >>> requests = Counter(
    ...     "http_requests_total",
    ...     "Total HTTP requests",
    ...     ["method", "status"],
    ... )
    >>> requests.labels(method="GET", status="200").inc()
    >>> requests.labels(method="POST", status="201").inc()

    Notes
    -----
    - Counter values only go up (or reset to zero on restart)
    - Use rate() in PromQL to get per-second rate
    - Never use counter for values that can decrease
    """

    _metric: Any  # prometheus_client.Counter | None

    def __init__(
        self,
        name: str,
        documentation: str,
        labelnames: Sequence[str] = (),
        registry: Any = None,
    ) -> None:
        """Initialize counter metric."""
        self._name = name
        self._documentation = documentation
        self._labelnames = labelnames

        if PROMETHEUS_AVAILABLE:
            # Unregister existing metric with same name if it exists
            # This prevents "Duplicated timeseries" errors in tests
            if registry is None:
                registry = prometheus_client.REGISTRY
            try:
                if (
                    hasattr(registry, "_names_to_collectors")
                    and name in registry._names_to_collectors
                ):
                    existing = registry._names_to_collectors[name]
                    registry.unregister(existing)
            except Exception:  # nosec B110 - metric cleanup errors are non-critical
                pass  # Ignore errors during cleanup - metric might not exist

            self._metric = prometheus_client.Counter(
                name,
                documentation,
                labelnames=labelnames,
                registry=registry,
            )
        else:  # pragma: no cover
            self._metric = None

    def labels(self, **kwargs: str) -> Counter:
        """
        Return a child counter with the specified labels.

        Parameters
        ----------
        **kwargs : str
            Label key-value pairs.

        Returns
        -------
        Counter
            Labeled counter instance.
        """
        if self._metric is not None:
            # Return wrapped labeled metric
            labeled = self._metric.labels(**kwargs)
            wrapper = Counter.__new__(Counter)
            wrapper._metric = labeled
            wrapper._name = self._name
            wrapper._documentation = self._documentation
            wrapper._labelnames = ()
            return wrapper
        return self  # pragma: no cover

    def inc(self, amount: float = 1) -> None:
        """
        Increment the counter.

        Parameters
        ----------
        amount : float, default=1
            Amount to increment by (must be >= 0).
        """
        if self._metric is not None:  # pragma: no branch
            self._metric.inc(amount)


class Gauge:
    """
    Gauge metric wrapper.

    A gauge is a metric that represents a single numerical value that can
    arbitrarily go up and down.

    Parameters
    ----------
    name : str
        Metric name.

    documentation : str
        Help text.

    labelnames : Sequence[str], optional
        Label names.

    registry : CollectorRegistry, optional
        Prometheus registry.

    Example
    -------
    >>> from obskit.metrics.types import Gauge
    >>>
    >>> # Gauge without labels
    >>> temperature = Gauge("temperature_celsius", "Current temperature")
    >>> temperature.set(23.5)
    >>>
    >>> # Gauge with labels
    >>> queue_size = Gauge(
    ...     "queue_size",
    ...     "Current queue size",
    ...     ["queue_name"],
    ... )
    >>> queue_size.labels(queue_name="orders").set(42)
    >>> queue_size.labels(queue_name="emails").inc()
    >>> queue_size.labels(queue_name="orders").dec(5)

    Notes
    -----
    - Gauges can go up and down
    - Use for current values (not totals)
    - Examples: temperature, memory usage, queue depth
    """

    _metric: Any  # prometheus_client.Gauge | None

    def __init__(
        self,
        name: str,
        documentation: str,
        labelnames: Sequence[str] = (),
        registry: Any = None,
    ) -> None:
        """Initialize gauge metric."""
        self._name = name
        self._documentation = documentation
        self._labelnames = labelnames

        if PROMETHEUS_AVAILABLE:
            # Unregister existing metric with same name if it exists
            if registry is None:
                registry = prometheus_client.REGISTRY
            try:
                if (
                    hasattr(registry, "_names_to_collectors")
                    and name in registry._names_to_collectors
                ):
                    existing = registry._names_to_collectors[name]
                    registry.unregister(existing)
            except Exception:  # nosec B110 - metric cleanup errors are non-critical
                pass  # Ignore errors during cleanup - metric might not exist

            self._metric = prometheus_client.Gauge(
                name,
                documentation,
                labelnames=labelnames,
                registry=registry,
            )
        else:  # pragma: no cover
            self._metric = None

    def labels(self, **kwargs: str) -> Gauge:
        """Return a child gauge with labels."""
        if self._metric is not None:
            labeled = self._metric.labels(**kwargs)
            wrapper = Gauge.__new__(Gauge)
            wrapper._metric = labeled
            wrapper._name = self._name
            wrapper._documentation = self._documentation
            wrapper._labelnames = ()
            return wrapper
        return self  # pragma: no cover

    def set(self, value: float) -> None:
        """
        Set the gauge to a value.

        Parameters
        ----------
        value : float
            The value to set.
        """
        if self._metric is not None:  # pragma: no branch
            self._metric.set(value)

    def inc(self, amount: float = 1) -> None:
        """
        Increment the gauge.

        Parameters
        ----------
        amount : float, default=1
            Amount to increment by.
        """
        if self._metric is not None:  # pragma: no branch
            self._metric.inc(amount)

    def dec(self, amount: float = 1) -> None:
        """
        Decrement the gauge.

        Parameters
        ----------
        amount : float, default=1
            Amount to decrement by.
        """
        if self._metric is not None:  # pragma: no branch
            self._metric.dec(amount)


class Histogram:
    """
    Histogram metric wrapper.

    A histogram samples observations and counts them in configurable buckets.
    Also provides sum and count of observations.

    Parameters
    ----------
    name : str
        Metric name.

    documentation : str
        Help text.

    labelnames : Sequence[str], optional
        Label names.

    buckets : Sequence[float], optional
        Bucket boundaries.

    registry : CollectorRegistry, optional
        Prometheus registry.

    Example
    -------
    >>> from obskit.metrics.types import Histogram
    >>>
    >>> # Histogram for latency
    >>> latency = Histogram(
    ...     "request_duration_seconds",
    ...     "Request duration",
    ...     ["endpoint"],
    ...     buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 5.0],
    ... )
    >>> latency.labels(endpoint="/api/users").observe(0.045)

    Notes
    -----
    - Use histogram_quantile() in PromQL for percentiles
    - Histograms are aggregatable across instances
    - Choose buckets based on your SLO targets
    """

    # Default buckets for common web service latencies
    DEFAULT_BUCKETS = (
        0.005,
        0.01,
        0.025,
        0.05,
        0.075,
        0.1,
        0.25,
        0.5,
        0.75,
        1.0,
        2.5,
        5.0,
        7.5,
        10.0,
        float("inf"),
    )

    _metric: Any  # prometheus_client.Histogram | None

    def __init__(
        self,
        name: str,
        documentation: str,
        labelnames: Sequence[str] = (),
        buckets: Sequence[float] | None = None,
        registry: Any = None,
    ) -> None:
        """Initialize histogram metric."""
        self._name = name
        self._documentation = documentation
        self._labelnames = labelnames
        self._buckets = tuple(buckets) if buckets else self.DEFAULT_BUCKETS

        if PROMETHEUS_AVAILABLE:
            # Unregister existing metric with same name if it exists
            if registry is None:
                registry = prometheus_client.REGISTRY
            try:
                if (
                    hasattr(registry, "_names_to_collectors")
                    and name in registry._names_to_collectors
                ):
                    existing = registry._names_to_collectors[name]
                    registry.unregister(existing)
            except Exception:  # nosec B110 - metric cleanup errors are non-critical
                pass  # Ignore errors during cleanup - metric might not exist

            self._metric = prometheus_client.Histogram(
                name,
                documentation,
                labelnames=labelnames,
                buckets=self._buckets,
                registry=registry,
            )
        else:  # pragma: no cover
            self._metric = None

    def labels(self, **kwargs: str) -> Histogram:
        """Return a child histogram with labels."""
        if self._metric is not None:
            labeled = self._metric.labels(**kwargs)
            wrapper = Histogram.__new__(Histogram)
            wrapper._metric = labeled
            wrapper._name = self._name
            wrapper._documentation = self._documentation
            wrapper._labelnames = ()
            wrapper._buckets = self._buckets
            return wrapper
        return self  # pragma: no cover

    def observe(self, value: float) -> None:
        """
        Observe a value.

        Parameters
        ----------
        value : float
            The value to observe.
        """
        if self._metric is not None:  # pragma: no branch
            self._metric.observe(value)


class Summary:
    """
    Summary metric wrapper.

    A summary samples observations and provides pre-calculated quantiles,
    sum, and count.

    Parameters
    ----------
    name : str
        Metric name.

    documentation : str
        Help text.

    labelnames : Sequence[str], optional
        Label names.

    registry : CollectorRegistry, optional
        Prometheus registry.

    Example
    -------
    >>> from obskit.metrics.types import Summary
    >>>
    >>> latency = Summary(
    ...     "request_duration_seconds",
    ...     "Request duration",
    ...     ["endpoint"],
    ... )
    >>> latency.labels(endpoint="/api/users").observe(0.045)

    Warning
    -------
    Summaries are NOT aggregatable across instances!
    Use histograms for multi-instance deployments.
    """

    _metric: Any  # prometheus_client.Summary | None

    def __init__(
        self,
        name: str,
        documentation: str,
        labelnames: Sequence[str] = (),
        registry: Any = None,
    ) -> None:
        """Initialize summary metric."""
        self._name = name
        self._documentation = documentation
        self._labelnames = labelnames

        if PROMETHEUS_AVAILABLE:
            # Unregister existing metric with same name if it exists
            if registry is None:
                registry = prometheus_client.REGISTRY
            try:
                if (
                    hasattr(registry, "_names_to_collectors")
                    and name in registry._names_to_collectors
                ):
                    existing = registry._names_to_collectors[name]
                    registry.unregister(existing)
            except Exception:  # nosec B110 - metric cleanup errors are non-critical
                pass  # Ignore errors during cleanup - metric might not exist

            self._metric = prometheus_client.Summary(
                name,
                documentation,
                labelnames=labelnames,
                registry=registry,
            )
        else:  # pragma: no cover
            self._metric = None

    def labels(self, **kwargs: str) -> Summary:
        """Return a child summary with labels."""
        if self._metric is not None:
            labeled = self._metric.labels(**kwargs)
            wrapper = Summary.__new__(Summary)
            wrapper._metric = labeled
            wrapper._name = self._name
            wrapper._documentation = self._documentation
            wrapper._labelnames = ()
            return wrapper
        return self  # pragma: no cover

    def observe(self, value: float) -> None:
        """
        Observe a value.

        Parameters
        ----------
        value : float
            The value to observe.
        """
        if self._metric is not None:  # pragma: no branch
            self._metric.observe(value)
