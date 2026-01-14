# Troubleshooting Guide

Solutions to common issues when using obskit.

## Metrics Issues

### Metrics Not Appearing

**Symptom**: `/metrics` endpoint returns nothing or missing metrics.

**Causes & Solutions**:

1. **Metrics server not started**
   ```python
   # Make sure to start the server
   from obskit import start_http_server
   start_http_server(port=9090)
   ```

2. **Wrong port**
   ```bash
   # Check which port is configured
   curl http://localhost:9090/metrics  # Default
   curl http://localhost:8080/metrics  # If changed
   ```

3. **Metrics not recorded**
   ```python
   # Ensure you're using the metrics
   metrics = get_red_metrics(service_name="my-service")
   
   with metrics.track_request(endpoint="/api", method="GET"):
       # Your code
       pass
   ```

### High Cardinality Warnings

**Symptom**: Prometheus memory usage growing, queries slow.

**Cause**: Too many unique label combinations.

**Solution**: Normalize labels
```python
# Bad: unbounded cardinality
metrics.track_request(endpoint=f"/users/{user_id}")

# Good: bounded cardinality
metrics.track_request(endpoint="/users/{id}")
```

### Duplicate Metrics Error

**Symptom**: `ValueError: Duplicated timeseries`

**Cause**: Creating metrics with same name but different labels.

**Solution**: Use singleton pattern
```python
# Bad: creates new metrics each time
def handle_request():
    metrics = get_red_metrics(service_name="api")

# Good: create once, reuse
metrics = get_red_metrics(service_name="api")

def handle_request():
    with metrics.track_request(...):
        pass
```

## Tracing Issues

### Traces Not Appearing in Jaeger

**Symptom**: No traces in Jaeger UI.

**Causes & Solutions**:

1. **OTLP endpoint not configured**
   ```python
   configure_tracing(
       service_name="my-service",
       otlp_endpoint="http://jaeger:4317",  # Must be set!
   )
   ```

2. **Sampling set to 0**
   ```python
   configure_tracing(
       service_name="my-service",
       sample_rate=1.0,  # 1.0 = 100%, not 0
   )
   ```

3. **Network connectivity**
   ```bash
   # Check collector is reachable
   curl http://jaeger:4317/health
   ```

### Traces Missing Parent Context

**Symptom**: Traces are disconnected, each service shows separate traces.

**Cause**: Context not propagated between services.

**Solution**: Inject/extract trace context
```python
# When calling another service
headers = {}
inject_trace_context(headers)
response = httpx.get(url, headers=headers)

# When receiving a request
ctx = extract_trace_context(request.headers)
with trace_context(ctx):
    process_request()
```

### High Trace Export Latency

**Symptom**: Service slowing down when tracing enabled.

**Solution**: Enable batching and rate limiting
```python
configure_tracing(
    service_name="my-service",
    otlp_endpoint="http://jaeger:4317",
    batch_export=True,
    rate_limit=1000,  # Max traces/second
)
```

## Logging Issues

### Logs Not Appearing

**Symptom**: No log output.

**Causes & Solutions**:

1. **Log level too high**
   ```python
   configure_logging(
       service_name="my-service",
       log_level="DEBUG",  # Lower for more output
   )
   ```

2. **Sampling filtering out logs**
   ```python
   configure_logging(
       service_name="my-service",
       sample_rate=1.0,  # 1.0 = all logs
   )
   ```

### Missing Correlation IDs

**Symptom**: Logs don't have correlation_id field.

**Solution**: Set correlation ID in middleware
```python
from obskit.core import set_correlation_id

@app.middleware("http")
async def correlation_middleware(request, call_next):
    correlation_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    set_correlation_id(correlation_id)
    return await call_next(request)
```

### PII Still Appearing in Logs

**Symptom**: Sensitive data in logs despite redaction enabled.

**Solutions**:

1. **Enable redaction**
   ```python
   configure_logging(
       service_name="my-service",
       pii_redaction=True,  # Must be enabled
   )
   ```

2. **Add custom patterns**
   ```python
   from obskit.compliance import PIIRedactor, PIIPattern
   
   redactor = PIIRedactor(
       patterns=[
           PIIPattern("custom", r"YOUR-PATTERN", "[REDACTED]"),
       ],
   )
   ```

## Health Check Issues

### Readiness Always Failing

**Symptom**: Pod never becomes ready, constant restarts.

**Causes & Solutions**:

1. **Check function failing**
   ```python
   # Add logging to debug
   async def check_database():
       try:
           await db.execute("SELECT 1")
           return True
       except Exception as e:
           logger.error("DB check failed", error=str(e))
           return False
   ```

2. **Timeout too short**
   ```yaml
   # Kubernetes manifest
   readinessProbe:
     httpGet:
       path: /ready
       port: 8000
     timeoutSeconds: 10  # Increase if checks are slow
   ```

3. **Dependency not ready**
   ```yaml
   # Add init container to wait for dependency
   initContainers:
     - name: wait-for-db
       image: busybox
       command: ['sh', '-c', 'until nc -z postgres 5432; do sleep 1; done']
   ```

### Liveness Probe Restarting Container

**Symptom**: Container keeps restarting.

**Causes**:

1. **Liveness check too complex** - Keep liveness simple
   ```python
   # Good: simple check
   health.add_liveness_check("alive", lambda: True)
   
   # Bad: complex check that might hang
   health.add_liveness_check("db", check_database)  # Use readiness instead
   ```

2. **Insufficient delay**
   ```yaml
   livenessProbe:
     initialDelaySeconds: 30  # Give app time to start
   ```

## Resilience Issues

### Circuit Breaker Always Open

**Symptom**: Circuit breaker never closes.

**Cause**: Half-open requests still failing.

**Solution**: Check underlying service
```python
# Add logging to debug
breaker = CircuitBreaker(
    failure_threshold=5,
    recovery_timeout=30.0,
    on_open=lambda: logger.warning("Circuit opened"),
    on_close=lambda: logger.info("Circuit closed"),
    on_half_open=lambda: logger.info("Circuit half-open"),
)
```

### Retry Exhausting Resources

**Symptom**: Too many retries causing load spikes.

**Solution**: Add jitter and circuit breaker
```python
@retry_async(
    max_attempts=3,
    base_delay=1.0,
    max_delay=30.0,
    jitter=0.5,  # Add randomness
    exclude=(CircuitBreakerOpen,),  # Don't retry when circuit open
)
async def call_api():
    async with breaker:
        return await make_request()
```

## Performance Issues

### High Memory Usage

**Causes & Solutions**:

1. **Too many metrics**
   ```python
   # Limit cardinality
   metrics.track_request(endpoint=normalize_path(path))
   ```

2. **Too many traces**
   ```python
   configure_tracing(sample_rate=0.1)  # 10% sampling
   ```

3. **Large log messages**
   ```python
   # Avoid logging large objects
   logger.info("Processed", item_count=len(items))  # Not items=items
   ```

### Slow Request Processing

**Cause**: Synchronous metric/trace operations.

**Solution**: Use async recording
```python
from obskit.metrics import AsyncREDMetrics

metrics = AsyncREDMetrics(service_name="api")
```

## Debugging Tips

### Enable Debug Mode

```python
from obskit.config import ObskitSettings

settings = ObskitSettings(debug=True)
```

### Check Configuration

```python
from obskit import get_settings

settings = get_settings()
print(f"Service: {settings.service_name}")
print(f"Log level: {settings.log_level}")
print(f"OTLP endpoint: {settings.otlp_endpoint}")
```

### Verify Metrics Registration

```python
from obskit.metrics import get_registry
from prometheus_client import generate_latest

registry = get_registry()
print(generate_latest(registry).decode())
```

## Getting Help

If you can't resolve an issue:

1. **Check the logs** with DEBUG level
2. **Search existing issues** on GitHub
3. **Create a new issue** with:
   - obskit version
   - Python version
   - Minimal reproduction code
   - Full error traceback

## Next Steps

- **[Configuration](../config/index.md)** - All configuration options
- **[Examples](../examples/fastapi.md)** - Working examples
- **[API Reference](../api/index.rst)** - Detailed documentation

