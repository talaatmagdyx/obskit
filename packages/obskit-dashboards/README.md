# obskit-dashboards

Grafana dashboard generators and visualization helpers for the obskit observability toolkit.

## Installation

```bash
pip install obskit-dashboards
```

## Features

- **RED metrics dashboard** — Auto-generate Grafana dashboards for Rate/Error/Duration metrics
- **Service overview panels** — Health, SLO burn rate, and error budget panels
- **Database dashboard** — Query latency, connection pool, and slow query panels
- **Queue dashboard** — Consumer lag, DLQ depth, and throughput panels

## Usage

```python
from obskit.dashboards import generate_service_dashboard

dashboard = generate_service_dashboard(
    service_name="order-service",
    datasource="Prometheus",
)
dashboard.save("dashboards/order-service.json")
```

## Part of obskit

This package is part of the [obskit](https://github.com/talaatmagdyx/obskit) monorepo.
