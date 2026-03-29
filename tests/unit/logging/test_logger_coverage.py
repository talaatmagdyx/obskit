"""Additional coverage tests for logging/logger.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import obskit.logging.logger as logging_module

sample_log = logging_module.sample_log
add_service_info = logging_module.add_service_info
configure_logging = logging_module.configure_logging
reset_logging = logging_module.reset_logging


class TestSampleLogCoverage:
    def setup_method(self):
        reset_logging()

    def teardown_method(self):
        reset_logging()

    def test_sample_log_attribute_error_returns_default(self):
        """Lines 109-110: AttributeError on log_sample_rate defaults to 1.0."""
        mock_settings = MagicMock()
        del mock_settings.log_sample_rate  # causes AttributeError

        with patch("obskit.logging.logger.get_settings", return_value=mock_settings):
            result = sample_log(MagicMock(), "info", {"event": "test"})
            # With sample_rate=1.0 (default), it should not be dropped
            assert result is not None


class TestAddServiceInfoCoverage:
    def test_add_service_info_attribute_errors(self):
        """Lines 192-203: AttributeError on service/environment/version."""
        mock_settings = MagicMock()
        # Remove attributes to trigger AttributeErrors
        del mock_settings.service_name
        del mock_settings.environment
        del mock_settings.version

        event_dict = {}
        with patch("obskit.logging.logger.get_settings", return_value=mock_settings):
            result = add_service_info(MagicMock(), "info", event_dict)

        assert result["service"] == "unknown"
        assert result["environment"] == "development"
        assert result["version"] == "0.0.0"


class TestConfigureLoggingCoverage:
    def setup_method(self):
        reset_logging()

    def teardown_method(self):
        reset_logging()

    def test_configure_logging_with_attribute_errors(self):
        """Lines 280-291: AttributeError on log_include_timestamp/log_format/log_level."""
        mock_settings = MagicMock()
        del mock_settings.log_include_timestamp
        del mock_settings.log_format
        del mock_settings.log_level

        with patch("obskit.logging.logger.get_settings", return_value=mock_settings):
            # Should not raise, uses defaults
            configure_logging()
