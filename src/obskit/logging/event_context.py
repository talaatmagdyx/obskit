"""
Event Handler Context Decorator
=================================

Bind structlog context-vars for the duration of an async event handler so that
every log line inside the handler automatically includes the correct tenant
context (``company_id``, ``company_schema``, …) without manual bookkeeping.

Usage
-----
::

    from obskit import with_event_context

    @with_event_context(lambda event: {
        "company_id": str(event.get("company_id", "")),
        "company_schema": event.get("company_schema", ""),
    })
    async def handle(self, event: dict) -> None:
        logger.info("processing event")  # includes company_id, company_schema
        ...
"""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any

from structlog.contextvars import bind_contextvars, unbind_contextvars


def with_event_context(
    extractor: Callable[[dict[str, Any]], dict[str, Any] | None],
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator factory that binds structlog context-vars for an async handler.

    Extracts context keys from the event dict using *extractor*, binds them
    for the duration of the handler call, and unbinds them automatically on
    exit — whether the handler returns normally or raises an exception.

    Parameters
    ----------
    extractor : callable
        A callable ``(event: dict) → dict | None`` that maps the incoming
        event to a set of structlog context-var bindings.  Return ``{}`` or
        ``None`` to skip binding (e.g. when the event lacks a required field).

    Returns
    -------
    callable
        Decorator that wraps async handler functions.

    Example
    -------
    ::

        @with_event_context(lambda event: {
            "company_id": str(event.get("company_id", "")),
            "company_schema": event.get("company_schema", ""),
        })
        async def handle(self, event: dict) -> None:
            ...

    Notes
    -----
    The decorator locates the event dict by searching positional arguments for
    the first :class:`dict` instance (skipping ``self`` which is typically a
    class instance), then falls back to a keyword argument named ``"event"``.

    Keys bound *inside* the handler via :func:`obskit.logging.context.bind_context`
    are **not** removed on exit — they are the caller's responsibility.
    """

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Locate the event dict:
            # • For `async def handle(self, event)` — first dict in positional args
            # • For `async def handle(event)` — also first dict in positional args
            # • Fall back to kwarg named "event"
            event: dict[str, Any] = {}
            for arg in args:
                if isinstance(arg, dict):
                    event = arg
                    break
            if not event:
                event = kwargs.get("event") or {}

            ctx = extractor(event) or {}
            if ctx:
                bind_contextvars(**ctx)
            try:
                return await fn(*args, **kwargs)
            finally:
                if ctx:
                    unbind_contextvars(*ctx.keys())

        return wrapper

    return decorator


__all__ = ["with_event_context"]
