"""Tests for obskit.logging.factory module."""

import pytest
from unittest.mock import MagicMock, patch

from obskit.logging.factory import (
    get_available_backends,
    configure_logging_backend,
    get_logger_from_factory,
    reset_logging_factory,
    register_backend,
)


class TestGetAvailableBackends:
    """Tests for get_available_backends function."""

    def test_returns_list(self):
        """Test that function returns a list."""
        backends = get_available_backends()
        assert isinstance(backends, list)

    def test_structlog_available(self):
        """Test structlog is in available backends."""
        backends = get_available_backends()
        assert "structlog" in backends


class TestConfigureLoggingBackend:
    """Tests for configure_logging_backend function."""

    def setup_method(self):
        """Reset factory before each test."""
        reset_logging_factory()

    def teardown_method(self):
        """Reset factory after each test."""
        reset_logging_factory()

    def test_configure_structlog(self):
        """Test configuring structlog backend."""
        configure_logging_backend(backend="structlog")

    def test_configure_with_invalid_backend(self):
        """Test configuring with invalid backend raises ImportError."""
        with pytest.raises(ImportError):
            configure_logging_backend(backend="nonexistent")


class TestGetLoggerFromFactory:
    """Tests for get_logger_from_factory function."""

    def setup_method(self):
        """Reset factory and configure before each test."""
        reset_logging_factory()
        # Pre-configure to avoid auto-detection delay
        configure_logging_backend(backend="structlog")

    def teardown_method(self):
        """Reset factory after each test."""
        reset_logging_factory()

    def test_get_logger(self):
        """Test getting logger."""
        logger = get_logger_from_factory("test.module")
        assert logger is not None

    def test_get_logger_has_methods(self):
        """Test that logger has standard methods."""
        logger = get_logger_from_factory("test")
        assert hasattr(logger, "info")
        assert hasattr(logger, "error")
        assert hasattr(logger, "warning")
        assert hasattr(logger, "debug")


class TestResetLoggingFactory:
    """Tests for reset_logging_factory function."""

    def test_reset_succeeds(self):
        """Test that reset doesn't raise."""
        reset_logging_factory()
        # Should not raise


class TestRegisterBackend:
    """Tests for register_backend function."""

    def setup_method(self):
        """Reset factory before each test."""
        reset_logging_factory()

    def teardown_method(self):
        """Reset factory after each test."""
        reset_logging_factory()

    def test_register_custom_backend(self):
        """Test registering a custom backend."""
        from obskit.logging.adapters.base import LoggerAdapter
        
        class MockBackend(LoggerAdapter):
            @classmethod
            def is_available(cls) -> bool:
                return True
            
            def get_logger(self, name: str):
                return MagicMock()
            
            def configure(self, **kwargs):
                pass
        
        register_backend("mock_custom", MockBackend)
        
        # Backend should now be available
        backends = get_available_backends()
        assert "mock_custom" in backends


class TestAutoConfiguration:
    """Tests for auto-configuration paths."""

    def setup_method(self):
        """Reset factory before each test."""
        reset_logging_factory()

    def teardown_method(self):
        """Reset factory after each test."""
        reset_logging_factory()

    def test_get_logger_auto_configures(self):
        """Test get_logger_from_factory auto-configures when not configured."""
        reset_logging_factory()
        
        # Don't manually configure, let it auto-configure
        logger = get_logger_from_factory("test.auto")
        
        assert logger is not None

    def test_configure_auto_backend(self):
        """Test configure with auto backend selection."""
        reset_logging_factory()
        
        configure_logging_backend(backend="auto")
        
        logger = get_logger_from_factory("test.auto")
        assert logger is not None

