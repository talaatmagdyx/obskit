"""OpenTelemetry tracer implementation."""

from __future__ import annotations

import contextlib
import logging as _std_logging
import threading
from collections.abc import AsyncGenerator, Callable, Generator
from functools import wraps
from typing import TYPE_CHECKING, Any, ParamSpec, TypeVar

from obskit.config import get_settings
from obskit.tracing._version import __version__ as _OBSKIT_TRACING_VERSION

_tracer_logger = _std_logging.getLogger(__name__)

if TYPE_CHECKING:
    pass  # NOSONAR

# Check if OpenTelemetry is available
try:
    from opentelemetry import baggage as baggage_api
    from opentelemetry import context as context_api
    from opentelemetry import trace
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor
    from opentelemetry.trace import Status, StatusCode, Tracer

    OPENTELEMETRY_AVAILABLE = True
except ImportError:  # pragma: no cover
    OPENTELEMETRY_AVAILABLE = False
    trace = None  # type: ignore[assignment]
    TracerProvider = None  # type: ignore[misc, assignment]
    BatchSpanProcessor = None  # type: ignore[misc, assignment]
    SimpleSpanProcessor = None  # type: ignore[misc, assignment]
    Resource = None  # type: ignore[misc, assignment]
    Status = None  # type: ignore[misc, assignment]
    StatusCode = None  # type: ignore[misc, assignment]
    Tracer = None  # type: ignore[misc, assignment]
    baggage_api = None  # type: ignore[assignment]
    context_api = None  # type: ignore[assignment]

P = ParamSpec("P")
T = TypeVar("T")

# Global tracer
_tracer: Tracer | None = None
_configured = False
_tracer_lock = threading.Lock()
# Reference to the BatchSpanProcessor so callers can inspect dropped-span count.
_batch_span_processor: object = None


def configure_tracing(
    service_name: str | None = None,
    otlp_endpoint: str | None = None,
    debug: bool = False,
    sample_rate: float = 1.0,
) -> bool:
    """Configure OpenTelemetry tracing.

    Args:
        service_name: Name of the service.
        otlp_endpoint: OTLP collector endpoint.
        debug: When *True*, pretty-prints all spans to stdout via the
               ConsoleSpanExporter — great for local development without
               needing Tempo/Jaeger.
        sample_rate: Fraction of traces to sample in ``[0.0, 1.0]``.
                     ``1.0`` = keep all (default); ``0.1`` = keep 10 %.
                     Uses W3C-compliant ``ParentBased(TraceIdRatioBased)``
                     so the sampling decision propagates from parent spans.

    Returns:
        True if configured successfully, False if OpenTelemetry not available.

    Thread Safety
    -------------
    This function is thread-safe using locks to prevent concurrent configuration.

    Example::

        # Production — remote Tempo, 10 % sampling
        configure_tracing(
            service_name="order-service",
            otlp_endpoint="http://tempo:4317",
            sample_rate=0.1,
        )

        # Development — print every span to stdout
        configure_tracing(debug=True)
    """
    global _configured, _tracer, _batch_span_processor

    if not OPENTELEMETRY_AVAILABLE:  # pragma: no cover
        return False

    with _tracer_lock:
        settings = get_settings()
        service = service_name or settings.service_name
        endpoint = otlp_endpoint or settings.otlp_endpoint

        # ── Resource: service identity + obskit metadata ──────────────────
        resource = Resource.create(
            {
                "service.name": service,
                "service.version": settings.version,
                "deployment.environment": settings.environment,
                # obskit SDK attribution (visible in Grafana Tempo / Jaeger)
                "telemetry.sdk.name": "obskit",
                "telemetry.sdk.version": _OBSKIT_TRACING_VERSION,
                "obskit.version": _OBSKIT_TRACING_VERSION,
            }
        )

        # ── Sampler ───────────────────────────────────────────────────────
        sampler: Any = None
        if sample_rate < 1.0:
            try:
                from opentelemetry.sdk.trace.sampling import (
                    ParentBased,
                    TraceIdRatioBased,
                )

                sampler = ParentBased(TraceIdRatioBased(sample_rate))
            except ImportError:  # pragma: no cover
                sampler = None

        # ── Provider ─────────────────────────────────────────────────────
        provider_kwargs: dict[str, Any] = {"resource": resource}
        if sampler is not None:
            provider_kwargs["sampler"] = sampler
        provider = TracerProvider(**provider_kwargs)

        # ── Debug console exporter ────────────────────────────────────────
        if debug:
            try:
                from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
                    InMemorySpanExporter,
                )

                # Prefer the built-in console exporter
                try:
                    from opentelemetry.sdk.trace.export import ConsoleSpanExporter

                    _console_exporter = ConsoleSpanExporter()
                except ImportError:  # pragma: no cover
                    _console_exporter = InMemorySpanExporter()  # type: ignore[assignment]

                provider.add_span_processor(SimpleSpanProcessor(_console_exporter))
            except ImportError:  # pragma: no cover
                pass  # NOSONAR

        # ── OTLP exporter ─────────────────────────────────────────────────
        # Track whether provider was registered in the OTLP branch so the
        # debug-only fallback below can use a standalone `if` (coverage.py
        # propagates `# pragma: no cover` to sibling `elif` clauses in the
        # same compound statement, making them untrackable).
        _provider_registered = False
        if endpoint and settings.tracing_enabled:  # pragma: no cover
            try:
                from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                    OTLPSpanExporter,
                )

                exporter = OTLPSpanExporter(
                    endpoint=endpoint,
                    insecure=settings.otlp_insecure,
                )

                max_queue_size = getattr(settings, "trace_export_queue_size", 2048)
                max_export_batch_size = getattr(settings, "trace_export_batch_size", 512)
                export_timeout = getattr(settings, "trace_export_timeout", 30.0)

                processor = BatchSpanProcessor(
                    exporter,
                    max_queue_size=max_queue_size,
                    max_export_batch_size=max_export_batch_size,
                    export_timeout_millis=int(export_timeout * 1000),
                )
                provider.add_span_processor(processor)
                # Store processor reference so get_span_drop_count() can inspect it.
                _batch_span_processor = processor
            except ImportError:  # pragma: no cover
                pass  # NOSONAR

            # Set global provider
            trace.set_tracer_provider(provider)

            _tracer = trace.get_tracer(__name__)
            _configured = True
            _provider_registered = True

        # When debug=True but no OTLP endpoint, still set the provider so spans render.
        # Intentionally a separate `if` (not `elif`) so coverage.py can track it
        # independently of the `# pragma: no cover` block above.
        if debug and not _provider_registered:
            trace.set_tracer_provider(provider)
            _tracer = trace.get_tracer(__name__)
            _configured = True
            _tracer_logger.info(
                "tracing_debug_mode_no_otlp_export: spans visible locally only. "
                "Set tracing_enabled=True and otlp_endpoint to export to a backend."
            )

    return True


def get_tracer() -> Tracer | None:
    """Get OpenTelemetry tracer instance.

    Returns:
        Tracer instance or None if not available.

    Thread Safety
    -------------
    This function is thread-safe using double-checked locking pattern.
    """
    global _tracer

    if not OPENTELEMETRY_AVAILABLE:  # pragma: no cover
        return None

    if _tracer is not None:
        return _tracer

    with _tracer_lock:
        if _tracer is None:
            _tracer = trace.get_tracer(__name__)

    return _tracer


# ---------------------------------------------------------------------------
# Sync context manager
# ---------------------------------------------------------------------------


@contextlib.contextmanager
def trace_span(
    name: str,
    component: str | None = None,
    operation: str | None = None,
    attributes: dict[str, Any] | None = None,
) -> Generator[Any, None, None]:
    """Create a *synchronous* trace span context manager.

    Args:
        name: Span name.
        component: Component name added as ``component`` attribute.
        operation: Operation name added as ``operation`` attribute.
        attributes: Additional span attributes.

    Yields:
        Span instance or None if tracing not available.

    Example::

        with trace_span("process_order", attributes={"order_id": "123"}):
            process_order()
    """
    tracer = get_tracer()

    if tracer is None:  # pragma: no cover
        yield None
        return

    with tracer.start_as_current_span(name) as span:
        if span:  # pragma: no branch
            if component:  # pragma: no cover
                span.set_attribute("component", component)
            if operation:  # pragma: no cover
                span.set_attribute("operation", operation)
            if attributes:  # pragma: no cover
                for key, value in attributes.items():
                    # Preserve native OTel types (int, float, bool) to avoid
                    # unnecessary string conversion and loss of type semantics.
                    if isinstance(value, (bool, int, float, str)):
                        span.set_attribute(key, value)
                    else:
                        span.set_attribute(key, str(value))

        try:
            yield span
        except Exception as e:  # pragma: no cover
            if span and Status is not None and StatusCode is not None:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
            raise


# ---------------------------------------------------------------------------
# Async context manager
# ---------------------------------------------------------------------------


@contextlib.asynccontextmanager
async def async_trace_span(
    name: str,
    component: str | None = None,
    operation: str | None = None,
    attributes: dict[str, Any] | None = None,
) -> AsyncGenerator[Any, None]:
    """Create an *asynchronous* trace span context manager.

    Identical to :func:`trace_span` but safe to use with ``async with``
    inside coroutines and async generators.

    Args:
        name: Span name.
        component: Component name.
        operation: Operation name.
        attributes: Additional span attributes.

    Yields:
        Span instance or None if tracing not available.

    Example::

        async with async_trace_span("fetch_user", attributes={"user_id": uid}):
            user = await db.get_user(uid)
    """
    tracer = get_tracer()

    if tracer is None:  # pragma: no cover
        yield None
        return

    with tracer.start_as_current_span(name) as span:
        if span:  # pragma: no branch
            if component:  # pragma: no cover
                span.set_attribute("component", component)
            if operation:  # pragma: no cover
                span.set_attribute("operation", operation)
            if attributes:  # pragma: no cover
                for key, value in attributes.items():
                    # Preserve native OTel types (int, float, bool) to avoid
                    # unnecessary string conversion and loss of type semantics.
                    if isinstance(value, (bool, int, float, str)):
                        span.set_attribute(key, value)
                    else:
                        span.set_attribute(key, str(value))

        try:
            yield span
        except Exception as e:  # pragma: no cover
            if span and Status is not None and StatusCode is not None:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
            raise


# ---------------------------------------------------------------------------
# Decorator
# ---------------------------------------------------------------------------


def trace_operation(
    component: str | None = None,
    operation: str | None = None,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Decorator to trace function execution.

    Args:
        component: Component name (defaults to module name).
        operation: Operation name (defaults to function name).

    Returns:
        Decorator function.

    Example::

        @trace_operation(component="OrderService")
        def create_order(order_data):
            return Order.create(**order_data)
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        comp = component or func.__module__.split(".")[-1]
        op = operation or func.__name__

        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            with trace_span(
                name=f"{comp}.{op}",
                component=comp,
                operation=op,
            ):
                return func(*args, **kwargs)

        return wrapper

    return decorator


# ---------------------------------------------------------------------------
# Context propagation helpers
# ---------------------------------------------------------------------------


def inject_trace_context(headers: dict[str, str] | None = None) -> dict[str, str]:
    """Inject W3C Trace Context headers for outgoing requests.

    Args:
        headers: Dict to inject into. Creates a new dict if *None*.

    Returns:
        Headers dict with ``traceparent`` / ``tracestate`` added.

    Example::

        headers = inject_trace_context()
        async with httpx.AsyncClient() as client:
            await client.get("https://api.example.com/", headers=headers)
    """
    if not OPENTELEMETRY_AVAILABLE:  # pragma: no cover
        return headers or {}

    if headers is None:
        headers = {}

    try:  # pragma: no cover
        from opentelemetry.trace.propagation.tracecontext import (
            TraceContextTextMapPropagator,
        )

        TraceContextTextMapPropagator().inject(headers)  # pragma: no cover
    except Exception:  # pragma: no cover  # nosec B110
        pass  # NOSONAR

    return headers


import re as _re

# W3C traceparent: version(2)-traceId(32)-parentId(16)-flags(2).
# Compiled once at module load — the lazy approach had a race where two
# threads could both see None and both create a separate Pattern object.
_W3C_TRACEPARENT_RE = _re.compile(
    r"^[0-9a-fA-F]{2}-[0-9a-fA-F]{32}-[0-9a-fA-F]{16}-[0-9a-fA-F]{2}$"
)


def _get_traceparent_re() -> Any:
    """Return compiled W3C traceparent regex."""
    return _W3C_TRACEPARENT_RE


def extract_trace_context(headers: dict[str, str] | None = None) -> Any:
    """Extract W3C Trace Context from incoming request headers.

    Invalid ``traceparent`` values (wrong format, oversized ``tracestate``)
    are silently discarded to prevent malformed data propagating downstream.

    Args:
        headers: Headers dictionary.

    Returns:
        OTel Context or None.
    """
    if not OPENTELEMETRY_AVAILABLE:  # pragma: no cover
        return None

    if headers is None:
        return None

    # Validate traceparent format before handing to OTel parser.
    traceparent = headers.get("traceparent") or headers.get("Traceparent")
    if traceparent is not None:
        if not _get_traceparent_re().match(traceparent):
            return None  # Malformed — do not propagate

    # Guard against oversized tracestate (W3C recommends max 512 bytes).
    tracestate = headers.get("tracestate") or headers.get("Tracestate", "")
    if len(tracestate) > 512:
        # Truncation risks breaking key=value syntax; safest to drop entirely.
        _tracer_logger.warning(
            "tracestate_dropped_oversized: size=%d bytes (max 512)", len(tracestate)
        )
        filtered = {k: v for k, v in headers.items() if k.lower() not in ("tracestate",)}
        headers = filtered

    try:  # pragma: no cover
        from opentelemetry.trace.propagation.tracecontext import (
            TraceContextTextMapPropagator,
        )

        return TraceContextTextMapPropagator().extract(headers)  # pragma: no cover
    except Exception:  # pragma: no cover
        return None


@contextlib.contextmanager
def trace_context(headers: dict[str, str] | None = None) -> Generator[Any, None, None]:
    """Context manager that activates an extracted trace context.

    Args:
        headers: Incoming request headers with W3C trace context.

    Yields:
        Extracted context or None.
    """
    if not OPENTELEMETRY_AVAILABLE:  # pragma: no cover
        yield None
        return

    context = extract_trace_context(headers)

    if context is None:
        yield None
        return

    try:  # pragma: no cover
        token = context_api.attach(context)  # pragma: no cover
        try:  # pragma: no cover
            yield context
        finally:  # pragma: no cover
            context_api.detach(token)
    except Exception:  # pragma: no cover
        yield None


# ---------------------------------------------------------------------------
# W3C Baggage helpers
# ---------------------------------------------------------------------------


_BAGGAGE_MAX_KEY_LEN = 128
_BAGGAGE_MAX_VALUE_LEN = 1024


def set_baggage(key: str, value: str) -> Any:
    """Set a W3C Baggage entry in the current context.

    Baggage propagates key-value pairs across service boundaries via HTTP
    headers (``baggage: key=value``).  All downstream services that use
    OTel propagation will receive these values automatically.

    Args:
        key: Baggage key (ASCII printable, no whitespace). Max 128 chars.
        value: Baggage value (ASCII printable). Max 1024 chars.

    Returns:
        The updated OTel context token (can be passed to
        :func:`clear_baggage` to restore the previous state).

    Raises:
        ValueError: If key or value exceeds the size limits.

    Example::

        set_baggage("tenant_id", "acme-corp")
        # Every HTTP call made from here forwards   baggage: tenant_id=acme-corp
    """
    if not OPENTELEMETRY_AVAILABLE:  # pragma: no cover
        return None

    if not (key.isascii() and all(32 < ord(c) < 127 for c in key)):
        raise ValueError(
            f"baggage key {key!r} contains non-ASCII-printable characters. "
            "Keys must be ASCII printable (no whitespace or control characters)."
        )
    if not (value.isascii() and all(32 <= ord(c) < 127 for c in value)):
        raise ValueError(
            f"baggage value for key {key!r} contains non-ASCII-printable characters. "
            "Values must be ASCII printable (no control characters)."
        )

    # Validate byte length (not char length) because keys/values are transmitted
    # as HTTP header bytes.  All valid baggage keys are ASCII so char == byte,
    # but values may contain percent-encoded UTF-8 sequences that inflate size.
    key_bytes = len(key.encode("ascii"))  # already validated as ASCII above
    if key_bytes > _BAGGAGE_MAX_KEY_LEN:
        raise ValueError(
            f"baggage key too long ({key_bytes} bytes, max {_BAGGAGE_MAX_KEY_LEN}). "
            "Oversized baggage causes memory exhaustion in downstream services."
        )
    value_bytes = len(value.encode("ascii"))  # already validated as ASCII above
    if value_bytes > _BAGGAGE_MAX_VALUE_LEN:
        raise ValueError(
            f"baggage value for key {key!r} too long ({value_bytes} bytes, "
            f"max {_BAGGAGE_MAX_VALUE_LEN})."
        )

    try:
        ctx = baggage_api.set_baggage(key, value)
        return context_api.attach(ctx)
    except Exception:  # pragma: no cover  # nosec B110
        return None


def get_baggage(key: str) -> str | None:
    """Read a W3C Baggage value from the current context.

    Args:
        key: Baggage key to look up.

    Returns:
        The value string, or *None* if not present.

    Example::

        tenant = get_baggage("tenant_id")   # "acme-corp"  (or None)
    """
    if not OPENTELEMETRY_AVAILABLE:  # pragma: no cover
        return None

    try:
        value = baggage_api.get_baggage(key)
        return str(value) if value is not None else None
    except Exception:  # pragma: no cover  # nosec B110
        return None


def get_all_baggage() -> dict[str, str]:
    """Return all W3C Baggage entries from the current context.

    Returns:
        Dict mapping key → value for every baggage entry.

    Example::

        items = get_all_baggage()   # {"tenant_id": "acme-corp", ...}
    """
    if not OPENTELEMETRY_AVAILABLE:  # pragma: no cover
        return {}

    try:
        entries = baggage_api.get_all()
        return {k: str(v) for k, v in entries.items()}
    except Exception:  # pragma: no cover  # nosec B110
        return {}


def clear_baggage(token: Any) -> None:
    """Detach a baggage context token, restoring the previous context.

    Args:
        token: Token returned by :func:`set_baggage`.

    Example::

        token = set_baggage("tenant_id", "acme-corp")
        try:
            await call_downstream()
        finally:
            clear_baggage(token)
    """
    if not OPENTELEMETRY_AVAILABLE or token is None:  # pragma: no cover
        return

    try:
        context_api.detach(token)
    except Exception:  # pragma: no cover  # nosec B110
        pass  # NOSONAR


# ---------------------------------------------------------------------------
# Current span helpers (useful for trace-log correlation)
# ---------------------------------------------------------------------------


def get_current_trace_id() -> str | None:
    """Return the trace-id hex string of the active span, or *None*.

    Example::

        trace_id = get_current_trace_id()   # "4bf92f3577b34da6..."  or None
    """
    if not OPENTELEMETRY_AVAILABLE:  # pragma: no cover
        return None

    try:
        span = trace.get_current_span()
        ctx = span.get_span_context()
        if ctx and ctx.is_valid:
            return format(ctx.trace_id, "032x")
    except Exception:  # pragma: no cover  # nosec B110
        pass  # NOSONAR
    return None


def get_current_span_id() -> str | None:
    """Return the span-id hex string of the active span, or *None*.

    Example::

        span_id = get_current_span_id()   # "00f067aa0ba902b7"  or None
    """
    if not OPENTELEMETRY_AVAILABLE:  # pragma: no cover
        return None

    try:
        span = trace.get_current_span()
        ctx = span.get_span_context()
        if ctx and ctx.is_valid:
            return format(ctx.span_id, "016x")
    except Exception:  # pragma: no cover  # nosec B110
        pass  # NOSONAR
    return None


# ---------------------------------------------------------------------------
# Miscellaneous
# ---------------------------------------------------------------------------


def is_tracing_available() -> bool:
    """Check if OpenTelemetry SDK is installed.

    Returns:
        True if OpenTelemetry is installed.
    """
    return OPENTELEMETRY_AVAILABLE


def reset_tracing() -> None:
    """Reset tracing configuration (for testing)."""
    global _tracer, _configured
    with _tracer_lock:
        _tracer = None
        _configured = False


def shutdown_tracing() -> None:
    """Flush all pending spans and shut down the tracer provider.

    Call this during application shutdown to avoid losing buffered spans.
    ``BatchSpanProcessor`` queues up to 30 seconds of spans; without an
    explicit shutdown they are silently dropped on process exit.

    This is called automatically when using :func:`tracing_lifespan` or
    :func:`setup_signal_handlers`.

    Example::

        from obskit.tracing import shutdown_tracing

        shutdown_tracing()
    """
    global _tracer, _configured

    if not OPENTELEMETRY_AVAILABLE:  # pragma: no cover
        return

    with _tracer_lock:
        if _configured and trace is not None:  # pragma: no cover
            try:
                provider = trace.get_tracer_provider()
                if hasattr(provider, "force_flush"):  # pragma: no cover
                    provider.force_flush(timeout_millis=5000)
                if hasattr(provider, "shutdown"):  # pragma: no cover
                    provider.shutdown()
            except Exception:  # pragma: no cover  # nosec B110
                pass  # NOSONAR


@contextlib.contextmanager
def tracing_lifespan() -> Generator[None, None, None]:
    """Context manager that ensures tracing is flushed on exit.

    Use this in your application lifespan to guarantee in-flight spans
    are exported before the process ends — even on SIGTERM.

    FastAPI example::

        from contextlib import asynccontextmanager
        from obskit.tracing.tracer import tracing_lifespan

        @asynccontextmanager
        async def lifespan(app):
            with tracing_lifespan():
                yield  # app runs here

        app = FastAPI(lifespan=lifespan)

    Plain Python example::

        with tracing_lifespan():
            run_worker()
    """
    try:
        yield
    finally:
        shutdown_tracing()


def get_span_drop_count() -> int:
    """Return the cumulative number of spans dropped by the BatchSpanProcessor.

    When the export queue is full (OTLP endpoint slow or unreachable) the
    processor silently drops new spans.  Poll this periodically and alert
    when the value is non-zero so operators can tune
    ``OBSKIT_TRACE_EXPORT_QUEUE_SIZE`` or reduce ``OBSKIT_TRACE_SAMPLE_RATE``.

    Returns
    -------
    int
        Number of spans dropped since process start.  Returns 0 when tracing
        is disabled or the processor does not expose drop counts.

    Example::

        from obskit.tracing.tracer import get_span_drop_count

        dropped = get_span_drop_count()
        if dropped > 0:
            logger.warning("spans_dropped", count=dropped,
                           hint="Increase OBSKIT_TRACE_EXPORT_QUEUE_SIZE")
    """
    if _batch_span_processor is None:
        return 0
    # OpenTelemetry BatchSpanProcessor exposes _dropped_spans (private but stable).
    return int(getattr(_batch_span_processor, "_dropped_spans", 0))


def setup_signal_handlers() -> None:  # pragma: no cover
    """Register SIGTERM/SIGINT handlers that flush traces before exit.

    Call once at application startup.  Works independently of the
    application framework — suitable for workers, CLIs, and scripts.

    Example::

        from obskit.tracing.tracer import setup_signal_handlers
        setup_signal_handlers()
    """
    import signal

    def _handler(signum: int, frame: object) -> None:
        shutdown_tracing()

    signal.signal(signal.SIGTERM, _handler)
    signal.signal(signal.SIGINT, _handler)
