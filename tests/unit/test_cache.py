"""Unit tests for cache instrumentation."""

import time
import pytest
from unittest.mock import MagicMock, patch

from obskit.cache import (
    CacheTracker,
    CacheGetContext,
    CacheOperationContext,
    RedisCacheTracker,
    cached,
    CACHE_REQUESTS,
    CACHE_LATENCY,
    CACHE_SIZE,
    CACHE_MEMORY,
    CACHE_HIT_RATE,
)


class TestCacheTracker:
    """Tests for CacheTracker class."""
    
    def test_init(self):
        """Test tracker initialization."""
        tracker = CacheTracker("test_cache")
        assert tracker.name == "test_cache"
        assert tracker._hits == 0
        assert tracker._misses == 0
    
    def test_record_hit(self):
        """Test recording cache hit."""
        tracker = CacheTracker("test_cache")
        tracker.record_hit(key="user:123")
        assert tracker._hits == 1
    
    def test_record_miss(self):
        """Test recording cache miss."""
        tracker = CacheTracker("test_cache")
        tracker.record_miss(key="user:456")
        assert tracker._misses == 1
    
    def test_record_set(self):
        """Test recording cache set."""
        tracker = CacheTracker("test_cache")
        tracker.record_set(key="user:789", size_bytes=1024)
        # Should not affect hit/miss counts
        assert tracker._hits == 0
        assert tracker._misses == 0
    
    def test_record_delete(self):
        """Test recording cache delete."""
        tracker = CacheTracker("test_cache")
        tracker.record_delete(key="user:123")
        # Should not affect hit/miss counts
        assert tracker._hits == 0
        assert tracker._misses == 0
    
    def test_record_error(self):
        """Test recording cache error."""
        tracker = CacheTracker("test_cache")
        tracker.record_error(operation="get", error="Connection failed", key="test")
        # Error logging should work without raising
    
    def test_hit_rate_calculation(self):
        """Test hit rate is correctly calculated."""
        tracker = CacheTracker("test_cache", window_size=100)
        
        # Record 8 hits and 2 misses
        for _ in range(8):
            tracker.record_hit()
        for _ in range(2):
            tracker.record_miss()
        
        stats = tracker.get_stats()
        assert stats["hit_rate"] == 0.8
    
    def test_get_stats(self):
        """Test get_stats returns correct data."""
        tracker = CacheTracker("test_cache")
        tracker.record_hit()
        tracker.record_hit()
        tracker.record_miss()
        
        stats = tracker.get_stats()
        assert stats["name"] == "test_cache"
        assert stats["hits"] == 2
        assert stats["misses"] == 1
        assert stats["total_requests"] == 3
    
    def test_track_get_context_manager(self):
        """Test track_get context manager."""
        tracker = CacheTracker("test_cache")
        
        with tracker.track_get("user:123") as ctx:
            ctx.hit(value={"name": "John"})
        
        assert tracker._hits == 1
    
    def test_track_get_miss(self):
        """Test track_get with cache miss."""
        tracker = CacheTracker("test_cache")
        
        with tracker.track_get("user:456") as ctx:
            ctx.miss()
        
        assert tracker._misses == 1
    
    def test_track_get_default_miss(self):
        """Test track_get defaults to miss if not recorded."""
        tracker = CacheTracker("test_cache")
        
        with tracker.track_get("user:789"):
            pass  # Don't call hit() or miss()
        
        assert tracker._misses == 1
    
    def test_track_operation_context_manager(self):
        """Test track_operation context manager."""
        tracker = CacheTracker("test_cache")
        
        with tracker.track_operation("set", "user:123"):
            pass  # Simulate set operation
    
    def test_update_size(self):
        """Test update_size sets gauge metrics."""
        tracker = CacheTracker("test_cache")
        tracker.update_size(items=1000, memory_bytes=1024 * 1024)


class TestCacheGetContext:
    """Tests for CacheGetContext class."""
    
    def test_hit_records_correctly(self):
        """Test hit() records hit on tracker."""
        tracker = CacheTracker("test_cache")
        ctx = CacheGetContext(tracker, "test_key")
        
        ctx.__enter__()
        ctx.hit(value="cached_value", size_bytes=100)
        ctx.__exit__(None, None, None)
        
        assert tracker._hits == 1
    
    def test_miss_records_correctly(self):
        """Test miss() records miss on tracker."""
        tracker = CacheTracker("test_cache")
        ctx = CacheGetContext(tracker, "test_key")
        
        ctx.__enter__()
        ctx.miss()
        ctx.__exit__(None, None, None)
        
        assert tracker._misses == 1
    
    def test_error_on_exception(self):
        """Test error is recorded on exception."""
        tracker = CacheTracker("test_cache")
        ctx = CacheGetContext(tracker, "test_key")
        
        ctx.__enter__()
        ctx.__exit__(ValueError, ValueError("Test error"), None)
        # Should record error, not hit or miss


class TestCachedDecorator:
    """Tests for cached decorator."""
    
    def test_caches_result(self):
        """Test decorator caches function result."""
        tracker = CacheTracker("test_cache")
        call_count = 0
        
        @cached(tracker=tracker, ttl=300, key_prefix="user")
        def get_user(user_id):
            nonlocal call_count
            call_count += 1
            return {"id": user_id, "name": "John"}
        
        # First call - cache miss
        result1 = get_user("123")
        assert result1 == {"id": "123", "name": "John"}
        assert call_count == 1
        
        # Second call - cache hit
        result2 = get_user("123")
        assert result2 == {"id": "123", "name": "John"}
        assert call_count == 1  # Function not called again
    
    def test_different_args_different_cache(self):
        """Test different arguments create different cache entries."""
        tracker = CacheTracker("test_cache")
        call_count = 0
        
        @cached(tracker=tracker, ttl=300, key_prefix="user")
        def get_user(user_id):
            nonlocal call_count
            call_count += 1
            return {"id": user_id}
        
        result1 = get_user("123")
        result2 = get_user("456")
        
        assert result1["id"] == "123"
        assert result2["id"] == "456"
        assert call_count == 2
    
    def test_invalidate(self):
        """Test cache invalidation."""
        tracker = CacheTracker("test_cache")
        call_count = 0
        
        @cached(tracker=tracker, ttl=300, key_prefix="user")
        def get_user(user_id):
            nonlocal call_count
            call_count += 1
            return {"id": user_id}
        
        get_user("123")
        assert call_count == 1
        
        get_user.invalidate("123")
        get_user("123")
        assert call_count == 2
    
    def test_clear(self):
        """Test cache clear."""
        tracker = CacheTracker("test_cache")
        call_count = 0
        
        @cached(tracker=tracker, ttl=300, key_prefix="user")
        def get_user(user_id):
            nonlocal call_count
            call_count += 1
            return {"id": user_id}
        
        get_user("123")
        get_user("456")
        assert call_count == 2
        
        get_user.clear()
        get_user("123")
        assert call_count == 3
    
    def test_skip_none(self):
        """Test skip_none option doesn't cache None results."""
        tracker = CacheTracker("test_cache")
        call_count = 0
        
        @cached(tracker=tracker, ttl=300, key_prefix="user", skip_none=True)
        def get_user(user_id):
            nonlocal call_count
            call_count += 1
            return None if user_id == "missing" else {"id": user_id}
        
        get_user("missing")
        get_user("missing")
        assert call_count == 2  # Called twice because None wasn't cached
    
    @pytest.mark.asyncio
    async def test_async_caching(self):
        """Test caching works with async functions."""
        tracker = CacheTracker("test_cache")
        call_count = 0
        
        @cached(tracker=tracker, ttl=300, key_prefix="async_user")
        async def get_user_async(user_id):
            nonlocal call_count
            call_count += 1
            return {"id": user_id}
        
        result1 = await get_user_async("123")
        result2 = await get_user_async("123")
        
        assert result1 == result2
        assert call_count == 1


class TestRedisCacheTracker:
    """Tests for RedisCacheTracker class."""
    
    def test_init(self):
        """Test initialization with Redis client."""
        mock_redis = MagicMock()
        tracker = RedisCacheTracker("redis", mock_redis)
        assert tracker.redis == mock_redis
    
    def test_sync_stats(self):
        """Test syncing stats from Redis INFO."""
        mock_redis = MagicMock()
        mock_redis.info.return_value = {
            "db0": {"keys": 1000},
            "used_memory": 1024 * 1024,
            "keyspace_hits": 800,
            "keyspace_misses": 200,
        }
        
        tracker = RedisCacheTracker("redis", mock_redis)
        tracker.sync_stats()
        
        mock_redis.info.assert_called_once()
    
    def test_sync_stats_handles_error(self):
        """Test sync_stats handles Redis errors gracefully."""
        mock_redis = MagicMock()
        mock_redis.info.side_effect = Exception("Connection failed")
        
        tracker = RedisCacheTracker("redis", mock_redis)
        tracker.sync_stats()  # Should not raise
