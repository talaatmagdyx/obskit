"""
Observability Context Managers
==============================

Context manager versions of the observability decorators.

These work both as ``async with`` / ``with`` blocks AND as function decorators
(Python's ``@asynccontextmanager`` / ``@contextmanager`` produce objects that
inherit from ``AsyncContextDecorator`` / ``ContextDecorator``).

Usage — context manager:

    async with observe(operation="db_query", component="DB"):
        result = await db.query(...)

    with observe_sync(operation="file_read", component="Storage"):
        data = open(path).read()

Usage — decorator:

    @observe(operation="fetch_orders", component="OrderService")
    async def fetch_orders():
        return await db.all()

    @observe_sync(operation="process_file", component="FileProcessor")
    def process_file(path):
        with open(path) as f:
            return f.read()

Note: when used as a decorator, ``operation`` cannot be auto-derived from the
function name (use ``with_observability`` / ``with_observability_sync`` for
that). Pass ``operation=`` explicitly or accept the ``"unnamed_operation"``
default.
"""

from __future__ import annotations

import random
import time
from collections.abc import AsyncGenerator, Generator
from contextlib import asynccontextmanager, contextmanager, nullcontext
from typing import Any

from obskit.core.context import async_correlation_context, get_correlation_id
from obskit.decorators.ht_runtime import get_ht_pipeline
from obskit.logging import get_logger, log_error, log_operation, log_performance
from obskit.metrics.red import get_red_metrics

logger = get_logger(__name__)


@asynccontextmanager
async def observe(
    component: str | None = None,
    operation: str | None = None,
    threshold_ms: float | None = None,
    track_metrics: bool = True,
    log_start: bool = False,
    sample_rate: float = 1.0,
    high_throughput: bool = False,
    **default_context: Any,
) -> AsyncGenerator[None, None]:
    """
    Async observability context manager (and decorator).

    Instruments the wrapped block with the same logging, metrics, and error
    tracking as ``with_observability``.  Because it is built on
    ``@asynccontextmanager`` it also acts as an async function decorator.

    Parameters
    ----------
    component : str, optional
        Component/service name. Defaults to ``"unknown"``.
    operation : str, optional
        Operation name. Defaults to ``"unnamed_operation"``.
    threshold_ms : float, optional
        Log a warning if the block takes longer than this many milliseconds.
    track_metrics : bool, default=True
        Record Prometheus RED metrics.
    log_start : bool, default=False
        Log when the block starts.
    sample_rate : float, default=1.0
        Fraction of invocations that go through the full pipeline.
        Non-sampled blocks still execute normally.
    high_throughput : bool, default=False
        Use the async ring-buffer + thread-local aggregator pipeline instead
        of the synchronous Prometheus + structlog pipeline.
    **default_context : Any
        Extra key/value pairs added to every log entry.

    Examples
    --------
    As a context manager::

        async with observe(operation="db_query", component="DB", threshold_ms=100):
            result = await db.query(sql)

    As a decorator::

        @observe(operation="fetch_orders", component="OrderService")
        async def fetch_orders():
            return await db.all()

    See Also
    --------
    with_observability : Async decorator with auto-derived operation name.
    observe_sync : Sync variant of this context manager / decorator.
    """
    comp = component or "unknown"
    op = operation or "unnamed_operation"

    # ------------------------------------------------------------------
    # Step 0: Sampling gate
    # ------------------------------------------------------------------
    if sample_rate < 1.0 and random.random() >= sample_rate:
        yield
        return

    # ------------------------------------------------------------------
    # Step 1: High-throughput path
    # ------------------------------------------------------------------
    if high_throughput:
        start_time = time.perf_counter()
        try:
            yield
            duration_s = time.perf_counter() - start_time
            get_ht_pipeline().record(op, comp, duration_s, True, default_context.copy())
        except Exception as e:
            duration_s = time.perf_counter() - start_time
            get_ht_pipeline().record(op, comp, duration_s, False, default_context.copy(), error=e)
            raise
        return

    # ------------------------------------------------------------------
    # Step 2: Standard path
    # ------------------------------------------------------------------
    context = default_context.copy()
    correlation_id = get_correlation_id()

    async with nullcontext() if correlation_id else async_correlation_context():
        start_time = time.perf_counter()

        if log_start:
            logger.debug("operation_started", component=comp, operation=op, **context)

        try:
            yield
            duration_ms = (time.perf_counter() - start_time) * 1000

            log_performance(
                operation=op,
                component=comp,
                duration_ms=duration_ms,
                threshold_ms=threshold_ms,
                **context,
            )

            if track_metrics:
                get_red_metrics().observe_request(
                    operation=op,
                    duration_seconds=duration_ms / 1000.0,
                    status="success",
                )

            log_operation(
                operation=op,
                component=comp,
                status="success",
                duration_ms=duration_ms,
                **context,
            )

        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000

            log_error(error=e, component=comp, operation=op, context=context)

            if track_metrics:
                get_red_metrics().observe_request(
                    operation=op,
                    duration_seconds=duration_ms / 1000.0,
                    status="failure",
                    error_type=type(e).__name__,
                )

            log_operation(
                operation=op,
                component=comp,
                status="failure",
                duration_ms=duration_ms,
                error=str(e),
                error_type=type(e).__name__,
                **context,
            )
            raise


@contextmanager
def observe_sync(
    component: str | None = None,
    operation: str | None = None,
    threshold_ms: float | None = None,
    track_metrics: bool = True,
    log_start: bool = False,
    sample_rate: float = 1.0,
    high_throughput: bool = False,
    **default_context: Any,
) -> Generator[None, None, None]:
    """
    Sync observability context manager (and decorator).

    Instruments the wrapped block with the same logging, metrics, and error
    tracking as ``with_observability_sync``.  Because it is built on
    ``@contextmanager`` it also acts as a function decorator.

    Parameters
    ----------
    component : str, optional
        Component/service name. Defaults to ``"unknown"``.
    operation : str, optional
        Operation name. Defaults to ``"unnamed_operation"``.
    threshold_ms : float, optional
        Log a warning if the block takes longer than this many milliseconds.
    track_metrics : bool, default=True
        Record Prometheus RED metrics.
    log_start : bool, default=False
        Log when the block starts.
    sample_rate : float, default=1.0
        Fraction of invocations that go through the full pipeline.
        Non-sampled blocks still execute normally.
    high_throughput : bool, default=False
        Use the async ring-buffer + thread-local aggregator pipeline instead
        of the synchronous Prometheus + structlog pipeline.
    **default_context : Any
        Extra key/value pairs added to every log entry.

    Examples
    --------
    As a context manager::

        with observe_sync(operation="file_read", component="Storage"):
            data = open(path).read()

    As a decorator::

        @observe_sync(operation="process_file", component="FileProcessor")
        def process_file(path):
            with open(path) as f:
                return f.read()

    See Also
    --------
    with_observability_sync : Sync decorator with auto-derived operation name.
    observe : Async variant of this context manager / decorator.
    """
    comp = component or "unknown"
    op = operation or "unnamed_operation"

    # ------------------------------------------------------------------
    # Step 0: Sampling gate
    # ------------------------------------------------------------------
    if sample_rate < 1.0 and random.random() >= sample_rate:
        yield
        return

    # ------------------------------------------------------------------
    # Step 1: High-throughput path
    # ------------------------------------------------------------------
    if high_throughput:
        start_time = time.perf_counter()
        try:
            yield
            duration_s = time.perf_counter() - start_time
            get_ht_pipeline().record(op, comp, duration_s, True, default_context.copy())
        except Exception as e:
            duration_s = time.perf_counter() - start_time
            get_ht_pipeline().record(op, comp, duration_s, False, default_context.copy(), error=e)
            raise
        return

    # ------------------------------------------------------------------
    # Step 2: Standard path
    # ------------------------------------------------------------------
    context = default_context.copy()
    start_time = time.perf_counter()

    if log_start:
        logger.debug("operation_started", component=comp, operation=op, **context)

    try:
        yield
        duration_ms = (time.perf_counter() - start_time) * 1000

        log_performance(
            operation=op,
            component=comp,
            duration_ms=duration_ms,
            threshold_ms=threshold_ms,
            **context,
        )

        if track_metrics:
            get_red_metrics().observe_request(
                operation=op,
                duration_seconds=duration_ms / 1000.0,
                status="success",
            )

        log_operation(
            operation=op,
            component=comp,
            status="success",
            duration_ms=duration_ms,
            **context,
        )

    except Exception as e:
        duration_ms = (time.perf_counter() - start_time) * 1000

        log_error(error=e, component=comp, operation=op, context=context)

        if track_metrics:
            get_red_metrics().observe_request(
                operation=op,
                duration_seconds=duration_ms / 1000.0,
                status="failure",
                error_type=type(e).__name__,
            )

        log_operation(
            operation=op,
            component=comp,
            status="failure",
            duration_ms=duration_ms,
            error=str(e),
            error_type=type(e).__name__,
            **context,
        )
        raise
