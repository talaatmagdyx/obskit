"""
Alerting Rules Module
=====================

Configurable Prometheus alerting rules, slow operation detection,
and rules generation utilities.
"""

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
    # Config
    "AlertConfig",
    "generate_prometheus_rules",
    # Slow Operation
    "SlowOperationDetector",
    "check_slow_operation",
    # Rules Generator
    "SLODefinition",
    "generate_recording_rules",
    "generate_slo_recording_rules",
    "generate_alert_rules",
    "generate_all_rules",
    "save_rules",
]
