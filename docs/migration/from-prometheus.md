# Migrating from prometheus-client to obskit

If you are currently instrumenting your Python services with raw `prometheus-client`,
obskit provides a higher-level, opinionated layer that eliminates boilerplate while
keeping full Prometheus compatibility.  Your existing dashboards and alert rules
continue to work — obskit registers metrics in the same Prometheus registry.

---

## Why Migrate?

| Raw prometheus-client | obskit |
|---|---|
| You choose metric names manually — inconsistency across services | RED/Golden/USE naming conventions enforced automatically |
| Counter → rate math is done in PromQL, not validated at instrument time | `REDMetrics.record_request()` ensures label cardinality is safe |
| No cardinality protection — a bug can create millions of time series | `CardinalityGuard` blocks new labels above a configurable threshold |
| Exemplars require manual `MetricWrapperBase.labels(..., exemplar={…})` | `observe_with_exemplar()` extracts the current trace ID automatically |
| Health server is separate from application logic | `obskit.health` integrates health checks with tracing |
| No structured log correlation | obskit injects `trace_id` and `span_id` into every log record |

obskit does **not** replace prometheus-client — it depends on it.  You keep all your
existing Prometheus infrastructure (exporters, Alertmanager, Grafana).

---

## Installation

```bash
# Minimal — metrics only
pip install "obskit[prometheus]"

# With health check server
pip install "obskit[prometheus]"

# Full stack
pip install "obskit[all]"
```

---

## Mapping: Counter and Histogram → REDMetrics

### Before — raw prometheus-client

```python
from prometheus_client import Counter, Histogram, start_http_server
import time

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "Request latency",
    ["method", "endpoint"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)

def handle_request(method: str, endpoint: str) -> dict:
    start = time.perf_counter()
    try:
        result = do_work()
        REQUEST_COUNT.labels(method=method, endpoint=endpoint, status="success").inc()
        return result
    except Exception as exc:
        REQUEST_COUNT.labels(method=method, endpoint=endpoint, status="error").inc()
        raise
    finally:
        REQUEST_LATENCY.labels(method=method, endpoint=endpoint).observe(
            time.perf_counter() - start
        )

start_http_server(9090)
```

### After — obskit REDMetrics

```python
import time
from obskit.metrics import REDMetrics
from obskit.config import configure

configure(service_name="order-service", metrics_port=9090)

red = REDMetrics("order_service")

def handle_request(method: str, endpoint: str) -> dict:
    start = time.perf_counter()
    try:
        result = do_work()
        red.record_request(endpoint, method, status="success",
                           duration=time.perf_counter() - start)
        return result
    except Exception as exc:
        red.record_request(endpoint, method, status="error",
                           duration=time.perf_counter() - start)
        raise
```

obskit automatically:

- Creates `order_service_requests_total` (Counter) with labels `{method, endpoint, status}`.
- Creates `order_service_request_duration_seconds` (Histogram) with SRE-standard buckets.
- Starts the metrics HTTP server on `OBSKIT_METRICS_PORT` (default 9090).

---

## Mapping: Exemplars

Exemplars link a specific Prometheus observation to a trace — enabling "jump from
metric to trace" in Grafana.  With raw prometheus-client you must extract the trace
ID manually.

### Before — raw prometheus-client exemplar

```python
from opentelemetry import trace
from prometheus_client import Histogram

LATENCY = Histogram("request_duration_seconds", "Latency", ["endpoint"])

def observe(endpoint: str, duration: float) -> None:
    span = trace.get_current_span()
    ctx = span.get_span_context()
    exemplar = {}
    if ctx.is_valid:
        exemplar = {"trace_id": format(ctx.trace_id, "032x")}
    LATENCY.labels(endpoint=endpoint).observe(duration, exemplar=exemplar)
```

### After — obskit observe_with_exemplar

```python
from obskit.metrics.exemplar import observe_with_exemplar
from prometheus_client import Histogram

LATENCY = Histogram("request_duration_seconds", "Latency", ["endpoint"])

def observe(endpoint: str, duration: float) -> None:
    observe_with_exemplar(LATENCY.labels(endpoint=endpoint), duration)
    # obskit extracts the current trace_id automatically
```

---

## Cardinality Protection

A common mistake with raw prometheus-client is using user-supplied values (e.g.,
`user_id`) as label values, creating millions of unique time series that OOM
Prometheus.

### Before — no protection

```python
REQUEST_COUNT.labels(user_id=request.user_id, endpoint=endpoint).inc()
# → Prometheus OOM after 1 million unique users
```

### After — CardinalityGuard

```python
from obskit.metrics.cardinality import CardinalityGuard

guard = CardinalityGuard(max_cardinality=500)

# Safe: blocks new labels when limit is reached, uses "__overflow__" bucket
safe_user_id = guard.safe_label("user_id", request.user_id)
REQUEST_COUNT.labels(user_id=safe_user_id, endpoint=endpoint).inc()
```

---

## Keeping Existing Metrics

You do not need to delete your existing `prometheus_client` metrics.  obskit
registers its metrics in the **default Prometheus registry** — the same registry used
by your existing code.  Both sets of metrics appear on `/metrics`.

```python
# Your existing metrics — keep them
from prometheus_client import Counter
LEGACY_COUNTER = Counter("legacy_ops_total", "Legacy operations")

# New obskit metrics alongside
from obskit.metrics import REDMetrics
red = REDMetrics("new_service")

# Both appear on /metrics
```

---

## Replacing start_http_server

`prometheus_client.start_http_server()` starts a bare metrics server on a background
thread.  obskit's health server does the same but also exposes `/health`, `/ready`,
and `/live` endpoints.

### Before

```python
from prometheus_client import start_http_server
start_http_server(9090)
```

### After

```python
from obskit.health.server import start_health_server

start_health_server(port=9090)
# Exposes: /metrics, /health, /ready, /live
```

Or, for FastAPI/Flask/Django, use the obskit middleware — it mounts all endpoints
automatically.

---

## Golden Signals and USE Method

Raw prometheus-client gives you Counter and Histogram primitives.  obskit provides
higher-level instruments that match Google SRE's monitoring methodologies.

```python
from obskit.metrics import GoldenSignals, USEMetrics

# Four Golden Signals for your service
golden = GoldenSignals("payment_service")
golden.observe_request("charge", duration_seconds=0.042)
golden.set_saturation("queue", 0.78)
golden.set_queue_depth("payment_queue", 156)

# USE Method for infrastructure resources
cpu = USEMetrics("server_cpu")
cpu.set_utilization("cpu", 0.65)
cpu.set_saturation("cpu", queue_depth=3)
```

---

## Prometheus Rule Files — No Changes Required

Your existing Prometheus recording rules and alerting rules reference metric names.
Because obskit uses the same prometheus-client registry and exposes compatible metric
names, no changes to `.rules.yml` files are required.

!!! tip "Metric name validation"
    Run `promtool check rules rules/*.yml` after upgrading to confirm no rules
    reference metrics that were removed.

---

## Migration Checklist

- [ ] Install `obskit[prometheus]` (health checks are included in the base package)
- [ ] Replace `Counter` + `Histogram` pairs with `REDMetrics`
- [ ] Replace manual exemplar extraction with `observe_with_exemplar()`
- [ ] Add `CardinalityGuard` to any metric that uses user-supplied label values
- [ ] Replace `start_http_server()` with `start_health_server()` (optional)
- [ ] Run `python -m obskit.core.diagnose` to verify the install
- [ ] Validate Prometheus scrape config still targets correct port/path
- [ ] Confirm Grafana dashboards show data (no metric name changes)
