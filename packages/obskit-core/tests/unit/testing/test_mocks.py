"""
Unit tests for obskit testing utilities — mocks and context managers.
"""

from __future__ import annotations

import pytest

from obskit.testing import (
    MockCircuitBreaker,
    MockHealthChecker,
    MockMetrics,
    MockSLOTracker,
    MockTracer,
    ObskitTestContext,
    disable_observability,
    mock_observability,
)
from obskit.testing.mocks import RecordedRequest, RecordedSpan

# ── MockMetrics ───────────────────────────────────────────────────────────────


class TestMockMetrics:
    def test_observe_request_records_entry(self) -> None:
        m = MockMetrics()
        m.observe_request("op", 0.1, "success")
        assert len(m.requests) == 1
        assert m.requests[0].operation == "op"
        assert m.requests[0].status == "success"

    def test_get_request_count_all(self) -> None:
        m = MockMetrics()
        m.observe_request("a", 0.1, "success")
        m.observe_request("b", 0.2, "failure")
        assert m.get_request_count() == 2

    def test_get_request_count_filtered_by_operation(self) -> None:
        m = MockMetrics()
        m.observe_request("a", 0.1, "success")
        m.observe_request("a", 0.1, "failure")
        m.observe_request("b", 0.1, "success")
        assert m.get_request_count("a") == 2
        assert m.get_request_count("b") == 1

    def test_get_request_count_filtered_by_status(self) -> None:
        m = MockMetrics()
        m.observe_request("a", 0.1, "success")
        m.observe_request("a", 0.1, "failure")
        assert m.get_request_count("a", "success") == 1
        assert m.get_request_count("a", "failure") == 1

    def test_assert_request_recorded_passes(self) -> None:
        m = MockMetrics()
        m.observe_request("create_order", 0.1, "success")
        m.assert_request_recorded("create_order")  # should not raise

    def test_assert_request_recorded_fails(self) -> None:
        m = MockMetrics()
        with pytest.raises(AssertionError, match="Expected at least 1 request"):
            m.assert_request_recorded("missing_op")

    def test_assert_request_recorded_with_status(self) -> None:
        m = MockMetrics()
        m.observe_request("op", 0.1, "failure")
        with pytest.raises(AssertionError):
            m.assert_request_recorded("op", status="success")

    def test_assert_no_requests_passes(self) -> None:
        m = MockMetrics()
        m.assert_no_requests()  # should not raise

    def test_assert_no_requests_fails(self) -> None:
        m = MockMetrics()
        m.observe_request("op", 0.1, "success")
        with pytest.raises(AssertionError, match="Expected no requests"):
            m.assert_no_requests("op")

    def test_reset_clears_requests(self) -> None:
        m = MockMetrics()
        m.observe_request("op", 0.1, "success")
        m.reset()
        assert len(m.requests) == 0

    def test_get_requests_returns_all(self) -> None:
        m = MockMetrics()
        m.observe_request("a", 0.1, "success")
        m.observe_request("b", 0.1, "success")
        assert len(m.get_requests()) == 2

    def test_get_requests_filtered(self) -> None:
        m = MockMetrics()
        m.observe_request("a", 0.1, "success")
        m.observe_request("b", 0.1, "success")
        assert len(m.get_requests("a")) == 1

    def test_track_request_records_success(self) -> None:
        m = MockMetrics()
        with m.track_request("my_op"):
            pass
        assert m.get_request_count("my_op", "success") == 1

    def test_track_request_records_failure(self) -> None:
        m = MockMetrics()
        with pytest.raises(ValueError):
            with m.track_request("my_op"):
                raise ValueError("boom")
        assert m.get_request_count("my_op", "failure") == 1

    def test_observe_stores_error_type(self) -> None:
        m = MockMetrics()
        m.observe_request("op", 0.1, "failure", "TimeoutError")
        assert m.requests[0].error_type == "TimeoutError"


# ── MockTracer ────────────────────────────────────────────────────────────────


class TestMockTracer:
    def test_trace_span_records_span(self) -> None:
        t = MockTracer()
        with t.trace_span("my_span"):
            pass
        assert len(t.spans) == 1
        assert t.spans[0].name == "my_span"

    def test_trace_span_status_ok_on_success(self) -> None:
        t = MockTracer()
        with t.trace_span("op"):
            pass
        assert t.spans[0].status == "ok"

    def test_trace_span_status_error_on_exception(self) -> None:
        t = MockTracer()
        with pytest.raises(RuntimeError):
            with t.trace_span("op"):
                raise RuntimeError("fail")
        assert t.spans[0].status == "error"

    def test_assert_span_created_passes(self) -> None:
        t = MockTracer()
        with t.trace_span("my_span"):
            pass
        t.assert_span_created("my_span")  # should not raise

    def test_assert_span_created_fails(self) -> None:
        t = MockTracer()
        with pytest.raises(AssertionError, match="Expected at least 1 span"):
            t.assert_span_created("missing_span")

    def test_get_spans_filtered(self) -> None:
        t = MockTracer()
        with t.trace_span("a"):
            pass
        with t.trace_span("b"):
            pass
        assert len(t.get_spans("a")) == 1

    def test_reset_clears_spans(self) -> None:
        t = MockTracer()
        with t.trace_span("op"):
            pass
        t.reset()
        assert len(t.spans) == 0
        assert t._current_span is None


# ── MockSLOTracker ────────────────────────────────────────────────────────────


class TestMockSLOTracker:
    def test_record_measurement(self) -> None:
        s = MockSLOTracker()
        s.record_measurement("availability", 1.0, success=True)
        assert len(s.measurements) == 1
        assert s.measurements[0].slo_name == "availability"

    def test_assert_measurement_recorded_passes(self) -> None:
        s = MockSLOTracker()
        s.record_measurement("latency")
        s.assert_measurement_recorded("latency")  # should not raise

    def test_assert_measurement_recorded_fails(self) -> None:
        s = MockSLOTracker()
        with pytest.raises(AssertionError, match="Expected at least 1 measurement"):
            s.assert_measurement_recorded("missing_slo")

    def test_get_status_returns_mock(self) -> None:
        s = MockSLOTracker()
        s.record_measurement("avail", 1.0, success=True)
        status = s.get_status("avail")
        assert status is not None
        assert status.current_value == 1.0

    def test_get_status_returns_none_when_empty(self) -> None:
        s = MockSLOTracker()
        assert s.get_status("unknown") is None

    def test_reset_clears_measurements(self) -> None:
        s = MockSLOTracker()
        s.record_measurement("avail")
        s.reset()
        assert len(s.measurements) == 0

    def test_register_slo(self) -> None:
        s = MockSLOTracker()
        s.register_slo("avail", target=0.999)
        assert "avail" in s._slos


# ── MockHealthChecker ─────────────────────────────────────────────────────────


class TestMockHealthChecker:
    def test_set_check_status(self) -> None:
        h = MockHealthChecker()
        h.set_check_status("database", True)
        assert h._checks["database"] is True

    def test_add_liveness_check(self) -> None:
        h = MockHealthChecker()

        @h.add_liveness_check("db")
        def check_db() -> bool:
            return True

        assert "db" in h._liveness_checks

    def test_add_readiness_check(self) -> None:
        h = MockHealthChecker()

        @h.add_readiness_check("cache")
        def check_cache() -> bool:
            return True

        assert "cache" in h._readiness_checks

    async def test_check_health_all_healthy(self) -> None:
        h = MockHealthChecker()
        h.set_check_status("db", True)
        result = await h.check_health()
        assert result.status == "healthy"

    async def test_check_health_unhealthy(self) -> None:
        h = MockHealthChecker()
        h.set_check_status("db", False)
        result = await h.check_health()
        assert result.status == "unhealthy"

    async def test_check_health_no_checks(self) -> None:
        h = MockHealthChecker()
        result = await h.check_health()
        assert result.status == "healthy"


# ── MockCircuitBreaker ────────────────────────────────────────────────────────


class TestMockCircuitBreaker:
    def test_default_state_closed(self) -> None:
        cb = MockCircuitBreaker()
        assert cb._state == "closed"

    def test_set_state(self) -> None:
        cb = MockCircuitBreaker()
        cb.set_state("open")
        assert cb._state == "open"

    def test_closed_state_allows_calls(self) -> None:
        cb = MockCircuitBreaker()
        with cb:
            pass  # should not raise

    def test_reset(self) -> None:
        cb = MockCircuitBreaker()
        cb.set_state("open")
        cb._failure_count = 3
        cb.reset()
        assert cb._state == "closed"
        assert cb._failure_count == 0
        assert cb._success_count == 0

    def test_success_increments_count(self) -> None:
        cb = MockCircuitBreaker()
        with cb:
            pass
        assert cb._success_count == 1

    def test_failure_increments_count(self) -> None:
        cb = MockCircuitBreaker()
        with pytest.raises(ValueError):
            with cb:
                raise ValueError("fail")
        assert cb._failure_count == 1


# ── ObskitTestContext ─────────────────────────────────────────────────────────


class TestObskitTestContext:
    def test_context_has_mock_components(self) -> None:
        ctx = ObskitTestContext()
        assert isinstance(ctx.metrics, MockMetrics)
        assert isinstance(ctx.tracer, MockTracer)
        assert isinstance(ctx.slo_tracker, MockSLOTracker)

    def test_reset_clears_all_mocks(self) -> None:
        ctx = ObskitTestContext()
        ctx.metrics.observe_request("op", 0.1, "success")
        with ctx.tracer.trace_span("span"):
            pass
        ctx.slo_tracker.record_measurement("avail")
        ctx.reset()
        assert len(ctx.metrics.requests) == 0
        assert len(ctx.tracer.spans) == 0
        assert len(ctx.slo_tracker.measurements) == 0

    def test_context_manager_starts_and_stops(self) -> None:
        ctx = ObskitTestContext()
        with ctx as c:
            assert c is ctx
        # After exit, patches should be stopped


# ── disable_observability ─────────────────────────────────────────────────────


class TestDisableObservability:
    def test_disable_observability_context_manager(self) -> None:
        # Should not raise
        with disable_observability():
            pass

    def test_disable_observability_multiple_times(self) -> None:
        with disable_observability():
            with disable_observability():
                pass


# ── mock_observability ────────────────────────────────────────────────────────


class TestMockObservability:
    def test_mock_observability_default(self) -> None:
        with mock_observability() as ctx:
            assert isinstance(ctx.metrics, MockMetrics)
            assert isinstance(ctx.tracer, MockTracer)

    def test_mock_observability_with_custom_metrics(self) -> None:
        custom_metrics = MockMetrics(name="custom")
        with mock_observability(metrics=custom_metrics) as ctx:
            assert ctx.metrics.name == "custom"

    def test_mock_observability_with_custom_tracer(self) -> None:
        custom_tracer = MockTracer()
        with mock_observability(tracer=custom_tracer) as ctx:
            assert ctx.tracer is custom_tracer

    def test_mock_observability_with_custom_slo_tracker(self) -> None:
        custom_slo = MockSLOTracker()
        with mock_observability(slo_tracker=custom_slo) as ctx:
            assert ctx.slo_tracker is custom_slo


# ── RecordedRequest dataclass ─────────────────────────────────────────────────


class TestRecordedRequest:
    def test_default_labels_are_empty(self) -> None:
        r = RecordedRequest(operation="op", duration_seconds=0.1, status="success")
        assert r.labels == {}

    def test_error_type_defaults_to_none(self) -> None:
        r = RecordedRequest(operation="op", duration_seconds=0.1, status="success")
        assert r.error_type is None


# ── RecordedSpan dataclass ────────────────────────────────────────────────────


class TestRecordedSpan:
    def test_default_status(self) -> None:
        s = RecordedSpan(name="my_span")
        assert s.status == "ok"

    def test_default_attributes(self) -> None:
        s = RecordedSpan(name="my_span")
        assert s.attributes == {}

    def test_default_events(self) -> None:
        s = RecordedSpan(name="my_span")
        assert s.events == []


class TestMockMetricsPatch:
    def test_mock_metrics_patch_context(self):
        m = MockMetrics()
        with m.patch() as patched_m:
            assert patched_m is m


class TestMockTracerPatch:
    def test_mock_tracer_get_spans_no_name(self):
        from obskit.testing.mocks import MockTracer, RecordedSpan
        t = MockTracer()
        span = RecordedSpan(name="test_span")
        t.spans.append(span)
        result = t.get_spans()
        assert result is t.spans

    def test_mock_tracer_patch_context(self):
        from obskit.testing.mocks import MockTracer
        t = MockTracer()
        with t.patch() as patched_t:
            assert patched_t is t


class TestMockSLOTrackerPatch:
    def test_mock_slo_tracker_patch_context(self):
        from obskit.testing.mocks import MockSLOTracker
        s = MockSLOTracker()
        with s.patch() as patched_s:
            assert patched_s is s


class TestMockCircuitBreakerProperties:
    def test_state_property(self):
        from obskit.testing.mocks import MockCircuitBreaker
        cb = MockCircuitBreaker("test")
        state = cb.state
        assert state is not None

    def test_failure_count_property(self):
        from obskit.testing.mocks import MockCircuitBreaker
        cb = MockCircuitBreaker("test")
        assert cb.failure_count == 0

    def test_success_count_property(self):
        from obskit.testing.mocks import MockCircuitBreaker
        cb = MockCircuitBreaker("test")
        assert cb.success_count == 0

    def test_enter_open_state_raises(self):
        from unittest.mock import patch

        import pytest

        from obskit.core.errors import CircuitOpenError
        from obskit.testing.mocks import MockCircuitBreaker
        cb = MockCircuitBreaker("test")
        cb.set_state("open")
        # Patch the obskit namespace to include CircuitOpenError
        with patch.dict("sys.modules", {"obskit": type("obskit", (), {"CircuitOpenError": CircuitOpenError})}):
            with pytest.raises(CircuitOpenError):
                with cb:
                    pass

