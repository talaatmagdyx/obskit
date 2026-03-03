"""
Tests for obskit.alerts.builder — AlertRule, AlertGroup, export_yaml
=====================================================================

Covers:
- AlertRule.error_rate() — PromQL expression, defaults, custom params
- AlertRule.latency() — histogram_quantile expression, ms→s conversion
- AlertRule.no_traffic() — sum(rate(...)) == 0 expression
- AlertRule.slo_burn() — multi-window burn-rate expression
- AlertRule.custom() — raw PromQL pass-through
- AlertRule.to_dict() — correct Prometheus rule shape
- AlertGroup.to_dict() — correct Prometheus group shape, optional interval
- AlertGroup.add() — fluent API, returns self
- export_yaml() — valid YAML string, optional file write, multiple groups
- Public API surface: AlertRule, AlertGroup, export_yaml importable from obskit.alerts
"""

from __future__ import annotations

import os
import tempfile

import pytest
import yaml

from obskit.alerts import AlertGroup, AlertRule, export_yaml


# ---------------------------------------------------------------------------
# TestAlertRuleDefaults
# ---------------------------------------------------------------------------


class TestAlertRuleDefaults:
    """Each factory method must produce sensible defaults."""

    # -- error_rate -----------------------------------------------------------

    def test_error_rate_default_alert_name(self):
        rule = AlertRule.error_rate(metric="http_requests_total")
        assert rule.alert == "HighErrorRate"

    def test_error_rate_default_severity(self):
        rule = AlertRule.error_rate(metric="http_requests_total")
        assert rule.severity == "critical"

    def test_error_rate_default_duration(self):
        rule = AlertRule.error_rate(metric="http_requests_total")
        assert rule.duration == "2m"

    def test_error_rate_default_threshold_in_expr(self):
        rule = AlertRule.error_rate(metric="http_requests_total", threshold=0.05)
        assert "> 0.05" in rule.expr

    def test_error_rate_default_error_label(self):
        rule = AlertRule.error_rate(metric="http_requests_total")
        assert 'status="error"' in rule.expr

    def test_error_rate_annotations_present(self):
        rule = AlertRule.error_rate(metric="http_requests_total")
        assert "summary" in rule.annotations
        assert "description" in rule.annotations

    # -- latency --------------------------------------------------------------

    def test_latency_default_name(self):
        rule = AlertRule.latency(metric="http_request_duration_seconds")
        assert rule.alert == "HighLatency"

    def test_latency_default_severity(self):
        rule = AlertRule.latency(metric="http_request_duration_seconds")
        assert rule.severity == "warning"

    def test_latency_default_duration(self):
        rule = AlertRule.latency(metric="http_request_duration_seconds")
        assert rule.duration == "3m"

    def test_latency_default_percentile_in_expr(self):
        rule = AlertRule.latency(metric="http_request_duration_seconds", percentile=0.99)
        assert "0.99" in rule.expr

    # -- no_traffic -----------------------------------------------------------

    def test_no_traffic_default_name(self):
        rule = AlertRule.no_traffic(metric="http_requests_total")
        assert rule.alert == "NoTraffic"

    def test_no_traffic_default_severity(self):
        rule = AlertRule.no_traffic(metric="http_requests_total")
        assert rule.severity == "warning"

    def test_no_traffic_default_duration(self):
        rule = AlertRule.no_traffic(metric="http_requests_total")
        assert rule.duration == "10m"

    # -- slo_burn -------------------------------------------------------------

    def test_slo_burn_default_name(self):
        rule = AlertRule.slo_burn(error_metric="http_requests_total")
        assert rule.alert == "SLOBurnFast"

    def test_slo_burn_default_severity(self):
        rule = AlertRule.slo_burn(error_metric="http_requests_total")
        assert rule.severity == "critical"

    def test_slo_burn_default_duration(self):
        rule = AlertRule.slo_burn(error_metric="http_requests_total")
        assert rule.duration == "2m"


# ---------------------------------------------------------------------------
# TestAlertRuleExpressions
# ---------------------------------------------------------------------------


class TestAlertRuleExpressions:
    """The generated PromQL expressions must be syntactically correct."""

    def test_error_rate_expr_uses_metric_name(self):
        rule = AlertRule.error_rate(metric="my_service_requests_total")
        assert "my_service_requests_total" in rule.expr

    def test_error_rate_expr_uses_rate(self):
        rule = AlertRule.error_rate(metric="my_service_requests_total")
        assert "rate(" in rule.expr

    def test_error_rate_expr_uses_status_label(self):
        rule = AlertRule.error_rate(
            metric="my_service_requests_total", error_label="5xx"
        )
        assert 'status="5xx"' in rule.expr

    def test_error_rate_expr_uses_window(self):
        rule = AlertRule.error_rate(metric="m", window="5m")
        assert "[5m]" in rule.expr

    def test_error_rate_custom_threshold(self):
        rule = AlertRule.error_rate(metric="m", threshold=0.10)
        assert "> 0.1" in rule.expr

    def test_latency_expr_uses_histogram_quantile(self):
        rule = AlertRule.latency(metric="http_request_duration_seconds")
        assert "histogram_quantile" in rule.expr

    def test_latency_expr_uses_bucket_suffix(self):
        rule = AlertRule.latency(metric="http_request_duration_seconds")
        assert "http_request_duration_seconds_bucket" in rule.expr

    def test_latency_expr_threshold_converted_to_seconds(self):
        # 2000 ms → 2.0 s
        rule = AlertRule.latency(
            metric="http_request_duration_seconds", threshold_ms=2000
        )
        assert "> 2.0" in rule.expr

    def test_latency_expr_threshold_ms_500(self):
        rule = AlertRule.latency(metric="m", threshold_ms=500)
        assert "> 0.5" in rule.expr

    def test_latency_expr_p95(self):
        rule = AlertRule.latency(metric="m", percentile=0.95)
        assert "0.95" in rule.expr

    def test_no_traffic_expr_sum_rate(self):
        rule = AlertRule.no_traffic(metric="http_requests_total")
        assert "sum(rate(http_requests_total[" in rule.expr

    def test_no_traffic_expr_equals_zero(self):
        rule = AlertRule.no_traffic(metric="http_requests_total")
        assert "== 0" in rule.expr

    def test_no_traffic_expr_custom_window(self):
        rule = AlertRule.no_traffic(metric="m", window="15m")
        assert "[15m]" in rule.expr

    def test_slo_burn_expr_has_fast_window(self):
        rule = AlertRule.slo_burn(
            error_metric="http_requests_total",
            fast_window="5m",
        )
        assert "[5m]" in rule.expr

    def test_slo_burn_expr_has_slow_window(self):
        rule = AlertRule.slo_burn(
            error_metric="http_requests_total",
            slow_window="1h",
        )
        assert "[1h]" in rule.expr

    def test_slo_burn_expr_uses_and_conjunction(self):
        rule = AlertRule.slo_burn(error_metric="http_requests_total")
        assert "and" in rule.expr

    def test_slo_burn_expr_burn_factor(self):
        rule = AlertRule.slo_burn(
            error_metric="http_requests_total", burn_factor=14.4
        )
        assert "> 14.4" in rule.expr

    def test_slo_burn_error_budget_calculation(self):
        # slo_target=0.999 → error_budget = 0.001
        rule = AlertRule.slo_burn(
            error_metric="http_requests_total", slo_target=0.999
        )
        assert "0.001" in rule.expr

    def test_custom_passes_expr_through(self):
        rule = AlertRule.custom(
            name="QueueSaturation",
            expr="rabbitmq_queue_messages > 10000",
            severity="warning",
        )
        assert rule.expr == "rabbitmq_queue_messages > 10000"


# ---------------------------------------------------------------------------
# TestAlertRuleCustomisation
# ---------------------------------------------------------------------------


class TestAlertRuleCustomisation:
    """Parameters properly override defaults."""

    def test_error_rate_custom_name(self):
        rule = AlertRule.error_rate(metric="m", name="MyErrorAlert")
        assert rule.alert == "MyErrorAlert"

    def test_error_rate_custom_severity(self):
        rule = AlertRule.error_rate(metric="m", severity="warning")
        assert rule.severity == "warning"

    def test_error_rate_custom_duration(self):
        rule = AlertRule.error_rate(metric="m", duration="5m")
        assert rule.duration == "5m"

    def test_error_rate_custom_labels(self):
        rule = AlertRule.error_rate(
            metric="m", labels={"team": "sre", "env": "prod"}
        )
        assert rule.labels["team"] == "sre"
        assert rule.labels["env"] == "prod"

    def test_error_rate_custom_annotations(self):
        rule = AlertRule.error_rate(
            metric="m",
            annotations={"summary": "my summary", "runbook_url": "https://example.com"},
        )
        assert rule.annotations["summary"] == "my summary"
        assert rule.annotations["runbook_url"] == "https://example.com"

    def test_latency_custom_percentile_p50(self):
        rule = AlertRule.latency(metric="m", percentile=0.50)
        assert "0.5" in rule.expr
        assert rule.alert == "HighLatency"

    def test_latency_custom_name(self):
        rule = AlertRule.latency(metric="m", name="SlowAPI")
        assert rule.alert == "SlowAPI"

    def test_no_traffic_custom_name(self):
        rule = AlertRule.no_traffic(metric="m", name="DeadService")
        assert rule.alert == "DeadService"

    def test_slo_burn_custom_name(self):
        rule = AlertRule.slo_burn(error_metric="m", name="BurnAlert")
        assert rule.alert == "BurnAlert"

    def test_slo_burn_custom_error_label(self):
        rule = AlertRule.slo_burn(error_metric="m", error_label="5xx")
        assert 'status="5xx"' in rule.expr

    def test_custom_duration(self):
        rule = AlertRule.custom(
            name="Q", expr="x > 1", severity="critical", duration="10m"
        )
        assert rule.duration == "10m"

    def test_custom_labels(self):
        rule = AlertRule.custom(
            name="Q",
            expr="x > 1",
            severity="warning",
            labels={"page": "true"},
        )
        assert rule.labels["page"] == "true"

    def test_custom_annotations(self):
        rule = AlertRule.custom(
            name="Q",
            expr="x > 1",
            severity="warning",
            annotations={"summary": "Queue is saturated"},
        )
        assert rule.annotations["summary"] == "Queue is saturated"


# ---------------------------------------------------------------------------
# TestAlertRuleToDict
# ---------------------------------------------------------------------------


class TestAlertRuleToDict:
    """to_dict() must produce a valid Prometheus rule dict."""

    def _rule(self) -> AlertRule:
        return AlertRule.error_rate(
            metric="http_requests_total",
            threshold=0.05,
            severity="critical",
            labels={"team": "platform"},
        )

    def test_to_dict_has_alert_key(self):
        d = self._rule().to_dict()
        assert "alert" in d

    def test_to_dict_has_expr_key(self):
        d = self._rule().to_dict()
        assert "expr" in d

    def test_to_dict_has_for_key(self):
        d = self._rule().to_dict()
        assert "for" in d

    def test_to_dict_has_labels_key(self):
        d = self._rule().to_dict()
        assert "labels" in d

    def test_to_dict_has_annotations_key(self):
        d = self._rule().to_dict()
        assert "annotations" in d

    def test_to_dict_severity_in_labels(self):
        d = self._rule().to_dict()
        assert d["labels"]["severity"] == "critical"

    def test_to_dict_extra_labels_merged(self):
        d = self._rule().to_dict()
        assert d["labels"]["team"] == "platform"

    def test_to_dict_for_matches_duration(self):
        rule = AlertRule.error_rate(metric="m", duration="5m")
        assert rule.to_dict()["for"] == "5m"

    def test_to_dict_alert_name_matches(self):
        rule = AlertRule.error_rate(metric="m", name="MyAlert")
        assert rule.to_dict()["alert"] == "MyAlert"

    def test_to_dict_expr_matches(self):
        rule = AlertRule.custom(name="X", expr="up == 0", severity="critical")
        assert rule.to_dict()["expr"] == "up == 0"


# ---------------------------------------------------------------------------
# TestAlertGroup
# ---------------------------------------------------------------------------


class TestAlertGroup:
    """Tests for AlertGroup dataclass and its to_dict()."""

    def test_empty_group(self):
        g = AlertGroup(name="my-service")
        assert g.name == "my-service"
        assert g.rules == []

    def test_add_returns_self(self):
        g = AlertGroup(name="svc")
        rule = AlertRule.error_rate(metric="m")
        result = g.add(rule)
        assert result is g

    def test_add_appends_rule(self):
        g = AlertGroup(name="svc")
        rule = AlertRule.error_rate(metric="m")
        g.add(rule)
        assert len(g.rules) == 1
        assert g.rules[0] is rule

    def test_fluent_chaining(self):
        g = (
            AlertGroup(name="svc")
            .add(AlertRule.error_rate(metric="m"))
            .add(AlertRule.no_traffic(metric="m"))
        )
        assert len(g.rules) == 2

    def test_to_dict_has_name(self):
        g = AlertGroup(name="order-service")
        d = g.to_dict()
        assert d["name"] == "order-service"

    def test_to_dict_has_rules(self):
        g = AlertGroup(
            name="svc",
            rules=[AlertRule.error_rate(metric="m")],
        )
        d = g.to_dict()
        assert "rules" in d
        assert len(d["rules"]) == 1

    def test_to_dict_no_interval_by_default(self):
        g = AlertGroup(name="svc")
        d = g.to_dict()
        assert "interval" not in d

    def test_to_dict_with_interval(self):
        g = AlertGroup(name="svc", interval="30s")
        d = g.to_dict()
        assert d["interval"] == "30s"

    def test_to_dict_rules_serialised(self):
        rule = AlertRule.error_rate(metric="m", threshold=0.05, severity="critical")
        g = AlertGroup(name="svc", rules=[rule])
        d = g.to_dict()
        assert d["rules"][0]["alert"] == "HighErrorRate"
        assert d["rules"][0]["labels"]["severity"] == "critical"

    def test_constructor_with_rules(self):
        rules = [
            AlertRule.error_rate(metric="m"),
            AlertRule.latency(metric="m"),
        ]
        g = AlertGroup(name="svc", rules=rules)
        assert len(g.rules) == 2


# ---------------------------------------------------------------------------
# TestExportYaml
# ---------------------------------------------------------------------------


class TestExportYaml:
    """Tests for export_yaml()."""

    def _group(self) -> AlertGroup:
        return AlertGroup(
            name="test-service",
            rules=[
                AlertRule.error_rate(metric="http_requests_total"),
                AlertRule.latency(metric="http_request_duration_seconds"),
            ],
        )

    def test_returns_string(self):
        yaml_str = export_yaml(self._group())
        assert isinstance(yaml_str, str)

    def test_yaml_is_parseable(self):
        yaml_str = export_yaml(self._group())
        parsed = yaml.safe_load(yaml_str)
        assert parsed is not None

    def test_yaml_has_groups_key(self):
        parsed = yaml.safe_load(export_yaml(self._group()))
        assert "groups" in parsed

    def test_yaml_group_name_correct(self):
        parsed = yaml.safe_load(export_yaml(self._group()))
        assert parsed["groups"][0]["name"] == "test-service"

    def test_yaml_rules_count(self):
        parsed = yaml.safe_load(export_yaml(self._group()))
        assert len(parsed["groups"][0]["rules"]) == 2

    def test_yaml_rule_has_alert_key(self):
        parsed = yaml.safe_load(export_yaml(self._group()))
        rule = parsed["groups"][0]["rules"][0]
        assert "alert" in rule

    def test_yaml_rule_has_expr_key(self):
        parsed = yaml.safe_load(export_yaml(self._group()))
        rule = parsed["groups"][0]["rules"][0]
        assert "expr" in rule

    def test_yaml_rule_has_for_key(self):
        parsed = yaml.safe_load(export_yaml(self._group()))
        rule = parsed["groups"][0]["rules"][0]
        assert "for" in rule

    def test_yaml_rule_has_labels(self):
        parsed = yaml.safe_load(export_yaml(self._group()))
        rule = parsed["groups"][0]["rules"][0]
        assert "labels" in rule

    def test_export_multiple_groups(self):
        g1 = AlertGroup(name="svc-a", rules=[AlertRule.error_rate(metric="m1")])
        g2 = AlertGroup(name="svc-b", rules=[AlertRule.no_traffic(metric="m2")])
        parsed = yaml.safe_load(export_yaml(g1, g2))
        assert len(parsed["groups"]) == 2
        names = {g["name"] for g in parsed["groups"]}
        assert names == {"svc-a", "svc-b"}

    def test_export_writes_file(self, tmp_path):
        out = tmp_path / "k8s" / "alerts.yaml"
        export_yaml(self._group(), path=str(out))
        assert out.exists()

    def test_export_file_content_is_valid_yaml(self, tmp_path):
        out = tmp_path / "alerts.yaml"
        export_yaml(self._group(), path=str(out))
        content = out.read_text()
        parsed = yaml.safe_load(content)
        assert "groups" in parsed

    def test_export_creates_parent_dirs(self, tmp_path):
        out = tmp_path / "deep" / "nested" / "alerts.yaml"
        export_yaml(self._group(), path=str(out))
        assert out.exists()

    def test_export_returns_same_yaml_regardless_of_path(self, tmp_path):
        out = tmp_path / "alerts.yaml"
        yaml_str = export_yaml(self._group(), path=str(out))
        assert yaml_str == out.read_text()

    def test_export_no_path_does_not_create_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        export_yaml(self._group())  # no path= argument
        # no files should be created in the current directory
        assert not any(tmp_path.iterdir())

    def test_export_empty_group(self):
        g = AlertGroup(name="empty")
        parsed = yaml.safe_load(export_yaml(g))
        assert parsed["groups"][0]["rules"] == []


# ---------------------------------------------------------------------------
# TestPublicApiSurface
# ---------------------------------------------------------------------------


class TestPublicApiSurface:
    """AlertRule, AlertGroup, and export_yaml must be importable from obskit.alerts."""

    def test_alert_rule_importable(self):
        from obskit.alerts import AlertRule as AR  # noqa: F401

        assert AR is AlertRule

    def test_alert_group_importable(self):
        from obskit.alerts import AlertGroup as AG  # noqa: F401

        assert AG is AlertGroup

    def test_export_yaml_importable(self):
        from obskit.alerts import export_yaml as ey  # noqa: F401

        assert ey is export_yaml

    def test_all_in_module_all(self):
        import obskit.alerts as alerts_mod

        assert "AlertRule" in alerts_mod.__all__
        assert "AlertGroup" in alerts_mod.__all__
        assert "export_yaml" in alerts_mod.__all__


# ---------------------------------------------------------------------------
# TestAnnotationContent
# ---------------------------------------------------------------------------


class TestAnnotationContent:
    """Default annotations must contain meaningful text."""

    def test_error_rate_summary_contains_percentage(self):
        rule = AlertRule.error_rate(metric="m", threshold=0.05)
        assert "5%" in rule.annotations["summary"]

    def test_error_rate_description_contains_metric(self):
        rule = AlertRule.error_rate(metric="my_metric")
        assert "my_metric" in rule.annotations["description"]

    def test_latency_summary_contains_ms(self):
        rule = AlertRule.latency(metric="m", threshold_ms=2000)
        assert "2000" in rule.annotations["summary"]

    def test_latency_description_contains_metric(self):
        rule = AlertRule.latency(metric="my_histogram")
        assert "my_histogram" in rule.annotations["description"]

    def test_no_traffic_summary_present(self):
        rule = AlertRule.no_traffic(metric="m")
        assert rule.annotations["summary"]  # non-empty string

    def test_no_traffic_description_contains_metric(self):
        rule = AlertRule.no_traffic(metric="my_counter")
        assert "my_counter" in rule.annotations["description"]

    def test_slo_burn_summary_contains_factor(self):
        rule = AlertRule.slo_burn(error_metric="m", burn_factor=14.4)
        assert "14.4" in rule.annotations["summary"]

    def test_slo_burn_description_contains_target(self):
        rule = AlertRule.slo_burn(error_metric="m", slo_target=0.999)
        assert "99.90%" in rule.annotations["description"]

    def test_custom_empty_annotations_by_default(self):
        rule = AlertRule.custom(name="X", expr="up == 0", severity="critical")
        assert rule.annotations == {}
