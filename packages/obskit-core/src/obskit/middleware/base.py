"""
Base Middleware for Request Context
====================================

Framework-agnostic middleware for extracting and propagating observability context.

Example
-------
>>> from obskit.middleware import extract_context_from_headers
>>>
>>> # Extract context from HTTP headers
>>> context = extract_context_from_headers(request.headers)
>>> # context = {'correlation_id': 'xxx', 'tenant_id': 'yyy', 'trace_context': {...}}
"""

from __future__ import annotations

import uuid
from typing import Any

from obskit.core import get_correlation_id, set_correlation_id
from obskit.logging import get_logger
from obskit.metrics.tenant import get_tenant_id, set_tenant_id

logger = get_logger("obskit.middleware")

# Standard headers for context propagation
CORRELATION_ID_HEADERS = [
    "X-Correlation-ID",
    "X-Request-ID",
    "X-Trace-ID",
    "Request-ID",
    "Correlation-ID",
]

TENANT_ID_HEADERS = [
    "X-Tenant-ID",
    "X-Company-ID",
    "X-Organization-ID",
    "Tenant-ID",
]

TRACE_CONTEXT_HEADERS = [
    "traceparent",
    "tracestate",
]


def extract_context_from_headers(
    headers: dict[str, str],
    generate_correlation_id: bool = True,
) -> dict[str, Any]:
    """
    Extract observability context from HTTP headers.

    Parameters
    ----------
    headers : dict
        HTTP headers (case-insensitive keys).
    generate_correlation_id : bool
        Generate correlation ID if not present (default: True).

    Returns
    -------
    dict
        Extracted context with keys:
        - correlation_id: Request correlation ID
        - tenant_id: Tenant ID (if present)
        - trace_context: OpenTelemetry trace context (if present)
    """
    # Normalize headers to lowercase
    normalized = {k.lower(): v for k, v in headers.items()}

    context = {}

    # Extract correlation ID
    correlation_id = None
    for header in CORRELATION_ID_HEADERS:
        value = normalized.get(header.lower())
        if value:
            correlation_id = value
            break

    if not correlation_id and generate_correlation_id:
        correlation_id = str(uuid.uuid4())

    if correlation_id:
        context["correlation_id"] = correlation_id
        set_correlation_id(correlation_id)

    # Extract tenant ID
    tenant_id = None
    for header in TENANT_ID_HEADERS:
        value = normalized.get(header.lower())
        if value:
            tenant_id = value
            break

    if tenant_id:
        context["tenant_id"] = tenant_id
        set_tenant_id(tenant_id)

    # Extract trace context
    trace_context = {}
    for header in TRACE_CONTEXT_HEADERS:
        value = normalized.get(header.lower())
        if value:
            trace_context[header] = value

    if trace_context:
        context["trace_context"] = trace_context

    return context


def inject_context_to_headers(
    headers: dict[str, str] | None = None,
    include_correlation_id: bool = True,
    include_tenant_id: bool = True,
) -> dict[str, str]:
    """
    Inject current observability context into HTTP headers.

    Parameters
    ----------
    headers : dict, optional
        Existing headers to update.
    include_correlation_id : bool
        Include correlation ID (default: True).
    include_tenant_id : bool
        Include tenant ID (default: True).

    Returns
    -------
    dict
        Headers with context injected.
    """
    headers = dict(headers) if headers else {}

    if include_correlation_id:
        correlation_id = get_correlation_id()
        if correlation_id:
            headers["X-Correlation-ID"] = correlation_id

    if include_tenant_id:
        tenant_id = get_tenant_id()
        if tenant_id:
            headers["X-Tenant-ID"] = tenant_id

    # Inject trace context
    try:
        from obskit.tracing import inject_trace_context

        headers = inject_trace_context(headers)
    except Exception:
        pass  # Tracing not available or injection failed - continue without trace context

    return headers


class BaseMiddleware:
    """
    Base middleware class for request context propagation.

    Subclass this for specific frameworks.

    Example
    -------
    >>> class MyFrameworkMiddleware(BaseMiddleware):
    ...     def __call__(self, request):
    ...         context = self.before_request(dict(request.headers))
    ...         try:
    ...             response = self.call_next(request)
    ...             self.after_request(response, context)
    ...             return response
    ...         except Exception as e:
    ...             self.on_error(e, context)
    ...             raise
    """

    def __init__(
        self,
        service_name: str = "service",
        record_metrics: bool = True,
        propagate_context: bool = True,
    ):
        self.service_name = service_name
        self.record_metrics = record_metrics
        self.propagate_context = propagate_context

        if record_metrics:
            from obskit.metrics import REDMetrics

            self._metrics = REDMetrics(name=service_name)
        else:
            self._metrics = None

    def before_request(self, headers: dict[str, str]) -> dict[str, Any]:
        """
        Called before processing request.

        Returns context dict for use in after_request.
        """
        import time

        context = extract_context_from_headers(headers)
        context["start_time"] = time.perf_counter()

        logger.debug(
            "request_started",
            correlation_id=context.get("correlation_id"),
            tenant_id=context.get("tenant_id"),
        )

        return context

    def after_request(
        self,
        response: Any,
        context: dict[str, Any],
        status_code: int = 200,
        operation: str = "request",
    ):
        """Called after processing request."""
        import time

        duration = time.perf_counter() - context.get("start_time", 0)

        # Determine status
        status = "success" if 200 <= status_code < 400 else "failure"

        # Record metrics
        if self._metrics:
            self._metrics.observe_request(
                operation=operation,
                duration_seconds=duration,
                status=status,
            )

        logger.debug(
            "request_completed",
            correlation_id=context.get("correlation_id"),
            status_code=status_code,
            duration_ms=int(duration * 1000),
        )

    def on_error(self, error: Exception, context: dict[str, Any]):
        """Called when an error occurs."""
        import time

        duration = time.perf_counter() - context.get("start_time", 0)

        # Record error metrics
        if self._metrics:
            self._metrics.observe_request(
                operation="request",
                duration_seconds=duration,
                status="failure",
                error_type=type(error).__name__,
            )

        logger.error(
            "request_failed",
            correlation_id=context.get("correlation_id"),
            error=str(error),
            error_type=type(error).__name__,
            duration_ms=int(duration * 1000),
        )


class ASGIMiddleware:
    """
    ASGI middleware for automatic context propagation.

    Works with FastAPI, Starlette, and other ASGI frameworks.

    Example
    -------
    >>> from fastapi import FastAPI
    >>> from obskit.middleware import ASGIMiddleware
    >>>
    >>> app = FastAPI()
    >>> app.add_middleware(ASGIMiddleware, service_name="my-service")
    """

    def __init__(
        self,
        app,
        service_name: str = "service",
        record_metrics: bool = True,
    ):
        self.app = app
        self.base = BaseMiddleware(
            service_name=service_name,
            record_metrics=record_metrics,
        )

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Extract headers
        headers = dict(scope.get("headers", []))
        headers = {k.decode(): v.decode() for k, v in headers.items()}

        # Before request
        context = self.base.before_request(headers)

        # Track response status
        status_code = 200

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message.get("status", 200)
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)

            # Get operation from path
            path = scope.get("path", "/")
            method = scope.get("method", "GET")
            operation = f"{method} {path}"

            self.base.after_request(None, context, status_code, operation)

        except Exception as e:
            self.base.on_error(e, context)
            raise


class WSGIMiddleware:
    """
    WSGI middleware for automatic context propagation.

    Works with Flask, Django, and other WSGI frameworks.

    Example
    -------
    >>> from flask import Flask
    >>> from obskit.middleware import WSGIMiddleware
    >>>
    >>> app = Flask(__name__)
    >>> app.wsgi_app = WSGIMiddleware(app.wsgi_app, service_name="my-service")
    """

    def __init__(
        self,
        app,
        service_name: str = "service",
        record_metrics: bool = True,
    ):
        self.app = app
        self.base = BaseMiddleware(
            service_name=service_name,
            record_metrics=record_metrics,
        )

    def __call__(self, environ, start_response):
        # Extract headers
        headers = {}
        for key, value in environ.items():
            if key.startswith("HTTP_"):
                header_name = key[5:].replace("_", "-")
                headers[header_name] = value

        # Before request
        context = self.base.before_request(headers)

        # Track response status
        status_code = [200]

        def custom_start_response(status, headers, exc_info=None):
            try:
                status_code[0] = int(status.split()[0])
            except (ValueError, IndexError):
                pass  # Invalid status format - use default status code
            return start_response(status, headers, exc_info)

        try:
            result = self.app(environ, custom_start_response)

            path = environ.get("PATH_INFO", "/")
            method = environ.get("REQUEST_METHOD", "GET")
            operation = f"{method} {path}"

            self.base.after_request(None, context, status_code[0], operation)

            return result

        except Exception as e:
            self.base.on_error(e, context)
            raise


__all__ = [
    "extract_context_from_headers",
    "inject_context_to_headers",
    "BaseMiddleware",
    "ASGIMiddleware",
    "WSGIMiddleware",
    "CORRELATION_ID_HEADERS",
    "TENANT_ID_HEADERS",
]
