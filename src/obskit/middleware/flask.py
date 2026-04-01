"""
Flask Middleware for obskit
============================

This module provides Flask middleware that automatically adds observability
to all requests: correlation IDs, metrics, logging, and tracing.

Example - Basic Usage
---------------------
.. code-block:: python

    from obskit import instrument_flask
    from flask import Flask

    app = Flask(__name__)
    instrument_flask(app)

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

from typing import TYPE_CHECKING

from obskit.middleware.core import MiddlewareCore

if TYPE_CHECKING:
    from flask import Flask, Response

# Check if Flask is available
try:
    from flask import Flask, Response, g, request

    FLASK_AVAILABLE = True
except ImportError:  # pragma: no cover
    FLASK_AVAILABLE = False


class ObskitFlaskMiddleware:
    """
    Flask middleware that automatically adds observability to all requests.

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

        self._core = MiddlewareCore(
            exclude_paths=exclude_paths,
            track_metrics=track_metrics,
            track_logging=track_logging,
            track_tracing=track_tracing,
        )

        if app is not None:
            self.init_app(app)

    def init_app(self, app: Flask) -> None:
        """Initialize the middleware with a Flask app (extension pattern)."""
        if not FLASK_AVAILABLE:  # pragma: no cover
            raise ImportError("Flask is not installed. Install with: pip install flask")

        if not hasattr(app, "extensions"):
            app.extensions = {}
        app.extensions["obskit"] = self

        app.before_request(self._before_request)
        app.after_request(self._after_request)
        app.teardown_request(self._teardown_request)

    def _before_request(self) -> None:
        """Called before each request."""
        if not FLASK_AVAILABLE:  # pragma: no cover
            return

        if self._core.should_exclude(request.path):
            g._obskit_excluded = True
            return

        g._obskit_excluded = False

        headers = dict(request.headers)
        operation = request.endpoint or request.path.replace("/", "_").strip("_") or "unknown"

        ctx = self._core.begin_request(
            headers=headers,
            path=request.path,
            method=request.method,
            operation=operation,
            client_ip=request.remote_addr,
        )
        g._obskit_ctx = ctx

    def _after_request(self, response: Response) -> Response:
        """Called after each request to process response."""
        if not FLASK_AVAILABLE:  # pragma: no cover
            return response

        if getattr(g, "_obskit_excluded", True):
            return response

        ctx = getattr(g, "_obskit_ctx", None)
        if ctx is None:  # pragma: no cover  # defensive guard
            return response

        self._core.end_request(ctx, response.status_code)

        # Add response headers
        for key, value in self._core.response_headers(ctx):
            response.headers[key] = value

        return response

    def _teardown_request(self, exception: BaseException | None = None) -> None:
        """Called after each request, even on error."""
        if not FLASK_AVAILABLE:  # pragma: no cover
            return

        if getattr(g, "_obskit_excluded", True):
            return

        if exception is not None:
            ctx = getattr(g, "_obskit_ctx", None)
            if ctx is not None:  # pragma: no branch  # ctx always set when not excluded
                self._core.record_error(
                    ctx,
                    exception if isinstance(exception, Exception) else Exception(str(exception)),
                )


# Lazy singleton instance for Flask extension pattern
_obskit_flask: ObskitFlaskMiddleware | None = None


def get_obskit_flask() -> ObskitFlaskMiddleware | None:
    """Get or create the Flask middleware singleton."""
    global _obskit_flask
    if FLASK_AVAILABLE and _obskit_flask is None:
        _obskit_flask = ObskitFlaskMiddleware()
    return _obskit_flask


obskit_flask: ObskitFlaskMiddleware | None = None
