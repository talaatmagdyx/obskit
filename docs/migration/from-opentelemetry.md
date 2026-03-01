# Migrating from raw OpenTelemetry SDK to obskit

The OpenTelemetry Python SDK is powerful but requires significant boilerplate to
configure correctly for production.  obskit wraps the SDK with sensible defaults,
auto-instrumentation detection, and first-class integration with structured logging
and Prometheus metrics — while keeping full OTel compatibility.

---

## Why Migrate?

### Raw OTel setup: ~60 lines of boilerplate

```python
# What you write today with raw OTel
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace.sampling import TraceIdRatioBased
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

resource = Resource.create({
    SERVICE_NAME: "order-service",
    "service.version": "1.2.3",
    "deployment.environment": "production",
})
sampler = TraceIdRatioBased(0.1)
provider = TracerProvider(resource=resource, sampler=sampler)
exporter = OTLPSpanExporter(
    endpoint="http://tempo:4317",
    insecure=True,
)
provider.add_span_processor(BatchSpanProcessor(exporter))
trace.set_tracer_provider(provider)

# Auto-instrumentation
FastAPIInstrumentor().instrument()
SQLAlchemyInstrumentor().instrument()
RedisInstrumentor().instrument()
HTTPXClientInstrumentor().instrument()

tracer = trace.get_tracer("order-service")
```

### With obskit: 3 lines

```python
from obskit.tracing import setup_tracing

setup_tracing(
    exporter_endpoint="http://tempo:4317",
    sample_rate=0.1,
    # auto-detects FastAPI, SQLAlchemy, Redis, httpx, etc.
)
```

---

## Installation

```bash
pip install "obskit[otlp]"

# For auto-instrumentation of specific frameworks:
pip install opentelemetry-instrumentation-fastapi
pip install opentelemetry-instrumentation-sqlalchemy
pip install opentelemetry-instrumentation-redis
pip install opentelemetry-instrumentation-httpx
```

---

## TracerProvider Setup → setup_tracing()

### Before

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

resource = Resource.create({SERVICE_NAME: "my-service"})
provider = TracerProvider(resource=resource)
provider.add_span_processor(
    BatchSpanProcessor(OTLPSpanExporter(endpoint="http://tempo:4317"))
)
trace.set_tracer_provider(provider)
```

### After

```python
from obskit.tracing import setup_tracing

setup_tracing(exporter_endpoint="http://tempo:4317")
```

You can still pass custom OTel resource attributes:

```python
setup_tracing(
    exporter_endpoint="http://tempo:4317",
    sample_rate=0.1,
    resource_attributes={
        "k8s.pod.name": os.environ.get("POD_NAME", "unknown"),
        "k8s.namespace.name": os.environ.get("K8S_NAMESPACE", "default"),
    },
)
```

---

## Manual Span Creation

### Before — tracer.start_as_current_span

```python
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

def process_order(order_id: str) -> None:
    with tracer.start_as_current_span(
        "process_order",
        attributes={"order.id": order_id, "order.service": "payment"},
    ) as span:
        result = charge_card(order_id)
        span.set_attribute("charge.status", result.status)
        if result.failed:
            span.set_status(trace.StatusCode.ERROR, result.error_message)
```

### After — trace_span

```python
from obskit.tracing import trace_span

def process_order(order_id: str) -> None:
    with trace_span(
        "process_order",
        attributes={"order.id": order_id, "order.service": "payment"},
    ) as span:
        result = charge_card(order_id)
        span.set_attribute("charge.status", result.status)
```

### Async spans

```python
from obskit.tracing import async_trace_span

async def fetch_inventory(sku: str) -> dict:
    async with async_trace_span("fetch_inventory", attributes={"sku": sku}):
        return await db.get_inventory(sku)
```

The `trace_span` and `async_trace_span` functions automatically:

- Set `error=true` and record the exception on the span when an exception propagates.
- Extract and propagate W3C TraceContext headers.
- Inject the `trace_id` into the current structlog context (trace-log correlation).

---

## Auto-Instrumentation

obskit auto-detects installed OTel instrumentation packages and applies them.

### Before — manual instrumentor registration

```python
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor

FastAPIInstrumentor().instrument(app=app)
SQLAlchemyInstrumentor().instrument()
RedisInstrumentor().instrument()
```

### After — automatic detection

```python
from obskit.tracing import setup_tracing

# setup_tracing detects and applies all installed instrumentors
setup_tracing(exporter_endpoint="http://tempo:4317")

# Or specify explicitly:
setup_tracing(
    exporter_endpoint="http://tempo:4317",
    instrument=["fastapi", "sqlalchemy", "redis"],
)
```

### Keeping your existing instrumentors

If you have custom instrumentor configuration, you can skip auto-detection and apply
instrumentors yourself after calling `setup_tracing()`:

```python
from obskit.tracing import setup_tracing
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

# Setup provider only, no auto-instrumentation
setup_tracing(exporter_endpoint="http://tempo:4317", instrument=[])

# Apply your instrumentors with custom config
FastAPIInstrumentor().instrument(
    app=app,
    excluded_urls="/health,/metrics",
    http_capture_headers_server_request=["X-Request-ID"],
)
```

---

## OTLP Exporter Configuration Migration

### Environment variables (no code change required)

```bash
# Before (raw OTel env vars still work)
export OTEL_EXPORTER_OTLP_ENDPOINT=http://tempo:4317
export OTEL_SERVICE_NAME=order-service
export OTEL_TRACES_SAMPLER=parentbased_traceidratio
export OTEL_TRACES_SAMPLER_ARG=0.1

# After (obskit env vars — preferred)
export OBSKIT_OTLP_ENDPOINT=http://tempo:4317
export OBSKIT_SERVICE_NAME=order-service
export OBSKIT_TRACE_SAMPLE_RATE=0.1
```

!!! note
    obskit reads **both** `OTEL_*` and `OBSKIT_*` environment variables.
    `OBSKIT_*` takes precedence when both are set.

---

## Trace-Log Correlation

One of obskit's biggest advantages over raw OTel is automatic trace-log correlation.
When `setup_tracing()` is called, obskit installs a structlog processor that injects
`trace_id` and `span_id` into every log record emitted during an active span.

### Before — manual correlation

```python
import structlog
from opentelemetry import trace

logger = structlog.get_logger()

def process_order(order_id: str) -> None:
    span = trace.get_current_span()
    ctx = span.get_span_context()
    log = logger.bind(
        trace_id=format(ctx.trace_id, "032x") if ctx.is_valid else None,
        span_id=format(ctx.span_id, "016x") if ctx.is_valid else None,
    )
    log.info("processing_order", order_id=order_id)
```

### After — automatic correlation

```python
from obskit.logging import get_logger

logger = get_logger(__name__)

def process_order(order_id: str) -> None:
    # trace_id and span_id are injected automatically
    logger.info("processing_order", order_id=order_id)
```

Output:

```json
{
  "event": "processing_order",
  "order_id": "ord-123",
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "span_id": "00f067aa0ba902b7",
  "level": "info",
  "timestamp": "2025-01-15T10:30:45.123456Z"
}
```

---

## W3C Baggage Propagation

obskit exposes a clean API for W3C Baggage, replacing verbose OTel SDK calls.

### Before

```python
from opentelemetry import baggage, context

ctx = baggage.set_baggage("tenant_id", "acme-corp")
context.attach(ctx)
tenant = baggage.get_baggage("tenant_id")
```

### After

```python
from obskit.tracing import set_baggage, get_baggage, clear_baggage

set_baggage("tenant_id", "acme-corp")
tenant = get_baggage("tenant_id")   # "acme-corp"
clear_baggage("tenant_id")
```

---

## Shutdown

```python
# Before
from opentelemetry.sdk.trace import TracerProvider
provider: TracerProvider = trace.get_tracer_provider()
provider.shutdown()

# After
from obskit.tracing import shutdown_tracing
shutdown_tracing()
```

---

## Migration Checklist

- [ ] Install `obskit-tracing` and remove manual OTel setup code
- [ ] Replace `TracerProvider` boilerplate with `setup_tracing()`
- [ ] Replace `tracer.start_as_current_span()` with `trace_span()` / `async_trace_span()`
- [ ] Remove manual instrumentor calls (or keep them with `instrument=[]`)
- [ ] Switch from `OTEL_*` env vars to `OBSKIT_*` (or keep both — both are read)
- [ ] Replace manual trace-log correlation with `get_logger()` from obskit-logging
- [ ] Replace `baggage.set_baggage()` with `set_baggage()` from obskit-tracing
- [ ] Replace `provider.shutdown()` with `shutdown_tracing()`
- [ ] Verify spans appear in your tracing backend (Grafana Tempo, Jaeger, etc.)
