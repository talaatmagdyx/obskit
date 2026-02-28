"""Unit tests for batch operation tracking."""

import asyncio

import pytest

from obskit.batch import (
    BatchContext,
    BatchResult,
    BatchTracker,
    track_batch,
)


class TestBatchResult:
    """Tests for BatchResult dataclass."""

    def test_init_defaults(self):
        """Test default values."""
        result = BatchResult()
        assert result.total_items == 0
        assert result.successful_items == 0
        assert result.failed_items == 0
        assert result.errors == []
        assert result.duration_seconds == 0.0

    def test_success_rate_empty(self):
        """Test success rate with no items."""
        result = BatchResult()
        assert result.success_rate == 1.0

    def test_success_rate_all_success(self):
        """Test success rate with all successful items."""
        result = BatchResult(total_items=10, successful_items=10, failed_items=0)
        assert result.success_rate == 1.0

    def test_success_rate_partial(self):
        """Test success rate with partial success."""
        result = BatchResult(total_items=10, successful_items=7, failed_items=3)
        assert result.success_rate == 0.7

    def test_all_succeeded_true(self):
        """Test all_succeeded when no failures."""
        result = BatchResult(total_items=10, successful_items=10, failed_items=0)
        assert result.all_succeeded is True

    def test_all_succeeded_false(self):
        """Test all_succeeded when there are failures."""
        result = BatchResult(total_items=10, successful_items=8, failed_items=2)
        assert result.all_succeeded is False


class TestBatchContext:
    """Tests for BatchContext class."""

    def test_init(self):
        """Test context initialization."""
        ctx = BatchContext("test_batch", batch_size=100)
        assert ctx.batch_name == "test_batch"
        assert ctx.batch_size == 100

    def test_record_success(self):
        """Test recording success."""
        ctx = BatchContext("test_batch")
        ctx.record_success()
        ctx.record_success(count=3)
        assert ctx._successful == 4

    def test_record_failure(self):
        """Test recording failure."""
        ctx = BatchContext("test_batch")
        ctx.record_failure(error="Test error", item_id="123")
        assert ctx._failed == 1
        assert len(ctx._errors) == 1
        assert ctx._errors[0]["error"] == "Test error"

    def test_record_skip(self):
        """Test recording skipped items."""
        ctx = BatchContext("test_batch")
        ctx.record_skip(count=5, reason="Already processed")
        # Skip doesn't affect success/fail counts
        assert ctx._successful == 0
        assert ctx._failed == 0

    def test_processed_count(self):
        """Test processed property."""
        ctx = BatchContext("test_batch")
        ctx.record_success(count=5)
        ctx.record_failure(count=2)
        assert ctx.processed == 7

    def test_success_rate(self):
        """Test success_rate property."""
        ctx = BatchContext("test_batch")
        ctx.record_success(count=8)
        ctx.record_failure(count=2)
        assert ctx.success_rate == 0.8

    def test_get_result(self):
        """Test get_result returns BatchResult."""
        ctx = BatchContext("test_batch", batch_size=10)
        ctx.record_success(count=7)
        ctx.record_failure(count=3, error="Failed")

        result = ctx.get_result()
        assert isinstance(result, BatchResult)
        assert result.total_items == 10
        assert result.successful_items == 7
        assert result.failed_items == 3


class TestBatchTracker:
    """Tests for BatchTracker class."""

    def test_init(self):
        """Test tracker initialization."""
        tracker = BatchTracker("test_tracker")
        assert tracker.name == "test_tracker"

    def test_track_batch_success(self):
        """Test tracking a successful batch."""
        tracker = BatchTracker("test_tracker")

        with tracker.track_batch(batch_size=10) as batch:
            for _i in range(10):
                batch.record_success()

        stats = tracker.get_stats()
        assert stats["total_batches"] == 1
        assert stats["successful_items"] == 10
        assert stats["failed_items"] == 0

    def test_track_batch_partial_failure(self):
        """Test tracking a batch with partial failures."""
        tracker = BatchTracker("test_tracker")

        with tracker.track_batch(batch_size=10) as batch:
            for _ in range(7):
                batch.record_success()
            for idx in range(3):
                batch.record_failure(error=f"Error {idx}")

        stats = tracker.get_stats()
        assert stats["successful_items"] == 7
        assert stats["failed_items"] == 3

    def test_track_batch_exception(self):
        """Test tracking a batch that raises exception."""
        tracker = BatchTracker("test_tracker")

        with pytest.raises(ValueError):
            with tracker.track_batch() as batch:
                batch.record_success()
                raise ValueError("Critical error")

    def test_process_batch(self):
        """Test process_batch helper method."""
        tracker = BatchTracker("test_tracker")
        items = [1, 2, 3, 4, 5]

        def processor(item):
            if item == 3:
                raise ValueError("Bad item")
            return item * 2

        result = tracker.process_batch(items=items, processor=processor, fail_fast=False)

        assert result.successful_items == 4
        assert result.failed_items == 1

    @pytest.mark.asyncio
    async def test_process_batch_async(self):
        """Test async batch processing."""
        tracker = BatchTracker("test_tracker")
        items = [1, 2, 3, 4, 5]

        async def processor(item):
            await asyncio.sleep(0.01)
            return item * 2

        result = await tracker.process_batch_async(items=items, processor=processor, concurrency=3)

        assert result.successful_items == 5
        assert result.failed_items == 0

    def test_get_stats(self):
        """Test get_stats returns correct statistics."""
        tracker = BatchTracker("test_tracker")

        with tracker.track_batch(batch_size=10) as batch:
            batch.record_success(count=10)

        with tracker.track_batch(batch_size=5) as batch:
            batch.record_success(count=3)
            batch.record_failure(count=2)

        stats = tracker.get_stats()
        assert stats["total_batches"] == 2
        assert stats["total_items"] == 15
        assert stats["successful_items"] == 13
        assert stats["failed_items"] == 2


class TestTrackBatchDecorator:
    """Tests for track_batch decorator."""

    def test_decorator_sync(self):
        """Test decorator on sync function."""

        @track_batch("decorated_batch", batch_size=5)
        def process_items(items, _batch_context=None):
            for _ in items:  # Item not used, just counting
                _batch_context.record_success()
            return len(items)

        result = process_items([1, 2, 3, 4, 5])
        assert result == 5

    @pytest.mark.asyncio
    async def test_decorator_async(self):
        """Test decorator on async function."""

        @track_batch("decorated_batch_async", batch_size=3)
        async def process_items_async(items, _batch_context=None):
            for _ in items:  # Item not used, just counting
                _batch_context.record_success()
            return len(items)

        result = await process_items_async([1, 2, 3])
        assert result == 3


class TestBatchTrackerEdgeCases:
    def test_record_skip_with_reason(self):
        from obskit.batch import BatchContext
        ctx = BatchContext("test_batch", 10)
        ctx.record_skip(count=1, reason="duplicate")

    def test_success_rate_zero_processed(self):
        from obskit.batch import BatchContext
        ctx = BatchContext("test_batch", 0)
        assert ctx.success_rate == 1.0

    def test_process_batch_without_batch_size_uses_processed(self):
        from obskit.batch import BatchTracker
        tracker = BatchTracker("test_tracker")
        called = []
        def processor(item):
            called.append(item)
        result = tracker.process_batch([1, 2, 3], processor)
        assert len(called) == 3

    def test_process_batch_with_on_error_callback(self):
        from obskit.batch import BatchTracker
        tracker = BatchTracker("test_tracker")
        errors = []
        def on_error(item, exc):
            errors.append((item, exc))
        def processor(item):
            if item == 2: raise ValueError("oops")
        tracker.process_batch([1, 2, 3], processor, on_error=on_error)
        assert len(errors) == 1
        assert errors[0][0] == 2

    def test_process_batch_fail_fast(self):
        import pytest

        from obskit.batch import BatchTracker
        tracker = BatchTracker("test_tracker")
        def processor(item):
            if item == 1: raise ValueError("fail")
        with pytest.raises(ValueError):
            tracker.process_batch([1, 2, 3], processor, fail_fast=True)


    def test_track_batch_no_batch_size_with_processed_items(self):
        from obskit.batch import BatchTracker
        tracker = BatchTracker("test_tracker")
        with tracker.track_batch(batch_size=0) as batch:
            batch.record_success()
            batch.record_success()
        # batch_size=0 but batch.processed > 0 covers lines 212-213


    def test_record_skip_without_reason(self):
        from obskit.batch import BatchContext
        ctx = BatchContext("test_batch", 10)
        ctx.record_skip(count=1)  # No reason - covers the if-reason else branch

    def test_track_batch_no_batch_size_zero_processed(self):
        from obskit.batch import BatchTracker
        tracker = BatchTracker("test_tracker")
        with tracker.track_batch(batch_size=0) as batch:
            pass  # No items processed - batch.processed == 0, covers 212->215 branch


class TestBatchTrackerAsyncEdgeCases:
    def test_process_batch_async_with_error_and_on_error(self):
        import asyncio

        from obskit.batch import BatchTracker
        tracker = BatchTracker("test_tracker")
        errors = []
        def on_error(item, exc):
            errors.append((item, exc))
        async def processor(item):
            if item == 2: raise ValueError("async error")
        asyncio.run(tracker.process_batch_async([1, 2, 3], processor, on_error=on_error))
        assert len(errors) == 1

    def test_process_batch_async_fail_fast(self):
        import asyncio

        import pytest

        from obskit.batch import BatchTracker
        tracker = BatchTracker("test_tracker")
        async def processor(item):
            if item == 1: raise ValueError("fail")
        with pytest.raises(ValueError):
            asyncio.run(tracker.process_batch_async([1, 2, 3], processor, fail_fast=True))

