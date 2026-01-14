"""Alerting Rules Module - Configurable Prometheus alerting rules."""

from obskit.alerts.config import AlertConfig, generate_prometheus_rules

__all__ = ["AlertConfig", "generate_prometheus_rules"]
