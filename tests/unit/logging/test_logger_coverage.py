"""Additional coverage tests for logging/logger.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import obskit.logging.logger as logging_module

sample_log = logging_module.sample_log
add_service_info = logging_module.add_service_info
add_correlation_id = logging_module.add_correlation_id
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

        with patch("obskit.config.get_settings", return_value=mock_settings):
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
        with patch("obskit.config.get_settings", return_value=mock_settings):
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

        with patch("obskit.config.get_settings", return_value=mock_settings):
            # Should not raise, uses defaults
            configure_logging()


class TestAddCorrelationIdProcessor:
    """Direct coverage of the add_correlation_id processor branches."""

    def setup_method(self):
        reset_logging()

    def teardown_method(self):
        reset_logging()

    def test_injects_id_when_context_is_set(self):
        """True branch: correlation ID present in context -> added to event dict."""
        from obskit.core.context import correlation_context

        with correlation_context("test-cid-abc"):
            result = add_service_info.__module__  # noqa: F841
            from obskit.logging.logger import add_correlation_id

            event = {"event": "test"}
            out = add_correlation_id(MagicMock(), "info", event)
        assert out["correlation_id"] == "test-cid-abc"

    def test_omits_field_when_no_context(self):
        """False branch: no correlation context -> field not added."""
        from obskit.logging.logger import add_correlation_id

        event = {"event": "test"}
        out = add_correlation_id(MagicMock(), "info", event)
        assert "correlation_id" not in out


class TestSampleLogDropEvent:
    """Verify sample_log raises DropEvent when sampling fires."""

    def setup_method(self):
        reset_logging()

    def teardown_method(self):
        reset_logging()

    def test_raises_drop_event_when_sampled_out(self):
        """sample_log must raise structlog.DropEvent (not return None) to drop a log."""
        import structlog
        from unittest.mock import patch
        from obskit.logging.logger import sample_log, configure_logging

        configure_logging()
        # Force random.random() to return 1.0 so sample_rate=0.01 triggers the drop
        with patch("obskit.logging.logger.random.random", return_value=1.0):
            # Override cached sample rate to sub-1.0 to activate sampling path
            import obskit.logging.logger as _lm
            original = _lm._cached_log_sample_rate
            _lm._cached_log_sample_rate = 0.01
            try:
                import pytest
                with pytest.raises(structlog.DropEvent):
                    sample_log(MagicMock(), "info", {"event": "test"})
            finally:
                _lm._cached_log_sample_rate = original

    def test_passes_through_errors_regardless_of_rate(self):
        """error/critical level always bypasses sampling."""
        import obskit.logging.logger as _lm
        from obskit.logging.logger import sample_log, configure_logging

        configure_logging()
        original = _lm._cached_log_sample_rate
        _lm._cached_log_sample_rate = 0.0
        try:
            event = {"event": "something_failed"}
            result = sample_log(MagicMock(), "error", event)
            assert result is event
        finally:
            _lm._cached_log_sample_rate = original
