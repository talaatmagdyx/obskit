# obskit Benchmarking Strategy

This document explains **why** each benchmarking decision was made, so results are
reproducible, comparable, and trustworthy.  Read this before running benchmarks for
the first time or interpreting results.

---

## 1. Why Two Benchmark Types?

obskit adds overhead on *every instrumented request*.  A single slow function in the
hot path appears directly in service tail latency.  Two benchmark types are needed
because they answer different questions:

| Type | Question | File(s) |
|------|----------|---------|
| **Microbenchmark** | "How fast is primitive X in isolation?" | `bench_*.py` (pytest-benchmark) |
| **Macrobenchmark** | "What is total overhead under production-like load?" | `macro_runner.py` |

Microbenchmarks find *where* time goes.  Macrobenchmarks tell you *how much* it
matters end-to-end.  Neither alone is sufficient:

- A microbenchmark that says `CircuitBreaker.__enter__` costs 2 µs says nothing
  about the total cost when it is composed with logging, metrics, and SLO tracking.
- A macrobenchmark that says p99 = 180 µs says nothing about which component is
  responsible for the tail.

---

## 2. Core Primitives Chosen for Microbenchmarks

Each benchmark file targets one subsystem that is on the critical path of every
instrumented request:

| File | Primitive | Why it matters |
|------|-----------|---------------|
| `bench_observability.py` | `with_observability` decorator | **Primary hot path** — composes all other primitives; any regression here adds directly to request latency |
| `bench_slo.py` | `SLOTracker.record_measurement` | Called per request; uses a lock + list; lock contention under concurrency is a real risk |
| `bench_metrics.py` | `REDMetrics.observe_request` | Prometheus counter/histogram update; label lookup is O(1) but with dict overhead |
| `bench_circuit_breaker.py` | `CircuitBreaker.__enter__/__exit__` | RLock acquire/release on every request; must be sub-microsecond in closed state |
| `bench_logging.py` | `logger.info()` | structlog pipeline runs twice per decorated call (start + end); in-band I/O is a latency risk |
| `bench_context.py` | `ContextVar.get/set` | Called on every request for correlation ID; raw `ContextVar` is the baseline |

---

## 3. Data Generation Plan

### 3.1 Tenant distribution — Zipf (α = 1.3, n = 1 000)

Real-world multi-tenant systems follow a heavy-tail distribution: a few tenants
generate the vast majority of traffic.  A uniform distribution underestimates
hot-path cache effects and metric cardinality.

**Zipf with α = 1.3** models this accurately:
- Tenant 1 receives ~28 % of all requests
- Top 10 tenants receive ~70 % of requests
- The long tail (tenants 100–1 000) represents rare customers

This matters for obskit because:
- Prometheus labels for hot tenants are cached in `_metrics` dicts after the first
  call — uniform distribution would never stress the slow path (first-time label
  registration).
- The `CardinalityProtector` is only triggered when new unique labels arrive — Zipf
  means most requests hit cached labels (fast path), while occasional tail requests
  hit new labels (slow path).  Both paths must be benchmarked.

```python
# Implementation in macro_runner.py
def _zipf_tenant(n: int = 1000, alpha: float = 1.3) -> str:
    ...
```

**Worst case** (`high_cardinality` scenario): every request uses a unique label —
exercises the slow path exclusively.  Run separately with fewer requests (n/10) and
single worker because it is intentionally pathological.

### 3.2 Request latency — Lognormal (μ = 50 ms, σ = 0.5)

Service request latencies are **not normally distributed**.  They are right-skewed:
most requests are fast, but occasional slow requests (GC pauses, lock contention,
cold caches) create a long right tail.

Lognormal (σ = 0.5, which gives a coefficient of variation ≈ 0.53) accurately
reproduces this shape without requiring a real service.  It is the standard model
used in queuing theory for web service latencies.

This matters for SLO benchmarks: a normal distribution would give an artificially
optimistic view of window eviction frequency and budget burn rate.

```python
def _lognormal_latency(mean_s: float = 0.05, sigma: float = 0.5) -> float:
    mu = math.log(mean_s) - 0.5 * sigma ** 2
    return math.exp(random.gauss(mu, sigma))
```

**Worst case**: fixed latency above the SLO threshold — stresses the "breach" code
path and eviction logic continuously.

### 3.3 Error rate — 2 % baseline, 0 % for overhead scenarios

2 % error injection models a degraded-but-operational service.  Overhead scenarios
(measuring pure obskit cost) use 0 % errors to isolate the instrumentation cost from
any conditional error-path logic.

---

## 4. Warmup Strategy

### Why warmup matters

CPython's adaptive bytecode specialisation (3.11+) and its module/object caches,
along with OS-level effects (cold TLB, cold instruction cache, lazy module imports,
pydantic model compilation, Prometheus metric dict population) all inflate the first
N calls.  (PyPy users additionally benefit from JIT compilation warming up.)
Including them in measurements produces artificially high mean and p99 values that
are not representative of steady-state production.

### What warmup covers in obskit

| Effect | Warmed up by |
|--------|-------------|
| Module import time | First call to `configure()` and `reset_*` |
| pydantic model compilation (`ObskitSettings`) | First `configure()` call |
| Prometheus metric dict population (first label) | First `observe_request()` call |
| structlog pipeline compilation | First `logger.info()` call |
| Thread pool startup overhead | First request through `ThreadPoolExecutor` |
| OS page faults (cold heap pages) | First N allocations |
| CPython function object caching | First N calls to decorated function |

### Warmup parameters

| Benchmark type | Warmup approach | Rounds |
|---------------|----------------|--------|
| pytest-benchmark | `--benchmark-warmup=on` (auto) | 5 rounds or until stable |
| macro_runner.py | Explicit warmup block before timing starts | `min(50, n // 10)` requests |
| bench_memory.py | 100–200 explicit noop calls before `tracemalloc.start()` | 100–200 |

### Excluding warmup from results

In `macro_runner.py`, the warmup `ThreadPoolExecutor` block runs and its results are
discarded.  `gc.collect()` is called after warmup and before the timed block to
ensure the GC is in a clean state and will not run during measurement.

---

## 5. Environment Isolation

### 5.1 CPU frequency scaling

Modern CPUs dynamically adjust clock speed (Intel SpeedStep, AMD Cool'n'Quiet,
ARM DVFS).  A benchmark run that starts cold may run at 1.2 GHz and gradually
ramp to 3.8 GHz, producing a downward latency trend that is an artefact of the
hardware, not the code.

```bash
# Linux: set performance governor (disables frequency scaling)
sudo cpupower frequency-set -g performance

# Verify
cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
# Should print: performance  (×N cores)

# Restore after benchmarking
sudo cpupower frequency-set -g powersave
```

On macOS, frequency scaling is managed by the OS and cannot be disabled; results will
have higher variance.  On Apple Silicon, use Activity Monitor to confirm the process
runs on Performance cores (P-cores), not Efficiency cores (E-cores).

### 5.2 CPU pinning

Even with frequency scaling disabled, OS scheduler preemption and NUMA effects add
jitter.  Pinning the benchmark to a single core eliminates scheduler-induced variance.

```bash
# Linux: pin to core 2 (avoid core 0, which handles interrupts)
taskset -c 2 python benchmarks/macro_runner.py --scenario full_stack

# Verify the process stays on core 2
watch -n 0.5 "ps -o pid,psr -p $(pgrep -f macro_runner)"
```

Multi-worker macrobenchmarks should use a contiguous range of physical cores (not
hyperthreads of the same core):

```bash
# 8 physical cores, no hyperthreading cross-contamination
taskset -c 2-9 python benchmarks/macro_runner.py --workers 8
```

### 5.3 Process isolation

Background processes add random latency spikes (GC in another process, browser
JavaScript, system daemons).  Before running a benchmark session:

```bash
# Check for CPU-hungry processes
# Linux (batch mode, single snapshot):
top -b -n 1 | head -20
# macOS:
top -l 1 | head -20

# Recommended: disable
# - Browsers (Chrome, Firefox)
# - Slack, Teams, Zoom
# - IDE indexers (JetBrains, VS Code)
# - Spotlight / locate / updatedb
# - Dropbox, OneDrive sync
# - Docker Desktop (significant background CPU)

# On Linux servers, also stop:
sudo systemctl stop cron
sudo systemctl stop snapd   # if not needed
```

### 5.4 ASLR and transparent huge pages

Address Space Layout Randomisation (ASLR) changes memory layout between runs, which
can affect cache performance.  For maximum reproducibility on Linux:

```bash
# Disable ASLR for this session only
echo 0 | sudo tee /proc/sys/kernel/randomize_va_space

# Disable transparent huge pages (reduces p99 variance from THP collapse)
echo never | sudo tee /sys/kernel/mm/transparent_hugepage/enabled

# Restore after session
echo 2 | sudo tee /proc/sys/kernel/randomize_va_space
echo madvise | sudo tee /sys/kernel/mm/transparent_hugepage/enabled
```

---

## 6. Repeat Runs and Statistics

### How many runs are enough?

A single benchmark run produces one number, which may be dominated by a GC pause,
OS scheduler preemption, or a thermal throttle event.  The minimum acceptable
sample is:

| Scenario | Minimum rounds | Why |
|----------|---------------|-----|
| Microbenchmark (pytest-benchmark) | 50 | pytest-benchmark auto-computes; use `--benchmark-min-rounds=50` |
| Macro run (macro_runner.py) | 10 000 requests | Reliable p99 needs ≥ 100/(1−p) samples: 100/0.01 = 10 000 |
| Memory benchmark | 1 run | tracemalloc is deterministic; GC noise handled by explicit `gc.collect()` |

For p99 reliability: you need at least **100 / (1 − 0.99) = 10 000 samples** for
a stable p99.  At p999 you need 100 / 0.001 = 100 000.  Use `--requests 10000`
minimum for p99 comparison; do not report p999 for runs < 100 000.

### Which statistic to use for go/no-go?

| Statistic | Use for | Do not use for |
|-----------|---------|---------------|
| `min` | Theoretical floor; best-case hardware cost | Capacity planning |
| `median` (p50) | Typical steady-state latency | Tail analysis |
| `p95` / `p99` | SLA thresholds; go/no-go gate | Development iteration (too noisy at low N) |
| `mean` | Regression detection in CI (`--benchmark-compare`) | Anything with outliers (mean is non-robust) |
| `stddev` | Jitter indicator; high stddev → GC or lock contention | Absolute latency comparison |
| `max` | Worst observed; GC pause detector | Anything (too sensitive to outliers) |

**Rule**: gate go/no-go on **p99**, not mean.  Mean hides tail behaviour.  Use
mean only for CI regression detection (it is more stable across small sample sizes).

### How to run a valid A/B comparison

```bash
# Step 1: Save baseline (main branch)
git checkout main
pytest benchmarks/ --benchmark-only -p no:xdist -o addopts="" \
  --benchmark-json=results/baseline.json

# Step 2: Run candidate (your branch)
git checkout feature/my-optimization
pytest benchmarks/ --benchmark-only -p no:xdist -o addopts="" \
  --benchmark-json=results/candidate.json

# Step 3: Compare
pytest-benchmark compare results/baseline.json results/candidate.json \
  --group-by=name --sort=name

# Step 4: Fail CI if mean regresses > 10%
pytest benchmarks/ --benchmark-only -p no:xdist -o addopts="" \
  --benchmark-compare=results/baseline.json \
  --benchmark-compare-fail=mean:10%
```

**Critical**: run A and B on the same machine, same OS state, same core pinning.
Even different runs on the same machine introduce ±5 % variance.  A/B results from
different machines are meaningless.

---

## 7. Benchmark Suite Map

```
benchmarks/
├── bench_observability.py   ← MOST IMPORTANT: full decorator hot path
│                              Groups: observability, observability_baseline, observability_slo
├── bench_slo.py             ← SLO tracker hot path + eviction + concurrency
│                              Groups: slo, slo_eviction, slo_concurrent
├── bench_metrics.py         ← Prometheus RED metrics hot path
│                              Groups: metrics
├── bench_circuit_breaker.py ← Circuit breaker state machine
│                              Groups: circuit_breaker
├── bench_logging.py         ← structlog pipeline cost
│                              Groups: logging
├── bench_context.py         ← ContextVar correlation ID
│                              Groups: context
├── bench_memory.py          ← Standalone: tracemalloc per-call allocation + leak detector
│                              Run: python benchmarks/bench_memory.py
├── macro_runner.py          ← Standalone: p50/p95/p99/p999 under Zipf+lognormal load
│                              Run: python benchmarks/macro_runner.py [--scenario X]
├── BENCHMARKING_STRATEGY.md ← This file
├── PROFILING_PLAYBOOK.md    ← Tool selection, interpretation, optimisations
├── go_no_go.md              ← Metrics checklist + fillable threshold table
└── README.md                ← Quick-start and CI integration
```

---

## 8. What Good Results Look Like

### Micro (pytest-benchmark, single core, warm)

> **Note**: numbers below are illustrative reference values only — actual results
> depend on hardware, Python version, and OS state.  Run the benchmarks on your
> own machine to establish the real baseline.

```
Name                                           Min        Mean      Median      Stddev     OPS
test_sync_noop (with_observability)           18 µs      22 µs      20 µs       4 µs     45 455
test_record_latency_fast (SLOTracker)          1.2 µs     1.5 µs     1.3 µs     0.2 µs  666 666
test_circuit_breaker_closed                   0.8 µs     1.0 µs     0.9 µs     0.1 µs 1 000 000
```

- **Min ≈ Median**: no GC jitter, no lock contention — healthy.
- **Stddev < 20 % of median**: acceptable noise for a multithreaded benchmark.
- **Stddev > 50 % of median**: GC is running during measurement, or lock contention;
  re-run with `gc.disable()` temporarily to diagnose.

### Macro (macro_runner.py, 16 workers, 10 000 requests)

> **Note**: numbers below are illustrative reference values only.

```
Scenario            p50    p95    p99   p999    rps     RSS Δ   peak_alloc
metrics_only         8 µs   18 µs   32 µs   95 µs  82 000    +2 MB    1.2 MB
logging_only        22 µs   48 µs   78 µs  210 µs  31 000    +1 MB    0.8 MB
circuit_breaker      2 µs    4 µs    7 µs   22 µs 210 000    +0 MB    0.1 MB
slo_only             3 µs    7 µs   12 µs   38 µs 140 000    +1 MB    0.5 MB
full_stack          35 µs   82 µs  145 µs  420 µs  18 000    +4 MB    2.1 MB
```

Red flags:
- **p999 >> 10× p99**: indicates occasional GC full collection during requests.
  Profile with `py-spy record --gil -o /tmp/obs_gil.svg -- python benchmarks/macro_runner.py`
  to confirm threads are waiting on the GIL.
- **RSS Δ growing** between repeated runs: memory leak.
  Run `bench_memory.py::bench_leak_detector`.
- **rps lower than single-worker × workers**: Python-level lock contention.
  Use the regular flamegraph (`py-spy record -o /tmp/obs.svg`) and look for wide
  `threading.RLock.acquire` blocks — that indicates Python lock contention, not GIL.

---

## 9. Checklist Before Publishing Results

- [ ] `cpupower frequency-set -g performance` (Linux) or confirmed P-core usage (macOS)
- [ ] `taskset -c 2` (or equivalent core pinning)
- [ ] All browsers, Slack, Docker Desktop closed
- [ ] `--benchmark-warmup=on` for pytest-benchmark; explicit warmup block for macro_runner
- [ ] `--benchmark-disable-gc` added for microbenchmarks to prevent GC runs mid-measurement
- [ ] Minimum 10 000 requests for stable p99; minimum 50 rounds for micro
- [ ] Baseline and candidate run on the same machine in the same session
- [ ] `gc.collect()` called before each timed block
- [ ] Results saved as JSON (`--benchmark-json` / `--output`) for diffing
- [ ] Python version recorded (`python --version`) — results are not comparable across major versions
- [ ] `python -m ruff check benchmarks/ src/obskit/` passes before benchmarking
  (avoid profiling code with known bugs)
