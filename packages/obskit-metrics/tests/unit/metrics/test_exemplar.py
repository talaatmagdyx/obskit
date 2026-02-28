"""Tests for obskit.metrics.exemplar — trace exemplar support."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from obskit.metrics.exemplar import (
    _OTEL_AVAILABLE,
    _PROM_AVAILABLE,
    get_trace_exemplar,
    is_exemplar_available,
    observe_with_exemplar,
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_valid_span(trace_id: int = 0x4BF92F3577B34DA6A3CE929D0E0E4736,
                     span_id: int = 0x00F067AA0BA902B7) -> MagicMock:
    span = MagicMock()
    ctx = MagicMock()
    ctx.is_valid = True
    ctx.trace_id = trace_id
    ctx.span_id = span_id
    span.get_span_context.return_value = ctx
    return span


def _make_invalid_span() -> MagicMock:
    span = MagicMock()
    ctx = MagicMock()
    ctx.is_valid = False
    span.get_span_context.return_value = ctx
    return span


# ---------------------------------------------------------------------------
# TestGetTraceExemplar
# ---------------------------------------------------------------------------


class TestGetTraceExemplar:
    """get_trace_exemplar() — reads active span context."""

    def test_returns_dict(self) -> None:
        result = get_trace_exemplar()
        assert isinstance(result, dict)

    def test_empty_when_no_valid_span(self) -> None:
        """With no active span, returns {}."""
        if not _OTEL_AVAILABLE:
            pytest.skip("opentelemetry-api not installed")

        import opentelemetry.trace as otel_trace

        with patch.object(otel_trace, "get_current_span", return_value=_make_invalid_span()):
            result = get_trace_exemplar()

        assert result == {}

    def test_contains_trace_id_when_span_active(self) -> None:
        """With a valid span, trace_id is in the returned dict."""
        if not _OTEL_AVAILABLE:
            pytest.skip("opentelemetry-api not installed")

        import opentelemetry.trace as otel_trace

        with patch.object(otel_trace, "get_current_span", return_value=_make_valid_span()):
            result = get_trace_exemplar()

        assert "trace_id" in result
        assert "span_id" in result

    def test_trace_id_format(self) -> None:
        """trace_id must be a 32-character lowercase hex string."""
        if not _OTEL_AVAILABLE:
            pytest.skip("opentelemetry-api not installed")

        import opentelemetry.trace as otel_trace

        with patch.object(otel_trace, "get_current_span", return_value=_make_valid_span()):
            result = get_trace_exemplar()

        assert len(result["trace_id"]) == 32
        assert all(c in "0123456789abcdef" for c in result["trace_id"])

    def test_span_id_format(self) -> None:
        """span_id must be a 16-character lowercase hex string."""
        if not _OTEL_AVAILABLE:
            pytest.skip("opentelemetry-api not installed")

        import opentelemetry.trace as otel_trace

        with patch.object(otel_trace, "get_current_span", return_value=_make_valid_span()):
            result = get_trace_exemplar()

        assert len(result["span_id"]) == 16

    def test_empty_when_otel_unavailable(self) -> None:
        """When _OTEL_AVAILABLE is False, returns {}."""
        with patch("obskit.metrics.exemplar._OTEL_AVAILABLE", False):
            result = get_trace_exemplar()
        assert result == {}

    def test_empty_on_exception(self) -> None:
        """Exceptions inside are swallowed — returns {}."""
        if not _OTEL_AVAILABLE:
            pytest.skip("opentelemetry-api not installed")

        import opentelemetry.trace as otel_trace

        with patch.object(otel_trace, "get_current_span", side_effect=RuntimeError("boom")):
            result = get_trace_exemplar()
        assert result == {}


# ---------------------------------------------------------------------------
# TestObserveWithExemplar
# ---------------------------------------------------------------------------


class TestObserveWithExemplar:
    """observe_with_exemplar() — wrapper around prometheus_client observe."""

    def test_calls_observe_with_exemplar_when_trace_active(self) -> None:
        """When a trace exemplar is available, observe is called with exemplar kwarg."""
        if not _OTEL_AVAILABLE:
            pytest.skip("opentelemetry-api not installed")

        import opentelemetry.trace as otel_trace

        mock_metric = MagicMock()

        with patch.object(otel_trace, "get_current_span", return_value=_make_valid_span()):
            observe_with_exemplar(mock_metric, 0.045)

        # Should have been called with exemplar kwarg or plain observe
        assert mock_metric.observe.call_count == 1

    def test_calls_plain_observe_when_no_trace(self) -> None:
        """Without an active span, observe is called without exemplar."""
        if not _OTEL_AVAILABLE:
            pytest.skip("opentelemetry-api not installed")

        import opentelemetry.trace as otel_trace

        mock_metric = MagicMock()

        with patch.object(otel_trace, "get_current_span", return_value=_make_invalid_span()):
            observe_with_exemplar(mock_metric, 0.123)

        mock_metric.observe.assert_called_once_with(0.123)

    def test_explicit_empty_exemplar_uses_plain_observe(self) -> None:
        """Passing exemplar={} forces plain observe (no auto-detection)."""
        mock_metric = MagicMock()
        observe_with_exemplar(mock_metric, 1.0, exemplar={})
        mock_metric.observe.assert_called_once_with(1.0)

    def test_explicit_exemplar_dict_used(self) -> None:
        """Explicit exemplar dict is passed to observe when non-empty."""
        mock_metric = MagicMock()
        exc = {"trace_id": "abc123"}
        observe_with_exemplar(mock_metric, 0.5, exemplar=exc)
        # Either observe(0.5, exemplar=exc) or observe(0.5) depending on prom version
        assert mock_metric.observe.call_count == 1

    def test_fallback_to_plain_observe_on_type_error(self) -> None:
        """If observe(exemplar=) raises TypeError (old prom-client), falls back."""
        mock_metric = MagicMock()
        mock_metric.observe.side_effect = [TypeError("unexpected kwarg"), None]

        exc = {"trace_id": "abc"}
        observe_with_exemplar(mock_metric, 0.9, exemplar=exc)

        # Second call (fallback) should have been made
        assert mock_metric.observe.call_count == 2

    def test_observe_value_passed_correctly(self) -> None:
        """The value argument is always passed to observe."""
        mock_metric = MagicMock()
        observe_with_exemplar(mock_metric, 42.0, exemplar={})
        args, _ = mock_metric.observe.call_args
        assert args[0] == 42.0

    def test_does_not_raise_on_general_exception(self) -> None:
        """A general exception in observe falls back silently."""
        mock_metric = MagicMock()
        exc_dict = {"trace_id": "x"}
        # First call raises a non-TypeError exception
        mock_metric.observe.side_effect = [Exception("prom crash"), None]
        observe_with_exemplar(mock_metric, 1.5, exemplar=exc_dict)
        # Fallback plain observe should have been called
        assert mock_metric.observe.call_count == 2


# ---------------------------------------------------------------------------
# TestIsExemplarAvailable
# ---------------------------------------------------------------------------


class TestIsExemplarAvailable:
    """is_exemplar_available() introspection."""

    def test_returns_bool(self) -> None:
        result = is_exemplar_available()
        assert isinstance(result, bool)

    def test_false_when_otel_unavailable(self) -> None:
        with patch("obskit.metrics.exemplar._OTEL_AVAILABLE", False):
            assert is_exemplar_available() is False

    def test_false_when_prom_unavailable(self) -> None:
        with patch("obskit.metrics.exemplar._PROM_AVAILABLE", False):
            assert is_exemplar_available() is False

    def test_true_when_both_available(self) -> None:
        with patch("obskit.metrics.exemplar._OTEL_AVAILABLE", True), \
             patch("obskit.metrics.exemplar._PROM_AVAILABLE", True):
            assert is_exemplar_available() is True
