"""
Resilience Patterns for obskit
===============================

This module provides resilience patterns to help your services handle
failures gracefully:

1. **Circuit Breaker**: Prevents cascading failures
2. **Retry**: Handles transient errors with backoff
3. **Rate Limiter**: Controls request throughput

Why Resilience Patterns?
------------------------
In distributed systems, failures are normal:

- Networks are unreliable
- Services go down for maintenance
- Resources become exhausted
- Bugs cause unexpected errors

Without resilience patterns, a single failing dependency can:
- Cause cascading failures across services
- Exhaust resources (connections, threads, memory)
- Create retry storms that overwhelm systems
- Lead to complete system outage

Circuit Breaker Pattern
-----------------------
The circuit breaker prevents cascading failures by "breaking" the
circuit when a service is failing, giving it time to recover.

.. code-block:: text

    State: CLOSED (normal operation)
           ↓
    [Failures exceed threshold]
           ↓
    State: OPEN (fast fail, no calls to service)
           ↓
    [After recovery timeout]
           ↓
    State: HALF_OPEN (test with limited requests)
           ↓
    [If test succeeds] → CLOSED
    [If test fails] → OPEN

Example:

.. code-block:: python

    from obskit.resilience import CircuitBreaker

    breaker = CircuitBreaker(
        name="payment_api",
        failure_threshold=5,      # Open after 5 failures
        recovery_timeout=30.0,    # Test recovery after 30s
    )

    async def charge_card(amount: float):
        async with breaker:
            return await payment_api.charge(amount)
        # If payment_api is failing, raises CircuitOpenError
        # instead of calling the failing API

Retry Pattern
-------------
Retries handle transient errors (network blips, temporary overload)
by attempting the operation again with exponential backoff.

.. code-block:: text

    Attempt 1: Call service → Fails
           ↓
    Wait: 1 second (+ random jitter)
           ↓
    Attempt 2: Call service → Fails
           ↓
    Wait: 2 seconds (+ random jitter)
           ↓
    Attempt 3: Call service → Succeeds!

Example:

.. code-block:: python

    from obskit.resilience import retry

    @retry(max_attempts=3, base_delay=1.0)
    async def fetch_data():
        return await external_api.get("/data")
    # Will retry up to 3 times with exponential backoff

Rate Limiting Pattern
---------------------
Rate limiting controls the flow of requests to prevent overwhelming
services or exceeding API quotas.

.. code-block:: text

    Request 1: Allow ✓
    Request 2: Allow ✓
    Request 3: Allow ✓
    Request 4: Deny ✗ (rate limit exceeded)
    [After time window passes]
    Request 5: Allow ✓

Example:

.. code-block:: python

    from obskit.resilience import RateLimiter

    # 100 requests per minute
    limiter = RateLimiter(requests=100, window_seconds=60)

    async def handle_request():
        async with limiter:
            return await process_request()
        # Raises RateLimitExceeded if over limit

Combining Patterns
------------------
Patterns can be combined for comprehensive resilience:

.. code-block:: python

    from obskit.resilience import CircuitBreaker, retry, RateLimiter

    breaker = CircuitBreaker("payment_api", failure_threshold=5)
    limiter = RateLimiter(requests=100, window_seconds=60)

    @retry(max_attempts=3, base_delay=0.5)
    async def process_payment(amount: float):
        # Rate limit → Circuit breaker → Actual call
        async with limiter:
            async with breaker:
                return await payment_api.charge(amount)

    # This provides:
    # 1. Rate limiting to protect downstream service
    # 2. Circuit breaker to fail fast when service is down
    # 3. Retry for transient errors

See Also
--------
obskit.decorators : Observability for resilience patterns
obskit.metrics : Track resilience pattern metrics
obskit.logging : Log resilience events
"""

from obskit.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerError,
    CircuitOpenError,
)
from obskit.resilience.rate_limiter import (
    RateLimiter,
    RateLimitExceeded,
    SlidingWindowRateLimiter,
    TokenBucketRateLimiter,
)
from obskit.resilience.retry import (
    RetryConfig,
    RetryError,
    retry,
    retry_async,
)

__all__ = [
    # ==========================================================================
    # Circuit Breaker
    # ==========================================================================
    # Main circuit breaker class
    "CircuitBreaker",
    # Base error class
    "CircuitBreakerError",
    # Raised when circuit is open
    "CircuitOpenError",
    # ==========================================================================
    # Retry
    # ==========================================================================
    # Async retry decorator
    "retry",
    # Alias for async retry
    "retry_async",
    # Retry configuration
    "RetryConfig",
    # Raised when all retries exhausted
    "RetryError",
    # ==========================================================================
    # Rate Limiting
    # ==========================================================================
    # Base rate limiter (sliding window)
    "RateLimiter",
    # Sliding window implementation
    "SlidingWindowRateLimiter",
    # Token bucket implementation
    "TokenBucketRateLimiter",
    # Raised when rate limit exceeded
    "RateLimitExceeded",
]
