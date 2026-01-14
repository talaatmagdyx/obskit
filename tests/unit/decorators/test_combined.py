"""Tests for obskit.decorators.combined module."""

import pytest

from obskit.decorators.combined import (
    track_metrics_only,
    track_operation,
    with_observability,
    with_observability_sync,
)


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
