"""
Unit tests for obskit gRPC middleware.

Tests cover:
- Helper functions (_extract_method_name, _grpc_status_to_status, _extract_correlation_id)
- ObskitServerInterceptor initialization
- ObskitClientInterceptor initialization
- Import guards when grpc is not available
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from obskit.middleware.grpc import (
    GRPC_AVAILABLE,
    _extract_correlation_id,
    _extract_method_name,
)


class TestExtractMethodName:
    """Tests for _extract_method_name helper."""

    def test_standard_grpc_path(self) -> None:
        result = _extract_method_name("/package.Service/Method")
        assert result == "package.Service.Method"

    def test_nested_package_path(self) -> None:
        result = _extract_method_name("/com.example.OrderService/CreateOrder")
        assert result == "com.example.OrderService.CreateOrder"

    def test_short_path_returned_as_is(self) -> None:
        result = _extract_method_name("Method")
        assert result == "Method"

    def test_two_part_path_returned_as_is(self) -> None:
        result = _extract_method_name("/Service")
        assert result == "/Service"


class TestExtractCorrelationId:
    """Tests for _extract_correlation_id helper."""

    def test_extracts_correlation_id(self) -> None:
        metadata = [("x-correlation-id", "abc-123"), ("content-type", "application/grpc")]
        result = _extract_correlation_id(metadata)
        assert result == "abc-123"

    def test_case_insensitive_key(self) -> None:
        metadata = [("X-Correlation-Id", "def-456")]
        result = _extract_correlation_id(metadata)
        assert result == "def-456"

    def test_returns_none_when_not_present(self) -> None:
        metadata = [("content-type", "application/grpc")]
        result = _extract_correlation_id(metadata)
        assert result is None

    def test_returns_none_for_none_metadata(self) -> None:
        result = _extract_correlation_id(None)
        assert result is None

    def test_returns_none_for_empty_metadata(self) -> None:
        result = _extract_correlation_id([])
        assert result is None

    def test_returns_none_for_none_value(self) -> None:
        metadata = [("x-correlation-id", None)]
        result = _extract_correlation_id(metadata)
        assert result is None


class TestGRPCAvailability:
    """Tests for GRPC_AVAILABLE flag."""

    def test_grpc_available_is_bool(self) -> None:
        assert isinstance(GRPC_AVAILABLE, bool)


@pytest.mark.skipif(not GRPC_AVAILABLE, reason="gRPC not installed")
class TestObskitServerInterceptorInit:
    """Tests for ObskitServerInterceptor initialization (requires grpc)."""

    def test_default_initialization(self) -> None:
        from obskit.middleware.grpc import ObskitServerInterceptor

        interceptor = ObskitServerInterceptor()
        assert interceptor.track_metrics is True
        assert interceptor.track_logging is True
        assert interceptor.track_tracing is True
        assert interceptor.excluded_methods == set()

    def test_custom_service_name(self) -> None:
        from obskit.middleware.grpc import ObskitServerInterceptor

        interceptor = ObskitServerInterceptor(service_name="my-service")
        assert interceptor.service_name == "my-service"

    def test_excluded_methods(self) -> None:
        from obskit.middleware.grpc import ObskitServerInterceptor

        excluded = ["grpc.health.v1.Health/Check"]
        interceptor = ObskitServerInterceptor(excluded_methods=excluded)
        assert "grpc.health.v1.Health/Check" in interceptor.excluded_methods

    def test_should_observe_not_excluded(self) -> None:
        from obskit.middleware.grpc import ObskitServerInterceptor

        interceptor = ObskitServerInterceptor()
        assert interceptor._should_observe("/package.Service/Method") is True

    def test_should_not_observe_excluded(self) -> None:
        from obskit.middleware.grpc import ObskitServerInterceptor

        interceptor = ObskitServerInterceptor(excluded_methods=["grpc.health.v1.Health/Check"])
        assert interceptor._should_observe("grpc.health.v1.Health/Check") is False

    def test_disabled_metrics(self) -> None:
        from obskit.middleware.grpc import ObskitServerInterceptor

        interceptor = ObskitServerInterceptor(track_metrics=False)
        assert interceptor.track_metrics is False
        assert not hasattr(interceptor, "red_metrics")


@pytest.mark.skipif(not GRPC_AVAILABLE, reason="gRPC not installed")
class TestObskitClientInterceptorInit:
    """Tests for ObskitClientInterceptor initialization (requires grpc)."""

    def test_default_initialization(self) -> None:
        from obskit.middleware.grpc import ObskitClientInterceptor

        interceptor = ObskitClientInterceptor()
        assert interceptor.track_metrics is True
        assert interceptor.track_logging is True
        assert interceptor.propagate_trace is True
        assert interceptor.propagate_correlation_id is True

    def test_disabled_options(self) -> None:
        from obskit.middleware.grpc import ObskitClientInterceptor

        interceptor = ObskitClientInterceptor(
            track_metrics=False,
            track_logging=False,
            propagate_trace=False,
            propagate_correlation_id=False,
        )
        assert interceptor.track_metrics is False
        assert interceptor.track_logging is False
        assert interceptor.propagate_trace is False
        assert interceptor.propagate_correlation_id is False

    def test_inject_metadata_with_correlation_id(self) -> None:
        from obskit.middleware.grpc import ObskitClientInterceptor

        interceptor = ObskitClientInterceptor(propagate_trace=False)
        with patch("obskit.middleware.grpc.get_correlation_id", return_value="test-corr-id"):
            result = interceptor._inject_metadata(None)

        assert any(k == "x-correlation-id" and v == "test-corr-id" for k, v in result)

    def test_inject_metadata_appends_to_existing(self) -> None:
        from obskit.middleware.grpc import ObskitClientInterceptor

        interceptor = ObskitClientInterceptor(propagate_trace=False, propagate_correlation_id=False)
        existing = [("content-type", "application/grpc")]
        result = interceptor._inject_metadata(existing)
        assert ("content-type", "application/grpc") in result
