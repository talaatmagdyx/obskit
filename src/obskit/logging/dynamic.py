"""
Dynamic Log Level Adjustment
=============================

This module provides runtime log level adjustment without requiring
application restart.

Example - Basic Usage
---------------------
.. code-block:: python

    from obskit.logging.dynamic import set_log_level, get_log_level

    # Change log level at runtime
    set_log_level("DEBUG")

    # Get current log level
    current = get_log_level()
"""

from __future__ import annotations

import logging
from typing import Literal

from obskit.config import get_settings
from obskit.logging.logger import configure_logging, get_logger

logger = get_logger("obskit.logging.dynamic")

# Cache of loggers by name for quick level updates
_logger_cache: dict[str, logging.Logger] = {}


def set_log_level(  # pragma: no cover
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
    component: str | None = None,
) -> None:
    """
    Set log level at runtime.

    This function allows changing log levels without restarting the application.
    Useful for debugging production issues or adjusting verbosity on demand.

    Parameters
    ----------
    level : str
        New log level. Must be one of: DEBUG, INFO, WARNING, ERROR, CRITICAL.

    component : str, optional
        Specific component/logger name to update.
        If None, updates all loggers and global settings.

    Example
    -------
    >>> from obskit.logging.dynamic import set_log_level
    >>>
    >>> # Set global log level
    >>> set_log_level("DEBUG")
    >>>
    >>> # Set level for specific component
    >>> set_log_level("DEBUG", component="obskit.metrics")
    """
    level_value = getattr(logging, level.upper())

    if component:
        # Update specific logger
        logger_instance = logging.getLogger(component)
        logger_instance.setLevel(level_value)
        _logger_cache[component] = logger_instance
        logger.info(
            "log_level_changed",
            component=component,
            level=level,
        )
    else:
        # Update all loggers and settings
        root_logger = logging.getLogger()
        root_logger.setLevel(level_value)

        # Update all cached loggers
        for cached_logger in _logger_cache.values():
            cached_logger.setLevel(level_value)

        # Update settings (requires reconfiguration)
        from obskit.config import configure

        get_settings()
        configure(log_level=level)

        # Reconfigure logging
        configure_logging()

        logger.info(
            "global_log_level_changed",
            level=level,
        )


def get_log_level(component: str | None = None) -> str:  # pragma: no cover
    """
    Get current log level.

    Parameters
    ----------
    component : str, optional
        Component/logger name. If None, returns global level.

    Returns
    -------
    str
        Current log level.
    """
    if component:
        logger_instance = logging.getLogger(component)
        level_value = logger_instance.getEffectiveLevel()
    else:
        root_logger = logging.getLogger()
        level_value = root_logger.getEffectiveLevel()
        if level_value == logging.NOTSET:
            # Fall back to settings
            settings = get_settings()
            level_value = getattr(logging, settings.log_level.upper())

    level_names = {
        logging.DEBUG: "DEBUG",
        logging.INFO: "INFO",
        logging.WARNING: "WARNING",
        logging.ERROR: "ERROR",
        logging.CRITICAL: "CRITICAL",
    }

    return level_names.get(level_value, "INFO")


def register_logger(name: str, logger_instance: logging.Logger) -> None:  # pragma: no cover
    """
    Register a logger for dynamic level management.

    Parameters
    ----------
    name : str
        Logger name.
    logger_instance : logging.Logger
        Logger instance.
    """
    _logger_cache[name] = logger_instance


__all__ = ["set_log_level", "get_log_level", "register_logger"]
