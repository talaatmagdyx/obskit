"""
Cache Instrumentation.

Provides automatic cache hit/miss tracking with metrics.
"""

import functools
import hashlib
import time
from collections.abc import Callable
from typing import Any, TypeVar

from prometheus_client import Counter, Gauge, Histogram

from .logging import get_logger

logger = get_logger(__name__)

# Metrics
CACHE_REQUESTS = Counter(
    "cache_requests_total", "Total cache requests", ["cache", "operation", "status"]
)

CACHE_LATENCY = Histogram(
    "cache_latency_seconds",
    "Cache operation latency",
    ["cache", "operation"],
    buckets=[0.0001, 0.0005, 0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
)

CACHE_SIZE = Gauge("cache_size_items", "Number of items in cache", ["cache"])

CACHE_MEMORY = Gauge("cache_memory_bytes", "Cache memory usage in bytes", ["cache"])

CACHE_HIT_RATE = Gauge("cache_hit_rate", "Cache hit rate (rolling)", ["cache"])

F = TypeVar("F", bound=Callable[..., Any])


class CacheTracker:
    """
    Tracks cache operations with metrics.

    Example:
        tracker = CacheTracker("redis")

        # Manual tracking
        with tracker.track_get("user:123") as ctx:
            value = redis.get("user:123")
            if value:
                ctx.hit(value)
            else:
                ctx.miss()

        # Or use decorator
        @tracker.cached(ttl=300, key_prefix="user")
        def get_user(user_id):
            return db.fetch_user(user_id)
    """

    def __init__(self, name: str, window_size: int = 1000):
        """
        Initialize cache tracker.

        Args:
            name: Cache name (used in metrics)
            window_size: Window size for hit rate calculation
        """
        self.name = name
        self.window_size = window_size
        self._hits = 0
        self._misses = 0
        self._recent_results: list = []

    def _update_hit_rate(self, is_hit: bool):
        """Update rolling hit rate."""
        self._recent_results.append(is_hit)
        if len(self._recent_results) > self.window_size:
            self._recent_results.pop(0)

        if self._recent_results:
            hit_rate = sum(self._recent_results) / len(self._recent_results)
            CACHE_HIT_RATE.labels(cache=self.name).set(hit_rate)

    def record_hit(self, key: str | None = None, size_bytes: int | None = None):
        """Record a cache hit."""
        self._hits += 1
        self._update_hit_rate(True)
        CACHE_REQUESTS.labels(cache=self.name, operation="get", status="hit").inc()
        logger.debug("cache_hit", cache=self.name, key=key)

    def record_miss(self, key: str | None = None):
        """Record a cache miss."""
        self._misses += 1
        self._update_hit_rate(False)
        CACHE_REQUESTS.labels(cache=self.name, operation="get", status="miss").inc()
        logger.debug("cache_miss", cache=self.name, key=key)

    def record_set(self, key: str | None = None, size_bytes: int | None = None):
        """Record a cache set operation."""
        CACHE_REQUESTS.labels(cache=self.name, operation="set", status="success").inc()

    def record_delete(self, key: str | None = None):
        """Record a cache delete operation."""
        CACHE_REQUESTS.labels(cache=self.name, operation="delete", status="success").inc()

    def record_error(self, operation: str, error: str, key: str | None = None):
        """Record a cache error."""
        CACHE_REQUESTS.labels(cache=self.name, operation=operation, status="error").inc()
        logger.warning("cache_error", cache=self.name, operation=operation, error=error, key=key)

    def track_get(self, key: str):
        """Context manager for tracking get operations."""
        return CacheGetContext(self, key)

    def track_operation(self, operation: str, key: str | None = None):
        """Context manager for tracking any cache operation."""
        return CacheOperationContext(self, operation, key)

    def update_size(self, items: int, memory_bytes: int | None = None):
        """Update cache size metrics."""
        CACHE_SIZE.labels(cache=self.name).set(items)
        if memory_bytes is not None:
            CACHE_MEMORY.labels(cache=self.name).set(memory_bytes)

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        total = self._hits + self._misses
        return {
            "name": self.name,
            "hits": self._hits,
            "misses": self._misses,
            "total_requests": total,
            "hit_rate": self._hits / total if total > 0 else 0.0,
        }


class CacheGetContext:
    """Context manager for tracking cache get operations."""

    def __init__(self, tracker: CacheTracker, key: str):
        self.tracker = tracker
        self.key = key
        self.start_time = time.time()
        self._recorded = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        CACHE_LATENCY.labels(cache=self.tracker.name, operation="get").observe(duration)

        if exc_type is not None:
            self.tracker.record_error("get", str(exc_val), self.key)
        elif not self._recorded:
            # Default to miss if not explicitly recorded
            self.tracker.record_miss(self.key)

    def hit(self, value: Any = None, size_bytes: int | None = None):
        """Record cache hit."""
        self._recorded = True
        self.tracker.record_hit(self.key, size_bytes)

    def miss(self):
        """Record cache miss."""
        self._recorded = True
        self.tracker.record_miss(self.key)


class CacheOperationContext:
    """Context manager for tracking cache operations."""

    def __init__(self, tracker: CacheTracker, operation: str, key: str | None = None):
        self.tracker = tracker
        self.operation = operation
        self.key = key
        self.start_time = time.time()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        CACHE_LATENCY.labels(cache=self.tracker.name, operation=self.operation).observe(duration)

        if exc_type is not None:
            self.tracker.record_error(self.operation, str(exc_val), self.key)
        else:
            CACHE_REQUESTS.labels(
                cache=self.tracker.name, operation=self.operation, status="success"
            ).inc()


def cached(
    tracker: CacheTracker,
    ttl: int = 300,
    key_prefix: str = "",
    key_builder: Callable[..., str] | None = None,
    skip_none: bool = True,
) -> Callable[[F], F]:
    """
    Decorator for caching function results with tracking.

    Args:
        tracker: CacheTracker instance
        ttl: Time to live in seconds
        key_prefix: Prefix for cache keys
        key_builder: Custom function to build cache key from args
        skip_none: Don't cache None results

    Returns:
        Decorated function

    Example:
        tracker = CacheTracker("redis")

        @cached(tracker=tracker, ttl=300, key_prefix="user")
        def get_user(user_id: str):
            return db.fetch_user(user_id)
    """

    # This is a template - actual implementation depends on cache backend
    def decorator(func: F) -> F:
        # In-memory cache for demo (replace with Redis/Memcached in production)
        _cache: dict[str, tuple] = {}

        def build_key(*args, **kwargs) -> str:
            if key_builder:
                return f"{key_prefix}:{key_builder(*args, **kwargs)}"

            # Default key builder
            key_parts = [str(arg) for arg in args]
            key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
            key_data = ":".join(key_parts)
            key_hash = hashlib.md5(key_data.encode()).hexdigest()[:16]
            return f"{key_prefix}:{func.__name__}:{key_hash}"

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            key = build_key(*args, **kwargs)

            # Try to get from cache
            with tracker.track_get(key) as ctx:
                if key in _cache:
                    value, expires_at = _cache[key]
                    if expires_at > time.time():
                        ctx.hit(value)
                        return value
                    else:
                        del _cache[key]
                ctx.miss()

            # Call function
            result = func(*args, **kwargs)

            # Store in cache
            if result is not None or not skip_none:
                with tracker.track_operation("set", key):
                    _cache[key] = (result, time.time() + ttl)
                tracker.record_set(key)

            return result

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            key = build_key(*args, **kwargs)

            with tracker.track_get(key) as ctx:
                if key in _cache:
                    value, expires_at = _cache[key]
                    if expires_at > time.time():
                        ctx.hit(value)
                        return value
                    else:
                        del _cache[key]
                ctx.miss()

            result = await func(*args, **kwargs)

            if result is not None or not skip_none:
                with tracker.track_operation("set", key):
                    _cache[key] = (result, time.time() + ttl)
                tracker.record_set(key)

            return result

        # Add cache control methods
        def invalidate(*args, **kwargs):
            key = build_key(*args, **kwargs)
            if key in _cache:
                del _cache[key]
                tracker.record_delete(key)

        def clear():
            _cache.clear()

        import asyncio

        if asyncio.iscoroutinefunction(func):
            async_wrapper.invalidate = invalidate  # type: ignore
            async_wrapper.clear = clear  # type: ignore
            return async_wrapper  # type: ignore

        wrapper.invalidate = invalidate  # type: ignore
        wrapper.clear = clear  # type: ignore
        return wrapper  # type: ignore

    return decorator


class RedisCacheTracker(CacheTracker):
    """
    Cache tracker specifically for Redis with automatic metric collection.

    Example:
        import redis

        client = redis.Redis()
        tracker = RedisCacheTracker("redis", client)

        # Metrics are automatically updated
        tracker.sync_stats()
    """

    def __init__(self, name: str, redis_client: Any, window_size: int = 1000):
        super().__init__(name, window_size)
        self.redis = redis_client

    def sync_stats(self):
        """Sync stats from Redis INFO command."""
        try:
            info = self.redis.info()

            # Update size metrics
            if "db0" in info:
                CACHE_SIZE.labels(cache=self.name).set(info["db0"].get("keys", 0))

            # Update memory metrics
            if "used_memory" in info:
                CACHE_MEMORY.labels(cache=self.name).set(info["used_memory"])

            # Update hit rate from Redis stats
            hits = info.get("keyspace_hits", 0)
            misses = info.get("keyspace_misses", 0)
            total = hits + misses
            if total > 0:
                CACHE_HIT_RATE.labels(cache=self.name).set(hits / total)

        except Exception as e:
            logger.warning("redis_stats_sync_failed", cache=self.name, error=str(e))


__all__ = [
    "CacheTracker",
    "CacheGetContext",
    "CacheOperationContext",
    "RedisCacheTracker",
    "cached",
    "CACHE_REQUESTS",
    "CACHE_LATENCY",
    "CACHE_SIZE",
    "CACHE_MEMORY",
    "CACHE_HIT_RATE",
]
