"""Tests to cover branch misses in resilience/adaptive.py, combined.py, factory.py."""

from __future__ import annotations

import asyncio
import time

import pytest


class TestAdaptiveRetryBranchCoverage:
    """Cover missing branches in resilience/adaptive.py."""

    def test_update_metrics_cooldown_not_elapsed(self):
        """Line 183->exit: cooldown not elapsed so _adapt is NOT called."""
        from obskit.resilience.adaptive import AdaptiveRetry, RetryConfig

        config = RetryConfig(
            min_samples=2,
            cooldown_seconds=999.0,  # Very long cooldown
            window_size=100,
        )
        retry = AdaptiveRetry("test-cooldown", config)

        # Set last adaptation to just now (so cooldown hasn't elapsed)
        retry._last_adaptation = time.time()

        # Add enough samples to trigger the if len >= min_samples
        retry._results.append(True)
        retry._results.append(True)

        # Call _update_metrics which will check cooldown
        retry._update_metrics(True, 0.01)

        # _backpressure_multiplier should still be 1.0 (adapt not called)
        assert retry._backpressure_multiplier == pytest.approx(1.0)

    def test_adapt_linear_above_threshold(self):
        """Lines 195-196: LINEAR strategy with error_rate > threshold."""
        from obskit.resilience.adaptive import AdaptiveRetry, BackpressureStrategy, RetryConfig

        config = RetryConfig(
            backpressure_strategy=BackpressureStrategy.LINEAR,
            error_rate_threshold=0.1,
        )
        retry = AdaptiveRetry("test-linear-high", config)
        retry._adapt(error_rate=0.5)  # 0.5 > 0.1 -> sets multiplier

        assert retry._backpressure_multiplier > 1.0

    def test_adapt_linear_below_threshold(self):
        """Lines 197-198: LINEAR strategy with error_rate <= threshold."""
        from obskit.resilience.adaptive import AdaptiveRetry, BackpressureStrategy, RetryConfig

        config = RetryConfig(
            backpressure_strategy=BackpressureStrategy.LINEAR,
            error_rate_threshold=0.1,
        )
        retry = AdaptiveRetry("test-linear-low", config)
        retry._adapt(error_rate=0.05)  # 0.05 < 0.1 -> multiplier = 1.0

        assert retry._backpressure_multiplier == pytest.approx(1.0)

    def test_adapt_exponential_above_threshold(self):
        """Lines 201-202: EXPONENTIAL strategy with error_rate > threshold."""
        from obskit.resilience.adaptive import AdaptiveRetry, BackpressureStrategy, RetryConfig

        config = RetryConfig(
            backpressure_strategy=BackpressureStrategy.EXPONENTIAL,
            error_rate_threshold=0.1,
        )
        retry = AdaptiveRetry("test-exp-high", config)
        retry._adapt(error_rate=0.5)

        assert retry._backpressure_multiplier > 1.0

    def test_adapt_exponential_below_threshold(self):
        """Lines 203-204: EXPONENTIAL strategy with error_rate <= threshold."""
        from obskit.resilience.adaptive import AdaptiveRetry, BackpressureStrategy, RetryConfig

        config = RetryConfig(
            backpressure_strategy=BackpressureStrategy.EXPONENTIAL,
            error_rate_threshold=0.1,
        )
        retry = AdaptiveRetry("test-exp-low", config)
        retry._adapt(error_rate=0.05)

        assert retry._backpressure_multiplier == pytest.approx(1.0)

    def test_adapt_adaptive_low_error_concurrency_increase(self):
        """Lines 224-225: ADAPTIVE strategy, low error rate -> increase concurrency."""
        from obskit.resilience.adaptive import AdaptiveRetry, BackpressureStrategy, RetryConfig

        config = RetryConfig(
            backpressure_strategy=BackpressureStrategy.ADAPTIVE,
            error_rate_threshold=0.2,
            max_concurrent=100,
            min_concurrent=1,
        )
        retry = AdaptiveRetry("test-adaptive-low-error", config)
        retry._max_allowed_concurrent = 10

        # error_rate < threshold * 0.5 = 0.1 -> increase concurrency
        retry._adapt(error_rate=0.05)

        assert retry._max_allowed_concurrent > 10

    def test_adapt_adaptive_high_error_concurrency_decrease(self):
        """Lines 211-214: ADAPTIVE strategy, high error rate -> decrease concurrency."""
        from obskit.resilience.adaptive import AdaptiveRetry, BackpressureStrategy, RetryConfig

        config = RetryConfig(
            backpressure_strategy=BackpressureStrategy.ADAPTIVE,
            error_rate_threshold=0.1,
            max_concurrent=100,
            min_concurrent=1,
            latency_threshold_seconds=1.0,
        )
        retry = AdaptiveRetry("test-adaptive-high-error", config)
        retry._max_allowed_concurrent = 10
        # Add latency above threshold to cover latency_factor branch
        retry._latencies.append(5.0)  # avg_latency=5.0 > 1.0

        # error_rate > threshold * 2 = 0.2 -> decrease concurrency
        retry._adapt(error_rate=0.5)

        assert retry._max_allowed_concurrent < 10

    def test_execute_sync_non_retryable_exception(self):
        """Lines 368-370: non-retryable exception raises immediately."""
        from obskit.resilience.adaptive import AdaptiveRetry, BackpressureStrategy, RetryConfig

        config = RetryConfig(
            max_retries=3,
            base_delay_seconds=0.001,
            backpressure_strategy=BackpressureStrategy.NONE,
        )
        retry = AdaptiveRetry("test-sync-non-retryable", config)
        # Only retry on TimeoutError, not ValueError
        retry.retryable_exceptions = {TimeoutError}

        call_count = [0]

        def failing_func():
            call_count[0] += 1
            raise ValueError("not retryable")

        with pytest.raises(ValueError):
            retry.execute_sync(failing_func)

        # Should fail on first attempt without retry
        assert call_count[0] == 1

    def test_execute_sync_exhausted_retries(self):
        """Lines 373-375: retries exhausted, raises."""
        from obskit.resilience.adaptive import AdaptiveRetry, BackpressureStrategy, RetryConfig

        config = RetryConfig(
            max_retries=2,
            base_delay_seconds=0.001,
            backpressure_strategy=BackpressureStrategy.NONE,
        )
        retry = AdaptiveRetry("test-sync-exhausted", config)

        call_count = [0]

        def failing_func():
            call_count[0] += 1
            raise ConnectionError("always fails")

        with pytest.raises(ConnectionError):
            retry.execute_sync(failing_func)

        # Should retry max_retries times
        assert call_count[0] == config.max_retries + 1

    def test_execute_sync_fallback_raise_last_exception(self):
        """Line 386: raise last_exception at end of execute_sync.

        This is reached when max_retries=0 and exception occurs.
        """
        from obskit.resilience.adaptive import AdaptiveRetry, BackpressureStrategy, RetryConfig

        config = RetryConfig(
            max_retries=0,
            base_delay_seconds=0.001,
            backpressure_strategy=BackpressureStrategy.NONE,
        )
        retry = AdaptiveRetry("test-sync-raise-last", config)

        def failing_func():
            raise ConnectionError("fails immediately")

        with pytest.raises(ConnectionError):
            retry.execute_sync(failing_func)

    @pytest.mark.asyncio
    async def test_execute_async_sync_func_via_execute(self):
        """Line 285: execute async wrapper calling sync function."""
        from obskit.resilience.adaptive import AdaptiveRetry, BackpressureStrategy, RetryConfig

        config = RetryConfig(
            max_retries=2,
            base_delay_seconds=0.001,
            backpressure_strategy=BackpressureStrategy.NONE,
        )
        retry = AdaptiveRetry("test-async-sync-call", config)

        call_count = [0]

        def sync_func():
            call_count[0] += 1
            return "sync_result"

        result = await retry.execute(sync_func)
        assert result == "sync_result"
        assert call_count[0] == 1

    @pytest.mark.asyncio
    async def test_execute_async_exhausted_retries(self):
        """Line 331: raise last_exception at end of execute (async)."""
        from obskit.resilience.adaptive import AdaptiveRetry, BackpressureStrategy, RetryConfig

        config = RetryConfig(
            max_retries=0,
            base_delay_seconds=0.001,
            backpressure_strategy=BackpressureStrategy.NONE,
        )
        retry = AdaptiveRetry("test-async-raise-last", config)

        async def failing_async():
            raise ConnectionError("async fails")

        with pytest.raises(ConnectionError):
            await retry.execute(failing_async)


class TestCombinedBranchCoverage:
    """Cover missing branches in resilience/combined.py."""

    def test_retry_config_backoff_none_strategy(self):
        """Line 79: else branch (unknown backoff strategy) returns base_delay."""
        from obskit.resilience.combined import BackoffStrategy, RetryConfig

        # We need to trigger the else branch - use a custom mock strategy
        config = RetryConfig(
            base_delay=1.0,
            max_delay=60.0,
        )
        # Monkey-patch backoff to an unexpected value
        config.backoff = "unknown_strategy"

        delay = config.get_delay(1)
        assert delay == pytest.approx(1.0)  # base_delay returned

    def test_resilient_executor_with_circuit_breaker_instance(self):
        """Line 146: circuit_breaker is a CircuitBreaker instance."""
        from obskit.resilience.circuit_breaker import CircuitBreaker
        from obskit.resilience.combined import ResilientExecutor

        cb = CircuitBreaker(name="test-cb-instance")
        executor = ResilientExecutor(circuit_breaker=cb)

        assert executor._circuit_breaker is cb

    def test_resilient_executor_with_none_circuit_breaker(self):
        """Line 148: circuit_breaker is None -> _circuit_breaker = None."""
        from obskit.resilience.combined import ResilientExecutor

        executor = ResilientExecutor(circuit_breaker=None)
        assert executor._circuit_breaker is None

    @pytest.mark.asyncio
    async def test_execute_async_with_circuit_breaker_sync_func(self):
        """Line 217: sync func executed via circuit breaker in async execute."""
        from obskit.resilience.circuit_breaker import CircuitBreaker
        from obskit.resilience.combined import ResilientExecutor

        cb = CircuitBreaker(name="test-async-sync-cb")
        executor = ResilientExecutor(
            circuit_breaker=cb,
            max_retries=1,
            base_delay=0.001,
        )

        result = await executor.execute(lambda: "sync_via_cb")
        assert result == "sync_via_cb"

    @pytest.mark.asyncio
    async def test_execute_circuit_open_raises(self):
        """Lines 202-209: circuit open triggers on_circuit_open and raises CircuitOpenError."""
        import obskit
        from obskit.resilience.circuit_breaker import CircuitBreaker, CircuitOpenError
        from obskit.resilience.combined import ResilientExecutor

        # Patch obskit.CircuitOpenError since combined.py does 'from obskit import CircuitOpenError'
        obskit.CircuitOpenError = CircuitOpenError

        # Use real CircuitBreaker in OPEN state
        cb = CircuitBreaker(name="test-open-raises", failure_threshold=1, recovery_timeout=100.0)
        try:
            with cb:  # NOSONAR
                raise ValueError("force open")
        except ValueError:
            pass  # NOSONAR

        callback_called = [False]

        def on_circuit_open():
            callback_called[0] = True

        executor = ResilientExecutor(
            circuit_breaker=cb,
            max_retries=1,
            base_delay=0.001,
            on_circuit_open=on_circuit_open,
        )

        with pytest.raises(CircuitOpenError):
            await executor.execute(lambda: "result")

        assert callback_called[0]

    @pytest.mark.asyncio
    async def test_execute_async_retry_exhausted_raises_last_exception(self):
        """Lines 256-258: last_exception raised when loop exhausts without returning."""
        from obskit.resilience.combined import ResilientExecutor

        executor = ResilientExecutor(
            circuit_breaker=None,
            max_retries=2,
            base_delay=0.001,
            retryable_exceptions=(ConnectionError,),
        )

        call_count = [0]

        async def failing_async():  # NOSONAR
            call_count[0] += 1
            raise ConnectionError("always fails")

        with pytest.raises(ConnectionError):
            await executor.execute(failing_async)

        assert call_count[0] == 2

    @pytest.mark.asyncio
    async def test_execute_circuit_open_exception_reraises(self):
        """Line 231: exception with Circuit in name re-raises without retry."""
        from obskit.resilience.circuit_breaker import CircuitOpenError
        from obskit.resilience.combined import ResilientExecutor

        call_count = [0]

        async def circuit_open_func():  # NOSONAR
            call_count[0] += 1
            raise CircuitOpenError(breaker_name="test", time_until_retry=0.0)

        executor = ResilientExecutor(
            circuit_breaker=None,
            max_retries=3,
            base_delay=0.001,
            retryable_exceptions=(Exception,),
        )

        # CircuitOpenError has 'Circuit' in the class name -> re-raises without retry
        with pytest.raises(CircuitOpenError):
            await executor.execute(circuit_open_func)

        # Should only be called once (no retry on circuit open)
        assert call_count[0] == 1

    def test_execute_sync_with_circuit_breaker(self):
        """Line 289: sync execution with circuit breaker."""
        from obskit.resilience.circuit_breaker import CircuitBreaker
        from obskit.resilience.combined import ResilientExecutor

        cb = CircuitBreaker(name="test-sync-cb")
        executor = ResilientExecutor(
            circuit_breaker=cb,
            max_retries=1,
            base_delay=0.001,
        )

        result = executor.execute_sync(lambda: "sync_with_cb")
        assert result == "sync_with_cb"

    def test_execute_sync_circuit_open_reraises(self):
        """Line 299: CircuitOpenError in sync path reraises immediately."""
        from obskit.resilience.circuit_breaker import CircuitOpenError
        from obskit.resilience.combined import ResilientExecutor

        call_count = [0]

        def circuit_open_func():
            call_count[0] += 1
            raise CircuitOpenError(breaker_name="test", time_until_retry=0.0)

        executor = ResilientExecutor(
            circuit_breaker=None,
            max_retries=3,
            base_delay=0.001,
            retryable_exceptions=(Exception,),
        )

        with pytest.raises(CircuitOpenError):
            executor.execute_sync(circuit_open_func)

        assert call_count[0] == 1

    def test_execute_sync_retry_exhausted_raises_last_exception(self):
        """Lines 318-320: last_exception raised after all retries exhausted in sync."""
        from obskit.resilience.combined import ResilientExecutor

        executor = ResilientExecutor(
            circuit_breaker=None,
            max_retries=2,
            base_delay=0.001,
            retryable_exceptions=(ConnectionError,),
        )

        call_count = [0]

        def failing_sync():
            call_count[0] += 1
            raise ConnectionError("always fails sync")

        with pytest.raises(ConnectionError):
            executor.execute_sync(failing_sync)

        assert call_count[0] == 2


class TestFactoryBranchCoverage:
    """Cover missing branches in resilience/factory.py."""

    def test_get_circuit_breaker_inner_lock_branch(self):
        """Lines 189->216: inner lock branch when circuit breaker already exists."""
        from obskit.resilience import factory as mod

        unique_name = "__inner_lock_cb_test__"
        mod._circuit_breakers.pop(unique_name, None)

        class _FakeDict(dict):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self._first_call_done = False
                self._target_key = None

            def __contains__(self, key):
                if key == self._target_key and not self._first_call_done:
                    self._first_call_done = True
                    return False
                return super().__contains__(key)

        from obskit.resilience.circuit_breaker import CircuitBreaker
        from obskit.resilience.factory import get_circuit_breaker

        existing_cb = CircuitBreaker(name=unique_name)

        fake_dict = _FakeDict()
        fake_dict._target_key = unique_name
        fake_dict[unique_name] = existing_cb

        original = mod._circuit_breakers
        mod._circuit_breakers = fake_dict
        try:
            result = get_circuit_breaker(unique_name)
            assert result is existing_cb
        finally:
            mod._circuit_breakers = original
            mod._circuit_breakers.pop(unique_name, None)

    def test_get_rate_limiter_inner_lock_branch(self):
        """Lines 255->279: inner lock branch when rate limiter already exists."""
        from obskit.resilience import factory as mod

        unique_name = "__inner_lock_rl_test__"
        mod._rate_limiters.pop(unique_name, None)

        class _FakeDict(dict):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self._first_call_done = False
                self._target_key = None

            def __contains__(self, key):
                if key == self._target_key and not self._first_call_done:
                    self._first_call_done = True
                    return False
                return super().__contains__(key)

        from obskit.resilience.factory import get_rate_limiter
        from obskit.resilience.rate_limiter import TokenBucketRateLimiter

        existing_rl = TokenBucketRateLimiter(bucket_size=100, refill_rate=1.0)

        fake_dict = _FakeDict()
        fake_dict._target_key = unique_name
        fake_dict[unique_name] = existing_rl

        original = mod._rate_limiters
        mod._rate_limiters = fake_dict
        try:
            result = get_rate_limiter(unique_name)
            assert result is existing_rl
        finally:
            mod._rate_limiters = original
            mod._rate_limiters.pop(unique_name, None)

    def test_reset_circuit_breaker_exception_returns_false(self):
        """Lines 301-302: reset raises exception, returns False."""
        from unittest.mock import MagicMock

        from obskit.resilience import factory as mod
        from obskit.resilience.factory import reset_circuit_breaker

        unique_name = "__reset_fail_cb__"
        mock_cb = MagicMock()
        mock_cb.reset.side_effect = RuntimeError("reset failed")

        mod._circuit_breakers[unique_name] = mock_cb
        try:
            result = reset_circuit_breaker(unique_name)
            assert result is False
        finally:
            mod._circuit_breakers.pop(unique_name, None)


class TestAdaptiveRetryMoreBranches:
    """Cover remaining branch misses in adaptive.py."""

    def test_adapt_adaptive_middle_error_rate_no_concurrency_change(self):
        """Line 224->230: ADAPTIVE with error rate in middle range (no concurrency change)."""
        from obskit.resilience.adaptive import AdaptiveRetry, BackpressureStrategy, RetryConfig

        config = RetryConfig(
            backpressure_strategy=BackpressureStrategy.ADAPTIVE,
            error_rate_threshold=0.1,
        )
        retry = AdaptiveRetry("test-adaptive-middle", config)
        retry._max_allowed_concurrent = 10

        # error_rate=0.08:
        # - NOT > threshold*2 (0.2) -> no decrease
        # - NOT < threshold*0.5 (0.05) -> no increase (224->230)
        retry._adapt(error_rate=0.08)

        # Concurrency stays at 10
        assert retry._max_allowed_concurrent == 10

    def test_adapt_unknown_strategy_skips_all_branches(self):
        """Line 206->230: unknown strategy skips LINEAR/EXPONENTIAL/ADAPTIVE branches."""
        from obskit.resilience.adaptive import AdaptiveRetry, BackpressureStrategy, RetryConfig

        config = RetryConfig(
            backpressure_strategy=BackpressureStrategy.LINEAR,
        )
        retry = AdaptiveRetry("test-unknown-strategy", config)

        # Override strategy to an unknown type -> skips all elif branches
        class UnknownStrategy:
            pass  # NOSONAR

        retry.config.backpressure_strategy = UnknownStrategy()
        # Should reach line 230 without entering any branch
        retry._adapt(error_rate=0.5)
        # multiplier capped at min(1.0, 10.0) = 1.0 (unchanged from default)
        assert retry._backpressure_multiplier == pytest.approx(1.0)

    @pytest.mark.asyncio
    async def test_execute_async_raises_last_exception_when_empty_retries(self):
        """Line 331: raise last_exception when max_retries=-1 (empty loop)."""
        from obskit.resilience.adaptive import AdaptiveRetry, BackpressureStrategy, RetryConfig

        config = RetryConfig(
            max_retries=-1,  # range(-1+1) = range(0) = empty loop
            base_delay_seconds=0.001,
            backpressure_strategy=BackpressureStrategy.NONE,
        )
        retry = AdaptiveRetry("test-async-neg-retries", config)

        with pytest.raises(Exception, match="Retry exhausted"):
            await retry.execute(lambda: "result")

    def test_execute_sync_raises_last_exception_when_empty_retries(self):
        """Line 386: raise last_exception when max_retries=-1 (empty loop in sync)."""
        from obskit.resilience.adaptive import AdaptiveRetry, BackpressureStrategy, RetryConfig

        config = RetryConfig(
            max_retries=-1,  # range(-1+1) = range(0) = empty loop
            base_delay_seconds=0.001,
            backpressure_strategy=BackpressureStrategy.NONE,
        )
        retry = AdaptiveRetry("test-sync-neg-retries", config)

        with pytest.raises(Exception, match="Retry exhausted"):
            retry.execute_sync(lambda: "result")
