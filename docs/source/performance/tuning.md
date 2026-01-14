# Performance Tuning Guide

This guide covers performance optimization strategies for high-throughput services using obskit.

## Performance Targets

| Component | Target Overhead | When to Optimize |
|-----------|----------------|------------------|
| Metric observation | < 10µs | > 100k ops/sec |
| Structured log | < 50µs | > 10k logs/sec |
| Trace span creation | < 20µs | > 50k spans/sec |
| Context propagation | < 1µs | Always acceptable |

## Metrics Optimization

### 1. Enable Metrics Sampling

For very high-frequency operations (>100k/sec), enable sampling:

```python
from obskit import configure

configure(
    service_name="my-service",
    metrics_sampling_rate=0.1,  # Sample 10% of metrics
)
```

Or per-operation:

```python
from obskit import get_red_metrics

metrics = get_red_metrics()

# High-frequency operations: sample
if should_sample():  # Your sampling logic
    metrics.observe_request("high_freq_op", duration)
```

### 2. Optimize Histogram Buckets

Default buckets may not fit your latency distribution:

```python
from obskit.metrics.presets import FAST_SERVICE_BUCKETS

configure(
    service_name="my-service",
    histogram_buckets=FAST_SERVICE_BUCKETS,  # Optimized for < 100ms operations
)
```

Available presets:
- `DEFAULT_BUCKETS`: General purpose (5ms - 10s)
- `FAST_SERVICE_BUCKETS`: Low latency (1ms - 500ms)
- `SLOW_SERVICE_BUCKETS`: High latency (100ms - 60s)
- `NETWORK_BUCKETS`: Network operations (10ms - 30s)

### 3. Use Labels Wisely

**Bad: High cardinality labels**
```python
# DON'T: User ID creates unbounded cardinality
metrics.observe_request(f"user_{user_id}", duration)
```

**Good: Bounded cardinality**
```python
# DO: Use bounded labels
metrics.observe_request(
    operation="get_user",
    duration_seconds=duration,
    # user_tier instead of user_id
)
```

### 4. Batch Metric Recording

For async applications, use async metric recording:

```python
from obskit.metrics import AsyncREDMetrics, get_red_metrics

metrics = get_red_metrics()
async_metrics = AsyncREDMetrics(metrics)

# Start background worker
await async_metrics.start()

# Non-blocking metric recording
await async_metrics.observe_request("operation", 0.1)

# Shutdown cleanly
await async_metrics.stop()
```

## Logging Optimization

### 1. Enable Log Sampling

For high-volume services:

```python
configure(
    service_name="my-service",
    log_sampling_rate=0.01,  # Log 1% of info messages
)
```

### 2. Use Appropriate Log Levels

```python
# Production
configure(log_level="WARNING")

# Staging
configure(log_level="INFO")

# Development
configure(log_level="DEBUG")
```

### 3. Lazy Evaluation

```python
# Expensive: Always evaluates
logger.debug(f"Processing {expensive_computation()}")

# Cheap: Only evaluates if debug enabled
logger.debug("processing", data=lambda: expensive_computation())
```

### 4. Reduce Log Context

```python
# Heavy context
logger.info("event", full_request=request_dict)  # Large object

# Light context
logger.info("event", request_id=request.id)  # Just ID
```

## Tracing Optimization

### 1. Configure Sampling

```python
configure(
    service_name="my-service",
    trace_sampling_rate=0.1,  # Sample 10% of traces
)
```

### 2. Use Parent-Based Sampling

Honors sampling decisions from upstream:

```python
configure(
    service_name="my-service",
    trace_sampling_rate=0.1,
    trace_parent_based=True,  # Inherit parent decision
)
```

### 3. Limit Span Attributes

```python
# Bad: Large attributes
with tracer.start_span("op", attributes={"response": large_response}):
    pass

# Good: Small attributes
with tracer.start_span("op", attributes={"response_size": len(response)}):
    pass
```

### 4. Rate Limit Exports

```python
configure(
    service_name="my-service",
    otlp_export_rate_limit=1000,  # Max 1000 spans/sec
)
```

## Circuit Breaker Optimization

### 1. Tune Thresholds

```python
from obskit.resilience import CircuitBreaker

# Fast-failing for critical paths
critical_breaker = CircuitBreaker(
    name="payment",
    failure_threshold=3,  # Open after 3 failures
    recovery_timeout=10.0,  # Try recovery after 10s
)

# Tolerant for non-critical paths
tolerant_breaker = CircuitBreaker(
    name="recommendations",
    failure_threshold=10,
    recovery_timeout=60.0,
)
```

### 2. Use Async Redis for Distributed State

```python
import redis.asyncio as aioredis
from obskit.resilience import DistributedCircuitBreaker

# Async Redis is faster than sync in async applications
redis_client = aioredis.Redis(host="localhost")

breaker = DistributedCircuitBreaker(
    name="api",
    redis_client=redis_client,
)
```

## Connection Pooling

### Redis Connection Pool

```python
import redis

# Create pool once
pool = redis.ConnectionPool(
    host='localhost',
    port=6379,
    max_connections=50,
)

# Use pool for circuit breakers
redis_client = redis.Redis(connection_pool=pool)
```

### HTTP Connection Pool

```python
import httpx

# Reuse client for Alertmanager
client = httpx.AsyncClient(
    limits=httpx.Limits(max_connections=100),
    timeout=30.0,
)
```

## Memory Optimization

### 1. Limit Metric History

Prometheus metrics can grow with unique label combinations:

```python
# Monitor cardinality
from prometheus_client import REGISTRY

for metric in REGISTRY.collect():
    for sample in metric.samples:
        print(f"{sample.name}: {len(sample.labels)} labels")
```

### 2. Use Summary Instead of Histogram

For percentiles without bucket storage:

```python
from obskit.metrics import Summary

response_time = Summary(
    'response_time_seconds',
    'Response time',
    quantiles=[0.5, 0.95, 0.99],
)
```

## Benchmark Your Configuration

Run obskit benchmarks to verify performance:

```bash
# Install benchmark dependencies
pip install pytest-benchmark

# Run benchmarks
pytest benchmarks/ --benchmark-enable --benchmark-json=results.json

# Compare against baseline
pytest benchmarks/ --benchmark-enable --benchmark-compare
```

### Example Results

```
------------------------ benchmark: metrics -------------------------
Name                              Min      Mean     StdDev    OPS
test_observe_request           4.2µs    5.1µs     0.8µs   196,078
test_track_request             8.3µs    9.7µs     1.2µs   103,092
test_counter_inc               1.1µs    1.3µs     0.2µs   769,230
```

## Production Checklist

- [ ] Metrics sampling enabled for high-frequency operations
- [ ] Histogram buckets tuned for your latency profile
- [ ] Log level set to WARNING or higher
- [ ] Log sampling enabled for INFO/DEBUG
- [ ] Trace sampling configured (typically 1-10%)
- [ ] Connection pools configured
- [ ] Circuit breaker thresholds tuned
- [ ] Benchmark results within targets
- [ ] Cardinality monitored

