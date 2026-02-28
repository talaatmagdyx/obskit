"""Distributed tracing module using OpenTelemetry.

Provides distributed tracing integration for request tracking
across service boundaries, including zero-code auto-instrumentation
for FastAPI, SQLAlchemy, Redis, httpx, Celery, and more.

Quick-start::

    # Call ONCE at application startup (before importing FastAPI etc.)
    from obskit.tracing import setup_tracing
    setup_tracing()                          # auto-detects installed libs

    # Local development — print spans to stdout
    setup_tracing(debug=True)

    # Production — remote collector + 10 % sampling
    setup_tracing(
        exporter_endpoint="http://tempo:4317",
        sample_rate=0.1,
    )

    # Or with an explicit library list:
    setup_tracing(
        exporter_endpoint="http://tempo:4317",
        instrument=["fastapi", "sqlalchemy", "redis"],
    )

Manual spans (no auto-instrumentation)::

    from obskit.tracing import get_tracer, trace_span, async_trace_span

    # Sync
    with trace_span("process_order", attributes={"order_id": "123"}):
        process_order()

    # Async
    async with async_trace_span("fetch_user"):
        user = await db.get_user(uid)

W3C Baggage propagation::

    from obskit.tracing import set_baggage, get_baggage

    set_baggage("tenant_id", "acme-corp")
    tenant = get_baggage("tenant_id")   # "acme-corp"

Trace-log correlation::

    from obskit.tracing import get_current_trace_id, get_current_span_id

    trace_id = get_current_trace_id()   # "4bf92f3577b34da6..."
    span_id  = get_current_span_id()    # "00f067aa0ba902b7"
"""

from obskit.tracing.auto import (
    apply_instrumentors,
    detect_available_instrumentors,
    get_applied_instrumentors,
    get_instrumentor_registry,
    uninstrument_all,
)
from obskit.tracing.setup import setup_tracing
from obskit.tracing.tracer import (
    async_trace_span,
    clear_baggage,
    configure_tracing,
    extract_trace_context,
    get_all_baggage,
    get_baggage,
    get_current_span_id,
    get_current_trace_id,
    get_tracer,
    inject_trace_context,
    is_tracing_available,
    reset_tracing,
    set_baggage,
    shutdown_tracing,
    trace_operation,
    trace_span,
)

__all__ = [
    # ── Unified setup (recommended entry point) ──────────────────────────
    "setup_tracing",
    # ── Auto-instrumentation ─────────────────────────────────────────────
    "apply_instrumentors",
    "detect_available_instrumentors",
    "get_applied_instrumentors",
    "get_instrumentor_registry",
    "uninstrument_all",
    # ── Manual tracing ───────────────────────────────────────────────────
    "get_tracer",
    "trace_span",
    "async_trace_span",
    "trace_operation",
    "inject_trace_context",
    "extract_trace_context",
    "configure_tracing",
    "is_tracing_available",
    "reset_tracing",
    "shutdown_tracing",
    # ── W3C Baggage ──────────────────────────────────────────────────────
    "set_baggage",
    "get_baggage",
    "get_all_baggage",
    "clear_baggage",
    # ── Trace-log correlation helpers ─────────────────────────────────────
    "get_current_trace_id",
    "get_current_span_id",
]
