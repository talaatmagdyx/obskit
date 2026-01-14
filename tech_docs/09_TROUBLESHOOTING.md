# Troubleshooting Guide

Common issues and solutions for obskit in production.

---

## Quick Diagnostics

```python
from obskit import get_settings, validate_config
from obskit.metrics.self_metrics import get_self_metrics

# Check configuration
settings = get_settings()
print(f"Service: {settings.service_name}")
print(f"Environment: {settings.environment}")
print(f"Metrics enabled: {settings.metrics_enabled}")
print(f"Auth enabled: {settings.metrics_auth_enabled}")

# Validate configuration
is_valid, errors = validate_config()
if not is_valid:
    for error in errors:
        print(f"Error: {error}")

# Check self-metrics
metrics = get_self_metrics()
snapshot = metrics.get_snapshot()
print(f"Queue depth: {snapshot.queue_depth}")
print(f"Dropped metrics: {snapshot.dropped_total}")
```

---

## Metrics Issues

### Metrics Not Appearing

**Symptom:** `/metrics` endpoint returns empty or 404

**Solutions:**

1. **Check metrics server is started:**
```python
from obskit.metrics import start_http_server
start_http_server(port=9090)  # Must call this!
```

2. **Check metrics are enabled:**
```python
configure(metrics_enabled=True)
```

3. **Verify port is accessible:**
```bash
curl http://localhost:9090/metrics
# Or with auth
curl -H "Authorization: Bearer $TOKEN" http://localhost:9090/metrics
```

### 401 Unauthorized on Metrics

**Symptom:** Metrics endpoint returns 401

**Solution:** Provide correct bearer token:
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:9090/metrics
```

Or check token configuration:
```python
settings = get_settings()
print(f"Auth enabled: {settings.metrics_auth_enabled}")
print(f"Token set: {bool(settings.metrics_auth_token)}")
```

### 429 Too Many Requests

**Symptom:** Metrics endpoint returns 429

**Solution:** Rate limiting is enabled. Wait and retry, or increase limit:
```python
configure(
    metrics_rate_limit_enabled=True,
    metrics_rate_limit_requests=120,  # Increase limit
)
```

### High Cardinality Warning

**Symptom:** Prometheus warns about high cardinality

**Solution:** Check for dynamic labels:
```python
# ❌ BAD - Creates unbounded labels
red.observe_request(operation=f"user_{user_id}")

# ✅ GOOD - Fixed label set
red.observe_request(operation="get_user")
```

### Metrics Dropped

**Symptom:** `obskit_metrics_dropped_total` increasing

**Solutions:**

1. **Increase queue size:**
```python
configure(async_metric_queue_size=50000)
```

2. **Enable sampling:**
```python
configure(metrics_sample_rate=0.1)  # Sample 10%
```

3. **Check queue saturation:**
```promql
obskit_async_queue_depth / obskit_async_queue_capacity
```

---

## Logging Issues

### Logs Not Appearing

**Symptom:** No log output

**Solutions:**

1. **Check log level:**
```python
configure(log_level="DEBUG")  # Lower level to see more
```

2. **Check sampling:**
```python
configure(log_sample_rate=1.0)  # Disable sampling
```

3. **Verify logger is configured:**
```python
from obskit import get_logger, configure_logging
configure_logging()
logger = get_logger(__name__)
logger.info("test")
```

### Logs Not JSON

**Symptom:** Logs in wrong format

**Solution:** Set format:
```python
configure(log_format="json")  # or "console"
```

### Missing Correlation IDs

**Symptom:** Logs missing `correlation_id`

**Solution:** Bind correlation ID:
```python
from obskit.logging import bind_correlation_id
import uuid

bind_correlation_id(str(uuid.uuid4()))
```

---

## Tracing Issues

### Traces Not Appearing

**Symptom:** No traces in Jaeger/Tempo

**Solutions:**

1. **Check tracing is enabled:**
```python
configure(
    tracing_enabled=True,
    otlp_endpoint="http://jaeger:4317",
)
```

2. **Check endpoint is reachable:**
```bash
curl -v http://jaeger:4317
```

3. **Check sample rate:**
```python
configure(trace_sample_rate=1.0)  # 100% for debugging
```

4. **Verify OpenTelemetry is installed:**
```bash
pip install obskit[tracing]
```

### Missing Spans

**Symptom:** Some spans not appearing

**Solution:** Ensure spans are created:
```python
from obskit.tracing import trace_span

with trace_span("my_operation") as span:
    span.set_attribute("key", "value")
    # Your code here
```

### Trace Context Not Propagating

**Symptom:** Traces not connected across services

**Solution:** Propagate context:
```python
from obskit.tracing import inject_trace_context, extract_trace_context

# Inject into outgoing requests
headers = {}
inject_trace_context(headers)
response = await client.get(url, headers=headers)

# Extract from incoming requests
context = extract_trace_context(request.headers)
```

---

## Health Check Issues

### Health Check Timeout

**Symptom:** Health checks timing out

**Solutions:**

1. **Increase timeout:**
```python
configure(health_check_timeout=10.0)
```

2. **Or per-check timeout:**
```python
from obskit.health import create_redis_check
checker.add_readiness_check(
    "redis",
    create_redis_check(client, timeout=10.0),
)
```

### Kubernetes Pod Restart Loop

**Symptom:** Pod constantly restarting

**Solutions:**

1. **Check liveness probe isn't checking external deps:**
```python
# Liveness should be simple
@checker.add_liveness_check("heartbeat")
async def check_heartbeat():
    return True  # Just check process is alive
```

2. **Increase failure threshold:**
```yaml
livenessProbe:
  failureThreshold: 5  # More tolerance
```

3. **Check startup probe:**
```yaml
startupProbe:
  failureThreshold: 30  # Allow longer startup
```

### Readiness Always Failing

**Symptom:** Service never becomes ready

**Solution:** Check dependency health:
```bash
# In the pod
kubectl exec -it <pod> -- /bin/sh
curl http://localhost:8080/ready
```

And debug specific checks:
```python
result = await checker.check_readiness()
for name, check_result in result.checks.items():
    print(f"{name}: {check_result.status} - {check_result.message}")
```

---

## Circuit Breaker Issues

### Circuit Always Open

**Symptom:** Circuit breaker never closes

**Solutions:**

1. **Check failure count:**
```python
print(f"State: {breaker._state}")
print(f"Failures: {breaker._failure_count}")
```

2. **Check recovery timeout:**
```python
# Maybe timeout is too long
breaker = CircuitBreaker(
    recovery_timeout=30.0,  # Reduce if needed
)
```

3. **Check half-open behavior:**
```python
# Ensure test requests can succeed
breaker = CircuitBreaker(
    half_open_requests=1,  # Fewer test requests
)
```

### Distributed CB Not Syncing

**Symptom:** Different instances have different circuit state

**Solutions:**

1. **Check Redis connectivity:**
```python
import redis
r = redis.Redis(host="redis", port=6379)
print(r.ping())  # Should return True
```

2. **Check Redis key:**
```python
key = f"{breaker.key_prefix}{breaker.name}"
state = redis_client.get(key)
print(f"State in Redis: {state}")
```

3. **Check TTL:**
```python
ttl = redis_client.ttl(key)
print(f"TTL: {ttl}s")
```

---

## Performance Issues

### High CPU Usage

**Symptom:** Observability adding significant CPU overhead

**Solutions:**

1. **Enable sampling:**
```python
configure(
    metrics_sample_rate=0.1,
    log_sample_rate=0.1,
    trace_sample_rate=0.1,
)
```

2. **Disable unnecessary features:**
```python
configure(
    tracing_enabled=False,  # If not needed
)
```

3. **Use async metrics:**
```python
from obskit.metrics import AsyncREDMetrics
async_red = AsyncREDMetrics("service")
```

### High Memory Usage

**Symptom:** Memory growing over time

**Solutions:**

1. **Check queue size:**
```python
configure(async_metric_queue_size=10000)  # Reduce if too high
```

2. **Enable sampling:**
```python
configure(metrics_sample_rate=0.1)
```

3. **Check metric cardinality:**
```promql
# Check for high cardinality metrics
topk(10, count by (__name__)({__name__=~".+"}))
```

### Slow Request Processing

**Symptom:** Requests slower with observability

**Solutions:**

1. **Use async metrics:**
```python
from obskit.metrics import AsyncREDMetrics
```

2. **Enable sampling:**
```python
configure(metrics_sample_rate=0.1)
```

3. **Profile to identify bottleneck:**
```python
import cProfile
cProfile.run('your_function()')
```

---

## Debugging Commands

### Check All Configuration

```python
from obskit import get_settings

settings = get_settings()
for field in settings.model_fields:
    value = getattr(settings, field)
    print(f"{field}: {value}")
```

### Check Self-Metrics

```python
from obskit.metrics.self_metrics import get_self_metrics

metrics = get_self_metrics()
snapshot = metrics.get_snapshot()
print(f"Queue depth: {snapshot.queue_depth}")
print(f"Queue capacity: {snapshot.queue_capacity}")
print(f"Dropped: {snapshot.dropped_total}")
print(f"Errors: {snapshot.errors_total}")
```

### Test Health Checks

```python
import asyncio
from obskit.health import get_health_checker

async def debug_health():
    checker = get_health_checker()
    result = await checker.check_health()
    print(f"Status: {result.status}")
    for name, check in result.checks.items():
        print(f"  {name}: {check.status} - {check.message}")

asyncio.run(debug_health())
```

### Test Circuit Breaker

```python
from obskit.resilience import CircuitBreaker

breaker = CircuitBreaker("test", failure_threshold=3)
print(f"State: {breaker._state}")
print(f"Failures: {breaker._failure_count}")
print(f"Last failure: {breaker._last_failure_time}")
```

---

## Getting Help

1. **Check documentation:** `tech_docs/` folder
2. **Check logs:** Enable DEBUG level
3. **Check metrics:** `obskit_*` metrics
4. **GitHub Issues:** Report bugs with:
   - obskit version
   - Python version
   - Configuration (redact secrets)
   - Error messages
   - Steps to reproduce
