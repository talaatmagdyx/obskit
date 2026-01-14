"""Fixtures for integration tests.

These fixtures provide real external services using testcontainers.
"""

from __future__ import annotations

import pytest

# Check if testcontainers is available
try:
    from importlib.util import find_spec

    TESTCONTAINERS_AVAILABLE = find_spec("testcontainers") is not None
except ImportError:
    TESTCONTAINERS_AVAILABLE = False


def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests (require Docker)"
    )


def pytest_collection_modifyitems(config, items):
    """Skip integration tests if testcontainers not available."""
    if not TESTCONTAINERS_AVAILABLE:
        skip_integration = pytest.mark.skip(
            reason="testcontainers not installed (pip install testcontainers)"
        )
        for item in items:
            if "integration" in item.keywords:
                item.add_marker(skip_integration)
