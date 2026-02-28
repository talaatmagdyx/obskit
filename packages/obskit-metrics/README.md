# obskit-metrics

Prometheus metrics for Python services — RED Method, Four Golden Signals, USE Method, cardinality protection, and trace exemplars.

## Install

```bash
pip install obskit-metrics
# With Prometheus client:
pip install "obskit-metrics[prometheus]"
```

## Quick start

```python
from obskit.metrics import REDMetrics, start_http_server

red = REDMetrics("order_service")

# Record a request
red.observe_request("create_order", duration_seconds=0.045, status="success")

# Auto-timing context manager
with red.track_request("process_payment"):
    gateway.charge(amount)

# Expose /metrics endpoint
start_http_server(port=9090)
```

## Four Golden Signals

```python
from obskit.metrics import GoldenSignals

golden = GoldenSignals("order_service")
golden.observe_request("create_order", 0.045)
golden.set_saturation("cpu", 0.75)        # 75% CPU
golden.set_queue_depth("order_queue", 42)
```

## Trace exemplars

Link metric data-points to Tempo traces (Grafana → jump from a latency spike to the exact trace):

```python
from obskit.metrics.exemplar import observe_with_exemplar
from prometheus_client import Histogram

h = Histogram("http_latency_seconds", "Latency", ["method"])
observe_with_exemplar(h.labels(method="GET"), 0.032)
# Attaches {"trace_id": "4bf92f35...", "span_id": "00f067aa..."} automatically
```

## PromQL cheat-sheet

```promql
# Request rate (req/s)
sum(rate(order_service_requests_total[5m])) by (operation)
# P95 latency
histogram_quantile(0.95, sum(rate(order_service_request_duration_seconds_bucket[5m])) by (le, operation))
# Error rate %
sum(rate(order_service_errors_total[5m])) / sum(rate(order_service_requests_total[5m])) * 100
```
