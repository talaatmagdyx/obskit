# Benchmark Suite

obskit includes a comprehensive benchmark suite to measure the performance overhead of observability operations. This is critical for understanding the cost of instrumentation in high-throughput services.

## Running Benchmarks

### Quick Start

```bash
# Run all benchmarks
./scripts/benchmark.sh

# Or manually (must disable parallel execution)
pytest benchmarks/ --benchmark-only -p no:xdist -o addopts=""
```

### Run Specific Benchmarks

```bash
# Only metrics benchmarks
./scripts/benchmark.sh metrics

# Only circuit breaker benchmarks
./scripts/benchmark.sh circuit_breaker

# Only context propagation benchmarks
./scripts/benchmark.sh context

# Only logging benchmarks
./scripts/benchmark.sh logging
```

### Compare Against Baseline

```bash
# Save current results as baseline
./scripts/benchmark.sh --save

# Compare against saved baseline
./scripts/benchmark.sh --compare
```

## Benchmark Categories

### 1. Metrics Benchmarks (`bench_metrics.py`)

Measures the overhead of metric collection operations:

| Operation | Description | Typical Time |
|-----------|-------------|--------------|
| `observe_request_success` | Record a successful request | ~200-500 ns |
| `observe_request_failure` | Record a failed request | ~200-500 ns |
| `track_request` | Context manager for request tracking | ~300-600 ns |
| `gauge.set` | Set gauge value | ~100-200 ns |
| `gauge.inc/dec` | Increment/decrement gauge | ~100-200 ns |
| `counter.inc` | Increment counter | ~100-200 ns |
| `histogram.observe` | Record histogram observation | ~200-400 ns |

**Example Output:**

```
----- benchmark 'metrics': 4 tests -----
Name                          Mean       StdDev     Median       OPS
observe_request_success      450 ns      50 ns      440 ns    2.2M
observe_request_failure      460 ns      55 ns      450 ns    2.2M
track_request                580 ns      60 ns      570 ns    1.7M
gauge_set                    120 ns      15 ns      115 ns    8.3M
```

### 2. Context Propagation Benchmarks (`bench_context.py`)

Measures the overhead of correlation ID and context management:

| Operation | Description | Typical Time |
|-----------|-------------|--------------|
| `set_correlation_id` | Set correlation ID | ~40-60 ns |
| `get_correlation_id` | Get correlation ID | ~40-60 ns |
| `correlation_context` | Sync context manager | ~100-150 ns |
| `async_correlation_context` | Async context manager | ~80-120 µs |
| Nested contexts | Multiple nested contexts | ~200-300 ns |

**Why This Matters:**

Context propagation happens on every request. Even small overhead multiplies across millions of requests.

### 3. Circuit Breaker Benchmarks (`bench_circuit_breaker.py`)

Measures the overhead of resilience patterns:

| Operation | Description | Typical Time |
|-----------|-------------|--------------|
| `state_check` | Check circuit state | ~40-60 ns |
| `failure_count_check` | Check failure count | ~40-60 ns |
| `decorated_function` | Call protected function | ~400-600 ns |
| `decorated_async_function` | Call protected async function | ~80-150 µs |
| `_record_success` | Record successful call | ~50-100 ns |
| `_record_failure` | Record failed call | ~50-100 ns |

**Key Insight:**

The circuit breaker adds ~500ns overhead per call when circuit is closed. This is negligible for most operations but important for ultra-high-frequency paths.

### 4. Logging Benchmarks (`bench_logging.py`)

Measures the overhead of structured logging:

| Operation | Description | Typical Time |
|-----------|-------------|--------------|
| Basic log | Simple log message | ~1-3 µs |
| Log with context | Log with correlation ID | ~2-5 µs |
| Log with extra fields | Log with multiple fields | ~3-8 µs |
| Debug (disabled) | Debug log when level=INFO | ~50-100 ns |

**Optimization Tip:**

Use log level guards for expensive log operations:

```python
if logger.isEnabledFor(logging.DEBUG):
    logger.debug("expensive", data=expensive_operation())
```

## Understanding Results

### Key Metrics

- **Min**: Best-case performance (no contention, warm cache)
- **Max**: Worst-case performance (GC, contention)
- **Mean**: Average performance
- **StdDev**: Consistency (lower is better)
- **Median**: Typical performance (less affected by outliers)
- **OPS**: Operations per second (higher is better)

### What to Watch For

1. **High StdDev**: Indicates inconsistent performance, possible GC pressure
2. **Large Min/Max Gap**: Suggests contention or resource constraints
3. **Low OPS**: May indicate blocking operations

## Performance Guidelines

### Acceptable Overhead by Operation Type

| Operation Type | Acceptable Overhead | Notes |
|----------------|---------------------|-------|
| HTTP Request | < 100 µs | Request typically takes 10-100ms |
| Database Query | < 10 µs | Query typically takes 1-50ms |
| In-memory Operation | < 1 µs | Operation takes microseconds |
| Hot Path (>100k/s) | < 100 ns | Every nanosecond counts |

### Optimizations Applied

obskit uses several optimizations to minimize overhead:

1. **Lazy Initialization**: Resources created only when first used
2. **Thread-local Storage**: No locks for correlation IDs
3. **Efficient Serialization**: Minimal allocations in hot paths
4. **Metric Batching**: Optional async recording for high-frequency metrics

### When to Use Async Metrics

For operations exceeding 10,000/second, consider async metric recording:

```python
from obskit.metrics.async_recording import AsyncREDMetrics

# Background metric recording
async_metrics = AsyncREDMetrics(red_metrics)
await async_metrics.start()

# Non-blocking metric recording
await async_metrics.observe_request("operation", 0.1, "success")
```

## Continuous Benchmarking

### CI Integration

Add to your CI pipeline:

```yaml
# .github/workflows/benchmark.yml
name: Benchmarks
on:
  push:
    branches: [main]
  pull_request:

jobs:
  benchmark:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: pip install -e ".[benchmark]"
      
      - name: Run benchmarks
        run: |
          pytest benchmarks/ --benchmark-only \
            -p no:xdist -o addopts="" \
            --benchmark-json=benchmark.json
      
      - name: Upload results
        uses: actions/upload-artifact@v4
        with:
          name: benchmark-results
          path: benchmark.json
```

### Regression Detection

Compare against baseline to detect regressions:

```bash
# Save baseline (e.g., on main branch)
pytest benchmarks/ --benchmark-only -p no:xdist \
  -o addopts="" --benchmark-save=baseline

# Compare PR against baseline
pytest benchmarks/ --benchmark-only -p no:xdist \
  -o addopts="" --benchmark-compare=baseline \
  --benchmark-compare-fail=mean:10%
```

## Writing Custom Benchmarks

### Basic Benchmark

```python
import pytest
from obskit.metrics.red import REDMetrics

class TestMyBenchmarks:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.metrics = REDMetrics(name="my_service")
        yield

    @pytest.mark.benchmark(group="my_group")
    def test_my_operation(self, benchmark):
        """Benchmark my operation."""
        def operation():
            # Your code here
            self.metrics.observe_request("op", 0.1, "success")
        
        benchmark(operation)
```

### Async Benchmark

```python
import asyncio
import pytest

class TestAsyncBenchmarks:
    @pytest.mark.benchmark(group="async")
    def test_async_operation(self, benchmark):
        """Benchmark async operation."""
        async def operation():
            await some_async_function()
        
        def run():
            asyncio.run(operation())
        
        benchmark(run)
```

### Parametrized Benchmark

```python
import pytest

@pytest.mark.parametrize("size", [10, 100, 1000, 10000])
def test_scaling(benchmark, size):
    """Benchmark with different input sizes."""
    data = list(range(size))
    
    def operation():
        return sum(data)
    
    benchmark(operation)
```

## Troubleshooting

### "Benchmarks are automatically disabled because xdist plugin is active"

**Solution**: Disable xdist when running benchmarks:

```bash
pytest benchmarks/ --benchmark-only -p no:xdist -o addopts=""
```

### "Can't have both --benchmark-only and --benchmark-disable"

**Solution**: Override pytest.ini settings:

```bash
pytest benchmarks/ --benchmark-only -p no:xdist -o addopts=""
```

### Inconsistent Results

**Solutions**:
1. Close other applications
2. Disable CPU frequency scaling
3. Run multiple times and compare
4. Use `--benchmark-warmup=on`

```bash
pytest benchmarks/ --benchmark-only -p no:xdist \
  -o addopts="" --benchmark-warmup=on --benchmark-min-rounds=100
```

## Reference

### Command Line Options

```bash
pytest benchmarks/ --benchmark-only \
  -p no:xdist \                    # Disable parallel execution
  -o addopts="" \                  # Override pytest.ini
  --benchmark-warmup=on \          # Enable warmup
  --benchmark-min-rounds=100 \     # Minimum iterations
  --benchmark-max-time=2.0 \       # Max time per benchmark
  --benchmark-columns=min,max,mean,median,ops \  # Output columns
  --benchmark-sort=mean \          # Sort by mean time
  --benchmark-group-by=group \     # Group by @pytest.mark.benchmark(group=)
  --benchmark-autosave \           # Save results
  --benchmark-compare \            # Compare with saved
  --benchmark-json=results.json    # Export JSON
```

### Available Benchmark Groups

- `metrics` - RED metrics operations
- `gauge` - Gauge operations
- `counter` - Counter operations
- `histogram` - Histogram operations
- `correlation` - Correlation ID operations
- `correlation_context` - Context manager operations
- `contextvars_raw` - Raw contextvars overhead
- `circuit_breaker` - Circuit breaker checks
- `circuit_breaker_record` - Circuit breaker recording
- `circuit_breaker_decorator` - Decorated function overhead
- `logging` - Structured logging operations

