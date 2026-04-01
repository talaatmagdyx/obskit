# obskit — Runtime Performance Audit

**Date:** 2026-04-01
**Analyst role:** Senior Python Performance Engineer & Runtime Analysis Specialist
**Python:** 3.13 (darwin arm64)
**Methodology:** cProfile (cumulative sort) + `time.perf_counter_ns` micro-benchmarks + `tracemalloc` heap snapshots

---

## A. Executive Summary

Four actionable performance issues were found through profiling across 12 hot-path benchmarks.
One is **Critical** (1.88 ms per SLO status read at steady state), two are **High** (O(n) generator
in every log-redaction check; O(n) redundant `rstrip` in path exclusion), and one is **Medium**
(unnecessary UUID4 allocation on every correlation-ID miss).  Library-level bottlenecks
(prometheus-client `labels()`, structlog JSON renderer) are documented but out-of-scope for direct
fix.

| ID | Severity | Hot path | Measured cost | Fix |
|----|----------|----------|---------------|-----|
| C1 | Critical  | `SLOTracker.get_status` | 1.88 ms / call @ 1 k measurements | Incremental O(1) counters |
| H1 | High      | `redaction._redact_value` | 2.4 M generator evals / 50 k calls | Pre-compiled regex |
| H2 | High      | `MiddlewareCore.should_exclude` | 400 k `rstrip()` / 100 k calls | Pre-compute at `__init__` |
| M1 | Medium    | `extract_correlation_id` (miss) | 1.9 µs; uuid4 = 60 % of cost | `secrets.token_hex(16)` |

---

## B. Methodology

### Step 1 — Micro-benchmark all hot paths

```
measure_ns(fn, iterations=100_000)
```
Each function called N times with GC disabled; mean and best (fastest single call) recorded.

### Step 2 — cProfile (cumulative)

```python
cProfile.Profile().enable()
for _ in range(iterations):
    fn()
pr.disable()
pstats.Stats(pr).sort_stats("cumulative").print_stats(20)
```

### Step 3 — tracemalloc heap diff

```python
tracemalloc.start()
snap_before = tracemalloc.take_snapshot()
# ... 10 k iterations ...
snap_after = tracemalloc.take_snapshot()
stats = snap_after.compare_to(snap_before, "lineno")
```

---

## C. Findings

### C1 — CRITICAL: SLOTracker.get_status is O(n) per call

**Measured cost:** 1,881,381 ns (1.88 ms) at 1 k measurements; 8 ms at 102 k measurements (linear).

**cProfile (5,000 × get_status, 102 k measurements in buffer):**

```
510,005,000 function calls in 40.728 seconds
  ncalls    tottime   cumtime  filename
   5,000      1.174    40.205  slo/tracker.py:136(get_status)
   5,000      0.004    39.021  slo/tracker.py:196(_calculate_value)
   5,000     22.417    39.016  {built-in method builtins.sum}
 510,005,000  16.599    16.599  slo/tracker.py:206(<genexpr>)  ← 510 M iterations
```

**Root cause:** `_calculate_value` for `AVAILABILITY` (and `ERROR_RATE`) evaluates
`sum(1 for m in measurements if m.success)` — this iterates all N measurements on every status
read.  With 5,000 reads × 102,000 measurements = 510 M generator iterations.

**Code:** `tracker.py:206`
```python
# BEFORE — O(n) every read
success_count = sum(1 for m in measurements if m.success)
return success_count / len(measurements)
```

**Fix:** Maintain incremental `_success_counts` and `_total_counts` dicts, updated on every
`record_measurement` (append +1, window-eviction −1).  `get_status` for AVAILABILITY/ERROR_RATE
reads the counters in O(1) without copying the deque.

---

### H1 — HIGH: redaction processor scans all sensitive keywords per field (any() generator)

**Measured cost:** 1,666 ns/call (clean event); 3.3 M function calls for 50 k invocations.

**cProfile (50,000 × redaction, 4-field clean event):**

```
3,300,001 function calls in 0.354 seconds
  ncalls      tottime  cumtime  filename
  200,000      0.119    0.226  {built-in method builtins.any}
2,400,000      0.107    0.107  redaction.py:110(<genexpr>)   ← 48 generator evals/call
  200,000      0.013    0.013  {method 'lower' of 'str' objects}
```

**Root cause:** For each field key the processor calls
`any(sensitive in key_lower for sensitive in _fields)` where `_fields` has 11 keywords.
For a "clean" log event (no secrets) it iterates all 11 keywords per field before returning
False.  With 4 fields: 44 generator steps + 4 generator object creations + 4 `.lower()` calls
per event.

**Code:** `redaction.py:110`
```python
# BEFORE — O(keywords) per field per event
key_lower = key.lower()
if any(sensitive in key_lower for sensitive in _fields):
```

**Fix:** Pre-compile a single case-insensitive regex from `_fields` at processor-creation time.
`re.search` is a single C-level call, replacing 11 Python generator steps.

---

### H2 — HIGH: should_exclude recomputes rstrip("/") on every call

**Measured cost:** 188 ns/call (miss); 400,000 `rstrip` + 400,000 `startswith` calls per 100 k
invocations.

**cProfile (100,000 × should_exclude miss, 4 excluded paths):**

```
1,000,001 function calls in 0.111 seconds
  ncalls     tottime  cumtime  filename
 100,000      0.061    0.102  middleware/core.py:91(should_exclude)
 400,000      0.021    0.021  {method 'startswith' of 'str' objects}
 400,000      0.020    0.020  {method 'rstrip' of 'str' objects}   ← all wasted
```

**Root cause:** The inner loop body is
`path.startswith(excluded.rstrip("/") + "/")`.
`excluded.rstrip("/") + "/"` is recomputed on every call for every excluded path — 4 × N
string allocations that produce the same strings each time.

**Code:** `core.py:93-94`
```python
# BEFORE — rstrip computed on every call
for excluded in self.exclude_paths:
    if path == excluded or path.startswith(excluded.rstrip("/") + "/"):
```

**Fix:** Pre-compute normalized prefixes once in `__init__` and iterate two parallel lists in
`should_exclude`.

---

### M1 — MEDIUM: extract_correlation_id miss allocates a UUID4 (1.9 µs)

**Measured cost (miss path):** 1,895 ns mean — 13× slower than the hit path (137 ns).

**cProfile (30,000 × miss, 0.110 s total):**

```
450,001 function calls in 0.110 seconds
  ncalls   tottime  cumtime  filename
  30,000     0.021    0.106  middleware/core.py:100(extract_correlation_id)
  30,000     0.009    0.066  uuid.py:710(uuid4)
  30,000     0.022    0.030  uuid.py:142(__init__)
  30,000     0.027    0.027  {built-in method posix.urandom}   ← 25 % of total
  30,000     0.009    0.009  uuid.py:283(__str__)
```

**Standalone uuid4 cost:** 1,652 ns mean.

**Root cause:** `str(uuid.uuid4())` constructs a UUID object: reads 16 bytes from `os.urandom`,
passes them through the `UUID.__init__` state machine (variant/version bit manipulation),
then renders a 36-character hyphenated string.  Only 25 chars of entropy are meaningful;
the rest is formatting overhead.

**Code:** `core.py:112`
```python
# BEFORE — uuid4 = 1.65 µs, 36 chars
return str(uuid.uuid4())
```

**Fix:** `secrets.token_hex(16)` returns 32 lowercase hex chars directly from `os.urandom(16).hex()`
with no intermediate object construction — measured at ~300 ns.  The generated value passes
`_CORRELATION_ID_RE = re.compile(r"^[a-zA-Z0-9\-_\.]{1,128}$")`.

---

### L1 — LOW (documented only): prometheus-client labels() calls sorted() on every observe

**Measured:** `prometheus_client/metrics.py:138(labels)` = 0.070 s / 30 k iterations (37 % of
total `observe_request` time).  `sorted()` called 120,000 times (twice per call — once for
counter, once for histogram).

This is upstream library behaviour (`prometheus_client` validates label order with `sorted()`).
No fix within obskit scope.  Operators at very high RPS (> 50 k req/s) should consider the
`PROMETHEUS_MULTIPROC_DIR` path or custom metric pre-labelling to reuse label handles.

---

### L2 — LOW (documented only): structlog JSON serialisation

**Measured:** structlog `log.info` = 2,583 ns mean; `json.encoder.iterencode` = 17 ms / 20 k
calls (hottest single function).

Switching to `orjson` (drop-in structlog renderer) typically halves JSON serialisation cost.
Out of scope for this audit.

---

## D. Memory Analysis

| Benchmark | Top allocator | Net Δ / 10 k calls |
|-----------|---------------|-------------------|
| REDMetrics.observe_request | prometheus_client:176 genexpr | +95.3 KiB (+1,743 objects, 56 B avg) |
| structlog log.info | near steady-state | negligible |
| SLOTracker.get_status (10 k measurements × 100 reads) | `tracker.py:214` list copy | +112 B (2 objects) |

The dominant allocator is the prometheus-client `<genexpr>` used in `_raise_if_not_observable` —
this is upstream and irreducible without forking prometheus-client.

The SLO `list(buf)` copy (line 157) shows only +112 B for 100 reads.  After the C1 fix
AVAILABILITY/ERROR_RATE reads will skip this copy entirely.

---

## E. Expected Impact (post-fix)

| Fix | Expected speedup | Basis |
|-----|-----------------|-------|
| C1 SLO counters | **~1000×** for AVAILABILITY/ERROR_RATE status reads | O(n) → O(1); no list copy |
| H1 Regex redaction | **~3×** on clean events (50 k/s) | Eliminates 2.4 M generator evals → 200 k C regex searches |
| H2 should_exclude pre-compute | **~15 % wall-clock** in should_exclude miss | Eliminates 400 k rstrip() string allocs |
| M1 token_hex vs uuid4 | **~5×** speedup on CID miss path | 300 ns vs 1,652 ns |

---

## F. Applied Fixes

All four issues are fixed in-place.  Impacted files:

| File | Change |
|------|--------|
| `src/obskit/slo/tracker.py` | C1: `_success_counts`/`_total_counts` dicts; O(1) fast path in `get_status` |
| `src/obskit/logging/redaction.py` | H1: `re.compile(pattern, IGNORECASE)` in `make_redaction_processor` |
| `src/obskit/middleware/core.py` | H2: `_exclude_prefixes` pre-computed in `__init__`; M1: `secrets.token_hex(16)` |
| `tests/unit/middleware/test_core.py` | Update length assertions: 36 → 32 |
| `tests/unit/slo/test_tracker.py` | Add zero-timespan throughput branch test |
