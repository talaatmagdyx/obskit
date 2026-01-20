"""
HTTP Health Server
==================

A standalone HTTP server for Kubernetes health probes.

Example
-------
>>> from obskit.health.server import start_health_server, stop_health_server
>>>
>>> # Start health server on port 8888
>>> start_health_server(port=8888)
>>>
>>> # Endpoints:
>>> # GET /health      - Overall health status
>>> # GET /health/live - Liveness probe (is process running?)
>>> # GET /health/ready - Readiness probe (can process requests?)
>>> # GET /health/slo  - SLO compliance status
>>> # GET /metrics     - Prometheus metrics (if enabled)
>>>
>>> # Stop server
>>> stop_health_server()
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import urlparse

from obskit.health import get_health_checker
from obskit.logging import get_logger

logger = get_logger("obskit.health.server")

# Global server instance
_health_server: HTTPServer | None = None
_health_server_thread: threading.Thread | None = None
_server_lock = threading.Lock()

# Custom handlers registry
_custom_handlers: dict[str, Callable[[], dict[str, Any]]] = {}


class HealthRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for health endpoints."""

    # Suppress default logging
    def log_message(self, format, *args):
        pass

    def _send_json(self, status_code: int, data: dict[str, Any]):
        """Send JSON response."""
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode("utf-8"))

    def do_GET(self):
        """Handle GET requests."""
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        # Route to appropriate handler
        handlers = {
            "/health": self._handle_health,
            "/health/live": self._handle_liveness,
            "/health/ready": self._handle_readiness,
            "/health/slo": self._handle_slo,
            "/healthz": self._handle_liveness,
            "/readyz": self._handle_readiness,
            "/livez": self._handle_liveness,
        }

        # Check custom handlers first
        if path in _custom_handlers:
            try:
                result = _custom_handlers[path]()
                status_code = 200 if result.get("healthy", True) else 503
                self._send_json(status_code, result)
            except Exception as e:
                self._send_json(500, {"error": str(e), "healthy": False})
            return

        # Use built-in handlers
        handler = handlers.get(path)
        if handler:
            handler()
        else:
            self.send_error(404, "Not Found")

    def _handle_health(self):
        """Handle overall health check."""
        try:
            _ = get_health_checker()  # Ensure health checker is initialized

            # Get liveness and readiness status
            liveness_ok = True
            readiness_ok = True

            # Check SLO compliance
            slo_status = self._get_slo_status()
            if slo_status.get("status") == "critical":
                readiness_ok = False

            response = {
                "status": "healthy" if (liveness_ok and readiness_ok) else "unhealthy",
                "checks": {
                    "liveness": "pass" if liveness_ok else "fail",
                    "readiness": "pass" if readiness_ok else "fail",
                },
                "slo": slo_status,
            }

            status_code = 200 if (liveness_ok and readiness_ok) else 503
            self._send_json(status_code, response)

        except Exception as e:
            logger.error("health_check_error", error=str(e))
            self._send_json(503, {"status": "error", "error": str(e)})

    def _handle_liveness(self):
        """Handle liveness probe - is the process running?"""
        self._send_json(
            200,
            {
                "status": "alive",
                "healthy": True,
            },
        )

    def _handle_readiness(self):
        """Handle readiness probe - can we process requests?"""
        try:
            # Check SLO compliance for readiness
            slo_status = self._get_slo_status()

            if slo_status.get("status") == "critical":
                self._send_json(
                    503,
                    {
                        "status": "not_ready",
                        "healthy": False,
                        "reason": "SLO compliance critical",
                        "slo": slo_status,
                    },
                )
            else:
                self._send_json(
                    200,
                    {
                        "status": "ready",
                        "healthy": True,
                        "slo": slo_status,
                    },
                )

        except Exception as e:
            self._send_json(
                503,
                {
                    "status": "error",
                    "healthy": False,
                    "error": str(e),
                },
            )

    def _handle_slo(self):
        """Handle SLO status endpoint."""
        try:
            slo_status = self._get_slo_status()
            status_code = 200 if slo_status.get("healthy", True) else 503
            self._send_json(status_code, slo_status)
        except Exception as e:
            self._send_json(500, {"error": str(e), "healthy": False})

    def _get_slo_status(self) -> dict[str, Any]:
        """Get SLO compliance status."""
        try:
            from obskit.health.slo_check import get_slo_health_status

            return get_slo_health_status()
        except Exception:
            return {"healthy": True, "status": "unknown", "message": "SLO tracking not available"}


def start_health_server(
    port: int = 8888,
    host: str = "0.0.0.0",
    daemon: bool = True,
) -> HTTPServer:
    """
    Start the HTTP health server.

    Parameters
    ----------
    port : int
        Port to listen on (default: 8888).
    host : str
        Host to bind to (default: '0.0.0.0').
    daemon : bool
        Run as daemon thread (default: True).

    Returns
    -------
    HTTPServer
        The server instance.

    Example
    -------
    >>> from obskit.health.server import start_health_server
    >>> start_health_server(port=8888)
    >>> # Now accessible at http://localhost:8888/health
    """
    global _health_server, _health_server_thread

    with _server_lock:
        if _health_server is not None:
            logger.warning("health_server_already_running", port=port)
            return _health_server

        try:
            _health_server = HTTPServer((host, port), HealthRequestHandler)
            _health_server_thread = threading.Thread(
                target=_health_server.serve_forever,
                name="obskit-health-server",
                daemon=daemon,
            )
            _health_server_thread.start()

            logger.info(
                "health_server_started",
                host=host,
                port=port,
                endpoints=["/health", "/health/live", "/health/ready", "/health/slo"],
            )

            return _health_server

        except Exception as e:
            logger.error("health_server_start_failed", error=str(e))
            _health_server = None
            raise


def stop_health_server():
    """
    Stop the HTTP health server.

    Example
    -------
    >>> from obskit.health.server import stop_health_server
    >>> stop_health_server()
    """
    global _health_server, _health_server_thread

    with _server_lock:
        if _health_server is None:
            return

        try:
            _health_server.shutdown()
            if _health_server_thread and _health_server_thread.is_alive():
                _health_server_thread.join(timeout=5.0)

            logger.info("health_server_stopped")

        except Exception as e:
            logger.error("health_server_stop_error", error=str(e))

        finally:
            _health_server = None
            _health_server_thread = None


def register_health_endpoint(
    path: str,
    handler: Callable[[], dict[str, Any]],
):
    """
    Register a custom health endpoint.

    Parameters
    ----------
    path : str
        URL path (e.g., '/health/custom').
    handler : Callable
        Function that returns a dict with health status.

    Example
    -------
    >>> def check_database():
    ...     return {'healthy': db.ping(), 'latency_ms': db.latency()}
    >>>
    >>> register_health_endpoint('/health/database', check_database)
    """
    if not path.startswith("/"):
        path = "/" + path
    _custom_handlers[path] = handler
    logger.debug("health_endpoint_registered", path=path)


def get_health_server() -> HTTPServer | None:
    """Get the current health server instance."""
    return _health_server


def is_health_server_running() -> bool:
    """Check if health server is running."""
    return (
        _health_server is not None
        and _health_server_thread is not None
        and _health_server_thread.is_alive()
    )


__all__ = [
    "start_health_server",
    "stop_health_server",
    "register_health_endpoint",
    "get_health_server",
    "is_health_server_running",
]
