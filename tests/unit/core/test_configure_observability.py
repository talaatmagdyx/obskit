"""Tests for configure_observability() entrypoint."""

from __future__ import annotations

import pytest

from obskit.config import configure_observability, reset_settings
from obskit.core.observability import Observability, get_observability, reset_observability


@pytest.fixture(autouse=True)
def _clean() -> None:
    reset_settings()
    reset_observability()
    yield  # type: ignore[misc]
    reset_settings()
    reset_observability()


class TestConfigureObservability:
    def test_returns_observability(self) -> None:
        obs = configure_observability(service_name="test-svc")
        assert isinstance(obs, Observability)
        assert obs.config.service.name == "test-svc"

    def test_sets_global(self) -> None:
        obs = configure_observability(service_name="global-svc")
        assert get_observability() is obs

    def test_preserves_settings_global(self) -> None:
        from obskit.config import get_settings

        configure_observability(service_name="settings-svc")
        settings = get_settings()
        assert settings.service_name == "settings-svc"

    def test_strict_mode_raises(self) -> None:
        with pytest.raises(ValueError, match="error"):
            configure_observability(
                strict=True,
                tracing_enabled=True,
                otlp_endpoint="not-a-url",
            )

    def test_invalid_kwarg_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown"):
            configure_observability(nonexistent_field="oops")

    def test_all_config_sections_populated(self) -> None:
        obs = configure_observability(
            service_name="full-svc",
            environment="production",
            version="3.0.0",
            log_level="DEBUG",
            log_format="console",
            trace_sample_rate=0.5,
        )
        assert obs.config.service.name == "full-svc"
        assert obs.config.service.environment == "production"
        assert obs.config.service.version == "3.0.0"
        assert obs.config.logging.level == "DEBUG"
        assert obs.config.logging.format == "console"
        assert obs.config.tracing.sample_rate == 0.5
