"""
Dashboard Generator
===================

Auto-generate Grafana dashboards from SLO definitions and metrics.

Example
-------
>>> from obskit.dashboards import generate_grafana_dashboard, DashboardBuilder
>>>
>>> # Quick generation
>>> dashboard = generate_grafana_dashboard(
...     service_name="order-service",
...     slo_names=["availability", "latency_p95"],
... )
>>>
>>> # Or use builder for customization
>>> builder = DashboardBuilder("order-service")
>>> builder.add_slo_panel("availability")
>>> builder.add_red_metrics_row()
>>> builder.add_error_budget_panel()
>>> dashboard = builder.build()
"""

from obskit.dashboards.grafana import (
    DashboardBuilder,
    generate_grafana_dashboard,
    generate_red_dashboard,
    generate_slo_dashboard,
)

__all__ = [
    "DashboardBuilder",
    "generate_grafana_dashboard",
    "generate_slo_dashboard",
    "generate_red_dashboard",
]
