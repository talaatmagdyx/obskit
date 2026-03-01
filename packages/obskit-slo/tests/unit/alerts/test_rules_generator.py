"""
Tests for obskit.alerts.rules_generator module.
"""

from __future__ import annotations

import os
import tempfile
from unittest.mock import patch

import pytest
import yaml

from obskit.alerts.rules_generator import (
    SLODefinition,
    generate_alert_rules,
    generate_all_rules,
    generate_recording_rules,
    generate_slo_recording_rules,
    save_rules,
)

# =============================================================================
# SLODefinition Tests
# =============================================================================


class TestSLODefinition:
    def test_defaults(self):
        slo = SLODefinition(name="availability", target=0.999)
        assert slo.name == "availability"
        assert slo.target == pytest.approx(0.999)
        assert slo.window == "5m"
        assert slo.burn_rate_windows is not None

    def test_default_burn_rate_windows(self):
        slo = SLODefinition(name="test", target=0.99)
        assert "5m" in slo.burn_rate_windows
        assert "1h" in slo.burn_rate_windows
        assert "6h" in slo.burn_rate_windows

    def test_custom_burn_rate_windows(self):
        slo = SLODefinition(name="test", target=0.99, burn_rate_windows=["1h", "24h"])
        assert slo.burn_rate_windows == ["1h", "24h"]

    def test_custom_window(self):
        slo = SLODefinition(name="test", target=0.99, window="30m")
        assert slo.window == "30m"


# =============================================================================
# generate_recording_rules Tests
# =============================================================================


class TestGenerateRecordingRules:
    def test_basic_structure(self):
        result = generate_recording_rules("order-service")
        assert "groups" in result
        assert len(result["groups"]) == 1
        group = result["groups"][0]
        assert group["name"] == "order-service_recording_rules"
        assert group["interval"] == "30s"
        assert len(group["rules"]) > 0

    def test_custom_metrics_prefix(self):
        result = generate_recording_rules("order-service", metrics_prefix="orders")
        rules = result["groups"][0]["rules"]
        # Check that rules use the custom prefix
        all_exprs = " ".join(r.get("expr", "") + r.get("record", "") for r in rules)
        assert "orders" in all_exprs

    def test_default_windows(self):
        result = generate_recording_rules("test-service")
        rules = result["groups"][0]["rules"]
        records = [r["record"] for r in rules]
        # Should have rules for 5m, 1h, 6h windows
        assert any("5m" in r for r in records)
        assert any("1h" in r for r in records)
        assert any("6h" in r for r in records)

    def test_custom_windows(self):
        result = generate_recording_rules("test-service", windows=["1m", "5m"])
        rules = result["groups"][0]["rules"]
        records = [r["record"] for r in rules]
        assert any("1m" in r for r in records)
        assert any("5m" in r for r in records)
        assert not any("6h" in r for r in records)

    def test_includes_availability_rules(self):
        result = generate_recording_rules("my-service")
        rules = result["groups"][0]["rules"]
        records = [r["record"] for r in rules]
        assert any("availability" in r for r in records)

    def test_includes_error_rate_rules(self):
        result = generate_recording_rules("my-service")
        rules = result["groups"][0]["rules"]
        records = [r["record"] for r in rules]
        assert any("error_rate" in r for r in records)

    def test_includes_latency_percentiles(self):
        result = generate_recording_rules("my-service")
        rules = result["groups"][0]["rules"]
        records = [r["record"] for r in rules]
        assert any("latency_p50" in r for r in records)
        assert any("latency_p95" in r for r in records)
        assert any("latency_p99" in r for r in records)

    def test_includes_request_rate(self):
        result = generate_recording_rules("my-service")
        rules = result["groups"][0]["rules"]
        records = [r["record"] for r in rules]
        assert any("request_rate" in r for r in records)

    def test_hyphen_to_underscore_conversion(self):
        """Service name with hyphens should be converted to underscores in prefix."""
        result = generate_recording_rules("my-service-name")
        rules = result["groups"][0]["rules"]
        records = [r["record"] for r in rules]
        assert any("my_service_name" in r for r in records)


# =============================================================================
# generate_slo_recording_rules Tests
# =============================================================================


class TestGenerateSloRecordingRules:
    def _make_slos(self):
        return [
            {"name": "availability", "target": 0.999, "type": "availability"},
            {"name": "latency_p95", "target": 0.5, "type": "latency"},
        ]

    def test_basic_structure(self):
        result = generate_slo_recording_rules("order-service", self._make_slos())
        assert "groups" in result
        group = result["groups"][0]
        assert "order-service_slo_recording_rules" in group["name"]

    def test_availability_slo_compliance_rule(self):
        slos = [{"name": "avail", "target": 0.999, "type": "availability"}]
        result = generate_slo_recording_rules("svc", slos)
        rules = result["groups"][0]["rules"]
        records = [r["record"] for r in rules]
        assert any("slo_compliance:avail" in r for r in records)

    def test_latency_slo_compliance_rule(self):
        slos = [{"name": "latency", "target": 0.5, "type": "latency"}]
        result = generate_slo_recording_rules("svc", slos)
        rules = result["groups"][0]["rules"]
        records = [r["record"] for r in rules]
        assert any("slo_compliance:latency" in r for r in records)

    def test_error_budget_rules(self):
        slos = [{"name": "availability", "target": 0.999, "type": "availability"}]
        result = generate_slo_recording_rules("svc", slos)
        rules = result["groups"][0]["rules"]
        records = [r["record"] for r in rules]
        assert any("error_budget_remaining" in r for r in records)

    def test_burn_rate_rules(self):
        slos = [{"name": "availability", "target": 0.999, "type": "availability"}]
        result = generate_slo_recording_rules("svc", slos)
        rules = result["groups"][0]["rules"]
        records = [r["record"] for r in rules]
        assert any("burn_rate" in r for r in records)

    def test_custom_metrics_prefix(self):
        slos = [{"name": "avail", "target": 0.999, "type": "availability"}]
        result = generate_slo_recording_rules("my-svc", slos, metrics_prefix="custom")
        rules = result["groups"][0]["rules"]
        records = [r["record"] for r in rules]
        assert any("custom" in r for r in records)

    def test_empty_slos(self):
        result = generate_slo_recording_rules("svc", [])
        assert len(result["groups"][0]["rules"]) == 0

    def test_unknown_slo_type_skips_compliance_rule(self):
        slos = [{"name": "throughput", "target": 100, "type": "throughput"}]
        result = generate_slo_recording_rules("svc", slos)
        rules = result["groups"][0]["rules"]
        # Throughput type has no compliance rule - only error budget and burn rate
        records = [r["record"] for r in rules]
        assert not any("slo_compliance" in r for r in records)


# =============================================================================
# generate_alert_rules Tests
# =============================================================================


class TestGenerateAlertRules:
    def _make_slos(self):
        return [
            {"name": "availability", "target": 0.999},
        ]

    def test_basic_structure(self):
        result = generate_alert_rules("order-service", self._make_slos())
        assert "groups" in result
        group = result["groups"][0]
        assert "order-service_alert_rules" in group["name"]

    def test_fast_burn_alert(self):
        result = generate_alert_rules("order-service", self._make_slos())
        alerts = [r["alert"] for r in result["groups"][0]["rules"]]
        assert any("FastBurn" in a for a in alerts)

    def test_slow_burn_alert(self):
        result = generate_alert_rules("order-service", self._make_slos())
        alerts = [r["alert"] for r in result["groups"][0]["rules"]]
        assert any("SlowBurn" in a for a in alerts)

    def test_error_budget_exhausted_alert(self):
        result = generate_alert_rules("order-service", self._make_slos())
        alerts = [r["alert"] for r in result["groups"][0]["rules"]]
        assert any("ErrorBudgetExhausted" in a for a in alerts)

    def test_error_budget_low_alert(self):
        result = generate_alert_rules("order-service", self._make_slos())
        alerts = [r["alert"] for r in result["groups"][0]["rules"]]
        assert any("ErrorBudgetLow" in a for a in alerts)

    def test_infrastructure_alerts_included_by_default(self):
        result = generate_alert_rules("order-service", self._make_slos())
        alerts = [r["alert"] for r in result["groups"][0]["rules"]]
        assert any("NoTraffic" in a for a in alerts)
        assert any("HighErrorRate" in a for a in alerts)
        assert any("HighLatency" in a for a in alerts)

    def test_infrastructure_alerts_excluded(self):
        result = generate_alert_rules("order-service", self._make_slos(), include_infrastructure=False)
        alerts = [r["alert"] for r in result["groups"][0]["rules"]]
        assert not any("NoTraffic" in a for a in alerts)

    def test_alert_has_severity_label(self):
        result = generate_alert_rules("order-service", self._make_slos())
        rules = result["groups"][0]["rules"]
        for rule in rules:
            assert "labels" in rule
            assert "severity" in rule["labels"]

    def test_alert_has_annotations(self):
        result = generate_alert_rules("order-service", self._make_slos())
        rules = result["groups"][0]["rules"]
        for rule in rules:
            assert "annotations" in rule
            assert "summary" in rule["annotations"]

    def test_service_name_in_alert_labels(self):
        result = generate_alert_rules("my-service", self._make_slos())
        rules = result["groups"][0]["rules"]
        for rule in rules:
            if "service" in rule["labels"]:
                assert rule["labels"]["service"] == "my-service"


# =============================================================================
# generate_all_rules Tests
# =============================================================================


class TestGenerateAllRules:
    def test_returns_yaml_string(self):
        result = generate_all_rules("order-service")
        assert isinstance(result, str)

    def test_valid_yaml(self):
        result = generate_all_rules("order-service")
        parsed = yaml.safe_load(result)
        assert "groups" in parsed

    def test_contains_all_rule_groups(self):
        result = generate_all_rules("order-service")
        parsed = yaml.safe_load(result)
        group_names = [g["name"] for g in parsed["groups"]]
        # Should have recording, SLO recording, and alert groups
        assert any("recording_rules" in n for n in group_names)
        assert any("alert_rules" in n for n in group_names)

    def test_custom_slos(self):
        slos = [
            {"name": "my_availability", "target": 0.999, "type": "availability"},
        ]
        result = generate_all_rules("my-service", slos=slos)
        assert isinstance(result, str)

    def test_default_slos_used_when_none(self):
        result = generate_all_rules("test-service", slos=None)
        assert "availability" in result


# =============================================================================
# save_rules Tests
# =============================================================================


class TestSaveRules:
    def test_save_rules_creates_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            save_rules("test-service", tmpdir)
            files = os.listdir(tmpdir)
            assert any("recording-rules" in f for f in files)
            assert any("alert-rules" in f for f in files)

    def test_save_rules_with_slos(self):
        slos = [{"name": "availability", "target": 0.999, "type": "availability"}]
        with tempfile.TemporaryDirectory() as tmpdir:
            save_rules("svc", tmpdir, slos=slos)
            files = os.listdir(tmpdir)
            assert any("slo-recording-rules" in f for f in files)

    def test_save_rules_creates_directory(self):
        with tempfile.TemporaryDirectory() as base_dir:
            output_dir = os.path.join(base_dir, "rules", "subdir")
            save_rules("test-service", output_dir)
            assert os.path.exists(output_dir)
