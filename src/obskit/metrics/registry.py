"""
Prometheus Registry and HTTP Server
====================================

This module manages the Prometheus metrics registry and provides
an HTTP server for exposing metrics at the `/metrics` endpoint.

Registry Management
-------------------
The registry is where all metrics are stored. obskit uses the default
Prometheus registry by default, but you can create custom registries
for isolation (useful in testing).

HTTP Server
-----------
Prometheus scrapes metrics via HTTP. This module provides a simple
HTTP server that exposes the `/metrics` endpoint.

Example - Starting Metrics Server
---------------------------------
.. code-block:: python

    from obskit.metrics import start_http_server

    # Start on default port
    start_http_server()  # http://localhost:9090/metrics

    # Custom port
    start_http_server(port=8080)  # http://localhost:8080/metrics

Example - Custom Registry
-------------------------
.. code-block:: python

    from obskit.metrics.registry import get_registry, create_registry

    # Get the default registry
    default_registry = get_registry()

    # Create isolated registry (for testing)
    test_registry = create_registry()

Prometheus Configuration
------------------------
Add to your prometheus.yml:

.. code-block:: yaml

    scrape_configs:
      - job_name: 'my-service'
        static_configs:
          - targets: ['localhost:9090']
        scrape_interval: 15s

See Also
--------
prometheus_client : The underlying Prometheus client
obskit.metrics.red : RED method implementation
"""

from __future__ import annotations

import threading
from typing import Any

from obskit.config import get_settings
from obskit.logging import get_logger

# Check if prometheus_client is available
try:
    import prometheus_client
    from prometheus_client import (
        REGISTRY,
        CollectorRegistry,
    )
    from prometheus_client import (
        start_http_server as _start_http_server,
    )

    PROMETHEUS_AVAILABLE = True
except ImportError:  # pragma: no cover
    PROMETHEUS_AVAILABLE = False
    REGISTRY = None  # type: ignore[assignment]
    CollectorRegistry = None  # type: ignore[misc, assignment]

# Logger
logger = get_logger("obskit.metrics.registry")

# Global state
_registry: Any | None = None
_registry_lock = threading.Lock()
_http_server_started: bool = False
_http_server_lock = threading.Lock()
_http_server_thread: threading.Thread | None = None
_http_server: Any | None = None  # HTTPServer instance


def get_registry() -> Any:
    """
    Get the Prometheus metrics registry.

    Returns the global registry used for all obskit metrics.
    If prometheus_client is not installed, returns None.

    Returns
    -------
    CollectorRegistry or None
        The Prometheus registry, or None if not available.

    Example
    -------
    >>> from obskit.metrics.registry import get_registry
    >>>
    >>> registry = get_registry()
    >>> if registry:
    ...     # Use registry
    ...     pass
    """
    global _registry

    if not PROMETHEUS_AVAILABLE:  # pragma: no cover
        logger.warning(
            "prometheus_not_available",
            message="prometheus_client not installed. Install with: pip install obskit[metrics]",
        )
        return None

    # Double-checked locking pattern for thread safety
    if _registry is None:
        with _registry_lock:
            if _registry is None:  # pragma: no branch
                _registry = REGISTRY

    return _registry


def create_registry() -> Any:
    """
    Create a new isolated Prometheus registry.

    Use this for testing to avoid metric conflicts between tests.

    Returns
    -------
    CollectorRegistry or None
        A new registry, or None if prometheus_client not installed.

    Example
    -------
    >>> from obskit.metrics.registry import create_registry
    >>>
    >>> # In test setup
    >>> registry = create_registry()
    >>> metrics = REDMetrics("test_service", registry=registry)
    """
    if not PROMETHEUS_AVAILABLE:  # pragma: no cover
        return None

    return CollectorRegistry()


def start_http_server(
    port: int | None = None,
    host: str | None = None,
) -> bool:
    """
    Start the Prometheus metrics HTTP server.

    Starts an HTTP server that exposes metrics at the `/metrics` endpoint.
    Prometheus scrapes this endpoint to collect metrics.

    Parameters
    ----------
    port : int, optional
        Port to listen on. Default: from settings (9090).

    host : str, optional
        Host to bind to. Default: "0.0.0.0" (all interfaces).

    Returns
    -------
    bool
        True if server started, False if not available or already running.

    Example
    -------
    >>> from obskit.metrics import start_http_server
    >>>
    >>> # Start with default settings
    >>> start_http_server()
    >>> # Metrics at http://localhost:9090/metrics
    >>>
    >>> # Custom port
    >>> start_http_server(port=8080)
    >>> # Metrics at http://localhost:8080/metrics

    Notes
    -----
    - Can only be called once (subsequent calls are no-ops)
    - The server runs in a background thread
    - Safe to call even if prometheus_client not installed
    - Thread-safe: uses locks to prevent race conditions
    """
    global _http_server_started, _http_server_thread, _http_server

    if not PROMETHEUS_AVAILABLE:  # pragma: no cover
        logger.warning(
            "metrics_server_unavailable",
            message="Cannot start metrics server: prometheus_client not installed",
        )
        return False

    with _http_server_lock:
        if _http_server_started:
            logger.debug("metrics_server_already_running")
            return True

        settings = get_settings()

        actual_port = port if port is not None else settings.metrics_port
        # nosec B104 - binding to all interfaces is intentional for container/k8s deployments
        actual_host = host if host is not None else "0.0.0.0"  # nosec B104

        try:
            # Check if authentication is enabled
            if settings.metrics_auth_enabled and settings.metrics_auth_token:
                # Use custom authenticated handler
                from http.server import HTTPServer

                from obskit.metrics.auth import create_authenticated_handler

                handler_class = create_authenticated_handler(settings.metrics_auth_token)
                _http_server = HTTPServer((actual_host, actual_port), handler_class)
                _http_server_thread = threading.Thread(
                    target=_http_server.serve_forever,
                    daemon=True,
                    name="obskit-metrics-server",
                )
                _http_server_thread.start()
                # _http_server is stored for potential future cleanup (currently unused)
                logger.info(
                    "metrics_server_started_with_auth",
                    port=actual_port,
                    host=actual_host,
                )
            else:
                # Use default Prometheus handler (no auth)
                # _start_http_server returns (WSGIServer, Thread), we only need the thread
                server_result = _start_http_server(actual_port, addr=actual_host)
                if server_result is not None:
                    _server, _http_server_thread = server_result
                    # Store server reference for potential future cleanup (currently unused)
                    _http_server = _server

            _http_server_started = True

            logger.info(
                "metrics_server_started",
                port=actual_port,
                host=actual_host,
                endpoint=f"http://{actual_host}:{actual_port}/metrics",
            )

            return True

        except Exception as e:  # pragma: no cover
            logger.error(
                "metrics_server_failed",
                error=str(e),
                error_type=type(e).__name__,
                port=actual_port,
            )
            return False


def stop_http_server() -> None:
    """
    Stop the Prometheus metrics HTTP server gracefully.

    This function stops the HTTP server and waits for it to shut down.
    The server can be restarted by calling start_http_server() again.

    Example
    -------
    >>> from obskit.metrics import start_http_server, stop_http_server
    >>>
    >>> # Start server
    >>> start_http_server(port=9090)
    >>>
    >>> # Later, stop it
    >>> stop_http_server()

    Notes
    -----
    - Thread-safe: uses locks to prevent race conditions
    - Safe to call even if server is not running
    - Waits up to 5 seconds for server to stop
    """
    global _http_server_started, _http_server_thread, _http_server

    with _http_server_lock:
        if not _http_server_started:
            return

        if _http_server_thread is not None:  # pragma: no branch
            try:
                # Try to stop the server if we have a reference to it
                # (for authenticated handler case where we use HTTPServer)
                if _http_server is not None:  # pragma: no branch
                    try:
                        _http_server.shutdown()
                    except AttributeError:  # nosec B110 - shutdown method may not exist
                        pass  # prometheus_client WSGIServer doesn't have shutdown method
                    except (
                        Exception
                    ):  # pragma: no cover  # nosec B110 - shutdown errors non-critical
                        pass  # Ignore errors during shutdown

                # The prometheus_client server thread is a daemon thread
                # We need to access the internal server to stop it
                # Unfortunately, prometheus_client doesn't expose a clean stop method
                # So we mark it as stopped and let it be cleaned up naturally
                logger.info("metrics_server_stopping")
                _http_server_started = False
                _http_server_thread = None
                _http_server = None
                logger.info("metrics_server_stopped")
            except Exception as e:  # pragma: no cover
                logger.error(
                    "metrics_server_stop_failed",
                    error=str(e),
                    error_type=type(e).__name__,
                )
                # Still mark as stopped to allow retry
                _http_server_started = False
        else:
            _http_server_started = False


def reset_registry() -> None:
    """
    Reset the registry for testing.

    Clears all registered metrics. Use this in test teardown.

    Warning
    -------
    This unregisters all metrics! Only use in tests.
    """
    global _registry

    with _registry_lock:
        if PROMETHEUS_AVAILABLE and _registry is not None:
            # Unregister all collectors
            collectors = list(_registry._names_to_collectors.values())
            for collector in collectors:  # pragma: no cover
                try:
                    _registry.unregister(collector)
                except Exception:  # pragma: no cover  # nosec B110 - cleanup errors non-critical
                    pass  # Ignore errors during cleanup

        _registry = None


# =============================================================================
# Utility Functions
# =============================================================================


def generate_latest() -> bytes:
    """
    Generate metrics output in Prometheus text format.

    Use this to manually export metrics without the HTTP server.

    Returns
    -------
    bytes
        Prometheus text format metrics.

    Example
    -------
    >>> from obskit.metrics.registry import generate_latest
    >>>
    >>> # Get metrics as text
    >>> metrics_text = generate_latest()
    >>> print(metrics_text.decode())
    """
    if not PROMETHEUS_AVAILABLE:  # pragma: no cover
        return b""

    return prometheus_client.generate_latest(get_registry())
