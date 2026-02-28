"""
Django Middleware for obskit
=============================

This module provides Django middleware that automatically adds observability
to all requests: correlation IDs, metrics, logging, and tracing.

Installation
------------
.. code-block:: bash

    pip install obskit[django]

Setup
-----
Add to your Django settings:

.. code-block:: python

    # settings.py
    MIDDLEWARE = [
        'obskit.middleware.django.ObskitDjangoMiddleware',
        # ... other middleware
    ]

    # Optional configuration
    OBSKIT = {
        'exclude_paths': ['/health/', '/metrics/'],
        'track_metrics': True,
        'track_logging': True,
        'track_tracing': True,
    }

Example - Basic Usage
---------------------
Once added to MIDDLEWARE, all requests automatically get:

- Correlation ID propagation
- Request/response logging
- RED metrics (rate, errors, duration)
- Distributed tracing

Example - Accessing Correlation ID in Views
--------------------------------------------
.. code-block:: python

    from obskit.core.context import get_correlation_id

    def my_view(request):
        correlation_id = get_correlation_id()
        # or from request attribute
        correlation_id = request.correlation_id
        return HttpResponse(f"Correlation ID: {correlation_id}")

Example - Custom Error Handling
--------------------------------
.. code-block:: python

    from obskit.middleware.django import ObskitDjangoMiddleware

    class MyObskitMiddleware(ObskitDjangoMiddleware):
        def process_exception(self, request, exception):
            # Custom error handling
            super().process_exception(request, exception)
            # Additional logging or alerting
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from obskit.core.context import set_correlation_id
from obskit.logging import get_logger
from obskit.metrics.red import REDMetrics, get_red_metrics
from obskit.tracing.tracer import extract_trace_context, inject_trace_context

if TYPE_CHECKING:
    from django.http import HttpRequest, HttpResponse

logger = get_logger("obskit.middleware.django")

# Check if Django is available
try:
    from django.conf import settings
    from django.http import HttpRequest, HttpResponse

    DJANGO_AVAILABLE = True
except ImportError:  # pragma: no cover
    DJANGO_AVAILABLE = False


class ObskitDjangoMiddleware:
    """
    Django middleware that automatically adds observability to all requests.

    This middleware provides:
    - Correlation ID propagation (from headers or auto-generated)
    - Request/response logging (structured JSON)
    - RED metrics (rate, errors, duration)
    - Distributed tracing (OpenTelemetry)
    - Error tracking

    Configuration via Django settings:

    .. code-block:: python

        OBSKIT = {
            'exclude_paths': ['/health/', '/metrics/'],
            'track_metrics': True,
            'track_logging': True,
            'track_tracing': True,
        }

    Example
    -------
    Add to MIDDLEWARE in settings.py:

    >>> MIDDLEWARE = [
    ...     'obskit.middleware.django.ObskitDjangoMiddleware',
    ...     # ... other middleware
    ... ]
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        if not DJANGO_AVAILABLE:  # pragma: no cover
            raise ImportError("Django is not installed. Install with: pip install django")

        self.get_response = get_response

        # Load configuration from Django settings
        obskit_settings: dict[str, Any] = getattr(settings, "OBSKIT", {})

        self.exclude_paths: list[str] = obskit_settings.get(
            "exclude_paths", ["/health/", "/ready/", "/live/", "/metrics/"]
        )
        self.track_metrics: bool = obskit_settings.get("track_metrics", True)
        self.track_logging: bool = obskit_settings.get("track_logging", True)
        self.track_tracing: bool = obskit_settings.get("track_tracing", True)

        # Get metrics instance
        self.red_metrics: REDMetrics | None = None
        if self.track_metrics:
            self.red_metrics = get_red_metrics()

    def _should_exclude(self, path: str) -> bool:
        """Check if path should be excluded from observability."""
        return any(path.startswith(excluded) for excluded in self.exclude_paths)

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """
        Process request with observability.

        This follows Django middleware protocol:
        1. Before request: Setup correlation ID, tracing, logging
        2. Call get_response
        3. After response: Record metrics, add headers, log completion
        """
        # Skip excluded paths
        if self._should_exclude(request.path):
            return self.get_response(request)

        # Extract or generate correlation ID
        correlation_id = request.headers.get("X-Correlation-ID")
        if not correlation_id:
            correlation_id = str(uuid.uuid4())

        # Set correlation ID in context
        set_correlation_id(correlation_id)

        # Store correlation ID on request for easy access in views
        request.correlation_id = correlation_id

        # Get operation name
        operation = self._get_operation_name(request)

        # Store timing info
        start_time = time.perf_counter()

        # Extract trace context if tracing enabled
        if self.track_tracing:  # pragma: no branch
            trace_headers = {
                key.replace("HTTP_", "").replace("_", "-"): value
                for key, value in request.META.items()
                if key.startswith("HTTP_")
            }
            # Extract trace context for propagation
            _ = extract_trace_context(trace_headers)

        # Log request start
        if self.track_logging:  # pragma: no branch
            self._log_request_start(request, operation, correlation_id)

        try:
            # Process request
            response = self.get_response(request)

            # Calculate duration
            duration_seconds = time.perf_counter() - start_time
            duration_ms = duration_seconds * 1000

            # Determine status
            is_success = response.status_code < 400

            # Record metrics
            if self.track_metrics and self.red_metrics:  # pragma: no branch
                self.red_metrics.observe_request(
                    operation=operation,
                    duration_seconds=duration_seconds,
                    status="success" if is_success else "failure",
                    error_type=None if is_success else f"HTTP{response.status_code}",
                )

            # Add correlation ID to response headers
            response["X-Correlation-ID"] = correlation_id

            # Inject trace context into response
            if self.track_tracing:  # pragma: no branch
                response_headers: dict[str, str] = {}
                inject_trace_context(response_headers)
                for key, value in response_headers.items():
                    response[key] = value

            # Log response
            if self.track_logging:  # pragma: no branch
                self._log_request_complete(
                    request, response, operation, duration_ms, correlation_id
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
                self._log_request_error(request, e, operation, duration_ms, correlation_id)

            # Re-raise
            raise

    def _get_operation_name(self, request: HttpRequest) -> str:
        """
        Get operation name from request.

        Tries to use URL name from resolver, falls back to path.
        """
        try:
            from django.urls import resolve

            match = resolve(request.path)
            if match.url_name:
                return str(match.url_name)
            if match.view_name:  # pragma: no branch
                return str(match.view_name)
        except Exception:  # nosec B110 - URL resolution failure is expected for some paths
            pass  # URL resolution may fail for various reasons - fall back to path-based name

        # Fall back to path-based name
        return request.path.replace("/", "_").strip("_") or "unknown"

    def _log_request_start(self, request: HttpRequest, operation: str, correlation_id: str) -> None:
        """Log request start."""
        logger.info(
            "request_started",
            method=request.method,
            path=request.path,
            operation=operation,
            correlation_id=correlation_id,
            client_ip=self._get_client_ip(request),
            user_id=str(request.user.id)
            if hasattr(request, "user") and request.user.is_authenticated
            else None,
        )

    def _log_request_complete(
        self,
        request: HttpRequest,
        response: HttpResponse,
        operation: str,
        duration_ms: float,
        correlation_id: str,
    ) -> None:
        """Log request completion."""
        logger.info(
            "request_completed",
            method=request.method,
            path=request.path,
            operation=operation,
            status_code=response.status_code,
            duration_ms=duration_ms,
            correlation_id=correlation_id,
        )

    def _log_request_error(
        self,
        request: HttpRequest,
        exception: Exception,
        operation: str,
        duration_ms: float,
        correlation_id: str,
    ) -> None:
        """Log request error."""
        logger.error(
            "request_failed",
            method=request.method,
            path=request.path,
            operation=operation,
            error=str(exception),
            error_type=type(exception).__name__,
            duration_ms=duration_ms,
            correlation_id=correlation_id,
            exc_info=True,
        )

    def _get_client_ip(self, request: HttpRequest) -> str | None:
        """Get client IP address from request."""
        # Check for proxy headers
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0].strip()
            return str(ip) if ip else None

        x_real_ip = request.META.get("HTTP_X_REAL_IP")
        if x_real_ip:
            return str(x_real_ip)

        remote_addr = request.META.get("REMOTE_ADDR")
        return str(remote_addr) if remote_addr else None

    def process_exception(self, request: HttpRequest, exception: Exception) -> None:
        """
        Handle unhandled exceptions.

        This is called when a view raises an exception.
        Override this method to add custom error handling.
        """
        # Error is already logged in __call__, but this hook allows
        # subclasses to add custom handling
        pass


# Type-safe factory for creating middleware
def get_obskit_middleware(
    exclude_paths: list[str] | None = None,
    track_metrics: bool = True,
    track_logging: bool = True,
    track_tracing: bool = True,
) -> type[ObskitDjangoMiddleware]:
    """
    Factory function to create configured middleware class.

    Use this when you need custom configuration different from Django settings.

    Parameters
    ----------
    exclude_paths : list[str], optional
        Paths to exclude from observability.
    track_metrics : bool
        Enable metrics collection.
    track_logging : bool
        Enable request logging.
    track_tracing : bool
        Enable distributed tracing.

    Returns
    -------
    type[ObskitDjangoMiddleware]
        Configured middleware class.

    Example
    -------
    .. code-block:: python

        # settings.py
        from obskit.middleware.django import get_obskit_middleware

        MIDDLEWARE = [
            get_obskit_middleware(
                exclude_paths=['/api/health/'],
                track_metrics=True,
            ),
            # ...
        ]
    """

    class ConfiguredObskitMiddleware(ObskitDjangoMiddleware):
        def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
            super().__init__(get_response)

            # Override with factory parameters
            if exclude_paths is not None:
                self.exclude_paths = exclude_paths
            self.track_metrics = track_metrics
            self.track_logging = track_logging
            self.track_tracing = track_tracing

            # Update metrics if tracking changed
            if self.track_metrics and self.red_metrics is None:
                self.red_metrics = get_red_metrics()
            elif not self.track_metrics:
                self.red_metrics = None

    return ConfiguredObskitMiddleware
