"""
Django Middleware for obskit
=============================

This module provides Django middleware that automatically adds observability
to all requests: correlation IDs, metrics, logging, and tracing.

Setup
-----
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
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from obskit.middleware.core import MiddlewareCore

if TYPE_CHECKING:
    from django.http import HttpRequest, HttpResponse

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

    Configuration via Django settings:

    .. code-block:: python

        OBSKIT = {
            'exclude_paths': ['/health/', '/metrics/'],
            'track_metrics': True,
            'track_logging': True,
            'track_tracing': True,
        }
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        if not DJANGO_AVAILABLE:  # pragma: no cover
            raise ImportError("Django is not installed. Install with: pip install django")

        self.get_response = get_response

        obskit_settings: dict[str, Any] = getattr(settings, "OBSKIT", {})

        self._core = MiddlewareCore(
            exclude_paths=obskit_settings.get(
                "exclude_paths", ["/health/", "/ready/", "/live/", "/metrics/"]
            ),
            track_metrics=obskit_settings.get("track_metrics", True),
            track_logging=obskit_settings.get("track_logging", True),
            track_tracing=obskit_settings.get("track_tracing", True),
        )

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """Process request with observability."""
        if self._core.should_exclude(request.path):
            return self.get_response(request)

        # Extract headers in Django format
        trace_headers = {
            key.replace("HTTP_", "").replace("_", "-"): value
            for key, value in request.META.items()
            if key.startswith("HTTP_")
        }

        operation = self._get_operation_name(request)

        ctx = self._core.begin_request(
            headers={**trace_headers, **dict(request.headers)},
            path=request.path,
            method=request.method,
            operation=operation,
            client_ip=self._get_client_ip(request),
        )

        # Store correlation ID on request for easy access in views
        request.correlation_id = ctx.correlation_id

        try:
            response = self.get_response(request)
            self._core.end_request(ctx, response.status_code)

            # Add response headers
            for key, value in self._core.response_headers(ctx):
                response[key] = value

            return response

        except Exception as e:
            self._core.record_error(ctx, e)
            raise

    def _get_operation_name(self, request: HttpRequest) -> str:
        """Get operation name from request URL resolver."""
        try:
            from django.urls import resolve

            match = resolve(request.path)
            if match.url_name:
                return str(match.url_name)
            if match.view_name:  # pragma: no branch
                return str(match.view_name)
        except Exception:  # nosec B110
            pass
        return request.path.replace("/", "_").strip("_") or "unknown"

    def _get_client_ip(self, request: HttpRequest) -> str | None:
        """Get client IP address from request."""
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
        """Handle unhandled exceptions (hook for subclasses)."""


def get_obskit_middleware(
    exclude_paths: list[str] | None = None,
    track_metrics: bool = True,
    track_logging: bool = True,
    track_tracing: bool = True,
) -> type[ObskitDjangoMiddleware]:
    """Factory function to create configured middleware class."""

    class ConfiguredObskitMiddleware(ObskitDjangoMiddleware):
        def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
            super().__init__(get_response)

            if exclude_paths is not None:
                self._core.exclude_paths = exclude_paths
            self._core.track_metrics = track_metrics
            self._core.track_logging = track_logging
            self._core.track_tracing = track_tracing

            # Update metrics if tracking changed
            if self._core.track_metrics and self._core.red_metrics is None:
                from obskit.metrics.red import get_red_metrics

                self._core.red_metrics = get_red_metrics()
            elif not self._core.track_metrics:
                self._core.red_metrics = None

    return ConfiguredObskitMiddleware
