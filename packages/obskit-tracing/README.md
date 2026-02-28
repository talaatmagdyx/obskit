# obskit-tracing

Zero-boilerplate OpenTelemetry tracing for Python services — one call instruments FastAPI, SQLAlchemy, Redis, httpx, Celery, and more.

## Install

```bash
# Minimal — manual spans only
pip install "obskit-tracing[opentelemetry]"

# Auto-instrument FastAPI + Redis + SQLAlchemy
pip install "obskit-tracing[opentelemetry,fastapi,redis,sqlalchemy]"

# Kitchen-sink — everything
pip install "obskit-tracing[auto]"
```

## Quick start

```python
from obskit.tracing import setup_tracing

# Auto-detect all installed instrumentation packages
setup_tracing(exporter_endpoint="http://tempo:4317")

# Local development — print spans to stdout
setup_tracing(debug=True)

# Production with 10 % sampling
setup_tracing(exporter_endpoint="http://tempo:4317", sample_rate=0.1)
```

## Manual spans

```python
from obskit.tracing import trace_span, async_trace_span

# Sync
with trace_span("process_order", attributes={"order_id": "123"}):
    process_order()

# Async
async with async_trace_span("fetch_user"):
    user = await db.get_user(uid)
```

## W3C Baggage

```python
from obskit.tracing import set_baggage, get_baggage

set_baggage("tenant_id", "acme-corp")       # propagates to all downstream HTTP calls
tenant = get_baggage("tenant_id")           # "acme-corp"
```

## Trace-log correlation

```python
from obskit.tracing import get_current_trace_id, get_current_span_id

trace_id = get_current_trace_id()   # "4bf92f3577b34da6..."
span_id  = get_current_span_id()    # "00f067aa0ba902b7"
```

## Supported auto-instrumentation packages

| Name | Extra | Library |
|------|-------|---------|
| `fastapi` | `[fastapi]` | FastAPI |
| `sqlalchemy` | `[sqlalchemy]` | SQLAlchemy |
| `redis` | `[redis]` | redis-py |
| `httpx` | `[httpx]` | httpx |
| `celery` | `[celery]` | Celery |
| `django` | `[django]` | Django |
| `requests` | `[requests]` | requests |
| `grpc_server` / `grpc_client` | `[grpc]` | gRPC |
| `aiopika` | `[aiopika]` | aio-pika (RabbitMQ) |
