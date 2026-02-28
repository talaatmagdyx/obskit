# obskit Benchmarks

Performance benchmarks for measuring the overhead of observability operations.

## Quick Start

```bash
# Recommended: Use the benchmark script
./scripts/benchmark.sh

# Or run manually (MUST disable xdist)
pytest benchmarks/ --benchmark-only -p no:xdist -o addopts=""
```

> ⚠️ **Important**: The default `pytest.ini` enables parallel execution (`-n auto`) which conflicts with benchmarks. Always use `-p no:xdist -o addopts=""` or the benchmark script.

## Running Benchmarks

### Run All Benchmarks

```bash
./scripts/benchmark.sh
```

### Run Specific Categories

```bash
# Metrics benchmarks
./scripts/benchmark.sh metrics

# Circuit breaker benchmarks  
./scripts/benchmark.sh circuit_breaker

# Context propagation benchmarks
./scripts/benchmark.sh context

# Logging benchmarks
./scripts/benchmark.sh logging
```

### Compare Against Baseline

```bash
# Save current results as baseline
./scripts/benchmark.sh --save

# Compare with saved baseline
./scripts/benchmark.sh --compare
```

### Manual Execution

```bash
# All benchmarks
pytest benchmarks/ --benchmark-only -p no:xdist -o addopts=""

# Specific file
pytest benchmarks/bench_metrics.py --benchmark-only -p no:xdist -o addopts=""

# With detailed output
pytest benchmarks/ --benchmark-only -p no:xdist -o addopts="" \
  --benchmark-columns=min,max,mean,stddev,median,ops

# Export to JSON
pytest benchmarks/ --benchmark-only -p no:xdist -o addopts="" \
  --benchmark-json=results.json
```

## Benchmark Categories

### Metrics (`bench_metrics.py`)
- RED metrics observation (success/failure)
- Counter increment operations
- Gauge set/inc/dec operations
- Histogram observations
- Request tracking context manager

### Context (`bench_context.py`)
- Correlation ID set/get/reset
- Sync context manager overhead
- Async context manager overhead
- Nested context handling
- Raw contextvars comparison

### Circuit Breaker (`bench_circuit_breaker.py`)
- State checking overhead
- Failure count checking
- Decorated sync function calls
- Decorated async function calls
- Success/failure recording

### Logging (`bench_logging.py`)
- Basic structured logging
- Logging with context binding
- Logging with extra fields
- Different log levels

## Interpreting Results

| Metric | Description |
|--------|-------------|
| **Min** | Best case (no GC, warm cache) |
| **Max** | Worst case (GC, contention) |
| **Mean** | Average performance |
| **StdDev** | Consistency (lower = more consistent) |
| **Median** | Typical performance |
| **OPS** | Operations per second (higher = better) |

## Performance Targets

| Operation | Target | Notes |
|-----------|--------|-------|
| Metric observation | < 1 µs | Per-request overhead |
| Correlation ID ops | < 100 ns | Called on every request |
| Circuit breaker check | < 100 ns | State check only |
| Circuit breaker decorated | < 1 µs | Full decorated call |
| Structured log | < 10 µs | Single log statement |

## Troubleshooting

### Error: "Benchmarks are automatically disabled because xdist plugin is active"

Use the benchmark script or disable xdist:

```bash
./scripts/benchmark.sh
# OR
pytest benchmarks/ --benchmark-only -p no:xdist -o addopts=""
```

### Inconsistent Results

1. Close other applications
2. Run with warmup: `--benchmark-warmup=on`
3. Increase rounds: `--benchmark-min-rounds=100`

## CI Integration

Add to your CI pipeline:

```yaml
- name: Run Benchmarks
  run: |
    pip install pytest-benchmark
    pytest benchmarks/ --benchmark-only -p no:xdist -o addopts="" \
      --benchmark-json=benchmarks.json

- name: Upload Benchmark Results
  uses: benchmark-action/github-action-benchmark@v1
  with:
    tool: pytest
    output-file-path: benchmarks.json
```

## Benchmark Files

| File | Type | Run with |
|------|------|---------|
| `bench_metrics.py` | pytest-benchmark | `pytest benchmarks/bench_metrics.py ...` |
| `bench_circuit_breaker.py` | pytest-benchmark | `pytest benchmarks/bench_circuit_breaker.py ...` |
| `bench_context.py` | pytest-benchmark | `pytest benchmarks/bench_context.py ...` |
| `bench_logging.py` | pytest-benchmark | `pytest benchmarks/bench_logging.py ...` |
| `bench_slo.py` | pytest-benchmark | `pytest benchmarks/bench_slo.py ...` |
| `bench_observability.py` | pytest-benchmark | `pytest benchmarks/bench_observability.py ...` |
| `bench_memory.py` | standalone tracemalloc | `python benchmarks/bench_memory.py` |
| `macro_runner.py` | standalone p50/p95/p99 | `python benchmarks/macro_runner.py` |

## Further Reading

- **[BENCHMARKING_STRATEGY.md](BENCHMARKING_STRATEGY.md)** — why each benchmark was designed the way it was: data distributions, warmup rationale, CPU isolation, statistics methodology, A/B comparison guide
- **[PROFILING_PLAYBOOK.md](PROFILING_PLAYBOOK.md)** — when to use cProfile vs py-spy vs scalene, how to interpret results, likely optimisations
- **[go_no_go.md](go_no_go.md)** — metrics checklist + fillable go/no-go threshold table for every scenario
