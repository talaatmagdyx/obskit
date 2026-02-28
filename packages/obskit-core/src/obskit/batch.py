"""
Batch Operation Tracking.

Provides utilities for tracking batch processing operations with metrics.
"""

import time
from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, TypeVar

from prometheus_client import Counter, Gauge, Histogram

from .logging import get_logger

logger = get_logger(__name__)

# Metrics
BATCH_COUNTER = Counter(
    "batch_processing_total", "Total batches processed", ["batch_name", "status"]
)

BATCH_ITEMS_COUNTER = Counter(
    "batch_items_total", "Total items processed in batches", ["batch_name", "status"]
)

BATCH_DURATION = Histogram(
    "batch_processing_duration_seconds",
    "Batch processing duration",
    ["batch_name"],
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0],
)

BATCH_SIZE = Histogram(
    "batch_size",
    "Batch size distribution",
    ["batch_name"],
    buckets=[1, 5, 10, 25, 50, 100, 250, 500, 1000, 5000, 10000],
)

BATCH_SUCCESS_RATE = Gauge("batch_success_rate", "Current batch success rate", ["batch_name"])

BATCH_IN_PROGRESS = Gauge(
    "batch_in_progress", "Number of batches currently in progress", ["batch_name"]
)

F = TypeVar("F", bound=Callable[..., Any])


@dataclass
class BatchResult:
    """Result of a batch operation."""

    total_items: int = 0
    successful_items: int = 0
    failed_items: int = 0
    errors: list[dict[str, Any]] = field(default_factory=list)
    duration_seconds: float = 0.0

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_items == 0:
            return 1.0
        return self.successful_items / self.total_items

    @property
    def all_succeeded(self) -> bool:
        """Check if all items succeeded."""
        return self.failed_items == 0


class BatchContext:
    """
    Context for tracking individual batch operations.

    Example:
        with tracker.track_batch(batch_size=100) as batch:
            for item in items:
                try:
                    process(item)
                    batch.record_success()
                except Exception as e:
                    batch.record_failure(error=str(e), item_id=item.id)
    """

    def __init__(self, batch_name: str, batch_size: int = 0):
        self.batch_name = batch_name
        self.batch_size = batch_size
        self.start_time = time.time()
        self._successful = 0
        self._failed = 0
        self._errors: list[dict[str, Any]] = []

    def record_success(self, count: int = 1):
        """Record successful item(s)."""
        self._successful += count
        BATCH_ITEMS_COUNTER.labels(batch_name=self.batch_name, status="success").inc(count)

    def record_failure(self, count: int = 1, error: str | None = None, **metadata):
        """
        Record failed item(s).

        Args:
            count: Number of failed items
            error: Error message
            **metadata: Additional metadata about the failure
        """
        self._failed += count
        BATCH_ITEMS_COUNTER.labels(batch_name=self.batch_name, status="failure").inc(count)

        if error:
            error_info = {"error": error, **metadata}
            self._errors.append(error_info)
            logger.warning("batch_item_failed", batch_name=self.batch_name, error=error, **metadata)

    def record_skip(self, count: int = 1, reason: str | None = None):
        """Record skipped item(s)."""
        BATCH_ITEMS_COUNTER.labels(batch_name=self.batch_name, status="skipped").inc(count)
        if reason:
            logger.debug("batch_item_skipped", batch_name=self.batch_name, reason=reason)

    @property
    def processed(self) -> int:
        """Total items processed (success + failure)."""
        return self._successful + self._failed

    @property
    def success_rate(self) -> float:
        """Current success rate."""
        if self.processed == 0:
            return 1.0
        return self._successful / self.processed

    def get_result(self) -> BatchResult:
        """Get batch result."""
        return BatchResult(
            total_items=self.batch_size or self.processed,
            successful_items=self._successful,
            failed_items=self._failed,
            errors=self._errors.copy(),
            duration_seconds=time.time() - self.start_time,
        )


class BatchTracker:
    """
    Tracks batch processing operations.

    Example:
        tracker = BatchTracker("widget_processing")

        with tracker.track_batch(batch_size=100) as batch:
            for item in items:
                try:
                    process(item)
                    batch.record_success()
                except Exception as e:
                    batch.record_failure(error=str(e))

        # Or process items directly
        results = tracker.process_batch(
            items=my_items,
            processor=process_item,
            batch_size=50
        )
    """

    def __init__(self, name: str):
        """
        Initialize batch tracker.

        Args:
            name: Name for this batch operation (used in metrics)
        """
        self.name = name
        self._total_batches = 0
        self._total_items = 0
        self._successful_items = 0
        self._failed_items = 0

    @contextmanager
    def track_batch(
        self, batch_size: int = 0, fail_fast: bool = False
    ) -> Generator[BatchContext, None, None]:
        """
        Context manager for tracking a batch operation.

        Args:
            batch_size: Expected batch size (0 if unknown)
            fail_fast: If True, raises exception on first failure

        Yields:
            BatchContext for recording results
        """
        BATCH_IN_PROGRESS.labels(batch_name=self.name).inc()
        batch = BatchContext(self.name, batch_size)

        try:
            yield batch

            # Record batch completion
            result = batch.get_result()
            status = "success" if result.all_succeeded else "partial_failure"

            BATCH_COUNTER.labels(batch_name=self.name, status=status).inc()
            BATCH_DURATION.labels(batch_name=self.name).observe(result.duration_seconds)

            if batch_size > 0:
                BATCH_SIZE.labels(batch_name=self.name).observe(batch_size)
            elif batch.processed > 0:
                BATCH_SIZE.labels(batch_name=self.name).observe(batch.processed)

            BATCH_SUCCESS_RATE.labels(batch_name=self.name).set(result.success_rate)

            # Update totals
            self._total_batches += 1
            self._total_items += result.total_items
            self._successful_items += result.successful_items
            self._failed_items += result.failed_items

            logger.info(
                "batch_completed",
                batch_name=self.name,
                total_items=result.total_items,
                successful=result.successful_items,
                failed=result.failed_items,
                success_rate=result.success_rate,
                duration_seconds=result.duration_seconds,
            )

        except Exception as e:
            BATCH_COUNTER.labels(batch_name=self.name, status="error").inc()
            logger.error(
                "batch_failed", batch_name=self.name, error=str(e), processed=batch.processed
            )
            raise
        finally:
            BATCH_IN_PROGRESS.labels(batch_name=self.name).dec()

    def process_batch(
        self,
        items: list[Any],
        processor: Callable[[Any], Any],
        batch_size: int | None = None,
        fail_fast: bool = False,
        on_error: Callable[[Any, Exception], None] | None = None,
    ) -> BatchResult:
        """
        Process a batch of items with tracking.

        Args:
            items: Items to process
            processor: Function to process each item
            batch_size: Process in sub-batches of this size
            fail_fast: Stop on first error
            on_error: Callback for errors (item, exception)

        Returns:
            BatchResult with processing summary
        """
        total_items = len(items)

        with self.track_batch(batch_size=total_items) as batch:
            for item in items:
                try:
                    processor(item)
                    batch.record_success()
                except Exception as e:
                    batch.record_failure(error=str(e))
                    if on_error:
                        on_error(item, e)
                    if fail_fast:
                        raise

            return batch.get_result()

    async def process_batch_async(
        self,
        items: list[Any],
        processor: Callable[[Any], Any],
        concurrency: int = 10,
        fail_fast: bool = False,
        on_error: Callable[[Any, Exception], None] | None = None,
    ) -> BatchResult:
        """
        Process a batch of items asynchronously with tracking.

        Args:
            items: Items to process
            processor: Async function to process each item
            concurrency: Max concurrent operations
            fail_fast: Stop on first error
            on_error: Callback for errors

        Returns:
            BatchResult with processing summary
        """
        import asyncio

        total_items = len(items)
        semaphore = asyncio.Semaphore(concurrency)

        async def process_with_semaphore(item, batch: BatchContext):
            async with semaphore:
                try:
                    await processor(item)
                    batch.record_success()
                except Exception as e:
                    batch.record_failure(error=str(e))
                    if on_error:
                        on_error(item, e)
                    if fail_fast:
                        raise

        with self.track_batch(batch_size=total_items) as batch:
            tasks = [process_with_semaphore(item, batch) for item in items]
            await asyncio.gather(*tasks, return_exceptions=not fail_fast)
            return batch.get_result()

    def get_stats(self) -> dict[str, Any]:
        """Get overall batch processing statistics."""
        return {
            "total_batches": self._total_batches,
            "total_items": self._total_items,
            "successful_items": self._successful_items,
            "failed_items": self._failed_items,
            "overall_success_rate": (
                self._successful_items / self._total_items if self._total_items > 0 else 1.0
            ),
        }


def track_batch(name: str, batch_size: int = 0):
    """
    Decorator for batch processing functions.

    Example:
        @track_batch("data_import", batch_size=100)
        def import_data(items):
            for item in items:
                process(item)
    """
    tracker = BatchTracker(name)

    def decorator(func: F) -> F:
        import functools

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with tracker.track_batch(batch_size=batch_size) as batch:
                kwargs["_batch_context"] = batch
                return func(*args, **kwargs)

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            with tracker.track_batch(batch_size=batch_size) as batch:
                kwargs["_batch_context"] = batch
                return await func(*args, **kwargs)

        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return wrapper  # type: ignore

    return decorator


__all__ = [
    "BatchTracker",
    "BatchContext",
    "BatchResult",
    "track_batch",
    "BATCH_COUNTER",
    "BATCH_ITEMS_COUNTER",
    "BATCH_DURATION",
    "BATCH_SIZE",
    "BATCH_SUCCESS_RATE",
    "BATCH_IN_PROGRESS",
]
