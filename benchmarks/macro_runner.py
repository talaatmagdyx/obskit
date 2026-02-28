"""
Macrobenchmark runner — simulates a production microservice workload.

Records p50 / p95 / p99 / p999 and throughput for each scenario.
Designed to be run standalone (not via pytest) for accurate timing.

Usage:
    python benchmarks/macro_runner.py
    python benchmarks/macro_runner.py --scenario api_gateway --workers 32
    python benchmarks/macro_runner.py --output results.json

Environment isolation tips (do these before running):
    sudo cpupower frequency-set -g performance   # Linux: disable CPU throttling
    taskset -c 2 python benchmarks/macro_runner.py  # pin to a single core
    # Close browsers, Slack, etc. — even background processes add jitter
"""

from __future__ import annotations

import argparse
import gc
import io
import json
import math
import os
import random
import statistics
import sys
import time
import tracemalloc
from collections.abc import Callable, Generator
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

# ---------------------------------------------------------------------------
# Result data class
# ---------------------------------------------------------------------------

@dataclass
class MacroResult:
    scenario: str
    workers: int
    requests: int
    duration_s: float
    latencies_us: list[float]         # per-request latency in microseconds
    errors: int = 0
    rss_before_kb: int = 0
    rss_after_kb: int = 0
    peak_alloc_kb: int = 0

    @property
    def throughput_rps(self) -> float:
        return self.requests / self.duration_s

    def percentile(self, p: float) -> float:
        """Return the p-th percentile latency in microseconds."""
        if not self.latencies_us:
            return 0.0
        sorted_lats = sorted(self.latencies_us)
        k = max(0, min(len(sorted_lats) - 1, int(math.ceil(p / 100 * len(sorted_lats))) - 1))
        return sorted_lats[k]

    def summary(self) -> dict[str, Any]:
        lats = self.latencies_us
        return {
            "scenario":        self.scenario,
            "workers":         self.workers,
            "total_requests":  self.requests,
            "errors":          self.errors,
            "error_rate_pct":  round(self.errors / max(self.requests, 1) * 100, 2),
            "throughput_rps":  round(self.throughput_rps, 1),
            "latency_us": {
                "min":   round(min(lats) if lats else 0, 1),
                "p50":   round(self.percentile(50), 1),
                "p75":   round(self.percentile(75), 1),
                "p95":   round(self.percentile(95), 1),
                "p99":   round(self.percentile(99), 1),
                "p999":  round(self.percentile(99.9), 1),
                "max":   round(max(lats) if lats else 0, 1),
                "stdev": round(statistics.stdev(lats) if len(lats) > 1 else 0, 1),
            },
            "memory": {
                "rss_before_kb":   self.rss_before_kb,
                "rss_after_kb":    self.rss_after_kb,
                "rss_delta_kb":    self.rss_after_kb - self.rss_before_kb,
                "peak_alloc_kb":   self.peak_alloc_kb,
            },
        }

    def print_summary(self) -> None:
        s = self.summary()
        lat = s["latency_us"]
        mem = s["memory"]
        print(f"\n{'─'*60}")
        print(f"  Scenario : {s['scenario']}")
        print(f"  Workers  : {s['workers']}    Requests: {s['total_requests']:,}")
        print(f"  Errors   : {s['errors']} ({s['error_rate_pct']}%)")
        print(f"  Throughput: {s['throughput_rps']:,.0f} req/s")
        print(f"  Latency (µs):  "
              f"p50={lat['p50']:.0f}  p95={lat['p95']:.0f}  "
              f"p99={lat['p99']:.0f}  p999={lat['p999']:.0f}  "
              f"max={lat['max']:.0f}  stdev={lat['stdev']:.0f}")
        print(f"  Memory (KB):  "
              f"RSS Δ={mem['rss_delta_kb']:+d}  peak_alloc={mem['peak_alloc_kb']}")


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _rss_kb() -> int:
    """Current RSS in KiB (Linux /proc; macOS psutil fallback)."""
    try:
        with open(f"/proc/{os.getpid()}/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1])
    except FileNotFoundError:
        pass
    try:
        import resource
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024
    except Exception:
        return 0


@contextmanager
def _quiet() -> Generator[None, None, None]:
    orig = sys.stderr
    sys.stderr = io.StringIO()
    try:
        yield
    finally:
        sys.stderr = orig


def _zipf_tenant(n: int = 1000, alpha: float = 1.3) -> str:
    """Sample a tenant ID from a Zipf distribution (few tenants get most traffic)."""
    r = random.random()
    cumulative = 0.0
    harmonic = sum(1.0 / (i ** alpha) for i in range(1, n + 1))
    for rank in range(1, n + 1):
        cumulative += (1.0 / (rank ** alpha)) / harmonic
        if r <= cumulative:
            return f"tenant_{rank:04d}"
    return f"tenant_{n:04d}"


def _lognormal_latency(mean_s: float = 0.05, sigma: float = 0.5) -> float:
    """Sample a request latency from a lognormal distribution."""
    mu = math.log(mean_s) - 0.5 * sigma ** 2
    return math.exp(random.gauss(mu, sigma))


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------

def _run_scenario(
    name: str,
    fn: Callable[[], None],
    n_requests: int,
    n_workers: int,
) -> MacroResult:
    """Drive `fn` from `n_workers` threads and collect latency samples."""
    gc.collect()
    tracemalloc.start()
    rss_before = _rss_kb()
    latencies: list[float] = []
    errors = 0

    # Warmup (excluded from results)
    with ThreadPoolExecutor(max_workers=n_workers) as ex:
        for f in as_completed([ex.submit(fn) for _ in range(min(50, n_requests // 10))]):
            try:
                f.result()
            except Exception:
                pass

    gc.collect()
    t_start = time.perf_counter()

    with ThreadPoolExecutor(max_workers=n_workers) as ex:
        def timed_fn() -> float:
            t0 = time.perf_counter()
            fn()
            return (time.perf_counter() - t0) * 1e6   # µs

        futs = [ex.submit(timed_fn) for _ in range(n_requests)]
        for f in as_completed(futs):
            try:
                latencies.append(f.result())
            except Exception:
                errors += 1
                latencies.append(0.0)

    duration = time.perf_counter() - t_start
    rss_after = _rss_kb()
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    return MacroResult(
        scenario=name,
        workers=n_workers,
        requests=n_requests,
        duration_s=duration,
        latencies_us=latencies,
        errors=errors,
        rss_before_kb=rss_before,
        rss_after_kb=rss_after,
        peak_alloc_kb=peak // 1024,
    )


# ---------------------------------------------------------------------------
# Scenario definitions
# ---------------------------------------------------------------------------

def _bootstrap() -> None:
    """Import and configure obskit once before all scenarios."""
    from obskit.config import configure
    from obskit.metrics.registry import reset_registry
    from obskit.resilience.circuit_breaker import reset_all_circuit_breakers
    from obskit.slo.tracker import SLOTracker, SLOType

    reset_registry()
    reset_all_circuit_breakers()
    configure(
        service_name="macro-bench",
        environment="production",
        log_level="WARNING",
        log_format="json",
    )
    tracker = SLOTracker()
    tracker.register_slo(
        name="latency",
        target=0.99,
        threshold=0.200,
        slo_type=SLOType.LATENCY,
    )
    return tracker


def scenario_metrics_only(n: int, workers: int) -> MacroResult:
    """Pure metrics hot path: observe_request × n_requests."""
    from obskit.metrics.red import REDMetrics, reset_red_metrics
    from obskit.metrics.registry import reset_registry

    reset_red_metrics()
    reset_registry()
    metrics = REDMetrics(name="macro_red")
    rng = random.Random(42)

    def fn() -> None:
        tenant = _zipf_tenant()
        dur = _lognormal_latency()
        ok = rng.random() > 0.02   # 2% error rate
        metrics.observe_request(
            operation=tenant,
            duration_seconds=dur,
            status="success" if ok else "failure",
        )

    with _quiet():
        result = _run_scenario("metrics_only", fn, n, workers)

    reset_red_metrics()
    reset_registry()
    return result


def scenario_logging_only(n: int, workers: int) -> MacroResult:
    """Pure logging hot path."""
    from obskit.logging import get_logger

    logger = get_logger("macro-bench")

    def fn() -> None:
        logger.info(
            "request_completed",
            tenant_id=_zipf_tenant(),
            duration_ms=_lognormal_latency() * 1000,
            status="success",
        )

    with _quiet():
        result = _run_scenario("logging_only", fn, n, workers)
    return result


def scenario_circuit_breaker_only(n: int, workers: int) -> MacroResult:
    """Circuit breaker context manager hot path."""
    from obskit.resilience.circuit_breaker import CircuitBreaker, reset_all_circuit_breakers

    reset_all_circuit_breakers()
    breaker = CircuitBreaker(name="macro-bench", failure_threshold=1000)

    def fn() -> None:
        with breaker:
            pass   # represents the guarded call

    result = _run_scenario("circuit_breaker_only", fn, n, workers)
    reset_all_circuit_breakers()
    return result


def scenario_slo_only(n: int, workers: int, tracker: Any) -> MacroResult:
    """SLO record_measurement hot path."""
    rng = random.Random(42)

    def fn() -> None:
        dur = _lognormal_latency()
        ok = rng.random() > 0.01
        tracker.record_measurement("latency", dur, ok)

    return _run_scenario("slo_only", fn, n, workers)


def scenario_full_stack(n: int, workers: int) -> MacroResult:
    """Full with_observability stack — the real production path."""
    from obskit.decorators.combined import with_observability
    from obskit.metrics.registry import reset_registry
    from obskit.resilience.circuit_breaker import reset_all_circuit_breakers

    reset_registry()
    reset_all_circuit_breakers()

    @with_observability(component="macro-bench")
    def handle_request() -> str:
        return "ok"

    with _quiet():
        result = _run_scenario("full_stack", handle_request, n, workers)

    reset_registry()
    reset_all_circuit_breakers()
    return result


def scenario_high_cardinality(n: int, workers: int) -> MacroResult:
    """Worst case: every request uses a unique operation label → max cardinality pressure."""
    from obskit.metrics.red import REDMetrics, reset_red_metrics
    from obskit.metrics.registry import reset_registry

    reset_red_metrics()
    reset_registry()
    metrics = REDMetrics(name="macro_hc")
    counter = [0]

    def fn() -> None:
        counter[0] += 1
        metrics.observe_request(
            operation=f"op_{counter[0]}",   # unique per call
            duration_seconds=_lognormal_latency(),
            status="success",
        )

    with _quiet():
        result = _run_scenario("high_cardinality", fn, n, workers)

    reset_red_metrics()
    reset_registry()
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

ALL_SCENARIOS = [
    "metrics_only",
    "logging_only",
    "circuit_breaker_only",
    "slo_only",
    "full_stack",
    "high_cardinality",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="obskit macrobenchmark runner")
    parser.add_argument("--scenario",  default="all",   choices=ALL_SCENARIOS + ["all"])
    parser.add_argument("--requests",  type=int, default=5_000)
    parser.add_argument("--workers",   type=int, default=16)
    parser.add_argument("--output",    default=None, help="Save JSON results to file")
    args = parser.parse_args()

    print(f"obskit macrobenchmark  requests={args.requests:,}  workers={args.workers}")
    print(f"Python {sys.version.split()[0]}  pid={os.getpid()}")

    with _quiet():
        tracker = _bootstrap()

    results = []
    run = args.scenario

    def add(r: MacroResult) -> None:
        r.print_summary()
        results.append(r.summary())

    if run in ("all", "metrics_only"):
        add(scenario_metrics_only(args.requests, args.workers))
    if run in ("all", "logging_only"):
        add(scenario_logging_only(args.requests, args.workers))
    if run in ("all", "circuit_breaker_only"):
        add(scenario_circuit_breaker_only(args.requests, args.workers))
    if run in ("all", "slo_only"):
        add(scenario_slo_only(args.requests, args.workers, tracker))
    if run in ("all", "full_stack"):
        add(scenario_full_stack(args.requests, args.workers))
    if run in ("all", "high_cardinality"):
        add(scenario_high_cardinality(args.requests // 10, 1))  # fewer; each creates new label

    if args.output:
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to {args.output}")

    print(f"\n{'='*60}")
    print("Go/no-go summary")
    print(f"{'='*60}")
    THRESHOLDS = {
        "metrics_only":        {"p99_us": 50,    "rps_min": 50_000},
        "logging_only":        {"p99_us": 100,   "rps_min": 20_000},
        "circuit_breaker_only":{"p99_us": 10,    "rps_min": 200_000},
        "slo_only":            {"p99_us": 20,    "rps_min": 100_000},
        "full_stack":          {"p99_us": 200,   "rps_min": 10_000},
        "high_cardinality":    {"p99_us": 500,   "rps_min": 1_000},
    }
    for r in results:
        name = r["scenario"]
        thresh = THRESHOLDS.get(name, {})
        p99 = r["latency_us"]["p99"]
        rps = r["throughput_rps"]
        p99_ok  = p99 <= thresh.get("p99_us", float("inf"))
        rps_ok  = rps >= thresh.get("rps_min", 0)
        verdict = "GO  ✓" if (p99_ok and rps_ok) else "NO-GO ✗"
        print(
            f"  {verdict}  {name:<28}  "
            f"p99={p99:>6.0f} µs (≤{thresh.get('p99_us','?')})  "
            f"rps={rps:>8,.0f} (≥{thresh.get('rps_min','?'):,})"
        )


if __name__ == "__main__":
    main()
