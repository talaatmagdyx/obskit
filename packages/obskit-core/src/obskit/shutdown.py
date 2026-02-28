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

Example - GracefulShutdown Class
--------------------------------
.. code-block:: python

    from obskit.shutdown import GracefulShutdown

    # Create shutdown manager
    shutdown_manager = GracefulShutdown(timeout=30)

    # Register cleanup tasks
    shutdown_manager.register(push_metrics_to_gateway)
    shutdown_manager.register(close_database_connections)
    shutdown_manager.register(stop_consuming_messages)

    # Wait for completion (blocks until shutdown signal or timeout)
    # This is useful for long-running services
    shutdown_manager.wait_for_completion()

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


class GracefulShutdown:
    """
    A class-based shutdown manager with enhanced features.

    Provides:
    - Ordered hook execution with priorities
    - Timeout support for long-running cleanup
    - Wait-for-completion blocking
    - Multiple shutdown signals support
    - Shutdown state tracking

    Example
    -------
    >>> from obskit.shutdown import GracefulShutdown
    >>>
    >>> # Create shutdown manager
    >>> shutdown_mgr = GracefulShutdown(timeout=30)
    >>>
    >>> # Register cleanup tasks with priorities (lower = earlier)
    >>> shutdown_mgr.register(flush_metrics, priority=10)
    >>> shutdown_mgr.register(close_connections, priority=20)
    >>> shutdown_mgr.register(cleanup_temp_files, priority=30)
    >>>
    >>> # In your main loop, wait for shutdown
    >>> shutdown_mgr.wait_for_completion()
    """

    def __init__(
        self,
        timeout: float = 30.0,
        exit_code: int = 0,
        auto_exit: bool = True,
    ):
        """
        Initialize graceful shutdown manager.

        Parameters
        ----------
        timeout : float
            Maximum seconds to wait for hooks to complete (default: 30).
        exit_code : int
            Exit code to use on normal shutdown (default: 0).
        auto_exit : bool
            Whether to call sys.exit() after shutdown (default: True).
        """
        self.timeout = timeout
        self.exit_code = exit_code
        self.auto_exit = auto_exit

        self._hooks: list[tuple[int, str, Callable[[], None]]] = []
        self._hooks_lock = threading.Lock()
        self._shutdown_event = threading.Event()
        self._shutdown_complete = threading.Event()
        self._shutdown_count = 0
        self._is_shutting_down = False

        # Register our signal handlers
        self._original_sigterm = None
        self._original_sigint = None
        self._setup_signals()

    def _setup_signals(self):
        """Setup signal handlers."""
        if "pytest" in sys.modules:
            return

        try:
            self._original_sigterm = signal.signal(signal.SIGTERM, self._signal_handler)
            self._original_sigint = signal.signal(signal.SIGINT, self._signal_handler)
            logger.debug("graceful_shutdown_signals_registered")
        except Exception as e:
            logger.warning("signal_setup_failed", error=str(e))

    def _signal_handler(self, signum: int, frame: object):
        """Handle shutdown signals."""
        self._shutdown_count += 1

        logger.info(
            "shutdown_signal_received",
            signal=signum,
            count=self._shutdown_count,
        )

        if self._shutdown_count == 1:
            # First signal - graceful shutdown
            self._shutdown_event.set()
            self._initiate_shutdown()
        elif self._shutdown_count >= 3:
            # Third signal - force exit
            logger.warning("force_shutdown", signal_count=self._shutdown_count)
            sys.exit(1)

    def register(
        self,
        hook: Callable[[], None],
        priority: int = 50,
        name: str | None = None,
    ) -> None:
        """
        Register a shutdown hook with priority.

        Parameters
        ----------
        hook : Callable
            Function to call during shutdown.
        priority : int
            Execution priority (lower = earlier, default: 50).
        name : str, optional
            Hook name for logging (defaults to function name).

        Example
        -------
        >>> shutdown_mgr.register(flush_metrics, priority=10, name="metrics")
        >>> shutdown_mgr.register(close_db, priority=20, name="database")
        """
        hook_name = name or getattr(hook, "__name__", "unknown")

        with self._hooks_lock:
            self._hooks.append((priority, hook_name, hook))
            # Keep sorted by priority
            self._hooks.sort(key=lambda x: x[0])

        logger.debug("shutdown_hook_registered", name=hook_name, priority=priority)

    def unregister(self, hook: Callable[[], None]) -> bool:
        """
        Unregister a shutdown hook.

        Parameters
        ----------
        hook : Callable
            The hook function to remove.

        Returns
        -------
        bool
            True if removed, False if not found.
        """
        with self._hooks_lock:
            for i, (_, _, h) in enumerate(self._hooks):
                if h == hook:
                    self._hooks.pop(i)
                    return True
        return False

    def _initiate_shutdown(self):
        """Execute shutdown sequence."""
        if self._is_shutting_down:
            return

        self._is_shutting_down = True
        logger.info("graceful_shutdown_initiated", timeout=self.timeout)

        # Run in a thread to not block signal handler
        shutdown_thread = threading.Thread(target=self._run_shutdown)
        shutdown_thread.daemon = True
        shutdown_thread.start()

        # Wait for completion with timeout
        shutdown_thread.join(timeout=self.timeout)

        if shutdown_thread.is_alive():
            logger.warning("shutdown_timeout_exceeded", timeout=self.timeout)

        self._shutdown_complete.set()

        # Also run global obskit shutdown
        shutdown()

        logger.info("graceful_shutdown_complete")

        if self.auto_exit:
            sys.exit(self.exit_code)

    def _run_shutdown(self):
        """Execute all hooks in priority order."""
        with self._hooks_lock:
            hooks = list(self._hooks)

        for priority, name, hook in hooks:
            try:
                logger.debug("executing_shutdown_hook", name=name, priority=priority)
                hook()
                logger.debug("shutdown_hook_completed", name=name)
            except Exception as e:
                logger.error(
                    "shutdown_hook_failed",
                    name=name,
                    error=str(e),
                    error_type=type(e).__name__,
                )

    def wait_for_completion(self, timeout: float | None = None):
        """
        Block until shutdown is triggered and complete.

        This is useful for long-running services.

        Parameters
        ----------
        timeout : float, optional
            Maximum seconds to wait (None = wait forever).

        Example
        -------
        >>> # In main()
        >>> shutdown_mgr = GracefulShutdown()
        >>> shutdown_mgr.register(cleanup_resources)
        >>>
        >>> # Start your service (non-blocking)
        >>> start_message_consumer()
        >>>
        >>> # Block until SIGTERM/SIGINT
        >>> shutdown_mgr.wait_for_completion()
        """
        logger.info("waiting_for_shutdown_signal")
        self._shutdown_event.wait(timeout=timeout)

        # If shutdown was triggered, wait for it to complete
        if self._is_shutting_down:
            self._shutdown_complete.wait(timeout=self.timeout)

    def trigger(self):
        """
        Manually trigger shutdown.

        Useful for testing or programmatic shutdown.
        """
        logger.info("manual_shutdown_triggered")
        self._shutdown_event.set()
        self._initiate_shutdown()

    @property
    def is_shutting_down(self) -> bool:
        """Check if shutdown is in progress."""
        return self._is_shutting_down

    @property
    def is_complete(self) -> bool:
        """Check if shutdown is complete."""
        return self._shutdown_complete.is_set()


# Global instance for convenience
_graceful_shutdown: GracefulShutdown | None = None


def get_graceful_shutdown(
    timeout: float = 30.0,
    exit_code: int = 0,
    auto_exit: bool = True,
) -> GracefulShutdown:
    """
    Get or create the global GracefulShutdown instance.

    Parameters
    ----------
    timeout : float
        Shutdown timeout in seconds.
    exit_code : int
        Exit code on normal shutdown.
    auto_exit : bool
        Whether to exit after shutdown.

    Returns
    -------
    GracefulShutdown
        The global shutdown manager instance.
    """
    global _graceful_shutdown

    if _graceful_shutdown is None:
        _graceful_shutdown = GracefulShutdown(
            timeout=timeout,
            exit_code=exit_code,
            auto_exit=auto_exit,
        )

    return _graceful_shutdown


__all__ = [
    "shutdown",
    "register_shutdown_hook",
    "unregister_shutdown_hook",
    "GracefulShutdown",
    "get_graceful_shutdown",
]
