# Structured Logging Guide

obskit provides structured logging with automatic context propagation,
correlation IDs, and optional PII redaction.

## Why Structured Logging?

Traditional logs are hard to search and analyze:

```
ERROR 2024-01-15 10:23:45 Something went wrong processing request
```

Structured logs are machine-readable:

```json
{
  "timestamp": "2024-01-15T10:23:45.123Z",
  "level": "error",
  "message": "Payment processing failed",
  "service": "payment-service",
  "trace_id": "abc123",
  "user_id": "user_456",
  "order_id": "ord_789",
  "error_code": "CARD_DECLINED"
}
```

Now you can:
- Search for all errors for a specific user
- Find all requests with a trace ID
- Aggregate error types

## Basic Setup

```python
from obskit import configure_logging

# Configure structured logging
logger = configure_logging(
    service_name="user-service",
    log_level="INFO",
)

# Use the logger
logger.info("User logged in", user_id="user_123")
logger.warning("Rate limit approaching", current=95, limit=100)
logger.error("Database connection failed", error="Connection timeout")
```

### Output

```json
{"timestamp": "2024-01-15T10:23:45.123Z", "level": "info", "event": "User logged in", "service": "user-service", "user_id": "user_123"}
{"timestamp": "2024-01-15T10:23:46.456Z", "level": "warning", "event": "Rate limit approaching", "service": "user-service", "current": 95, "limit": 100}
{"timestamp": "2024-01-15T10:23:47.789Z", "level": "error", "event": "Database connection failed", "service": "user-service", "error": "Connection timeout"}
```

## Log Levels

| Level | When to Use |
|-------|-------------|
| `DEBUG` | Detailed diagnostic info (development only) |
| `INFO` | Routine operations (request received, task completed) |
| `WARNING` | Something unexpected but handled |
| `ERROR` | Operation failed but service continues |
| `CRITICAL` | Service cannot continue |

```python
logger.debug("Query plan generated", plan=query_plan)
logger.info("Order created", order_id=order.id)
logger.warning("Retry attempt", attempt=3, max_attempts=5)
logger.error("Payment failed", order_id=order.id, error=str(e))
logger.critical("Database unavailable", retries_exhausted=True)
```

## Context Binding

Add context that persists across log calls:

```python
# Bind context for all subsequent logs
request_logger = logger.bind(
    request_id="req_abc123",
    user_id="user_456",
)

request_logger.info("Processing request")
# {"request_id": "req_abc123", "user_id": "user_456", "event": "Processing request"}

request_logger.info("Request completed")
# {"request_id": "req_abc123", "user_id": "user_456", "event": "Request completed"}
```

### Request Context

```python
from obskit.core import set_correlation_id, get_correlation_id

def handle_request(request):
    # Set correlation ID from header or generate new
    correlation_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    set_correlation_id(correlation_id)
    
    # All logs automatically include correlation_id
    logger.info("Request started")  
    # {"correlation_id": "abc123", "event": "Request started"}
```

## Trace Correlation

Logs automatically include trace context when tracing is configured:

```python
from obskit import configure_logging, configure_tracing

configure_tracing(service_name="api")
logger = configure_logging(service_name="api")

with tracer.start_as_current_span("process_order"):
    logger.info("Processing order", order_id="ord_123")
    # {"trace_id": "abc...", "span_id": "def...", "event": "Processing order"}
```

This enables clicking from a log line directly to the trace in Jaeger/Zipkin.

## Exception Logging

```python
try:
    process_payment()
except PaymentError as e:
    logger.exception(
        "Payment processing failed",
        order_id=order.id,
        amount=order.total,
    )
    # Automatically includes stack trace
```

### Output

```json
{
  "level": "error",
  "event": "Payment processing failed",
  "order_id": "ord_123",
  "amount": 99.99,
  "exception": "PaymentError: Card declined",
  "traceback": "Traceback (most recent call last):\n  File..."
}
```

## Dynamic Log Level

Change log level at runtime without restart:

```python
from obskit.logging import set_log_level, get_log_level

# Check current level
current = get_log_level()  # "INFO"

# Temporarily increase verbosity for debugging
set_log_level("DEBUG")

# ... debug the issue ...

# Restore normal level
set_log_level("INFO")
```

### Via API Endpoint

```python
from fastapi import FastAPI
from obskit.logging import set_log_level

app = FastAPI()

@app.post("/admin/log-level")
def update_log_level(level: str):
    set_log_level(level)
    return {"status": "ok", "level": level}
```

## Log Sampling

For high-volume services, sample logs:

```python
configure_logging(
    service_name="high-traffic-api",
    sample_rate=0.1,  # Log 10% of INFO messages
)
```

Errors are never sampled - they're always logged.

## Output Formats

### JSON (Production)

```python
configure_logging(
    service_name="api",
    format="json",
)
```

### Console (Development)

```python
configure_logging(
    service_name="api",
    format="console",
)
```

Output:
```
2024-01-15 10:23:45 [info     ] User logged in                 service=api user_id=user_123
```

## Integration with Log Aggregators

### ELK Stack

```python
# Logs are JSON, ready for Filebeat/Logstash
configure_logging(service_name="api", format="json")
```

### Datadog

```python
configure_logging(
    service_name="api",
    format="json",
    extra_processors=[datadog_processor],
)
```

### CloudWatch

```python
# JSON logs work with CloudWatch Logs Insights
configure_logging(service_name="api", format="json")
```

## Best Practices

### 1. Use Structured Fields, Not String Interpolation

```python
# Good: structured field
logger.info("User created", user_id=user.id, email=user.email)

# Bad: string interpolation
logger.info(f"User created: {user.id}, {user.email}")
```

### 2. Log at Appropriate Levels

```python
# Good: INFO for business events
logger.info("Order placed", order_id=order.id)

# Bad: DEBUG for production events
logger.debug("Order placed", order_id=order.id)  # Won't see in prod
```

### 3. Include Context, Not Just Messages

```python
# Good: actionable context
logger.error(
    "Payment failed",
    order_id=order.id,
    user_id=user.id,
    error_code=e.code,
    retry_count=attempt,
)

# Bad: just message
logger.error("Payment failed")
```

### 4. Don't Log Sensitive Data

```python
# Good: redact sensitive data
from obskit.compliance import redact_pii
logger.info("User registered", email=redact_pii(user.email))

# Bad: logging raw PII
logger.info("User registered", email=user.email)  # GDPR violation
```

## Troubleshooting

### Logs Not Appearing

1. Check log level configuration
2. Verify logging is configured before use
3. Check output destination

### Missing Context

1. Ensure correlation ID is set
2. Verify context binding is in scope
3. Check middleware is installed

### Performance Issues

1. Enable log sampling
2. Reduce DEBUG logging in production
3. Use async log handlers for high volume

## Next Steps

- **[PII Redaction](pii.md)** - Protect sensitive data in logs
- **[Tracing Guide](tracing.md)** - Correlate logs with traces
- **[Troubleshooting](../troubleshooting/index.md)** - Common issues and solutions

