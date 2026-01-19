# Metrics Guide

Complete guide to RED, Golden Signals, and USE metrics methodologies.

---

## Overview

obskit implements three industry-standard metrics methodologies:

| Methodology | Purpose | Key Metrics |
|-------------|---------|-------------|
| **RED** | Service health | Rate, Errors, Duration |
| **Golden Signals** | Comprehensive SRE | Latency, Traffic, Errors, Saturation |
| **USE** | Infrastructure | Utilization, Saturation, Errors |

---

## RED Method (Recommended for Services)

The RED method measures user-facing service health.

### Basic Usage

```python
from obskit.metrics import REDMetrics, get_red_metrics

# Get global instance
red = get_red_metrics()

# Record a successful request
red.observe_request(
    operation="create_order",
    duration_seconds=0.150,
    status="success",
)

# Record a failed request
red.observe_request(
    operation="create_order",
    duration_seconds=0.250,
    status="error",
    error_type="ValidationError",
)
```

### Context Manager (Recommended)

```python
# Automatic timing and error tracking
with red.track_request("process_payment") as tracker:
    result = payment_service.process(order)
    
    if not result.success:
        tracker.set_error("PaymentFailed")
        
    # Duration is automatically recorded on exit
```

### Async Support

```python
from obskit.metrics import AsyncREDMetrics

async_red = AsyncREDMetrics("order_service")

# Async recording (non-blocking)
await async_red.observe_request_async(
    operation="create_order",
    duration_seconds=0.150,
    status="success",
)
```

### Prometheus Metrics Generated

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `red_requests_total` | Counter | service, operation, status | Total requests |
| `red_request_duration_seconds` | Histogram | service, operation | Request duration |
| `red_request_duration_seconds_summary` | Summary | service, operation | Percentiles (if enabled) |
| `red_errors_total` | Counter | service, operation, error_type | Total errors |

### Example Prometheus Queries

```promql
# Request rate
rate(red_requests_total{service="order-service"}[5m])

# Error rate
sum(rate(red_requests_total{status="error"}[5m])) 
  / sum(rate(red_requests_total[5m]))

# P99 latency
histogram_quantile(0.99, 
  rate(red_request_duration_seconds_bucket{service="order-service"}[5m])
)

# P50 latency
histogram_quantile(0.50, 
  rate(red_request_duration_seconds_bucket{service="order-service"}[5m])
)
```

---

## Golden Signals (Comprehensive SRE Monitoring)

The Four Golden Signals extend RED with saturation monitoring.

### Basic Usage

```python
from obskit.metrics import GoldenSignals, get_golden_signals

golden = get_golden_signals()

# Latency
golden.observe_latency("api_request", 0.150)

# Traffic
golden.inc_traffic("api_request")

# Errors
golden.inc_error("api_request", "timeout")

# Saturation
golden.set_saturation("connection_pool", 0.75)  # 75% full
```

### Queue Depth Tracking

```python
# Track queue depth
golden.set_queue_depth("order_queue", 42)
golden.inc_queue_depth("order_queue")  # 43
golden.dec_queue_depth("order_queue")  # 42
```

### Progress Tracking (Batch Jobs)

```python
# Track batch job progress
golden.set_progress(
    operation="data_import",
    completed_items=500,
    total_items=1000,
)
```

### Combined Recording

```python
# Record all signals at once
golden.observe_request(
    operation="create_order",
    duration_seconds=0.150,
)  # Records latency and traffic
```

### Prometheus Metrics Generated

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `golden_latency_seconds` | Histogram | service, operation | Request latency |
| `golden_traffic_total` | Counter | service, operation | Request count |
| `golden_errors_total` | Counter | service, operation, error_type | Error count |
| `golden_saturation` | Gauge | service, resource | Resource saturation |
| `golden_queue_depth` | Gauge | service, queue | Queue depth |

---

## USE Method (Infrastructure Monitoring)

The USE method measures infrastructure resource health.

### Basic Usage

```python
from obskit.metrics import USEMetrics, get_use_metrics

use = get_use_metrics()

# Utilization (percentage of time busy)
use.set_utilization("cpu", 0.65)       # 65% CPU
use.set_utilization("memory", 0.80)    # 80% memory

# Saturation (queued work)
use.set_saturation("connection_pool", 0.90)  # 90% saturated

# Errors
use.inc_error("disk", "io_error")
use.inc_error("network", "packet_drop", count=5)
```

### Combined Recording

```python
# Record all metrics at once
use.record_use_metrics(
    resource="worker_pool",
    utilization=0.70,
    saturation=0.85,
    errors={"timeout": 2, "rejected": 1},
)
```

### Prometheus Metrics Generated

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `use_utilization` | Gauge | service, resource | Resource utilization |
| `use_saturation` | Gauge | service, resource | Resource saturation |
| `use_errors_total` | Counter | service, resource, error_type | Error count |

---

## Tenant-Aware Metrics

Track metrics per tenant for multi-tenant applications.

```python
from obskit.metrics import TenantREDMetrics, tenant_metrics_context

tenant_red = TenantREDMetrics("order_service")

# Set tenant context
with tenant_metrics_context("tenant-123"):
    tenant_red.observe_request(
        operation="create_order",
        duration_seconds=0.150,
        status="success",
    )
    # Metrics include tenant_id label
```

---

## Histogram Bucket Presets

Choose appropriate bucket sizes for your use case:

```python
from obskit.metrics import REDMetrics
from obskit.metrics.presets import (
    FAST_SERVICE_BUCKETS,    # [0.001, 0.005, 0.01, 0.025, 0.05, 0.1]
    API_SERVICE_BUCKETS,     # [0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]
    DATABASE_SERVICE_BUCKETS, # [0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0]
    BATCH_SERVICE_BUCKETS,   # [1, 5, 10, 30, 60, 120, 300, 600]
    DEFAULT_BUCKETS,         # Prometheus defaults
)

# Fast cache service (<100ms)
cache_metrics = REDMetrics(
    "cache_service",
    histogram_buckets=FAST_SERVICE_BUCKETS,
)

# Standard API (10ms-5s)
api_metrics = REDMetrics(
    "api_service",
    histogram_buckets=API_SERVICE_BUCKETS,
)

# Batch processing (1s-10min)
batch_metrics = REDMetrics(
    "batch_service",
    histogram_buckets=BATCH_SERVICE_BUCKETS,
)
```

---

## Pushgateway Integration

Push metrics from batch jobs:

```python
from obskit.metrics import PushgatewayExporter

exporter = PushgatewayExporter(
    gateway_url="http://pushgateway:9091",
    job_name="data_import_job",
)

# Record job metrics
exporter.record_gauge("items_processed", 1000)
exporter.record_counter("errors_total", 5)

# Push to gateway
exporter.push()
```

### Batch Job Context Manager

```python
from obskit.metrics.pushgateway import batch_job_metrics

with batch_job_metrics(
    gateway_url="http://pushgateway:9091",
    job_name="nightly_report",
) as exporter:
    # Process data
    for item in items:
        process(item)
        exporter.record_counter("items_processed", 1)
    
    # Automatically pushes on exit
```

---

## OTLP Metrics Export

Export metrics to OpenTelemetry collectors:

```python
from obskit.metrics import OTLPMetricsExporter

exporter = OTLPMetricsExporter(
    endpoint="http://otel-collector:4317",
)

# Start background exporter
exporter.start()

# Metrics are automatically exported
# ...

# Stop on shutdown
exporter.stop()
```

---

## Sampling for High Traffic

Enable sampling for high-frequency operations:

```python
from obskit import configure

configure(
    # Sample 10% of metrics
    metrics_sample_rate=0.1,
)

# With AsyncREDMetrics
from obskit.metrics import AsyncREDMetrics

async_red = AsyncREDMetrics(
    "high_traffic_service",
    sample_rate=0.1,
)
```

---

## Best Practices

### 1. Choose the Right Methodology

| Service Type | Recommended |
|--------------|-------------|
| User-facing APIs | RED |
| Background services | Golden Signals |
| Infrastructure | USE |
| All of the above | Golden Signals + USE |

### 2. Label Cardinality

⚠️ Avoid high-cardinality labels:

```python
# ❌ BAD - User IDs create unbounded cardinality
red.observe_request(operation=f"get_user_{user_id}")

# ✅ GOOD - Fixed set of operations
red.observe_request(operation="get_user")
```

### 3. Meaningful Operation Names

```python
# ✅ GOOD - Clear, consistent naming
red.observe_request(operation="create_order")
red.observe_request(operation="get_order")
red.observe_request(operation="update_order")
red.observe_request(operation="delete_order")

# ❌ BAD - Inconsistent naming
red.observe_request(operation="CreateOrder")
red.observe_request(operation="order_get")
red.observe_request(operation="UpdateOrderV2")
```

### 4. Error Categorization

```python
# ✅ GOOD - Categorized errors
red.observe_request(
    operation="create_order",
    status="error",
    error_type="ValidationError",
)
red.observe_request(
    operation="create_order",
    status="error",
    error_type="DatabaseError",
)

# ❌ BAD - Full error messages
red.observe_request(
    operation="create_order",
    error_type=str(exception),  # Creates high cardinality
)
```

---

## Grafana Dashboard Examples

### RED Dashboard Query

```promql
# Success rate
sum(rate(red_requests_total{status="success"}[5m])) 
  / sum(rate(red_requests_total[5m])) * 100

# Request rate by operation
sum(rate(red_requests_total[5m])) by (operation)

# Latency heatmap
sum(rate(red_request_duration_seconds_bucket[5m])) by (le)
```

### Alerting Rules

```yaml
groups:
- name: red-alerts
  rules:
  - alert: HighErrorRate
    expr: |
      sum(rate(red_requests_total{status="error"}[5m])) 
        / sum(rate(red_requests_total[5m])) > 0.05
    for: 5m
    labels:
      severity: critical
    annotations:
      summary: "Error rate above 5%"
      
  - alert: HighLatency
    expr: |
      histogram_quantile(0.99, rate(red_request_duration_seconds_bucket[5m])) > 1
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "P99 latency above 1 second"
```
