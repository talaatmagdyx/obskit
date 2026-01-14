"""
Pytest configuration and fixtures for benchmarks.
"""

from typing import Generator

import pytest

from obskit.core.context import set_correlation_id
from obskit.metrics.red import REDMetrics, reset_red_metrics


def reset_correlation_id() -> None:
    """Reset the correlation ID by setting it to None."""
    set_correlation_id(None)


@pytest.fixture
def red_metrics() -> Generator[REDMetrics, None, None]:
    """Create a fresh REDMetrics instance for benchmarking."""
    reset_red_metrics()
    metrics = REDMetrics(name="bench_service")
    yield metrics
    reset_red_metrics()


@pytest.fixture
def correlation_id() -> Generator[str, None, None]:
    """Set up and return a correlation ID."""
    cid = "bench-correlation-id-12345"
    set_correlation_id(cid)
    yield cid
    reset_correlation_id()


@pytest.fixture(autouse=True)
def reset_context() -> Generator[None, None, None]:
    """Reset context between tests."""
    reset_correlation_id()
    yield
    reset_correlation_id()


# Benchmark groups configuration
def pytest_configure(config: pytest.Config) -> None:
    """Configure pytest markers."""
    config.addinivalue_line(
        "markers", "benchmark_group(name): Mark test with benchmark group"
    )

