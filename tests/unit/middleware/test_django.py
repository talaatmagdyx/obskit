"""Tests for obskit.middleware.django module."""

from unittest.mock import MagicMock, patch

import pytest

# Check if Django is available
try:
    import django  # noqa: F401
    from django.conf import settings as django_settings

    if not django_settings.configured:
        django_settings.configure(
            DEBUG=True,
            DATABASES={},
            INSTALLED_APPS=[],
            ROOT_URLCONF=[],
            MIDDLEWARE=[],
            OBSKIT={},
        )
    DJANGO_AVAILABLE = True
except ImportError:
    DJANGO_AVAILABLE = False
    django_settings = None  # type: ignore[assignment]


@pytest.mark.skipif(not DJANGO_AVAILABLE, reason="Django not installed")
class TestObskitDjangoMiddleware:
    """Tests for ObskitDjangoMiddleware class."""

    @patch("obskit.middleware.django.DJANGO_AVAILABLE", True)
    @patch("obskit.middleware.django.settings")
    @patch("obskit.middleware.django.get_red_metrics")
    def test_init(self, mock_get_red_metrics, mock_settings):
        """Test middleware initialization."""
        from obskit.middleware.django import ObskitDjangoMiddleware

        mock_settings.OBSKIT = {}
        mock_get_response = MagicMock()
        mock_red = MagicMock()
        mock_get_red_metrics.return_value = mock_red

        middleware = ObskitDjangoMiddleware(mock_get_response)

        assert middleware.get_response == mock_get_response
        assert middleware.track_metrics is True
        assert middleware.track_logging is True
        assert middleware.track_tracing is True

    @patch("obskit.middleware.django.DJANGO_AVAILABLE", True)
    @patch("obskit.middleware.django.settings")
    @patch("obskit.middleware.django.get_red_metrics")
    def test_init_with_custom_settings(self, mock_get_red_metrics, mock_settings):
        """Test initialization with custom settings."""
        from obskit.middleware.django import ObskitDjangoMiddleware

        mock_settings.OBSKIT = {
            "exclude_paths": ["/api/health/"],
            "track_metrics": False,
            "track_logging": False,
            "track_tracing": False,
        }
        mock_get_response = MagicMock()

        middleware = ObskitDjangoMiddleware(mock_get_response)

        assert middleware.exclude_paths == ["/api/health/"]
        assert middleware.track_metrics is False
        assert middleware.track_logging is False
        assert middleware.track_tracing is False

    @patch("obskit.middleware.django.DJANGO_AVAILABLE", True)
    @patch("obskit.middleware.django.settings")
    @patch("obskit.middleware.django.get_red_metrics")
    def test_should_exclude(self, mock_get_red_metrics, mock_settings):
        """Test path exclusion logic."""
        from obskit.middleware.django import ObskitDjangoMiddleware

        mock_settings.OBSKIT = {"exclude_paths": ["/health/", "/metrics/"]}
        mock_get_response = MagicMock()

        middleware = ObskitDjangoMiddleware(mock_get_response)

        assert middleware._should_exclude("/health/") is True
        assert middleware._should_exclude("/metrics/") is True
        assert middleware._should_exclude("/api/orders") is False

    @patch("obskit.middleware.django.DJANGO_AVAILABLE", True)
    @patch("obskit.middleware.django.settings")
    @patch("obskit.middleware.django.get_red_metrics")
    @patch("obskit.middleware.django.set_correlation_id")
    def test_call_sets_correlation_id(self, mock_set_corr_id, mock_get_red_metrics, mock_settings):
        """Test that calling middleware sets correlation ID."""
        from obskit.middleware.django import ObskitDjangoMiddleware

        mock_settings.OBSKIT = {}
        mock_get_response = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get_response.return_value = mock_response

        mock_request = MagicMock()
        mock_request.path = "/api/orders"
        mock_request.method = "GET"
        mock_request.headers = {}
        mock_request.META = {}
        mock_request.user.is_authenticated = False

        middleware = ObskitDjangoMiddleware(mock_get_response)
        middleware(mock_request)

        mock_set_corr_id.assert_called_once()

    @patch("obskit.middleware.django.DJANGO_AVAILABLE", True)
    @patch("obskit.middleware.django.settings")
    @patch("obskit.middleware.django.get_red_metrics")
    def test_call_excluded_path(self, mock_get_red_metrics, mock_settings):
        """Test that excluded paths are skipped."""
        from obskit.middleware.django import ObskitDjangoMiddleware

        mock_settings.OBSKIT = {"exclude_paths": ["/health/"]}
        mock_get_response = MagicMock()
        mock_response = MagicMock()
        mock_get_response.return_value = mock_response

        mock_request = MagicMock()
        mock_request.path = "/health/"

        middleware = ObskitDjangoMiddleware(mock_get_response)
        result = middleware(mock_request)

        assert result == mock_response
        mock_get_response.assert_called_once_with(mock_request)

    @patch("obskit.middleware.django.DJANGO_AVAILABLE", True)
    @patch("obskit.middleware.django.settings")
    @patch("obskit.middleware.django.get_red_metrics")
    def test_call_records_metrics(self, mock_get_red_metrics, mock_settings):
        """Test that metrics are recorded."""
        from obskit.middleware.django import ObskitDjangoMiddleware

        mock_settings.OBSKIT = {}
        mock_red = MagicMock()
        mock_get_red_metrics.return_value = mock_red

        mock_get_response = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get_response.return_value = mock_response

        mock_request = MagicMock()
        mock_request.path = "/api/orders"
        mock_request.method = "GET"
        mock_request.headers = {}
        mock_request.META = {}
        mock_request.user.is_authenticated = False

        middleware = ObskitDjangoMiddleware(mock_get_response)
        middleware(mock_request)

        mock_red.observe_request.assert_called_once()

    @patch("obskit.middleware.django.DJANGO_AVAILABLE", True)
    @patch("obskit.middleware.django.settings")
    @patch("obskit.middleware.django.get_red_metrics")
    def test_call_adds_correlation_header(self, mock_get_red_metrics, mock_settings):
        """Test correlation ID is added to response headers."""
        from obskit.middleware.django import ObskitDjangoMiddleware

        mock_settings.OBSKIT = {}
        mock_get_response = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get_response.return_value = mock_response

        mock_request = MagicMock()
        mock_request.path = "/api/orders"
        mock_request.method = "GET"
        mock_request.headers = {"X-Correlation-ID": "test-123"}
        mock_request.META = {}
        mock_request.user.is_authenticated = False

        middleware = ObskitDjangoMiddleware(mock_get_response)
        middleware(mock_request)

        mock_response.__setitem__.assert_any_call("X-Correlation-ID", "test-123")

    @patch("obskit.middleware.django.DJANGO_AVAILABLE", True)
    @patch("obskit.middleware.django.settings")
    @patch("obskit.middleware.django.get_red_metrics")
    def test_call_handles_exception(self, mock_get_red_metrics, mock_settings):
        """Test exception handling."""
        from obskit.middleware.django import ObskitDjangoMiddleware

        mock_settings.OBSKIT = {}
        mock_red = MagicMock()
        mock_get_red_metrics.return_value = mock_red

        mock_get_response = MagicMock()
        mock_get_response.side_effect = ValueError("Test error")

        mock_request = MagicMock()
        mock_request.path = "/api/orders"
        mock_request.method = "GET"
        mock_request.headers = {}
        mock_request.META = {}
        mock_request.user.is_authenticated = False

        middleware = ObskitDjangoMiddleware(mock_get_response)

        with pytest.raises(ValueError):
            middleware(mock_request)

        # Should still record error metrics
        mock_red.observe_request.assert_called_once()
        call_kwargs = mock_red.observe_request.call_args.kwargs
        assert call_kwargs.get("status") == "failure"

    @patch("obskit.middleware.django.DJANGO_AVAILABLE", True)
    @patch("obskit.middleware.django.settings")
    @patch("obskit.middleware.django.get_red_metrics")
    def test_get_client_ip_from_x_forwarded_for(self, mock_get_red_metrics, mock_settings):
        """Test getting client IP from X-Forwarded-For."""
        from obskit.middleware.django import ObskitDjangoMiddleware

        mock_settings.OBSKIT = {}
        mock_get_response = MagicMock()

        mock_request = MagicMock()
        mock_request.META = {"HTTP_X_FORWARDED_FOR": "1.2.3.4, 5.6.7.8"}

        middleware = ObskitDjangoMiddleware(mock_get_response)
        ip = middleware._get_client_ip(mock_request)

        assert ip == "1.2.3.4"

    @patch("obskit.middleware.django.DJANGO_AVAILABLE", True)
    @patch("obskit.middleware.django.settings")
    @patch("obskit.middleware.django.get_red_metrics")
    def test_get_client_ip_from_x_real_ip(self, mock_get_red_metrics, mock_settings):
        """Test getting client IP from X-Real-IP."""
        from obskit.middleware.django import ObskitDjangoMiddleware

        mock_settings.OBSKIT = {}
        mock_get_response = MagicMock()

        mock_request = MagicMock()
        mock_request.META = {"HTTP_X_REAL_IP": "10.0.0.1"}

        middleware = ObskitDjangoMiddleware(mock_get_response)
        ip = middleware._get_client_ip(mock_request)

        assert ip == "10.0.0.1"

    @patch("obskit.middleware.django.DJANGO_AVAILABLE", True)
    @patch("obskit.middleware.django.settings")
    @patch("obskit.middleware.django.get_red_metrics")
    def test_process_exception(self, mock_get_red_metrics, mock_settings):
        """Test process_exception hook."""
        from obskit.middleware.django import ObskitDjangoMiddleware

        mock_settings.OBSKIT = {}
        mock_get_response = MagicMock()

        middleware = ObskitDjangoMiddleware(mock_get_response)

        # Should not raise
        middleware.process_exception(MagicMock(), ValueError("test"))

    @patch("obskit.middleware.django.DJANGO_AVAILABLE", True)
    @patch("obskit.middleware.django.settings")
    @patch("obskit.middleware.django.get_red_metrics")
    @patch("obskit.middleware.django.inject_trace_context")
    def test_injects_trace_headers(self, mock_inject, mock_get_red_metrics, mock_settings):
        """Test middleware injects trace headers into response."""
        from obskit.middleware.django import ObskitDjangoMiddleware

        mock_settings.OBSKIT = {"track_tracing": True}
        mock_red = MagicMock()
        mock_get_red_metrics.return_value = mock_red

        # Make inject_trace_context add headers
        def add_headers(headers):
            headers["traceparent"] = "00-test-trace-id"
            return headers

        mock_inject.side_effect = add_headers

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.__setitem__ = MagicMock()
        mock_get_response = MagicMock(return_value=mock_response)

        mock_request = MagicMock()
        mock_request.path = "/test"
        mock_request.method = "GET"
        mock_request.META = {"REMOTE_ADDR": "127.0.0.1"}

        middleware = ObskitDjangoMiddleware(mock_get_response)
        middleware.track_tracing = True  # Set directly
        middleware(mock_request)

        mock_inject.assert_called()
        mock_response.__setitem__.assert_called()


@pytest.mark.skipif(not DJANGO_AVAILABLE, reason="Django not installed")
class TestGetObskitMiddleware:
    """Tests for get_obskit_middleware factory."""

    @patch("obskit.middleware.django.DJANGO_AVAILABLE", True)
    @patch("obskit.middleware.django.settings")
    @patch("obskit.middleware.django.get_red_metrics")
    def test_creates_configured_middleware(self, mock_get_red_metrics, mock_settings):
        """Test factory creates configured middleware."""
        from obskit.middleware.django import ObskitDjangoMiddleware, get_obskit_middleware

        mock_settings.OBSKIT = {}

        MiddlewareClass = get_obskit_middleware(
            exclude_paths=["/custom/"],
            track_metrics=False,
        )

        assert issubclass(MiddlewareClass, ObskitDjangoMiddleware)

        mock_get_response = MagicMock()
        middleware = MiddlewareClass(mock_get_response)

        assert middleware.exclude_paths == ["/custom/"]
        assert middleware.track_metrics is False

    @patch("obskit.middleware.django.DJANGO_AVAILABLE", True)
    @patch("obskit.middleware.django.settings")
    @patch("obskit.middleware.django.get_red_metrics")
    def test_factory_with_all_options(self, mock_get_red_metrics, mock_settings):
        """Test factory with all options."""
        from obskit.middleware.django import get_obskit_middleware

        mock_settings.OBSKIT = {}
        mock_red = MagicMock()
        mock_get_red_metrics.return_value = mock_red

        MiddlewareClass = get_obskit_middleware(
            exclude_paths=["/api/health/", "/api/ready/"],
            track_metrics=True,
            track_logging=False,
            track_tracing=False,
        )

        mock_get_response = MagicMock()
        middleware = MiddlewareClass(mock_get_response)

        assert middleware.exclude_paths == ["/api/health/", "/api/ready/"]
        assert middleware.track_metrics is True
        assert middleware.track_logging is False
        assert middleware.track_tracing is False

    @patch("obskit.middleware.django.DJANGO_AVAILABLE", True)
    @patch("obskit.middleware.django.settings")
    @patch("obskit.middleware.django.get_red_metrics")
    def test_factory_enables_metrics(self, mock_get_red_metrics, mock_settings):
        """Test factory enables metrics when track_metrics is True."""
        from obskit.middleware.django import get_obskit_middleware

        mock_settings.OBSKIT = {"track_metrics": False}  # Disabled in settings
        mock_red = MagicMock()
        mock_get_red_metrics.return_value = mock_red

        # Factory should override settings
        MiddlewareClass = get_obskit_middleware(track_metrics=True)

        mock_get_response = MagicMock()
        middleware = MiddlewareClass(mock_get_response)

        assert middleware.track_metrics is True
        assert middleware.red_metrics is not None


@pytest.mark.skipif(not DJANGO_AVAILABLE, reason="Django not installed")
class TestMiddlewareLogging:
    """Tests for logging methods."""

    @patch("obskit.middleware.django.DJANGO_AVAILABLE", True)
    @patch("obskit.middleware.django.settings")
    @patch("obskit.middleware.django.get_red_metrics")
    @patch("obskit.middleware.django.logger")
    def test_log_request_start(self, mock_logger, mock_get_red_metrics, mock_settings):
        """Test _log_request_start method."""
        from obskit.middleware.django import ObskitDjangoMiddleware

        mock_settings.OBSKIT = {}
        mock_get_response = MagicMock()

        mock_request = MagicMock()
        mock_request.method = "POST"
        mock_request.path = "/api/orders"
        mock_request.META = {}
        mock_request.user.is_authenticated = True
        mock_request.user.id = 123

        middleware = ObskitDjangoMiddleware(mock_get_response)
        middleware._log_request_start(mock_request, "create_order", "corr-123")

        mock_logger.info.assert_called_once()

    @patch("obskit.middleware.django.DJANGO_AVAILABLE", True)
    @patch("obskit.middleware.django.settings")
    @patch("obskit.middleware.django.get_red_metrics")
    @patch("obskit.middleware.django.logger")
    def test_log_request_complete(self, mock_logger, mock_get_red_metrics, mock_settings):
        """Test _log_request_complete method."""
        from obskit.middleware.django import ObskitDjangoMiddleware

        mock_settings.OBSKIT = {}
        mock_get_response = MagicMock()

        mock_request = MagicMock()
        mock_request.method = "GET"
        mock_request.path = "/api/orders"

        mock_response = MagicMock()
        mock_response.status_code = 200

        middleware = ObskitDjangoMiddleware(mock_get_response)
        middleware._log_request_complete(
            mock_request, mock_response, "get_orders", 45.5, "corr-123"
        )

        mock_logger.info.assert_called_once()

    @patch("obskit.middleware.django.DJANGO_AVAILABLE", True)
    @patch("obskit.middleware.django.settings")
    @patch("obskit.middleware.django.get_red_metrics")
    @patch("obskit.middleware.django.logger")
    def test_log_request_error(self, mock_logger, mock_get_red_metrics, mock_settings):
        """Test _log_request_error method."""
        from obskit.middleware.django import ObskitDjangoMiddleware

        mock_settings.OBSKIT = {}
        mock_get_response = MagicMock()

        mock_request = MagicMock()
        mock_request.method = "POST"
        mock_request.path = "/api/orders"

        middleware = ObskitDjangoMiddleware(mock_get_response)
        middleware._log_request_error(
            mock_request, ValueError("test error"), "create_order", 12.5, "corr-123"
        )

        mock_logger.error.assert_called_once()


@pytest.mark.skipif(not DJANGO_AVAILABLE, reason="Django not installed")
class TestMiddlewareOperationName:
    """Tests for _get_operation_name method."""

    @patch("obskit.middleware.django.DJANGO_AVAILABLE", True)
    @patch("obskit.middleware.django.settings")
    @patch("obskit.middleware.django.get_red_metrics")
    def test_get_operation_name_fallback(self, mock_get_red_metrics, mock_settings):
        """Test _get_operation_name falls back to path."""
        from obskit.middleware.django import ObskitDjangoMiddleware

        mock_settings.OBSKIT = {}
        mock_get_response = MagicMock()

        mock_request = MagicMock()
        mock_request.path = "/api/orders/123"

        middleware = ObskitDjangoMiddleware(mock_get_response)

        # Patch resolve at django.urls level where it's imported from
        with patch("django.urls.resolve") as mock_resolve:
            mock_resolve.side_effect = Exception("No match")
            operation = middleware._get_operation_name(mock_request)

        assert operation == "api_orders_123"

    @patch("obskit.middleware.django.DJANGO_AVAILABLE", True)
    @patch("obskit.middleware.django.settings")
    @patch("obskit.middleware.django.get_red_metrics")
    def test_get_operation_name_empty_path(self, mock_get_red_metrics, mock_settings):
        """Test _get_operation_name with root path."""
        from obskit.middleware.django import ObskitDjangoMiddleware

        mock_settings.OBSKIT = {}
        mock_get_response = MagicMock()

        mock_request = MagicMock()
        mock_request.path = "/"

        middleware = ObskitDjangoMiddleware(mock_get_response)

        with patch("django.urls.resolve") as mock_resolve:
            mock_resolve.side_effect = Exception("No match")
            operation = middleware._get_operation_name(mock_request)

        assert operation == "unknown"

    @patch("obskit.middleware.django.DJANGO_AVAILABLE", True)
    @patch("obskit.middleware.django.settings")
    @patch("obskit.middleware.django.get_red_metrics")
    def test_get_operation_name_from_url_name(self, mock_get_red_metrics, mock_settings):
        """Test _get_operation_name uses URL name when available."""
        from obskit.middleware.django import ObskitDjangoMiddleware

        mock_settings.OBSKIT = {}
        mock_get_response = MagicMock()

        mock_request = MagicMock()
        mock_request.path = "/api/orders"

        middleware = ObskitDjangoMiddleware(mock_get_response)

        # Mock resolve to return url_name
        mock_match = MagicMock()
        mock_match.url_name = "order_list"
        mock_match.view_name = None

        with patch("django.urls.resolve") as mock_resolve:
            mock_resolve.return_value = mock_match
            operation = middleware._get_operation_name(mock_request)

        assert operation == "order_list"

    @patch("obskit.middleware.django.DJANGO_AVAILABLE", True)
    @patch("obskit.middleware.django.settings")
    @patch("obskit.middleware.django.get_red_metrics")
    def test_get_operation_name_from_view_name(self, mock_get_red_metrics, mock_settings):
        """Test _get_operation_name uses view name as fallback."""
        from obskit.middleware.django import ObskitDjangoMiddleware

        mock_settings.OBSKIT = {}
        mock_get_response = MagicMock()

        mock_request = MagicMock()
        mock_request.path = "/api/orders"

        middleware = ObskitDjangoMiddleware(mock_get_response)

        mock_match = MagicMock()
        mock_match.url_name = None
        mock_match.view_name = "orders_view"

        with patch("django.urls.resolve") as mock_resolve:
            mock_resolve.return_value = mock_match
            operation = middleware._get_operation_name(mock_request)

        assert operation == "orders_view"


@pytest.mark.skipif(not DJANGO_AVAILABLE, reason="Django not installed")
class TestMiddlewareClientIP:
    """Tests for _get_client_ip method."""

    @patch("obskit.middleware.django.DJANGO_AVAILABLE", True)
    @patch("obskit.middleware.django.settings")
    @patch("obskit.middleware.django.get_red_metrics")
    def test_get_client_ip_from_remote_addr(self, mock_get_red_metrics, mock_settings):
        """Test getting client IP from REMOTE_ADDR."""
        from obskit.middleware.django import ObskitDjangoMiddleware

        mock_settings.OBSKIT = {}
        mock_get_response = MagicMock()

        mock_request = MagicMock()
        mock_request.META = {"REMOTE_ADDR": "192.168.1.100"}

        middleware = ObskitDjangoMiddleware(mock_get_response)
        ip = middleware._get_client_ip(mock_request)

        assert ip == "192.168.1.100"

    @patch("obskit.middleware.django.DJANGO_AVAILABLE", True)
    @patch("obskit.middleware.django.settings")
    @patch("obskit.middleware.django.get_red_metrics")
    def test_get_client_ip_none(self, mock_get_red_metrics, mock_settings):
        """Test getting client IP when none available."""
        from obskit.middleware.django import ObskitDjangoMiddleware

        mock_settings.OBSKIT = {}
        mock_get_response = MagicMock()

        mock_request = MagicMock()
        mock_request.META = {}

        middleware = ObskitDjangoMiddleware(mock_get_response)
        ip = middleware._get_client_ip(mock_request)

        assert ip is None

    @patch("obskit.middleware.django.DJANGO_AVAILABLE", True)
    @patch("obskit.middleware.django.settings")
    @patch("obskit.middleware.django.get_red_metrics")
    def test_get_client_ip_empty_forwarded_for(self, mock_get_red_metrics, mock_settings):
        """Test X-Forwarded-For with empty first IP."""
        from obskit.middleware.django import ObskitDjangoMiddleware

        mock_settings.OBSKIT = {}
        mock_get_response = MagicMock()

        mock_request = MagicMock()
        mock_request.META = {"HTTP_X_FORWARDED_FOR": "  , 1.2.3.4"}

        middleware = ObskitDjangoMiddleware(mock_get_response)
        ip = middleware._get_client_ip(mock_request)

        # Empty first entry returns None
        assert ip is None


@pytest.mark.skipif(not DJANGO_AVAILABLE, reason="Django not installed")
class TestMiddlewareTracing:
    """Tests for tracing functionality."""

    @patch("obskit.middleware.django.DJANGO_AVAILABLE", True)
    @patch("obskit.middleware.django.settings")
    @patch("obskit.middleware.django.get_red_metrics")
    @patch("obskit.middleware.django.inject_trace_context")
    @patch("obskit.middleware.django.extract_trace_context")
    def test_injects_trace_context(
        self, mock_extract, mock_inject, mock_get_red_metrics, mock_settings
    ):
        """Test trace context injection into response."""
        from obskit.middleware.django import ObskitDjangoMiddleware

        mock_settings.OBSKIT = {"track_tracing": True}
        mock_inject.return_value = None

        mock_get_response = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get_response.return_value = mock_response

        mock_request = MagicMock()
        mock_request.path = "/api/orders"
        mock_request.method = "GET"
        mock_request.headers = {}
        mock_request.META = {}
        mock_request.user.is_authenticated = False

        middleware = ObskitDjangoMiddleware(mock_get_response)
        middleware(mock_request)

        mock_inject.assert_called_once()
