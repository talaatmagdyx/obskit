# Alerts

Standard SRE alert-rule templates with a fluent builder API. Zero hardcoded thresholds, zero hardcoded metric names.

## Installation

```bash
pip install obskit
pip install PyYAML   # already a core dependency — no extra install needed
```

---

## Overview

obskit provides two complementary alerting APIs:

| API | When to use |
|-----|-------------|
| **Fluent builder** (`AlertRule`, `AlertGroup`, `export_yaml`) | New services — standard SRE patterns, fully parameterised |
| **Lower-level generator** (`generate_alert_rules`, `generate_recording_rules`) | Advanced rules, recording rules, custom Prometheus templates |

This page covers the **fluent builder**. See the User Guide for the lower-level API.

---

## AlertRule

A single Prometheus alerting rule. Use the class-method factories to create standard SRE patterns.

```python
from obskit.alerts import AlertRule
```

### AlertRule.error_rate()

Fires when the error fraction of a counter metric exceeds a threshold.

```python
rule = AlertRule.error_rate(
    metric="http_requests_total",   # Counter metric name
    threshold=0.05,                 # 5% error rate (default)
    severity="critical",            # "critical" | "warning" | any string
    window="2m",                    # PromQL rate window (default: "2m")
    duration="2m",                  # How long before firing (default: "2m")
    name="HighErrorRate",           # Alert name in Alertmanager (default)
    error_label="error",            # Value of the 'status' label counted as error
    labels={"team": "sre"},         # Extra Alertmanager labels (optional)
    annotations=None,               # Override default annotations (optional)
)
```

Generated PromQL expression:

```promql
rate(http_requests_total{status="error"}[2m])
/ rate(http_requests_total[2m])
> 0.05
```

---

### AlertRule.latency()

Fires when a histogram percentile exceeds a latency threshold.

```python
rule = AlertRule.latency(
    metric="http_request_duration_seconds",  # Histogram base name (no _bucket suffix)
    percentile=0.99,                          # p99 (default)
    threshold_ms=2000,                        # 2 000 ms = 2 s (default)
    severity="warning",                       # default
    window="5m",                              # default
    duration="3m",                            # default
    name="HighLatency",                       # default
)
```

Generated PromQL expression:

```promql
histogram_quantile(0.99,
  sum(rate(http_request_duration_seconds_bucket[5m])) by (le))
> 2.0
```

!!! tip "Threshold units"
    Pass `threshold_ms` in **milliseconds** — obskit converts to seconds automatically.

---

### AlertRule.no_traffic()

Fires when a service receives zero requests for a sustained period.

```python
rule = AlertRule.no_traffic(
    metric="http_requests_total",
    window="10m",         # Rate window and alert duration (default: "10m")
    severity="warning",   # default
    duration="10m",       # default
    name="NoTraffic",     # default
)
```

Generated PromQL expression:

```promql
sum(rate(http_requests_total[10m])) == 0
```

!!! note "Use case"
    This detects upstream failures, misrouted traffic, or silent deploy failures where the service is up but unreachable.

---

### AlertRule.slo_burn()

Multi-window SLO error-budget burn-rate alert (Google SRE Book approach).

Fires when the error budget is burning at `burn_factor` times the sustainable rate, confirmed over both a fast and slow window to reduce false positives.

```python
rule = AlertRule.slo_burn(
    error_metric="http_requests_total",
    slo_target=0.999,      # 99.9% availability target
    fast_window="5m",      # Short confirmation window (default)
    slow_window="1h",      # Long confirmation window (default)
    burn_factor=14.4,      # Burn rate multiplier (default = 2% budget/hour)
    severity="critical",   # default
    duration="2m",         # default
    name="SLOBurnFast",    # default
    error_label="error",   # Value of the 'status' label counted as error
)
```

Generated PromQL expression:

```promql
rate(http_requests_total{status="error"}[5m])
/ rate(http_requests_total[5m])
/ 0.001
> 14.4
and
rate(http_requests_total{status="error"}[1h])
/ rate(http_requests_total[1h])
/ 0.001
> 14.4
```

!!! info "burn_factor = 14.4 explained"
    A monthly SLO with a 14.4× burn rate means 100% of the monthly error budget will be consumed in 2 days. This is the standard Google SRE "fast burn" threshold.

---

### AlertRule.custom()

Fully custom alert rule — use when the standard templates don't fit.

```python
rule = AlertRule.custom(
    name="QueueSaturation",
    expr="rabbitmq_queue_messages > 10000",
    severity="warning",
    duration="5m",
    labels={"team": "platform"},
    annotations={"summary": "RabbitMQ queue is saturated"},
)
```

---

### AlertRule.to_dict()

Serialises the rule to a Prometheus YAML rule dict.

```python
rule.to_dict()
# {
#   "alert": "HighErrorRate",
#   "expr": 'rate(http_requests_total{status="error"}[2m]) / rate(http_requests_total[2m]) > 0.05',
#   "for": "2m",
#   "labels": {"severity": "critical"},
#   "annotations": {
#     "summary": "High error rate (> 5%)",
#     "description": "Error rate above 5% over the last 2m. Metric: http_requests_total."
#   }
# }
```

---

## AlertGroup

A named group of `AlertRule` objects — maps directly to a Prometheus `groups[].rules` block.

```python
from obskit.alerts import AlertGroup

group = AlertGroup(
    name="order-service",
    rules=[
        AlertRule.error_rate(metric="http_requests_total", threshold=0.05),
        AlertRule.latency(metric="http_request_duration_seconds", threshold_ms=2000),
    ],
    interval="30s",  # Optional: override evaluation interval
)
```

### add() — fluent API

Append rules one at a time using the fluent `add()` method:

```python
group = (
    AlertGroup(name="order-service")
    .add(AlertRule.error_rate(metric="http_requests_total"))
    .add(AlertRule.no_traffic(metric="http_requests_total"))
    .add(AlertRule.slo_burn(error_metric="http_requests_total", slo_target=0.999))
)
```

### to_dict()

```python
group.to_dict()
# {
#   "name": "order-service",
#   "rules": [...],
#   "interval": "30s"   # only present when interval is set
# }
```

---

## export_yaml()

Export one or more `AlertGroup` objects to Prometheus alert-rules YAML.

```python
from obskit.alerts import export_yaml

yaml_str = export_yaml(group)                      # String only
yaml_str = export_yaml(group, path="k8s/alerts.yaml")  # String + write file
```

Parent directories are created automatically. Pass multiple groups to combine them into one file:

```python
yaml_str = export_yaml(group_a, group_b, path="k8s/all-alerts.yaml")
```

**Output format** (valid Prometheus alert-rules YAML):

```yaml
groups:
- name: order-service
  rules:
  - alert: HighErrorRate
    expr: 'rate(http_requests_total{status="error"}[2m]) / rate(http_requests_total[2m])
      > 0.05'
    for: 2m
    labels:
      severity: critical
    annotations:
      summary: High error rate (> 5%)
      description: Error rate above 5% over the last 2m. Metric http_requests_total.
  - alert: HighLatency
    expr: histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[5m]))
      by (le)) > 2.0
    for: 3m
    labels:
      severity: warning
    annotations:
      summary: High p99 latency (> 2000ms)
      description: p99 latency exceeds 2000ms over the last 5m. ...
```

---

## Complete example

```python
from obskit.alerts import AlertRule, AlertGroup, export_yaml

group = AlertGroup(
    name="payment-service",
    rules=[
        # Red flag — page on-call immediately
        AlertRule.error_rate(
            metric="payment_requests_total",
            threshold=0.05,
            severity="critical",
            name="PaymentHighErrorRate",
            labels={"team": "payments", "page": "true"},
        ),

        # P99 latency SLO — 3-second budget
        AlertRule.latency(
            metric="payment_duration_seconds",
            percentile=0.99,
            threshold_ms=3000,
            severity="critical",
            name="PaymentHighLatency",
        ),

        # P95 latency — early warning
        AlertRule.latency(
            metric="payment_duration_seconds",
            percentile=0.95,
            threshold_ms=1500,
            severity="warning",
            name="PaymentLatencyWarning",
        ),

        # No traffic = something is very wrong
        AlertRule.no_traffic(
            metric="payment_requests_total",
            window="5m",
            severity="critical",
        ),

        # SLO burn rate — 99.95% target
        AlertRule.slo_burn(
            error_metric="payment_requests_total",
            slo_target=0.9995,
            burn_factor=14.4,
            severity="critical",
        ),

        # Queue depth — infrastructure check
        AlertRule.custom(
            name="PaymentQueueSaturation",
            expr="rabbitmq_queue_messages{queue='payment-processing'} > 5000",
            severity="warning",
            duration="5m",
            annotations={"summary": "Payment queue is backing up"},
        ),
    ],
)

# Export to Kubernetes alert rules file
yaml_str = export_yaml(group, path="k8s/payment-alerts.yaml")
print(f"Exported {len(group.rules)} rules")
```

---

## Using in a startup script

A common pattern is to export alert rules on service startup or as part of CI:

```python
# src/bootstrap.py
from obskit.alerts import AlertRule, AlertGroup, export_yaml

def export_alert_rules(namespace: str, service: str, path: str = "k8s/alerts.yaml") -> None:
    """Call this once during CI/CD to regenerate alert YAML from code."""
    group = AlertGroup(
        name=f"{service}.rules",
        rules=[
            AlertRule.error_rate(
                metric=f"{namespace}_requests_total",
                threshold=0.05,
                severity="critical",
                name=f"{service}_HighErrorRate",
            ),
            AlertRule.latency(
                metric=f"{namespace}_duration_seconds",
                threshold_ms=2000,
                severity="warning",
                name=f"{service}_HighLatency",
            ),
            AlertRule.slo_burn(
                error_metric=f"{namespace}_requests_total",
                slo_target=0.999,
                severity="critical",
            ),
            AlertRule.no_traffic(
                metric=f"{namespace}_requests_total",
            ),
        ],
    )
    export_yaml(group, path=path)


# In CI or service startup:
export_alert_rules(namespace="email", service="email-service")
```

---

## API Reference

### AlertRule

| Factory method | Description |
|---|---|
| `AlertRule.error_rate(metric, threshold, severity, window, duration, name, error_label, labels, annotations)` | Error-rate alert using `rate()` |
| `AlertRule.latency(metric, percentile, threshold_ms, severity, window, duration, name, labels, annotations)` | Histogram-percentile latency alert |
| `AlertRule.no_traffic(metric, window, severity, duration, name, labels, annotations)` | Zero-traffic / silence alert |
| `AlertRule.slo_burn(error_metric, slo_target, fast_window, slow_window, burn_factor, severity, duration, name, error_label, labels, annotations)` | Multi-window SLO burn-rate alert |
| `AlertRule.custom(name, expr, severity, duration, labels, annotations)` | Raw PromQL pass-through |

| Attribute | Type | Description |
|---|---|---|
| `alert` | `str` | Alert name (Alertmanager) |
| `expr` | `str` | PromQL expression |
| `severity` | `str` | Severity label |
| `duration` | `str` | How long before firing |
| `labels` | `dict[str, str]` | Extra labels |
| `annotations` | `dict[str, str]` | Alert annotations |

### AlertGroup

| Attribute / method | Type | Description |
|---|---|---|
| `name` | `str` | Group name (Prometheus) |
| `rules` | `list[AlertRule]` | Alert rules in this group |
| `interval` | `str \| None` | Override evaluation interval |
| `add(rule)` | `AlertGroup` | Append rule, return self (fluent) |
| `to_dict()` | `dict` | Serialize to Prometheus group dict |

### export_yaml

```python
def export_yaml(*groups: AlertGroup, path: str | None = None) -> str
```

| Parameter | Description |
|---|---|
| `*groups` | One or more `AlertGroup` objects |
| `path` | Optional file path to write YAML. Parent dirs created automatically. |

Returns the YAML string regardless of whether `path` is provided.
