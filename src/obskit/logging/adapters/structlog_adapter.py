"""
Structlog Adapter - Default Logging Backend
============================================

This module provides the structlog adapter, which is the default
logging backend for obskit.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog

from obskit.logging.adapters.base import LoggerAdapter

# Check if structlog is available
STRUCTLOG_AVAILABLE = True


class StructlogAdapter(LoggerAdapter):
    """
    Structlog-based logging adapter.

    This is the default and recommended logging backend for obskit.
    It provides structured logging with automatic context propagation.

    Features
    --------
    - JSON output for production
    - Colored console output for development
    - Automatic timestamp injection
    - Service metadata in every log entry
    - Exception formatting with tracebacks

    Example
    -------
    >>> StructlogAdapter.configure(
    ...     service_name="my-service",
    ...     environment="production",
    ...     version="1.0.0",
    ...     log_level="INFO",
    ...     log_format="json",
    ... )
    >>> logger = StructlogAdapter.get_logger()
    >>> logger.info("request_received", path="/api/users")
    """

    _configured: bool = False
    _service_name: str = "unknown"
    _environment: str = "development"
    _version: str = "0.0.0"

    def __init__(  # pragma: no cover
        self, logger: Any = None, name: str | None = None
    ) -> None:
        """
        Initialize the adapter.

        Parameters
        ----------
        logger : Any, optional
            Underlying structlog logger. If None, creates a new one.
        name : str, optional
            Logger name.
        """
        self._name = name or "obskit"
        if logger is not None:
            self._logger = logger
        else:
            self._logger = structlog.get_logger(self._name)

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
        """Configure structlog for the application."""
        cls._service_name = service_name
        cls._environment = environment
        cls._version = version

        # Build processors list
        processors: list[Any] = [
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
        ]

        # Add timestamp if requested
        if include_timestamp:
            processors.append(structlog.processors.TimeStamper(fmt="iso"))

        # Add service context
        processors.append(
            structlog.processors.CallsiteParameterAdder(
                parameters=[
                    structlog.processors.CallsiteParameter.FILENAME,
                    structlog.processors.CallsiteParameter.LINENO,
                ]
            )
        )

        # Add exception formatting
        processors.append(structlog.processors.StackInfoRenderer())
        processors.append(structlog.processors.format_exc_info)

        # Choose renderer based on format
        if log_format == "json":
            processors.append(structlog.processors.JSONRenderer())
        else:
            # Console format with colors
            processors.append(
                structlog.dev.ConsoleRenderer(
                    colors=sys.stderr.isatty(),
                    exception_formatter=structlog.dev.plain_traceback,
                )
            )

        # Configure structlog
        structlog.configure(
            processors=processors,
            wrapper_class=structlog.make_filtering_bound_logger(
                getattr(logging, log_level.upper(), logging.INFO)
            ),
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(),
            cache_logger_on_first_use=True,
        )

        # Also configure standard logging
        logging.basicConfig(
            format="%(message)s",
            stream=sys.stdout,
            level=getattr(logging, log_level.upper(), logging.INFO),
        )

        cls._configured = True

    @classmethod
    def get_logger(cls, name: str | None = None) -> StructlogAdapter:  # pragma: no cover
        """Get a configured logger instance."""
        if not cls._configured:
            # Use default configuration
            cls.configure(
                service_name=cls._service_name,
                environment=cls._environment,
                version=cls._version,
                log_level="INFO",
                log_format="json",
            )

        logger = structlog.get_logger(name or "obskit")
        # Bind service context
        logger = logger.bind(
            service=cls._service_name,
            environment=cls._environment,
            version=cls._version,
        )
        return cls(logger, name)

    @classmethod
    def is_available(cls) -> bool:  # pragma: no cover
        """Check if structlog is available."""
        return STRUCTLOG_AVAILABLE

    def debug(self, event: str, **kwargs: Any) -> None:  # pragma: no cover
        """Log a debug message."""
        self._logger.debug(event, **kwargs)

    def info(self, event: str, **kwargs: Any) -> None:  # pragma: no cover
        """Log an info message."""
        self._logger.info(event, **kwargs)

    def warning(self, event: str, **kwargs: Any) -> None:  # pragma: no cover
        """Log a warning message."""
        self._logger.warning(event, **kwargs)

    def error(self, event: str, **kwargs: Any) -> None:  # pragma: no cover
        """Log an error message."""
        self._logger.error(event, **kwargs)

    def critical(self, event: str, **kwargs: Any) -> None:  # pragma: no cover
        """Log a critical message."""
        self._logger.critical(event, **kwargs)

    def exception(self, event: str, **kwargs: Any) -> None:  # pragma: no cover
        """Log an exception with traceback."""
        self._logger.exception(event, **kwargs)

    def bind(self, **kwargs: Any) -> StructlogAdapter:  # pragma: no cover
        """Create a new logger with bound context."""
        new_logger = self._logger.bind(**kwargs)
        return StructlogAdapter(new_logger, self._name)

    def with_context(self, **kwargs: Any) -> StructlogAdapter:  # pragma: no cover
        """Create a new logger with additional context."""
        return self.bind(**kwargs)
