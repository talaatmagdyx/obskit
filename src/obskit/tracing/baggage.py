"""W3C Baggage context managers for obskit.

:func:`baggage_context` and :func:`async_baggage_context` set W3C baggage
key/value pairs for the duration of a block and clean them up automatically on
exit — the same pattern :class:`~obskit.logging.context.scoped_context` provides
for structured log context.

W3C baggage travels with every outgoing HTTP request when an OTel propagator
(e.g. ``opentelemetry-instrumentation-httpx``) is active.  Use it to attach
tenant or request identifiers that should appear in *all* downstream traces
without having to thread them through every function signature.

Example — sync
--------------
::

    from obskit.tracing.baggage import baggage_context

    with baggage_context(company_id="42", region="eu"):
        response = httpx.get("https://internal-api/data")
        # outgoing request carries:
        #   baggage: company_id=42, region=eu

Example — async (typical use in a FastAPI / use-case)
-----------------------------------------------------
::

    from obskit.tracing.baggage import async_baggage_context

    async with async_baggage_context(company_id=str(dto.company_id)):
        result = await self._execute(dto)

Example — combined with scoped_context
--------------------------------------
::

    from obskit import scoped_context
    from obskit.tracing.baggage import async_baggage_context

    async with scoped_context(company_id=str(dto.company_id)):
        async with async_baggage_context(company_id=str(dto.company_id)):
            result = await self._execute(dto)

    # Or use scoped_context(propagate=["company_id"]) which does both at once.

Notes
-----
*   If ``opentelemetry-api`` is not installed the context managers are no-ops.
*   Each context manager re-stacks baggage: nested calls add to the current
    baggage without discarding keys set by an outer scope.
*   Values are always coerced to ``str`` before being set as baggage.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, Generator
from contextlib import asynccontextmanager, contextmanager
from typing import Any

# ---------------------------------------------------------------------------
# OTel availability guard
# ---------------------------------------------------------------------------

try:
    from opentelemetry import baggage as _otel_baggage
    from opentelemetry.context import attach as _attach
    from opentelemetry.context import detach as _detach

    _OTEL_AVAILABLE = True
except ImportError:  # pragma: no cover
    _OTEL_AVAILABLE = False  # pragma: no cover


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------


def _build_context(**kwargs: Any) -> Any:
    """Build an OTel Context with all kwargs set as baggage items."""
    ctx = None
    for key, value in kwargs.items():
        ctx = _otel_baggage.set_baggage(key, str(value), context=ctx)
    return ctx


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


@contextmanager
def baggage_context(**kwargs: Any) -> Generator[None, None, None]:
    """Set W3C baggage key/values for the duration of a synchronous block.

    Attaches the baggage to the OTel context on enter and detaches it on exit,
    regardless of whether an exception is raised.  If ``opentelemetry-api`` is
    not installed the block runs unchanged (no-op).

    Parameters
    ----------
    **kwargs : Any
        Key/value pairs to set as W3C baggage.  Values are coerced to ``str``.

    Yields
    ------
    None

    Example
    -------
    >>> with baggage_context(company_id="42"):
    ...     send_http_request()  # baggage: company_id=42
    """
    if not _OTEL_AVAILABLE or not kwargs:
        yield
        return

    ctx = _build_context(**kwargs)
    token = _attach(ctx)
    try:
        yield
    finally:
        _detach(token)


@asynccontextmanager
async def async_baggage_context(**kwargs: Any) -> AsyncGenerator[None, None]:
    """Set W3C baggage key/values for the duration of an async block.

    Async counterpart of :func:`baggage_context`.  Use this inside ``async``
    functions to propagate baggage across ``await`` boundaries.

    Parameters
    ----------
    **kwargs : Any
        Key/value pairs to set as W3C baggage.  Values are coerced to ``str``.

    Yields
    ------
    None

    Example
    -------
    >>> async with async_baggage_context(company_id=str(dto.company_id)):
    ...     result = await self._execute(dto)
    """
    if not _OTEL_AVAILABLE or not kwargs:
        yield
        return

    ctx = _build_context(**kwargs)
    token = _attach(ctx)
    try:
        yield
    finally:
        _detach(token)


__all__ = [
    "baggage_context",
    "async_baggage_context",
]
