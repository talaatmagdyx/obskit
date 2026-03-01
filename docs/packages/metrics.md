# obskit-metrics

Prometheus-native metrics for obskit services. Implements the RED method, the Four Golden Signals, the USE method, trace exemplars, multi-tenant labelling, cardinality protection, and OTLP/Pushgateway export.

## Installation

```bash
pip install "obskit[prometheus]"
```

### With Prometheus client

```bash
pip install "obskit-metrics[prometheus]"
```

---

## RED Method — REDMetrics

**Rate · Errors · Duration** — the standard methodology for measuring request-driven services.

The `REDMetrics` class creates three families of Prometheus metrics under a single service namespace:

| Family | Type | Labels |
|---|---|---|
| `<service>_requests_total` | Counter | `operation`, `status` |
| `<service>_errors_total` | Counter | `operation`, `error_type` |
| `<service>_request_duration_seconds` | Histogram (or Summary) | `operation` |

```python
from obskit.metrics import REDMetrics

red = REDMetrics("order_service")
```

### record_request / observe_request

```python
# Record a successful request
red.observe_request(
    operation="create_order",
    duration_seconds=0.045,
    status="success",
)

# Record a failure with error type
red.observe_request(
    operation="create_order",
    duration_seconds=0.012,
    status="failure",
    error_type="ValidationError",
)

# With trace exemplars (links latency spikes to traces in Grafana)
red.observe_request(
    operation="create_order",
    duration_seconds=1.23,
    exemplars=True,    # auto-injects current trace_id + span_id
)
```

### track_request context manager

```python
# Automatic timing and error detection
with red.track_request("process_payment"):
    result = process_payment(amount)
# → on success: observe_request(..., status="success")
# → on exception: observe_request(..., status="failure", error_type=<ExcType>)
```

### get_red_metrics — singleton accessor

```python
from obskit.metrics.red import get_red_metrics

# Returns a shared REDMetrics instance (created from ObskitSettings.service_name)
red = get_red_metrics()
```

---

## Four Golden Signals — GoldenSignals

Extends RED with **Saturation** — the fourth golden signal introduced by the Google SRE book.

```python
from obskit.metrics.golden import GoldenSignals

signals = GoldenSignals("api_gateway")

# Rate / Errors / Duration — same as REDMetrics
signals.observe_request("search", 0.032)
signals.observe_request("search", 0.200, status="failure", error_type="Timeout")

# Saturation — how full is the resource?
signals.set_saturation("cpu", 0.72)           # 72% CPU
signals.set_saturation("connections", 0.95)   # 95% connection pool full

# Queue depth as a saturation proxy
signals.set_queue_depth("order_queue", depth=1_250)
```

Created Prometheus metrics (saturation):

- `<service>_resource_saturation{resource="..."}` — Gauge 0.0–1.0
- `<service>_queue_depth{queue_name="..."}` — Gauge

---

## USE Method — USEMetrics

**Utilization · Saturation · Errors** — designed for infrastructure and resource monitoring, not request flows.

```python
from obskit.metrics.use import USEMetrics

use = USEMetrics("app_server")

# Utilization — how busy is the resource?
use.set_utilization("cpu", 0.68)          # 68% CPU time busy
use.set_utilization("memory", 0.45)       # 45% of RAM in use
use.set_utilization("db_pool", 0.80)      # 80% of DB connections used

# Saturation — extra work that can't be serviced immediately
use.set_saturation("cpu", 0.12)           # run-queue length normalised
use.set_saturation("disk_io", 8.0)        # I/O queue depth

# Errors — discrete error events
use.inc_error("network", "packet_loss")
use.inc_error("disk", "read_error")
```

Created Prometheus metrics:

| Family | Type | Labels |
|---|---|---|
| `<category>_utilization` | Gauge | `resource` |
| `<category>_saturation` | Gauge | `resource` |
| `<category>_errors_total` | Counter | `resource`, `error_type` |

---

## Exemplars

Prometheus exemplars embed a `trace_id` into individual histogram observations, allowing Grafana to draw a clickable link from a latency spike on a metric panel directly to the matching Tempo trace.

**Requirements:** `prometheus-client >= 0.16.0` + `opentelemetry-api` installed.

```python
from obskit.metrics.exemplar import (
    observe_with_exemplar,
    get_trace_exemplar,
    is_exemplar_available,
)
from prometheus_client import Histogram

# Check availability
if is_exemplar_available():
    print("Exemplar links will appear in Grafana")

# Get the current span's IDs as an exemplar dict
exemplar = get_trace_exemplar()
# {"trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
#  "span_id":  "00f067aa0ba902b7"}
# Returns {} when no span is active or OTel is unavailable.

# Observe a histogram with automatic exemplar injection
h = Histogram("http_latency_seconds", "HTTP request latency", ["method"])
observe_with_exemplar(h.labels(method="GET"), 0.032)
# → observation stored with trace_id exemplar if a span is active
# → plain observe() if no span is active (graceful fallback)

# Supply an explicit exemplar
observe_with_exemplar(
    h.labels(method="POST"),
    0.150,
    exemplar={"trace_id": "deadbeef...", "order_id": "ord-99"},
)
```

### Grafana setup

1. Enable exemplar storage in Prometheus: `--enable-feature=exemplar-storage`
2. Open your histogram panel in Grafana → **Query** → toggle **Exemplars**
3. Trace links appear as diamonds on the panel when you zoom into spike areas

!!! note "OpenMetrics scrape format"
    Prometheus must scrape your `/metrics` endpoint using the **OpenMetrics** content type (`application/openmetrics-text`) for exemplars to be included in the scrape.

---

## Tenant metrics — TenantREDMetrics

Inject a `tenant_id` label into all RED metrics for multi-tenant SaaS services.

```python
from obskit.metrics.tenant import (
    TenantREDMetrics,
    tenant_metrics_context,
    get_tenant_id,
    set_tenant_id,
)

tenant_metrics = TenantREDMetrics("order_service")

# Explicit tenant ID per observation
tenant_metrics.observe_request(
    tenant_id="acme-corp",
    operation="create_order",
    duration_seconds=0.045,
    status="success",
)

# Context-manager approach — set once, used by all metrics in scope
with tenant_metrics_context("acme-corp"):
    red = get_red_metrics()
    red.observe_request("create_order", 0.045)
    red.observe_request("list_orders", 0.012)

# Low-level context variable
set_tenant_id("acme-corp")
current = get_tenant_id()   # "acme-corp"
```

!!! warning "Cardinality caution"
    Adding `tenant_id` as a label multiplies cardinality by the number of unique tenants. Pair `TenantREDMetrics` with `CardinalityGuard` when you have more than a few hundred tenants.

---

## Cardinality protection — CardinalityGuard

Prevents cardinality explosions caused by high-entropy label values (user IDs, UUIDs, request IDs, timestamps).

```python
from obskit.metrics.cardinality import (
    CardinalityProtector,
    get_cardinality_protector,
)

# Get the global singleton protector
protector = get_cardinality_protector()

# Protect a label value — returns the value if within limit,
# otherwise returns the fallback string
safe_user_id = protector.protect(
    "user_id",
    user_id,
    max_cardinality=500,
    fallback="other",
)

REQUEST_COUNT.labels(user_id=safe_user_id).inc()
```

When cardinality exceeds the limit the following internal metrics are updated:

| Metric | Type | Labels | Description |
|---|---|---|---|
| `obskit_cardinality_rejections_total` | Counter | `label_name` | Rejected values |
| `obskit_cardinality_current` | Gauge | `label_name` | Unique tracked values |
| `obskit_cardinality_limit` | Gauge | `label_name` | Configured limit |

---

## OTLP metrics export

```python
from obskit.metrics.otlp import setup_otlp_metrics, shutdown_otlp_metrics

# Export metrics to an OTLP collector alongside traces
setup_otlp_metrics(
    endpoint="http://otel-collector:4317",
    service_name="order-service",      # defaults to ObskitSettings.service_name
    insecure=True,
    export_interval_seconds=60,
)

# Graceful shutdown (flushes pending exports)
shutdown_otlp_metrics()
```

---

## Prometheus Push Gateway

Send metrics from short-lived jobs (batch jobs, crons) to a Prometheus Pushgateway.

```python
from obskit.metrics.pushgateway import push_to_gateway

# Push all registered metrics
push_to_gateway(
    gateway="http://pushgateway:9091",
    job="nightly_report",
    grouping_key={"instance": "worker-01"},
)
```

---

## OpenMetrics format

obskit exposes metrics in the standard [OpenMetrics](https://openmetrics.io/) text format by default. To force an OpenMetrics scrape (required for exemplars):

```http
GET /metrics HTTP/1.1
Accept: application/openmetrics-text; version=1.0.0; charset=utf-8
```

The Prometheus server can be configured to scrape OpenMetrics format:

```yaml
scrape_configs:
  - job_name: "order-service"
    static_configs:
      - targets: ["order-service:9090"]
    # Prometheus 2.43+ auto-negotiates; for older versions:
    # params:
    #   format: ["openmetrics"]
```

---

## Full example

```python
from obskit.config import configure
from obskit.metrics import REDMetrics
from obskit.metrics.golden import GoldenSignals
from obskit.metrics.exemplar import is_exemplar_available

configure(
    service_name="order-service",
    environment="production",
    otlp_endpoint="http://tempo:4317",
)

red = REDMetrics("order_service")
golden = GoldenSignals("order_service")

async def create_order(order_data: dict):
    with red.track_request("create_order"):
        result = await db.insert_order(order_data)
        # Exemplar is injected automatically if OTel span is active
        red.observe_request(
            "create_order",
            0.045,
            exemplars=is_exemplar_available(),
        )
        return result

# Update saturation from a background task
async def update_saturation():
    golden.set_saturation("db_pool", db_pool.utilization())
    golden.set_queue_depth("order_queue", await queue.depth())
```
