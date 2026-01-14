"""Tests for obskit.logging.logger module."""

import pytest
from unittest.mock import patch, MagicMock

from obskit.logging.logger import (
    get_logger,
    configure_logging,
    reset_logging,
    log_operation,
    log_performance,
    log_error,
)


class TestGetLogger:
    """Tests for get_logger function."""

    def setup_method(self):
        """Reset state before each test."""
        reset_logging()

    def teardown_method(self):
        """Clean up after each test."""
        reset_logging()

    def test_returns_logger(self):
        """Test that get_logger returns a logger."""
        logger = get_logger("test")
        
        assert logger is not None

    def test_returns_logger_for_same_name(self):
        """Test that same name returns a logger."""
        logger1 = get_logger("test")
        logger2 = get_logger("test")
        
        # Both should be valid loggers
        assert logger1 is not None
        assert logger2 is not None

    def test_different_loggers_for_different_names(self):
        """Test that different names return different loggers."""
        logger1 = get_logger("test1")
        logger2 = get_logger("test2")
        
        assert logger1 is not logger2


class TestConfigureLogging:
    """Tests for configure_logging function."""

    def setup_method(self):
        """Reset state before each test."""
        reset_logging()

    def teardown_method(self):
        """Clean up after each test."""
        reset_logging()

    def test_configure_with_defaults(self):
        """Test configure_logging with defaults."""
        configure_logging()
        
        # Should not raise
        logger = get_logger("test")
        assert logger is not None

    def test_configure_idempotent(self):
        """Test configure_logging can be called multiple times."""
        configure_logging()
        configure_logging()  # Should not raise
        
        logger = get_logger("test")
        assert logger is not None

    def test_configure_sets_flag(self):
        """Test configure_logging sets the configured flag."""
        import obskit.logging.logger as logger_module
        
        assert logger_module._logging_configured is False
        configure_logging()
        assert logger_module._logging_configured is True


class TestResetLogging:
    """Tests for reset_logging function."""

    def test_reset_clears_state(self):
        """Test that reset clears state."""
        logger1 = get_logger("test")
        
        reset_logging()
        
        logger2 = get_logger("test")
        
        # After reset, may get different logger
        assert logger2 is not None


class TestLoggerMethods:
    """Tests for logger methods."""

    def setup_method(self):
        """Reset state before each test."""
        reset_logging()
        configure_logging()

    def teardown_method(self):
        """Clean up after each test."""
        reset_logging()

    def test_info_method(self):
        """Test info method."""
        logger = get_logger("test")
        
        # Should not raise
        logger.info("test_message", key="value")

    def test_debug_method(self):
        """Test debug method."""
        logger = get_logger("test")
        
        # Should not raise
        logger.debug("test_message", key="value")

    def test_warning_method(self):
        """Test warning method."""
        logger = get_logger("test")
        
        # Should not raise
        logger.warning("test_message", key="value")

    def test_error_method(self):
        """Test error method."""
        logger = get_logger("test")
        
        # Should not raise
        logger.error("test_message", key="value")

    def test_log_with_kwargs(self):
        """Test logging with keyword arguments."""
        logger = get_logger("test")
        
        # Should not raise
        logger.info(
            "test_event",
            user_id="123",
            action="login",
            duration_ms=50,
        )


class TestLogOperation:
    """Tests for log_operation function."""

    def setup_method(self):
        """Reset state before each test."""
        reset_logging()
        configure_logging()

    def teardown_method(self):
        """Clean up after each test."""
        reset_logging()

    def test_log_operation_success(self):
        """Test log_operation for success."""
        log_operation(
            operation="test_op",
            component="TestComponent",
            status="success",
            duration_ms=50.0,
        )

    def test_log_operation_failure(self):
        """Test log_operation for failure."""
        log_operation(
            operation="test_op",
            component="TestComponent",
            status="failure",
            duration_ms=50.0,
            error="Test error",
        )

    def test_log_operation_with_extra(self):
        """Test log_operation with extra data."""
        log_operation(
            operation="test_op",
            component="TestComponent",
            status="success",
            duration_ms=50.0,
            user_id="123",
            request_id="abc",
        )

    def test_log_operation_without_duration(self):
        """Test log_operation without duration."""
        log_operation(
            operation="test_op",
            component="TestComponent",
        )


class TestLogPerformance:
    """Tests for log_performance function."""

    def setup_method(self):
        """Reset state before each test."""
        reset_logging()
        configure_logging()

    def teardown_method(self):
        """Clean up after each test."""
        reset_logging()

    def test_log_performance(self):
        """Test log_performance."""
        log_performance(
            operation="test_op",
            component="TestComponent",
            duration_ms=50.0,
        )

    def test_log_performance_with_threshold_exceeded(self):
        """Test log_performance with threshold exceeded (triggers warning)."""
        log_performance(
            operation="test_op",
            component="TestComponent",
            duration_ms=100.0,
            threshold_ms=50.0,  # duration exceeds threshold
        )

    def test_log_performance_below_threshold(self):
        """Test log_performance below threshold (no warning)."""
        log_performance(
            operation="test_op",
            component="TestComponent",
            duration_ms=30.0,
            threshold_ms=50.0,
        )

    def test_log_performance_with_extra(self):
        """Test log_performance with extra context."""
        log_performance(
            operation="test_op",
            component="TestComponent",
            duration_ms=45.0,
            query_type="search",
            result_count=10,
        )


class TestLogError:
    """Tests for log_error function."""

    def setup_method(self):
        """Reset state before each test."""
        reset_logging()
        configure_logging()

    def teardown_method(self):
        """Clean up after each test."""
        reset_logging()

    def test_log_error(self):
        """Test log_error with basic params."""
        error = ValueError("Test error message")
        log_error(
            error=error,
            component="TestComponent",
            operation="test_op",
        )

    def test_log_error_with_context(self):
        """Test log_error with context dictionary."""
        try:
            raise ValueError("Test error")
        except ValueError as e:
            log_error(
                error=e,
                component="TestComponent",
                operation="test_op",
                context={
                    "user_id": "123",
                    "request_id": "abc",
                },
            )

    def test_log_error_with_different_exception_types(self):
        """Test log_error with different exception types."""
        for exc_class in [ValueError, TypeError, RuntimeError]:
            error = exc_class("Test error")
            log_error(
                error=error,
                component="TestComponent",
                operation="test_op",
            )
