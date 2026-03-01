"""Unit tests for obskit.metrics.cardinality module."""

from __future__ import annotations

import threading
import time

import pytest

from obskit.metrics.cardinality import (
    CardinalityConfig,
    CardinalityProtector,
    LRUCache,
    get_cardinality_protector,
    protect_id,
    protect_label,
    reset_cardinality_protector,
)


class TestLRUCache:
    """Tests for LRUCache."""

    def test_init(self):
        """Test LRUCache initialization."""
        cache = LRUCache(max_size=10, ttl_seconds=60.0)
        assert cache.max_size == 10
        assert cache.ttl_seconds == pytest.approx(60.0)
        assert len(cache) == 0

    def test_put_and_get(self):
        """Test basic put and get operations."""
        cache = LRUCache(max_size=10)
        cache.put("key1", "value1")
        assert cache.get("key1") == "value1"
        assert len(cache) == 1

    def test_get_nonexistent(self):
        """Test get returns None for nonexistent keys."""
        cache = LRUCache(max_size=10)
        assert cache.get("nonexistent") is None

    def test_contains(self):
        """Test contains method."""
        cache = LRUCache(max_size=10)
        cache.put("key1", "value1")
        assert cache.contains("key1") is True
        assert cache.contains("key2") is False

    def test_eviction(self):
        """Test LRU eviction when max_size is reached."""
        cache = LRUCache(max_size=3)
        cache.put("key1", "value1")
        cache.put("key2", "value2")
        cache.put("key3", "value3")
        # Adding fourth item should evict key1 (oldest)
        cache.put("key4", "value4")

        assert len(cache) == 3
        assert cache.get("key1") is None  # Evicted
        assert cache.get("key2") == "value2"
        assert cache.get("key3") == "value3"
        assert cache.get("key4") == "value4"

    def test_lru_update_order(self):
        """Test that accessing an item updates its position."""
        cache = LRUCache(max_size=3)
        cache.put("key1", "value1")
        cache.put("key2", "value2")
        cache.put("key3", "value3")

        # Access key1 to make it most recently used
        cache.get("key1")

        # Adding new item should evict key2 (now oldest)
        cache.put("key4", "value4")

        assert cache.get("key1") == "value1"  # Still present
        assert cache.get("key2") is None  # Evicted
        assert cache.get("key3") == "value3"
        assert cache.get("key4") == "value4"

    def test_ttl_expiration(self):
        """Test TTL expiration."""
        cache = LRUCache(max_size=10, ttl_seconds=0.1)
        cache.put("key1", "value1")

        assert cache.get("key1") == "value1"

        # Wait for TTL to expire
        time.sleep(0.15)

        assert cache.get("key1") is None

    def test_ttl_expiration_on_contains(self):
        """Test TTL expiration is checked in contains."""
        cache = LRUCache(max_size=10, ttl_seconds=0.1)
        cache.put("key1", "value1")

        assert cache.contains("key1") is True

        time.sleep(0.15)

        assert cache.contains("key1") is False

    def test_clear(self):
        """Test clear method."""
        cache = LRUCache(max_size=10)
        cache.put("key1", "value1")
        cache.put("key2", "value2")

        cache.clear()

        assert len(cache) == 0
        assert cache.get("key1") is None

    def test_update_existing_key(self):
        """Test updating existing key."""
        cache = LRUCache(max_size=10)
        cache.put("key1", "value1")
        cache.put("key1", "value2")

        assert cache.get("key1") == "value2"
        assert len(cache) == 1

    def test_thread_safety(self):
        """Test thread safety of LRU cache."""
        cache = LRUCache(max_size=1000)
        errors = []

        def worker(thread_id):
            try:
                for i in range(100):
                    cache.put(f"key_{thread_id}_{i}", f"value_{i}")
                    cache.get(f"key_{thread_id}_{i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0


class TestCardinalityConfig:
    """Tests for CardinalityConfig."""

    def test_defaults(self):
        """Test default configuration."""
        config = CardinalityConfig()
        assert config.default_limit == 1000
        assert config.ttl_seconds == pytest.approx(3600.0)
        assert config.label_limits == {}

    def test_custom_config(self):
        """Test custom configuration."""
        config = CardinalityConfig(
            default_limit=500,
            ttl_seconds=1800.0,
            label_limits={"user_id": 10000},
        )
        assert config.default_limit == 500
        assert config.ttl_seconds == pytest.approx(1800.0)
        assert config.label_limits == {"user_id": 10000}


class TestCardinalityProtector:
    """Tests for CardinalityProtector."""

    def test_init_with_default_config(self):
        """Test initialization with default config."""
        protector = CardinalityProtector()
        assert protector.config.default_limit == 1000

    def test_init_with_custom_config(self):
        """Test initialization with custom config."""
        config = CardinalityConfig(default_limit=500)
        protector = CardinalityProtector(config)
        assert protector.config.default_limit == 500

    def test_protect_within_limit(self):
        """Test protection when within limit."""
        config = CardinalityConfig(default_limit=5)
        protector = CardinalityProtector(config)

        for i in range(5):
            result = protector.protect("label", f"value_{i}", fallback="other")
            assert result == f"value_{i}"

    def test_protect_at_limit_returns_fallback(self):
        """Test protection returns fallback when at limit."""
        config = CardinalityConfig(default_limit=3)
        protector = CardinalityProtector(config)

        # Fill up to limit
        for i in range(3):
            protector.protect("label", f"value_{i}", fallback="other")

        # Next new value should return fallback
        result = protector.protect("label", "new_value", fallback="other")
        assert result == "other"

    def test_protect_existing_value_always_allowed(self):
        """Test that existing values are always allowed."""
        config = CardinalityConfig(default_limit=2)
        protector = CardinalityProtector(config)

        protector.protect("label", "value_1")
        protector.protect("label", "value_2")

        # Limit reached, but existing value should still work
        result = protector.protect("label", "value_1", fallback="other")
        assert result == "value_1"

    def test_protect_none_value(self):
        """Test protection with None value."""
        protector = CardinalityProtector()
        result = protector.protect("label", None, fallback="other")
        assert result == "other"

    def test_protect_default_fallback_for_string(self):
        """Test default fallback for string values."""
        config = CardinalityConfig(default_limit=1)
        protector = CardinalityProtector(config)

        protector.protect("label", "value_1")
        result = protector.protect("label", "new_value")
        assert result == "other"  # Default fallback

    def test_set_limit(self):
        """Test setting custom limit for a label."""
        protector = CardinalityProtector()
        protector.set_limit("user_id", 100)
        assert protector.config.label_limits["user_id"] == 100

    def test_different_limits_per_label(self):
        """Test different limits for different labels."""
        protector = CardinalityProtector()
        protector.set_limit("label1", 2)
        protector.set_limit("label2", 3)

        # Fill label1
        for i in range(2):
            protector.protect("label1", f"val_{i}")

        # label1 at limit
        result1 = protector.protect("label1", "new", fallback="x")
        assert result1 == "x"

        # label2 still has room
        for i in range(3):
            result = protector.protect("label2", f"val_{i}", fallback="x")
            assert result == f"val_{i}"

    def test_get_stats(self):
        """Test get_stats method."""
        config = CardinalityConfig(default_limit=10)
        protector = CardinalityProtector(config)

        for i in range(5):
            protector.protect("label", f"value_{i}")

        stats = protector.get_stats("label")
        assert stats["label_name"] == "label"
        assert stats["current_count"] == 5
        assert stats["limit"] == 10
        assert stats["utilization"] == pytest.approx(0.5)
        assert stats["at_limit"] is False

    def test_get_stats_at_limit(self):
        """Test get_stats when at limit."""
        config = CardinalityConfig(default_limit=3)
        protector = CardinalityProtector(config)

        for i in range(3):
            protector.protect("label", f"value_{i}")

        stats = protector.get_stats("label")
        assert stats["at_limit"] is True
        assert stats["utilization"] == pytest.approx(1.0)

    def test_reset_specific_label(self):
        """Test resetting a specific label."""
        protector = CardinalityProtector()
        protector.protect("label1", "value")
        protector.protect("label2", "value")

        protector.reset("label1")

        stats1 = protector.get_stats("label1")
        stats2 = protector.get_stats("label2")
        assert stats1["current_count"] == 0
        assert stats2["current_count"] == 1

    def test_reset_all_labels(self):
        """Test resetting all labels."""
        protector = CardinalityProtector()
        protector.protect("label1", "value")
        protector.protect("label2", "value")

        protector.reset()

        stats1 = protector.get_stats("label1")
        stats2 = protector.get_stats("label2")
        assert stats1["current_count"] == 0
        assert stats2["current_count"] == 0

    def test_custom_transform(self):
        """Test custom transform function."""
        protector = CardinalityProtector()

        # Use transform to normalize values
        result = protector.protect(
            "label",
            "UPPERCASE",
            transform=lambda x: x.lower(),
        )
        assert result == "UPPERCASE"

        # Same normalized value should be recognized
        result = protector.protect(
            "label",
            "uppercase",
            transform=lambda x: x.lower(),
        )
        assert result == "uppercase"


class TestGlobalProtector:
    """Tests for global protector functions."""

    def setup_method(self):
        """Reset global protector before each test."""
        reset_cardinality_protector()

    def test_get_cardinality_protector_singleton(self):
        """Test that get_cardinality_protector returns singleton."""
        p1 = get_cardinality_protector()
        p2 = get_cardinality_protector()
        assert p1 is p2

    def test_get_cardinality_protector_with_config(self):
        """Test getting protector with initial config."""
        config = CardinalityConfig(default_limit=500)
        protector = get_cardinality_protector(config)
        assert protector.config.default_limit == 500

    def test_reset_cardinality_protector(self):
        """Test resetting global protector."""
        p1 = get_cardinality_protector()
        reset_cardinality_protector()
        p2 = get_cardinality_protector()
        assert p1 is not p2

    def test_protect_label_convenience(self):
        """Test protect_label convenience function."""
        result = protect_label("user_id", "user123")
        assert result == "user123"

    def test_protect_label_with_none(self):
        """Test protect_label with None value."""
        result = protect_label("user_id", None, fallback="anonymous")
        assert result == "anonymous"

    def test_protect_id_string(self):
        """Test protect_id with string."""
        result = protect_id("user_id", "user123")
        assert result == "user123"

    def test_protect_id_int(self):
        """Test protect_id with integer."""
        result = protect_id("user_id", 12345)
        assert result == "12345"

    def test_protect_id_with_none(self):
        """Test protect_id with None value."""
        result = protect_id("user_id", None, fallback="unknown")
        assert result == "unknown"


class TestCardinalityProtectorThreadSafety:
    """Thread safety tests for CardinalityProtector."""

    def test_concurrent_protection(self):
        """Test concurrent calls to protect."""
        config = CardinalityConfig(default_limit=1000)
        protector = CardinalityProtector(config)
        errors = []
        results = []

        def worker(thread_id):
            try:
                for i in range(100):
                    result = protector.protect(
                        "label",
                        f"value_{thread_id}_{i}",
                        fallback="other",
                    )
                    results.append(result)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 1000
