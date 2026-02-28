"""
Logger Interface - Abstract Base Class for Logging Backends
============================================================

This module defines the contract for logging backends in obskit.
Implementations can use structlog, loguru, or custom logging solutions.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class LoggerInterface(ABC):
    """
    Abstract base class for logging backends.

    This interface defines the contract that all logging adapters must implement.
    It provides a consistent API regardless of the underlying logging library.

    Methods
    -------
    debug(event, **kwargs)
        Log a debug message.
    info(event, **kwargs)
        Log an info message.
    warning(event, **kwargs)
        Log a warning message.
    error(event, **kwargs)
        Log an error message.
    critical(event, **kwargs)
        Log a critical message.
    exception(event, **kwargs)
        Log an exception with traceback.
    bind(**kwargs)
        Create a new logger with bound context.

    Example
    -------
    >>> class MyLogger(LoggerInterface):
    ...     def info(self, event: str, **kwargs) -> None:
    ...         print(f"[INFO] {event}: {kwargs}")
    ...     # ... implement other methods
    """

    @abstractmethod
    def debug(self, event: str, **kwargs: Any) -> None:
        """
        Log a debug message.

        Parameters
        ----------
        event : str
            The event name or message.
        **kwargs : Any
            Additional structured data to include in the log.
        """

    @abstractmethod
    def info(self, event: str, **kwargs: Any) -> None:
        """
        Log an info message.

        Parameters
        ----------
        event : str
            The event name or message.
        **kwargs : Any
            Additional structured data to include in the log.
        """

    @abstractmethod
    def warning(self, event: str, **kwargs: Any) -> None:
        """
        Log a warning message.

        Parameters
        ----------
        event : str
            The event name or message.
        **kwargs : Any
            Additional structured data to include in the log.
        """

    @abstractmethod
    def error(self, event: str, **kwargs: Any) -> None:
        """
        Log an error message.

        Parameters
        ----------
        event : str
            The event name or message.
        **kwargs : Any
            Additional structured data to include in the log.
        """

    @abstractmethod
    def critical(self, event: str, **kwargs: Any) -> None:
        """
        Log a critical message.

        Parameters
        ----------
        event : str
            The event name or message.
        **kwargs : Any
            Additional structured data to include in the log.
        """

    @abstractmethod
    def exception(self, event: str, **kwargs: Any) -> None:
        """
        Log an exception with traceback.

        Parameters
        ----------
        event : str
            The event name or message.
        **kwargs : Any
            Additional structured data to include in the log.
        """

    @abstractmethod
    def bind(self, **kwargs: Any) -> LoggerInterface:
        """
        Create a new logger with bound context.

        Parameters
        ----------
        **kwargs : Any
            Context data to bind to the new logger.

        Returns
        -------
        LoggerInterface
            A new logger instance with the bound context.

        Example
        -------
        >>> logger = get_logger()
        >>> request_logger = logger.bind(request_id="abc123")
        >>> request_logger.info("Processing request")
        """

    def msg(self, event: str, **kwargs: Any) -> None:
        """
        Alias for info(). Provided for structlog compatibility.

        Parameters
        ----------
        event : str
            The event name or message.
        **kwargs : Any
            Additional structured data.
        """
        self.info(event, **kwargs)

    def warn(self, event: str, **kwargs: Any) -> None:
        """
        Alias for warning(). Provided for compatibility.

        Parameters
        ----------
        event : str
            The event name or message.
        **kwargs : Any
            Additional structured data.
        """
        self.warning(event, **kwargs)
