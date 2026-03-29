"""Tests for obskit.testing.context module."""

import pytest

from obskit.testing.context import capture_metrics, capture_traces, disable_observability


class TestCaptureMetrics:
    def test_capture_metrics_context_manager(self):
        with capture_metrics() as metrics:
            metrics.observe_request("op", 0.1, "success")
        assert len(metrics.requests) == 1

    def test_capture_metrics_yields_mock(self):
        from obskit.testing.mocks import MockMetrics

        with capture_metrics() as m:
            assert isinstance(m, MockMetrics)


class TestCaptureTraces:
    def test_capture_traces_context_manager(self):
        with capture_traces() as tracer:
            tracer.trace_span("test_span").__enter__()

    def test_capture_traces_yields_mock_tracer(self):
        from obskit.testing.mocks import MockTracer

        with capture_traces() as t:
            assert isinstance(t, MockTracer)


class TestDisableObservabilityContext:
    def test_disable_observability_context(self):
        with disable_observability():
            pass  # NOSONAR

    def test_disable_then_noop_span(self):
        from obskit.testing.context import disable_observability

        # disable_observability yields None (bare yield)
        with disable_observability():
            pass  # Just verifies it works without error


class TestDisableObservabilityNoop:
    def test_noop_span_yields_mock(self):
        from unittest.mock import patch

        from obskit.testing.context import disable_observability

        with disable_observability():
            # Test that trace_span patches work
            import obskit.tracing as tr

            # Access the patched trace_span and invoke it
            span_cm = tr.trace_span("test")
            with span_cm as span:
                assert span is not None


class TestContextCoverageGaps:
    """Tests targeting specific uncovered branches in context.py."""

    def test_disable_observability_calls_noop_span(self):
        """Test that noop_span is actually called inside disable_observability (line 87)."""
        import obskit.tracing as tracing_mod
        from obskit.testing.context import disable_observability

        with disable_observability():
            # Call trace_span which is patched to noop_span
            # This triggers execution of the inner noop_span yielding MagicMock
            with tracing_mod.trace_span("test_span") as span:
                assert span is not None

    def test_capture_metrics_records_request(self):
        """Test capture_metrics yielding mock and recording (lines 161-163)."""
        with capture_metrics() as metrics:
            assert metrics is not None
            # Use the mock to record
            metrics.observe_request("test_op", 0.5, "success")
        assert len(metrics.requests) == 1

    def test_capture_traces_records_span(self):
        """Test capture_traces yielding mock tracer (lines 177-179)."""
        with capture_traces() as tracer:
            assert tracer is not None
            # Use the trace_span from the mock
            with tracer.trace_span("test_span"):
                pass  # NOSONAR
        assert len(tracer.spans) == 1


class TestObskitTestContext:
    def test_context_manager(self):
        from obskit.testing.context import ObskitTestContext

        ctx = ObskitTestContext()
        with ctx:
            pass  # NOSONAR

    def test_context_has_metrics(self):
        from obskit.testing.context import ObskitTestContext
        from obskit.testing.mocks import MockMetrics

        ctx = ObskitTestContext()
        assert isinstance(ctx.metrics, MockMetrics)

    def test_context_has_tracer(self):
        from obskit.testing.context import ObskitTestContext
        from obskit.testing.mocks import MockTracer

        ctx = ObskitTestContext()
        assert isinstance(ctx.tracer, MockTracer)

    def test_context_has_slo_tracker(self):
        from obskit.testing.context import ObskitTestContext
        from obskit.testing.mocks import MockSLOTracker

        ctx = ObskitTestContext()
        assert isinstance(ctx.slo_tracker, MockSLOTracker)

    def test_context_reset(self):
        from obskit.testing.context import ObskitTestContext

        ctx = ObskitTestContext()
        with ctx:
            ctx.metrics.observe_request("op", 0.1, "success")
            assert len(ctx.metrics.requests) == 1
            ctx.reset()
            assert len(ctx.metrics.requests) == 0


class TestMockObservabilityContext:
    def test_mock_observability_yields_context(self):
        from obskit.testing.context import ObskitTestContext, mock_observability

        with mock_observability() as ctx:
            assert isinstance(ctx, ObskitTestContext)

    def test_mock_observability_with_custom_metrics(self):
        from obskit.testing.context import mock_observability
        from obskit.testing.mocks import MockMetrics

        custom_metrics = MockMetrics()
        with mock_observability(metrics=custom_metrics) as ctx:
            assert ctx.metrics is custom_metrics

    def test_mock_observability_with_custom_tracer(self):
        from obskit.testing.context import mock_observability
        from obskit.testing.mocks import MockTracer

        custom_tracer = MockTracer()
        with mock_observability(tracer=custom_tracer) as ctx:
            assert ctx.tracer is custom_tracer

    def test_mock_observability_with_custom_slo(self):
        from obskit.testing.context import mock_observability
        from obskit.testing.mocks import MockSLOTracker

        custom_slo = MockSLOTracker()
        with mock_observability(slo_tracker=custom_slo) as ctx:
            assert ctx.slo_tracker is custom_slo
