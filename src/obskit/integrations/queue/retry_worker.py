"""
Retry Worker Instrumentation
=============================

Prometheus metrics for background retry loops (e.g. Redis → RabbitMQ dead-letter
re-queuing).  Exposes two metrics per named worker:

``retry_worker_events_total{name, status}``
    Cumulative counter of events processed by the retry loop.  The *status*
    label distinguishes outcomes:

    * ``"success"``  — event re-queued or processed successfully
    * ``"failure"``  — processing failed (e.g. RabbitMQ unavailable)
    * ``"skip"``     — event intentionally skipped (TTL expired, bad payload)
    * ``"requeue"``  — event returned to the queue for a later retry

``retry_worker_queue_depth{name}``
    Current number of events waiting in the retry queue.  Call
    :meth:`RetryWorkerInstrumentor.set_queue_depth` after each queue poll to
    keep the gauge current.

Usage
-----
::

    from obskit.integrations.queue.retry_worker import instrument_retry_worker

    instr = instrument_retry_worker(name="event_retry")

    while True:
        events = await redis.lrange("retry_queue", 0, -1)
        instr.set_queue_depth(len(events))

        for event in events:
            try:
                await rabbitmq.publish(event)
                instr.record_event("success")
            except Exception:
                instr.record_event("failure")
"""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

# ---------------------------------------------------------------------------
# Metric definitions
# ---------------------------------------------------------------------------

RETRY_WORKER_EVENTS_TOTAL: Counter = Counter(
    "retry_worker_events_total",
    "Total events processed by the retry worker",
    ["name", "status"],
)

RETRY_WORKER_QUEUE_DEPTH: Gauge = Gauge(
    "retry_worker_queue_depth",
    "Current number of events waiting in the retry queue",
    ["name"],
)

RETRY_WORKER_BACKOFF_SECONDS: Histogram = Histogram(
    "retry_worker_backoff_seconds",
    "Time spent in backoff sleep before re-queuing an event",
    ["name"],
)


class RetryWorkerInstrumentor:
    """Prometheus instrumentation handle for a named retry worker.

    Do not instantiate directly — use :func:`instrument_retry_worker`.

    Parameters
    ----------
    name : str
        Human-readable label that identifies this worker in metric series.
    """

    __slots__ = ("_name",)

    def __init__(self, name: str) -> None:
        self._name = name

    def record_event(self, status: str) -> None:
        """Increment ``retry_worker_events_total`` for *status*.

        Parameters
        ----------
        status : str
            Outcome label.  Conventional values: ``"success"``,
            ``"failure"``, ``"skip"``, ``"requeue"``.  Any non-empty string
            is accepted.

        Example
        -------
        >>> instr.record_event("success")
        >>> instr.record_event("failure")
        """
        RETRY_WORKER_EVENTS_TOTAL.labels(name=self._name, status=status).inc()

    def set_queue_depth(self, depth: int) -> None:
        """Set the ``retry_worker_queue_depth`` gauge.

        Parameters
        ----------
        depth : int
            Current number of events waiting to be retried.

        Example
        -------
        >>> instr.set_queue_depth(len(pending_events))
        """
        RETRY_WORKER_QUEUE_DEPTH.labels(name=self._name).set(depth)

    def record_backoff(self, seconds: float) -> None:
        """Record time spent sleeping in backoff before re-queuing an event.

        Emits an observation to the ``retry_worker_backoff_seconds`` histogram.
        Call this after each backoff sleep to track how long the worker is
        spending in wait — useful for tuning the ``backoff_seconds`` config.

        Parameters
        ----------
        seconds : float
            Duration of the backoff sleep in seconds.

        Example
        -------
        >>> import asyncio
        >>> await asyncio.sleep(self._backoff)
        >>> instr.record_backoff(self._backoff)
        """
        RETRY_WORKER_BACKOFF_SECONDS.labels(name=self._name).observe(seconds)


def instrument_retry_worker(*, name: str = "default") -> RetryWorkerInstrumentor:
    """Return a Prometheus instrumentation handle for a retry worker.

    Parameters
    ----------
    name : str
        Human-readable worker name used as a metric label.
        Default: ``"default"``.

    Returns
    -------
    RetryWorkerInstrumentor
        Handle with :meth:`~RetryWorkerInstrumentor.record_event` and
        :meth:`~RetryWorkerInstrumentor.set_queue_depth` methods.

    Example
    -------
    >>> from obskit.integrations.queue.retry_worker import instrument_retry_worker
    >>>
    >>> instr = instrument_retry_worker(name="event_retry")
    >>> instr.record_event("success")
    >>> instr.set_queue_depth(42)
    """
    return RetryWorkerInstrumentor(name)


__all__ = [
    "RetryWorkerInstrumentor",
    "instrument_retry_worker",
    "RETRY_WORKER_EVENTS_TOTAL",
    "RETRY_WORKER_QUEUE_DEPTH",
    "RETRY_WORKER_BACKOFF_SECONDS",
]
