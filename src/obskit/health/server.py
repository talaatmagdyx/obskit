"""
WorkerHealthServer — minimal HTTP liveness probe for worker processes.

Runs a tiny HTTP server in a background daemon thread so that Kubernetes
liveness probes can reach non-HTTP services (RabbitMQ consumers, cron
workers, async pipeline workers, etc.) without requiring FastAPI or Flask.

Usage
-----
.. code-block:: python

    from obskit.health import WorkerHealthServer

    health_server = WorkerHealthServer(
        port=8002,
        checks={
            "consumer": lambda: consumer.is_alive(),
            "retry_worker": lambda: retry_worker.is_running,
        },
        max_silence_seconds=120,
    )
    await health_server.start()

    # In the message processing loop:
    health_server.record_activity()

    # On shutdown:
    health_server.stop()

HTTP contract
-------------
``GET /health``
    Returns ``200 OK`` with a JSON body when all checks pass and the
    activity timer is within threshold::

        {"status": "ok", "checks": {"consumer": {"status": "ok"}, ...}}

    Returns ``503 Service Unavailable`` with the same structure when any
    check fails or silence exceeds *max_silence_seconds*::

        {
            "status": "fail",
            "checks": {
                "consumer": {"status": "fail"},
                "activity": {
                    "status": "stale",
                    "silence_seconds": 135.2,
                    "threshold_seconds": 120
                }
            }
        }

``GET /live`` and ``GET /ready``
    Aliases for ``/health`` — accepted for Kubernetes probe compatibility.

Any other path returns ``404``.
"""

from __future__ import annotations

import http.server
import json
import threading
import time
from collections.abc import Callable
from typing import Any


class WorkerHealthServer:
    """Minimal HTTP liveness/readiness probe for non-HTTP worker processes.

    Runs ``http.server.HTTPServer`` in a daemon thread — no FastAPI, Flask,
    or asyncio required.  A Kubernetes ``livenessProbe`` on ``/health`` will
    restart the pod automatically when a check fails or when the worker has
    not processed a message in ``max_silence_seconds``.

    Parameters
    ----------
    port:
        TCP port to listen on (e.g. ``8002``).
    checks:
        Mapping of check name → zero-argument callable that returns a
        truthy value when healthy.  Exceptions are caught and treated as
        ``fail``.  Sync callables only — async checks must be wrapped.
    max_silence_seconds:
        If set, the server returns 503 when :meth:`record_activity` has
        not been called within this many seconds.  Use this to detect
        a stuck consumer that is alive as a process but not processing.

    Example::

        health = WorkerHealthServer(
            port=8002,
            checks={"consumer": lambda: consumer.is_alive()},
            max_silence_seconds=120,
        )
        await health.start()
        health.record_activity()   # call after each message processed
    """

    def __init__(
        self,
        port: int,
        checks: dict[str, Callable[[], Any]],
        *,
        max_silence_seconds: float | None = None,
    ) -> None:
        self._port = port
        self._checks = checks
        self._max_silence_seconds = max_silence_seconds
        self._last_activity: float = time.monotonic()
        self._server: http.server.HTTPServer | None = None
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the health HTTP server in a background daemon thread.

        Safe to call from async code — the server itself runs in a
        regular thread and does not block the event loop.
        """
        self._start_sync()

    def start_sync(self) -> None:
        """Start from synchronous code (e.g. plain ``__main__``)."""
        self._start_sync()

    def stop(self) -> None:
        """Shut down the HTTP server and join the background thread."""
        if self._server is not None:
            self._server.shutdown()
        if self._thread is not None:
            self._thread.join(timeout=5.0)

    def record_activity(self) -> None:
        """Record that a message or task was processed.

        Resets the silence timer used by *max_silence_seconds*.  Call this
        after every successful message consumption in the worker loop.
        """
        self._last_activity = time.monotonic()

    @property
    def port(self) -> int:
        """The TCP port the server is listening on."""
        return self._port

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _start_sync(self) -> None:
        server_ref = self
        handler_class = server_ref._make_handler()
        self._server = http.server.HTTPServer(("", self._port), handler_class)
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name=f"obskit-health-{self._port}",
            daemon=True,
        )
        self._thread.start()

    def _make_handler(self) -> type:
        server_ref = self

        class _Handler(http.server.BaseHTTPRequestHandler):
            _HEALTH_PATHS = {"/health", "/live", "/ready"}

            def do_GET(self) -> None:  # noqa: N802
                if self.path not in self._HEALTH_PATHS:
                    self.send_response(404)
                    self.end_headers()
                    return

                ok, body = server_ref._evaluate()
                status = 200 if ok else 503
                data = json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args: Any) -> None:  # noqa: ARG002
                pass  # suppress default httpd access logs

        return _Handler

    def _evaluate(self) -> tuple[bool, dict[str, Any]]:
        """Run all checks and return ``(healthy, response_body)``."""
        results: dict[str, Any] = {}
        overall_ok = True

        for name, fn in self._checks.items():
            try:
                ok = bool(fn())
            except Exception as exc:
                ok = False
                results[name] = {"status": "error", "detail": str(exc)}
            else:
                results[name] = {"status": "ok" if ok else "fail"}
            if not ok:
                overall_ok = False

        if self._max_silence_seconds is not None:
            elapsed = time.monotonic() - self._last_activity
            silence_ok = elapsed < self._max_silence_seconds
            results["activity"] = {
                "status": "ok" if silence_ok else "stale",
                "silence_seconds": round(elapsed, 1),
                "threshold_seconds": self._max_silence_seconds,
            }
            if not silence_ok:
                overall_ok = False

        return overall_ok, {
            "status": "ok" if overall_ok else "fail",
            "checks": results,
        }


__all__ = ["WorkerHealthServer"]
