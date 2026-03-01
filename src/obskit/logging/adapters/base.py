"""
Base Logger Adapter - Abstract Base for Logging Backends
=========================================================

This module provides the base adapter class that all logging adapters
must inherit from.
"""

from __future__ import annotations

from abc import abstractmethod
from typing import Any

from obskit.interfaces.logging import LoggerInterface


class LoggerAdapter(LoggerInterface):
    """
    Base adapter class for logging backends.

    This class extends LoggerInterface with additional methods
    for adapter-specific configuration and lifecycle management.

    Subclasses must implement all abstract methods from LoggerInterface
    plus the configure() class method.

    Class Methods
    -------------
    configure(service_name, environment, version, log_level, log_format, **kwargs)
        Configure the logging backend.

    Example
    -------
    >>> class MyAdapter(LoggerAdapter):
    ...     @classmethod
    ...     def configure(cls, service_name, environment, version, log_level, log_format, **kwargs):
    ...         # Configure the backend
    ...         pass
    ...
    ...     def info(self, event, **kwargs):
    ...         # Log info message
    ...         pass
    """

    @classmethod
    @abstractmethod
    def configure(
        cls,
        service_name: str,
        environment: str,
        version: str,
        log_level: str,
        log_format: str,
        include_timestamp: bool = True,
        **kwargs: Any,
    ) -> None:
        """
        Configure the logging backend.

        This method should be called once at application startup to
        configure the logging system.

        Parameters
        ----------
        service_name : str
            Name of the service.
        environment : str
            Deployment environment (development, staging, production).
        version : str
            Service version.
        log_level : str
            Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_format : str
            Output format ("json" or "console").
        include_timestamp : bool
            Whether to include timestamps.
        **kwargs : Any
            Additional backend-specific configuration.
        """

    @classmethod
    @abstractmethod
    def get_logger(cls, name: str | None = None) -> LoggerAdapter:
        """
        Get a logger instance.

        Parameters
        ----------
        name : str, optional
            Logger name. If None, returns the root logger.

        Returns
        -------
        LoggerAdapter
            Configured logger instance.
        """

    @classmethod
    @abstractmethod
    def is_available(cls) -> bool:
        """
        Check if the logging backend is available.

        Returns
        -------
        bool
            True if the backend's dependencies are installed.
        """

    @abstractmethod
    def with_context(self, **kwargs: Any) -> LoggerAdapter:
        """
        Create a new logger with additional context.

        Similar to bind() but returns the concrete adapter type.

        Parameters
        ----------
        **kwargs : Any
            Context data to add.

        Returns
        -------
        LoggerAdapter
            New logger with added context.
        """
