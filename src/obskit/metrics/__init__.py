"""
Metrics Module for obskit
=========================

This module provides Prometheus metrics implementations following three
industry-standard methodologies:

1. **RED Method** (REDMetrics)
   - Rate: Number of requests per second
   - Errors: Number of failed requests
   - Duration: Time taken to serve requests

   Best for: Service endpoints, API calls, business operations
   Reference: https://grafana.com/blog/the-red-method-how-to-instrument-your-services/

2. **Four Golden Signals** (GoldenSignals)
   - Latency: Time to serve requests
   - Traffic: Demand on the system (requests/sec)
   - Errors: Rate of failed requests
   - Saturation: How "full" the service is

   Best for: Comprehensive service monitoring with capacity planning
   Reference: https://sre.google/sre-book/monitoring-distributed-systems/

3. **USE Method** (USEMetrics)
   - Utilization: % time resource was busy
   - Saturation: Work queued (waiting)
   - Errors: Error event count

   Best for: Infrastructure monitoring (CPU, memory, disk, network)
   Reference: https://www.brendangregg.com/usemethod.html

Quick Reference
---------------

+-----------------+------------------+------------------+------------------+
| Methodology     | Focus            | Key Metrics      | Use Case         |
+=================+==================+==================+==================+
| RED Method      | User experience  | Rate, Errors,    | Service          |
|                 |                  | Duration         | endpoints        |
+-----------------+------------------+------------------+------------------+
| Golden Signals  | Service health   | Latency, Traffic,| Complete         |
|                 |                  | Errors, Satur.   | monitoring       |
+-----------------+------------------+------------------+------------------+
| USE Method      | Resources        | Utilization,     | Infrastructure   |
|                 |                  | Saturation, Err. | (CPU, mem, etc.) |
+-----------------+------------------+------------------+------------------+

Quick Start
-----------
.. code-block:: python

    from obskit.metrics import REDMetrics, GoldenSignals, USEMetrics

    # RED Method for API endpoints
    red = REDMetrics("order_service")
    red.observe_request(
        operation="create_order",
        duration_seconds=0.045,
        status="success",
    )

    # Golden Signals for complete monitoring
    golden = GoldenSignals("order_service")
    golden.observe_request("create_order", duration_seconds=0.045)
    golden.set_saturation("cpu", 0.75)
    golden.set_queue_depth("order_queue", 42)

    # USE Method for infrastructure
    cpu = USEMetrics("server_cpu")
    cpu.set_utilization("cpu", 0.65)
    cpu.set_saturation("cpu", 3)

Histogram vs Summary
--------------------
obskit supports both Prometheus Histograms and Summaries for latency:

**Histograms** (default, recommended):
    - Aggregatable across instances (can calculate percentiles from multiple pods)
    - Configurable buckets
    - Works with Prometheus histogram_quantile() function
    - Slight loss of precision at bucket boundaries

**Summaries**:
    - Pre-calculated exact percentiles
    - NOT aggregatable (can't combine across instances)
    - More expensive to calculate
    - Best for single-instance deployments

.. code-block:: python

    # Use both histogram and summary
    red = REDMetrics(
        "order_service",
        use_histogram=True,   # For aggregation (default)
        use_summary=True,     # For exact percentiles
    )

Prometheus Queries
------------------
Common PromQL queries for RED metrics:

.. code-block:: promql

    # Request rate (requests per second)
    sum(rate(order_service_requests_total[5m])) by (operation)

    # Error rate (percentage)
    sum(rate(order_service_errors_total[5m])) by (operation)
    /
    sum(rate(order_service_requests_total[5m])) by (operation)

    # P95 latency (from histogram)
    histogram_quantile(0.95,
        sum(rate(order_service_request_duration_seconds_bucket[5m])) by (le, operation)
    )

    # P99 latency (from histogram)
    histogram_quantile(0.99,
        sum(rate(order_service_request_duration_seconds_bucket[5m])) by (le, operation)
    )

Starting Metrics Server
-----------------------
.. code-block:: python

    from obskit.metrics import start_http_server

    # Start Prometheus metrics server
    start_http_server(port=9090)

    # Metrics now available at http://localhost:9090/metrics

Using with ASGI Middleware
--------------------------
.. code-block:: python

    from obskit.metrics.registry import MetricsMiddleware
    from starlette.applications import Starlette

    app = Starlette()
    app.add_middleware(MetricsMiddleware, path="/metrics")

See Also
--------
obskit.decorators : Automatic metrics via decorators
obskit.slo : SLO tracking with error budgets
"""

from obskit.metrics.golden import GoldenSignals
from obskit.metrics.red import REDMetrics
from obskit.metrics.registry import get_registry, start_http_server
from obskit.metrics.self_metrics import (
    get_self_metrics,
    record_dropped_metric,
    record_error,
    update_queue_metrics,
)
from obskit.metrics.types import Counter, Gauge, Histogram, Summary
from obskit.metrics.use import USEMetrics

__all__ = [
    # ==========================================================================
    # Metrics Methodologies
    # ==========================================================================
    # RED Method (Rate, Errors, Duration)
    # Best for: Service endpoints, API calls
    "REDMetrics",
    # Four Golden Signals (Latency, Traffic, Errors, Saturation)
    # Best for: Complete service monitoring
    "GoldenSignals",
    # USE Method (Utilization, Saturation, Errors)
    # Best for: Infrastructure monitoring
    "USEMetrics",
    # ==========================================================================
    # Prometheus Metric Types
    # ==========================================================================
    # Counter: Monotonically increasing value (requests, errors)
    "Counter",
    # Gauge: Value that can go up and down (temperature, queue size)
    "Gauge",
    # Histogram: Distribution of values in buckets (latency)
    "Histogram",
    # Summary: Pre-calculated percentiles (latency)
    "Summary",
    # ==========================================================================
    # Registry and Server
    # ==========================================================================
    # Get Prometheus registry for custom metrics
    "get_registry",
    # Start HTTP server for /metrics endpoint
    "start_http_server",
    # ==========================================================================
    # Self-Monitoring Metrics
    # ==========================================================================
    # Get obskit's internal metrics
    "get_self_metrics",
    # Record dropped metric event
    "record_dropped_metric",
    # Record internal error
    "record_error",
    # Update queue metrics
    "update_queue_metrics",
]
