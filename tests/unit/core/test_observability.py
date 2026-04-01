"""Tests for the Observability facade."""

from __future__ import annotations

from collections.abc import Generator

import pytest

from obskit.core.observability import (
    Observability,
    _set_observability,
    get_observability,
    reset_observability,
)
from obskit.core.observability_config import ObservabilityConfig, ServiceConfig


@pytest.fixture(autouse=True)
def _clean_global() -> Generator[None, None, None]:
    """Ensure the global singleton is reset after every test."""
    reset_observability()
    yield
    reset_observability()


class TestObservability:
    def test_config_property(self) -> None:
        cfg = ObservabilityConfig(service=ServiceConfig(name="test-svc"))
        obs = Observability(cfg)
        assert obs.config is cfg
        assert obs.config.service.name == "test-svc"

    def test_tracer_is_lazy(self) -> None:
        obs = Observability(ObservabilityConfig())
        # Accessing .tracer triggers get_tracer()
        tracer = obs.tracer
        assert tracer is not None
        # Second access returns the cached value
        assert obs.tracer is tracer

    def test_metrics_is_lazy(self) -> None:
        obs = Observability(ObservabilityConfig())
        metrics = obs.metrics
        assert metrics is not None
        assert obs.metrics is metrics

    def test_logger_is_lazy(self) -> None:
        obs = Observability(ObservabilityConfig())
        logger = obs.logger
        assert logger is not None
        assert obs.logger is logger

    def test_shutdown(self) -> None:
        obs = Observability(ObservabilityConfig())
        # Should not raise
        obs.shutdown()

    def test_repr(self) -> None:
        cfg = ObservabilityConfig(
            service=ServiceConfig(name="my-svc", environment="prod"),
        )
        obs = Observability(cfg)
        r = repr(obs)
        assert "my-svc" in r
        assert "prod" in r


class TestGlobalSingleton:
    def test_get_observability_creates_default(self) -> None:
        obs = get_observability()
        assert isinstance(obs, Observability)
        assert obs.config.service.name == "unknown"

    def test_set_and_get(self) -> None:
        cfg = ObservabilityConfig(service=ServiceConfig(name="explicit"))
        obs = Observability(cfg)
        _set_observability(obs)
        assert get_observability() is obs

    def test_reset(self) -> None:
        _set_observability(Observability(ObservabilityConfig()))
        reset_observability()
        # After reset, get_observability creates a fresh default
        obs = get_observability()
        assert obs.config.service.name == "unknown"

    def test_get_returns_same_instance(self) -> None:
        obs1 = get_observability()
        obs2 = get_observability()
        assert obs1 is obs2
