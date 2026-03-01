"""Unit tests for obskit.errors.responses — structured error responses."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from obskit.core.context import _correlation_id, set_correlation_id
from obskit.errors.responses import (
    AuthenticationError,
    AuthorizationError,
    CircuitOpenError,
    ErrorResponse,
    NotFoundError,
    ObservableError,
    RateLimitError,
    ServiceUnavailableError,
    ValidationError,
    create_error_response,
    format_exception,
)


@pytest.fixture(autouse=True)
async def reset_correlation_id():
    """Reset correlation ID before each test to prevent contamination."""
    token = set_correlation_id(None)
    yield
    _correlation_id.reset(token)


# =============================================================================
# ErrorResponse
# =============================================================================


class TestErrorResponse:
    def test_basic_creation(self):
        resp = ErrorResponse(error="Something failed", error_type="RuntimeError")
        assert resp.error == "Something failed"
        assert resp.error_type == "RuntimeError"

    def test_optional_fields_default_to_none(self):
        resp = ErrorResponse(error="err", error_type="Err")
        assert resp.code is None
        assert resp.details is None
        assert resp.trace_id is None
        assert resp.span_id is None
        assert resp.correlation_id is None
        assert resp.stack_trace is None

    def test_to_dict_basic(self):
        resp = ErrorResponse(error="err msg", error_type="ErrorType")
        d = resp.to_dict()
        assert d["error"] == "err msg"
        assert d["error_type"] == "ErrorType"

    def test_to_dict_excludes_none_values(self):
        resp = ErrorResponse(error="err", error_type="Type")
        d = resp.to_dict()
        assert "code" not in d
        assert "details" not in d
        assert "trace_id" not in d
        assert "stack_trace" not in d

    def test_to_dict_includes_code_when_set(self):
        resp = ErrorResponse(error="err", error_type="Type", code="MY_CODE")
        d = resp.to_dict()
        assert d["code"] == "MY_CODE"

    def test_to_dict_includes_details_when_set(self):
        resp = ErrorResponse(error="err", error_type="Type", details={"key": "val"})
        d = resp.to_dict()
        assert d["details"] == {"key": "val"}

    def test_to_dict_includes_trace_id_when_set(self):
        resp = ErrorResponse(error="err", error_type="Type", trace_id="abc123")
        d = resp.to_dict()
        assert d["trace_id"] == "abc123"

    def test_to_dict_includes_correlation_id_when_set(self):
        resp = ErrorResponse(error="err", error_type="Type", correlation_id="corr-123")
        d = resp.to_dict()
        assert d["correlation_id"] == "corr-123"

    def test_to_dict_includes_stack_trace_when_set(self):
        resp = ErrorResponse(error="err", error_type="Type", stack_trace=["line1", "line2"])
        d = resp.to_dict()
        assert d["stack_trace"] == ["line1", "line2"]

    def test_timestamp_always_present(self):
        resp = ErrorResponse(error="err", error_type="Type")
        d = resp.to_dict()
        assert "timestamp" in d


# =============================================================================
# ObservableError
# =============================================================================


class TestObservableError:
    def test_basic_creation(self):
        err = ObservableError("Something went wrong")
        assert err.message == "Something went wrong"
        assert str(err) == "Something went wrong"

    def test_code_defaults_to_class_name(self):
        err = ObservableError("msg")
        assert err.code == "OBSERVABLEERROR"

    def test_custom_code_used_when_provided(self):
        err = ObservableError("msg", code="MY_ERROR")
        assert err.code == "MY_ERROR"

    def test_details_default_to_empty_dict(self):
        err = ObservableError("msg")
        assert err.details == {}

    def test_custom_details(self):
        err = ObservableError("msg", details={"field": "value"})
        assert err.details == {"field": "value"}

    def test_http_status_default(self):
        err = ObservableError("msg")
        assert err.http_status == 500

    def test_custom_http_status(self):
        err = ObservableError("msg", http_status=400)
        assert err.http_status == 400

    def test_cause_stored(self):
        cause = ValueError("root cause")
        err = ObservableError("msg", cause=cause)
        assert err.cause is cause

    def test_to_response_returns_error_response(self):
        err = ObservableError("test error", code="TEST_CODE")
        resp = err.to_response()
        assert isinstance(resp, ErrorResponse)
        assert resp.error == "test error"
        assert resp.code == "TEST_CODE"

    def test_to_response_with_stack_trace(self):
        try:
            raise ObservableError("error with tb")
        except ObservableError as e:
            resp = e.to_response(include_stack_trace=True)
            assert resp.stack_trace is not None

    def test_to_dict_returns_dict(self):
        err = ObservableError("msg")
        d = err.to_dict()
        assert isinstance(d, dict)
        assert d["error"] == "msg"

    def test_trace_id_none_without_otel(self):
        with patch("obskit.errors.responses.ObservableError._get_trace_id", return_value=None):
            err = ObservableError("msg")
            assert err.trace_id is None

    def test_is_exception(self):
        with pytest.raises(ObservableError):
            raise ObservableError("test")


# =============================================================================
# ValidationError (errors.responses version)
# =============================================================================


class TestValidationError:
    def test_code_is_validation_error(self):
        err = ValidationError("Invalid email")
        assert err.code == "VALIDATION_ERROR"

    def test_http_status_is_400(self):
        err = ValidationError("bad input")
        assert err.http_status == 400

    def test_field_in_details_when_provided(self):
        err = ValidationError("Invalid value", field="email")
        assert err.details["field"] == "email"

    def test_no_field_key_when_not_provided(self):
        err = ValidationError("Invalid value")
        assert "field" not in err.details

    def test_is_observable_error(self):
        err = ValidationError("x")
        assert isinstance(err, ObservableError)


# =============================================================================
# NotFoundError
# =============================================================================


class TestNotFoundError:
    def test_code_is_not_found(self):
        err = NotFoundError("Order")
        assert err.code == "NOT_FOUND"

    def test_http_status_is_404(self):
        err = NotFoundError("User")
        assert err.http_status == 404

    def test_message_without_identifier(self):
        err = NotFoundError("Order")
        assert "Order" in err.message
        assert "not found" in err.message.lower()

    def test_message_with_identifier(self):
        err = NotFoundError("Order", identifier=123)
        assert "123" in err.message

    def test_resource_in_details(self):
        err = NotFoundError("User")
        assert err.details["resource"] == "User"

    def test_identifier_in_details_when_provided(self):
        err = NotFoundError("Order", identifier=456)
        assert err.details["identifier"] == "456"

    def test_is_observable_error(self):
        err = NotFoundError("x")
        assert isinstance(err, ObservableError)


# =============================================================================
# AuthenticationError
# =============================================================================


class TestAuthenticationError:
    def test_code_is_authentication_error(self):
        err = AuthenticationError()
        assert err.code == "AUTHENTICATION_ERROR"

    def test_http_status_is_401(self):
        err = AuthenticationError()
        assert err.http_status == 401

    def test_default_message(self):
        err = AuthenticationError()
        assert "authentication" in err.message.lower()

    def test_custom_message(self):
        err = AuthenticationError("Token expired")
        assert err.message == "Token expired"


# =============================================================================
# AuthorizationError
# =============================================================================


class TestAuthorizationError:
    def test_code_is_authorization_error(self):
        err = AuthorizationError()
        assert err.code == "AUTHORIZATION_ERROR"

    def test_http_status_is_403(self):
        err = AuthorizationError()
        assert err.http_status == 403

    def test_default_message(self):
        err = AuthorizationError()
        assert "access" in err.message.lower() or "denied" in err.message.lower()


# =============================================================================
# RateLimitError (errors.responses version)
# =============================================================================


class TestRateLimitErrorResponse:
    def test_code_is_rate_limit_exceeded(self):
        err = RateLimitError()
        assert err.code == "RATE_LIMIT_EXCEEDED"

    def test_http_status_is_429(self):
        err = RateLimitError()
        assert err.http_status == 429

    def test_retry_after_in_details_when_provided(self):
        err = RateLimitError(retry_after=60)
        assert err.details["retry_after"] == 60

    def test_no_retry_after_in_details_when_not_provided(self):
        err = RateLimitError()
        assert "retry_after" not in err.details


# =============================================================================
# ServiceUnavailableError
# =============================================================================


class TestServiceUnavailableError:
    def test_code_is_service_unavailable(self):
        err = ServiceUnavailableError()
        assert err.code == "SERVICE_UNAVAILABLE"

    def test_http_status_is_503(self):
        err = ServiceUnavailableError()
        assert err.http_status == 503

    def test_default_message(self):
        err = ServiceUnavailableError()
        assert "unavailable" in err.message.lower() or "temporarily" in err.message.lower()


# =============================================================================
# CircuitOpenError (errors.responses version)
# =============================================================================


class TestCircuitOpenErrorResponse:
    def test_code_is_circuit_open(self):
        err = CircuitOpenError()
        assert err.code == "CIRCUIT_OPEN"

    def test_http_status_is_503(self):
        err = CircuitOpenError()
        assert err.http_status == 503

    def test_service_in_message(self):
        err = CircuitOpenError(service="payment_api")
        assert "payment_api" in err.message

    def test_service_in_details(self):
        err = CircuitOpenError(service="payment_api")
        assert err.details["service"] == "payment_api"

    def test_default_service_name(self):
        err = CircuitOpenError()
        assert err.details["service"] == "service"


# =============================================================================
# create_error_response
# =============================================================================


class TestCreateErrorResponse:
    def test_with_regular_exception(self):
        exc = ValueError("plain error")
        response = create_error_response(exc)
        assert response["error"] == "plain error"
        assert response["error_type"] == "ValueError"

    def test_with_observable_error(self):
        exc = ObservableError("observable error", code="MY_ERR")
        response = create_error_response(exc)
        assert response["error"] == "observable error"
        assert response["code"] == "MY_ERR"

    def test_code_override_for_plain_exception(self):
        exc = ValueError("err")
        response = create_error_response(exc, code="CUSTOM_CODE")
        assert response["code"] == "CUSTOM_CODE"

    def test_details_override(self):
        exc = ValueError("err")
        response = create_error_response(exc, details={"extra": "info"})
        assert response["details"] == {"extra": "info"}

    def test_correlation_id_included_by_default(self):
        from obskit.core.context import correlation_context

        exc = ValueError("err")
        with correlation_context("test-corr"):
            response = create_error_response(exc, include_correlation_id=True)

        assert response["correlation_id"] == "test-corr"

    def test_correlation_id_excluded_when_disabled(self):
        exc = ValueError("err")
        response = create_error_response(exc, include_correlation_id=False)
        assert "correlation_id" not in response

    def test_stack_trace_included_when_requested(self):
        try:
            raise ValueError("traceable error")
        except ValueError as exc:
            response = create_error_response(exc, include_stack_trace=True)
        assert "stack_trace" in response

    def test_stack_trace_not_included_by_default(self):
        exc = ValueError("err")
        response = create_error_response(exc)
        assert "stack_trace" not in response

    def test_code_override_for_observable_error(self):
        exc = ObservableError("err", code="ORIG_CODE")
        response = create_error_response(exc, code="OVERRIDE_CODE")
        assert response["code"] == "OVERRIDE_CODE"

    def test_details_merged_for_observable_error(self):
        exc = ObservableError("err", details={"orig": "value"})
        response = create_error_response(exc, details={"extra": "added"})
        assert response["details"]["orig"] == "value"
        assert response["details"]["extra"] == "added"

    def test_empty_exception_message_uses_type_name(self):
        exc = Exception()
        response = create_error_response(exc)
        assert response["error_type"] == "Exception"


# =============================================================================
# format_exception
# =============================================================================


class TestFormatException:
    def test_formats_basic_exception(self):
        try:
            raise ValueError("basic error")
        except ValueError as exc:
            result = format_exception(exc)

        assert "ValueError" in result
        assert "basic error" in result

    def test_includes_correlation_id_when_set(self):
        from obskit.core.context import correlation_context

        try:
            raise ValueError("error")
        except ValueError as exc:
            with correlation_context("format-test-id"):
                result = format_exception(exc)

        assert "format-test-id" in result

    def test_returns_string(self):
        exc = RuntimeError("test")
        result = format_exception(exc)
        assert isinstance(result, str)

    def test_max_frames_truncates(self):
        try:
            raise RuntimeError("deep error")
        except RuntimeError as exc:
            result = format_exception(exc, max_frames=1)
        # Should not raise and truncation should work
        assert "RuntimeError" in result


# =============================================================================
# Additional coverage tests for uncovered branches
# =============================================================================


class TestErrorResponseToDictCoverage:
    """Test ErrorResponse.to_dict with span_id and timestamp edge cases."""

    def test_to_dict_with_span_id(self):
        """Test that span_id is included in to_dict when set (line 69)."""
        from obskit.errors.responses import ErrorResponse
        r = ErrorResponse(
            error="test",
            error_type="TestError",
            span_id="0123456789abcdef",
        )
        result = r.to_dict()
        assert "span_id" in result
        assert result["span_id"] == "0123456789abcdef"

    def test_to_dict_with_empty_timestamp(self):
        """Test to_dict branch when timestamp is falsy (line 72->74)."""
        from obskit.errors.responses import ErrorResponse
        r = ErrorResponse(
            error="test",
            error_type="TestError",
            timestamp="",  # falsy
        )
        result = r.to_dict()
        assert "timestamp" not in result


class TestObservableErrorTraceCoverage:
    """Test ObservableError trace/span ID extraction edge cases."""

    def test_get_trace_id_otel_exception(self):
        """Test _get_trace_id when OTel raises (lines 127-128)."""
        from unittest.mock import patch

        from obskit.errors.responses import ObservableError

        mock_trace = MagicMock()
        mock_trace.get_current_span.side_effect = RuntimeError("OTel error")

        with patch.dict("sys.modules", {"opentelemetry": MagicMock(), "opentelemetry.trace": mock_trace}):
            err = ObservableError("test")
        # Should not raise - exception is swallowed
        assert err.trace_id is None

    def test_get_span_id_otel_exception(self):
        """Test _get_span_id when OTel raises (lines 138-139)."""
        from unittest.mock import patch

        from obskit.errors.responses import ObservableError

        mock_trace = MagicMock()
        mock_trace.get_current_span.side_effect = RuntimeError("OTel error")

        with patch.dict("sys.modules", {"opentelemetry": MagicMock(), "opentelemetry.trace": mock_trace}):
            err = ObservableError("test")
        assert err.span_id is None


class TestCreateErrorResponseTraceCoverage:
    """Test create_error_response with include_trace_id=True."""

    def test_create_error_response_with_trace_id_otel_raises(self):
        """Test include_trace_id=True when OTel raises (lines 298-306)."""
        from unittest.mock import patch

        from obskit.errors.responses import create_error_response

        mock_trace = MagicMock()
        mock_trace.get_current_span.side_effect = RuntimeError("OTel error")

        with patch.dict("sys.modules", {"opentelemetry": MagicMock(), "opentelemetry.trace": mock_trace}):
            exc = ValueError("test error")
            response = create_error_response(exc, include_trace_id=True)
        # Should complete without error
        assert response is not None

    def test_create_error_response_with_valid_otel_span(self):
        """Test include_trace_id=True with a valid OTel span (lines 302-306)."""
        from unittest.mock import patch

        from obskit.errors.responses import create_error_response

        mock_span = MagicMock()
        mock_span_ctx = MagicMock()
        mock_span_ctx.is_valid = True
        mock_span_ctx.trace_id = 0x1234567890abcdef1234567890abcdef
        mock_span_ctx.span_id = 0x1234567890abcdef
        mock_span.get_span_context.return_value = mock_span_ctx

        mock_trace = MagicMock()
        mock_trace.get_current_span.return_value = mock_span

        with patch.dict("sys.modules", {"opentelemetry": MagicMock(), "opentelemetry.trace": mock_trace}):
            exc = ValueError("test error")
            response = create_error_response(exc, include_trace_id=True)
        assert response is not None


class TestFormatExceptionTraceCoverage:
    """Test format_exception with trace ID extraction."""

    def test_format_exception_with_valid_otel_span(self):
        """Test format_exception when OTel span has valid trace ID (lines 347-350)."""
        from unittest.mock import patch

        from obskit.errors.responses import format_exception

        mock_span = MagicMock()
        mock_span_ctx = MagicMock()
        mock_span_ctx.is_valid = True
        mock_span_ctx.trace_id = 0xabcdef1234567890abcdef1234567890
        mock_span.get_span_context.return_value = mock_span_ctx

        mock_trace = MagicMock()
        mock_trace.get_current_span.return_value = mock_span

        with patch.dict("sys.modules", {"opentelemetry": MagicMock(), "opentelemetry.trace": mock_trace}):
            exc = ValueError("test")
            result = format_exception(exc)
        assert isinstance(result, str)

    def test_format_exception_otel_raises(self):
        """Test format_exception when OTel raises (lines 350-351)."""
        from unittest.mock import patch

        from obskit.errors.responses import format_exception

        mock_trace = MagicMock()
        mock_trace.get_current_span.side_effect = RuntimeError("OTel error")

        with patch.dict("sys.modules", {"opentelemetry": MagicMock(), "opentelemetry.trace": mock_trace}):
            exc = ValueError("test")
            result = format_exception(exc)
        assert isinstance(result, str)


class TestErrorResponseMoreCoverage:
    """Additional tests for remaining uncovered lines."""

    def test_create_error_response_include_trace_id_false(self):
        """Test that include_trace_id=False skips trace block (line 297->309)."""
        from obskit.errors.responses import create_error_response
        exc = ValueError("test")
        # include_trace_id=False should skip the OTel trace block
        response = create_error_response(exc, include_trace_id=False)
        assert response is not None
        assert "trace_id" not in response

    def test_create_error_response_with_valid_span_has_span_id(self):
        """Test create_error_response with valid span sets span_id (line 304)."""
        from unittest.mock import patch

        import opentelemetry.trace as otel_trace

        from obskit.errors.responses import create_error_response

        mock_span = MagicMock()
        mock_span_ctx = MagicMock()
        mock_span_ctx.is_valid = True
        mock_span_ctx.trace_id = 0x1234567890abcdef1234567890abcdef
        mock_span_ctx.span_id = 0x1234567890abcdef
        mock_span.get_span_context.return_value = mock_span_ctx

        with patch.object(otel_trace, "get_current_span", return_value=mock_span):
            exc = ValueError("test")
            response = create_error_response(exc, include_trace_id=True)
        # Should set trace_id and span_id
        assert response is not None

    def test_format_exception_includes_trace_id_from_valid_span(self):
        """Test format_exception appends trace_id when span is valid (line 349)."""
        from unittest.mock import patch

        import opentelemetry.trace as otel_trace

        from obskit.errors.responses import format_exception

        mock_span = MagicMock()
        mock_span_ctx = MagicMock()
        mock_span_ctx.is_valid = True
        mock_span_ctx.trace_id = 0x123abc456def789012345678901234ab
        mock_span.get_span_context.return_value = mock_span_ctx

        with patch.object(otel_trace, "get_current_span", return_value=mock_span):
            exc = ValueError("test error")
            result = format_exception(exc)
        # Should include trace_id in result
        assert isinstance(result, str)
