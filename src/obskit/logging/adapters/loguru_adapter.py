"""
Loguru Adapter - Optional Logging Backend
==========================================

This module provides the loguru adapter for teams that prefer
loguru over structlog.

Installation
------------
.. code-block:: bash

    pip install obskit[loguru]
"""

from __future__ import annotations

import sys
from datetime import UTC
from typing import Any

from obskit.logging.adapters.base import LoggerAdapter

# Check if loguru is available
try:
    from loguru import Logger
    from loguru import logger as loguru_logger

    LOGURU_AVAILABLE = True
except ImportError:  # pragma: no cover
    LOGURU_AVAILABLE = False
    loguru_logger = None  # type: ignore[assignment]
    Logger = None  # type: ignore[assignment, misc]


class LoguruAdapter(LoggerAdapter):
    """
    Loguru-based logging adapter.

    Provides structured logging using the loguru library.
    Requires the loguru optional dependency.

    Features
    --------
    - Simple API with powerful features
    - Automatic exception catching
    - Colorful and customizable output
    - Lazy evaluation of log messages
    - Asynchronous logging support

    Example
    -------
    >>> LoguruAdapter.configure(
    ...     service_name="my-service",
    ...     environment="production",
    ...     version="1.0.0",
    ...     log_level="INFO",
    ...     log_format="json",
    ... )
    >>> logger = LoguruAdapter.get_logger()
    >>> logger.info("request_received", path="/api/users")
    """

    _configured: bool = False
    _service_name: str = "unknown"
    _environment: str = "development"
    _version: str = "0.0.0"
    _context: dict[str, Any]

    def __init__(  # pragma: no cover
        self, context: dict[str, Any] | None = None, name: str | None = None
    ) -> None:
        """
        Initialize the adapter.

        Parameters
        ----------
        context : dict, optional
            Initial context for log entries.
        name : str, optional
            Logger name.
        """
        self._name = name or "obskit"
        self._context = context or {}

    @classmethod
    def configure(  # pragma: no cover
        cls,
        service_name: str,
        environment: str,
        version: str,
        log_level: str,
        log_format: str,
        include_timestamp: bool = True,
        **kwargs: Any,
    ) -> None:
        """Configure loguru for the application."""
        if not LOGURU_AVAILABLE:
            raise ImportError("loguru is not installed. Install with: pip install obskit[loguru]")

        cls._service_name = service_name
        cls._environment = environment
        cls._version = version

        # Remove default handler
        loguru_logger.remove()

        # Build format string
        if log_format == "json":
            # JSON format
            def json_serializer(record: dict[str, Any]) -> str:
                import json
                from datetime import datetime

                log_entry: dict[str, Any] = {
                    "event": record["message"],
                    "level": record["level"].name.lower(),
                    "service": cls._service_name,
                    "environment": cls._environment,
                    "version": cls._version,
                }

                if include_timestamp:
                    log_entry["timestamp"] = datetime.now(UTC).isoformat()

                # Add extra context
                if record.get("extra"):
                    log_entry.update(record["extra"])

                # Add exception info if present
                if record["exception"]:
                    log_entry["exception"] = {
                        "type": record["exception"].type.__name__
                        if record["exception"].type
                        else None,
                        "value": str(record["exception"].value)
                        if record["exception"].value
                        else None,
                        "traceback": record["exception"].traceback,
                    }

                return json.dumps(log_entry)

            loguru_logger.add(
                sys.stderr,
                format="{message}",
                level=log_level.upper(),
                serialize=False,
                filter=lambda record: True,
            )

            # Patch to use JSON serializer
            loguru_logger.add(
                sys.stdout,
                format=json_serializer,  # type: ignore[arg-type]
                level=log_level.upper(),
                colorize=False,
            )
        else:
            # Console format with colors
            format_parts = []
            if include_timestamp:
                format_parts.append("<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green>")
            format_parts.extend(
                [
                    "<level>{level: <8}</level>",
                    f"<cyan>{service_name}</cyan>",
                    "<white>{message}</white>",
                    "<dim>{extra}</dim>",
                ]
            )

            loguru_logger.add(
                sys.stderr,
                format=" | ".join(format_parts),
                level=log_level.upper(),
                colorize=True,
            )

        cls._configured = True

    @classmethod
    def get_logger(cls, name: str | None = None) -> LoguruAdapter:  # pragma: no cover
        """Get a configured logger instance."""
        if not LOGURU_AVAILABLE:
            raise ImportError("loguru is not installed. Install with: pip install obskit[loguru]")

        if not cls._configured:
            # Use default configuration
            cls.configure(
                service_name=cls._service_name,
                environment=cls._environment,
                version=cls._version,
                log_level="INFO",
                log_format="json",
            )

        # Create with service context
        context = {
            "service": cls._service_name,
            "environment": cls._environment,
            "version": cls._version,
        }
        return cls(context, name)

    @classmethod
    def is_available(cls) -> bool:  # pragma: no cover
        """Check if loguru is available."""
        return LOGURU_AVAILABLE

    def _log(self, level: str, event: str, **kwargs: Any) -> None:  # pragma: no cover
        """Internal logging method."""
        if not LOGURU_AVAILABLE:  # pragma: no branch
            return

        # Merge context with kwargs
        all_context = {**self._context, **kwargs}

        # Use loguru's opt() for extra context
        loguru_logger.opt(depth=2).bind(**all_context).log(level.upper(), event)  # pragma: no cover

    def debug(self, event: str, **kwargs: Any) -> None:  # pragma: no cover
        """Log a debug message."""
        self._log("DEBUG", event, **kwargs)

    def info(self, event: str, **kwargs: Any) -> None:  # pragma: no cover
        """Log an info message."""
        self._log("INFO", event, **kwargs)

    def warning(self, event: str, **kwargs: Any) -> None:  # pragma: no cover
        """Log a warning message."""
        self._log("WARNING", event, **kwargs)

    def error(self, event: str, **kwargs: Any) -> None:  # pragma: no cover
        """Log an error message."""
        self._log("ERROR", event, **kwargs)

    def critical(self, event: str, **kwargs: Any) -> None:  # pragma: no cover
        """Log a critical message."""
        self._log("CRITICAL", event, **kwargs)

    def exception(self, event: str, **kwargs: Any) -> None:  # pragma: no cover
        """Log an exception with traceback."""
        if LOGURU_AVAILABLE:
            all_context = {**self._context, **kwargs}
            loguru_logger.opt(depth=1, exception=True).bind(**all_context).error(event)

    def bind(self, **kwargs: Any) -> LoguruAdapter:  # pragma: no cover
        """Create a new logger with bound context."""
        new_context = {**self._context, **kwargs}
        return LoguruAdapter(new_context, self._name)

    def with_context(self, **kwargs: Any) -> LoguruAdapter:  # pragma: no cover
        """Create a new logger with additional context."""
        return self.bind(**kwargs)
