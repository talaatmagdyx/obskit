# Alert Rules

obskit ships a fluent builder that turns standard SRE alert patterns into valid Prometheus / Alertmanager YAML with zero hardcoded thresholds or metric names.

!!! tip "Design principle"
    obskit provides the *pattern* (SRE templates). You provide the *parameters* (metric names and thresholds). Nothing is hardcoded.

---

## The four standard SRE patterns

Every production service should be covered by at least these four signals:

| Pattern | What it detects | obskit method |
|---------|----------------|---------------|
| **Error rate** | Proportion of failed requests exceeds a threshold | `AlertRule.error_rate()` |
| **Latency** | Histogram percentile (p99, p95…) exceeds a budget | `AlertRule.latency()` |
| **No traffic** | Service goes completely silent (upstream failure, misroute) | `AlertRule.no_traffic()` |
| **SLO burn rate** | Error budget is being consumed too fast | `AlertRule.slo_burn()` |

A fifth method, **`AlertRule.custom()`**, covers anything that doesn't fit a standard template.

---

## Quick start

```python
from obskit.alerts import AlertRule, AlertGroup, export_yaml

group = AlertGroup(
    name="order-service",
    rules=[
        AlertRule.error_rate(
            metric="http_requests_total",
            threshold=0.05,          # 5% errors → critical
            severity="critical",
        ),
        AlertRule.latency(
            metric="http_request_duration_seconds",
            percentile=0.99,
            threshold_ms=2000,       # p99 > 2 s → warning
            severity="warning",
        ),
        AlertRule.no_traffic(
            metric="http_requests_total",
            window="10m",            # silence for 10 min → warning
        ),
        AlertRule.slo_burn(
            error_metric="http_requests_total",
            slo_target=0.999,        # 99.9% availability target
            severity="critical",
        ),
        # Anything else — raw PromQL
        AlertRule.custom(
            name="QueueSaturation",
            expr="rabbitmq_queue_messages > 10000",
            severity="warning",
            duration="5m",
        ),
    ],
)

yaml_str = export_yaml(group, path="k8s/alerts.yaml")
```

This produces a file that Prometheus / Alertmanager can load directly:

```yaml
groups:
- name: order-service
  rules:
  - alert: HighErrorRate
    expr: 'rate(http_requests_total{status="error"}[2m]) / rate(http_requests_total[2m]) > 0.05'
    for: 2m
    labels:
      severity: critical
    ...
```

---

## Choosing severity levels

Use consistent severity levels so your on-call routing rules can page the right people:

| Level | Meaning | Typical routing |
|-------|---------|----------------|
| `critical` | SLO breach, data loss, complete outage | Page on-call immediately |
| `warning` | Degraded performance, budget at risk | Notify Slack, review next day |
| `info` | Informational, no action needed | Dashboard only |

```python
AlertRule.error_rate(metric="m", threshold=0.05, severity="critical")  # pages on-call
AlertRule.error_rate(metric="m", threshold=0.01, severity="warning")   # Slack notification
```

---

## Customising annotations

By default obskit generates `summary` and `description` annotations. Override them to add runbook links or team-specific context:

```python
AlertRule.error_rate(
    metric="payment_requests_total",
    threshold=0.05,
    severity="critical",
    annotations={
        "summary":     "Payment service error rate above 5%",
        "description": "More than 5% of payment requests are failing.",
        "runbook_url": "https://wiki.example.com/runbooks/payment-errors",
        "dashboard":   "https://grafana.example.com/d/payments",
    },
)
```

---

## Adding extra Alertmanager labels

Extra labels are merged with the `severity` label and can be used by Alertmanager routing rules:

```python
AlertRule.slo_burn(
    error_metric="http_requests_total",
    slo_target=0.999,
    severity="critical",
    labels={
        "team":    "platform",
        "service": "order-service",
        "page":    "true",           # used by Alertmanager to trigger PagerDuty
    },
)
```

---

## Multiple services — one file

Group rules from several services into a single YAML file:

```python
from obskit.alerts import AlertRule, AlertGroup, export_yaml

order_group = AlertGroup(
    name="order-service",
    rules=[
        AlertRule.error_rate(metric="order_requests_total"),
        AlertRule.latency(metric="order_duration_seconds", threshold_ms=3000),
    ],
)

payment_group = AlertGroup(
    name="payment-service",
    rules=[
        AlertRule.error_rate(metric="payment_requests_total", threshold=0.01),
        AlertRule.slo_burn(error_metric="payment_requests_total", slo_target=0.9999),
    ],
)

# Both groups → one file
export_yaml(order_group, payment_group, path="k8s/all-alerts.yaml")
```

---

## Exporting rules at CI/CD time

The recommended pattern is to export alert rules from your Python code so they stay in sync with the service. Add this to your CI pipeline or call it from `main.py` at startup:

```python
# scripts/export_alerts.py
from obskit.alerts import AlertRule, AlertGroup, export_yaml

def main():
    group = AlertGroup(
        name="my-service",
        rules=[
            AlertRule.error_rate(metric="my_requests_total"),
            AlertRule.latency(metric="my_duration_seconds", threshold_ms=2000),
            AlertRule.no_traffic(metric="my_requests_total"),
            AlertRule.slo_burn(error_metric="my_requests_total", slo_target=0.999),
        ],
    )
    export_yaml(group, path="k8s/alerts.yaml")
    print(f"Exported {len(group.rules)} alert rules → k8s/alerts.yaml")

if __name__ == "__main__":
    main()
```

```bash
python scripts/export_alerts.py
# Exported 4 alert rules → k8s/alerts.yaml
```

Then commit `k8s/alerts.yaml` to version control. Your Prometheus configuration can mount it as a `ConfigMap`.

---

## Applying to Kubernetes

```yaml
# k8s/prometheus-rules-configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: order-service-alerts
  namespace: monitoring
  labels:
    prometheus: kube-prometheus
    role: alert-rules
data:
  alerts.yaml: |
    # Generated by obskit — do not edit manually
    # Run: python scripts/export_alerts.py
    groups:
    - name: order-service
      rules: ...
```

!!! tip "GitOps workflow"
    Run `python scripts/export_alerts.py` in your CI pipeline → commit the generated YAML → deploy it as a Kubernetes `ConfigMap`. Prometheus automatically reloads rules when the `ConfigMap` is updated.

---

## SLO burn rate explained

The `slo_burn` alert uses the multi-window approach from the [Google SRE Workbook](https://sre.google/workbook/alerting-on-slos/).

Two windows are checked simultaneously:

- **Fast window** (default 5 min) — detects very recent spikes
- **Slow window** (default 1 h) — confirms the burn is sustained, reducing false positives

Both must exceed `burn_factor` for the alert to fire.

```python
# Default: 14.4× burn factor = error budget exhausted in ~2 days
AlertRule.slo_burn(
    error_metric="http_requests_total",
    slo_target=0.999,
    burn_factor=14.4,   # = 2% of monthly budget per hour
)

# Faster alert: 6× burn factor = budget exhausted in ~5 days
AlertRule.slo_burn(
    error_metric="http_requests_total",
    slo_target=0.999,
    burn_factor=6.0,
    severity="warning",
    name="SLOBurnSlow",
)
```

| Burn factor | Time to exhaust monthly budget | Recommended severity |
|-------------|-------------------------------|---------------------|
| 14.4 | ~2 days | critical |
| 6.0 | ~5 days | warning |
| 3.0 | ~10 days | info |

---

## See also

- [`obskit.alerts` package reference](../packages/alerts.md) — full API reference
- [`build_health_router`](../packages/health.md#build_health_router) — FastAPI router for health endpoints
- [SLO Tracking](slo.md) — track SLOs at runtime in Prometheus
