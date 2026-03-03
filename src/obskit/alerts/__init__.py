"""
Alerting Rules Module
=====================

Configurable Prometheus alerting rules, slow operation detection,
and rules generation utilities.

Fluent Builder API (recommended)
---------------------------------
Use ``AlertRule``, ``AlertGroup``, and ``export_yaml`` for a clean,
fully-parameterized approach to building standard SRE alert rules:

.. code-block:: python

    from obskit.alerts import AlertRule, AlertGroup, export_yaml

    group = AlertGroup(
        name="order-service",
        rules=[
            AlertRule.error_rate(metric="http_requests_total", threshold=0.05),
            AlertRule.latency(metric="http_request_duration_seconds", threshold_ms=2000),
            AlertRule.no_traffic(metric="http_requests_total"),
            AlertRule.slo_burn(error_metric="http_requests_total", slo_target=0.999),
            AlertRule.custom(
                name="QueueSaturation",
                expr="rabbitmq_queue_messages > 10000",
                severity="warning",
            ),
        ],
    )

    yaml_str = export_yaml(group, path="k8s/alerts.yaml")
"""

from obskit.alerts.builder import AlertGroup, AlertRule, export_yaml
from obskit.alerts.config import AlertConfig, generate_prometheus_rules
from obskit.alerts.rules_generator import (
    SLODefinition,
    generate_alert_rules,
    generate_all_rules,
    generate_recording_rules,
    generate_slo_recording_rules,
    save_rules,
)
from obskit.alerts.slow_operation import SlowOperationDetector, check_slow_operation

__all__ = [
    # ==========================================================================
    # Fluent Builder API (recommended for new code)
    # ==========================================================================
    # Single alert rule with SRE factory methods
    "AlertRule",
    # Named group of alert rules → maps to Prometheus groups[].rules
    "AlertGroup",
    # Export one or more AlertGroup objects to Prometheus YAML
    "export_yaml",
    # ==========================================================================
    # Config
    # ==========================================================================
    "AlertConfig",
    "generate_prometheus_rules",
    # ==========================================================================
    # Slow Operation
    # ==========================================================================
    "SlowOperationDetector",
    "check_slow_operation",
    # ==========================================================================
    # Rules Generator (lower-level API)
    # ==========================================================================
    "SLODefinition",
    "generate_recording_rules",
    "generate_slo_recording_rules",
    "generate_alert_rules",
    "generate_all_rules",
    "save_rules",
]
