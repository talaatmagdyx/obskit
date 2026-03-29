"""Tests for obskit.logging.trace_correlation — trace-log correlation processor."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from obskit.logging.trace_correlation import (
    _OTEL_AVAILABLE,
    add_trace_context,
    get_trace_context,
    is_trace_correlation_available,
)

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _make_valid_span(
    trace_id: int = 0x4BF92F3577B34DA6A3CE929D0E0E4736, span_id: int = 0x00F067AA0BA902B7
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


# ---------------------------------------------------------------------------
# TestAddTraceContext
# ---------------------------------------------------------------------------


class TestAddTraceContext:
    """add_trace_context() structlog processor."""

    def test_returns_event_dict_unchanged_when_no_span(self) -> None:
        """With no active span, the event dict is returned unchanged."""
        if not _OTEL_AVAILABLE:
            pytest.skip("opentelemetry-api not installed")

        import opentelemetry.trace as otel_trace

        # Use a span that returns an invalid context
        with patch.object(otel_trace, "get_current_span", return_value=_make_invalid_span()):
            event = {"event": "test_event", "level": "info"}
            result = add_trace_context(MagicMock(), "info", event)

        assert "trace_id" not in result
        assert "span_id" not in result
        assert result["event"] == "test_event"

    def test_injects_trace_id_and_span_id_when_span_active(self) -> None:
        """With a valid active span, trace_id and span_id are added."""
        if not _OTEL_AVAILABLE:
            pytest.skip("opentelemetry-api not installed")

        import opentelemetry.trace as otel_trace

        with patch.object(otel_trace, "get_current_span", return_value=_make_valid_span()):
            event: dict = {"event": "order_placed"}
            result = add_trace_context(MagicMock(), "info", event)

        assert "trace_id" in result
        assert "span_id" in result
        assert len(result["trace_id"]) == 32
        assert len(result["span_id"]) == 16

    def test_trace_id_is_hex_string(self) -> None:
        """trace_id is a lowercase 32-character hex string."""
        if not _OTEL_AVAILABLE:
            pytest.skip("opentelemetry-api not installed")

        import opentelemetry.trace as otel_trace

        with patch.object(otel_trace, "get_current_span", return_value=_make_valid_span()):
            result = add_trace_context(MagicMock(), "info", {})

        tid = result.get("trace_id", "")
        assert all(c in "0123456789abcdef" for c in tid)

    def test_returns_event_dict_on_exception(self) -> None:
        """Exceptions inside the processor are swallowed — dict returned unchanged."""
        if not _OTEL_AVAILABLE:
            pytest.skip("opentelemetry-api not installed")

        import opentelemetry.trace as otel_trace

        with patch.object(otel_trace, "get_current_span", side_effect=RuntimeError("oops")):
            event: dict = {"event": "safe"}
            result = add_trace_context(MagicMock(), "info", event)

        assert result["event"] == "safe"
        assert "trace_id" not in result

    def test_does_not_modify_other_fields(self) -> None:
        """Existing event dict fields survive the processor unchanged."""
        if not _OTEL_AVAILABLE:
            pytest.skip("opentelemetry-api not installed")

        import opentelemetry.trace as otel_trace

        event = {"event": "x", "order_id": "123", "user_id": "u-456"}
        with patch.object(otel_trace, "get_current_span", return_value=_make_invalid_span()):
            result = add_trace_context(MagicMock(), "info", event)

        assert result["order_id"] == "123"
        assert result["user_id"] == "u-456"

    def test_returns_event_dict_when_otel_unavailable(self) -> None:
        """When _OTEL_AVAILABLE is False the dict is returned unmodified."""
        event: dict = {"event": "nootel"}
        with patch("obskit.logging.trace_correlation._OTEL_AVAILABLE", False):
            result = add_trace_context(MagicMock(), "info", event)
        assert result is event
        assert "trace_id" not in result


# ---------------------------------------------------------------------------
# TestGetTraceContext
# ---------------------------------------------------------------------------


class TestGetTraceContext:
    """get_trace_context() helper function."""

    def test_returns_empty_dict_when_no_valid_span(self) -> None:
        """With no active span, returns {}."""
        if not _OTEL_AVAILABLE:
            pytest.skip("opentelemetry-api not installed")

        import opentelemetry.trace as otel_trace

        with patch.object(otel_trace, "get_current_span", return_value=_make_invalid_span()):
            result = get_trace_context()

        assert result == {}

    def test_returns_dict_with_trace_and_span_ids(self) -> None:
        """With a valid span, returns dict with trace_id and span_id keys."""
        if not _OTEL_AVAILABLE:
            pytest.skip("opentelemetry-api not installed")

        import opentelemetry.trace as otel_trace

        with patch.object(otel_trace, "get_current_span", return_value=_make_valid_span()):
            result = get_trace_context()

        assert "trace_id" in result
        assert "span_id" in result

    def test_returns_empty_on_exception(self) -> None:
        """Exceptions are swallowed — returns {}."""
        if not _OTEL_AVAILABLE:
            pytest.skip("opentelemetry-api not installed")

        import opentelemetry.trace as otel_trace

        with patch.object(otel_trace, "get_current_span", side_effect=RuntimeError("err")):
            result = get_trace_context()

        assert result == {}

    def test_returns_empty_when_otel_unavailable(self) -> None:
        """When _OTEL_AVAILABLE is False, returns {}."""
        with patch("obskit.logging.trace_correlation._OTEL_AVAILABLE", False):
            result = get_trace_context()
        assert result == {}

    def test_result_is_always_dict(self) -> None:
        """get_trace_context always returns a dict (never raises)."""
        result = get_trace_context()
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# TestIsTraceCorrelationAvailable
# ---------------------------------------------------------------------------


class TestIsTraceCorrelationAvailable:
    """is_trace_correlation_available() introspection helper."""

    def test_returns_bool(self) -> None:
        result = is_trace_correlation_available()
        assert isinstance(result, bool)

    def test_matches_otel_available_flag(self) -> None:
        assert is_trace_correlation_available() == _OTEL_AVAILABLE

    def test_false_when_otel_unavailable(self) -> None:
        with patch("obskit.logging.trace_correlation._OTEL_AVAILABLE", False):
            assert is_trace_correlation_available() is False

    def test_true_when_otel_available(self) -> None:
        with patch("obskit.logging.trace_correlation._OTEL_AVAILABLE", True):
            # _otel_trace must also be non-None; it is when OTel is installed
            assert is_trace_correlation_available() is True
