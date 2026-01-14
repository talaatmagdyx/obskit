# SLO Tracking Guide

Service Level Objectives (SLOs) define your reliability targets.
obskit helps you track and alert on SLO compliance.

## Why SLOs?

### The Problem Without SLOs

- "Is 99% uptime good enough?" (Depends on the business)
- "Should we fix this bug or add features?" (No objective answer)
- "How much testing is enough?" (Unknown)

### The Solution: SLOs

SLOs provide clear, measurable targets:

| SLO | Target | Error Budget |
|-----|--------|--------------|
| Availability | 99.9% | 8.76 hours/year downtime |
| Latency p99 | < 200ms | 0.1% of requests can be slow |
| Error Rate | < 0.1% | 1 in 1000 requests can fail |

## Core Concepts

### SLI (Service Level Indicator)

A **measurement** of service behavior:

```python
# SLI: What percentage of requests succeed?
success_rate = successful_requests / total_requests
```

### SLO (Service Level Objective)

A **target** for an SLI:

```python
# SLO: 99.9% of requests should succeed
target = 0.999
```

### Error Budget

How much **failure is allowed**:

```python
# Error Budget = 1 - SLO = 0.1%
# Over 30 days: 0.1% × 30 × 24 × 60 = 43.2 minutes of downtime
error_budget_minutes = 43.2
```

## Basic Usage

```python
from obskit.slo import SLOTracker

# Define an SLO
availability_slo = SLOTracker(
    name="api_availability",
    target=0.999,  # 99.9%
    window_days=30,
)

# Record outcomes
def handle_request():
    try:
        result = process_request()
        availability_slo.record_success()
        return result
    except Exception as e:
        availability_slo.record_failure()
        raise
```

## SLO Types

### Availability SLO

Percentage of successful requests:

```python
availability = SLOTracker(
    name="availability",
    target=0.999,  # 99.9%
    window_days=30,
)
```

### Latency SLO

Percentage of requests under a threshold:

```python
from obskit.slo import LatencySLO

latency = LatencySLO(
    name="api_latency",
    threshold_ms=200,  # 200ms
    target=0.99,       # 99% under threshold
    window_days=30,
)

# Record request duration
latency.record(duration_ms=150)  # Success (under threshold)
latency.record(duration_ms=300)  # Failure (over threshold)
```

### Error Rate SLO

Maximum acceptable error rate:

```python
from obskit.slo import ErrorRateSLO

errors = ErrorRateSLO(
    name="error_rate",
    max_error_rate=0.001,  # 0.1% max errors
    window_days=7,
)
```

## Error Budget Tracking

```python
slo = SLOTracker(name="api", target=0.999, window_days=30)

# Check current status
status = slo.get_status()

print(f"Current SLI: {status.current_sli:.4f}")      # 0.9985
print(f"Target: {status.target:.4f}")                 # 0.9990
print(f"Budget remaining: {status.budget_remaining:.2%}")  # 45.00%
print(f"Budget consumed: {status.budget_consumed:.2%}")    # 55.00%
print(f"Burn rate: {status.burn_rate:.2f}x")               # 1.83x
```

### Budget States

```python
if status.budget_remaining > 0.5:
    # Plenty of budget - can take risks
    print("Green: Safe to deploy")
elif status.budget_remaining > 0.2:
    # Budget getting low
    print("Yellow: Proceed with caution")
else:
    # Budget nearly exhausted
    print("Red: Focus on reliability")
```

## Prometheus Integration

### Expose SLO Metrics

```python
from obskit.slo import expose_slo_metrics

# Automatically exposes metrics to Prometheus
expose_slo_metrics()
```

### Metrics Exposed

```text
# HELP slo_requests_total Total requests for SLO
# TYPE slo_requests_total counter
slo_requests_total{slo="api_availability",result="success"} 99850
slo_requests_total{slo="api_availability",result="failure"} 150

# HELP slo_budget_remaining Error budget remaining (0-1)
# TYPE slo_budget_remaining gauge
slo_budget_remaining{slo="api_availability"} 0.45

# HELP slo_burn_rate Current error budget burn rate
# TYPE slo_burn_rate gauge
slo_burn_rate{slo="api_availability"} 1.83
```

## Alerting

### Burn Rate Alerts

Alert based on how fast you're consuming error budget:

```python
from obskit.alerts import AlertConfig, generate_prometheus_rules

config = AlertConfig(
    slo_target=0.999,
    window_days=30,
    
    # Fast burn: alert if consuming 14x faster than sustainable
    fast_burn_rate=14.0,
    fast_burn_window="1h",
    
    # Slow burn: alert if consuming 3x faster
    slow_burn_rate=3.0,
    slow_burn_window="6h",
)

# Generate Prometheus alerting rules
rules = generate_prometheus_rules(config)
```

### Generated Alert Rules

```yaml
groups:
  - name: slo_alerts
    rules:
      - alert: SLOFastBurn
        expr: |
          (
            sum(rate(slo_requests_total{result="failure"}[1h]))
            /
            sum(rate(slo_requests_total[1h]))
          ) > (14 * 0.001)
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "SLO burning fast - {{ $value | humanizePercentage }} error rate"
      
      - alert: SLOSlowBurn
        expr: |
          (
            sum(rate(slo_requests_total{result="failure"}[6h]))
            /
            sum(rate(slo_requests_total[6h]))
          ) > (3 * 0.001)
        for: 15m
        labels:
          severity: warning
```

## Multi-Window Alerts

The recommended approach uses multiple time windows:

```python
# Short window, high threshold - catches severe incidents
fast_alert = AlertConfig(
    burn_rate=14.0,
    short_window="5m",
    long_window="1h",
)

# Long window, lower threshold - catches slow degradation
slow_alert = AlertConfig(
    burn_rate=1.0,
    short_window="6h",
    long_window="3d",
)
```

## Dashboard Integration

### Grafana Dashboard

```python
from obskit.slo import generate_grafana_dashboard

dashboard = generate_grafana_dashboard(
    slos=[
        {"name": "api_availability", "target": 0.999},
        {"name": "api_latency", "target": 0.99, "threshold": "200ms"},
    ]
)

# Save to file for Grafana import
with open("slo_dashboard.json", "w") as f:
    json.dump(dashboard, f)
```

## Best Practices

### 1. Start with Achievable Targets

```python
# Bad: Start with 99.99% (4.38 min/month)
slo = SLOTracker(name="api", target=0.9999)  # Too aggressive initially

# Good: Start with 99.9% (43.8 min/month)
slo = SLOTracker(name="api", target=0.999)  # Achievable, then tighten
```

### 2. Choose Meaningful Windows

```python
# 30 days is common for monthly error budgets
monthly_slo = SLOTracker(window_days=30)

# 7 days for faster feedback
weekly_slo = SLOTracker(window_days=7)
```

### 3. SLOs Should Align with User Experience

```python
# Good: Users care about these
latency_slo = LatencySLO(name="page_load", threshold_ms=2000, target=0.95)
availability_slo = SLOTracker(name="checkout", target=0.999)

# Bad: Internal metrics users don't see
cache_slo = SLOTracker(name="cache_hit", target=0.99)  # Not user-facing
```

### 4. Document Your SLOs

```python
SLOS = {
    "api_availability": {
        "sli": "Percentage of HTTP requests returning 2xx/3xx",
        "target": "99.9%",
        "window": "30 days",
        "owner": "platform-team",
        "rationale": "Aligned with customer SLA",
    },
    "api_latency_p99": {
        "sli": "99th percentile response time",
        "target": "< 500ms",
        "window": "30 days", 
        "owner": "platform-team",
        "rationale": "User research shows abandonment above 500ms",
    },
}
```

## Common Patterns

### Request-Based SLO

```python
@app.middleware("http")
async def track_slo(request, call_next):
    try:
        response = await call_next(request)
        if response.status_code < 500:
            slo.record_success()
        else:
            slo.record_failure()
        return response
    except Exception:
        slo.record_failure()
        raise
```

### Time-Based SLO

```python
import asyncio

async def heartbeat():
    """Record availability every minute."""
    while True:
        if is_service_healthy():
            slo.record_success()
        else:
            slo.record_failure()
        await asyncio.sleep(60)
```

## Next Steps

- **[Metrics Guide](metrics.md)** - Track the underlying metrics
- **[Configuration](../config/index.md)** - Set up alerting configuration
- **[Examples](../examples/kubernetes.md)** - Production deployment

