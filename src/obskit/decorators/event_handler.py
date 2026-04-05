"""
Event Handler Tracing and Metrics Decorator
=============================================

Wrap async event handler methods with an OTel child span and Prometheus
metrics so that the full pipeline — ``HTTP request → queue publish →
consumer receive → handler.handle() → use_case.execute()`` — is visible
as a connected trace in Tempo/Jaeger.

Metrics emitted
---------------
``event_handler_duration_seconds{name}``
    Histogram of handler execution time from entry to return / raise.

``event_handler_errors_total{name}``
    Counter: incremented when the handler raises an unhandled exception.

Usage
-----
::

    from obskit import instrument_event_handler, with_event_context

    class EngagementInsertHandler:
        @instrument_event_handler(name="engagement_insert")
        @with_event_context(lambda e: {"company_id": str(e.get("company_id", ""))})
        async def handle(self, event_data: dict) -> None:
            await self._use_case.execute(event_data)

The ``instrument_event_handler`` decorator should be the **outermost** decorator
so that the span wraps the entire handler, including any context binding done
by ``with_event_context``.  The resulting trace will show:

    consumer span → event_handler.engagement_insert span → ...
"""

from __future__ import annotations

import functools
import time
from collections.abc import Callable
from typing import Any

from prometheus_client import Counter, Histogram

EVENT_HANDLER_DURATION_SECONDS: Histogram = Histogram(
    "event_handler_duration_seconds",
    "Duration of event handler execution in seconds",
    ["name"],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)

EVENT_HANDLER_ERRORS_TOTAL: Counter = Counter(
    "event_handler_errors_total",
    "Total event handler errors",
    ["name"],
)


def instrument_event_handler(
    name: str,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator factory: wrap an async handler with a child OTel span + metrics.

    Parameters
    ----------
    name : str
        Handler name — used as the span operation name
        (``event_handler.<name>``) and as the metric label value.

    Returns
    -------
    callable
        Decorator that wraps the target async function.

    Example
    -------
    ::

        @instrument_event_handler(name="status_update")
        async def handle(self, event_data: dict) -> None:
            await self._use_case.execute(event_data)

    The emitted span name is ``event_handler.status_update``.  When
    ``use_span_context`` is active on the calling thread (e.g. after
    ``extract_trace_context_from_headers``), this span is automatically
    parented under the publisher's trace.

    Notes
    -----
    * Duration is recorded in the ``finally`` block — it captures the full
      wall time including exceptions.
    * The error counter is incremented **before** re-raising so the metric
      is always recorded even if the caller swallows the exception.
    * OTel tracing degrades gracefully: when ``obskit[otlp]`` is not
      installed the span is a no-op and only the Prometheus metrics are
      emitted.
    """
    _name = name
    _span_name = f"event_handler.{name}"

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            from obskit.tracing.tracer import async_trace_span  # noqa: PLC0415

            start = time.perf_counter()
            try:
                async with async_trace_span(_span_name):
                    return await fn(*args, **kwargs)
            except Exception:
                EVENT_HANDLER_ERRORS_TOTAL.labels(name=_name).inc()
                raise
            finally:
                elapsed = time.perf_counter() - start
                EVENT_HANDLER_DURATION_SECONDS.labels(name=_name).observe(elapsed)

        return wrapper

    return decorator


__all__ = [
    "instrument_event_handler",
    "EVENT_HANDLER_DURATION_SECONDS",
    "EVENT_HANDLER_ERRORS_TOTAL",
]
