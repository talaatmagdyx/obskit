"""Async log ring buffer for high-throughput structured logging.

structlog's pipeline runs synchronously on the hot path by default, which
means every decorated request pays the cost of string formatting, dict
creation, and (worst case) a blocking write to stdout/file.

This module provides a ``queue.Queue``-backed ring buffer that:

1. Enqueues a pre-built log record in **~50 ns** (non-blocking ``put_nowait``).
2. Drains the queue on a background daemon thread using the caller-supplied
   emit function (e.g. ``structlog.get_logger().info``).
3. Silently drops records when the buffer is full (back-pressure policy is
   *best-effort* — never block the caller).

Usage::

    from obskit.logging.async_ring import AsyncLogRing

    ring = AsyncLogRing(maxsize=100_000)
    ring.start(emit_fn=print)     # or structlog logger.info etc.

    # Hot path (~50 ns):
    ring.enqueue({"event": "request_done", "op": "search", "duration_ms": 12})

    ring.stop()                   # flush remaining records and join thread
"""

from __future__ import annotations

import queue
import threading
from collections.abc import Callable
from typing import Any


class AsyncLogRing:
    """Non-blocking log ring buffer with background drain thread.

    Parameters
    ----------
    maxsize : int
        Maximum number of log records held in the buffer.  When full,
        ``enqueue()`` silently drops new records (best-effort).
        Default: 100_000.
    drain_batch : int
        Maximum number of records emitted per drain iteration.
        Default: 500.

    Example
    -------
    >>> import structlog
    >>> log = structlog.get_logger()
    >>>
    >>> def emit(record: dict) -> None:
    ...     log.info(record.pop("event", "log"), **record)
    >>>
    >>> ring = AsyncLogRing(maxsize=100_000)
    >>> ring.start(emit_fn=emit)
    >>>
    >>> ring.enqueue({"event": "request_done", "op": "search", "duration_ms": 12})
    >>> ring.stop()
    """

    def __init__(self, maxsize: int = 100_000, drain_batch: int = 500) -> None:
        self._q: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=maxsize)
        self._drain_batch = drain_batch
        self._stop_event = threading.Event()
        self._drain_thread: threading.Thread | None = None
        self._emit_fn: Callable[[dict[str, Any]], None] | None = None
        self._dropped: int = 0  # monotonic drop counter (for metrics)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self, emit_fn: Callable[[dict[str, Any]], None]) -> None:
        """Start the background drain thread.

        Parameters
        ----------
        emit_fn : callable
            Called with each log record dict.  Must be thread-safe.
            Example: ``lambda r: structlog.get_logger().info(**r)``
        """
        if self._drain_thread is not None and self._drain_thread.is_alive():
            return
        self._emit_fn = emit_fn
        self._stop_event.clear()
        self._drain_thread = threading.Thread(
            target=self._drain_loop,
            name="obskit-log-drain",
            daemon=True,
        )
        self._drain_thread.start()

    def stop(self, timeout_s: float = 5.0) -> None:
        """Signal drain thread to stop and flush remaining records.

        Parameters
        ----------
        timeout_s : float
            Maximum seconds to wait for the drain thread to finish.
        """
        self._stop_event.set()
        if self._drain_thread is not None:
            self._drain_thread.join(timeout=timeout_s)
        # Final drain on the calling thread
        self._drain_once(drain_all=True)

    # ------------------------------------------------------------------
    # Hot path
    # ------------------------------------------------------------------

    def enqueue(self, record: dict[str, Any]) -> bool:
        """Enqueue a log record (non-blocking, ~50 ns).

        Parameters
        ----------
        record : dict
            Log record to buffer.  Should be a plain dict with string keys.

        Returns
        -------
        bool
            ``True`` if the record was enqueued, ``False`` if dropped.
        """
        try:
            self._q.put_nowait(record)
            return True
        except queue.Full:
            self._dropped += 1
            return False

    @property
    def dropped(self) -> int:
        """Number of records dropped due to a full buffer."""
        return self._dropped

    @property
    def qsize(self) -> int:
        """Approximate number of records in the buffer."""
        return self._q.qsize()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _drain_loop(self) -> None:
        """Background thread: drain records until stop is signalled."""
        while not self._stop_event.is_set():
            self._drain_once()
            # Brief sleep to avoid spinning when queue is empty
            if self._q.empty():
                self._stop_event.wait(timeout=0.001)

    def _drain_once(self, drain_all: bool = False) -> None:
        """Emit up to ``_drain_batch`` records from the queue."""
        if self._emit_fn is None:
            return
        limit = self._q.maxsize if drain_all else self._drain_batch
        emitted = 0
        while emitted < limit:
            try:
                record = self._q.get_nowait()
            except queue.Empty:
                break
            try:
                self._emit_fn(record)
            except Exception:  # noqa: BLE001
                # Never let an emit error kill the drain thread
                pass  # NOSONAR
            emitted += 1
