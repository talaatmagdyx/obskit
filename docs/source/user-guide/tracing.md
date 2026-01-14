# Distributed Tracing Guide

Distributed tracing helps you understand request flow across services.
obskit uses OpenTelemetry for standards-compliant tracing.

## Why Tracing?

In a microservices architecture, a single request might touch many services:

```{mermaid}
sequenceDiagram
    participant User
    participant Gateway
    participant Auth
    participant API
    participant Database
    
    User->>Gateway: Request
    Gateway->>Auth: Validate token
    Auth-->>Gateway: Valid
    Gateway->>API: Forward request
    API->>Database: Query
    Database-->>API: Results
    API-->>Gateway: Response
    Gateway-->>User: Response
```

Without tracing, debugging is guesswork. With tracing, you see exactly where time is spent.

## Basic Setup

```python
from obskit import configure_tracing

# Configure OpenTelemetry tracing
tracer = configure_tracing(
    service_name="user-service",
    otlp_endpoint="http://jaeger:4317",  # Or your OTLP collector
)
```

### Environment Variables

Configure via environment variables:

```bash
export OBSKIT_SERVICE_NAME="user-service"
export OBSKIT_OTLP_ENDPOINT="http://jaeger:4317"
export OBSKIT_TRACE_SAMPLE_RATE="1.0"  # 100% sampling
```

## Creating Spans

### Manual Spans

```python
from obskit import get_tracer

tracer = get_tracer()

def process_order(order_id: str):
    with tracer.start_as_current_span("process_order") as span:
        span.set_attribute("order.id", order_id)
        
        # Child span
        with tracer.start_as_current_span("validate_order"):
            validate(order_id)
        
        with tracer.start_as_current_span("charge_payment"):
            charge(order_id)
```

### Decorator

```python
from obskit.tracing import traced

@traced(name="process_order")
def process_order(order_id: str):
    # Automatically creates a span
    validate(order_id)
    charge(order_id)

@traced(name="fetch_user", attributes={"component": "database"})
async def fetch_user(user_id: str):
    return await db.users.find_one({"_id": user_id})
```

## Context Propagation

### Automatic Propagation

When using HTTP clients, context propagates automatically:

```python
import httpx
from obskit.tracing import inject_trace_context

async def call_service():
    headers = {}
    inject_trace_context(headers)
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "http://other-service/api",
            headers=headers,
        )
```

### Extracting Context

In your service, extract the trace context:

```python
from obskit.tracing import extract_trace_context, trace_context

def handle_request(request):
    # Extract trace context from incoming headers
    ctx = extract_trace_context(dict(request.headers))
    
    with trace_context(ctx):
        # All spans created here are part of the same trace
        process_request()
```

### FastAPI Middleware

With the middleware, context is handled automatically:

```python
from fastapi import FastAPI
from obskit.middleware import ObskitMiddleware

app = FastAPI()
app.add_middleware(ObskitMiddleware)

@app.get("/users/{user_id}")
async def get_user(user_id: str):
    # Trace context is already set by middleware
    return await fetch_user(user_id)
```

## Span Attributes

Add meaningful attributes to spans:

```python
with tracer.start_as_current_span("database_query") as span:
    span.set_attribute("db.system", "postgresql")
    span.set_attribute("db.name", "users")
    span.set_attribute("db.operation", "SELECT")
    span.set_attribute("db.statement", "SELECT * FROM users WHERE id = ?")
    
    result = db.execute(query)
    span.set_attribute("db.rows_affected", len(result))
```

### Standard Attributes

Use OpenTelemetry semantic conventions:

| Attribute | Description |
|-----------|-------------|
| `http.method` | HTTP method |
| `http.url` | Full URL |
| `http.status_code` | Response status code |
| `db.system` | Database type |
| `db.operation` | Query type (SELECT, INSERT) |
| `messaging.system` | Message broker type |
| `rpc.service` | RPC service name |

## Error Recording

```python
with tracer.start_as_current_span("risky_operation") as span:
    try:
        result = risky_operation()
    except Exception as e:
        span.set_status(Status(StatusCode.ERROR, str(e)))
        span.record_exception(e)
        raise
```

## Sampling

Control trace sampling to manage volume:

### Head-Based Sampling

```python
from obskit import configure_tracing

# Sample 10% of traces
configure_tracing(
    service_name="high-traffic-service",
    sample_rate=0.1,
)
```

### Conditional Sampling

```python
from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased

# Sample 1% of normal traffic, but always sample errors
configure_tracing(
    service_name="api",
    sampler=ParentBased(root=TraceIdRatioBased(0.01)),
)
```

## Backends

### Jaeger

```python
configure_tracing(
    service_name="my-service",
    otlp_endpoint="http://jaeger:4317",
)
```

### Zipkin

```python
# Jaeger can receive Zipkin format
configure_tracing(
    service_name="my-service",
    otlp_endpoint="http://zipkin:9411/api/v2/spans",
)
```

### AWS X-Ray

```python
# Use OTLP with AWS Distro for OpenTelemetry
configure_tracing(
    service_name="my-service",
    otlp_endpoint="http://aws-otel-collector:4317",
)
```

## Best Practices

### 1. Name Spans Meaningfully

```python
# Good: describes the operation
with tracer.start_as_current_span("fetch_user_orders"):
    ...

# Bad: too generic
with tracer.start_as_current_span("query"):
    ...
```

### 2. Keep Spans Focused

```python
# Good: one span per logical operation
with tracer.start_as_current_span("validate_token"):
    validate()

with tracer.start_as_current_span("fetch_user"):
    fetch()

# Bad: one giant span
with tracer.start_as_current_span("handle_request"):
    validate()
    fetch()
    process()
    respond()
```

### 3. Add Business Context

```python
span.set_attribute("user.id", user_id)
span.set_attribute("order.total", order.total)
span.set_attribute("feature.flag", "new_checkout")
```

### 4. Handle Sensitive Data

```python
from obskit.compliance import redact_pii

# Don't log sensitive data in spans
span.set_attribute("user.email", redact_pii(email))
```

## Troubleshooting

### No Traces Appearing

1. Check OTLP endpoint connectivity
2. Verify sampling isn't set to 0
3. Check collector logs for errors

### Missing Context

1. Ensure headers are propagated between services
2. Check middleware is installed
3. Verify trace context extraction

### High Cardinality

1. Don't use user IDs as span names
2. Normalize URLs before using as attributes
3. Use bounded attribute values

## Next Steps

- **[Logging Guide](logging.md)** - Correlate logs with traces
- **[Metrics Guide](metrics.md)** - Complete the observability picture
- **[Examples](../examples/fastapi.md)** - Full working examples

