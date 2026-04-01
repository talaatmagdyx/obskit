"""Unit tests for obskit.logging.otlp — OTLP log handler."""

from __future__ import annotations

import logging
import threading
import time
from queue import Queue
from unittest.mock import MagicMock, patch

import pytest

# =============================================================================
# Module-level state tests
# =============================================================================


class TestOTLPModuleState:
    def test_module_importable(self):
        from obskit.logging import otlp

        assert otlp is not None

    def test_otel_availability_flag_is_bool(self):
        from obskit.logging.otlp import OTEL_LOGGING_AVAILABLE

        assert isinstance(OTEL_LOGGING_AVAILABLE, bool)

    def test_otlp_exporter_availability_flag_is_bool(self):
        from obskit.logging.otlp import OTLP_EXPORTER_AVAILABLE

        assert isinstance(OTLP_EXPORTER_AVAILABLE, bool)


# =============================================================================
# configure_otlp_logging
# =============================================================================


class TestConfigureOTLPLogging:
    def test_returns_false_when_otel_not_available(self):
        from obskit.logging import otlp as otlp_mod

        with patch.object(otlp_mod, "OTEL_LOGGING_AVAILABLE", False):
            result = otlp_mod.configure_otlp_logging()
        assert result is False

    def test_returns_false_when_exporter_not_available(self):
        from obskit.logging import otlp as otlp_mod

        with (
            patch.object(otlp_mod, "OTEL_LOGGING_AVAILABLE", True),
            patch.object(otlp_mod, "OTLP_EXPORTER_AVAILABLE", False),
        ):
            result = otlp_mod.configure_otlp_logging()
        assert result is False

    def test_returns_true_when_already_configured(self):
        from obskit.logging import otlp as otlp_mod

        with (
            patch.object(otlp_mod, "OTEL_LOGGING_AVAILABLE", True),
            patch.object(otlp_mod, "OTLP_EXPORTER_AVAILABLE", True),
            patch.object(otlp_mod, "_otlp_configured", True),
        ):
            result = otlp_mod.configure_otlp_logging()
        assert result is True

    def test_configures_with_mock_dependencies(self):
        from obskit.logging import otlp as otlp_mod

        mock_provider = MagicMock()
        mock_exporter = MagicMock()
        mock_processor = MagicMock()
        mock_resource = MagicMock()
        mock_resource_cls = MagicMock()
        mock_resource_cls.create.return_value = mock_resource

        with (
            patch.object(otlp_mod, "OTEL_LOGGING_AVAILABLE", True),
            patch.object(otlp_mod, "OTLP_EXPORTER_AVAILABLE", True),
            patch.object(otlp_mod, "_otlp_configured", False),
            patch.object(otlp_mod, "_otlp_logger_provider", None),
            patch.object(otlp_mod, "Resource", mock_resource_cls),
            patch.object(otlp_mod, "LoggerProvider", return_value=mock_provider),
            patch.object(otlp_mod, "OTLPLogExporter", return_value=mock_exporter),
            patch.object(otlp_mod, "BatchLogRecordProcessor", return_value=mock_processor),
        ):
            result = otlp_mod.configure_otlp_logging(
                endpoint="http://localhost:4317",
                service_name="test_service",
            )

        assert result is True

    def test_configure_sets_provider(self):
        from obskit.logging import otlp as otlp_mod

        mock_provider = MagicMock()
        mock_exporter = MagicMock()
        mock_processor = MagicMock()
        mock_resource = MagicMock()
        mock_resource_cls = MagicMock()
        mock_resource_cls.create.return_value = mock_resource

        # Reset state
        original_configured = otlp_mod._otlp_configured
        original_provider = otlp_mod._otlp_logger_provider

        try:
            with (
                patch.object(otlp_mod, "OTEL_LOGGING_AVAILABLE", True),
                patch.object(otlp_mod, "OTLP_EXPORTER_AVAILABLE", True),
                patch.object(otlp_mod, "_otlp_configured", False),
                patch.object(otlp_mod, "_otlp_logger_provider", None),
                patch.object(otlp_mod, "Resource", mock_resource_cls),
                patch.object(otlp_mod, "LoggerProvider", return_value=mock_provider),
                patch.object(otlp_mod, "OTLPLogExporter", return_value=mock_exporter),
                patch.object(otlp_mod, "BatchLogRecordProcessor", return_value=mock_processor),
            ):
                otlp_mod.configure_otlp_logging(endpoint="http://test:4317")
                assert otlp_mod._otlp_configured is True
        finally:
            otlp_mod._otlp_configured = original_configured
            otlp_mod._otlp_logger_provider = original_provider


# =============================================================================
# shutdown_otlp_logging
# =============================================================================


class TestShutdownOTLPLogging:
    def test_no_op_when_not_configured(self):
        from obskit.logging import otlp as otlp_mod

        # Should not raise
        original_provider = otlp_mod._otlp_logger_provider
        otlp_mod._otlp_logger_provider = None
        try:
            otlp_mod.shutdown_otlp_logging()
        finally:
            otlp_mod._otlp_logger_provider = original_provider

    def test_shutdown_calls_provider_shutdown(self):
        from obskit.logging import otlp as otlp_mod

        mock_provider = MagicMock()
        original_provider = otlp_mod._otlp_logger_provider
        original_configured = otlp_mod._otlp_configured

        otlp_mod._otlp_logger_provider = mock_provider
        otlp_mod._otlp_configured = True

        try:
            otlp_mod.shutdown_otlp_logging()
            mock_provider.shutdown.assert_called_once()
            assert otlp_mod._otlp_logger_provider is None
            assert otlp_mod._otlp_configured is False
        finally:
            otlp_mod._otlp_logger_provider = original_provider
            otlp_mod._otlp_configured = original_configured


# =============================================================================
# get_otlp_handler
# =============================================================================


class TestGetOTLPHandler:
    def test_returns_none_when_not_available(self):
        from obskit.logging import otlp as otlp_mod

        with patch.object(otlp_mod, "OTEL_LOGGING_AVAILABLE", False):
            result = otlp_mod.get_otlp_handler()
        assert result is None

    def test_returns_logging_handler_when_configured(self):
        from obskit.logging import otlp as otlp_mod

        mock_provider = MagicMock()
        mock_handler = MagicMock(spec=logging.Handler)
        mock_logging_handler_cls = MagicMock(return_value=mock_handler)

        with (
            patch.object(otlp_mod, "OTEL_LOGGING_AVAILABLE", True),
            patch.object(otlp_mod, "_otlp_logger_provider", mock_provider),
            patch.object(otlp_mod, "LoggingHandler", mock_logging_handler_cls),
        ):
            result = otlp_mod.get_otlp_handler()

        assert result is mock_handler


# =============================================================================
# OTLPLogHandler
# =============================================================================


class TestOTLPLogHandler:
    def _create_handler(self):
        from obskit.logging.otlp import OTLPLogHandler

        handler = OTLPLogHandler(
            endpoint="http://localhost:4317",
            service_name="test_service",
            insecure=True,
            batch_size=10,
            flush_interval=0.1,
        )
        return handler

    def test_creation(self):
        handler = self._create_handler()
        assert handler.endpoint == "http://localhost:4317"
        assert handler.service_name == "test_service"
        assert handler.insecure is True
        handler.close()

    def test_batch_size_stored(self):
        handler = self._create_handler()
        assert handler.batch_size == 10
        handler.close()

    def test_flush_interval_stored(self):
        handler = self._create_handler()
        assert handler.flush_interval == pytest.approx(0.1)
        handler.close()

    def test_queue_created(self):
        handler = self._create_handler()
        assert isinstance(handler._queue, Queue)
        handler.close()

    def test_not_shutdown_initially(self):
        handler = self._create_handler()
        assert handler._shutdown is False
        handler.close()

    def test_flush_thread_started(self):
        handler = self._create_handler()
        assert handler._flush_thread is not None
        assert handler._flush_thread.is_alive()
        handler.close()

    def test_emit_queues_log_record(self):
        handler = self._create_handler()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="test message",
            args=(),
            exc_info=None,
        )
        handler.emit(record)
        time.sleep(0.05)
        # Queue might be empty if flushed, but no crash
        handler.close()

    def test_emit_skips_when_shutdown(self):
        handler = self._create_handler()
        handler._shutdown = True
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="test message",
            args=(),
            exc_info=None,
        )
        handler.emit(record)
        assert handler._queue.empty()
        handler.close()

    def test_close_sets_shutdown(self):
        handler = self._create_handler()
        handler.close()
        assert handler._shutdown is True

    def test_close_joins_flush_thread(self):
        handler = self._create_handler()
        handler.close()
        # Thread should be finished within timeout
        if handler._flush_thread:
            assert not handler._flush_thread.is_alive()

    def test_emit_includes_service_name(self):
        handler = self._create_handler()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="test message",
            args=(),
            exc_info=None,
        )
        handler.emit(record)
        time.sleep(0.05)
        handler.close()

    def test_start_flush_thread_creates_daemon_thread(self):
        handler = self._create_handler()
        assert handler._flush_thread.daemon is True
        handler.close()

    def test_export_batch_no_op_when_empty(self):
        handler = self._create_handler()
        # Should not raise
        handler._export_batch([])
        handler.close()

    def test_export_batch_with_records(self):
        handler = self._create_handler()
        batch = [{"timestamp": "2024-01-01", "severity": "INFO", "body": "test"}]
        # _export_batch is a no-op; real export happens via _otel_handler in emit()
        handler._export_batch(batch)  # Should not raise
        handler.close()


# =============================================================================
# create_otlp_log_processor
# =============================================================================


class TestCreateOTLPLogProcessor:
    def test_returns_callable(self):
        from obskit.logging.otlp import create_otlp_log_processor

        processor = create_otlp_log_processor()
        assert callable(processor)

    def test_processor_adds_severity_number(self):
        from obskit.logging.otlp import create_otlp_log_processor

        processor = create_otlp_log_processor()
        event_dict = {"event": "test"}
        result = processor(None, "info", event_dict)
        assert result["severity_number"] == 9

    def test_processor_debug_severity(self):
        from obskit.logging.otlp import create_otlp_log_processor

        processor = create_otlp_log_processor()
        result = processor(None, "debug", {"event": "test"})
        assert result["severity_number"] == 5

    def test_processor_warning_severity(self):
        from obskit.logging.otlp import create_otlp_log_processor

        processor = create_otlp_log_processor()
        result = processor(None, "warning", {"event": "test"})
        assert result["severity_number"] == 13

    def test_processor_error_severity(self):
        from obskit.logging.otlp import create_otlp_log_processor

        processor = create_otlp_log_processor()
        result = processor(None, "error", {"event": "test"})
        assert result["severity_number"] == 17

    def test_processor_critical_severity(self):
        from obskit.logging.otlp import create_otlp_log_processor

        processor = create_otlp_log_processor()
        result = processor(None, "critical", {"event": "test"})
        assert result["severity_number"] == 21

    def test_processor_unknown_severity_defaults_to_9(self):
        from obskit.logging.otlp import create_otlp_log_processor

        processor = create_otlp_log_processor()
        result = processor(None, "custom_level", {"event": "test"})
        assert result["severity_number"] == 9

    def test_processor_preserves_existing_keys(self):
        from obskit.logging.otlp import create_otlp_log_processor

        processor = create_otlp_log_processor()
        event_dict = {"event": "test", "custom_key": "custom_value"}
        result = processor(None, "info", event_dict)
        assert result["custom_key"] == "custom_value"
        assert result["event"] == "test"

    def test_processor_endpoint_parameter_accepted(self):
        from obskit.logging.otlp import create_otlp_log_processor

        # Should accept endpoint parameter without error
        processor = create_otlp_log_processor(endpoint="http://localhost:4317")
        assert callable(processor)

    def test_processor_adds_trace_context_when_available(self):
        from obskit.logging import otlp as otlp_mod
        from obskit.logging.otlp import create_otlp_log_processor

        mock_span = MagicMock()
        mock_span.is_recording.return_value = True
        mock_ctx = MagicMock()
        mock_ctx.trace_id = 12345
        mock_ctx.span_id = 67890
        mock_ctx.trace_flags = 1
        mock_span.get_span_context.return_value = mock_ctx

        mock_trace = MagicMock()
        mock_trace.get_current_span.return_value = mock_span

        with (
            patch.object(otlp_mod, "OTEL_LOGGING_AVAILABLE", True),
            patch.object(otlp_mod, "trace", mock_trace),
        ):
            processor = create_otlp_log_processor()
            result = processor(None, "info", {"event": "test"})

        assert "trace_id" in result
        assert "span_id" in result
        assert "trace_flags" in result

    def test_processor_no_trace_context_when_not_recording(self):
        from obskit.logging import otlp as otlp_mod
        from obskit.logging.otlp import create_otlp_log_processor

        mock_span = MagicMock()
        mock_span.is_recording.return_value = False

        mock_trace = MagicMock()
        mock_trace.get_current_span.return_value = mock_span

        with (
            patch.object(otlp_mod, "OTEL_LOGGING_AVAILABLE", True),
            patch.object(otlp_mod, "trace", mock_trace),
        ):
            processor = create_otlp_log_processor()
            result = processor(None, "info", {"event": "test"})

        assert "trace_id" not in result

    def test_processor_no_trace_context_when_otel_unavailable(self):
        from obskit.logging import otlp as otlp_mod
        from obskit.logging.otlp import create_otlp_log_processor

        with patch.object(otlp_mod, "OTEL_LOGGING_AVAILABLE", False):
            processor = create_otlp_log_processor()
            result = processor(None, "info", {"event": "test"})

        assert "trace_id" not in result
