# SLO Tracking

A Service Level Objective (SLO) is a commitment to your users: *"X% of requests will meet quality criteria Y over time window Z."* obskit's `SLOTracker` records events, computes SLIs, tracks error budgets across multiple time windows, and generates Prometheus alert rules.

---

## Quick Start

```python
from obskit.slo import SLOTracker, SLOWindow

tracker = SLOTracker(
    name="checkout_availability",
    objective=0.999,             # 99.9% availability
    windows=[SLOWindow.DAY, SLOWindow.MONTH],
)

# Record outcomes as requests complete
tracker.record_success()
tracker.record_failure(error_type="timeout")

# Inspect current status
report = tracker.get_report()
print(f"SLI: {report['sli']:.4%}")
print(f"Error budget remaining: {report['budget_remaining']:.1%}")
```

---

## What Are SLOs and Error Budgets?

### Service Level Indicator (SLI)

An SLI is the measured value of the quality criterion. Common SLIs:

| SLI type | Example definition |
|---|---|
| **Availability** | Fraction of requests that returned a non-5xx response |
| **Latency** | Fraction of requests that completed in < 300 ms |
| **Error rate** | Fraction of requests that did not return an error |
| **Data freshness** | Fraction of reads that returned data updated in < 1 hour |

### Service Level Objective (SLO)

The SLO is the **target** for the SLI. If the SLI is *"fraction of successful requests"*, an SLO of 99.9% means you target at most 1 failure per 1000 requests.

### Error Budget

The error budget is `1 - SLO`. At 99.9% availability over 30 days:
- Total events budget: 0.1% can fail
- In time terms: 43.8 minutes of downtime allowed per month

Error budgets create a shared language between reliability and feature work:
- Budget is healthy → ship fast, take risks
- Budget is at 50% → review upcoming risky deployments
- Budget is exhausted → reliability sprint, freeze risky changes

---

## SLOTracker API

```python
from obskit.slo import SLOTracker, SLOWindow

tracker = SLOTracker(
    name="checkout_availability",   # Unique name — used in metric labels
    objective=0.999,                # SLO target (0.0–1.0)
    windows=[                       # Track error budget in these windows
        SLOWindow.HOUR,             # 1 hour rolling window
        SLOWindow.DAY,              # 24 hour rolling window
        SLOWindow.WEEK,             # 7 day rolling window
        SLOWindow.MONTH,            # 30 day rolling window
    ],
    labels={"service": "checkout", "tier": "critical"},  # Extra Prometheus labels
)
```

### SLOWindow

| Value | Duration | Use case |
|---|---|---|
| `SLOWindow.HOUR` | 1 hour | Short-term burn rate alerts |
| `SLOWindow.DAY` | 24 hours | Daily health reviews |
| `SLOWindow.WEEK` | 7 days | Weekly reliability reviews |
| `SLOWindow.MONTH` | 30 days | Monthly SLA reporting |

---

## Recording Events

### Availability SLO

```python
# In your request handler:
try:
    result = await checkout(cart_id)
    tracker.record_success()
    return result
except Exception as exc:
    tracker.record_failure(
        error_type=type(exc).__name__,   # Recorded in metrics for root cause analysis
    )
    raise
```

### Latency SLO

For latency SLOs, you define "success" as completing within a threshold:

```python
import time

tracker = SLOTracker(
    name="checkout_latency_p99",
    objective=0.99,   # 99% of requests must complete within the threshold
)

start = time.perf_counter()
result = await checkout(cart_id)
duration = time.perf_counter() - start

LATENCY_THRESHOLD = 0.5   # 500ms

if duration < LATENCY_THRESHOLD:
    tracker.record_success()
else:
    tracker.record_failure(error_type="latency_exceeded")
```

### Using the `with_slo_tracking` decorator

```python
from obskit.slo import with_slo_tracking

tracker = SLOTracker(name="checkout_availability", objective=0.999)

@with_slo_tracking(tracker)
async def checkout(cart_id: str) -> dict:
    return await _do_checkout(cart_id)
```

The decorator records success/failure based on whether an exception is raised.

---

## Inspecting SLO Status

### `get_report()`

```python
report = tracker.get_report()
```

Returns a dict with current SLI and budget status for all configured windows:

```python
{
    "name": "checkout_availability",
    "objective": 0.999,
    "sli": 0.9993,                    # Current SLI (trailing 30-day window)
    "budget_remaining": 0.7,          # 70% of error budget remaining
    "is_within_slo": True,
    "windows": {
        "1h": {
            "sli": 0.9988,
            "budget_remaining": 0.12,
            "requests_total": 48201,
            "failures_total": 57,
        },
        "24h": {
            "sli": 0.9993,
            "budget_remaining": 0.7,
            "requests_total": 1152420,
            "failures_total": 807,
        },
        "7d": {
            "sli": 0.9994,
            "budget_remaining": 0.6,
            "requests_total": 8067140,
            "failures_total": 4840,
        },
        "30d": {
            "sli": 0.9993,
            "budget_remaining": 0.7,
            "requests_total": 34602600,
            "failures_total": 24222,
        },
    },
}
```

---

## Prometheus Metrics

obskit automatically exposes SLO data as Prometheus metrics:

```text
# Current SLI per window
obskit_slo_sli{name="checkout_availability", window="1h"}   0.9988
obskit_slo_sli{name="checkout_availability", window="24h"}  0.9993

# Error budget remaining (ratio)
obskit_slo_budget_remaining{name="checkout_availability", window="1h"}  0.12
obskit_slo_budget_remaining{name="checkout_availability", window="30d"} 0.70

# Event counters (for computing SLI externally with PromQL)
obskit_slo_requests_total{name="checkout_availability"}  34602600
obskit_slo_failures_total{name="checkout_availability", error_type="timeout"} 18442
obskit_slo_failures_total{name="checkout_availability", error_type="PaymentError"} 5780
```

---

## Multi-Window Alerting (Burn Rate)

The most effective SLO alerting strategy uses **burn rate**: how fast is the error budget being consumed relative to the budget replenishment rate?

A burn rate of 1.0 means budget is being consumed at exactly the rate it replenishes (you will exactly hit the SLO at end of month). A burn rate of 14.4 means budget will be exhausted in 2 hours (for a 30-day SLO).

### Alert rules generated by obskit

```python
from obskit.slo import SLOTracker, SLOWindow
from obskit.alerts.rules_generator import generate_alert_rules

tracker = SLOTracker(
    name="checkout_availability",
    objective=0.999,
    windows=[SLOWindow.HOUR, SLOWindow.DAY, SLOWindow.WEEK, SLOWindow.MONTH],
)

rules = generate_alert_rules(tracker)
print(rules.to_yaml())
```

Generated Prometheus alert rules:

```yaml
groups:
  - name: slo.checkout_availability
    rules:
      # Page immediately — burning budget very fast
      - alert: CheckoutAvailabilityBurnRateCritical
        expr: >
          (
            obskit_slo_failures_total{name="checkout_availability"}[1h]
            / obskit_slo_requests_total{name="checkout_availability"}[1h]
          ) > (14.4 * 0.001)
        for: 2m
        labels:
          severity: page
          slo: checkout_availability
        annotations:
          summary: "Checkout SLO burning at 14.4x — budget exhausted in 2h"
          runbook_url: "https://runbooks.example.com/slo/checkout"

      # Wake up but do not page — burning fast but not critically
      - alert: CheckoutAvailabilityBurnRateHigh
        expr: >
          (
            obskit_slo_failures_total{name="checkout_availability"}[6h]
            / obskit_slo_requests_total{name="checkout_availability"}[6h]
          ) > (6 * 0.001)
        for: 15m
        labels:
          severity: warning
          slo: checkout_availability
        annotations:
          summary: "Checkout SLO burning at 6x — investigate within 1 hour"

      # Budget nearly exhausted
      - alert: CheckoutAvailabilityBudgetLow
        expr: obskit_slo_budget_remaining{name="checkout_availability", window="30d"} < 0.1
        for: 0m
        labels:
          severity: warning
        annotations:
          summary: "Checkout error budget < 10% remaining for the month"
```

---

## Integration with Health Checks

Surface SLO status in your `/health/ready` endpoint:

```python
from obskit.health import HealthChecker, HealthStatus
from obskit.health.checker import HealthResult
from obskit.slo import SLOTracker

tracker = SLOTracker(name="checkout_availability", objective=0.999)

async def slo_health_check() -> HealthResult:
    report = tracker.get_report()
    budget = report["budget_remaining"]

    if not report["is_within_slo"]:
        return HealthResult(
            status=HealthStatus.unhealthy,
            message=f"SLO violated: SLI={report['sli']:.4%} < objective={report['objective']:.4%}",
        )
    if budget < 0.10:
        return HealthResult(
            status=HealthStatus.degraded,
            message=f"Error budget critical: {budget:.0%} remaining",
        )
    return HealthResult(
        status=HealthStatus.healthy,
        message=f"SLI {report['sli']:.4%} ({budget:.0%} budget remaining)",
    )

checker = HealthChecker(service="checkout")
checker.add_check("slo_checkout", slo_health_check, critical=False)
```

---

## Grafana Dashboard

### Key panels for SLO dashboards

=== "SLI over time"
    ```promql
    1 - (
      increase(obskit_slo_failures_total{name="checkout_availability"}[$__range])
      /
      increase(obskit_slo_requests_total{name="checkout_availability"}[$__range])
    )
    ```

=== "Error budget burn rate"
    ```promql
    (
      rate(obskit_slo_failures_total{name="checkout_availability"}[1h])
      /
      rate(obskit_slo_requests_total{name="checkout_availability"}[1h])
    ) / 0.001  # Divide by error rate = 1 - objective
    ```

=== "Budget remaining"
    ```promql
    obskit_slo_budget_remaining{name="checkout_availability", window="30d"}
    ```

=== "Failure breakdown by type"
    ```promql
    sum by (error_type) (
      rate(obskit_slo_failures_total{name="checkout_availability"}[1h])
    )
    ```

### Dashboard annotations

Mark deployments and incidents on your SLO dashboards to correlate changes with budget burn:

```python
# In your deployment pipeline:
import requests

requests.post("http://grafana:3000/api/annotations", json={
    "tags": ["deployment", "checkout-service"],
    "text": f"Deployed checkout-service v2.1.0",
    "time": int(time.time() * 1000),
})
```

---

## Defining Good SLOs

### Start conservative

It is easier to tighten an SLO than to loosen it. Start at 99% and tighten based on observed SLI data over 3–6 months.

### Match user expectations

Ask: *"What level of reliability do users notice?"* Users rarely notice 99.9% → 99% degradation. They do notice 99% → 95%.

### Cover latency, not just availability

A service that always responds with 500ms p99 is technically "available" but provides poor user experience. Include latency SLOs:

```python
availability_tracker = SLOTracker(
    name="checkout_availability",
    objective=0.999,
)
latency_tracker = SLOTracker(
    name="checkout_latency_p95",
    objective=0.95,   # 95% of requests under 300ms
)
```

### SLO Naming Conventions

| Name | Objective | Window | SLI definition |
|---|---|---|---|
| `checkout_availability` | 99.9% | 30d | Non-5xx responses / total responses |
| `checkout_latency_p95` | 95% | 30d | Responses < 300ms / total responses |
| `search_latency_p99` | 99% | 30d | Responses < 1000ms / total responses |
| `payment_success_rate` | 99.5% | 30d | Successful payment transactions / total attempts |

---

## Fleet-wide SLO tracking with Redis

The in-process `SLOTracker` stores measurements in memory — each Gunicorn or uvicorn worker has its own view.  For production deployments with multiple workers you may want a consistent, cross-process SLO number.  Use `AsyncRedisSLOTracker` for that.

### When to use each tracker

| Tracker | Storage | Use case |
|---|---|---|
| `SLOTracker` | In-process `deque` | Single-process apps, dev/test, async workers where one process = one SLO view |
| `AsyncRedisSLOTracker` | Redis sorted sets | Multi-worker Gunicorn/uvicorn, where all workers must share one SLO number |

### Setup

```python
import redis.asyncio as aioredis
from obskit.slo.redis_tracker import AsyncRedisSLOTracker
from obskit.slo.types import SLOType

redis_client = aioredis.from_url(
    "redis://redis.infra:6379",
    decode_responses=True,
)

tracker = AsyncRedisSLOTracker(redis_client, service="checkout")

tracker.register_slo(
    "api_availability",
    SLOType.AVAILABILITY,
    target_value=0.999,
    window_seconds=3600,
)
tracker.register_slo(
    "api_p99_latency",
    SLOType.LATENCY,
    target_value=300.0,   # ms
    window_seconds=3600,
    percentile=99,
)
```

### FastAPI middleware integration

```python
from fastapi import FastAPI, Request
from obskit.slo.redis_tracker import AsyncRedisSLOTracker

app = FastAPI()

@app.middleware("http")
async def slo_middleware(request: Request, call_next):
    import time
    start = time.perf_counter()
    success = True
    try:
        response = await call_next(request)
        success = response.status_code < 500
        return response
    except Exception:
        success = False
        raise
    finally:
        duration_ms = (time.perf_counter() - start) * 1000
        await tracker.record_measurement("api_availability", 1.0, success=success)
        await tracker.record_measurement("api_p99_latency", duration_ms, success=True)
```

### Checking status

```python
status = await tracker.get_status("api_availability")
if status:
    print(f"Fleet availability: {status.current_value:.4%}")
    print(f"Compliance: {status.compliance}")
    print(f"Error budget remaining: {status.error_budget_remaining:.1%}")

# All SLOs at once
all_status = await tracker.get_all_status()
for name, s in all_status.items():
    print(f"{name}: {'✓' if s.compliance else '✗'} {s.current_value:.4%}")
```

### Redis key structure

```
obskit:slo:checkout:api_availability:total     — every request (ZADD score=Unix ts)
obskit:slo:checkout:api_availability:success   — successful requests only
obskit:slo:checkout:api_p99_latency:latencies  — "<latency_ms>:<uuid>" members
```

Keys are evicted automatically via `ZREMRANGEBYSCORE` on every write and have a TTL of `window_seconds + 60` seconds.
