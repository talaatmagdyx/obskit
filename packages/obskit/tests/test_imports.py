"""Smoke tests for the obskit meta-package.

Verifies that the meta-package correctly re-exports symbols from all
sub-packages via the shared namespace.
"""


def test_core_imports() -> None:
    from obskit.config import get_settings
    from obskit.core.types import Status, HealthStatus, CircuitState

    assert get_settings is not None
    assert Status.SUCCESS == "success"
    assert HealthStatus.HEALTHY == "healthy"
    assert CircuitState.CLOSED == "closed"


def test_logging_imports() -> None:
    from obskit.logging import get_logger

    logger = get_logger("test")
    assert logger is not None


def test_metrics_imports() -> None:
    from obskit.metrics import REDMetrics

    assert REDMetrics is not None


def test_tracing_imports() -> None:
    from obskit.tracing import get_tracer, is_tracing_available

    assert get_tracer is not None
    assert is_tracing_available is not None


def test_health_imports() -> None:
    from obskit.health import HealthChecker

    assert HealthChecker is not None


def test_resilience_imports() -> None:
    from obskit.resilience import CircuitBreaker

    assert CircuitBreaker is not None


def test_slo_imports() -> None:
    from obskit.slo import SLOTracker

    assert SLOTracker is not None
