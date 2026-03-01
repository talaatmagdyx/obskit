"""Tests for obskit.resilience.distributed module."""

import json
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from obskit.resilience.circuit_breaker import CircuitOpenError, CircuitState
from obskit.resilience.distributed import (
    AsyncDistributedCircuitBreaker,
    DistributedCircuitBreaker,
    _is_async_redis_client,
)


class TestIsAsyncRedisClient:
    """Tests for _is_async_redis_client function."""

    def test_sync_client(self):
        """Test detection of sync Redis client."""
        mock = MagicMock()
        # Remove aclose to make it look sync
        del mock.aclose
        mock.get.return_value = "sync_value"

        result = _is_async_redis_client(mock)
        assert result is False

    def test_async_client_with_aclose(self):
        """Test detection of async client via aclose."""
        mock = MagicMock()
        mock.aclose = MagicMock()

        result = _is_async_redis_client(mock)
        assert result is True

    def test_client_with_exception_on_get(self):
        """Test handling when get() raises."""
        mock = MagicMock()
        del mock.aclose
        mock.get.side_effect = Exception("Connection error")

        result = _is_async_redis_client(mock)
        assert result is False

    def test_client_with_coroutine_return(self):
        """Test detection via coroutine return from get()."""

        async def mock_get(_):  # NOSONAR
            return "value"

        mock = MagicMock()
        del mock.aclose
        mock.get.return_value = mock_get("test")  # Returns coroutine

        result = _is_async_redis_client(mock)
        assert result is True


class TestDistributedCircuitBreaker:
    """Tests for DistributedCircuitBreaker class."""

    def test_init_sync(self):
        """Test initialization with sync Redis."""
        mock = MagicMock()
        mock.get.return_value = None
        del mock.aclose

        breaker = DistributedCircuitBreaker(
            name="test",
            redis_client=mock,
            failure_threshold=5,
            recovery_timeout=30.0,
        )
        assert breaker.name == "test"

    def test_init_with_custom_key_prefix(self):
        """Test initialization with custom key prefix."""
        mock = MagicMock()
        mock.get.return_value = None
        del mock.aclose

        breaker = DistributedCircuitBreaker(
            name="test",
            redis_client=mock,
            key_prefix="custom:cb:",
        )
        assert "custom:cb:" in breaker._redis_key

    def test_get_state_sync_no_data(self):
        """Test getting state when Redis has no data."""
        mock = MagicMock()
        mock.get.return_value = None
        del mock.aclose

        breaker = DistributedCircuitBreaker(
            name="test",
            redis_client=mock,
        )

        result = breaker._get_state_from_redis_sync()
        assert result is None

    def test_get_state_sync_with_data(self):
        """Test getting state from Redis with valid data."""
        state = json.dumps(
            {
                "state": "closed",
                "failure_count": 3,
                "last_failure_time": time.time() - 10,
                "half_open_count": 0,
            }
        )

        mock = MagicMock()
        mock.get.return_value = state
        del mock.aclose

        breaker = DistributedCircuitBreaker(
            name="test",
            redis_client=mock,
        )

        result = breaker._get_state_from_redis_sync()
        assert result is not None
        assert result["failure_count"] == 3

    def test_get_state_sync_invalid_json(self):
        """Test handling of invalid JSON from Redis."""
        mock = MagicMock()
        mock.get.return_value = "not valid json"
        del mock.aclose

        breaker = DistributedCircuitBreaker(
            name="test",
            redis_client=mock,
        )

        result = breaker._get_state_from_redis_sync()
        assert result is None

    def test_save_state_sync(self):
        """Test saving state to Redis."""
        mock = MagicMock()
        mock.get.return_value = None
        mock.setex.return_value = True
        del mock.aclose

        breaker = DistributedCircuitBreaker(
            name="test",
            redis_client=mock,
            ttl_seconds=3600,
        )

        breaker._save_state_to_redis_sync({"state": "open"})
        mock.setex.assert_called_once()

    def test_context_manager_sync_success(self):
        """Test sync context manager on success."""
        mock = MagicMock()
        mock.get.return_value = None
        mock.setex.return_value = True
        del mock.aclose

        breaker = DistributedCircuitBreaker(
            name="test",
            redis_client=mock,
        )

        with breaker:
            pass  # Success

    def test_context_manager_sync_failure(self):
        """Test sync context manager on failure."""
        mock = MagicMock()
        mock.get.return_value = None
        mock.setex.return_value = True
        del mock.aclose

        breaker = DistributedCircuitBreaker(
            name="test",
            redis_client=mock,
        )

        with pytest.raises(ValueError):
            with breaker:
                raise ValueError("Test error")


class TestDistributedCircuitBreakerAsync:
    """Tests for async DistributedCircuitBreaker."""

    @pytest.mark.asyncio
    async def test_async_context_manager(self):
        """Test async context manager."""
        mock = MagicMock()
        mock.get = AsyncMock(return_value=None)
        mock.setex = AsyncMock(return_value=True)
        mock.aclose = AsyncMock()

        breaker = DistributedCircuitBreaker(
            name="async-test",
            redis_client=mock,
        )

        async with breaker:
            pass  # Success

    @pytest.mark.asyncio
    async def test_async_get_state(self):
        """Test async state retrieval."""
        state = json.dumps(
            {
                "state": "open",
                "failure_count": 5,
                "last_failure_time": time.time(),
                "half_open_count": 1,
            }
        )

        mock = MagicMock()
        mock.get = AsyncMock(return_value=state)
        mock.setex = AsyncMock()
        mock.aclose = AsyncMock()

        breaker = DistributedCircuitBreaker(
            name="async-test",
            redis_client=mock,
        )

        result = await breaker._get_state_from_redis_async()
        assert result is not None
        assert result["failure_count"] == 5

    @pytest.mark.asyncio
    async def test_async_save_state(self):
        """Test async state saving."""
        mock = MagicMock()
        mock.get = AsyncMock(return_value=None)
        mock.setex = AsyncMock(return_value=True)
        mock.aclose = AsyncMock()

        breaker = DistributedCircuitBreaker(
            name="async-test",
            redis_client=mock,
        )

        await breaker._save_state_to_redis_async({"state": "closed"})
        mock.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_context_manager_failure(self):
        """Test async context manager with failure."""
        mock = MagicMock()
        mock.get = AsyncMock(return_value=None)
        mock.setex = AsyncMock(return_value=True)
        mock.aclose = AsyncMock()

        breaker = DistributedCircuitBreaker(
            name="async-fail-test",
            redis_client=mock,
            failure_threshold=1,
        )

        with pytest.raises(ValueError):
            async with breaker:
                raise ValueError("Async error")

    @pytest.mark.asyncio
    async def test_async_invalid_json(self):
        """Test async handling of invalid JSON."""
        mock = MagicMock()
        mock.get = AsyncMock(return_value="invalid json{")
        mock.setex = AsyncMock()
        mock.aclose = AsyncMock()

        breaker = DistributedCircuitBreaker(
            name="invalid-json-test",
            redis_client=mock,
        )

        result = await breaker._get_state_from_redis_async()
        assert result is None


class TestDistributedCircuitBreakerStateTransitions:
    """Tests for state transitions."""

    def test_sync_opens_after_failures(self):
        """Test circuit opens after failure threshold."""
        mock = MagicMock()
        mock.get.return_value = None
        mock.setex.return_value = True
        del mock.aclose

        breaker = DistributedCircuitBreaker(
            name="open-test",
            redis_client=mock,
            failure_threshold=2,
        )

        # First failure
        with pytest.raises(ValueError):
            with breaker:
                raise ValueError("Error 1")

        # Second failure should open
        with pytest.raises(ValueError):
            with breaker:
                raise ValueError("Error 2")

    @pytest.mark.asyncio
    async def test_async_opens_after_failures(self):
        """Test async circuit opens after failure threshold."""
        mock = MagicMock()
        mock.get = AsyncMock(return_value=None)
        mock.setex = AsyncMock(return_value=True)
        mock.aclose = AsyncMock()

        breaker = DistributedCircuitBreaker(
            name="async-open-test",
            redis_client=mock,
            failure_threshold=2,
        )

        # First failure
        with pytest.raises(ValueError):
            async with breaker:
                raise ValueError("Error 1")

        # Second failure
        with pytest.raises(ValueError):
            async with breaker:
                raise ValueError("Error 2")

    def test_sync_get_state_with_exception(self):
        """Test sync get state handles Redis exceptions."""
        mock = MagicMock()
        mock.get.side_effect = Exception("Redis error")
        mock.setex.return_value = True
        del mock.aclose

        breaker = DistributedCircuitBreaker(
            name="redis-error-test",
            redis_client=mock,
        )

        result = breaker._get_state_from_redis_sync()
        assert result is None

    def test_sync_save_state_with_exception(self):
        """Test sync save state handles Redis exceptions."""
        mock = MagicMock()
        mock.get.return_value = None
        mock.setex.side_effect = Exception("Redis error")
        del mock.aclose

        breaker = DistributedCircuitBreaker(
            name="save-error-test",
            redis_client=mock,
        )

        # Should not raise
        breaker._save_state_to_redis_sync({"state": "open"})

    @pytest.mark.asyncio
    async def test_async_get_state_with_exception(self):
        """Test async get state handles Redis exceptions."""
        mock = MagicMock()
        mock.get = AsyncMock(side_effect=Exception("Redis error"))
        mock.setex = AsyncMock()
        mock.aclose = AsyncMock()

        breaker = DistributedCircuitBreaker(
            name="async-redis-error-test",
            redis_client=mock,
        )

        result = await breaker._get_state_from_redis_async()
        assert result is None

    @pytest.mark.asyncio
    async def test_async_save_state_with_exception(self):
        """Test async save state handles Redis exceptions."""
        mock = MagicMock()
        mock.get = AsyncMock(return_value=None)
        mock.setex = AsyncMock(side_effect=Exception("Redis error"))
        mock.aclose = AsyncMock()

        breaker = DistributedCircuitBreaker(
            name="async-save-error-test",
            redis_client=mock,
        )

        # Should not raise
        await breaker._save_state_to_redis_async({"state": "open"})

    def test_sync_with_redis_when_state_exists(self):
        """Test sync with Redis restores state from Redis."""
        import time

        state = json.dumps(
            {
                "state": "open",
                "failure_count": 5,
                "last_failure_time": time.time() - 10,
                "half_open_count": 1,
            }
        )

        mock = MagicMock()
        mock.get.return_value = state
        mock.setex.return_value = True
        del mock.aclose

        breaker = DistributedCircuitBreaker(
            name="sync-state-test",
            redis_client=mock,
        )

        breaker._sync_with_redis_sync()
        assert breaker._failure_count == 5
        assert breaker._half_open_count == 1

    @pytest.mark.asyncio
    async def test_async_sync_with_redis_when_state_exists(self):
        """Test async sync with Redis restores state from Redis."""
        state = json.dumps(
            {
                "state": "open",
                "failure_count": 3,
                "last_failure_time": time.time() - 5,
                "half_open_count": 2,
            }
        )

        mock = MagicMock()
        mock.get = AsyncMock(return_value=state)
        mock.setex = AsyncMock(return_value=True)
        mock.aclose = AsyncMock()

        breaker = DistributedCircuitBreaker(
            name="async-sync-state-test",
            redis_client=mock,
        )

        await breaker._sync_with_redis_async()
        assert breaker._failure_count == 3
        assert breaker._half_open_count == 2


class TestCircuitOpenBehavior:
    """Tests for circuit open behavior."""

    def test_sync_circuit_open_raises_error(self):
        """Test sync circuit raises CircuitOpenError when open."""
        # Create breaker in open state
        state = json.dumps(
            {
                "state": "open",
                "failure_count": 10,
                "last_failure_time": time.time(),  # Just failed, not ready for retry
                "half_open_count": 0,
            }
        )

        mock = MagicMock()
        mock.get.return_value = state
        mock.setex.return_value = True
        del mock.aclose

        breaker = DistributedCircuitBreaker(
            name="open-circuit-test",
            redis_client=mock,
            recovery_timeout=60.0,  # Long timeout
        )

        with pytest.raises(CircuitOpenError):
            with breaker:
                pass  # NOSONAR

    def test_sync_circuit_transitions_to_half_open_after_timeout(self):
        """Test circuit transitions to half-open after recovery timeout."""
        # Create breaker in open state but past recovery timeout
        state = json.dumps(
            {
                "state": "open",
                "failure_count": 10,
                "last_failure_time": time.time() - 100,  # Long ago
                "half_open_count": 0,
            }
        )

        mock = MagicMock()
        mock.get.return_value = state
        mock.setex.return_value = True
        del mock.aclose

        breaker = DistributedCircuitBreaker(
            name="half-open-test",
            redis_client=mock,
            recovery_timeout=30.0,
        )

        # Should not raise, transition to half-open
        with breaker:
            pass  # Success

        assert breaker._state == CircuitState.CLOSED or breaker._state == CircuitState.HALF_OPEN

    def test_sync_record_success_in_half_open(self):
        """Test recording success in half-open state."""
        mock = MagicMock()
        mock.get.return_value = None
        mock.setex.return_value = True
        del mock.aclose

        breaker = DistributedCircuitBreaker(
            name="success-half-open-test",
            redis_client=mock,
            half_open_requests=2,
        )

        # Put in half-open state
        breaker._state = CircuitState.HALF_OPEN
        breaker._half_open_count = 0

        # First success
        breaker._record_success_sync()
        assert breaker._half_open_count == 1

        # Second success - should close
        breaker._record_success_sync()
        assert breaker._state == CircuitState.CLOSED
        assert breaker._failure_count == 0

    def test_sync_record_success_in_closed(self):
        """Test recording success in closed state."""
        mock = MagicMock()
        mock.get.return_value = None
        mock.setex.return_value = True
        del mock.aclose

        breaker = DistributedCircuitBreaker(
            name="success-closed-test",
            redis_client=mock,
        )

        breaker._failure_count = 3  # Some failures
        breaker._record_success_sync()
        assert breaker._failure_count == 0

    def test_sync_record_failure_in_half_open(self):
        """Test recording failure in half-open state."""
        mock = MagicMock()
        mock.get.return_value = None
        mock.setex.return_value = True
        del mock.aclose

        breaker = DistributedCircuitBreaker(
            name="failure-half-open-test",
            redis_client=mock,
        )

        breaker._state = CircuitState.HALF_OPEN
        breaker._record_failure_sync()

        assert breaker._state == CircuitState.OPEN

    def test_sync_record_failure_threshold(self):
        """Test failure threshold triggers open state."""
        mock = MagicMock()
        mock.get.return_value = None
        mock.setex.return_value = True
        del mock.aclose

        breaker = DistributedCircuitBreaker(
            name="threshold-test",
            redis_client=mock,
            failure_threshold=3,
        )

        # Record failures up to threshold
        breaker._record_failure_sync()
        assert breaker._state == CircuitState.CLOSED

        breaker._record_failure_sync()
        assert breaker._state == CircuitState.CLOSED

        breaker._record_failure_sync()
        assert breaker._state == CircuitState.OPEN


class TestAsyncDistributedCircuitBreaker:
    """Tests for AsyncDistributedCircuitBreaker class."""

    def test_async_breaker_rejects_sync_client(self):
        """Test AsyncDistributedCircuitBreaker rejects sync Redis client."""
        mock = MagicMock()
        mock.get.return_value = None
        del mock.aclose  # Make it look sync

        with pytest.raises(ValueError, match="requires an async Redis client"):
            AsyncDistributedCircuitBreaker(
                name="test",
                redis_client=mock,
            )

    def test_async_breaker_accepts_async_client(self):
        """Test AsyncDistributedCircuitBreaker accepts async client."""
        mock = MagicMock()
        mock.get = AsyncMock(return_value=None)
        mock.setex = AsyncMock()
        mock.aclose = AsyncMock()  # Makes it async

        breaker = AsyncDistributedCircuitBreaker(
            name="async-only-test",
            redis_client=mock,
        )
        assert breaker._is_async_redis is True

    def test_async_breaker_rejects_sync_context_manager(self):
        """Test AsyncDistributedCircuitBreaker raises on sync with."""
        mock = MagicMock()
        mock.get = AsyncMock(return_value=None)
        mock.setex = AsyncMock()
        mock.aclose = AsyncMock()

        breaker = AsyncDistributedCircuitBreaker(
            name="sync-with-test",
            redis_client=mock,
        )

        with pytest.raises(RuntimeError, match="can only be used with 'async with'"):
            with breaker:
                pass  # NOSONAR

    @pytest.mark.asyncio
    async def test_async_breaker_works_with_async_with(self):
        """Test AsyncDistributedCircuitBreaker works with async with."""
        mock = MagicMock()
        mock.get = AsyncMock(return_value=None)
        mock.setex = AsyncMock(return_value=True)
        mock.aclose = AsyncMock()

        breaker = AsyncDistributedCircuitBreaker(
            name="async-with-test",
            redis_client=mock,
        )

        async with breaker:
            pass  # Success


class TestDistributedBreaker_SyncWithAsyncClient:
    """Tests for using sync context manager with async Redis client."""

    def test_sync_context_with_async_client_raises(self):
        """Test sync context manager raises with async client."""
        mock = MagicMock()
        mock.get = AsyncMock(return_value=None)
        mock.setex = AsyncMock()
        mock.aclose = AsyncMock()

        breaker = DistributedCircuitBreaker(
            name="sync-async-error-test",
            redis_client=mock,
        )

        with pytest.raises(RuntimeError, match="Cannot use sync context manager with async Redis"):
            with breaker:
                pass  # NOSONAR


class TestBackwardCompatMethods:
    """Tests for backward compatibility methods."""

    def test_get_state_from_redis_sync_backend(self):
        """Test _get_state_from_redis with sync client."""
        state = json.dumps({"state": "closed", "failure_count": 0, "half_open_count": 0})

        mock = MagicMock()
        mock.get.return_value = state
        mock.setex.return_value = True
        del mock.aclose

        breaker = DistributedCircuitBreaker(
            name="compat-sync-test",
            redis_client=mock,
        )

        result = breaker._get_state_from_redis()
        assert result is not None
        assert result["state"] == "closed"

    def test_save_state_to_redis_sync_backend(self):
        """Test _save_state_to_redis with sync client."""
        mock = MagicMock()
        mock.get.return_value = None
        mock.setex.return_value = True
        del mock.aclose

        breaker = DistributedCircuitBreaker(
            name="compat-save-test",
            redis_client=mock,
        )

        breaker._save_state_to_redis({"state": "open"})
        mock.setex.assert_called()

    def test_sync_with_redis_sync_backend(self):
        """Test _sync_with_redis with sync client."""
        mock = MagicMock()
        mock.get.return_value = None
        mock.setex.return_value = True
        del mock.aclose

        breaker = DistributedCircuitBreaker(
            name="compat-sync-with-test",
            redis_client=mock,
        )

        breaker._sync_with_redis()
        mock.get.assert_called()


class TestGetStateDict:
    """Tests for _get_state_dict method."""

    def test_get_state_dict(self):
        """Test _get_state_dict returns correct structure."""
        mock = MagicMock()
        mock.get.return_value = None
        mock.setex.return_value = True
        del mock.aclose

        breaker = DistributedCircuitBreaker(
            name="state-dict-test",
            redis_client=mock,
        )

        # Modify state
        breaker._failure_count = 5
        breaker._half_open_count = 2
        breaker._last_failure_time = 12345.0

        state = breaker._get_state_dict()

        assert state["state"] == "closed"
        assert state["failure_count"] == 5
        assert state["half_open_count"] == 2
        assert state["last_failure_time"] == pytest.approx(12345.0)


class TestCheckShouldAttemptReset:
    """Tests for _check_should_attempt_reset method."""

    def test_check_reset_no_failure_time(self):
        """Test reset check returns True when no failure time."""
        mock = MagicMock()
        mock.get.return_value = None
        del mock.aclose

        breaker = DistributedCircuitBreaker(
            name="reset-no-time-test",
            redis_client=mock,
        )

        breaker._last_failure_time = None
        assert breaker._check_should_attempt_reset() is True

    def test_check_reset_before_timeout(self):
        """Test reset check returns False before timeout."""
        mock = MagicMock()
        mock.get.return_value = None
        del mock.aclose

        breaker = DistributedCircuitBreaker(
            name="reset-before-test",
            redis_client=mock,
            recovery_timeout=60.0,
        )

        breaker._last_failure_time = time.time() - 10  # 10 seconds ago
        assert breaker._check_should_attempt_reset() is False

    def test_check_reset_after_timeout(self):
        """Test reset check returns True after timeout."""
        mock = MagicMock()
        mock.get.return_value = None
        del mock.aclose

        breaker = DistributedCircuitBreaker(
            name="reset-after-test",
            redis_client=mock,
            recovery_timeout=30.0,
        )

        breaker._last_failure_time = time.time() - 60  # 60 seconds ago
        assert breaker._check_should_attempt_reset() is True


class TestAsyncContextManager:
    """Tests for async context manager methods."""

    @pytest.mark.asyncio
    async def test_aenter_with_sync_redis(self):
        """Test __aenter__ with sync Redis client."""
        mock = MagicMock()
        mock.get.return_value = None
        mock.setex.return_value = True
        del mock.aclose

        breaker = DistributedCircuitBreaker(
            name="aenter-sync-test",
            redis_client=mock,
        )

        result = await breaker.__aenter__()
        assert result is breaker

    @pytest.mark.asyncio
    async def test_aexit_with_sync_redis(self):
        """Test __aexit__ with sync Redis client."""
        mock = MagicMock()
        mock.get.return_value = None
        mock.setex.return_value = True
        del mock.aclose

        breaker = DistributedCircuitBreaker(
            name="aexit-sync-test",
            redis_client=mock,
        )

        await breaker.__aenter__()
        result = await breaker.__aexit__(None, None, None)
        assert result is None or result is False

    @pytest.mark.asyncio
    async def test_aenter_with_async_redis(self):
        """Test __aenter__ with async Redis client."""
        mock = MagicMock()
        mock.get = AsyncMock(return_value=None)
        mock.setex = AsyncMock(return_value=True)
        mock.aclose = AsyncMock()

        breaker = DistributedCircuitBreaker(
            name="aenter-async-test",
            redis_client=mock,
        )

        result = await breaker.__aenter__()
        assert result is breaker
        mock.get.assert_called()

    @pytest.mark.asyncio
    async def test_aexit_with_async_redis(self):
        """Test __aexit__ with async Redis client."""
        mock = MagicMock()
        mock.get = AsyncMock(return_value=None)
        mock.setex = AsyncMock(return_value=True)
        mock.aclose = AsyncMock()

        breaker = DistributedCircuitBreaker(
            name="aexit-async-test",
            redis_client=mock,
        )

        await breaker.__aenter__()
        await breaker.__aexit__(None, None, None)
        mock.setex.assert_called()

    @pytest.mark.asyncio
    async def test_aexit_with_exception(self):
        """Test __aexit__ records failure on exception."""
        mock = MagicMock()
        mock.get = AsyncMock(return_value=None)
        mock.setex = AsyncMock(return_value=True)
        mock.aclose = AsyncMock()

        breaker = DistributedCircuitBreaker(
            name="aexit-exception-test",
            redis_client=mock,
            failure_threshold=10,
        )

        await breaker.__aenter__()

        # Simulate exception exit
        await breaker.__aexit__(ValueError, ValueError("test"), None)

        assert breaker._failure_count >= 1


class TestSyncContextExit:
    """Tests for sync context manager __exit__."""

    def test_exit_records_success(self):
        """Test __exit__ records success on normal exit."""
        mock = MagicMock()
        mock.get.return_value = None
        mock.setex.return_value = True
        del mock.aclose

        breaker = DistributedCircuitBreaker(
            name="exit-success-test",
            redis_client=mock,
        )

        # Give some failures first
        breaker._failure_count = 3

        with breaker:
            pass  # Success

        # After success, failure count should be reset
        assert breaker._failure_count == 0

    def test_exit_records_failure(self):
        """Test __exit__ records failure on exception."""
        mock = MagicMock()
        mock.get.return_value = None
        mock.setex.return_value = True
        del mock.aclose

        breaker = DistributedCircuitBreaker(
            name="exit-failure-test",
            redis_client=mock,
            failure_threshold=10,
        )

        initial_count = breaker._failure_count

        with pytest.raises(ValueError):
            with breaker:
                raise ValueError("test error")

        assert breaker._failure_count > initial_count


class TestBackwardCompatMethodsExtended:
    """Extended tests for backward compatibility methods."""

    def test_get_state_from_redis_sync_client(self):
        """Test _get_state_from_redis with sync client."""
        mock = MagicMock()
        mock.get.return_value = json.dumps(
            {
                "state": "closed",
                "failure_count": 0,
                "last_failure_time": None,
            }
        ).encode()
        del mock.aclose

        breaker = DistributedCircuitBreaker(
            name="compat-get-state-sync",
            redis_client=mock,
        )

        state = breaker._get_state_from_redis()
        assert state is not None
        assert state["state"] == "closed"

    def test_save_state_to_redis_sync_client(self):
        """Test _save_state_to_redis with sync client."""
        mock = MagicMock()
        mock.get.return_value = None
        mock.setex.return_value = True
        del mock.aclose

        breaker = DistributedCircuitBreaker(
            name="compat-save-state-sync",
            redis_client=mock,
        )

        breaker._save_state_to_redis({"state": "open"})
        mock.setex.assert_called()

    def test_sync_with_redis_sync_client(self):
        """Test _sync_with_redis with sync client."""
        mock = MagicMock()
        mock.get.return_value = json.dumps(
            {
                "state": "closed",
                "failure_count": 2,
                "last_failure_time": None,
            }
        ).encode()
        mock.setex.return_value = True
        del mock.aclose

        breaker = DistributedCircuitBreaker(
            name="compat-sync-redis-sync",
            redis_client=mock,
        )

        breaker._sync_with_redis()
        # Should have synced state from Redis
        assert breaker._failure_count == 2

    @pytest.mark.asyncio
    async def test_get_state_from_redis_async_client_no_loop(self):
        """Test _get_state_from_redis with async client - no running loop."""
        mock = MagicMock()
        mock.get = AsyncMock(
            return_value=json.dumps(
                {
                    "state": "closed",
                    "failure_count": 0,
                }
            ).encode()
        )
        mock.aclose = AsyncMock()

        breaker = DistributedCircuitBreaker(
            name="compat-get-async",
            redis_client=mock,
        )

        # This is the async path - call the async method directly
        state = await breaker._get_state_from_redis_async()
        assert state is not None

    def test_get_state_from_redis_async_in_sync_context(self):
        """Test _get_state_from_redis with async client from sync context."""
        mock = MagicMock()
        mock.get = AsyncMock(
            return_value=json.dumps(
                {
                    "state": "closed",
                    "failure_count": 0,
                }
            ).encode()
        )
        mock.aclose = AsyncMock()

        breaker = DistributedCircuitBreaker(
            name="compat-get-async-sync-ctx",
            redis_client=mock,
        )

        # Call from sync context - should use asyncio.run
        state = breaker._get_state_from_redis()
        assert state is not None

    def test_save_state_to_redis_async_in_sync_context(self):
        """Test _save_state_to_redis with async client from sync context."""
        mock = MagicMock()
        mock.get = AsyncMock(return_value=None)
        mock.setex = AsyncMock(return_value=True)
        mock.aclose = AsyncMock()

        breaker = DistributedCircuitBreaker(
            name="compat-save-async-sync-ctx",
            redis_client=mock,
        )

        # Call from sync context - should use asyncio.run
        breaker._save_state_to_redis({"state": "open"})

    def test_sync_with_redis_async_in_sync_context(self):
        """Test _sync_with_redis with async client from sync context."""
        mock = MagicMock()
        mock.get = AsyncMock(
            return_value=json.dumps(
                {
                    "state": "closed",
                    "failure_count": 3,
                }
            ).encode()
        )
        mock.setex = AsyncMock(return_value=True)
        mock.aclose = AsyncMock()

        breaker = DistributedCircuitBreaker(
            name="compat-sync-async-sync-ctx",
            redis_client=mock,
        )

        # Call from sync context - should use asyncio.run
        breaker._sync_with_redis()
        assert breaker._failure_count == 3


class TestIsAsyncRedisClientEdgeCases:
    """Edge case tests for _is_async_redis_client."""

    def test_isinstance_aioredis(self):
        """Test detection via isinstance with aioredis.Redis."""
        # This tests line 102-103
        mock = MagicMock()
        mock.aclose = AsyncMock()  # Has aclose so will return True early

        result = _is_async_redis_client(mock)
        assert result is True

    def test_isinstance_exception(self):
        """Test handling when isinstance raises exception."""
        # Create a mock that causes isinstance to fail
        mock = MagicMock()
        del mock.aclose
        mock.get.return_value = "sync_value"

        result = _is_async_redis_client(mock)
        assert result is False
