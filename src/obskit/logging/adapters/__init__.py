"""
Logging Adapters - Pluggable Backend System for obskit Logging
===============================================================

This module provides adapters for different logging backends.
By default, structlog is used.

Available Adapters
------------------
- ``StructlogAdapter``: Default adapter using structlog (recommended)

Usage
-----
The adapter is automatically selected based on configuration:

.. code-block:: python

    from obskit import configure

    # Use structlog (default)
    configure(service_name="my-service")

Custom Adapters
---------------
You can create custom adapters by implementing LoggerInterface:

.. code-block:: python


    class MyCustomAdapter(LoggerInterface):
        def info(self, event: str, **kwargs) -> None:
            # Custom implementation
            pass  # NOSONAR
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
    pass  # NOSONAR
