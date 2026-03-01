"""Unit tests for obskit.core.batch_context — batch job context propagation."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock, patch

import pytest

from obskit.core.batch_context import (
    batch_job_context,
    capture_context,
    create_task_with_context,
    get_batch_job_context,
    propagate_to_executor,
    propagate_to_task,
    restore_context,
)
from obskit.core.context import (
    _correlation_id,
    correlation_context,
    get_correlation_id,
    set_correlation_id,
)


@pytest.fixture(autouse=True)
async def reset_correlation_id():
    """Reset correlation ID before each test to prevent contamination."""
    token = set_correlation_id(None)
    yield
    _correlation_id.reset(token)


# =============================================================================
# capture_context
# =============================================================================


class TestCaptureContext:
    def test_captures_correlation_id_when_set(self):
        with correlation_context("test-corr-id"):
            ctx = capture_context()
        assert ctx["correlation_id"] == "test-corr-id"

    def test_captures_none_correlation_id_when_not_set(self):
        # Ensure no correlation ID is set
        with correlation_context("temp"):
            pass  # NOSONAR
        # After context exits, correlation_id is None
        ctx = capture_context()
        assert ctx.get("correlation_id") is None

    def test_captures_captured_at_timestamp(self):
        ctx = capture_context()
        assert "captured_at" in ctx

    def test_no_batch_job_key_when_not_in_batch(self):
        ctx = capture_context()
        assert "batch_job" not in ctx

    def test_captures_batch_job_context_when_present(self):
        async def run():
            async with batch_job_context("test_job") as _:
                return capture_context()

        with patch("obskit.core.batch_context._get_logger", return_value=MagicMock()):
            ctx = asyncio.get_event_loop().run_until_complete(run())
        assert "batch_job" in ctx
        assert ctx["batch_job"]["job_name"] == "test_job"


# =============================================================================
# restore_context
# =============================================================================


class TestRestoreContext:
    def test_restores_correlation_id(self):
        captured = {"correlation_id": "restored-id"}
        with restore_context(captured):
            cid = get_correlation_id()
        assert cid == "restored-id"

    def test_restores_previous_correlation_id_after_exit(self):
        with correlation_context("original-id"):
            captured = {"correlation_id": "new-id"}
            with restore_context(captured):
                assert get_correlation_id() == "new-id"
            assert get_correlation_id() == "original-id"

    def test_context_without_correlation_id_is_noop(self):
        _original_id = get_correlation_id()
        with restore_context({}):
            pass  # NOSONAR
        # Should not crash

    def test_restores_batch_job_context(self):
        batch_info = {"job_name": "test", "job_id": "abc"}
        ctx = {"batch_job": batch_info}
        with restore_context(ctx):
            batch_ctx = get_batch_job_context()
            assert batch_ctx is not None
            assert batch_ctx["job_name"] == "test"

    def test_restores_previous_batch_context_after_exit(self):
        ctx = {"batch_job": {"job_name": "inner"}}
        with restore_context(ctx):
            assert get_batch_job_context() is not None
        # After exit, batch context should be restored to None
        assert get_batch_job_context() is None


# =============================================================================
# batch_job_context
# =============================================================================


class TestBatchJobContext:
    def test_sets_correlation_id(self):
        mock_logger = MagicMock()

        async def run():
            with patch("obskit.core.batch_context._get_logger", return_value=mock_logger):
                async with batch_job_context("my_job") as ctx:
                    return get_correlation_id(), ctx

        cid, _ = asyncio.get_event_loop().run_until_complete(run())
        assert cid is not None
        assert "batch:my_job:" in cid

    def test_yields_job_context_dict(self):
        mock_logger = MagicMock()

        async def run():
            with patch("obskit.core.batch_context._get_logger", return_value=mock_logger):
                async with batch_job_context("report_job") as ctx:
                    return ctx

        ctx = asyncio.get_event_loop().run_until_complete(run())
        assert ctx["job_name"] == "report_job"
        assert "job_id" in ctx
        assert "started_at" in ctx

    def test_custom_job_id_used_when_provided(self):
        mock_logger = MagicMock()

        async def run():
            with patch("obskit.core.batch_context._get_logger", return_value=mock_logger):
                async with batch_job_context("job", job_id="custom-id-123") as ctx:
                    return ctx

        ctx = asyncio.get_event_loop().run_until_complete(run())
        assert ctx["job_id"] == "custom-id-123"

    def test_metadata_merged_into_context(self):
        mock_logger = MagicMock()

        async def run():
            with patch("obskit.core.batch_context._get_logger", return_value=mock_logger):
                async with batch_job_context("job", metadata={"source": "warehouse"}) as ctx:
                    return ctx

        ctx = asyncio.get_event_loop().run_until_complete(run())
        assert ctx["source"] == "warehouse"

    def test_logs_start_and_completion(self):
        mock_logger = MagicMock()

        async def run():
            with patch("obskit.core.batch_context._get_logger", return_value=mock_logger):
                async with batch_job_context("report_job"):
                    pass  # NOSONAR

        asyncio.get_event_loop().run_until_complete(run())
        # Logger should have been called for start and completion
        assert mock_logger.info.call_count >= 2

    def test_logs_failure_on_exception(self):
        mock_logger = MagicMock()

        async def run():
            with patch("obskit.core.batch_context._get_logger", return_value=mock_logger):
                with pytest.raises(ValueError):
                    async with batch_job_context("failing_job"):
                        raise ValueError("job failed")

        asyncio.get_event_loop().run_until_complete(run())
        # Logger.error should have been called for failure
        assert mock_logger.error.called

    def test_exception_propagates(self):
        mock_logger = MagicMock()

        async def run():
            with patch("obskit.core.batch_context._get_logger", return_value=mock_logger):
                async with batch_job_context("job"):
                    raise RuntimeError("propagated")

        with pytest.raises(RuntimeError, match="propagated"):
            asyncio.get_event_loop().run_until_complete(run())

    def test_batch_context_cleared_after_exit(self):
        mock_logger = MagicMock()

        async def run():
            with patch("obskit.core.batch_context._get_logger", return_value=mock_logger):
                async with batch_job_context("job"):
                    pass  # NOSONAR
            return get_batch_job_context()

        result = asyncio.get_event_loop().run_until_complete(run())
        assert result is None


# =============================================================================
# get_batch_job_context
# =============================================================================


class TestGetBatchJobContext:
    def test_returns_none_outside_batch(self):
        assert get_batch_job_context() is None

    def test_returns_context_inside_batch(self):
        mock_logger = MagicMock()

        async def run():
            with patch("obskit.core.batch_context._get_logger", return_value=mock_logger):
                async with batch_job_context("my_job"):
                    return get_batch_job_context()

        ctx = asyncio.get_event_loop().run_until_complete(run())
        assert ctx is not None
        assert ctx["job_name"] == "my_job"


# =============================================================================
# propagate_to_executor
# =============================================================================


class TestPropagateToExecutor:
    def test_function_executes_successfully(self):
        executor = ThreadPoolExecutor(max_workers=2)

        @propagate_to_executor(executor)
        def simple_task():
            return "done"

        with correlation_context("test-id"):
            result = simple_task()

        assert result == "done"
        executor.shutdown(wait=True)

    def test_context_propagated_to_thread(self):
        collected = []
        executor = ThreadPoolExecutor(max_workers=2)

        @propagate_to_executor(executor)
        def capture_context_in_thread():
            collected.append(get_correlation_id())

        with correlation_context("propagated-id"):
            capture_context_in_thread()

        executor.shutdown(wait=True)
        assert collected == ["propagated-id"]

    def test_preserves_function_name(self):
        executor = ThreadPoolExecutor(max_workers=1)

        @propagate_to_executor(executor)
        def my_named_func():
            pass  # NOSONAR

        assert my_named_func.__name__ == "my_named_func"
        executor.shutdown(wait=True)

    def test_exception_propagates(self):
        executor = ThreadPoolExecutor(max_workers=1)

        @propagate_to_executor(executor)
        def failing_task():
            raise ValueError("task error")

        with pytest.raises(ValueError, match="task error"):
            failing_task()

        executor.shutdown(wait=True)


# =============================================================================
# propagate_to_task
# =============================================================================


class TestPropagateToTask:
    def test_wraps_async_function(self):
        @propagate_to_task
        async def my_task(x):
            return x * 2

        result = asyncio.get_event_loop().run_until_complete(my_task(5))
        assert result == 10

    def test_preserves_function_name(self):
        @propagate_to_task
        async def named_task():
            pass  # NOSONAR

        assert named_task.__name__ == "named_task"

    def test_propagates_context(self):
        results = []

        @propagate_to_task
        async def capture_id():
            results.append(get_correlation_id())

        async def run():
            with correlation_context("ctx-id"):
                await capture_id()

        asyncio.get_event_loop().run_until_complete(run())
        assert results == ["ctx-id"]


# =============================================================================
# create_task_with_context
# =============================================================================


class TestCreateTaskWithContext:
    def test_creates_task_and_runs(self):
        results = []

        async def my_coro():  # NOSONAR
            results.append("ran")

        async def run():
            task = create_task_with_context(my_coro())
            await task

        asyncio.get_event_loop().run_until_complete(run())
        assert results == ["ran"]

    def test_propagates_correlation_id(self):
        captured = []

        async def capture_id():  # NOSONAR
            captured.append(get_correlation_id())

        async def run():
            with correlation_context("task-ctx-id"):
                task = create_task_with_context(capture_id())
                await task

        asyncio.get_event_loop().run_until_complete(run())
        assert captured == ["task-ctx-id"]

    def test_task_named_when_name_provided(self):
        async def noop():
            pass  # NOSONAR

        async def run():
            task = create_task_with_context(noop(), name="my-task")
            await task
            return task.get_name()

        name = asyncio.get_event_loop().run_until_complete(run())
        assert name == "my-task"

    def test_exception_in_task_propagates(self):
        async def failing_coro():
            raise ValueError("task failed")

        async def run():
            task = create_task_with_context(failing_coro())
            await task

        with pytest.raises(ValueError, match="task failed"):
            asyncio.get_event_loop().run_until_complete(run())


# =============================================================================
# Additional coverage tests
# =============================================================================


class TestBatchContextCoverageGaps:
    """Tests for remaining uncovered lines in batch_context.py."""

    def test_get_logger_function(self):
        """Test the lazy _get_logger() function (lines 85-87)."""
        from obskit.core.batch_context import _get_logger
        logger = _get_logger()
        assert logger is not None

    def test_capture_context_with_tracing(self):
        """Test capture_context when trace headers are populated (line 138)."""
        from unittest.mock import MagicMock, patch

        from obskit.core.batch_context import capture_context
        from obskit.core.context import correlation_context

        # Patch inject_trace_context to return trace headers
        def mock_inject(headers):
            headers["X-Trace-ID"] = "trace-123"
            return headers

        with patch("obskit.tracing.tracer.inject_trace_context", side_effect=mock_inject):
            with correlation_context("test-ctx"):
                ctx = capture_context()

        assert "trace_headers" in ctx
        assert ctx["trace_headers"]["X-Trace-ID"] == "trace-123"
