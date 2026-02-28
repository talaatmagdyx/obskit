"""
Batch Job Context Propagation
=============================

This module provides context propagation utilities for batch jobs,
background tasks, and worker processes.

The Problem
-----------
When running batch jobs or background tasks, the correlation context
from the original request is lost. This module provides utilities to:

1. Capture context before spawning a task
2. Restore context when the task runs
3. Create new context for standalone batch jobs

Example - Background Task
-------------------------
.. code-block:: python

    from obskit.core.batch_context import capture_context, restore_context
    import asyncio

    async def process_order(order_id: str):
        # Capture current context
        ctx = capture_context()

        # Spawn background task
        asyncio.create_task(
            background_process(order_id, ctx)
        )

    async def background_process(order_id: str, ctx: dict):
        # Restore context in background task
        with restore_context(ctx):
            # Now correlation_id and trace context are available
            logger.info("Processing order", order_id=order_id)

Example - Batch Job
-------------------
.. code-block:: python

    from obskit.core.batch_context import batch_job_context

    async def run_daily_report():
        # Create a new context for the batch job
        async with batch_job_context(job_name="daily_report"):
            # All code here has a unique correlation ID
            await generate_report()
            await send_report()

Example - Worker Pool
---------------------
.. code-block:: python

    from obskit.core.batch_context import propagate_to_executor
    from concurrent.futures import ThreadPoolExecutor

    executor = ThreadPoolExecutor(max_workers=4)

    @propagate_to_executor(executor)
    def process_item(item):
        # Context is automatically propagated
        logger.info("Processing item", item_id=item.id)
        return process(item)
"""

from __future__ import annotations

import asyncio
import functools
import uuid
from collections.abc import AsyncGenerator, Awaitable, Callable, Generator
from concurrent.futures import Executor
from contextlib import asynccontextmanager, contextmanager
from contextvars import ContextVar, copy_context
from datetime import UTC, datetime
from typing import Any, ParamSpec, TypeVar

from obskit.core.context import get_correlation_id, set_correlation_id


# Use lazy import to avoid circular dependency
def _get_logger() -> Any:
    from obskit.logging import get_logger

    return get_logger("obskit.core.batch_context")


P = ParamSpec("P")
T = TypeVar("T")

# Context variable for batch job metadata
_batch_job_context: ContextVar[dict[str, Any] | None] = ContextVar(
    "batch_job_context", default=None
)


def capture_context() -> dict[str, Any]:
    """
    Capture the current observability context for propagation.

    This function captures all relevant context that should be
    propagated to background tasks or worker threads.

    Returns
    -------
    dict[str, Any]
        Dictionary containing captured context.

    Example
    -------
    >>> from obskit.core.batch_context import capture_context
    >>>
    >>> # In main request handler
    >>> ctx = capture_context()
    >>>
    >>> # Pass to background task
    >>> asyncio.create_task(background_task(data, ctx))
    """
    context: dict[str, Any] = {
        "correlation_id": get_correlation_id(),
        "captured_at": datetime.now(UTC).isoformat(),
    }

    # Capture batch job context if present
    batch_ctx = _batch_job_context.get()
    if batch_ctx:
        context["batch_job"] = batch_ctx.copy()

    # Capture trace context if available
    try:
        from obskit.tracing.tracer import inject_trace_context

        trace_headers: dict[str, str] = {}
        inject_trace_context(trace_headers)
        if trace_headers:
            context["trace_headers"] = trace_headers
    except Exception:  # pragma: no cover  # nosec B110 - intentional: tracing is optional
        pass  # Tracing may not be configured - this is expected

    return context


@contextmanager
def restore_context(ctx: dict[str, Any]) -> Generator[None, None, None]:
    """
    Restore a previously captured context.

    Parameters
    ----------
    ctx : dict[str, Any]
        Context dictionary from capture_context().

    Yields
    ------
    None

    Example
    -------
    >>> from obskit.core.batch_context import capture_context, restore_context
    >>>
    >>> def background_task(data: dict, ctx: dict):
    ...     with restore_context(ctx):
    ...         # correlation_id is now available
    ...         process_data(data)
    """
    # Restore correlation ID
    old_correlation_id = get_correlation_id()
    if ctx.get("correlation_id"):
        set_correlation_id(ctx["correlation_id"])

    # Restore batch job context
    old_batch_ctx = _batch_job_context.get()
    if ctx.get("batch_job"):
        _batch_job_context.set(ctx["batch_job"])

    try:
        yield
    finally:
        # Restore previous values
        if old_correlation_id:
            set_correlation_id(old_correlation_id)
        _batch_job_context.set(old_batch_ctx)


@asynccontextmanager
async def batch_job_context(
    job_name: str,
    job_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> AsyncGenerator[dict[str, Any], None]:
    """
    Create a new context for a batch job.

    This context manager sets up correlation ID and job metadata
    for batch jobs that don't have an incoming request context.

    Parameters
    ----------
    job_name : str
        Name of the batch job.
    job_id : str, optional
        Unique ID for this job run. Auto-generated if not provided.
    metadata : dict, optional
        Additional metadata for the job.

    Yields
    ------
    dict[str, Any]
        The job context dictionary.

    Example
    -------
    >>> from obskit.core.batch_context import batch_job_context
    >>>
    >>> async def run_nightly_sync():
    ...     async with batch_job_context(
    ...         job_name="nightly_sync",
    ...         metadata={"source": "warehouse"},
    ...     ) as ctx:
    ...         logger.info("Starting sync", job_id=ctx["job_id"])
    ...         await sync_data()
    """
    job_id = job_id or str(uuid.uuid4())
    correlation_id = f"batch:{job_name}:{job_id[:8]}"

    job_ctx: dict[str, Any] = {
        "job_name": job_name,
        "job_id": job_id,
        "started_at": datetime.now(UTC).isoformat(),
        "correlation_id": correlation_id,
        **(metadata or {}),
    }

    # Set context
    set_correlation_id(correlation_id)
    old_batch_ctx = _batch_job_context.get()
    _batch_job_context.set(job_ctx)

    logger = _get_logger()
    logger.info(
        "batch_job_started",
        job_name=job_name,
        job_id=job_id,
        correlation_id=correlation_id,
    )

    try:
        yield job_ctx

        # Log completion
        duration = (
            datetime.now(UTC) - datetime.fromisoformat(job_ctx["started_at"])
        ).total_seconds()

        _get_logger().info(
            "batch_job_completed",
            job_name=job_name,
            job_id=job_id,
            duration_seconds=round(duration, 2),
            status="success",
        )

    except Exception as e:
        # Log failure
        duration = (
            datetime.now(UTC) - datetime.fromisoformat(job_ctx["started_at"])
        ).total_seconds()

        _get_logger().error(
            "batch_job_failed",
            job_name=job_name,
            job_id=job_id,
            duration_seconds=round(duration, 2),
            status="failure",
            error=str(e),
            error_type=type(e).__name__,
        )
        raise

    finally:
        _batch_job_context.set(old_batch_ctx)


def get_batch_job_context() -> dict[str, Any] | None:
    """
    Get the current batch job context.

    Returns
    -------
    dict[str, Any] | None
        Current batch job context or None if not in a batch job.
    """
    return _batch_job_context.get()


def propagate_to_executor(
    executor: Executor,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """
    Decorator to propagate context to executor-submitted functions.

    Parameters
    ----------
    executor : Executor
        The executor to submit tasks to.

    Returns
    -------
    Callable
        Decorator that wraps functions with context propagation.

    Example
    -------
    >>> from concurrent.futures import ThreadPoolExecutor
    >>> from obskit.core.batch_context import propagate_to_executor
    >>>
    >>> executor = ThreadPoolExecutor(max_workers=4)
    >>>
    >>> @propagate_to_executor(executor)
    ... def process_item(item):
    ...     # Context is automatically propagated
    ...     return process(item)
    >>>
    >>> # Submit with context
    >>> future = process_item(item)
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            # Capture current context
            ctx = capture_context()
            context = copy_context()

            def run_with_context() -> T:
                with restore_context(ctx):
                    return func(*args, **kwargs)

            # Submit to executor with copied context
            future = executor.submit(context.run, run_with_context)
            return future.result()

        return wrapper

    return decorator


def propagate_to_task(
    func: Callable[P, Awaitable[T]],
) -> Callable[P, Awaitable[T]]:
    """
    Decorator to propagate context to async tasks.

    Parameters
    ----------
    func : Callable
        Async function to wrap.

    Returns
    -------
    Callable
        Wrapped function that propagates context.

    Example
    -------
    >>> from obskit.core.batch_context import propagate_to_task
    >>>
    >>> @propagate_to_task
    ... async def background_process(data: dict):
    ...     # Context from caller is available here
    ...     await process_data(data)
    >>>
    >>> # Create task - context is propagated
    >>> asyncio.create_task(background_process(data))
    """

    @functools.wraps(func)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        # Context is already propagated in asyncio
        return await func(*args, **kwargs)

    return wrapper


def create_task_with_context(
    coro: Awaitable[T],
    name: str | None = None,
) -> asyncio.Task[T]:
    """
    Create an asyncio task with context propagation.

    Parameters
    ----------
    coro : Awaitable[T]
        Coroutine to run.
    name : str, optional
        Name for the task.

    Returns
    -------
    asyncio.Task[T]
        The created task.

    Example
    -------
    >>> from obskit.core.batch_context import create_task_with_context
    >>>
    >>> async def main():
    ...     # Create task that preserves context
    ...     task = create_task_with_context(
    ...         process_order(order_id),
    ...         name="process_order",
    ...     )
    ...     await task
    """
    # Capture current context
    ctx = capture_context()

    async def wrapped() -> T:
        with restore_context(ctx):
            return await coro

    return asyncio.create_task(wrapped(), name=name)


__all__ = [
    "capture_context",
    "restore_context",
    "batch_job_context",
    "get_batch_job_context",
    "propagate_to_executor",
    "propagate_to_task",
    "create_task_with_context",
]
