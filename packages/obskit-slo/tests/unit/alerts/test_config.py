"""Tests for obskit.alerts.config module."""

import os
from unittest.mock import patch

from obskit.alerts.config import AlertConfig, generate_prometheus_rules
import pytest


class TestAlertConfig:
    """Tests for AlertConfig class."""

    def test_default_values(self):
        """Test default configuration values."""
        config = AlertConfig()

        assert config.error_rate_threshold == pytest.approx(0.01)
        assert config.critical_error_rate_threshold == pytest.approx(0.10)
        assert config.latency_p95_threshold == pytest.approx(0.5)
        assert config.latency_p99_threshold == pytest.approx(1.0)
        assert config.low_request_rate_threshold == pytest.approx(0.1)
        assert config.saturation_warning_threshold == pytest.approx(0.90)
        assert config.saturation_critical_threshold == pytest.approx(0.95)
        assert config.queue_depth_threshold == 1000
        assert config.cpu_utilization_threshold == pytest.approx(0.90)
        assert config.memory_utilization_threshold == pytest.approx(0.90)
        assert config.cpu_saturation_threshold == pytest.approx(10.0)
        assert config.service_degraded_error_rate == pytest.approx(0.05)
        assert config.service_degraded_latency == pytest.approx(1.0)
        assert config.slo_error_budget_threshold == pytest.approx(0.001)
        assert config.slo_latency_threshold == pytest.approx(0.2)

    def test_custom_values(self):
        """Test custom configuration values."""
        config = AlertConfig(
            error_rate_threshold=0.05,
            latency_p95_threshold=0.3,
            queue_depth_threshold=500,
        )

        assert config.error_rate_threshold == pytest.approx(0.05)
        assert config.latency_p95_threshold == pytest.approx(0.3)
        assert config.queue_depth_threshold == 500

    def test_alert_intervals_default(self):
        """Test default alert intervals."""
        config = AlertConfig()

        assert "default" in config.alert_intervals
        assert "slo" in config.alert_intervals

    def test_alert_durations_default(self):
        """Test default alert durations."""
        config = AlertConfig()

        assert "high_error_rate" in config.alert_durations
        assert "critical_error_rate" in config.alert_durations
        assert "high_latency_p95" in config.alert_durations

    def test_from_env_default_values(self):
        """Test from_env with no environment variables."""
        config = AlertConfig.from_env()

        assert config.error_rate_threshold == pytest.approx(0.01)

    @patch.dict(os.environ, {"OBSKIT_ALERT_ERROR_RATE_THRESHOLD": "0.05"})
    def test_from_env_custom_error_rate(self):
        """Test from_env reads custom error rate."""
        config = AlertConfig.from_env()

        assert config.error_rate_threshold == pytest.approx(0.05)

    @patch.dict(
        os.environ,
        {
            "OBSKIT_ALERT_ERROR_RATE_THRESHOLD": "0.02",
            "OBSKIT_ALERT_LATENCY_P95_THRESHOLD": "0.3",
            "OBSKIT_ALERT_QUEUE_DEPTH_THRESHOLD": "500",
        },
    )
    def test_from_env_multiple_values(self):
        """Test from_env reads multiple environment variables."""
        config = AlertConfig.from_env()

        assert config.error_rate_threshold == pytest.approx(0.02)
        assert config.latency_p95_threshold == pytest.approx(0.3)
        assert config.queue_depth_threshold == 500

    def test_to_dict(self):
        """Test converting config to dictionary."""
        config = AlertConfig(error_rate_threshold=0.05)
        result = config.to_dict()

        assert isinstance(result, dict)
        assert result["error_rate_threshold"] == pytest.approx(0.05)
        assert "latency_p95_threshold" in result
        assert "alert_intervals" in result
        assert "alert_durations" in result


class TestGeneratePrometheusRules:
    """Tests for generate_prometheus_rules function."""

    def test_generates_yaml_string(self):
        """Test function generates YAML string."""
        rules = generate_prometheus_rules()

        assert isinstance(rules, str)
        assert len(rules) > 0

    def test_with_default_config(self):
        """Test with default configuration."""
        rules = generate_prometheus_rules()

        assert "groups:" in rules
        assert "alert:" in rules
        assert "expr:" in rules

    def test_with_custom_config(self):
        """Test with custom configuration."""
        config = AlertConfig(error_rate_threshold=0.05)
        rules = generate_prometheus_rules(config)

        assert "0.05" in rules

    def test_contains_alert_names(self):
        """Test generated rules contain expected alert names."""
        rules = generate_prometheus_rules()

        assert "HighErrorRate" in rules
        assert "CriticalErrorRate" in rules
        assert "HighLatencyP95" in rules
        assert "CriticalLatencyP99" in rules
        assert "LowRequestRate" in rules
        assert "HighSaturation" in rules
        assert "CriticalSaturation" in rules
        assert "HighQueueDepth" in rules
        assert "HighCPUUtilization" in rules
        assert "HighMemoryUtilization" in rules
        assert "ServiceDown" in rules
        assert "ServiceDegraded" in rules

    def test_contains_severity_levels(self):
        """Test generated rules contain severity levels."""
        rules = generate_prometheus_rules()

        assert "severity: critical" in rules
        assert "severity: warning" in rules

    def test_contains_alert_groups(self):
        """Test generated rules contain expected groups."""
        rules = generate_prometheus_rules()

        assert "red_method_alerts" in rules
        assert "golden_signals_alerts" in rules
        assert "use_method_alerts" in rules
        assert "service_health_alerts" in rules
        assert "slo_alerts" in rules

    def test_with_none_config(self):
        """Test with None config uses defaults."""
        rules = generate_prometheus_rules(None)

        assert "0.01" in rules  # Default error_rate_threshold

    def test_threshold_values_in_output(self):
        """Test that threshold values appear in output."""
        config = AlertConfig(
            error_rate_threshold=0.03,
            latency_p95_threshold=0.4,
        )
        rules = generate_prometheus_rules(config)

        assert "0.03" in rules
        assert "0.4" in rules

    def test_duration_values_in_output(self):
        """Test that duration values appear in output."""
        rules = generate_prometheus_rules()

        # Default duration for high_error_rate is 300s (5m)
        assert "300s" in rules or "for: 300" in rules
