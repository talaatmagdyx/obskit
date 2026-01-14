"""Distributed tracing module using OpenTelemetry.

Provides distributed tracing integration for request tracking
across service boundaries.

Example:
    >>> from obskit.tracing import get_tracer, trace_span
    >>>
    >>> tracer = get_tracer()
    >>>
    >>> with trace_span("process_order", attributes={"order_id": "123"}):
    ...     process_order()
"""

from obskit.tracing.tracer import (
    configure_tracing,
    extract_trace_context,
    get_tracer,
    inject_trace_context,
    trace_operation,
    trace_span,
)

__all__ = [
    "get_tracer",
    "trace_span",
    "trace_operation",
    "inject_trace_context",
    "extract_trace_context",
    "configure_tracing",
]
