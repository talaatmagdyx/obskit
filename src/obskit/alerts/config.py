"""
Configurable Alerting Rules Configuration
==========================================

This module provides configuration for Prometheus alerting rules,
allowing users to customize thresholds and alert conditions.

Example - Basic Usage
---------------------
.. code-block:: python

    from obskit.alerts.config import AlertConfig, generate_prometheus_rules

    # Create custom configuration
    config = AlertConfig(
        error_rate_threshold=0.05,  # 5% instead of default 1%
        critical_error_rate_threshold=0.20,  # 20% instead of default 10%
        latency_p95_threshold=0.3,  # 300ms instead of default 500ms
    )

    # Generate Prometheus rules YAML
    rules_yaml = generate_prometheus_rules(config)

    # Write to file
    with open("prometheus_rules.yml", "w") as f:
        f.write(rules_yaml)

Example - From Environment Variables
-------------------------------------
.. code-block:: python

    from obskit.alerts.config import AlertConfig, generate_prometheus_rules
    import os

    config = AlertConfig.from_env()
    rules_yaml = generate_prometheus_rules(config)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AlertConfig:
    """
    Configuration for Prometheus alerting rules.

    All thresholds are customizable to match your service requirements.

    Parameters
    ----------
    error_rate_threshold : float
        Error rate threshold for HighErrorRate alert (default: 0.01 = 1%).

    critical_error_rate_threshold : float
        Error rate threshold for CriticalErrorRate alert (default: 0.10 = 10%).

    latency_p95_threshold : float
        P95 latency threshold in seconds (default: 0.5 = 500ms).

    latency_p99_threshold : float
        P99 latency threshold in seconds (default: 1.0 = 1s).

    low_request_rate_threshold : float
        Low request rate threshold in req/s (default: 0.1).

    saturation_warning_threshold : float
        Saturation warning threshold (default: 0.90 = 90%).

    saturation_critical_threshold : float
        Saturation critical threshold (default: 0.95 = 95%).

    queue_depth_threshold : int
        High queue depth threshold (default: 1000).

    cpu_utilization_threshold : float
        CPU utilization threshold (default: 0.90 = 90%).

    memory_utilization_threshold : float
        Memory utilization threshold (default: 0.90 = 90%).

    cpu_saturation_threshold : float
        CPU saturation threshold (default: 10 processes).

    service_degraded_error_rate : float
        Error rate for service degraded alert (default: 0.05 = 5%).

    service_degraded_latency : float
        Latency for service degraded alert (default: 1.0 = 1s).

    slo_error_budget_threshold : float
        Error budget threshold for SLO alerts (default: 0.001 = 0.1%).

    slo_latency_threshold : float
        Latency threshold for SLO alerts (default: 0.2 = 200ms).

    alert_intervals : dict[str, int]
        Alert evaluation intervals in seconds (default: various).

    alert_durations : dict[str, int]
        Alert duration requirements in seconds (default: various).
    """

    # Error Rate Thresholds
    error_rate_threshold: float = 0.01  # 1%
    critical_error_rate_threshold: float = 0.10  # 10%

    # Latency Thresholds (in seconds)
    latency_p95_threshold: float = 0.5  # 500ms
    latency_p99_threshold: float = 1.0  # 1s

    # Request Rate Thresholds
    low_request_rate_threshold: float = 0.1  # req/s

    # Saturation Thresholds
    saturation_warning_threshold: float = 0.90  # 90%
    saturation_critical_threshold: float = 0.95  # 95%

    # Queue Thresholds
    queue_depth_threshold: int = 1000

    # Infrastructure Thresholds
    cpu_utilization_threshold: float = 0.90  # 90%
    memory_utilization_threshold: float = 0.90  # 90%
    cpu_saturation_threshold: float = 10.0  # processes

    # Service Degradation Thresholds
    service_degraded_error_rate: float = 0.05  # 5%
    service_degraded_latency: float = 1.0  # 1s

    # SLO Thresholds
    slo_error_budget_threshold: float = 0.001  # 0.1%
    slo_latency_threshold: float = 0.2  # 200ms

    # Alert Timing
    alert_intervals: dict[str, int] = field(
        default_factory=lambda: {
            "default": 30,
            "slo": 30,
        }
    )

    alert_durations: dict[str, int] = field(
        default_factory=lambda: {
            "high_error_rate": 300,  # 5m
            "critical_error_rate": 120,  # 2m
            "high_latency_p95": 600,  # 10m
            "critical_latency_p99": 300,  # 5m
            "low_request_rate": 900,  # 15m
            "high_saturation": 300,  # 5m
            "critical_saturation": 120,  # 2m
            "high_queue_depth": 300,  # 5m
            "high_cpu": 600,  # 10m
            "high_memory": 300,  # 5m
            "cpu_saturation": 300,  # 5m
            "infrastructure_errors": 60,  # 1m
            "service_down": 900,  # 15m
            "service_degraded": 300,  # 5m
            "slo_error_budget": 3600,  # 1h
            "slo_latency": 600,  # 10m
        }
    )

    @classmethod
    def from_env(cls) -> AlertConfig:
        """
        Create AlertConfig from environment variables.

        Environment Variables:
        - OBSKIT_ALERT_ERROR_RATE_THRESHOLD
        - OBSKIT_ALERT_CRITICAL_ERROR_RATE_THRESHOLD
        - OBSKIT_ALERT_LATENCY_P95_THRESHOLD
        - OBSKIT_ALERT_LATENCY_P99_THRESHOLD
        - OBSKIT_ALERT_LOW_REQUEST_RATE_THRESHOLD
        - OBSKIT_ALERT_SATURATION_WARNING_THRESHOLD
        - OBSKIT_ALERT_SATURATION_CRITICAL_THRESHOLD
        - OBSKIT_ALERT_QUEUE_DEPTH_THRESHOLD
        - OBSKIT_ALERT_CPU_UTILIZATION_THRESHOLD
        - OBSKIT_ALERT_MEMORY_UTILIZATION_THRESHOLD
        - OBSKIT_ALERT_CPU_SATURATION_THRESHOLD
        - OBSKIT_ALERT_SERVICE_DEGRADED_ERROR_RATE
        - OBSKIT_ALERT_SERVICE_DEGRADED_LATENCY
        - OBSKIT_ALERT_SLO_ERROR_BUDGET_THRESHOLD
        - OBSKIT_ALERT_SLO_LATENCY_THRESHOLD

        Returns
        -------
        AlertConfig
            Configuration from environment variables.
        """
        import os

        def get_float(key: str, default: float) -> float:
            value = os.getenv(key)
            return float(value) if value else default

        def get_int(key: str, default: int) -> int:
            value = os.getenv(key)
            return int(value) if value else default

        return cls(
            error_rate_threshold=get_float("OBSKIT_ALERT_ERROR_RATE_THRESHOLD", 0.01),
            critical_error_rate_threshold=get_float(
                "OBSKIT_ALERT_CRITICAL_ERROR_RATE_THRESHOLD", 0.10
            ),
            latency_p95_threshold=get_float("OBSKIT_ALERT_LATENCY_P95_THRESHOLD", 0.5),
            latency_p99_threshold=get_float("OBSKIT_ALERT_LATENCY_P99_THRESHOLD", 1.0),
            low_request_rate_threshold=get_float("OBSKIT_ALERT_LOW_REQUEST_RATE_THRESHOLD", 0.1),
            saturation_warning_threshold=get_float(
                "OBSKIT_ALERT_SATURATION_WARNING_THRESHOLD", 0.90
            ),
            saturation_critical_threshold=get_float(
                "OBSKIT_ALERT_SATURATION_CRITICAL_THRESHOLD", 0.95
            ),
            queue_depth_threshold=get_int("OBSKIT_ALERT_QUEUE_DEPTH_THRESHOLD", 1000),
            cpu_utilization_threshold=get_float("OBSKIT_ALERT_CPU_UTILIZATION_THRESHOLD", 0.90),
            memory_utilization_threshold=get_float(
                "OBSKIT_ALERT_MEMORY_UTILIZATION_THRESHOLD", 0.90
            ),
            cpu_saturation_threshold=get_float("OBSKIT_ALERT_CPU_SATURATION_THRESHOLD", 10.0),
            service_degraded_error_rate=get_float("OBSKIT_ALERT_SERVICE_DEGRADED_ERROR_RATE", 0.05),
            service_degraded_latency=get_float("OBSKIT_ALERT_SERVICE_DEGRADED_LATENCY", 1.0),
            slo_error_budget_threshold=get_float("OBSKIT_ALERT_SLO_ERROR_BUDGET_THRESHOLD", 0.001),
            slo_latency_threshold=get_float("OBSKIT_ALERT_SLO_LATENCY_THRESHOLD", 0.2),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "error_rate_threshold": self.error_rate_threshold,
            "critical_error_rate_threshold": self.critical_error_rate_threshold,
            "latency_p95_threshold": self.latency_p95_threshold,
            "latency_p99_threshold": self.latency_p99_threshold,
            "low_request_rate_threshold": self.low_request_rate_threshold,
            "saturation_warning_threshold": self.saturation_warning_threshold,
            "saturation_critical_threshold": self.saturation_critical_threshold,
            "queue_depth_threshold": self.queue_depth_threshold,
            "cpu_utilization_threshold": self.cpu_utilization_threshold,
            "memory_utilization_threshold": self.memory_utilization_threshold,
            "cpu_saturation_threshold": self.cpu_saturation_threshold,
            "service_degraded_error_rate": self.service_degraded_error_rate,
            "service_degraded_latency": self.service_degraded_latency,
            "slo_error_budget_threshold": self.slo_error_budget_threshold,
            "slo_latency_threshold": self.slo_latency_threshold,
            "alert_intervals": self.alert_intervals,
            "alert_durations": self.alert_durations,
        }


def generate_prometheus_rules(config: AlertConfig | None = None) -> str:
    """
    Generate Prometheus alerting rules YAML from configuration.

    Parameters
    ----------
    config : AlertConfig, optional
        Alert configuration. If None, uses default configuration.

    Returns
    -------
    str
        Prometheus alerting rules YAML.

    Example
    -------
    >>> from obskit.alerts.config import AlertConfig, generate_prometheus_rules
    >>>
    >>> config = AlertConfig(error_rate_threshold=0.05)
    >>> rules_yaml = generate_prometheus_rules(config)
    >>>
    >>> with open("prometheus_rules.yml", "w") as f:
    ...     f.write(rules_yaml)
    """
    if config is None:
        config = AlertConfig()

    # Template for Prometheus rules
    template = f"""# Prometheus Alerting Rules for obskit
# =====================================
#
# This file is auto-generated from AlertConfig.
# To customize, use: from obskit.alerts.config import AlertConfig, generate_prometheus_rules
#
# Configuration:
#   Error Rate Threshold: {config.error_rate_threshold} ({config.error_rate_threshold * 100}%)
#   Critical Error Rate: {config.critical_error_rate_threshold} ({config.critical_error_rate_threshold * 100}%)
#   P95 Latency Threshold: {config.latency_p95_threshold}s ({config.latency_p95_threshold * 1000}ms)
#   P99 Latency Threshold: {config.latency_p99_threshold}s ({config.latency_p99_threshold * 1000}ms)
#
# Alert Severity Levels:
#   - critical: Immediate action required
#   - warning: Attention needed, may escalate
#   - info: Informational, monitor closely

groups:
  # ========================================================================
  # RED Method Alerts
  # ========================================================================
  - name: red_method_alerts
    interval: {config.alert_intervals.get("default", 30)}s
    rules:
      # High Error Rate Alert
      - alert: HighErrorRate
        expr: |
          sum(rate({{__name__=~".*_errors_total"}}[5m])) by (service, operation, error_type)
          /
          sum(rate({{__name__=~".*_requests_total"}}[5m])) by (service, operation)
          > {config.error_rate_threshold}
        for: {config.alert_durations.get("high_error_rate", 300)}s
        labels:
          severity: critical
          alert_type: error_rate
        annotations:
          summary: "High error rate detected: {{ $labels.operation }}"
          description: |
            Error rate is {{ $value | humanizePercentage }} for operation {{ $labels.operation }}.
            Error type: {{ $labels.error_type }}
            Service: {{ $labels.service }}
            Threshold: {config.error_rate_threshold * 100}%

      # Critical Error Rate (Very High)
      - alert: CriticalErrorRate
        expr: |
          sum(rate({{__name__=~".*_errors_total"}}[5m])) by (service, operation)
          /
          sum(rate({{__name__=~".*_requests_total"}}[5m])) by (service, operation)
          > {config.critical_error_rate_threshold}
        for: {config.alert_durations.get("critical_error_rate", 120)}s
        labels:
          severity: critical
          alert_type: error_rate
        annotations:
          summary: "CRITICAL: Error rate > {config.critical_error_rate_threshold * 100}% for {{ $labels.operation }}"
          description: |
            Error rate is {{ $value | humanizePercentage }} for {{ $labels.operation }}.
            Service: {{ $labels.service }}
            Threshold: {config.critical_error_rate_threshold * 100}%

      # High Latency Alert (P95)
      - alert: HighLatencyP95
        expr: |
          histogram_quantile(0.95,
            sum(rate({{__name__=~".*_request_duration_seconds_bucket"}}[5m])) by (le, operation, service)
          ) > {config.latency_p95_threshold}
        for: {config.alert_durations.get("high_latency_p95", 600)}s
        labels:
          severity: warning
          alert_type: latency
        annotations:
          summary: "P95 latency > {config.latency_p95_threshold * 1000}ms for {{ $labels.operation }}"
          description: |
            P95 latency is {{ $value | humanizeDuration }} for operation {{ $labels.operation }}.
            Service: {{ $labels.service }}
            Threshold: {config.latency_p95_threshold * 1000}ms

      # Critical Latency Alert (P99)
      - alert: CriticalLatencyP99
        expr: |
          histogram_quantile(0.99,
            sum(rate({{__name__=~".*_request_duration_seconds_bucket"}}[5m])) by (le, operation, service)
          ) > {config.latency_p99_threshold}
        for: {config.alert_durations.get("critical_latency_p99", 300)}s
        labels:
          severity: critical
          alert_type: latency
        annotations:
          summary: "P99 latency > {config.latency_p99_threshold * 1000}ms for {{ $labels.operation }}"
          description: |
            P99 latency is {{ $value | humanizeDuration }} for operation {{ $labels.operation }}.
            Service: {{ $labels.service }}
            Threshold: {config.latency_p99_threshold * 1000}ms

      # Low Request Rate (Service May Be Down)
      - alert: LowRequestRate
        expr: |
          sum(rate({{__name__=~".*_requests_total"}}[5m])) by (service, operation) < {config.low_request_rate_threshold}
        for: {config.alert_durations.get("low_request_rate", 900)}s
        labels:
          severity: warning
          alert_type: availability
        annotations:
          summary: "Low request rate for {{ $labels.operation }}"
          description: |
            Request rate is {{ $value | humanize }} req/s for {{ $labels.operation }}.
            Service may be experiencing issues.
            Service: {{ $labels.service }}
            Threshold: {config.low_request_rate_threshold} req/s

  # ========================================================================
  # Golden Signals Alerts
  # ========================================================================
  - name: golden_signals_alerts
    interval: {config.alert_intervals.get("default", 30)}s
    rules:
      # High Saturation Alert
      - alert: HighSaturation
        expr: |
          {{__name__=~".*_saturation"}} > {config.saturation_warning_threshold}
        for: {config.alert_durations.get("high_saturation", 300)}s
        labels:
          severity: warning
          alert_type: saturation
        annotations:
          summary: "High saturation detected: {{ $labels.resource }}"
          description: |
            Saturation is {{ $value | humanizePercentage }} for resource {{ $labels.resource }}.
            Service: {{ $labels.service }}
            Threshold: {config.saturation_warning_threshold * 100}%

      # Critical Saturation Alert
      - alert: CriticalSaturation
        expr: |
          {{__name__=~".*_saturation"}} > {config.saturation_critical_threshold}
        for: {config.alert_durations.get("critical_saturation", 120)}s
        labels:
          severity: critical
          alert_type: saturation
        annotations:
          summary: "CRITICAL: Saturation > {config.saturation_critical_threshold * 100}% for {{ $labels.resource }}"
          description: |
            Saturation is {{ $value | humanizePercentage }} for resource {{ $labels.resource }}.
            Service: {{ $labels.service }}
            Threshold: {config.saturation_critical_threshold * 100}%

      # High Queue Depth
      - alert: HighQueueDepth
        expr: |
          {{__name__=~".*_queue_depth"}} > {config.queue_depth_threshold}
        for: {config.alert_durations.get("high_queue_depth", 300)}s
        labels:
          severity: warning
          alert_type: queue
        annotations:
          summary: "High queue depth: {{ $labels.queue }}"
          description: |
            Queue depth is {{ $value | humanize }} for queue {{ $labels.queue }}.
            Service: {{ $labels.service }}
            Threshold: {config.queue_depth_threshold}

  # ========================================================================
  # USE Method Alerts (Infrastructure)
  # ========================================================================
  - name: use_method_alerts
    interval: {config.alert_intervals.get("default", 30)}s
    rules:
      # High CPU Utilization
      - alert: HighCPUUtilization
        expr: |
          {{__name__=~".*_utilization", resource="cpu"}} > {config.cpu_utilization_threshold}
        for: {config.alert_durations.get("high_cpu", 600)}s
        labels:
          severity: warning
          alert_type: infrastructure
        annotations:
          summary: "High CPU utilization: {{ $value | humanizePercentage }}"
          description: |
            CPU utilization is {{ $value | humanizePercentage }}.
            Resource: {{ $labels.resource }}
            Threshold: {config.cpu_utilization_threshold * 100}%

      # High Memory Utilization
      - alert: HighMemoryUtilization
        expr: |
          {{__name__=~".*_utilization", resource="memory"}} > {config.memory_utilization_threshold}
        for: {config.alert_durations.get("high_memory", 300)}s
        labels:
          severity: warning
          alert_type: infrastructure
        annotations:
          summary: "High memory utilization: {{ $value | humanizePercentage }}"
          description: |
            Memory utilization is {{ $value | humanizePercentage }}.
            Resource: {{ $labels.resource }}
            Threshold: {config.memory_utilization_threshold * 100}%

      # CPU Saturation (Processes Waiting)
      - alert: CPUSaturation
        expr: |
          {{__name__=~".*_saturation", resource="cpu"}} > {config.cpu_saturation_threshold}
        for: {config.alert_durations.get("cpu_saturation", 300)}s
        labels:
          severity: warning
          alert_type: infrastructure
        annotations:
          summary: "CPU saturation: {{ $value }} processes waiting"
          description: |
            {{ $value }} processes are waiting for CPU.
            Resource: {{ $labels.resource }}
            Threshold: {config.cpu_saturation_threshold}

      # Infrastructure Errors
      - alert: InfrastructureErrors
        expr: |
          rate({{__name__=~".*_errors_total"}}[5m]) > 0
        for: {config.alert_durations.get("infrastructure_errors", 60)}s
        labels:
          severity: critical
          alert_type: infrastructure
        annotations:
          summary: "Infrastructure errors detected: {{ $labels.resource }}"
          description: |
            Error rate is {{ $value | humanize }} errors/s for resource {{ $labels.resource }}.
            Error type: {{ $labels.error_type }}

  # ========================================================================
  # Service Health Alerts
  # ========================================================================
  - name: service_health_alerts
    interval: {config.alert_intervals.get("default", 30)}s
    rules:
      # Service Down (No Metrics)
      - alert: ServiceDown
        expr: |
          absent({{__name__=~".*_requests_total"}}) or
          sum(rate({{__name__=~".*_requests_total"}}[15m])) == 0
        for: {config.alert_durations.get("service_down", 900)}s
        labels:
          severity: critical
          alert_type: availability
        annotations:
          summary: "Service appears to be down: No metrics received"
          description: |
            No metrics have been received from the service in the last 15 minutes.
            The service may be down or metrics collection is broken.

      # Service Degraded (High Error Rate + High Latency)
      - alert: ServiceDegraded
        expr: |
          (
            sum(rate({{__name__=~".*_errors_total"}}[5m])) by (service)
            /
            sum(rate({{__name__=~".*_requests_total"}}[5m])) by (service)
            > {config.service_degraded_error_rate}
          ) and (
            histogram_quantile(0.95,
              sum(rate({{__name__=~".*_request_duration_seconds_bucket"}}[5m])) by (le, service)
            ) > {config.service_degraded_latency}
          )
        for: {config.alert_durations.get("service_degraded", 300)}s
        labels:
          severity: critical
          alert_type: degradation
        annotations:
          summary: "Service degraded: High errors and latency"
          description: |
            Service {{ $labels.service }} is experiencing both high error rates and high latency.
            Error rate: > {config.service_degraded_error_rate * 100}%
            P95 latency: > {config.service_degraded_latency * 1000}ms

  # ========================================================================
  # SLO-Based Alerts
  # ========================================================================
  - name: slo_alerts
    interval: {config.alert_intervals.get("slo", 30)}s
    rules:
      # Error Budget Burn Rate
      - alert: HighErrorBudgetBurnRate
        expr: |
          # Example: 99.9% availability SLO
          (
            sum(rate({{__name__=~".*_errors_total"}}[1h])) by (service)
            /
            sum(rate({{__name__=~".*_requests_total"}}[1h])) by (service)
          ) > {config.slo_error_budget_threshold}
        for: {config.alert_durations.get("slo_error_budget", 3600)}s
        labels:
          severity: warning
          alert_type: slo
        annotations:
          summary: "Error budget burn rate high for {{ $labels.service }}"
          description: |
            Service {{ $labels.service }} is consuming error budget faster than expected.
            Current error rate: {{ $value | humanizePercentage }}
            Threshold: {config.slo_error_budget_threshold * 100}%

      # Latency SLO Violation
      - alert: LatencySLOViolation
        expr: |
          # Example: P95 latency < 200ms SLO
          histogram_quantile(0.95,
            sum(rate({{__name__=~".*_request_duration_seconds_bucket"}}[5m])) by (le, service, operation)
          ) > {config.slo_latency_threshold}
        for: {config.alert_durations.get("slo_latency", 600)}s
        labels:
          severity: warning
          alert_type: slo
        annotations:
          summary: "Latency SLO violation: {{ $labels.operation }}"
          description: |
            Operation {{ $labels.operation }} is violating latency SLO.
            P95 latency: {{ $value | humanizeDuration }}
            SLO: < {config.slo_latency_threshold * 1000}ms
"""

    return template


__all__ = ["AlertConfig", "generate_prometheus_rules"]
