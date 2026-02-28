"""
Rate Limiter Implementation
===========================

Rate limiting controls the flow of requests to prevent overwhelming
services or exceeding API quotas.

Why Rate Limiting?
------------------
Rate limiting is essential for:

1. **Protecting services**: Prevent overload from traffic spikes
2. **API compliance**: Stay within third-party API quotas
3. **Fair usage**: Distribute capacity among clients
4. **Cost control**: Limit expensive operations

Rate Limiting Algorithms
------------------------
This module provides two common algorithms:

**Sliding Window**
    Counts requests in a rolling time window.

    - Accurate: Exactly N requests per window
    - Memory: Stores timestamp of each request
    - Use case: General rate limiting

**Token Bucket**
    Adds tokens at a fixed rate, requests consume tokens.

    - Flexible: Allows bursts up to bucket size
    - Memory: Just stores token count and last update
    - Use case: Bursty traffic patterns

Comparison
----------

.. code-block:: text

    Sliding Window (10 req/min):

    Time:     0s    10s   20s   30s   40s   50s   60s
    Requests: ▓▓▓▓▓ ▓▓▓▓▓                     ▓▓▓▓▓
              └─────────────── 10 requests ───────────┘

    Token Bucket (10 tokens, 10/min refill):

    Time:     0s    10s   20s   30s   40s   50s   60s
    Tokens:   10    8     10    10    7     10    10
    Requests: ▓▓    ▓     ▓     ▓▓▓   ▓     ▓▓▓▓▓
              └─ Can burst up to bucket size ─┘

Example - Basic Usage
---------------------
.. code-block:: python

    from obskit.resilience import RateLimiter

    # 100 requests per minute
    limiter = RateLimiter(requests=100, window_seconds=60)

    async def handle_request():
        async with limiter:
            return await process_request()

Example - Token Bucket
----------------------
.. code-block:: python

    from obskit.resilience import TokenBucketRateLimiter

    # 10 tokens max, refill 1 token per second
    limiter = TokenBucketRateLimiter(
        bucket_size=10,
        refill_rate=1.0,  # tokens per second
    )

    async def handle_request():
        async with limiter:
            return await process_request()

Example - Handling Rate Limit
-----------------------------
.. code-block:: python

    from obskit.resilience import RateLimiter, RateLimitExceeded

    limiter = RateLimiter(requests=100, window_seconds=60)

    async def handle_request():
        try:
            async with limiter:
                return await process_request()
        except RateLimitExceeded as e:
            return {"error": f"Rate limit exceeded. Retry after {e.retry_after:.1f}s"}
"""

from __future__ import annotations

import asyncio
import time
from collections import deque
from typing import Any

from obskit.config import get_settings
from obskit.logging import get_logger

# Logger
logger = get_logger("obskit.rate_limiter")


class RateLimitExceeded(Exception):
    """
    Raised when rate limit is exceeded.

    Attributes
    ----------
    limit : int
        The rate limit that was exceeded.
    window_seconds : float
        The time window in seconds.
    retry_after : float
        Seconds until another request may be allowed.

    Example
    -------
    >>> try:
    ...     async with limiter:
    ...         await process()
    ... except RateLimitExceeded as e:
    ...     return Response(
    ...         status_code=429,
    ...         headers={"Retry-After": str(int(e.retry_after))},
    ...     )
    """

    def __init__(
        self,
        limit: int,
        window_seconds: float,
        retry_after: float,
    ) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self.retry_after = retry_after

        super().__init__(
            f"Rate limit exceeded: {limit} requests per {window_seconds}s. "
            f"Retry after {retry_after:.1f}s."
        )


class RateLimiter:
    """
    Sliding window rate limiter.

    Limits requests to a fixed number within a rolling time window.
    This is the most accurate rate limiting algorithm.

    Parameters
    ----------
    requests : int, optional
        Maximum requests per window.
        Default: from settings.

    window_seconds : float, optional
        Time window in seconds.
        Default: from settings.

    Attributes
    ----------
    requests : int
        Maximum allowed requests.

    window_seconds : float
        Time window size.

    current_count : int
        Current number of requests in window.

    Example - Basic Usage
    ---------------------
    >>> from obskit.resilience import RateLimiter
    >>>
    >>> # 100 requests per minute
    >>> limiter = RateLimiter(requests=100, window_seconds=60)
    >>>
    >>> async def handle_request():
    ...     async with limiter:
    ...         return await process_request()

    Example - Check Without Acquiring
    ---------------------------------
    >>> limiter = RateLimiter(requests=100, window_seconds=60)
    >>>
    >>> if limiter.would_exceed():
    ...     return "Rate limit would be exceeded"
    >>>
    >>> async with limiter:
    ...     return await process_request()

    Example - Manual Acquire/Release
    --------------------------------
    >>> limiter = RateLimiter(requests=100, window_seconds=60)
    >>>
    >>> acquired = await limiter.acquire()
    >>> if not acquired:
    ...     return "Rate limit exceeded"
    >>>
    >>> try:
    ...     return await process_request()
    ... finally:
    ...     pass  # No explicit release needed

    Example - HTTP Response Headers
    -------------------------------
    >>> limiter = RateLimiter(requests=100, window_seconds=60)
    >>>
    >>> async def handle_request():
    ...     try:
    ...         async with limiter:
    ...             result = await process_request()
    ...             return Response(
    ...                 content=result,
    ...                 headers={
    ...                     "X-RateLimit-Limit": str(limiter.requests),
    ...                     "X-RateLimit-Remaining": str(limiter.remaining),
    ...                 },
    ...             )
    ...     except RateLimitExceeded as e:
    ...         return Response(
    ...             status_code=429,
    ...             headers={
    ...                 "X-RateLimit-Limit": str(e.limit),
    ...                 "X-RateLimit-Remaining": "0",
    ...                 "Retry-After": str(int(e.retry_after)),
    ...             },
    ...         )
    """

    def __init__(
        self,
        requests: int | None = None,
        window_seconds: float | None = None,
    ) -> None:
        """
        Initialize the rate limiter.

        Parameters
        ----------
        requests : int, optional
            Max requests per window.
        window_seconds : float, optional
            Window size in seconds.
        """
        settings = get_settings()

        self.requests = requests if requests is not None else settings.rate_limit_requests
        self.window_seconds = (
            window_seconds if window_seconds is not None else settings.rate_limit_window_seconds
        )

        # Track request timestamps in a deque for efficient sliding window
        self._request_times: deque[float] = deque()

        # Lock for thread/async safety
        self._lock = asyncio.Lock()

    @property
    def current_count(self) -> int:
        """Get current number of requests in the window."""
        self._cleanup_old_requests()
        return len(self._request_times)

    @property
    def remaining(self) -> int:
        """Get remaining requests allowed in current window."""
        return max(0, self.requests - self.current_count)

    def _cleanup_old_requests(self) -> None:
        """Remove requests that are outside the current window."""
        cutoff = time.time() - self.window_seconds

        while self._request_times and self._request_times[0] < cutoff:
            self._request_times.popleft()

    def _calculate_retry_after(self) -> float:
        """Calculate seconds until a new request would be allowed."""
        if not self._request_times:  # pragma: no cover
            return 0.0

        # Oldest request will "expire" at this time
        oldest = self._request_times[0]
        expiry = oldest + self.window_seconds

        return max(0.0, expiry - time.time())

    def would_exceed(self) -> bool:
        """
        Check if a new request would exceed the rate limit.

        Does NOT consume a request slot.

        Returns
        -------
        bool
            True if rate limit would be exceeded.

        Example
        -------
        >>> if limiter.would_exceed():
        ...     return "Try again later"
        """
        self._cleanup_old_requests()
        return len(self._request_times) >= self.requests

    async def acquire(self) -> bool:
        """
        Attempt to acquire a request slot.

        Returns
        -------
        bool
            True if acquired, False if rate limit exceeded.

        Example
        -------
        >>> if await limiter.acquire():
        ...     await process_request()
        ... else:
        ...     return "Rate limit exceeded"
        """
        async with self._lock:
            self._cleanup_old_requests()

            if len(self._request_times) >= self.requests:
                return False

            self._request_times.append(time.time())
            return True

    async def __aenter__(self) -> RateLimiter:
        """
        Enter the rate limiter context.

        Raises
        ------
        RateLimitExceeded
            If rate limit is exceeded.
        """
        async with self._lock:
            self._cleanup_old_requests()

            if len(self._request_times) >= self.requests:
                retry_after = self._calculate_retry_after()

                logger.debug(
                    "rate_limit_exceeded",
                    limit=self.requests,
                    window_seconds=self.window_seconds,
                    retry_after=retry_after,
                )

                raise RateLimitExceeded(
                    limit=self.requests,
                    window_seconds=self.window_seconds,
                    retry_after=retry_after,
                )

            self._request_times.append(time.time())
            return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> bool:
        """Exit the rate limiter context."""
        return False


# Alias for clarity
SlidingWindowRateLimiter = RateLimiter


class TokenBucketRateLimiter:
    """
    Token bucket rate limiter with burst support.

    Allows controlled bursting while maintaining an average rate.
    Tokens are added at a fixed rate, and each request consumes one token.

    Parameters
    ----------
    bucket_size : int
        Maximum tokens (burst capacity).

    refill_rate : float
        Tokens added per second.

    initial_tokens : int, optional
        Starting tokens. Default: bucket_size.

    Attributes
    ----------
    bucket_size : int
        Maximum token capacity.

    refill_rate : float
        Tokens per second.

    available_tokens : float
        Current available tokens.

    Example - Basic Usage
    ---------------------
    >>> from obskit.resilience import TokenBucketRateLimiter
    >>>
    >>> # 10 tokens max, refill 1 per second
    >>> limiter = TokenBucketRateLimiter(bucket_size=10, refill_rate=1.0)
    >>>
    >>> async def handle_request():
    ...     async with limiter:
    ...         return await process_request()

    Example - Bursty Traffic
    ------------------------
    >>> # Allow bursts of 50, average 10/second
    >>> limiter = TokenBucketRateLimiter(
    ...     bucket_size=50,      # Can handle 50 immediate requests
    ...     refill_rate=10.0,    # Then 10 per second sustained
    ... )

    Example - API Rate Limit
    ------------------------
    >>> # Match API quota: 1000/day with 100 burst
    >>> limiter = TokenBucketRateLimiter(
    ...     bucket_size=100,
    ...     refill_rate=1000 / 86400,  # ~0.0116 tokens/second
    ... )

    Notes
    -----
    Token bucket is ideal when:
    - You want to allow occasional bursts
    - Traffic is naturally bursty
    - You're matching an external API's rate limit
    """

    def __init__(
        self,
        bucket_size: int,
        refill_rate: float,
        initial_tokens: int | None = None,
    ) -> None:
        """
        Initialize the token bucket.

        Parameters
        ----------
        bucket_size : int
            Maximum tokens in bucket.
        refill_rate : float
            Tokens per second to add.
        initial_tokens : int, optional
            Starting tokens.
        """
        self.bucket_size = bucket_size
        self.refill_rate = refill_rate

        self._tokens = float(initial_tokens if initial_tokens is not None else bucket_size)
        self._last_refill = time.time()

        # Lock for thread/async safety
        self._lock = asyncio.Lock()

    @property
    def available_tokens(self) -> float:
        """Get current available tokens (without refilling)."""
        return self._tokens

    def _refill(self) -> None:
        """Add tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self._last_refill

        # Add tokens based on elapsed time
        tokens_to_add = elapsed * self.refill_rate
        self._tokens = min(self.bucket_size, self._tokens + tokens_to_add)
        self._last_refill = now

    def _calculate_retry_after(self) -> float:
        """Calculate seconds until a token will be available."""
        if self._tokens >= 1.0:  # pragma: no cover
            return 0.0

        # Time until we have at least 1 token
        tokens_needed = 1.0 - self._tokens  # pragma: no cover
        return tokens_needed / self.refill_rate  # pragma: no cover

    async def acquire(self, tokens: int = 1) -> bool:
        """
        Attempt to acquire tokens.

        Parameters
        ----------
        tokens : int, default=1
            Number of tokens to acquire.

        Returns
        -------
        bool
            True if acquired, False if not enough tokens.
        """
        async with self._lock:
            self._refill()

            if self._tokens >= tokens:
                self._tokens -= tokens
                return True

            return False

    async def __aenter__(self) -> TokenBucketRateLimiter:
        """
        Enter the rate limiter context.

        Raises
        ------
        RateLimitExceeded
            If no tokens available.
        """
        async with self._lock:
            self._refill()

            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return self

            retry_after = self._calculate_retry_after()  # pragma: no cover

            logger.debug(  # pragma: no cover
                "rate_limit_exceeded",
                bucket_size=self.bucket_size,
                available_tokens=self._tokens,
                retry_after=retry_after,
            )

            raise RateLimitExceeded(  # pragma: no cover
                limit=self.bucket_size,
                window_seconds=1.0 / self.refill_rate if self.refill_rate > 0 else 0,
                retry_after=retry_after,
            )

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> bool:
        """Exit the rate limiter context."""
        return False
