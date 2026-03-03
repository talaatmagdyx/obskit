"""
AlertRule, AlertGroup, export_yaml
===================================

Fluent builder for standard Prometheus / Alertmanager alert rules.

**Design principle:** obskit provides the *pattern* (SRE templates),
the caller provides the *parameters* (metric names and thresholds).
Zero hardcoded thresholds. Zero hardcoded metric names.

Usage
-----
.. code-block:: python

    from obskit.alerts import AlertRule, AlertGroup, export_yaml

    rules = AlertGroup(
        name="order-service",
        rules=[
            AlertRule.error_rate(
                metric="http_requests_total",
                threshold=0.05,
                severity="critical",
            ),
            AlertRule.latency(
                metric="http_request_duration_seconds",
                percentile=0.99,
                threshold_ms=2000,
                severity="warning",
            ),
            AlertRule.no_traffic(
                metric="http_requests_total",
                window="10m",
            ),
            AlertRule.slo_burn(
                error_metric="http_requests_total",
                slo_target=0.999,
                severity="critical",
            ),
            # Fully custom when standard templates don't fit
            AlertRule.custom(
                name="QueueSaturation",
                expr="rabbitmq_queue_messages > 10000",
                severity="warning",
                duration="5m",
            ),
        ],
    )

    yaml_str = export_yaml(rules, path="k8s/alerts.yaml")
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import yaml


@dataclass
class AlertRule:
    """
    A single Prometheus alerting rule.

    Use the class-method factories for standard SRE patterns:

    - ``AlertRule.error_rate(...)``
    - ``AlertRule.latency(...)``
    - ``AlertRule.no_traffic(...)``
    - ``AlertRule.slo_burn(...)``
    - ``AlertRule.custom(...)``

    Attributes
    ----------
    alert : str
        Alert name (appears in Alertmanager).
    expr : str
        PromQL expression that triggers the alert when true.
    severity : str
        Alert severity label (e.g. ``"critical"``, ``"warning"``).
    duration : str
        How long the condition must be true before firing. Default: ``"2m"``.
    labels : dict
        Extra Alertmanager labels.
    annotations : dict
        Alert annotations (summary, description, runbook_url, etc.).
    """

    alert: str
    expr: str
    severity: str
    duration: str = "2m"
    labels: dict[str, str] = field(default_factory=dict)
    annotations: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to Prometheus YAML rule dict."""
        return {
            "alert": self.alert,
            "expr": self.expr,
            "for": self.duration,
            "labels": {"severity": self.severity, **self.labels},
            "annotations": self.annotations,
        }

    # ------------------------------------------------------------------
    # Standard SRE alert templates
    # ------------------------------------------------------------------

    @classmethod
    def error_rate(
        cls,
        *,
        metric: str,
        threshold: float = 0.05,
        severity: str = "critical",
        window: str = "2m",
        duration: str = "2m",
        name: str = "HighErrorRate",
        error_label: str = "error",
        labels: dict[str, str] | None = None,
        annotations: dict[str, str] | None = None,
    ) -> AlertRule:
        """
        Standard error-rate alert.

        Fires when the proportion of ``status="<error_label>"`` requests
        exceeds ``threshold`` over ``window``.

        Parameters
        ----------
        metric : str
            Counter metric name (e.g. ``"http_requests_total"``).
        threshold : float
            Error fraction to trigger on (default: ``0.05`` = 5%).
        severity : str
            Alert severity (default: ``"critical"``).
        window : str
            PromQL rate window (default: ``"2m"``).
        duration : str
            How long before firing (default: ``"2m"``).
        name : str
            Alert name (default: ``"HighErrorRate"``).
        error_label : str
            Value of the ``status`` label that counts as an error
            (default: ``"error"``).
        labels : dict, optional
            Extra Alertmanager labels.
        annotations : dict, optional
            Custom annotations (overrides defaults).

        Example
        -------
        >>> AlertRule.error_rate(
        ...     metric="http_requests_total",
        ...     threshold=0.05,
        ...     severity="critical",
        ... )
        """
        pct = f"{threshold * 100:.0f}%"
        expr = (
            f'rate({metric}{{status="{error_label}"}}[{window}])'
            f" / rate({metric}[{window}])"
            f" > {threshold}"
        )
        return cls(
            alert=name,
            expr=expr,
            severity=severity,
            duration=duration,
            labels=labels or {},
            annotations=annotations
            or {
                "summary": f"High error rate (> {pct})",
                "description": (
                    f"Error rate above {pct} over the last {window}. Metric: {metric}."
                ),
            },
        )

    @classmethod
    def latency(
        cls,
        *,
        metric: str,
        percentile: float = 0.99,
        threshold_ms: float = 2000,
        severity: str = "warning",
        window: str = "5m",
        duration: str = "3m",
        name: str = "HighLatency",
        labels: dict[str, str] | None = None,
        annotations: dict[str, str] | None = None,
    ) -> AlertRule:
        """
        Standard latency-percentile alert.

        Fires when the Nth percentile latency exceeds ``threshold_ms``.

        Parameters
        ----------
        metric : str
            Histogram metric **base** name, without ``_bucket`` suffix
            (e.g. ``"http_request_duration_seconds"``).
        percentile : float
            Quantile to evaluate (default: ``0.99`` = p99).
        threshold_ms : float
            Threshold in **milliseconds** (default: ``2000`` = 2 s).
        severity : str
            Alert severity (default: ``"warning"``).
        window : str
            PromQL rate window (default: ``"5m"``).
        duration : str
            How long before firing (default: ``"3m"``).
        name : str
            Alert name (default: ``"HighLatency"``).

        Example
        -------
        >>> AlertRule.latency(
        ...     metric="http_request_duration_seconds",
        ...     percentile=0.99,
        ...     threshold_ms=2000,
        ... )
        """
        p_label = f"p{int(percentile * 100)}"
        threshold_s = threshold_ms / 1000
        expr = (
            f"histogram_quantile({percentile}, "
            f"sum(rate({metric}_bucket[{window}])) by (le))"
            f" > {threshold_s}"
        )
        return cls(
            alert=name,
            expr=expr,
            severity=severity,
            duration=duration,
            labels=labels or {},
            annotations=annotations
            or {
                "summary": f"High {p_label} latency (> {threshold_ms:.0f}ms)",
                "description": (
                    f"{p_label} latency exceeds {threshold_ms:.0f}ms "
                    f"over the last {window}. Metric: {metric}."
                ),
            },
        )

    @classmethod
    def no_traffic(
        cls,
        *,
        metric: str,
        window: str = "10m",
        severity: str = "warning",
        duration: str = "10m",
        name: str = "NoTraffic",
        labels: dict[str, str] | None = None,
        annotations: dict[str, str] | None = None,
    ) -> AlertRule:
        """
        Alert when the service receives zero traffic.

        Fires when ``sum(rate(metric[window])) == 0`` for ``duration``.

        Parameters
        ----------
        metric : str
            Counter metric name (e.g. ``"http_requests_total"``).
        window : str
            Rate window (default: ``"10m"``).
        severity : str
            Alert severity (default: ``"warning"``).
        duration : str
            How long before firing (default: ``"10m"``).
        name : str
            Alert name (default: ``"NoTraffic"``).

        Example
        -------
        >>> AlertRule.no_traffic(metric="http_requests_total")
        """
        expr = f"sum(rate({metric}[{window}])) == 0"
        return cls(
            alert=name,
            expr=expr,
            severity=severity,
            duration=duration,
            labels=labels or {},
            annotations=annotations
            or {
                "summary": "No traffic received",
                "description": f"No requests received in the last {window}. Metric: {metric}.",
            },
        )

    @classmethod
    def slo_burn(
        cls,
        *,
        error_metric: str,
        slo_target: float = 0.999,
        fast_window: str = "5m",
        slow_window: str = "1h",
        burn_factor: float = 14.4,
        severity: str = "critical",
        duration: str = "2m",
        name: str = "SLOBurnFast",
        error_label: str = "error",
        labels: dict[str, str] | None = None,
        annotations: dict[str, str] | None = None,
    ) -> AlertRule:
        """
        Multi-window SLO error-budget burn-rate alert (Google SRE approach).

        Fires when the error budget is burning at ``burn_factor`` times the
        sustainable rate, confirmed over both a fast and a slow window.

        Parameters
        ----------
        error_metric : str
            Counter metric name (e.g. ``"http_requests_total"``).
        slo_target : float
            SLO availability target (default: ``0.999`` = 99.9%).
        fast_window : str
            Short confirmation window (default: ``"5m"``).
        slow_window : str
            Long confirmation window (default: ``"1h"``).
        burn_factor : float
            Burn rate multiplier (default: ``14.4`` = 2% of monthly budget/hour).
        severity : str
            Alert severity (default: ``"critical"``).
        duration : str
            How long before firing (default: ``"2m"``).
        name : str
            Alert name (default: ``"SLOBurnFast"``).
        error_label : str
            Value of the ``status`` label that counts as an error (default: ``"error"``).

        Example
        -------
        >>> AlertRule.slo_burn(
        ...     error_metric="http_requests_total",
        ...     slo_target=0.999,
        ...     burn_factor=14.4,
        ...     severity="critical",
        ... )
        """
        error_budget = round(1 - slo_target, 6)
        burn_expr_fast = (
            f'rate({error_metric}{{status="{error_label}"}}[{fast_window}])'
            f" / rate({error_metric}[{fast_window}])"
            f" / {error_budget}"
        )
        burn_expr_slow = (
            f'rate({error_metric}{{status="{error_label}"}}[{slow_window}])'
            f" / rate({error_metric}[{slow_window}])"
            f" / {error_budget}"
        )
        expr = f"{burn_expr_fast} > {burn_factor}\nand\n{burn_expr_slow} > {burn_factor}"
        return cls(
            alert=name,
            expr=expr,
            severity=severity,
            duration=duration,
            labels=labels or {},
            annotations=annotations
            or {
                "summary": f"SLO error budget burning {burn_factor}x too fast",
                "description": (
                    f"Error budget burning at {burn_factor}x the sustainable rate. "
                    f"SLO target: {slo_target * 100:.2f}%. Metric: {error_metric}."
                ),
            },
        )

    @classmethod
    def custom(
        cls,
        *,
        name: str,
        expr: str,
        severity: str,
        duration: str = "2m",
        labels: dict[str, str] | None = None,
        annotations: dict[str, str] | None = None,
    ) -> AlertRule:
        """
        Fully custom alert rule — use when standard templates don't fit.

        Parameters
        ----------
        name : str
            Alert name.
        expr : str
            Raw PromQL expression.
        severity : str
            Alert severity.
        duration : str
            How long before firing (default: ``"2m"``).
        labels : dict, optional
            Extra Alertmanager labels.
        annotations : dict, optional
            Alert annotations.

        Example
        -------
        >>> AlertRule.custom(
        ...     name="QueueSaturation",
        ...     expr="rabbitmq_queue_messages > 10000",
        ...     severity="warning",
        ...     duration="5m",
        ...     annotations={"summary": "Queue is saturated"},
        ... )
        """
        return cls(
            alert=name,
            expr=expr,
            severity=severity,
            duration=duration,
            labels=labels or {},
            annotations=annotations or {},
        )


@dataclass
class AlertGroup:
    """
    A named group of ``AlertRule`` objects.

    Maps directly to a Prometheus ``groups[].rules`` block.

    Parameters
    ----------
    name : str
        Group name (appears in Prometheus rule files).
    rules : list[AlertRule]
        Alert rules in this group.
    interval : str, optional
        Override evaluation interval (e.g. ``"30s"``).

    Example
    -------
    >>> from obskit.alerts import AlertRule, AlertGroup
    >>>
    >>> group = AlertGroup(
    ...     name="order-service",
    ...     rules=[
    ...         AlertRule.error_rate(metric="http_requests_total"),
    ...         AlertRule.latency(metric="http_request_duration_seconds"),
    ...     ],
    ... )
    """

    name: str
    rules: list[AlertRule] = field(default_factory=list)
    interval: str | None = None

    def add(self, rule: AlertRule) -> AlertGroup:
        """Append a rule and return self (fluent API)."""
        self.rules.append(rule)
        return self

    def to_dict(self) -> dict[str, Any]:
        """Serialize to Prometheus YAML group dict."""
        group: dict[str, Any] = {
            "name": self.name,
            "rules": [rule.to_dict() for rule in self.rules],
        }
        if self.interval:
            group["interval"] = self.interval
        return group


def export_yaml(
    *groups: AlertGroup,
    path: str | None = None,
) -> str:
    """
    Export one or more ``AlertGroup`` objects to Prometheus YAML format.

    Parameters
    ----------
    *groups : AlertGroup
        One or more groups to export.
    path : str, optional
        File path to write the YAML to. Parent directories are created
        automatically. If ``None``, only the string is returned.

    Returns
    -------
    str
        Valid Prometheus alert-rules YAML string.

    Example
    -------
    >>> from obskit.alerts import AlertRule, AlertGroup, export_yaml
    >>>
    >>> g = AlertGroup(
    ...     name="my-service",
    ...     rules=[
    ...         AlertRule.error_rate(metric="http_requests_total"),
    ...         AlertRule.no_traffic(metric="http_requests_total"),
    ...     ],
    ... )
    >>> yaml_str = export_yaml(g, path="k8s/alerts.yaml")

    Multiple groups
    ---------------
    >>> yaml_str = export_yaml(group_a, group_b, path="k8s/all-alerts.yaml")
    """
    payload: dict[str, Any] = {"groups": [g.to_dict() for g in groups]}
    yaml_str: str = yaml.dump(payload, default_flow_style=False, sort_keys=False)

    if path:
        parent = os.path.dirname(path)
        if parent:  # pragma: no branch
            os.makedirs(parent, exist_ok=True)
        with open(path, "w") as fh:
            fh.write(yaml_str)

    return yaml_str


__all__ = [
    "AlertRule",
    "AlertGroup",
    "export_yaml",
]
