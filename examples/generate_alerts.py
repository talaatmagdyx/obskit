#!/usr/bin/env python3
"""
Example: Generate Custom Prometheus Alerting Rules
==================================================

This example shows how to generate custom Prometheus alerting rules
with configurable thresholds.

Usage:
    python generate_alerts.py > prometheus_rules.yml
"""

from obskit.alerts.config import AlertConfig, generate_prometheus_rules


def main():
    """Generate custom alerting rules."""

    # Example 1: Default configuration
    print("# Example 1: Default Configuration")
    print("=" * 60)
    default_config = AlertConfig()
    default_rules = generate_prometheus_rules(default_config)
    print(default_rules)
    print("\n\n")

    # Example 2: Custom configuration for strict requirements
    print("# Example 2: Strict Configuration (Lower Thresholds)")
    print("=" * 60)
    strict_config = AlertConfig(
        error_rate_threshold=0.005,  # 0.5% instead of 1%
        critical_error_rate_threshold=0.05,  # 5% instead of 10%
        latency_p95_threshold=0.2,  # 200ms instead of 500ms
        latency_p99_threshold=0.5,  # 500ms instead of 1s
        saturation_warning_threshold=0.80,  # 80% instead of 90%
        saturation_critical_threshold=0.90,  # 90% instead of 95%
    )
    strict_rules = generate_prometheus_rules(strict_config)
    print(strict_rules)
    print("\n\n")

    # Example 3: Lenient configuration for high-traffic services
    print("# Example 3: Lenient Configuration (Higher Thresholds)")
    print("=" * 60)
    lenient_config = AlertConfig(
        error_rate_threshold=0.02,  # 2% instead of 1%
        critical_error_rate_threshold=0.20,  # 20% instead of 10%
        latency_p95_threshold=1.0,  # 1s instead of 500ms
        latency_p99_threshold=2.0,  # 2s instead of 1s
        saturation_warning_threshold=0.95,  # 95% instead of 90%
        saturation_critical_threshold=0.98,  # 98% instead of 95%
    )
    lenient_rules = generate_prometheus_rules(lenient_config)
    print(lenient_rules)


if __name__ == "__main__":
    main()
