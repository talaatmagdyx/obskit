"""API contract tests — ensure the public surface stays stable.

If any of these tests fail, it means the public API changed.
Update the expected values intentionally, not accidentally.
"""

from __future__ import annotations

import re
from collections.abc import Generator

import pytest

from obskit.config import reset_settings
from obskit.core.observability import reset_observability


@pytest.fixture(autouse=True)
def _clean() -> Generator[None, None, None]:
    reset_settings()
    reset_observability()
    yield
    reset_settings()
    reset_observability()


EXPECTED_ALL = sorted(
    [
        "__version__",
        "__version_info__",
        "configure_observability",
        "Observability",
        "ObservabilityConfig",
        "get_observability",
        "reset_observability",
        "ObskitSettings",
        "configure",
        "get_settings",
        "get_logger",
        "get_tracer",
        "get_red_metrics",
        "HealthCheck",
        "HealthChecker",
        "build_health_router",
        "get_correlation_id",
        "set_correlation_id",
        "correlation_context",
        "async_correlation_context",
        "instrument_fastapi",
        "instrument_flask",
        "instrument_django",
        "child_exit",
        "is_multiprocess_mode",
        "make_multiprocess_app",
        "setup_multiprocess_registry",
    ]
)


class TestPublicAPI:
    def test_obskit_all_exports(self) -> None:
        """__all__ must match the expected public surface exactly."""
        import obskit

        assert sorted(obskit.__all__) == EXPECTED_ALL

    def test_configure_observability_returns_observability(self) -> None:
        from obskit import Observability, configure_observability

        obs = configure_observability(service_name="contract-test")
        assert isinstance(obs, Observability)

    def test_observability_has_expected_properties(self) -> None:
        from obskit import configure_observability

        obs = configure_observability(service_name="contract-test")

        # Properties that must exist
        assert hasattr(obs, "config")
        assert hasattr(obs, "tracer")
        assert hasattr(obs, "metrics")
        assert hasattr(obs, "logger")
        assert hasattr(obs, "diagnostics")
        assert hasattr(obs, "shutdown")
        assert callable(obs.shutdown)

    def test_observability_config_is_frozen(self) -> None:
        from obskit import ObservabilityConfig

        cfg = ObservabilityConfig()
        with pytest.raises(AttributeError):
            cfg.service = None  # type: ignore[misc]

    def test_lazy_imports_resolve(self) -> None:
        import obskit

        for name in obskit._LAZY_IMPORTS:
            value = getattr(obskit, name)
            assert callable(value), f"{name} should be callable"

    def test_version_format(self) -> None:
        import obskit

        assert re.match(r"^\d+\.\d+\.\d+", obskit.__version__)

    def test_version_tuple(self) -> None:
        import obskit

        assert isinstance(obskit.__version_info__, tuple)
        assert len(obskit.__version_info__) == 3
        assert all(isinstance(v, int) for v in obskit.__version_info__)

    def test_unknown_attr_raises(self) -> None:
        import obskit

        with pytest.raises(AttributeError, match="no attribute"):
            _ = obskit.nonexistent_thing_xyz  # type: ignore[attr-defined]
