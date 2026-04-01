# Metrics

Prometheus-native metrics for obskit services. Implements the RED method, trace exemplars, cardinality protection, and OTLP export.

## Installation

```bash
pip install "obskit[prometheus]"
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

## Multiprocess mode (Gunicorn / uWSGI)

When running multiple worker processes (Gunicorn, uWSGI) each process has its own Prometheus registry. Without coordination, scraping `/metrics` from any single worker returns only that worker's counters. `obskit.metrics.multiprocess` handles the setup automatically.

```python
from obskit.metrics.multiprocess import (
    is_multiprocess_mode,
    setup_multiprocess_registry,
    make_multiprocess_app,
)
```

### Detection

```python
# Returns True when PROMETHEUS_MULTIPROC_DIR or prometheus_multiproc_dir is set
if is_multiprocess_mode():
    print("Running in multiprocess mode")
```

### Registry setup

```python
registry = setup_multiprocess_registry()
# - Returns the default REGISTRY in single-process mode
# - In multiprocess mode: creates the multiproc dir if it doesn't exist,
#   raises RuntimeError if the dir is not writable,
#   returns a CollectorRegistry with MultiProcessCollector attached
```

### WSGI metrics app

```python
# Serve /metrics from a dedicated WSGI endpoint
metrics_app = make_multiprocess_app(registry)
```

### Gunicorn integration

```python
# gunicorn_config.py
import os
from obskit.metrics.multiprocess import setup_multiprocess_registry

def child_exit(server, worker):
    """Called by Gunicorn when a worker exits — clean up multiproc files."""
    from prometheus_client import multiprocess
    multiprocess.mark_process_dead(worker.pid)

os.environ.setdefault("PROMETHEUS_MULTIPROC_DIR", "/tmp/prometheus_multiproc")
```

### Environment variables

| Variable | Description |
|---|---|
| `PROMETHEUS_MULTIPROC_DIR` | Directory where each worker writes its metrics files |
| `prometheus_multiproc_dir` | Lowercase alias (both are checked) |

!!! warning "Directory must be writable"
    The multiproc directory must exist and be writable by all worker processes. If `setup_multiprocess_registry()` cannot create or write to the directory it raises `RuntimeError` with a descriptive message.

---

## Full example

```python
from obskit.config import configure
from obskit.metrics import REDMetrics
from obskit.metrics.exemplar import is_exemplar_available

configure(
    service_name="order-service",
    environment="production",
    otlp_endpoint="http://tempo:4317",
)

red = REDMetrics("order_service")

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
```
