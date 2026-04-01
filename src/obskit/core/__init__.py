"""
Core Module for obskit
======================

Provides fundamental utilities:

- **Context Propagation**: Correlation ID management using contextvars
- **Type Definitions**: Common types and protocols
"""

from obskit.core.context import (
    async_correlation_context,
    correlation_context,
    get_correlation_id,
    set_correlation_id,
)
from obskit.core.types import (
    Component,
    ErrorType,
    Operation,
    Status,
)

__all__ = [
    "get_correlation_id",
    "set_correlation_id",
    "correlation_context",
    "async_correlation_context",
    "Component",
    "Operation",
    "Status",
    "ErrorType",
]
