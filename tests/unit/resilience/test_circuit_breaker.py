"""Tests for obskit.resilience.circuit_breaker module."""

import time

import pytest

from obskit.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitOpenError,
    CircuitState,
    _circuit_breakers,
    _circuit_breakers_lock,
    get_circuit_breaker,
    reset_all_circuit_breakers,
)


class TestCircuitBreaker:
    """Tests for CircuitBreaker class."""

    def test_init_default_values(self):
        """Test default initialization."""
        breaker = CircuitBreaker(name="test")
        assert breaker.name == "test"
        assert breaker.state == CircuitState.CLOSED

    def test_init_custom_values(self):
        """Test initialization with custom values."""
        breaker = CircuitBreaker(
            name="custom",
            failure_threshold=10,
            recovery_timeout=60.0,
            half_open_requests=5,
        )
        assert breaker.name == "custom"

    def test_starts_closed(self):
        """Test that breaker starts in CLOSED state."""
        breaker = CircuitBreaker(name="test")
        assert breaker.state == CircuitState.CLOSED

    def test_is_closed_property(self):
        """Test is_closed property."""
        breaker = CircuitBreaker(name="test")
        assert breaker.is_closed is True
        assert breaker.is_open is False

    def test_failure_count_property(self):
        """Test failure_count property."""
        breaker = CircuitBreaker(name="test")
        assert breaker.failure_count == 0

    def test_is_half_open_property(self):
        """Test is_half_open property."""
        breaker = CircuitBreaker(name="test")
        assert breaker.is_half_open is False

    def test_reset_method(self):
        """Test reset method."""
        breaker = CircuitBreaker(name="test", failure_threshold=1)
        # Force to open state by setting internal state
        breaker._state = CircuitState.OPEN
        breaker._failure_count = 5

        breaker.reset()

        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0


class TestCircuitState:
    """Tests for CircuitState enum."""

    def test_states_exist(self):
        """Test that all states exist."""
        assert CircuitState.CLOSED is not None
        assert CircuitState.OPEN is not None
        assert CircuitState.HALF_OPEN is not None


class TestCircuitOpenError:
    """Tests for CircuitOpenError exception."""

    def test_error_message(self):
        """Test error message contains circuit name."""
        error = CircuitOpenError("test-circuit", time_until_retry=10.0)
        assert "test-circuit" in str(error)
        assert error.time_until_retry == 10.0


class TestAsyncCircuitBreaker:
    """Tests for async circuit breaker usage."""

    @pytest.mark.asyncio
    async def test_async_context_manager_success(self):
        """Test async context manager on success."""
        breaker = CircuitBreaker(name="async-test")

        async with breaker:
            pass  # Success

        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_async_context_manager_failure(self):
        """Test async context manager on failure."""
        breaker = CircuitBreaker(name="async-test", failure_threshold=1)

        with pytest.raises(ValueError):
            async with breaker:
                raise ValueError("Async error")

        assert breaker.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_async_opens_after_threshold(self):
        """Test circuit opens after failure threshold."""
        breaker = CircuitBreaker(name="async-test", failure_threshold=2)

        # First failure
        with pytest.raises(ValueError):
            async with breaker:
                raise ValueError("Error 1")

        # Second failure - should open
        with pytest.raises(ValueError):
            async with breaker:
                raise ValueError("Error 2")

        assert breaker.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_async_raises_when_open(self):
        """Test async raises when circuit is open."""
        breaker = CircuitBreaker(name="async-raise-test", failure_threshold=1)

        # Open the circuit
        with pytest.raises(ValueError):
            async with breaker:
                raise ValueError("Open circuit")

        # Should raise CircuitOpenError
        with pytest.raises(CircuitOpenError):
            async with breaker:
                pass

    @pytest.mark.asyncio
    async def test_half_open_to_closed_transition(self):
        """Test circuit transitions from half-open to closed after enough successes."""
        breaker = CircuitBreaker(
            name="half-open-test",
            failure_threshold=1,
            recovery_timeout=0.01,  # Very short timeout
            half_open_requests=2,
        )

        # Open the circuit
        with pytest.raises(ValueError):
            async with breaker:
                raise ValueError("Open circuit")

        assert breaker.state == CircuitState.OPEN

        # Wait for recovery timeout
        time.sleep(0.02)

        # First success in half-open
        async with breaker:
            pass

        assert breaker.state == CircuitState.HALF_OPEN

        # Second success should close circuit
        async with breaker:
            pass

        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_half_open_to_open_on_failure(self):
        """Test circuit reopens from half-open on failure."""
        breaker = CircuitBreaker(
            name="reopen-test",
            failure_threshold=1,
            recovery_timeout=0.01,
            half_open_requests=3,
        )

        # Open the circuit
        with pytest.raises(ValueError):
            async with breaker:
                raise ValueError("Open circuit")

        # Wait for recovery timeout
        time.sleep(0.02)

        # Trigger half-open with a success
        async with breaker:
            pass

        assert breaker.state == CircuitState.HALF_OPEN

        # Failure in half-open should reopen
        with pytest.raises(ValueError):
            async with breaker:
                raise ValueError("Reopen")

        assert breaker.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_excluded_exceptions_not_counted(self):
        """Test that excluded exceptions don't count as failures."""
        breaker = CircuitBreaker(
            name="excluded-test",
            failure_threshold=2,
            excluded_exceptions=(ValueError,),
        )

        # ValueError should not count as failure
        with pytest.raises(ValueError):
            async with breaker:
                raise ValueError("Excluded")

        assert breaker.failure_count == 0
        assert breaker.state == CircuitState.CLOSED

        # RuntimeError should count
        with pytest.raises(RuntimeError):
            async with breaker:
                raise RuntimeError("Counted")

        assert breaker.failure_count == 1

    @pytest.mark.asyncio
    async def test_success_resets_failure_count(self):
        """Test that success resets failure count in closed state."""
        breaker = CircuitBreaker(name="reset-test", failure_threshold=3)

        # Record a failure
        with pytest.raises(ValueError):
            async with breaker:
                raise ValueError("Failure")

        assert breaker.failure_count == 1

        # Success should reset
        async with breaker:
            pass

        assert breaker.failure_count == 0

    @pytest.mark.asyncio
    async def test_decorator_pattern(self):
        """Test using circuit breaker as decorator."""
        breaker = CircuitBreaker(name="decorator-test")

        @breaker
        async def decorated_func():
            return "success"

        result = await decorated_func()
        assert result == "success"

    @pytest.mark.asyncio
    async def test_decorator_pattern_with_failure(self):
        """Test decorator pattern with failure."""
        breaker = CircuitBreaker(name="decorator-fail-test", failure_threshold=1)

        @breaker
        async def failing_func():
            raise ValueError("Decorated failure")

        with pytest.raises(ValueError):
            await failing_func()

        assert breaker.state == CircuitState.OPEN


class TestCircuitBreakerRegistry:
    """Tests for module-level circuit breaker registry."""

    def setup_method(self):
        """Clear registry before each test."""
        with _circuit_breakers_lock:
            _circuit_breakers.clear()

    def teardown_method(self):
        """Clear registry after each test."""
        with _circuit_breakers_lock:
            _circuit_breakers.clear()

    def test_get_circuit_breaker_creates_new(self):
        """Test get_circuit_breaker creates new breaker."""
        breaker = get_circuit_breaker("new-breaker")
        assert breaker.name == "new-breaker"
        assert breaker.state == CircuitState.CLOSED

    def test_get_circuit_breaker_returns_same(self):
        """Test get_circuit_breaker returns same instance."""
        breaker1 = get_circuit_breaker("shared-breaker")
        breaker2 = get_circuit_breaker("shared-breaker")
        assert breaker1 is breaker2

    def test_get_circuit_breaker_with_kwargs(self):
        """Test get_circuit_breaker passes kwargs."""
        breaker = get_circuit_breaker(
            "custom-breaker",
            failure_threshold=10,
        )
        assert breaker._failure_threshold == 10

    def test_reset_all_circuit_breakers(self):
        """Test reset_all_circuit_breakers."""
        breaker1 = get_circuit_breaker("breaker1", failure_threshold=1)
        breaker2 = get_circuit_breaker("breaker2", failure_threshold=1)

        # Force open state
        breaker1._state = CircuitState.OPEN
        breaker2._state = CircuitState.OPEN

        reset_all_circuit_breakers()

        assert breaker1.state == CircuitState.CLOSED
        assert breaker2.state == CircuitState.CLOSED


class TestCircuitBreakerTimeUntilRetry:
    """Tests for _get_time_until_retry method."""

    def test_time_until_retry_no_failures(self):
        """Test _get_time_until_retry when no failures recorded."""
        breaker = CircuitBreaker(
            name="time-test",
            failure_threshold=5,
        )

        # No failures - _last_failure_time is None
        assert breaker._last_failure_time is None

        result = breaker._get_time_until_retry()
        assert result == 0.0
