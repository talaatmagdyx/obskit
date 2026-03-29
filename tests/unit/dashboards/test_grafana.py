"""
Comprehensive unit tests for obskit.dashboards.grafana module.

Covers:
- Panel dataclass and to_dict()
- DashboardBuilder.__init__()
- DashboardBuilder._next_panel_id()
- DashboardBuilder._add_panel()
- DashboardBuilder.add_row()
- DashboardBuilder.add_stat_panel()
- DashboardBuilder.add_gauge_panel()
- DashboardBuilder.add_timeseries_panel()
- DashboardBuilder.add_slo_compliance_panel()
- DashboardBuilder.add_error_budget_panel()
- DashboardBuilder.add_red_metrics_row()
- DashboardBuilder.add_golden_signals_row()
- DashboardBuilder.add_slo_row()
- DashboardBuilder.build()
- DashboardBuilder.to_json()
- DashboardBuilder.save()
- generate_grafana_dashboard()
- generate_slo_dashboard()
- generate_red_dashboard()
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import fields
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from obskit.dashboards.grafana import (
    DashboardBuilder,
    Panel,
    generate_grafana_dashboard,
    generate_red_dashboard,
    generate_slo_dashboard,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_panels_by_type(panels: list[dict], panel_type: str) -> list[dict]:
    return [p for p in panels if p.get("type") == panel_type]


def _find_panels_by_title(panels: list[dict], title: str) -> list[dict]:
    return [p for p in panels if p.get("title") == title]


# ===========================================================================
# Panel dataclass tests
# ===========================================================================


class TestPanel:
    """Tests for the Panel dataclass."""

    def test_panel_required_fields(self):
        """Panel can be instantiated with required fields only."""
        panel = Panel(
            title="My Panel",
            type="stat",
            gridPos={"h": 4, "w": 6, "x": 0, "y": 0},
            targets=[{"expr": "up", "refId": "A"}],
        )
        assert panel.title == "My Panel"
        assert panel.type == "stat"
        assert panel.gridPos == {"h": 4, "w": 6, "x": 0, "y": 0}
        assert panel.targets == [{"expr": "up", "refId": "A"}]

    def test_panel_default_options_and_field_config(self):
        """options and fieldConfig default to empty dicts."""
        panel = Panel(
            title="T",
            type="gauge",
            gridPos={},
            targets=[],
        )
        assert panel.options == {}
        assert panel.fieldConfig == {}

    def test_panel_custom_options_and_field_config(self):
        """Panel accepts custom options and fieldConfig."""
        opts = {"colorMode": "value"}
        fc = {"defaults": {"unit": "percent"}}
        panel = Panel(
            title="T",
            type="stat",
            gridPos={},
            targets=[],
            options=opts,
            fieldConfig=fc,
        )
        assert panel.options == opts
        assert panel.fieldConfig == fc

    def test_to_dict_keys(self):
        """to_dict() returns all expected keys."""
        panel = Panel(
            title="Title",
            type="timeseries",
            gridPos={"h": 8, "w": 12, "x": 0, "y": 0},
            targets=[{"expr": "rate(requests[5m])", "refId": "A"}],
            options={"legend": {}},
            fieldConfig={"defaults": {"unit": "short"}},
        )
        d = panel.to_dict()
        assert set(d.keys()) == {
            "title",
            "type",
            "gridPos",
            "targets",
            "options",
            "fieldConfig",
            "datasource",
        }

    def test_to_dict_datasource(self):
        """to_dict() always injects prometheus datasource."""
        panel = Panel(title="T", type="stat", gridPos={}, targets=[])
        d = panel.to_dict()
        assert d["datasource"] == {"type": "prometheus", "uid": "${datasource}"}

    def test_to_dict_values_are_passthrough(self):
        """to_dict() copies title, type, gridPos, targets, options, fieldConfig as-is."""
        grid = {"h": 4, "w": 6, "x": 6, "y": 2}
        targets = [{"expr": "up", "refId": "A"}]
        panel = Panel(title="Test", type="gauge", gridPos=grid, targets=targets)
        d = panel.to_dict()
        assert d["title"] == "Test"
        assert d["type"] == "gauge"
        assert d["gridPos"] == grid
        assert d["targets"] == targets

    def test_panel_independent_default_dicts(self):
        """Each Panel instance has independent default option/fieldConfig dicts."""
        p1 = Panel(title="A", type="stat", gridPos={}, targets=[])
        p2 = Panel(title="B", type="stat", gridPos={}, targets=[])
        p1.options["key"] = "value"
        assert "key" not in p2.options

    def test_panel_dataclass_fields(self):
        """Panel is a proper dataclass with the right field names."""
        field_names = {f.name for f in fields(Panel)}
        assert field_names == {"title", "type", "gridPos", "targets", "options", "fieldConfig"}


# ===========================================================================
# DashboardBuilder.__init__ tests
# ===========================================================================


class TestDashboardBuilderInit:
    """Tests for DashboardBuilder initialisation."""

    def test_default_title(self):
        builder = DashboardBuilder("order-service")
        assert builder.title == "order-service Overview"

    def test_custom_title(self):
        builder = DashboardBuilder("order-service", title="My Custom Title")
        assert builder.title == "My Custom Title"

    def test_default_uid_replaces_hyphens(self):
        builder = DashboardBuilder("order-service")
        assert builder.uid == "order_service_overview"

    def test_custom_uid(self):
        builder = DashboardBuilder("order-service", uid="custom_uid_123")
        assert builder.uid == "custom_uid_123"

    def test_initial_panels_empty(self):
        builder = DashboardBuilder("svc")
        assert builder.panels == []

    def test_initial_panel_id_is_one(self):
        builder = DashboardBuilder("svc")
        assert builder._panel_id == 1

    def test_initial_current_y_is_zero(self):
        builder = DashboardBuilder("svc")
        assert builder._current_y == 0

    def test_service_name_stored(self):
        builder = DashboardBuilder("my-service")
        assert builder.service_name == "my-service"

    def test_uid_with_underscores_stays(self):
        builder = DashboardBuilder("my_service")
        assert builder.uid == "my_service_overview"


# ===========================================================================
# DashboardBuilder._next_panel_id tests
# ===========================================================================


class TestNextPanelId:
    """Tests for _next_panel_id()."""

    def test_first_call_returns_one(self):
        builder = DashboardBuilder("svc")
        assert builder._next_panel_id() == 1

    def test_second_call_returns_two(self):
        builder = DashboardBuilder("svc")
        builder._next_panel_id()
        assert builder._next_panel_id() == 2

    def test_increments_sequentially(self):
        builder = DashboardBuilder("svc")
        ids = [builder._next_panel_id() for _ in range(5)]
        assert ids == [1, 2, 3, 4, 5]

    def test_internal_counter_advances(self):
        builder = DashboardBuilder("svc")
        builder._next_panel_id()
        assert builder._panel_id == 2


# ===========================================================================
# DashboardBuilder._add_panel tests
# ===========================================================================


class TestAddPanel:
    """Tests for _add_panel()."""

    def test_panel_id_assigned(self):
        builder = DashboardBuilder("svc")
        p: dict[str, Any] = {"title": "T", "type": "stat"}
        builder._add_panel(p)
        assert p["id"] == 1

    def test_panel_appended_to_panels_list(self):
        builder = DashboardBuilder("svc")
        p: dict[str, Any] = {"title": "T", "type": "stat"}
        builder._add_panel(p)
        assert len(builder.panels) == 1
        assert builder.panels[0] is p

    def test_first_panel_x_is_zero(self):
        builder = DashboardBuilder("svc")
        p: dict[str, Any] = {"title": "T", "type": "stat"}
        builder._add_panel(p)
        assert p["gridPos"]["x"] == 0

    def test_second_panel_x_is_twelve(self):
        builder = DashboardBuilder("svc")
        p1: dict[str, Any] = {"title": "A", "type": "stat"}
        p2: dict[str, Any] = {"title": "B", "type": "stat"}
        builder._add_panel(p1)
        builder._add_panel(p2)
        assert p2["gridPos"]["x"] == 12

    def test_third_panel_x_wraps_back_to_zero(self):
        """After 2 panels, the 3rd wraps x back to 0."""
        builder = DashboardBuilder("svc")
        panels = [{"title": str(i), "type": "stat"} for i in range(3)]
        for p in panels:
            builder._add_panel(p)
        assert panels[2]["gridPos"]["x"] == 0

    def test_default_width_and_height(self):
        builder = DashboardBuilder("svc")
        p: dict[str, Any] = {"title": "T", "type": "stat"}
        builder._add_panel(p)
        assert p["gridPos"]["w"] == 12
        assert p["gridPos"]["h"] == 8

    def test_custom_width_and_height(self):
        builder = DashboardBuilder("svc")
        p: dict[str, Any] = {"title": "T", "type": "stat"}
        builder._add_panel(p, width=6, height=4)
        assert p["gridPos"]["w"] == 6
        assert p["gridPos"]["h"] == 4

    def test_current_y_advances_after_two_panels(self):
        """_current_y should advance by height after every second panel."""
        builder = DashboardBuilder("svc")
        p1: dict[str, Any] = {"title": "A", "type": "stat"}
        p2: dict[str, Any] = {"title": "B", "type": "stat"}
        builder._add_panel(p1, height=4)
        builder._add_panel(p2, height=4)
        assert builder._current_y == 4

    def test_current_y_stays_after_one_panel(self):
        builder = DashboardBuilder("svc")
        p: dict[str, Any] = {"title": "T", "type": "stat"}
        builder._add_panel(p, height=8)
        assert builder._current_y == 0

    def test_panel_id_increments_across_multiple_panels(self):
        builder = DashboardBuilder("svc")
        panels = [{"title": str(i), "type": "stat"} for i in range(4)]
        for p in panels:
            builder._add_panel(p)
        ids = [p["id"] for p in panels]
        assert ids == [1, 2, 3, 4]


# ===========================================================================
# DashboardBuilder.add_row tests
# ===========================================================================


class TestAddRow:
    """Tests for add_row()."""

    def test_row_added_to_panels(self):
        builder = DashboardBuilder("svc")
        builder.add_row("Section A")
        assert len(builder.panels) == 1

    def test_row_type_is_row(self):
        builder = DashboardBuilder("svc")
        builder.add_row("Section A")
        assert builder.panels[0]["type"] == "row"

    def test_row_title_matches(self):
        builder = DashboardBuilder("svc")
        builder.add_row("My Row Title")
        assert builder.panels[0]["title"] == "My Row Title"

    def test_row_grid_pos(self):
        builder = DashboardBuilder("svc")
        builder.add_row("R")
        gp = builder.panels[0]["gridPos"]
        assert gp == {"h": 1, "w": 24, "x": 0, "y": 0}

    def test_row_collapsed_is_false(self):
        builder = DashboardBuilder("svc")
        builder.add_row("R")
        assert builder.panels[0]["collapsed"] is False

    def test_row_advances_current_y(self):
        builder = DashboardBuilder("svc")
        builder.add_row("R")
        assert builder._current_y == 1

    def test_multiple_rows_advance_y(self):
        builder = DashboardBuilder("svc")
        builder.add_row("R1")
        builder.add_row("R2")
        assert builder._current_y == 2

    def test_row_id_assigned_from_counter(self):
        builder = DashboardBuilder("svc")
        builder.add_row("R")
        assert builder.panels[0]["id"] == 1

    def test_second_row_has_correct_y(self):
        builder = DashboardBuilder("svc")
        builder.add_row("R1")
        builder.add_row("R2")
        assert builder.panels[1]["gridPos"]["y"] == 1


# ===========================================================================
# DashboardBuilder.add_stat_panel tests
# ===========================================================================


class TestAddStatPanel:
    """Tests for add_stat_panel()."""

    def test_stat_panel_added(self):
        builder = DashboardBuilder("svc")
        builder.add_stat_panel("Availability", "up")
        assert len(builder.panels) == 1

    def test_stat_panel_type(self):
        builder = DashboardBuilder("svc")
        builder.add_stat_panel("Availability", "up")
        assert builder.panels[0]["type"] == "stat"

    def test_stat_panel_title(self):
        builder = DashboardBuilder("svc")
        builder.add_stat_panel("My Stat", "up")
        assert builder.panels[0]["title"] == "My Stat"

    def test_stat_panel_query_in_targets(self):
        builder = DashboardBuilder("svc")
        builder.add_stat_panel("SLO", "obskit_slo_compliance")
        target = builder.panels[0]["targets"][0]
        assert target["expr"] == "obskit_slo_compliance"
        assert target["refId"] == "A"

    def test_stat_panel_default_unit(self):
        builder = DashboardBuilder("svc")
        builder.add_stat_panel("T", "up")
        unit = builder.panels[0]["fieldConfig"]["defaults"]["unit"]
        assert unit == "percent"

    def test_stat_panel_custom_unit(self):
        builder = DashboardBuilder("svc")
        builder.add_stat_panel("T", "up", unit="percentunit")
        unit = builder.panels[0]["fieldConfig"]["defaults"]["unit"]
        assert unit == "percentunit"

    def test_stat_panel_default_thresholds(self):
        builder = DashboardBuilder("svc")
        builder.add_stat_panel("T", "up")
        steps = builder.panels[0]["fieldConfig"]["defaults"]["thresholds"]["steps"]
        assert len(steps) == 3
        colors = [s["color"] for s in steps]
        assert "red" in colors
        assert "yellow" in colors
        assert "green" in colors

    def test_stat_panel_custom_thresholds(self):
        custom = [{"color": "red", "value": None}, {"color": "green", "value": 0.9}]
        builder = DashboardBuilder("svc")
        builder.add_stat_panel("T", "up", thresholds=custom)
        steps = builder.panels[0]["fieldConfig"]["defaults"]["thresholds"]["steps"]
        assert steps == custom

    def test_stat_panel_width_is_six(self):
        builder = DashboardBuilder("svc")
        builder.add_stat_panel("T", "up")
        assert builder.panels[0]["gridPos"]["w"] == 6

    def test_stat_panel_height_is_four(self):
        builder = DashboardBuilder("svc")
        builder.add_stat_panel("T", "up")
        assert builder.panels[0]["gridPos"]["h"] == 4

    def test_stat_panel_options_present(self):
        builder = DashboardBuilder("svc")
        builder.add_stat_panel("T", "up")
        opts = builder.panels[0]["options"]
        assert "colorMode" in opts
        assert "graphMode" in opts

    def test_stat_panel_datasource(self):
        builder = DashboardBuilder("svc")
        builder.add_stat_panel("T", "up")
        ds = builder.panels[0]["datasource"]
        assert ds == {"type": "prometheus", "uid": "${datasource}"}


# ===========================================================================
# DashboardBuilder.add_gauge_panel tests
# ===========================================================================


class TestAddGaugePanel:
    """Tests for add_gauge_panel()."""

    def test_gauge_panel_added(self):
        builder = DashboardBuilder("svc")
        builder.add_gauge_panel("Error Budget", "metric")
        assert len(builder.panels) == 1

    def test_gauge_panel_type(self):
        builder = DashboardBuilder("svc")
        builder.add_gauge_panel("T", "metric")
        assert builder.panels[0]["type"] == "gauge"

    def test_gauge_panel_title(self):
        builder = DashboardBuilder("svc")
        builder.add_gauge_panel("My Gauge", "metric")
        assert builder.panels[0]["title"] == "My Gauge"

    def test_gauge_panel_query_in_targets(self):
        builder = DashboardBuilder("svc")
        builder.add_gauge_panel("T", "my_metric")
        target = builder.panels[0]["targets"][0]
        assert target["expr"] == "my_metric"
        assert target["refId"] == "A"

    def test_gauge_panel_default_unit(self):
        builder = DashboardBuilder("svc")
        builder.add_gauge_panel("T", "m")
        unit = builder.panels[0]["fieldConfig"]["defaults"]["unit"]
        assert unit == "percent"

    def test_gauge_panel_custom_unit(self):
        builder = DashboardBuilder("svc")
        builder.add_gauge_panel("T", "m", unit="percentunit")
        unit = builder.panels[0]["fieldConfig"]["defaults"]["unit"]
        assert unit == "percentunit"

    def test_gauge_panel_default_min_max(self):
        builder = DashboardBuilder("svc")
        builder.add_gauge_panel("T", "m")
        defaults = builder.panels[0]["fieldConfig"]["defaults"]
        assert defaults["min"] == 0
        assert defaults["max"] == 1

    def test_gauge_panel_custom_min_max(self):
        builder = DashboardBuilder("svc")
        builder.add_gauge_panel("T", "m", min_val=0, max_val=100)
        defaults = builder.panels[0]["fieldConfig"]["defaults"]
        assert defaults["min"] == 0
        assert defaults["max"] == 100

    def test_gauge_panel_thresholds_present(self):
        builder = DashboardBuilder("svc")
        builder.add_gauge_panel("T", "m")
        steps = builder.panels[0]["fieldConfig"]["defaults"]["thresholds"]["steps"]
        assert len(steps) == 3

    def test_gauge_panel_width_is_six(self):
        builder = DashboardBuilder("svc")
        builder.add_gauge_panel("T", "m")
        assert builder.panels[0]["gridPos"]["w"] == 6

    def test_gauge_panel_height_is_six(self):
        builder = DashboardBuilder("svc")
        builder.add_gauge_panel("T", "m")
        assert builder.panels[0]["gridPos"]["h"] == 6

    def test_gauge_panel_options(self):
        builder = DashboardBuilder("svc")
        builder.add_gauge_panel("T", "m")
        opts = builder.panels[0]["options"]
        assert "showThresholdLabels" in opts
        assert opts["showThresholdMarkers"] is True

    def test_gauge_panel_datasource(self):
        builder = DashboardBuilder("svc")
        builder.add_gauge_panel("T", "m")
        ds = builder.panels[0]["datasource"]
        assert ds == {"type": "prometheus", "uid": "${datasource}"}


# ===========================================================================
# DashboardBuilder.add_timeseries_panel tests
# ===========================================================================


class TestAddTimeseriesPanel:
    """Tests for add_timeseries_panel()."""

    def test_timeseries_panel_added(self):
        builder = DashboardBuilder("svc")
        builder.add_timeseries_panel("Rate", [{"expr": "rate(req[5m])", "legend": "RPS"}])
        assert len(builder.panels) == 1

    def test_timeseries_panel_type(self):
        builder = DashboardBuilder("svc")
        builder.add_timeseries_panel("T", [{"expr": "up"}])
        assert builder.panels[0]["type"] == "timeseries"

    def test_timeseries_panel_title(self):
        builder = DashboardBuilder("svc")
        builder.add_timeseries_panel("My Series", [{"expr": "up"}])
        assert builder.panels[0]["title"] == "My Series"

    def test_timeseries_single_target(self):
        builder = DashboardBuilder("svc")
        builder.add_timeseries_panel("T", [{"expr": "up", "legend": "Up"}])
        targets = builder.panels[0]["targets"]
        assert len(targets) == 1
        assert targets[0]["expr"] == "up"
        assert targets[0]["legendFormat"] == "Up"
        assert targets[0]["refId"] == "A"

    def test_timeseries_multiple_targets(self):
        builder = DashboardBuilder("svc")
        queries = [
            {"expr": "metric_p50", "legend": "P50"},
            {"expr": "metric_p95", "legend": "P95"},
            {"expr": "metric_p99", "legend": "P99"},
        ]
        builder.add_timeseries_panel("Latency", queries)
        targets = builder.panels[0]["targets"]
        assert len(targets) == 3
        assert targets[0]["refId"] == "A"
        assert targets[1]["refId"] == "B"
        assert targets[2]["refId"] == "C"

    def test_timeseries_target_without_legend(self):
        """If a query has no 'legend' key, legendFormat defaults to empty string."""
        builder = DashboardBuilder("svc")
        builder.add_timeseries_panel("T", [{"expr": "up"}])
        assert builder.panels[0]["targets"][0]["legendFormat"] == ""

    def test_timeseries_default_unit(self):
        builder = DashboardBuilder("svc")
        builder.add_timeseries_panel("T", [{"expr": "up"}])
        unit = builder.panels[0]["fieldConfig"]["defaults"]["unit"]
        assert unit == "short"

    def test_timeseries_custom_unit(self):
        builder = DashboardBuilder("svc")
        builder.add_timeseries_panel("T", [{"expr": "up"}], unit="reqps")
        unit = builder.panels[0]["fieldConfig"]["defaults"]["unit"]
        assert unit == "reqps"

    def test_timeseries_width_is_twelve(self):
        builder = DashboardBuilder("svc")
        builder.add_timeseries_panel("T", [{"expr": "up"}])
        assert builder.panels[0]["gridPos"]["w"] == 12

    def test_timeseries_height_is_eight(self):
        builder = DashboardBuilder("svc")
        builder.add_timeseries_panel("T", [{"expr": "up"}])
        assert builder.panels[0]["gridPos"]["h"] == 8

    def test_timeseries_options_legend_and_tooltip(self):
        builder = DashboardBuilder("svc")
        builder.add_timeseries_panel("T", [{"expr": "up"}])
        opts = builder.panels[0]["options"]
        assert "legend" in opts
        assert "tooltip" in opts

    def test_timeseries_field_config_custom(self):
        builder = DashboardBuilder("svc")
        builder.add_timeseries_panel("T", [{"expr": "up"}])
        custom = builder.panels[0]["fieldConfig"]["defaults"]["custom"]
        assert custom["lineWidth"] == 2
        assert custom["fillOpacity"] == 10

    def test_timeseries_datasource(self):
        builder = DashboardBuilder("svc")
        builder.add_timeseries_panel("T", [{"expr": "up"}])
        ds = builder.panels[0]["datasource"]
        assert ds == {"type": "prometheus", "uid": "${datasource}"}


# ===========================================================================
# DashboardBuilder.add_slo_compliance_panel tests
# ===========================================================================


class TestAddSloCompliancePanel:
    """Tests for add_slo_compliance_panel()."""

    def test_slo_compliance_adds_stat_panel(self):
        builder = DashboardBuilder("svc")
        builder.add_slo_compliance_panel("availability")
        assert len(builder.panels) == 1
        assert builder.panels[0]["type"] == "stat"

    def test_slo_compliance_title_format(self):
        builder = DashboardBuilder("svc")
        builder.add_slo_compliance_panel("availability")
        assert builder.panels[0]["title"] == "SLO: availability"

    def test_slo_compliance_query_format(self):
        builder = DashboardBuilder("svc")
        builder.add_slo_compliance_panel("latency_p95")
        target = builder.panels[0]["targets"][0]
        assert target["expr"] == 'obskit_slo_compliance{slo="latency_p95"}'

    def test_slo_compliance_unit_is_percentunit(self):
        builder = DashboardBuilder("svc")
        builder.add_slo_compliance_panel("availability")
        unit = builder.panels[0]["fieldConfig"]["defaults"]["unit"]
        assert unit == "percentunit"

    def test_slo_compliance_default_target(self):
        """Default target=0.999 produces thresholds at 0.989 and 0.999."""
        builder = DashboardBuilder("svc")
        builder.add_slo_compliance_panel("availability")
        steps = builder.panels[0]["fieldConfig"]["defaults"]["thresholds"]["steps"]
        values = [s["value"] for s in steps]
        assert pytest.approx(0.989, abs=1e-9) in values
        assert pytest.approx(0.999, abs=1e-9) in values

    def test_slo_compliance_custom_target(self):
        builder = DashboardBuilder("svc")
        builder.add_slo_compliance_panel("availability", target=0.95)
        steps = builder.panels[0]["fieldConfig"]["defaults"]["thresholds"]["steps"]
        values = [s["value"] for s in steps]
        assert pytest.approx(0.94, abs=1e-9) in values
        assert pytest.approx(0.95, abs=1e-9) in values

    def test_slo_compliance_threshold_colors(self):
        builder = DashboardBuilder("svc")
        builder.add_slo_compliance_panel("availability")
        steps = builder.panels[0]["fieldConfig"]["defaults"]["thresholds"]["steps"]
        colors = {s["color"] for s in steps}
        assert "red" in colors
        assert "yellow" in colors
        assert "green" in colors


# ===========================================================================
# DashboardBuilder.add_error_budget_panel tests
# ===========================================================================


class TestAddErrorBudgetPanel:
    """Tests for add_error_budget_panel()."""

    def test_error_budget_adds_gauge_panel(self):
        builder = DashboardBuilder("svc")
        builder.add_error_budget_panel()
        assert len(builder.panels) == 1
        assert builder.panels[0]["type"] == "gauge"

    def test_error_budget_title(self):
        builder = DashboardBuilder("svc")
        builder.add_error_budget_panel()
        assert builder.panels[0]["title"] == "Error Budget Remaining"

    def test_error_budget_unit_is_percentunit(self):
        builder = DashboardBuilder("svc")
        builder.add_error_budget_panel()
        unit = builder.panels[0]["fieldConfig"]["defaults"]["unit"]
        assert unit == "percentunit"

    def test_error_budget_generic_query_when_no_name(self):
        builder = DashboardBuilder("svc")
        builder.add_error_budget_panel()
        target = builder.panels[0]["targets"][0]
        assert target["expr"] == "obskit_slo_error_budget_remaining"

    def test_error_budget_scoped_query_when_name_given(self):
        builder = DashboardBuilder("svc")
        builder.add_error_budget_panel(slo_name="availability")
        target = builder.panels[0]["targets"][0]
        assert 'slo=~"availability.*"' in target["expr"]

    def test_error_budget_empty_string_gives_generic_query(self):
        """Explicit empty string is same as omitted."""
        builder = DashboardBuilder("svc")
        builder.add_error_budget_panel(slo_name="")
        target = builder.panels[0]["targets"][0]
        assert target["expr"] == "obskit_slo_error_budget_remaining"


# ===========================================================================
# DashboardBuilder.add_red_metrics_row tests
# ===========================================================================


class TestAddRedMetricsRow:
    """Tests for add_red_metrics_row()."""

    def test_red_row_adds_multiple_panels(self):
        builder = DashboardBuilder("my-service")
        builder.add_red_metrics_row()
        # 1 row + 3 timeseries panels
        assert len(builder.panels) == 4

    def test_red_row_first_panel_is_row_type(self):
        builder = DashboardBuilder("my-service")
        builder.add_red_metrics_row()
        assert builder.panels[0]["type"] == "row"
        assert builder.panels[0]["title"] == "RED Metrics"

    def test_red_row_request_rate_panel(self):
        builder = DashboardBuilder("my-service")
        builder.add_red_metrics_row()
        titles = [p["title"] for p in builder.panels]
        assert "Request Rate" in titles

    def test_red_row_error_rate_panel(self):
        builder = DashboardBuilder("my-service")
        builder.add_red_metrics_row()
        titles = [p["title"] for p in builder.panels]
        assert "Error Rate" in titles

    def test_red_row_latency_panel(self):
        builder = DashboardBuilder("my-service")
        builder.add_red_metrics_row()
        titles = [p["title"] for p in builder.panels]
        assert "Latency Percentiles" in titles

    def test_red_row_request_rate_uses_service_name(self):
        builder = DashboardBuilder("order-service")
        builder.add_red_metrics_row()
        rr_panel = _find_panels_by_title(builder.panels, "Request Rate")[0]
        expr = rr_panel["targets"][0]["expr"]
        assert "order-service" in expr

    def test_red_row_error_rate_uses_service_name(self):
        builder = DashboardBuilder("order-service")
        builder.add_red_metrics_row()
        er_panel = _find_panels_by_title(builder.panels, "Error Rate")[0]
        expr = er_panel["targets"][0]["expr"]
        assert "order-service" in expr

    def test_red_row_latency_has_three_targets(self):
        builder = DashboardBuilder("order-service")
        builder.add_red_metrics_row()
        lat_panel = _find_panels_by_title(builder.panels, "Latency Percentiles")[0]
        assert len(lat_panel["targets"]) == 3

    def test_red_row_latency_target_legends(self):
        builder = DashboardBuilder("order-service")
        builder.add_red_metrics_row()
        lat_panel = _find_panels_by_title(builder.panels, "Latency Percentiles")[0]
        legends = [t["legendFormat"] for t in lat_panel["targets"]]
        assert "P50" in legends
        assert "P95" in legends
        assert "P99" in legends

    def test_red_row_request_rate_unit(self):
        builder = DashboardBuilder("svc")
        builder.add_red_metrics_row()
        rr_panel = _find_panels_by_title(builder.panels, "Request Rate")[0]
        assert rr_panel["fieldConfig"]["defaults"]["unit"] == "reqps"

    def test_red_row_error_rate_unit(self):
        builder = DashboardBuilder("svc")
        builder.add_red_metrics_row()
        er_panel = _find_panels_by_title(builder.panels, "Error Rate")[0]
        assert er_panel["fieldConfig"]["defaults"]["unit"] == "percentunit"

    def test_red_row_latency_unit(self):
        builder = DashboardBuilder("svc")
        builder.add_red_metrics_row()
        lat_panel = _find_panels_by_title(builder.panels, "Latency Percentiles")[0]
        assert lat_panel["fieldConfig"]["defaults"]["unit"] == "s"


# ===========================================================================
# DashboardBuilder.add_golden_signals_row tests
# ===========================================================================


class TestAddGoldenSignalsRow:
    """Tests for add_golden_signals_row()."""

    def test_golden_signals_adds_multiple_panels(self):
        builder = DashboardBuilder("svc")
        builder.add_golden_signals_row()
        # 1 row + 2 timeseries
        assert len(builder.panels) == 3

    def test_golden_signals_row_type(self):
        builder = DashboardBuilder("svc")
        builder.add_golden_signals_row()
        assert builder.panels[0]["type"] == "row"
        assert builder.panels[0]["title"] == "Golden Signals"

    def test_golden_signals_traffic_panel(self):
        builder = DashboardBuilder("svc")
        builder.add_golden_signals_row()
        titles = [p["title"] for p in builder.panels]
        assert "Traffic" in titles

    def test_golden_signals_saturation_panel(self):
        builder = DashboardBuilder("svc")
        builder.add_golden_signals_row()
        titles = [p["title"] for p in builder.panels]
        assert "Saturation" in titles

    def test_golden_signals_traffic_uses_service_name(self):
        builder = DashboardBuilder("order-service")
        builder.add_golden_signals_row()
        traffic_panel = _find_panels_by_title(builder.panels, "Traffic")[0]
        expr = traffic_panel["targets"][0]["expr"]
        assert "order-service" in expr

    def test_golden_signals_saturation_uses_service_name(self):
        builder = DashboardBuilder("order-service")
        builder.add_golden_signals_row()
        sat_panel = _find_panels_by_title(builder.panels, "Saturation")[0]
        expr = sat_panel["targets"][0]["expr"]
        assert "order-service" in expr

    def test_golden_signals_traffic_unit(self):
        builder = DashboardBuilder("svc")
        builder.add_golden_signals_row()
        traffic_panel = _find_panels_by_title(builder.panels, "Traffic")[0]
        assert traffic_panel["fieldConfig"]["defaults"]["unit"] == "reqps"

    def test_golden_signals_saturation_unit(self):
        builder = DashboardBuilder("svc")
        builder.add_golden_signals_row()
        sat_panel = _find_panels_by_title(builder.panels, "Saturation")[0]
        assert sat_panel["fieldConfig"]["defaults"]["unit"] == "percentunit"


# ===========================================================================
# DashboardBuilder.add_slo_row tests
# ===========================================================================


class TestAddSloRow:
    """Tests for add_slo_row()."""

    def test_slo_row_with_two_slos(self):
        builder = DashboardBuilder("svc")
        builder.add_slo_row(["availability", "latency_p95"])
        # 1 row + 2 stat panels (SLOs) + 1 gauge (error budget)
        assert len(builder.panels) == 4

    def test_slo_row_first_panel_is_row(self):
        builder = DashboardBuilder("svc")
        builder.add_slo_row(["availability"])
        assert builder.panels[0]["type"] == "row"
        assert builder.panels[0]["title"] == "SLO Status"

    def test_slo_row_each_slo_gets_stat_panel(self):
        builder = DashboardBuilder("svc")
        builder.add_slo_row(["avail", "latency"])
        stat_panels = _find_panels_by_type(builder.panels, "stat")
        assert len(stat_panels) == 2

    def test_slo_row_stat_titles(self):
        builder = DashboardBuilder("svc")
        builder.add_slo_row(["avail", "latency"])
        stat_panels = _find_panels_by_type(builder.panels, "stat")
        titles = {p["title"] for p in stat_panels}
        assert "SLO: avail" in titles
        assert "SLO: latency" in titles

    def test_slo_row_error_budget_gauge_added(self):
        builder = DashboardBuilder("svc")
        builder.add_slo_row(["availability"])
        gauge_panels = _find_panels_by_type(builder.panels, "gauge")
        assert len(gauge_panels) == 1
        assert gauge_panels[0]["title"] == "Error Budget Remaining"

    def test_slo_row_with_single_slo(self):
        builder = DashboardBuilder("svc")
        builder.add_slo_row(["only-slo"])
        # row + 1 stat + 1 gauge
        assert len(builder.panels) == 3

    def test_slo_row_error_budget_uses_generic_query(self):
        """add_slo_row calls add_error_budget_panel() without slo_name."""
        builder = DashboardBuilder("svc")
        builder.add_slo_row(["avail"])
        gauge_panels = _find_panels_by_type(builder.panels, "gauge")
        assert gauge_panels[0]["targets"][0]["expr"] == "obskit_slo_error_budget_remaining"


# ===========================================================================
# DashboardBuilder.build tests
# ===========================================================================


class TestBuild:
    """Tests for build()."""

    def test_build_returns_dict(self):
        builder = DashboardBuilder("svc")
        result = builder.build()
        assert isinstance(result, dict)

    def test_build_uid_matches(self):
        builder = DashboardBuilder("order-service")
        result = builder.build()
        assert result["uid"] == "order_service_overview"

    def test_build_custom_uid(self):
        builder = DashboardBuilder("svc", uid="custom_uid")
        result = builder.build()
        assert result["uid"] == "custom_uid"

    def test_build_title_matches(self):
        builder = DashboardBuilder("order-service")
        result = builder.build()
        assert result["title"] == "order-service Overview"

    def test_build_custom_title(self):
        builder = DashboardBuilder("svc", title="My Dashboard")
        result = builder.build()
        assert result["title"] == "My Dashboard"

    def test_build_tags(self):
        builder = DashboardBuilder("my-service")
        result = builder.build()
        assert "obskit" in result["tags"]
        assert "auto-generated" in result["tags"]
        assert "my-service" in result["tags"]

    def test_build_timezone(self):
        builder = DashboardBuilder("svc")
        result = builder.build()
        assert result["timezone"] == "browser"

    def test_build_schema_version(self):
        builder = DashboardBuilder("svc")
        result = builder.build()
        assert result["schemaVersion"] == 38

    def test_build_version(self):
        builder = DashboardBuilder("svc")
        result = builder.build()
        assert result["version"] == 1

    def test_build_refresh(self):
        builder = DashboardBuilder("svc")
        result = builder.build()
        assert result["refresh"] == "30s"

    def test_build_time_range(self):
        builder = DashboardBuilder("svc")
        result = builder.build()
        assert result["time"] == {"from": "now-1h", "to": "now"}

    def test_build_templating_has_datasource_variable(self):
        builder = DashboardBuilder("svc")
        result = builder.build()
        variables = result["templating"]["list"]
        names = [v["name"] for v in variables]
        assert "datasource" in names

    def test_build_panels_list(self):
        builder = DashboardBuilder("svc")
        result = builder.build()
        assert "panels" in result
        assert isinstance(result["panels"], list)

    def test_build_panels_empty_when_none_added(self):
        builder = DashboardBuilder("svc")
        result = builder.build()
        assert result["panels"] == []

    def test_build_panels_include_added_panels(self):
        builder = DashboardBuilder("svc")
        builder.add_row("Test Row")
        result = builder.build()
        assert len(result["panels"]) == 1

    def test_build_does_not_mutate_panels_list(self):
        """Calling build() twice returns same panels each time."""
        builder = DashboardBuilder("svc")
        builder.add_row("R")
        r1 = builder.build()
        r2 = builder.build()
        assert r1["panels"] == r2["panels"]


# ===========================================================================
# DashboardBuilder.to_json tests
# ===========================================================================


class TestToJson:
    """Tests for to_json()."""

    def test_to_json_returns_string(self):
        builder = DashboardBuilder("svc")
        result = builder.to_json()
        assert isinstance(result, str)

    def test_to_json_valid_json(self):
        builder = DashboardBuilder("svc")
        result = builder.to_json()
        parsed = json.loads(result)
        assert isinstance(parsed, dict)

    def test_to_json_default_indent(self):
        builder = DashboardBuilder("svc")
        result = builder.to_json()
        # With indent=2, the output should contain newlines and indentation
        assert "\n" in result

    def test_to_json_custom_indent(self):
        builder = DashboardBuilder("svc")
        result_2 = builder.to_json(indent=2)
        result_4 = builder.to_json(indent=4)
        # 4-space indent produces longer output than 2-space
        assert len(result_4) >= len(result_2)

    def test_to_json_content_matches_build(self):
        builder = DashboardBuilder("svc")
        builder.add_row("A Row")
        parsed = json.loads(builder.to_json())
        assert parsed == builder.build()

    def test_to_json_contains_uid(self):
        builder = DashboardBuilder("my-service")
        result = builder.to_json()
        assert "my_service_overview" in result

    def test_to_json_contains_title(self):
        builder = DashboardBuilder("my-service")
        result = builder.to_json()
        assert "my-service Overview" in result


# ===========================================================================
# DashboardBuilder.save tests
# ===========================================================================


class TestSave:
    """Tests for save()."""

    def test_save_creates_file(self):
        builder = DashboardBuilder("svc")
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            path = tmp.name
        try:
            builder.save(path)
            assert os.path.exists(path)
        finally:
            os.unlink(path)

    def test_save_writes_valid_json(self):
        builder = DashboardBuilder("svc")
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            path = tmp.name
        try:
            builder.save(path)
            with open(path) as f:
                data = json.load(f)
            assert isinstance(data, dict)
        finally:
            os.unlink(path)

    def test_save_content_matches_build(self):
        builder = DashboardBuilder("svc")
        builder.add_row("Test Row")
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            path = tmp.name
        try:
            builder.save(path)
            with open(path) as f:
                data = json.load(f)
            assert data == builder.build()
        finally:
            os.unlink(path)

    def test_save_logs_info(self):
        """save() should call logger.info with dashboard_saved event."""
        builder = DashboardBuilder("svc")
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            path = tmp.name
        try:
            with patch("obskit.dashboards.grafana.logger") as mock_logger:
                builder.save(path)
                mock_logger.info.assert_called_once_with("dashboard_saved", filepath=path)
        finally:
            os.unlink(path)

    def test_save_overwrites_existing_file(self):
        builder1 = DashboardBuilder("svc1", title="Dashboard 1")
        builder2 = DashboardBuilder("svc2", title="Dashboard 2")
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            path = tmp.name
        try:
            builder1.save(path)
            builder2.save(path)
            with open(path) as f:
                data = json.load(f)
            assert data["title"] == "Dashboard 2"
        finally:
            os.unlink(path)


# ===========================================================================
# generate_grafana_dashboard tests
# ===========================================================================


class TestGenerateGrafanaDashboard:
    """Tests for generate_grafana_dashboard()."""

    def test_returns_dict(self):
        result = generate_grafana_dashboard("order-service")
        assert isinstance(result, dict)

    def test_default_title(self):
        result = generate_grafana_dashboard("order-service")
        assert result["title"] == "order-service Overview"

    def test_custom_title(self):
        result = generate_grafana_dashboard("order-service", title="Custom Title")
        assert result["title"] == "Custom Title"

    def test_includes_red_by_default(self):
        result = generate_grafana_dashboard("svc")
        row_panels = [p for p in result["panels"] if p.get("type") == "row"]
        row_titles = [p["title"] for p in row_panels]
        assert "RED Metrics" in row_titles

    def test_no_red_when_disabled(self):
        result = generate_grafana_dashboard("svc", include_red=False)
        row_panels = [p for p in result["panels"] if p.get("type") == "row"]
        row_titles = [p["title"] for p in row_panels]
        assert "RED Metrics" not in row_titles

    def test_no_slo_row_when_slo_names_none(self):
        result = generate_grafana_dashboard("svc", slo_names=None)
        row_panels = [p for p in result["panels"] if p.get("type") == "row"]
        row_titles = [p["title"] for p in row_panels]
        assert "SLO Status" not in row_titles

    def test_slo_row_added_when_slo_names_given(self):
        result = generate_grafana_dashboard("svc", slo_names=["avail", "latency"])
        row_panels = [p for p in result["panels"] if p.get("type") == "row"]
        row_titles = [p["title"] for p in row_panels]
        assert "SLO Status" in row_titles

    def test_golden_signals_excluded_by_default(self):
        result = generate_grafana_dashboard("svc")
        row_panels = [p for p in result["panels"] if p.get("type") == "row"]
        row_titles = [p["title"] for p in row_panels]
        assert "Golden Signals" not in row_titles

    def test_golden_signals_included_when_requested(self):
        result = generate_grafana_dashboard("svc", include_golden_signals=True)
        row_panels = [p for p in result["panels"] if p.get("type") == "row"]
        row_titles = [p["title"] for p in row_panels]
        assert "Golden Signals" in row_titles

    def test_all_options_enabled(self):
        result = generate_grafana_dashboard(
            "svc",
            slo_names=["avail"],
            include_red=True,
            include_golden_signals=True,
        )
        row_panels = [p for p in result["panels"] if p.get("type") == "row"]
        row_titles = [p["title"] for p in row_panels]
        assert "SLO Status" in row_titles
        assert "RED Metrics" in row_titles
        assert "Golden Signals" in row_titles

    def test_slo_names_create_stat_panels(self):
        result = generate_grafana_dashboard("svc", slo_names=["avail", "latency"])
        stat_panels = _find_panels_by_type(result["panels"], "stat")
        assert len(stat_panels) == 2

    def test_tags_include_service_name(self):
        result = generate_grafana_dashboard("my-service")
        assert "my-service" in result["tags"]

    def test_tags_include_obskit(self):
        result = generate_grafana_dashboard("svc")
        assert "obskit" in result["tags"]

    def test_empty_panels_when_nothing_included(self):
        result = generate_grafana_dashboard("svc", include_red=False)
        assert result["panels"] == []

    def test_uid_derived_from_service_name(self):
        result = generate_grafana_dashboard("order-service")
        assert result["uid"] == "order_service_overview"


# ===========================================================================
# generate_slo_dashboard tests
# ===========================================================================


class TestGenerateSLODashboard:
    """Tests for generate_slo_dashboard()."""

    def test_returns_dict(self):
        result = generate_slo_dashboard("svc", ["avail"])
        assert isinstance(result, dict)

    def test_default_title(self):
        result = generate_slo_dashboard("order-service", ["avail"])
        assert result["title"] == "order-service SLO Dashboard"

    def test_custom_title(self):
        result = generate_slo_dashboard("svc", ["avail"], title="SLO Overview")
        assert result["title"] == "SLO Overview"

    def test_uid_has_slo_suffix(self):
        result = generate_slo_dashboard("order-service", ["avail"])
        assert result["uid"] == "order_service_slo"

    def test_slo_overview_row_present(self):
        result = generate_slo_dashboard("svc", ["avail"])
        row_panels = [p for p in result["panels"] if p.get("type") == "row"]
        titles = [p["title"] for p in row_panels]
        assert "SLO Overview" in titles

    def test_error_budgets_row_present(self):
        result = generate_slo_dashboard("svc", ["avail"])
        row_panels = [p for p in result["panels"] if p.get("type") == "row"]
        titles = [p["title"] for p in row_panels]
        assert "Error Budgets" in titles

    def test_each_slo_gets_compliance_panel(self):
        result = generate_slo_dashboard("svc", ["avail", "latency", "throughput"])
        stat_panels = _find_panels_by_type(result["panels"], "stat")
        assert len(stat_panels) == 3

    def test_slo_compliance_panel_titles(self):
        result = generate_slo_dashboard("svc", ["avail", "latency"])
        stat_panels = _find_panels_by_type(result["panels"], "stat")
        titles = {p["title"] for p in stat_panels}
        assert "SLO: avail" in titles
        assert "SLO: latency" in titles

    def test_error_budget_gauge_present(self):
        result = generate_slo_dashboard("svc", ["avail"])
        gauge_panels = _find_panels_by_type(result["panels"], "gauge")
        assert len(gauge_panels) == 1

    def test_burn_rate_timeseries_present(self):
        result = generate_slo_dashboard("svc", ["avail"])
        ts_panels = _find_panels_by_type(result["panels"], "timeseries")
        titles = [p["title"] for p in ts_panels]
        assert "Error Budget Burn Rate" in titles

    def test_burn_rate_query_uses_service_name(self):
        result = generate_slo_dashboard("order-service", ["avail"])
        ts_panels = _find_panels_by_type(result["panels"], "timeseries")
        burn_rate = _find_panels_by_title(ts_panels, "Error Budget Burn Rate")[0]
        expr = burn_rate["targets"][0]["expr"]
        assert "order-service" in expr

    def test_burn_rate_legend_uses_label(self):
        result = generate_slo_dashboard("svc", ["avail"])
        ts_panels = _find_panels_by_type(result["panels"], "timeseries")
        burn_rate = _find_panels_by_title(ts_panels, "Error Budget Burn Rate")[0]
        legend = burn_rate["targets"][0]["legendFormat"]
        assert "{{slo}}" in legend

    def test_single_slo_name(self):
        result = generate_slo_dashboard("svc", ["only-slo"])
        stat_panels = _find_panels_by_type(result["panels"], "stat")
        assert len(stat_panels) == 1
        assert stat_panels[0]["title"] == "SLO: only-slo"

    def test_tags_include_service_name(self):
        result = generate_slo_dashboard("my-service", ["avail"])
        assert "my-service" in result["tags"]


# ===========================================================================
# generate_red_dashboard tests
# ===========================================================================


class TestGenerateRedDashboard:
    """Tests for generate_red_dashboard()."""

    def test_returns_dict(self):
        result = generate_red_dashboard("svc")
        assert isinstance(result, dict)

    def test_default_title(self):
        result = generate_red_dashboard("order-service")
        assert result["title"] == "order-service RED Metrics"

    def test_custom_title(self):
        result = generate_red_dashboard("svc", title="My RED Dashboard")
        assert result["title"] == "My RED Dashboard"

    def test_uid_has_red_suffix(self):
        result = generate_red_dashboard("order-service")
        assert result["uid"] == "order_service_red"

    def test_red_metrics_row_present(self):
        result = generate_red_dashboard("svc")
        row_panels = [p for p in result["panels"] if p.get("type") == "row"]
        titles = [p["title"] for p in row_panels]
        assert "RED Metrics" in titles

    def test_golden_signals_row_present(self):
        result = generate_red_dashboard("svc")
        row_panels = [p for p in result["panels"] if p.get("type") == "row"]
        titles = [p["title"] for p in row_panels]
        assert "Golden Signals" in titles

    def test_request_rate_panel_present(self):
        result = generate_red_dashboard("svc")
        titles = [p.get("title") for p in result["panels"]]
        assert "Request Rate" in titles

    def test_error_rate_panel_present(self):
        result = generate_red_dashboard("svc")
        titles = [p.get("title") for p in result["panels"]]
        assert "Error Rate" in titles

    def test_latency_percentiles_panel_present(self):
        result = generate_red_dashboard("svc")
        titles = [p.get("title") for p in result["panels"]]
        assert "Latency Percentiles" in titles

    def test_traffic_panel_present(self):
        result = generate_red_dashboard("svc")
        titles = [p.get("title") for p in result["panels"]]
        assert "Traffic" in titles

    def test_saturation_panel_present(self):
        result = generate_red_dashboard("svc")
        titles = [p.get("title") for p in result["panels"]]
        assert "Saturation" in titles

    def test_panels_use_service_name_in_queries(self):
        result = generate_red_dashboard("my-service")
        timeseries = _find_panels_by_type(result["panels"], "timeseries")
        # At least some timeseries panels should reference the service name
        exprs = [t["expr"] for p in timeseries for t in p["targets"]]
        assert any("my-service" in expr for expr in exprs)

    def test_tags_include_service_name(self):
        result = generate_red_dashboard("my-service")
        assert "my-service" in result["tags"]

    def test_total_row_count(self):
        """RED dashboard must have exactly 2 rows: RED Metrics and Golden Signals."""
        result = generate_red_dashboard("svc")
        row_panels = [p for p in result["panels"] if p.get("type") == "row"]
        assert len(row_panels) == 2


# ===========================================================================
# Integration-style tests (multiple methods combined)
# ===========================================================================


class TestIntegration:
    """Integration-style tests exercising multiple DashboardBuilder methods together."""

    def test_full_dashboard_panel_count(self):
        """A fully built dashboard with SLO row + RED row should have the right count."""
        builder = DashboardBuilder("svc")
        builder.add_slo_row(["avail", "latency"])
        # add_slo_row: 1 row + 2 stat + 1 gauge = 4
        builder.add_red_metrics_row()
        # add_red_metrics_row: 1 row + 3 ts = 4
        assert len(builder.panels) == 8

    def test_panel_ids_are_unique(self):
        builder = DashboardBuilder("svc")
        builder.add_row("R1")
        builder.add_stat_panel("S", "up")
        builder.add_gauge_panel("G", "m")
        builder.add_timeseries_panel("T", [{"expr": "up"}])
        ids = [p["id"] for p in builder.panels]
        assert len(ids) == len(set(ids))

    def test_build_after_multiple_add_calls_is_serializable(self):
        builder = DashboardBuilder("order-service")
        builder.add_slo_row(["avail"])
        builder.add_red_metrics_row()
        builder.add_golden_signals_row()
        result = builder.build()
        serialized = json.dumps(result)
        reparsed = json.loads(serialized)
        assert reparsed["uid"] == "order_service_overview"

    def test_row_y_positions_advance_correctly(self):
        """Row separators should appear at increasing y positions."""
        builder = DashboardBuilder("svc")
        builder.add_row("Row 1")
        builder.add_row("Row 2")
        rows = [p for p in builder.panels if p.get("type") == "row"]
        assert rows[0]["gridPos"]["y"] == 0
        assert rows[1]["gridPos"]["y"] == 1

    def test_generate_and_save_round_trip(self):
        """generate_grafana_dashboard -> save -> reload produces valid dashboard."""
        _dashboard = generate_grafana_dashboard("svc", slo_names=["avail"], include_red=True)
        builder = DashboardBuilder("svc")
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            path = tmp.name
        try:
            builder.save(path)
            with open(path) as f:
                loaded = json.load(f)
            assert "uid" in loaded
            assert "panels" in loaded
        finally:
            os.unlink(path)

    def test_dashboard_templating_datasource_type(self):
        builder = DashboardBuilder("svc")
        result = builder.build()
        ds_var = result["templating"]["list"][0]
        assert ds_var["type"] == "datasource"
        assert ds_var["query"] == "prometheus"

    def test_error_budget_panel_query_with_slo_name(self):
        """add_error_budget_panel with slo_name uses regex match."""
        builder = DashboardBuilder("svc")
        builder.add_error_budget_panel(slo_name="avail")
        query = builder.panels[0]["targets"][0]["expr"]
        assert "avail" in query
        assert ".*" in query

    def test_add_stat_panel_with_none_thresholds_uses_defaults(self):
        """Passing thresholds=None explicitly uses default thresholds."""
        builder = DashboardBuilder("svc")
        builder.add_stat_panel("T", "up", thresholds=None)
        steps = builder.panels[0]["fieldConfig"]["defaults"]["thresholds"]["steps"]
        assert len(steps) == 3

    def test_multiple_stat_panels_have_incrementing_ids(self):
        builder = DashboardBuilder("svc")
        for i in range(4):
            builder.add_stat_panel(f"Panel {i}", f"metric_{i}")
        ids = [p["id"] for p in builder.panels]
        assert ids == list(range(1, 5))
