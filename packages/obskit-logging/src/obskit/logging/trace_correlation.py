"""Trace-log correlation for obskit-logging.

When an OpenTelemetry span is active, every structured log record
emitted through obskit automatically gains ``trace_id`` and ``span_id``
fields.  This lets you jump straight from a log line in Loki/Grafana to
the corresponding trace in Tempo — no extra code needed.

The correlation is **optional and zero-dependency**: if ``obskit-tracing``
(and by extension ``opentelemetry-api``) is not installed, the processor
is a transparent no-op.

Usage
-----
The processor is injected into the structlog pipeline automatically when
you call :func:`configure_logging`.  You can also call
:func:`configure_trace_log_correlation` explicitly to add it after the
fact::

    from obskit.logging.trace_correlation import configure_trace_log_correlation

    configure_trace_log_correlation()

Or use the low-level processor directly in a custom pipeline::

    import structlog
    from obskit.logging.trace_correlation import add_trace_context

    structlog.configure(processors=[add_trace_context, ...])

Output
------
When a span is active the log record gains two extra fields:

.. code-block:: json

    {
        "event":    "order_placed",
        "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
        "span_id":  "00f067aa0ba902b7"
    }

If no span is active the fields are simply absent — the log is
unchanged.
"""

from __future__ import annotations

from structlog.types import EventDict, WrappedLogger

# ---------------------------------------------------------------------------
# OTel availability check (graceful degradation)
# ---------------------------------------------------------------------------

try:
    from opentelemetry import trace as _otel_trace

    _OTEL_AVAILABLE = True
except ImportError:
    _otel_trace = None  # type: ignore[assignment]
    _OTEL_AVAILABLE = False


# ---------------------------------------------------------------------------
# Structlog processor
# ---------------------------------------------------------------------------


def add_trace_context(
    logger: WrappedLogger,
    method_name: str,
    event_dict: EventDict,
) -> EventDict:
    """Structlog processor — injects ``trace_id`` and ``span_id`` when a span is active.

    Parameters
    ----------
    logger:
        The wrapped logger (unused, required by structlog's API).
    method_name:
        The log-level method name (``"info"``, ``"error"``, …).
    event_dict:
        The mutable event dictionary.  ``trace_id`` and ``span_id`` are
        added only when a valid OTel span is active.

    Returns
    -------
    EventDict
        The (possibly enriched) event dictionary.

    Notes
    -----
    *   Completely safe to add even when ``opentelemetry-api`` is not
        installed — falls back to a no-op.
    *   Fields are only added when ``span_context.is_valid`` is ``True``,
        so the no-op / INVALID_SPAN case produces no extra keys.
    """
    if not _OTEL_AVAILABLE or _otel_trace is None:
        return event_dict

    try:
        span = _otel_trace.get_current_span()
        ctx = span.get_span_context()
        if ctx and ctx.is_valid:
            event_dict["trace_id"] = format(ctx.trace_id, "032x")
            event_dict["span_id"] = format(ctx.span_id, "016x")
    except Exception:  # nosec B110 — never let logging crash the app
        pass

    return event_dict


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def get_trace_context() -> dict[str, str]:
    """Return ``{"trace_id": ..., "span_id": ...}`` for the active span.

    Returns an empty dict when no span is active or OTel is unavailable.

    Example::

        ctx = get_trace_context()
        # {"trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
        #  "span_id":  "00f067aa0ba902b7"}
    """
    if not _OTEL_AVAILABLE or _otel_trace is None:
        return {}

    try:
        span = _otel_trace.get_current_span()
        ctx = span.get_span_context()
        if ctx and ctx.is_valid:
            return {
                "trace_id": format(ctx.trace_id, "032x"),
                "span_id": format(ctx.span_id, "016x"),
            }
    except Exception:  # nosec B110
        pass

    return {}


def is_trace_correlation_available() -> bool:
    """Return *True* if ``opentelemetry-api`` is installed.

    Use this to decide whether to surface trace links in dashboards or
    error pages.

    Example::

        if is_trace_correlation_available():
            print("Trace links available")
    """
    return _OTEL_AVAILABLE
