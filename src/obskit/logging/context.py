"""
Log Context Binding
===================

Thin wrappers around ``structlog.contextvars`` so that application code
never needs to import structlog directly for request-scoped context binding.

Typical usage — in ASGI middleware or a dependency::

    from obskit.logging.context import bind_context, clear_context

    # At the start of each request
    clear_context()
    bind_context(company_id=tenant_id, request_id=req_id)

    # context is automatically included in every log call for this task

The context variables are Python :mod:`contextvars` under the hood, so they
are isolated per async task / thread (no cross-request leakage).

Functions
---------
bind_context(**kw)
    Add key/value pairs to the current log context.

unbind_context(*keys)
    Remove specific keys from the current log context.

clear_context()
    Remove **all** keys from the current log context.

get_context()
    Return a copy of the current log context dict.

reset_context(token)
    Reset context to a snapshot captured by a previous :func:`bind_context`
    call (uses the ``contextvars.Token`` returned by structlog internals).
"""

from __future__ import annotations

from typing import Any

from structlog.contextvars import (
    bind_contextvars,
    clear_contextvars,
    get_contextvars,
    unbind_contextvars,
)


def _try_attach_baggage(keys: list[str], kw: dict[str, Any]) -> Any:
    """Attach OTel baggage for the specified keys; returns token or None."""
    try:
        from opentelemetry import baggage as _otel_baggage  # noqa: PLC0415
        from opentelemetry.context import attach as _attach  # noqa: PLC0415
    except ImportError:
        return None
    ctx = None
    for k in keys:
        if k in kw:
            ctx = _otel_baggage.set_baggage(k, str(kw[k]), context=ctx)
    if ctx is None:
        return None
    return _attach(ctx)


def _try_detach_baggage(token: Any) -> None:
    """Detach OTel baggage token if it was attached."""
    if token is None:
        return
    try:
        from opentelemetry.context import detach as _detach  # noqa: PLC0415
        _detach(token)
    except ImportError:  # pragma: no cover
        pass  # NOSONAR


class scoped_context:
    """Context manager that binds key/value pairs for its duration only.

    Works as both a synchronous ``with`` block and an asynchronous
    ``async with`` block.  The bound keys are unbound on exit regardless of
    whether an exception is raised.

    Parameters
    ----------
    propagate : list[str], optional
        Keys from ``**kw`` to also set as W3C OTel baggage.  When set, the
        named keys are attached to the current OTel context so they travel
        with every outgoing HTTP request (via ``instrument_httpx`` or any
        other OTel propagator).  Values are coerced to ``str``.  The baggage
        is detached on exit.  Keys not present in ``**kw`` are silently
        ignored.
    **kw : Any
        Key/value pairs to bind for the duration of the block.

    Examples
    --------
    Async (typical use in a request handler or use-case):

    >>> async with scoped_context(company_id="acme", schema="acme_db"):
    ...     await repo.create_record(data)
    ... # company_id and schema are removed here

    Async with W3C baggage propagation (multi-tenant services):

    >>> async with scoped_context(company_id=str(dto.company_id), propagate=["company_id"]):
    ...     result = await self._execute(dto)
    ... # company_id in logs AND in baggage — no need for separate set_baggage calls

    Sync (background tasks, CLI commands):

    >>> with scoped_context(job_id="batch-42"):
    ...     process_batch()

    Notes
    -----
    Only the keys passed to the constructor are unbound on exit.  Any
    keys bound *inside* the block via :func:`bind_context` are left in
    place — they were added by the caller's own code and are that
    caller's responsibility.
    """

    __slots__ = ("_kw", "_propagate", "_otel_token")

    def __init__(self, propagate: list[str] | None = None, **kw: Any) -> None:
        self._kw = kw
        self._propagate = propagate
        self._otel_token: Any = None

    # ------------------------------------------------------------------
    # Synchronous protocol
    # ------------------------------------------------------------------

    def __enter__(self) -> scoped_context:
        bind_contextvars(**self._kw)
        if self._propagate:
            self._otel_token = _try_attach_baggage(self._propagate, self._kw)
        return self

    def __exit__(self, *_: object) -> None:
        unbind_contextvars(*self._kw.keys())
        if self._otel_token is not None:
            _try_detach_baggage(self._otel_token)
            self._otel_token = None

    # ------------------------------------------------------------------
    # Asynchronous protocol
    # ------------------------------------------------------------------

    async def __aenter__(self) -> scoped_context:
        bind_contextvars(**self._kw)
        if self._propagate:
            self._otel_token = _try_attach_baggage(self._propagate, self._kw)
        return self

    async def __aexit__(self, *_: object) -> None:
        unbind_contextvars(*self._kw.keys())
        if self._otel_token is not None:
            _try_detach_baggage(self._otel_token)
            self._otel_token = None


def bind_context(**kw: Any) -> None:
    """Add key/value pairs to the current structured log context.

    Parameters
    ----------
    **kw : Any
        Key/value pairs to merge into the context.

    Example
    -------
    >>> from obskit.logging.context import bind_context
    >>> bind_context(company_id="acme", region="eu-west-1")
    """
    bind_contextvars(**kw)


def unbind_context(*keys: str) -> None:
    """Remove specific keys from the current structured log context.

    Parameters
    ----------
    *keys : str
        Names of the keys to remove.

    Example
    -------
    >>> from obskit.logging.context import unbind_context
    >>> unbind_context("company_id", "region")
    """
    unbind_contextvars(*keys)


def clear_context() -> None:
    """Remove **all** keys from the current structured log context.

    Call this at the start of each request to ensure a clean slate.

    Example
    -------
    >>> from obskit.logging.context import clear_context
    >>> clear_context()
    """
    clear_contextvars()


def get_context() -> dict[str, Any]:
    """Return a snapshot of the current structured log context.

    Returns
    -------
    dict[str, Any]
        A copy of all currently bound key/value pairs.

    Example
    -------
    >>> from obskit.logging.context import get_context
    >>> ctx = get_context()
    >>> ctx.get("company_id")
    """
    return get_contextvars()


def reset_context() -> None:
    """Reset all context vars to their initial (unbound) state.

    Equivalent to :func:`clear_context`; provided as a complementary name
    for code that models context management as a "reset to baseline" operation.
    Prefer :func:`clear_context` for request-lifecycle teardown.
    """
    clear_contextvars()


__all__ = [
    "bind_context",
    "unbind_context",
    "clear_context",
    "get_context",
    "reset_context",
    "scoped_context",
]
