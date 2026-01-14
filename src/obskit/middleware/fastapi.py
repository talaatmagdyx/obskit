"""
FastAPI Middleware for obskit
==============================

This module provides FastAPI middleware that automatically adds observability
to all requests: correlation IDs, metrics, logging, and tracing.

Example - Basic Usage
---------------------
.. code-block:: python

    from fastapi import FastAPI
    from obskit.middleware.fastapi import ObskitMiddleware

    app = FastAPI()
    app.add_middleware(ObskitMiddleware)

    @app.get("/orders")
    async def get_orders():
        return {"orders": []}

    # Automatically gets:
    # - Correlation ID propagation
    # - Request/response logging
    # - RED metrics (rate, errors, duration)
    # - Distributed tracing

Example - With Custom Configuration
------------------------------------
.. code-block:: python

    from obskit.middleware.fastapi import ObskitMiddleware

    app.add_middleware(
        ObskitMiddleware,
        exclude_paths=["/health", "/metrics"],  # Skip observability for these
        track_metrics=True,  # Enable metrics
        track_logging=True,  # Enable logging
        track_tracing=True,  # Enable tracing
    )
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Any

from obskit.core.context import async_correlation_context, get_correlation_id
from obskit.logging import get_logger
from obskit.metrics.red import REDMetrics, get_red_metrics
from obskit.tracing.tracer import extract_trace_context, inject_trace_context, trace_context

logger = get_logger("obskit.middleware.fastapi")

try:
    from fastapi import Request, Response
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.types import ASGIApp

    FASTAPI_AVAILABLE = True
except ImportError:  # pragma: no cover
    FASTAPI_AVAILABLE = False

    class BaseHTTPMiddleware:  # type: ignore[no-redef]
        """Stub class when FastAPI is not available."""

        def __init__(self, app: Any) -> None:
            pass

    ASGIApp = Any  # type: ignore[misc]
    Request = Any  # type: ignore[misc, assignment]
    Response = Any  # type: ignore[misc, assignment]


class ObskitMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware that automatically adds observability to all requests.

    This middleware provides:
    - Correlation ID propagation (from headers or auto-generated)
    - Request/response logging (structured JSON)
    - RED metrics (rate, errors, duration)
    - Distributed tracing (OpenTelemetry)
    - Error tracking

    Parameters
    ----------
    app : ASGIApp
        The FastAPI application.

    exclude_paths : list[str], optional
        Path patterns to exclude from observability.
        Default: ["/health", "/ready", "/live", "/metrics"]

    track_metrics : bool, optional
        Enable metrics collection. Default: True.

    track_logging : bool, optional
        Enable request/response logging. Default: True.

    track_tracing : bool, optional
        Enable distributed tracing. Default: True.

    Example
    -------
    >>> from fastapi import FastAPI
    >>> from obskit.middleware.fastapi import ObskitMiddleware
    >>>
    >>> app = FastAPI()
    >>> app.add_middleware(ObskitMiddleware)
    >>>
    >>> @app.get("/orders")
    >>> async def get_orders():
    ...     return {"orders": []}
    """

    # Type annotation for optional metrics
    red_metrics: REDMetrics | None

    def __init__(
        self,
        app: ASGIApp,
        exclude_paths: list[str] | None = None,
        track_metrics: bool = True,
        track_logging: bool = True,
        track_tracing: bool = True,
    ) -> None:
        if not FASTAPI_AVAILABLE:  # pragma: no cover
            raise ImportError("FastAPI is not installed. Install with: pip install fastapi")

        super().__init__(app)

        self.exclude_paths = exclude_paths or ["/health", "/ready", "/live", "/metrics"]
        self.track_metrics = track_metrics
        self.track_logging = track_logging
        self.track_tracing = track_tracing

        # Get metrics instance
        if self.track_metrics:
            self.red_metrics = get_red_metrics()
        else:
            self.red_metrics = None

    def _should_exclude(self, path: str) -> bool:
        """Check if path should be excluded from observability."""
        return any(path.startswith(excluded) for excluded in self.exclude_paths)

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """
        Process request with observability.

        This method:
        1. Extracts/generates correlation ID
        2. Extracts trace context
        3. Logs request start
        4. Records metrics
        5. Handles errors
        6. Logs response
        """
        # Skip observability for excluded paths
        if self._should_exclude(request.url.path):
            return await call_next(request)

        # Extract correlation ID from header or generate new one
        correlation_id = request.headers.get("X-Correlation-ID")

        # Extract trace context from headers
        trace_headers = dict(request.headers)

        # Start timing
        start_time = time.perf_counter()

        # Get operation name from route
        operation = request.url.path.replace("/", "_").strip("_") or "unknown"
        if hasattr(request, "route") and request.route:  # pragma: no cover
            operation = request.route.path.replace("/", "_").strip("_") or operation

        # Setup observability context
        async with async_correlation_context(correlation_id):
            # Extract and use trace context if available
            if self.track_tracing:
                trace_ctx = extract_trace_context(trace_headers)
                if trace_ctx:
                    # Use trace context for this request
                    with trace_context(trace_headers):
                        return await self._process_request(
                            request, call_next, start_time, operation
                        )

            # Process without trace context
            return await self._process_request(request, call_next, start_time, operation)

    async def _process_request(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
        start_time: float,
        operation: str,
    ) -> Response:
        """Process request with observability."""
        correlation_id = get_correlation_id()

        # Log request start
        if self.track_logging:  # pragma: no branch
            logger.info(
                "request_started",
                method=request.method,
                path=request.url.path,
                operation=operation,
                correlation_id=correlation_id,
                client_ip=request.client.host if request.client else None,
            )

        try:
            # Process request
            response = await call_next(request)

            # Calculate duration
            duration_seconds = time.perf_counter() - start_time
            duration_ms = duration_seconds * 1000

            # Record metrics
            if self.track_metrics and self.red_metrics:
                self.red_metrics.observe_request(
                    operation=operation,
                    duration_seconds=duration_seconds,
                    status="success" if response.status_code < 400 else "failure",
                    error_type=None
                    if response.status_code < 400
                    else f"HTTP{response.status_code}",
                )

            # Add correlation ID to response headers
            response.headers["X-Correlation-ID"] = correlation_id or ""

            # Inject trace context into response if tracing enabled
            if self.track_tracing:
                response_headers = dict(response.headers)
                inject_trace_context(response_headers)
                # Update response headers (FastAPI/Starlette limitation)
                for key, value in response_headers.items():
                    if key not in response.headers:
                        response.headers[key] = value

            # Log response
            if self.track_logging:  # pragma: no branch
                logger.info(
                    "request_completed",
                    method=request.method,
                    path=request.url.path,
                    operation=operation,
                    status_code=response.status_code,
                    duration_ms=duration_ms,
                    correlation_id=correlation_id,
                )

            return response

        except Exception as e:
            # Calculate duration
            duration_seconds = time.perf_counter() - start_time
            duration_ms = duration_seconds * 1000

            # Record error metrics
            if self.track_metrics and self.red_metrics:
                self.red_metrics.observe_request(
                    operation=operation,
                    duration_seconds=duration_seconds,
                    status="failure",
                    error_type=type(e).__name__,
                )

            # Log error
            if self.track_logging:
                logger.error(
                    "request_failed",
                    method=request.method,
                    path=request.url.path,
                    operation=operation,
                    error=str(e),
                    error_type=type(e).__name__,
                    duration_ms=duration_ms,
                    correlation_id=correlation_id,
                    exc_info=True,
                )

            # Re-raise exception
            raise
