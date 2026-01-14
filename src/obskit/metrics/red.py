"""
RED Method Implementation
=========================

The RED Method is a microservices monitoring methodology developed by
Tom Wilkie (Grafana/Weave) that focuses on three key metrics:

- **R**ate: The number of requests per second
- **E**rrors: The number of failed requests
- **D**uration: The time each request takes

These metrics directly measure what your users experience, making them
ideal for monitoring service endpoints and APIs.

Why RED Method?
---------------
1. **User-centric**: Measures what users actually experience
2. **Simple**: Only three metrics to understand and alert on
3. **Universal**: Applies to any request-response service
4. **Actionable**: Easy to set SLOs and alerts

Prometheus Metrics Created
--------------------------
For a service named "order_service", this creates:

**Counters:**
    - ``order_service_requests_total{operation="...", status="success|failure"}``
    - ``order_service_errors_total{operation="...", error_type="..."}``

**Histogram (if enabled):**
    - ``order_service_request_duration_seconds_bucket{operation="...", le="..."}``
    - ``order_service_request_duration_seconds_sum{operation="..."}``
    - ``order_service_request_duration_seconds_count{operation="..."}``

**Summary (if enabled):**
    - ``order_service_request_duration_seconds{operation="...", quantile="..."}``
    - ``order_service_request_duration_seconds_sum{operation="..."}``
    - ``order_service_request_duration_seconds_count{operation="..."}``

Example - Basic Usage
---------------------
.. code-block:: python

    from obskit.metrics import REDMetrics

    # Create metrics for your service
    red = REDMetrics("order_service")

    # Record a successful request
    red.observe_request(
        operation="create_order",
        duration_seconds=0.045,  # 45 milliseconds
        status="success",
    )

    # Record a failed request with error type
    red.observe_request(
        operation="create_order",
        duration_seconds=0.012,
        status="failure",
        error_type="ValidationError",
    )

Example - With Context Manager
------------------------------
.. code-block:: python

    from obskit.metrics import REDMetrics

    red = REDMetrics("payment_service")

    # Automatically measure duration
    with red.track_request("process_payment"):
        result = payment_gateway.charge(amount)
        if not result.success:
            raise PaymentError(result.error)
    # Duration automatically recorded, status based on exception

Example - Custom Histogram Buckets
----------------------------------
.. code-block:: python

    from obskit.metrics import REDMetrics

    # For a fast service (sub-100ms SLO)
    fast_buckets = [0.001, 0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25]
    red = REDMetrics("cache_service", histogram_buckets=fast_buckets)

    # For a slow service (multi-second operations)
    slow_buckets = [0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0]
    red = REDMetrics("batch_processor", histogram_buckets=slow_buckets)

PromQL Queries
--------------
.. code-block:: promql

    # Request rate (requests per second over 5 minutes)
    sum(rate(order_service_requests_total[5m])) by (operation)

    # Error rate (as percentage)
    sum(rate(order_service_errors_total[5m])) by (operation, error_type)
    /
    sum(rate(order_service_requests_total[5m])) by (operation)
    * 100

    # Success rate (as percentage)
    sum(rate(order_service_requests_total{status="success"}[5m])) by (operation)
    /
    sum(rate(order_service_requests_total[5m])) by (operation)
    * 100

    # P50 latency (median) from histogram
    histogram_quantile(0.50,
        sum(rate(order_service_request_duration_seconds_bucket[5m])) by (le, operation)
    )

    # P95 latency from histogram
    histogram_quantile(0.95,
        sum(rate(order_service_request_duration_seconds_bucket[5m])) by (le, operation)
    )

    # P99 latency from histogram
    histogram_quantile(0.99,
        sum(rate(order_service_request_duration_seconds_bucket[5m])) by (le, operation)
    )

    # Average latency
    sum(rate(order_service_request_duration_seconds_sum[5m])) by (operation)
    /
    sum(rate(order_service_request_duration_seconds_count[5m])) by (operation)

Alerting Examples
-----------------
.. code-block:: yaml

    # Prometheus alerting rules
    groups:
      - name: red-alerts
        rules:
          # High error rate alert
          - alert: HighErrorRate
            expr: |
              sum(rate(order_service_errors_total[5m])) by (operation)
              /
              sum(rate(order_service_requests_total[5m])) by (operation)
              > 0.01
            for: 5m
            labels:
              severity: critical
            annotations:
              summary: "Error rate > 1% for {{ $labels.operation }}"

          # High latency alert (P95 > 500ms)
          - alert: HighLatency
            expr: |
              histogram_quantile(0.95,
                sum(rate(order_service_request_duration_seconds_bucket[5m])) by (le, operation)
              ) > 0.5
            for: 5m
            labels:
              severity: warning
            annotations:
              summary: "P95 latency > 500ms for {{ $labels.operation }}"

References
----------
- RED Method: https://grafana.com/blog/the-red-method-how-to-instrument-your-services/
- Prometheus Histograms: https://prometheus.io/docs/practices/histograms/
"""

from __future__ import annotations

import random
import time
from collections.abc import Generator
from contextlib import contextmanager
from typing import Literal

from obskit.config import get_settings
from obskit.metrics.registry import get_registry
from obskit.metrics.types import Counter, Histogram, Summary

# =============================================================================
# Default Configuration
# =============================================================================

# Default histogram buckets optimized for typical web service latencies
# Covers from 1ms to 10s with good resolution around common latency targets
DEFAULT_LATENCY_BUCKETS: tuple[float, ...] = (
    0.001,  # 1ms   - Extremely fast (cache hit)
    0.005,  # 5ms   - Very fast
    0.010,  # 10ms  - Fast (simple DB query)
    0.025,  # 25ms  - Normal (complex query)
    0.050,  # 50ms  - Expected (external call)
    0.100,  # 100ms - Acceptable
    0.250,  # 250ms - Slow
    0.500,  # 500ms - Very slow
    1.000,  # 1s    - SLO threshold
    2.500,  # 2.5s  - Unacceptable
    5.000,  # 5s    - Timeout warning
    10.000,  # 10s   - Near timeout
)

# Default summary quantiles
DEFAULT_QUANTILES: tuple[float, ...] = (0.5, 0.9, 0.95, 0.99)


class REDMetrics:
    """
    RED Method metrics collector for service monitoring.

    The RED Method provides three essential metrics for any request-based
    service:

    - **Rate**: Requests per second (counter, derived via rate())
    - **Errors**: Failed requests per second (counter, derived via rate())
    - **Duration**: Time per request (histogram/summary)

    Parameters
    ----------
    name : str
        Service name prefix for all metrics.
        Example: "order_service" creates "order_service_requests_total", etc.

    histogram_buckets : tuple[float, ...], optional
        Custom latency buckets for histogram.
        Default covers 1ms to 10s with good resolution.

    summary_quantiles : tuple[float, ...], optional
        Quantiles for summary metrics.
        Default: (0.5, 0.9, 0.95, 0.99)

    use_histogram : bool, optional
        Whether to create histogram metrics.
        Default: True (from settings)

    use_summary : bool, optional
        Whether to create summary metrics.
        Default: False (from settings)

    Attributes
    ----------
    name : str
        Service name prefix.

    requests_total : Counter
        Total requests by operation and status.

    errors_total : Counter
        Total errors by operation and error type.

    duration_histogram : Histogram or None
        Latency distribution (if use_histogram=True).

    duration_summary : Summary or None
        Latency percentiles (if use_summary=True).

    Example
    -------
    >>> from obskit.metrics import REDMetrics
    >>>
    >>> # Create metrics collector
    >>> red = REDMetrics("order_service")
    >>>
    >>> # Record a successful operation
    >>> red.observe_request(
    ...     operation="create_order",
    ...     duration_seconds=0.045,
    ...     status="success",
    ... )
    >>>
    >>> # Record a failed operation with error type
    >>> red.observe_request(
    ...     operation="create_order",
    ...     duration_seconds=0.012,
    ...     status="failure",
    ...     error_type="ValidationError",
    ... )

    Example - Context Manager
    -------------------------
    >>> red = REDMetrics("payment_service")
    >>>
    >>> # Automatic timing and error detection
    >>> with red.track_request("process_payment"):
    ...     gateway.charge(amount)
    >>> # Success recorded with measured duration
    >>>
    >>> with red.track_request("refund"):
    ...     raise RefundError("Insufficient funds")
    >>> # Error recorded with error_type="RefundError"

    Example - Decorator Integration
    -------------------------------
    >>> from obskit.decorators import with_observability
    >>> from obskit.metrics import REDMetrics
    >>>
    >>> # The decorator uses REDMetrics internally
    >>> @with_observability(component="OrderService")
    ... async def create_order(data: dict) -> Order:
    ...     return await Order.create(**data)
    >>>
    >>> # Manually using REDMetrics with a decorator
    >>> red = REDMetrics("order_service")
    >>>
    >>> def track_red(operation: str):
    ...     def decorator(func):
    ...         @functools.wraps(func)
    ...         async def wrapper(*args, **kwargs):
    ...             with red.track_request(operation):
    ...                 return await func(*args, **kwargs)
    ...         return wrapper
    ...     return decorator
    >>>
    >>> @track_red("create_order")
    ... async def create_order(data):
    ...     return await Order.create(**data)
    """

    # Type annotations for optional metrics
    duration_histogram: Histogram | None
    duration_summary: Summary | None

    def __init__(
        self,
        name: str,
        histogram_buckets: tuple[float, ...] | None = None,
        summary_quantiles: tuple[float, ...] | None = None,
        use_histogram: bool | None = None,
        use_summary: bool | None = None,
        sample_rate: float | None = None,
    ) -> None:
        """
        Initialize RED metrics for a service.

        Parameters
        ----------
        name : str
            Service name prefix for metrics.
        histogram_buckets : tuple[float, ...], optional
            Custom histogram buckets.
        summary_quantiles : tuple[float, ...], optional
            Custom summary quantiles.
        use_histogram : bool, optional
            Create histogram (default from settings).
        use_summary : bool, optional
            Create summary (default from settings).
        sample_rate : float, optional
            Metrics sampling rate (0.0 to 1.0). Default: from settings.
            Use lower values for high-frequency operations to reduce cardinality.
            Example: 0.1 = sample 10% of operations.
        """
        # Get settings for defaults
        settings = get_settings()
        registry = get_registry()

        # Store configuration
        self.name = name
        self._buckets = histogram_buckets or DEFAULT_LATENCY_BUCKETS
        self._quantiles = summary_quantiles or DEFAULT_QUANTILES
        self._use_histogram = use_histogram if use_histogram is not None else settings.use_histogram
        self._use_summary = use_summary if use_summary is not None else settings.use_summary
        self._sample_rate = sample_rate if sample_rate is not None else settings.metrics_sample_rate

        # =================================================================
        # Rate Metric: Total number of requests
        # =================================================================
        # This counter tracks all requests, labeled by:
        # - operation: The specific operation being performed
        # - status: "success" or "failure"
        #
        # Use rate() in PromQL to get requests per second:
        #   rate(order_service_requests_total[5m])
        self.requests_total = Counter(
            name=f"{name}_requests_total",
            documentation=(
                f"Total number of requests for {name}. "
                "Labels: operation (string), status (success/failure)."
            ),
            labelnames=["operation", "status"],
            registry=registry,
        )

        # =================================================================
        # Errors Metric: Total number of errors by type
        # =================================================================
        # This counter tracks errors, labeled by:
        # - operation: The operation that failed
        # - error_type: The type/class of the error
        #
        # Separate from requests_total for detailed error breakdown
        self.errors_total = Counter(
            name=f"{name}_errors_total",
            documentation=(
                f"Total number of errors for {name}. "
                "Labels: operation (string), error_type (string)."
            ),
            labelnames=["operation", "error_type"],
            registry=registry,
        )

        # =================================================================
        # Duration Histogram: Distribution of request latencies
        # =================================================================
        # Histograms are aggregatable across instances!
        # Use histogram_quantile() in PromQL:
        #   histogram_quantile(0.95, rate(..._bucket[5m]))
        if self._use_histogram:
            self.duration_histogram = Histogram(
                name=f"{name}_request_duration_seconds",
                documentation=(
                    f"Request duration distribution for {name} in seconds. "
                    "Use histogram_quantile() for percentiles."
                ),
                labelnames=["operation"],
                buckets=self._buckets,
                registry=registry,
            )
        else:
            self.duration_histogram = None

        # =================================================================
        # Duration Summary: Pre-calculated percentiles
        # =================================================================
        # Summaries provide exact percentiles but are NOT aggregatable!
        # Use only for single-instance deployments.
        if self._use_summary:
            # Note: prometheus_client Summary doesn't support custom quantiles
            # in the same way, so we use the default quantiles
            self.duration_summary = Summary(
                name=f"{name}_request_duration_quantiles",
                documentation=(
                    f"Request duration quantiles for {name}. NOT aggregatable across instances."
                ),
                labelnames=["operation"],
                registry=registry,
            )
        else:
            self.duration_summary = None

    def observe_request(
        self,
        operation: str,
        duration_seconds: float,
        status: Literal["success", "failure"] = "success",
        error_type: str | None = None,
    ) -> None:
        """
        Record a request observation.

        This method updates all relevant RED metrics:
        - Increments the request counter
        - Records duration in histogram/summary
        - Increments error counter if status="failure"

        Parameters
        ----------
        operation : str
            Name of the operation (e.g., "create_order", "get_user").
            This becomes a metric label.

        duration_seconds : float
            How long the operation took in seconds.
            Example: 0.045 for 45 milliseconds

        status : {"success", "failure"}
            Whether the operation succeeded or failed.

        error_type : str, optional
            Type of error if status="failure".
            Typically the exception class name.
            Example: "ValidationError", "TimeoutError"

        Example
        -------
        >>> red = REDMetrics("order_service")
        >>>
        >>> # Record successful request
        >>> red.observe_request(
        ...     operation="create_order",
        ...     duration_seconds=0.045,
        ...     status="success",
        ... )
        >>>
        >>> # Record failed request
        >>> red.observe_request(
        ...     operation="create_order",
        ...     duration_seconds=0.012,
        ...     status="failure",
        ...     error_type="ValidationError",
        ... )
        """
        # Always record errors (not sampled) to ensure error visibility
        if status == "failure":
            error_label = error_type or "UnknownError"
            self.errors_total.labels(operation=operation, error_type=error_label).inc()

        # Apply sampling for success metrics - skip if not sampled
        # nosec B311 - random is used for metric sampling, not security
        if self._sample_rate < 1.0 and random.random() > self._sample_rate:  # nosec B311
            return  # Skip this observation (errors already recorded above)

        # Increment request counter (when sampled)
        self.requests_total.labels(operation=operation, status=status).inc()

        # Record duration in histogram if enabled
        if self.duration_histogram is not None:  # pragma: no branch
            self.duration_histogram.labels(operation=operation).observe(duration_seconds)

        # Record duration in summary if enabled
        if self.duration_summary is not None:  # pragma: no branch
            self.duration_summary.labels(operation=operation).observe(duration_seconds)

    def observe_error(
        self,
        operation: str,
        error_type: str,
    ) -> None:
        """
        Record an error observation (separate from request).

        Use this when you want to track errors that aren't tied to a
        specific request duration, such as background job failures.

        Parameters
        ----------
        operation : str
            Name of the operation that failed.

        error_type : str
            Type of error.
            Example: "ConnectionError", "ValidationError"

        Example
        -------
        >>> red = REDMetrics("background_worker")
        >>>
        >>> try:
        ...     process_job(job)
        ... except Exception as e:
        ...     red.observe_error("process_job", type(e).__name__)
        ...     raise
        """
        self.errors_total.labels(operation=operation, error_type=error_type).inc()

    @contextmanager
    def track_request(
        self,
        operation: str,
    ) -> Generator[None, None, None]:
        """
        Context manager for tracking request metrics.

        Automatically measures duration and detects errors, making it
        easy to add metrics to any code block.

        Parameters
        ----------
        operation : str
            Name of the operation being tracked.

        Yields
        ------
        None
            Control is yielded to the with block.

        Example
        -------
        >>> red = REDMetrics("payment_service")
        >>>
        >>> with red.track_request("process_payment"):
        ...     result = gateway.charge(amount)
        ...     if not result.ok:
        ...         raise PaymentError(result.error)
        >>>
        >>> # On success: Records duration with status="success"
        >>> # On exception: Records duration with status="failure" and error_type

        Database operations::

            >>> red = REDMetrics("database")
            >>> with red.track_request("insert_user"):
            ...     cursor.execute("INSERT INTO users ...", params)
            ...     connection.commit()

        External API calls::

            >>> red = REDMetrics("external_api")
            >>> with red.track_request("fetch_weather"):
            ...     response = requests.get("https://api.weather.com/...")
            ...     response.raise_for_status()
        """
        # Record start time with high precision
        start_time = time.perf_counter()

        try:
            # Yield control to the with block
            yield

            # Success path - measure duration and record
            duration = time.perf_counter() - start_time
            self.observe_request(
                operation=operation,
                duration_seconds=duration,
                status="success",
            )

        except Exception as e:
            # Error path - measure duration and record with error type
            duration = time.perf_counter() - start_time
            self.observe_request(
                operation=operation,
                duration_seconds=duration,
                status="failure",
                error_type=type(e).__name__,
            )
            # Re-raise the exception - we only observe, don't suppress
            raise


# =============================================================================
# Module-Level Singleton
# =============================================================================

import threading

# Global REDMetrics instance for the configured service
_red_metrics: REDMetrics | None = None
_red_metrics_lock = threading.Lock()


def get_red_metrics() -> REDMetrics:
    """
    Get the global REDMetrics instance.

    Returns the singleton REDMetrics instance for the configured service.
    Creates one using the service_name from settings if not yet initialized.

    Returns
    -------
    REDMetrics
        The global RED metrics instance.

    Example
    -------
    >>> from obskit.metrics.red import get_red_metrics
    >>>
    >>> # Get the singleton instance
    >>> red = get_red_metrics()
    >>>
    >>> # Record metrics
    >>> red.observe_request("create_order", 0.045)

    Notes
    -----
    The instance is created lazily on first access. To customize the
    service name, call obskit.configure() before using get_red_metrics().

    Thread Safety
    -------------
    This function is thread-safe using double-checked locking pattern.
    """
    global _red_metrics

    # Double-checked locking pattern for thread safety
    if _red_metrics is None:
        with _red_metrics_lock:
            if _red_metrics is None:  # pragma: no branch
                settings = get_settings()
                _red_metrics = REDMetrics(settings.service_name)

    return _red_metrics


def reset_red_metrics() -> None:
    """
    Reset the global REDMetrics instance.

    Primarily used for testing to ensure clean state between tests.

    Warning
    -------
    Do not call this in production code.
    """
    global _red_metrics
    with _red_metrics_lock:
        _red_metrics = None
