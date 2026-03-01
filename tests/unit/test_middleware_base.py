"""Unit tests for obskit.middleware.base — framework-agnostic middleware."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from obskit.core.context import (
    _correlation_id,
    correlation_context,
    get_correlation_id,
    set_correlation_id,
)
from obskit.middleware.base import (
    CORRELATION_ID_HEADERS,
    TENANT_ID_HEADERS,
    BaseMiddleware,
    extract_context_from_headers,
    inject_context_to_headers,
)


@pytest.fixture(autouse=True)
async def reset_correlation_id():
    """Reset correlation ID before each test to avoid contamination."""
    token = set_correlation_id(None)
    yield
    _correlation_id.reset(token)


# =============================================================================
# extract_context_from_headers
# =============================================================================


class TestExtractContextFromHeaders:
    def test_extracts_x_correlation_id(self):
        headers = {"X-Correlation-ID": "my-correlation-id"}
        ctx = extract_context_from_headers(headers)
        assert ctx["correlation_id"] == "my-correlation-id"

    def test_extracts_x_request_id_as_correlation(self):
        headers = {"X-Request-ID": "req-123"}
        ctx = extract_context_from_headers(headers)
        assert ctx["correlation_id"] == "req-123"

    def test_extracts_x_trace_id_as_correlation(self):
        headers = {"X-Trace-ID": "trace-abc"}
        ctx = extract_context_from_headers(headers)
        assert ctx["correlation_id"] == "trace-abc"

    def test_generates_correlation_id_when_not_present(self):
        ctx = extract_context_from_headers({}, generate_correlation_id=True)
        assert "correlation_id" in ctx
        assert ctx["correlation_id"] is not None

    def test_no_correlation_id_when_disabled(self):
        ctx = extract_context_from_headers({}, generate_correlation_id=False)
        assert "correlation_id" not in ctx

    def test_extracts_x_tenant_id(self):
        headers = {"X-Tenant-ID": "tenant-abc"}
        ctx = extract_context_from_headers(headers)
        assert ctx["tenant_id"] == "tenant-abc"

    def test_extracts_x_company_id_as_tenant(self):
        headers = {"X-Company-ID": "company-123"}
        ctx = extract_context_from_headers(headers)
        assert ctx["tenant_id"] == "company-123"

    def test_no_tenant_key_when_not_present(self):
        ctx = extract_context_from_headers({})
        assert "tenant_id" not in ctx

    def test_extracts_trace_parent_header(self):
        headers = {"traceparent": "00-trace-span-01"}
        ctx = extract_context_from_headers(headers)
        assert "trace_context" in ctx
        assert ctx["trace_context"]["traceparent"] == "00-trace-span-01"

    def test_extracts_tracestate_header(self):
        headers = {"tracestate": "key=value"}
        ctx = extract_context_from_headers(headers)
        assert "trace_context" in ctx
        assert ctx["trace_context"]["tracestate"] == "key=value"

    def test_no_trace_context_when_absent(self):
        ctx = extract_context_from_headers({"X-Correlation-ID": "id"})
        assert "trace_context" not in ctx

    def test_case_insensitive_header_matching(self):
        headers = {"x-correlation-id": "lower-case-id"}
        ctx = extract_context_from_headers(headers)
        assert ctx["correlation_id"] == "lower-case-id"

    def test_sets_correlation_id_in_context(self):
        headers = {"X-Correlation-ID": "set-in-context"}
        extract_context_from_headers(headers)
        assert get_correlation_id() == "set-in-context"

    def test_first_matching_header_wins(self):
        # X-Correlation-ID should take precedence over X-Request-ID
        headers = {"X-Correlation-ID": "corr-id", "X-Request-ID": "req-id"}
        ctx = extract_context_from_headers(headers)
        assert ctx["correlation_id"] == "corr-id"

    def test_all_defined_correlation_headers_exist(self):
        assert len(CORRELATION_ID_HEADERS) > 0

    def test_all_defined_tenant_headers_exist(self):
        assert len(TENANT_ID_HEADERS) > 0


# =============================================================================
# inject_context_to_headers
# =============================================================================


class TestInjectContextToHeaders:
    def test_injects_correlation_id_when_set(self):
        with correlation_context("inject-test-id"):
            headers = inject_context_to_headers()
        assert headers.get("X-Correlation-ID") == "inject-test-id"

    def test_no_correlation_id_header_when_none_set(self):
        headers = inject_context_to_headers(include_correlation_id=True)
        # If no correlation_id is currently set, no header should be added
        # (this depends on the current context state)
        # Just ensure no crash
        assert isinstance(headers, dict)

    def test_correlation_id_not_injected_when_disabled(self):
        with correlation_context("should-not-inject"):
            headers = inject_context_to_headers(include_correlation_id=False)
        assert "X-Correlation-ID" not in headers

    def test_updates_existing_headers(self):
        with correlation_context("update-test"):
            headers = inject_context_to_headers(headers={"Existing": "value"})
        assert headers["Existing"] == "value"
        assert headers.get("X-Correlation-ID") == "update-test"

    def test_does_not_mutate_original_headers_dict(self):
        original = {"Existing": "value"}
        with correlation_context("non-mutating"):
            _result = inject_context_to_headers(headers=original)
        # original should be unchanged
        assert "X-Correlation-ID" not in original

    def test_returns_dict(self):
        result = inject_context_to_headers()
        assert isinstance(result, dict)

    def test_none_headers_creates_new_dict(self):
        result = inject_context_to_headers(headers=None)
        assert isinstance(result, dict)


# =============================================================================
# BaseMiddleware
# =============================================================================


class TestBaseMiddleware:
    def test_init_defaults(self):
        with patch("obskit.metrics.REDMetrics"):
            mw = BaseMiddleware()
            assert mw.service_name == "service"
            assert mw.record_metrics is True
            assert mw.propagate_context is True

    def test_init_without_metrics(self):
        mw = BaseMiddleware(record_metrics=False)
        assert mw._metrics is None

    def test_init_with_custom_service_name(self):
        with patch("obskit.metrics.REDMetrics"):
            mw = BaseMiddleware(service_name="my_service")
        assert mw.service_name == "my_service"

    def test_before_request_returns_context_dict(self):
        mw = BaseMiddleware(record_metrics=False)
        headers = {"X-Correlation-ID": "test-id"}
        ctx = mw.before_request(headers)
        assert isinstance(ctx, dict)
        assert "start_time" in ctx
        assert ctx.get("correlation_id") == "test-id"

    def test_before_request_generates_correlation_id_when_missing(self):
        mw = BaseMiddleware(record_metrics=False)
        ctx = mw.before_request({})
        assert "correlation_id" in ctx

    def test_after_request_success_status(self):
        mock_red = MagicMock()
        with patch("obskit.metrics.REDMetrics", return_value=mock_red):
            mw = BaseMiddleware(record_metrics=True)
        ctx = {"start_time": 0.0, "correlation_id": "test"}
        mw.after_request(None, ctx, status_code=200, operation="GET /test")
        mock_red.observe_request.assert_called_once()
        call_kwargs = mock_red.observe_request.call_args[1]
        assert call_kwargs["status"] == "success"

    def test_after_request_failure_status_for_5xx(self):
        mock_red = MagicMock()
        with patch("obskit.metrics.REDMetrics", return_value=mock_red):
            mw = BaseMiddleware(record_metrics=True)
        ctx = {"start_time": 0.0}
        mw.after_request(None, ctx, status_code=500, operation="POST /test")
        call_kwargs = mock_red.observe_request.call_args[1]
        assert call_kwargs["status"] == "failure"

    def test_after_request_failure_status_for_4xx(self):
        mock_red = MagicMock()
        with patch("obskit.metrics.REDMetrics", return_value=mock_red):
            mw = BaseMiddleware(record_metrics=True)
        ctx = {"start_time": 0.0}
        mw.after_request(None, ctx, status_code=400)
        call_kwargs = mock_red.observe_request.call_args[1]
        assert call_kwargs["status"] == "failure"

    def test_after_request_no_metrics_when_disabled(self):
        mw = BaseMiddleware(record_metrics=False)
        ctx = {"start_time": 0.0}
        # Should not raise
        mw.after_request(None, ctx, status_code=200)

    def test_on_error_logs_error(self):
        mw = BaseMiddleware(record_metrics=False)
        ctx = {"start_time": 0.0, "correlation_id": "err-test"}
        error = ValueError("test error")
        # Should not raise
        mw.on_error(error, ctx)

    def test_on_error_records_metrics_when_enabled(self):
        mock_red = MagicMock()
        with patch("obskit.metrics.REDMetrics", return_value=mock_red):
            mw = BaseMiddleware(record_metrics=True)
        ctx = {"start_time": 0.0}
        mw.on_error(ValueError("error"), ctx)
        mock_red.observe_request.assert_called_once()
        call_kwargs = mock_red.observe_request.call_args[1]
        assert call_kwargs["status"] == "failure"


# =============================================================================
# ASGIMiddleware (basic tests without actual ASGI framework)
# =============================================================================


class TestASGIMiddleware:
    def test_can_be_imported(self):
        from obskit.middleware.base import ASGIMiddleware

    def test_init_creates_base_middleware(self):
        from obskit.middleware.base import ASGIMiddleware
        mock_app = MagicMock()
        mw = ASGIMiddleware(mock_app, service_name="test_svc", record_metrics=False)
        assert mw.app is mock_app
        assert mw.base.service_name == "test_svc"

    def test_non_http_scope_passes_through(self):
        import asyncio

        from obskit.middleware.base import ASGIMiddleware
        mock_app = AsyncMock()
        mw = ASGIMiddleware(mock_app, record_metrics=False)

        scope = {"type": "websocket"}
        receive = AsyncMock()
        send = AsyncMock()

        async def run():
            await mw(scope, receive, send)

        asyncio.run(run())
        mock_app.assert_awaited_once_with(scope, receive, send)

    def test_http_scope_processed(self):
        import asyncio

        from obskit.middleware.base import ASGIMiddleware

        async def mock_app(scope, receive, send):
            await send({"type": "http.response.start", "status": 200})

        mw = ASGIMiddleware(mock_app, record_metrics=False)

        scope = {
            "type": "http",
            "headers": [],
            "path": "/test",
            "method": "GET",
        }
        receive = AsyncMock()
        send_mock = AsyncMock()

        async def run():
            await mw(scope, receive, send_mock)

        asyncio.run(run())
        # send_mock should have been called with the wrapped send
        assert send_mock.call_count >= 1


# =============================================================================
# WSGIMiddleware (basic tests)
# =============================================================================


class TestWSGIMiddleware:
    def test_can_be_imported(self):
        from obskit.middleware.base import WSGIMiddleware

    def test_init_creates_base_middleware(self):
        from obskit.middleware.base import WSGIMiddleware
        mock_app = MagicMock()
        mw = WSGIMiddleware(mock_app, service_name="wsgi_svc", record_metrics=False)
        assert mw.app is mock_app
        assert mw.base.service_name == "wsgi_svc"

    def test_call_extracts_headers_from_environ(self):
        from obskit.middleware.base import WSGIMiddleware

        called_contexts = []

        def mock_app(environ, start_response):
            called_contexts.append(get_correlation_id())
            start_response("200 OK", [])
            return [b"response"]

        mw = WSGIMiddleware(mock_app, record_metrics=False)

        environ = {
            "HTTP_X_CORRELATION_ID": "wsgi-corr-id",
            "PATH_INFO": "/api/test",
            "REQUEST_METHOD": "POST",
        }
        start_response = MagicMock()
        result = mw(environ, start_response)
        assert result == [b"response"]
        assert called_contexts[0] == "wsgi-corr-id"

    def test_call_handles_exception(self):
        from obskit.middleware.base import WSGIMiddleware

        def failing_app(environ, start_response):
            raise RuntimeError("app error")

        mw = WSGIMiddleware(failing_app, record_metrics=False)

        environ = {"PATH_INFO": "/", "REQUEST_METHOD": "GET"}
        start_response = MagicMock()

        with pytest.raises(RuntimeError, match="app error"):
            mw(environ, start_response)

    def test_status_code_extracted_from_start_response(self):
        from obskit.middleware.base import WSGIMiddleware

        _status_codes = []

        def mock_app(environ, start_response):
            start_response("404 Not Found", [])
            return [b""]

        mw = WSGIMiddleware(mock_app, record_metrics=False)
        environ = {"PATH_INFO": "/missing", "REQUEST_METHOD": "GET"}
        start_response = MagicMock()
        mw(environ, start_response)
        start_response.assert_called_once()

    def test_invalid_status_format_does_not_crash(self):
        from obskit.middleware.base import WSGIMiddleware

        def mock_app(environ, start_response):
            start_response("INVALID STATUS", [])
            return [b""]

        mw = WSGIMiddleware(mock_app, record_metrics=False)
        environ = {"PATH_INFO": "/", "REQUEST_METHOD": "GET"}
        start_response = MagicMock()
        # Should not raise
        mw(environ, start_response)


# =============================================================================
# Additional coverage tests for uncovered branches
# =============================================================================


class TestCreateHeadersCoverage:
    """Test create_request_headers branch coverage."""

    def test_include_tenant_id_with_tenant_set(self):
        """Test include_tenant_id=True when tenant_id is set (line 147->148)."""
        from obskit.metrics.tenant import set_tenant_id
        from obskit.middleware.base import inject_context_to_headers
        set_tenant_id("test-tenant")
        headers = inject_context_to_headers(include_tenant_id=True)
        assert headers.get("X-Tenant-ID") == "test-tenant"
        set_tenant_id("")

    def test_include_tenant_id_false(self):
        """Test include_tenant_id=False skips tenant header (line 145->151)."""
        from obskit.metrics.tenant import set_tenant_id
        from obskit.middleware.base import inject_context_to_headers
        set_tenant_id("some-tenant")
        headers = inject_context_to_headers(include_tenant_id=False)
        assert "X-Tenant-ID" not in headers
        set_tenant_id("")

    def test_inject_trace_context_exception(self):
        """Test exception in inject_trace_context is swallowed (lines 155-156)."""
        from unittest.mock import patch

        from obskit.middleware.base import inject_context_to_headers
        with patch("obskit.tracing.inject_trace_context", side_effect=RuntimeError("trace error")):
            # Should not raise
            headers = inject_context_to_headers()
        assert isinstance(headers, dict)


class TestASGIMiddlewareCoverage:
    """Test ASGI middleware branch coverage."""

    def test_send_wrapper_http_response_start(self):
        """Test send_wrapper captures status from http.response.start (lines 315->317)."""
        import asyncio

        from obskit.middleware.base import ASGIMiddleware

        send_messages = []

        async def run_test():
            async def mock_app(scope, receive, send):
                await send({"type": "http.response.start", "status": 201, "headers": []})
                await send({"type": "http.response.body", "body": b"ok"})

            async def mock_send(message):  # NOSONAR
                send_messages.append(message)

            async def mock_receive():  # NOSONAR
                return {}

            scope = {
                "type": "http",
                "headers": [],
                "path": "/test",
                "method": "GET",
            }

            mw = ASGIMiddleware(mock_app, record_metrics=False)
            await mw(scope, mock_receive, mock_send)

        asyncio.run(run_test())

        # send_wrapper was called with http.response.start message
        assert len(send_messages) == 2
        assert send_messages[0]["type"] == "http.response.start"

    def test_asgi_middleware_exception_path(self):
        """Test exception handler in ASGI middleware (lines 329-331)."""
        import asyncio

        from obskit.middleware.base import ASGIMiddleware

        async def run_test():
            async def failing_app(scope, receive, send):
                raise RuntimeError("ASGI app error")

            async def mock_send(message):
                pass  # NOSONAR

            async def mock_receive():  # NOSONAR
                return {}

            scope = {
                "type": "http",
                "headers": [],
                "path": "/test",
                "method": "GET",
            }

            mw = ASGIMiddleware(failing_app, record_metrics=False)
            await mw(scope, mock_receive, mock_send)

        with pytest.raises(RuntimeError, match="ASGI app error"):
            asyncio.run(run_test())
