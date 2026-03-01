# Performance Guide

obskit is designed for production use in high-throughput services.  This page
documents benchmark results, overhead budgets, and tuning recommendations.

---

## Benchmark Methodology

All benchmarks are run with [pytest-benchmark](https://pytest-benchmark.readthedocs.io/)
in single-threaded mode on a fixed-frequency CPU (no turbo boost).  Results are
reported as minimum latency (best case) and operations per second.

```bash
# Run micro-benchmarks
pytest benchmarks/ --benchmark-only -p no:xdist -o addopts="" \
  --benchmark-columns=min,mean,median,stddev,ops \
  --benchmark-warmup=on --benchmark-min-rounds=50

# Run macro-benchmarks
python benchmarks/macro_runner.py --requests 10000 --workers 16

# Run memory benchmarks
python benchmarks/bench_memory.py
```

---

## Go / No-Go Thresholds

These are the **release gates** — a PR that causes any metric to exceed its
threshold is blocked until the regression is resolved.

### Micro-benchmark thresholds

| Benchmark | Min latency threshold | Ops/s threshold |
|---|---|---|
| `with_observability` sync (no-op) | ≤ 50 µs | ≥ 20,000 |
| `with_observability` async (no-op) | ≤ 50 µs | ≥ 20,000 |
| `with_observability` with exception | ≤ 100 µs | ≥ 10,000 |
| Decorator stack depth 3 | ≤ 150 µs | ≥ 6,000 |
| `SLOTracker.record_measurement()` | ≤ 5 µs | ≥ 200,000 |
| `SLOTracker.get_status()` (full window) | ≤ 20 µs | ≥ 50,000 |
| `CircuitBreaker.__enter__` (CLOSED) | ≤ 2 µs | ≥ 500,000 |
| `CircuitBreaker.__enter__` (OPEN) | ≤ 1 µs | ≥ 1,000,000 |
| `logger.info()` | ≤ 20 µs | ≥ 50,000 |
| Correlation ID set + get | ≤ 1 µs | ≥ 1,000,000 |
| `REDMetrics.record_request()` | ≤ 5 µs | ≥ 200,000 |

### Macro-benchmark thresholds (p99)

10,000 requests, 16 workers, Zipf tenant distribution, lognormal latency.

| Scenario | p99 budget | Min req/s | Error rate |
|---|---|---|---|
| `metrics_only` | ≤ 50 µs | ≥ 50,000 | 0% |
| `logging_only` | ≤ 100 µs | ≥ 20,000 | 0% |
| `circuit_breaker_only` | ≤ 10 µs | ≥ 200,000 | 0% |
| `slo_only` | ≤ 20 µs | ≥ 100,000 | 0% |
| `full_stack` | ≤ 200 µs | ≥ 10,000 | 0% |
| `high_cardinality` (500 unique labels) | ≤ 500 µs | ≥ 1,000 | 0% |

### Memory thresholds

| Metric | Threshold |
|---|---|
| Per-call net allocation — `with_observability` | ≤ 2 KiB per 1,000 calls |
| SLO 1-hour rolling window (10,000 records) | ≤ 5 MB |
| SLO 0-second window with full eviction | ≤ 500 KB |
| Logger `bind()` + `info()` (1,000 calls) | ≤ 500 KB |
| Prometheus cardinality (500 unique label sets) | ≤ 10 MB |
| Leak detector delta (5,000 requests after warmup) | < 250 objects |

---

## Per-Operation Overhead Reference

Use these numbers to reason about overhead at your traffic level.

| Operation | Overhead | Notes |
|---|---|---|
| `get_logger(__name__)` | ~2 µs (once) | Cached after first call |
| `logger.info("event", **kwargs)` | ~15–20 µs | Structlog pipeline: format, contextvars, JSON render |
| `REDMetrics.record_request()` | ~3–5 µs | Counter.inc() + Histogram.observe() + label lookup |
| `observe_with_exemplar()` | ~5–8 µs | Same as above + OTel span context read |
| `trace_span()` enter | ~2–5 µs | OTel span creation + context push |
| `trace_span()` exit (no error) | ~2–4 µs | Span end + attribute flush |
| `async_trace_span()` enter | ~3–6 µs | Async overhead + OTel span creation |
| `CircuitBreaker` enter (CLOSED) | ~1–2 µs | RLock + state check |
| `CircuitBreaker` enter (OPEN) | < 1 µs | Fast-fail, no lock contention |
| `SLOTracker.record_measurement()` | ~3–5 µs | Lock + list append + eviction check |
| `CardinalityGuard.safe_label()` | ~1–2 µs (cached) | Dict lookup + counter check |
| `CardinalityGuard.safe_label()` (new label) | ~5–10 µs | Lock + dict insert |
| `set_baggage()` | < 1 µs | ContextVar set |
| `get_baggage()` | < 1 µs | ContextVar get |

---

## Sample Rate Recommendations

Choose your sampling rates based on traffic volume.  The goal is to balance
observability completeness with overhead.

### Trace sample rate (`OBSKIT_TRACE_SAMPLE_RATE`)

| Traffic level | Recommended rate | Rationale |
|---|---|---|
| < 10 req/s | `1.0` (100%) | Low volume; full trace coverage is cheap |
| 10–100 req/s | `1.0` (100%) | Still manageable; full coverage recommended |
| 100–1,000 req/s | `0.1` (10%) | Reduces Tempo storage by 10× |
| 1,000–10,000 req/s | `0.01` (1%) | Standard for high-throughput services |
| > 10,000 req/s | `0.001` (0.1%) | Use with head-based + tail-based sampling |

!!! tip "Always sample errors"
    obskit will sample 100% of error spans regardless of `trace_sample_rate`.
    Set `OBSKIT_TRACE_SAMPLE_RATE=0.01` and you will still see all errors.

### Log sample rate (`OBSKIT_LOG_SAMPLE_RATE`)

| Traffic level | Recommended rate | Notes |
|---|---|---|
| < 100 req/s | `1.0` | Log everything |
| 100–1,000 req/s | `0.1` | Sample INFO and below; always emit WARNING+ |
| > 1,000 req/s | `0.01` | Use `AdaptiveSampler`; auto-increases on errors |

### Metrics sample rate (`OBSKIT_METRICS_SAMPLE_RATE`)

In most cases, keep metrics at `1.0`.  Prometheus counters are inaccurate when
sampled.  Only reduce if metrics collection itself is a bottleneck (unusual).

---

## Cardinality Budget Guidelines

Prometheus's memory usage scales linearly with the number of unique time series.
A single `Histogram` with 4 label combinations × 10 buckets = 40 time series.

**Budget formula:**

```
Total time series = Σ (unique_label_combinations × histogram_buckets)
```

**Recommended limits:**

| Resource | Time series budget | Notes |
|---|---|---|
| Small service (2 GB Prometheus) | ≤ 100,000 | ~50 metrics × 2,000 label combos |
| Medium service (8 GB Prometheus) | ≤ 500,000 | Standard for mid-size deployments |
| Large service (32 GB Prometheus) | ≤ 2,000,000 | Requires tuned Prometheus config |

**Practical rules:**

- Never use `user_id`, `request_id`, or any unbounded value as a label.
- Use `CardinalityGuard(max_cardinality=500)` for any label derived from user input.
- Use at most 4–5 label dimensions per metric.
- Prefer low-cardinality enumerations: `status={"success","error"}`, `method={"GET","POST",…}`.

---

## Async vs Sync Performance

obskit supports both async and sync code paths.  Async is slightly higher-overhead
due to event loop scheduling, but enables higher concurrency without blocking.

| Pattern | Latency | Concurrency | Use when |
|---|---|---|---|
| `trace_span()` (sync) | ~4 µs | Limited by threads | Django, Flask, Celery |
| `async_trace_span()` (async) | ~6 µs | Unlimited (cooperative) | FastAPI, aiohttp, async workers |
| `CircuitBreaker` (sync) | ~1–2 µs | Thread-safe (RLock) | Any sync code |
| `CircuitBreaker` (async) | ~2–3 µs | Async-safe (asyncio.Lock) | Async frameworks |

**Recommendation:** Use async APIs in async code and sync APIs in sync code.
Mixing (e.g., calling async from sync) requires `asyncio.run()` and has ~50 µs
overhead for event loop creation.

---

## Memory Footprint Per Component

Approximate RSS increase per component at steady state (after 10,000 requests):

| Component | RSS delta | Dominant contributor |
|---|---|---|
| `obskit` (core + logging) | ~5 MB | pydantic-settings model + structlog processor chain |
| `obskit[prometheus]` | ~5–50 MB | Prometheus registry (scales with cardinality) |
| `obskit[otlp]` | ~10 MB | OTel SDK + BatchSpanProcessor queue (2,048 spans) |
| `obskit` health module | ~1 MB | HealthChecker state + check registry |
| `obskit` resilience module | ~1 MB | CircuitBreaker state machines |
| `obskit` slo module | ~2–20 MB | SLO measurement windows (scales with window size) |
| `obskit[kafka]` / `obskit[rabbitmq]` | ~2 MB | Kafka/RabbitMQ consumer metrics |

!!! info "Prometheus cardinality dominates memory"
    The `obskit[prometheus]` footprint depends almost entirely on how many unique label
    combinations exist.  1,000 unique time series ≈ ~1 MB.  10,000 ≈ ~10 MB.

---

## Production Tuning Tips

### Use `async_trace_span` in async code

```python
# Avoid: sync span in async context forces thread-local context
with trace_span("my_op"):           # OK but not ideal in async
    await do_work()

# Prefer: async context manager
async with async_trace_span("my_op"):
    await do_work()
```

### Disable debug mode in production

```bash
# Avoid in production — ConsoleSpanExporter is synchronous and slow
OBSKIT_LOG_FORMAT=console  # only for local development

# Use in production
OBSKIT_LOG_FORMAT=json
```

### Set sample_rate for high-throughput services

```bash
# > 1,000 req/s
OBSKIT_TRACE_SAMPLE_RATE=0.01
OBSKIT_LOG_SAMPLE_RATE=0.01
```

### Reduce trace export batch timeout for lower-latency shutdown

```bash
OBSKIT_TRACE_EXPORT_TIMEOUT=5.0   # default 30s; reduce for faster pod shutdown
```

### Pin CPU frequency before benchmarking

```bash
# Linux
sudo cpupower frequency-set -g performance

# Pin to a single core to reduce jitter
taskset -c 2 pytest benchmarks/ --benchmark-only
```

### Profile hot paths with py-spy

```bash
pip install py-spy
py-spy record -o /tmp/obskit.svg --pid $(pgrep -f "uvicorn main:app") --duration 30
# Open /tmp/obskit.svg in a browser — identifies the actual bottleneck
```

---

## CI Performance Regression Check

Add this to your CI pipeline to catch regressions automatically:

```yaml
- name: Benchmark regression check
  run: |
    pytest benchmarks/ --benchmark-only -p no:xdist -o addopts="" \
      --benchmark-json=results/bench_pr.json \
      --benchmark-compare=results/bench_main.json \
      --benchmark-compare-fail=mean:10%
```

**Regression policy:**

| Delta vs baseline | Action |
|---|---|
| < 5% slower | Acceptable noise — pass |
| 5–10% slower | Review required — explain in PR |
| > 10% slower | Block merge — mandatory investigation |
| Memory leak detected | Block merge — must be fixed |
