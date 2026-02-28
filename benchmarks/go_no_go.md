# obskit Performance: Metrics Checklist & Go/No-Go Template

Fill in the **Measured** column after each benchmark run.
A scenario is **GO** only when every metric in its row passes.

---

## Section 1 — Metrics Capture Checklist

Run this checklist before committing a release or merging a PR that touches a hot path.

### 1.1 Micro-benchmarks (pytest-benchmark)

```bash
pytest benchmarks/ --benchmark-only -p no:xdist -o addopts="" \
  --benchmark-columns=min,mean,median,stddev,ops \
  --benchmark-json=results/$(git rev-parse --short HEAD).json
```

Capture these columns for every benchmark:

| Metric | Tool | Notes |
|--------|------|-------|
| `min` latency (µs) | pytest-benchmark | Best-case; used for go/no-go threshold |
| `mean` latency (µs) | pytest-benchmark | Typical cost |
| `median` (p50) latency (µs) | pytest-benchmark | Robust central tendency |
| `stddev` (µs) | pytest-benchmark | High stddev → GC or lock jitter |
| `ops` (req/s) | pytest-benchmark | Throughput; compare to rps_min threshold |

### 1.2 Macro-benchmarks (macro_runner.py)

```bash
python benchmarks/macro_runner.py --requests 10000 --workers 16 \
  --output results/macro_$(git rev-parse --short HEAD).json
```

Capture per scenario:

| Metric | Description |
|--------|-------------|
| `p50` latency (µs) | Median request cost |
| `p95` latency (µs) | Near-tail; SLA-relevant |
| `p99` latency (µs) | **Primary go/no-go metric** |
| `p999` latency (µs) | Extreme tail; watch for GC pauses |
| `max` latency (µs) | Worst single request |
| `stdev` (µs) | High → jitter from GC / lock |
| `throughput_rps` | Requests per second at `--workers` |
| `error_rate_pct` | Must be 0 % for obskit overhead scenarios |

### 1.3 Memory (bench_memory.py)

```bash
python benchmarks/bench_memory.py 2>&1 | tee results/memory_$(git rev-parse --short HEAD).txt
```

| Metric | Description |
|--------|-------------|
| Per-call net allocation (KiB) — `with_observability` | Allocation delta for 1 000 calls divided by 1 000 |
| SLO window growth (KiB / 10 k records) | 1-hour window should grow linearly; 0 s window should stay flat |
| Logger `bind()` allocation (KiB / 1 k calls) | Each `bind()` creates a new dict |
| Prometheus cardinality growth (KiB / 500 tenants) | Each unique label set → new TimeSeries object |
| Leak-detector delta (objects) | Must be < 5 % × n_requests |

### 1.4 System-level metrics (capture during macro run)

Capture these with an external tool (e.g. `psutil`, `vmstat`, `dstat`) during `macro_runner.py`:

| Metric | Tool | Notes |
|--------|------|-------|
| CPU % (per core) | `psutil.cpu_percent(percpu=True)` | Should not saturate a single core |
| RSS delta (KB) | `/proc/<pid>/status` VmRSS or `resource.getrusage` | Captured by macro_runner automatically |
| Peak heap allocation (KB) | `tracemalloc.get_traced_memory()[1]` | Captured by macro_runner automatically |
| GC collection count | `gc.get_count()` before/after | Excessive gen-2 collections add p999 jitter |
| Context switches (voluntary) | `/proc/<pid>/status` VCS / `resource.ru_nvcsw` | High → lock contention |
| Context switches (involuntary) | `/proc/<pid>/status` IVCS / `resource.ru_nivcsw` | High → CPU saturation / preemption |
| Syscall count | `strace -c -p <pid>` (Linux) | High write syscalls → unbuffered log sink |

---

## Section 2 — Go/No-Go Threshold Template

### How to use

1. Run benchmarks and fill in the **Measured** columns.
2. Mark each row GO (✓) or NO-GO (✗).
3. All rows must be GO before releasing.
4. If any row is NO-GO, open a performance regression issue and block the merge.

---

### 2.1 Micro-benchmark thresholds

_pytest-benchmark, single-threaded, no-op or trivial workload._

| Benchmark | Threshold (min µs) | Threshold (ops/s) | Measured min (µs) | Measured ops/s | Status |
|-----------|-------------------|-------------------|-------------------|----------------|--------|
| `test_sync_noop` (with_observability) | ≤ 50 µs | ≥ 20 000 | | | |
| `test_async_noop` (with_observability) | ≤ 50 µs | ≥ 20 000 | | | |
| `test_sync_with_exception` | ≤ 100 µs | ≥ 10 000 | | | |
| `test_decorator_stack_depth_3` | ≤ 150 µs | ≥ 6 000 | | | |
| `test_record_latency_fast` (SLO) | ≤ 5 µs | ≥ 200 000 | | | |
| `test_record_latency_slow` (SLO) | ≤ 5 µs | ≥ 200 000 | | | |
| `test_get_status_full_window` (SLO) | ≤ 20 µs | ≥ 50 000 | | | |
| `test_record_with_full_eviction` (SLO) | ≤ 10 µs | ≥ 100 000 | | | |
| `test_record_from_16_threads` (SLO) | ≤ 500 µs batch | ≥ 500 | | | |
| Circuit breaker `__enter__` (closed) | ≤ 2 µs | ≥ 500 000 | | | |
| Circuit breaker `__enter__` (open) | ≤ 1 µs | ≥ 1 000 000 | | | |
| Structured log `.info()` | ≤ 20 µs | ≥ 50 000 | | | |
| Correlation ID `set` + `get` | ≤ 1 µs | ≥ 1 000 000 | | | |
| RED metrics `observe_request` | ≤ 5 µs | ≥ 200 000 | | | |

---

### 2.2 Macro-benchmark thresholds

_`macro_runner.py`, 10 000 requests, 16 workers, Zipf tenant + lognormal latency._

| Scenario | p99 budget (µs) | rps_min | error_rate | Measured p99 | Measured rps | Status |
|----------|----------------|---------|-----------|--------------|--------------|--------|
| `metrics_only` | ≤ 50 | ≥ 50 000 | 0 % | | | |
| `logging_only` | ≤ 100 | ≥ 20 000 | 0 % | | | |
| `circuit_breaker_only` | ≤ 10 | ≥ 200 000 | 0 % | | | |
| `slo_only` | ≤ 20 | ≥ 100 000 | 0 % | | | |
| `full_stack` | ≤ 200 | ≥ 10 000 | 0 % | | | |
| `high_cardinality` (500 req, 1 worker) | ≤ 500 | ≥ 1 000 | 0 % | | | |

---

### 2.3 Memory thresholds

| Metric | Threshold | Measured | Status |
|--------|-----------|----------|--------|
| Per-call net alloc — `with_observability` (1 k calls) | ≤ 2 KiB total (≤ 2 B/call) | | |
| SLO 1-hour window growth (10 k records) | ≤ 5 MB | | |
| SLO 0 s window (10 k records, full eviction) | ≤ 500 KB | | |
| Logger `bind()` + `.info()` (1 k calls) | ≤ 500 KB | | |
| Prometheus cardinality (500 unique labels) | ≤ 10 MB | | |
| Leak detector delta (5 k requests after warmup) | < 250 objects (5 % × 5 000) | | |

---

### 2.4 System-level thresholds

_Measured during `macro_runner.py --requests 10000 --workers 16 --scenario full_stack`._

| Metric | Threshold | Measured | Status |
|--------|-----------|----------|--------|
| Peak RSS delta (MB) | ≤ 50 MB above baseline | | |
| CPU % single core | ≤ 90 % (no single core saturated) | | |
| GC gen-2 collections during run | ≤ 5 | | |
| Voluntary context switches / req | ≤ 2 | | |
| Involuntary context switches / req | ≤ 1 | | |

---

## Section 3 — Regression Detection in CI

Add to `.github/workflows/bench.yml` (or equivalent):

```yaml
name: Performance regression check
on: [pull_request]

jobs:
  bench:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install deps
        run: pip install -e ".[dev]" pytest-benchmark

      - name: Run micro-benchmarks
        run: |
          pytest benchmarks/ --benchmark-only -p no:xdist -o addopts="" \
            --benchmark-json=results/bench_pr.json \
            --benchmark-compare=results/bench_main.json \
            --benchmark-compare-fail=mean:10%   # fail if mean regresses > 10%

      - name: Run macro-benchmark go/no-go
        run: |
          python benchmarks/macro_runner.py \
            --requests 5000 --workers 8 \
            --output results/macro_pr.json
          # Exit code 0 = all GO; non-zero = at least one NO-GO (macro_runner prints verdict)
```

**Regression policy**

| Delta vs baseline | Action |
|-------------------|--------|
| < 5 % slower | Acceptable noise — auto-merge |
| 5 – 10 % slower | Review required — explain in PR |
| > 10 % slower | Block merge — mandatory perf investigation |
| Any NO-GO in macro | Block merge — mandatory perf investigation |
| Leak detector FAIL | Block merge — memory leak must be fixed |

---

## Section 4 — Quick Reference Card

```
Before benchmarking:
  sudo cpupower frequency-set -g performance   # disable CPU throttling (Linux)
  taskset -c 2 python benchmarks/macro_runner.py   # pin to core 2

Micro (pytest-benchmark):
  pytest benchmarks/ --benchmark-only -p no:xdist -o addopts="" \
    --benchmark-warmup=on --benchmark-min-rounds=50

Macro (standalone):
  python benchmarks/macro_runner.py --requests 10000 --workers 16 --output results.json

Memory (standalone):
  python benchmarks/bench_memory.py

Profile sync noop regression:
  python -m cProfile -o /tmp/obs.prof -c "
    import sys; sys.stderr = open('/dev/null','w')
    from obskit.config import configure; from obskit.decorators.combined import with_observability
    from obskit.metrics.registry import reset_registry
    configure(service_name='p', log_level='WARNING', log_format='json'); reset_registry()
    @with_observability(component='p')
    def f(): return 42
    [f() for _ in range(20_000)]
  "
  python -m snakeviz /tmp/obs.prof

Profile live production process:
  py-spy record -o /tmp/obs.svg --pid <PID> --duration 30
  # open /tmp/obs.svg in browser
```
