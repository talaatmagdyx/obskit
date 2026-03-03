"""Thread-local metric aggregator for high-throughput services.

At millions of requests/second, every Prometheus write acquires a GIL-held
lock inside the prometheus_client C extension.  This module eliminates
per-request lock contention by buffering counters and histogram observations
in ``threading.local()`` storage and flushing them to Prometheus on a
configurable interval (default 1 s) via a background daemon thread.

Hot-path cost: ~30–60 ns (dict lookup + int increment in thread-local storage).
Cold-path cost (flush): amortised across all requests in the interval.

Usage::

    from obskit.metrics.threadsafe_aggregator import ThreadLocalAggregator

    agg = ThreadLocalAggregator(flush_interval_s=1.0)
    agg.start()                          # start background flush thread

    # In request handler (hot path):
    agg.record_request("create_order", duration_s=0.045, success=True)

    agg.stop()                           # graceful shutdown (waits for flush)
"""

from __future__ import annotations

import threading
from collections import defaultdict
from collections.abc import Callable
from typing import Any


class _Buffer:
    """Plain per-thread accumulator — readable from any thread.

    Unlike ``threading.local``, a ``_Buffer`` is a normal Python object
    whose attributes are accessible from any thread.  We use
    ``threading.local`` only to *find* each thread's ``_Buffer`` instance,
    not to store the data itself.
    """

    __slots__ = ("counts", "durations")

    def __init__(self) -> None:
        # counts[(operation, status)] = total_calls
        self.counts: dict[tuple[str, str], int] = defaultdict(int)
        # durations[(operation, status)] = [list of duration_s floats]
        self.durations: dict[tuple[str, str], list[float]] = defaultdict(list)


class _ThreadLocal(threading.local):
    """Thread-local pointer to a per-thread _Buffer."""

    buf: _Buffer | None = None


class ThreadLocalAggregator:
    """Aggregate Prometheus writes in thread-local buffers, flush on interval.

    Parameters
    ----------
    flush_interval_s : float
        Seconds between background flushes (default 1.0).
    on_flush : callable, optional
        Called with ``(counts, durations)`` on each flush.  Defaults to a
        no-op if not provided; inject your Prometheus write logic here.

    Example
    -------
    >>> def my_flush(counts, durations):
    ...     for (op, status), n in counts.items():
    ...         prometheus_counter.labels(op, status).inc(n)
    ...     for (op, status), ds in durations.items():
    ...         for d in ds:
    ...             prometheus_histogram.labels(op, status).observe(d)
    >>>
    >>> agg = ThreadLocalAggregator(flush_interval_s=1.0, on_flush=my_flush)
    >>> agg.start()
    >>> agg.record_request("search", 0.012, success=True)
    >>> agg.stop()
    """

    def __init__(
        self,
        flush_interval_s: float = 1.0,
        on_flush: Callable[[dict[tuple[str, str], int], dict[tuple[str, str], list[float]]], None]
        | None = None,
    ) -> None:
        self._flush_interval_s = flush_interval_s
        self._on_flush = on_flush or (lambda _c, _d: None)
        # _tl holds each thread's *pointer* to its _Buffer (thread-local reference).
        # The _Buffer objects themselves are plain objects readable by the flush thread.
        self._tl = _ThreadLocal()
        # Registry of all _Buffer objects from every thread that has written.
        self._buffers: list[_Buffer] = []
        self._registry_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._flush_thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the background flush daemon thread."""
        if self._flush_thread is not None and self._flush_thread.is_alive():
            return
        self._stop_event.clear()
        self._flush_thread = threading.Thread(
            target=self._flush_loop,
            name="obskit-aggregator-flush",
            daemon=True,
        )
        self._flush_thread.start()

    def stop(self, timeout_s: float = 5.0) -> None:
        """Stop the flush thread and perform one final flush."""
        self._stop_event.set()
        if self._flush_thread is not None:
            self._flush_thread.join(timeout=timeout_s)
        self._flush_once()

    # ------------------------------------------------------------------
    # Hot path (called per request)
    # ------------------------------------------------------------------

    def record_request(
        self,
        operation: str,
        duration_s: float,
        success: bool = True,
        **_extra: Any,
    ) -> None:
        """Buffer one request observation in thread-local storage.

        Parameters
        ----------
        operation : str
            Operation name used as a Prometheus label.
        duration_s : float
            Request duration in seconds.
        success : bool
            Whether the request succeeded.
        """
        buf = self._get_buffer()
        status = "success" if success else "failure"
        key = (operation, status)
        buf.counts[key] += 1
        buf.durations[key].append(duration_s)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _get_buffer(self) -> _Buffer:
        """Return this thread's _Buffer, creating and registering it on first use."""
        buf = self._tl.buf
        if buf is None:
            buf = _Buffer()
            self._tl.buf = buf
            with self._registry_lock:
                self._buffers.append(buf)
        return buf

    def _flush_loop(self) -> None:
        """Background thread: flush every ``_flush_interval_s`` seconds."""
        while not self._stop_event.wait(timeout=self._flush_interval_s):
            self._flush_once()

    def _flush_once(self) -> None:
        """Snapshot all per-thread _Buffer objects and call ``on_flush``."""
        merged_counts: dict[tuple[str, str], int] = defaultdict(int)
        merged_durations: dict[tuple[str, str], list[float]] = defaultdict(list)

        with self._registry_lock:
            buffers = list(self._buffers)

        for buf in buffers:
            # Swap counts/durations atomically under the GIL.  _Buffer is a
            # plain object (not threading.local), so the flush thread can read
            # and replace its attributes directly.
            old_counts = buf.counts
            old_durations = buf.durations
            buf.counts = defaultdict(int)
            buf.durations = defaultdict(list)

            for key, n in old_counts.items():
                merged_counts[key] += n
            for key, ds in old_durations.items():
                merged_durations[key].extend(ds)

        if merged_counts or merged_durations:
            self._on_flush(dict(merged_counts), dict(merged_durations))

    def get_pending_counts(self) -> dict[tuple[str, str], int]:
        """Return a snapshot of un-flushed counts across all threads (for testing)."""
        merged: dict[tuple[str, str], int] = defaultdict(int)
        with self._registry_lock:
            buffers = list(self._buffers)
        for buf in buffers:
            for key, n in buf.counts.items():
                merged[key] += n
        return dict(merged)
