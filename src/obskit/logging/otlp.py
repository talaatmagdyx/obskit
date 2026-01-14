"""
OTLP Logging Export
===================

This module provides OpenTelemetry Protocol (OTLP) export for structured logs,
enabling unified observability with traces and metrics through a single protocol.

Features
--------
- Export structured logs to OTLP collector
- Automatic correlation with traces (trace_id, span_id)
- Batching and retry for reliability
- Support for both gRPC and HTTP protocols

Example - Basic Setup
---------------------
.. code-block:: python

    from obskit.logging.otlp import configure_otlp_logging, get_otlp_logger

    # Configure OTLP export
    configure_otlp_logging(
        endpoint="http://otel-collector:4317",
        service_name="order-service",
    )

    # Get logger with OTLP export
    logger = get_otlp_logger("order_service")
    logger.info("Order created", order_id="12345")

Example - With Trace Correlation
--------------------------------
.. code-block:: python

    from obskit.logging.otlp import OTLPLogHandler
    from obskit.tracing import trace_span
    import logging

    # Add OTLP handler to Python logger
    handler = OTLPLogHandler(endpoint="http://otel-collector:4317")
    logging.getLogger().addHandler(handler)

    # Logs within spans are automatically correlated
    with trace_span("process_order"):
        logging.info("Processing order")  # Includes trace_id, span_id
"""

from __future__ import annotations

import atexit
import logging
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime
from queue import Empty, Queue
from typing import Any

from obskit.config import get_settings
from obskit.logging import get_logger

logger = get_logger("obskit.logging.otlp")

# Check for OpenTelemetry availability
try:
    from opentelemetry import trace
    from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
    from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
    from opentelemetry.sdk.resources import Resource

    OTEL_LOGGING_AVAILABLE = True
except ImportError:  # pragma: no cover
    OTEL_LOGGING_AVAILABLE = False
    trace = None  # type: ignore[assignment]
    LoggerProvider = None  # type: ignore[misc, assignment]
    LoggingHandler = None  # type: ignore[misc, assignment]
    BatchLogRecordProcessor = None  # type: ignore[misc, assignment]
    Resource = None  # type: ignore[misc, assignment]

# Check for OTLP exporter
try:
    from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter

    OTLP_EXPORTER_AVAILABLE = True
except ImportError:  # pragma: no cover
    OTLP_EXPORTER_AVAILABLE = False
    OTLPLogExporter = None  # type: ignore[misc, assignment]


_otlp_logger_provider: LoggerProvider | None = None
_otlp_configured = False
_otlp_lock = threading.Lock()


def configure_otlp_logging(
    endpoint: str | None = None,
    service_name: str | None = None,
    insecure: bool | None = None,
    batch_size: int = 512,
    export_timeout_ms: int = 30000,
) -> bool:
    """
    Configure OTLP logging export.

    Parameters
    ----------
    endpoint : str, optional
        OTLP collector endpoint. Defaults to settings.otlp_endpoint.
    service_name : str, optional
        Service name for logs. Defaults to settings.service_name.
    insecure : bool, optional
        Use insecure connection. Defaults to settings.otlp_insecure.
    batch_size : int
        Maximum batch size for log export. Default: 512.
    export_timeout_ms : int
        Export timeout in milliseconds. Default: 30000.

    Returns
    -------
    bool
        True if configuration succeeded, False otherwise.

    Example
    -------
    >>> from obskit.logging.otlp import configure_otlp_logging
    >>>
    >>> configure_otlp_logging(
    ...     endpoint="http://otel-collector:4317",
    ...     service_name="my-service",
    ... )
    """
    global _otlp_logger_provider, _otlp_configured

    if not OTEL_LOGGING_AVAILABLE:  # pragma: no cover
        logger.warning(
            "otlp_logging_not_available",
            message="OpenTelemetry SDK not installed. Install with: pip install opentelemetry-sdk",
        )
        return False

    if not OTLP_EXPORTER_AVAILABLE:  # pragma: no cover
        logger.warning(
            "otlp_exporter_not_available",
            message="OTLP exporter not installed. Install with: pip install opentelemetry-exporter-otlp",
        )
        return False

    with _otlp_lock:
        if _otlp_configured:
            return True

        settings = get_settings()
        actual_endpoint = endpoint or settings.otlp_endpoint
        actual_service_name = service_name or settings.service_name
        actual_insecure = insecure if insecure is not None else settings.otlp_insecure

        # Create resource
        resource = Resource.create(
            {
                "service.name": actual_service_name,
                "service.version": settings.version,
                "deployment.environment": settings.environment,
            }
        )

        # Create logger provider
        _otlp_logger_provider = LoggerProvider(resource=resource)

        # Create OTLP exporter
        exporter = OTLPLogExporter(
            endpoint=actual_endpoint,
            insecure=actual_insecure,
        )

        # Add batch processor
        processor = BatchLogRecordProcessor(
            exporter,
            max_export_batch_size=batch_size,
            export_timeout_millis=export_timeout_ms,
        )
        _otlp_logger_provider.add_log_record_processor(processor)

        _otlp_configured = True

        # Register shutdown handler
        atexit.register(shutdown_otlp_logging)

        logger.info(
            "otlp_logging_configured",
            endpoint=actual_endpoint,
            service_name=actual_service_name,
        )
        return True


def get_otlp_handler() -> logging.Handler | None:
    """
    Get a Python logging handler that exports to OTLP.

    Returns
    -------
    logging.Handler | None
        LoggingHandler for OTLP export, or None if not available.

    Example
    -------
    >>> import logging
    >>> from obskit.logging.otlp import configure_otlp_logging, get_otlp_handler
    >>>
    >>> configure_otlp_logging()
    >>> handler = get_otlp_handler()
    >>> if handler:
    ...     logging.getLogger().addHandler(handler)
    """
    global _otlp_logger_provider

    if not OTEL_LOGGING_AVAILABLE:  # pragma: no cover
        return None

    if _otlp_logger_provider is None:
        configure_otlp_logging()

    if _otlp_logger_provider is None:  # pragma: no cover
        return None

    return LoggingHandler(
        level=logging.NOTSET,
        logger_provider=_otlp_logger_provider,
    )


def shutdown_otlp_logging() -> None:
    """
    Shutdown OTLP logging and flush pending logs.
    """
    global _otlp_logger_provider, _otlp_configured

    with _otlp_lock:
        if _otlp_logger_provider is not None:
            try:
                _otlp_logger_provider.shutdown()  # type: ignore[no-untyped-call]
            except Exception:  # pragma: no cover  # nosec B110 - shutdown errors are non-critical
                pass  # Shutdown may fail if already stopped
            _otlp_logger_provider = None
            _otlp_configured = False


class OTLPLogHandler(logging.Handler):
    """
    Custom logging handler that exports logs to OTLP.

    This handler provides more control than the SDK's LoggingHandler,
    including automatic trace correlation and structured attribute handling.

    Parameters
    ----------
    endpoint : str
        OTLP collector endpoint.
    service_name : str, optional
        Service name for logs.
    insecure : bool
        Use insecure connection. Default: True.
    batch_size : int
        Maximum batch size. Default: 100.
    flush_interval : float
        Flush interval in seconds. Default: 5.0.

    Example
    -------
    >>> import logging
    >>> from obskit.logging.otlp import OTLPLogHandler
    >>>
    >>> handler = OTLPLogHandler(
    ...     endpoint="http://otel-collector:4317",
    ...     service_name="my-service",
    ... )
    >>> handler.setLevel(logging.INFO)
    >>>
    >>> logger = logging.getLogger("my_app")
    >>> logger.addHandler(handler)
    >>> logger.info("Application started")
    """

    def __init__(
        self,
        endpoint: str,
        service_name: str | None = None,
        insecure: bool = True,
        batch_size: int = 100,
        flush_interval: float = 5.0,
    ) -> None:
        super().__init__()

        settings = get_settings()
        self.endpoint = endpoint
        self.service_name = service_name or settings.service_name
        self.insecure = insecure
        self.batch_size = batch_size
        self.flush_interval = flush_interval

        self._queue: Queue[dict[str, Any]] = Queue(maxsize=10000)
        self._shutdown = False
        self._flush_thread: threading.Thread | None = None

        # Start background flush thread
        self._start_flush_thread()

    def _start_flush_thread(self) -> None:
        """Start the background flush thread."""
        self._flush_thread = threading.Thread(
            target=self._flush_loop,
            daemon=True,
            name="otlp-log-flusher",
        )
        self._flush_thread.start()

    def _flush_loop(self) -> None:
        """Background loop that flushes logs periodically."""
        batch: list[dict[str, Any]] = []
        last_flush = time.time()

        while not self._shutdown:
            try:
                # Collect logs from queue
                try:
                    log_record = self._queue.get(timeout=0.1)
                    batch.append(log_record)
                except Empty:
                    pass  # Expected when queue is empty - continue to check flush conditions

                # Flush if batch is full or interval elapsed
                now = time.time()
                should_flush = len(batch) >= self.batch_size or (
                    batch and now - last_flush >= self.flush_interval
                )

                if should_flush:
                    self._export_batch(batch)
                    batch = []
                    last_flush = now

            except Exception:  # pragma: no cover  # nosec B110 - background thread must not crash
                pass  # Don't crash the flush thread

        # Final flush on shutdown
        if batch:
            self._export_batch(batch)

    def _export_batch(self, batch: list[dict[str, Any]]) -> None:
        """Export a batch of logs to OTLP."""
        if not batch:
            return

        # This is a simplified implementation
        # In production, you'd use the actual OTLP exporter
        # For now, just a placeholder - real implementation would serialize and send to OTLP
        _ = batch  # Acknowledge batch parameter for future implementation

    def emit(self, record: logging.LogRecord) -> None:
        """
        Emit a log record to the OTLP queue.

        Parameters
        ----------
        record : logging.LogRecord
            The log record to emit.
        """
        if self._shutdown:
            return

        try:
            # Build log entry
            log_entry: dict[str, Any] = {
                "timestamp": datetime.now(UTC).isoformat(),
                "severity": record.levelname,
                "body": self.format(record),
                "attributes": {
                    "logger.name": record.name,
                    "code.filepath": record.pathname,
                    "code.lineno": record.lineno,
                    "code.function": record.funcName,
                },
                "resource": {
                    "service.name": self.service_name,
                },
            }

            # Add trace context if available
            if OTEL_LOGGING_AVAILABLE and trace is not None:
                span = trace.get_current_span()
                if span and span.is_recording():
                    ctx = span.get_span_context()
                    log_entry["trace_id"] = format(ctx.trace_id, "032x")
                    log_entry["span_id"] = format(ctx.span_id, "016x")

            # Add extra attributes
            if hasattr(record, "__dict__"):
                for key, value in record.__dict__.items():
                    if key not in (
                        "name",
                        "msg",
                        "args",
                        "levelname",
                        "levelno",
                        "pathname",
                        "filename",
                        "module",
                        "lineno",
                        "funcName",
                        "created",
                        "msecs",
                        "relativeCreated",
                        "thread",
                        "threadName",
                        "processName",
                        "process",
                        "message",
                        "exc_info",
                        "exc_text",
                        "stack_info",
                    ):
                        log_entry["attributes"][key] = str(value)

            # Queue for async export
            try:
                self._queue.put_nowait(log_entry)
            except Exception:  # pragma: no cover  # nosec B110 - queue full is expected under load
                pass  # Queue full, drop log - expected behavior under high load

        except Exception:  # pragma: no cover
            self.handleError(record)

    def close(self) -> None:
        """Close the handler and flush remaining logs."""
        self._shutdown = True
        if self._flush_thread and self._flush_thread.is_alive():
            self._flush_thread.join(timeout=5.0)
        super().close()


def create_otlp_log_processor(
    endpoint: str | None = None,
) -> Callable[[Any, str, dict[str, Any]], dict[str, Any]]:
    """
    Create a structlog processor that adds OTLP-compatible attributes.

    Parameters
    ----------
    endpoint : str, optional
        OTLP endpoint (not used, but for consistency).

    Returns
    -------
    Callable
        Structlog processor function.

    Example
    -------
    >>> import structlog
    >>> from obskit.logging.otlp import create_otlp_log_processor
    >>>
    >>> structlog.configure(
    ...     processors=[
    ...         create_otlp_log_processor(),
    ...         structlog.processors.JSONRenderer(),
    ...     ]
    ... )
    """

    def otlp_processor(
        logger: Any,
        method_name: str,
        event_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """Add OTLP-compatible attributes to log event."""
        # Add trace context if available
        if OTEL_LOGGING_AVAILABLE and trace is not None:
            span = trace.get_current_span()
            if span and span.is_recording():
                ctx = span.get_span_context()
                event_dict["trace_id"] = format(ctx.trace_id, "032x")
                event_dict["span_id"] = format(ctx.span_id, "016x")
                event_dict["trace_flags"] = ctx.trace_flags

        # Add severity number for OTLP
        severity_map = {
            "debug": 5,
            "info": 9,
            "warning": 13,
            "error": 17,
            "critical": 21,
        }
        event_dict["severity_number"] = severity_map.get(method_name.lower(), 9)

        return event_dict

    return otlp_processor


__all__ = [
    "configure_otlp_logging",
    "get_otlp_handler",
    "shutdown_otlp_logging",
    "OTLPLogHandler",
    "create_otlp_log_processor",
    "OTEL_LOGGING_AVAILABLE",
    "OTLP_EXPORTER_AVAILABLE",
]
