# SLO

Service Level Objective (SLO) tracking, error budget management, and Prometheus alert rule generation for obskit services.

## Installation

```bash
pip install "obskit[slo]"
```

For Prometheus burn-rate alert rule generation:

```bash
pip install "obskit[slo-prometheus]"
```

---

## Overview

An SLO defines a quantitative reliability target for a service. obskit slo tracking measures against those targets in rolling time windows, calculates remaining error budgets, and can generate Prometheus alerting rules to fire before the budget is exhausted.

---

## SLOType

```python
from obskit.slo.types import SLOType

SLOType.AVAILABILITY  # Percentage of successful requests (0.0–1.0)
SLOType.LATENCY       # Response time within threshold (requires percentile)
SLOType.ERROR_RATE    # Percentage of failed requests (0.0–1.0)
SLOType.THROUGHPUT    # Requests per second
```

---

## SLOTracker

The central registry for SLOs. Thread-safe via internal locking; safe to use from async code.

```python
from obskit.slo.tracker import SLOTracker

tracker = SLOTracker()
```

### register_slo

```python
tracker.register_slo(
    name="api_availability",
    slo_type=SLOType.AVAILABILITY,
    target_value=0.999,          # 99.9% availability
    window_seconds=86_400,       # 24-hour rolling window
)

tracker.register_slo(
    name="api_p99_latency",
    slo_type=SLOType.LATENCY,
    target_value=0.500,          # P99 must be ≤ 500 ms
    window_seconds=3_600,        # 1-hour window
    percentile=99,               # required for LATENCY SLOs
)

tracker.register_slo(
    name="api_error_rate",
    slo_type=SLOType.ERROR_RATE,
    target_value=0.001,          # error rate ≤ 0.1%
    window_seconds=86_400,
)
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `name` | `str` | — | Unique SLO identifier |
| `slo_type` | `SLOType` | — | Type of objective |
| `target_value` | `float` | — | Target value (availability / error-rate: 0–1; latency: seconds; throughput: req/s) |
| `window_seconds` | `int` | `86400` | Rolling measurement window in seconds |
| `percentile` | `int \| None` | `None` | P50/P95/P99 (required for `LATENCY`) |

### record_measurement

```python
# Record a successful request
tracker.record_measurement("api_availability", value=1.0, success=True)

# Record a failed request
tracker.record_measurement("api_availability", value=0.0, success=False)

# Record a latency observation (value in seconds)
tracker.record_measurement("api_p99_latency", value=0.045, success=True)

# Error rate — value is the error indicator (0 or 1)
tracker.record_measurement("api_error_rate", value=1.0, success=False)
```

!!! tip "Automatic eviction"
    Measurements outside the window are evicted on every `record_measurement()` call so the list stays bounded. No separate cleanup thread is needed.

### get_status

```python
from obskit.slo.types import SLOStatus

status: SLOStatus | None = tracker.get_status("api_availability")

if status:
    print(status.current_value)           # 0.9995
    print(status.compliance)              # True
    print(status.error_budget_remaining)  # 0.333 (33% budget left)
    print(status.error_budget_burn_rate)  # 2.1 (burning 2.1x normal rate)
    print(status.measurement_count)       # 50_000
    print(status.window_start)            # datetime
    print(status.window_end)              # datetime

    d = status.to_dict()
    # {
    #   "slo_type": "availability",
    #   "target_value": 0.999,
    #   "current_value": 0.9995,
    #   "compliance": true,
    #   "error_budget_remaining": 0.3333,
    #   "error_budget_burn_rate": 2.1,
    #   "window_start": "2026-02-27T10:00:00",
    #   "window_end":   "2026-02-28T10:00:00",
    #   "measurement_count": 50000
    # }
```

---

## SLOStatus

| Field | Type | Description |
|---|---|---|
| `slo_type` | `SLOType` | The objective type |
| `target` | `SLOTarget` | Target definition |
| `current_value` | `float` | Current measured value |
| `compliance` | `bool` | Whether the SLO is currently met |
| `error_budget_remaining` | `float` | Fraction of error budget remaining (0–1) |
| `error_budget_burn_rate` | `float` | Current burn rate (1.0 = normal, >1 = burning faster than expected) |
| `window_start` | `datetime` | Start of the rolling window |
| `window_end` | `datetime` | End of the rolling window |
| `measurement_count` | `int` | Observations in the current window |

---

## ErrorBudget

```python
from obskit.slo.types import ErrorBudget

budget = ErrorBudget(
    total_budget=0.001,        # 0.1% error allowance
    consumed=0.0007,
    burn_rate=1.5,
    time_remaining_seconds=4_800,
)

print(budget.remaining)            # 0.0003
print(budget.remaining_percentage) # 30.0
print(budget.is_exhausted)         # False
```

---

## Multi-window tracking

Track the same SLO across multiple time horizons simultaneously (common SRE practice: 1-hour, 6-hour, 24-hour, 7-day):

```python
windows = {
    "1h":  3_600,
    "6h":  21_600,
    "24h": 86_400,
    "7d":  604_800,
}

for label, seconds in windows.items():
    tracker.register_slo(
        name=f"api_availability_{label}",
        slo_type=SLOType.AVAILABILITY,
        target_value=0.999,
        window_seconds=seconds,
    )

# Record to all windows at once
def record_request(success: bool):
    for label in windows:
        tracker.record_measurement(
            f"api_availability_{label}",
            value=1.0 if success else 0.0,
            success=success,
        )
```

---

## @with_slo_tracking decorator

Automatically record SLO measurements for any sync or async function:

```python
from obskit.slo.tracker import with_slo_tracking   # sync
from obskit.slo.tracker import async_with_slo_tracking   # async

tracker = SLOTracker()
tracker.register_slo("api_availability", SLOType.AVAILABILITY, 0.999)

# Async
@async_with_slo_tracking(tracker, "api_availability")
async def create_order(order_data: dict):
    return await db.insert_order(order_data)

# Sync
@with_slo_tracking(tracker, "api_availability")
def process_batch(items: list):
    return [process(item) for item in items]
```

---

## Prometheus alert rule generation

obskit can generate Prometheus alerting rules for multi-window burn-rate alerts — the approach recommended by Google SRE:

```python
from obskit.slo.prometheus import generate_slo_alerts

rules_yaml = generate_slo_alerts(
    slo_name="api_availability",
    slo_type=SLOType.AVAILABILITY,
    target=0.999,
    metric="http_requests_total",
    error_metric="http_requests_total{status=~'5..'}",
)

print(rules_yaml)
# groups:
# - name: api_availability_slo_alerts
#   rules:
#   - alert: ApiAvailabilitySLOBurnRateFast
#     expr: ...
#     for: 2m
#     labels:
#       severity: critical
#   - alert: ApiAvailabilitySLOBurnRateSlow
#     ...
```

---

## Integration with health checks

Expose SLO compliance as a health check so Kubernetes readiness probes can reflect SLO state:

```python
from obskit.health import get_health_checker
from obskit.slo.tracker import SLOTracker
from obskit.slo.types import SLOType

tracker = SLOTracker()
tracker.register_slo("api_availability", SLOType.AVAILABILITY, 0.999)

checker = get_health_checker()

async def slo_availability_check():
    status = tracker.get_status("api_availability")
    if status is None:
        return {"healthy": True, "message": "No measurements yet"}

    return {
        "healthy": status.compliance,
        "message": (
            f"Availability SLO: {status.current_value:.4%} "
            f"(target {status.target.target_value:.3%})"
        ),
        "details": status.to_dict(),
    }

checker.add_check("slo_availability", slo_availability_check)
```

---

## AsyncRedisSLOTracker

Fleet-wide SLO tracker that stores measurements in Redis sorted sets so all Gunicorn/uvicorn workers share a single, consistent SLO view.

### Installation

```bash
pip install "obskit[slo]" redis
```

### Architecture

Each SLO uses Redis sorted sets keyed by Unix timestamp:

```
obskit:slo:<service>:<name>:total    — every measurement
obskit:slo:<service>:<name>:success  — successful measurements only
obskit:slo:<service>:<name>:latencies  — LATENCY only: member = "<value>:<uuid>"
```

Window management uses `ZREMRANGEBYSCORE` on every write.  A TTL of `window_seconds + 60` ensures eventual cleanup when the application stops.

### Quick start

```python
import redis.asyncio as aioredis
from obskit.slo.redis_tracker import AsyncRedisSLOTracker
from obskit.slo.types import SLOType

redis_client = aioredis.from_url("redis://localhost:6379", decode_responses=True)
tracker = AsyncRedisSLOTracker(redis_client, service="my-api")

tracker.register_slo(
    "api_availability",
    SLOType.AVAILABILITY,
    target_value=0.999,
    window_seconds=3600,
)

# In each request handler
await tracker.record_measurement("api_availability", value=1.0, success=True)

# On /metrics or a background task
status = await tracker.get_status("api_availability")
print(status.to_dict())
```

### `AsyncRedisSLOTracker(redis, *, service, key_prefix)`

| Parameter | Type | Default | Description |
|---|---|---|---|
| `redis` | async Redis client | — | `redis.asyncio.Redis` or any compatible client |
| `service` | `str` | `"default"` | Service name used in Redis key namespace |
| `key_prefix` | `str` | `"obskit:slo"` | Redis key prefix |

Both `decode_responses=True` and binary clients are supported.

### `register_slo(name, slo_type, target_value, window_seconds, percentile)`

Synchronous — stores the target locally with no Redis I/O.  Same signature as `SLOTracker.register_slo`.

### `async record_measurement(name, value, success)`

Issues 4–6 Redis commands per call (ZADD + ZREMRANGEBYSCORE + EXPIRE per set).  For high-throughput services consider recording to an in-process `SLOTracker` and flushing aggregates to Redis periodically.

### `async get_status(name) → SLOStatus | None`

Returns `None` if the SLO has not been registered.  Returns a `SLOStatus` with the same fields as `SLOTracker.get_status`.

### `async get_all_status() → dict[str, SLOStatus]`

Returns fleet-wide status for all registered SLOs.

---

## Full example

```python
import asyncio
from obskit.slo.tracker import SLOTracker
from obskit.slo.types import SLOType

tracker = SLOTracker()

# Register SLOs
tracker.register_slo("api_availability", SLOType.AVAILABILITY, 0.999, window_seconds=86_400)
tracker.register_slo("api_p99_latency",  SLOType.LATENCY,      0.300, window_seconds=3_600, percentile=99)
tracker.register_slo("api_error_rate",   SLOType.ERROR_RATE,   0.001, window_seconds=86_400)

async def handle_request():
    import time
    start = time.perf_counter()
    success = True
    try:
        result = await process_request()
        return result
    except Exception:
        success = False
        raise
    finally:
        duration = time.perf_counter() - start
        tracker.record_measurement("api_availability", 1.0 if success else 0.0, success=success)
        tracker.record_measurement("api_p99_latency",  duration, success=True)
        tracker.record_measurement("api_error_rate",   0.0 if success else 1.0, success=success)

# Inspect
status = tracker.get_status("api_availability")
print(f"Compliance: {status.compliance}")
print(f"Error budget remaining: {status.error_budget_remaining:.1%}")
print(f"Burn rate: {status.error_budget_burn_rate:.2f}x")
```
