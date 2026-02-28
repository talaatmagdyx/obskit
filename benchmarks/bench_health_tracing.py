"""
Benchmarks for health-check tracing — HealthResult.to_dict() overhead.

Measures the cost of injecting trace context into health check responses.
This is called on every /health HTTP request.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch
from typing import Any

import pytest

from obskit.health.checker import CheckResult, HealthResult
from obskit.core.types import HealthStatus


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


def _healthy_result() -> HealthResult:
    return HealthResult(
        healthy=True,
        status=HealthStatus.HEALTHY,
        checks={},
        service="bench-svc",
        version="2.0.0",
        timestamp=datetime(2026, 2, 28, 10, 0, 0, tzinfo=UTC),
    )


def _unhealthy_result() -> HealthResult:
    return HealthResult(
        healthy=False,
        status=HealthStatus.UNHEALTHY,
        checks={
            "db": CheckResult(name="db", healthy=False, duration_ms=5.0, error="timeout"),
            "cache": CheckResult(name="cache", healthy=True, duration_ms=0.5),
        },
        service="bench-svc",
        version="2.0.0",
        timestamp=datetime(2026, 2, 28, 10, 0, 0, tzinfo=UTC),
    )


class TestHealthTracingBenchmarks:
    """Benchmarks for HealthResult.to_dict() with/without trace context."""

    # ------------------------------------------------------------------
    # to_dict — no active span
    # ------------------------------------------------------------------

    @pytest.mark.benchmark(group="health_tracing")
    def test_to_dict_no_span(self, benchmark: Any) -> None:
        """to_dict() when no OTel span is active (most common in prod health checks)."""
        try:
            import opentelemetry.trace as otel_trace
        except ImportError:
            pytest.skip("opentelemetry-api not installed")

        result = _healthy_result()
        invalid_span = _make_invalid_span()

        def run() -> dict:
            with patch.object(otel_trace, "get_current_span",
                              return_value=invalid_span):
                return result.to_dict()

        d = benchmark(run)
        assert "trace_id" not in d
        assert d["healthy"] is True

    @pytest.mark.benchmark(group="health_tracing")
    def test_to_dict_with_active_span(self, benchmark: Any) -> None:
        """to_dict() when an OTel span IS active — injects trace_id + span_id."""
        try:
            import opentelemetry.trace as otel_trace
        except ImportError:
            pytest.skip("opentelemetry-api not installed")

        result = _healthy_result()
        valid_span = _make_valid_span()

        def run() -> dict:
            with patch.object(otel_trace, "get_current_span",
                              return_value=valid_span):
                return result.to_dict()

        d = benchmark(run)
        assert "trace_id" in d
        assert len(d["trace_id"]) == 32

    # ------------------------------------------------------------------
    # to_dict — unhealthy result with multiple checks
    # ------------------------------------------------------------------

    @pytest.mark.benchmark(group="health_tracing")
    def test_to_dict_unhealthy_with_span(self, benchmark: Any) -> None:
        """to_dict() for unhealthy result with multiple checks and active span."""
        try:
            import opentelemetry.trace as otel_trace
        except ImportError:
            pytest.skip("opentelemetry-api not installed")

        result = _unhealthy_result()
        valid_span = _make_valid_span()

        def run() -> dict:
            with patch.object(otel_trace, "get_current_span",
                              return_value=valid_span):
                return result.to_dict()

        d = benchmark(run)
        assert d["healthy"] is False
        assert "trace_id" in d
        assert "db" in d["checks"]

    # ------------------------------------------------------------------
    # to_dict — otel unavailable (fastest path)
    # ------------------------------------------------------------------

    @pytest.mark.benchmark(group="health_tracing")
    def test_to_dict_otel_unavailable(self, benchmark: Any) -> None:
        """to_dict() when OTel is not installed — pure dict build, no span lookup."""
        result = _healthy_result()

        def run() -> dict:
            with patch("obskit.health.checker._OTEL_AVAILABLE", False):
                return result.to_dict()

        d = benchmark(run)
        assert d["healthy"] is True
        assert "trace_id" not in d

    # ------------------------------------------------------------------
    # Idempotency — calling to_dict() multiple times
    # ------------------------------------------------------------------

    @pytest.mark.benchmark(group="health_tracing")
    def test_to_dict_idempotent(self, benchmark: Any) -> None:
        """to_dict() called 10x on the same result is stable."""
        result = _healthy_result()

        def run() -> list[dict]:
            return [result.to_dict() for _ in range(10)]

        dicts = benchmark(run)
        assert all(d["service"] == "bench-svc" for d in dicts)
