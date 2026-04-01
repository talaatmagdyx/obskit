# Migrating from Datadog to obskit + OSS Stack

This guide helps teams that are running Datadog APM, metrics, and logging who want to
move to an open-source observability stack with no vendor lock-in.

!!! info "Target OSS stack"
    - **Traces** → Grafana Tempo (OTLP ingest)
    - **Metrics** → Prometheus + Grafana
    - **Logs** → Grafana Loki (via promtail or OTLP)
    - **Dashboards** → Grafana
    - **Alerts** → Alertmanager / Grafana Alerting

---

## Why Migrate from Datadog?

| Concern | Datadog | obskit + OSS |
|---|---|---|
| Vendor lock-in | Datadog-proprietary SDK, trace format | OTLP open standard; switch backends without code changes |
| Cost | $3–$5 per host per month for APM; log ingestion billed per GB | Self-hosted; infrastructure cost only |
| Data residency | Data leaves your network to Datadog's SaaS | Runs entirely in your own infrastructure |
| Cardinality limits | Datadog enforces tag cardinality limits | You control Prometheus cardinality |
| Custom spans | Requires Datadog-specific `ddtrace` decorators | Standard OTel API; portable |
| Portability | `ddtrace` is Datadog-only | obskit uses OTel; works with Tempo, Jaeger, Zipkin |

---

## Installation

```bash
# Remove Datadog SDK
pip uninstall ddtrace datadog

# Install obskit
pip install "obskit[all]"

# Infrastructure (docker-compose or Helm)
# See: docs/guides/docker-compose.md
```

---

## Tracing: ddtrace → setup_tracing with OTLP to Tempo

### Before — ddtrace

```python
# In your application startup (often via DD_TRACE_ENABLED env var)
import ddtrace
ddtrace.patch_all()

from ddtrace import tracer, patch

# Manual spans
with tracer.trace("process_order", service="order-service", resource="POST /orders") as span:
    span.set_tag("order.id", order_id)
    result = process()
    span.set_tag("result.status", result.status)
```

```bash
# Environment variables
DD_AGENT_HOST=localhost
DD_TRACE_AGENT_PORT=8126
DD_SERVICE=order-service
DD_ENV=production
DD_VERSION=1.2.3
```

### After — obskit + Tempo

```python
from obskit.tracing import setup_tracing, trace_span
from obskit.config import configure

configure(
    service_name="order-service",
    environment="production",
    version="1.2.3",
)
# Auto-instruments FastAPI, SQLAlchemy, httpx, Redis, etc.
setup_tracing(exporter_endpoint="http://tempo:4317")

# Manual spans
with trace_span("process_order", attributes={"order.id": order_id}) as span:
    result = process()
    span.set_attribute("result.status", result.status)
```

```bash
# Environment variables
OBSKIT_SERVICE_NAME=order-service
OBSKIT_ENVIRONMENT=production
OBSKIT_VERSION=1.2.3
OBSKIT_OTLP_ENDPOINT=http://tempo:4317
```

---

## Metrics: DogStatsd → Prometheus + Grafana

Datadog uses the DogStatsd format for custom metrics.  obskit uses Prometheus
counters, histograms, and gauges — the standard for cloud-native observability.

### Before — DogStatsd

```python
from datadog import initialize, statsd

initialize(statsd_host="localhost", statsd_port=8125)

def handle_payment(amount: float, currency: str) -> None:
    statsd.increment("payment.processed", tags=[f"currency:{currency}"])
    statsd.histogram("payment.amount", amount, tags=[f"currency:{currency}"])
    with statsd.timed("payment.duration", tags=[f"currency:{currency}"]):
        process_payment(amount, currency)
```

### After — obskit REDMetrics

```python
import time
from obskit.metrics import REDMetrics

payments = REDMetrics("payment_service")

def handle_payment(amount: float, currency: str) -> None:
    start = time.perf_counter()
    try:
        process_payment(amount, currency)
        payments.record_request(
            "/payments", "POST",
            status="success",
            duration=time.perf_counter() - start,
            extra_labels={"currency": currency},
        )
    except Exception:
        payments.record_request(
            "/payments", "POST",
            status="error",
            duration=time.perf_counter() - start,
            extra_labels={"currency": currency},
        )
        raise
```

### DogStatsd metric type mapping

| DogStatsd | obskit / Prometheus |
|---|---|
| `statsd.increment("metric")` | `Counter("metric_total", …).inc()` |
| `statsd.gauge("metric", value)` | `Gauge("metric", …).set(value)` |
| `statsd.histogram("metric", value)` | `Histogram("metric", …).observe(value)` |
| `statsd.timed("metric")` context manager | `REDMetrics.record_request()` with duration |
| `statsd.event(title, text)` | Grafana annotation via API |
| `statsd.service_check(name, status)` | `obskit.health.HealthChecker` |

---

## Logs: Datadog Agent Log Collection → Grafana Loki

### Before — Datadog JSON logs

```python
import json
import logging

class DatadogFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps({
            "message": record.getMessage(),
            "level": record.levelname.lower(),
            "dd.trace_id": getattr(record, "dd.trace_id", None),
            "dd.span_id": getattr(record, "dd.span_id", None),
        })

logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
handler.setFormatter(DatadogFormatter())
logger.addHandler(handler)
```

### After — obskit + Loki

```python
from obskit.logging import get_logger
from obskit.config import configure

configure(service_name="order-service", log_format="json")
logger = get_logger(__name__)

# trace_id and span_id are injected automatically
# Logs are in OpenTelemetry-compatible JSON format
logger.info("payment_processed", amount=99.99, currency="USD")
```

**Log shipping to Loki:** Use promtail to tail stdout and push to Loki, or set
`OBSKIT_OTLP_ENDPOINT` to ship logs directly via OTLP.

```yaml
# promtail config snippet
scrape_configs:
  - job_name: order-service
    static_configs:
      - targets: [localhost]
        labels:
          app: order-service
          __path__: /var/log/order-service/*.log
    pipeline_stages:
      - json:
          expressions:
            level: level
            trace_id: trace_id
      - labels:
          level:
          trace_id:
```

---

## Datadog APM Correlations → Grafana Correlations

In Datadog, you click a log and jump to the trace.  Grafana provides the same
feature via **Correlations** (configured in Grafana UI: Explore → Correlations).

obskit automatically includes `trace_id` in every log record during an active span.
Configure a Grafana correlation from Loki to Tempo:

- **Field:** `trace_id`
- **Target datasource:** Tempo
- **URL:** `${__value.raw}`

This recreates the Datadog log→trace drill-down experience.

---

## Datadog Service Map → Grafana Service Graph

Datadog's Service Map is replicated in Grafana via the **Service Graph** panel
(requires Tempo with metrics-generator enabled).

```yaml
# tempo.yaml
metrics_generator:
  registry:
    external_labels:
      source: tempo
  storage:
    path: /tmp/tempo/generator
  traces_storage:
    path: /tmp/tempo/traces
  processor:
    service_graphs:
      enabled: true
    span_metrics:
      enabled: true
```

---

## Cost Comparison

!!! note "Rough estimate for a 10-service deployment"
    | Component | Datadog | OSS Stack |
    |---|---|---|
    | APM | ~$40/host/month | Tempo: $0 (compute only) |
    | Logs (10 GB/day) | ~$1.50/GB/month = ~$450/month | Loki: ~$0.03/GB/month = ~$9/month |
    | Metrics | ~$5/custom metric/month | Prometheus: $0 |
    | **Total (estimate)** | **~$1,000/month** | **~$50–$200/month (compute)** |

    Actual costs depend heavily on traffic volume, retention, and cloud provider.

---

## Migration Checklist

- [ ] Deploy the OSS stack (docker-compose or Helm) — see [Docker Compose guide](../guides/docker-compose.md)
- [ ] Replace `ddtrace.patch_all()` with `setup_tracing(exporter_endpoint="http://tempo:4317")`
- [ ] Replace `ddtrace.tracer.trace()` spans with `trace_span()` / `async_trace_span()`
- [ ] Replace DogStatsd `statsd.increment/gauge/histogram` with `REDMetrics`
- [ ] Replace Datadog logger formatter with `obskit.logging.get_logger()`
- [ ] Configure promtail or OTLP collector to ship logs to Loki
- [ ] Set up Grafana correlations (Loki trace_id → Tempo)
- [ ] Set up Grafana Service Graph (Tempo metrics-generator)
- [ ] Migrate Datadog monitors to Grafana Alerting rules
- [ ] Remove `ddtrace` and `datadog` packages from `requirements.txt`
- [ ] Update `DD_*` environment variables to `OBSKIT_*`
- [ ] Run `python -m obskit.core.diagnose` to verify the install
- [ ] Verify traces appear in Tempo
- [ ] Verify metrics appear in Prometheus / Grafana
- [ ] Verify logs appear in Loki with `trace_id` labels
