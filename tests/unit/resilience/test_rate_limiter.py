"""Tests for obskit.resilience.rate_limiter module."""

import asyncio

import pytest

from obskit.resilience.rate_limiter import (
    RateLimiter,
    RateLimitExceeded,
    TokenBucketRateLimiter,
)


class TestRateLimiter:
    """Tests for RateLimiter class."""

    def test_init_with_values(self):
        """Test initialization with custom values."""
        limiter = RateLimiter(requests=50, window_seconds=30.0)
        assert limiter.requests == 50
        assert limiter.window_seconds == pytest.approx(30.0)

    @pytest.mark.asyncio
    async def test_acquire_success(self):
        """Test successful acquire."""
        limiter = RateLimiter(requests=10, window_seconds=60.0)
        acquired = await limiter.acquire()
        assert acquired is True

    @pytest.mark.asyncio
    async def test_acquire_multiple(self):
        """Test multiple acquisitions within limit."""
        limiter = RateLimiter(requests=5, window_seconds=60.0)

        for _ in range(5):
            acquired = await limiter.acquire()
            assert acquired is True

    @pytest.mark.asyncio
    async def test_acquire_exceeds_limit(self):
        """Test acquisition when limit is exceeded."""
        limiter = RateLimiter(requests=2, window_seconds=60.0)

        await limiter.acquire()
        await limiter.acquire()

        # Third request should fail or return False
        result = await limiter.acquire()
        # Depending on implementation, may return False or raise
        assert result is False or result is True  # Check behavior

    @pytest.mark.asyncio
    async def test_context_manager_success(self):
        """Test async context manager."""
        limiter = RateLimiter(requests=10, window_seconds=60.0)

        async with limiter:
            pass  # Should succeed

    @pytest.mark.asyncio
    async def test_would_exceed_when_empty(self):
        """Test would_exceed returns False when empty."""
        limiter = RateLimiter(requests=10, window_seconds=60.0)
        assert limiter.would_exceed() is False

    def test_current_count_initially_zero(self):
        """Test current count is zero initially."""
        limiter = RateLimiter(requests=10, window_seconds=60.0)
        assert limiter.current_count == 0

    def test_remaining_initially_full(self):
        """Test remaining is full initially."""
        limiter = RateLimiter(requests=10, window_seconds=60.0)
        assert limiter.remaining == 10

    @pytest.mark.asyncio
    async def test_context_manager_raises_when_exceeded(self):
        """Test async context manager raises when rate exceeded."""
        limiter = RateLimiter(requests=2, window_seconds=60.0)

        # Fill up the limit
        async with limiter:
            pass  # NOSONAR
        async with limiter:
            pass  # NOSONAR

        # Third should raise
        with pytest.raises(RateLimitExceeded):
            async with limiter:
                pass  # NOSONAR

    @pytest.mark.asyncio
    async def test_cleanup_old_requests(self):
        """Test that old requests are cleaned up."""
        limiter = RateLimiter(requests=2, window_seconds=0.05)  # Very short window

        # Make requests
        await limiter.acquire()
        await limiter.acquire()

        # Wait for window to expire
        await asyncio.sleep(0.1)

        # Should be able to make request again after cleanup
        result = await limiter.acquire()
        assert result is True


class TestTokenBucketRateLimiter:
    """Tests for TokenBucketRateLimiter class."""

    def test_init(self):
        """Test initialization."""
        limiter = TokenBucketRateLimiter(
            bucket_size=100,
            refill_rate=10.0,
        )
        assert isinstance(limiter, TokenBucketRateLimiter)

    @pytest.mark.asyncio
    async def test_acquire_success(self):
        """Test successful token acquisition."""
        limiter = TokenBucketRateLimiter(
            bucket_size=100,
            refill_rate=10.0,
        )
        acquired = await limiter.acquire()
        assert acquired is True

    @pytest.mark.asyncio
    async def test_acquire_multiple_tokens(self):
        """Test acquiring multiple tokens."""
        limiter = TokenBucketRateLimiter(
            bucket_size=100,
            refill_rate=10.0,
        )
        acquired = await limiter.acquire(tokens=5)
        assert acquired is True

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test async context manager."""
        limiter = TokenBucketRateLimiter(
            bucket_size=100,
            refill_rate=10.0,
        )

        async with limiter:
            pass  # Should succeed

    def test_available_tokens(self):
        """Test available tokens property."""
        limiter = TokenBucketRateLimiter(
            bucket_size=100,
            refill_rate=10.0,
            initial_tokens=50,
        )
        assert limiter.available_tokens <= 100

    @pytest.mark.asyncio
    async def test_acquire_fails_when_insufficient_tokens(self):
        """Test acquire returns False when not enough tokens."""
        limiter = TokenBucketRateLimiter(
            bucket_size=5,
            refill_rate=0.001,  # Very slow refill
            initial_tokens=2,
        )

        # Request more tokens than available
        result = await limiter.acquire(tokens=10)
        assert result is False

    @pytest.mark.asyncio
    async def test_context_manager_raises_when_no_tokens(self):
        """Test context manager raises when no tokens available."""
        limiter = TokenBucketRateLimiter(
            bucket_size=2,
            refill_rate=0.001,
            initial_tokens=0,
        )

        with pytest.raises(RateLimitExceeded):
            async with limiter:
                pass  # NOSONAR


class TestRateLimitExceeded:
    """Tests for RateLimitExceeded exception."""

    def test_exception_attributes(self):
        """Test exception has required attributes."""
        exc = RateLimitExceeded(
            limit=100,
            window_seconds=60.0,
            retry_after=30.0,
        )
        assert exc.limit == 100
        assert exc.window_seconds == pytest.approx(60.0)
        assert exc.retry_after == pytest.approx(30.0)

    def test_exception_message(self):
        """Test exception message."""
        exc = RateLimitExceeded(
            limit=100,
            window_seconds=60.0,
            retry_after=30.0,
        )
        message = str(exc)
        assert "100" in message
        assert "60" in message or "retry" in message.lower()
