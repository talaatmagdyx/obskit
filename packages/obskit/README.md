<div align="center">

# 🔭 obskit

**The meta-package that installs the complete obskit observability toolkit for Python microservices**

---

[![PyPI](https://img.shields.io/pypi/v/obskit.svg?color=blue)](https://pypi.org/project/obskit/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![obskit](https://img.shields.io/badge/part%20of-obskit-blueviolet.svg)](https://github.com/talaatmagdyx/obskit)

</div>

## What it does

- **One install, everything included** — `pip install obskit` pulls in all 11 core observability packages: structured logging, Prometheus metrics, OpenTelemetry tracing, Kubernetes health checks, circuit breakers, SLO tracking, observability decorators, database instrumentation, queue tracing, Grafana dashboard generators, and the shared core
- **Namespace package architecture** — all packages share the `obskit` namespace, so `from obskit.logging import get_logger`, `from obskit.metrics import REDMetrics`, and `from obskit.tracing import setup_tracing` all work regardless of which sub-packages you installed individually
- **Modular by design** — each sub-package is also installable on its own (`pip install obskit-logging`), so services that need only structured logging don't pull in Prometheus or gRPC dependencies

---

## What is a Meta-Package?

A meta-package is a Python package whose only job is to declare dependencies. `obskit` contains no source code of its own — installing it simply causes pip to install all the sub-packages it depends on. This pattern lets you:

- Install everything with one command in development
- Pin the entire toolkit to a consistent version in production
- Install only what you need in constrained environments

```bash
# Development: get everything
pip install "obskit[all]"

# Production microservice with FastAPI: only what you need
pip install obskit-logging obskit-metrics obskit-tracing obskit-middleware-fastapi

# Minimal: just structured logging
pip install obskit-logging
```

---

## Install Options

| Command | What you get |
|---------|--------------|
| `pip install obskit` | All 11 core packages (no framework middleware) |
| `pip install "obskit[middleware]"` | Core packages + FastAPI, Flask, Django, gRPC middleware |
| `pip install "obskit[all]"` | Everything — equivalent to `obskit[middleware]` |

---

## Package Dependency Tree

```
obskit  (meta-package)
├── obskit-core           ← Config, correlation IDs, shared interfaces
├── obskit-logging        ← Structlog adapter + trace-log correlation
│   └── obskit-core
├── obskit-metrics        ← RED, Golden Signals, USE, Prometheus
│   └── obskit-core
├── obskit-tracing        ← OpenTelemetry setup + auto-instrumentation
│   └── obskit-core
├── obskit-health         ← Kubernetes readiness/liveness checks
│   ├── obskit-core
│   └── obskit-metrics
├── obskit-resilience     ← Circuit breakers, retry, rate limiting
│   ├── obskit-core
│   ├── obskit-logging
│   └── obskit-metrics
├── obskit-slo            ← SLO tracking, error budgets, alerting
│   ├── obskit-core
│   ├── obskit-logging
│   └── obskit-metrics
├── obskit-decorators     ← @observe, @with_observability decorators
│   ├── obskit-core
│   ├── obskit-logging
│   ├── obskit-metrics
│   └── obskit-slo
├── obskit-db             ← SQLAlchemy instrumentation
│   ├── obskit-core
│   ├── obskit-logging
│   └── obskit-metrics
├── obskit-queue          ← Kafka + RabbitMQ message tracing
│   ├── obskit-core
│   ├── obskit-logging
│   └── obskit-metrics
└── obskit-dashboards     ← Grafana dashboard code generators
    └── obskit-core

# Optional: framework middleware (obskit[middleware] or obskit[all])
├── obskit-middleware-fastapi  ← FastAPI ASGI middleware
│   ├── obskit-core
│   ├── obskit-logging
│   ├── obskit-metrics
│   └── obskit-tracing
├── obskit-middleware-flask    ← Flask WSGI middleware
│   ├── obskit-core
│   ├── obskit-logging
│   ├── obskit-metrics
│   └── obskit-tracing
├── obskit-middleware-django   ← Django middleware
│   ├── obskit-core
│   ├── obskit-logging
│   ├── obskit-metrics
│   └── obskit-tracing
└── obskit-middleware-grpc     ← gRPC server + client interceptors
    ├── obskit-core
    └── obskit-tracing
```

---

## Namespace Package Structure

All packages share a single `obskit` Python namespace using PEP 420 implicit namespace packages. Each sub-package contributes its own sub-namespace:

```
obskit/                          ← shared namespace root (no __init__.py)
├── core/                        ← from obskit-core
│   ├── config.py                ←   get_settings()
│   ├── context.py               ←   get_correlation_id(), set_correlation_id()
│   └── errors.py                ←   ObskitError
├── logging/                     ← from obskit-logging
│   └── __init__.py              ←   get_logger()
├── metrics/                     ← from obskit-metrics
│   ├── red.py                   ←   REDMetrics, get_red_metrics()
│   ├── golden_signals.py        ←   GoldenSignalsMetrics
│   └── __init__.py              ←   start_http_server()
├── tracing/                     ← from obskit-tracing
│   └── tracer.py                ←   setup_tracing()
├── health/                      ← from obskit-health
│   └── checker.py               ←   HealthChecker
├── resilience/                  ← from obskit-resilience
│   └── circuit_breaker.py       ←   CircuitBreaker
├── slo/                         ← from obskit-slo
│   └── tracker.py               ←   SLOTracker
├── decorators/                  ← from obskit-decorators
│   └── observe.py               ←   @observe
├── db/                          ← from obskit-db
│   └── instrumentation.py       ←   instrument_sqlalchemy()
├── queue/                       ← from obskit-queue
│   └── kafka.py, rabbitmq.py    ←   KafkaTracer, RabbitMQTracer
├── dashboards/                  ← from obskit-dashboards
│   └── grafana.py               ←   GrafanaDashboard
└── middleware/                  ← from obskit-middleware-*
    ├── fastapi.py               ←   ObskitMiddleware
    ├── flask.py                 ←   ObskitFlaskMiddleware
    ├── django.py                ←   ObskitDjangoMiddleware
    └── grpc.py                  ←   ObskitServerInterceptor, ObskitClientInterceptor
```

This means these imports work identically whether you installed `obskit` or the individual packages:

```python
from obskit.logging import get_logger        # from obskit-logging
from obskit.metrics import REDMetrics        # from obskit-metrics
from obskit.tracing import setup_tracing     # from obskit-tracing
from obskit.health import HealthChecker      # from obskit-health
```

---

## Batteries Included Quick Start

A complete order service with structured logging, Prometheus metrics, distributed tracing, health checks, and FastAPI middleware:

```python
# main.py — a fully observable FastAPI order service
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# obskit — one namespace, all the tools
from obskit.tracing import setup_tracing
from obskit.logging import get_logger
from obskit.metrics import REDMetrics, start_http_server
from obskit.middleware.fastapi import ObskitMiddleware
from obskit.core.context import get_correlation_id

logger = get_logger(__name__)
red = REDMetrics("order_service")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialize tracing and expose metrics
    setup_tracing(
        service_name="order-service",
        exporter_endpoint="http://tempo:4317",
    )
    start_http_server(9090)  # Prometheus at http://localhost:9090/metrics
    logger.info("order_service_started")
    yield
    logger.info("order_service_stopped")


app = FastAPI(title="Order Service", lifespan=lifespan)

# One line — every endpoint gets correlation IDs, RED metrics, and OTel spans
app.add_middleware(
    ObskitMiddleware,
    exclude_paths=["/health", "/metrics"],
)


class OrderRequest(BaseModel):
    customer_id: str
    items: list[str]
    total: float


@app.get("/health")
async def health():
    return {"status": "ok"}  # excluded from instrumentation


@app.post("/orders", status_code=201)
async def create_order(order: OrderRequest):
    logger.info(
        "order_creating",
        customer_id=order.customer_id,
        item_count=len(order.items),
        total=order.total,
    )
    # Simulate processing
    order_id = "ord-" + order.customer_id[:3] + "-892"
    logger.info("order_created", order_id=order_id)
    return {
        "order_id": order_id,
        "status": "pending",
        "correlation_id": get_correlation_id(),
    }


@app.get("/orders/{order_id}")
async def get_order(order_id: str):
    if not order_id.startswith("ord-"):
        raise HTTPException(status_code=404, detail="Order not found")
    logger.info("order_fetched", order_id=order_id)
    return {"order_id": order_id, "status": "confirmed", "items": ["WIDGET-001"]}
```

Run it:

```bash
pip install "obskit[all]" fastapi uvicorn
uvicorn main:app --host 0.0.0.0 --port 8000
```

What you get automatically:

```bash
# Every request produces structured logs
{"event": "request_started",   "method": "POST", "path": "/orders", "correlation_id": "3fa8c1d2-..."}
{"event": "order_creating",    "customer_id": "cust-42", "item_count": 2, "total": 149.99, "correlation_id": "3fa8c1d2-..."}
{"event": "order_created",     "order_id": "ord-cus-892", "correlation_id": "3fa8c1d2-..."}
{"event": "request_completed", "status_code": 201, "duration_ms": 3.8, "correlation_id": "3fa8c1d2-..."}

# Prometheus metrics at :9090/metrics
# order_service_requests_total{operation="orders",status="success"} 1.0
# order_service_request_duration_seconds_bucket{operation="orders",...} ...

# Response header
# X-Correlation-ID: 3fa8c1d2-6b47-4e9c-a882-f1e39c7d4201
```

---

## All Sub-Packages

| Package | PyPI | What you get |
|---------|------|--------------|
| [`obskit-core`](https://pypi.org/project/obskit-core/) | [![PyPI](https://img.shields.io/pypi/v/obskit-core.svg?color=blue)](https://pypi.org/project/obskit-core/) | Config, correlation IDs, shared errors, test helpers |
| [`obskit-logging`](https://pypi.org/project/obskit-logging/) | [![PyPI](https://img.shields.io/pypi/v/obskit-logging.svg?color=blue)](https://pypi.org/project/obskit-logging/) | Structlog adapter with automatic trace-log correlation |
| [`obskit-metrics`](https://pypi.org/project/obskit-metrics/) | [![PyPI](https://img.shields.io/pypi/v/obskit-metrics.svg?color=blue)](https://pypi.org/project/obskit-metrics/) | RED, Golden Signals, USE metrics + cardinality protection |
| [`obskit-tracing`](https://pypi.org/project/obskit-tracing/) | [![PyPI](https://img.shields.io/pypi/v/obskit-tracing.svg?color=blue)](https://pypi.org/project/obskit-tracing/) | OpenTelemetry setup + auto-instrumentation for 8+ libraries |
| [`obskit-health`](https://pypi.org/project/obskit-health/) | [![PyPI](https://img.shields.io/pypi/v/obskit-health.svg?color=blue)](https://pypi.org/project/obskit-health/) | Kubernetes readiness/liveness endpoints with dependency aggregation |
| [`obskit-resilience`](https://pypi.org/project/obskit-resilience/) | [![PyPI](https://img.shields.io/pypi/v/obskit-resilience.svg?color=blue)](https://pypi.org/project/obskit-resilience/) | Circuit breakers, retry with backoff, rate limiting |
| [`obskit-slo`](https://pypi.org/project/obskit-slo/) | [![PyPI](https://img.shields.io/pypi/v/obskit-slo.svg?color=blue)](https://pypi.org/project/obskit-slo/) | SLO tracking, error budgets, alerting rule generation |
| [`obskit-decorators`](https://pypi.org/project/obskit-decorators/) | [![PyPI](https://img.shields.io/pypi/v/obskit-decorators.svg?color=blue)](https://pypi.org/project/obskit-decorators/) | `@observe` and `@with_observability` function decorators |
| [`obskit-db`](https://pypi.org/project/obskit-db/) | [![PyPI](https://img.shields.io/pypi/v/obskit-db.svg?color=blue)](https://pypi.org/project/obskit-db/) | SQLAlchemy query metrics and slow query logging |
| [`obskit-queue`](https://pypi.org/project/obskit-queue/) | [![PyPI](https://img.shields.io/pypi/v/obskit-queue.svg?color=blue)](https://pypi.org/project/obskit-queue/) | Kafka and RabbitMQ message tracing with context propagation |
| [`obskit-dashboards`](https://pypi.org/project/obskit-dashboards/) | [![PyPI](https://img.shields.io/pypi/v/obskit-dashboards.svg?color=blue)](https://pypi.org/project/obskit-dashboards/) | Grafana dashboard JSON generators for obskit metrics |
| [`obskit-middleware-fastapi`](https://pypi.org/project/obskit-middleware-fastapi/) | [![PyPI](https://img.shields.io/pypi/v/obskit-middleware-fastapi.svg?color=blue)](https://pypi.org/project/obskit-middleware-fastapi/) | FastAPI ASGI middleware (correlation ID, metrics, tracing) |
| [`obskit-middleware-flask`](https://pypi.org/project/obskit-middleware-flask/) | [![PyPI](https://img.shields.io/pypi/v/obskit-middleware-flask.svg?color=blue)](https://pypi.org/project/obskit-middleware-flask/) | Flask WSGI middleware (correlation ID, metrics, tracing) |
| [`obskit-middleware-django`](https://pypi.org/project/obskit-middleware-django/) | [![PyPI](https://img.shields.io/pypi/v/obskit-middleware-django.svg?color=blue)](https://pypi.org/project/obskit-middleware-django/) | Django middleware (settings-driven, DRF-compatible) |
| [`obskit-middleware-grpc`](https://pypi.org/project/obskit-middleware-grpc/) | [![PyPI](https://img.shields.io/pypi/v/obskit-middleware-grpc.svg?color=blue)](https://pypi.org/project/obskit-middleware-grpc/) | gRPC server and client interceptors |

---

## Grafana / Prometheus / Tempo Integration

obskit is designed for the Grafana observability stack out of the box:

```yaml
# docker-compose.yml snippet
services:
  order-service:
    image: my-order-service
    ports:
      - "8000:8000"   # app
      - "9090:9090"   # Prometheus metrics

  prometheus:
    image: prom/prometheus
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml

  tempo:
    image: grafana/tempo
    command: ["-config.file=/etc/tempo.yaml"]

  loki:
    image: grafana/loki

  grafana:
    image: grafana/grafana
    ports:
      - "3000:3000"
```

```yaml
# prometheus.yml
scrape_configs:
  - job_name: order-service
    static_configs:
      - targets: ["order-service:9090"]
```

```python
# In your service startup
from obskit.tracing import setup_tracing
from obskit.metrics import start_http_server

setup_tracing(
    service_name="order-service",
    exporter_endpoint="http://tempo:4317",   # OTLP gRPC to Tempo
)
start_http_server(9090)                      # Prometheus pull endpoint
```

---

## obskit is the meta-package

`obskit` itself contains no source code — it is a dependency declaration that brings together the entire toolkit. For production microservices, install only the packages your service actually uses:

| Use case | Install |
|----------|---------|
| FastAPI service with full observability | `pip install obskit "obskit-middleware-fastapi" "obskit-tracing[opentelemetry,fastapi]"` |
| Flask service | `pip install obskit "obskit-middleware-flask" "obskit-tracing[opentelemetry]"` |
| Django service | `pip install obskit "obskit-middleware-django" "obskit-tracing[opentelemetry,django]"` |
| gRPC service | `pip install obskit "obskit-middleware-grpc" "obskit-tracing[opentelemetry,grpc]"` |
| Celery worker | `pip install obskit "obskit-tracing[opentelemetry,celery]"` |
| Everything | `pip install "obskit[all]"` |

Sub-package PyPI links:
[obskit-core](https://pypi.org/project/obskit-core/) •
[obskit-logging](https://pypi.org/project/obskit-logging/) •
[obskit-metrics](https://pypi.org/project/obskit-metrics/) •
[obskit-tracing](https://pypi.org/project/obskit-tracing/) •
[obskit-health](https://pypi.org/project/obskit-health/) •
[obskit-resilience](https://pypi.org/project/obskit-resilience/) •
[obskit-slo](https://pypi.org/project/obskit-slo/) •
[obskit-decorators](https://pypi.org/project/obskit-decorators/) •
[obskit-db](https://pypi.org/project/obskit-db/) •
[obskit-queue](https://pypi.org/project/obskit-queue/) •
[obskit-dashboards](https://pypi.org/project/obskit-dashboards/) •
[obskit-middleware-fastapi](https://pypi.org/project/obskit-middleware-fastapi/) •
[obskit-middleware-flask](https://pypi.org/project/obskit-middleware-flask/) •
[obskit-middleware-django](https://pypi.org/project/obskit-middleware-django/) •
[obskit-middleware-grpc](https://pypi.org/project/obskit-middleware-grpc/)
