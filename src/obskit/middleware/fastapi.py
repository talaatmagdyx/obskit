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

import re
import time
from typing import Any

# W3C traceparent: version(2)-traceId(32)-parentId(16)-flags(2)
# Accepts uppercase hex (AWS X-Ray, GCP Cloud Trace emit uppercase)
_W3C_TRACEPARENT_RE = re.compile(r"^[0-9a-fA-F]{2}-[0-9a-fA-F]{32}-[0-9a-fA-F]{16}-[0-9a-fA-F]{2}$")
# Safe correlation ID: alphanumeric + hyphens, underscores, and dots, max 128 chars
_CORRELATION_ID_RE = re.compile(r"^[a-zA-Z0-9\-_\.]{1,128}$")

from obskit.core.context import async_correlation_context, get_correlation_id
from obskit.logging import get_logger
from obskit.metrics.red import REDMetrics, get_red_metrics
from obskit.tracing.tracer import extract_trace_context, inject_trace_context, trace_context

logger = get_logger("obskit.middleware.fastapi")

try:
    from starlette.types import ASGIApp, Message, Receive, Scope, Send

    FASTAPI_AVAILABLE = True
except ImportError:  # pragma: no cover
    FASTAPI_AVAILABLE = False

    ASGIApp = Any  # type: ignore[misc]
    Scope = Any  # type: ignore[misc,assignment]
    Receive = Any  # type: ignore[misc]
    Send = Any  # type: ignore[misc]
    Message = Any  # type: ignore[misc,assignment]


class ObskitMiddleware:
    """
    Raw ASGI middleware that automatically adds observability to all requests.

    Uses raw ASGI (not BaseHTTPMiddleware) so the ``send`` callable can be
    intercepted — this allows measuring *total* response duration including
    streaming body, not just time-to-first-byte.

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
        Default: [\"/health\", \"/ready\", \"/live\", \"/metrics\"]

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

        self.app = app
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
        """Check if path should be excluded from observability.

        Matches exact path or any sub-path (with trailing slash) so that
        ``/health`` also excludes ``/health/`` and ``/health/detail``.
        """
        for excluded in self.exclude_paths:
            if path == excluded or path.startswith(excluded.rstrip("/") + "/"):
                return True
        return False

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """ASGI entry point — handles http and websocket scopes."""
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        path: str = scope.get("path", "/")

        if self._should_exclude(path):
            await self.app(scope, receive, send)
            return

        # ── Extract headers ──────────────────────────────────────────────────
        raw_headers: list[tuple[bytes, bytes]] = scope.get("headers", [])
        headers: dict[str, str] = {
            k.decode("latin-1", errors="replace"): v.decode("latin-1", errors="replace")
            for k, v in raw_headers
        }

        # Extract and validate correlation ID
        raw_cid = headers.get("x-correlation-id")
        if raw_cid is not None and not _CORRELATION_ID_RE.match(raw_cid):
            raw_cid = None  # Discard invalid ID; a new one will be generated

        # ── Operation name ───────────────────────────────────────────────────
        # Prefer the route *template* (e.g. "/orders/{id}") over the raw path
        # (e.g. "/orders/123") to avoid unbounded Prometheus cardinality from
        # dynamic path segments.  The route is set by FastAPI's router after
        # matching, so it may not be available at middleware entry; fall back to
        # the raw path only as a last resort.
        route = scope.get("route")
        if route and hasattr(route, "path"):  # pragma: no cover
            operation = route.path.replace("/", "_").strip("_") or "unknown"
        else:
            operation = path.replace("/", "_").strip("_") or "unknown"

        method: str = scope.get("method", "UNKNOWN") if scope["type"] == "http" else "WS"

        # ── Timing ──────────────────────────────────────────────────────────
        start_time = time.perf_counter()

        # ── Wrapped send to capture status_code + measure full duration ──────
        status_code_holder: list[int] = [0]

        async def observing_send(message: Message) -> None:
            if message["type"] == "http.response.start":
                status_code_holder[0] = message.get("status", 0)

                # Inject outgoing trace context + correlation ID headers
                correlation_id = get_correlation_id()
                extra_headers: list[tuple[bytes, bytes]] = []

                if correlation_id:
                    extra_headers.append((b"x-correlation-id", correlation_id.encode("latin-1")))

                if self.track_tracing:
                    trace_out = inject_trace_context({})
                    for key, value in trace_out.items():
                        extra_headers.append(
                            (key.lower().encode("latin-1"), value.encode("latin-1"))
                        )

                if extra_headers:
                    existing: list[tuple[bytes, bytes]] = list(message.get("headers", []))
                    existing_keys = {k.lower() for k, _ in existing}
                    for k, v in extra_headers:
                        if k not in existing_keys:
                            existing.append((k, v))
                    message = {**message, "headers": existing}

            elif message["type"] == "http.response.body":
                if not message.get("more_body", False):
                    # Last chunk — record full duration
                    duration_seconds = time.perf_counter() - start_time
                    duration_ms = duration_seconds * 1000
                    sc = status_code_holder[0]

                    if self.track_metrics and self.red_metrics:
                        self.red_metrics.observe_request(
                            operation=operation,
                            duration_seconds=duration_seconds,
                            status="success" if sc < 400 else "failure",
                            error_type=None if sc < 400 else f"HTTP{sc}",
                        )

                    if self.track_logging:
                        logger.info(
                            "request_completed",
                            method=method,
                            path=path,
                            operation=operation,
                            status_code=sc,
                            duration_ms=duration_ms,
                            correlation_id=get_correlation_id(),
                        )

            await send(message)

        # ── Run inside observability context ─────────────────────────────────
        async with async_correlation_context(raw_cid):
            correlation_id = get_correlation_id()

            if self.track_logging:
                logger.info(
                    "request_started",
                    method=method,
                    path=path,
                    operation=operation,
                    correlation_id=correlation_id,
                    client_ip=self._get_client_ip(scope),
                )

            try:
                if self.track_tracing:
                    trace_ctx = extract_trace_context(headers)
                    if trace_ctx is not None:
                        with trace_context(headers):
                            await self.app(scope, receive, observing_send)
                        return

                await self.app(scope, receive, observing_send)

            except Exception as e:
                duration_seconds = time.perf_counter() - start_time
                duration_ms = duration_seconds * 1000

                if self.track_metrics and self.red_metrics:
                    self.red_metrics.observe_request(
                        operation=operation,
                        duration_seconds=duration_seconds,
                        status="failure",
                        error_type=type(e).__name__,
                    )

                if self.track_logging:
                    logger.error(
                        "request_failed",
                        method=method,
                        path=path,
                        operation=operation,
                        error=str(e),
                        error_type=type(e).__name__,
                        duration_ms=duration_ms,
                        correlation_id=get_correlation_id(),
                        exc_info=True,
                    )

                raise

    @staticmethod
    def _get_client_ip(scope: Scope) -> str | None:
        """Extract client IP from ASGI scope."""
        client = scope.get("client")
        if client and isinstance(client, (list, tuple)) and len(client) >= 1:
            ip = client[0]
            return str(ip) if ip is not None else None
        return None
