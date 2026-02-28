# obskit Profiling Playbook

A decision-driven guide: choose the right tool for the symptom, then act on what you see.

---

## 1. Tool Selection Matrix

| Symptom | First tool | Why |
|---------|-----------|-----|
| "Which function is slow?" (development) | `cProfile` + `snakeviz` | Low friction, stdlib, deterministic |
| "p99 spiked in production" | `py-spy` | Attaches to live PID, zero restart |
| "CPU % is high but no obvious bottleneck" | `scalene` | Line-level CPU + memory + native |
| "Memory grows over time" | `tracemalloc` / `memray` | Captures allocation site, not just live objects |
| "Lock contention / GIL saturation" | `py-spy --gil` | Shows % time waiting for GIL |
| "Which C extension is burning time?" | `scalene` or `py-spy --native` | Native frame unwinding |
| "Request tail latency is bimodal" | `py-spy` (flame graph) | Separates hot paths visually |

---

## 2. Tool Reference

### 2.1 `cProfile` (stdlib)

**Best for**: development-time profiling of a known code path; reproducible, deterministic call counts.

**Overhead**: ~10–30 % CPU (not safe for production load).

```bash
# Profile the macro runner, dump to file
python -m cProfile -o /tmp/obskit.prof benchmarks/macro_runner.py --scenario full_stack

# Visualise interactively
pip install snakeviz
snakeviz /tmp/obskit.prof

# Or print top-20 by cumulative time
python -c "
import pstats, io
s = pstats.Stats('/tmp/obskit.prof', stream=io.StringIO())
s.sort_stats('cumulative').print_stats(20)
print(s.stream.getvalue())
"
```

**Reading the output**

| Column | Meaning | Action trigger |
|--------|---------|----------------|
| `ncalls` | Total call count | Unexpectedly high → cache or batch |
| `tottime` | Time in function body (excludes callees) | High → algorithmic issue in that function |
| `cumtime` | Time including all callees | High → hot call chain, dig deeper |
| `percall` (cum) | Per-call cost | Multiply by request rate to get p99 budget |

**What optimisations look like**

- `tottime` high on `dict.__setitem__` / `list.append` → reduce per-request allocations
- `tottime` high on `threading.RLock.acquire` → reduce lock scope or use lock-free structures
- `cumtime` high on `logging` → lower log level or batch writes
- `ncalls` >> expected → missing memoisation or cache invalidation bug

---

### 2.2 `py-spy` (sampling, live attach)

**Best for**: production profiling without restart; finding the p99 call stack under real load.

**Overhead**: ~1 % CPU (sampling profiler; safe for production at default 100 Hz).

```bash
pip install py-spy

# Flame graph of a running process (.svg → flamegraph format by default)
# Note: --pid requires sudo on Linux (ptrace restriction); launching a new process does not
sudo py-spy record -o /tmp/obskit.svg --pid $(pgrep -f macro_runner) --duration 30

# Record while launching a fresh process (no sudo needed)
py-spy record -o /tmp/obskit.svg -- python benchmarks/macro_runner.py --scenario full_stack

# Interactive speedscope output (open at https://www.speedscope.app — supports zoom/search)
py-spy record --format speedscope -o /tmp/obskit.json -- python benchmarks/macro_runner.py --scenario full_stack

# Top-like live view
py-spy top --pid $(pgrep -f macro_runner)

# Show GIL contention (threads waiting for GIL)
sudo py-spy record -o /tmp/obskit_gil.svg --gil --pid $(pgrep -f macro_runner) --duration 30
```

**Reading the flame graph**

- Width = cumulative time; tall = many frames; wide+short = leaf hotspot.
- Look for a **wide plateau** near the bottom — that is your dominant hot path.
- GIL flame graph: wide blocks of `waiting for GIL` → add multiprocessing or release GIL in C extension.

**Common findings for obskit**

| Flame width | Likely cause | Fix |
|-------------|-------------|-----|
| `structlog` pipeline | Log level filter not short-circuiting | Raise log_level to WARNING in prod |
| `prometheus_client` label lookup | High cardinality exploding `_metrics` dict | Enforce cardinality limit (already in `CardinalityProtector`) |
| `threading.RLock.acquire` | Lock contention under load | Profile lock hold time; consider `threading.local` caches |
| `copy.deepcopy` | Unexpected object copying in hot path | Replace with shallow copy or struct sharing |

---

### 2.3 `scalene` (CPU + memory + native, line-level)

**Best for**: attributing CPU time to specific lines and distinguishing Python vs native vs system time; also catches per-line allocations.

**Overhead**: ~5–10 % CPU; safe for development, borderline for production.

```bash
pip install scalene

# Profile a script, open HTML report in browser
# Use -- to separate scalene flags from the script's own arguments
scalene benchmarks/macro_runner.py -- --scenario metrics_only

# JSON output for CI diffing (-o is the correct flag; --outfile does not exist)
scalene --json -o /tmp/scalene.json -- benchmarks/macro_runner.py

# Focus on a single module (--profile-only matches against file path substrings)
scalene --cpu-only --profile-only src/obskit/metrics/red.py -- benchmarks/macro_runner.py
```

**Reading the HTML report**

| Column | Meaning |
|--------|---------|
| `%CPU (Python)` | Time executing Python bytecode on this line |
| `%CPU (native)` | Time in C/C++ extensions called from this line |
| `%CPU (system)` | Time in OS calls (I/O, syscalls) |
| `Memory (Python)` | Python heap allocations on this line |
| `Memory (native)` | Native heap allocations (e.g. numpy) |
| `Copy (MB/s)` | Memory bandwidth (high → unnecessary data movement) |

**Interpretation shortcuts**

- High `%CPU (native)` on a line calling `prometheus_client` → the C extension is the bottleneck; check label cardinality.
- High `Memory (Python)` on `logger.bind(...)` → structlog creates a new dict per call; consider pre-binding common fields.
- High `%CPU (system)` → I/O or syscall; check if log output is going to a blocking sink.

---

### 2.4 `tracemalloc` (stdlib allocation tracing)

**Best for**: finding which call site allocates the most memory; comparing before/after states; CI leak detection.

```python
import tracemalloc, gc

gc.collect()
tracemalloc.start(25)          # 25-frame traceback depth
snapshot_before = tracemalloc.take_snapshot()

# ... run N requests ...

snapshot_after = tracemalloc.take_snapshot()
tracemalloc.stop()

stats = snapshot_after.compare_to(snapshot_before, "lineno")
for s in stats[:10]:
    print(s)
```

**Run the bundled memory benchmark**

```bash
python benchmarks/bench_memory.py
```

**Interpretation**

- `size_diff > 0` lines are net allocations. Sort by `size_diff` descending.
- A line with `size_diff` proportional to `n_requests` is a **per-request leak candidate**.
- After warmup, a fixed `size_diff` is expected (caches, singletons); a growing one is a bug.
- Use `traceback.format()` to navigate to the exact allocation site.

---

### 2.5 `memray` (binary allocation tracing, flamegraphs)

**Best for**: production-grade memory profiling with flamegraphs; identifies allocations by call site across C extensions.

```bash
pip install memray

# Record allocations to a binary file
python -m memray run -o /tmp/obskit.bin benchmarks/bench_memory.py

# Generate HTML flamegraph
python -m memray flamegraph /tmp/obskit.bin -o /tmp/obskit_memory.html

# Generate allocation table
python -m memray table /tmp/obskit.bin
```

---

## 3. Decision Flow

```
Is the issue CPU or memory?
├── CPU
│   ├── Development / reproducible path?  →  cProfile + snakeviz
│   ├── Production / live PID?           →  py-spy record -o obs.svg   (flamegraph is the default)
│   └── Line-level attribution needed?   →  scalene
└── Memory
    ├── Which call site allocates?        →  tracemalloc / bench_memory.py
    ├── Per-call allocation regression?   →  bench_memory.py::bench_decorator_alloc
    ├── Leak over time?                   →  bench_memory.py::bench_leak_detector
    └── Native allocations / flamegraph?  →  memray
```

---

## 4. Likely Optimisations by Finding

### 4.1 Algorithmic (CPU-bound)

| Finding | Candidate fix |
|---------|--------------|
| `O(n)` scan inside hot path | Replace with dict / set lookup |
| Repeated `sorted()` on same list | Cache sort or use `heapq` |
| `json.dumps` per log call | Pre-serialise static fields; only serialise dynamic part |
| `re.compile` inside loop | Compile at module load |
| SLO window eviction scanning entire list | Bisect to find cutoff index |

### 4.2 I/O-bound

| Finding | Candidate fix |
|---------|--------------|
| Log writes to unbuffered sink | Use `logging.handlers.MemoryHandler` (batch) |
| Prometheus `/metrics` scrape blocks | Use `multiprocess` mode; separate scrape process |
| Health-check HTTP call on hot path | Cache result; use async health aggregator |

### 4.3 Allocation-bound

| Finding | Candidate fix |
|---------|--------------|
| New `dict` per `logger.bind()` call | Pre-bind static fields at startup; share bound logger |
| New `list` per SLO window eviction | Use `collections.deque(maxlen=N)` |
| `str` formatting in suppressed log | Pass lazy callables: `logger.debug("e", val=lambda: compute())` — structlog evaluates them only when the log is emitted |
| `tuple` allocation inside `labels()` | Cache `prometheus_client` metric handles |

### 4.4 Lock-contention-bound (GIL / threading)

| Finding | Candidate fix |
|---------|--------------|
| Wide GIL blocks in py-spy | Move CPU work to `ProcessPoolExecutor` |
| `RLock.acquire` dominant in profile | Reduce lock scope; use per-request local objects |
| `threading.local` not used for caches | Add `threading.local()` for per-thread metric caches |

---

## 5. Benchmark → Profiler Integration

```bash
# 1. Run micro-benchmarks to find regression
pytest benchmarks/ --benchmark-only -p no:xdist -o addopts="" --benchmark-compare

# 2. Identify the slow test (e.g. test_sync_noop)
#    then profile just that scenario:
python -m cProfile -o /tmp/obs.prof -c "
from obskit.config import configure, reset_settings
from obskit.decorators.combined import with_observability
from obskit.metrics.registry import reset_registry
configure(service_name='prof', log_level='WARNING', log_format='json')
reset_registry()
@with_observability(component='prof')
def noop(): return 42
for _ in range(10_000): noop()
"
snakeviz /tmp/obs.prof

# 3. For production tail-latency spikes:
py-spy record -o /tmp/obs.svg -- python benchmarks/macro_runner.py --scenario full_stack --requests 50000
```
