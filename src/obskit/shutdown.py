"""
Graceful Shutdown Management for obskit
========================================

This module provides graceful shutdown functionality for obskit components.
It handles signal registration, cleanup hooks, and resource shutdown.

Example - Basic Usage
---------------------
.. code-block:: python

    from obskit import shutdown

    # At application startup
    # Signal handlers are automatically registered

    # During shutdown (or call shutdown() explicitly)
    shutdown()

Example - Custom Shutdown Hooks
-------------------------------
.. code-block:: python

    from obskit.shutdown import register_shutdown_hook

    def cleanup_database():
        db.close_connections()

    register_shutdown_hook(cleanup_database)

    # shutdown() will call cleanup_database() automatically

Example - FastAPI Integration
-----------------------------
.. code-block:: python

    from fastapi import FastAPI
    from obskit import shutdown

    app = FastAPI()

    @app.on_event("shutdown")
    async def shutdown_event():
        shutdown()
"""

from __future__ import annotations

import atexit
import signal
import sys
import threading
from collections.abc import Callable

from obskit.logging import get_logger

logger = get_logger("obskit.shutdown")

# Shutdown hooks registry
_shutdown_hooks: list[Callable[[], None]] = []
_shutdown_hooks_lock = threading.Lock()
_shutdown_in_progress = False
_shutdown_lock = threading.Lock()


def register_shutdown_hook(hook: Callable[[], None]) -> None:
    """
    Register a function to be called during shutdown.

    Shutdown hooks are called in the order they were registered.
    If a hook raises an exception, it is logged but does not stop
    other hooks from executing.

    Parameters
    ----------
    hook : Callable[[], None]
        Function to call during shutdown. Should not take any arguments.

    Example
    -------
    >>> from obskit.shutdown import register_shutdown_hook

    >>> def cleanup_resources():
    ...     # Close connections, flush buffers, etc.
    ...     pass

    >>> register_shutdown_hook(cleanup_resources)

    Notes
    -----
    - Hooks are called synchronously during shutdown
    - Hooks should be idempotent (safe to call multiple times)
    - Hooks should complete quickly (avoid long-running operations)
    """
    with _shutdown_hooks_lock:
        _shutdown_hooks.append(hook)


def unregister_shutdown_hook(hook: Callable[[], None]) -> None:
    """
    Unregister a shutdown hook.

    Parameters
    ----------
    hook : Callable[[], None]
        The hook function to remove.
    """
    with _shutdown_hooks_lock:
        if hook in _shutdown_hooks:
            _shutdown_hooks.remove(hook)


def shutdown() -> None:
    """
    Gracefully shutdown all obskit components.

    This function:
    1. Stops the metrics HTTP server
    2. Shuts down tracing and flushes pending spans
    3. Calls all registered shutdown hooks
    4. Cleans up resources

    This function is idempotent - it's safe to call multiple times.

    Example
    -------
    >>> from obskit import shutdown
    >>>
    >>> # During application shutdown
    >>> shutdown()

    Notes
    -----
    - This function is thread-safe
    - It's automatically called on SIGTERM and SIGINT
    - It's registered with atexit for cleanup on normal exit
    """
    global _shutdown_in_progress

    with _shutdown_lock:
        # Check if shutdown is already in progress (read _shutdown_in_progress)
        if _shutdown_in_progress:
            logger.debug("shutdown_already_in_progress")
            return

        # Mark shutdown as in progress (write _shutdown_in_progress)
        _shutdown_in_progress = True
        logger.info("shutdown_started")

    try:
        # Stop metrics HTTP server
        try:
            from obskit.metrics.registry import stop_http_server

            stop_http_server()
            logger.debug("metrics_server_stopped")
        except Exception as e:
            logger.error(
                "metrics_server_stop_failed",
                error=str(e),
                error_type=type(e).__name__,
            )

        # Shutdown tracing
        try:
            from obskit.tracing.tracer import shutdown_tracing

            shutdown_tracing()
            logger.debug("tracing_shutdown_complete")
        except Exception as e:
            logger.error(
                "tracing_shutdown_failed",
                error=str(e),
                error_type=type(e).__name__,
            )

        # Shutdown async metric recording
        try:
            import asyncio

            from obskit.metrics.async_recording import shutdown_async_recording

            # Try to shutdown async recording if event loop exists
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Schedule shutdown (fire and forget)
                    try:  # pragma: no cover
                        asyncio.create_task(shutdown_async_recording())
                    except RuntimeError:  # pragma: no cover
                        # Can't create task, skip
                        pass
                else:
                    loop.run_until_complete(shutdown_async_recording())
            except RuntimeError:  # pragma: no cover
                # No event loop, skip
                pass

            logger.debug("async_metrics_shutdown_complete")
        except Exception as e:
            logger.error(
                "async_metrics_shutdown_failed",
                error=str(e),
                error_type=type(e).__name__,
            )

        # Call registered shutdown hooks
        with _shutdown_hooks_lock:
            hooks = list(_shutdown_hooks)

        for hook in hooks:
            try:
                hook()
                logger.debug("shutdown_hook_executed", hook=hook.__name__)
            except Exception as e:
                logger.error(
                    "shutdown_hook_failed",
                    hook=hook.__name__,
                    error=str(e),
                    error_type=type(e).__name__,
                )

        logger.info("shutdown_complete")

    except Exception as e:
        logger.error(
            "shutdown_error",
            error=str(e),
            error_type=type(e).__name__,
        )
        raise


def _signal_handler(signum: int, frame: object) -> None:
    """
    Signal handler for SIGTERM and SIGINT.

    This handler calls shutdown() and then exits the process.
    Note: During pytest runs, signal handlers are not registered,
    so this function should not be called in test environments.
    """
    logger.info("signal_received", signal=signum)
    shutdown()
    sys.exit(0)


def _setup_signal_handlers() -> None:
    """Setup signal handlers for graceful shutdown."""
    # Don't register signal handlers during pytest runs
    # This prevents interference with pytest's own signal handling
    if "pytest" in sys.modules:
        return

    try:
        # Register handlers for termination signals
        signal.signal(signal.SIGTERM, _signal_handler)
        signal.signal(signal.SIGINT, _signal_handler)

        # Register atexit handler for normal exit
        atexit.register(shutdown)

        logger.debug("signal_handlers_registered")
    except Exception as e:
        logger.warning(
            "signal_handler_setup_failed",
            error=str(e),
            error_type=type(e).__name__,
        )


# Automatically setup signal handlers when module is imported
_setup_signal_handlers()
