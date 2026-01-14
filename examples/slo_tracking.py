"""
Example: SLO Tracking with Error Budgets
========================================

This example shows how to implement Service Level Objectives (SLOs)
with error budget tracking and alerting using obskit.

Features:
- Define SLOs (availability, latency)
- Track error budgets
- Generate Prometheus alerting rules
- Alertmanager integration
"""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass as slo_dataclass
from typing import Any

from obskit import configure, get_logger, start_http_server
from obskit.alerts import AlertConfig, generate_prometheus_rules
from obskit.slo import SLOTracker, SLOType


# Define SLO structure for this example
@slo_dataclass
class SLODefinition:
    """SLO definition for this example."""

    name: str
    description: str
    target: float
    window_days: int = 30
    threshold_ms: float | None = None


def expose_slo_metrics() -> None:
    """Expose SLO metrics (stub for example)."""
    pass


def update_slo_metrics(slo_name: str, current_value: float, target: float) -> None:
    """Update SLO metrics (stub for example)."""
    pass


class SyncAlertmanagerWebhook:
    """Simple Alertmanager webhook client."""

    def __init__(self, alertmanager_url: str):
        self.url = alertmanager_url

    def send_alert(
        self,
        alert_name: str,
        severity: str,
        labels: dict[str, str],
        annotations: dict[str, str],
    ) -> None:
        """Send alert to Alertmanager."""
        print(f"ALERT: {alert_name} ({severity})")


# =============================================================================
# SLO Definitions
# =============================================================================

# Define your Service Level Objectives
SLO_DEFINITIONS = {
    "availability": SLODefinition(
        name="api_availability",
        description="API should be available 99.9% of the time",
        target=0.999,  # 99.9%
        window_days=30,
        # 30 days * 24 hours * 60 minutes * (1 - 0.999) = 43.2 minutes of allowed downtime
    ),
    "latency_p99": SLODefinition(
        name="api_latency_p99",
        description="99% of requests should complete within 500ms",
        target=0.99,  # 99%
        window_days=30,
        threshold_ms=500,
    ),
    "latency_p95": SLODefinition(
        name="api_latency_p95",
        description="95% of requests should complete within 200ms",
        target=0.95,
        window_days=30,
        threshold_ms=200,
    ),
    "error_rate": SLODefinition(
        name="api_error_rate",
        description="Error rate should be below 0.1%",
        target=0.999,  # 99.9% success = 0.1% error
        window_days=7,
    ),
}


# =============================================================================
# SLO Tracker Implementation
# =============================================================================


class ProductionSLOTracker:
    """
    Production-ready SLO tracking with error budgets.

    This class:
    - Tracks SLO compliance
    - Calculates error budgets
    - Generates alerts when budgets are consumed
    - Exposes metrics for Grafana dashboards
    """

    def __init__(self):
        self.tracker = SLOTracker()

        # Register SLOs using the tracker API
        self.tracker.register_slo(
            name="api_availability",
            slo_type=SLOType.AVAILABILITY,
            target_value=0.999,
            window_seconds=30 * 24 * 3600,  # 30 days
        )
        self.tracker.register_slo(
            name="api_latency_p99",
            slo_type=SLOType.LATENCY,
            target_value=0.99,
            window_seconds=30 * 24 * 3600,
            percentile=99,
        )
        self.tracker.register_slo(
            name="api_latency_p95",
            slo_type=SLOType.LATENCY,
            target_value=0.95,
            window_seconds=30 * 24 * 3600,
            percentile=95,
        )

        self.logger = get_logger("slo-tracker")

        # Counters for error budget calculation
        self.total_requests = 0
        self.successful_requests = 0
        self.requests_under_latency_threshold = {
            "p99_500ms": 0,
            "p95_200ms": 0,
        }

        # Expose SLO metrics
        expose_slo_metrics()

    def record_request(
        self,
        success: bool,
        latency_ms: float,
    ) -> None:
        """Record a request for SLO tracking."""
        self.total_requests += 1

        if success:
            self.successful_requests += 1

        if latency_ms < 500:
            self.requests_under_latency_threshold["p99_500ms"] += 1
        if latency_ms < 200:
            self.requests_under_latency_threshold["p95_200ms"] += 1

        # Update SLO metrics
        self._update_metrics()

    def _update_metrics(self) -> None:
        """Update Prometheus metrics for SLOs."""
        if self.total_requests == 0:
            return

        # Availability SLI
        availability = self.successful_requests / self.total_requests
        update_slo_metrics(
            slo_name="api_availability",
            current_value=availability,
            target=0.999,
        )

        # Latency P99 SLI
        latency_p99_compliance = (
            self.requests_under_latency_threshold["p99_500ms"] / self.total_requests
        )
        update_slo_metrics(
            slo_name="api_latency_p99",
            current_value=latency_p99_compliance,
            target=0.99,
        )

        # Latency P95 SLI
        latency_p95_compliance = (
            self.requests_under_latency_threshold["p95_200ms"] / self.total_requests
        )
        update_slo_metrics(
            slo_name="api_latency_p95",
            current_value=latency_p95_compliance,
            target=0.95,
        )

    def get_error_budget_status(self) -> dict[str, Any]:
        """Get current error budget status for all SLOs."""
        if self.total_requests == 0:
            return {"status": "no_data"}

        availability = self.successful_requests / self.total_requests

        # Calculate error budget
        # Error budget = (1 - SLO target) * total_requests
        availability_budget = (1 - 0.999) * self.total_requests
        availability_consumed = self.total_requests - self.successful_requests
        availability_remaining = max(0, availability_budget - availability_consumed)

        return {
            "availability": {
                "current": availability,
                "target": 0.999,
                "budget_total": availability_budget,
                "budget_consumed": availability_consumed,
                "budget_remaining": availability_remaining,
                "budget_remaining_percent": (
                    (availability_remaining / availability_budget * 100)
                    if availability_budget > 0
                    else 100
                ),
            },
            "latency_p99": {
                "current": self.requests_under_latency_threshold["p99_500ms"] / self.total_requests,
                "target": 0.99,
                "threshold_ms": 500,
            },
            "latency_p95": {
                "current": self.requests_under_latency_threshold["p95_200ms"] / self.total_requests,
                "target": 0.95,
                "threshold_ms": 200,
            },
        }

    def check_and_alert(self, alertmanager_url: str | None = None) -> list[dict[str, Any]]:
        """Check SLOs and send alerts if necessary."""
        alerts = []
        status = self.get_error_budget_status()

        if status.get("status") == "no_data":
            return alerts

        # Check availability
        avail = status["availability"]
        if avail["budget_remaining_percent"] < 20:
            alert = {
                "alert_name": "SLOErrorBudgetLow",
                "severity": "warning" if avail["budget_remaining_percent"] > 10 else "critical",
                "slo": "availability",
                "budget_remaining_percent": avail["budget_remaining_percent"],
            }
            alerts.append(alert)
            self.logger.warning(
                "slo_budget_low",
                slo="availability",
                budget_remaining=avail["budget_remaining_percent"],
            )

        # Send to Alertmanager if configured
        if alertmanager_url and alerts:
            self._send_alerts(alertmanager_url, alerts)

        return alerts

    def _send_alerts(self, alertmanager_url: str, alerts: list[dict[str, Any]]) -> None:
        """Send alerts to Alertmanager."""
        webhook = SyncAlertmanagerWebhook(alertmanager_url=alertmanager_url)

        for alert in alerts:
            webhook.send_alert(
                alert_name=alert["alert_name"],
                severity=alert["severity"],
                labels={"slo": alert["slo"]},
                annotations={
                    "summary": f"SLO error budget low: {alert['budget_remaining_percent']:.1f}% remaining",
                    "description": f"The {alert['slo']} SLO has consumed most of its error budget.",
                },
            )


# =============================================================================
# Prometheus Alerting Rules
# =============================================================================


def generate_slo_alerting_rules() -> str:
    """Generate Prometheus alerting rules for SLOs."""
    config = AlertConfig(
        error_rate_threshold=0.01,  # Alert if error rate > 1%
        latency_p99_threshold=0.5,  # Alert if p99 > 500ms
        latency_p95_threshold=0.2,  # Alert if p95 > 200ms
    )

    return generate_prometheus_rules(config)


# =============================================================================
# Example Prometheus Rules (Manual)
# =============================================================================

PROMETHEUS_SLO_RULES = """
# prometheus_rules.yml - SLO-based alerting rules

groups:
  - name: slo.rules
    rules:
      # =========================================
      # SLO: Availability (99.9%)
      # =========================================

      # Record: 5-minute error rate
      - record: slo:api_availability:error_rate_5m
        expr: |
          1 - (
            sum(rate(api_service_requests_total{status="success"}[5m]))
            /
            sum(rate(api_service_requests_total[5m]))
          )

      # Alert: High error rate (burning error budget fast)
      - alert: SLOAvailabilityBurningFast
        expr: slo:api_availability:error_rate_5m > 0.001 * 14.4
        for: 2m
        labels:
          severity: critical
          slo: availability
        annotations:
          summary: "API availability SLO burning error budget fast"
          description: "Error rate is {{ $value | humanizePercentage }}, burning 14.4x normal rate"

      # Alert: Slow burn (will exhaust budget in window)
      - alert: SLOAvailabilityBurningSlow
        expr: slo:api_availability:error_rate_5m > 0.001 * 3
        for: 1h
        labels:
          severity: warning
          slo: availability
        annotations:
          summary: "API availability SLO burning error budget"
          description: "Error rate is {{ $value | humanizePercentage }}"

      # =========================================
      # SLO: Latency P99 (99% < 500ms)
      # =========================================

      # Record: P99 latency
      - record: slo:api_latency:p99_5m
        expr: |
          histogram_quantile(0.99,
            sum(rate(api_service_request_duration_seconds_bucket[5m])) by (le)
          )

      # Alert: P99 latency too high
      - alert: SLOLatencyP99High
        expr: slo:api_latency:p99_5m > 0.5
        for: 5m
        labels:
          severity: warning
          slo: latency_p99
        annotations:
          summary: "API P99 latency exceeds 500ms"
          description: "P99 latency is {{ $value | humanizeDuration }}"

      # =========================================
      # Error Budget Alerts
      # =========================================

      # Record: Error budget remaining (30-day window)
      - record: slo:api_availability:error_budget_remaining
        expr: |
          1 - (
            sum(increase(api_service_errors_total[30d]))
            /
            (0.001 * sum(increase(api_service_requests_total[30d])))
          )

      # Alert: Error budget nearly exhausted
      - alert: SLOErrorBudgetNearlyExhausted
        expr: slo:api_availability:error_budget_remaining < 0.1
        for: 5m
        labels:
          severity: critical
          slo: availability
        annotations:
          summary: "SLO error budget nearly exhausted"
          description: "Only {{ $value | humanizePercentage }} of error budget remaining"
"""


# =============================================================================
# Grafana Dashboard Queries
# =============================================================================

GRAFANA_SLO_QUERIES = {
    "availability_current": """
        sum(rate(api_service_requests_total{status="success"}[5m]))
        /
        sum(rate(api_service_requests_total[5m]))
    """,
    "availability_vs_target": """
        (
            sum(rate(api_service_requests_total{status="success"}[5m]))
            /
            sum(rate(api_service_requests_total[5m]))
        ) - 0.999
    """,
    "error_budget_consumed_percent": """
        100 * (
            sum(increase(api_service_errors_total[30d]))
            /
            (0.001 * sum(increase(api_service_requests_total[30d])))
        )
    """,
    "error_budget_burn_rate": """
        sum(rate(api_service_errors_total[1h]))
        /
        (0.001 * sum(rate(api_service_requests_total[1h])) / 720)
    """,
    "time_to_budget_exhaustion_hours": """
        (
            (0.001 * sum(increase(api_service_requests_total[30d])))
            - sum(increase(api_service_errors_total[30d]))
        )
        /
        sum(rate(api_service_errors_total[1h]))
        / 3600
    """,
}


# =============================================================================
# Demo
# =============================================================================


async def demo():
    """Run SLO tracking demo."""
    configure(service_name="slo-demo", environment="production")
    start_http_server(port=9090)

    print("\n" + "=" * 60)
    print("SLO Tracking Demo")
    print("=" * 60)

    tracker = ProductionSLOTracker()

    print("\n📊 Simulating API traffic...")
    print("   SLO Target: 99.9% availability")
    print("   SLO Target: 99% requests < 500ms")
    print("   SLO Target: 95% requests < 200ms")

    # Simulate traffic with realistic patterns
    for i in range(1000):
        # 99.5% success rate (slightly below SLO)
        success = random.random() < 0.995

        # Latency distribution
        if random.random() < 0.90:
            latency_ms = random.uniform(50, 180)  # Fast
        elif random.random() < 0.95:
            latency_ms = random.uniform(180, 450)  # Medium
        else:
            latency_ms = random.uniform(450, 2000)  # Slow

        tracker.record_request(success=success, latency_ms=latency_ms)

        if i % 200 == 0:
            print(f"   Processed {i + 1} requests...")

    print("\n" + "=" * 60)
    print("Error Budget Status")
    print("=" * 60)

    status = tracker.get_error_budget_status()

    print("\n📈 Availability:")
    print(
        f"   Current:   {status['availability']['current']:.4f} ({status['availability']['current'] * 100:.2f}%)"
    )
    print(
        f"   Target:    {status['availability']['target']} ({status['availability']['target'] * 100:.1f}%)"
    )
    print(f"   Budget consumed: {status['availability']['budget_consumed']:.0f} errors")
    print(f"   Budget remaining: {status['availability']['budget_remaining_percent']:.1f}%")

    print("\n⏱️  Latency P99 (<500ms):")
    print(f"   Current: {status['latency_p99']['current'] * 100:.2f}%")
    print(f"   Target:  {status['latency_p99']['target'] * 100:.0f}%")

    print("\n⏱️  Latency P95 (<200ms):")
    print(f"   Current: {status['latency_p95']['current'] * 100:.2f}%")
    print(f"   Target:  {status['latency_p95']['target'] * 100:.0f}%")

    # Check for alerts
    print("\n" + "=" * 60)
    print("Alerts")
    print("=" * 60)

    alerts = tracker.check_and_alert()
    if alerts:
        for alert in alerts:
            print(f"\n⚠️  {alert['alert_name']}")
            print(f"    Severity: {alert['severity']}")
            print(f"    SLO: {alert['slo']}")
            print(f"    Budget remaining: {alert['budget_remaining_percent']:.1f}%")
    else:
        print("\n✅ No alerts - all SLOs within budget")

    print("\n" + "=" * 60)
    print("Prometheus Alerting Rules")
    print("=" * 60)
    print(PROMETHEUS_SLO_RULES[:1000] + "...")

    print("\n✅ Demo complete!")
    print("   Metrics available at http://localhost:9090/metrics")


if __name__ == "__main__":
    asyncio.run(demo())
