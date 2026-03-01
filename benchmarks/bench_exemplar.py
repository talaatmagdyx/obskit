"""
Benchmarks for Prometheus trace exemplar hot paths.

These benchmarks measure the overhead of observe_with_exemplar() vs
plain observe() — critical since it's called on every request.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from typing import Any

import pytest

from obskit.metrics.exemplar import (
    get_trace_exemplar,
    is_exemplar_available,
    observe_with_exemplar,
)

_OTEL_NOT_INSTALLED = "opentelemetry-api not installed"


def _make_valid_span(
    trace_id: int = 0x4BF92F3577B34DA6A3CE929D0E0E4736,
    span_id: int = 0x00F067AA0BA902B7,
) -> MagicMock:
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


class TestExemplarBenchmarks:
    """Benchmarks for exemplar hot paths."""

    # ------------------------------------------------------------------
    # get_trace_exemplar
    # ------------------------------------------------------------------

    @pytest.mark.benchmark(group="exemplar")
    def test_get_trace_exemplar_no_span(self, benchmark: Any) -> None:
        """get_trace_exemplar() with no active span — returns {}."""
        try:
            import opentelemetry.trace as otel_trace
        except ImportError:
            pytest.skip(_OTEL_NOT_INSTALLED)

        def run() -> dict:
            with patch.object(otel_trace, "get_current_span",
                              return_value=_make_invalid_span()):
                return get_trace_exemplar()

        result = benchmark(run)
        assert result == {}

    @pytest.mark.benchmark(group="exemplar")
    def test_get_trace_exemplar_with_span(self, benchmark: Any) -> None:
        """get_trace_exemplar() with active span — builds {trace_id, span_id}."""
        try:
            import opentelemetry.trace as otel_trace
        except ImportError:
            pytest.skip(_OTEL_NOT_INSTALLED)

        valid_span = _make_valid_span()

        def run() -> dict:
            with patch.object(otel_trace, "get_current_span",
                              return_value=valid_span):
                return get_trace_exemplar()

        result = benchmark(run)
        assert "trace_id" in result
        assert len(result["trace_id"]) == 32

    @pytest.mark.benchmark(group="exemplar")
    def test_get_trace_exemplar_otel_unavailable(self, benchmark: Any) -> None:
        """get_trace_exemplar() when OTel is not installed — fast bool-check path."""
        def run() -> dict:
            with patch("obskit.metrics.exemplar._OTEL_AVAILABLE", False):
                return get_trace_exemplar()

        result = benchmark(run)
        assert result == {}

    # ------------------------------------------------------------------
    # observe_with_exemplar — the critical hot path
    # ------------------------------------------------------------------

    @pytest.mark.benchmark(group="exemplar")
    def test_observe_with_exemplar_active_span(self, benchmark: Any) -> None:
        """observe_with_exemplar() when a trace is active — calls observe(exemplar=...)."""
        try:
            import opentelemetry.trace as otel_trace
        except ImportError:
            pytest.skip(_OTEL_NOT_INSTALLED)

        mock_metric = MagicMock()
        valid_span = _make_valid_span()

        def run() -> None:
            with patch.object(otel_trace, "get_current_span",
                              return_value=valid_span):
                observe_with_exemplar(mock_metric, 0.045)

        benchmark(run)
        assert mock_metric.observe.call_count > 0

    @pytest.mark.benchmark(group="exemplar")
    def test_observe_with_exemplar_no_span(self, benchmark: Any) -> None:
        """observe_with_exemplar() when no trace — plain observe() call."""
        try:
            import opentelemetry.trace as otel_trace
        except ImportError:
            pytest.skip(_OTEL_NOT_INSTALLED)

        mock_metric = MagicMock()
        invalid_span = _make_invalid_span()

        def run() -> None:
            with patch.object(otel_trace, "get_current_span",
                              return_value=invalid_span):
                observe_with_exemplar(mock_metric, 0.123)

        benchmark(run)

    @pytest.mark.benchmark(group="exemplar")
    def test_observe_with_exemplar_explicit_exemplar(self, benchmark: Any) -> None:
        """observe_with_exemplar() with explicit exemplar dict — no OTel lookup."""
        mock_metric = MagicMock()
        exc = {"trace_id": "4bf92f3577b34da6a3ce929d0e0e4736"}

        def run() -> None:
            observe_with_exemplar(mock_metric, 0.5, exemplar=exc)

        benchmark(run)

    @pytest.mark.benchmark(group="exemplar")
    def test_observe_with_explicit_empty_exemplar(self, benchmark: Any) -> None:
        """observe_with_exemplar(exemplar={}) — plain observe, no lookup."""
        mock_metric = MagicMock()

        def run() -> None:
            observe_with_exemplar(mock_metric, 1.0, exemplar={})

        benchmark(run)

    # ------------------------------------------------------------------
    # is_exemplar_available
    # ------------------------------------------------------------------

    @pytest.mark.benchmark(group="exemplar")
    def test_is_exemplar_available(self, benchmark: Any) -> None:
        """is_exemplar_available() introspection call overhead."""
        result = benchmark(is_exemplar_available)
        assert isinstance(result, bool)
