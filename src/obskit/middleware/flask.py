"""
Flask Middleware for obskit
============================

This module provides Flask middleware that automatically adds observability
to all requests: correlation IDs, metrics, logging, and tracing.

Installation
------------
.. code-block:: bash

    pip install obskit[flask]

Example - Basic Usage
---------------------
.. code-block:: python

    from flask import Flask
    from obskit.middleware.flask import ObskitFlaskMiddleware

    app = Flask(__name__)
    ObskitFlaskMiddleware(app)

    @app.route("/orders")
    def get_orders():
        return {"orders": []}

    # Automatically gets:
    # - Correlation ID propagation
    # - Request/response logging
    # - RED metrics (rate, errors, duration)
    # - Distributed tracing

Example - With Custom Configuration
------------------------------------
.. code-block:: python

    from obskit.middleware.flask import ObskitFlaskMiddleware

    middleware = ObskitFlaskMiddleware(
        app,
        exclude_paths=["/health", "/metrics"],
        track_metrics=True,
        track_logging=True,
        track_tracing=True,
    )

Example - Using Extension Pattern
----------------------------------
.. code-block:: python

    from flask import Flask
    from obskit.middleware.flask import obskit_flask

    app = Flask(__name__)
    obskit_flask.init_app(app)
"""

from __future__ import annotations

import time
import uuid
from typing import TYPE_CHECKING

from obskit.core.context import set_correlation_id
from obskit.logging import get_logger
from obskit.metrics.red import REDMetrics, get_red_metrics
from obskit.tracing.tracer import extract_trace_context, inject_trace_context

if TYPE_CHECKING:
    from flask import Flask, Response

logger = get_logger("obskit.middleware.flask")

# Check if Flask is available
try:
    from flask import Flask, Response, g, request

    FLASK_AVAILABLE = True
except ImportError:  # pragma: no cover
    FLASK_AVAILABLE = False


class ObskitFlaskMiddleware:
    """
    Flask middleware that automatically adds observability to all requests.

    This middleware provides:
    - Correlation ID propagation (from headers or auto-generated)
    - Request/response logging (structured JSON)
    - RED metrics (rate, errors, duration)
    - Distributed tracing (OpenTelemetry)
    - Error tracking

    Parameters
    ----------
    app : Flask, optional
        The Flask application. If not provided, use init_app() later.

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
    >>> from flask import Flask
    >>> from obskit.middleware.flask import ObskitFlaskMiddleware
    >>>
    >>> app = Flask(__name__)
    >>> ObskitFlaskMiddleware(app)
    >>>
    >>> @app.route("/orders")
    >>> def get_orders():
    ...     return {"orders": []}
    """

    def __init__(
        self,
        app: Flask | None = None,
        exclude_paths: list[str] | None = None,
        track_metrics: bool = True,
        track_logging: bool = True,
        track_tracing: bool = True,
    ) -> None:
        if not FLASK_AVAILABLE:  # pragma: no cover
            raise ImportError("Flask is not installed. Install with: pip install flask")

        self.exclude_paths = exclude_paths or ["/health", "/ready", "/live", "/metrics"]
        self.track_metrics = track_metrics
        self.track_logging = track_logging
        self.track_tracing = track_tracing

        # Get metrics instance
        self.red_metrics: REDMetrics | None = None
        if self.track_metrics:
            self.red_metrics = get_red_metrics()

        if app is not None:
            self.init_app(app)

    def init_app(self, app: Flask) -> None:
        """
        Initialize the middleware with a Flask app.

        This follows Flask's extension pattern, allowing deferred initialization.

        Parameters
        ----------
        app : Flask
            The Flask application.

        Example
        -------
        >>> middleware = ObskitFlaskMiddleware()
        >>> app = Flask(__name__)
        >>> middleware.init_app(app)
        """
        if not FLASK_AVAILABLE:  # pragma: no cover
            raise ImportError("Flask is not installed. Install with: pip install flask")

        # Store reference to this middleware on app
        if not hasattr(app, "extensions"):
            app.extensions = {}
        app.extensions["obskit"] = self

        # Register before/after request hooks
        app.before_request(self._before_request)
        app.after_request(self._after_request)
        app.teardown_request(self._teardown_request)

    def _should_exclude(self, path: str) -> bool:
        """Check if path should be excluded from observability."""
        return any(path.startswith(excluded) for excluded in self.exclude_paths)

    def _before_request(self) -> None:
        """Called before each request."""
        if not FLASK_AVAILABLE:  # pragma: no cover
            return

        # Skip excluded paths
        if self._should_exclude(request.path):
            g._obskit_excluded = True
            return

        g._obskit_excluded = False

        # Extract or generate correlation ID
        correlation_id = request.headers.get("X-Correlation-ID")
        if not correlation_id:
            correlation_id = str(uuid.uuid4())

        # Store in Flask's g object
        g._obskit_correlation_id = correlation_id
        g._obskit_start_time = time.perf_counter()

        # Set correlation ID in context
        set_correlation_id(correlation_id)

        # Get operation name from endpoint
        operation = request.endpoint or request.path.replace("/", "_").strip("_") or "unknown"
        g._obskit_operation = operation

        # Extract trace context if tracing enabled
        if self.track_tracing:
            trace_headers = dict(request.headers)
            g._obskit_trace_ctx = extract_trace_context(trace_headers)

        # Log request start
        if self.track_logging:  # pragma: no branch
            logger.info(
                "request_started",
                method=request.method,
                path=request.path,
                operation=operation,
                correlation_id=correlation_id,
                client_ip=request.remote_addr,
            )

    def _after_request(self, response: Response) -> Response:
        """Called after each request to process response."""
        if not FLASK_AVAILABLE:  # pragma: no cover
            return response

        # Skip if excluded
        if getattr(g, "_obskit_excluded", True):
            return response

        # Get timing info
        start_time = getattr(g, "_obskit_start_time", time.perf_counter())
        duration_seconds = time.perf_counter() - start_time
        duration_ms = duration_seconds * 1000

        correlation_id = getattr(g, "_obskit_correlation_id", "")
        operation = getattr(g, "_obskit_operation", "unknown")

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
        response.headers["X-Correlation-ID"] = correlation_id

        # Inject trace context into response
        if self.track_tracing:  # pragma: no branch
            response_headers: dict[str, str] = {}
            inject_trace_context(response_headers)
            for key, value in response_headers.items():  # pragma: no cover
                response.headers[key] = value

        # Log response
        if self.track_logging:  # pragma: no branch
            logger.info(
                "request_completed",
                method=request.method,
                path=request.path,
                operation=operation,
                status_code=response.status_code,
                duration_ms=duration_ms,
                correlation_id=correlation_id,
            )

        return response

    def _teardown_request(self, exception: BaseException | None = None) -> None:
        """Called after each request, even on error."""
        if not FLASK_AVAILABLE:  # pragma: no cover
            return

        # Skip if excluded
        if getattr(g, "_obskit_excluded", True):
            return

        # If there was an exception, log it
        if exception is not None:
            start_time = getattr(g, "_obskit_start_time", time.perf_counter())
            duration_seconds = time.perf_counter() - start_time
            duration_ms = duration_seconds * 1000

            correlation_id = getattr(g, "_obskit_correlation_id", "")
            operation = getattr(g, "_obskit_operation", "unknown")

            # Record error metrics
            if self.track_metrics and self.red_metrics:  # pragma: no branch
                self.red_metrics.observe_request(
                    operation=operation,
                    duration_seconds=duration_seconds,
                    status="failure",
                    error_type=type(exception).__name__,
                )

            # Log error
            if self.track_logging:  # pragma: no branch
                logger.error(
                    "request_failed",
                    method=request.method if request else "UNKNOWN",
                    path=request.path if request else "unknown",
                    operation=operation,
                    error=str(exception),
                    error_type=type(exception).__name__,
                    duration_ms=duration_ms,
                    correlation_id=correlation_id,
                    exc_info=True,
                )


# Singleton instance for Flask extension pattern
obskit_flask: ObskitFlaskMiddleware | None = ObskitFlaskMiddleware() if FLASK_AVAILABLE else None
