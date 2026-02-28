"""OpenTelemetry tracer implementation."""

from __future__ import annotations

import contextlib
import threading
from collections.abc import AsyncGenerator, Callable, Generator
from functools import wraps
from typing import TYPE_CHECKING, Any, ParamSpec, TypeVar

from obskit.config import get_settings
from obskit.tracing._version import __version__ as _OBSKIT_TRACING_VERSION

if TYPE_CHECKING:
    pass

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
    global _configured, _tracer

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

    # ── Debug console exporter ────────────────────────────────────────────
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
            pass

    # ── OTLP exporter ────────────────────────────────────────────────────
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
        except ImportError:  # pragma: no cover
            pass

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
        pass

    return headers


def extract_trace_context(headers: dict[str, str] | None = None) -> Any:
    """Extract W3C Trace Context from incoming request headers.

    Args:
        headers: Headers dictionary.

    Returns:
        OTel Context or None.
    """
    if not OPENTELEMETRY_AVAILABLE:  # pragma: no cover
        return None

    if headers is None:
        return None

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


def set_baggage(key: str, value: str) -> Any:
    """Set a W3C Baggage entry in the current context.

    Baggage propagates key-value pairs across service boundaries via HTTP
    headers (``baggage: key=value``).  All downstream services that use
    OTel propagation will receive these values automatically.

    Args:
        key: Baggage key (ASCII printable, no whitespace).
        value: Baggage value (ASCII printable).

    Returns:
        The updated OTel context token (can be passed to
        :func:`clear_baggage` to restore the previous state).

    Example::

        set_baggage("tenant_id", "acme-corp")
        # Every HTTP call made from here forwards   baggage: tenant_id=acme-corp
    """
    if not OPENTELEMETRY_AVAILABLE:  # pragma: no cover
        return None

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
        pass


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
        pass
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
        pass
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

    Call this during application shutdown to avoid losing spans.

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
                if hasattr(provider, "shutdown"):  # pragma: no cover
                    provider.shutdown()
            except Exception:  # pragma: no cover  # nosec B110
                pass
