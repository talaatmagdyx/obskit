"""
Benchmarks for trace-log correlation hot paths.

These benchmarks measure the overhead added by the add_trace_context
structlog processor — critical since it runs on EVERY log call.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from typing import Any

import pytest

from obskit.logging.trace_correlation import (
    add_trace_context,
    get_trace_context,
    is_trace_correlation_available,
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


class TestTraceCorrelationBenchmarks:
    """Benchmarks for the add_trace_context structlog processor."""

    # ------------------------------------------------------------------
    # add_trace_context — no active span (most common in batch workers)
    # ------------------------------------------------------------------

    @pytest.mark.benchmark(group="trace_correlation")
    def test_add_trace_context_no_span(self, benchmark: Any) -> None:
        """Overhead when no OTel span is active (no-op path)."""
        try:
            import opentelemetry.trace as otel_trace
        except ImportError:
            pytest.skip(_OTEL_NOT_INSTALLED)

        mock_logger = MagicMock()

        def run() -> dict:
            event: dict = {"event": "order_placed", "order_id": "123"}
            with patch.object(otel_trace, "get_current_span",
                              return_value=_make_invalid_span()):
                return add_trace_context(mock_logger, "info", event)

        result = benchmark(run)
        assert "trace_id" not in result

    @pytest.mark.benchmark(group="trace_correlation")
    def test_add_trace_context_with_active_span(self, benchmark: Any) -> None:
        """Overhead when an OTel span IS active (injects trace_id + span_id)."""
        try:
            import opentelemetry.trace as otel_trace
        except ImportError:
            pytest.skip(_OTEL_NOT_INSTALLED)

        mock_logger = MagicMock()
        valid_span = _make_valid_span()

        def run() -> dict:
            event: dict = {"event": "order_placed", "order_id": "123"}
            with patch.object(otel_trace, "get_current_span",
                              return_value=valid_span):
                return add_trace_context(mock_logger, "info", event)

        result = benchmark(run)
        assert "trace_id" in result
        assert len(result["trace_id"]) == 32

    # ------------------------------------------------------------------
    # get_trace_context — standalone helper
    # ------------------------------------------------------------------

    @pytest.mark.benchmark(group="trace_correlation")
    def test_get_trace_context_no_span(self, benchmark: Any) -> None:
        """get_trace_context() with no active span — returns {}."""
        try:
            import opentelemetry.trace as otel_trace
        except ImportError:
            pytest.skip(_OTEL_NOT_INSTALLED)

        def run() -> dict:
            with patch.object(otel_trace, "get_current_span",
                              return_value=_make_invalid_span()):
                return get_trace_context()

        result = benchmark(run)
        assert result == {}

    @pytest.mark.benchmark(group="trace_correlation")
    def test_get_trace_context_with_span(self, benchmark: Any) -> None:
        """get_trace_context() with active span — returns {trace_id, span_id}."""
        try:
            import opentelemetry.trace as otel_trace
        except ImportError:
            pytest.skip(_OTEL_NOT_INSTALLED)

        valid_span = _make_valid_span()

        def run() -> dict:
            with patch.object(otel_trace, "get_current_span",
                              return_value=valid_span):
                return get_trace_context()

        result = benchmark(run)
        assert "trace_id" in result

    # ------------------------------------------------------------------
    # otel unavailable (fastest path — single bool check)
    # ------------------------------------------------------------------

    @pytest.mark.benchmark(group="trace_correlation")
    def test_add_trace_context_otel_unavailable(self, benchmark: Any) -> None:
        """Overhead when OTel is not installed — pure bool-check fast path."""
        mock_logger = MagicMock()

        def run() -> dict:
            event: dict = {"event": "nootel"}
            with patch("obskit.logging.trace_correlation._OTEL_AVAILABLE", False):
                return add_trace_context(mock_logger, "info", event)

        result = benchmark(run)
        assert result["event"] == "nootel"

    # ------------------------------------------------------------------
    # is_trace_correlation_available — introspection
    # ------------------------------------------------------------------

    @pytest.mark.benchmark(group="trace_correlation")
    def test_is_trace_correlation_available(self, benchmark: Any) -> None:
        """is_trace_correlation_available() introspection call."""
        result = benchmark(is_trace_correlation_available)
        assert isinstance(result, bool)
