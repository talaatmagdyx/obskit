"""Unit tests for adaptive retry with backpressure."""

import pytest

from obskit.resilience.adaptive import (
    AdaptiveRetry,
    BackpressureStrategy,
    RetryConfig,
    RetryState,
    adaptive_retry,
)


class TestBackpressureStrategy:
    """Tests for BackpressureStrategy enum."""

    def test_values(self):
        """Test enum values exist."""
        assert BackpressureStrategy.NONE.value == "none"
        assert BackpressureStrategy.LINEAR.value == "linear"
        assert BackpressureStrategy.EXPONENTIAL.value == "exponential"
        assert BackpressureStrategy.ADAPTIVE.value == "adaptive"


class TestRetryConfig:
    """Tests for RetryConfig dataclass."""

    def test_defaults(self):
        """Test default configuration values."""
        config = RetryConfig()

        assert config.max_retries == 3
        assert config.base_delay_seconds == 0.1
        assert config.max_delay_seconds == 60.0
        assert config.exponential_base == 2.0
        assert config.jitter_factor == 0.25
        assert config.backpressure_strategy == BackpressureStrategy.ADAPTIVE
        assert config.error_rate_threshold == 0.1
        assert config.max_concurrent == 100

    def test_custom_config(self):
        """Test custom configuration."""
        config = RetryConfig(
            max_retries=5,
            base_delay_seconds=0.5,
            max_delay_seconds=30.0,
            backpressure_strategy=BackpressureStrategy.LINEAR,
        )

        assert config.max_retries == 5
        assert config.base_delay_seconds == 0.5
        assert config.backpressure_strategy == BackpressureStrategy.LINEAR


class TestRetryState:
    """Tests for RetryState dataclass."""

    def test_init(self):
        """Test state initialization."""
        state = RetryState(name="test")

        assert state.name == "test"
        assert state.attempt == 0
        assert state.last_error is None
        assert state.total_delay == 0.0
        assert state.backpressure_multiplier == 1.0


class TestAdaptiveRetry:
    """Tests for AdaptiveRetry class."""

    def test_init_defaults(self):
        """Test default initialization."""
        retry = AdaptiveRetry(name="test")

        assert retry.name == "test"
        assert retry.config is not None
        assert Exception in retry.retryable_exceptions

    def test_init_with_config(self):
        """Test initialization with custom config."""
        config = RetryConfig(max_retries=5)
        retry = AdaptiveRetry(name="test", config=config)

        assert retry.config.max_retries == 5

    def test_init_with_custom_exceptions(self):
        """Test initialization with custom retryable exceptions."""
        retry = AdaptiveRetry(name="test", retryable_exceptions={ConnectionError, TimeoutError})

        assert ConnectionError in retry.retryable_exceptions
        assert TimeoutError in retry.retryable_exceptions

    def test_is_retryable(self):
        """Test checking if exception is retryable."""
        retry = AdaptiveRetry(name="test", retryable_exceptions={ConnectionError, TimeoutError})

        assert retry._is_retryable(ConnectionError("test")) is True
        assert retry._is_retryable(TimeoutError("test")) is True
        assert retry._is_retryable(ValueError("test")) is False

    def test_calculate_delay_base(self):
        """Test base delay calculation."""
        config = RetryConfig(
            base_delay_seconds=1.0,
            exponential_base=2.0,
            jitter_factor=0.0,  # No jitter for testing
        )
        retry = AdaptiveRetry(name="test", config=config)
        state = RetryState(name="test", backpressure_multiplier=1.0)

        delay0 = retry._calculate_delay(0, state)
        delay1 = retry._calculate_delay(1, state)
        delay2 = retry._calculate_delay(2, state)

        assert delay0 == 1.0  # 1 * 2^0
        assert delay1 == 2.0  # 1 * 2^1
        assert delay2 == 4.0  # 1 * 2^2

    def test_calculate_delay_with_backpressure(self):
        """Test delay calculation with backpressure."""
        config = RetryConfig(base_delay_seconds=1.0, jitter_factor=0.0)
        retry = AdaptiveRetry(name="test", config=config)
        state = RetryState(name="test", backpressure_multiplier=2.0)

        delay = retry._calculate_delay(0, state)

        assert delay == 2.0  # 1.0 * 2.0 backpressure

    def test_calculate_delay_max_cap(self):
        """Test delay is capped at max."""
        config = RetryConfig(base_delay_seconds=10.0, max_delay_seconds=5.0, jitter_factor=0.0)
        retry = AdaptiveRetry(name="test", config=config)
        state = RetryState(name="test")

        delay = retry._calculate_delay(3, state)

        assert delay == 5.0  # Capped at max

    @pytest.mark.asyncio
    async def test_execute_success(self):
        """Test successful execution."""
        retry = AdaptiveRetry(name="test")

        async def success_func():
            return "success"

        result = await retry.execute(success_func)

        assert result == "success"

    @pytest.mark.asyncio
    async def test_execute_retry_then_success(self):
        """Test retry on failure then success."""
        config = RetryConfig(max_retries=3, base_delay_seconds=0.01)
        retry = AdaptiveRetry(name="test", config=config)

        call_count = 0

        async def fail_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Failed")
            return "success"

        result = await retry.execute(fail_then_succeed)

        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_execute_exhausted_retries(self):
        """Test exhausted retries raises exception."""
        config = RetryConfig(max_retries=2, base_delay_seconds=0.01)
        retry = AdaptiveRetry(name="test", config=config)

        async def always_fail():
            raise ConnectionError("Always fails")

        with pytest.raises(ConnectionError):
            await retry.execute(always_fail)

    @pytest.mark.asyncio
    async def test_execute_non_retryable_exception(self):
        """Test non-retryable exception raises immediately."""
        retry = AdaptiveRetry(name="test", retryable_exceptions={ConnectionError})

        call_count = 0

        async def raise_value_error():
            nonlocal call_count
            call_count += 1
            raise ValueError("Not retryable")

        with pytest.raises(ValueError):
            await retry.execute(raise_value_error)

        assert call_count == 1  # Not retried

    def test_execute_sync_success(self):
        """Test synchronous execution success."""
        retry = AdaptiveRetry(name="test")

        def success_func():
            return "sync_success"

        result = retry.execute_sync(success_func)

        assert result == "sync_success"

    def test_execute_sync_retry(self):
        """Test synchronous retry."""
        config = RetryConfig(max_retries=3, base_delay_seconds=0.01)
        retry = AdaptiveRetry(name="test", config=config)

        call_count = 0

        def fail_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("Failed")
            return "success"

        result = retry.execute_sync(fail_then_succeed)

        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_wrap_decorator_async(self):
        """Test wrap decorator for async functions."""
        config = RetryConfig(base_delay_seconds=0.01)
        retry = AdaptiveRetry(name="test", config=config)

        @retry.wrap
        async def wrapped_async():
            return "wrapped"

        result = await wrapped_async()

        assert result == "wrapped"

    def test_wrap_decorator_sync(self):
        """Test wrap decorator for sync functions."""
        config = RetryConfig(base_delay_seconds=0.01)
        retry = AdaptiveRetry(name="test", config=config)

        @retry.wrap
        def wrapped_sync():
            return "sync_wrapped"

        result = wrapped_sync()

        assert result == "sync_wrapped"

    def test_get_stats(self):
        """Test getting retry statistics."""
        retry = AdaptiveRetry(name="test")

        stats = retry.get_stats()

        assert stats["name"] == "test"
        assert "backpressure_multiplier" in stats
        assert "error_rate" in stats
        assert "current_concurrent" in stats

    @pytest.mark.asyncio
    async def test_adaptation_reduces_multiplier_on_errors(self):
        """Test adaptation increases backpressure on errors."""
        config = RetryConfig(
            backpressure_strategy=BackpressureStrategy.ADAPTIVE,
            error_rate_threshold=0.1,
            window_size=10,
            min_samples=5,
            cooldown_seconds=0.0,
        )
        retry = AdaptiveRetry(name="test", config=config)

        # Record errors
        for _ in range(10):
            retry._update_metrics(success=False, latency=0.1)

        # Trigger adaptation
        retry._adapt(error_rate=0.5)

        # Backpressure should be increased
        assert retry._backpressure_multiplier > 1.0

    @pytest.mark.asyncio
    async def test_adaptation_strategy_none(self):
        """Test no adaptation with NONE strategy."""
        config = RetryConfig(backpressure_strategy=BackpressureStrategy.NONE)
        retry = AdaptiveRetry(name="test", config=config)

        retry._adapt(error_rate=0.5)

        # Should not change
        assert retry._backpressure_multiplier == 1.0


class TestAdaptiveRetryDecorator:
    """Tests for adaptive_retry decorator."""

    @pytest.mark.asyncio
    async def test_decorator_basic(self):
        """Test basic decorator usage."""

        @adaptive_retry("test_func", max_retries=2, base_delay=0.01)
        async def my_func():
            return "decorated"

        result = await my_func()

        assert result == "decorated"

    @pytest.mark.asyncio
    async def test_decorator_with_retries(self):
        """Test decorator with retries."""
        call_count = 0

        @adaptive_retry("test_func", max_retries=3, base_delay=0.01)
        async def failing_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("Fail")
            return "success"

        result = await failing_func()

        assert result == "success"
        assert call_count == 2

    def test_decorator_sync(self):
        """Test decorator with sync function."""

        @adaptive_retry("test_sync", max_retries=2, base_delay=0.01)
        def sync_func():
            return "sync_result"

        result = sync_func()

        assert result == "sync_result"
