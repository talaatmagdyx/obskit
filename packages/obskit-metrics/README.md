<div align="center">

# 📊 obskit-metrics

**RED metrics, Four Golden Signals, USE Method, cardinality protection, and trace exemplars for Prometheus**

---

[![PyPI](https://img.shields.io/pypi/v/obskit-metrics.svg?color=blue)](https://pypi.org/project/obskit-metrics/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![obskit](https://img.shields.io/badge/part%20of-obskit-blueviolet.svg)](https://github.com/talaatmagdyx/obskit)

</div>

## What it does

- **Instruments Python microservices** with three proven monitoring methodologies: RED (Rate/Errors/Duration), Four Golden Signals, and USE (Utilization/Saturation/Errors) — choose the right tool for each layer of your stack.
- **Prevents cardinality explosions** in production with a built-in LRU-based guard that replaces unbounded label values (user IDs, order IDs) with a safe fallback before they wreck your Prometheus.
- **Links metric data points to distributed traces** by attaching `trace_id` and `span_id` exemplars to Histogram observations, so a latency spike in Grafana becomes a one-click jump into Grafana Tempo.

---

## Installation

```bash
# Core only (no Prometheus client bundled)
pip install obskit-metrics

# With Prometheus scrape endpoint
pip install "obskit-metrics[prometheus]"

# With OpenTelemetry export
pip install "obskit-metrics[otlp]"

# Everything
pip install "obskit-metrics[prometheus,otlp]"
```

---

## Quick Start

```python
from obskit.metrics import REDMetrics, start_http_server

# Create RED metrics for your service
red = REDMetrics("order_service")

# Auto-timing context manager — records duration, status, and error type
with red.track_request("create_order"):
    order = db.create(payload)

# Or record manually after the fact
red.observe_request(
    operation="validate_payment",
    duration_seconds=0.012,
    status="success",
)

# Expose /metrics on port 9090 for Prometheus to scrape
start_http_server(port=9090)
```

---

## Features

### 1. REDMetrics — Rate, Errors, Duration

The [RED Method](https://grafana.com/blog/the-red-method-how-to-instrument-your-services/) answers the three questions every on-call engineer asks: *How fast? How broken? How slow?*

`REDMetrics` creates three Prometheus metric families automatically:

| Metric | Type | Label |
|---|---|---|
| `{name}_requests_total` | Counter | `operation`, `status` |
| `{name}_errors_total` | Counter | `operation`, `error_type` |
| `{name}_request_duration_seconds` | Histogram | `operation` |

```python
from obskit.metrics import REDMetrics

red = REDMetrics("order_service")

# --- Context manager (recommended) ---
# Measures wall-clock duration, detects exceptions automatically.
# On exception: status="failure", error_type=type(e).__name__
with red.track_request("process_payment"):
    result = payment_gateway.charge(order.total)

# --- Manual observation ---
red.observe_request(
    operation="create_order",
    duration_seconds=0.045,
    status="success",
)

# Record a failure with a specific error type
red.observe_request(
    operation="create_order",
    duration_seconds=0.002,
    status="failure",
    error_type="ValidationError",
)

# Custom histogram buckets for a sub-100ms SLO
fast_red = REDMetrics(
    "payment_gateway",
    histogram_buckets=(0.001, 0.005, 0.010, 0.025, 0.050, 0.100, 0.250),
)

# Low sampling rate for extremely high-throughput operations (10% sample)
sampled_red = REDMetrics("search_service", sample_rate=0.10)
```

### 2. GoldenSignals — Latency, Traffic, Errors, Saturation

[Google's Four Golden Signals](https://sre.google/sre-book/monitoring-distributed-systems/) extend RED with Saturation — the missing link for capacity planning.

`GoldenSignals` wraps a `REDMetrics` instance and adds two Gauge families:

| Metric | Type | Labels |
|---|---|---|
| `{name}_saturation` | Gauge | `resource` |
| `{name}_queue_depth` | Gauge | `queue` |

```python
from obskit.metrics import GoldenSignals
import psutil

golden = GoldenSignals("order_service")

# Track requests (Latency + Traffic + Errors come from the embedded RED)
with golden.red.track_request("checkout"):
    order = fulfillment.process(cart)

# Saturation: how full is each resource? (0.0 = idle, 1.0 = full)
golden.set_saturation("cpu", psutil.cpu_percent() / 100)
golden.set_saturation("memory", psutil.virtual_memory().percent / 100)
golden.set_saturation("db_connections", pool.active / pool.max)

# Queue depth: how much unprocessed work is waiting?
golden.set_queue_depth("order_queue", redis.llen("pending_orders"))
golden.set_queue_depth("email_queue", redis.llen("email_notifications"))

# Background task to keep saturation metrics fresh
import asyncio

async def track_saturation():
    while True:
        golden.set_saturation("cpu", psutil.cpu_percent() / 100)
        golden.set_saturation("memory", psutil.virtual_memory().percent / 100)
        golden.set_queue_depth("order_queue", redis.llen("pending_orders"))
        await asyncio.sleep(15)
```

### 3. USEMetrics — Utilization, Saturation, Errors

The [USE Method](https://www.brendangregg.com/usemethod.html) by Brendan Gregg is designed for *resources*, not services. Use it for CPU, memory, disk I/O, network interfaces, and database connection pools.

```python
from obskit.metrics import USEMetrics
from obskit.metrics.use import create_system_metrics
import psutil

# Create metrics for a specific resource category
pool_use = USEMetrics("database_pool")

class ManagedPool:
    def __init__(self, max_size: int = 20):
        self.max = max_size
        self.active = 0
        self.waiting = 0

    def acquire(self):
        # Utilization: fraction of pool currently checked out
        pool_use.set_utilization("connections", self.active / self.max)
        # Saturation: threads blocked waiting for a connection
        pool_use.set_saturation("connections", self.waiting)

        if self.active >= self.max:
            self.waiting += 1
            try:
                conn = self._wait_for_connection()
            except TimeoutError:
                pool_use.inc_error("connections", "timeout")
                raise
            finally:
                self.waiting -= 1
        else:
            conn = self._acquire_immediate()

        self.active += 1
        return conn

# Convenience function for all four system resources at once
system = create_system_metrics()
system["cpu"].set_utilization("cpu0", psutil.cpu_percent() / 100)
system["memory"].set_utilization("memory", psutil.virtual_memory().percent / 100)
system["disk"].set_saturation("sda", 8)        # 8 I/O requests queued
system["network"].inc_error("eth0", "rx_drop", 3)

# Batch update with observe_all()
pool_use.observe_all(
    resource="connections",
    utilization=0.80,
    saturation=3,
    errors={"timeout": 1},
)
```

### 4. Trace Exemplars — Click from a Spike to the Exact Trace

When `opentelemetry-api` is installed, `observe_with_exemplar()` automatically reads the active span context and attaches `trace_id` and `span_id` to the Prometheus observation. In Grafana, enable "Exemplars" on a histogram panel and each data point becomes a clickable link into Grafana Tempo.

```python
from obskit.metrics.exemplar import observe_with_exemplar, get_trace_exemplar, is_exemplar_available
from prometheus_client import Histogram

# Works with any prometheus_client Histogram or Summary
http_latency = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["method", "route"],
)

# Auto-injects {"trace_id": "4bf92f35...", "span_id": "00f067aa..."} from the active span
observe_with_exemplar(
    http_latency.labels(method="POST", route="/orders"),
    value=0.032,
)

# Check availability at startup
if is_exemplar_available():
    print("Grafana Tempo exemplar links enabled")

# Grafana setup:
# 1. Start Prometheus with --enable-feature=exemplar-storage
# 2. Open a histogram panel in Grafana
# 3. Query → enable "Exemplars" toggle
# 4. Latency spikes now show clickable trace links
```

### 5. Cardinality Guard — Stop Label Explosions Before They Happen

High-cardinality labels (user IDs, order IDs, raw URLs) can create millions of unique metric time series and bring Prometheus to its knees. `CardinalityProtector` uses a thread-safe LRU cache to cap the number of unique values per label.

```python
from obskit.metrics import CardinalityProtector, CardinalityConfig, get_cardinality_protector
from obskit.metrics import protect_label, protect_id
from prometheus_client import Counter

ORDERS_TOTAL = Counter(
    "orders_processed_total",
    "Orders processed by customer segment",
    ["customer_tier", "region"],
)

# Configure per-label limits
config = CardinalityConfig(
    default_limit=500,           # Default: 500 unique values per label
    ttl_seconds=3600,            # Values expire after 1 hour
    label_limits={
        "customer_tier": 10,     # We only have 10 tiers
        "region": 50,            # Up to 50 regions
    },
)
protector = CardinalityProtector(config=config)

def record_order(customer_tier: str, region: str):
    safe_tier = protector.protect("customer_tier", customer_tier, fallback="other")
    safe_region = protector.protect("region", region, fallback="unknown")
    ORDERS_TOTAL.labels(customer_tier=safe_tier, region=safe_region).inc()

# Convenience function using the global protector
def record_user_action(user_id: str, action: str):
    # Once >1000 unique user_ids have been seen, new ones map to "other"
    safe_id = protect_id("user_id", user_id, fallback="other")
    ACTIONS_TOTAL.labels(user_id=safe_id, action=action).inc()

# Inspect cardinality health
stats = protector.get_stats("region")
# {"label_name": "region", "current_count": 48, "limit": 50, "utilization": 0.96, "at_limit": False}
```

### 6. Exposing the /metrics Endpoint

```python
from obskit.metrics import start_http_server

# Starts a background thread serving Prometheus text format at /metrics
start_http_server(port=9090)

# With FastAPI: use the ASGI middleware instead
from obskit.metrics.registry import MetricsMiddleware
from fastapi import FastAPI

app = FastAPI()
app.add_middleware(MetricsMiddleware, path="/metrics")
```

---

## PromQL Cheat Sheet

```promql
# --- Rate (requests/second over 5 minutes) ---
sum(rate(order_service_requests_total[5m])) by (operation)

# --- Error rate as a percentage ---
sum(rate(order_service_errors_total[5m])) by (operation, error_type)
/
sum(rate(order_service_requests_total[5m])) by (operation)
* 100

# --- P50 latency (median) ---
histogram_quantile(0.50,
  sum(rate(order_service_request_duration_seconds_bucket[5m])) by (le, operation)
)

# --- P95 latency ---
histogram_quantile(0.95,
  sum(rate(order_service_request_duration_seconds_bucket[5m])) by (le, operation)
)

# --- P99 latency ---
histogram_quantile(0.99,
  sum(rate(order_service_request_duration_seconds_bucket[5m])) by (le, operation)
)

# --- Average latency ---
sum(rate(order_service_request_duration_seconds_sum[5m])) by (operation)
/
sum(rate(order_service_request_duration_seconds_count[5m])) by (operation)

# --- Resource saturation approaching limit ---
order_service_saturation{resource="cpu"} > 0.85

# --- Queue growing (indicates throughput problem) ---
delta(order_service_queue_depth{queue="order_queue"}[15m]) > 50

# --- CPU over-utilized (USE method) ---
system_cpu_utilization{resource="cpu0"} > 0.90

# --- Cardinality guard triggering (means a label has too many unique values) ---
rate(obskit_cardinality_rejections_total[5m]) > 0
```

### Prometheus Alerting Rules

```yaml
groups:
  - name: obskit-red-alerts
    rules:
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
          summary: "Error rate > 1% on {{ $labels.operation }}"

      - alert: SlowP99Latency
        expr: |
          histogram_quantile(0.99,
            sum(rate(order_service_request_duration_seconds_bucket[5m])) by (le, operation)
          ) > 1.0
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "P99 latency > 1s on {{ $labels.operation }}"

      - alert: HighResourceSaturation
        expr: order_service_saturation > 0.90
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "{{ $labels.resource }} is 90%+ saturated"
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `OBSKIT_SERVICE_NAME` | `"service"` | Prefix for all metric names |
| `OBSKIT_METRICS_USE_HISTOGRAM` | `true` | Enable histogram metrics |
| `OBSKIT_METRICS_USE_SUMMARY` | `false` | Enable summary metrics |
| `OBSKIT_METRICS_SAMPLE_RATE` | `1.0` | Fraction of observations to record (0.0–1.0) |
| `OBSKIT_METRICS_PORT` | `9090` | Default port for `start_http_server()` |

---

## Part of the obskit family

`obskit-metrics` is part of the [obskit](https://github.com/talaatmagdyx/obskit) monorepo — a production-ready observability toolkit for Python microservices.

| Install only this package | Install everything |
|---|---|
| `pip install obskit-metrics` | `pip install "obskit[all]"` |
