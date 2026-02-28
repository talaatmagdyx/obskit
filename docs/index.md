# obskit

**Production-ready observability toolkit for Python microservices.**

obskit is a modular, zero-overhead observability SDK that brings structured logging, Prometheus metrics, OpenTelemetry tracing, and health checks to your Python services — with a single consistent API.

## Features at a glance

| Feature | Package | Install |
|---------|---------|---------|
| Structured logging + trace correlation | `obskit-logging` | `pip install obskit-logging` |
| RED/Golden/USE metrics + exemplars | `obskit-metrics` | `pip install obskit-metrics` |
| Distributed tracing (OTel) | `obskit-tracing` | `pip install obskit-tracing` |
| Health check framework | `obskit-health` | `pip install obskit-health` |
| Circuit breaker / load shedding | `obskit-resilience` | `pip install obskit-resilience` |
| SLO tracking + alerting | `obskit-slo` | `pip install obskit-slo` |
| FastAPI / Flask / Django / gRPC middleware | `obskit-middleware-*` | `pip install obskit-middleware-fastapi` |
| Everything | `obskit` | `pip install obskit[all]` |

## Quick install

```bash
# Focused install — only what you need
pip install obskit-metrics obskit-logging

# Full install — every package
pip install "obskit[all]"
```

## Zero-boilerplate setup

```python
from obskit.tracing import setup_tracing
from obskit.logging import get_logger

# One call at startup — auto-instruments FastAPI, SQLAlchemy, Redis, httpx…
setup_tracing(exporter_endpoint="http://tempo:4317", sample_rate=0.1)

log = get_logger(__name__)
log.info("order_placed", order_id="123", user_id="u-456")
# → {"event": "order_placed", "order_id": "123", "trace_id": "4bf92f...", "span_id": "00f067..."}
```

## Why obskit?

- **Modular** — install only `obskit-metrics` without pulling in OTel or FastAPI
- **Zero import changes** — `from obskit.logging import get_logger` works whether you install `obskit-logging` or the full `obskit` meta-package
- **Graceful degradation** — all optional integrations (OTel, Prometheus) no-op when not installed
- **100% test coverage** on all packages
- **PEP 561 typed** — full mypy support out of the box
