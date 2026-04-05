"""
HTTP Client Instrumentation
============================

Prometheus metrics and OTel trace spans for outbound ``httpx.AsyncClient`` calls.

Metrics
-------
``http_client_requests_total{name, method, status_code}``
    Counter of outbound HTTP requests.  *status_code* is the HTTP response code
    as a string (``"200"``, ``"404"``, …) or ``"error"`` when a network
    exception is raised before a response is received.

``http_client_duration_seconds{name, method}``
    Histogram of outbound request latency in seconds.

Tracing
-------
Each request creates an OTel span (``"HTTP <METHOD>"``) with ``http.method``
and ``http.client.name`` attributes.  The W3C ``traceparent`` header is
injected into every outgoing request so upstream services can join the trace.

Usage
-----
::

    from obskit.integrations.http import instrument_httpx
    import httpx

    # Simple wrapping
    client = instrument_httpx(httpx.AsyncClient(), name="twitter")
    response = await client.get("https://api.twitter.com/endpoint")

    # As a context manager
    async with instrument_httpx(httpx.AsyncClient(), name="facebook") as client:
        response = await client.post(url, json=payload)
"""

from __future__ import annotations

import asyncio
import functools
import time
from typing import Any

from prometheus_client import Counter, Histogram

# ---------------------------------------------------------------------------
# Metric definitions
# ---------------------------------------------------------------------------

HTTP_CLIENT_REQUESTS_TOTAL: Counter = Counter(
    "http_client_requests_total",
    "Total outbound HTTP requests made by the instrumented client",
    ["name", "method", "status_code"],
)

HTTP_CLIENT_DURATION_SECONDS: Histogram = Histogram(
    "http_client_duration_seconds",
    "Outbound HTTP request duration in seconds",
    ["name", "method"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

# HTTP method names that should be instrumented
_HTTP_METHODS: frozenset[str] = frozenset(
    {"get", "post", "put", "patch", "delete", "head", "options", "request"}
)


class InstrumentedHttpxClient:
    """Prometheus + OTel instrumentation proxy for ``httpx.AsyncClient``.

    Do not instantiate directly — use :func:`instrument_httpx`.

    Parameters
    ----------
    client : httpx.AsyncClient
        The underlying async HTTP client.
    name : str
        Human-readable label used in Prometheus metric series.
    """

    __slots__ = ("_client", "_name")

    def __init__(self, client: Any, name: str) -> None:
        object.__setattr__(self, "_client", client)
        object.__setattr__(self, "_name", name)

    def __getattr__(self, attr: str) -> Any:
        original = getattr(self._client, attr)

        if attr not in _HTTP_METHODS or not asyncio.iscoroutinefunction(original):
            return original

        name = self._name
        method_label = attr.upper()

        @functools.wraps(original)
        async def _instrumented(*args: Any, **kwargs: Any) -> Any:
            # For the generic `request(method, url, ...)` form, extract the
            # HTTP method from the first positional arg.
            if attr == "request" and args:
                _method = str(args[0]).upper()
            else:
                _method = method_label

            # Ensure we have a mutable dict for traceparent injection.
            if kwargs.get("headers") is None:
                kwargs["headers"] = {}
            if not isinstance(kwargs["headers"], dict):
                kwargs["headers"] = dict(kwargs["headers"])

            start = time.perf_counter()
            status_code = "error"

            from obskit.tracing.tracer import (  # noqa: PLC0415
                async_trace_span,
                inject_trace_context,
            )

            async with async_trace_span(
                f"HTTP {_method}",
                component="http_client",
                attributes={"http.method": _method, "http.client.name": name},
            ):
                # Inject the current span's W3C traceparent into outgoing headers.
                inject_trace_context(kwargs["headers"])

                try:
                    response = await original(*args, **kwargs)
                    status_code = str(response.status_code)
                    return response
                except Exception:
                    raise
                finally:
                    elapsed = time.perf_counter() - start
                    HTTP_CLIENT_REQUESTS_TOTAL.labels(
                        name=name, method=_method, status_code=status_code
                    ).inc()
                    HTTP_CLIENT_DURATION_SECONDS.labels(
                        name=name, method=_method
                    ).observe(elapsed)

        return _instrumented

    # ------------------------------------------------------------------
    # Async context manager — proxy to the underlying client
    # ------------------------------------------------------------------

    async def __aenter__(self) -> InstrumentedHttpxClient:
        await self._client.__aenter__()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self._client.__aexit__(*args)


def instrument_httpx(client: Any, *, name: str = "default") -> InstrumentedHttpxClient:
    """Wrap an ``httpx.AsyncClient`` with Prometheus metrics and OTel trace spans.

    Parameters
    ----------
    client : httpx.AsyncClient
        The client instance to instrument.
    name : str
        Human-readable name used as the ``name`` label in metric series.
        Default: ``"default"``.

    Returns
    -------
    InstrumentedHttpxClient
        A transparent proxy that records metrics and creates OTel spans for
        every HTTP method call (``get``, ``post``, ``put``, ``patch``,
        ``delete``, ``head``, ``options``, ``request``).

    Example
    -------
    >>> import httpx
    >>> from obskit.integrations.http import instrument_httpx
    >>>
    >>> client = instrument_httpx(httpx.AsyncClient(), name="twitter")
    >>> response = await client.get("https://api.twitter.com/endpoint")
    """
    return InstrumentedHttpxClient(client, name)


__all__ = [
    "InstrumentedHttpxClient",
    "instrument_httpx",
    "HTTP_CLIENT_REQUESTS_TOTAL",
    "HTTP_CLIENT_DURATION_SECONDS",
]
