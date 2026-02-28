"""
Context Propagation for Correlation IDs
========================================

This module provides thread-safe and async-safe context propagation for
correlation IDs using Python's contextvars module.

What is a Correlation ID?
-------------------------
A correlation ID is a unique identifier that links all logs, traces, and
metrics for a single request or operation. When debugging issues, you can
search for a correlation ID to find all related data.

Why contextvars?
----------------
Python's contextvars module provides:

1. **Thread safety**: Each thread has its own context
2. **Async safety**: Each asyncio task has its own context
3. **Copy-on-fork**: Context is properly copied when spawning tasks
4. **No explicit passing**: Functions don't need to pass IDs manually

How It Works
------------
.. code-block:: text

    Thread/Task 1          Thread/Task 2          Thread/Task 3
    ┌─────────────┐        ┌─────────────┐        ┌─────────────┐
    │ context:    │        │ context:    │        │ context:    │
    │  id=abc-123 │        │  id=def-456 │        │  id=ghi-789 │
    │             │        │             │        │             │
    │ get_id() →  │        │ get_id() →  │        │ get_id() →  │
    │  "abc-123"  │        │  "def-456"  │        │  "ghi-789"  │
    └─────────────┘        └─────────────┘        └─────────────┘

    Each execution context maintains its own correlation ID.
    No race conditions, no explicit passing needed.

Example - Basic Usage
---------------------
.. code-block:: python

    from obskit.core.context import (
        correlation_context,
        get_correlation_id,
        set_correlation_id,
    )

    # Auto-generated ID
    with correlation_context():
        print(get_correlation_id())  # "3f8a7b2c-1d4e-5f6g..."

    # Use provided ID
    with correlation_context("request-12345"):
        print(get_correlation_id())  # "request-12345"

    # Outside context
    print(get_correlation_id())  # None

Example - Async Usage
---------------------
.. code-block:: python

    import asyncio
    from obskit.core.context import async_correlation_context, get_correlation_id

    async def process_request():
        async with async_correlation_context():
            correlation_id = get_correlation_id()
            print(f"Processing with ID: {correlation_id}")

            # Spawn child tasks - they inherit the context
            await asyncio.gather(
                fetch_user_data(),
                fetch_order_data(),
            )

    async def fetch_user_data():
        # Same correlation ID as parent
        print(f"User data ID: {get_correlation_id()}")

    async def fetch_order_data():
        # Same correlation ID as parent
        print(f"Order data ID: {get_correlation_id()}")

Example - HTTP Middleware
-------------------------
.. code-block:: python

    from obskit.core.context import correlation_context, get_correlation_id

    async def correlation_middleware(request, call_next):
        '''Add correlation ID to each request.'''
        # Get ID from header or generate new one
        correlation_id = request.headers.get("X-Correlation-ID")

        async with correlation_context(correlation_id):
            # Process request with correlation context
            response = await call_next(request)

            # Add ID to response headers
            response.headers["X-Correlation-ID"] = get_correlation_id()
            return response

Example - Background Job Processing
-----------------------------------
.. code-block:: python

    from obskit.core.context import correlation_context, get_correlation_id
    from obskit import get_logger

    logger = get_logger(__name__)

    async def process_job(job_data: dict):
        '''Process a background job with correlation tracking.'''
        # Use job ID as correlation ID, or generate new one
        job_correlation_id = job_data.get("correlation_id")

        async with correlation_context(job_correlation_id):
            logger.info(
                "job_started",
                job_id=job_data["id"],
                job_type=job_data["type"],
            )

            try:
                result = await execute_job(job_data)
                logger.info("job_completed", result=result)
            except Exception as e:
                logger.error(
                    "job_failed",
                    error=str(e),
                    error_type=type(e).__name__,
                )
                raise
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator, Generator
from contextlib import asynccontextmanager, contextmanager
from contextvars import ContextVar, Token

# =============================================================================
# Context Variables
# =============================================================================

# The correlation ID context variable
# This is thread-safe and async-safe thanks to contextvars
_correlation_id: ContextVar[str | None] = ContextVar(
    "correlation_id",
    default=None,  # No correlation ID by default
)


# =============================================================================
# Public API - Get/Set Functions
# =============================================================================


def get_correlation_id() -> str | None:
    """
    Get the current correlation ID from the context.

    Returns the correlation ID for the current execution context
    (thread or asyncio task). Returns None if no correlation context
    has been established.

    Returns
    -------
    str or None
        The current correlation ID, or None if not set.

    Example
    -------
    >>> from obskit.core.context import get_correlation_id, correlation_context
    >>>
    >>> # Outside any context
    >>> print(get_correlation_id())  # None
    >>>
    >>> # Inside a correlation context
    >>> with correlation_context():
    ...     print(get_correlation_id())  # "3f8a7b2c-..."
    >>>
    >>> # Back outside
    >>> print(get_correlation_id())  # None

    Thread Safety
    -------------
    This function is thread-safe. Each thread maintains its own
    correlation ID context, so concurrent threads won't interfere.

    Async Safety
    ------------
    This function is async-safe. Each asyncio task maintains its own
    correlation ID context. Child tasks spawned with asyncio.create_task()
    or asyncio.gather() will inherit the parent's context.
    """
    return _correlation_id.get()


def set_correlation_id(correlation_id: str | None) -> Token[str | None]:
    """
    Set the correlation ID for the current context.

    This is a low-level function. Prefer using correlation_context()
    for automatic cleanup. Use this when you need to set a correlation
    ID without the context manager (e.g., in middleware setup).

    Parameters
    ----------
    correlation_id : str or None
        The correlation ID to set. Pass None to clear.

    Returns
    -------
    Token
        A token that can be used to restore the previous value.
        Call _correlation_id.reset(token) to restore.

    Example
    -------
    >>> from obskit.core.context import set_correlation_id, get_correlation_id
    >>>
    >>> # Set correlation ID
    >>> token = set_correlation_id("request-12345")
    >>> print(get_correlation_id())  # "request-12345"
    >>>
    >>> # Restore previous value
    >>> _correlation_id.reset(token)
    >>> print(get_correlation_id())  # None (or previous value)

    Warning
    -------
    If you use this function directly, you're responsible for cleanup.
    Use correlation_context() for automatic cleanup.
    """
    return _correlation_id.set(correlation_id)


# =============================================================================
# Context Managers
# =============================================================================


@contextmanager
def correlation_context(
    correlation_id: str | None = None,
) -> Generator[str, None, None]:
    """
    Context manager for establishing a correlation scope.

    Creates a scope where all code has access to a correlation ID.
    When the context exits, the previous correlation ID is restored.

    Parameters
    ----------
    correlation_id : str, optional
        A specific correlation ID to use. If not provided, a new
        UUID4 will be generated.

    Yields
    ------
    str
        The correlation ID for this context.

    Example - Auto-generated ID
    ---------------------------
    >>> from obskit.core.context import correlation_context, get_correlation_id
    >>>
    >>> with correlation_context() as cid:
    ...     print(f"Correlation ID: {cid}")
    ...     # All operations here share this ID
    ...     assert get_correlation_id() == cid
    >>>
    >>> # Outside context, ID is cleared
    >>> assert get_correlation_id() is None

    Example - Provided ID
    ---------------------
    >>> with correlation_context("my-custom-id-123") as cid:
    ...     print(f"Using provided ID: {cid}")
    ...     assert cid == "my-custom-id-123"

    Example - Nested Contexts
    -------------------------
    >>> with correlation_context("outer-id"):
    ...     print(f"Outer: {get_correlation_id()}")  # outer-id
    ...
    ...     with correlation_context("inner-id"):
    ...         print(f"Inner: {get_correlation_id()}")  # inner-id
    ...
    ...     # Back to outer
    ...     print(f"Outer again: {get_correlation_id()}")  # outer-id

    Example - Request Handling
    --------------------------
    >>> def handle_request(request):
    ...     '''Handle HTTP request with correlation tracking.'''
    ...     # Get client-provided ID or generate new one
    ...     client_id = request.headers.get("X-Correlation-ID")
    ...
    ...     with correlation_context(client_id):
    ...         logger.info("request_started", path=request.path)
    ...         result = process_request(request)
    ...         logger.info("request_completed")
    ...         return result

    Notes
    -----
    - The context is properly cleaned up even if an exception occurs
    - Nested contexts work correctly (inner scope uses inner ID)
    - Thread-safe: each thread has its own context
    """
    # Generate ID if not provided
    cid = correlation_id or str(uuid.uuid4())

    # Save current value and set new one
    token = _correlation_id.set(cid)

    try:
        # Yield the correlation ID to the caller
        yield cid
    finally:
        # Always restore the previous value
        _correlation_id.reset(token)


@asynccontextmanager
async def async_correlation_context(
    correlation_id: str | None = None,
) -> AsyncGenerator[str, None]:
    """
    Async context manager for establishing a correlation scope.

    This is the async version of correlation_context(). Use this in
    async functions to properly manage correlation IDs across await points.

    Parameters
    ----------
    correlation_id : str, optional
        A specific correlation ID to use. If not provided, a new
        UUID4 will be generated.

    Yields
    ------
    str
        The correlation ID for this context.

    Example - Async Request Handler
    -------------------------------
    >>> async def handle_request(request):
    ...     client_id = request.headers.get("X-Correlation-ID")
    ...
    ...     async with async_correlation_context(client_id) as cid:
    ...         logger.info("request_started")
    ...
    ...         # Async operations - context is preserved across awaits
    ...         user = await fetch_user(request.user_id)
    ...         order = await create_order(user, request.items)
    ...
    ...         # Even spawned tasks inherit the context
    ...         await asyncio.gather(
    ...             send_confirmation_email(user, order),
    ...             update_inventory(order),
    ...         )
    ...
    ...         return {"order_id": order.id}

    Example - Background Task
    -------------------------
    >>> async def process_background_job(job):
    ...     async with async_correlation_context(job.get("trace_id")):
    ...         logger.info("job_started", job_type=job["type"])
    ...         await execute_job(job)
    ...         logger.info("job_completed")

    Note on Task Inheritance
    ------------------------
    Child tasks created with asyncio.create_task() or asyncio.gather()
    will inherit the correlation context from the parent. This means
    you can spawn concurrent operations and they'll all share the
    same correlation ID.
    """
    # Generate ID if not provided
    cid = correlation_id or str(uuid.uuid4())

    # Save current value and set new one
    token = _correlation_id.set(cid)

    try:
        # Yield the correlation ID to the caller
        yield cid
    finally:
        # Always restore the previous value
        _correlation_id.reset(token)


# =============================================================================
# Utility Functions
# =============================================================================


def generate_correlation_id() -> str:
    """
    Generate a new correlation ID.

    Uses UUID4 for globally unique, random identifiers.

    Returns
    -------
    str
        A new UUID4 string.

    Example
    -------
    >>> from obskit.core.context import generate_correlation_id
    >>>
    >>> cid = generate_correlation_id()
    >>> print(cid)  # "3f8a7b2c-1d4e-5f6a-8b9c-0d1e2f3a4b5c"
    """
    return str(uuid.uuid4())


def ensure_correlation_id() -> str:
    """
    Get the current correlation ID, or generate one if not set.

    This is useful when you need a correlation ID but aren't sure
    if one has been set. It will NOT set the correlation ID in the
    context - use set_correlation_id() or correlation_context() for that.

    Returns
    -------
    str
        The current correlation ID, or a newly generated one.

    Example
    -------
    >>> from obskit.core.context import ensure_correlation_id
    >>>
    >>> # If no context is set, generates a new ID (but doesn't store it)
    >>> cid1 = ensure_correlation_id()
    >>> cid2 = ensure_correlation_id()
    >>> print(cid1 == cid2)  # False - new ID each time when not in context
    >>>
    >>> # Inside a context, returns the same ID
    >>> with correlation_context("my-id"):
    ...     cid1 = ensure_correlation_id()
    ...     cid2 = ensure_correlation_id()
    ...     print(cid1 == cid2)  # True - same context ID
    """
    current = get_correlation_id()
    if current is not None:
        return current
    return generate_correlation_id()
