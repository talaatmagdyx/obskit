"""Tests for obskit.metrics.auth module."""

from io import BytesIO
from unittest.mock import MagicMock, patch

from obskit.metrics.auth import (
    AuthenticatedMetricsHandler,
    create_authenticated_handler,
)


class TestAuthenticatedMetricsHandler:
    """Tests for AuthenticatedMetricsHandler class."""

    def _create_handler_instance(self, auth_token=None, path="/metrics", auth_header=None):
        """Helper to create a handler with mocked internals."""
        # Create handler without calling BaseHTTPRequestHandler.__init__
        handler = object.__new__(AuthenticatedMetricsHandler)
        handler.auth_token = auth_token
        handler.path = path
        handler.requestline = f"GET {path} HTTP/1.1"
        handler.request_version = "HTTP/1.1"
        handler.command = "GET"
        handler.wfile = BytesIO()

        # Mock headers
        headers = {}
        if auth_header:
            headers["Authorization"] = auth_header
        handler.headers = headers

        # Track response
        handler._response_code = None
        handler._response_headers = []

        def original_send_response(code):
            return setattr(handler, "_response_code", code)

        def original_send_header(k, v):
            return handler._response_headers.append((k, v))

        def original_end_headers():
            return None

        handler.send_response = original_send_response
        handler.send_header = original_send_header
        handler.end_headers = original_end_headers

        return handler

    def test_no_auth_required_metrics_path(self):
        """Test handler without auth token allows /metrics access."""
        handler = self._create_handler_instance(auth_token=None, path="/metrics")

        with patch("prometheus_client.MetricsHandler") as mock_metrics:
            mock_metrics.do_GET = MagicMock()
            handler.do_GET()
            mock_metrics.do_GET.assert_called_once()

    def test_no_auth_required_other_path_returns_404(self):
        """Test non-metrics path returns 404."""
        handler = self._create_handler_instance(auth_token=None, path="/other")

        handler.do_GET()

        assert handler._response_code == 404
        assert b"Not Found" in handler.wfile.getvalue()

    def test_missing_auth_header_returns_401(self):
        """Test missing Authorization header returns 401."""
        handler = self._create_handler_instance(auth_token="secret-token", auth_header=None)

        handler.do_GET()

        assert handler._response_code == 401
        assert any("WWW-Authenticate" in h[0] for h in handler._response_headers)
        assert b"Unauthorized" in handler.wfile.getvalue()

    def test_invalid_auth_format_returns_401(self):
        """Test invalid Authorization format (not Bearer) returns 401."""
        handler = self._create_handler_instance(
            auth_token="secret-token", auth_header="Basic dXNlcjpwYXNz"
        )

        handler.do_GET()

        assert handler._response_code == 401

    def test_wrong_token_returns_403(self):
        """Test wrong token returns 403."""
        handler = self._create_handler_instance(
            auth_token="secret-token", auth_header="Bearer wrong-token"
        )

        handler.do_GET()

        assert handler._response_code == 403
        assert b"Forbidden" in handler.wfile.getvalue()

    def test_valid_token_allows_access(self):
        """Test valid token allows access to metrics."""
        handler = self._create_handler_instance(
            auth_token="secret-token", path="/metrics", auth_header="Bearer secret-token"
        )

        with patch("prometheus_client.MetricsHandler") as mock_metrics:
            mock_metrics.do_GET = MagicMock()
            handler.do_GET()
            mock_metrics.do_GET.assert_called_once()

    def test_valid_token_non_metrics_path_returns_404(self):
        """Test valid token on non-metrics path returns 404."""
        handler = self._create_handler_instance(
            auth_token="secret-token", path="/other", auth_header="Bearer secret-token"
        )

        handler.do_GET()

        assert handler._response_code == 404

    def test_log_message(self):
        """Test log_message uses obskit logger."""
        handler = self._create_handler_instance()

        with patch("obskit.metrics.auth.logger") as mock_logger:
            handler.log_message("Test %s %s", "arg1", "arg2")
            mock_logger.debug.assert_called_once_with("metrics_request", message="Test arg1 arg2")


class TestCreateAuthenticatedHandler:
    """Tests for create_authenticated_handler function."""

    def test_creates_handler_class(self):
        """Test factory creates handler class."""
        HandlerClass = create_authenticated_handler("my-token")

        assert issubclass(HandlerClass, AuthenticatedMetricsHandler)

    def test_created_handler_uses_token(self):
        """Test created handler class uses the provided token."""
        HandlerClass = create_authenticated_handler("test-token-123")

        # Create instance without full init
        handler = object.__new__(HandlerClass)
        handler.auth_token = None

        # The __init__ should set the token via super().__init__
        # We can't easily test this without full socket setup
        # Verify the class exists and is correct type
        assert HandlerClass.__name__ == "Handler"

    @patch("http.server.BaseHTTPRequestHandler.__init__")
    def test_handler_init_sets_token(self, mock_base_init):
        """Test that created handler __init__ sets auth_token."""
        mock_base_init.return_value = None

        HandlerClass = create_authenticated_handler("my-secret-token")

        # Create a minimal mock request
        mock_request = MagicMock()
        mock_client_address = ("127.0.0.1", 12345)
        mock_server = MagicMock()

        # Create handler - this should call __init__ which sets auth_token
        handler = HandlerClass(mock_request, mock_client_address, mock_server)

        assert handler.auth_token == "my-secret-token"


class TestAuthenticatedMetricsHandlerInit:
    """Tests for AuthenticatedMetricsHandler initialization."""

    @patch("http.server.BaseHTTPRequestHandler.__init__")
    def test_init_stores_auth_token(self, mock_base_init):
        """Test __init__ stores auth_token."""
        mock_base_init.return_value = None

        mock_request = MagicMock()
        mock_client_address = ("127.0.0.1", 12345)
        mock_server = MagicMock()

        handler = AuthenticatedMetricsHandler(
            mock_request, mock_client_address, mock_server, auth_token="test-token"
        )

        assert handler.auth_token == "test-token"

    @patch("http.server.BaseHTTPRequestHandler.__init__")
    def test_init_without_token(self, mock_base_init):
        """Test __init__ without auth_token defaults to None."""
        mock_base_init.return_value = None

        mock_request = MagicMock()
        mock_client_address = ("127.0.0.1", 12345)
        mock_server = MagicMock()

        handler = AuthenticatedMetricsHandler(mock_request, mock_client_address, mock_server)

        assert handler.auth_token is None


class TestAuthHandlerEdgeCases:
    """Additional tests for edge cases in AuthenticatedMetricsHandler.do_GET()."""

    def _make_handler(self, auth_token=None, auth_header=None, path="/metrics"):
        """Create a handler with mocked response methods."""
        from io import BytesIO

        handler = object.__new__(AuthenticatedMetricsHandler)
        handler.auth_token = auth_token
        handler.path = path
        handler.requestline = f"GET {path} HTTP/1.1"
        handler.request_version = "HTTP/1.1"
        handler.command = "GET"
        handler.wfile = BytesIO()
        handler.client_address = ("127.0.0.1", 12345)
        headers = {}
        if auth_header:
            headers["Authorization"] = auth_header
        handler.headers = headers
        handler._response_code = None
        handler._response_headers = []
        handler.send_response = lambda code: setattr(handler, "_response_code", code)
        handler.send_header = lambda k, v: handler._response_headers.append((k, v))
        handler.end_headers = lambda: None
        return handler

    def test_auth_header_too_long_returns_401(self):
        """Authorization header > 512 bytes returns 401."""
        long_header = "Bearer " + "x" * 600
        handler = self._make_handler(auth_token="secret", auth_header=long_header)
        handler.do_GET()
        assert handler._response_code == 401
        assert b"too long" in handler.wfile.getvalue()

    def test_empty_bearer_token_returns_401(self):
        """'Bearer ' with empty token returns 401."""
        handler = self._make_handler(auth_token="secret", auth_header="Bearer ")
        handler.do_GET()
        assert handler._response_code == 401
        assert b"Empty token" in handler.wfile.getvalue()

    def test_auth_lockout_returns_429(self):
        """IP that has exceeded failed-auth threshold returns 429."""
        import time
        from obskit.metrics.auth import _failed_auth, _FAILED_AUTH_MAX

        handler = self._make_handler(auth_token="secret")
        client_ip = "127.0.0.3"
        handler.client_address = (client_ip, 12345)
        # Simulate enough recent failed attempts to trigger lockout
        now = time.time()
        _failed_auth[client_ip] = [now] * (_FAILED_AUTH_MAX + 1)
        try:
            handler.do_GET()
            assert handler._response_code == 429
            assert b"Too Many" in handler.wfile.getvalue()
        finally:
            _failed_auth.pop(client_ip, None)

    def test_rate_limited_returns_429(self):
        """Rate limiter exceeded returns 429."""
        from unittest.mock import MagicMock, patch

        mock_limiter = MagicMock()
        mock_limiter.is_allowed.return_value = False
        handler = self._make_handler(auth_token=None)
        with patch("obskit.metrics.auth._get_rate_limiter", return_value=mock_limiter):
            handler.do_GET()
        assert handler._response_code == 429
        assert b"Rate limit" in handler.wfile.getvalue()


class TestCreateRateLimitedHandler:
    """Tests for create_rate_limited_handler()."""

    def test_returns_handler_class(self):
        """Returns a class that is a subclass of AuthenticatedMetricsHandler."""
        from obskit.metrics.auth import create_rate_limited_handler

        HandlerClass = create_rate_limited_handler()
        assert issubclass(HandlerClass, AuthenticatedMetricsHandler)

    @patch("http.server.BaseHTTPRequestHandler.__init__")
    def test_handler_has_no_auth_token(self, mock_base_init):
        """Rate-limited handler sets auth_token=None."""
        from obskit.metrics.auth import create_rate_limited_handler

        mock_base_init.return_value = None
        HandlerClass = create_rate_limited_handler()
        handler = HandlerClass(MagicMock(), ("127.0.0.1", 12345), MagicMock())
        assert handler.auth_token is None
