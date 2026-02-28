"""
Distributed Circuit Breaker (Redis-backed)
===========================================

This module provides Redis-backed circuit breakers that share state
across multiple service instances, enabling faster failure detection
in multi-instance deployments.

Now supports both sync (redis.Redis) and async (redis.asyncio.Redis) clients.

Example - Sync Redis
--------------------
.. code-block:: python

    from obskit.resilience.distributed import DistributedCircuitBreaker
    import redis

    redis_client = redis.Redis(host="localhost", port=6379)

    breaker = DistributedCircuitBreaker(
        name="payment_api",
        redis_client=redis_client,
        failure_threshold=10,
        recovery_timeout=60.0,
    )

    async with breaker:
        result = await payment_api.charge(amount)

Example - Async Redis
---------------------
.. code-block:: python

    from obskit.resilience.distributed import DistributedCircuitBreaker
    import redis.asyncio as aioredis

    redis_client = aioredis.Redis(host="localhost", port=6379)

    breaker = DistributedCircuitBreaker(
        name="payment_api",
        redis_client=redis_client,
        failure_threshold=10,
        recovery_timeout=60.0,
    )

    async with breaker:
        result = await payment_api.charge(amount)
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import TYPE_CHECKING, Any

from obskit.logging import get_logger
from obskit.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitState,
)

if TYPE_CHECKING:
    pass

logger = get_logger("obskit.resilience.distributed")

try:
    import importlib.util

    REDIS_AVAILABLE = importlib.util.find_spec("redis") is not None
except ImportError:  # pragma: no cover
    REDIS_AVAILABLE = False

# Check for async redis
try:
    import redis.asyncio as aioredis

    ASYNC_REDIS_AVAILABLE = True
except ImportError:  # pragma: no cover
    ASYNC_REDIS_AVAILABLE = False
    aioredis = None  # type: ignore[assignment]


def _is_async_redis_client(client: Any) -> bool:
    """
    Detect if a Redis client is async (redis.asyncio).

    Parameters
    ----------
    client : Any
        Redis client instance.

    Returns
    -------
    bool
        True if the client is async, False otherwise.
    """
    # Check for redis.asyncio.Redis
    if ASYNC_REDIS_AVAILABLE and aioredis is not None:  # pragma: no cover
        try:
            if isinstance(client, aioredis.Redis):
                return True
        except Exception:  # nosec B110 - type check failure is expected when aioredis unavailable
            pass  # isinstance() may fail if aioredis types are not available

    # Check for common async Redis client patterns
    # - Has coroutine methods (get returns coroutine when called)
    # - Has 'aclose' method (async close)
    if hasattr(client, "aclose"):
        return True

    # Check if get() returns a coroutine
    try:
        result = client.get("__obskit_test_async__")
        if asyncio.iscoroutine(result):
            # Clean up the coroutine
            result.close()
            return True
    except Exception:  # nosec B110 - type detection failure is expected for some clients
        pass  # Client.get() may raise for various reasons (connection, type issues)

    return False


class DistributedCircuitBreaker(CircuitBreaker):
    """
    Circuit breaker with Redis-backed shared state.

    This circuit breaker shares state across multiple service instances
    via Redis, enabling faster failure detection in multi-instance deployments.

    Supports both sync and async Redis clients:
    - redis.Redis (sync)
    - redis.asyncio.Redis (async)

    Parameters
    ----------
    name : str
        Unique name for the circuit breaker.

    redis_client : Any
        Redis client instance (redis.Redis or redis.asyncio.Redis).

    failure_threshold : int, optional
        Number of failures before opening circuit.
        Default: 5

    recovery_timeout : float, optional
        Seconds to wait before testing recovery.
        Default: 30.0

    half_open_requests : int, optional
        Number of test requests in half-open state.
        Default: 3

    key_prefix : str, optional
        Redis key prefix. Default: "obskit:circuit_breaker:"

    ttl_seconds : int, optional
        TTL for Redis keys. Default: 3600 (1 hour)

    Example - Sync Redis
    -------------------
    >>> import redis
    >>> from obskit.resilience.distributed import DistributedCircuitBreaker
    >>>
    >>> redis_client = redis.Redis(host="localhost", port=6379)
    >>>
    >>> breaker = DistributedCircuitBreaker(
    ...     name="payment_api",
    ...     redis_client=redis_client,
    ...     failure_threshold=10,
    ... )
    >>>
    >>> async with breaker:
    ...     result = await payment_api.charge(amount)

    Example - Async Redis
    --------------------
    >>> import redis.asyncio as aioredis
    >>> from obskit.resilience.distributed import DistributedCircuitBreaker
    >>>
    >>> redis_client = aioredis.Redis(host="localhost", port=6379)
    >>>
    >>> breaker = DistributedCircuitBreaker(
    ...     name="payment_api",
    ...     redis_client=redis_client,
    ...     failure_threshold=10,
    ... )
    >>>
    >>> async with breaker:
    ...     result = await payment_api.charge(amount)
    """

    def __init__(
        self,
        name: str,
        redis_client: Any,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_requests: int = 3,
        key_prefix: str = "obskit:circuit_breaker:",
        ttl_seconds: int = 3600,
    ) -> None:
        if not REDIS_AVAILABLE and not ASYNC_REDIS_AVAILABLE:  # pragma: no cover
            raise ImportError("Redis is not installed. Install with: pip install redis")

        # Initialize base circuit breaker
        super().__init__(
            name=name,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            half_open_requests=half_open_requests,
        )

        self.redis_client = redis_client
        self.key_prefix = key_prefix
        self.ttl_seconds = ttl_seconds
        self._redis_key = f"{key_prefix}{name}"
        self._is_async_redis = _is_async_redis_client(redis_client)
        # Initialize half_open_count for state dict serialization
        self._half_open_count = 0

        logger.debug(
            "distributed_circuit_breaker_init",
            name=name,
            is_async_redis=self._is_async_redis,
            key=self._redis_key,
        )

    # =========================================================================
    # Sync Redis Operations
    # =========================================================================

    def _get_state_from_redis_sync(self) -> dict[str, Any] | None:
        """Get circuit breaker state from Redis (sync)."""
        try:
            data = self.redis_client.get(self._redis_key)
            if data:
                result: dict[str, Any] = json.loads(data)
                return result
        except Exception as e:
            logger.warning(
                "redis_state_read_failed",
                error=str(e),
                error_type=type(e).__name__,
                key=self._redis_key,
            )
        return None

    def _save_state_to_redis_sync(self, state: dict[str, Any]) -> None:
        """Save circuit breaker state to Redis (sync)."""
        try:
            data = json.dumps(state)
            self.redis_client.setex(
                self._redis_key,
                self.ttl_seconds,
                data,
            )
        except Exception as e:
            logger.warning(
                "redis_state_write_failed",
                error=str(e),
                error_type=type(e).__name__,
                key=self._redis_key,
            )

    def _sync_with_redis_sync(self) -> None:
        """Sync local state with Redis (sync)."""
        redis_state = self._get_state_from_redis_sync()

        if redis_state:
            self._state = CircuitState(redis_state.get("state", "closed"))
            self._failure_count = redis_state.get("failure_count", 0)
            self._last_failure_time = redis_state.get("last_failure_time")
            self._half_open_count = redis_state.get("half_open_count", 0)
        else:
            self._save_state_to_redis_sync(self._get_state_dict())

    # =========================================================================
    # Async Redis Operations
    # =========================================================================

    async def _get_state_from_redis_async(self) -> dict[str, Any] | None:
        """Get circuit breaker state from Redis (async)."""
        try:
            data = await self.redis_client.get(self._redis_key)
            if data:
                result: dict[str, Any] = json.loads(data)
                return result
        except Exception as e:
            logger.warning(
                "redis_state_read_failed_async",
                error=str(e),
                error_type=type(e).__name__,
                key=self._redis_key,
            )
        return None

    async def _save_state_to_redis_async(self, state: dict[str, Any]) -> None:
        """Save circuit breaker state to Redis (async)."""
        try:
            data = json.dumps(state)
            await self.redis_client.setex(
                self._redis_key,
                self.ttl_seconds,
                data,
            )
        except Exception as e:
            logger.warning(
                "redis_state_write_failed_async",
                error=str(e),
                error_type=type(e).__name__,
                key=self._redis_key,
            )

    async def _sync_with_redis_async(self) -> None:
        """Sync local state with Redis (async)."""
        redis_state = await self._get_state_from_redis_async()

        if redis_state:
            self._state = CircuitState(redis_state.get("state", "closed"))
            self._failure_count = redis_state.get("failure_count", 0)
            self._last_failure_time = redis_state.get("last_failure_time")
            self._half_open_count = redis_state.get("half_open_count", 0)
        else:
            await self._save_state_to_redis_async(self._get_state_dict())

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _get_state_dict(self) -> dict[str, Any]:
        """Get current state as dictionary."""
        return {
            "state": self._state.value,
            "failure_count": self._failure_count,
            "last_failure_time": self._last_failure_time,
            "half_open_count": self._half_open_count,
        }

    # =========================================================================
    # Backward Compatibility (kept for existing code)
    # =========================================================================

    def _get_state_from_redis(self) -> dict[str, Any] | None:
        """Get circuit breaker state from Redis (backward compat)."""
        if self._is_async_redis:
            # For async clients called from sync context, we need to run in event loop
            # This is a fallback - prefer using the async context manager
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():  # pragma: no cover
                    # If we're in an async context, this shouldn't be called
                    logger.warning(
                        "sync_redis_call_in_async_context",
                        message="Calling sync Redis method from async context",
                    )
                    return None
                return loop.run_until_complete(self._get_state_from_redis_async())
            except RuntimeError:  # pragma: no cover
                # No event loop, create one
                return asyncio.run(self._get_state_from_redis_async())
        return self._get_state_from_redis_sync()

    def _save_state_to_redis(self, state: dict[str, Any]) -> None:
        """Save circuit breaker state to Redis (backward compat)."""
        if self._is_async_redis:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():  # pragma: no cover
                    logger.warning(
                        "sync_redis_call_in_async_context",
                        message="Calling sync Redis method from async context",
                    )
                    return
                loop.run_until_complete(self._save_state_to_redis_async(state))
            except RuntimeError:  # pragma: no cover
                asyncio.run(self._save_state_to_redis_async(state))
        else:
            self._save_state_to_redis_sync(state)

    def _sync_with_redis(self) -> None:
        """Sync local state with Redis (backward compat)."""
        if self._is_async_redis:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():  # pragma: no cover
                    logger.warning(
                        "sync_redis_call_in_async_context",
                        message="Calling sync Redis method from async context",
                    )
                    return
                loop.run_until_complete(self._sync_with_redis_async())
            except RuntimeError:  # pragma: no cover
                asyncio.run(self._sync_with_redis_async())
        else:
            self._sync_with_redis_sync()

    # =========================================================================
    # Async Context Manager
    # =========================================================================

    async def __aenter__(self) -> DistributedCircuitBreaker:
        """Enter circuit breaker context with Redis sync."""
        # Sync with Redis before checking state
        if self._is_async_redis:
            await self._sync_with_redis_async()
        else:
            self._sync_with_redis_sync()

        # Use parent's logic
        await super().__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> bool:
        """Exit circuit breaker context and sync to Redis."""
        # Let parent handle the logic
        result = await super().__aexit__(exc_type, exc_val, exc_tb)

        # Sync state to Redis after update
        if self._is_async_redis:
            await self._save_state_to_redis_async(self._get_state_dict())
        else:
            self._save_state_to_redis_sync(self._get_state_dict())

        return result

    # =========================================================================
    # Sync Context Manager (for sync Redis clients)
    # =========================================================================

    def _check_should_attempt_reset(self) -> bool:
        """Check if recovery timeout has elapsed and we should attempt reset."""
        if self._last_failure_time is None:
            return True
        elapsed = time.time() - self._last_failure_time
        return elapsed >= self._recovery_timeout

    def _record_success_sync(self) -> None:
        """Record a successful call (sync version)."""
        if self._state == CircuitState.HALF_OPEN:
            self._half_open_count += 1
            if self._half_open_count >= self._half_open_requests:
                self._state = CircuitState.CLOSED
                self._failure_count = 0
        elif self._state == CircuitState.CLOSED:  # pragma: no branch
            self._failure_count = 0

    def _record_failure_sync(self, error: BaseException | None = None) -> None:
        """Record a failed call (sync version)."""
        self._failure_count += 1
        self._last_failure_time = time.time()

        if self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.OPEN
        elif self._state == CircuitState.CLOSED:  # pragma: no branch
            if self._failure_count >= self._failure_threshold:
                self._state = CircuitState.OPEN

    def __enter__(self) -> DistributedCircuitBreaker:
        """Enter circuit breaker context (sync) with Redis sync."""
        if self._is_async_redis:
            raise RuntimeError(
                "Cannot use sync context manager with async Redis client. Use 'async with' instead."
            )

        # Sync with Redis before checking state
        self._sync_with_redis_sync()

        # Check if circuit is open
        from obskit.resilience.circuit_breaker import CircuitOpenError

        if self._state == CircuitState.OPEN:
            if not self._check_should_attempt_reset():
                # Calculate time until retry
                time_until_retry = 0.0
                if self._last_failure_time is not None:  # pragma: no branch
                    elapsed = time.time() - self._last_failure_time
                    time_until_retry = max(0.0, self._recovery_timeout - elapsed)
                raise CircuitOpenError(self.name, time_until_retry)
            # Transition to half-open
            self._state = CircuitState.HALF_OPEN
            self._half_open_count = 0

        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Exit circuit breaker context (sync) and sync to Redis."""
        if exc_type is not None:
            self._record_failure_sync(exc_val)
        else:
            self._record_success_sync()

        # Sync state to Redis after update
        self._save_state_to_redis_sync(self._get_state_dict())


class AsyncDistributedCircuitBreaker(DistributedCircuitBreaker):
    """
    Async-only distributed circuit breaker.

    This is a convenience class that enforces async Redis usage.
    Use this when you want to ensure only async operations are used.

    Example
    -------
    >>> import redis.asyncio as aioredis
    >>> from obskit.resilience.distributed import AsyncDistributedCircuitBreaker
    >>>
    >>> redis_client = aioredis.Redis(host="localhost", port=6379)
    >>>
    >>> breaker = AsyncDistributedCircuitBreaker(
    ...     name="payment_api",
    ...     redis_client=redis_client,
    ... )
    >>>
    >>> async with breaker:
    ...     result = await payment_api.charge(amount)
    """

    def __init__(
        self,
        name: str,
        redis_client: Any,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_requests: int = 3,
        key_prefix: str = "obskit:circuit_breaker:",
        ttl_seconds: int = 3600,
    ) -> None:
        if not ASYNC_REDIS_AVAILABLE:  # pragma: no cover
            raise ImportError(
                "Async Redis is not available. Install with: pip install 'redis[hiredis]>=5.0.0'"
            )

        super().__init__(
            name=name,
            redis_client=redis_client,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            half_open_requests=half_open_requests,
            key_prefix=key_prefix,
            ttl_seconds=ttl_seconds,
        )

        if not self._is_async_redis:
            raise ValueError(
                "AsyncDistributedCircuitBreaker requires an async Redis client "
                "(redis.asyncio.Redis). Use DistributedCircuitBreaker for sync clients."
            )

    def __enter__(self) -> AsyncDistributedCircuitBreaker:
        """Prevent sync context manager usage."""
        raise RuntimeError(
            "AsyncDistributedCircuitBreaker can only be used with 'async with'. "
            "Use DistributedCircuitBreaker if you need sync support."
        )


__all__ = [
    "DistributedCircuitBreaker",
    "AsyncDistributedCircuitBreaker",
    "REDIS_AVAILABLE",
    "ASYNC_REDIS_AVAILABLE",
]
