<div align="center">

# 🔍 obskit-tracing

**Zero-boilerplate OpenTelemetry tracing — one call instruments your entire stack**

---

[![PyPI](https://img.shields.io/pypi/v/obskit-tracing.svg?color=blue)](https://pypi.org/project/obskit-tracing/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![obskit](https://img.shields.io/badge/part%20of-obskit-blueviolet.svg)](https://github.com/talaatmagdyx/obskit)

</div>

## What it does

- **One-call setup** — `setup_tracing()` auto-detects every installed instrumentation library and patches them, so FastAPI, SQLAlchemy, Redis, httpx, and Celery produce spans without a single line of framework-specific configuration code.
- **Manual spans with automatic error recording** — `trace_span` and `async_trace_span` context managers set `ERROR` status and record exceptions automatically, so you never forget to mark a failing span.
- **W3C Baggage propagation** — `set_baggage` / `get_baggage` let you pass cross-cutting values (tenant ID, feature flags, user tier) across every HTTP call and message queue hop without touching your transport layer.

---

## Installation

```bash
# Minimal — OTel SDK + OTLP exporter, manual spans only
pip install "obskit-tracing[opentelemetry]"

# Auto-instrument a FastAPI + SQLAlchemy + Redis service
pip install "obskit-tracing[opentelemetry,fastapi,sqlalchemy,redis]"

# Everything — all supported libraries in one go
pip install "obskit-tracing[auto]"
```

| Extra | What it installs |
|---|---|
| `[opentelemetry]` | OTel API, SDK, and OTLP gRPC exporter — required for any real tracing |
| `[fastapi]` | `opentelemetry-instrumentation-fastapi` |
| `[sqlalchemy]` | `opentelemetry-instrumentation-sqlalchemy` |
| `[redis]` | `opentelemetry-instrumentation-redis` |
| `[httpx]` | `opentelemetry-instrumentation-httpx` |
| `[celery]` | `opentelemetry-instrumentation-celery` |
| `[django]` | `opentelemetry-instrumentation-django` |
| `[requests]` | `opentelemetry-instrumentation-requests` |
| `[grpc]` | `opentelemetry-instrumentation-grpc` (server + client) |
| `[aiopika]` | `opentelemetry-instrumentation-aio-pika` (RabbitMQ) |
| `[auto]` | All of the above |

---

## Quick Start

```python
from obskit.tracing import setup_tracing

# Auto-detect all installed instrumentation packages
# Call this ONCE, before importing FastAPI / SQLAlchemy / etc.
setup_tracing(exporter_endpoint="http://tempo:4317")
```

That single call:
1. Configures a `TracerProvider` with `service.name`, `service.version`, and `deployment.environment` from `ObskitSettings`.
2. Discovers every installed OTel instrumentation package.
3. Patches them so their libraries produce spans automatically.
4. Starts a `BatchSpanProcessor` that ships spans to your OTLP collector.

```python
# Local development — print every span to stdout, no collector needed
setup_tracing(debug=True)

# Production with 10% sampling (W3C ParentBased+TraceIdRatioBased)
setup_tracing(
    exporter_endpoint="http://tempo:4317",
    sample_rate=0.1,
)

# Explicit library list — only instrument what you name
setup_tracing(
    exporter_endpoint="http://tempo:4317",
    instrument=["fastapi", "sqlalchemy", "redis"],
    sample_rate=0.05,
)
```

---

## Features

### 1. setup_tracing() — auto-detects installed instrumentation libs

`setup_tracing()` is the recommended entry point. Import it and call it before your application framework initialises.

```python
# main.py — FastAPI service
from obskit.config import configure
from obskit.tracing import setup_tracing, shutdown_tracing

configure(
    service_name="order-service",
    environment="production",
    version="2.1.0",
    otlp_endpoint="http://tempo:4317",
    trace_sample_rate=0.1,
)

# setup_tracing reads otlp_endpoint and trace_sample_rate from settings
setup_tracing()

from fastapi import FastAPI   # import AFTER setup_tracing for auto-instrumentation

app = FastAPI()

@app.on_event("shutdown")
async def on_shutdown():
    shutdown_tracing()  # flush pending spans before process exits
```

To see what was patched:

```python
from obskit.tracing import detect_available_instrumentors, get_applied_instrumentors

print(detect_available_instrumentors())  # ["fastapi", "redis", "sqlalchemy"]
print(get_applied_instrumentors())       # same list after setup_tracing()
```

### 2. trace_span / async_trace_span — manual spans

Use these context managers anywhere you want to instrument a block of code that is not covered by auto-instrumentation (business logic, third-party SDKs, background tasks).

```python
from obskit.tracing import trace_span, async_trace_span, trace_operation

# Sync context manager
def fulfill_order(order_id: str) -> None:
    with trace_span(
        "fulfill_order",
        component="FulfillmentService",
        operation="fulfill",
        attributes={"order_id": order_id, "warehouse": "eu-west-1"},
    ) as span:
        items = pick_items(order_id)
        ship(items)
        # Exceptions are automatically recorded on the span and re-raised

# Async context manager — safe inside coroutines and async generators
async def fetch_recommendations(user_id: str) -> list[dict]:
    async with async_trace_span(
        "fetch_recommendations",
        component="RecommendationEngine",
        attributes={"user_id": user_id, "algorithm": "collaborative-filter"},
    ):
        vectors = await embedding_store.get(user_id)
        return await model.predict(vectors)

# Decorator — traces the entire function, naming the span after the class/function
@trace_operation(component="PaymentService")
def charge_card(amount: float, card_token: str) -> dict:
    return payment_gateway.charge(amount=amount, source=card_token)
```

Every span records its start time, end time, status (`OK` or `ERROR`), and any exception via `span.record_exception()` automatically — no try/except boilerplate needed.

### 3. W3C Baggage propagation

Baggage is a W3C standard for passing key-value metadata across service boundaries via HTTP headers (`baggage: key=value`). Every downstream service that uses OTel propagation receives these values automatically — no custom header parsing required.

```python
from obskit.tracing import set_baggage, get_baggage, get_all_baggage, clear_baggage

# In an API gateway or middleware — set baggage for the entire request tree
token = set_baggage("tenant_id", "acme-corp")
set_baggage("user_tier", "premium")
set_baggage("feature_flags", "new_checkout,fast_shipping")

# In a downstream service — read values without any HTTP header parsing
tenant   = get_baggage("tenant_id")    # "acme-corp"
tier     = get_baggage("user_tier")    # "premium"
all_vals = get_all_baggage()           # {"tenant_id": "acme-corp", "user_tier": "premium", ...}

# Scope baggage to a specific block and restore the previous context after
token = set_baggage("request_priority", "high")
try:
    await call_downstream_service()
finally:
    clear_baggage(token)   # restores previous baggage context
```

Baggage propagates automatically through any OTel-instrumented HTTP client (httpx, requests) without extra headers configuration.

### 4. get_current_trace_id() / get_current_span_id() — log correlation

Use these helpers to stitch traces and logs together in Grafana / Loki / Datadog. When you use `obskit-logging`, injection is automatic. Use these functions when you need the IDs explicitly — for instance, to embed them in an API response for client-side debugging.

```python
from fastapi import FastAPI
from obskit.tracing import setup_tracing, trace_span, get_current_trace_id, get_current_span_id
from obskit.logging import get_logger

setup_tracing(exporter_endpoint="http://tempo:4317")

app = FastAPI()
logger = get_logger(__name__)

@app.post("/orders")
async def create_order(payload: dict):
    with trace_span("create_order", attributes={"user_id": payload["user_id"]}):
        trace_id = get_current_trace_id()   # "4bf92f3577b34da6a3ce929d0e0e4736"
        span_id  = get_current_span_id()    # "00f067aa0ba902b7"

        # obskit-logging injects these automatically — no manual work needed
        logger.info("order_processing", order_payload_keys=list(payload.keys()))

        order = await order_service.create(payload)

        # Embed in response so frontend engineers can find the trace
        return {
            "order_id": order.id,
            "trace_id": trace_id,   # "click to open in Grafana" UX
        }
```

### 5. Sampling strategies

obskit-tracing supports three sampling modes, all configured through `setup_tracing()` or `ObskitSettings`.

```python
from obskit.tracing import setup_tracing

# Always-on — 100% of traces (default, good for development)
setup_tracing(exporter_endpoint="http://tempo:4317", sample_rate=1.0)

# Always-off — no traces exported (useful in test suites)
setup_tracing(sample_rate=0.0)

# Ratio-based — W3C compliant ParentBased(TraceIdRatioBased)
# The sampling decision made at the root propagates to all child spans,
# so a sampled trace is complete even across many microservices.
setup_tracing(exporter_endpoint="http://tempo:4317", sample_rate=0.1)   # 10%

# Or via environment variable — no code change needed between environments
# OBSKIT_TRACE_SAMPLE_RATE=0.05
setup_tracing()   # reads sample_rate from settings
```

### 6. W3C Trace Context header injection / extraction

When calling downstream services with a raw HTTP client that is not auto-instrumented, you can manually inject and extract W3C `traceparent` / `tracestate` headers.

```python
import httpx
from obskit.tracing import inject_trace_context, trace_context

# Outgoing request — inject traceparent header so the downstream service
# joins the same trace
async def call_inventory_service(product_ids: list[str]) -> dict:
    headers = inject_trace_context()   # adds "traceparent" and "tracestate"
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "http://inventory-service/check",
            json={"product_ids": product_ids},
            headers=headers,
        )
    return resp.json()

# Incoming request — activate the upstream trace context
async def handle_webhook(request):
    with trace_context(dict(request.headers)) as ctx:
        # Spans created here are children of the upstream trace
        with trace_span("process_webhook"):
            await process(request.body)
```

---

## Supported auto-instrumentation packages

| Library | Extra flag | What gets traced |
|---|---|---|
| FastAPI | `[fastapi]` | Every route — method, path, status code, request duration |
| SQLAlchemy | `[sqlalchemy]` | Every query — SQL statement, table, duration |
| redis-py | `[redis]` | Every command — command name, key, duration |
| httpx | `[httpx]` | Every outgoing HTTP call — method, URL, status code |
| Celery | `[celery]` | Task publish and execution — task name, queue, state |
| Django | `[django]` | Every request — view name, method, status code |
| requests | `[requests]` | Every outgoing HTTP call — method, URL, status code |
| gRPC server | `[grpc]` | Every RPC — service, method, status |
| gRPC client | `[grpc]` | Every outgoing RPC — service, method, status |
| aio-pika (RabbitMQ) | `[aiopika]` | Every message publish and consume — exchange, routing key |

---

## Environment Variables

All variables are read from `ObskitSettings` and can also be set programmatically via `configure()`.

| Variable | Default | Description |
|---|---|---|
| `OBSKIT_TRACING_ENABLED` | `true` | Master switch for all tracing |
| `OBSKIT_OTLP_ENDPOINT` | `"http://localhost:4317"` | OTLP gRPC collector URL (Tempo, Jaeger, etc.) |
| `OBSKIT_OTLP_INSECURE` | `true` | Use non-TLS connection; set `false` in production with TLS |
| `OBSKIT_TRACE_SAMPLE_RATE` | `1.0` | Sampling fraction 0.0 (off) to 1.0 (all), uses W3C ParentBased |
| `OBSKIT_TRACE_EXPORT_QUEUE_SIZE` | `2048` | Max queued spans before new spans are dropped |
| `OBSKIT_TRACE_EXPORT_BATCH_SIZE` | `512` | Max spans per export batch |
| `OBSKIT_TRACE_EXPORT_TIMEOUT` | `30.0` | Export operation timeout in seconds |
| `OBSKIT_SERVICE_NAME` | `"unknown"` | Appears as `service.name` resource attribute in every span |
| `OBSKIT_ENVIRONMENT` | `"development"` | Appears as `deployment.environment` resource attribute |
| `OBSKIT_VERSION` | `"0.0.0"` | Appears as `service.version` resource attribute |

---

## 🧩 Part of the obskit family

`obskit-tracing` is part of the [obskit](https://github.com/talaatmagdyx/obskit) monorepo — a production-ready observability toolkit for Python microservices.

| Install only this package | Install everything |
|---|---|
| `pip install "obskit-tracing[opentelemetry]"` | `pip install "obskit[all]"` |
