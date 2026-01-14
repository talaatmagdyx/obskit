# Performance Guide

Optimize obskit for high-throughput production environments.

## Performance Characteristics

### Overhead Measurements

| Operation | Typical Overhead | Notes |
|-----------|-----------------|-------|
| Counter increment | ~100ns | Minimal impact |
| Histogram observation | ~500ns | More expensive than counters |
| Span creation | ~1-5μs | Depends on attributes |
| Log entry (JSON) | ~1-5μs | Serialization cost |
| PII redaction | ~10-50μs | Pattern matching |
| Context propagation | ~100ns | Very fast |

### Memory Usage

| Component | Memory (typical) | Notes |
|-----------|-----------------|-------|
| RED metrics (per service) | ~10KB | Plus ~100B per unique label set |
| Trace span | ~1KB | Before export |
| Log buffer | ~1MB | Configurable |
| Circuit breaker | ~100B | Per breaker instance |

## Optimization Strategies

### 1. Metrics Sampling

For extremely high throughput (>100k requests/second):

```python
from obskit import get_red_metrics

# Sample 10% of requests
metrics = get_red_metrics(
    service_name="high-traffic-api",
    sample_rate=0.1,
)
```

**When to use**: >10k requests/second per metric

**Trade-off**: Reduced accuracy for reduced overhead

### 2. Trace Sampling

Tracing is more expensive than metrics. Sample aggressively in production:

```python
from obskit import configure_tracing

# Production: 1% sampling
configure_tracing(
    service_name="api",
    sample_rate=0.01,
)

# Development: 100% sampling
configure_tracing(
    service_name="api",
    sample_rate=1.0,
)
```

**Recommendation by load**:

| Requests/second | Sample Rate |
|-----------------|-------------|
| < 100 | 100% (1.0) |
| 100 - 1,000 | 10% (0.1) |
| 1,000 - 10,000 | 1% (0.01) |
| > 10,000 | 0.1% (0.001) |

### 3. Log Sampling

For high-volume INFO logs:

```python
from obskit import configure_logging

# Sample 10% of INFO logs (errors always logged)
logger = configure_logging(
    service_name="api",
    sample_rate=0.1,
)
```

### 4. Async Metric Recording

For ultra-high-throughput services:

```python
from obskit.metrics import AsyncREDMetrics

# Metrics are queued and recorded in background
metrics = AsyncREDMetrics(
    service_name="event-processor",
    queue_size=10000,
)
```

**Benefits**:
- Non-blocking metric updates
- Batched Prometheus updates
- ~10x faster for high-volume

**Trade-offs**:
- Slight delay in metric visibility
- Memory for queue

### 5. Histogram Bucket Optimization

Default buckets may not suit your latency profile:

```python
# For fast APIs (most requests < 100ms)
fast_buckets = [0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0]

# For batch jobs (seconds to minutes)
batch_buckets = [1, 5, 10, 30, 60, 120, 300, 600, 1800]

metrics = get_red_metrics(
    service_name="api",
    duration_buckets=fast_buckets,
)
```

**Why it matters**: Each bucket is a separate time series. Too many = memory waste. Too few = poor resolution.

### 6. Cardinality Control

High cardinality is the #1 metrics performance killer:

```python
# Bad: unbounded cardinality
metrics.track_request(endpoint=f"/users/{user_id}")  # Millions of time series!

# Good: bounded cardinality
def normalize_path(path: str) -> str:
    # /users/12345 -> /users/{id}
    import re
    return re.sub(r'/\d+', '/{id}', path)

metrics.track_request(endpoint=normalize_path(request.path))
```

**Rule of thumb**: Keep unique label combinations under 10,000 per metric.

## Benchmarks

### Metrics Benchmark

```python
import time
from obskit import get_red_metrics

metrics = get_red_metrics(service_name="benchmark")

# Warm up
for _ in range(1000):
    metrics.observe_request("/api", "GET", "success", 0.1)

# Benchmark
start = time.perf_counter()
iterations = 100_000

for _ in range(iterations):
    metrics.observe_request("/api", "GET", "success", 0.1)

duration = time.perf_counter() - start
ops_per_second = iterations / duration

print(f"Throughput: {ops_per_second:,.0f} ops/sec")
print(f"Latency: {duration/iterations*1e6:.2f} μs/op")
```

**Typical results**:
- ~500,000 ops/sec (counter only)
- ~200,000 ops/sec (with histogram)

### Logging Benchmark

```python
import time
from obskit import configure_logging

logger = configure_logging(service_name="benchmark")

start = time.perf_counter()
iterations = 100_000

for i in range(iterations):
    logger.info("Benchmark log", iteration=i, value=3.14)

duration = time.perf_counter() - start
ops_per_second = iterations / duration

print(f"Throughput: {ops_per_second:,.0f} logs/sec")
```

**Typical results**:
- ~100,000 logs/sec (JSON format)
- ~150,000 logs/sec (console format)
- ~50,000 logs/sec (with PII redaction)

## Resource Tuning

### CPU Optimization

```python
# Use fewer histogram buckets
metrics = get_red_metrics(
    service_name="api",
    duration_buckets=[0.1, 0.5, 1.0, 5.0],  # Only 4 buckets
)

# Disable expensive features in hot paths
configure_logging(
    service_name="api",
    pii_redaction=False,  # Skip regex matching
)
```

### Memory Optimization

```python
# Limit trace buffer
configure_tracing(
    service_name="api",
    max_queue_size=1000,  # Limit pending spans
)

# Use smaller log buffer
configure_logging(
    service_name="api",
    buffer_size=1000,  # Smaller buffer
)
```

### Network Optimization

```python
# Batch trace exports
configure_tracing(
    service_name="api",
    batch_export=True,
    export_interval_ms=5000,  # Export every 5 seconds
)

# Rate limit exports
configure_tracing(
    service_name="api",
    rate_limit=1000,  # Max 1000 spans/second
)
```

## Production Recommendations

### Small Service (<1k req/s)

```python
# Full observability, no sampling
configure_logging(service_name="api", log_level="INFO")
configure_tracing(service_name="api", sample_rate=1.0)
metrics = get_red_metrics(service_name="api")
```

### Medium Service (1k-10k req/s)

```python
# Light sampling
configure_logging(service_name="api", log_level="INFO", sample_rate=0.5)
configure_tracing(service_name="api", sample_rate=0.1)
metrics = get_red_metrics(service_name="api", sample_rate=0.5)
```

### Large Service (>10k req/s)

```python
# Aggressive sampling, async recording
configure_logging(service_name="api", log_level="WARNING", sample_rate=0.1)
configure_tracing(service_name="api", sample_rate=0.01)
metrics = AsyncREDMetrics(service_name="api", sample_rate=0.1)
```

## Monitoring obskit Overhead

### Self-Monitoring Metrics

obskit exposes its own performance metrics:

```text
# Metric recording latency
obskit_metric_record_duration_seconds_bucket{...}

# Trace export queue size
obskit_trace_queue_size

# Log buffer utilization
obskit_log_buffer_utilization
```

### Grafana Dashboard Query

```promql
# obskit overhead as % of request time
sum(rate(obskit_metric_record_duration_seconds_sum[5m]))
/
sum(rate(my_service_request_duration_seconds_sum[5m]))
```

## Next Steps

- **[Configuration](../config/index.md)** - All tuning options
- **[Architecture](../architecture/overview.md)** - Internal design
- **[Troubleshooting](../troubleshooting/index.md)** - Common issues

