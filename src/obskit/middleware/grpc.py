"""
gRPC Middleware Support
=======================

This module provides observability middleware for gRPC services,
implementing RED metrics, structured logging, and distributed tracing.

Features
--------
- Automatic RED metrics for all RPC calls
- Structured logging with correlation IDs
- Distributed tracing with context propagation
- Error tracking with gRPC status codes

Example - Server Interceptor
----------------------------
.. code-block:: python

    import grpc
    from obskit.middleware.grpc import ObskitServerInterceptor

    # Create interceptor
    interceptor = ObskitServerInterceptor(
        service_name="order-service",
        track_metrics=True,
        track_logging=True,
        track_tracing=True,
    )

    # Add to server
    server = grpc.aio.server(interceptors=[interceptor])

Example - Client Interceptor
----------------------------
.. code-block:: python

    from obskit.middleware.grpc import ObskitClientInterceptor

    # Create interceptor
    interceptor = ObskitClientInterceptor(
        track_metrics=True,
        propagate_trace=True,
    )

    # Add to channel
    channel = grpc.aio.insecure_channel(
        "localhost:50051",
        interceptors=[interceptor],
    )
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Any, Literal, TypeVar

from obskit.config import get_settings
from obskit.core.context import get_correlation_id, set_correlation_id
from obskit.logging import get_logger
from obskit.metrics.red import get_red_metrics

logger = get_logger("obskit.middleware.grpc")

# Type for gRPC handlers
T = TypeVar("T")

# Check for gRPC availability
try:
    import grpc
    from grpc import aio

    GRPC_AVAILABLE = True
except ImportError:  # pragma: no cover
    GRPC_AVAILABLE = False
    grpc = None
    aio = None

# Metadata key for correlation ID
CORRELATION_ID_KEY = "x-correlation-id"
TRACE_PARENT_KEY = "traceparent"
TRACE_STATE_KEY = "tracestate"


def _extract_method_name(method: str) -> str:
    """Extract operation name from gRPC method path."""
    # gRPC method format: /package.Service/Method
    parts = method.split("/")
    if len(parts) >= 3:
        return f"{parts[1]}.{parts[2]}"
    return method


def _grpc_status_to_status(code: Any) -> str:
    """Convert gRPC status code to success/failure."""
    if not GRPC_AVAILABLE:  # pragma: no cover
        return "unknown"

    if code == grpc.StatusCode.OK:
        return "success"
    return "failure"


def _extract_correlation_id(metadata: Any) -> str | None:
    """Extract correlation ID from gRPC metadata."""
    if metadata is None:
        return None

    for key, value in metadata:
        if key.lower() == CORRELATION_ID_KEY:
            return str(value) if value is not None else None
    return None


class ObskitServerInterceptor:
    """
    gRPC server interceptor for observability.

    Adds metrics, logging, and tracing to all incoming RPC calls.

    Parameters
    ----------
    service_name : str, optional
        Service name for metrics. Defaults to settings.service_name.
    track_metrics : bool
        Enable RED metrics tracking. Default: True.
    track_logging : bool
        Enable structured logging. Default: True.
    track_tracing : bool
        Enable distributed tracing. Default: True.
    excluded_methods : list[str], optional
        Methods to exclude from observability (e.g., health checks).

    Example
    -------
    >>> import grpc.aio
    >>> from obskit.middleware.grpc import ObskitServerInterceptor
    >>>
    >>> interceptor = ObskitServerInterceptor(
    ...     excluded_methods=["grpc.health.v1.Health/Check"],
    ... )
    >>>
    >>> server = grpc.aio.server(interceptors=[interceptor])
    """

    def __init__(
        self,
        service_name: str | None = None,
        track_metrics: bool = True,
        track_logging: bool = True,
        track_tracing: bool = True,
        excluded_methods: list[str] | None = None,
    ) -> None:
        if not GRPC_AVAILABLE:  # pragma: no cover
            raise ImportError("gRPC is not installed. Install with: pip install grpcio")

        settings = get_settings()
        self.service_name = service_name or settings.service_name
        self.track_metrics = track_metrics
        self.track_logging = track_logging
        self.track_tracing = track_tracing
        self.excluded_methods = set(excluded_methods or [])

        if self.track_metrics:
            self.red_metrics = get_red_metrics()

    def _should_observe(self, method: str) -> bool:
        """Check if method should be observed."""
        return method not in self.excluded_methods

    async def intercept_service(
        self,
        continuation: Callable[[Any], Awaitable[Any]],
        handler_call_details: Any,
    ) -> Any:
        """
        Intercept incoming RPC call.

        This method wraps the actual RPC handler with observability.
        """
        method = handler_call_details.method

        if not self._should_observe(method):
            return await continuation(handler_call_details)

        operation = _extract_method_name(method)

        # Extract correlation ID from metadata
        correlation_id = _extract_correlation_id(handler_call_details.invocation_metadata)
        if correlation_id:
            set_correlation_id(correlation_id)

        start_time = time.perf_counter()
        status: Literal["success", "failure"] = "success"
        error_type: str | None = None

        if self.track_logging:
            logger.debug(
                "grpc_request_started",
                method=method,
                operation=operation,
                correlation_id=get_correlation_id(),
            )

        try:
            response = await continuation(handler_call_details)
            return response

        except grpc.RpcError as e:
            status = "failure"
            error_type = e.code().name if hasattr(e, "code") else "RpcError"
            raise

        except Exception as e:
            status = "failure"
            error_type = type(e).__name__
            raise

        finally:
            duration_seconds = time.perf_counter() - start_time
            duration_ms = duration_seconds * 1000

            if self.track_metrics:
                self.red_metrics.observe_request(
                    operation=operation,
                    duration_seconds=duration_seconds,
                    status=status,
                    error_type=error_type,
                )

            if self.track_logging:
                log_func = logger.info if status == "success" else logger.warning
                log_func(
                    "grpc_request_completed",
                    method=method,
                    operation=operation,
                    status=status,
                    duration_ms=round(duration_ms, 2),
                    error_type=error_type,
                    correlation_id=get_correlation_id(),
                )


class ObskitClientInterceptor:
    """
    gRPC client interceptor for observability.

    Adds metrics, logging, and trace context propagation to outgoing RPC calls.

    Parameters
    ----------
    track_metrics : bool
        Enable RED metrics tracking. Default: True.
    track_logging : bool
        Enable structured logging. Default: True.
    propagate_trace : bool
        Propagate trace context in metadata. Default: True.
    propagate_correlation_id : bool
        Propagate correlation ID in metadata. Default: True.

    Example
    -------
    >>> import grpc.aio
    >>> from obskit.middleware.grpc import ObskitClientInterceptor
    >>>
    >>> interceptor = ObskitClientInterceptor()
    >>>
    >>> channel = grpc.aio.insecure_channel(
    ...     "localhost:50051",
    ...     interceptors=[interceptor],
    ... )
    """

    def __init__(
        self,
        track_metrics: bool = True,
        track_logging: bool = True,
        propagate_trace: bool = True,
        propagate_correlation_id: bool = True,
    ) -> None:
        if not GRPC_AVAILABLE:  # pragma: no cover
            raise ImportError("gRPC is not installed. Install with: pip install grpcio")

        self.track_metrics = track_metrics
        self.track_logging = track_logging
        self.propagate_trace = propagate_trace
        self.propagate_correlation_id = propagate_correlation_id

        if self.track_metrics:
            self.red_metrics = get_red_metrics()

    def _inject_metadata(
        self,
        metadata: list[tuple[str, str]] | None,
    ) -> list[tuple[str, str]]:
        """Inject trace context and correlation ID into metadata."""
        result = list(metadata) if metadata else []

        # Inject correlation ID
        if self.propagate_correlation_id:
            correlation_id = get_correlation_id()
            if correlation_id:
                result.append((CORRELATION_ID_KEY, correlation_id))

        # Inject trace context
        if self.propagate_trace:
            try:
                from obskit.tracing.tracer import inject_trace_context

                headers: dict[str, str] = {}
                inject_trace_context(headers)
                for key, value in headers.items():
                    result.append((key.lower(), value))
            except Exception:  # pragma: no cover  # nosec B110 - tracing injection is best-effort
                pass  # Trace context injection failure is non-critical

        return result

    async def intercept_unary_unary(
        self,
        continuation: Callable[..., Awaitable[Any]],
        client_call_details: Any,
        request: Any,
    ) -> Any:
        """Intercept unary-unary RPC call."""
        return await self._intercept_call(continuation, client_call_details, request)

    async def intercept_unary_stream(
        self,
        continuation: Callable[..., Awaitable[Any]],
        client_call_details: Any,
        request: Any,
    ) -> Any:
        """Intercept unary-stream RPC call."""
        return await self._intercept_call(continuation, client_call_details, request)

    async def intercept_stream_unary(
        self,
        continuation: Callable[..., Awaitable[Any]],
        client_call_details: Any,
        request_iterator: Any,
    ) -> Any:
        """Intercept stream-unary RPC call."""
        return await self._intercept_call(continuation, client_call_details, request_iterator)

    async def intercept_stream_stream(
        self,
        continuation: Callable[..., Awaitable[Any]],
        client_call_details: Any,
        request_iterator: Any,
    ) -> Any:
        """Intercept stream-stream RPC call."""
        return await self._intercept_call(continuation, client_call_details, request_iterator)

    async def _intercept_call(
        self,
        continuation: Callable[..., Awaitable[Any]],
        client_call_details: Any,
        request: Any,
    ) -> Any:
        """Common interception logic for all call types."""
        method = client_call_details.method
        operation = _extract_method_name(method)

        # Inject metadata
        new_metadata = self._inject_metadata(client_call_details.metadata)

        # Create new call details with injected metadata
        new_details = aio.ClientCallDetails(
            method=client_call_details.method,
            timeout=client_call_details.timeout,
            metadata=new_metadata,
            credentials=client_call_details.credentials,
            wait_for_ready=client_call_details.wait_for_ready,
        )

        start_time = time.perf_counter()
        status: Literal["success", "failure"] = "success"
        error_type: str | None = None

        if self.track_logging:
            logger.debug(
                "grpc_client_request_started",
                method=method,
                operation=operation,
                correlation_id=get_correlation_id(),
            )

        try:
            response = await continuation(new_details, request)
            return response

        except grpc.RpcError as e:
            status = "failure"
            error_type = e.code().name if hasattr(e, "code") else "RpcError"
            raise

        except Exception as e:
            status = "failure"
            error_type = type(e).__name__
            raise

        finally:
            duration_seconds = time.perf_counter() - start_time
            duration_ms = duration_seconds * 1000

            if self.track_metrics:
                self.red_metrics.observe_request(
                    operation=f"client.{operation}",
                    duration_seconds=duration_seconds,
                    status=status,
                    error_type=error_type,
                )

            if self.track_logging:
                log_func = logger.info if status == "success" else logger.warning
                log_func(
                    "grpc_client_request_completed",
                    method=method,
                    operation=operation,
                    status=status,
                    duration_ms=round(duration_ms, 2),
                    error_type=error_type,
                    correlation_id=get_correlation_id(),
                )


__all__ = [
    "ObskitServerInterceptor",
    "ObskitClientInterceptor",
    "GRPC_AVAILABLE",
]
