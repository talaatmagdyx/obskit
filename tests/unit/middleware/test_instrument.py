"""Tests for instrument_*() convenience functions."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from obskit.middleware.instrument import instrument_django, instrument_fastapi, instrument_flask


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
