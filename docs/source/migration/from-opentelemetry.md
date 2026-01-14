# Migrating from OpenTelemetry

This guide shows how to migrate from raw OpenTelemetry SDK to obskit.

## Before: Raw OpenTelemetry

```python
# tracing.py
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.instrumentation.requests import RequestsInstrumentor

# Configure provider
resource = Resource(attributes={
    SERVICE_NAME: "my-service",
    "service.version": "1.0.0",
    "deployment.environment": "production",
})

provider = TracerProvider(resource=resource)
processor = BatchSpanProcessor(OTLPSpanExporter(endpoint="http://collector:4317"))
provider.add_span_processor(processor)
trace.set_tracer_provider(provider)

# Get tracer
tracer = trace.get_tracer(__name__)

# Instrument libraries
RequestsInstrumentor().instrument()

# In your application
def process_order(order_id):
    with tracer.start_as_current_span("process_order") as span:
        span.set_attribute("order.id", order_id)
        
        with tracer.start_as_current_span("validate"):
            validate_order(order_id)
        
        with tracer.start_as_current_span("charge"):
            charge_payment(order_id)
```

## After: obskit

```python
# main.py
from obskit import configure
from obskit.tracing import get_tracer, trace_context

# One-time configuration
configure(
    service_name="my-service",
    version="1.0.0",
    environment="production",
    otlp_endpoint="http://collector:4317",
)

# Get tracer
tracer = get_tracer()

# In your application
def process_order(order_id):
    with trace_context({"order.id": order_id}):
        with tracer.start_span("process_order"):
            validate_order(order_id)
            charge_payment(order_id)
```

## Step-by-Step Migration

### Step 1: Install obskit

```bash
pip install obskit[tracing]
```

### Step 2: Replace configuration

**Before:**
```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource, SERVICE_NAME

resource = Resource(attributes={
    SERVICE_NAME: "my-service",
    "service.version": "1.0.0",
})
provider = TracerProvider(resource=resource)
processor = BatchSpanProcessor(OTLPSpanExporter(endpoint="http://collector:4317"))
provider.add_span_processor(processor)
trace.set_tracer_provider(provider)
```

**After:**
```python
from obskit import configure

configure(
    service_name="my-service",
    version="1.0.0",
    otlp_endpoint="http://collector:4317",
)
```

### Step 3: Update tracer usage

**Before:**
```python
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

with tracer.start_as_current_span("operation") as span:
    span.set_attribute("key", "value")
    do_work()
```

**After:**
```python
from obskit.tracing import get_tracer

tracer = get_tracer()

with tracer.start_span("operation", attributes={"key": "value"}):
    do_work()
```

### Step 4: Update context propagation

**Before:**
```python
from opentelemetry.propagate import inject, extract
from opentelemetry import context

# Inject context into headers
headers = {}
inject(headers)

# Extract context from headers
ctx = extract(carrier=request.headers)
token = context.attach(ctx)
try:
    process_request()
finally:
    context.detach(token)
```

**After:**
```python
from obskit.tracing import inject_trace_context, extract_trace_context, trace_context

# Inject context
headers = {}
inject_trace_context(headers)

# Extract and use context
trace_ctx = extract_trace_context(request.headers)
with trace_context(trace_ctx):
    process_request()
```

### Step 5: Use middleware for automatic tracing

**Before:**
```python
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

app = FastAPI()
FastAPIInstrumentor.instrument_app(app)
```

**After:**
```python
from fastapi import FastAPI
from obskit.middleware import ObskitMiddleware

app = FastAPI()
app.add_middleware(ObskitMiddleware)
```

## Feature Mapping

| OpenTelemetry | obskit |
|--------------|--------|
| `TracerProvider` | `configure(otlp_endpoint=...)` |
| `trace.get_tracer()` | `get_tracer()` |
| `start_as_current_span()` | `tracer.start_span()` |
| `span.set_attribute()` | Attributes in `start_span()` |
| `inject()/extract()` | `inject_trace_context()/extract_trace_context()` |
| `FastAPIInstrumentor` | `ObskitMiddleware` |

## Benefits After Migration

1. **Unified configuration**: Tracing, metrics, and logging in one place
2. **Automatic correlation**: Trace IDs in logs and metrics
3. **Less boilerplate**: No manual provider setup
4. **Consistent patterns**: Same API across all telemetry types
5. **Built-in sampling**: Configurable trace sampling

## Keeping OpenTelemetry Access

obskit wraps OpenTelemetry, so you can still access it:

```python
from obskit import configure
from opentelemetry import trace

configure(service_name="my-service", otlp_endpoint="...")

# Access underlying OTel tracer
otel_tracer = trace.get_tracer("my-module")

# Mix obskit and OTel
from obskit.tracing import get_tracer
obskit_tracer = get_tracer()
```

## Sampling Configuration

**Before:**
```python
from opentelemetry.sdk.trace.sampling import TraceIdRatioBased

provider = TracerProvider(
    sampler=TraceIdRatioBased(0.1)  # 10% sampling
)
```

**After:**
```python
from obskit import configure

configure(
    service_name="my-service",
    trace_sampling_rate=0.1,  # 10% sampling
)
```

