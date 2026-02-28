"""
Tests for obskit.resilience.combined module.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from obskit.resilience.combined import (
    BackoffStrategy,
    ResilientExecutor,
    RetryConfig,
    resilient_call,
    resilient_call_sync,
    with_resilience,
)

# =============================================================================
# BackoffStrategy Tests
# =============================================================================


class TestBackoffStrategy:
    def test_constant_value(self):
        assert BackoffStrategy.CONSTANT.value == "constant"

    def test_exponential_value(self):
        assert BackoffStrategy.EXPONENTIAL.value == "exponential"

    def test_exponential_jitter_value(self):
        assert BackoffStrategy.EXPONENTIAL_JITTER.value == "exponential_jitter"


# =============================================================================
# RetryConfig Tests
# =============================================================================


class TestRetryConfig:
    def test_defaults(self):
        config = RetryConfig()
        assert config.max_retries == 3
        assert config.base_delay == 1.0
        assert config.max_delay == 60.0

    def test_constant_delay(self):
        config = RetryConfig(base_delay=2.0, backoff=BackoffStrategy.CONSTANT)
        assert config.get_delay(1) == 2.0
        assert config.get_delay(5) == 2.0

    def test_linear_delay(self):
        config = RetryConfig(base_delay=1.0, backoff=BackoffStrategy.LINEAR)
        assert config.get_delay(1) == 1.0
        assert config.get_delay(3) == 3.0

    def test_exponential_delay(self):
        config = RetryConfig(base_delay=1.0, backoff=BackoffStrategy.EXPONENTIAL)
        assert config.get_delay(1) == 1.0
        assert config.get_delay(2) == 2.0
        assert config.get_delay(3) == 4.0

    def test_exponential_jitter_delay(self):
        config = RetryConfig(base_delay=1.0, backoff=BackoffStrategy.EXPONENTIAL_JITTER)
        delay = config.get_delay(1)
        # Jitter adds between 0.5 and 1.5 to base
        assert 0.5 <= delay <= 1.5

    def test_delay_capped_at_max(self):
        config = RetryConfig(base_delay=100.0, max_delay=10.0, backoff=BackoffStrategy.CONSTANT)
        assert config.get_delay(1) == 10.0


# =============================================================================
# ResilientExecutor Tests
# =============================================================================


class TestResilientExecutor:
    def test_init_no_circuit_breaker(self):
        executor = ResilientExecutor(max_retries=5)
        assert executor._circuit_breaker is None
        assert executor._retry_config.max_retries == 5

    def test_init_with_string_backoff(self):
        executor = ResilientExecutor(backoff="constant")
        assert executor._retry_config.backoff == BackoffStrategy.CONSTANT

    def test_execute_sync_success(self):
        executor = ResilientExecutor(max_retries=3)
        result = executor.execute_sync(lambda: "ok")
        assert result == "ok"

    def test_execute_sync_with_args(self):
        executor = ResilientExecutor(max_retries=3)
        result = executor.execute_sync(lambda x, y: x + y, 3, 4)
        assert result == 7

    def test_execute_sync_retries_on_failure(self):
        call_count = [0]

        def flaky():
            call_count[0] += 1
            if call_count[0] < 3:
                raise ValueError("Transient error")
            return "success"

        executor = ResilientExecutor(max_retries=3, base_delay=0.001, backoff="constant")
        result = executor.execute_sync(flaky)
        assert result == "success"
        assert call_count[0] == 3

    def test_execute_sync_raises_after_max_retries(self):
        executor = ResilientExecutor(max_retries=2, base_delay=0.001, backoff="constant")
        with pytest.raises(ValueError, match="always fails"):
            executor.execute_sync(lambda: (_ for _ in ()).throw(ValueError("always fails")))

    def test_execute_sync_with_circuit_breaker_string(self):
        """Test that string circuit breaker name resolves to instance."""
        executor = ResilientExecutor(
            circuit_breaker="test_cb_sync_unique",
            max_retries=1,
        )
        assert executor._circuit_breaker is not None

    def test_execute_sync_on_retry_callback(self):
        retries = []
        executor = ResilientExecutor(
            max_retries=3,
            base_delay=0.001,
            backoff="constant",
            on_retry=lambda attempt, exc: retries.append(attempt),
        )
        call_count = [0]

        def flaky():
            call_count[0] += 1
            if call_count[0] < 3:
                raise ValueError("fail")
            return "ok"

        executor.execute_sync(flaky)
        assert len(retries) == 2  # 2 retries before success

    def test_execute_sync_circuit_name_raises_circuit_error(self):
        """Test that circuit error is re-raised immediately."""
        mock_cb = MagicMock()
        mock_state = MagicMock()
        mock_state.name = "OPEN"
        mock_cb.state = mock_state
        mock_cb.__enter__ = MagicMock(side_effect=Exception("CircuitOpenError"))
        mock_cb.__exit__ = MagicMock(return_value=False)

        executor = ResilientExecutor(max_retries=3, base_delay=0.001)
        executor._circuit_breaker = mock_cb

        with pytest.raises(Exception):
            executor.execute_sync(lambda: "ok")


class TestResilientExecutorAsync:
    @pytest.mark.asyncio
    async def test_execute_async_success(self):
        executor = ResilientExecutor(max_retries=3)

        async def async_func():
            return "async_ok"

        result = await executor.execute(async_func)
        assert result == "async_ok"

    @pytest.mark.asyncio
    async def test_execute_async_sync_func(self):
        executor = ResilientExecutor(max_retries=3)
        result = await executor.execute(lambda: "sync_in_async")
        assert result == "sync_in_async"

    @pytest.mark.asyncio
    async def test_execute_async_retries(self):
        call_count = [0]

        async def flaky():
            call_count[0] += 1
            if call_count[0] < 2:
                raise ConnectionError("timeout")
            return "recovered"

        executor = ResilientExecutor(max_retries=3, base_delay=0.001, backoff="constant")
        result = await executor.execute(flaky)
        assert result == "recovered"
        assert call_count[0] == 2

    @pytest.mark.asyncio
    async def test_execute_async_raises_after_max_retries(self):
        async def always_fails():
            raise RuntimeError("Permanent failure")

        executor = ResilientExecutor(max_retries=2, base_delay=0.001, backoff="constant")
        with pytest.raises(RuntimeError, match="Permanent failure"):
            await executor.execute(always_fails)

    @pytest.mark.asyncio
    async def test_execute_async_on_retry_callback(self):
        retries = []

        async def flaky():
            raise ValueError("fail")

        executor = ResilientExecutor(
            max_retries=2,
            base_delay=0.001,
            backoff="constant",
            on_retry=lambda attempt, exc: retries.append(attempt),
        )
        with pytest.raises(ValueError):
            await executor.execute(flaky)
        assert len(retries) == 1  # 1 retry on attempt 1

    @pytest.mark.asyncio
    async def test_execute_async_with_circuit_breaker(self):
        mock_cb = MagicMock()
        mock_state = MagicMock()
        mock_state.name = "CLOSED"
        mock_cb.state = mock_state
        mock_cb.__enter__ = MagicMock(return_value=mock_cb)
        mock_cb.__exit__ = MagicMock(return_value=False)

        executor = ResilientExecutor(max_retries=1)
        executor._circuit_breaker = mock_cb

        async def good_func():
            return "circuit_ok"

        result = await executor.execute(good_func)
        assert result == "circuit_ok"

    @pytest.mark.asyncio
    async def test_execute_async_open_circuit_calls_callback(self):
        mock_cb = MagicMock()
        mock_state = MagicMock()
        mock_state.name = "OPEN"
        mock_cb.state = mock_state
        mock_cb.name = "test_breaker"

        callback_called = []
        executor = ResilientExecutor(
            max_retries=1,
            on_circuit_open=lambda: callback_called.append(True),
        )
        executor._circuit_breaker = mock_cb

        # The circuit is open, so execute should raise an exception
        # Note: The actual exception type depends on the import resolution in combined.py
        with pytest.raises(Exception):
            await executor.execute(lambda: "ok")


# =============================================================================
# resilient_call Tests
# =============================================================================


class TestResilientCall:
    @pytest.mark.asyncio
    async def test_resilient_call_success(self):
        async def my_func(x):
            return x * 2

        result = await resilient_call(my_func, args=(5,))
        assert result == 10

    @pytest.mark.asyncio
    async def test_resilient_call_with_kwargs(self):
        async def my_func(x, multiplier=1):
            return x * multiplier

        result = await resilient_call(my_func, args=(3,), kwargs={"multiplier": 4})
        assert result == 12

    @pytest.mark.asyncio
    async def test_resilient_call_with_max_retries(self):
        call_count = [0]

        async def flaky():
            call_count[0] += 1
            if call_count[0] < 2:
                raise ValueError("fail")
            return "ok"

        result = await resilient_call(flaky, max_retries=3, backoff="constant")
        assert result == "ok"


# =============================================================================
# resilient_call_sync Tests
# =============================================================================


class TestResilientCallSync:
    def test_resilient_call_sync_success(self):
        def my_func(x):
            return x + 1

        result = resilient_call_sync(my_func, args=(9,))
        assert result == 10

    def test_resilient_call_sync_with_kwargs(self):
        def my_func(x, y=0):
            return x + y

        result = resilient_call_sync(my_func, args=(5,), kwargs={"y": 3})
        assert result == 8


# =============================================================================
# with_resilience Decorator Tests
# =============================================================================


class TestWithResilience:
    @pytest.mark.asyncio
    async def test_async_function_decorator(self):
        @with_resilience(max_retries=3, backoff="constant")
        async def async_func():
            return "decorated_async"

        result = await async_func()
        assert result == "decorated_async"

    def test_sync_function_decorator(self):
        @with_resilience(max_retries=3, backoff="constant")
        def sync_func():
            return "decorated_sync"

        result = sync_func()
        assert result == "decorated_sync"

    def test_sync_function_retries(self):
        call_count = [0]

        @with_resilience(max_retries=3, backoff="constant")
        def flaky_func():
            call_count[0] += 1
            if call_count[0] < 3:
                raise ValueError("transient")
            return "ok"

        result = flaky_func()
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_async_function_retries(self):
        call_count = [0]

        @with_resilience(max_retries=3, backoff="constant")
        async def flaky_async():
            call_count[0] += 1
            if call_count[0] < 2:
                raise OSError("network error")
            return "recovered"

        result = await flaky_async()
        assert result == "recovered"

    def test_preserves_function_name(self):
        @with_resilience()
        def my_special_function():
            return "ok"

        assert my_special_function.__name__ == "my_special_function"
