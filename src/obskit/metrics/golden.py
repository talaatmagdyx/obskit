"""
Four Golden Signals Implementation
==================================

The Four Golden Signals are a monitoring methodology from Google's SRE book
that provides comprehensive visibility into service health:

1. **Latency**: Time to serve a request
   - Track both successful and failed requests separately
   - Failed requests may be faster (early exit) or slower (timeouts)

2. **Traffic**: Demand on the system
   - Requests per second
   - Can also track other units (transactions, sessions)

3. **Errors**: Rate of failed requests
   - HTTP 5xx errors, timeouts, invalid responses
   - Should include implicit errors (wrong answer, too slow)

4. **Saturation**: How "full" the service is
   - CPU utilization, memory usage
   - Queue depths, concurrent connections
   - The most challenging metric to predict capacity

Why Four Golden Signals?
------------------------
1. **Holistic view**: Covers all aspects of service health
2. **User-focused**: Latency and errors directly impact users
3. **Capacity planning**: Traffic and saturation help plan scaling
4. **Industry standard**: Widely used at Google and beyond

Comparison with RED Method
--------------------------
The Four Golden Signals extend the RED Method:

+-----------------+---------------------+---------------------+
| Aspect          | RED Method          | Four Golden Signals |
+=================+=====================+=====================+
| Rate/Traffic    | Requests/sec        | Requests/sec        |
+-----------------+---------------------+---------------------+
| Errors          | Error count         | Error rate          |
+-----------------+---------------------+---------------------+
| Duration        | Latency histogram   | Latency histogram   |
+-----------------+---------------------+---------------------+
| Saturation      | -                   | Resource usage,     |
|                 |                     | queue depths        |
+-----------------+---------------------+---------------------+

Use RED for simple service monitoring; use Golden Signals when you need
saturation metrics for capacity planning.

Prometheus Metrics Created
--------------------------
For a service named "order_service":

**From RED (inherited):**
    - ``order_service_requests_total{operation, status}``
    - ``order_service_errors_total{operation, error_type}``
    - ``order_service_request_duration_seconds{operation}``

**Saturation Metrics:**
    - ``order_service_saturation{resource}`` - 0.0 to 1.0
    - ``order_service_queue_depth{queue}`` - Current queue size

Example - Complete Monitoring
-----------------------------
.. code-block:: python

    from obskit.metrics import GoldenSignals

    # Create metrics collector
    golden = GoldenSignals("order_service")

    # Track a request (latency + traffic + errors)
    golden.observe_request(
        operation="create_order",
        duration_seconds=0.045,
        status="success",
    )

    # Track saturation metrics
    golden.set_saturation("cpu", 0.75)       # 75% CPU usage
    golden.set_saturation("memory", 0.60)    # 60% memory usage
    golden.set_saturation("connections", 0.45)  # 45% connection pool

    # Track queue depths
    golden.set_queue_depth("order_queue", 42)    # 42 orders waiting
    golden.set_queue_depth("email_queue", 156)   # 156 emails pending

PromQL Queries
--------------
.. code-block:: promql

    # Latency (P95)
    histogram_quantile(0.95,
        sum(rate(order_service_request_duration_seconds_bucket[5m])) by (le, operation)
    )

    # Traffic (requests per second)
    sum(rate(order_service_requests_total[5m])) by (operation)

    # Error rate (percentage)
    sum(rate(order_service_errors_total[5m])) by (operation)
    /
    sum(rate(order_service_requests_total[5m])) by (operation)
    * 100

    # Saturation (by resource)
    order_service_saturation

    # Queue depth trending up
    delta(order_service_queue_depth[1h]) > 0

Alerting Examples
-----------------
.. code-block:: yaml

    groups:
      - name: golden-signals
        rules:
          # Latency SLO breach (P99 > 1s)
          - alert: HighLatency
            expr: |
              histogram_quantile(0.99,
                sum(rate(order_service_request_duration_seconds_bucket[5m])) by (le)
              ) > 1.0
            for: 5m
            labels:
              severity: warning

          # Error budget burn
          - alert: HighErrorRate
            expr: |
              sum(rate(order_service_errors_total[5m]))
              /
              sum(rate(order_service_requests_total[5m]))
              > 0.001
            for: 5m
            labels:
              severity: critical

          # Saturation approaching limit
          - alert: HighSaturation
            expr: order_service_saturation > 0.9
            for: 5m
            labels:
              severity: warning

          # Queue growing
          - alert: QueueGrowing
            expr: delta(order_service_queue_depth[15m]) > 100
            for: 5m
            labels:
              severity: warning

References
----------
- Four Golden Signals: https://sre.google/sre-book/monitoring-distributed-systems/
- Google SRE Book: https://sre.google/sre-book/table-of-contents/
"""

from __future__ import annotations

from typing import Literal

from obskit.config import get_settings
from obskit.metrics.red import REDMetrics
from obskit.metrics.registry import get_registry
from obskit.metrics.types import Gauge


class GoldenSignals:
    """
    Four Golden Signals metrics collector.

    Extends REDMetrics with saturation tracking for comprehensive
    service monitoring following Google SRE best practices.

    The Four Golden Signals are:

    1. **Latency** (from RED): Request duration
    2. **Traffic** (from RED): Request rate
    3. **Errors** (from RED): Error rate
    4. **Saturation** (new): Resource utilization

    Parameters
    ----------
    name : str
        Service name prefix for all metrics.

    histogram_buckets : tuple[float, ...], optional
        Custom latency buckets.

    use_histogram : bool, optional
        Whether to use histograms for latency.

    use_summary : bool, optional
        Whether to use summaries for latency.

    Attributes
    ----------
    red : REDMetrics
        The underlying RED metrics (Rate, Errors, Duration).

    saturation : Gauge
        Resource saturation gauge (0.0 to 1.0).

    queue_depth : Gauge
        Queue depth gauge for tracking pending work.

    Example
    -------
    >>> from obskit.metrics import GoldenSignals
    >>>
    >>> golden = GoldenSignals("order_service")
    >>>
    >>> # Track request (covers Latency, Traffic, Errors)
    >>> golden.observe_request(
    ...     operation="create_order",
    ...     duration_seconds=0.045,
    ...     status="success",
    ... )
    >>>
    >>> # Track Saturation
    >>> golden.set_saturation("cpu", 0.75)
    >>> golden.set_saturation("memory", 0.60)
    >>> golden.set_queue_depth("order_queue", 42)

    Example - Complete Service Monitoring
    -------------------------------------
    >>> golden = GoldenSignals("payment_service")
    >>>
    >>> async def process_payment(payment_id: str, amount: float):
    ...     # Track the request
    ...     start = time.time()
    ...     try:
    ...         result = await gateway.charge(payment_id, amount)
    ...         golden.observe_request(
    ...             "process_payment",
    ...             time.time() - start,
    ...             "success",
    ...         )
    ...         return result
    ...     except Exception as e:
    ...         golden.observe_request(
    ...             "process_payment",
    ...             time.time() - start,
    ...             "failure",
    ...             type(e).__name__,
    ...         )
    ...         raise
    >>>
    >>> # Background task to update saturation
    >>> async def update_saturation():
    ...     while True:
    ...         golden.set_saturation("cpu", get_cpu_usage())
    ...         golden.set_saturation("memory", get_memory_usage())
    ...         golden.set_saturation("connections", get_pool_usage())
    ...         golden.set_queue_depth("pending", get_queue_size())
    ...         await asyncio.sleep(15)  # Update every 15s
    """

    def __init__(
        self,
        name: str,
        histogram_buckets: tuple[float, ...] | None = None,
        use_histogram: bool | None = None,
        use_summary: bool | None = None,
    ) -> None:
        """
        Initialize Four Golden Signals metrics.

        Parameters
        ----------
        name : str
            Service name prefix.
        histogram_buckets : tuple[float, ...], optional
            Custom latency buckets.
        use_histogram : bool, optional
            Use histograms (default from settings).
        use_summary : bool, optional
            Use summaries (default from settings).
        """
        # Get settings and registry
        self._settings = get_settings()
        registry = get_registry()

        # Store configuration
        self.name = name

        # =================================================================
        # Inherit RED Metrics (Latency, Traffic, Errors)
        # =================================================================
        # REDMetrics provides:
        # - requests_total (Traffic)
        # - errors_total (Errors)
        # - duration_histogram/summary (Latency)
        self.red = REDMetrics(
            name=name,
            histogram_buckets=histogram_buckets,
            use_histogram=use_histogram,
            use_summary=use_summary,
        )

        # =================================================================
        # Saturation Gauge
        # =================================================================
        # Track how "full" resources are, from 0.0 (empty) to 1.0 (full)
        # Labels:
        # - resource: What resource is being measured (cpu, memory, etc.)
        self.saturation = Gauge(
            name=f"{name}_saturation",
            documentation=(
                f"Resource saturation for {name} (0.0-1.0). "
                "1.0 means the resource is completely saturated. "
                "Label: resource (cpu, memory, connections, etc.)"
            ),
            labelnames=["resource"],
            registry=registry,
        )

        # =================================================================
        # Queue Depth Gauge
        # =================================================================
        # Track pending work in queues
        # Labels:
        # - queue: Name of the queue being measured
        self.queue_depth = Gauge(
            name=f"{name}_queue_depth",
            documentation=(
                f"Queue depth (pending items) for {name}. "
                "Higher values indicate more pending work. "
                "Label: queue (name of the queue)"
            ),
            labelnames=["queue"],
            registry=registry,
        )

    def observe_request(
        self,
        operation: str,
        duration_seconds: float,
        status: Literal["success", "failure"] = "success",
        error_type: str | None = None,
    ) -> None:
        """
        Record a request observation (Latency, Traffic, Errors).

        Delegates to the underlying REDMetrics for request tracking.

        Parameters
        ----------
        operation : str
            Name of the operation.

        duration_seconds : float
            Request duration in seconds.

        status : {"success", "failure"}
            Request outcome.

        error_type : str, optional
            Error type if status="failure".

        Example
        -------
        >>> golden = GoldenSignals("api")
        >>>
        >>> # Successful request
        >>> golden.observe_request("get_user", 0.023, "success")
        >>>
        >>> # Failed request
        >>> golden.observe_request("get_user", 0.001, "failure", "NotFoundError")
        """
        self.red.observe_request(
            operation=operation,
            duration_seconds=duration_seconds,
            status=status,
            error_type=error_type,
        )

    def set_saturation(
        self,
        resource: str,
        value: float,
    ) -> None:
        """
        Set the saturation level for a resource.

        Saturation measures how "full" a resource is. A value of 1.0
        means the resource is completely saturated (at capacity).

        Parameters
        ----------
        resource : str
            Name of the resource being measured.
            Common values: "cpu", "memory", "disk", "connections", "threads"

        value : float
            Saturation level from 0.0 (empty) to 1.0 (full).
            Values > 1.0 indicate over-saturation (work is queuing).

        Example
        -------
        >>> golden = GoldenSignals("order_service")
        >>>
        >>> # Track various resource saturation
        >>> golden.set_saturation("cpu", 0.75)           # 75% CPU
        >>> golden.set_saturation("memory", 0.60)        # 60% memory
        >>> golden.set_saturation("connections", 0.45)   # 45% of connection pool
        >>> golden.set_saturation("disk_io", 0.30)       # 30% disk I/O
        >>>
        >>> # Over-saturation (> 1.0)
        >>> golden.set_saturation("threads", 1.2)        # 120% - threads queuing

        Example - Background Monitoring
        -------------------------------
        >>> import psutil
        >>>
        >>> async def monitor_saturation():
        ...     while True:
        ...         golden.set_saturation("cpu", psutil.cpu_percent() / 100)
        ...         golden.set_saturation("memory", psutil.virtual_memory().percent / 100)
        ...         golden.set_saturation("disk", psutil.disk_usage('/').percent / 100)
        ...         await asyncio.sleep(15)
        """
        self.saturation.labels(resource=resource).set(value)

    def set_queue_depth(
        self,
        queue: str,
        depth: int,
    ) -> None:
        """
        Set the current depth of a queue.

        Queue depth is a key saturation metric that shows how much
        work is waiting to be processed.

        Parameters
        ----------
        queue : str
            Name of the queue.

        depth : int
            Number of items currently in the queue.

        Example
        -------
        >>> golden = GoldenSignals("order_service")
        >>>
        >>> # Track different queues
        >>> golden.set_queue_depth("pending_orders", 42)
        >>> golden.set_queue_depth("email_notifications", 156)
        >>> golden.set_queue_depth("payment_retries", 7)

        Example - Integration with Message Queue
        ----------------------------------------
        >>> from redis import Redis
        >>>
        >>> redis = Redis()
        >>>
        >>> async def monitor_queues():
        ...     while True:
        ...         golden.set_queue_depth(
        ...             "orders",
        ...             redis.llen("order_queue"),
        ...         )
        ...         golden.set_queue_depth(
        ...             "notifications",
        ...             redis.llen("notification_queue"),
        ...         )
        ...         await asyncio.sleep(10)
        """
        self.queue_depth.labels(queue=queue).set(depth)

    def inc_queue_depth(self, queue: str, amount: int = 1) -> None:
        """
        Increment queue depth by a specified amount.

        Use this when adding items to a queue.

        Parameters
        ----------
        queue : str
            Name of the queue.

        amount : int, default=1
            Amount to increment by.

        Example
        -------
        >>> golden.inc_queue_depth("orders", 5)  # Added 5 orders
        """
        self.queue_depth.labels(queue=queue).inc(amount)

    def dec_queue_depth(self, queue: str, amount: int = 1) -> None:
        """
        Decrement queue depth by a specified amount.

        Use this when processing items from a queue.

        Parameters
        ----------
        queue : str
            Name of the queue.

        amount : int, default=1
            Amount to decrement by.

        Example
        -------
        >>> golden.dec_queue_depth("orders", 1)  # Processed 1 order
        """
        self.queue_depth.labels(queue=queue).dec(amount)

    def set_progress(
        self,
        operation: str,
        progress_percent: float,
        total_items: int | None = None,
        completed_items: int | None = None,
    ) -> None:
        """
        Track progress for long-running operations.

        This is useful for batch processing, data migrations, and other
        long-running operations where you want to track completion percentage.

        Parameters
        ----------
        operation : str
            Name of the operation being tracked.

        progress_percent : float
            Progress percentage from 0.0 to 100.0.

        total_items : int, optional
            Total number of items to process.

        completed_items : int, optional
            Number of items completed.

        Example
        -------
        >>> golden = GoldenSignals("batch_processor")
        >>>
        >>> # Track batch job progress
        >>> golden.set_progress(
        ...     operation="process_orders",
        ...     progress_percent=45.5,
        ...     total_items=1000,
        ...     completed_items=455,
        ... )
        >>>
        >>> # In Prometheus/Grafana:
        >>> # batch_processor_progress{operation="process_orders"} 45.5
        >>> # batch_processor_total_items{operation="process_orders"} 1000
        >>> # batch_processor_completed_items{operation="process_orders"} 455
        """
        # Create progress gauge if it doesn't exist
        if not hasattr(self, "_progress_gauges"):
            from obskit.metrics.types import Gauge

            registry = get_registry()

            self._progress_gauges = {
                "progress": Gauge(
                    name=f"{self.name}_progress",
                    documentation=f"Progress percentage for {self.name} operations",
                    labelnames=["operation"],
                    registry=registry,
                ),
                "total_items": Gauge(
                    name=f"{self.name}_total_items",
                    documentation=f"Total items for {self.name} operations",
                    labelnames=["operation"],
                    registry=registry,
                ),
                "completed_items": Gauge(
                    name=f"{self.name}_completed_items",
                    documentation=f"Completed items for {self.name} operations",
                    labelnames=["operation"],
                    registry=registry,
                ),
            }

        # Set progress metrics
        self._progress_gauges["progress"].labels(operation=operation).set(progress_percent)

        if total_items is not None:
            self._progress_gauges["total_items"].labels(operation=operation).set(total_items)

        if completed_items is not None:
            self._progress_gauges["completed_items"].labels(operation=operation).set(
                completed_items
            )


# =============================================================================
# Module-Level Singleton
# =============================================================================

import threading

_golden_signals: GoldenSignals | None = None
_golden_signals_lock = threading.Lock()


def get_golden_signals() -> GoldenSignals:
    """
    Get the global GoldenSignals instance.

    Returns
    -------
    GoldenSignals
        The global Four Golden Signals metrics instance.

    Thread Safety
    -------------
    This function is thread-safe using double-checked locking pattern.
    """
    global _golden_signals

    # Double-checked locking pattern for thread safety
    if _golden_signals is None:
        with _golden_signals_lock:
            if _golden_signals is None:  # pragma: no branch
                settings = get_settings()
                _golden_signals = GoldenSignals(settings.service_name)

    return _golden_signals


def reset_golden_signals() -> None:
    """Reset for testing."""
    global _golden_signals
    with _golden_signals_lock:
        _golden_signals = None
