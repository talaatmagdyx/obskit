"""
Logger Factory - Creates Logger Instances Based on Configuration
=================================================================

This module provides factory functions for creating logger instances
based on the configured backend.
"""

from __future__ import annotations

import threading
from typing import Any, Literal

from obskit.logging.adapters.base import LoggerAdapter

# Backend registry
_backends: dict[str, type[LoggerAdapter]] = {}
_configured_backend: type[LoggerAdapter] | None = None
_factory_lock = threading.Lock()

# Register available backends
try:
    from obskit.logging.adapters.structlog_adapter import StructlogAdapter

    _backends["structlog"] = StructlogAdapter
except ImportError:  # pragma: no cover
    pass

try:
    from obskit.logging.adapters.loguru_adapter import LoguruAdapter

    _backends["loguru"] = LoguruAdapter
except ImportError:  # pragma: no cover
    pass


def get_available_backends() -> list[str]:  # pragma: no cover
    """
    Get list of available logging backends.

    Returns
    -------
    list[str]
        Names of available backends.
    """
    return [name for name, backend in _backends.items() if backend.is_available()]


def configure_logging_backend(  # pragma: no cover
    backend: Literal["structlog", "loguru", "auto"] = "structlog",
    service_name: str = "unknown",
    environment: str = "development",
    version: str = "0.0.0",
    log_level: str = "INFO",
    log_format: Literal["json", "console"] = "json",
    include_timestamp: bool = True,
    **kwargs: Any,
) -> type[LoggerAdapter]:
    """
    Configure the logging backend.

    Parameters
    ----------
    backend : {"structlog", "loguru", "auto"}
        Which logging backend to use.
        - "structlog": Use structlog (default, recommended)
        - "loguru": Use loguru
        - "auto": Auto-detect, prefer structlog if both installed
    service_name : str
        Name of the service.
    environment : str
        Deployment environment.
    version : str
        Service version.
    log_level : str
        Minimum log level.
    log_format : {"json", "console"}
        Output format.
    include_timestamp : bool
        Whether to include timestamps.
    **kwargs : Any
        Additional backend-specific configuration.

    Returns
    -------
    type[LoggerAdapter]
        The configured backend class.

    Raises
    ------
    ImportError
        If the requested backend is not available.

    Example
    -------
    >>> configure_logging_backend(
    ...     backend="structlog",
    ...     service_name="my-service",
    ...     log_level="INFO",
    ... )
    """
    global _configured_backend

    with _factory_lock:
        # Determine which backend to use
        if backend == "auto":
            # Prefer structlog, fall back to loguru
            if "structlog" in _backends and _backends["structlog"].is_available():
                backend_class = _backends["structlog"]
            elif "loguru" in _backends and _backends["loguru"].is_available():
                backend_class = _backends["loguru"]
            else:
                raise ImportError(
                    "No logging backend available. Install structlog or loguru: "
                    "pip install structlog or pip install loguru"
                )
        else:
            if backend not in _backends:
                raise ImportError(
                    f"Logging backend '{backend}' is not available. "
                    f"Available backends: {list(_backends.keys())}"
                )
            backend_class = _backends[backend]
            if not backend_class.is_available():
                raise ImportError(
                    f"Logging backend '{backend}' is not installed. "
                    f"Install with: pip install obskit[{backend}]"
                )

        # Configure the backend
        backend_class.configure(
            service_name=service_name,
            environment=environment,
            version=version,
            log_level=log_level,
            log_format=log_format,
            include_timestamp=include_timestamp,
            **kwargs,
        )

        _configured_backend = backend_class
        return backend_class


def get_logger_from_factory(name: str | None = None) -> LoggerAdapter:  # pragma: no cover
    """
    Get a logger instance from the configured backend.

    Parameters
    ----------
    name : str, optional
        Logger name.

    Returns
    -------
    LoggerAdapter
        Configured logger instance.

    Raises
    ------
    RuntimeError
        If no backend has been configured.
    """
    global _configured_backend

    with _factory_lock:
        if _configured_backend is None:
            # Auto-configure with defaults
            configure_logging_backend(backend="auto")

        if _configured_backend is None:
            raise RuntimeError("No logging backend configured")

        return _configured_backend.get_logger(name)


def register_backend(name: str, backend_class: type[LoggerAdapter]) -> None:  # pragma: no cover
    """
    Register a custom logging backend.

    Parameters
    ----------
    name : str
        Name for the backend.
    backend_class : type[LoggerAdapter]
        The backend class to register.

    Example
    -------
    >>> class MyCustomBackend(LoggerAdapter):
    ...     # Implementation
    ...     pass
    >>>
    >>> register_backend("custom", MyCustomBackend)
    >>> configure_logging_backend(backend="custom", ...)
    """
    with _factory_lock:
        _backends[name] = backend_class


def reset_logging_factory() -> None:
    """
    Reset the logging factory.

    Primarily useful for testing.
    """
    global _configured_backend

    with _factory_lock:
        _configured_backend = None
