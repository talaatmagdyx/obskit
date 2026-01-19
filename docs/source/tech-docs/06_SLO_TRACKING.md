# SLO Tracking Guide

Complete guide to Service Level Objectives and error budget management.

---

## Overview

obskit provides comprehensive SLO tracking:

| SLO Type | Description | Example Target |
|----------|-------------|----------------|
| **Availability** | Uptime percentage | 99.9% (3 nines) |
| **Error Rate** | Error percentage | < 0.1% |
| **Latency** | Response time | P99 < 200ms |
| **Throughput** | Requests/second | > 1000 RPS |

---

## Basic Setup

```python
from obskit.slo import SLOTracker, SLOType, get_slo_tracker

# Get global tracker
tracker = get_slo_tracker()

# Register SLOs
tracker.register_slo(
    name="api_availability",
    slo_type=SLOType.AVAILABILITY,
    target_value=0.999,  # 99.9%
    window_seconds=86400 * 30,  # 30-day window
)

tracker.register_slo(
    name="api_latency_p99",
    slo_type=SLOType.LATENCY,
    target_value=0.200,  # 200ms
    percentile=99,
    window_seconds=86400 * 7,  # 7-day window
)

tracker.register_slo(
    name="api_error_rate",
    slo_type=SLOType.ERROR_RATE,
    target_value=0.001,  # 0.1%
    window_seconds=86400,  # 1-day window
)
```

---

## Recording Measurements

### In Request Handlers

```python
import time
from obskit.slo import track_slo

@app.post("/api/orders")
async def create_order(data: dict):
    start = time.perf_counter()
    success = True
    
    try:
        result = await order_service.create(data)
        return result
    except Exception as e:
        success = False
        raise
    finally:
        duration = time.perf_counter() - start
        
        # Track availability
        track_slo("api_availability", value=1.0 if success else 0.0, success=success)
        
        # Track latency
        track_slo("api_latency_p99", value=duration, success=True)
        
        # Track error rate
        track_slo("api_error_rate", value=0.0 if success else 1.0, success=success)
```

### With Decorator

```python
from obskit.decorators import with_observability

@with_observability(
    component="OrderService",
    track_slo=True,
    slo_name="api_availability",
)
async def create_order(data: dict):
    return await order_service.create(data)
```

---

## SLO Status

### Get Status

```python
status = tracker.get_status("api_availability")

print(f"Current value: {status.current_value:.4f}")      # 0.9995
print(f"Target: {status.target.target_value:.4f}")       # 0.999
print(f"Compliant: {status.compliance}")                  # True
print(f"Error budget remaining: {status.error_budget_remaining:.2%}")  # 50%
print(f"Burn rate: {status.error_budget_burn_rate:.2f}x")  # 0.5x
print(f"Measurements: {status.measurement_count}")        # 10000
```

### All SLOs Status

```python
# Get all SLO statuses
all_status = tracker.get_all_status()

for name, status in all_status.items():
    print(f"{name}: {status.current_value:.4f} "
          f"({'✅' if status.compliance else '❌'})")
```

### Export as Dictionary

```python
# Export for API response
slo_data = tracker.to_dict()
return {"slos": slo_data}
```

---

## Error Budgets

### Understanding Error Budgets

```
Error Budget = 1 - SLO Target

For 99.9% availability SLO:
- Error Budget = 0.1% (1 - 0.999)
- In 30 days: 43.2 minutes of downtime allowed

Error Budget Remaining:
- If current availability = 99.95%
- Used = 0.05%
- Remaining = 0.05% (50% of budget)
```

### Burn Rate

```
Burn Rate = Error Budget Used / Expected Usage

If consuming budget at 2x rate:
- Will exhaust budget in half the time
- Action required to slow down burn
```

### Budget Thresholds

| Remaining | Severity | Action |
|-----------|----------|--------|
| > 50% | ✅ Healthy | Normal operations |
| 25-50% | ⚠️ Warning | Monitor closely |
| 10-25% | 🔶 Critical | Investigate |
| < 10% | 🔴 Emergency | Stop changes |
| 0% | ❌ Exhausted | SLO violation |

---

## Alertmanager Integration

### Fire SLO Alert

```python
from obskit.slo import AlertmanagerWebhook

webhook = AlertmanagerWebhook(
    alertmanager_url="http://alertmanager:9093",
)

# Check and alert
status = tracker.get_status("api_availability")

if status.error_budget_remaining < 0.25:
    await webhook.fire_slo_alert(
        slo_name="api_availability",
        current_value=status.current_value,
        target_value=status.target.target_value,
        error_budget_remaining=status.error_budget_remaining,
        severity="warning" if status.error_budget_remaining > 0.10 else "critical",
    )
```

### Resolve Alert

```python
# When SLO recovers
if status.error_budget_remaining > 0.25:
    await webhook.resolve_alert(
        alert_name="SLOViolation",
        labels={"slo_name": "api_availability"},
    )
```

### Sync Webhook (No Async)

```python
from obskit.slo import SyncAlertmanagerWebhook

webhook = SyncAlertmanagerWebhook(
    alertmanager_url="http://alertmanager:9093",
)

webhook.fire_slo_alert(
    slo_name="api_availability",
    current_value=0.998,
    target_value=0.999,
    error_budget_remaining=0.15,
)
```

---

## Prometheus Integration

### Expose SLO Metrics

```python
from obskit.slo import expose_slo_metrics, update_slo_metrics

# Start exposing metrics
expose_slo_metrics()

# Update metrics (call periodically)
update_slo_metrics(tracker)
```

### Generated Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `slo_current_value` | Gauge | slo_name, slo_type | Current SLO value |
| `slo_target_value` | Gauge | slo_name, slo_type | Target value |
| `slo_compliance` | Gauge | slo_name | 1 if compliant |
| `slo_error_budget_remaining` | Gauge | slo_name | Remaining budget |
| `slo_error_budget_burn_rate` | Gauge | slo_name | Burn rate |
| `slo_measurement_count` | Counter | slo_name | Total measurements |

### Prometheus Queries

```promql
# SLO compliance
slo_compliance{slo_name="api_availability"}

# Error budget remaining
slo_error_budget_remaining{slo_name="api_availability"}

# Burn rate trending
rate(slo_error_budget_burn_rate[1h])

# SLOs at risk (< 25% budget)
slo_error_budget_remaining < 0.25
```

---

## SLO Endpoint

### FastAPI Example

```python
@app.get("/slo")
async def slo_status():
    """Get all SLO statuses."""
    return tracker.to_dict()

@app.get("/slo/{slo_name}")
async def slo_detail(slo_name: str):
    """Get specific SLO status."""
    status = tracker.get_status(slo_name)
    if status is None:
        raise HTTPException(404, f"SLO {slo_name} not found")
    return status.to_dict()
```

### Response Example

```json
{
  "api_availability": {
    "slo_type": "availability",
    "target_value": 0.999,
    "current_value": 0.9995,
    "compliance": true,
    "error_budget_remaining": 0.5,
    "error_budget_burn_rate": 0.5,
    "window_start": "2025-12-14T12:00:00Z",
    "window_end": "2026-01-13T12:00:00Z",
    "measurement_count": 1000000
  },
  "api_latency_p99": {
    "slo_type": "latency",
    "target_value": 0.2,
    "current_value": 0.15,
    "compliance": true,
    "error_budget_remaining": 1.0,
    "error_budget_burn_rate": 0.0,
    "percentile": 99
  }
}
```

---

## SLO Types Deep Dive

### Availability SLO

```python
# Definition
tracker.register_slo(
    name="api_availability",
    slo_type=SLOType.AVAILABILITY,
    target_value=0.999,  # 99.9%
)

# Recording
# value: 1.0 = success, 0.0 = failure
tracker.record_measurement("api_availability", value=1.0, success=True)
tracker.record_measurement("api_availability", value=0.0, success=False)

# Calculation
# availability = successful_requests / total_requests
```

### Error Rate SLO

```python
# Definition
tracker.register_slo(
    name="api_error_rate",
    slo_type=SLOType.ERROR_RATE,
    target_value=0.001,  # 0.1% error rate
)

# Recording
# value: 0.0 = no error, 1.0 = error
tracker.record_measurement("api_error_rate", value=0.0, success=True)
tracker.record_measurement("api_error_rate", value=1.0, success=False)

# Calculation
# error_rate = error_requests / total_requests
```

### Latency SLO

```python
# Definition
tracker.register_slo(
    name="api_latency_p99",
    slo_type=SLOType.LATENCY,
    target_value=0.200,  # 200ms
    percentile=99,
)

# Recording
# value: actual latency in seconds
tracker.record_measurement("api_latency_p99", value=0.150, success=True)

# Calculation
# P99 = 99th percentile of latency values
```

### Throughput SLO

```python
# Definition
tracker.register_slo(
    name="api_throughput",
    slo_type=SLOType.THROUGHPUT,
    target_value=1000,  # 1000 RPS
)

# Recording
# value: typically 1.0 per request
tracker.record_measurement("api_throughput", value=1.0, success=True)

# Calculation
# throughput = total_requests / time_window_seconds
```

---

## Best Practices

### 1. Choose Appropriate Windows

| SLO Type | Recommended Window | Reason |
|----------|-------------------|--------|
| Availability | 30 days | Business SLA alignment |
| Error Rate | 1-7 days | Quick detection |
| Latency | 7 days | Stable percentiles |
| Throughput | 1 hour | Real-time capacity |

### 2. Set Realistic Targets

```python
# Start conservative, tighten over time
tracker.register_slo(
    name="api_availability",
    target_value=0.99,  # Start with 99%
    # Later: 0.999, 0.9999
)
```

### 3. Alert on Budget, Not Violations

```python
# Alert when budget is burning fast
if status.error_budget_burn_rate > 2.0:
    # Burning budget 2x faster than expected
    alert("error_budget_burn_high")
    
# Not just when SLO is violated
if not status.compliance:
    # Too late!
    alert("slo_violated")
```

### 4. Regular Review

```python
# Weekly SLO review
def weekly_slo_report():
    for name, status in tracker.get_all_status().items():
        print(f"{name}:")
        print(f"  Current: {status.current_value:.4f}")
        print(f"  Target: {status.target.target_value:.4f}")
        print(f"  Budget: {status.error_budget_remaining:.2%}")
        print(f"  Burn Rate: {status.error_budget_burn_rate:.2f}x")
```

---

## Alerting Rules

```yaml
groups:
- name: slo-alerts
  rules:
  # Budget warning
  - alert: SLOBudgetWarning
    expr: slo_error_budget_remaining < 0.25
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "SLO {{ $labels.slo_name }} has < 25% budget"
      
  # Budget critical
  - alert: SLOBudgetCritical
    expr: slo_error_budget_remaining < 0.10
    for: 5m
    labels:
      severity: critical
    annotations:
      summary: "SLO {{ $labels.slo_name }} has < 10% budget"
      
  # High burn rate
  - alert: SLOBurnRateHigh
    expr: slo_error_budget_burn_rate > 2
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "SLO {{ $labels.slo_name }} burning budget 2x faster"
      
  # SLO violated
  - alert: SLOViolation
    expr: slo_compliance == 0
    for: 1m
    labels:
      severity: critical
    annotations:
      summary: "SLO {{ $labels.slo_name }} is violated"
```
