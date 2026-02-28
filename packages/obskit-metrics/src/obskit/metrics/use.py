"""
USE Method Implementation
=========================

The USE Method is an infrastructure monitoring methodology created by
Brendan Gregg that provides systematic analysis of system resources:

- **U**tilization: Percentage of time the resource was busy
- **S**aturation: Degree to which resource has extra work it can't service
- **E**rrors: Count of error events

Why USE Method?
---------------
1. **Complete coverage**: Ensures no resource is overlooked
2. **Systematic**: Works through all resources methodically
3. **Problem detection**: Identifies bottlenecks and errors quickly
4. **Capacity planning**: Shows when resources need scaling

Target Resources
----------------
The USE Method applies to each physical/logical resource:

+-----------+-------------------+-------------------+------------------+
| Resource  | Utilization       | Saturation        | Errors           |
+===========+===================+===================+==================+
| CPU       | % time busy       | Run queue length  | ECC errors       |
+-----------+-------------------+-------------------+------------------+
| Memory    | % used            | Swap usage,       | Allocation       |
|           |                   | OOM kills         | failures         |
+-----------+-------------------+-------------------+------------------+
| Disk      | % busy            | I/O queue depth   | Read/write       |
|           |                   |                   | errors           |
+-----------+-------------------+-------------------+------------------+
| Network   | % bandwidth       | TCP retransmits,  | Interface        |
|           |                   | buffer overflow   | errors           |
+-----------+-------------------+-------------------+------------------+
| DB Pool   | % connections     | Waiting threads   | Connection       |
|           | in use            |                   | failures         |
+-----------+-------------------+-------------------+------------------+

Difference from RED/Golden Signals
----------------------------------
+------------+---------------------------+---------------------------+
| Aspect     | RED/Golden Signals        | USE Method                |
+============+===========================+===========================+
| Focus      | Service (user experience) | Resource (system health)  |
+------------+---------------------------+---------------------------+
| Metrics    | Rate, Errors, Duration    | Utilization, Saturation,  |
|            | (+ Saturation for Golden) | Errors                    |
+------------+---------------------------+---------------------------+
| Use Case   | API endpoints, business   | CPU, memory, disk,        |
|            | operations                | network, DB connections   |
+------------+---------------------------+---------------------------+
| Question   | "Are users happy?"        | "Are resources healthy?"  |
+------------+---------------------------+---------------------------+

Prometheus Metrics Created
--------------------------
For a resource category named "server":

- ``server_utilization{resource}`` - Value 0.0 to 1.0
- ``server_saturation{resource}`` - Arbitrary positive value
- ``server_errors_total{resource, error_type}`` - Counter

Example - Complete Infrastructure Monitoring
--------------------------------------------
.. code-block:: python

    from obskit.metrics import USEMetrics
    import psutil

    # Create USE metrics for server resources
    cpu_use = USEMetrics("server_cpu")
    memory_use = USEMetrics("server_memory")
    disk_use = USEMetrics("server_disk")
    network_use = USEMetrics("server_network")

    def collect_metrics():
        # CPU metrics
        cpu_use.set_utilization("cpu", psutil.cpu_percent() / 100)
        cpu_use.set_saturation("cpu", len(psutil.Process().cpu_num()))

        # Memory metrics
        mem = psutil.virtual_memory()
        memory_use.set_utilization("memory", mem.percent / 100)
        memory_use.set_saturation("memory", psutil.swap_memory().percent / 100)

        # Disk metrics
        disk = psutil.disk_usage('/')
        disk_use.set_utilization("disk", disk.percent / 100)
        io = psutil.disk_io_counters()
        disk_use.set_saturation("disk", io.busy_time if hasattr(io, 'busy_time') else 0)

        # Network metrics
        net = psutil.net_io_counters()
        network_use.inc_error("network", "drops", net.dropin + net.dropout)

Example - Database Connection Pool
----------------------------------
.. code-block:: python

    from obskit.metrics import USEMetrics

    db_pool = USEMetrics("database_pool")

    class ConnectionPool:
        def __init__(self, max_size: int = 10):
            self.max_size = max_size
            self.in_use = 0
            self.waiting = 0

        def get_connection(self):
            # Update utilization
            db_pool.set_utilization(
                "connections",
                self.in_use / self.max_size
            )
            # Update saturation (waiting threads)
            db_pool.set_saturation("connections", self.waiting)

            if self.in_use >= self.max_size:
                self.waiting += 1
                db_pool.set_saturation("connections", self.waiting)
                # Wait for connection...

            try:
                conn = self._acquire()
                self.in_use += 1
                return conn
            except Exception as e:
                db_pool.inc_error("connections", type(e).__name__)
                raise

PromQL Queries
--------------
.. code-block:: promql

    # High utilization resources (> 80%)
    {__name__=~".*_utilization"} > 0.8

    # Saturated resources (any saturation)
    {__name__=~".*_saturation"} > 0

    # Error rate by resource
    sum(rate({__name__=~".*_errors_total"}[5m])) by (resource, error_type)

    # CPU utilization trend
    avg_over_time(server_cpu_utilization[1h])

    # Memory saturation spikes
    max_over_time(server_memory_saturation[1h])

Alerting Examples
-----------------
.. code-block:: yaml

    groups:
      - name: use-alerts
        rules:
          # High CPU utilization
          - alert: HighCPUUtilization
            expr: server_cpu_utilization > 0.9
            for: 10m
            labels:
              severity: warning
            annotations:
              summary: "CPU utilization > 90% for 10 minutes"

          # CPU saturation (processes waiting)
          - alert: CPUSaturation
            expr: server_cpu_saturation > 10
            for: 5m
            labels:
              severity: critical
            annotations:
              summary: "{{ $value }} processes waiting for CPU"

          # Memory near exhaustion
          - alert: MemoryNearExhaustion
            expr: server_memory_utilization > 0.95
            for: 5m
            labels:
              severity: critical
            annotations:
              summary: "Memory > 95% utilized"

          # Disk errors
          - alert: DiskErrors
            expr: rate(server_disk_errors_total[5m]) > 0
            for: 1m
            labels:
              severity: critical
            annotations:
              summary: "Disk errors detected"

References
----------
- USE Method: https://www.brendangregg.com/usemethod.html
- Brendan Gregg's Blog: https://www.brendangregg.com/
- Systems Performance Book: https://www.brendangregg.com/systems-performance-2nd-edition-book.html
"""

from __future__ import annotations

from obskit.metrics.registry import get_registry
from obskit.metrics.types import Counter, Gauge


class USEMetrics:
    """
    USE Method metrics collector for infrastructure monitoring.

    The USE Method provides three metrics for each resource:

    - **Utilization**: Percentage of time resource was busy (0.0-1.0)
    - **Saturation**: Extra work queued/waiting (0 = no waiting)
    - **Errors**: Count of error events

    Parameters
    ----------
    name : str
        Resource category name prefix.
        Example: "server_cpu", "database_pool", "message_queue"

    Attributes
    ----------
    name : str
        Resource category name.

    utilization : Gauge
        Resource utilization gauge (0.0 to 1.0).

    saturation : Gauge
        Resource saturation gauge (0 = no waiting).

    errors : Counter
        Error counter by resource and type.

    Example
    -------
    >>> from obskit.metrics import USEMetrics
    >>>
    >>> # Create USE metrics for CPU
    >>> cpu = USEMetrics("server_cpu")
    >>>
    >>> # Set utilization (70% busy)
    >>> cpu.set_utilization("cpu", 0.70)
    >>>
    >>> # Set saturation (5 processes waiting)
    >>> cpu.set_saturation("cpu", 5)
    >>>
    >>> # Record errors
    >>> cpu.inc_error("cpu", "thermal_throttle")

    Example - Database Connection Pool Monitoring
    ---------------------------------------------
    >>> pool_use = USEMetrics("database_pool")
    >>>
    >>> class DatabasePool:
    ...     def __init__(self, max_connections: int):
    ...         self.max = max_connections
    ...         self.active = 0
    ...         self.waiting = 0
    ...
    ...     def get_connection(self):
    ...         # Update metrics
    ...         pool_use.set_utilization(
    ...             "connections",
    ...             self.active / self.max
    ...         )
    ...         pool_use.set_saturation("connections", self.waiting)
    ...
    ...         if self.active >= self.max:
    ...             self.waiting += 1
    ...             pool_use.set_saturation("connections", self.waiting)
    ...             # Wait...
    ...
    ...         try:
    ...             conn = self._acquire()
    ...             self.active += 1
    ...             return conn
    ...         except ConnectionError as e:
    ...             pool_use.inc_error("connections", "connection_failed")
    ...             raise

    Example - System Resource Monitoring with psutil
    ------------------------------------------------
    >>> import psutil
    >>>
    >>> cpu_use = USEMetrics("system_cpu")
    >>> memory_use = USEMetrics("system_memory")
    >>> disk_use = USEMetrics("system_disk")
    >>>
    >>> def collect_system_metrics():
    ...     '''Collect system metrics every 15 seconds.'''
    ...     # CPU utilization (0.0 to 1.0)
    ...     cpu_use.set_utilization("cpu", psutil.cpu_percent() / 100)
    ...
    ...     # CPU saturation (load average / num CPUs)
    ...     load = psutil.getloadavg()[0]
    ...     cpu_use.set_saturation("cpu", load / psutil.cpu_count())
    ...
    ...     # Memory utilization
    ...     mem = psutil.virtual_memory()
    ...     memory_use.set_utilization("memory", mem.percent / 100)
    ...
    ...     # Memory saturation (swap usage as proxy)
    ...     swap = psutil.swap_memory()
    ...     memory_use.set_saturation("memory", swap.percent / 100)
    ...
    ...     # Disk utilization
    ...     disk = psutil.disk_usage('/')
    ...     disk_use.set_utilization("disk", disk.percent / 100)
    """

    def __init__(self, name: str) -> None:
        """
        Initialize USE metrics for a resource category.

        Parameters
        ----------
        name : str
            Resource category name prefix for all metrics.
            This appears in metric names like "{name}_utilization".
        """
        # Get registry for metric registration
        registry = get_registry()

        # Store configuration
        self.name = name

        # =================================================================
        # Utilization Gauge
        # =================================================================
        # Measures the percentage of time the resource was busy.
        # Value range: 0.0 (idle) to 1.0 (fully utilized)
        #
        # For some resources (like CPU), you may occasionally see > 1.0
        # if hyperthreading or multiple cores are involved.
        self.utilization = Gauge(
            name=f"{name}_utilization",
            documentation=(
                f"Resource utilization for {name} (0.0-1.0). "
                "Measures the proportion of time the resource is busy. "
                "Label: resource (specific resource identifier)"
            ),
            labelnames=["resource"],
            registry=registry,
        )

        # =================================================================
        # Saturation Gauge
        # =================================================================
        # Measures queued or waiting work that the resource can't service.
        # Value: 0 means no saturation, positive values indicate waiting work.
        #
        # Examples:
        # - CPU: Run queue length (processes waiting to execute)
        # - Disk: I/O queue depth (requests waiting)
        # - Network: Socket buffer fullness, retransmits
        # - DB Pool: Threads waiting for connections
        self.saturation = Gauge(
            name=f"{name}_saturation",
            documentation=(
                f"Resource saturation for {name}. "
                "Measures queued work that can't be serviced. "
                "0 = no waiting, higher = more saturation. "
                "Label: resource (specific resource identifier)"
            ),
            labelnames=["resource"],
            registry=registry,
        )

        # =================================================================
        # Errors Counter
        # =================================================================
        # Counts error events for the resource.
        #
        # Examples:
        # - CPU: ECC memory errors, thermal throttling
        # - Disk: Read/write errors, bad sectors
        # - Network: CRC errors, drops, collisions
        # - DB Pool: Connection failures, timeouts
        self.errors = Counter(
            name=f"{name}_errors_total",
            documentation=(
                f"Total error events for {name}. "
                "Labels: resource (identifier), error_type (type of error)"
            ),
            labelnames=["resource", "error_type"],
            registry=registry,
        )

    def set_utilization(self, resource: str, value: float) -> None:
        """
        Set the utilization level for a resource.

        Utilization measures what percentage of time the resource was
        busy serving requests (not idle).

        Parameters
        ----------
        resource : str
            Specific resource identifier.
            Examples: "cpu", "memory", "disk_sda", "eth0"

        value : float
            Utilization level from 0.0 (idle) to 1.0 (fully busy).
            Some resources may report > 1.0 (e.g., multi-core CPU average).

        Example
        -------
        >>> use = USEMetrics("server")
        >>>
        >>> # CPU 75% utilized
        >>> use.set_utilization("cpu", 0.75)
        >>>
        >>> # Memory 60% used
        >>> use.set_utilization("memory", 0.60)
        >>>
        >>> # Specific disk 45% busy
        >>> use.set_utilization("disk_sda", 0.45)
        >>>
        >>> # Network interface 30% of bandwidth
        >>> use.set_utilization("eth0", 0.30)

        Notes
        -----
        - Utilization should be measured over a time window (e.g., last 15s)
        - High utilization (> 0.7) often leads to saturation
        - Some resources are fine at 100% utilization (batch processing)
        """
        self.utilization.labels(resource=resource).set(value)

    def set_saturation(self, resource: str, value: float) -> None:
        """
        Set the saturation level for a resource.

        Saturation measures work that can't be serviced - queued or
        waiting work. Zero means no saturation (all work processed
        immediately). Higher values indicate queueing/waiting.

        Parameters
        ----------
        resource : str
            Specific resource identifier.

        value : float
            Saturation level. 0 = no waiting.
            The interpretation depends on the resource:
            - CPU: Run queue length (processes waiting)
            - Memory: Swap usage percentage
            - Disk: I/O queue depth
            - Network: Buffer fullness, retransmit rate

        Example
        -------
        >>> use = USEMetrics("server")
        >>>
        >>> # CPU: 3 processes waiting (run queue)
        >>> use.set_saturation("cpu", 3)
        >>>
        >>> # Memory: 10% of swap used (memory pressure)
        >>> use.set_saturation("memory", 0.10)
        >>>
        >>> # Disk: 8 I/O requests queued
        >>> use.set_saturation("disk", 8)
        >>>
        >>> # Network: 15% buffer usage
        >>> use.set_saturation("network", 0.15)

        Notes
        -----
        - Saturation > 0 indicates resource contention
        - Some saturation is normal under load
        - High saturation without high utilization indicates a bottleneck
        """
        self.saturation.labels(resource=resource).set(value)

    def inc_error(
        self,
        resource: str,
        error_type: str,
        count: int = 1,
    ) -> None:
        """
        Increment the error counter for a resource.

        Error events indicate problems with the resource that may
        cause data corruption, performance issues, or failures.

        Parameters
        ----------
        resource : str
            Specific resource identifier.

        error_type : str
            Type/category of the error.
            Examples: "read_error", "timeout", "crc_error", "overflow"

        count : int, default=1
            Number of errors to record.

        Example
        -------
        >>> use = USEMetrics("server")
        >>>
        >>> # Single disk read error
        >>> use.inc_error("disk_sda", "read_error")
        >>>
        >>> # Network dropped 5 packets
        >>> use.inc_error("eth0", "rx_dropped", 5)
        >>>
        >>> # CPU thermal throttle event
        >>> use.inc_error("cpu0", "thermal_throttle")
        >>>
        >>> # Memory ECC correction
        >>> use.inc_error("dimm0", "ecc_corrected")

        Common Error Types by Resource
        ------------------------------
        - **CPU**: thermal_throttle, ecc_error, mce (machine check)
        - **Memory**: ecc_corrected, ecc_uncorrected, oom_kill
        - **Disk**: read_error, write_error, bad_sector, timeout
        - **Network**: crc_error, rx_dropped, tx_dropped, overflow
        - **DB Pool**: connection_failed, timeout, max_connections
        """
        self.errors.labels(resource=resource, error_type=error_type).inc(count)

    def observe_all(
        self,
        resource: str,
        utilization: float | None = None,
        saturation: float | None = None,
        errors: dict[str, int] | None = None,
    ) -> None:
        """
        Convenience method to update all USE metrics at once.

        Parameters
        ----------
        resource : str
            Resource identifier.

        utilization : float, optional
            Utilization value (0.0-1.0).

        saturation : float, optional
            Saturation value.

        errors : dict[str, int], optional
            Dictionary of error_type -> count.

        Example
        -------
        >>> use = USEMetrics("database_pool")
        >>>
        >>> use.observe_all(
        ...     resource="connections",
        ...     utilization=0.80,
        ...     saturation=3,  # 3 threads waiting
        ...     errors={"timeout": 1},
        ... )
        """
        if utilization is not None:  # pragma: no branch
            self.set_utilization(resource, utilization)

        if saturation is not None:  # pragma: no branch
            self.set_saturation(resource, saturation)

        if errors:
            for error_type, count in errors.items():
                self.inc_error(resource, error_type, count)


# =============================================================================
# Convenience Functions for Common Resources
# =============================================================================


def create_system_metrics() -> dict[str, USEMetrics]:
    """
    Create USE metrics for common system resources.

    This is a convenience function that creates USEMetrics instances
    for CPU, memory, disk, and network - the most common resources.

    Returns
    -------
    dict[str, USEMetrics]
        Dictionary with keys: "cpu", "memory", "disk", "network"

    Example
    -------
    >>> from obskit.metrics.use import create_system_metrics
    >>>
    >>> metrics = create_system_metrics()
    >>>
    >>> # Use individual metrics
    >>> metrics["cpu"].set_utilization("cpu", 0.75)
    >>> metrics["memory"].set_utilization("memory", 0.60)
    >>> metrics["disk"].set_saturation("disk", 5)
    >>> metrics["network"].inc_error("eth0", "dropped")
    """
    return {
        "cpu": USEMetrics("system_cpu"),
        "memory": USEMetrics("system_memory"),
        "disk": USEMetrics("system_disk"),
        "network": USEMetrics("system_network"),
    }


# =============================================================================
# Module-Level Singleton
# =============================================================================

import threading

_use_metrics: dict[str, USEMetrics] = {}
_use_metrics_lock = threading.Lock()


def get_use_metrics(name: str) -> USEMetrics:
    """
    Get or create a USEMetrics instance for a resource.

    This provides a simple way to get USEMetrics instances without
    managing their lifecycle manually.

    Parameters
    ----------
    name : str
        Resource category name.

    Returns
    -------
    USEMetrics
        The USE metrics instance for this resource.

    Example
    -------
    >>> from obskit.metrics.use import get_use_metrics
    >>>
    >>> # Get metrics (creates if needed)
    >>> cpu = get_use_metrics("system_cpu")
    >>> cpu.set_utilization("cpu", 0.75)
    >>>
    >>> # Getting again returns same instance
    >>> cpu2 = get_use_metrics("system_cpu")
    >>> assert cpu is cpu2

    Thread Safety
    -------------
    This function is thread-safe using locks to protect dictionary access.
    """
    # Thread-safe dictionary access
    with _use_metrics_lock:
        if name not in _use_metrics:
            _use_metrics[name] = USEMetrics(name)

        return _use_metrics[name]


def reset_use_metrics() -> None:
    """Reset for testing."""
    global _use_metrics
    with _use_metrics_lock:
        _use_metrics = {}
