"""
Prometheus Rules Generator
==========================

Generate Prometheus recording rules and alerting rules from SLO definitions.

Example
-------
>>> from obskit.alerts.rules_generator import (
...     generate_recording_rules,
...     generate_alert_rules,
...     generate_all_rules,
... )
>>>
>>> # Generate recording rules
>>> recording = generate_recording_rules(
...     service_name="order-service",
...     metrics_prefix="order_service",
... )
>>>
>>> # Generate alert rules
>>> alerts = generate_alert_rules(
...     service_name="order-service",
...     slos=[
...         {"name": "availability", "target": 0.999},
...         {"name": "latency_p95", "target": 0.5},
...     ],
... )
>>>
>>> # Generate all rules
>>> all_rules = generate_all_rules("order-service")
>>> with open("rules.yml", "w") as f:
...     f.write(all_rules)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import yaml

from obskit.logging import get_logger

logger = get_logger("obskit.alerts.rules_generator")


@dataclass
class SLODefinition:
    """SLO definition for rule generation."""

    name: str
    target: float
    window: str = "5m"
    burn_rate_windows: list[str] = None

    def __post_init__(self):
        if self.burn_rate_windows is None:
            self.burn_rate_windows = ["5m", "1h", "6h"]


def generate_recording_rules(
    service_name: str,
    metrics_prefix: str | None = None,
    windows: list[str] | None = None,
) -> dict[str, Any]:
    """
    Generate Prometheus recording rules for a service.

    Parameters
    ----------
    service_name : str
        Name of the service.
    metrics_prefix : str, optional
        Prefix for metrics (defaults to service_name with underscores).
    windows : list of str, optional
        Time windows for aggregation (default: ["5m", "1h", "6h"]).

    Returns
    -------
    dict
        Prometheus rules YAML structure.
    """
    prefix = metrics_prefix or service_name.replace("-", "_")
    windows = windows or ["5m", "1h", "6h"]

    rules = []

    for window in windows:
        # Availability
        rules.append(
            {
                "record": f"{prefix}:availability:{window}",
                "expr": f"""
sum(rate({prefix}_requests_total{{status="success"}}[{window}]))
/ sum(rate({prefix}_requests_total[{window}]))
""".strip(),
            }
        )

        # Error rate
        rules.append(
            {
                "record": f"{prefix}:error_rate:{window}",
                "expr": f"""
sum(rate({prefix}_requests_total{{status="failure"}}[{window}]))
/ sum(rate({prefix}_requests_total[{window}]))
""".strip(),
            }
        )

        # Latency percentiles
        for percentile in [0.50, 0.95, 0.99]:
            p_name = str(int(percentile * 100))
            rules.append(
                {
                    "record": f"{prefix}:latency_p{p_name}:{window}",
                    "expr": f"""
histogram_quantile({percentile},
  sum(rate({prefix}_request_duration_seconds_bucket[{window}])) by (le))
""".strip(),
                }
            )

        # Request rate
        rules.append(
            {
                "record": f"{prefix}:request_rate:{window}",
                "expr": f"sum(rate({prefix}_requests_total[{window}]))",
            }
        )

    return {
        "groups": [
            {
                "name": f"{service_name}_recording_rules",
                "interval": "30s",
                "rules": rules,
            }
        ],
    }


def generate_slo_recording_rules(
    service_name: str,
    slos: list[dict[str, Any]],
    metrics_prefix: str | None = None,
) -> dict[str, Any]:
    """
    Generate SLO-specific recording rules.

    Parameters
    ----------
    service_name : str
        Service name.
    slos : list of dict
        SLO definitions with 'name', 'target', 'type'.
    metrics_prefix : str, optional
        Metrics prefix.

    Returns
    -------
    dict
        Prometheus rules structure.
    """
    prefix = metrics_prefix or service_name.replace("-", "_")
    rules = []

    for slo in slos:
        name = slo["name"]
        target = slo["target"]
        slo_type = slo.get("type", "availability")

        # SLO compliance
        if slo_type == "availability":
            rules.append(
                {
                    "record": f"{prefix}:slo_compliance:{name}",
                    "expr": f"clamp_max({prefix}:availability:5m / {target}, 1)",
                }
            )
        elif slo_type == "latency":
            rules.append(
                {
                    "record": f"{prefix}:slo_compliance:{name}",
                    "expr": f"clamp_max({target} / {prefix}:latency_p95:5m, 1)",
                }
            )

        # Error budget remaining
        rules.append(
            {
                "record": f"{prefix}:error_budget_remaining:{name}",
                "expr": f"1 - ({prefix}:error_rate:5m / (1 - {target}))",
            }
        )

        # Burn rate (multiple windows)
        for window in ["5m", "1h", "6h"]:
            rules.append(
                {
                    "record": f"{prefix}:burn_rate:{name}:{window}",
                    "expr": f"{prefix}:error_rate:{window} / (1 - {target})",
                }
            )

    return {
        "groups": [
            {
                "name": f"{service_name}_slo_recording_rules",
                "interval": "30s",
                "rules": rules,
            }
        ],
    }


def generate_alert_rules(
    service_name: str,
    slos: list[dict[str, Any]],
    metrics_prefix: str | None = None,
    include_infrastructure: bool = True,
) -> dict[str, Any]:
    """
    Generate Prometheus alerting rules.

    Parameters
    ----------
    service_name : str
        Service name.
    slos : list of dict
        SLO definitions.
    metrics_prefix : str, optional
        Metrics prefix.
    include_infrastructure : bool
        Include infrastructure alerts (default: True).

    Returns
    -------
    dict
        Prometheus alert rules structure.
    """
    prefix = metrics_prefix or service_name.replace("-", "_")
    rules = []

    # Multi-window burn rate alerts (Google SRE approach)
    for slo in slos:
        name = slo["name"]
        # target = slo["target"]  # Reserved for future use in alert messages

        # Fast burn alert (2% of monthly budget in 1 hour)
        rules.append(
            {
                "alert": f"{service_name.title().replace('-', '')}FastBurn_{name}",
                "expr": f"""
{prefix}:burn_rate:{name}:5m > 14.4
and
{prefix}:burn_rate:{name}:1h > 14.4
""".strip(),
                "for": "2m",
                "labels": {
                    "severity": "critical",
                    "slo": name,
                    "service": service_name,
                },
                "annotations": {
                    "summary": f"Fast error budget burn on {name}",
                    "description": f"Burning error budget 14.4x faster than sustainable for SLO {name}",
                },
            }
        )

        # Slow burn alert (10% of monthly budget in 3 days)
        rules.append(
            {
                "alert": f"{service_name.title().replace('-', '')}SlowBurn_{name}",
                "expr": f"""
{prefix}:burn_rate:{name}:5m > 1
and
{prefix}:burn_rate:{name}:6h > 1
""".strip(),
                "for": "1h",
                "labels": {
                    "severity": "warning",
                    "slo": name,
                    "service": service_name,
                },
                "annotations": {
                    "summary": f"Slow error budget burn on {name}",
                    "description": f"Burning error budget faster than sustainable for SLO {name}",
                },
            }
        )

        # Error budget exhausted
        rules.append(
            {
                "alert": f"{service_name.title().replace('-', '')}ErrorBudgetExhausted_{name}",
                "expr": f"{prefix}:error_budget_remaining:{name} < 0",
                "for": "5m",
                "labels": {
                    "severity": "critical",
                    "slo": name,
                    "service": service_name,
                },
                "annotations": {
                    "summary": f"Error budget exhausted for {name}",
                    "description": f"SLO {name} error budget is exhausted",
                },
            }
        )

        # Error budget warning
        rules.append(
            {
                "alert": f"{service_name.title().replace('-', '')}ErrorBudgetLow_{name}",
                "expr": f"{prefix}:error_budget_remaining:{name} < 0.25",
                "for": "10m",
                "labels": {
                    "severity": "warning",
                    "slo": name,
                    "service": service_name,
                },
                "annotations": {
                    "summary": f"Error budget low for {name}",
                    "description": f"SLO {name} error budget below 25%",
                },
            }
        )

    # Infrastructure alerts
    if include_infrastructure:
        # No traffic
        rules.append(
            {
                "alert": f"{service_name.title().replace('-', '')}NoTraffic",
                "expr": f"sum(rate({prefix}_requests_total[5m])) == 0",
                "for": "10m",
                "labels": {
                    "severity": "warning",
                    "service": service_name,
                },
                "annotations": {
                    "summary": f"No traffic to {service_name}",
                    "description": f"No requests received by {service_name} in the last 10 minutes",
                },
            }
        )

        # High error rate
        rules.append(
            {
                "alert": f"{service_name.title().replace('-', '')}HighErrorRate",
                "expr": f"{prefix}:error_rate:5m > 0.05",
                "for": "5m",
                "labels": {
                    "severity": "critical",
                    "service": service_name,
                },
                "annotations": {
                    "summary": f"High error rate on {service_name}",
                    "description": f"Error rate above 5% for {service_name}",
                },
            }
        )

        # High latency
        rules.append(
            {
                "alert": f"{service_name.title().replace('-', '')}HighLatency",
                "expr": f"{prefix}:latency_p95:5m > 5",
                "for": "5m",
                "labels": {
                    "severity": "warning",
                    "service": service_name,
                },
                "annotations": {
                    "summary": f"High latency on {service_name}",
                    "description": f"P95 latency above 5s for {service_name}",
                },
            }
        )

    return {
        "groups": [
            {
                "name": f"{service_name}_alert_rules",
                "rules": rules,
            }
        ],
    }


def generate_all_rules(
    service_name: str,
    slos: list[dict[str, Any]] | None = None,
    metrics_prefix: str | None = None,
) -> str:
    """
    Generate all Prometheus rules as YAML.

    Parameters
    ----------
    service_name : str
        Service name.
    slos : list of dict, optional
        SLO definitions. Defaults to standard availability/latency SLOs.
    metrics_prefix : str, optional
        Metrics prefix.

    Returns
    -------
    str
        YAML string with all rules.

    Example
    -------
    >>> rules = generate_all_rules("order-service")
    >>> with open("rules.yml", "w") as f:
    ...     f.write(rules)
    """
    # Default SLOs
    if slos is None:
        slos = [
            {"name": "availability", "target": 0.999, "type": "availability"},
            {"name": "latency_p95", "target": 2.0, "type": "latency"},
            {"name": "error_rate", "target": 0.001, "type": "error_rate"},
        ]

    # Generate all rules
    recording = generate_recording_rules(service_name, metrics_prefix)
    slo_recording = generate_slo_recording_rules(service_name, slos, metrics_prefix)
    alerts = generate_alert_rules(service_name, slos, metrics_prefix)

    # Combine all groups
    all_groups = recording["groups"] + slo_recording["groups"] + alerts["groups"]

    return yaml.dump({"groups": all_groups}, default_flow_style=False, sort_keys=False)


def save_rules(
    service_name: str,
    output_dir: str,
    slos: list[dict[str, Any]] | None = None,
):
    """
    Save all rules to files.

    Parameters
    ----------
    service_name : str
        Service name.
    output_dir : str
        Output directory.
    slos : list of dict, optional
        SLO definitions.
    """
    import os

    os.makedirs(output_dir, exist_ok=True)

    # Recording rules
    recording = generate_recording_rules(service_name)
    with open(os.path.join(output_dir, f"{service_name}-recording-rules.yml"), "w") as f:
        yaml.dump(recording, f, default_flow_style=False)

    # SLO recording rules
    if slos:
        slo_recording = generate_slo_recording_rules(service_name, slos)
        with open(os.path.join(output_dir, f"{service_name}-slo-recording-rules.yml"), "w") as f:
            yaml.dump(slo_recording, f, default_flow_style=False)

    # Alert rules
    alerts = generate_alert_rules(service_name, slos or [])
    with open(os.path.join(output_dir, f"{service_name}-alert-rules.yml"), "w") as f:
        yaml.dump(alerts, f, default_flow_style=False)

    logger.info("rules_saved", output_dir=output_dir)


__all__ = [
    "SLODefinition",
    "generate_recording_rules",
    "generate_slo_recording_rules",
    "generate_alert_rules",
    "generate_all_rules",
    "save_rules",
]
