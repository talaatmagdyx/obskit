# Performance Guide

## Resource Requirements

### Minimum Requirements

| Resource | Development | Production (Low Traffic) | Production (High Traffic) |
|----------|-------------|--------------------------|---------------------------|
| CPU | 0.1 cores | 0.25 cores | 0.5-1 cores |
| Memory | 50 MB | 100 MB | 256-512 MB |
| Network | Minimal | 1 Mbps | 10+ Mbps |

### Memory Breakdown

| Component | Base Memory | Per 10K Operations |
|-----------|-------------|-------------------|
| Metrics Registry | 10 MB | +5 MB |
| Async Metric Queue | 5 MB | - |
| Trace Export Queue | 10 MB | - |
| Logging Buffers | 5 MB | - |
| Health Checks | 1 MB | - |

### Scaling Considerations

**For high-traffic services (>100K ops/sec):**
- Enable sampling (metrics, logs, traces)
- Use async metric recording
- Consider dedicated metrics endpoint
- Monitor memory growth

## Performance Benchmarks

### Metric Recording Overhead

```
Benchmark: RED Metrics observe_request()
Hardware: Apple M1 Pro, 16GB RAM
Python: 3.12.2

╔═══════════════════════════════════════════════════════════════════╗
║ Operation               │ Time (μs) │ Ops/sec    │ Memory (KB) ║
╠═══════════════════════════════════════════════════════════════════╣
║ observe_request()       │ 2.5       │ 400,000    │ 0.1         ║
║ observe_request() async │ 0.8       │ 1,250,000  │ 0.1         ║
║ inc_error()             │ 1.2       │ 833,333    │ 0.05        ║
║ track_request context   │ 3.5       │ 285,714    │ 0.2         ║
╚═══════════════════════════════════════════════════════════════════╝
```

### Logging Overhead

```
Benchmark: Structured Logging
Hardware: Apple M1 Pro, 16GB RAM

╔═══════════════════════════════════════════════════════════════════╗
║ Operation               │ Time (μs) │ Ops/sec    │ Notes        ║
╠═══════════════════════════════════════════════════════════════════╣
║ logger.info() JSON      │ 15        │ 66,666     │ To stdout    ║
║ logger.info() Console   │ 25        │ 40,000     │ With colors  ║
║ logger.info() Sampled   │ 0.5       │ 2,000,000  │ 1% sampling  ║
╚═══════════════════════════════════════════════════════════════════╝
```

### Tracing Overhead

```
Benchmark: OpenTelemetry Tracing
Hardware: Apple M1 Pro, 16GB RAM

╔═══════════════════════════════════════════════════════════════════╗
║ Operation               │ Time (μs) │ Ops/sec    │ Notes        ║
╠═══════════════════════════════════════════════════════════════════╣
║ trace_span() context    │ 5.0       │ 200,000    │ No export    ║
║ trace_span() with attrs │ 8.0       │ 125,000    │ 5 attributes ║
║ trace_span() sampled    │ 0.5       │ 2,000,000  │ 10% sampling ║
╚═══════════════════════════════════════════════════════════════════╝
```

### Circuit Breaker Overhead

```
Benchmark: Circuit Breaker
Hardware: Apple M1 Pro, 16GB RAM

╔═══════════════════════════════════════════════════════════════════╗
║ Operation                    │ Time (μs) │ Ops/sec    │ Notes   ║
╠═══════════════════════════════════════════════════════════════════╣
║ Local CircuitBreaker         │ 1.5       │ 666,666    │ Closed  ║
║ DistributedCircuitBreaker    │ 500       │ 2,000      │ Redis   ║
║ DistributedCircuitBreaker    │ 250       │ 4,000      │ Cached  ║
╚═══════════════════════════════════════════════════════════════════╝
```

### Middleware Overhead

```
Benchmark: FastAPI Middleware
Hardware: Apple M1 Pro, 16GB RAM

╔═══════════════════════════════════════════════════════════════════╗
║ Configuration                │ Latency Added │ Notes             ║
╠═══════════════════════════════════════════════════════════════════╣
║ Full (metrics+logs+tracing)  │ 50-100 μs     │ All features      ║
║ Metrics only                 │ 10-20 μs      │ track_metrics=T   ║
║ Logging only                 │ 20-40 μs      │ track_logging=T   ║
║ Tracing only                 │ 30-50 μs      │ track_tracing=T   ║
║ With 10% sampling            │ 5-10 μs       │ Amortized         ║
╚═══════════════════════════════════════════════════════════════════╝
```

## Optimization Strategies

### 1. Enable Sampling for High-Traffic Services

```python
configure(
    # Sample 10% of metrics
    metrics_sample_rate=0.1,
    
    # Sample 1% of logs
    log_sample_rate=0.01,
    
    # Sample 10% of traces
    trace_sample_rate=0.1,
)
```

**Impact:** 10x reduction in overhead for sampled operations.

### 2. Use Async Metric Recording

```python
from obskit.metrics.async_recording import AsyncREDMetrics
from obskit.metrics import REDMetrics

# Create async wrapper
base_metrics = REDMetrics("service")
async_metrics = AsyncREDMetrics(base_metrics)

# Non-blocking metric recording
await async_metrics.observe_request(
    operation="high_freq_op",
    duration_seconds=0.001,
    status="success",
)
```

**Impact:** ~3x faster metric recording for high-frequency operations.

### 3. Configure Queue Sizes

```python
configure(
    # Reduce queue size for memory-constrained environments
    async_metric_queue_size=5000,  # Default: 10000
    
    # Or increase for burst handling
    async_metric_queue_size=50000,
)
```

### 4. Use Metrics-Only Tracking

```python
from obskit.decorators import track_metrics_only

@track_metrics_only(operation="cache_lookup")
async def cache_lookup(key: str):
    # No logging overhead, just metrics
    return await cache.get(key)
```

### 5. Optimize Histogram Buckets

```python
from obskit.metrics import REDMetrics

# For fast services (<100ms)
fast_buckets = [0.001, 0.005, 0.01, 0.025, 0.05, 0.1]
red = REDMetrics("cache_service", histogram_buckets=fast_buckets)

# For slow services (>1s)
slow_buckets = [0.1, 0.5, 1, 2.5, 5, 10, 30]
red = REDMetrics("batch_service", histogram_buckets=slow_buckets)
```

## Monitoring obskit Performance

### Self-Metrics

obskit exposes metrics about its own performance:

```promql
# Queue depth
obskit_async_queue_depth

# Queue capacity
obskit_async_queue_capacity

# Dropped metrics (queue full)
rate(obskit_metrics_dropped_total[5m])

# Internal errors
rate(obskit_errors_total[5m])
```

### Alerting on obskit Issues

```yaml
groups:
  - name: obskit_health
    rules:
      - alert: ObskitQueueFull
        expr: obskit_async_queue_depth / obskit_async_queue_capacity > 0.9
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "obskit metric queue is nearly full"
          
      - alert: ObskitMetricsDropped
        expr: rate(obskit_metrics_dropped_total[5m]) > 0
        for: 1m
        labels:
          severity: warning
        annotations:
          summary: "obskit is dropping metrics"
```

## Metric Cardinality Management

High cardinality metrics can cause memory issues. Monitor and limit:

```python
# BAD: High cardinality (user_id as label)
metrics.observe_request(
    operation=f"api_{user_id}",  # Don't do this!
    ...
)

# GOOD: Bounded cardinality
metrics.observe_request(
    operation="api_request",
    ...
)
```

### Monitoring Cardinality

```promql
# Count unique time series
count({__name__=~"myservice_.*"})

# Monitor series growth
increase(prometheus_tsdb_head_series[1h])
```

## Running Benchmarks

```bash
# Install benchmark dependencies
pip install pytest-benchmark

# Run all benchmarks
pytest benchmarks/ --benchmark-enable

# Run specific benchmark
pytest benchmarks/bench_metrics.py --benchmark-enable

# Compare with baseline
pytest benchmarks/ --benchmark-enable --benchmark-compare

# Generate JSON report
pytest benchmarks/ --benchmark-enable --benchmark-json=results.json
```

## Load Testing

```bash
# Install load testing tools
pip install locust httpx

# Run load test
locust -f tests/load/locustfile.py --host http://localhost:8000

# Or use hey/wrk
hey -n 10000 -c 100 http://localhost:8000/api/endpoint
```

---

**Last Updated:** 2026-01-09
