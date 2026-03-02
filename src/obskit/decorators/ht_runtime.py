"""High-throughput pipeline singleton for with_observability(high_throughput=True).

When ``high_throughput=True`` is set on a decorator, the standard synchronous
pipeline (structlog × 2 + Prometheus lock per request) is replaced by this
module's lazy-started singleton:

- **AsyncLogRing**: enqueues log records in ~50 ns; drained by a daemon thread.
- **ThreadLocalAggregator**: buffers per-request metric counts in thread-local
  storage (~30–60 ns); flushed to Prometheus every 1 s by a daemon thread.

Both components start on the **first decorated call** (double-checked lock),
so there is no startup-ordering requirement.

Optional integrations (call ``configure_ht_pipeline()`` before first use)
--------------------------------------------------------------------------
- **StatsDEmitter**: aggregated counts + timings are also emitted to a StatsD
  agent every ~1 s, alongside the standard Prometheus flush.
- **HighThroughputSLOTracker**: each ``record()`` call also posts a measurement
  to the tracker (lock-free, ~100 ns overhead).

Process shutdown / testing
--------------------------
Call ``reset_ht_pipeline()`` to stop the daemon threads and release resources.
The autouse ``reset_obskit_state`` fixture in ``tests/conftest.py`` calls this
automatically between tests.

Import chain (no circular imports)
-----------------------------------
    combined.py → ht_runtime.py → async_ring, threadsafe_aggregator, red,
                                  statsd_emitter, slo.high_throughput (all leaf modules)
"""

from __future__ import annotations

import threading
import warnings
from typing import Any, Literal, cast

import structlog

from obskit.logging.async_ring import AsyncLogRing
from obskit.metrics.red import get_red_metrics
from obskit.metrics.statsd_emitter import StatsDEmitter
from obskit.metrics.threadsafe_aggregator import ThreadLocalAggregator
from obskit.slo.high_throughput import HighThroughputSLOTracker


class _HTPipeline:
    """Lazy-started singleton holding AsyncLogRing + ThreadLocalAggregator.

    All public methods are thread-safe.

    Optional integrations are attached via :meth:`configure` **before** the
    first :meth:`record` call.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._started = False
        self._agg: ThreadLocalAggregator | None = None
        self._ring: AsyncLogRing | None = None
        self._statsd: StatsDEmitter | None = None
        self._slo_tracker: HighThroughputSLOTracker | None = None

    # ------------------------------------------------------------------
    # Configuration (call before first record())
    # ------------------------------------------------------------------

    def configure(
        self,
        statsd: StatsDEmitter | None = None,
        slo_tracker: HighThroughputSLOTracker | None = None,
    ) -> None:
        """Attach optional integrations to the pipeline.

        Must be called **before** the first :meth:`record` call (i.e. before
        the first ``with_observability(..., high_throughput=True)`` invocation).
        Calls after the pipeline has started are silently ignored with a
        ``RuntimeWarning``.

        Parameters
        ----------
        statsd : StatsDEmitter, optional
            When set, aggregated counts and timings are *also* emitted to a
            StatsD agent during every flush cycle (~1 s).  Prometheus emission
            is unaffected.  The caller retains ownership of the socket; the
            pipeline will **not** close it on :meth:`stop`.
        slo_tracker : HighThroughputSLOTracker, optional
            When set, every :meth:`record` call posts a lock-free measurement
            to the tracker (~100 ns overhead per call).  Register SLOs on the
            tracker before decorated functions are called.
        """
        with self._lock:
            if self._started:
                warnings.warn(
                    "configure() called after the HT pipeline has already started; "
                    "settings ignored. Call configure_ht_pipeline() before the first "
                    "high_throughput=True invocation.",
                    RuntimeWarning,
                    stacklevel=3,
                )
                return
            self._statsd = statsd
            self._slo_tracker = slo_tracker

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
        """Buffer one request observation (metrics + log) on the hot path.

        Parameters
        ----------
        operation : str
            Operation name (used as Prometheus label and log field).
        component : str
            Component name (used as log field).
        duration_s : float
            Request duration in seconds.
        success : bool
            Whether the request succeeded.
        context : dict
            Additional key-value pairs included in the log record.
        error : exception, optional
            Exception to log on failure path.
        """
        self._ensure_started()

        # Buffer metric — ~30–60 ns (thread-local dict increment)
        self._agg.record_request(operation, duration_s, success)  # type: ignore[union-attr]

        # Optional SLO tracking — lock-free, ~100 ns
        if self._slo_tracker is not None:
            self._slo_tracker.record_measurement(operation, duration_s, success=success)

        # Build and enqueue log record — ~50 ns (queue.put_nowait)
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
    def started(self) -> bool:
        """True if the daemon threads are running."""
        return self._started

    def stop(self, timeout_s: float = 5.0) -> None:
        """Flush and stop both daemon threads.

        Safe to call multiple times (idempotent).  Does **not** close an
        externally-provided :class:`StatsDEmitter` — the caller owns that.
        """
        with self._lock:
            if not self._started:
                return
            if self._agg is not None:
                self._agg.stop(timeout_s=timeout_s)
            if self._ring is not None:
                self._ring.stop(timeout_s=timeout_s)
            self._agg = None
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
            if self._started:
                return
            self._do_start()

    def _do_start(self) -> None:
        """Initialise and start AsyncLogRing + ThreadLocalAggregator."""
        _log = structlog.get_logger("obskit.ht")

        # Capture optional integrations for closure use
        statsd = self._statsd

        def emit_log(record: dict[str, Any]) -> None:
            """Forward a buffered log record to structlog."""
            event = record.pop("event", "log")
            _log.info(event, **record)

        def flush_metrics(
            counts: dict[tuple[str, str], int],
            durations: dict[tuple[str, str], list[float]],
        ) -> None:
            """Flush buffered durations to Prometheus REDMetrics (+ optional StatsD)."""
            red = get_red_metrics()
            for (op, status), ds in durations.items():
                for d in ds:
                    red.observe_request(op, d, cast(Literal["success", "failure", "error"], status))

            # Optional StatsD emission — fire-and-forget UDP, never raises
            if statsd is not None:
                for (op, status), count in counts.items():
                    statsd.emit_counter(
                        "requests_total",
                        value=count,
                        tags={"operation": op, "status": status},
                    )
                for (op, _status), ds in durations.items():
                    for d in ds:
                        statsd.emit_timing(
                            "request_duration_ms",
                            value=d * 1000,
                            tags={"operation": op},
                        )

        ring = AsyncLogRing(maxsize=100_000)
        ring.start(emit_fn=emit_log)

        agg = ThreadLocalAggregator(flush_interval_s=1.0, on_flush=flush_metrics)
        agg.start()

        self._ring = ring
        self._agg = agg
        self._started = True


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_ht_pipeline = _HTPipeline()


def get_ht_pipeline() -> _HTPipeline:
    """Return the process-level high-throughput pipeline (lazy-started)."""
    return _ht_pipeline


def configure_ht_pipeline(
    statsd: StatsDEmitter | None = None,
    slo_tracker: HighThroughputSLOTracker | None = None,
) -> None:
    """Configure optional integrations on the global HT pipeline.

    Must be called **before** the first ``with_observability(...,
    high_throughput=True)`` invocation.

    Parameters
    ----------
    statsd : StatsDEmitter, optional
        Attach a StatsD emitter.  Aggregated counts and timings will be
        emitted alongside the standard Prometheus flush every ~1 s.
    slo_tracker : HighThroughputSLOTracker, optional
        Attach an SLO tracker.  Every decorated call will post a lock-free
        measurement to it.

    Example
    -------
    >>> from obskit.metrics.statsd_emitter import StatsDEmitter
    >>> from obskit.slo.high_throughput import HighThroughputSLOTracker
    >>> from obskit.slo.types import SLOType
    >>> from obskit.decorators.ht_runtime import configure_ht_pipeline
    >>>
    >>> tracker = HighThroughputSLOTracker()
    >>> tracker.register_slo("api_availability", SLOType.AVAILABILITY, 0.999)
    >>>
    >>> emitter = StatsDEmitter(host="statsd.internal", port=8125, prefix="svc")
    >>>
    >>> configure_ht_pipeline(statsd=emitter, slo_tracker=tracker)
    >>> # Now all high_throughput=True calls feed both Prometheus and StatsD,
    >>> # and availability SLO is tracked automatically.
    """
    _ht_pipeline.configure(statsd=statsd, slo_tracker=slo_tracker)


def reset_ht_pipeline() -> None:
    """Stop and replace the singleton — call between tests to prevent leakage."""
    global _ht_pipeline
    _ht_pipeline.stop()
    _ht_pipeline = _HTPipeline()
