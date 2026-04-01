"""Tests for obskit.decorators.context_managers (observe / observe_sync)."""

from unittest.mock import patch

import pytest

from obskit.decorators.context_managers import observe, observe_sync
from obskit.decorators._ht_pipeline import get_ht_pipeline, reset_ht_pipeline

# =============================================================================
# Async context manager — observe()
# =============================================================================


class TestObserve:
    """Tests for the observe() async context manager / decorator."""

    def setup_method(self):
        reset_ht_pipeline()

    def teardown_method(self):
        reset_ht_pipeline()

    # ------------------------------------------------------------------
    # Basic context manager behaviour
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_success_block_executes(self):
        """Body of the context manager runs without error."""
        ran = []
        async with observe(operation="cm_success", component="Test"):
            ran.append(1)
        assert ran == [1]

    @pytest.mark.asyncio
    async def test_exception_propagates(self):
        """An exception raised inside the block propagates out."""
        with pytest.raises(ValueError, match="cm_error"):
            async with observe(operation="cm_fail", component="Test"):
                raise ValueError("cm_error")

    @pytest.mark.asyncio
    async def test_side_effects_visible_after_block(self):
        """Variables mutated inside the block are visible after."""
        result = []
        async with observe(operation="side_effect"):
            result.append("done")
        assert result == ["done"]

    # ------------------------------------------------------------------
    # High-throughput path
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_high_throughput_success_buffers_metric(self):
        """HT path enqueues a log record in the ring buffer on success."""
        async with observe(operation="ht_cm_success", high_throughput=True):
            pass  # NOSONAR
        assert get_ht_pipeline()._ring.qsize >= 1

    @pytest.mark.asyncio
    async def test_high_throughput_failure_buffers_metric(self):
        """HT path enqueues a log record in the ring buffer on failure."""
        with pytest.raises(RuntimeError):
            async with observe(operation="ht_cm_fail", high_throughput=True):
                raise RuntimeError("fail")
        assert get_ht_pipeline()._ring.qsize >= 1

    @pytest.mark.asyncio
    async def test_high_throughput_enqueues_log_record(self):
        """HT path puts a log record in the ring buffer."""
        async with observe(operation="ht_cm_log", component="C", high_throughput=True):
            pass  # NOSONAR
        assert get_ht_pipeline()._ring.qsize >= 1

    # ------------------------------------------------------------------
    # Sampling gate
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_sample_rate_gate_skips_pipeline(self):
        """When random() >= sample_rate the pipeline is skipped; body still runs."""
        ran = []
        with patch("obskit.decorators.context_managers.random.random", return_value=0.99):
            async with observe(operation="skipped", high_throughput=True, sample_rate=0.1):
                ran.append(1)
        assert ran == [1]
        # Pipeline was never started → _ring is None
        pipeline = get_ht_pipeline()
        assert pipeline._ring is None

    @pytest.mark.asyncio
    async def test_sample_rate_gate_runs_pipeline(self):
        """When random() < sample_rate the HT pipeline runs."""
        with patch("obskit.decorators.context_managers.random.random", return_value=0.05):
            async with observe(operation="sampled_in", high_throughput=True, sample_rate=0.1):
                pass  # NOSONAR
        assert get_ht_pipeline()._ring.qsize >= 1

    # ------------------------------------------------------------------
    # Used as an async decorator
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_as_async_decorator_success(self):
        """@observe(...) works as a decorator on an async function."""

        @observe(operation="dec_async", high_throughput=True)
        async def fn():
            return "decorated"

        result = await fn()
        assert result == "decorated"

    @pytest.mark.asyncio
    async def test_as_async_decorator_exception_propagates(self):
        """Exceptions inside a decorated async function still propagate."""

        @observe(operation="dec_async_fail", high_throughput=True)
        async def fn():
            raise TypeError("dec_error")

        with pytest.raises(TypeError, match="dec_error"):
            await fn()

    @pytest.mark.asyncio
    async def test_as_async_decorator_buffers_metric(self):
        """@observe decorator enqueues log record in ring buffer."""

        @observe(operation="dec_async_metric", high_throughput=True)
        async def fn():
            return 1

        await fn()
        assert get_ht_pipeline()._ring.qsize >= 1

    # ------------------------------------------------------------------
    # Standard path (non-HT)
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_standard_path_records_success_metric(self):
        """Standard path calls observe_request with 'success' status."""
        with patch("obskit.decorators.context_managers.get_red_metrics") as mock_red:
            async with observe(operation="std_success", component="C"):
                pass  # NOSONAR
        mock_red.return_value.observe_request.assert_called_once()
        kwargs = mock_red.return_value.observe_request.call_args.kwargs
        assert kwargs["operation"] == "std_success"
        assert kwargs["status"] == "success"

    @pytest.mark.asyncio
    async def test_standard_path_records_failure_metric(self):
        """Standard path calls observe_request with 'failure' status on exception."""
        with patch("obskit.decorators.context_managers.get_red_metrics") as mock_red:
            with pytest.raises(ValueError):
                async with observe(operation="std_fail", component="C"):
                    raise ValueError("fail")
        kwargs = mock_red.return_value.observe_request.call_args.kwargs
        assert kwargs["status"] == "failure"

    @pytest.mark.asyncio
    async def test_track_metrics_false_skips_metric(self):
        """With track_metrics=False no metric is recorded on standard path."""
        with patch("obskit.decorators.context_managers.get_red_metrics") as mock_red:
            async with observe(operation="no_metric", track_metrics=False):
                pass  # NOSONAR
        mock_red.return_value.observe_request.assert_not_called()

    @pytest.mark.asyncio
    async def test_default_operation_name(self):
        """When operation is omitted the default 'unnamed_operation' is used."""
        with patch("obskit.decorators.context_managers.get_red_metrics") as mock_red:
            async with observe():
                pass  # NOSONAR
        kwargs = mock_red.return_value.observe_request.call_args.kwargs
        assert kwargs["operation"] == "unnamed_operation"

    @pytest.mark.asyncio
    async def test_standard_path_extra_context_does_not_raise(self):
        """Extra keyword context is forwarded without raising."""
        async with observe(operation="ctx_op", tenant_id="t-1", region="eu"):
            pass  # must not raise

    @pytest.mark.asyncio
    async def test_log_start_emits_debug_log(self):
        """log_start=True causes a debug log before the body executes."""
        with patch("obskit.decorators.context_managers.logger") as mock_logger:
            async with observe(operation="log_start_op", log_start=True):
                pass  # NOSONAR
        mock_logger.debug.assert_called_once_with(
            "operation_started",
            component="unknown",
            operation="log_start_op",
        )

    @pytest.mark.asyncio
    async def test_log_start_false_no_debug_log(self):
        """log_start=False (default) does not emit a debug log."""
        with patch("obskit.decorators.context_managers.logger") as mock_logger:
            async with observe(operation="no_log_start_op"):
                pass  # NOSONAR
        mock_logger.debug.assert_not_called()


# =============================================================================
# Sync context manager — observe_sync()
# =============================================================================


class TestObserveSync:
    """Tests for the observe_sync() sync context manager / decorator."""

    def setup_method(self):
        reset_ht_pipeline()

    def teardown_method(self):
        reset_ht_pipeline()

    # ------------------------------------------------------------------
    # Basic context manager behaviour
    # ------------------------------------------------------------------

    def test_success_block_executes(self):
        """Body of the sync context manager runs without error."""
        ran = []
        with observe_sync(operation="sync_cm_success", component="Test"):
            ran.append(1)
        assert ran == [1]

    def test_exception_propagates(self):
        """An exception raised inside the block propagates out."""
        with pytest.raises(ValueError, match="sync_cm_error"):
            with observe_sync(operation="sync_cm_fail", component="Test"):
                raise ValueError("sync_cm_error")

    def test_side_effects_visible_after_block(self):
        """Variables mutated inside the block are visible after."""
        result = []
        with observe_sync(operation="sync_side_effect"):
            result.append("done")
        assert result == ["done"]

    # ------------------------------------------------------------------
    # High-throughput path
    # ------------------------------------------------------------------

    def test_high_throughput_success_buffers_metric(self):
        """HT path enqueues a log record in the ring buffer on success."""
        with observe_sync(operation="sync_ht_cm_success", high_throughput=True):
            pass  # NOSONAR
        assert get_ht_pipeline()._ring.qsize >= 1

    def test_high_throughput_failure_buffers_metric(self):
        """HT path enqueues a log record in the ring buffer on failure."""
        with pytest.raises(RuntimeError):
            with observe_sync(operation="sync_ht_cm_fail", high_throughput=True):
                raise RuntimeError("sync_fail")
        assert get_ht_pipeline()._ring.qsize >= 1

    def test_high_throughput_enqueues_log_record(self):
        """HT path puts a log record in the ring buffer."""
        with observe_sync(operation="sync_ht_cm_log", component="C", high_throughput=True):
            pass  # NOSONAR
        assert get_ht_pipeline()._ring.qsize >= 1

    # ------------------------------------------------------------------
    # Sampling gate
    # ------------------------------------------------------------------

    def test_sample_rate_gate_skips_pipeline(self):
        """When random() >= sample_rate the pipeline is skipped; body still runs."""
        ran = []
        with patch("obskit.decorators.context_managers.random.random", return_value=0.99):
            with observe_sync(operation="sync_skipped", high_throughput=True, sample_rate=0.1):
                ran.append(1)
        assert ran == [1]
        # Pipeline was never started → _ring is None
        pipeline = get_ht_pipeline()
        assert pipeline._ring is None

    def test_sample_rate_gate_runs_pipeline(self):
        """When random() < sample_rate the HT pipeline runs."""
        with patch("obskit.decorators.context_managers.random.random", return_value=0.05):
            with observe_sync(operation="sync_sampled_in", high_throughput=True, sample_rate=0.1):
                pass  # NOSONAR
        assert get_ht_pipeline()._ring.qsize >= 1

    # ------------------------------------------------------------------
    # Used as a sync decorator
    # ------------------------------------------------------------------

    def test_as_sync_decorator_success(self):
        """@observe_sync(...) works as a decorator on a sync function."""

        @observe_sync(operation="dec_sync", high_throughput=True)
        def fn():
            return "decorated_sync"

        result = fn()
        assert result == "decorated_sync"

    def test_as_sync_decorator_exception_propagates(self):
        """Exceptions inside a decorated sync function still propagate."""

        @observe_sync(operation="dec_sync_fail", high_throughput=True)
        def fn():
            raise TypeError("dec_sync_error")

        with pytest.raises(TypeError, match="dec_sync_error"):
            fn()

    def test_as_sync_decorator_buffers_metric(self):
        """@observe_sync decorator enqueues log record in ring buffer."""

        @observe_sync(operation="dec_sync_metric", high_throughput=True)
        def fn():
            return 1

        fn()
        assert get_ht_pipeline()._ring.qsize >= 1

    def test_as_sync_decorator_multiple_calls(self):
        """Decorated function can be called multiple times correctly."""
        call_count = [0]

        @observe_sync(operation="dec_sync_multi", high_throughput=True)
        def fn():
            call_count[0] += 1
            return call_count[0]

        assert fn() == 1
        assert fn() == 2
        assert get_ht_pipeline()._ring.qsize >= 2

    # ------------------------------------------------------------------
    # Standard path (non-HT)
    # ------------------------------------------------------------------

    def test_standard_path_records_success_metric(self):
        """Standard path calls observe_request with 'success' status."""
        with patch("obskit.decorators.context_managers.get_red_metrics") as mock_red:
            with observe_sync(operation="sync_std_success", component="C"):
                pass  # NOSONAR
        mock_red.return_value.observe_request.assert_called_once()
        kwargs = mock_red.return_value.observe_request.call_args.kwargs
        assert kwargs["operation"] == "sync_std_success"
        assert kwargs["status"] == "success"

    def test_standard_path_records_failure_metric(self):
        """Standard path calls observe_request with 'failure' status on exception."""
        with patch("obskit.decorators.context_managers.get_red_metrics") as mock_red:
            with pytest.raises(ValueError):
                with observe_sync(operation="sync_std_fail", component="C"):
                    raise ValueError("fail")
        kwargs = mock_red.return_value.observe_request.call_args.kwargs
        assert kwargs["status"] == "failure"

    def test_track_metrics_false_skips_metric(self):
        """With track_metrics=False no metric is recorded on standard path."""
        with patch("obskit.decorators.context_managers.get_red_metrics") as mock_red:
            with observe_sync(operation="sync_no_metric", track_metrics=False):
                pass  # NOSONAR
        mock_red.return_value.observe_request.assert_not_called()

    def test_default_operation_name(self):
        """When operation is omitted the default 'unnamed_operation' is used."""
        with patch("obskit.decorators.context_managers.get_red_metrics") as mock_red:
            with observe_sync():
                pass  # NOSONAR
        kwargs = mock_red.return_value.observe_request.call_args.kwargs
        assert kwargs["operation"] == "unnamed_operation"

    def test_standard_path_extra_context_does_not_raise(self):
        """Extra keyword context is forwarded without raising."""
        with observe_sync(operation="sync_ctx_op", tenant_id="t-1", region="eu"):
            pass  # must not raise

    def test_log_start_emits_debug_log(self):
        """log_start=True causes a debug log before the body executes."""
        with patch("obskit.decorators.context_managers.logger") as mock_logger:
            with observe_sync(operation="sync_log_start_op", log_start=True):
                pass  # NOSONAR
        mock_logger.debug.assert_called_once_with(
            "operation_started",
            component="unknown",
            operation="sync_log_start_op",
        )

    def test_log_start_false_no_debug_log(self):
        """log_start=False (default) does not emit a debug log."""
        with patch("obskit.decorators.context_managers.logger") as mock_logger:
            with observe_sync(operation="sync_no_log_start_op"):
                pass  # NOSONAR
        mock_logger.debug.assert_not_called()


class TestObserveTrackMetricsFalseErrorPath:
    """Tests covering the track_metrics=False error branch in observe (line 178->186)."""

    @pytest.mark.asyncio
    async def test_async_observe_no_metric_on_error(self):
        """observe with track_metrics=False does not record metric on exception.

        This covers branch 178->186: the False branch of if track_metrics: inside
        the observe async context manager exception handler.
        """
        from unittest.mock import patch

        from obskit.decorators.context_managers import observe

        with patch("obskit.decorators.context_managers.get_red_metrics") as mock_red:
            with pytest.raises(ValueError):
                async with observe(operation="async_no_metric_fail", track_metrics=False):
                    raise ValueError("async no metric error")
        mock_red.return_value.observe_request.assert_not_called()

    @pytest.mark.asyncio
    async def test_async_observe_no_metric_still_logs_error(self):
        """observe with track_metrics=False still logs error even without metrics."""
        from unittest.mock import patch

        from obskit.decorators.context_managers import observe

        with patch("obskit.decorators.context_managers.log_error") as mock_log_error:
            with pytest.raises(RuntimeError):
                async with observe(operation="async_no_metric_log", track_metrics=False):
                    raise RuntimeError("should still log")
        mock_log_error.assert_called_once()


class TestObserveSyncTrackMetricsFalseErrorPath:
    """Tests covering track_metrics=False error branch in observe_sync (line 322->330)."""

    def test_sync_observe_no_metric_on_error(self):
        """observe_sync with track_metrics=False does not record metric on exception.

        This covers branch 322->330: the False branch of if track_metrics: inside
        the observe_sync context manager exception handler.
        """
        from unittest.mock import patch

        from obskit.decorators.context_managers import observe_sync

        with patch("obskit.decorators.context_managers.get_red_metrics") as mock_red:
            with pytest.raises(ValueError):
                with observe_sync(operation="sync_no_metric_fail", track_metrics=False):
                    raise ValueError("sync no metric error")
        mock_red.return_value.observe_request.assert_not_called()

    def test_sync_observe_no_metric_still_logs_error(self):
        """observe_sync with track_metrics=False still calls log_error."""
        from unittest.mock import patch

        from obskit.decorators.context_managers import observe_sync

        with patch("obskit.decorators.context_managers.log_error") as mock_log_error:
            with pytest.raises(RuntimeError):
                with observe_sync(operation="sync_no_metric_log", track_metrics=False):
                    raise RuntimeError("sync log without metric")
        mock_log_error.assert_called_once()
