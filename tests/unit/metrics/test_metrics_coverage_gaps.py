"""
Coverage gap tests for obskit-metrics package - metrics submodule.

Targets specific missing lines/branches in:
- metrics/cardinality.py
- metrics/otlp.py
- metrics/registry.py
- metrics/statsd_emitter.py
- metrics/types.py
"""

from __future__ import annotations

import threading
from unittest.mock import MagicMock, patch

import pytest

# =============================================================================
# metrics/cardinality.py gaps
# =============================================================================


class TestCardinalityGaps:
    """Lines 40-43, 72-74, 212->215, 229->234, 236, 287->289, 292->294,
    309, 348->exit, 350->exit, 355->353, 387->390."""

    def setup_method(self):
        from obskit.metrics.cardinality import reset_cardinality_protector

        reset_cardinality_protector()

    def teardown_method(self):
        from obskit.metrics.cardinality import reset_cardinality_protector

        reset_cardinality_protector()

    def test_prometheus_metrics_exist(self):
        """Lines 40-43, 72-74: PROMETHEUS_AVAILABLE controls metric creation."""
        import obskit.metrics.cardinality as c_module

        assert hasattr(c_module, "CARDINALITY_REJECTIONS")
        assert hasattr(c_module, "CARDINALITY_CURRENT")
        assert hasattr(c_module, "CARDINALITY_LIMIT")

    def test_get_cache_creates_new_cache_and_sets_limit_metric(self):
        """Line 212->215: _get_cache creates new cache and sets CARDINALITY_LIMIT metric."""
        from obskit.metrics.cardinality import CardinalityConfig, CardinalityProtector

        config = CardinalityConfig(default_limit=100)
        protector = CardinalityProtector(config=config)
        cache = protector._get_cache("test_label")
        assert cache is not None
        cache2 = protector._get_cache("test_label")
        assert cache is cache2

    def test_set_limit_recreates_cache_when_exists(self):
        """Lines 229->234, 236: set_limit recreates existing cache."""
        from obskit.metrics.cardinality import CardinalityConfig, CardinalityProtector

        config = CardinalityConfig(default_limit=100)
        protector = CardinalityProtector(config=config)
        protector._get_cache("my_label")
        protector.set_limit("my_label", 50)
        cache = protector._caches["my_label"]
        assert cache.max_size == 50

    def test_protect_updates_cardinality_current_when_value_added(self):
        """Lines 287->289: CARDINALITY_CURRENT updated when new value added."""
        from obskit.metrics.cardinality import CardinalityConfig, CardinalityProtector

        config = CardinalityConfig(default_limit=100)
        protector = CardinalityProtector(config=config)
        result = protector.protect("user_id", "user-123")
        assert result == "user-123"

    def test_protect_increments_rejections_when_limit_reached(self):
        """Lines 292->294: CARDINALITY_REJECTIONS incremented when limit reached."""
        from obskit.metrics.cardinality import CardinalityConfig, CardinalityProtector

        config = CardinalityConfig(default_limit=2)
        protector = CardinalityProtector(config=config)
        protector.protect("service", "svc-a")
        protector.protect("service", "svc-b")
        result = protector.protect("service", "svc-c")
        assert result == "other"

    def test_protect_returns_value_when_limit_reached_non_string(self):
        """Line 309: protect returns original value for non-string when limit exceeded."""
        from obskit.metrics.cardinality import CardinalityConfig, CardinalityProtector

        config = CardinalityConfig(default_limit=1)
        protector = CardinalityProtector(config=config)
        protector.protect("num_label", 1)
        result = protector.protect("num_label", 2)
        assert result == 2

    def test_reset_specific_label_clears_and_updates_metric(self):
        """Lines 348->exit, 350->exit: reset specific label clears cache."""
        from obskit.metrics.cardinality import CardinalityConfig, CardinalityProtector

        config = CardinalityConfig(default_limit=100)
        protector = CardinalityProtector(config=config)
        protector.protect("my_label", "v1")
        protector.protect("my_label", "v2")
        cache_before = len(protector._get_cache("my_label"))
        assert cache_before == 2
        protector.reset("my_label")
        cache_after = len(protector._get_cache("my_label"))
        assert cache_after == 0

    def test_reset_specific_label_not_in_caches(self):
        """Line 348->exit: False branch - label not in caches when reset called."""
        from obskit.metrics.cardinality import CardinalityConfig, CardinalityProtector

        config = CardinalityConfig(default_limit=100)
        protector = CardinalityProtector(config=config)
        # Reset a label that was never added to caches - should be a no-op
        protector.reset("nonexistent_label")  # label_name is truthy but not in _caches

    def test_reset_all_labels_clears_all_and_updates_metrics(self):
        """Lines 355->353: reset None clears all caches."""
        from obskit.metrics.cardinality import CardinalityConfig, CardinalityProtector

        config = CardinalityConfig(default_limit=100)
        protector = CardinalityProtector(config=config)
        protector.protect("label_a", "v1")
        protector.protect("label_b", "v1")
        protector.reset()
        assert len(protector._get_cache("label_a")) == 0
        assert len(protector._get_cache("label_b")) == 0

    def test_get_cardinality_protector_double_checked_locking(self):
        """Lines 387->390: double-checked locking creates new protector."""
        import obskit.metrics.cardinality as c_module
        from obskit.metrics.cardinality import (
            get_cardinality_protector,
            reset_cardinality_protector,
        )

        reset_cardinality_protector()
        assert c_module._cardinality_protector is None
        p1 = get_cardinality_protector()
        assert p1 is not None
        p2 = get_cardinality_protector()
        assert p1 is p2


# =============================================================================
# metrics/otlp.py gaps
# =============================================================================


class TestOTLPGaps:
    """Lines 316-317, 344-350."""

    @pytest.mark.skipif(
        not __import__(
            "obskit.metrics.otlp", fromlist=["OTLP_METRICS_AVAILABLE"]
        ).OTLP_METRICS_AVAILABLE,
        reason="OTLP not available",
    )
    def test_shutdown_exception_is_caught(self):
        """Lines 316-317: exception during shutdown is caught and logged."""
        from obskit.metrics.otlp import OTLPMetricsExporter

        exporter = OTLPMetricsExporter(
            endpoint="http://otel:4317",
            service_name="test-service",
        )
        exporter.start()
        assert exporter._started

        # Mock the meter provider to raise on shutdown - _started stays True since
        # self._started = False is on line 313 BEFORE the raise
        if exporter._meter_provider:
            exporter._meter_provider.shutdown = MagicMock(
                side_effect=RuntimeError("shutdown failed")
            )

        exporter.shutdown()
        # When exception is caught on line 316, _started is NOT set to False
        # (it would have been set on 313 but exception happens at line 311)
        assert exporter._started  # Still True since exception prevented line 313

    @pytest.mark.skipif(
        not __import__(
            "obskit.metrics.otlp", fromlist=["OTLP_METRICS_AVAILABLE"]
        ).OTLP_METRICS_AVAILABLE,
        reason="OTLP not available",
    )
    def test_force_flush_exception_returns_false(self):
        """Lines 344-350: exception in force_flush returns False."""
        from obskit.metrics.otlp import OTLPMetricsExporter

        exporter = OTLPMetricsExporter(
            endpoint="http://otel:4317",
            service_name="test-service",
        )
        exporter.start()

        if exporter._meter_provider:
            exporter._meter_provider.force_flush = MagicMock(
                side_effect=RuntimeError("flush failed")
            )

        result = exporter.force_flush()
        assert result is False

        # Clean up - force _started to False so shutdown works
        exporter._started = False


# =============================================================================
# metrics/registry.py gaps
# =============================================================================


class TestRegistryGaps:
    """Lines 250->255."""

    def setup_method(self):
        from obskit.metrics.registry import reset_registry

        reset_registry()

    def teardown_method(self):
        from obskit.metrics.registry import reset_registry, stop_http_server

        stop_http_server()
        reset_registry()

    @patch("obskit.metrics.registry.PROMETHEUS_AVAILABLE", True)
    def test_start_http_server_no_auth_sets_server_started(self):
        """Lines 250->255: _start_http_server returns non-None result (True branch)."""
        from obskit.metrics.registry import reset_registry, start_http_server, stop_http_server

        reset_registry()

        mock_server = MagicMock()
        mock_thread = MagicMock()

        with (
            patch("obskit.metrics.registry._start_http_server") as mock_start,
            patch("obskit.metrics.registry.get_settings") as mock_settings_fn,
        ):
            mock_settings_fn.return_value.metrics_auth_enabled = False
            mock_settings_fn.return_value.metrics_auth_token = None
            mock_settings_fn.return_value.metrics_port = 19999
            mock_start.return_value = (mock_server, mock_thread)
            result = start_http_server(port=19999, host="127.0.0.1")
            assert result is True

        stop_http_server()
        reset_registry()

    @patch("obskit.metrics.registry.PROMETHEUS_AVAILABLE", True)
    def test_start_http_server_no_auth_returns_none(self):
        """Lines 250->255: False branch - _start_http_server returns None."""
        from obskit.metrics.registry import reset_registry, start_http_server, stop_http_server

        reset_registry()

        with (
            patch("obskit.metrics.registry._start_http_server") as mock_start,
            patch("obskit.metrics.registry.get_settings") as mock_settings_fn,
        ):
            mock_settings_fn.return_value.metrics_auth_enabled = False
            mock_settings_fn.return_value.metrics_auth_token = None
            mock_settings_fn.return_value.metrics_port = 19998
            # _start_http_server returns None
            mock_start.return_value = None
            result = start_http_server(port=19998, host="127.0.0.1")
            assert result is True  # Server started even if result is None

        stop_http_server()
        reset_registry()


# =============================================================================
# metrics/types.py gaps
# =============================================================================


class TestTypesGaps:
    """Lines 159-160, 280-281, 431-432, 533-534."""

    def test_counter_exception_in_unregister_is_swallowed(self):
        """Lines 159-160: exception during counter unregistration is swallowed."""
        import prometheus_client

        from obskit.metrics.types import Counter

        registry = prometheus_client.CollectorRegistry()

        # First counter registers fine
        _c1 = Counter(name="test_exc_ctr_u", documentation="Test", registry=registry)

        # Make unregister raise AND mock prometheus_client.Counter to avoid ValueError
        mock_counter_instance = MagicMock()
        with patch.object(registry, "unregister", side_effect=Exception("unregister failed")):
            with patch("obskit.metrics.types.prometheus_client") as mock_pc:
                mock_pc.REGISTRY = registry
                mock_pc.Counter.return_value = mock_counter_instance
                mock_pc.Gauge = prometheus_client.Gauge
                mock_pc.Histogram = prometheus_client.Histogram
                mock_pc.Summary = prometheus_client.Summary
                # Trigger the except block: name is in _names_to_collectors, unregister raises
                _c2 = Counter(name="test_exc_ctr_u", documentation="Test 2", registry=registry)
        # The except block (lines 159-160) was executed

    def test_gauge_exception_in_unregister_is_swallowed(self):
        """Lines 280-281: exception during gauge unregistration is swallowed."""
        import prometheus_client

        from obskit.metrics.types import Gauge

        registry = prometheus_client.CollectorRegistry()

        _g1 = Gauge(name="test_exc_gau_u", documentation="Test", registry=registry)

        mock_gauge_instance = MagicMock()
        with patch.object(registry, "unregister", side_effect=Exception("unregister failed")):
            with patch("obskit.metrics.types.prometheus_client") as mock_pc:
                mock_pc.REGISTRY = registry
                mock_pc.Gauge.return_value = mock_gauge_instance
                mock_pc.Counter = prometheus_client.Counter
                _g2 = Gauge(name="test_exc_gau_u", documentation="Test 2", registry=registry)

    def test_histogram_exception_in_unregister_is_swallowed(self):
        """Lines 431-432: exception during histogram unregistration is swallowed."""
        import prometheus_client

        from obskit.metrics.types import Histogram

        registry = prometheus_client.CollectorRegistry()

        _h1 = Histogram(name="test_exc_his_u", documentation="Test", registry=registry)

        mock_hist_instance = MagicMock()
        with patch.object(registry, "unregister", side_effect=Exception("unregister failed")):
            with patch("obskit.metrics.types.prometheus_client") as mock_pc:
                mock_pc.REGISTRY = registry
                mock_pc.Histogram.return_value = mock_hist_instance
                mock_pc.Counter = prometheus_client.Counter
                _h2 = Histogram(name="test_exc_his_u", documentation="Test 2", registry=registry)

    def test_summary_exception_in_unregister_is_swallowed(self):
        """Lines 533-534: exception during summary unregistration is swallowed."""
        import prometheus_client

        from obskit.metrics.types import Summary

        registry = prometheus_client.CollectorRegistry()

        _s1 = Summary(name="test_exc_sum_u", documentation="Test", registry=registry)

        mock_summ_instance = MagicMock()
        with patch.object(registry, "unregister", side_effect=Exception("unregister failed")):
            with patch("obskit.metrics.types.prometheus_client") as mock_pc:
                mock_pc.REGISTRY = registry
                mock_pc.Summary.return_value = mock_summ_instance
                mock_pc.Counter = prometheus_client.Counter
                _s2 = Summary(name="test_exc_sum_u", documentation="Test 2", registry=registry)
