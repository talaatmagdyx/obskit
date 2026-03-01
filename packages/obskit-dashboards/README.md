<div align="center">

# 📉 obskit-dashboards

**Auto-generate Grafana dashboards for your obskit services — RED metrics, SLO burn rate, queues, and databases**

---

[![PyPI](https://img.shields.io/pypi/v/obskit-dashboards.svg?color=blue)](https://pypi.org/project/obskit-dashboards/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![obskit](https://img.shields.io/badge/part%20of-obskit-blueviolet.svg)](https://github.com/talaatmagdyx/obskit)

</div>

## What it does

- **Generates production-ready Grafana dashboards in Python** — call `generate_grafana_dashboard("order-service")` and receive a complete Grafana JSON model with pre-wired RED metrics, SLO compliance gauges, error budget panels, and latency percentile time series — no ClickOps required.
- **Keeps dashboards in version control** — dashboards are generated as code, checked into your repo, and deployed automatically with your service. When the service changes, the dashboard generation script runs and the new JSON is committed.
- **Composable with `DashboardBuilder`** — the builder pattern lets you mix pre-built rows (RED, Golden Signals, SLO, database, queue) with your own custom `stat`, `gauge`, and `timeseries` panels to build dashboards that precisely match your architecture.

---

## Installation

```bash
pip install obskit-dashboards
```

---

## Quick Start

```python
from obskit.dashboards import generate_grafana_dashboard

dashboard = generate_grafana_dashboard(
    service_name="order-service",
    slo_names=["availability", "latency_p95", "checkout_success_rate"],
    include_red=True,
    include_golden_signals=True,
    title="Order Service — Production",
)

# Save as JSON file for Grafana provisioning
import json
with open("dashboards/order-service.json", "w") as f:
    json.dump(dashboard, f, indent=2)
```

The generated file can be placed in Grafana's provisioning directory (`/etc/grafana/provisioning/dashboards/`) or uploaded via the Grafana API.

---

## `generate_grafana_dashboard` — Full Service Dashboard

```python
from obskit.dashboards import generate_grafana_dashboard

dashboard = generate_grafana_dashboard(
    service_name="payment-service",     # metric prefix and UID base
    slo_names=[
        "payment_availability",
        "payment_latency_p95",
        "checkout_success_rate",
    ],
    include_red=True,                   # Request Rate, Error Rate, Latency P50/P95/P99
    include_golden_signals=True,        # Traffic, Saturation
    title="Payment Service Overview",
)
```

The returned `dict` is a Grafana-compatible dashboard JSON. It includes:

- A `datasource` template variable (`${datasource}`) wired to every panel
- An SLO status row with compliance stat panels and an error budget gauge
- A RED metrics row with request rate (reqps), error rate (%), and latency percentile time series
- A Golden Signals row with traffic and saturation panels
- Standard metadata: `uid`, `tags`, `refresh: 30s`, `schemaVersion: 38`

---

## `generate_slo_dashboard` — SLO-Focused View

```python
from obskit.dashboards import generate_slo_dashboard

dashboard = generate_slo_dashboard(
    service_name="order-service",
    slo_names=["order_availability", "order_latency_p95", "fulfillment_rate"],
    title="Order Service — SLO Overview",
)
```

Produces:

1. An SLO Overview row with one `stat` panel per SLO, colored green / yellow / red based on compliance
2. An Error Budgets row with a gauge showing remaining budget
3. An Error Budget Burn Rate time series panel

---

## `generate_red_dashboard` — RED Metrics Only

```python
from obskit.dashboards import generate_red_dashboard

dashboard = generate_red_dashboard(
    service_name="inventory-service",
    title="Inventory Service — RED Metrics",
)
```

---

## `DashboardBuilder` — Compose Custom Dashboards

For full control, use `DashboardBuilder` to assemble exactly the panels your service needs:

```python
from obskit.dashboards import DashboardBuilder
import json

builder = DashboardBuilder(
    service_name="checkout-service",
    title="Checkout Service — Full Observability",
)

# SLO section
builder.add_slo_row(["checkout_availability", "payment_success_rate"])

# RED metrics
builder.add_red_metrics_row()

# Database section
builder.add_row("Database")
builder.add_timeseries_panel(
    title="Query Latency (P50 / P95 / P99)",
    queries=[
        {
            "expr": "histogram_quantile(0.50, rate(ecommerce_request_duration_seconds_bucket{operation=~'ecommerce\\\\..*'}[5m]))",
            "legend": "P50",
        },
        {
            "expr": "histogram_quantile(0.95, rate(ecommerce_request_duration_seconds_bucket{operation=~'ecommerce\\\\..*'}[5m]))",
            "legend": "P95",
        },
        {
            "expr": "histogram_quantile(0.99, rate(ecommerce_request_duration_seconds_bucket{operation=~'ecommerce\\\\..*'}[5m]))",
            "legend": "P99",
        },
    ],
    unit="s",
)
builder.add_stat_panel(
    title="Slow Query Rate",
    query='rate(query_analyzer_slow_queries_total{database="ecommerce"}[5m])',
    unit="reqps",
    thresholds=[
        {"color": "green", "value": None},
        {"color": "yellow", "value": 0.1},
        {"color": "red", "value": 1.0},
    ],
)
builder.add_gauge_panel(
    title="Connection Pool Saturation",
    query='ecommerce_saturation{resource="ecommerce.connections"}',
    unit="percentunit",
    min_val=0,
    max_val=1,
)

# Queue section
builder.add_row("Message Queues")
builder.add_timeseries_panel(
    title="Consumer Lag — order.placed",
    queries=[
        {
            "expr": 'consumer_lag_messages{queue_name="order.placed", consumer_group="fulfillment-service"}',
            "legend": "Lag (messages)",
        }
    ],
    unit="short",
)
builder.add_timeseries_panel(
    title="DLQ Depth",
    queries=[
        {
            "expr": 'dlq_size{dlq_name="orders_dlq"}',
            "legend": "Dead messages",
        }
    ],
    unit="short",
)

# Build and save
dashboard = builder.build()
with open("dashboards/checkout-service.json", "w") as f:
    json.dump(dashboard, f, indent=2)
```

### Available builder methods

| Method | Panel type | Description |
|---|---|---|
| `add_stat_panel(title, query, unit, thresholds)` | `stat` | Single-value stat with threshold coloring |
| `add_gauge_panel(title, query, unit, min_val, max_val)` | `gauge` | Radial gauge with threshold markers |
| `add_timeseries_panel(title, queries, unit)` | `timeseries` | Multi-series line chart |
| `add_slo_compliance_panel(slo_name, target)` | `stat` | SLO compliance with green/yellow/red thresholds |
| `add_error_budget_panel(slo_name)` | `gauge` | Error budget remaining |
| `add_red_metrics_row()` | Row + 3 panels | Request rate, error rate, latency percentiles |
| `add_golden_signals_row()` | Row + 2 panels | Traffic and saturation |
| `add_slo_row(slo_names)` | Row + N panels | SLO compliance per SLO + error budget |
| `add_row(title)` | `row` | Section divider |

---

## Dashboard Output Format

`DashboardBuilder.build()` returns a plain `dict` — standard Grafana JSON model v38. Here is an abbreviated example:

```json
{
  "uid": "order_service_overview",
  "title": "Order Service Overview",
  "tags": ["obskit", "auto-generated", "order-service"],
  "schemaVersion": 38,
  "refresh": "30s",
  "timezone": "browser",
  "time": {"from": "now-1h", "to": "now"},
  "templating": {
    "list": [
      {
        "name": "datasource",
        "type": "datasource",
        "query": "prometheus",
        "current": {"text": "Prometheus", "value": "prometheus"}
      }
    ]
  },
  "panels": [
    {
      "id": 1,
      "type": "row",
      "title": "SLO Status",
      "gridPos": {"h": 1, "w": 24, "x": 0, "y": 0}
    },
    {
      "id": 2,
      "type": "stat",
      "title": "SLO: availability",
      "datasource": {"type": "prometheus", "uid": "${datasource}"},
      "targets": [{"expr": "obskit_slo_compliance{slo=\"availability\"}", "refId": "A"}],
      "fieldConfig": {
        "defaults": {
          "unit": "percentunit",
          "thresholds": {
            "steps": [
              {"color": "red", "value": null},
              {"color": "yellow", "value": 0.989},
              {"color": "green", "value": 0.999}
            ]
          }
        }
      }
    }
  ]
}
```

---

## Exporting and Persisting Dashboards

```python
builder = DashboardBuilder("order-service")
builder.add_red_metrics_row()

# Save to file
builder.save("dashboards/order-service.json")

# Export as JSON string (for Grafana API upload)
json_str = builder.to_json(indent=2)

# Or access the raw dict
dashboard_dict = builder.build()
```

---

## CI/CD Integration

Generate dashboards as part of your deployment pipeline to keep them always in sync with the latest metric names and SLOs.

### GitHub Actions example

```yaml
# .github/workflows/deploy.yml
- name: Generate Grafana dashboards
  run: |
    pip install obskit-dashboards
    python scripts/generate_dashboards.py

- name: Commit updated dashboards
  run: |
    git add dashboards/
    git diff --cached --quiet || git commit -m "chore: regenerate Grafana dashboards"
    git push

- name: Upload dashboards to Grafana
  run: |
    for f in dashboards/*.json; do
      curl -s -X POST \
        -H "Authorization: Bearer $GRAFANA_API_KEY" \
        -H "Content-Type: application/json" \
        -d "{\"dashboard\": $(cat $f), \"overwrite\": true}" \
        "$GRAFANA_URL/api/dashboards/db"
    done
```

### Generation script

```python
# scripts/generate_dashboards.py
import json
from obskit.dashboards import generate_grafana_dashboard, generate_slo_dashboard

SERVICES = [
    {
        "name": "order-service",
        "slos": ["availability", "latency_p95", "fulfillment_rate"],
    },
    {
        "name": "payment-service",
        "slos": ["payment_availability", "payment_latency_p95"],
    },
    {
        "name": "inventory-service",
        "slos": ["inventory_availability"],
    },
]

for service in SERVICES:
    # Full service overview dashboard
    overview = generate_grafana_dashboard(
        service_name=service["name"],
        slo_names=service["slos"],
        include_red=True,
        include_golden_signals=True,
    )
    path = f"dashboards/{service['name']}.json"
    with open(path, "w") as f:
        json.dump(overview, f, indent=2)
    print(f"Generated {path}")

    # Dedicated SLO dashboard
    slo = generate_slo_dashboard(
        service_name=service["name"],
        slo_names=service["slos"],
    )
    slo_path = f"dashboards/{service['name']}-slo.json"
    with open(slo_path, "w") as f:
        json.dump(slo, f, indent=2)
    print(f"Generated {slo_path}")

print(f"Done — generated {len(SERVICES) * 2} dashboards")
```

---

## SLO Panel Reference

SLO panels query these obskit metrics (emitted by `obskit-slo`):

| Metric | Description |
|---|---|
| `obskit_slo_compliance{slo="..."}` | Current SLO compliance (0.0 – 1.0) |
| `obskit_slo_error_budget_remaining` | Remaining error budget as a fraction |
| `obskit_slo_burn_rate{service="..."}` | Error budget burn rate (1.0 = on target) |

---

## Part of the obskit family

`obskit-dashboards` is part of the [obskit](https://github.com/talaatmagdyx/obskit) monorepo — a production-ready observability toolkit for Python microservices.

| Install only this package | Install everything |
|---|---|
| `pip install obskit-dashboards` | `pip install "obskit[all]"` |
