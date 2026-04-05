# SLO Readiness Check

`add_slo_readiness_check` makes Kubernetes `/ready` return **503** when a named SLO's error budget falls below a threshold — preventing traffic from being routed to a service that is burning through its budget.

## Quick Start

```python
from obskit import add_slo_readiness_check, configure_observability

obs = configure_observability(service_name="orders-api")

# Register the SLO first
obs.metrics.register_slo("availability", target=0.999)

# Then gate readiness on budget health
add_slo_readiness_check("availability", critical_threshold=0.10)
# /health/ready → 503 when error budget < 10 %
```

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `slo_name` | — | Name of a registered SLO |
| `critical_threshold` | `0.10` | Budget fraction below which readiness fails |
| `warning_threshold` | `0.25` | Budget fraction that triggers a warning (still healthy) |
| `health_checker` | global | `HealthChecker` instance to register with |

## Budget thresholds

```
budget ≥ warning_threshold              → healthy
warning_threshold > budget ≥ critical   → warning (still healthy, logged)
budget < critical_threshold             → CRITICAL — /ready returns 503
```

## Multiple SLOs

```python
add_slo_readiness_check("availability", critical_threshold=0.05)
add_slo_readiness_check("latency_p99",  critical_threshold=0.20)
# Both must pass for /ready to return 200
```

## Direct check

```python
from obskit.health.slo_check import SLOReadinessCheck

check = SLOReadinessCheck("availability", critical_threshold=0.10)
result = check.check()
print(result.healthy, result.error_budget_remaining)
```

## Retrieve a registered check

*New in v1.7.0.* Use `get_slo_readiness_check` to retrieve an already-registered check by name — useful for tests or monitoring dashboards that want to inspect the current budget without re-registering:

```python
from obskit import add_slo_readiness_check, get_slo_readiness_check

add_slo_readiness_check("availability", critical_threshold=0.10)

# Later — retrieve the same check object
check = get_slo_readiness_check("availability")
result = check.check()
print(result.healthy, result.error_budget_remaining)
```

`add_slo_readiness_check` is idempotent — calling it a second time with the same name returns the existing check without creating a duplicate.

## API Reference

::: obskit.health.slo_check.add_slo_readiness_check
::: obskit.health.slo_check.get_slo_readiness_check
::: obskit.health.slo_check.SLOReadinessCheck
::: obskit.health.slo_check.get_slo_health_status
