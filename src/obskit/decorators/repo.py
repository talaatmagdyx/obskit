"""
Repository Instrumentation Decorator
======================================

Auto-wrap all public async methods of a repository class with OTel trace spans
so every DB operation is visible in distributed traces without boilerplate.

Usage
-----
::

    from obskit import instrument_repo

    @instrument_repo(component="postgres")
    class NotesRepo:
        async def insert_note(self, title: str, body: str) -> None:
            ...

        async def get_notes(self, limit: int = 100) -> list[dict]:
            ...
    # Each method call creates a span:
    #   "NotesRepo.insert_note" (component="postgres")
    #   "NotesRepo.get_notes"   (component="postgres")
"""

from __future__ import annotations

import asyncio
import functools
import time
from collections.abc import Callable
from typing import Any


def instrument_repo(
    *,
    component: str = "db",
    span_prefix: str | None = None,
    slow_threshold_ms: float | None = None,
) -> Callable[[type], type]:
    """Class decorator that wraps all public async methods with OTel trace spans.

    Parameters
    ----------
    component : str
        Span ``component`` attribute, e.g. ``"postgres"``, ``"redis"``,
        ``"mongo"``.  Default: ``"db"``.
    span_prefix : str, optional
        Prefix for span names.  If *None*, the decorated class name is used.
        Span name format: ``"{prefix}.{method_name}"``.

    Returns
    -------
    callable
        Class decorator.

    Example
    -------
    ::

        @instrument_repo(component="postgres")
        class TagsRepo:
            async def upsert_tags(self, entity_id: int, tags: list[str]) -> None:
                ...
            async def delete_tags(self, entity_id: int) -> None:
                ...
        # Spans: "TagsRepo.upsert_tags", "TagsRepo.delete_tags"

    Notes
    -----
    Only **public async** methods (names not starting with ``_``) defined
    *directly* on the class are wrapped.  Static methods, class methods,
    and synchronous methods are left untouched.
    Span attributes are set on the OTel span: ``component=<component>``.
    slow_threshold_ms : float, optional
        If set, emit a ``slow_repo_operation`` warning log for any method call
        whose wall-clock duration exceeds this threshold (in milliseconds).
    """

    def decorator(cls: type) -> type:
        prefix = span_prefix if span_prefix is not None else cls.__name__

        for attr_name, value in vars(cls).items():
            if attr_name.startswith("_"):
                continue
            # Skip staticmethod / classmethod descriptor objects
            if isinstance(value, (staticmethod, classmethod)):
                continue
            if not asyncio.iscoroutinefunction(value):
                continue

            span_name = f"{prefix}.{attr_name}"
            _component = component
            _threshold_ms = slow_threshold_ms

            @functools.wraps(value)
            async def _wrapped(
                *args: Any,
                _fn: Any = value,
                _span: str = span_name,
                _comp: str = _component,
                _thr: float | None = _threshold_ms,
                **kwargs: Any,
            ) -> Any:
                from obskit.tracing.tracer import async_trace_span  # noqa: PLC0415

                t0 = time.monotonic()
                try:
                    async with async_trace_span(_span, component=_comp):
                        return await _fn(*args, **kwargs)
                finally:
                    if _thr is not None:
                        elapsed_ms = (time.monotonic() - t0) * 1000.0
                        if elapsed_ms > _thr:
                            from obskit.logging.logger import get_logger  # noqa: PLC0415

                            get_logger().warning(
                                "slow_repo_operation",
                                operation=_span,
                                duration_ms=round(elapsed_ms, 2),
                                threshold_ms=_thr,
                            )

            setattr(cls, attr_name, _wrapped)

        return cls

    return decorator


__all__ = ["instrument_repo"]
