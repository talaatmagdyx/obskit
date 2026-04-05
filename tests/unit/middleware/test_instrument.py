"""Tests for instrument_*() convenience functions."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from obskit.middleware.instrument import (
    configure_app_observability,
    instrument_django,
    instrument_fastapi,
    instrument_flask,
)


class TestInstrumentFastapi:
    def test_adds_middleware(self) -> None:
        mock_app = MagicMock()
        instrument_fastapi(mock_app)
        mock_app.add_middleware.assert_called_once()

    def test_passes_exclude_paths(self) -> None:
        mock_app = MagicMock()
        instrument_fastapi(mock_app, exclude_paths=["/custom"])
        call_kwargs = mock_app.add_middleware.call_args[1]
        assert call_kwargs["exclude_paths"] == ["/custom"]

    def test_passes_tracking_flags(self) -> None:
        mock_app = MagicMock()
        instrument_fastapi(
            mock_app,
            track_metrics=False,
            track_logging=False,
            track_tracing=False,
        )
        call_kwargs = mock_app.add_middleware.call_args[1]
        assert call_kwargs["track_metrics"] is False
        assert call_kwargs["track_logging"] is False
        assert call_kwargs["track_tracing"] is False


class TestInstrumentFlask:
    @patch("obskit.middleware.flask.ObskitFlaskMiddleware")
    def test_creates_and_inits(self, mock_cls: MagicMock) -> None:
        mock_instance = MagicMock()
        mock_cls.return_value = mock_instance
        mock_app = MagicMock()

        instrument_flask(mock_app)

        mock_cls.assert_called_once()
        mock_instance.init_app.assert_called_once_with(mock_app)

    @patch("obskit.middleware.flask.ObskitFlaskMiddleware")
    def test_passes_kwargs(self, mock_cls: MagicMock) -> None:
        mock_cls.return_value = MagicMock()
        mock_app = MagicMock()

        instrument_flask(
            mock_app,
            exclude_paths=["/custom"],
            track_metrics=False,
        )

        call_kwargs = mock_cls.call_args[1]
        assert call_kwargs["exclude_paths"] == ["/custom"]
        assert call_kwargs["track_metrics"] is False


class TestInstrumentDjango:
    @patch("obskit.middleware.django.get_obskit_middleware")
    def test_returns_middleware_class(self, mock_factory: MagicMock) -> None:
        mock_factory.return_value = type("FakeMW", (), {})
        result = instrument_django(exclude_paths=["/custom"])
        mock_factory.assert_called_once_with(
            exclude_paths=["/custom"],
            track_metrics=True,
            track_logging=True,
            track_tracing=True,
        )
        assert isinstance(result, type)


class TestConfigureAppObservability:
    def test_adds_middleware(self) -> None:
        from fastapi import FastAPI

        app = FastAPI()
        original_add = app.add_middleware
        calls = []

        def tracking_add(cls, **kw):
            calls.append(cls)
            return original_add(cls, **kw)

        app.add_middleware = tracking_add
        configure_app_observability(app)

        from obskit.middleware.fastapi import ObskitMiddleware

        assert any(c is ObskitMiddleware for c in calls)

    def test_metrics_endpoint_accessible(self) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        app = FastAPI()

        @app.get("/test")
        async def root():
            return {}

        configure_app_observability(app)

        client = TestClient(app)
        response = client.get("/metrics")
        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]

    def test_custom_metrics_path(self) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        app = FastAPI()
        configure_app_observability(app, metrics_path="/prom/metrics")

        client = TestClient(app)
        assert client.get("/prom/metrics").status_code == 200
        assert client.get("/metrics").status_code == 404

    def test_exclude_paths_forwarded(self) -> None:
        mock_app = MagicMock()
        configure_app_observability(mock_app, exclude_paths=["/internal"])
        call_kwargs = mock_app.add_middleware.call_args[1]
        assert call_kwargs["exclude_paths"] == ["/internal"]

    def test_tracking_flags_forwarded(self) -> None:
        mock_app = MagicMock()
        configure_app_observability(
            mock_app,
            track_metrics=False,
            track_logging=False,
            track_tracing=False,
        )
        call_kwargs = mock_app.add_middleware.call_args[1]
        assert call_kwargs["track_metrics"] is False
        assert call_kwargs["track_logging"] is False
        assert call_kwargs["track_tracing"] is False

    def test_default_metrics_path_is_slash_metrics(self) -> None:
        mock_app = MagicMock()
        configure_app_observability(mock_app)
        mock_app.add_api_route.assert_called_once()
        route_path = mock_app.add_api_route.call_args[0][0]
        assert route_path == "/metrics"

    def test_context_extractor_forwarded(self) -> None:
        mock_app = MagicMock()
        extractor = lambda h: {"company_id": h.get("x-company-id", "")}
        configure_app_observability(mock_app, context_extractor=extractor)
        call_kwargs = mock_app.add_middleware.call_args[1]
        assert call_kwargs["context_extractor"] is extractor

    def test_context_extractor_none_not_in_kwargs(self) -> None:
        mock_app = MagicMock()
        configure_app_observability(mock_app)
        call_kwargs = mock_app.add_middleware.call_args[1]
        assert "context_extractor" not in call_kwargs


class TestInstrumentFastapiContextExtractor:
    def test_context_extractor_forwarded_to_middleware(self) -> None:
        mock_app = MagicMock()
        extractor = lambda h: {"company_id": h.get("x-company-id", "")}
        instrument_fastapi(mock_app, context_extractor=extractor)
        call_kwargs = mock_app.add_middleware.call_args[1]
        assert call_kwargs["context_extractor"] is extractor

    def test_context_extractor_none_not_in_kwargs(self) -> None:
        mock_app = MagicMock()
        instrument_fastapi(mock_app)
        call_kwargs = mock_app.add_middleware.call_args[1]
        assert "context_extractor" not in call_kwargs
