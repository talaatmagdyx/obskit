"""Tests for obskit.decorators.combined module."""

from unittest.mock import patch

import pytest

from obskit.decorators.combined import (
    track_metrics_only,
    track_operation,
    with_observability,
    with_observability_sync,
)
from obskit.decorators.ht_runtime import get_ht_pipeline, reset_ht_pipeline


class TestWithObservability:
    """Tests for with_observability decorator."""

    @pytest.mark.asyncio
    async def test_success(self):
        """Test decorator with successful function."""

        @with_observability(operation="test_op")
        async def successful_function():
            return "success"

        result = await successful_function()
        assert result == "success"

    @pytest.mark.asyncio
    async def test_failure(self):
        """Test decorator with failing function."""

        @with_observability(operation="failing_op")
        async def failing_function():
            raise ValueError("Test error")

        with pytest.raises(ValueError):
            await failing_function()

    @pytest.mark.asyncio
    async def test_preserves_return_value(self):
        """Test that decorator preserves return value."""

        @with_observability(operation="return_test")
        async def returns_dict():
            return {"key": "value", "count": 42}

        result = await returns_dict()
        assert result == {"key": "value", "count": 42}

    @pytest.mark.asyncio
    async def test_preserves_function_name(self):
        """Test that decorator preserves function name."""

        @with_observability(operation="named")
        async def my_named_function():
            return True

        assert my_named_function.__name__ == "my_named_function"


class TestWithObservabilitySync:
    """Tests for with_observability_sync decorator."""

    def test_success(self):
        """Test sync decorator with successful function."""

        @with_observability_sync(operation="sync_test")
        def successful_function():
            return "sync_success"

        result = successful_function()
        assert result == "sync_success"

    def test_failure(self):
        """Test sync decorator with failing function."""

        @with_observability_sync(operation="sync_fail")
        def failing_function():
            raise ValueError("Sync error")

        with pytest.raises(ValueError):
            failing_function()

    def test_preserves_return_value(self):
        """Test that sync decorator preserves return value."""

        @with_observability_sync(operation="sync_return")
        def returns_list():
            return [1, 2, 3]

        result = returns_list()
        assert result == [1, 2, 3]


class TestTrackOperation:
    """Tests for track_operation decorator."""

    @pytest.mark.asyncio
    async def test_async_tracking(self):
        """Test async operation tracking."""

        @track_operation("tracked_async")
        async def tracked_function():
            return "tracked"

        result = await tracked_function()
        assert result == "tracked"

    @pytest.mark.asyncio
    async def test_sync_tracking(self):
        """Test sync operation tracking - decorator returns async."""

        @track_operation("tracked_sync")
        async def tracked_function():
            return "sync_tracked"

        result = await tracked_function()
        assert result == "sync_tracked"


class TestTrackMetricsOnly:
    """Tests for track_metrics_only decorator."""

    @pytest.mark.asyncio
    async def test_async_metrics(self):
        """Test async metrics-only tracking."""

        @track_metrics_only(operation="metrics_async")
        async def metered_function():
            return "metered"

        result = await metered_function()
        assert result == "metered"

    @pytest.mark.asyncio
    async def test_sync_metrics(self):
        """Test sync metrics-only tracking - decorator returns async."""

        @track_metrics_only(operation="metrics_sync")
        async def metered_function():
            return "sync_metered"

        result = await metered_function()
        assert result == "sync_metered"


class TestSampleRate:
    """Tests for the sample_rate parameter on with_observability and with_observability_sync."""

    @pytest.mark.asyncio
    async def test_async_sample_rate_1_always_observes(self):
        """sample_rate=1.0 (default) always runs the full pipeline."""
        call_count = [0]

        @with_observability(operation="sampled_async", sample_rate=1.0)
        async def fn():
            call_count[0] += 1
            return "ok"

        for _ in range(10):
            result = await fn()
            assert result == "ok"
        assert call_count[0] == 10

    @pytest.mark.asyncio
    async def test_async_sample_rate_0_never_observes(self):
        """sample_rate=0.0 skips the pipeline on every call but still executes fn."""
        with patch("obskit.decorators.combined.random.random", return_value=0.99):

            @with_observability(operation="sampled_async_0", sample_rate=0.0)
            async def fn():
                return "result"

            result = await fn()
            assert result == "result"

    @pytest.mark.asyncio
    async def test_async_sample_rate_skips_on_non_sample(self):
        """When random() >= sample_rate, the pipeline is skipped."""
        with patch("obskit.decorators.combined.random.random", return_value=0.5):

            @with_observability(operation="skip_me", sample_rate=0.1)
            async def fn():
                return "raw"

            # random() returns 0.5 which is >= 0.1, so pipeline is skipped
            result = await fn()
            assert result == "raw"

    @pytest.mark.asyncio
    async def test_async_sample_rate_runs_on_sample(self):
        """When random() < sample_rate, the full pipeline runs."""
        with patch("obskit.decorators.combined.random.random", return_value=0.05):

            @with_observability(operation="observe_me", sample_rate=0.1)
            async def fn():
                return "instrumented"

            result = await fn()
            assert result == "instrumented"

    def test_sync_sample_rate_1_always_observes(self):
        """sample_rate=1.0 on sync decorator always runs pipeline."""
        call_count = [0]

        @with_observability_sync(operation="sync_sampled", sample_rate=1.0)
        def fn():
            call_count[0] += 1
            return "ok"

        for _ in range(5):
            assert fn() == "ok"
        assert call_count[0] == 5

    def test_sync_sample_rate_skips_on_non_sample(self):
        """When random() >= sample_rate, sync pipeline is skipped."""
        with patch("obskit.decorators.combined.random.random", return_value=0.9):

            @with_observability_sync(operation="sync_skip", sample_rate=0.1)
            def fn():
                return "raw_sync"

            assert fn() == "raw_sync"

    def test_sync_sample_rate_runs_on_sample(self):
        """When random() < sample_rate, sync pipeline runs."""
        with patch("obskit.decorators.combined.random.random", return_value=0.01):

            @with_observability_sync(operation="sync_observe", sample_rate=0.1)
            def fn():
                return "instrumented_sync"

            assert fn() == "instrumented_sync"

    @pytest.mark.asyncio
    async def test_async_exception_propagated_when_sampled(self):
        """Exceptions in sampled calls still propagate correctly."""
        with patch("obskit.decorators.combined.random.random", return_value=0.0):

            @with_observability(operation="exc_sampled", sample_rate=1.0)
            async def fn():
                raise ValueError("boom")

            with pytest.raises(ValueError, match="boom"):
                await fn()

    @pytest.mark.asyncio
    async def test_async_exception_propagated_when_not_sampled(self):
        """Exceptions in non-sampled calls still propagate correctly."""
        with patch("obskit.decorators.combined.random.random", return_value=0.99):

            @with_observability(operation="exc_not_sampled", sample_rate=0.1)
            async def fn():
                raise RuntimeError("skip but still raise")

            with pytest.raises(RuntimeError, match="skip but still raise"):
                await fn()


class TestHighThroughputMode:
    """Tests for with_observability(high_throughput=True) and sync variant."""

    def setup_method(self):
        reset_ht_pipeline()

    def teardown_method(self):
        reset_ht_pipeline()

    # ------------------------------------------------------------------
    # Async decorator
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_async_returns_correct_value(self):
        """high_throughput=True still returns the function's return value."""

        @with_observability(component="HT", high_throughput=True)
        async def fn():
            return "ht_result"

        assert await fn() == "ht_result"

    @pytest.mark.asyncio
    async def test_async_exception_propagates(self):
        """Exceptions are re-raised unchanged in high-throughput mode."""

        @with_observability(component="HT", high_throughput=True)
        async def fn():
            raise ValueError("ht_error")

        with pytest.raises(ValueError, match="ht_error"):
            await fn()

    @pytest.mark.asyncio
    async def test_async_buffers_success_metric(self):
        """A successful HT call buffers a 'success' count in the aggregator."""

        @with_observability(operation="ht_success_op", high_throughput=True)
        async def fn():
            return 42

        await fn()
        counts = get_ht_pipeline()._agg.get_pending_counts()
        assert counts.get(("ht_success_op", "success"), 0) == 1

    @pytest.mark.asyncio
    async def test_async_buffers_failure_metric(self):
        """A failing HT call buffers a 'failure' count in the aggregator."""

        @with_observability(operation="ht_fail_op", high_throughput=True)
        async def fn():
            raise RuntimeError("fail")

        with pytest.raises(RuntimeError):
            await fn()

        counts = get_ht_pipeline()._agg.get_pending_counts()
        assert counts.get(("ht_fail_op", "failure"), 0) == 1

    @pytest.mark.asyncio
    async def test_async_enqueues_log_record(self):
        """A HT call puts a log record in the async ring buffer."""

        @with_observability(component="HT", operation="ht_log_op", high_throughput=True)
        async def fn():
            return "ok"

        await fn()
        assert get_ht_pipeline()._ring.qsize >= 1

    @pytest.mark.asyncio
    async def test_async_sample_rate_gate_respected(self):
        """sample_rate gate fires before the high_throughput path."""
        with patch("obskit.decorators.combined.random.random", return_value=0.99):

            @with_observability(operation="ht_sampled", high_throughput=True, sample_rate=0.1)
            async def fn():
                return "not_instrumented"

            # random() >= sample_rate → skip pipeline; function still executes
            assert await fn() == "not_instrumented"
            # Pipeline never started → _agg is None, so no metrics buffered
            pipeline = get_ht_pipeline()
            counts = pipeline._agg.get_pending_counts() if pipeline._agg is not None else {}
            assert counts.get(("ht_sampled", "success"), 0) == 0

    @pytest.mark.asyncio
    async def test_async_preserves_function_name(self):
        """@wraps is applied: __name__ is preserved."""

        @with_observability(component="HT", high_throughput=True)
        async def my_special_fn():
            return None

        assert my_special_fn.__name__ == "my_special_fn"

    # ------------------------------------------------------------------
    # Sync decorator
    # ------------------------------------------------------------------

    def test_sync_returns_correct_value(self):
        """with_observability_sync high_throughput=True returns correct value."""

        @with_observability_sync(component="HT", high_throughput=True)
        def fn():
            return "sync_ht"

        assert fn() == "sync_ht"

    def test_sync_exception_propagates(self):
        """Exceptions are re-raised unchanged in sync high-throughput mode."""

        @with_observability_sync(component="HT", high_throughput=True)
        def fn():
            raise TypeError("sync_ht_error")

        with pytest.raises(TypeError, match="sync_ht_error"):
            fn()

    def test_sync_buffers_success_metric(self):
        """Sync HT success call is counted as 'success'."""

        @with_observability_sync(operation="sync_ht_op", high_throughput=True)
        def fn():
            return 1

        fn()
        counts = get_ht_pipeline()._agg.get_pending_counts()
        assert counts.get(("sync_ht_op", "success"), 0) == 1

    def test_sync_buffers_failure_metric(self):
        """Sync HT failure call is counted as 'failure'."""

        @with_observability_sync(operation="sync_ht_fail", high_throughput=True)
        def fn():
            raise ValueError("sync_fail")

        with pytest.raises(ValueError):
            fn()

        counts = get_ht_pipeline()._agg.get_pending_counts()
        assert counts.get(("sync_ht_fail", "failure"), 0) == 1

    def test_sync_sample_rate_gate_respected(self):
        """sample_rate gate fires before the sync high_throughput path."""
        with patch("obskit.decorators.combined.random.random", return_value=0.99):

            @with_observability_sync(
                operation="sync_ht_sampled", high_throughput=True, sample_rate=0.1
            )
            def fn():
                return "skipped"

            assert fn() == "skipped"
            pipeline = get_ht_pipeline()
            counts = pipeline._agg.get_pending_counts() if pipeline._agg is not None else {}
            assert counts.get(("sync_ht_sampled", "success"), 0) == 0


class TestTrackMetricsFalseErrorPath:
    """Tests for track_metrics=False in error paths (lines 354->366, 532->541)."""

    @pytest.mark.asyncio
    async def test_async_no_metrics_on_failure(self):
        """with_observability track_metrics=False does not call observe_request on error.

        This covers branch 354->366: the else branch of if track_metrics: in the
        async wrapper except clause.
        """
        from unittest.mock import patch

        with patch("obskit.decorators.combined.get_red_metrics") as mock_red:

            @with_observability(operation="no_metric_fail", track_metrics=False)
            async def fn():
                raise ValueError("no metrics please")

            with pytest.raises(ValueError):
                await fn()
        mock_red.return_value.observe_request.assert_not_called()

    def test_sync_no_metrics_on_failure(self):
        """with_observability_sync track_metrics=False does not call observe_request on error.

        This covers branch 532->541: the else branch of if track_metrics: in the
        sync wrapper except clause.
        """
        from unittest.mock import patch

        with patch("obskit.decorators.combined.get_red_metrics") as mock_red:

            @with_observability_sync(operation="sync_no_metric_fail", track_metrics=False)
            def fn():
                raise RuntimeError("sync no metrics")

            with pytest.raises(RuntimeError):
                fn()
        mock_red.return_value.observe_request.assert_not_called()


class TestTrackOperationErrorPath:
    """Tests for track_operation exception path (lines 648-659)."""

    @pytest.mark.asyncio
    async def test_exception_is_logged_and_reraised(self):
        """track_operation logs error and re-raises exception (lines 648-659)."""

        @track_operation(component="TestComp", operation="err_op")
        async def fn():
            raise TypeError("track_op_error")

        with pytest.raises(TypeError, match="track_op_error"):
            await fn()

    @pytest.mark.asyncio
    async def test_exception_type_is_preserved(self):
        """track_operation re-raises the original exception type."""

        @track_operation(component="TestComp", operation="type_preserve")
        async def fn():
            raise KeyError("missing_key")

        with pytest.raises(KeyError):
            await fn()

    @pytest.mark.asyncio
    async def test_success_still_works(self):
        """track_operation works normally on success path."""

        @track_operation(component="TestComp", operation="ok_op")
        async def fn():
            return 42

        result = await fn()
        assert result == 42


class TestTrackMetricsOnlyErrorPath:
    """Tests for track_metrics_only exception path (lines 758-769)."""

    @pytest.mark.asyncio
    async def test_exception_records_failure_metric_and_reraises(self):
        """track_metrics_only records failure metric and re-raises (lines 758-769)."""
        from unittest.mock import patch

        with patch("obskit.decorators.combined.get_red_metrics") as mock_red:

            @track_metrics_only(operation="metrics_fail_op")
            async def fn():
                raise ValueError("metrics_only_error")

            with pytest.raises(ValueError, match="metrics_only_error"):
                await fn()

        mock_red.return_value.observe_request.assert_called_once()
        call_kwargs = mock_red.return_value.observe_request.call_args.kwargs
        assert call_kwargs["status"] == "failure"
        assert call_kwargs["operation"] == "metrics_fail_op"
        assert call_kwargs["error_type"] == "ValueError"

    @pytest.mark.asyncio
    async def test_exception_type_preserved(self):
        """track_metrics_only re-raises the original exception type."""

        @track_metrics_only(operation="metrics_type_err")
        async def fn():
            raise RuntimeError("keep_this_type")

        with pytest.raises(RuntimeError, match="keep_this_type"):
            await fn()


class TestAsyncNullContext:
    """Tests for _AsyncNullContext class (lines 791, 795)."""

    @pytest.mark.asyncio
    async def test_aenter_returns_none(self):
        """_AsyncNullContext.__aenter__ executes (line 791)."""
        from obskit.decorators.combined import _AsyncNullContext

        ctx = _AsyncNullContext()
        result = await ctx.__aenter__()
        assert result is None

    @pytest.mark.asyncio
    async def test_aexit_returns_none(self):
        """_AsyncNullContext.__aexit__ executes (line 795)."""
        from obskit.decorators.combined import _AsyncNullContext

        ctx = _AsyncNullContext()
        result = await ctx.__aexit__(None, None, None)
        assert result is None

    @pytest.mark.asyncio
    async def test_used_as_async_context_manager(self):
        """_AsyncNullContext can be used as async context manager."""
        from obskit.decorators.combined import _AsyncNullContext

        async with _AsyncNullContext():
            pass  # must not raise
