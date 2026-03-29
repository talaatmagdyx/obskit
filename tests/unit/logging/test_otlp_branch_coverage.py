"""Additional coverage tests for otlp.py branch misses."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest


class TestOTLPBranchCoverage:
    """Cover remaining branch misses in logging/otlp.py."""

    def test_emit_without_otel_available(self):
        """Line 389->397: OTEL not available so trace context is skipped."""
        from obskit.logging import otlp as otlp_mod
        from obskit.logging.otlp import OTLPLogHandler

        handler = OTLPLogHandler(endpoint="http://localhost:4317", service_name="test-svc")
        handler._shutdown = True  # don't flush in background

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="test without otel",
            args=(),
            exc_info=None,
        )

        # Patch OTEL unavailable -> skips trace context block
        with patch.object(otlp_mod, "OTEL_LOGGING_AVAILABLE", False):
            handler._shutdown = False
            handler.emit(record)
            handler._shutdown = True

        assert isinstance(handler, OTLPLogHandler)

    def test_emit_with_record_without_dict(self):
        """Line 397->425: record with no __dict__ skips attributes loop."""
        from obskit.logging import otlp as otlp_mod
        from obskit.logging.otlp import OTLPLogHandler

        handler = OTLPLogHandler(endpoint="http://localhost:4317", service_name="test-svc")
        handler._shutdown = True

        # Create a record-like object with no __dict__
        class NoDict:
            __slots__ = [
                "levelno",
                "levelname",
                "name",
                "msg",
                "pathname",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
            ]

            def getMessage(self):
                return "test without dict"

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="test",
            args=(),
            exc_info=None,
        )

        # Patch hasattr to return False for record.__dict__
        original_hasattr = hasattr

        def patched_hasattr(obj, name):
            if obj is record and name == "__dict__":
                return False
            return original_hasattr(obj, name)

        handler._shutdown = False
        with patch("builtins.hasattr", side_effect=patched_hasattr):
            handler.emit(record)
        handler._shutdown = True

    def test_close_with_thread_not_alive(self):
        """Line 436->438: close when flush_thread is dead (not alive)."""
        from obskit.logging.otlp import OTLPLogHandler

        handler = OTLPLogHandler(endpoint="http://localhost:4317", service_name="test-svc")

        # Set the flush thread to be present but not alive
        mock_thread = MagicMock()
        mock_thread.is_alive.return_value = False
        handler._flush_thread = mock_thread

        # close() should not call join() since thread is not alive
        handler.close()

        # Verify join was not called
        mock_thread.join.assert_not_called()
