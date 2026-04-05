"""
FastAPI Middleware for obskit
==============================

This module provides FastAPI middleware that automatically adds observability
to all requests: correlation IDs, metrics, logging, and tracing.

Example - Basic Usage
---------------------
.. code-block:: python

    from obskit import instrument_fastapi
    from fastapi import FastAPI

    app = FastAPI()
    instrument_fastapi(app)

Example - With Custom Configuration
------------------------------------
.. code-block:: python

    from obskit.middleware.fastapi import ObskitMiddleware

    app.add_middleware(
        ObskitMiddleware,
        exclude_paths=["/health", "/metrics"],
        track_metrics=True,
        track_logging=True,
        track_tracing=True,
    )
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from obskit.core.context import async_correlation_context
from obskit.logging.context import bind_context, unbind_context
from obskit.middleware.core import MiddlewareCore
from obskit.tracing.tracer import trace_context

# Only decode headers that obskit actually consumes — avoids allocating a full
# dict for all 20-40 typical HTTP headers on every request.
_OBSERVABILITY_HEADERS: frozenset[bytes] = frozenset(
    [b"x-correlation-id", b"traceparent", b"tracestate", b"baggage"]
)

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
    context_extractor : Callable[[dict[str, str]], dict[str, Any]], optional
        Optional callable that receives the decoded request headers and returns
        a dict of extra key/value pairs to bind into the structured log
        context for the duration of the request.  Use this to inject
        tenant-specific fields (e.g. ``company_id``) without writing custom
        middleware::

            ObskitMiddleware(
                app,
                context_extractor=lambda h: {
                    "company_id": h.get("x-company-id", ""),
                },
            )
    """

    def __init__(
        self,
        app: ASGIApp,
        exclude_paths: list[str] | None = None,
        track_metrics: bool = True,
        track_logging: bool = True,
        track_tracing: bool = True,
        context_extractor: Callable[[dict[str, str]], dict[str, Any]] | None = None,
    ) -> None:
        if not FASTAPI_AVAILABLE:  # pragma: no cover
            raise ImportError("FastAPI is not installed. Install with: pip install fastapi")

        self.app = app
        self._context_extractor = context_extractor
        self._core = MiddlewareCore(
            exclude_paths=exclude_paths,
            track_metrics=track_metrics,
            track_logging=track_logging,
            track_tracing=track_tracing,
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """ASGI entry point — handles http and websocket scopes."""
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        path: str = scope.get("path", "/")

        if self._core.should_exclude(path):
            await self.app(scope, receive, send)
            return

        # ── Extract headers ──────────────────────────────────────────────────
        raw_headers: list[tuple[bytes, bytes]] = scope.get("headers", [])
        # Observability headers (4 well-known keys) — used for correlation ID,
        # tracing, and baggage propagation.  Kept minimal for hot-path speed.
        headers: dict[str, str] = {
            k.decode("latin-1", errors="replace"): v.decode("latin-1", errors="replace")
            for k, v in raw_headers
            if k.lower() in _OBSERVABILITY_HEADERS
        }
        # Full header dict — decoded lazily only when a context_extractor is
        # configured so that per-request cost is zero for the common case.
        all_headers: dict[str, str] = (
            {
                k.decode("latin-1", errors="replace"): v.decode("latin-1", errors="replace")
                for k, v in raw_headers
            }
            if self._context_extractor is not None
            else headers
        )

        # ── Correlation ID ───────────────────────────────────────────────────
        raw_cid = MiddlewareCore.extract_correlation_id(headers)

        # ── Operation name ───────────────────────────────────────────────────
        route = scope.get("route")
        if route and hasattr(route, "path"):  # pragma: no cover
            operation = route.path.replace("/", "_").strip("_") or "unknown"
        else:
            operation = path.replace("/", "_").strip("_") or "unknown"

        method: str = scope.get("method", "UNKNOWN") if scope["type"] == "http" else "WS"

        # ── Begin request via MiddlewareCore ─────────────────────────────────
        ctx = self._core.begin_request(
            headers=headers,
            path=path,
            method=method,
            operation=operation,
            client_ip=self._get_client_ip(scope),
        )

        # ── Wrapped send to capture status_code + measure full duration ──────
        status_code: int = 0

        async def observing_send(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message.get("status", 0)

                # Inject outgoing response headers
                resp_headers = self._core.response_headers(ctx)
                if resp_headers:  # pragma: no branch  # always has correlation ID
                    extra: list[tuple[bytes, bytes]] = [
                        (
                            k.encode("latin-1", errors="replace"),
                            v.encode("latin-1", errors="replace"),
                        )
                        for k, v in resp_headers
                    ]
                    existing: list[tuple[bytes, bytes]] = list(message.get("headers", []))
                    existing_keys = {k.lower() for k, _ in existing}
                    for k, v in extra:
                        if k not in existing_keys:  # pragma: no branch
                            existing.append((k, v))
                    message = {**message, "headers": existing}

            elif message["type"] == "http.response.body":
                if not message.get("more_body", False):
                    # Last chunk — record full duration
                    sc = status_code
                    effective_op = operation
                    if sc == 404 and not scope.get("route"):
                        effective_op = "unmatched_route"
                    self._core.end_request(ctx, sc, operation_override=effective_op)

            await send(message)

        # ── Run inside observability context ─────────────────────────────────
        async with async_correlation_context(raw_cid):
            # Bind caller-supplied extra context (e.g. tenant ID) into the
            # structlog context vars for the duration of this request.
            _extra_ctx: dict[str, Any] = {}
            if self._context_extractor is not None:
                _extra_ctx = self._context_extractor(all_headers) or {}
                if _extra_ctx:
                    bind_context(**_extra_ctx)

            try:
                if self._core.track_tracing and ctx.trace_ctx is not None:
                    with trace_context(headers):
                        await self.app(scope, receive, observing_send)
                    return

                await self.app(scope, receive, observing_send)

            except Exception as e:
                self._core.record_error(ctx, e)
                raise

            finally:
                if _extra_ctx:
                    unbind_context(*_extra_ctx.keys())
                if not ctx.metrics_recorded:
                    if status_code > 0:
                        # Catch early client disconnects (streaming responses
                        # where client closes before last body chunk).
                        sc = status_code
                        effective_op = operation
                        if sc == 404 and not scope.get("route"):
                            effective_op = "unmatched_route"
                        self._core.end_request(ctx, sc, operation_override=effective_op)
                    elif scope["type"] == "websocket":
                        # WebSocket connections never emit http.response.start
                        # so status_code stays 0 — record with 101 (Switching
                        # Protocols) so the request shows up in RED metrics.
                        self._core.end_request(ctx, 101, operation_override=operation)

    @staticmethod
    def _get_client_ip(scope: Scope) -> str | None:
        """Extract client IP from ASGI scope."""
        client = scope.get("client")
        if client and isinstance(client, (list, tuple)) and len(client) >= 1:
            ip = client[0]
            return str(ip) if ip is not None else None
        return None
