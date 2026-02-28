# obskit-slo

SLO (Service Level Objective) tracking with error budgets, burn-rate alerts, and multi-window SLO compliance for Python services.

## Install

```bash
pip install obskit-slo
```

## Quick start

```python
from obskit.slo import SLOTracker, SLOType

tracker = SLOTracker()

# Register a 99.9% availability SLO over 30 days
tracker.register_slo(
    name="api_availability",
    slo_type=SLOType.AVAILABILITY,
    target_value=0.999,
    window_seconds=30 * 86400,
)

# Record measurements
tracker.record_measurement("api_availability", value=1.0, success=True)   # good
tracker.record_measurement("api_availability", value=0.0, success=False)  # bad

# Check status
status = tracker.get_status("api_availability")
print(status.error_budget_remaining)   # 0.998 (remaining budget)
print(status.is_within_slo)           # True / False
```

## Alerts

```python
from obskit.alerts import AlertManager, AlertRule, AlertSeverity

manager = AlertManager()
manager.add_rule(AlertRule(
    name="high_error_rate",
    condition=lambda metrics: metrics["error_rate"] > 0.01,
    severity=AlertSeverity.CRITICAL,
    message="Error rate exceeded 1%",
))
```
