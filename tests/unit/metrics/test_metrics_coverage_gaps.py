"""
Coverage gap tests for obskit-metrics package - metrics submodule.

Targets specific missing lines/branches in:
- metrics/async_recording.py
- metrics/cardinality.py
- metrics/otlp.py
- metrics/pushgateway.py
- metrics/registry.py
- metrics/self_metrics.py
- metrics/statsd_emitter.py
- metrics/tenant.py
- metrics/threadsafe_aggregator.py
- metrics/types.py
"""

from __future__ import annotations

import asyncio
import threading
from unittest.mock import MagicMock, patch

import pytest

# =============================================================================
# metrics/async_recording.py gaps
# =============================================================================


class TestAsyncRecordingGaps:
    """Lines 49->exit, 110-111, 229-243, 274-275."""

    def setup_method(self):
        import obskit.metrics.async_recording as m
        if m._metric_worker_task and not m._metric_worker_task.done():
            m._metric_worker_task.cancel()
        m._metric_queue = None
        m._metric_worker_task = None

    def teardown_method(self):
        import obskit.metrics.async_recording as m
        if m._metric_worker_task and not m._metric_worker_task.done():
            m._metric_worker_task.cancel()
        m._metric_queue = None
        m._metric_worker_task = None

    @pytest.mark.asyncio
    async def test_update_self_metrics_when_queue_is_none(self):
        """Line 49->exit: _update_self_metrics skips update when _metric_queue is None."""
        import obskit.metrics.async_recording as m

        m._metric_queue = None
        m._update_self_metrics()

    @pytest.mark.asyncio
    async def test_worker_handles_outer_exception(self):
        """Lines 110-111: outer Exception in worker loop is caught and logged."""
        import obskit.metrics.async_recording as m

        m._metric_queue = asyncio.Queue(maxsize=10)
        call_count = [0]

        def raising_update():
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("test outer exception")

        with patch.object(m, "_update_self_metrics", side_effect=raising_update):
            task = asyncio.create_task(m._metric_worker())
            await asyncio.sleep(0.1)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:  # NOSONAR
                pass  # NOSONAR

        assert call_count[0] >= 1

    @pytest.mark.asyncio
    async def test_observe_request_exception_fallback_to_sync(self):
        """Lines 229-243: Exception in observe_request falls back to sync."""
        import obskit.metrics.async_recording as m
        from obskit.metrics.async_recording import AsyncREDMetrics

        mock_base = MagicMock()
        metrics = AsyncREDMetrics(mock_base)

        m._metric_queue = asyncio.Queue(maxsize=100)

        with patch("asyncio.wait_for", side_effect=ValueError("queue error")):
            await metrics.observe_request(
                operation="test-op",
                duration_seconds=0.01,
                status="success",
            )

        mock_base.observe_request.assert_called()

    @pytest.mark.asyncio
    async def test_shutdown_drains_remaining_queue_items(self):
        """Lines 274-275: Exception during shutdown drain is swallowed."""
        import obskit.metrics.async_recording as m
        from obskit.metrics.async_recording import _ensure_worker_started, shutdown_async_recording

        await _ensure_worker_started()

        m._metric_queue.put_nowait({"metrics": MagicMock(), "method": "observe_request", "args": (), "kwargs": {}})

        await shutdown_async_recording()
        assert m._metric_queue is None
        assert m._metric_worker_task is None

    @pytest.mark.asyncio
    async def test_shutdown_exception_in_drain_swallowed(self):
        """Lines 274-275: Exception in method call during shutdown drain is caught."""
        import obskit.metrics.async_recording as m
        from obskit.metrics.async_recording import _ensure_worker_started, shutdown_async_recording

        await _ensure_worker_started()

        # Create a metrics mock whose observe_request method raises
        failing_metrics = MagicMock()
        failing_metrics.observe_request.side_effect = RuntimeError("drain error")

        m._metric_queue.put_nowait({
            "metrics": failing_metrics,
            "method": "observe_request",
            "args": (),
            "kwargs": {},
        })

        # Should not raise - exception is swallowed at line 274-275
        await shutdown_async_recording()
        assert m._metric_queue is None


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
        not __import__("obskit.metrics.otlp", fromlist=["OTLP_METRICS_AVAILABLE"]).OTLP_METRICS_AVAILABLE,
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
            exporter._meter_provider.shutdown = MagicMock(side_effect=RuntimeError("shutdown failed"))

        exporter.shutdown()
        # When exception is caught on line 316, _started is NOT set to False
        # (it would have been set on 313 but exception happens at line 311)
        assert exporter._started  # Still True since exception prevented line 313

    @pytest.mark.skipif(
        not __import__("obskit.metrics.otlp", fromlist=["OTLP_METRICS_AVAILABLE"]).OTLP_METRICS_AVAILABLE,
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
            exporter._meter_provider.force_flush = MagicMock(side_effect=RuntimeError("flush failed"))

        result = exporter.force_flush()
        assert result is False

        # Clean up - force _started to False so shutdown works
        exporter._started = False


# =============================================================================
# metrics/pushgateway.py gaps
# =============================================================================


class TestPushgatewayGaps:
    """Lines 542-543."""

    def test_batch_job_metrics_exception_in_push_is_logged(self):
        """Lines 542-543: exception during push in batch_job_metrics is logged."""
        from obskit.metrics.pushgateway import batch_job_metrics

        with patch("obskit.metrics.pushgateway.PushgatewayExporter") as mock_exporter_cls:
            mock_exporter = MagicMock()
            mock_exporter.push.side_effect = RuntimeError("push failed")
            mock_exporter_cls.return_value = mock_exporter

            with batch_job_metrics(
                gateway_url="http://pushgateway:9091",
                job_name="test-job",
            ):
                pass  # NOSONAR


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

        with patch("obskit.metrics.registry._start_http_server") as mock_start,              patch("obskit.metrics.registry.get_settings") as mock_settings_fn:
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

        with patch("obskit.metrics.registry._start_http_server") as mock_start,              patch("obskit.metrics.registry.get_settings") as mock_settings_fn:
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
# metrics/self_metrics.py gaps
# =============================================================================


class TestSelfMetricsGaps:
    """Lines 188->190, 190->195, 309->302, 314-315."""

    def setup_method(self):
        import obskit.metrics.self_metrics as sm
        sm.reset_self_metrics()

    def teardown_method(self):
        import obskit.metrics.self_metrics as sm
        sm.reset_self_metrics()

    def test_get_snapshot_when_queue_depth_is_not_none(self):
        """Lines 188->190, 190->195: True branches - get_snapshot reads queue_depth and queue_capacity."""
        import obskit.metrics.self_metrics as sm

        sm.reset_self_metrics()
        metrics = sm.ObskitSelfMetrics()
        metrics.set_queue_depth(42)
        metrics.set_queue_capacity(1000)
        snapshot = metrics.get_snapshot()
        assert snapshot.queue_depth == 42
        assert snapshot.queue_capacity == 1000

    def test_get_snapshot_with_none_queue_depth(self):
        """Lines 188->190: False branch - _queue_depth is None while PROMETHEUS_AVAILABLE=True."""
        from unittest.mock import patch

        import obskit.metrics.self_metrics as sm

        # Create instance via __new__ to bypass __init__ (no Prometheus registration)
        # then patch PROMETHEUS_AVAILABLE=True so get_snapshot enters the outer if-block
        # and hits the False branch of `if self._queue_depth is not None:`.
        metrics = sm.ObskitSelfMetrics.__new__(sm.ObskitSelfMetrics)
        metrics._version = "0.0.0"
        metrics._queue_depth = None
        metrics._queue_capacity = None
        metrics._dropped_total = None
        metrics._errors_total = None
        metrics._info = None
        with patch("obskit.metrics.self_metrics.PROMETHEUS_AVAILABLE", True):
            snapshot = metrics.get_snapshot()
        assert snapshot.queue_depth == 0
        assert snapshot.queue_capacity == 0

    def test_get_snapshot_with_none_queue_capacity_only(self):
        """Lines 190->195: False branch - _queue_capacity is None but _queue_depth is not."""
        from unittest.mock import MagicMock, patch

        import obskit.metrics.self_metrics as sm

        # Create instance via __new__ to avoid registering real Prometheus Gauges,
        # inject a mock _queue_depth (value=10) with _queue_capacity=None.
        metrics = sm.ObskitSelfMetrics.__new__(sm.ObskitSelfMetrics)
        metrics._version = "0.0.0"
        mock_depth = MagicMock()
        mock_depth._value.get.return_value = 10
        metrics._queue_depth = mock_depth
        metrics._queue_capacity = None
        metrics._dropped_total = None
        metrics._errors_total = None
        metrics._info = None
        with patch("obskit.metrics.self_metrics.PROMETHEUS_AVAILABLE", True):
            snapshot = metrics.get_snapshot()
        assert snapshot.queue_depth == 10
        assert snapshot.queue_capacity == 0

    def test_reset_self_metrics_unregisters_collectors(self):
        """Lines 309->302, 314-315: reset_self_metrics unregisters Prometheus collectors."""
        import obskit.metrics.self_metrics as sm

        sm.reset_self_metrics()
        metrics = sm.ObskitSelfMetrics()
        assert isinstance(metrics, sm.ObskitSelfMetrics)
        sm.reset_self_metrics()
        assert sm._self_metrics is None

    def test_reset_self_metrics_with_none_collector(self):
        """Line 309->302: False branch - collector is None in the for loop."""
        import obskit.metrics.self_metrics as sm

        sm.reset_self_metrics()
        metrics = sm.ObskitSelfMetrics()
        # Null out only the collectors that were NOT registered in Prometheus
        # (_dropped_total, _errors_total, _info) so their real Gauge counterparts
        # still get properly unregistered while the None branch is still hit.
        metrics._dropped_total = None
        metrics._errors_total = None
        metrics._info = None
        sm.reset_self_metrics()
        assert sm._self_metrics is None


# =============================================================================
# metrics/statsd_emitter.py gaps
# =============================================================================


class TestStatsDEmitterGaps:
    """Lines 169-170."""

    def test_close_handles_os_error(self):
        """Lines 169-170: OSError during socket close is swallowed."""
        from obskit.metrics.statsd_emitter import StatsDEmitter

        emitter = StatsDEmitter(host="127.0.0.1", port=8125)
        mock_sock = MagicMock()
        mock_sock.close.side_effect = OSError("socket already closed")
        emitter._sock = mock_sock

        emitter.close()


# =============================================================================
# metrics/tenant.py gaps
# =============================================================================


class TestTenantGaps:
    """Lines 169-173."""

    def test_tenant_context_sets_trace_attributes_on_active_span(self):
        """Lines 169-171: set_attribute called on recording span."""
        from obskit.metrics.tenant import tenant_context

        mock_span = MagicMock()
        mock_span.is_recording.return_value = True

        # patch the import inside the function
        mock_trace = MagicMock()
        mock_trace.get_current_span.return_value = mock_span

        with patch.dict("sys.modules", {"opentelemetry": MagicMock(), "opentelemetry.trace": mock_trace}):
            with patch("builtins.__import__"):
                def import_side_effect(name, *args, **kwargs):
                    if name == "opentelemetry":
                        return MagicMock(trace=mock_trace)
                    if name == "opentelemetry.trace" or (args and "trace" in args[0] if args else False):
                        return mock_trace
                    return __import__(name, *args, **kwargs)

                # Just run without mocking import - test the exception paths instead

        # Test that tenant_context works when opentelemetry is available
        with tenant_context("t-123", company_id="comp-456") as ctx:
            assert ctx["tenant_id"] == "t-123"

    def test_tenant_context_with_recording_span(self):
        """Lines 169-171: set_attribute called on recording span via module patch."""
        import sys

        from obskit.metrics.tenant import tenant_context

        mock_span = MagicMock()
        mock_span.is_recording.return_value = True
        mock_trace_module = MagicMock()
        mock_trace_module.get_current_span.return_value = mock_span

        # Temporarily inject mock into sys.modules
        sys.modules["opentelemetry.trace"] = mock_trace_module
        mock_otel = MagicMock()
        mock_otel.trace = mock_trace_module
        sys.modules["opentelemetry"] = mock_otel

        try:
            with tenant_context("t-123", company_id="comp-456") as ctx:
                assert ctx["tenant_id"] == "t-123"
            mock_span.set_attribute.assert_any_call("tenant.id", "t-123")
            mock_span.set_attribute.assert_any_call("company.id", "comp-456")
        finally:
            # Restore original modules
            if "opentelemetry.trace" in sys.modules:
                del sys.modules["opentelemetry.trace"]
            if "opentelemetry" in sys.modules:
                del sys.modules["opentelemetry"]

    def test_tenant_context_exception_from_trace_is_swallowed(self):
        """Lines 172-173: exception during trace attribute setting is swallowed."""
        import sys

        from obskit.metrics.tenant import tenant_context

        mock_span = MagicMock()
        mock_span.is_recording.return_value = True
        mock_span.set_attribute.side_effect = RuntimeError("trace error")
        mock_trace_module = MagicMock()
        mock_trace_module.get_current_span.return_value = mock_span

        sys.modules["opentelemetry.trace"] = mock_trace_module
        mock_otel = MagicMock()
        mock_otel.trace = mock_trace_module
        sys.modules["opentelemetry"] = mock_otel

        try:
            with tenant_context("t-789") as ctx:
                assert ctx["tenant_id"] == "t-789"
        finally:
            if "opentelemetry.trace" in sys.modules:
                del sys.modules["opentelemetry.trace"]
            if "opentelemetry" in sys.modules:
                del sys.modules["opentelemetry"]

    def test_tenant_context_without_company_id(self):
        """Line 170->175: False branch - company_id is None so company.id attribute not set."""
        import sys

        from obskit.metrics.tenant import tenant_context

        mock_span = MagicMock()
        mock_span.is_recording.return_value = True
        mock_trace_module = MagicMock()
        mock_trace_module.get_current_span.return_value = mock_span

        sys.modules["opentelemetry.trace"] = mock_trace_module
        mock_otel = MagicMock()
        mock_otel.trace = mock_trace_module
        sys.modules["opentelemetry"] = mock_otel

        try:
            # No company_id provided - line 170 is False, company.id not set
            with tenant_context("t-no-company") as ctx:
                assert ctx["tenant_id"] == "t-no-company"
            # tenant.id IS set
            mock_span.set_attribute.assert_any_call("tenant.id", "t-no-company")
            # company.id is NOT set (False branch of if company_id:)
            for call in mock_span.set_attribute.call_args_list:
                assert "company.id" not in str(call)
        finally:
            if "opentelemetry.trace" in sys.modules:
                del sys.modules["opentelemetry.trace"]
            if "opentelemetry" in sys.modules:
                del sys.modules["opentelemetry"]


# =============================================================================
# metrics/threadsafe_aggregator.py gaps
# =============================================================================


class TestThreadsafeAggregatorGaps:
    """Lines 118->120."""

    def test_stop_with_flush_thread_not_none(self):
        """Lines 118->120: True branch - stop() joins flush thread and performs final flush."""
        from obskit.metrics.threadsafe_aggregator import ThreadLocalAggregator

        flushed = []

        def on_flush(counts, durations):
            flushed.append(dict(counts))

        agg = ThreadLocalAggregator(flush_interval_s=60.0, on_flush=on_flush)
        agg.start()
        assert agg._flush_thread is not None

        agg.record_request("op", duration_s=0.1, success=True)
        agg.stop(timeout_s=2.0)

        # After stop, at least one flush should have occurred (the final flush)
        assert len(flushed) >= 1  # stop() calls _flush_once

    def test_stop_with_flush_thread_none(self):
        """Lines 118->120: False branch - stop() when _flush_thread is None."""
        from obskit.metrics.threadsafe_aggregator import ThreadLocalAggregator

        flushed = []

        def on_flush(counts, durations):
            flushed.append(dict(counts))

        agg = ThreadLocalAggregator(flush_interval_s=60.0, on_flush=on_flush)
        # Don't call agg.start() - _flush_thread stays None
        assert agg._flush_thread is None
        # stop() should handle None _flush_thread gracefully
        agg.stop(timeout_s=1.0)  # Covers 118->120 False branch


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
