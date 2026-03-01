# How to Use Trace Exemplars

Trace exemplars attach a `trace_id` (and optionally a `span_id`) to a specific metric
observation.  When Prometheus scrapes your service in OpenMetrics format and Grafana is
configured to display exemplars, each histogram bucket can show a dot that, when clicked,
jumps directly to the exact trace that produced that data point.

---

## What are trace exemplars?

An **exemplar** is a metadata annotation on a single metric observation.  It is part of
the [OpenMetrics specification](https://github.com/OpenObservability/OpenMetrics/blob/main/specification/OpenMetrics.md#exemplars)
and is supported by `prometheus_client >= 0.16.0`.

Without exemplars you can see *that* your p99 latency spiked to 3 seconds at 14:05, but
you cannot see *which request* caused the spike.  With exemplars, each histogram
observation carries a `trace_id` pointer.  In Grafana you see the spike, click the
exemplar dot, and arrive at the slow trace in Tempo — all without searching manually.

```
Histogram observation (0.045 s)
  └─ Prometheus bucket:  le="0.05", count=1
       └─ Exemplar:      {trace_id="4bf92f35...", span_id="00f067aa..."} value=0.045
```

---

## Requirements

| Package | Minimum version | Role |
|---------|-----------------|------|
| `obskit-metrics` | 2.0.0 | `observe_with_exemplar()` / `get_trace_exemplar()` |
| `obskit-tracing` | 2.0.0 | Active OTel span context |
| `prometheus_client` | 0.16.0 | Exemplar storage and OpenMetrics exposition |
| `opentelemetry-sdk` | 1.20.0 | OTel span context |

---

## Installation

```bash
pip install "obskit[prometheus]" obskit-tracing
```

---

## API reference

### `observe_with_exemplar(metric_labels, value)`

Records `value` on a `Histogram` or `Summary` and attaches the current OTel
`trace_id` / `span_id` as an exemplar.

```python
from obskit.metrics import observe_with_exemplar
from prometheus_client import Histogram

REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path"],
)

# Inside a request handler (OTel span active):
observe_with_exemplar(
    REQUEST_DURATION.labels(method="GET", path="/orders"),
    0.045,
)
```

!!! warning "Counter and Gauge are not supported"
    `observe_with_exemplar()` only works with **Histogram** and **Summary** metrics.
    Counters and Gauges do not support the `observe()` method.  Calling it on a Counter
    will raise a `TypeError`.  Use the standard `.inc()` method for counters.

### `get_trace_exemplar()`

Returns the current OTel span identifiers as a plain `dict` suitable for passing to
`prometheus_client`'s low-level exemplar API or for including in log records.

```python
from obskit.metrics import get_trace_exemplar

exemplar = get_trace_exemplar()
# When a span is active:
# {"trace_id": "4bf92f3577b34da6a3ce929d0e0e4736", "span_id": "00f067aa0ba902b7"}
# When no span is active:
# {}
```

### `is_exemplar_available()`

Returns `True` if both `prometheus_client >= 0.16.0` and the OTel SDK are present and
configured.  Use this in startup checks or conditional logic.

```python
from obskit.metrics import is_exemplar_available

if is_exemplar_available():
    print("Exemplars will be attached to metric observations")
else:
    print("Exemplar support disabled — observations recorded without trace context")
```

---

## Complete FastAPI example

```python
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from prometheus_client import Histogram, generate_latest, CONTENT_TYPE_LATEST
from opentelemetry import trace

from obskit.logging import get_logger
from obskit.metrics import observe_with_exemplar, is_exemplar_available
from obskit.middleware.fastapi import ObservabilityMiddleware
from obskit.tracing import setup_tracing

# ── Initialise tracing ────────────────────────────────────────────────────────
setup_tracing(service_name="order-service", exporter_endpoint="http://localhost:4317")

# ── Define metrics ────────────────────────────────────────────────────────────
REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["method", "path", "status_code"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)

ORDER_PROCESSING_SECONDS = Histogram(
    "order_processing_seconds",
    "Time to process a single order",
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 5.0],
)

log = get_logger("order_service")

# ── Application ───────────────────────────────────────────────────────────────
app = FastAPI()
app.add_middleware(ObservabilityMiddleware, service_name="order-service")


@app.middleware("http")
async def record_request_duration(request: Request, call_next):
    start = time.perf_counter()
    response: Response = await call_next(request)
    duration = time.perf_counter() - start

    observe_with_exemplar(
        REQUEST_DURATION.labels(
            method=request.method,
            path=request.url.path,
            status_code=str(response.status_code),
        ),
        duration,
    )
    return response


@app.post("/orders")
async def create_order(payload: dict):
    tracer = trace.get_tracer("order_service")
    with tracer.start_as_current_span("process_order") as span:
        start = time.perf_counter()

        # Simulate order processing
        import asyncio
        await asyncio.sleep(0.03)

        elapsed = time.perf_counter() - start
        observe_with_exemplar(ORDER_PROCESSING_SECONDS, elapsed)

        log.info("order_created", duration_ms=round(elapsed * 1000, 2))
        return {"order_id": "ord-9f2a", "trace_id": format(
            span.get_span_context().trace_id, "032x"
        )}


@app.get("/metrics")
async def metrics():
    # Return OpenMetrics format so Prometheus can scrape exemplars.
    from prometheus_client import REGISTRY
    from prometheus_client.openmetrics.exposition import generate_latest as om_generate
    return Response(content=om_generate(REGISTRY), media_type="application/openmetrics-text")
```

!!! tip "OpenMetrics /metrics endpoint"
    The standard `generate_latest()` returns the Prometheus text format, which does
    **not** include exemplars.  To expose exemplars you must use
    `prometheus_client.openmetrics.exposition.generate_latest` and set the
    `Content-Type` to `application/openmetrics-text`.

---

## Prometheus scrape configuration

Prometheus must scrape in OpenMetrics format to collect exemplars.  Add
`honor_timestamps: true` and override the `Accept` header:

```yaml
# prometheus.yml
scrape_configs:
  - job_name: "order-service"
    honor_timestamps: true
    scrape_interval: 15s
    static_configs:
      - targets: ["host.docker.internal:8000"]
    # Request OpenMetrics format so exemplars are included in the scrape
    metrics_path: /metrics
    params: {}
    scheme: http
    # Override Accept header for OpenMetrics
    honor_labels: false
    sample_limit: 0
    # Prometheus 2.43+ scrapes OpenMetrics automatically when the endpoint
    # responds with Content-Type: application/openmetrics-text
    # For older Prometheus versions add:
    follow_redirects: true
```

!!! note "Prometheus 2.43+"
    Prometheus 2.43 and later automatically detect and use OpenMetrics format when
    the `/metrics` endpoint responds with `Content-Type: application/openmetrics-text`.
    No additional scrape configuration is required.

    For Prometheus < 2.43, set the `Accept` header explicitly using the
    `scrape_protocols` field (available since 2.49) or use a recording rule to
    preserve exemplars.

---

## Grafana: enabling exemplars on the Prometheus datasource

1. Open **Configuration → Data Sources → Prometheus**.
2. Scroll to **Exemplars** and click **Add**.
3. Set:
   - **Internal link**: enabled
   - **Data source**: Tempo
   - **URL label**: `trace_id`
   - **Label name**: `trace_id`
4. Save and test the datasource.

---

## Grafana: viewing exemplar dots on histogram panels

1. Add a **Time series** panel with a Prometheus histogram query, for example:

   ```promql
   histogram_quantile(0.99,
     sum by (le) (
       rate(http_request_duration_seconds_bucket[5m])
     )
   )
   ```

2. In the panel **Query** tab, enable the **Exemplars** toggle (the diamond icon next
   to the query row).

3. The panel will now display small diamond-shaped dots on the graph wherever an
   exemplar was recorded.

4. **Click any dot** → Grafana opens the Tempo trace explorer pre-loaded with that
   `trace_id`.

```
p99 latency graph
  ━━━━━━━━━━━━━━◆━━━━━━━━━━━━━━━━◆━━━━━━━━
                ↑                ↑
          exemplar dot     exemplar dot
          (click to open Tempo trace)
```

---

## Wire exemplars into a Summary metric

Exemplars work the same way with `Summary` metrics:

```python
from prometheus_client import Summary
from obskit.metrics import observe_with_exemplar

DB_QUERY_SECONDS = Summary(
    "db_query_seconds",
    "Database query latency",
    ["table", "operation"],
)

# Inside a function with an active OTel span:
observe_with_exemplar(
    DB_QUERY_SECONDS.labels(table="orders", operation="select"),
    0.012,
)
```

---

## Checking exemplar availability at startup

```python
from obskit.metrics import is_exemplar_available
from obskit.logging import get_logger

log = get_logger("startup")

def check_observability():
    if is_exemplar_available():
        log.info("exemplars_enabled")
    else:
        log.warning(
            "exemplars_disabled",
            reason="prometheus_client < 0.16.0 or obskit-tracing not installed",
        )
```

---

## Troubleshooting

### No exemplar dots appearing in Grafana

Work through this checklist:

1. **Is `prometheus_client >= 0.16.0` installed?**

   ```bash
   python -c "import prometheus_client; print(prometheus_client.__version__)"
   ```

2. **Is the `/metrics` endpoint returning OpenMetrics format?**

   ```bash
   curl -H "Accept: application/openmetrics-text" http://localhost:8000/metrics | grep "# HELP"
   ```

   The response must start with `# HELP` and use the `_total` suffix pattern.  If you
   see the classic Prometheus format, the endpoint is not returning OpenMetrics.

3. **Is an OTel span active when `observe_with_exemplar()` is called?**

   ```python
   from opentelemetry import trace
   span = trace.get_current_span()
   print(span.get_span_context().is_valid)  # Must be True
   ```

4. **Is the Exemplars toggle enabled on the Grafana panel?**

   The toggle is per-query.  Check that the diamond icon is highlighted in the query
   row of the panel editor.

5. **Is the Prometheus datasource in Grafana configured with an exemplar link to Tempo?**

   See the [Grafana configuration section](#grafana-enabling-exemplars-on-the-prometheus-datasource)
   above.

6. **Is Prometheus scraping exemplars?**

   Run a Prometheus instant query:

   ```promql
   {__name__="http_request_duration_seconds_bucket"}
   ```

   Switch the Prometheus UI to **Table** view and check for the `# EXEMPLAR` lines.

### `observe_with_exemplar()` raises `TypeError`

You are calling it on a `Counter` or `Gauge`, which only support `.inc()` and `.set()`.
Use `observe_with_exemplar()` exclusively with `Histogram` and `Summary`.

### Exemplars appear in Prometheus but not in Grafana

Ensure the Prometheus datasource in Grafana has the **Internal link** to Tempo
configured correctly.  The `Label name` must match exactly the key used in the exemplar
dict — obskit uses `trace_id`.

---

## Summary

| Step | Action |
|------|--------|
| Install | `pip install "obskit[prometheus]" obskit-tracing` |
| Define metric | Use `Histogram` or `Summary` (not Counter/Gauge) |
| Record | `observe_with_exemplar(metric.labels(…), value)` |
| Expose | Return `application/openmetrics-text` from `/metrics` |
| Prometheus | `honor_timestamps: true` in scrape config |
| Grafana | Enable exemplar link (Prometheus DS → Tempo) |
| Grafana panel | Enable Exemplars toggle on the query row |
