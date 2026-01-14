"""OpenTelemetry tracer implementation."""

from __future__ import annotations

import contextlib
import threading
from collections.abc import Callable, Generator
from functools import wraps
from typing import TYPE_CHECKING, Any, ParamSpec, TypeVar

from obskit.config import get_settings

if TYPE_CHECKING:
    pass

# Check if OpenTelemetry is available
try:
    from opentelemetry import trace
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.trace import Status, StatusCode, Tracer
    # TraceContextTextMapPropagator is imported locally in functions that use it
    # to avoid unused import warning - see inject_trace_context and extract_trace_context

    OPENTELEMETRY_AVAILABLE = True
except ImportError:  # pragma: no cover
    OPENTELEMETRY_AVAILABLE = False
    trace = None  # type: ignore[assignment]
    TracerProvider = None  # type: ignore[misc, assignment]
    BatchSpanProcessor = None  # type: ignore[misc, assignment]
    Resource = None  # type: ignore[misc, assignment]
    Status = None  # type: ignore[misc, assignment]
    StatusCode = None  # type: ignore[misc, assignment]
    Tracer = None  # type: ignore[misc, assignment]
    # TraceContextTextMapPropagator is not needed at module level - imported locally

P = ParamSpec("P")
T = TypeVar("T")

# Global tracer
_tracer: Tracer | None = None
_configured = False
_tracer_lock = threading.Lock()


def configure_tracing(
    service_name: str | None = None,
    otlp_endpoint: str | None = None,
) -> bool:
    """Configure OpenTelemetry tracing.

    Args:
        service_name: Name of the service.
        otlp_endpoint: OTLP collector endpoint.

    Returns:
        True if configured successfully, False if OpenTelemetry not available.

    Thread Safety
    -------------
    This function is thread-safe using locks to prevent concurrent configuration.
    """
    global _configured, _tracer

    if not OPENTELEMETRY_AVAILABLE:  # pragma: no cover
        return False

    with _tracer_lock:
        settings = get_settings()
        service = service_name or settings.service_name
        endpoint = otlp_endpoint or settings.otlp_endpoint

        # Create resource
        resource = Resource.create(
            {
                "service.name": service,
                "service.version": settings.version,
                "deployment.environment": settings.environment,
            }
        )

        # Create provider
        provider = TracerProvider(resource=resource)

    # Add OTLP exporter if configured
    if endpoint and settings.tracing_enabled:  # pragma: no cover
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter,
            )

            exporter = OTLPSpanExporter(
                endpoint=endpoint,
                insecure=settings.otlp_insecure,
            )

            # Use BatchSpanProcessor with rate limiting
            # BatchSpanProcessor already has built-in batching and backpressure
            # We can add additional rate limiting if needed
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
            # OTLP exporter is optional - opentelemetry-exporter-otlp not installed
            pass

        # Set global provider
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
    global _tracer, _configured

    if not OPENTELEMETRY_AVAILABLE:  # pragma: no cover
        return None

    # Double-checked locking pattern for thread safety
    if not _configured:
        with _tracer_lock:
            if not _configured:
                configure_tracing()

    if _tracer is None:  # pragma: no cover
        with _tracer_lock:
            if _tracer is None:  # pragma: no branch
                _tracer = trace.get_tracer(__name__)

    return _tracer


@contextlib.contextmanager
def trace_span(
    name: str,
    component: str | None = None,
    operation: str | None = None,
    attributes: dict[str, Any] | None = None,
) -> Generator[Any, None, None]:
    """Create a trace span context manager.

    Args:
        name: Span name.
        component: Component name.
        operation: Operation name.
        attributes: Additional span attributes.

    Yields:
        Span instance or None if tracing not available.

    Example:
        >>> with trace_span("process_order", attributes={"order_id": "123"}):
        ...     process_order()
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

    Example:
        >>> @trace_operation(component="OrderService")
        ... def create_order(order_data):
        ...     return Order.create(**order_data)
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


def inject_trace_context(headers: dict[str, str] | None = None) -> dict[str, str]:
    """Inject trace context into headers for propagation.

    This function injects W3C Trace Context headers into the provided
    headers dictionary, enabling distributed tracing across service boundaries.

    Args:
        headers: Headers dictionary to inject into. If None, creates new dict.

    Returns:
        Headers with trace context injected (W3C traceparent and tracestate).

    Example - HTTP Client
    ---------------------
    >>> import httpx
    >>> from obskit.tracing import inject_trace_context
    >>>
    >>> headers = {}
    >>> inject_trace_context(headers)
    >>>
    >>> async with httpx.AsyncClient() as client:
    ...     response = await client.get(
    ...         "https://api.example.com/data",
    ...         headers=headers,
    ...     )

    Example - FastAPI Request
    -------------------------
    >>> from fastapi import Request
    >>> from obskit.tracing import inject_trace_context
    >>>
    >>> async def call_downstream(request: Request):
    ...     headers = dict(request.headers)
    ...     inject_trace_context(headers)
    ...     # Use headers for downstream call
    """
    if not OPENTELEMETRY_AVAILABLE:  # pragma: no cover
        return headers or {}

    if headers is None:
        headers = {}

    try:  # pragma: no cover
        from opentelemetry.trace.propagation.tracecontext import (
            TraceContextTextMapPropagator,
        )

        propagator = TraceContextTextMapPropagator()
        propagator.inject(headers)  # pragma: no cover
    except Exception:  # pragma: no cover  # nosec B110 - trace injection is best-effort
        pass  # Trace context injection failure is non-critical

    return headers


def extract_trace_context(headers: dict[str, str] | None = None) -> Any:
    """Extract trace context from headers.

    This function extracts W3C Trace Context from incoming headers,
    allowing the current service to continue a trace started by another service.

    Args:
        headers: Headers dictionary to extract from.

    Returns:
        Trace context that can be used to create child spans, or None.

    Example - FastAPI Middleware
    -----------------------------
    >>> from fastapi import Request
    >>> from obskit.tracing import extract_trace_context, trace_span
    >>>
    >>> async def trace_middleware(request: Request, call_next):
    ...     context = extract_trace_context(dict(request.headers))
    ...
    ...     if context:
    ...         from opentelemetry.trace import set_span_in_context
    ...         with trace_span("handle_request") as span:
    ...             return await call_next(request)
    ...     else:
    ...         return await call_next(request)
    """
    if not OPENTELEMETRY_AVAILABLE:  # pragma: no cover
        return None

    if headers is None:
        return None

    try:  # pragma: no cover
        from opentelemetry.trace.propagation.tracecontext import (
            TraceContextTextMapPropagator,
        )

        propagator = TraceContextTextMapPropagator()
        return propagator.extract(headers)  # pragma: no cover
    except Exception:  # pragma: no cover
        return None


@contextlib.contextmanager
def trace_context(headers: dict[str, str] | None = None) -> Generator[Any, None, None]:
    """Create a trace context from headers.

    This context manager extracts trace context from headers and makes
    it the current context, allowing child spans to be created.

    Args:
        headers: Headers dictionary containing trace context.

    Yields:
        The current span context or None.

    Example
    -------
    >>> from obskit.tracing import trace_context
    >>>
    >>> # Extract context from incoming request
    >>> with trace_context(request_headers):
    ...     # All spans created here will be children of the extracted trace
    ...     with trace_span("process_request"):
    ...         process_request()
    """
    if not OPENTELEMETRY_AVAILABLE:  # pragma: no cover
        yield None
        return

    context = extract_trace_context(headers)

    if context is None:
        yield None
        return

    try:  # pragma: no cover
        from opentelemetry import context as context_api

        # Set the extracted context as current
        token = context_api.attach(context)  # pragma: no cover
        try:  # pragma: no cover
            yield context
        finally:  # pragma: no cover
            # Restore previous context
            context_api.detach(token)
    except Exception:  # pragma: no cover
        yield None


def is_tracing_available() -> bool:
    """Check if tracing is available.

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
    """Shutdown tracing and flush all pending spans.

    This function should be called during application shutdown to ensure
    all traces are sent to the collector before the process exits.

    Example
    -------
    >>> from obskit.tracing import shutdown_tracing
    >>>
    >>> # During application shutdown
    >>> shutdown_tracing()
    """
    global _tracer, _configured

    if not OPENTELEMETRY_AVAILABLE:  # pragma: no cover
        return

    with _tracer_lock:
        if _configured and trace is not None:  # pragma: no cover
            try:
                # Get the tracer provider and shutdown
                provider = trace.get_tracer_provider()
                if hasattr(provider, "shutdown"):  # pragma: no cover
                    provider.shutdown()
            except Exception:  # pragma: no cover  # nosec B110 - shutdown errors non-critical
                pass  # Ignore errors during shutdown
