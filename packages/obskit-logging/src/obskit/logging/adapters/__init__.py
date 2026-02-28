"""
Logging Adapters - Pluggable Backend System for obskit Logging
===============================================================

This module provides adapters for different logging backends.
By default, structlog is used, but loguru can be enabled via configuration.

Available Adapters
------------------
- ``StructlogAdapter``: Default adapter using structlog (recommended)
- ``LoguruAdapter``: Optional adapter using loguru

Usage
-----
The adapter is automatically selected based on configuration:

.. code-block:: python

    from obskit import configure

    # Use structlog (default)
    configure(service_name="my-service")

    # Use loguru
    configure(service_name="my-service", logging_backend="loguru")

    # Auto-detect (prefers structlog if both installed)
    configure(service_name="my-service", logging_backend="auto")

Custom Adapters
---------------
You can create custom adapters by implementing LoggerInterface:

.. code-block:: python

    from obskit.interfaces import LoggerInterface

    class MyCustomAdapter(LoggerInterface):
        def info(self, event: str, **kwargs) -> None:
            # Custom implementation
            pass
"""

from obskit.logging.adapters.base import LoggerAdapter

__all__ = ["LoggerAdapter"]

# Try to import adapters - they may not be available if dependencies aren't installed
_adapters: list[str] = []

try:
    from obskit.logging.adapters.structlog_adapter import StructlogAdapter

    _adapters.append("StructlogAdapter")
    __all__.append("StructlogAdapter")
except ImportError:  # pragma: no cover
    pass

try:
    from obskit.logging.adapters.loguru_adapter import LoguruAdapter

    _adapters.append("LoguruAdapter")
    __all__.append("LoguruAdapter")
except ImportError:  # pragma: no cover
    pass
