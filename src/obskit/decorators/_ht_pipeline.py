"""High-throughput pipeline singleton for with_observability(high_throughput=True).

When ``high_throughput=True`` is set on a decorator, the standard synchronous
pipeline (structlog × 2 + Prometheus lock per request) is replaced by this
module's lazy-started singleton:

- **AsyncLogRing**: enqueues log records in ~50 ns; drained by a daemon thread.

Both components start on the **first decorated call** (double-checked lock),
so there is no startup-ordering requirement.

Process shutdown / testing
--------------------------
Call ``reset_ht_pipeline()`` to stop the daemon threads and release resources.
The autouse ``reset_obskit_state`` fixture in ``tests/conftest.py`` calls this
automatically between tests.

Import chain (no circular imports)
-----------------------------------
    combined.py → _ht_pipeline.py → async_ring, red (all leaf modules)
"""

from __future__ import annotations

import threading
from typing import Any

import structlog

from obskit.logging.async_ring import AsyncLogRing


class _HTPipeline:
    """Lazy-started singleton holding AsyncLogRing.

    All public methods are thread-safe.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._started = False
        self._ring: AsyncLogRing | None = None

    # ------------------------------------------------------------------
    # Hot path (~80–120 ns total per record call)
    # ------------------------------------------------------------------

    def record(
        self,
        operation: str,
        component: str,
        duration_s: float,
        success: bool,
        context: dict[str, Any],
        error: BaseException | None = None,
    ) -> None:
        """Buffer one log observation and record Prometheus metrics on the hot path.

        Metrics are recorded synchronously (~200 ns — Prometheus counter increments
        are atomic int operations).  Logs are buffered via AsyncLogRing (~50 ns enqueue)
        and drained by a background thread.
        """
        self._ensure_started()

        # Metrics: record synchronously so dashboards/alerts are never silently dark.
        # Counter increments inside prometheus_client are O(1) atomic operations —
        # cheaper than structlog processing, safe to call on every request.
        try:
            from obskit.metrics.red import get_red_metrics  # noqa: PLC0415

            get_red_metrics().observe_request(
                operation=operation,
                duration_seconds=duration_s,
                status="success" if success else "failure",
                error_type=type(error).__name__ if error is not None else None,
            )
        except Exception:  # noqa: BLE001
            pass  # never let metric failure degrade the hot path

        # Logs: enqueue for background drain.
        log_record: dict[str, Any] = {
            "event": "operation_completed" if success else "operation_failed",
            "component": component,
            "operation": operation,
            "duration_ms": round(duration_s * 1000, 3),
            **context,
        }
        if error is not None:
            log_record["error"] = str(error)
            log_record["error_type"] = type(error).__name__
        self._ring.enqueue(log_record)  # type: ignore[union-attr]

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    @property
    def started(self) -> bool:  # pragma: no cover
        """True if the daemon threads are running."""
        return self._started  # pragma: no cover

    def stop(self, timeout_s: float = 5.0) -> None:
        """Flush and stop the daemon thread.

        Safe to call multiple times (idempotent).
        """
        with self._lock:
            if not self._started:
                return
            if self._ring is not None:  # pragma: no cover
                self._ring.stop(timeout_s=timeout_s)  # pragma: no cover
            self._ring = None
            self._started = False

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _ensure_started(self) -> None:
        """Start daemon threads on first use (double-checked lock)."""
        if self._started:
            return
        with self._lock:
            if self._started:  # pragma: no cover
                return  # pragma: no cover
            self._do_start()

    def _do_start(self) -> None:
        """Initialise and start AsyncLogRing."""
        _log = structlog.get_logger("obskit.ht")

        def emit_log(record: dict[str, Any]) -> None:
            """Forward a buffered log record to structlog."""
            event = record.pop("event", "log")
            _log.info(event, **record)

        ring = AsyncLogRing(maxsize=100_000)
        ring.start(emit_fn=emit_log)

        self._ring = ring
        self._started = True


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_ht_pipeline = _HTPipeline()


def get_ht_pipeline() -> _HTPipeline:
    """Return the process-level high-throughput pipeline (lazy-started)."""
    return _ht_pipeline


def configure_ht_pipeline() -> None:
    """Configure the global HT pipeline."""
    pass  # pragma: no cover  # No optional integrations remain after threadsafe_aggregator removal


def reset_ht_pipeline() -> None:
    """Stop and replace the singleton — call between tests to prevent leakage."""
    global _ht_pipeline
    _ht_pipeline.stop()
    _ht_pipeline = _HTPipeline()
