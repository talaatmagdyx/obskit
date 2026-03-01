"""Smoke tests for the obskit meta-package.

Verifies that the meta-package correctly re-exports symbols from all
sub-packages via the shared namespace.
"""


def test_core_imports() -> None:
    from obskit.config import get_settings
    from obskit.core.types import Status, HealthStatus, CircuitState

    assert Status.SUCCESS == "success"
    assert HealthStatus.HEALTHY == "healthy"
    assert CircuitState.CLOSED == "closed"


def test_logging_imports() -> None:
    from obskit.logging import get_logger

    _logger = get_logger("test")


def test_metrics_imports() -> None:
    from obskit.metrics import REDMetrics



def test_tracing_imports() -> None:
    from obskit.tracing import get_tracer, is_tracing_available



def test_health_imports() -> None:
    from obskit.health import HealthChecker



def test_resilience_imports() -> None:
    from obskit.resilience import CircuitBreaker



def test_slo_imports() -> None:
    from obskit.slo import SLOTracker

