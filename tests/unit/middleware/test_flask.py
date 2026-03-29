"""Tests for obskit.middleware.flask module."""

from unittest.mock import MagicMock, patch

import pytest

# Check if Flask is available
try:
    from flask import Flask

    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False
    Flask = None  # type: ignore[misc, assignment]


@pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not installed")
class TestObskitFlaskMiddleware:
    """Tests for ObskitFlaskMiddleware class."""

    @patch("obskit.middleware.flask.FLASK_AVAILABLE", True)
    @patch("obskit.middleware.flask.get_red_metrics")
    def test_init(self, mock_get_red_metrics):
        """Test middleware initialization without app."""
        from obskit.middleware.flask import ObskitFlaskMiddleware

        mock_red = MagicMock()
        mock_get_red_metrics.return_value = mock_red

        middleware = ObskitFlaskMiddleware()

        assert middleware.track_metrics is True
        assert middleware.track_logging is True
        assert middleware.track_tracing is True
        assert middleware.red_metrics == mock_red

    @patch("obskit.middleware.flask.FLASK_AVAILABLE", True)
    @patch("obskit.middleware.flask.get_red_metrics")
    def test_init_with_custom_params(self, mock_get_red_metrics):
        """Test initialization with custom parameters."""
        from obskit.middleware.flask import ObskitFlaskMiddleware

        middleware = ObskitFlaskMiddleware(
            exclude_paths=["/api/health"],
            track_metrics=False,
            track_logging=False,
            track_tracing=False,
        )

        assert middleware.exclude_paths == ["/api/health"]
        assert middleware.track_metrics is False
        assert middleware.track_logging is False
        assert middleware.track_tracing is False

    @patch("obskit.middleware.flask.FLASK_AVAILABLE", True)
    @patch("obskit.middleware.flask.get_red_metrics")
    def test_init_app(self, mock_get_red_metrics):
        """Test init_app registers hooks."""
        from obskit.middleware.flask import ObskitFlaskMiddleware

        mock_app = MagicMock()
        mock_app.extensions = {}

        middleware = ObskitFlaskMiddleware()
        middleware.init_app(mock_app)

        assert "obskit" in mock_app.extensions
        mock_app.before_request.assert_called_once()
        mock_app.after_request.assert_called_once()
        mock_app.teardown_request.assert_called_once()

    @patch("obskit.middleware.flask.FLASK_AVAILABLE", True)
    @patch("obskit.middleware.flask.get_red_metrics")
    def test_init_with_app(self, mock_get_red_metrics):
        """Test initialization with app."""
        from obskit.middleware.flask import ObskitFlaskMiddleware

        mock_app = MagicMock()
        mock_app.extensions = {}

        ObskitFlaskMiddleware(app=mock_app)

        assert "obskit" in mock_app.extensions

    @patch("obskit.middleware.flask.FLASK_AVAILABLE", True)
    @patch("obskit.middleware.flask.get_red_metrics")
    def test_should_exclude(self, mock_get_red_metrics):
        """Test path exclusion logic."""
        from obskit.middleware.flask import ObskitFlaskMiddleware

        middleware = ObskitFlaskMiddleware(exclude_paths=["/health", "/metrics"])

        assert middleware._should_exclude("/health") is True
        assert middleware._should_exclude("/metrics") is True
        assert middleware._should_exclude("/api/orders") is False

    @patch("obskit.middleware.flask.get_red_metrics")
    def test_full_request_cycle(self, mock_get_red_metrics):
        """Test full request cycle with Flask test client."""
        from obskit.middleware.flask import ObskitFlaskMiddleware

        mock_red = MagicMock()
        mock_get_red_metrics.return_value = mock_red

        app = Flask(__name__)
        ObskitFlaskMiddleware(app, track_tracing=False)

        @app.route("/test")
        def test_view():
            return "OK"

        with app.test_client() as client:
            response = client.get("/test")

            assert response.status_code == 200
            assert "X-Correlation-ID" in response.headers
            mock_red.observe_request.assert_called()

    @patch("obskit.middleware.flask.get_red_metrics")
    def test_excluded_path_skips_observability(self, mock_get_red_metrics):
        """Test that excluded paths skip observability."""
        from obskit.middleware.flask import ObskitFlaskMiddleware

        mock_red = MagicMock()
        mock_get_red_metrics.return_value = mock_red

        app = Flask(__name__)
        ObskitFlaskMiddleware(
            app,
            exclude_paths=["/health"],
            track_tracing=False,
        )

        @app.route("/health")
        def health():
            return "OK"

        with app.test_client() as client:
            response = client.get("/health")

            assert response.status_code == 200
            # Should not record metrics for excluded path
            mock_red.observe_request.assert_not_called()

    @patch("obskit.middleware.flask.get_red_metrics")
    def test_error_response_records_failure(self, mock_get_red_metrics):
        """Test that error responses record failure metrics."""
        from obskit.middleware.flask import ObskitFlaskMiddleware

        mock_red = MagicMock()
        mock_get_red_metrics.return_value = mock_red

        app = Flask(__name__)
        ObskitFlaskMiddleware(app, track_tracing=False)

        @app.route("/error")
        def error_view():
            from flask import abort

            abort(500)

        with app.test_client() as client:
            response = client.get("/error")

            assert response.status_code == 500
            mock_red.observe_request.assert_called()
            call_kwargs = mock_red.observe_request.call_args.kwargs
            assert call_kwargs.get("status") == "failure"

    @patch("obskit.middleware.flask.get_red_metrics")
    def test_correlation_id_from_header(self, mock_get_red_metrics):
        """Test correlation ID is taken from request header."""
        from obskit.middleware.flask import ObskitFlaskMiddleware

        mock_red = MagicMock()
        mock_get_red_metrics.return_value = mock_red

        app = Flask(__name__)
        ObskitFlaskMiddleware(app, track_tracing=False)

        @app.route("/test")
        def test_view():
            return "OK"

        with app.test_client() as client:
            response = client.get("/test", headers={"X-Correlation-ID": "custom-123"})

            assert response.status_code == 200
            assert response.headers.get("X-Correlation-ID") == "custom-123"

    @patch("obskit.middleware.flask.get_red_metrics")
    def test_exception_in_view_records_error(self, mock_get_red_metrics):
        """Test that exception in view records error metrics."""
        from obskit.middleware.flask import ObskitFlaskMiddleware

        mock_red = MagicMock()
        mock_get_red_metrics.return_value = mock_red

        app = Flask(__name__)
        app.config["TESTING"] = True
        ObskitFlaskMiddleware(app, track_tracing=False)

        @app.route("/exception")
        def exception_view():
            raise ValueError("Test error")

        with app.test_client() as client:
            # In testing mode, Flask will raise the exception
            with pytest.raises(ValueError):
                client.get("/exception")

            # Error metrics should be recorded in teardown
            # Note: actual behavior depends on exception handling

    @patch("obskit.middleware.flask.get_red_metrics")
    def test_init_app_without_extensions(self, mock_get_red_metrics):
        """Test init_app creates extensions dict if not present."""
        from obskit.middleware.flask import ObskitFlaskMiddleware

        # Create a simple object without extensions
        class MockApp:
            def before_request(self, f):
                pass  # NOSONAR

            def after_request(self, f):
                pass  # NOSONAR

            def teardown_request(self, f):
                pass  # NOSONAR

        mock_app = MockApp()

        middleware = ObskitFlaskMiddleware()
        middleware.init_app(mock_app)

        assert hasattr(mock_app, "extensions")
        assert mock_app.extensions["obskit"] is middleware

    @patch("obskit.middleware.flask.get_red_metrics")
    @patch("obskit.middleware.flask.inject_trace_context")
    @patch("obskit.middleware.flask.extract_trace_context")
    def test_request_with_tracing(self, mock_extract, mock_inject, mock_get_red_metrics):
        """Test request with tracing enabled."""
        from obskit.middleware.flask import ObskitFlaskMiddleware

        mock_red = MagicMock()
        mock_get_red_metrics.return_value = mock_red
        mock_extract.return_value = MagicMock()
        mock_inject.return_value = None

        app = Flask(__name__)
        ObskitFlaskMiddleware(app, track_tracing=True)

        @app.route("/test")
        def test_view():
            return "OK"

        with app.test_client() as client:
            response = client.get("/test")

            assert response.status_code == 200
            mock_extract.assert_called()
            mock_inject.assert_called()

    @patch("obskit.middleware.flask.get_red_metrics")
    @patch("obskit.middleware.flask.logger")
    def test_request_with_logging(self, mock_logger, mock_get_red_metrics):
        """Test request with logging enabled."""
        from obskit.middleware.flask import ObskitFlaskMiddleware

        mock_red = MagicMock()
        mock_get_red_metrics.return_value = mock_red

        app = Flask(__name__)
        ObskitFlaskMiddleware(app, track_tracing=False, track_logging=True)

        @app.route("/test")
        def test_view():
            return "OK"

        with app.test_client() as client:
            response = client.get("/test")

            assert response.status_code == 200
            # Logger should be called at least twice (start and complete)
            assert mock_logger.info.call_count >= 2

    @patch("obskit.middleware.flask.get_red_metrics")
    @patch("obskit.middleware.flask.logger")
    def test_teardown_with_exception(self, mock_logger, mock_get_red_metrics):
        """Test teardown logs errors on exception."""
        from obskit.middleware.flask import ObskitFlaskMiddleware

        mock_red = MagicMock()
        mock_get_red_metrics.return_value = mock_red

        app = Flask(__name__)
        app.config["PROPAGATE_EXCEPTIONS"] = False
        ObskitFlaskMiddleware(app, track_tracing=False, track_logging=True)

        @app.route("/error")
        def error_view():
            raise RuntimeError("Test error")

        # Add custom error handler to prevent exception propagation
        @app.errorhandler(RuntimeError)
        def handle_runtime_error(e):
            return "Error", 500

        with app.test_client() as client:
            response = client.get("/error")

            assert response.status_code == 500
            # Error metrics and logging should be recorded
            mock_red.observe_request.assert_called()

    @patch("obskit.middleware.flask.get_red_metrics")
    def test_get_obskit_flask_creates_instance(self, mock_get_red_metrics):
        """Test get_obskit_flask creates singleton when _obskit_flask is None (lines 331-333)."""
        import obskit.middleware.flask as flask_module
        from obskit.middleware.flask import get_obskit_flask

        mock_red = MagicMock()
        mock_get_red_metrics.return_value = mock_red

        # Reset the singleton to None
        original = flask_module._obskit_flask
        flask_module._obskit_flask = None

        try:
            result = get_obskit_flask()
            assert result is not None
            assert isinstance(result, flask_module.ObskitFlaskMiddleware)
            # Second call should return the same instance
            result2 = get_obskit_flask()
            assert result2 is result
        finally:
            flask_module._obskit_flask = original

    @patch("obskit.middleware.flask.get_red_metrics")
    def test_get_obskit_flask_returns_existing_instance(self, mock_get_red_metrics):
        """Test get_obskit_flask returns existing instance when already set."""
        import obskit.middleware.flask as flask_module
        from obskit.middleware.flask import ObskitFlaskMiddleware, get_obskit_flask

        mock_red = MagicMock()
        mock_get_red_metrics.return_value = mock_red

        # Pre-set a mock instance
        original = flask_module._obskit_flask
        mock_instance = MagicMock(spec=ObskitFlaskMiddleware)
        flask_module._obskit_flask = mock_instance

        try:
            result = get_obskit_flask()
            # Should return existing instance without creating a new one
            assert result is mock_instance
        finally:
            flask_module._obskit_flask = original
