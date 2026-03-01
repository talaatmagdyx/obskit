"""
Tests for obskit gRPC middleware interceptors — intercept_service, _intercept_call,
and _inject_metadata with trace propagation.

Covers the missing lines:
- intercept_service (server interceptor async method) — lines 176-228
- _intercept_call (client interceptor) — lines 357-412
- _inject_metadata with trace propagation — lines 302-308
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from obskit.middleware.grpc import (
    GRPC_AVAILABLE,
    _extract_method_name,
    _grpc_status_to_status,
)

pytestmark = pytest.mark.skipif(not GRPC_AVAILABLE, reason="gRPC not installed")


# =============================================================================
# _grpc_status_to_status Tests
# =============================================================================


class TestGrpcStatusToStatus:
    def test_ok_returns_success(self):
        import grpc

        result = _grpc_status_to_status(grpc.StatusCode.OK)
        assert result == "success"

    def test_non_ok_returns_failure(self):
        import grpc

        result = _grpc_status_to_status(grpc.StatusCode.NOT_FOUND)
        assert result == "failure"

    def test_internal_error_returns_failure(self):
        import grpc

        result = _grpc_status_to_status(grpc.StatusCode.INTERNAL)
        assert result == "failure"


# =============================================================================
# ObskitServerInterceptor.intercept_service Tests
# =============================================================================


class TestObskitServerInterceptorInterceptService:
    def _make_interceptor(self, **kwargs):
        from obskit.middleware.grpc import ObskitServerInterceptor

        return ObskitServerInterceptor(**kwargs)

    def _make_call_details(self, method="/package.Service/Method", metadata=None):
        details = MagicMock()
        details.method = method
        details.invocation_metadata = metadata or []
        return details

    @pytest.mark.asyncio
    async def test_intercept_service_success(self):
        interceptor = self._make_interceptor(track_metrics=False, track_logging=False, track_tracing=False)
        details = self._make_call_details()

        mock_response = MagicMock()
        continuation = AsyncMock(return_value=mock_response)

        result = await interceptor.intercept_service(continuation, details)
        assert result is mock_response
        continuation.assert_called_once_with(details)

    @pytest.mark.asyncio
    async def test_intercept_service_excluded_method(self):
        interceptor = self._make_interceptor(
            excluded_methods=["grpc.health.v1.Health/Check"],
            track_metrics=False,
        )
        details = self._make_call_details(method="grpc.health.v1.Health/Check")
        mock_response = MagicMock()
        continuation = AsyncMock(return_value=mock_response)

        result = await interceptor.intercept_service(continuation, details)
        assert result is mock_response

    @pytest.mark.asyncio
    async def test_intercept_service_with_metrics(self):
        interceptor = self._make_interceptor(track_metrics=True, track_logging=False)
        mock_metrics = MagicMock()
        interceptor.red_metrics = mock_metrics
        details = self._make_call_details()
        continuation = AsyncMock(return_value=MagicMock())

        await interceptor.intercept_service(continuation, details)
        mock_metrics.observe_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_intercept_service_with_logging(self):
        interceptor = self._make_interceptor(track_metrics=False, track_logging=True)
        details = self._make_call_details()
        continuation = AsyncMock(return_value=MagicMock())

        with patch("obskit.middleware.grpc.logger") as mock_logger:
            await interceptor.intercept_service(continuation, details)
            # Should have logged request start (debug) and completion (info)
            assert mock_logger.debug.called or mock_logger.info.called

    @pytest.mark.asyncio
    async def test_intercept_service_with_correlation_id(self):
        interceptor = self._make_interceptor(track_metrics=False, track_logging=False)
        metadata = [("x-correlation-id", "corr-123")]
        details = self._make_call_details(metadata=metadata)
        continuation = AsyncMock(return_value=MagicMock())

        with patch("obskit.middleware.grpc.set_correlation_id") as mock_set_id:
            await interceptor.intercept_service(continuation, details)
            mock_set_id.assert_called_once_with("corr-123")

    @pytest.mark.asyncio
    async def test_intercept_service_no_correlation_id(self):
        interceptor = self._make_interceptor(track_metrics=False, track_logging=False)
        details = self._make_call_details(metadata=[])
        continuation = AsyncMock(return_value=MagicMock())

        with patch("obskit.middleware.grpc.set_correlation_id") as mock_set_id:
            await interceptor.intercept_service(continuation, details)
            mock_set_id.assert_not_called()

    @pytest.mark.asyncio
    async def test_intercept_service_grpc_rpc_error(self):
        import grpc

        interceptor = self._make_interceptor(track_metrics=False, track_logging=False)
        details = self._make_call_details()

        # Create a concrete subclass of grpc.RpcError to use as exception
        class ConcreteRpcError(grpc.RpcError):
            def code(self):
                return grpc.StatusCode.INTERNAL
            def details(self):
                return "internal error"

        continuation = AsyncMock(side_effect=ConcreteRpcError())

        with pytest.raises(grpc.RpcError):
            await interceptor.intercept_service(continuation, details)

    @pytest.mark.asyncio
    async def test_intercept_service_generic_exception(self):
        interceptor = self._make_interceptor(track_metrics=False, track_logging=False)
        details = self._make_call_details()
        continuation = AsyncMock(side_effect=RuntimeError("handler crashed"))

        with pytest.raises(RuntimeError):
            await interceptor.intercept_service(continuation, details)

    @pytest.mark.asyncio
    async def test_intercept_service_records_failure_metrics(self):
        interceptor = self._make_interceptor(track_metrics=True, track_logging=False)
        mock_metrics = MagicMock()
        interceptor.red_metrics = mock_metrics
        details = self._make_call_details()
        continuation = AsyncMock(side_effect=ValueError("error"))

        with pytest.raises(ValueError):
            await interceptor.intercept_service(continuation, details)

        call_kwargs = mock_metrics.observe_request.call_args.kwargs
        assert call_kwargs["status"] == "failure"
        assert call_kwargs["error_type"] == "ValueError"

    @pytest.mark.asyncio
    async def test_intercept_service_logs_warning_on_failure(self):
        interceptor = self._make_interceptor(track_metrics=False, track_logging=True)
        details = self._make_call_details()
        continuation = AsyncMock(side_effect=RuntimeError("failure"))

        with patch("obskit.middleware.grpc.logger") as mock_logger:
            with pytest.raises(RuntimeError):
                await interceptor.intercept_service(continuation, details)
            mock_logger.warning.assert_called()

    @pytest.mark.asyncio
    async def test_intercept_service_logs_info_on_success(self):
        interceptor = self._make_interceptor(track_metrics=False, track_logging=True)
        details = self._make_call_details()
        continuation = AsyncMock(return_value=MagicMock())

        with patch("obskit.middleware.grpc.logger") as mock_logger:
            await interceptor.intercept_service(continuation, details)
            mock_logger.info.assert_called()


# =============================================================================
# ObskitClientInterceptor._intercept_call Tests
# =============================================================================


class TestObskitClientInterceptorInterceptCall:
    def _make_interceptor(self, **kwargs):
        from obskit.middleware.grpc import ObskitClientInterceptor

        return ObskitClientInterceptor(**kwargs)

    def _make_client_call_details(self, method="/package.Service/Method"):
        details = MagicMock()
        details.method = method
        details.metadata = None
        details.timeout = None
        details.credentials = None
        details.wait_for_ready = None
        return details

    @pytest.mark.asyncio
    async def test_intercept_call_success(self):
        interceptor = self._make_interceptor(
            track_metrics=False, track_logging=False, propagate_trace=False, propagate_correlation_id=False
        )
        details = self._make_client_call_details()
        mock_response = MagicMock()
        continuation = AsyncMock(return_value=mock_response)

        result = await interceptor._intercept_call(continuation, details, request=MagicMock())
        assert result is mock_response

    @pytest.mark.asyncio
    async def test_intercept_call_with_metrics(self):
        interceptor = self._make_interceptor(
            track_metrics=True, track_logging=False, propagate_trace=False, propagate_correlation_id=False
        )
        mock_metrics = MagicMock()
        interceptor.red_metrics = mock_metrics
        details = self._make_client_call_details()
        continuation = AsyncMock(return_value=MagicMock())

        await interceptor._intercept_call(continuation, details, MagicMock())
        mock_metrics.observe_request.assert_called_once()
        call_kwargs = mock_metrics.observe_request.call_args.kwargs
        assert call_kwargs["operation"].startswith("client.")

    @pytest.mark.asyncio
    async def test_intercept_call_with_logging(self):
        interceptor = self._make_interceptor(
            track_metrics=False, track_logging=True, propagate_trace=False, propagate_correlation_id=False
        )
        details = self._make_client_call_details()
        continuation = AsyncMock(return_value=MagicMock())

        with patch("obskit.middleware.grpc.logger") as mock_logger:
            await interceptor._intercept_call(continuation, details, MagicMock())
            assert mock_logger.debug.called or mock_logger.info.called

    @pytest.mark.asyncio
    async def test_intercept_call_grpc_rpc_error(self):
        import grpc

        interceptor = self._make_interceptor(
            track_metrics=False, track_logging=False, propagate_trace=False, propagate_correlation_id=False
        )
        details = self._make_client_call_details()

        # Create a concrete subclass of grpc.RpcError to use as exception
        class ConcreteRpcError(grpc.RpcError):
            def code(self):
                return grpc.StatusCode.UNAVAILABLE
            def details(self):
                return "unavailable"

        continuation = AsyncMock(side_effect=ConcreteRpcError())

        with pytest.raises(grpc.RpcError):
            await interceptor._intercept_call(continuation, details, MagicMock())

    @pytest.mark.asyncio
    async def test_intercept_call_generic_exception(self):
        interceptor = self._make_interceptor(
            track_metrics=False, track_logging=False, propagate_trace=False, propagate_correlation_id=False
        )
        details = self._make_client_call_details()
        continuation = AsyncMock(side_effect=ConnectionError("network error"))

        with pytest.raises(ConnectionError):
            await interceptor._intercept_call(continuation, details, MagicMock())

    @pytest.mark.asyncio
    async def test_intercept_call_failure_records_metrics(self):
        interceptor = self._make_interceptor(
            track_metrics=True, track_logging=False, propagate_trace=False, propagate_correlation_id=False
        )
        mock_metrics = MagicMock()
        interceptor.red_metrics = mock_metrics
        details = self._make_client_call_details()
        continuation = AsyncMock(side_effect=OSError("disk error"))

        with pytest.raises(IOError):
            await interceptor._intercept_call(continuation, details, MagicMock())

        call_kwargs = mock_metrics.observe_request.call_args.kwargs
        assert call_kwargs["status"] == "failure"
        # In Python 3, IOError is an alias for OSError, so type(e).__name__ == "OSError"
        assert call_kwargs["error_type"] in ("IOError", "OSError")

    @pytest.mark.asyncio
    async def test_intercept_call_logs_warning_on_failure(self):
        interceptor = self._make_interceptor(
            track_metrics=False, track_logging=True, propagate_trace=False, propagate_correlation_id=False
        )
        details = self._make_client_call_details()
        continuation = AsyncMock(side_effect=ValueError("test failure"))

        with patch("obskit.middleware.grpc.logger") as mock_logger:
            with pytest.raises(ValueError):
                await interceptor._intercept_call(continuation, details, MagicMock())
            mock_logger.warning.assert_called()

    @pytest.mark.asyncio
    async def test_intercept_unary_unary(self):
        from obskit.middleware.grpc import ObskitClientInterceptor

        interceptor = ObskitClientInterceptor(
            track_metrics=False, track_logging=False, propagate_trace=False, propagate_correlation_id=False
        )
        details = self._make_client_call_details()
        continuation = AsyncMock(return_value=MagicMock())
        result = await interceptor.intercept_unary_unary(continuation, details, MagicMock())
        assert result is not None

    @pytest.mark.asyncio
    async def test_intercept_unary_stream(self):
        from obskit.middleware.grpc import ObskitClientInterceptor

        interceptor = ObskitClientInterceptor(
            track_metrics=False, track_logging=False, propagate_trace=False, propagate_correlation_id=False
        )
        details = self._make_client_call_details()
        continuation = AsyncMock(return_value=MagicMock())
        result = await interceptor.intercept_unary_stream(continuation, details, MagicMock())
        assert result is not None

    @pytest.mark.asyncio
    async def test_intercept_stream_unary(self):
        from obskit.middleware.grpc import ObskitClientInterceptor

        interceptor = ObskitClientInterceptor(
            track_metrics=False, track_logging=False, propagate_trace=False, propagate_correlation_id=False
        )
        details = self._make_client_call_details()
        continuation = AsyncMock(return_value=MagicMock())
        result = await interceptor.intercept_stream_unary(continuation, details, MagicMock())
        assert result is not None

    @pytest.mark.asyncio
    async def test_intercept_stream_stream(self):
        from obskit.middleware.grpc import ObskitClientInterceptor

        interceptor = ObskitClientInterceptor(
            track_metrics=False, track_logging=False, propagate_trace=False, propagate_correlation_id=False
        )
        details = self._make_client_call_details()
        continuation = AsyncMock(return_value=MagicMock())
        result = await interceptor.intercept_stream_stream(continuation, details, MagicMock())
        assert result is not None

    @pytest.mark.asyncio
    async def test_intercept_call_injects_metadata(self):
        interceptor = self._make_interceptor(
            track_metrics=False, track_logging=False, propagate_trace=False, propagate_correlation_id=True
        )
        details = self._make_client_call_details()
        details.metadata = [("existing-key", "existing-value")]
        captured_details = []

        async def capture_continuation(new_details, request):  # NOSONAR
            captured_details.append(new_details)
            return MagicMock()

        with patch("obskit.middleware.grpc.get_correlation_id", return_value="injected-id"):
            await interceptor._intercept_call(capture_continuation, details, MagicMock())

        assert len(captured_details) == 1
        new_meta = captured_details[0].metadata
        meta_dict = {k: v for k, v in new_meta}
        assert "existing-key" in meta_dict
        assert "x-correlation-id" in meta_dict
        assert meta_dict["x-correlation-id"] == "injected-id"


# =============================================================================
# _inject_metadata with trace propagation Tests
# =============================================================================


class TestInjectMetadataTracePropagation:
    def _make_interceptor(self, **kwargs):
        from obskit.middleware.grpc import ObskitClientInterceptor

        return ObskitClientInterceptor(**kwargs)

    def test_inject_metadata_with_trace(self):
        interceptor = self._make_interceptor(
            track_metrics=False, propagate_trace=True, propagate_correlation_id=False
        )
        headers = {"traceparent": "00-abc123-def456-01", "tracestate": "vendor=value"}
        with patch("obskit.tracing.tracer.inject_trace_context", lambda h: h.update(headers)):
            result = interceptor._inject_metadata(None)
        # traceparent and tracestate should be injected (lowercase)
        keys = [k for k, v in result]
        assert "traceparent" in keys
        assert "tracestate" in keys

    def test_inject_metadata_trace_exception_silenced(self):
        interceptor = self._make_interceptor(
            track_metrics=False, propagate_trace=True, propagate_correlation_id=False
        )
        with patch(
            "obskit.middleware.grpc.inject_trace_context",
            side_effect=Exception("tracer not available"),
            create=True,
        ):
            # Should not raise
            result = interceptor._inject_metadata(None)
        assert isinstance(result, list)

    def test_inject_metadata_with_existing_and_trace(self):
        interceptor = self._make_interceptor(
            track_metrics=False, propagate_trace=True, propagate_correlation_id=True
        )
        existing = [("custom-header", "value123")]
        headers = {"traceparent": "00-trace-span-01"}
        with patch("obskit.middleware.grpc.get_correlation_id", return_value="corr-id"):
            with patch("obskit.tracing.tracer.inject_trace_context", lambda h: h.update(headers)):
                result = interceptor._inject_metadata(existing)
        keys = [k for k, v in result]
        assert "custom-header" in keys
        assert "x-correlation-id" in keys
        assert "traceparent" in keys

    def test_inject_metadata_no_correlation_id_when_none(self):
        interceptor = self._make_interceptor(
            track_metrics=False, propagate_trace=False, propagate_correlation_id=True
        )
        with patch("obskit.middleware.grpc.get_correlation_id", return_value=None):
            result = interceptor._inject_metadata(None)
        keys = [k for k, v in result]
        assert "x-correlation-id" not in keys

    def test_inject_metadata_disabled_correlation_propagation(self):
        interceptor = self._make_interceptor(
            track_metrics=False, propagate_trace=False, propagate_correlation_id=False
        )
        result = interceptor._inject_metadata(None)
        assert result == []

    def test_inject_metadata_existing_metadata_preserved(self):
        interceptor = self._make_interceptor(
            track_metrics=False, propagate_trace=False, propagate_correlation_id=False
        )
        existing = [("key1", "val1"), ("key2", "val2")]
        result = interceptor._inject_metadata(existing)
        assert ("key1", "val1") in result
        assert ("key2", "val2") in result
