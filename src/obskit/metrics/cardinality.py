"""
Cardinality Protection for Prometheus Metrics
==============================================

Provides protection against high cardinality labels that can cause
Prometheus performance issues and increased storage costs.

High cardinality occurs when label values have many unique values
(e.g., user IDs, request IDs, timestamps). This module provides
utilities to limit and protect against cardinality explosion.

Example
-------
>>> from obskit.metrics import CardinalityProtector, get_cardinality_protector
>>>
>>> # Get or create a protector
>>> protector = get_cardinality_protector()
>>>
>>> # Protect a label value
>>> safe_user_id = protector.protect("user_id", user_id, fallback="other")
>>> # If too many unique user_ids, returns "other" instead
>>>
>>> # Use in metrics
>>> REQUEST_COUNT.labels(user_id=safe_user_id).inc()
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Callable, TypeVar

from prometheus_client import Counter, Gauge

from obskit.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")

# Metrics for monitoring cardinality protection
CARDINALITY_REJECTIONS = Counter(
    "obskit_cardinality_rejections_total",
    "Total number of label values rejected due to cardinality limits",
    ["label_name"],
)

CARDINALITY_CURRENT = Gauge(
    "obskit_cardinality_current",
    "Current number of unique values tracked for each label",
    ["label_name"],
)

CARDINALITY_LIMIT = Gauge(
    "obskit_cardinality_limit",
    "Configured cardinality limit for each label",
    ["label_name"],
)


class LRUCache:
    """
    Thread-safe LRU cache for tracking label values.

    Parameters
    ----------
    max_size : int
        Maximum number of items to store.
    ttl_seconds : float, optional
        Time-to-live for entries. None means no expiration.
    """

    def __init__(self, max_size: int, ttl_seconds: float | None = None) -> None:
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._lock = threading.RLock()

    def get(self, key: str) -> Any | None:
        """Get a value from the cache."""
        with self._lock:
            if key not in self._cache:
                return None

            value, timestamp = self._cache[key]

            # Check TTL
            if self.ttl_seconds is not None:
                if time.time() - timestamp > self.ttl_seconds:
                    del self._cache[key]
                    return None

            # Move to end (most recently used)
            self._cache.move_to_end(key)
            return value

    def put(self, key: str, value: Any) -> None:
        """Put a value in the cache."""
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                self._cache[key] = (value, time.time())
            else:
                if len(self._cache) >= self.max_size:
                    # Remove oldest item
                    self._cache.popitem(last=False)
                self._cache[key] = (value, time.time())

    def contains(self, key: str) -> bool:
        """Check if key is in cache (without updating LRU order)."""
        with self._lock:
            if key not in self._cache:
                return False

            if self.ttl_seconds is not None:
                _, timestamp = self._cache[key]
                if time.time() - timestamp > self.ttl_seconds:
                    del self._cache[key]
                    return False

            return True

    def __len__(self) -> int:
        """Return number of items in cache."""
        with self._lock:
            return len(self._cache)

    def clear(self) -> None:
        """Clear all items from cache."""
        with self._lock:
            self._cache.clear()


@dataclass
class CardinalityConfig:
    """
    Configuration for cardinality protection.

    Parameters
    ----------
    default_limit : int
        Default maximum unique values per label.
    ttl_seconds : float
        Time-to-live for tracked values.
    label_limits : dict
        Per-label cardinality limits.
    """

    default_limit: int = 1000
    ttl_seconds: float = 3600.0  # 1 hour
    label_limits: dict[str, int] = field(default_factory=dict)


class CardinalityProtector:
    """
    Protects against high cardinality labels in Prometheus metrics.

    This class tracks unique label values and replaces new values
    with a fallback when the cardinality limit is reached.

    Parameters
    ----------
    config : CardinalityConfig, optional
        Configuration for the protector.

    Example
    -------
    >>> protector = CardinalityProtector()
    >>>
    >>> # Set specific limits for labels
    >>> protector.set_limit("user_id", 10000)
    >>> protector.set_limit("company_id", 500)
    >>>
    >>> # Protect label values
    >>> safe_user = protector.protect("user_id", user_id)
    >>> safe_company = protector.protect("company_id", company_id)
    >>>
    >>> # Use in metrics
    >>> REQUESTS.labels(user=safe_user, company=safe_company).inc()
    """

    def __init__(self, config: CardinalityConfig | None = None) -> None:
        self.config = config or CardinalityConfig()
        self._caches: dict[str, LRUCache] = {}
        self._lock = threading.RLock()

    def _get_cache(self, label_name: str) -> LRUCache:
        """Get or create cache for a label."""
        with self._lock:
            if label_name not in self._caches:
                limit = self.config.label_limits.get(label_name, self.config.default_limit)
                self._caches[label_name] = LRUCache(
                    max_size=limit,
                    ttl_seconds=self.config.ttl_seconds,
                )
                CARDINALITY_LIMIT.labels(label_name=label_name).set(limit)

            return self._caches[label_name]

    def set_limit(self, label_name: str, limit: int) -> None:
        """
        Set cardinality limit for a specific label.

        Parameters
        ----------
        label_name : str
            Name of the label.
        limit : int
            Maximum unique values allowed.
        """
        self.config.label_limits[label_name] = limit
        CARDINALITY_LIMIT.labels(label_name=label_name).set(limit)

        # Recreate cache if exists
        with self._lock:
            if label_name in self._caches:
                old_cache = self._caches[label_name]
                self._caches[label_name] = LRUCache(
                    max_size=limit,
                    ttl_seconds=self.config.ttl_seconds,
                )
                # Note: old values are lost, but this is acceptable for limit changes

    def protect(
        self,
        label_name: str,
        value: T,
        fallback: T | None = None,
        transform: Callable[[T], str] | None = None,
    ) -> T:
        """
        Protect a label value against cardinality explosion.

        Parameters
        ----------
        label_name : str
            Name of the label being protected.
        value : T
            The label value to protect.
        fallback : T, optional
            Value to use if cardinality limit is reached.
            Defaults to "other" for strings.
        transform : callable, optional
            Function to transform value to cache key.

        Returns
        -------
        T
            The original value if within limits, fallback otherwise.

        Example
        -------
        >>> protector = CardinalityProtector()
        >>> safe_id = protector.protect("user_id", user_id, fallback="anonymous")
        """
        if value is None:
            return fallback if fallback is not None else value  # type: ignore

        cache = self._get_cache(label_name)
        key = transform(value) if transform else str(value)

        # Check if already tracked
        if cache.contains(key):
            return value

        # Check if we can add new value
        limit = self.config.label_limits.get(label_name, self.config.default_limit)
        if len(cache) < limit:
            cache.put(key, value)
            CARDINALITY_CURRENT.labels(label_name=label_name).set(len(cache))
            return value

        # Cardinality limit reached
        CARDINALITY_REJECTIONS.labels(label_name=label_name).inc()
        logger.debug(
            "cardinality_limit_reached",
            label_name=label_name,
            limit=limit,
            value_rejected=key[:50] if len(key) > 50 else key,
        )

        # Return fallback
        if fallback is not None:
            return fallback

        # Default fallback for strings
        if isinstance(value, str):
            return "other"  # type: ignore

        return value

    def get_stats(self, label_name: str) -> dict[str, Any]:
        """
        Get statistics for a label.

        Parameters
        ----------
        label_name : str
            Name of the label.

        Returns
        -------
        dict
            Statistics including current count, limit, and utilization.
        """
        cache = self._get_cache(label_name)
        limit = self.config.label_limits.get(label_name, self.config.default_limit)
        current = len(cache)

        return {
            "label_name": label_name,
            "current_count": current,
            "limit": limit,
            "utilization": current / limit if limit > 0 else 0,
            "at_limit": current >= limit,
        }

    def reset(self, label_name: str | None = None) -> None:
        """
        Reset tracking for a label or all labels.

        Parameters
        ----------
        label_name : str, optional
            Specific label to reset. If None, resets all.
        """
        with self._lock:
            if label_name:
                if label_name in self._caches:
                    self._caches[label_name].clear()
                    CARDINALITY_CURRENT.labels(label_name=label_name).set(0)
            else:
                for name, cache in self._caches.items():
                    cache.clear()
                    CARDINALITY_CURRENT.labels(label_name=name).set(0)


# Singleton instance
_cardinality_protector: CardinalityProtector | None = None
_protector_lock = threading.Lock()


def get_cardinality_protector(config: CardinalityConfig | None = None) -> CardinalityProtector:
    """
    Get or create the global CardinalityProtector instance.

    Parameters
    ----------
    config : CardinalityConfig, optional
        Configuration for the protector (only used on first call).

    Returns
    -------
    CardinalityProtector
        The global protector instance.

    Example
    -------
    >>> protector = get_cardinality_protector()
    >>> safe_value = protector.protect("user_id", user_id)
    """
    global _cardinality_protector

    if _cardinality_protector is None:
        with _protector_lock:
            if _cardinality_protector is None:
                _cardinality_protector = CardinalityProtector(config)

    return _cardinality_protector


def reset_cardinality_protector() -> None:
    """Reset the global CardinalityProtector instance (for testing)."""
    global _cardinality_protector
    with _protector_lock:
        _cardinality_protector = None


# Convenience functions for common label types
def protect_label(
    label_name: str,
    value: str | None,
    fallback: str = "other",
) -> str:
    """
    Protect a string label value.

    Convenience function that uses the global protector.

    Parameters
    ----------
    label_name : str
        Name of the label.
    value : str
        Value to protect.
    fallback : str
        Fallback value if limit reached.

    Returns
    -------
    str
        Protected value.
    """
    if value is None:
        return fallback
    return get_cardinality_protector().protect(label_name, value, fallback)


def protect_id(
    label_name: str,
    value: str | int | None,
    fallback: str = "other",
) -> str:
    """
    Protect an ID label value (string or int).

    Parameters
    ----------
    label_name : str
        Name of the label.
    value : str | int
        ID value to protect.
    fallback : str
        Fallback value if limit reached.

    Returns
    -------
    str
        Protected value as string.
    """
    if value is None:
        return fallback
    return get_cardinality_protector().protect(label_name, str(value), fallback)


__all__ = [
    "CardinalityConfig",
    "CardinalityProtector",
    "LRUCache",
    "get_cardinality_protector",
    "protect_id",
    "protect_label",
    "reset_cardinality_protector",
]
