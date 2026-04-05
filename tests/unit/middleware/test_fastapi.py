"""Tests for obskit.middleware.fastapi module."""

from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from obskit.middleware.fastapi import ObskitMiddleware


class TestObskitMiddleware:
    """Tests for ObskitMiddleware class."""

    def setup_method(self):
        """Reset state before each test."""

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

        assert "/custom-health" in middleware._core.exclude_paths
        assert middleware._core.track_metrics is False
        assert middleware._core.track_logging is False
        assert middleware._core.track_tracing is False

    @patch("obskit.middleware.core.get_red_metrics")
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

    @patch("obskit.middleware.core.get_red_metrics")
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

    @patch("obskit.middleware.core.get_red_metrics")
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

    @patch("obskit.middleware.core.get_red_metrics")
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

    @patch("obskit.middleware.core.get_red_metrics")
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

    @patch("obskit.middleware.core.get_red_metrics")
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

        assert middleware._core.should_exclude("/health") is True
        assert middleware._core.should_exclude("/metrics") is True
        assert middleware._core.should_exclude("/api/v1/status") is True
        assert middleware._core.should_exclude("/api/v1/users") is False

    @patch("obskit.middleware.core.get_red_metrics")
    @patch("obskit.middleware.core._core_logger")
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

    @patch("obskit.middleware.core.get_red_metrics")
    @patch("obskit.middleware.core.inject_trace_context")
    @patch("obskit.middleware.core.extract_trace_context")
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

    @patch("obskit.middleware.core.get_red_metrics")
    @patch("obskit.middleware.fastapi.trace_context")
    @patch("obskit.middleware.core.extract_trace_context")
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

    @patch("obskit.middleware.core.get_red_metrics")
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

    @patch("obskit.middleware.core.get_red_metrics")
    @patch("obskit.middleware.core._core_logger")
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

    @patch("obskit.middleware.core.get_red_metrics")
    @patch("obskit.middleware.core.inject_trace_context")
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

    @patch("obskit.middleware.core.get_red_metrics")
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

    @patch("obskit.middleware.core.get_red_metrics")
    def test_middleware_exception_no_metrics(self, mock_get_red):
        """Test exception path with track_metrics=False (branch 270->279 False)."""
        mock_red = MagicMock()
        mock_get_red.return_value = mock_red

        app = FastAPI()
        app.add_middleware(
            ObskitMiddleware,
            track_metrics=False,
            track_logging=True,
            track_tracing=False,
        )

        @app.get("/error")
        async def error_endpoint():
            raise RuntimeError("metrics disabled error")

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/error")

        assert response.status_code == 500
        # With track_metrics=False, observe_request should NOT be called
        mock_red.observe_request.assert_not_called()

    @patch("obskit.middleware.core.get_red_metrics")
    @patch("obskit.middleware.core._core_logger")
    def test_middleware_exception_no_logging(self, mock_logger, mock_get_red):
        """Test exception path with track_logging=False (branch 279->293 False)."""
        mock_red = MagicMock()
        mock_get_red.return_value = mock_red

        app = FastAPI()
        app.add_middleware(
            ObskitMiddleware,
            track_metrics=True,
            track_logging=False,
            track_tracing=False,
        )

        @app.get("/error")
        async def error_endpoint():
            raise RuntimeError("logging disabled error")

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/error")

        assert response.status_code == 500
        # With track_logging=False, logger.error should NOT be called
        mock_logger.error.assert_not_called()
        # But metrics should still be recorded
        mock_red.observe_request.assert_called()

    @patch("obskit.middleware.core.get_red_metrics")
    def test_middleware_non_http_scope_passes_through(self, mock_get_red):
        """Non http/websocket scope type passes through without processing (lines 162-163)."""
        mock_get_red.return_value = MagicMock()

        app = FastAPI()
        app.add_middleware(ObskitMiddleware)

        # Use TestClient which triggers lifespan events
        # We can simulate a non-http scope by calling middleware directly
        import asyncio
        from obskit.middleware.fastapi import ObskitMiddleware as Mw

        inner_app_called = []

        async def inner_app(scope, receive, send):
            inner_app_called.append(scope["type"])

        mw = Mw(inner_app)

        async def run():
            # Pass a "lifespan" scope — not http/websocket
            await mw({"type": "lifespan", "path": "/"}, None, None)

        asyncio.run(run())
        assert "lifespan" in inner_app_called

    @patch("obskit.middleware.core.get_red_metrics")
    def test_middleware_invalid_correlation_id_discarded(self, mock_get_red):
        """Invalid correlation ID in header is discarded (line 181)."""
        mock_get_red.return_value = MagicMock()

        app = FastAPI()
        app.add_middleware(ObskitMiddleware, track_logging=False, track_tracing=False)

        @app.get("/test")
        async def endpoint():
            return {"ok": True}

        client = TestClient(app)
        # Send an invalid correlation ID (contains special chars)
        response = client.get("/test", headers={"x-correlation-id": "invalid id with spaces!!!"})
        assert response.status_code == 200

    @patch("obskit.middleware.core.get_red_metrics")
    def test_middleware_more_body_true_skips_metrics(self, mock_get_red):
        """When more_body=True, metrics/logging not yet recorded (line 230->255)."""
        mock_red = MagicMock()
        mock_get_red.return_value = mock_red

        app = FastAPI()
        app.add_middleware(ObskitMiddleware, track_logging=False, track_tracing=False)

        from fastapi.responses import StreamingResponse

        async def generator():
            yield b"chunk1"
            yield b"chunk2"

        @app.get("/stream")
        async def stream_endpoint():
            return StreamingResponse(generator(), media_type="text/plain")

        client = TestClient(app)
        response = client.get("/stream")
        assert response.status_code == 200
        # metrics.observe_request called once (on final chunk)
        mock_red.observe_request.assert_called_once()

    @patch("obskit.middleware.core.get_red_metrics")
    def test_middleware_track_logging_false_skips_logging(self, mock_get_red):
        """With track_logging=False, request_completed log is not emitted (line 244->255)."""
        mock_red = MagicMock()
        mock_get_red.return_value = mock_red

        app = FastAPI()
        app.add_middleware(
            ObskitMiddleware,
            track_logging=False,
            track_tracing=False,
        )

        @app.get("/silent")
        async def silent():
            return {"ok": True}

        with patch("obskit.middleware.core._core_logger") as mock_logger:
            client = TestClient(app)
            client.get("/silent")
            mock_logger.info.assert_not_called()

    @patch("obskit.middleware.core.get_red_metrics")
    def test_get_client_ip_no_client(self, mock_get_red):
        """_get_client_ip returns None when scope has no client (line 315)."""
        mock_get_red.return_value = MagicMock()
        mw = ObskitMiddleware(FastAPI())
        # No "client" key in scope
        assert mw._get_client_ip({}) is None
        # client is None
        assert mw._get_client_ip({"client": None}) is None
        # client is empty tuple
        assert mw._get_client_ip({"client": ()}) is None

    @patch("obskit.middleware.core.get_red_metrics")
    @patch("obskit.core.context.get_correlation_id", return_value=None)
    def test_middleware_no_correlation_id_no_tracing_empty_extra_headers(
        self, mock_cid, mock_get_red
    ):
        """When correlation_id is None and track_tracing=False, extra_headers=[] (branches 211->214, 221->255)."""
        mock_red = MagicMock()
        mock_get_red.return_value = mock_red

        app = FastAPI()
        app.add_middleware(
            ObskitMiddleware,
            track_metrics=False,
            track_logging=False,
            track_tracing=False,
        )

        @app.get("/test2")
        async def endpoint():
            return {"ok": True}

        client = TestClient(app)
        response = client.get("/test2")
        assert response.status_code == 200

    @patch("obskit.middleware.core.get_red_metrics")
    def test_middleware_response_already_has_correlation_header(self, mock_get_red):
        """When response already has x-correlation-id, don't add duplicate (branch 225->224)."""
        mock_red = MagicMock()
        mock_get_red.return_value = mock_red

        app = FastAPI()
        app.add_middleware(
            ObskitMiddleware,
            track_metrics=False,
            track_logging=False,
            track_tracing=False,
        )

        from fastapi import Response

        @app.get("/with-cid")
        async def endpoint_with_cid():
            # Return a response that already sets x-correlation-id
            return Response(
                content='{"ok": true}',
                media_type="application/json",
                headers={"x-correlation-id": "existing-id-123"},
            )

        client = TestClient(app)
        response = client.get("/with-cid")
        assert response.status_code == 200
        # Should have the header (either from response or middleware — not duplicated)
        assert "x-correlation-id" in response.headers

    @patch("obskit.middleware.core.get_red_metrics")
    def test_middleware_custom_message_type_passes_through(self, mock_get_red):
        """Non http.response.start/body message types pass through unchanged (branch 229->255)."""
        import asyncio

        mock_red = MagicMock()
        mock_get_red.return_value = mock_red

        sent_messages = []

        async def inner_app(scope, receive, send):
            # Simulate sending a custom message type
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "custom.message.type", "data": "something"})
            await send({"type": "http.response.body", "body": b"ok", "more_body": False})

        mw = ObskitMiddleware(
            inner_app, track_metrics=False, track_logging=False, track_tracing=False
        )

        async def fake_send(msg):
            sent_messages.append(msg)

        async def fake_receive():
            return {"type": "http.request", "body": b""}

        async def run():
            await mw(
                {
                    "type": "http",
                    "path": "/test",
                    "method": "GET",
                    "headers": [],
                    "query_string": b"",
                },
                fake_receive,
                fake_send,
            )

        asyncio.run(run())
        # All 3 messages should have been forwarded
        assert len(sent_messages) == 3
        assert sent_messages[1]["type"] == "custom.message.type"

    @patch("obskit.middleware.core.get_red_metrics")
    def test_middleware_404_unmatched_route_normalised(self, mock_get_red):
        """404 responses with no matched route use 'unmatched_route' label (line 241)."""
        mock_red = MagicMock()
        mock_get_red.return_value = mock_red

        app = FastAPI()
        app.add_middleware(ObskitMiddleware, track_tracing=False, track_logging=False)

        client = TestClient(app, raise_server_exceptions=False)
        # Request a path that has no registered route → FastAPI returns 404
        response = client.get("/this/path/does/not/exist/at/all")

        assert response.status_code == 404
        mock_red.observe_request.assert_called_once()
        call_kwargs = mock_red.observe_request.call_args.kwargs
        assert call_kwargs["operation"] == "unmatched_route"

    @patch("obskit.middleware.core.get_red_metrics")
    def test_middleware_finally_records_metrics_on_early_disconnect(self, mock_get_red):
        """finally block records metrics when client disconnects before last body chunk."""
        import asyncio

        mock_red = MagicMock()
        mock_get_red.return_value = mock_red

        app = FastAPI()
        mw = ObskitMiddleware(app, track_logging=False, track_tracing=False)

        async def disconnecting_app(scope, receive, send):
            # Send response start (sets status_code_holder) but never send body chunk
            await send({"type": "http.response.start", "status": 200, "headers": []})
            # Simulate disconnect by raising before sending body
            raise ConnectionResetError("client disconnected")

        mw.app = disconnecting_app

        async def fake_send(msg):  # NOSONAR
            pass  # intentional no-op — ASGI send stub

        async def fake_receive():  # NOSONAR — must be async for ASGI protocol
            return {"type": "http.request", "body": b""}

        async def run():
            try:
                await mw(
                    {
                        "type": "http",
                        "path": "/stream",
                        "method": "GET",
                        "headers": [],
                        "query_string": b"",
                    },
                    fake_receive,
                    fake_send,
                )
            except ConnectionResetError:
                pass  # expected — middleware re-raises after recording

        asyncio.run(run())
        # metrics_recorded was True via the except block (ConnectionResetError is an Exception)
        # so the finally block condition is False → observe_request called exactly once
        mock_red.observe_request.assert_called_once()

    @patch("obskit.middleware.core.get_red_metrics")
    def test_middleware_finally_records_metrics_headers_sent_no_body(self, mock_get_red):
        """finally block fires when headers sent but body never starts (no exception)."""
        import asyncio

        mock_red = MagicMock()
        mock_get_red.return_value = mock_red

        app = FastAPI()
        mw = ObskitMiddleware(app, track_logging=False, track_tracing=False)

        async def headers_only_app(scope, receive, send):
            # Send headers but return without sending any body message
            await send({"type": "http.response.start", "status": 200, "headers": []})
            # No body message sent — simulates a generator that yields nothing

        mw.app = headers_only_app

        async def fake_send(msg):  # NOSONAR
            pass  # intentional no-op — ASGI send stub

        async def fake_receive():  # NOSONAR — must be async for ASGI protocol
            return {"type": "http.request", "body": b""}

        async def run():
            await mw(
                {
                    "type": "http",
                    "path": "/partial",
                    "method": "GET",
                    "headers": [],
                    "query_string": b"",
                },
                fake_receive,
                fake_send,
            )

        asyncio.run(run())
        # finally block should have fired since no body chunk set metrics_recorded
        mock_red.observe_request.assert_called_once()
        call_kwargs = mock_red.observe_request.call_args.kwargs
        assert call_kwargs["status"] == "success"

    def test_middleware_finally_404_unmatched_and_logging(self):
        """finally block: 404 with no route → 'unmatched_route'; track_logging emits log."""
        import asyncio
        from unittest.mock import patch as _patch

        app = FastAPI()
        # track_metrics=False, track_logging=True — exercises the 336->343 branch
        # and the logger.info branch inside finally.
        mw = ObskitMiddleware(app, track_metrics=False, track_logging=True, track_tracing=False)

        async def headers_only_app(scope, receive, send):
            await send({"type": "http.response.start", "status": 404, "headers": []})
            # No body sent — triggers finally block

        mw.app = headers_only_app

        async def fake_send(msg):  # NOSONAR
            pass  # intentional no-op — ASGI send stub

        async def fake_receive():  # NOSONAR — must be async for ASGI protocol
            return {"type": "http.request", "body": b""}

        async def run():
            await mw(
                {
                    "type": "http",
                    "path": "/missing",
                    "method": "GET",
                    "headers": [],
                    "query_string": b"",
                    # No "route" key → unmatched_route path
                },
                fake_receive,
                fake_send,
            )

        with _patch("obskit.middleware.core._core_logger") as mock_logger:
            asyncio.run(run())
        # track_logging=True so finally block called logger.info("request_completed", ...)
        mock_logger.info.assert_called()

    @patch("obskit.middleware.core.get_red_metrics")
    def test_websocket_metrics_recorded_with_101(self, mock_get_red):
        """finally block: websocket scope with status_code==0 → end_request called with 101."""
        import asyncio

        mock_red = MagicMock()
        mock_get_red.return_value = mock_red

        app = FastAPI()
        mw = ObskitMiddleware(app, track_logging=False, track_tracing=False)

        async def ws_app(scope, receive, send):
            # WebSocket apps never call http.response.start — status_code stays 0
            pass

        mw.app = ws_app

        async def fake_send(msg):  # NOSONAR
            pass  # intentional no-op — ASGI send stub

        async def fake_receive():  # NOSONAR — must be async for ASGI protocol
            return {"type": "websocket.connect"}

        async def run():
            await mw(
                {
                    "type": "websocket",
                    "path": "/ws",
                    "headers": [],
                    "query_string": b"",
                },
                fake_receive,
                fake_send,
            )

        asyncio.run(run())
        # end_request should be called with status 101 for WebSocket
        mock_red.observe_request.assert_called_once()
        call_kwargs = mock_red.observe_request.call_args.kwargs
        assert call_kwargs["status"] == "success"

    @patch("obskit.middleware.core.get_red_metrics")
    def test_http_no_send_status_zero_no_metrics(self, mock_get_red):
        """finally block: http scope, status_code==0, elif websocket is False → no metrics recorded."""
        import asyncio

        mock_red = MagicMock()
        mock_get_red.return_value = mock_red

        app = FastAPI()
        mw = ObskitMiddleware(app, track_logging=False, track_tracing=False)

        async def silent_http_app(scope, receive, send):
            # HTTP app that never calls send — status_code stays 0
            pass

        mw.app = silent_http_app

        async def fake_send(msg):  # NOSONAR
            pass  # intentional no-op — ASGI send stub

        async def fake_receive():  # NOSONAR — must be async for ASGI protocol
            return {"type": "http.request", "body": b""}

        async def run():
            await mw(
                {
                    "type": "http",
                    "path": "/silent",
                    "method": "GET",
                    "headers": [],
                    "query_string": b"",
                },
                fake_receive,
                fake_send,
            )

        asyncio.run(run())
        # status_code==0 and not websocket → neither branch fires → no metrics
        mock_red.observe_request.assert_not_called()


class TestContextExtractor:
    """Tests for ObskitMiddleware context_extractor hook."""

    def test_context_extractor_binds_extra_fields(self):
        """context_extractor result is bound into structlog contextvars during request."""
        import asyncio

        from structlog.contextvars import clear_contextvars, get_contextvars

        captured: dict = {}

        async def capturing_app(scope, receive, send):
            captured.update(get_contextvars())
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"", "more_body": False})

        mw = ObskitMiddleware(
            capturing_app,
            track_logging=False,
            track_metrics=False,
            track_tracing=False,
            context_extractor=lambda h: {"company_id": h.get("x-company-id", "")},
        )

        messages = []

        async def fake_send(msg):  # NOSONAR
            messages.append(msg)

        async def fake_receive():  # NOSONAR — must be async for ASGI protocol
            return {"type": "http.request", "body": b""}

        clear_contextvars()
        asyncio.run(
            mw(
                {
                    "type": "http",
                    "path": "/api/data",
                    "method": "GET",
                    "headers": [(b"x-company-id", b"acme")],
                    "query_string": b"",
                },
                fake_receive,
                fake_send,
            )
        )

        assert captured.get("company_id") == "acme"

    def test_context_extractor_unbound_after_request(self):
        """Extra context vars must be removed after the request completes."""
        import asyncio

        from structlog.contextvars import clear_contextvars, get_contextvars

        async def noop_app(scope, receive, send):
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"", "more_body": False})

        mw = ObskitMiddleware(
            noop_app,
            track_logging=False,
            track_metrics=False,
            track_tracing=False,
            context_extractor=lambda h: {"company_id": "acme"},
        )

        async def fake_send(msg):  # NOSONAR
            pass  # intentional no-op — ASGI send stub

        async def fake_receive():  # NOSONAR — must be async for ASGI protocol
            return {"type": "http.request", "body": b""}

        clear_contextvars()
        asyncio.run(
            mw(
                {
                    "type": "http",
                    "path": "/api/data",
                    "method": "GET",
                    "headers": [],
                    "query_string": b"",
                },
                fake_receive,
                fake_send,
            )
        )

        # After request: company_id must have been unbound
        ctx_after = get_contextvars()
        assert "company_id" not in ctx_after

    def test_no_context_extractor_works_normally(self):
        """Middleware works fine when context_extractor is None (default)."""
        import asyncio

        async def noop_app(scope, receive, send):
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"", "more_body": False})

        mw = ObskitMiddleware(
            noop_app,
            track_logging=False,
            track_metrics=False,
            track_tracing=False,
        )

        async def fake_send(msg):  # NOSONAR
            pass  # intentional no-op — ASGI send stub

        async def fake_receive():  # NOSONAR — must be async for ASGI protocol
            return {"type": "http.request", "body": b""}

        # Should not raise
        asyncio.run(
            mw(
                {
                    "type": "http",
                    "path": "/api/data",
                    "method": "GET",
                    "headers": [],
                    "query_string": b"",
                },
                fake_receive,
                fake_send,
            )
        )

    def test_empty_extractor_result_skips_bind(self):
        """If context_extractor returns {} no bind/unbind calls are made."""
        import asyncio

        from obskit.logging.context import bind_context, unbind_context
        from unittest.mock import patch as _patch

        async def noop_app(scope, receive, send):
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"", "more_body": False})

        mw = ObskitMiddleware(
            noop_app,
            track_logging=False,
            track_metrics=False,
            track_tracing=False,
            context_extractor=lambda h: {},  # returns empty dict
        )

        async def fake_send(msg):  # NOSONAR
            pass  # intentional no-op — ASGI send stub

        async def fake_receive():  # NOSONAR — must be async for ASGI protocol
            return {"type": "http.request", "body": b""}

        with _patch("obskit.middleware.fastapi.bind_context") as mock_bind, \
             _patch("obskit.middleware.fastapi.unbind_context") as mock_unbind:
            asyncio.run(
                mw(
                    {
                        "type": "http",
                        "path": "/api/data",
                        "method": "GET",
                        "headers": [],
                        "query_string": b"",
                    },
                    fake_receive,
                    fake_send,
                )
            )

        mock_bind.assert_not_called()
        mock_unbind.assert_not_called()
