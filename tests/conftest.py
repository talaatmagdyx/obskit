"""
Pytest configuration and fixtures for obskit tests.

This module provides shared fixtures and configuration for all tests.
"""

import pytest
from unittest.mock import MagicMock, patch


# =============================================================================
# Configuration Reset Fixtures
# =============================================================================

@pytest.fixture(autouse=True)
def reset_obskit_state():
    """Reset obskit global state before and after each test."""
    # Reset before test
    _reset_all_state()
    
    yield
    
    # Reset after test
    _reset_all_state()


def _reset_all_state():
    """Reset all obskit global state."""
    # Reset configuration
    try:
        from obskit.config import reset_settings
        reset_settings()
    except ImportError:
        pass
    
    # Reset RED metrics
    try:
        from obskit.metrics.red import reset_red_metrics
        reset_red_metrics()
    except ImportError:
        pass
    
    # Reset tracing
    try:
        from obskit.tracing.tracer import reset_tracing
        reset_tracing()
    except ImportError:
        pass
    
    # Reset logging factory
    try:
        from obskit.logging.factory import reset_logging_factory
        reset_logging_factory()
    except ImportError:
        pass
    
    # Reset Prometheus registry to avoid duplicate metrics
    try:
        from prometheus_client import REGISTRY
        collectors = list(REGISTRY._names_to_collectors.values())
        for collector in collectors:
            try:
                REGISTRY.unregister(collector)
            except Exception:
                pass
        REGISTRY._names_to_collectors.clear()
    except ImportError:
        pass


# =============================================================================
# Common Fixtures
# =============================================================================

@pytest.fixture
def mock_redis_sync():
    """Provide a mock sync Redis client."""
    mock = MagicMock()
    mock.get.return_value = None
    mock.setex.return_value = True
    # Remove aclose to make it look sync
    del mock.aclose
    return mock


@pytest.fixture
def mock_redis_async():
    """Provide a mock async Redis client."""
    from unittest.mock import AsyncMock
    
    mock = MagicMock()
    mock.get = AsyncMock(return_value=None)
    mock.setex = AsyncMock(return_value=True)
    mock.aclose = AsyncMock()
    return mock


@pytest.fixture
def sample_settings():
    """Provide sample test settings."""
    return {
        "service_name": "test-service",
        "environment": "test",
        "version": "1.0.0",
        "log_level": "DEBUG",
        "log_format": "json",
        "metrics_enabled": True,
        "tracing_enabled": False,
    }


# =============================================================================
# Django Fixtures
# =============================================================================

@pytest.fixture
def django_settings():
    """Configure Django settings for tests."""
    try:
        import django
        from django.conf import settings
        
        if not settings.configured:
            settings.configure(
                DEBUG=True,
                DATABASES={},
                INSTALLED_APPS=[],
                ROOT_URLCONF='',
                OBSKIT={
                    'exclude_paths': ['/health/', '/metrics/'],
                    'track_metrics': True,
                    'track_logging': True,
                    'track_tracing': False,
                },
            )
        return settings
    except ImportError:
        pytest.skip("Django not installed")


# =============================================================================
# Flask Fixtures
# =============================================================================

@pytest.fixture
def flask_app():
    """Provide a test Flask application."""
    try:
        from flask import Flask
        app = Flask(__name__)
        app.config['TESTING'] = True
        return app
    except ImportError:
        pytest.skip("Flask not installed")


# =============================================================================
# Async Fixtures
# =============================================================================

@pytest.fixture
def event_loop():
    """Create an event loop for async tests."""
    import asyncio
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
