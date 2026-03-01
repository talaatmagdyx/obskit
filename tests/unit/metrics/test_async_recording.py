"""Tests for obskit.metrics.async_recording module."""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

import obskit.metrics.async_recording as async_recording_module

# Aliases for commonly used imports
AsyncREDMetrics = async_recording_module.AsyncREDMetrics
_ensure_worker_started = async_recording_module._ensure_worker_started
_metric_worker = async_recording_module._metric_worker
shutdown_async_recording = async_recording_module.shutdown_async_recording


def reset_module_state():
    """Reset module global state."""
    if (
        async_recording_module._metric_worker_task
        and not async_recording_module._metric_worker_task.done()
    ):
        try:
            async_recording_module._metric_worker_task.cancel()
        except RuntimeError:
            # Event loop may already be closed during sync teardown; ignore
            pass
    async_recording_module._metric_queue = None
    async_recording_module._metric_worker_task = None


class TestAsyncREDMetrics:
    """Tests for AsyncREDMetrics class."""

    def setup_method(self):
        """Reset state before each test."""
        reset_module_state()

    def teardown_method(self):
        """Clean up after each test."""
        reset_module_state()

    def test_init(self):
        """Test AsyncREDMetrics initialization."""
        mock_base = MagicMock()

        metrics = AsyncREDMetrics(mock_base)

        assert metrics._base is mock_base
        assert metrics._queue_size == 10000

    def test_init_custom_queue_size(self):
        """Test initialization with custom queue size."""
        mock_base = MagicMock()

        metrics = AsyncREDMetrics(mock_base, queue_size=5000)

        assert metrics._queue_size == 5000

    @pytest.mark.asyncio
    async def test_observe_request_queues_metric(self):
        """Test observe_request adds metric to queue."""
        module = async_recording_module

        mock_base = MagicMock()
        metrics = AsyncREDMetrics(mock_base)

        await metrics.observe_request(
            operation="test_op",
            duration_seconds=0.05,
            status="success",
        )

        # Give worker time to process
        await asyncio.sleep(0.2)

        # Either queued or processed
        assert module._metric_queue is not None

    @pytest.mark.asyncio
    async def test_observe_request_processes_metric(self):
        """Test observe_request metric is eventually processed."""
        mock_base = MagicMock()
        metrics = AsyncREDMetrics(mock_base)

        await metrics.observe_request(
            operation="test_op",
            duration_seconds=0.05,
            status="success",
        )

        # Give worker time to process
        await asyncio.sleep(0.3)

        # Shutdown to process remaining
        await shutdown_async_recording()

        # The metric should have been processed
        mock_base.observe_request.assert_called()

    @pytest.mark.asyncio
    async def test_observe_request_with_error_type(self):
        """Test observe_request with error_type."""
        mock_base = MagicMock()
        metrics = AsyncREDMetrics(mock_base)

        await metrics.observe_request(
            operation="test_op",
            duration_seconds=0.05,
            status="failure",
            error_type="ValueError",
        )

        await asyncio.sleep(0.2)
        await shutdown_async_recording()


class TestEnsureWorkerStarted:
    """Tests for _ensure_worker_started function."""

    def setup_method(self):
        """Reset state before each test."""
        reset_module_state()

    def teardown_method(self):
        """Clean up after each test."""
        reset_module_state()

    @pytest.mark.asyncio
    async def test_creates_queue(self):
        """Test function creates queue."""
        module = async_recording_module

        await _ensure_worker_started()

        assert module._metric_queue is not None
        assert module._metric_queue.maxsize == 10000

    @pytest.mark.asyncio
    async def test_creates_worker_task(self):
        """Test function creates worker task."""
        module = async_recording_module

        await _ensure_worker_started()

        assert module._metric_worker_task is not None
        assert not module._metric_worker_task.done()

    @pytest.mark.asyncio
    async def test_idempotent(self):
        """Test calling multiple times is safe."""
        module = async_recording_module

        await _ensure_worker_started()
        first_queue = module._metric_queue
        first_task = module._metric_worker_task

        await _ensure_worker_started()

        assert module._metric_queue is first_queue
        assert module._metric_worker_task is first_task


class TestMetricWorker:
    """Tests for _metric_worker function."""

    def setup_method(self):
        """Reset state before each test."""
        reset_module_state()

    def teardown_method(self):
        """Clean up after each test."""
        reset_module_state()

    @pytest.mark.asyncio
    async def test_worker_processes_metric(self):
        """Test worker processes queued metrics."""
        module = async_recording_module

        await _ensure_worker_started()

        mock_metrics = MagicMock()

        await module._metric_queue.put(
            {
                "metrics": mock_metrics,
                "method": "observe_request",
                "args": ("test_op", 0.05),
                "kwargs": {"status": "success"},
            }
        )

        # Give worker time to process
        await asyncio.sleep(0.2)

        mock_metrics.observe_request.assert_called_once_with("test_op", 0.05, status="success")

    @pytest.mark.asyncio
    async def test_worker_handles_invalid_method(self):
        """Test worker handles invalid method gracefully."""
        module = async_recording_module

        await _ensure_worker_started()

        mock_metrics = MagicMock()
        mock_metrics.nonexistent_method = None
        del mock_metrics.nonexistent_method

        await module._metric_queue.put(
            {
                "metrics": mock_metrics,
                "method": "nonexistent_method",
                "args": (),
                "kwargs": {},
            }
        )

        # Give worker time to process
        await asyncio.sleep(0.2)

        # Should not raise, just log warning

    @pytest.mark.asyncio
    async def test_worker_handles_method_exception(self):
        """Test worker handles exception in method call."""
        module = async_recording_module

        await _ensure_worker_started()

        mock_metrics = MagicMock()
        mock_metrics.observe_request.side_effect = ValueError("Test error")

        await module._metric_queue.put(
            {
                "metrics": mock_metrics,
                "method": "observe_request",
                "args": ("test_op", 0.05),
                "kwargs": {},
            }
        )

        # Give worker time to process
        await asyncio.sleep(0.2)

        # Should not raise, just log error


class TestShutdownAsyncRecording:
    """Tests for shutdown_async_recording function."""

    def setup_method(self):
        """Reset state before each test."""
        reset_module_state()

    @pytest.mark.asyncio
    async def test_shutdown_cancels_worker(self):
        """Test shutdown cancels worker task."""
        module = async_recording_module

        await _ensure_worker_started()

        assert module._metric_worker_task is not None

        await shutdown_async_recording()

        assert module._metric_worker_task is None
        assert module._metric_queue is None

    @pytest.mark.asyncio
    async def test_shutdown_processes_remaining(self):
        """Test shutdown processes remaining queue items."""
        module = async_recording_module

        await _ensure_worker_started()

        mock_metrics = MagicMock()

        # Add item directly to queue
        await module._metric_queue.put(
            {
                "metrics": mock_metrics,
                "method": "observe_request",
                "args": ("test_op", 0.05),
                "kwargs": {},
            }
        )

        # Shutdown immediately
        await shutdown_async_recording()

        # Item should have been processed during shutdown
        mock_metrics.observe_request.assert_called()

    @pytest.mark.asyncio
    async def test_shutdown_when_not_started(self):
        """Test shutdown when not started is safe."""
        module = async_recording_module

        module._metric_queue = None
        module._metric_worker_task = None

        # Should not raise
        await shutdown_async_recording()

        assert module._metric_queue is None
        assert module._metric_worker_task is None


class TestWorkerEdgeCases:
    """Tests for edge cases in metric worker."""

    def setup_method(self):
        """Reset state before each test."""
        reset_module_state()

    def teardown_method(self):
        """Clean up after each test."""
        reset_module_state()

    @pytest.mark.asyncio
    async def test_worker_returns_when_queue_none(self):
        """Test _metric_worker returns immediately when queue is None."""
        module = async_recording_module

        module._metric_queue = None

        # This should return immediately without error
        await _metric_worker()

    @pytest.mark.asyncio
    async def test_observe_request_fallback_sync(self):
        """Test observe_request falls back to sync when queue unavailable."""
        module = async_recording_module

        mock_base = MagicMock()
        metrics = AsyncREDMetrics(mock_base)

        # Patch _ensure_worker_started to do nothing but leave queue None
        with patch.object(module, "_ensure_worker_started", return_value=None):
            module._metric_queue = None

            await metrics.observe_request(
                operation="test_op",
                duration_seconds=0.05,
                status="success",
            )

        # Should have called base directly
        mock_base.observe_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_observe_request_queue_full_timeout(self):
        """Test observe_request handles queue full/timeout."""
        module = async_recording_module

        mock_base = MagicMock()
        metrics = AsyncREDMetrics(mock_base, queue_size=1)

        # Set up a pre-filled maxsize=1 queue directly — no real worker needed.
        # Starting a worker and then replacing _metric_queue causes the worker
        # to lose its queue reference, making shutdown_async_recording() hang.
        module._metric_queue = asyncio.Queue(maxsize=1)
        module._metric_queue.put_nowait({"metrics": MagicMock(), "method": "test"})
        module._metric_worker_task = None  # no worker running

        async def _noop() -> None:
            pass

        # Patch _ensure_worker_started so observe_request doesn't spin up a worker
        with patch("obskit.metrics.async_recording._ensure_worker_started", side_effect=_noop), \
             patch("obskit.metrics.async_recording.logger"):
            await metrics.observe_request(
                operation="test_op",
                duration_seconds=0.05,
                status="success",
            )
            # Queue was full → observe_request should have timed out and dropped the metric

        # Clean up without a worker to shut down
        module._metric_queue = None

    @pytest.mark.asyncio
    async def test_worker_timeout_continue(self):
        """Test worker continues on timeout when waiting for queue."""
        module = async_recording_module

        await _ensure_worker_started()

        # The worker should continue waiting after timeout
        # Give it a couple seconds to hit the timeout
        await asyncio.sleep(1.5)

        # Worker should still be running
        assert module._metric_worker_task is not None
        assert not module._metric_worker_task.done()

        await shutdown_async_recording()
