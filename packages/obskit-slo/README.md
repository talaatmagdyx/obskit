<div align="center">

# 📈 obskit-slo

**SLO/SLA tracking with error budgets, burn-rate alerts, and multi-window compliance reporting**

---

[![PyPI](https://img.shields.io/pypi/v/obskit-slo.svg?color=blue)](https://pypi.org/project/obskit-slo/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![obskit](https://img.shields.io/badge/part%20of-obskit-blueviolet.svg)](https://github.com/talaatmagdyx/obskit)

</div>

## What it does

- **Tracks Service Level Objectives in-process** — no external dependency on Prometheus recording rules. Register an SLO once, feed it measurements, and call `get_status()` to instantly know your current value, remaining error budget, and burn rate.
- **Decorates functions with automatic SLO measurement** — `@with_slo_tracking()` wraps any sync or async function, recording success/failure and optionally latency, so service-level compliance is captured without instrumenting every call site manually.
- **Predicts SLA breaches before they happen** — `SLAPredictor` uses linear trend analysis on rolling windows to compute a risk score, estimated hours until breach, and actionable mitigation suggestions, publishing results as Prometheus metrics.

---

## Installation

```bash
# Core SLO tracking
pip install obskit-slo

# With Alertmanager integration
pip install "obskit-slo[alertmanager]"

# With Prometheus metrics export
pip install "obskit-slo[prometheus]"

# Full stack
pip install "obskit-slo[alertmanager,prometheus]"
```

---

## Quick Start

```python
from obskit.slo import SLOTracker, SLOType

tracker = SLOTracker()

# Register a 99.9% availability SLO over a 30-day rolling window
tracker.register_slo(
    name="api_availability",
    slo_type=SLOType.AVAILABILITY,
    target_value=0.999,
    window_seconds=30 * 86400,
)

# Feed measurements as requests complete
tracker.record_measurement("api_availability", value=1.0, success=True)   # good request
tracker.record_measurement("api_availability", value=0.0, success=False)  # bad request

# Check compliance at any time
status = tracker.get_status("api_availability")
print(status.current_value)           # 0.5  (50% success rate so far)
print(status.compliance)              # False
print(status.error_budget_remaining)  # 0.0  (budget exhausted)
print(status.error_budget_burn_rate)  # 1.0  (burning at 100% of budget)
```

---

## Features

### 1. SLOTracker — Register, Record, Report

`SLOTracker` supports four SLO types that cover the most common production objectives:

| `SLOType` | Compliant when | Use for |
|---|---|---|
| `AVAILABILITY` | `current >= target` | Uptime, success rate |
| `ERROR_RATE` | `current <= target` | % of failed requests |
| `LATENCY` | `P{n} <= target` | Response time budget |
| `THROUGHPUT` | `current >= target` | Minimum request rate |

```python
from obskit.slo import SLOTracker, SLOType

tracker = SLOTracker()

# Availability: 99.9% of order creation requests must succeed (30-day window)
tracker.register_slo(
    name="order_availability",
    slo_type=SLOType.AVAILABILITY,
    target_value=0.999,
    window_seconds=30 * 86400,
)

# Latency: P95 checkout latency must stay under 500 ms (7-day window)
tracker.register_slo(
    name="checkout_latency_p95",
    slo_type=SLOType.LATENCY,
    target_value=0.500,          # seconds
    window_seconds=7 * 86400,
    percentile=95,
)

# Error rate: less than 0.1% of payment requests may fail (1-day window)
tracker.register_slo(
    name="payment_error_rate",
    slo_type=SLOType.ERROR_RATE,
    target_value=0.001,          # 0.1%
    window_seconds=86400,
)

# Record measurements
tracker.record_measurement("order_availability", value=1.0, success=True)
tracker.record_measurement("checkout_latency_p95", value=0.342, success=True)
tracker.record_measurement("payment_error_rate", value=0.0, success=False)  # error!

# Inspect a single SLO
status = tracker.get_status("order_availability")
print(f"Compliant: {status.compliance}")
print(f"Error budget remaining: {status.error_budget_remaining:.4f}")
print(f"Burn rate: {status.error_budget_burn_rate:.2f}x")

# Export all SLOs as a dict (JSON-serializable)
report = tracker.to_dict()
```

### 2. `get_status()` — Reading the Full Picture

Every `SLOStatus` object gives you everything you need to drive dashboards, alerts, and automated gates:

```python
status = tracker.get_status("order_availability")

# Core compliance fields
status.compliance              # True / False
status.current_value           # e.g. 0.9992 (99.92% success rate)
status.error_budget_remaining  # e.g. 0.0002 (0.02% budget remaining out of 0.1%)
status.error_budget_burn_rate  # e.g. 0.8    (80% of budget consumed)

# Window metadata
status.window_start            # datetime (UTC)
status.window_end              # datetime (UTC)
status.measurement_count       # number of data points in this window

# JSON export for APIs or logging
payload = status.to_dict()
# {
#   "slo_type": "availability",
#   "target_value": 0.999,
#   "current_value": 0.999200,
#   "compliance": true,
#   "error_budget_remaining": 0.0002,
#   "error_budget_burn_rate": 0.8000,
#   "window_start": "2026-02-01T00:00:00+00:00",
#   "window_end":   "2026-03-01T00:00:00+00:00",
#   "measurement_count": 8640000
# }
```

### 3. `@with_slo_tracking()` — Automatic Function-Level SLO

Decorate any function and SLO measurements are recorded automatically. It detects async functions and wraps them correctly without any extra configuration.

```python
from obskit.slo.tracker import with_slo_tracking, with_slo_tracking_sync
from obskit.slo import SLOTracker, SLOType

tracker = SLOTracker()
tracker.register_slo(
    name="create_order",
    slo_type=SLOType.AVAILABILITY,
    target_value=0.999,
    window_seconds=86400,
)
tracker.register_slo(
    name="create_order_latency",
    slo_type=SLOType.LATENCY,
    target_value=0.500,     # 500 ms
    window_seconds=86400,
    percentile=95,
)

# Async function: records success/failure on every call
# track_latency=True also records the wall-clock duration to "create_order_latency"
@with_slo_tracking("create_order", track_latency=True)
async def create_order(payload: dict) -> dict:
    return await orders_db.insert(payload)

# Sync function works identically
@with_slo_tracking_sync("validate_payment", track_latency=True)
def validate_payment(card_token: str, amount: float) -> bool:
    return fraud_service.check(card_token, amount)

# Both will:
# - Record success=True when the function returns normally
# - Record success=False when the function raises an exception
# - Re-raise the original exception (SLO tracking is non-invasive)
```

### 4. Alertmanager Integration — SLO Breach Alerts

Send alerts directly to Prometheus Alertmanager when your error budget drops below a threshold. Both async and sync callers are supported.

```python
from obskit.slo.alertmanager import AlertmanagerWebhook

webhook = AlertmanagerWebhook(
    alertmanager_url="http://alertmanager.monitoring.svc:9093",
)

# Fire a generic alert
await webhook.fire_alert(
    alert_name="SLOBudgetLow",
    labels={"service": "order-api", "slo": "availability", "team": "platform"},
    annotations={
        "summary": "API availability SLO budget running low",
        "description": "Less than 20% error budget remaining for the 30-day window",
        "runbook_url": "https://wiki.internal/runbooks/slo-recovery",
    },
    severity="warning",
)

# Convenience method for SLO-specific alerts (auto-determines severity from budget)
status = tracker.get_status("order_availability")
if not status.compliance or status.error_budget_remaining < 0.25:
    await webhook.fire_slo_alert(
        service_name="order-api",
        slo_name="order_availability",
        current_value=status.current_value,
        target_value=status.target.target_value,
        error_budget_remaining=status.error_budget_remaining,
        # severity is auto-set: "critical" if budget <= 0, "warning" < 25%, "info" otherwise
    )

# Resolve when the SLO recovers
status = tracker.get_status("order_availability")
if status.compliance and status.error_budget_remaining > 0.50:
    await webhook.resolve_slo_alert("order-api", "order_availability")
```

### 5. SLA Predictor — Forecast Budget Exhaustion

`SLAPredictor` uses linear regression over a rolling history window to compute a risk score (0–100), predict the number of hours until breach, and suggest mitigation steps. Results are also published as Prometheus metrics.

```python
from obskit.sla_predictor import SLAPredictor, get_sla_predictor
import time

predictor = SLAPredictor(
    warning_threshold_hours=4.0,   # fire warning if breach predicted within 4 hours
    max_history_hours=168,          # keep up to 7 days of history
    on_warning=lambda risk: logger.warning(
        "sla_breach_predicted",
        sla=risk.sla_name,
        hours=risk.hours_until_breach,
        risk_score=risk.risk_score,
    ),
)

# Define an SLA: P95 checkout latency must stay under 200 ms
predictor.set_sla(
    name="checkout_latency",
    target_value=200,       # ms
    percentile=95,
    comparison="less_than",
    window_hours=1,
    description="Checkout P95 latency SLA: under 200ms",
)

# Feed measurements from your instrumentation
for latency_ms in measure_p95_latency():
    predictor.record("checkout_latency", latency_ms)

# Assess breach risk
risk = predictor.assess_risk("checkout_latency")
print(f"Risk score:          {risk.risk_score}/100")
print(f"Breach likely:       {risk.breach_likely}")
print(f"Hours until breach:  {risk.hours_until_breach}")
print(f"Current P95:         {risk.current_value:.1f} ms")
print(f"Target:              {risk.target_value:.1f} ms")
print(f"Trend:               {risk.trend}")           # "improving" | "degrading" | "stable"
print(f"Suggestions:")
for s in risk.suggestions:
    print(f"  - {s}")

# Scan all SLAs for at-risk ones (risk score >= 50)
at_risk = predictor.get_at_risk_slas(threshold=50.0)
for r in at_risk:
    print(f"AT RISK: {r.sla_name} — {r.risk_score}/100 — breach in {r.hours_until_breach:.1f}h")
```

Prometheus metrics published by `SLAPredictor`:

| Metric | Type | Description |
|---|---|---|
| `sla_risk_score{sla_name}` | Gauge | Risk score 0–100 |
| `sla_predicted_breach_hours{sla_name}` | Gauge | Hours until breach (-1 = no breach) |
| `sla_current_value{sla_name}` | Gauge | Most recent recorded value |
| `sla_breach_alerts_total{sla_name,severity}` | Counter | Breach warning events |

### 6. Performance Budgets — Code-Level Enforcement

`PerformanceBudget` enforces latency, error rate, and throughput constraints at the function level. Violations are logged and tracked as Prometheus metrics — a useful complement to SLO tracking for local development and CI gates.

```python
from obskit.budgets import PerformanceBudget, BudgetManager, get_budget_manager

# Define a budget for the checkout endpoint
checkout_budget = PerformanceBudget(
    name="checkout",
    latency_p50_ms=100,
    latency_p95_ms=500,
    latency_p99_ms=1000,
    error_rate_percent=1.0,     # max 1% errors
    throughput_min_rps=10.0,    # must handle at least 10 rps
    window_seconds=60,
    on_violation=lambda budget, metric, value: pagerduty.notify(
        f"Budget '{budget}' violated: {metric}={value:.2f}"
    ),
)

@checkout_budget.enforce
async def checkout(cart_id: str) -> dict:
    return await fulfillment.process(cart_id)

# Inspect budget health
status = checkout_budget.get_status()
print(f"Healthy:    {status.healthy}")
print(f"Violations: {status.violations}")
# ["latency_p95_ms: 621.43 (threshold: <= 500)"]

# Manage multiple budgets centrally
manager = get_budget_manager()
manager.register(checkout_budget)

if manager.is_any_exceeded():
    for name in manager.get_exceeded_budgets():
        print(f"Budget exceeded: {name}")
```

---

## Realistic 30-Day API Availability SLO Example

```python
import asyncio
from obskit.slo import SLOTracker, SLOType
from obskit.slo.tracker import with_slo_tracking
from obskit.slo.alertmanager import AlertmanagerWebhook
from obskit.sla_predictor import SLAPredictor

# --- Setup ---
tracker = SLOTracker()
webhook = AlertmanagerWebhook(alertmanager_url="http://alertmanager:9093")
predictor = SLAPredictor(warning_threshold_hours=6.0)

# 30-day API availability SLO: 99.9% uptime = max 43 minutes downtime/month
tracker.register_slo(
    name="api_availability",
    slo_type=SLOType.AVAILABILITY,
    target_value=0.999,
    window_seconds=30 * 86400,
)

# P95 latency SLO: 95% of requests must complete within 300 ms
tracker.register_slo(
    name="api_latency_p95",
    slo_type=SLOType.LATENCY,
    target_value=0.300,
    window_seconds=30 * 86400,
    percentile=95,
)

predictor.set_sla(
    name="api_latency",
    target_value=300,   # ms
    percentile=95,
    comparison="less_than",
    window_hours=6,
)

# --- Instrumented handler ---
@with_slo_tracking("api_availability", track_latency=True, latency_slo_name="api_latency_p95")
async def handle_order_request(order_id: str) -> dict:
    return await orders_service.get(order_id)

# --- Background: alert when budget drops below thresholds ---
async def monitor_slo():
    while True:
        await asyncio.sleep(60)

        status = tracker.get_status("api_availability")
        if status is None:
            continue

        if status.error_budget_remaining < 0.10:  # < 10% budget left
            await webhook.fire_slo_alert(
                service_name="order-api",
                slo_name="api_availability",
                current_value=status.current_value,
                target_value=status.target.target_value,
                error_budget_remaining=status.error_budget_remaining,
            )
        elif status.compliance and status.error_budget_remaining > 0.50:
            await webhook.resolve_slo_alert("order-api", "api_availability")

asyncio.create_task(monitor_slo())
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `OBSKIT_SERVICE_NAME` | `"service"` | Service name used in log context |
| `OBSKIT_LOG_LEVEL` | `"INFO"` | Log level for SLO tracker events |

---

## Part of the obskit family

`obskit-slo` is part of the [obskit](https://github.com/talaatmagdyx/obskit) monorepo — a production-ready observability toolkit for Python microservices.

| Install only this package | Install everything |
|---|---|
| `pip install obskit-slo` | `pip install "obskit[all]"` |
