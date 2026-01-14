# Obskit Quick Reference Guide

Quick reference for common patterns and use cases.

## Installation

```bash
# Basic installation
pip install obskit

# With tracing (OpenTelemetry)
pip install obskit[tracing]

# With metrics (Prometheus)
pip install obskit[metrics]

# Everything
pip install obskit[all]
```

## Configuration

```python
from obskit import configure

# Basic
configure(service_name="my-service", environment="production")

# Full
configure(
    service_name="my-service",
    environment="production",
    log_level="INFO",
    tracing_enabled=True,
    metrics_enabled=True,
    metrics_port=9090
)
```

## Logging

```python
from obskit import get_logger

logger = get_logger("module_name")

# Log levels
logger.debug("debug_message", key="value")
logger.info("info_message", key="value")
logger.warning("warning_message", key="value")
logger.error("error_message", error="details")
logger.exception("exception_occurred")  # Includes stack trace
```

## Metrics - RED Method

```python
from obskit.metrics import REDMetrics

metrics = REDMetrics("service_name")

# Automatic tracking
with metrics.track_request(operation="operation_name"):
    do_work()

# Manual tracking
metrics.request_count.labels(operation="op", status="success").inc()
metrics.error_count.labels(operation="op", error_type="Error").inc()
metrics.request_duration_histogram.labels(operation="op").observe(0.5)
```

## Metrics - Golden Signals

```python
from obskit.metrics import GoldenSignals

signals = GoldenSignals("service_name")

# Track all four signals
signals.request_count.labels(operation="op", status="success").inc()
signals.error_count.labels(operation="op", error_type="Error").inc()
signals.saturation.labels(resource="cpu").set(0.85)
signals.queue_depth.labels(operation="op").set(5)
```

## Metrics - USE Method

```python
from obskit.metrics import USEMetrics

metrics = USEMetrics("resource_name")

# Track utilization, saturation, errors
metrics.set_utilization("cpu", 0.75)
metrics.set_saturation("memory", 0.5)
metrics.inc_error("disk", "read_error")
```

## Decorators

```python
from obskit.decorators import with_observability

# Sync function
@with_observability(component="ServiceName")
def sync_function():
    return process()

# Async function
@with_observability(component="ServiceName")
async def async_function():
    return await process()
```

## Circuit Breaker

```python
from obskit.resilience import CircuitBreaker

breaker = CircuitBreaker("service_name", failure_threshold=5)

# Async context manager
async with breaker:
    result = await call_service()

# Decorator
@breaker
async def call_service():
    return await service.call()
```

## Retry

```python
from obskit.resilience import retry

# Basic
@retry(max_attempts=3)
async def fetch():
    return await http.get()

# Advanced
@retry(
    max_attempts=5,
    base_delay=0.1,
    max_delay=10.0,
    exponential_base=2.0,
    jitter=True,
    retry_on=(ConnectionError, TimeoutError)
)
async def fetch():
    return await http.get()
```

## Rate Limiting

```python
from obskit.resilience import RateLimiter

limiter = RateLimiter(requests=100, window_seconds=60)

# Acquire
if await limiter.acquire():
    process()

# Context manager
async with limiter:
    process()
```

## Health Checks

```python
from obskit.health import HealthChecker

checker = HealthChecker()

# Add checks
@checker.add_readiness_check("database")
def check_db():
    return db.is_connected()

@checker.add_liveness_check("service")
def check_alive():
    return {"healthy": True}

# Check health
result = await checker.check_health()
```

## SLO Tracking

```python
from obskit.slo import track_slo, SLOType

# Decorator
@track_slo(
    name="api_availability",
    slo_type=SLOType.AVAILABILITY,
    target_value=0.999
)
async def handle_request():
    return await process()

# Manual
from obskit.slo import SLOTracker

tracker = SLOTracker()
tracker.register_slo(
    name="api_availability",
    slo_type=SLOType.AVAILABILITY,
    target_value=0.999
)
tracker.record_measurement("api_availability", 1.0, True)
```

## Correlation IDs

```python
from obskit.core.context import correlation_context, get_correlation_id

# Set correlation ID
with correlation_context("req-123"):
    corr_id = get_correlation_id()
    # All logs include correlation_id

# In async
async def process():
    corr_id = get_correlation_id()
    # Use in downstream calls
```

## Tracing

```python
from obskit.tracing import trace_span, inject_trace_context

# Create span
with trace_span("operation_name"):
    process()

# Inject for propagation
headers = {}
inject_trace_context(headers)
# Send headers to downstream service
```

## FastAPI Integration

```python
from fastapi import FastAPI, Request
from obskit import configure, get_logger
from obskit.decorators import with_observability
from obskit.core.context import correlation_context
import uuid

app = FastAPI()
configure(service_name="api-service")
logger = get_logger("api")

@app.middleware("http")
async def add_correlation_id(request: Request, call_next):
    corr_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
    with correlation_context(corr_id):
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = corr_id
        return response

@app.get("/users/{user_id}")
@with_observability(component="UserAPI")
async def get_user(user_id: str):
    return {"id": user_id}
```

## Prometheus Metrics

```python
from obskit.metrics import start_http_server

# Start metrics server
start_http_server(port=9090)

# Metrics available at http://localhost:9090/metrics
```

## Common Patterns

### Pattern 1: Request Handler

```python
@with_observability(component="API")
async def handle_request(request):
    logger.info("request_received", request_id=request.id)
    try:
        result = await process(request)
        logger.info("request_completed", request_id=request.id)
        return result
    except Exception as e:
        logger.error("request_failed", request_id=request.id, error=str(e))
        raise
```

### Pattern 2: External Service Call

```python
breaker = CircuitBreaker("external_api")

@retry(max_attempts=3)
async def call_external():
    async with breaker:
        return await http_client.get("https://api.example.com")
```

### Pattern 3: Database Operation

```python
metrics = REDMetrics("database")

async def query_db(query):
    with metrics.track_request(operation="query"):
        return await db.execute(query)
```

### Pattern 4: Background Job

```python
@with_observability(component="Worker")
async def background_job():
    logger.info("job_started")
    try:
        await process_job()
        logger.info("job_completed")
    except Exception as e:
        logger.error("job_failed", error=str(e))
        raise
```

### Pattern 5: Batch Processing

```python
limiter = RateLimiter(requests=10, window_seconds=1)

async def process_batch(items):
    results = []
    for item in items:
        await limiter.acquire()
        result = await process_item(item)
        results.append(result)
    return results
```

## Environment Variables

```bash
# Service configuration
export OBSKIT_SERVICE_NAME="my-service"
export OBSKIT_ENVIRONMENT="production"

# Logging
export OBSKIT_LOG_LEVEL="INFO"
export OBSKIT_LOG_FORMAT="json"

# Tracing
export OBSKIT_TRACING_ENABLED="true"
export OBSKIT_OTLP_ENDPOINT="http://localhost:4317"

# Metrics
export OBSKIT_METRICS_ENABLED="true"
export OBSKIT_METRICS_PORT="9090"
export OBSKIT_METRICS_METHOD="red"
```

## Best Practices

1. **Always use correlation IDs** for request tracking
2. **Use decorators** for automatic observability
3. **Track metrics** for all external calls
4. **Use circuit breakers** for external services
5. **Implement health checks** for all dependencies
6. **Track SLOs** for critical operations
7. **Use structured logging** with context
8. **Avoid high cardinality** in metrics labels
9. **Sample traces** in high-volume scenarios
10. **Monitor error budgets** and set up alerts

## Troubleshooting

### Metrics not appearing
- Check if `prometheus_client` is installed: `pip install obskit[metrics]`
- Verify metrics server is running: `start_http_server()`
- Check Prometheus configuration

### Tracing not working
- Check if OpenTelemetry is installed: `pip install obskit[tracing]`
- Verify OTLP endpoint is accessible
- Check tracing is enabled: `configure(tracing_enabled=True)`

### Logs not structured
- Ensure `structlog` is installed (included by default)
- Check log format: `configure(log_format="json")`
- Verify log level: `configure(log_level="DEBUG")`

