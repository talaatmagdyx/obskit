# Migrating from Datadog

This guide shows how to migrate from Datadog's observability stack to obskit with Prometheus/Jaeger/Grafana.

## Why Migrate?

| Aspect | Datadog | obskit + OSS Stack |
|--------|---------|-------------------|
| Cost | $$$ (per host/metric) | Open source |
| Vendor lock-in | High | None |
| Self-hosted option | No | Yes |
| Data ownership | Cloud | Yours |
| Customization | Limited | Full control |

## Architecture Comparison

**Datadog:**
```
App → Datadog Agent → Datadog Cloud → Datadog UI
```

**obskit + OSS:**
```
App → Prometheus (metrics) → Grafana
    → Jaeger (traces)     ↗
    → Loki (logs)        ↗
```

## Before: Datadog

```python
# datadog_setup.py
from datadog import initialize, statsd
from ddtrace import tracer, patch_all
import logging

# Initialize Datadog
initialize(api_key="...", app_key="...")
patch_all()

# Metrics
statsd.increment('web.requests', tags=['endpoint:orders'])
statsd.histogram('web.request.duration', duration, tags=['endpoint:orders'])
statsd.gauge('web.active_connections', count)

# Tracing
@tracer.wrap(service="order-service", resource="process_order")
def process_order(order_id):
    span = tracer.current_span()
    span.set_tag("order.id", order_id)
    return do_work()

# Logging
logging.info("Processing order", extra={"order_id": order_id})
```

## After: obskit

```python
# main.py
from obskit import configure, get_red_metrics, get_logger
from obskit.tracing import get_tracer

configure(
    service_name="order-service",
    otlp_endpoint="http://jaeger:4317",  # Or your collector
    metrics_port=9090,
)

metrics = get_red_metrics()
logger = get_logger()
tracer = get_tracer()

def process_order(order_id):
    logger.info("processing_order", order_id=order_id)
    
    with tracer.start_span("process_order", attributes={"order.id": order_id}):
        with metrics.track_request("process_order"):
            return do_work()
```

## Step-by-Step Migration

### Step 1: Set up open-source backends

```yaml
# docker-compose.yml
version: '3'
services:
  prometheus:
    image: prom/prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml

  jaeger:
    image: jaegertracing/all-in-one
    ports:
      - "16686:16686"  # UI
      - "4317:4317"    # OTLP gRPC

  grafana:
    image: grafana/grafana
    ports:
      - "3000:3000"
```

### Step 2: Install obskit

```bash
pip install obskit[all]
```

### Step 3: Replace Datadog initialization

**Before:**
```python
from datadog import initialize
from ddtrace import patch_all

initialize(api_key="xxx", app_key="xxx")
patch_all()
```

**After:**
```python
from obskit import configure

configure(
    service_name="my-service",
    environment="production",
    version="1.0.0",
    otlp_endpoint="http://jaeger:4317",
    metrics_port=9090,
)
```

### Step 4: Migrate metrics

**Before (Datadog DogStatsD):**
```python
from datadog import statsd

statsd.increment('requests.total', tags=['endpoint:orders', 'status:200'])
statsd.histogram('request.duration', 0.5, tags=['endpoint:orders'])
statsd.gauge('connections.active', 42)
```

**After (obskit/Prometheus):**
```python
from obskit import get_red_metrics
from obskit.metrics import Gauge

metrics = get_red_metrics()
active_connections = Gauge('connections_active', 'Active connections')

# Increment + histogram combined
metrics.observe_request(
    operation="orders",
    duration_seconds=0.5,
    status="success",
)

# Gauge
active_connections.set(42)
```

### Step 5: Migrate tracing

**Before (ddtrace):**
```python
from ddtrace import tracer

@tracer.wrap(service="my-service", resource="operation")
def my_function():
    span = tracer.current_span()
    span.set_tag("key", "value")
    return result
```

**After (obskit/OpenTelemetry):**
```python
from obskit.tracing import get_tracer

tracer = get_tracer()

def my_function():
    with tracer.start_span("operation", attributes={"key": "value"}):
        return result
```

### Step 6: Migrate logging

**Before (Datadog logging):**
```python
import logging
from ddtrace import tracer

logger = logging.getLogger(__name__)

def process():
    span = tracer.current_span()
    logger.info("Processing", extra={
        "dd.trace_id": span.trace_id,
        "dd.span_id": span.span_id,
    })
```

**After (obskit structured logging):**
```python
from obskit import get_logger

logger = get_logger(__name__)

def process():
    # trace_id and correlation_id automatically included
    logger.info("processing")
```

## Metric Name Mapping

| Datadog | Prometheus/obskit |
|---------|-------------------|
| `web.requests` | `http_requests_total` |
| `web.request.duration` | `http_request_duration_seconds` |
| `system.cpu.usage` | `process_cpu_seconds_total` |
| Custom tags | Prometheus labels |

## Dashboard Migration

Export Datadog dashboards and recreate in Grafana:

1. **Export from Datadog**: Download dashboard JSON
2. **Use Grafana importers**: Some community tools convert formats
3. **Use obskit dashboards**: Pre-built RED method dashboards included

```bash
# Import obskit dashboard
kubectl apply -f helm/obskit/dashboards/
```

## Alert Migration

| Datadog Alert | Prometheus Alert |
|---------------|-----------------|
| Monitor | AlertRule |
| Query: `avg:http.request.duration{service:api}` | `histogram_quantile(0.99, http_request_duration_seconds)` |
| Threshold: > 1s | `> 1` |

Example Prometheus alert:

```yaml
groups:
  - name: slo-alerts
    rules:
      - alert: HighLatency
        expr: histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m])) > 1
        for: 5m
        labels:
          severity: warning
```

## Cost Comparison

| Scenario | Datadog (estimate) | Self-hosted OSS |
|----------|-------------------|-----------------|
| 10 hosts, 1000 metrics | ~$500/mo | Infrastructure cost only |
| 100 hosts, 10000 metrics | ~$5000/mo | Infrastructure cost only |
| Traces (1M/day) | ~$200/mo | Storage cost only |

## Gradual Migration

1. **Week 1-2**: Deploy OSS stack alongside Datadog
2. **Week 3-4**: Configure obskit, dual-write metrics
3. **Week 5-6**: Build Grafana dashboards
4. **Week 7-8**: Set up Prometheus alerts
5. **Week 9-10**: Validate data parity
6. **Week 11-12**: Decommission Datadog agent

## Common Gotchas

1. **Metric naming**: Datadog uses dots, Prometheus uses underscores
2. **Tag format**: Datadog `tag:value`, Prometheus `{label="value"}`
3. **Push vs Pull**: Datadog pushes, Prometheus scrapes
4. **APM sampling**: May need to adjust trace sampling rates

