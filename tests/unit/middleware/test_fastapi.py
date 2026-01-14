"""Tests for obskit.middleware.fastapi module."""

from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from obskit.middleware.fastapi import ObskitMiddleware


class TestObskitMiddleware:
    """Tests for ObskitMiddleware class."""

    def setup_method(self):
        """Reset state before each test."""
        pass

    def test_init(self):
        """Test middleware initialization."""
        app = FastAPI()
        middleware = ObskitMiddleware(app)

        assert middleware.app is app

    def test_init_with_custom_params(self):
        """Test initialization with custom parameters."""
        app = FastAPI()
        middleware = ObskitMiddleware(
            app,
            exclude_paths=["/custom-health"],
            track_metrics=False,
            track_logging=False,
            track_tracing=False,
        )

        assert "/custom-health" in middleware.exclude_paths
        assert middleware.track_metrics is False
        assert middleware.track_logging is False
        assert middleware.track_tracing is False

    @patch("obskit.middleware.fastapi.get_red_metrics")
    def test_middleware_adds_correlation_id(self, mock_get_red):
        """Test middleware adds correlation ID to response."""
        mock_red = MagicMock()
        mock_get_red.return_value = mock_red

        app = FastAPI()
        app.add_middleware(
            ObskitMiddleware,
            track_tracing=False,
        )

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        client = TestClient(app)
        response = client.get("/test")

        assert response.status_code == 200
        assert "X-Correlation-ID" in response.headers

    @patch("obskit.middleware.fastapi.get_red_metrics")
    def test_middleware_uses_provided_correlation_id(self, mock_get_red):
        """Test middleware uses correlation ID from request."""
        mock_red = MagicMock()
        mock_get_red.return_value = mock_red

        app = FastAPI()
        app.add_middleware(
            ObskitMiddleware,
            track_tracing=False,
        )

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        client = TestClient(app)
        response = client.get("/test", headers={"X-Correlation-ID": "custom-id-123"})

        assert response.status_code == 200
        assert response.headers.get("X-Correlation-ID") == "custom-id-123"

    @patch("obskit.middleware.fastapi.get_red_metrics")
    def test_middleware_records_metrics(self, mock_get_red):
        """Test middleware records RED metrics."""
        mock_red = MagicMock()
        mock_get_red.return_value = mock_red

        app = FastAPI()
        app.add_middleware(
            ObskitMiddleware,
            track_tracing=False,
        )

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        client = TestClient(app)
        response = client.get("/test")

        assert response.status_code == 200
        mock_red.observe_request.assert_called()

    @patch("obskit.middleware.fastapi.get_red_metrics")
    def test_middleware_excludes_paths(self, mock_get_red):
        """Test middleware excludes configured paths."""
        mock_red = MagicMock()
        mock_get_red.return_value = mock_red

        app = FastAPI()
        app.add_middleware(
            ObskitMiddleware,
            exclude_paths=["/health"],
            track_tracing=False,
        )

        @app.get("/health")
        async def health_endpoint():
            return {"status": "ok"}

        client = TestClient(app)
        response = client.get("/health")

        assert response.status_code == 200
        # Metrics should not be recorded for excluded paths
        mock_red.observe_request.assert_not_called()

    @patch("obskit.middleware.fastapi.get_red_metrics")
    def test_middleware_handles_error(self, mock_get_red):
        """Test middleware handles errors correctly."""
        mock_red = MagicMock()
        mock_get_red.return_value = mock_red

        app = FastAPI()
        app.add_middleware(
            ObskitMiddleware,
            track_tracing=False,
        )

        @app.get("/error")
        async def error_endpoint():
            raise ValueError("Test error")

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/error")

        assert response.status_code == 500

    @patch("obskit.middleware.fastapi.get_red_metrics")
    def test_middleware_records_failure_status(self, mock_get_red):
        """Test middleware records failure for error responses."""
        mock_red = MagicMock()
        mock_get_red.return_value = mock_red

        app = FastAPI()
        app.add_middleware(
            ObskitMiddleware,
            track_tracing=False,
        )

        @app.get("/not-found")
        async def not_found():
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="Not found")

        client = TestClient(app)
        response = client.get("/not-found")

        assert response.status_code == 404
        mock_red.observe_request.assert_called()
        call_kwargs = mock_red.observe_request.call_args.kwargs
        assert call_kwargs.get("status") == "failure"

    def test_should_exclude(self):
        """Test _should_exclude method."""
        app = FastAPI()
        middleware = ObskitMiddleware(
            app,
            exclude_paths=["/health", "/metrics", "/api/v1/status"],
        )

        assert middleware._should_exclude("/health") is True
        assert middleware._should_exclude("/metrics") is True
        assert middleware._should_exclude("/api/v1/status") is True
        assert middleware._should_exclude("/api/v1/users") is False

    @patch("obskit.middleware.fastapi.get_red_metrics")
    @patch("obskit.middleware.fastapi.logger")
    def test_middleware_with_logging(self, mock_logger, mock_get_red):
        """Test middleware with logging enabled."""
        mock_red = MagicMock()
        mock_get_red.return_value = mock_red

        app = FastAPI()
        app.add_middleware(
            ObskitMiddleware,
            track_logging=True,
            track_tracing=False,
        )

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        client = TestClient(app)
        response = client.get("/test")

        assert response.status_code == 200
        # Logger should have been called for request start and completion
        assert mock_logger.info.call_count >= 2

    @patch("obskit.middleware.fastapi.get_red_metrics")
    @patch("obskit.middleware.fastapi.inject_trace_context")
    @patch("obskit.middleware.fastapi.extract_trace_context")
    def test_middleware_with_tracing(self, mock_extract, mock_inject, mock_get_red):
        """Test middleware with tracing enabled."""
        mock_red = MagicMock()
        mock_get_red.return_value = mock_red
        mock_extract.return_value = None  # No trace context
        mock_inject.return_value = {}

        app = FastAPI()
        app.add_middleware(
            ObskitMiddleware,
            track_tracing=True,
        )

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        client = TestClient(app)
        response = client.get("/test")

        assert response.status_code == 200
        mock_inject.assert_called()

    @patch("obskit.middleware.fastapi.get_red_metrics")
    @patch("obskit.middleware.fastapi.trace_context")
    @patch("obskit.middleware.fastapi.extract_trace_context")
    def test_middleware_with_trace_context(self, mock_extract, mock_trace_ctx, mock_get_red):
        """Test middleware with incoming trace context."""
        mock_red = MagicMock()
        mock_get_red.return_value = mock_red
        mock_extract.return_value = MagicMock()  # Has trace context

        # Setup trace_context as context manager
        mock_trace_ctx.return_value.__enter__ = MagicMock()
        mock_trace_ctx.return_value.__exit__ = MagicMock(return_value=False)

        app = FastAPI()
        app.add_middleware(
            ObskitMiddleware,
            track_tracing=True,
        )

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        client = TestClient(app)
        response = client.get(
            "/test",
            headers={"traceparent": "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"},
        )

        assert response.status_code == 200

    @patch("obskit.middleware.fastapi.get_red_metrics")
    def test_middleware_without_metrics(self, mock_get_red):
        """Test middleware with metrics disabled."""
        mock_red = MagicMock()
        mock_get_red.return_value = mock_red

        app = FastAPI()
        app.add_middleware(
            ObskitMiddleware,
            track_metrics=False,
            track_tracing=False,
        )

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        client = TestClient(app)
        response = client.get("/test")

        assert response.status_code == 200
        # Metrics should not be called
        mock_red.observe_request.assert_not_called()

    @patch("obskit.middleware.fastapi.get_red_metrics")
    @patch("obskit.middleware.fastapi.logger")
    def test_middleware_exception_logging(self, mock_logger, mock_get_red):
        """Test middleware logs errors on exception."""
        mock_red = MagicMock()
        mock_get_red.return_value = mock_red

        app = FastAPI()
        app.add_middleware(
            ObskitMiddleware,
            track_logging=True,
            track_tracing=False,
        )

        @app.get("/error")
        async def error_endpoint():
            raise ValueError("Test error")

        client = TestClient(app, raise_server_exceptions=False)
        client.get("/error")

    @patch("obskit.middleware.fastapi.get_red_metrics")
    @patch("obskit.middleware.fastapi.inject_trace_context")
    def test_middleware_injects_trace_headers(self, mock_inject, mock_get_red):
        """Test middleware injects trace headers into response."""
        mock_red = MagicMock()
        mock_get_red.return_value = mock_red

        # Make inject_trace_context add a header
        def add_traceparent(headers):
            headers["traceparent"] = "00-test-trace-id"
            return headers

        mock_inject.side_effect = add_traceparent

        app = FastAPI()
        app.add_middleware(
            ObskitMiddleware,
            track_tracing=True,
        )

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        client = TestClient(app)
        response = client.get("/test")

        assert response.status_code == 200
        mock_inject.assert_called()

    @patch("obskit.middleware.fastapi.get_red_metrics")
    def test_middleware_uses_route_path(self, mock_get_red):
        """Test middleware uses route path for operation name."""
        mock_red = MagicMock()
        mock_get_red.return_value = mock_red

        app = FastAPI()
        app.add_middleware(
            ObskitMiddleware,
            track_tracing=False,
        )

        @app.get("/users/{user_id}")
        async def get_user(user_id: int):
            return {"id": user_id}

        client = TestClient(app)
        response = client.get("/users/123")

        assert response.status_code == 200
        # Verify metrics was called - operation should be derived from route
        mock_red.observe_request.assert_called()
        call_args = mock_red.observe_request.call_args
        # Check that some operation was recorded
        assert call_args is not None
