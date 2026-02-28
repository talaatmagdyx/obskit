"""
Tests for obskit.metrics.openmetrics module.

Tests cover:
- OPENMETRICS_CONTENT_TYPE constant
- generate_openmetrics function
- _get_openmetrics_type helper
- _format_labels helper
- _format_value helper
- OpenMetricsExemplar: to_string
- OpenMetricsRegistry: add_exemplar, add_info, generate
- add_exemplar convenience function
"""

import math
import time
from unittest.mock import MagicMock, patch

import pytest
from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram

from obskit.metrics.openmetrics import (
    OPENMETRICS_CONTENT_TYPE,
    PROMETHEUS_AVAILABLE,
    OpenMetricsExemplar,
    OpenMetricsRegistry,
    _format_labels,
    _format_value,
    _get_openmetrics_type,
    add_exemplar,
    generate_openmetrics,
)

# =============================================================================
# Constants
# =============================================================================


class TestConstants:
    def test_content_type(self):
        assert OPENMETRICS_CONTENT_TYPE == "application/openmetrics-text; version=1.0.0; charset=utf-8"

    def test_prometheus_available(self):
        assert PROMETHEUS_AVAILABLE is True


# =============================================================================
# _format_labels
# =============================================================================


class TestFormatLabels:
    def test_empty_labels(self):
        result = _format_labels({})
        assert result == ""

    def test_single_label(self):
        result = _format_labels({"method": "GET"})
        assert result == '{method="GET"}'

    def test_multiple_labels_sorted(self):
        result = _format_labels({"status": "200", "method": "GET"})
        # Should be sorted alphabetically
        assert result == '{method="GET",status="200"}'

    def test_label_with_backslash(self):
        result = _format_labels({"path": "a\\b"})
        assert "\\\\" in result

    def test_label_with_double_quote(self):
        result = _format_labels({"value": 'say "hello"'})
        assert '\\"' in result

    def test_label_with_newline(self):
        result = _format_labels({"msg": "line1\nline2"})
        assert "\\n" in result

    def test_none_value_handling(self):
        # Labels are expected to be strings
        result = _format_labels({"key": "value"})
        assert "key" in result


# =============================================================================
# _format_value
# =============================================================================


class TestFormatValue:
    def test_positive_inf(self):
        result = _format_value(float("inf"))
        assert result == "+Inf"

    def test_negative_inf(self):
        result = _format_value(float("-inf"))
        assert result == "-Inf"

    def test_nan(self):
        result = _format_value(float("nan"))
        assert result == "NaN"

    def test_integer_like_float(self):
        result = _format_value(42.0)
        assert "42" in result

    def test_zero(self):
        result = _format_value(0.0)
        assert result == "0.0" or result == "0"

    def test_very_large_value(self):
        result = _format_value(1e16)
        # Should use scientific notation
        assert "e" in result.lower()

    def test_very_small_value(self):
        result = _format_value(1e-5)
        # Should use scientific notation
        assert "e" in result.lower()

    def test_normal_value(self):
        result = _format_value(0.5)
        assert "0.5" in result

    def test_zero_not_scientific(self):
        result = _format_value(0.0)
        # Zero is treated as abs(value) == 0, not small
        assert "e" not in result.lower()


# =============================================================================
# _get_openmetrics_type
# =============================================================================


class TestGetOpenMetricsType:
    def _make_metric(self, type_name):
        m = MagicMock()
        m.type = type_name
        return m

    def test_counter_type(self):
        result = _get_openmetrics_type(self._make_metric("counter"))
        assert result == "counter"

    def test_gauge_type(self):
        result = _get_openmetrics_type(self._make_metric("gauge"))
        assert result == "gauge"

    def test_histogram_type(self):
        result = _get_openmetrics_type(self._make_metric("histogram"))
        assert result == "histogram"

    def test_summary_type(self):
        result = _get_openmetrics_type(self._make_metric("summary"))
        assert result == "summary"

    def test_info_type(self):
        result = _get_openmetrics_type(self._make_metric("info"))
        assert result == "info"

    def test_stateset_type(self):
        result = _get_openmetrics_type(self._make_metric("stateset"))
        assert result == "stateset"

    def test_unknown_type(self):
        result = _get_openmetrics_type(self._make_metric("weird_type"))
        assert result == "unknown"

    def test_uppercase_type(self):
        result = _get_openmetrics_type(self._make_metric("GAUGE"))
        assert result == "gauge"


# =============================================================================
# generate_openmetrics
# =============================================================================


class TestGenerateOpenMetrics:
    def test_returns_bytes(self):
        registry = CollectorRegistry()
        result = generate_openmetrics(registry)
        assert isinstance(result, bytes)

    def test_ends_with_eof(self):
        registry = CollectorRegistry()
        result = generate_openmetrics(registry)
        assert result.endswith(b"# EOF")

    def test_contains_gauge_metric(self):
        registry = CollectorRegistry()
        g = Gauge("test_gauge_om", "A test gauge", registry=registry)
        g.set(42)
        result = generate_openmetrics(registry)
        assert b"test_gauge_om" in result

    def test_contains_counter_metric(self):
        registry = CollectorRegistry()
        c = Counter("test_counter_om_total", "A test counter", registry=registry)
        c.inc(5)
        result = generate_openmetrics(registry)
        assert b"test_counter_om" in result

    def test_contains_help_and_type_lines(self):
        registry = CollectorRegistry()
        g = Gauge("test_gauge_ht", "Help text for gauge", registry=registry)
        g.set(1)
        result = generate_openmetrics(registry)
        decoded = result.decode("utf-8")
        assert "# HELP" in decoded
        assert "# TYPE" in decoded

    def test_with_labeled_metric(self):
        registry = CollectorRegistry()
        g = Gauge("test_labeled_om", "A labeled gauge", ["env"], registry=registry)
        g.labels(env="prod").set(10)
        result = generate_openmetrics(registry)
        assert b"env" in result

    def test_default_registry(self):
        # Uses global REGISTRY when no registry provided
        # Should not raise
        result = generate_openmetrics()
        assert isinstance(result, bytes)
        assert result.endswith(b"# EOF")

    def test_contains_histogram_bucket_sample(self):
        """Line 130: histogram _bucket samples hit the elif branch."""
        from prometheus_client import Histogram as PCHistogram
        registry = CollectorRegistry()
        h = PCHistogram(
            "test_histogram_bucket_om",
            "A test histogram",
            registry=registry,
        )
        h.observe(0.5)
        result = generate_openmetrics(registry)
        decoded = result.decode("utf-8")
        # Histogram generates _bucket samples which hit line 130
        assert "_bucket" in decoded


# =============================================================================
# OpenMetricsExemplar
# =============================================================================


class TestOpenMetricsExemplar:
    def test_creation(self):
        exemplar = OpenMetricsExemplar(
            labels={"trace_id": "abc123"},
            value=0.042,
        )
        assert exemplar.labels == {"trace_id": "abc123"}
        assert exemplar.value == 0.042
        assert exemplar.timestamp is not None

    def test_creation_with_timestamp(self):
        ts = time.time()
        exemplar = OpenMetricsExemplar(
            labels={"trace_id": "abc"},
            value=1.0,
            timestamp=ts,
        )
        assert exemplar.timestamp == ts

    def test_to_string(self):
        exemplar = OpenMetricsExemplar(
            labels={"trace_id": "abc123"},
            value=0.5,
            timestamp=1234567890.0,
        )
        result = exemplar.to_string()
        assert "trace_id" in result
        assert "abc123" in result
        assert "0.5" in result
        assert "1234567890.0" in result
        assert result.startswith(" # {")

    def test_to_string_multiple_labels(self):
        exemplar = OpenMetricsExemplar(
            labels={"trace_id": "t1", "span_id": "s1"},
            value=0.1,
            timestamp=1000.0,
        )
        result = exemplar.to_string()
        assert "trace_id" in result
        assert "span_id" in result

    def test_auto_timestamp(self):
        before = time.time()
        exemplar = OpenMetricsExemplar(labels={}, value=1.0)
        after = time.time()
        assert before <= exemplar.timestamp <= after


# =============================================================================
# OpenMetricsRegistry
# =============================================================================


class TestOpenMetricsRegistry:
    def test_initialization_with_default_registry(self):
        registry = OpenMetricsRegistry()
        assert registry._prometheus_registry is not None
        assert registry._exemplars == {}
        assert registry._info_metrics == {}

    def test_initialization_with_custom_registry(self):
        prom_registry = CollectorRegistry()
        registry = OpenMetricsRegistry(prometheus_registry=prom_registry)
        assert registry._prometheus_registry is prom_registry

    def test_add_info(self):
        registry = OpenMetricsRegistry(prometheus_registry=CollectorRegistry())
        registry.add_info("service_info", {"version": "1.0.0", "env": "prod"})
        assert "service_info" in registry._info_metrics
        assert registry._info_metrics["service_info"]["version"] == "1.0.0"

    def test_add_exemplar(self):
        prom_registry = CollectorRegistry()
        registry = OpenMetricsRegistry(prometheus_registry=prom_registry)
        registry.add_exemplar(
            "http_duration",
            labels={"method": "GET"},
            value=0.042,
            exemplar_labels={"trace_id": "abc123"},
        )
        key = 'http_duration{method="GET"}'
        assert key in registry._exemplars
        assert len(registry._exemplars[key]) == 1

    def test_add_exemplar_caps_at_100(self):
        prom_registry = CollectorRegistry()
        registry = OpenMetricsRegistry(prometheus_registry=prom_registry)
        for i in range(105):
            registry.add_exemplar(
                "http_duration2",
                labels={"method": "POST"},
                value=float(i),
                exemplar_labels={"trace_id": f"t{i}"},
            )
        key = 'http_duration2{method="POST"}'
        assert len(registry._exemplars[key]) == 100

    def test_generate_returns_bytes(self):
        prom_registry = CollectorRegistry()
        registry = OpenMetricsRegistry(prometheus_registry=prom_registry)
        result = registry.generate()
        assert isinstance(result, bytes)

    def test_generate_ends_with_eof(self):
        prom_registry = CollectorRegistry()
        registry = OpenMetricsRegistry(prometheus_registry=prom_registry)
        result = registry.generate()
        assert result.endswith(b"# EOF")

    def test_generate_includes_info_metrics(self):
        prom_registry = CollectorRegistry()
        registry = OpenMetricsRegistry(prometheus_registry=prom_registry)
        registry.add_info("build_info", {"version": "2.0.0"})
        result = registry.generate()
        decoded = result.decode("utf-8")
        assert "build_info" in decoded
        assert "# TYPE build_info info" in decoded

    def test_generate_includes_prometheus_metrics(self):
        prom_registry = CollectorRegistry()
        g = Gauge("my_gauge_om_reg", "A gauge", registry=prom_registry)
        g.set(99)
        registry = OpenMetricsRegistry(prometheus_registry=prom_registry)
        result = registry.generate()
        assert b"my_gauge_om_reg" in result

    def test_generate_includes_exemplars(self):
        prom_registry = CollectorRegistry()
        g = Gauge("gauge_with_exemplar", "A gauge", registry=prom_registry)
        g.set(1.0)
        registry = OpenMetricsRegistry(prometheus_registry=prom_registry)
        # Add exemplar for the gauge sample
        registry.add_exemplar(
            "gauge_with_exemplar",
            labels={},
            value=1.0,
            exemplar_labels={"trace_id": "abc"},
        )
        result = registry.generate()
        # The exemplar should appear in the output
        assert b"trace_id" in result


# =============================================================================
# add_exemplar convenience function
# =============================================================================


class TestAddExemplarFunction:
    def test_add_exemplar_does_not_raise(self):
        # The function is a stub that just logs
        add_exemplar(
            "http_duration_seconds",
            labels={"handler": "/api"},
            value=0.1,
            exemplar_labels={"trace_id": "xyz"},
        )

    def test_add_exemplar_with_empty_labels(self):
        # Should not raise
        add_exemplar(
            "my_metric",
            labels={},
            value=1.0,
            exemplar_labels={"span": "abc"},
        )
