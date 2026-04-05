"""
Thread Context Propagation
==========================

Provides a drop-in :class:`threading.Thread` replacement that automatically
copies the current structlog context-vars and OpenTelemetry trace context into
every child thread.

Without this, threads created from an async request handler (e.g. via
:func:`asyncio.get_event_loop().run_in_executor`) run with a blank log context
— ``request_id``, ``company_id``, and active trace spans are all lost.

Usage
-----
Call :func:`patch_threading` **once** at application startup — typically inside
:func:`~obskit.config.configure_observability`::

    from obskit import configure_observability
    configure_observability(service_name="my-api", patch_threads=True)

Or manually::

    from obskit.threading import patch_threading
    patch_threading()

After patching, any ``threading.Thread(target=...)`` inherits the caller's log
context and OTel span automatically.

Reverting
---------
:func:`reset_threading_patch` restores the original ``threading.Thread`` class.
Intended for test teardown only — do not call in production.
"""

from __future__ import annotations

import threading
from typing import Any

from structlog.contextvars import (
    bind_contextvars,
    clear_contextvars,
    get_contextvars,
)

# Save the unpatched class at import time so reset_threading_patch() can
# restore it even after multiple patch() / reset() cycles.
_original_thread: type[threading.Thread] = threading.Thread
_patched: bool = False


class _ContextThread(threading.Thread):
    """threading.Thread subclass that propagates observability context.

    Captures the structlog context-vars and (if opentelemetry is installed)
    the OTel context in :meth:`start`, then restores them inside :meth:`run`
    before the thread target executes.
    """

    # Slots avoid per-instance dict overhead; the two attributes are set
    # exclusively by start() before run() is called.
    __slots__ = ("_obskit_log_ctx", "_obskit_otel_ctx")

    def start(self) -> None:
        # Capture structlog context before the parent thread continues.
        self._obskit_log_ctx: dict[str, Any] = get_contextvars()

        # Capture OTel context when the SDK is installed; skip otherwise.
        try:
            from opentelemetry import context as _otel_ctx  # noqa: PLC0415

            self._obskit_otel_ctx: Any = _otel_ctx.get_current()
        except ImportError:
            self._obskit_otel_ctx = None

        super().start()

    def run(self) -> None:
        # Restore structlog context into this thread's context-var storage.
        clear_contextvars()
        if self._obskit_log_ctx:
            bind_contextvars(**self._obskit_log_ctx)

        # Restore OTel context; detach unconditionally in the finally block.
        _otel_token: Any = None
        if self._obskit_otel_ctx is not None:
            try:
                from opentelemetry import context as _otel_ctx  # noqa: PLC0415

                _otel_token = _otel_ctx.attach(self._obskit_otel_ctx)
            except ImportError:  # pragma: no cover
                pass

        try:
            super().run()
        finally:
            if _otel_token is not None:
                try:
                    from opentelemetry import context as _otel_ctx  # noqa: PLC0415

                    _otel_ctx.detach(_otel_token)
                except ImportError:  # pragma: no cover
                    pass


def patch_threading() -> None:
    """Replace ``threading.Thread`` with a context-propagating subclass.

    Idempotent — safe to call multiple times.  After calling this function,
    every new ``threading.Thread`` instance will automatically inherit the
    caller's structlog context and OpenTelemetry trace context.

    Example
    -------
    >>> from obskit.threading import patch_threading
    >>> patch_threading()
    >>> import threading
    >>> assert threading.Thread is _ContextThread
    """
    global _patched
    if _patched:
        return
    threading.Thread = _ContextThread  # type: ignore[misc]
    _patched = True


def reset_threading_patch() -> None:
    """Restore the original ``threading.Thread`` class.

    Intended for **test teardown only**.  Do not call in production — it will
    break context propagation for any threads started after the reset.
    """
    global _patched
    threading.Thread = _original_thread
    _patched = False


__all__ = [
    "patch_threading",
    "reset_threading_patch",
    "_ContextThread",
]
