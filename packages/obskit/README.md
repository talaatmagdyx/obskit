# obskit

The complete observability toolkit for Python microservices — structured logging, Prometheus metrics, distributed tracing, health checks, circuit breakers, SLOs, and framework middleware in one package.

## Install

```bash
# Full stack
pip install obskit

# Minimal (just what you need)
pip install obskit-metrics obskit-tracing
```

## Quick start — 4 lines of observability

```python
from obskit.tracing import setup_tracing
from obskit.logging import get_logger
from obskit.metrics import REDMetrics

# One-time setup at startup
setup_tracing(exporter_endpoint="http://tempo:4317")

logger = get_logger(__name__)
red    = REDMetrics("order_service")

# In your handler
logger.info("order_placed", order_id="123")           # → Loki (with trace_id\!)
red.observe_request("create_order", 0.045)            # → Prometheus
# FastAPI/SQLAlchemy/Redis spans are automatic        # → Tempo
```

## Package breakdown

| Package | Install | What you get |
|---------|---------|--------------|
| `obskit-core` | always | Config, errors, correlation IDs |
| `obskit-logging` | always | Structlog + trace-log correlation |
| `obskit-metrics` | always | RED, Golden Signals, USE, exemplars |
| `obskit-tracing` | always | OTel setup, auto-instrument, baggage |
| `obskit-health` | always | Kubernetes health endpoints |
| `obskit-resilience` | always | Circuit breakers, retry, rate limiting |
| `obskit-slo` | always | SLO tracking + error budgets |
| `obskit-middleware-fastapi` | optional | FastAPI ASGI middleware |
| `obskit-middleware-flask` | optional | Flask WSGI middleware |
| `obskit-middleware-django` | optional | Django middleware |
| `obskit-middleware-grpc` | optional | gRPC interceptors |

## Grafana / Prometheus integration

```bash
# Start metrics server
python -c "from obskit.metrics import start_http_server; start_http_server(9090)"
# Metrics at http://localhost:9090/metrics

# Configure Prometheus scrape
# scrape_configs:
#   - job_name: my-service
#     static_configs:
#       - targets: ['localhost:9090']
```
