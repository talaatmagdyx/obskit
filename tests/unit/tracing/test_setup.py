"""Tests for obskit.tracing.setup — unified setup_tracing() entry point."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from obskit.tracing.auto import uninstrument_all
from obskit.tracing.setup import setup_tracing
from obskit.tracing.tracer import reset_tracing


class TestSetupTracingIntegration:
    """setup_tracing() orchestrates configure_tracing + apply_instrumentors."""

    def setup_method(self) -> None:
        reset_tracing()
        uninstrument_all()

    def teardown_method(self) -> None:
        reset_tracing()
        uninstrument_all()

    # --- basic behaviour ---------------------------------------------------

    def test_returns_empty_list_when_auto_instrument_false(self) -> None:
        """No instrumentation applied when auto_instrument=False."""
        with (
            patch("obskit.tracing.setup.configure_tracing") as mock_cfg,
            patch("obskit.tracing.setup.apply_instrumentors") as mock_apply,
        ):
            result = setup_tracing(auto_instrument=False)

        mock_cfg.assert_called_once()
        mock_apply.assert_not_called()
        assert result == []

    def test_calls_configure_tracing(self) -> None:
        """setup_tracing always calls configure_tracing."""
        with (
            patch("obskit.tracing.setup.configure_tracing") as mock_cfg,
            patch("obskit.tracing.setup.apply_instrumentors", return_value=[]),
        ):
            setup_tracing()

        mock_cfg.assert_called_once()

    def test_passes_service_name_to_configure(self) -> None:
        """service_name is forwarded to configure_tracing."""
        with (
            patch("obskit.tracing.setup.configure_tracing") as mock_cfg,
            patch("obskit.tracing.setup.apply_instrumentors", return_value=[]),
        ):
            setup_tracing(service_name="my-svc", auto_instrument=False)

        mock_cfg.assert_called_once_with(
            service_name="my-svc",
            otlp_endpoint=None,
            debug=False,
            sample_rate=1.0,
        )

    def test_passes_endpoint_to_configure(self) -> None:
        """exporter_endpoint is forwarded as otlp_endpoint."""
        with (
            patch("obskit.tracing.setup.configure_tracing") as mock_cfg,
            patch("obskit.tracing.setup.apply_instrumentors", return_value=[]),
        ):
            setup_tracing(exporter_endpoint="http://tempo:4317", auto_instrument=False)

        mock_cfg.assert_called_once_with(
            service_name=None,
            otlp_endpoint="http://tempo:4317",
            debug=False,
            sample_rate=1.0,
        )

    def test_passes_instrument_list_to_apply(self) -> None:
        """instrument kwarg is forwarded to apply_instrumentors."""
        with (
            patch("obskit.tracing.setup.configure_tracing"),
            patch("obskit.tracing.setup.apply_instrumentors", return_value=["redis"]) as mock_apply,
        ):
            result = setup_tracing(instrument=["redis"])

        mock_apply.assert_called_once_with(["redis"])
        assert result == ["redis"]

    def test_passes_none_instrument_to_apply(self) -> None:
        """When instrument is None, apply_instrumentors receives None."""
        with (
            patch("obskit.tracing.setup.configure_tracing"),
            patch("obskit.tracing.setup.apply_instrumentors", return_value=[]) as mock_apply,
        ):
            setup_tracing(instrument=None)

        mock_apply.assert_called_once_with(None)

    def test_returns_applied_names(self) -> None:
        """Return value comes from apply_instrumentors."""
        with (
            patch("obskit.tracing.setup.configure_tracing"),
            patch(
                "obskit.tracing.setup.apply_instrumentors",
                return_value=["fastapi", "redis"],
            ),
        ):
            result = setup_tracing()

        assert result == ["fastapi", "redis"]

    # --- debug and sample_rate forwarding ----------------------------------

    def test_passes_debug_true_to_configure(self) -> None:
        """debug=True is forwarded to configure_tracing."""
        with (
            patch("obskit.tracing.setup.configure_tracing") as mock_cfg,
            patch("obskit.tracing.setup.apply_instrumentors", return_value=[]),
        ):
            setup_tracing(debug=True, auto_instrument=False)

        mock_cfg.assert_called_once_with(
            service_name=None,
            otlp_endpoint=None,
            debug=True,
            sample_rate=1.0,
        )

    def test_passes_sample_rate_to_configure(self) -> None:
        """sample_rate is forwarded to configure_tracing."""
        with (
            patch("obskit.tracing.setup.configure_tracing") as mock_cfg,
            patch("obskit.tracing.setup.apply_instrumentors", return_value=[]),
        ):
            setup_tracing(sample_rate=0.1, auto_instrument=False)

        mock_cfg.assert_called_once_with(
            service_name=None,
            otlp_endpoint=None,
            debug=False,
            sample_rate=0.1,
        )

    def test_debug_and_sample_rate_together(self) -> None:
        """debug + sample_rate are both forwarded correctly."""
        with (
            patch("obskit.tracing.setup.configure_tracing") as mock_cfg,
            patch("obskit.tracing.setup.apply_instrumentors", return_value=[]),
        ):
            setup_tracing(debug=True, sample_rate=0.5, auto_instrument=False)

        mock_cfg.assert_called_once_with(
            service_name=None,
            otlp_endpoint=None,
            debug=True,
            sample_rate=0.5,
        )

    # --- full kwargs combination -------------------------------------------

    def test_all_kwargs_forwarded_correctly(self) -> None:
        """All kwargs reach the right downstream call."""
        with (
            patch("obskit.tracing.setup.configure_tracing") as mock_cfg,
            patch(
                "obskit.tracing.setup.apply_instrumentors",
                return_value=["fastapi"],
            ) as mock_apply,
        ):
            result = setup_tracing(
                exporter_endpoint="http://otel:4317",
                auto_instrument=True,
                instrument=["fastapi"],
                service_name="order-svc",
                debug=True,
                sample_rate=0.2,
            )

        mock_cfg.assert_called_once_with(
            service_name="order-svc",
            otlp_endpoint="http://otel:4317",
            debug=True,
            sample_rate=0.2,
        )
        mock_apply.assert_called_once_with(["fastapi"])
        assert result == ["fastapi"]

    # --- real integration (no mocks) --------------------------------------

    def test_real_call_auto_instrument_false(self) -> None:
        """Real call with auto_instrument=False must not raise."""
        result = setup_tracing(auto_instrument=False)
        assert result == []

    def test_real_call_with_empty_instrument_list(self) -> None:
        """Explicit empty list → nothing applied, no error."""
        result = setup_tracing(instrument=[], auto_instrument=True)
        assert result == []

    def test_real_call_default(self) -> None:
        """Default call (no OTel instrumentation packages installed) succeeds."""
        result = setup_tracing()
        assert isinstance(result, list)

    def test_real_call_debug_mode(self) -> None:
        """Real call with debug=True must not raise."""
        result = setup_tracing(debug=True, auto_instrument=False)
        assert result == []

    def test_real_call_sample_rate(self) -> None:
        """Real call with sample_rate must not raise."""
        result = setup_tracing(sample_rate=0.5, auto_instrument=False)
        assert result == []

    def test_real_call_debug_and_sample_rate(self) -> None:
        """Real call with debug=True + sample_rate must not raise."""
        result = setup_tracing(debug=True, sample_rate=0.1, auto_instrument=False)
        assert result == []
