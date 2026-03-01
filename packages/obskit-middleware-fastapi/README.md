<div align="center">

# ⚡ obskit-middleware-fastapi

**One-line FastAPI middleware that auto-instruments every request with correlation IDs, RED metrics, and distributed traces**

---

[![PyPI](https://img.shields.io/pypi/v/obskit-middleware-fastapi.svg?color=blue)](https://pypi.org/project/obskit-middleware-fastapi/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![obskit](https://img.shields.io/badge/part%20of-obskit-blueviolet.svg)](https://github.com/talaatmagdyx/obskit)

</div>

## What it does

- **Zero-config observability** — a single `app.add_middleware(ObskitMiddleware)` call instruments every endpoint: correlation IDs, RED metrics, structured access logs, and OpenTelemetry spans are all automatic
- **Correlation ID propagation** — reads `X-Correlation-ID` from incoming requests (or generates one), threads it through every log line and span, and echoes it back in the response header so clients can trace end-to-end
- **Smart path exclusion** — health, readiness, and metrics endpoints are excluded by default so Prometheus and Kubernetes probes never pollute your latency histograms

---

## Installation

```bash
pip install obskit-middleware-fastapi
```

To add distributed tracing with an OTLP backend (Grafana Tempo, Jaeger, etc.):

```bash
pip install "obskit-middleware-fastapi" "obskit-tracing[opentelemetry,fastapi]"
```

---

## Quick Start

```python
from fastapi import FastAPI
from obskit.middleware.fastapi import ObskitMiddleware

app = FastAPI()
app.add_middleware(ObskitMiddleware)  # that's it


@app.get("/orders/{order_id}")
async def get_order(order_id: str):
    # correlation_id, trace_id, RED metrics — all automatic
    return {"order_id": order_id, "status": "confirmed"}
```

Every request through this app now produces:

```
{"event": "request_started",  "method": "GET", "path": "/orders/ord-892", "correlation_id": "3fa8c1d2-...", "client_ip": "10.0.0.5"}
{"event": "request_completed","method": "GET", "path": "/orders/ord-892", "status_code": 200, "duration_ms": 4.3, "correlation_id": "3fa8c1d2-..."}
```

And the response carries:

```
X-Correlation-ID: 3fa8c1d2-6b47-4e9c-a882-f1e39c7d4201
```

---

## Before vs After

Without obskit you'd need to write all of this yourself for every service:

```python
# WITHOUT obskit — boilerplate you repeat in every service
import uuid, time, logging
from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware
from prometheus_client import Counter, Histogram
from opentelemetry import trace

REQUEST_COUNT = Counter("requests_total", ["method", "path", "status"])
REQUEST_LATENCY = Histogram("request_duration_seconds", ["operation"])

class ManualMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
        tracer = trace.get_tracer(__name__)
        start = time.perf_counter()
        logging.info(f"[{correlation_id}] {request.method} {request.url.path}")
        with tracer.start_as_current_span(request.url.path):
            response = await call_next(request)
        duration = time.perf_counter() - start
        REQUEST_COUNT.labels(request.method, request.url.path, response.status_code).inc()
        REQUEST_LATENCY.labels(request.url.path).observe(duration)
        response.headers["X-Correlation-ID"] = correlation_id
        logging.info(f"[{correlation_id}] {response.status_code} {duration*1000:.1f}ms")
        return response

app = FastAPI()
app.add_middleware(ManualMiddleware)
```

```python
# WITH obskit — done
from fastapi import FastAPI
from obskit.middleware.fastapi import ObskitMiddleware

app = FastAPI()
app.add_middleware(ObskitMiddleware)
```

---

## Features

### Automatic RED Metrics

Every request records the three metrics that matter most for any HTTP service:

| Metric | Type | Labels | What it tells you |
|--------|------|--------|-------------------|
| `requests_total` | Counter | `operation`, `status`, `error_type` | Request rate and error rate |
| `request_duration_seconds` | Histogram | `operation`, `status` | Latency distribution (p50, p95, p99) |

```python
# Expose metrics for Prometheus to scrape
from obskit.metrics import start_http_server

start_http_server(9090)
# curl http://localhost:9090/metrics
```

Prometheus scrape config:

```yaml
scrape_configs:
  - job_name: order-service
    static_configs:
      - targets: ["order-service:9090"]
```

### Correlation ID Threading

The middleware reads `X-Correlation-ID` from the incoming request. If absent, it generates a UUID v4. The ID is:

- Bound to the current async context so all log calls within the request carry it automatically
- Injected into the active OpenTelemetry span as a baggage attribute
- Echoed back in the response `X-Correlation-ID` header

```python
from fastapi import FastAPI, Request
from obskit.middleware.fastapi import ObskitMiddleware
from obskit.core.context import get_correlation_id
from obskit.logging import get_logger

app = FastAPI()
app.add_middleware(ObskitMiddleware)

logger = get_logger(__name__)


@app.post("/orders")
async def create_order(request: Request):
    # correlation_id is in context — logger picks it up automatically
    logger.info("processing_order", amount=99.95, currency="USD")
    # → {"event": "processing_order", "amount": 99.95, "correlation_id": "3fa8c1d2-..."}

    # You can also read it explicitly
    cid = get_correlation_id()
    return {"order_id": "ord-123", "correlation_id": cid}
```

### Distributed Tracing with obskit-tracing

When `obskit-tracing` is configured, the middleware automatically extracts W3C `traceparent` / `tracestate` headers from incoming requests and links spans to the upstream trace. Downstream calls made with instrumented clients (httpx, requests, SQLAlchemy) will appear as child spans.

```python
from fastapi import FastAPI
from obskit.middleware.fastapi import ObskitMiddleware
from obskit.tracing import setup_tracing

# One-time startup configuration
setup_tracing(
    service_name="order-service",
    exporter_endpoint="http://tempo:4317",
)

app = FastAPI()
app.add_middleware(ObskitMiddleware)


@app.post("/orders")
async def create_order():
    # This handler's span is automatically:
    # - linked to any upstream trace via traceparent header
    # - propagated to downstream httpx/requests calls
    # - exported to Tempo/Jaeger via OTLP
    ...
```

### Excluding Paths

Health probes and metrics endpoints should never skew your latency dashboards. The default exclusion list covers the most common Kubernetes and Prometheus patterns, and you can extend it:

```python
app.add_middleware(
    ObskitMiddleware,
    exclude_paths=[
        "/health",
        "/ready",
        "/live",
        "/metrics",
        "/api/v1/internal/status",  # add your own
    ],
)
```

Excluded paths pass straight through with zero overhead — no timing, no logging, no metrics.

### Selective Instrumentation

All three pillars of observability can be toggled independently:

```python
app.add_middleware(
    ObskitMiddleware,
    track_metrics=True,   # Prometheus RED metrics
    track_logging=True,   # Structured JSON access logs
    track_tracing=True,   # OpenTelemetry spans
)
```

This is useful when you want metrics but are not yet running an OTLP backend, or when you need to reduce log volume in high-traffic services.

---

## What Every Request Gets

| Signal | Detail | Where it goes |
|--------|--------|---------------|
| `X-Correlation-ID` header | Generated UUID or forwarded from client | Response headers + log context |
| `request_started` log | method, path, operation, client_ip | Loki / stdout |
| `request_completed` log | status_code, duration_ms, correlation_id | Loki / stdout |
| `requests_total` counter | Incremented with status label | Prometheus |
| `request_duration_seconds` histogram | Full latency distribution | Prometheus |
| OTel span | Named after the route path | Tempo / Jaeger via OTLP |
| `traceparent` propagation | Extracted from request, injected into response | Distributed trace graph |

---

## Configuration Reference

```python
app.add_middleware(
    ObskitMiddleware,
    exclude_paths=["/health", "/ready", "/live", "/metrics"],  # default
    track_metrics=True,   # default
    track_logging=True,   # default
    track_tracing=True,   # default
)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `exclude_paths` | `list[str]` | `["/health", "/ready", "/live", "/metrics"]` | Path prefixes to skip entirely |
| `track_metrics` | `bool` | `True` | Record RED metrics in Prometheus |
| `track_logging` | `bool` | `True` | Emit structured access logs |
| `track_tracing` | `bool` | `True` | Create and export OTel spans |

---

## Complete Example: Order Service

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from obskit.middleware.fastapi import ObskitMiddleware
from obskit.tracing import setup_tracing
from obskit.logging import get_logger
from obskit.metrics import start_http_server

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_tracing(service_name="order-service", exporter_endpoint="http://tempo:4317")
    start_http_server(9090)
    yield


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    ObskitMiddleware,
    exclude_paths=["/health", "/metrics"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}  # not instrumented


@app.post("/orders")
async def create_order(customer_id: str, total: float):
    logger.info("order_creating", customer_id=customer_id, total=total)
    # ... business logic ...
    logger.info("order_created", order_id="ord-456", total=total)
    return {"order_id": "ord-456", "status": "pending"}


@app.get("/orders/{order_id}")
async def get_order(order_id: str):
    if order_id == "missing":
        raise HTTPException(404, "Order not found")
        # → automatically records HTTP404 error metric
    return {"order_id": order_id, "status": "confirmed"}
```

---

## 🧩 Part of the obskit family

`obskit-middleware-fastapi` is part of the [obskit](https://github.com/talaatmagdyx/obskit) monorepo — a production-ready observability toolkit for Python microservices.

| Install only this package | Install everything |
|---|---|
| `pip install obskit-middleware-fastapi` | `pip install "obskit[all]"` |
