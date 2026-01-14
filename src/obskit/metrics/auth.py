"""
Metrics Endpoint Authentication and Rate Limiting
==================================================

This module provides authentication and rate limiting for the metrics
endpoint to prevent unauthorized access and DoS attacks.

Example - Basic Usage
---------------------
.. code-block:: python

    from obskit import configure
    from obskit.metrics import start_http_server

    configure(
        metrics_auth_enabled=True,
        metrics_auth_token="your-secret-token",
        metrics_rate_limit_enabled=True,
        metrics_rate_limit_requests=60,  # 60 requests per minute
    )

    start_http_server()
    # Metrics endpoint now requires: Authorization: Bearer your-secret-token
    # And is rate-limited to 60 requests per minute
"""

from __future__ import annotations

import threading
import time
from http.server import BaseHTTPRequestHandler
from typing import Any

from obskit.logging import get_logger

logger = get_logger("obskit.metrics.auth")

HTTP_SERVER_AVAILABLE = True


class RateLimiter:
    """
    Simple sliding window rate limiter for metrics endpoint.

    Thread-safe implementation that tracks requests per minute.
    """

    def __init__(self, max_requests: int = 60, window_seconds: float = 60.0) -> None:
        """
        Initialize rate limiter.

        Parameters
        ----------
        max_requests : int
            Maximum requests allowed per window.
        window_seconds : float
            Time window in seconds.
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: list[float] = []
        self._lock = threading.Lock()

    def is_allowed(self) -> bool:
        """
        Check if a request is allowed.

        Returns
        -------
        bool
            True if request is allowed, False if rate limited.
        """
        now = time.time()
        cutoff = now - self.window_seconds

        with self._lock:
            # Remove expired entries
            self._requests = [t for t in self._requests if t > cutoff]

            if len(self._requests) >= self.max_requests:
                return False

            self._requests.append(now)
            return True

    def get_remaining(self) -> int:
        """Get remaining requests in current window."""
        now = time.time()
        cutoff = now - self.window_seconds

        with self._lock:
            self._requests = [t for t in self._requests if t > cutoff]
            return max(0, self.max_requests - len(self._requests))


# Global rate limiter instance
_metrics_rate_limiter: RateLimiter | None = None
_rate_limiter_lock = threading.Lock()


def _get_rate_limiter() -> RateLimiter | None:
    """Get the metrics rate limiter if enabled."""
    global _metrics_rate_limiter

    from obskit.config import get_settings

    settings = get_settings()

    if not settings.metrics_rate_limit_enabled:
        return None

    if _metrics_rate_limiter is None:
        with _rate_limiter_lock:
            if _metrics_rate_limiter is None:  # pragma: no branch
                _metrics_rate_limiter = RateLimiter(
                    max_requests=settings.metrics_rate_limit_requests,
                    window_seconds=60.0,  # Per minute
                )

    return _metrics_rate_limiter


class AuthenticatedMetricsHandler(BaseHTTPRequestHandler):
    """
    HTTP request handler with authentication for metrics endpoint.

    This handler wraps the Prometheus metrics handler and adds
    token-based authentication.
    """

    def __init__(self, *args: Any, auth_token: str | None = None, **kwargs: Any) -> None:
        self.auth_token = auth_token
        super().__init__(*args, **kwargs)

    def do_GET(self) -> None:
        """Handle GET requests with authentication and rate limiting."""
        # Check rate limiting
        rate_limiter = _get_rate_limiter()
        if rate_limiter is not None and not rate_limiter.is_allowed():
            self.send_response(429)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Retry-After", "60")
            self.end_headers()
            self.wfile.write(b"Too Many Requests: Rate limit exceeded\n")
            logger.warning("metrics_rate_limited", client=self.client_address[0])
            return

        # Check authentication if enabled
        if self.auth_token:
            auth_header = self.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                self.send_response(401)
                self.send_header("Content-Type", "text/plain")
                self.send_header("WWW-Authenticate", 'Bearer realm="metrics"')
                self.end_headers()
                self.wfile.write(b"Unauthorized: Missing or invalid Authorization header\n")
                return

            token = auth_header[7:]  # Remove "Bearer " prefix
            if token != self.auth_token:
                self.send_response(403)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(b"Forbidden: Invalid token\n")
                return

        # Delegate to Prometheus handler
        try:
            import prometheus_client

            # Check if this is the /metrics endpoint
            if self.path == "/metrics":
                # Use Prometheus's MetricsHandler
                prometheus_client.MetricsHandler.do_GET(self)  # type: ignore[arg-type]
            else:
                # 404 for other paths
                self.send_response(404)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(b"Not Found\n")
        except Exception as e:  # pragma: no cover
            logger.error(
                "metrics_handler_error",
                error=str(e),
                error_type=type(e).__name__,
            )
            self.send_response(500)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(f"Internal Server Error: {e}\n".encode())

    def log_message(self, fmt: str, *args: object) -> None:
        """Override to use obskit logger instead of default."""
        logger.debug("metrics_request", message=fmt % args)


def create_authenticated_handler(auth_token: str) -> type[AuthenticatedMetricsHandler]:
    """
    Create an authenticated metrics handler class.

    Parameters
    ----------
    auth_token : str
        Authentication token required for access.

    Returns
    -------
    type
        Handler class with authentication.
    """

    class Handler(AuthenticatedMetricsHandler):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, auth_token=auth_token, **kwargs)

    return Handler
