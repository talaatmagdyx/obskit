"""
Grafana Dashboard Generator
===========================

Generate Grafana dashboards from SLO definitions and service metrics.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from obskit.logging import get_logger

logger = get_logger("obskit.dashboards.grafana")


@dataclass
class Panel:
    """Represents a Grafana panel."""

    title: str
    type: str
    gridPos: dict[str, int]
    targets: list[dict[str, Any]]
    options: dict[str, Any] = field(default_factory=dict)
    fieldConfig: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "type": self.type,
            "gridPos": self.gridPos,
            "targets": self.targets,
            "options": self.options,
            "fieldConfig": self.fieldConfig,
            "datasource": {"type": "prometheus", "uid": "${datasource}"},
        }


class DashboardBuilder:
    """
    Builder for creating Grafana dashboards.

    Example
    -------
    >>> builder = DashboardBuilder("order-service")
    >>> builder.add_slo_panel("availability", target=0.999)
    >>> builder.add_red_metrics_row()
    >>> dashboard = builder.build()
    """

    def __init__(
        self,
        service_name: str,
        title: str | None = None,
        uid: str | None = None,
    ):
        self.service_name = service_name
        self.title = title or f"{service_name} Overview"
        self.uid = uid or f"{service_name.replace('-', '_')}_overview"
        self.panels: list[dict[str, Any]] = []
        self.rows: list[dict[str, Any]] = []
        self._panel_id = 1
        self._current_y = 0

    def _next_panel_id(self) -> int:
        pid = self._panel_id
        self._panel_id += 1
        return pid

    def _add_panel(self, panel: dict[str, Any], width: int = 12, height: int = 8):
        """Add a panel to the dashboard."""
        panel["id"] = self._next_panel_id()
        panel["gridPos"] = {
            "h": height,
            "w": width,
            "x": (len(self.panels) % 2) * 12,
            "y": self._current_y,
        }
        if (len(self.panels) + 1) % 2 == 0:
            self._current_y += height
        self.panels.append(panel)

    def add_row(self, title: str):
        """Add a row separator."""
        self.panels.append(
            {
                "id": self._next_panel_id(),
                "type": "row",
                "title": title,
                "gridPos": {"h": 1, "w": 24, "x": 0, "y": self._current_y},
                "collapsed": False,
            }
        )
        self._current_y += 1

    def add_stat_panel(
        self,
        title: str,
        query: str,
        unit: str = "percent",
        thresholds: list[dict] | None = None,
    ):
        """Add a stat panel."""
        panel = {
            "title": title,
            "type": "stat",
            "datasource": {"type": "prometheus", "uid": "${datasource}"},
            "targets": [
                {
                    "expr": query,
                    "refId": "A",
                }
            ],
            "options": {
                "colorMode": "value",
                "graphMode": "area",
                "justifyMode": "auto",
                "textMode": "auto",
            },
            "fieldConfig": {
                "defaults": {
                    "unit": unit,
                    "thresholds": {
                        "mode": "absolute",
                        "steps": thresholds
                        or [
                            {"color": "red", "value": None},
                            {"color": "yellow", "value": 0.95},
                            {"color": "green", "value": 0.99},
                        ],
                    },
                },
            },
        }
        self._add_panel(panel, width=6, height=4)

    def add_gauge_panel(
        self,
        title: str,
        query: str,
        unit: str = "percent",
        min_val: float = 0,
        max_val: float = 1,
    ):
        """Add a gauge panel."""
        panel = {
            "title": title,
            "type": "gauge",
            "datasource": {"type": "prometheus", "uid": "${datasource}"},
            "targets": [
                {
                    "expr": query,
                    "refId": "A",
                }
            ],
            "options": {
                "showThresholdLabels": False,
                "showThresholdMarkers": True,
            },
            "fieldConfig": {
                "defaults": {
                    "unit": unit,
                    "min": min_val,
                    "max": max_val,
                    "thresholds": {
                        "mode": "absolute",
                        "steps": [
                            {"color": "red", "value": None},
                            {"color": "yellow", "value": 0.9},
                            {"color": "green", "value": 0.99},
                        ],
                    },
                },
            },
        }
        self._add_panel(panel, width=6, height=6)

    def add_timeseries_panel(
        self,
        title: str,
        queries: list[dict[str, str]],
        unit: str = "short",
    ):
        """Add a time series panel."""
        targets = [
            {"expr": q["expr"], "legendFormat": q.get("legend", ""), "refId": chr(65 + i)}
            for i, q in enumerate(queries)
        ]
        panel = {
            "title": title,
            "type": "timeseries",
            "datasource": {"type": "prometheus", "uid": "${datasource}"},
            "targets": targets,
            "options": {
                "legend": {"displayMode": "list", "placement": "bottom"},
                "tooltip": {"mode": "multi"},
            },
            "fieldConfig": {
                "defaults": {
                    "unit": unit,
                    "custom": {
                        "lineWidth": 2,
                        "fillOpacity": 10,
                    },
                },
            },
        }
        self._add_panel(panel, width=12, height=8)

    def add_slo_compliance_panel(self, slo_name: str, target: float = 0.999):
        """Add SLO compliance stat panel."""
        self.add_stat_panel(
            title=f"SLO: {slo_name}",
            query=f'obskit_slo_compliance{{slo="{slo_name}"}}',
            unit="percentunit",
            thresholds=[
                {"color": "red", "value": None},
                {"color": "yellow", "value": target - 0.01},
                {"color": "green", "value": target},
            ],
        )

    def add_error_budget_panel(self, slo_name: str = ""):
        """Add error budget remaining panel."""
        query = (
            f'obskit_slo_error_budget_remaining{{slo=~"{slo_name}.*"}}'
            if slo_name
            else "obskit_slo_error_budget_remaining"
        )
        self.add_gauge_panel(
            title="Error Budget Remaining",
            query=query,
            unit="percentunit",
        )

    def add_red_metrics_row(self):
        """Add a row with RED metrics panels."""
        self.add_row("RED Metrics")

        # Request Rate
        self.add_timeseries_panel(
            title="Request Rate",
            queries=[
                {
                    "expr": f"sum(rate({self.service_name}_requests_total[5m]))",
                    "legend": "Requests/sec",
                }
            ],
            unit="reqps",
        )

        # Error Rate
        self.add_timeseries_panel(
            title="Error Rate",
            queries=[
                {
                    "expr": f'sum(rate({self.service_name}_requests_total{{status="failure"}}[5m])) / sum(rate({self.service_name}_requests_total[5m]))',
                    "legend": "Error Rate",
                }
            ],
            unit="percentunit",
        )

        # Latency
        self.add_timeseries_panel(
            title="Latency Percentiles",
            queries=[
                {
                    "expr": f"histogram_quantile(0.50, sum(rate({self.service_name}_request_duration_seconds_bucket[5m])) by (le))",
                    "legend": "P50",
                },
                {
                    "expr": f"histogram_quantile(0.95, sum(rate({self.service_name}_request_duration_seconds_bucket[5m])) by (le))",
                    "legend": "P95",
                },
                {
                    "expr": f"histogram_quantile(0.99, sum(rate({self.service_name}_request_duration_seconds_bucket[5m])) by (le))",
                    "legend": "P99",
                },
            ],
            unit="s",
        )

    def add_golden_signals_row(self):
        """Add a row with Golden Signals panels."""
        self.add_row("Golden Signals")

        # Traffic
        self.add_timeseries_panel(
            title="Traffic",
            queries=[
                {
                    "expr": f"sum(rate({self.service_name}_requests_total[5m]))",
                    "legend": "Requests/sec",
                }
            ],
            unit="reqps",
        )

        # Saturation
        self.add_timeseries_panel(
            title="Saturation",
            queries=[
                {
                    "expr": f"{self.service_name}_saturation",
                    "legend": "Saturation",
                }
            ],
            unit="percentunit",
        )

    def add_slo_row(self, slo_names: list[str]):
        """Add a row with SLO panels."""
        self.add_row("SLO Status")

        for slo_name in slo_names:
            self.add_slo_compliance_panel(slo_name)

        self.add_error_budget_panel()

    def build(self) -> dict[str, Any]:
        """Build the dashboard JSON."""
        return {
            "uid": self.uid,
            "title": self.title,
            "tags": ["obskit", "auto-generated", self.service_name],
            "timezone": "browser",
            "schemaVersion": 38,
            "version": 1,
            "refresh": "30s",
            "time": {"from": "now-1h", "to": "now"},
            "templating": {
                "list": [
                    {
                        "name": "datasource",
                        "type": "datasource",
                        "query": "prometheus",
                        "current": {"text": "Prometheus", "value": "prometheus"},
                    },
                ],
            },
            "panels": self.panels,
        }

    def to_json(self, indent: int = 2) -> str:
        """Export dashboard as JSON string."""
        return json.dumps(self.build(), indent=indent)

    def save(self, filepath: str):
        """Save dashboard to file."""
        with open(filepath, "w") as f:
            f.write(self.to_json())
        logger.info("dashboard_saved", filepath=filepath)


def generate_grafana_dashboard(
    service_name: str,
    slo_names: list[str] | None = None,
    include_red: bool = True,
    include_golden_signals: bool = False,
    title: str | None = None,
) -> dict[str, Any]:
    """
    Generate a complete Grafana dashboard.

    Parameters
    ----------
    service_name : str
        Name of the service.
    slo_names : list of str, optional
        SLO names to include.
    include_red : bool
        Include RED metrics row (default: True).
    include_golden_signals : bool
        Include Golden Signals row (default: False).
    title : str, optional
        Dashboard title.

    Returns
    -------
    dict
        Grafana dashboard JSON.

    Example
    -------
    >>> dashboard = generate_grafana_dashboard(
    ...     "order-service",
    ...     slo_names=["availability", "latency_p95"],
    ... )
    >>> with open("dashboard.json", "w") as f:
    ...     json.dump(dashboard, f)
    """
    builder = DashboardBuilder(service_name, title=title)

    if slo_names:
        builder.add_slo_row(slo_names)

    if include_red:
        builder.add_red_metrics_row()

    if include_golden_signals:
        builder.add_golden_signals_row()

    return builder.build()


def generate_slo_dashboard(
    service_name: str,
    slo_names: list[str],
    title: str | None = None,
) -> dict[str, Any]:
    """Generate an SLO-focused dashboard."""
    builder = DashboardBuilder(
        service_name,
        title=title or f"{service_name} SLO Dashboard",
        uid=f"{service_name.replace('-', '_')}_slo",
    )

    builder.add_row("SLO Overview")

    for slo_name in slo_names:
        builder.add_slo_compliance_panel(slo_name)

    builder.add_row("Error Budgets")
    builder.add_error_budget_panel()

    # Burn rate
    builder.add_timeseries_panel(
        title="Error Budget Burn Rate",
        queries=[
            {
                "expr": f'obskit_slo_burn_rate{{service="{service_name}"}}',
                "legend": "{{slo}}",
            }
        ],
        unit="short",
    )

    return builder.build()


def generate_red_dashboard(
    service_name: str,
    title: str | None = None,
) -> dict[str, Any]:
    """Generate a RED metrics dashboard."""
    builder = DashboardBuilder(
        service_name,
        title=title or f"{service_name} RED Metrics",
        uid=f"{service_name.replace('-', '_')}_red",
    )

    builder.add_red_metrics_row()
    builder.add_golden_signals_row()

    return builder.build()


__all__ = [
    "DashboardBuilder",
    "generate_grafana_dashboard",
    "generate_slo_dashboard",
    "generate_red_dashboard",
]
