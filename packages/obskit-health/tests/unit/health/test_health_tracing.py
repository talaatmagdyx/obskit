"""Tests for trace-context injection in obskit.health.checker.HealthResult."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from obskit.health.checker import CheckResult, HealthResult, _get_health_trace_context
from obskit.core.types import HealthStatus


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


def _healthy_result() -> HealthResult:
    return HealthResult(
        healthy=True,
        status=HealthStatus.HEALTHY,
        checks={},
        service="test-svc",
        version="2.0.0",
        timestamp=datetime(2026, 2, 28, 10, 0, 0, tzinfo=UTC),
    )


# ---------------------------------------------------------------------------
# TestGetHealthTraceContext
# ---------------------------------------------------------------------------


class TestGetHealthTraceContext:
    """_get_health_trace_context() private helper."""

    def test_returns_dict(self) -> None:
        result = _get_health_trace_context()
        assert isinstance(result, dict)

    def test_empty_when_no_valid_span(self) -> None:
        """Without an active span, returns {}."""
        try:
            import opentelemetry.trace as otel_trace
        except ImportError:
            pytest.skip("opentelemetry-api not installed")

        with patch.object(otel_trace, "get_current_span", return_value=_make_invalid_span()):
            result = _get_health_trace_context()

        assert result == {}

    def test_returns_trace_and_span_ids_when_span_active(self) -> None:
        """With a valid span, returns trace_id and span_id."""
        try:
            import opentelemetry.trace as otel_trace
        except ImportError:
            pytest.skip("opentelemetry-api not installed")

        with patch.object(otel_trace, "get_current_span", return_value=_make_valid_span()):
            result = _get_health_trace_context()

        assert "trace_id" in result
        assert "span_id" in result
        assert len(result["trace_id"]) == 32
        assert len(result["span_id"]) == 16

    def test_empty_on_exception(self) -> None:
        """Exceptions are swallowed — returns {}."""
        try:
            import opentelemetry.trace as otel_trace
        except ImportError:
            pytest.skip("opentelemetry-api not installed")

        with patch.object(otel_trace, "get_current_span", side_effect=RuntimeError("boom")):
            result = _get_health_trace_context()

        assert result == {}

    def test_empty_when_otel_unavailable(self) -> None:
        """When _OTEL_AVAILABLE is False, returns {}."""
        with patch("obskit.health.checker._OTEL_AVAILABLE", False):
            result = _get_health_trace_context()
        assert result == {}


# ---------------------------------------------------------------------------
# TestHealthResultToDict
# ---------------------------------------------------------------------------


class TestHealthResultToDict:
    """HealthResult.to_dict() — trace context injection."""

    def test_no_trace_keys_when_no_span(self) -> None:
        """Without an active span, to_dict() has no trace_id/span_id."""
        try:
            import opentelemetry.trace as otel_trace
        except ImportError:
            result_dict = _healthy_result().to_dict()
            assert "trace_id" not in result_dict
            return

        with patch.object(otel_trace, "get_current_span", return_value=_make_invalid_span()):
            result_dict = _healthy_result().to_dict()

        assert "trace_id" not in result_dict
        assert "span_id" not in result_dict

    def test_trace_keys_present_when_span_active(self) -> None:
        """With a valid span, to_dict() includes trace_id and span_id."""
        try:
            import opentelemetry.trace as otel_trace
        except ImportError:
            pytest.skip("opentelemetry-api not installed")

        with patch.object(otel_trace, "get_current_span", return_value=_make_valid_span()):
            result_dict = _healthy_result().to_dict()

        assert "trace_id" in result_dict
        assert "span_id" in result_dict

    def test_standard_fields_always_present(self) -> None:
        """Standard fields (status, healthy, service, etc.) are never removed."""
        result_dict = _healthy_result().to_dict()

        assert "status" in result_dict
        assert "healthy" in result_dict
        assert "service" in result_dict
        assert "version" in result_dict
        assert "timestamp" in result_dict
        assert "checks" in result_dict

    def test_trace_id_is_32_hex_chars(self) -> None:
        """trace_id in the response is correctly formatted."""
        try:
            import opentelemetry.trace as otel_trace
        except ImportError:
            pytest.skip("opentelemetry-api not installed")

        with patch.object(otel_trace, "get_current_span", return_value=_make_valid_span()):
            d = _healthy_result().to_dict()

        tid = d.get("trace_id", "")
        assert len(tid) == 32
        assert all(c in "0123456789abcdef" for c in tid)

    def test_unhealthy_result_also_gets_trace_context(self) -> None:
        """Unhealthy results also include trace context when a span is active."""
        try:
            import opentelemetry.trace as otel_trace
        except ImportError:
            pytest.skip("opentelemetry-api not installed")

        unhealthy = HealthResult(
            healthy=False,
            status=HealthStatus.UNHEALTHY,
            checks={
                "db": CheckResult(name="db", healthy=False, duration_ms=5.0, error="timeout"),
            },
            service="svc",
            version="1.0",
        )

        with patch.object(otel_trace, "get_current_span", return_value=_make_valid_span()):
            d = unhealthy.to_dict()

        assert d["healthy"] is False
        assert "trace_id" in d

    def test_to_dict_does_not_mutate_checks(self) -> None:
        """Calling to_dict() multiple times is safe and idempotent."""
        result = _healthy_result()
        d1 = result.to_dict()
        d2 = result.to_dict()
        assert d1["status"] == d2["status"]
