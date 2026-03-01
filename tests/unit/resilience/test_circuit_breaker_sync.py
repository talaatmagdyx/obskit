"""Unit tests for sync circuit breaker functionality."""

from __future__ import annotations

import time

import pytest

from obskit.resilience import CircuitBreaker, CircuitOpenError, with_circuit_breaker_sync


class TestSyncCircuitBreaker:
    """Tests for sync circuit breaker context manager."""

    def test_sync_context_manager_success(self):
        """Test successful sync context manager usage."""
        breaker = CircuitBreaker(name="test_sync", failure_threshold=3)

        with breaker:
            result = "success"

        assert result == "success"
        assert breaker.is_closed

    def test_sync_context_manager_failure(self):
        """Test sync context manager records failures."""
        breaker = CircuitBreaker(name="test_sync_fail", failure_threshold=3)

        with pytest.raises(ValueError):
            with breaker:
                raise ValueError("test error")

        assert breaker.failure_count == 1

    def test_sync_opens_after_threshold(self):
        """Test circuit opens after failure threshold."""
        breaker = CircuitBreaker(name="test_sync_open", failure_threshold=2)

        for _ in range(2):
            with pytest.raises(ValueError):
                with breaker:
                    raise ValueError("test error")

        assert not breaker.is_closed

    def test_sync_raises_when_open(self):
        """Test CircuitOpenError raised when circuit is open."""
        breaker = CircuitBreaker(
            name="test_sync_open_error",
            failure_threshold=1,
            recovery_timeout=10.0,
        )

        # Trigger circuit to open
        with pytest.raises(ValueError):
            with breaker:
                raise ValueError("test error")

        # Should now raise CircuitOpenError
        with pytest.raises(CircuitOpenError) as exc_info:
            with breaker:
                pass  # NOSONAR

        assert exc_info.value.breaker_name == "test_sync_open_error"

    def test_sync_half_open_to_closed_transition(self):
        """Test transition from half-open to closed state."""
        breaker = CircuitBreaker(
            name="test_sync_half_open_close",
            failure_threshold=1,
            recovery_timeout=0.1,
            half_open_requests=1,
        )

        # Trigger circuit to open
        with pytest.raises(ValueError):
            with breaker:
                raise ValueError("test error")

        # Wait for recovery timeout
        time.sleep(0.15)

        # Successful request should close the circuit
        with breaker:
            pass  # NOSONAR

        assert breaker.is_closed

    def test_sync_half_open_to_open_on_failure(self):
        """Test transition from half-open back to open on failure."""
        breaker = CircuitBreaker(
            name="test_sync_half_open_reopen",
            failure_threshold=1,
            recovery_timeout=0.1,
        )

        # Trigger circuit to open
        with pytest.raises(ValueError):
            with breaker:
                raise ValueError("test error")

        # Wait for recovery timeout
        time.sleep(0.15)

        # Failure in half-open should reopen circuit
        with pytest.raises(ValueError):
            with breaker:
                raise ValueError("test error")

        assert not breaker.is_closed

    def test_sync_call_method(self):
        """Test call_sync method."""
        breaker = CircuitBreaker(name="test_call_sync", failure_threshold=3)

        def my_func(x, y):
            return x + y

        result = breaker.call_sync(my_func, 1, 2)
        assert result == 3

    def test_sync_call_method_with_failure(self):
        """Test call_sync method with failure."""
        breaker = CircuitBreaker(name="test_call_sync_fail", failure_threshold=3)

        def failing_func():
            raise ValueError("test error")

        with pytest.raises(ValueError):
            breaker.call_sync(failing_func)

        assert breaker.failure_count == 1


class TestWithCircuitBreakerSyncDecorator:
    """Tests for with_circuit_breaker_sync decorator."""

    def test_decorator_success(self):
        """Test decorator with successful function."""

        @with_circuit_breaker_sync("test_decorator_sync")
        def my_func(x):
            return x * 2

        result = my_func(5)
        assert result == 10

    def test_decorator_failure(self):
        """Test decorator records failures."""

        @with_circuit_breaker_sync("test_decorator_sync_fail", failure_threshold=3)
        def failing_func():
            raise ValueError("test error")

        with pytest.raises(ValueError):
            failing_func()

    def test_decorator_opens_circuit(self):
        """Test decorator opens circuit after threshold."""

        @with_circuit_breaker_sync(
            "test_decorator_sync_open",
            failure_threshold=2,
            recovery_timeout=10.0,
        )
        def failing_func():
            raise ValueError("test error")

        # Trigger failures
        for _ in range(2):
            with pytest.raises(ValueError):
                failing_func()

        # Should now raise CircuitOpenError
        with pytest.raises(CircuitOpenError):
            failing_func()

    def test_decorator_preserves_function_name(self):
        """Test decorator preserves function name."""

        @with_circuit_breaker_sync("test_decorator_sync_name")
        def my_named_function():
            pass  # NOSONAR

        assert my_named_function.__name__ == "my_named_function"

    def test_decorator_with_kwargs(self):
        """Test decorator with keyword arguments."""

        @with_circuit_breaker_sync("test_decorator_sync_kwargs")
        def my_func(a, b=10):
            return a + b

        result = my_func(5, b=20)
        assert result == 25

    def test_decorator_custom_settings(self):
        """Test decorator with custom settings."""

        @with_circuit_breaker_sync(
            "test_decorator_sync_custom",
            failure_threshold=5,
            recovery_timeout=30.0,
            half_open_requests=2,
        )
        def my_func():
            return "success"

        result = my_func()
        assert result == "success"


class TestSyncCircuitBreakerExcludedExceptions:
    """Tests for excluded exceptions in sync circuit breaker."""

    def test_excluded_exception_not_counted(self):
        """Test that excluded exceptions don't count as failures."""

        class IgnorableError(Exception):
            pass  # NOSONAR

        breaker = CircuitBreaker(
            name="test_sync_excluded",
            failure_threshold=2,
            excluded_exceptions=(IgnorableError,),
        )

        # Raise excluded exception multiple times
        for _ in range(5):
            with pytest.raises(IgnorableError):
                with breaker:
                    raise IgnorableError("ignored")

        # Circuit should still be closed
        assert breaker.is_closed

    def test_mixed_exceptions(self):
        """Test mix of excluded and counted exceptions."""

        class IgnorableError(Exception):
            pass  # NOSONAR

        breaker = CircuitBreaker(
            name="test_sync_mixed",
            failure_threshold=2,
            excluded_exceptions=(IgnorableError,),
        )

        # Excluded exception
        with pytest.raises(IgnorableError):
            with breaker:
                raise IgnorableError("ignored")

        # Counted exception
        with pytest.raises(ValueError):
            with breaker:
                raise ValueError("counted")

        assert breaker.failure_count == 1  # Only ValueError counted
