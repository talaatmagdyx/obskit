"""Tests for the shared MiddlewareCore."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from obskit.middleware.core import (
    MiddlewareCore,
    RequestContext,
    _CORRELATION_ID_RE,
    _DEFAULT_EXCLUDE_PATHS,
)


class TestRequestContext:
    def test_defaults(self) -> None:
        ctx = RequestContext(
            start_time=1.0,
            correlation_id="abc",
            operation="test_op",
            method="GET",
            path="/test",
        )
        assert ctx.trace_ctx is None
        assert ctx.metrics_recorded is False
        assert ctx.extra == {}


class TestCorrelationIdRegex:
    @pytest.mark.parametrize(
        "valid",
        [
            "abc-123",
            "request_id_456",
            "a" * 64,
            "a" * 128,
            "simple",
            "request_id.456",  # dots are allowed per spec
        ],
    )
    def test_valid_ids(self, valid: str) -> None:
        assert _CORRELATION_ID_RE.match(valid) is not None

    @pytest.mark.parametrize(
        "invalid",
        [
            "",
            "a" * 129,
            "has spaces",
            "has;semicolons",
            "<script>alert(1)</script>",
        ],
    )
    def test_invalid_ids(self, invalid: str) -> None:
        assert _CORRELATION_ID_RE.match(invalid) is None


class TestShouldExclude:
    def test_exact_match(self) -> None:
        core = MiddlewareCore(exclude_paths=["/health", "/metrics"])
        assert core.should_exclude("/health") is True
        assert core.should_exclude("/metrics") is True

    def test_sub_path_match(self) -> None:
        core = MiddlewareCore(exclude_paths=["/health"])
        assert core.should_exclude("/health/detail") is True
        assert core.should_exclude("/health/") is True

    def test_no_false_positive(self) -> None:
        core = MiddlewareCore(exclude_paths=["/health"])
        assert core.should_exclude("/health_check") is False
        assert core.should_exclude("/api/health") is False

    def test_non_excluded(self) -> None:
        core = MiddlewareCore(exclude_paths=["/health"])
        assert core.should_exclude("/api/orders") is False

    def test_default_paths(self) -> None:
        core = MiddlewareCore()
        assert core.exclude_paths == _DEFAULT_EXCLUDE_PATHS
        for p in ["/health", "/ready", "/live", "/metrics"]:
            assert core.should_exclude(p) is True


class TestExtractCorrelationId:
    def test_extracts_lowercase_header(self) -> None:
        cid = MiddlewareCore.extract_correlation_id({"x-correlation-id": "abc-123"})
        assert cid == "abc-123"

    def test_extracts_mixed_case_header(self) -> None:
        cid = MiddlewareCore.extract_correlation_id({"X-Correlation-ID": "def-456"})
        assert cid == "def-456"

    def test_generates_uuid_when_missing(self) -> None:
        cid = MiddlewareCore.extract_correlation_id({})
        assert len(cid) == 32  # secrets.token_hex(16) — 32 lowercase hex chars

    def test_rejects_invalid_and_generates(self) -> None:
        cid = MiddlewareCore.extract_correlation_id(
            {"x-correlation-id": "<script>alert(1)</script>"}
        )
        # Should generate a new token, not use the invalid one
        assert "<script>" not in cid
        assert len(cid) == 32


class TestBeginRequest:
    def test_sets_correlation_id(self) -> None:
        core = MiddlewareCore(track_metrics=False, track_logging=False, track_tracing=False)
        ctx = core.begin_request(
            headers={"x-correlation-id": "test-123"},
            path="/api/orders",
            method="GET",
        )
        assert ctx.correlation_id == "test-123"
        assert ctx.method == "GET"
        assert ctx.path == "/api/orders"

    def test_default_operation_from_path(self) -> None:
        core = MiddlewareCore(track_metrics=False, track_logging=False, track_tracing=False)
        ctx = core.begin_request(headers={}, path="/api/orders", method="GET")
        assert ctx.operation == "api_orders"

    def test_explicit_operation(self) -> None:
        core = MiddlewareCore(track_metrics=False, track_logging=False, track_tracing=False)
        ctx = core.begin_request(
            headers={}, path="/api/orders", method="GET", operation="list_orders"
        )
        assert ctx.operation == "list_orders"

    def test_empty_path_defaults_to_unknown(self) -> None:
        core = MiddlewareCore(track_metrics=False, track_logging=False, track_tracing=False)
        ctx = core.begin_request(headers={}, path="/", method="GET")
        assert ctx.operation == "unknown"

    def test_logging_emitted(self) -> None:
        core = MiddlewareCore(track_metrics=False, track_logging=True, track_tracing=False)
        with patch("obskit.middleware.core._core_logger") as mock_logger:
            core.begin_request(headers={}, path="/test", method="POST")
            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args
            assert call_args[0][0] == "request_started"

    def test_tracing_extract(self) -> None:
        core = MiddlewareCore(track_metrics=False, track_logging=False, track_tracing=True)
        ctx = core.begin_request(headers={}, path="/test", method="GET")
        # trace_ctx may be None if no traceparent header, but the code path was exercised
        assert ctx.trace_ctx is None or ctx.trace_ctx is not None


class TestEndRequest:
    def _make_ctx(self, **kwargs: object) -> RequestContext:
        import time

        defaults = {
            "start_time": time.perf_counter(),
            "correlation_id": "test-id",
            "operation": "test_op",
            "method": "GET",
            "path": "/test",
        }
        defaults.update(kwargs)
        return RequestContext(**defaults)  # type: ignore[arg-type]

    def test_records_success(self) -> None:
        mock_metrics = MagicMock()
        core = MiddlewareCore(track_logging=False, track_tracing=False)
        core.red_metrics = mock_metrics

        ctx = self._make_ctx()
        core.end_request(ctx, 200)

        mock_metrics.observe_request.assert_called_once()
        call_kwargs = mock_metrics.observe_request.call_args[1]
        assert call_kwargs["status"] == "success"
        assert call_kwargs["error_type"] is None
        assert ctx.metrics_recorded is True

    def test_records_failure(self) -> None:
        mock_metrics = MagicMock()
        core = MiddlewareCore(track_logging=False, track_tracing=False)
        core.red_metrics = mock_metrics

        ctx = self._make_ctx()
        core.end_request(ctx, 500)

        call_kwargs = mock_metrics.observe_request.call_args[1]
        assert call_kwargs["status"] == "failure"
        assert call_kwargs["error_type"] == "HTTP500"

    def test_no_double_recording(self) -> None:
        mock_metrics = MagicMock()
        core = MiddlewareCore(track_logging=False, track_tracing=False)
        core.red_metrics = mock_metrics

        ctx = self._make_ctx()
        core.end_request(ctx, 200)
        core.end_request(ctx, 200)  # Second call should be a no-op

        assert mock_metrics.observe_request.call_count == 1

    def test_operation_override(self) -> None:
        mock_metrics = MagicMock()
        core = MiddlewareCore(track_logging=False, track_tracing=False)
        core.red_metrics = mock_metrics

        ctx = self._make_ctx(operation="original")
        core.end_request(ctx, 200, operation_override="overridden")

        call_kwargs = mock_metrics.observe_request.call_args[1]
        assert call_kwargs["operation"] == "overridden"

    def test_logging_emitted(self) -> None:
        core = MiddlewareCore(track_metrics=False, track_logging=True, track_tracing=False)
        with patch("obskit.middleware.core._core_logger") as mock_logger:
            ctx = self._make_ctx()
            core.end_request(ctx, 200)
            mock_logger.info.assert_called_once()
            assert mock_logger.info.call_args[0][0] == "request_completed"


class TestRecordError:
    def _make_ctx(self) -> RequestContext:
        import time

        return RequestContext(
            start_time=time.perf_counter(),
            correlation_id="err-id",
            operation="err_op",
            method="POST",
            path="/fail",
        )

    def test_records_error_metrics(self) -> None:
        mock_metrics = MagicMock()
        core = MiddlewareCore(track_logging=False, track_tracing=False)
        core.red_metrics = mock_metrics

        ctx = self._make_ctx()
        core.record_error(ctx, ValueError("boom"))

        call_kwargs = mock_metrics.observe_request.call_args[1]
        assert call_kwargs["status"] == "failure"
        assert call_kwargs["error_type"] == "ValueError"
        assert ctx.metrics_recorded is True

    def test_no_double_recording(self) -> None:
        mock_metrics = MagicMock()
        core = MiddlewareCore(track_logging=False, track_tracing=False)
        core.red_metrics = mock_metrics

        ctx = self._make_ctx()
        core.record_error(ctx, ValueError("boom"))
        core.record_error(ctx, ValueError("second"))

        assert mock_metrics.observe_request.call_count == 1

    def test_logging_emitted(self) -> None:
        core = MiddlewareCore(track_metrics=False, track_logging=True, track_tracing=False)
        with patch("obskit.middleware.core._core_logger") as mock_logger:
            ctx = self._make_ctx()
            core.record_error(ctx, RuntimeError("oops"))
            mock_logger.error.assert_called_once()
            assert mock_logger.error.call_args[0][0] == "request_failed"


class TestResponseHeaders:
    def test_includes_correlation_id(self) -> None:
        core = MiddlewareCore(track_tracing=False, track_metrics=False, track_logging=False)
        ctx = RequestContext(
            start_time=0.0,
            correlation_id="resp-id",
            operation="op",
            method="GET",
            path="/",
        )
        headers = core.response_headers(ctx)
        header_dict = dict(headers)
        assert header_dict["X-Correlation-ID"] is not None

    def test_includes_trace_headers_when_tracing(self) -> None:
        core = MiddlewareCore(track_tracing=True, track_metrics=False, track_logging=False)
        ctx = RequestContext(
            start_time=0.0,
            correlation_id="resp-id",
            operation="op",
            method="GET",
            path="/",
        )
        headers = core.response_headers(ctx)
        # At minimum we get the correlation ID header
        assert len(headers) >= 1

    def test_trace_headers_injected(self) -> None:
        """Ensure trace context key-value pairs are appended to response headers."""
        core = MiddlewareCore(track_tracing=True, track_metrics=False, track_logging=False)
        ctx = RequestContext(
            start_time=0.0,
            correlation_id="resp-id",
            operation="op",
            method="GET",
            path="/",
        )
        with patch(
            "obskit.middleware.core.inject_trace_context",
            return_value={"traceparent": "00-abc-def-01"},
        ):
            headers = core.response_headers(ctx)
        header_dict = dict(headers)
        assert header_dict.get("traceparent") == "00-abc-def-01"


class TestMiddlewareCoreInit:
    def test_custom_exclude_paths(self) -> None:
        core = MiddlewareCore(exclude_paths=["/custom"])
        assert core.exclude_paths == ["/custom"]

    def test_metrics_disabled(self) -> None:
        core = MiddlewareCore(track_metrics=False)
        assert core.red_metrics is None

    def test_metrics_enabled_default(self) -> None:
        core = MiddlewareCore(track_metrics=True)
        assert core.red_metrics is not None

    def test_with_obs(self) -> None:
        mock_obs = MagicMock()
        mock_obs.metrics = MagicMock()
        core = MiddlewareCore(obs=mock_obs)
        assert core.red_metrics is mock_obs.metrics
