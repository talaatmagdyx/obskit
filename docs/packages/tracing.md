# obskit-tracing

OpenTelemetry-based distributed tracing for obskit services. Provides zero-code auto-instrumentation, manual span creation, W3C Baggage propagation, and support for Tempo, Jaeger, Zipkin, and any generic OTLP collector.

## Installation

```bash
pip install obskit-tracing
```

### With OpenTelemetry SDK

```bash
pip install "obskit-tracing[opentelemetry]"
```

### With auto-instrumentation for all common libraries

```bash
pip install "obskit-tracing[auto]"
```

---

## setup_tracing

The single entry point for production use. Call it **once at application startup**, before importing instrumented libraries (FastAPI, SQLAlchemy, etc.).

```python
from obskit.tracing import setup_tracing

applied = setup_tracing(
    exporter_endpoint="http://tempo:4317",
    sample_rate=0.1,
)
print("Instrumented:", applied)
# Instrumented: ['fastapi', 'sqlalchemy', 'redis', 'httpx']
```

### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `exporter_endpoint` | `str \| None` | `None` | OTLP collector URL. Falls back to `ObskitSettings.otlp_endpoint` |
| `auto_instrument` | `bool` | `True` | Auto-detect and patch all installed instrumentation packages |
| `instrument` | `list[str] \| None` | `None` | Explicit list of instrumentors (overrides auto-detection) |
| `service_name` | `str \| None` | `None` | Service name override. Falls back to `ObskitSettings.service_name` |
| `debug` | `bool` | `False` | Print every span to stdout (console exporter; no collector needed) |
| `sample_rate` | `float` | `1.0` | Fraction of traces to keep: `1.0` = all, `0.1` = 10% |

### Returns

`list[str]` — names of instrumentors successfully applied. Empty list when `auto_instrument=False`.

### Examples

```python
# Minimal — reads everything from obskit-core settings
setup_tracing()

# Local development — print spans to stdout, no Tempo/Jaeger needed
setup_tracing(debug=True)

# Production — 10% sampling to Grafana Tempo
setup_tracing(
    exporter_endpoint="http://tempo:4317",
    sample_rate=0.1,
)

# Explicit library list (reproducible in tests)
setup_tracing(
    exporter_endpoint="http://tempo:4317",
    instrument=["fastapi", "sqlalchemy", "redis", "httpx"],
)

# Manual spans only, disable auto-instrumentation
setup_tracing(
    exporter_endpoint="http://jaeger:4317",
    auto_instrument=False,
)
```

---

## configure_tracing (low-level)

When you need fine-grained control without auto-instrumentation:

```python
from obskit.tracing import configure_tracing

ok = configure_tracing(
    service_name="order-service",
    otlp_endpoint="http://jaeger:4317",
    debug=False,
    sample_rate=0.25,
)
```

---

## trace_span — synchronous context manager

```python
from obskit.tracing import trace_span

with trace_span("process_order", attributes={"order_id": "ord-123"}):
    process_order(order)
```

### Parameters

| Parameter | Type | Description |
|---|---|---|
| `name` | `str` | Span name (displayed in Tempo/Jaeger) |
| `component` | `str \| None` | Added as `component` span attribute |
| `operation` | `str \| None` | Added as `operation` span attribute |
| `attributes` | `dict[str, Any] \| None` | Additional span attributes (values stringified) |

```python
with trace_span(
    "validate_payment",
    component="PaymentService",
    operation="validation",
    attributes={"payment_id": "pay-456", "currency": "USD"},
) as span:
    result = validate(payment)
    if span:
        span.set_attribute("validated", True)
```

!!! tip "Safe when tracing is unavailable"
    If `obskit-tracing[opentelemetry]` is not installed or tracing is not configured, `trace_span` yields `None` and is otherwise a no-op. Your business logic is never interrupted.

---

## async_trace_span — asynchronous context manager

Identical to `trace_span` but safe to use with `async with` inside coroutines.

```python
from obskit.tracing import async_trace_span

async def fetch_user(uid: str):
    async with async_trace_span(
        "fetch_user",
        attributes={"user_id": uid},
    ) as span:
        user = await db.get_user(uid)
        if span:
            span.set_attribute("found", user is not None)
        return user
```

---

## trace_operation decorator

```python
from obskit.tracing.tracer import trace_operation

# Wraps any sync or async function in a span
@trace_operation("send_notification")
async def send_notification(user_id: str, message: str):
    await email_client.send(user_id, message)
```

---

## Auto-instrumentation

`setup_tracing()` automatically patches all OTel instrumentation packages that are installed. The following libraries are supported:

| Name | OTel package | Patches |
|---|---|---|
| `fastapi` | `opentelemetry-instrumentation-fastapi` | All routes |
| `sqlalchemy` | `opentelemetry-instrumentation-sqlalchemy` | All queries |
| `redis` | `opentelemetry-instrumentation-redis` | All commands |
| `httpx` | `opentelemetry-instrumentation-httpx` | All outgoing HTTP |
| `celery` | `opentelemetry-instrumentation-celery` | All tasks |
| `django` | `opentelemetry-instrumentation-django` | All views |
| `requests` | `opentelemetry-instrumentation-requests` | All outgoing HTTP |
| `grpc_server` | `opentelemetry-instrumentation-grpc` | gRPC server calls |
| `grpc_client` | `opentelemetry-instrumentation-grpc` | gRPC client calls |
| `aiopika` | `opentelemetry-instrumentation-aio-pika` | RabbitMQ messages |

```python
from obskit.tracing import detect_available_instrumentors, get_applied_instrumentors

# Read-only probe — what is installed?
available = detect_available_instrumentors()
# ["fastapi", "sqlalchemy", "redis"]

# What has been applied so far?
applied = get_applied_instrumentors()

# Tear down all instrumentors (useful in tests)
from obskit.tracing import uninstrument_all
uninstrument_all()
```

---

## W3C Baggage

Baggage propagates key-value pairs across service boundaries via HTTP `baggage:` headers. All OTel-instrumented downstream services receive them automatically.

```python
from obskit.tracing import set_baggage, get_baggage, get_all_baggage, clear_baggage

# Set a baggage entry (returns a context token)
token = set_baggage("tenant_id", "acme-corp")
# Every outgoing HTTP call from here forwards:
#   baggage: tenant_id=acme-corp

# Read in the same or a downstream service
tenant = get_baggage("tenant_id")    # "acme-corp"

# Read all entries
items = get_all_baggage()            # {"tenant_id": "acme-corp", ...}

# Restore previous context when done
try:
    await call_downstream()
finally:
    clear_baggage(token)
```

---

## Current span helpers

```python
from obskit.tracing import get_current_trace_id, get_current_span_id

trace_id = get_current_trace_id()   # "4bf92f3577b34da6a3ce929d0e0e4736" or None
span_id  = get_current_span_id()    # "00f067aa0ba902b7" or None
```

These are used internally by `obskit-logging` to inject `trace_id` and `span_id` into every log record automatically.

---

## Context propagation (HTTP headers)

```python
from obskit.tracing.tracer import inject_trace_context, extract_trace_context

# Outgoing request — inject the active span's context into headers
headers = {}
inject_trace_context(headers)
# headers = {"traceparent": "00-4bf92f35...-00f067aa...-01"}

response = await httpx_client.get(url, headers=headers)

# Incoming request — restore context from W3C traceparent header
ctx = extract_trace_context(dict(request.headers))
```

---

## Environment variable configuration

All settings can be overridden via environment variables through `obskit-core`:

```bash
# Service identity
export OBSKIT_SERVICE_NAME=order-service
export OBSKIT_ENVIRONMENT=production
export OBSKIT_VERSION=2.0.0

# Tracing
export OBSKIT_TRACING_ENABLED=true
export OBSKIT_OTLP_ENDPOINT=http://tempo:4317
export OBSKIT_OTLP_INSECURE=false
export OBSKIT_TRACE_SAMPLE_RATE=0.1
export OBSKIT_TRACE_EXPORT_QUEUE_SIZE=2048
export OBSKIT_TRACE_EXPORT_BATCH_SIZE=512
export OBSKIT_TRACE_EXPORT_TIMEOUT=30
```

---

## Exporters

| Exporter | Endpoint format | Notes |
|---|---|---|
| Grafana Tempo | `http://tempo:4317` | gRPC OTLP; default for obskit |
| Jaeger | `http://jaeger:4317` | Jaeger 1.35+ accepts OTLP |
| Zipkin | `http://zipkin:9411/api/v2/spans` | HTTP, not gRPC |
| OTLP collector | `http://otel-collector:4317` | Routes to any backend |
| Console (debug) | — | `setup_tracing(debug=True)` |

```python
# Tempo (gRPC OTLP)
setup_tracing(exporter_endpoint="http://tempo:4317")

# Jaeger (gRPC OTLP accepted since Jaeger 1.35)
setup_tracing(exporter_endpoint="http://jaeger:4317")

# Generic OTLP collector
setup_tracing(exporter_endpoint="http://otel-collector:4317")

# Local development — no collector required
setup_tracing(debug=True)
```

---

## Shutdown

```python
from obskit.tracing.tracer import shutdown_tracing

# Flush pending spans and close the exporter
# (registered automatically via atexit; call explicitly for clean shutdown)
shutdown_tracing()
```

---

## Availability check

```python
from obskit.tracing.tracer import is_tracing_available

if is_tracing_available():
    print("OpenTelemetry SDK is installed and configured")
```

---

## Full FastAPI example

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from obskit.config import configure
from obskit.tracing import setup_tracing, trace_span, async_trace_span, set_baggage

@asynccontextmanager
async def lifespan(app: FastAPI):
    configure(
        service_name="order-service",
        environment="production",
        otlp_endpoint="http://tempo:4317",
        trace_sample_rate=0.1,
    )
    setup_tracing(
        exporter_endpoint="http://tempo:4317",
        sample_rate=0.1,
        instrument=["fastapi", "sqlalchemy", "redis"],
    )
    yield

app = FastAPI(lifespan=lifespan)

@app.post("/orders")
async def create_order(order: dict):
    set_baggage("tenant_id", order.get("tenant_id", "default"))

    async with async_trace_span(
        "create_order",
        attributes={"order.total": str(order.get("total", 0))},
    ):
        result = await order_service.create(order)
        return result
```
