"""Tests for obskit.logging.dynamic module."""

import logging
import pytest
from unittest.mock import MagicMock, patch

from obskit.logging.dynamic import (
    set_log_level,
    get_log_level,
    register_logger,
)


class TestSetLogLevel:
    """Tests for set_log_level function."""

    def test_set_debug_level(self):
        """Test setting DEBUG level."""
        set_log_level("DEBUG")

    def test_set_info_level(self):
        """Test setting INFO level."""
        set_log_level("INFO")

    def test_set_warning_level(self):
        """Test setting WARNING level."""
        set_log_level("WARNING")

    def test_set_error_level(self):
        """Test setting ERROR level."""
        set_log_level("ERROR")

    def test_set_critical_level(self):
        """Test setting CRITICAL level."""
        set_log_level("CRITICAL")

    def test_set_level_for_component(self):
        """Test setting level for specific component."""
        set_log_level("DEBUG", component="test.component")


class TestGetLogLevel:
    """Tests for get_log_level function."""

    def test_get_default_level(self):
        """Test getting default log level."""
        level = get_log_level()
        assert level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

    def test_level_after_set(self):
        """Test level reflects what was set."""
        set_log_level("DEBUG")
        level = get_log_level()
        assert level == "DEBUG"

    def test_get_level_for_component(self):
        """Test getting level for specific component."""
        register_logger("test.component", logging.getLogger("test.component"))
        set_log_level("WARNING", component="test.component")
        level = get_log_level(component="test.component")
        assert level == "WARNING"


class TestRegisterLogger:
    """Tests for register_logger function."""

    def test_register_logger(self):
        """Test registering a logger."""
        test_logger = logging.getLogger("test.registered")
        register_logger("test.registered", test_logger)

    def test_register_multiple_loggers(self):
        """Test registering multiple loggers."""
        logger1 = logging.getLogger("module1")
        logger2 = logging.getLogger("module2")
        register_logger("module1", logger1)
        register_logger("module2", logger2)

