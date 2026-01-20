"""
Connection Pool Metrics
=======================

Track database, cache, and message queue connection pools.

Features:
- Pool size tracking (active, idle, max)
- Checkout latency
- Connection errors
- Pool exhaustion alerts

Example:
    from obskit.pools import ConnectionPoolTracker, PoolType

    # Create tracker
    pg_pool = ConnectionPoolTracker("postgres", pool_type=PoolType.DATABASE)

    # Update pool stats
    pg_pool.set_pool_size(active=5, idle=3, max=10)

    # Track checkout
    with pg_pool.track_checkout() as conn:
        cursor = conn.cursor()
        cursor.execute(query)

    # Track errors
    pg_pool.track_error("timeout")
"""

import threading
import time
from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from prometheus_client import Counter, Gauge, Histogram

from obskit.logging import get_logger

logger = get_logger(__name__)


# =============================================================================
# Prometheus Metrics
# =============================================================================

POOL_CONNECTIONS_ACTIVE = Gauge(
    "pool_connections_active", "Number of active connections in pool", ["pool_name", "pool_type"]
)

POOL_CONNECTIONS_IDLE = Gauge(
    "pool_connections_idle", "Number of idle connections in pool", ["pool_name", "pool_type"]
)

POOL_CONNECTIONS_MAX = Gauge(
    "pool_connections_max", "Maximum connections allowed in pool", ["pool_name", "pool_type"]
)

POOL_UTILIZATION = Gauge(
    "pool_utilization_ratio", "Pool utilization (active/max)", ["pool_name", "pool_type"]
)

POOL_CHECKOUT_TOTAL = Counter(
    "pool_checkout_total", "Total connection checkouts", ["pool_name", "pool_type", "status"]
)

POOL_CHECKOUT_LATENCY = Histogram(
    "pool_checkout_latency_seconds",
    "Connection checkout latency",
    ["pool_name", "pool_type"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

POOL_ERRORS_TOTAL = Counter(
    "pool_errors_total", "Total pool errors", ["pool_name", "pool_type", "error_type"]
)

POOL_WAIT_QUEUE = Gauge(
    "pool_wait_queue_size", "Number of requests waiting for connection", ["pool_name", "pool_type"]
)

POOL_EXHAUSTED_TOTAL = Counter(
    "pool_exhausted_total", "Times pool was exhausted", ["pool_name", "pool_type"]
)


# =============================================================================
# Enums and Data Classes
# =============================================================================


class PoolType(Enum):
    """Type of connection pool."""

    DATABASE = "database"
    CACHE = "cache"
    QUEUE = "queue"
    HTTP = "http"
    CUSTOM = "custom"


@dataclass
class PoolStats:
    """Statistics for a connection pool."""

    pool_name: str
    pool_type: PoolType
    active: int = 0
    idle: int = 0
    max_size: int = 0
    wait_queue: int = 0
    checkouts_total: int = 0
    errors_total: int = 0
    avg_checkout_latency_ms: float = 0.0
    utilization: float = 0.0
    last_updated: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "pool_name": self.pool_name,
            "pool_type": self.pool_type.value,
            "active": self.active,
            "idle": self.idle,
            "max_size": self.max_size,
            "wait_queue": self.wait_queue,
            "checkouts_total": self.checkouts_total,
            "errors_total": self.errors_total,
            "avg_checkout_latency_ms": self.avg_checkout_latency_ms,
            "utilization": self.utilization,
            "last_updated": self.last_updated.isoformat(),
        }


# =============================================================================
# Connection Pool Tracker
# =============================================================================


class ConnectionPoolTracker:
    """
    Track connection pool metrics.

    Parameters
    ----------
    pool_name : str
        Name of the pool (e.g., "postgres", "redis")
    pool_type : PoolType
        Type of pool
    max_size : int, optional
        Maximum pool size
    alert_threshold : float, optional
        Utilization threshold for alerts (default: 0.8)
    on_exhausted : callable, optional
        Callback when pool is exhausted
    """

    def __init__(
        self,
        pool_name: str,
        pool_type: PoolType = PoolType.DATABASE,
        max_size: int = 10,
        alert_threshold: float = 0.8,
        on_exhausted: Callable[[str], None] | None = None,
    ):
        self.pool_name = pool_name
        self.pool_type = pool_type
        self.max_size = max_size
        self.alert_threshold = alert_threshold
        self.on_exhausted = on_exhausted

        self._active = 0
        self._idle = 0
        self._wait_queue = 0
        self._checkouts_total = 0
        self._errors_total = 0
        self._checkout_latencies: list[float] = []
        self._lock = threading.Lock()

        # Initialize metrics
        POOL_CONNECTIONS_MAX.labels(pool_name=pool_name, pool_type=pool_type.value).set(max_size)

    def set_pool_size(
        self,
        active: int | None = None,
        idle: int | None = None,
        max_size: int | None = None,
        wait_queue: int | None = None,
    ):
        """
        Update pool size metrics.

        Parameters
        ----------
        active : int, optional
            Number of active connections
        idle : int, optional
            Number of idle connections
        max_size : int, optional
            Maximum pool size
        wait_queue : int, optional
            Number of requests waiting
        """
        with self._lock:
            if active is not None:
                self._active = active
                POOL_CONNECTIONS_ACTIVE.labels(
                    pool_name=self.pool_name, pool_type=self.pool_type.value
                ).set(active)

            if idle is not None:
                self._idle = idle
                POOL_CONNECTIONS_IDLE.labels(
                    pool_name=self.pool_name, pool_type=self.pool_type.value
                ).set(idle)

            if max_size is not None:
                self.max_size = max_size
                POOL_CONNECTIONS_MAX.labels(
                    pool_name=self.pool_name, pool_type=self.pool_type.value
                ).set(max_size)

            if wait_queue is not None:
                self._wait_queue = wait_queue
                POOL_WAIT_QUEUE.labels(
                    pool_name=self.pool_name, pool_type=self.pool_type.value
                ).set(wait_queue)

            # Calculate utilization
            if self.max_size > 0:
                utilization = self._active / self.max_size
                POOL_UTILIZATION.labels(
                    pool_name=self.pool_name, pool_type=self.pool_type.value
                ).set(utilization)

                # Check for high utilization
                if utilization >= self.alert_threshold:
                    logger.warning(
                        "pool_high_utilization",
                        pool_name=self.pool_name,
                        utilization=utilization,
                        threshold=self.alert_threshold,
                    )

                # Check for exhaustion
                if utilization >= 1.0:
                    POOL_EXHAUSTED_TOTAL.labels(
                        pool_name=self.pool_name, pool_type=self.pool_type.value
                    ).inc()

                    logger.error(
                        "pool_exhausted",
                        pool_name=self.pool_name,
                    )

                    if self.on_exhausted:
                        self.on_exhausted(self.pool_name)

    @contextmanager
    def track_checkout(self) -> Generator[None, None, None]:
        """
        Track a connection checkout.

        Example
        -------
        with pool_tracker.track_checkout():
            conn = pool.get_connection()
            # use connection
        """
        start_time = time.perf_counter()
        success = True

        try:
            yield
        except Exception:
            success = False
            raise
        finally:
            duration = time.perf_counter() - start_time

            with self._lock:
                self._checkouts_total += 1
                self._checkout_latencies.append(duration)

                # Keep last 1000 latencies
                if len(self._checkout_latencies) > 1000:
                    self._checkout_latencies = self._checkout_latencies[-1000:]

            status = "success" if success else "error"

            POOL_CHECKOUT_TOTAL.labels(
                pool_name=self.pool_name, pool_type=self.pool_type.value, status=status
            ).inc()

            POOL_CHECKOUT_LATENCY.labels(
                pool_name=self.pool_name, pool_type=self.pool_type.value
            ).observe(duration)

    def track_checkout_start(self):
        """Track start of checkout (for manual tracking)."""
        return time.perf_counter()

    def track_checkout_end(self, start_time: float, success: bool = True):
        """Track end of checkout (for manual tracking)."""
        duration = time.perf_counter() - start_time

        with self._lock:
            self._checkouts_total += 1
            self._checkout_latencies.append(duration)

        status = "success" if success else "error"

        POOL_CHECKOUT_TOTAL.labels(
            pool_name=self.pool_name, pool_type=self.pool_type.value, status=status
        ).inc()

        POOL_CHECKOUT_LATENCY.labels(
            pool_name=self.pool_name, pool_type=self.pool_type.value
        ).observe(duration)

    def track_error(self, error_type: str):
        """
        Track a pool error.

        Parameters
        ----------
        error_type : str
            Type of error (e.g., "timeout", "connection_refused", "pool_exhausted")
        """
        with self._lock:
            self._errors_total += 1

        POOL_ERRORS_TOTAL.labels(
            pool_name=self.pool_name, pool_type=self.pool_type.value, error_type=error_type
        ).inc()

        logger.warning(
            "pool_error",
            pool_name=self.pool_name,
            error_type=error_type,
        )

    def get_stats(self) -> PoolStats:
        """Get current pool statistics."""
        with self._lock:
            avg_latency = 0.0
            if self._checkout_latencies:
                avg_latency = sum(self._checkout_latencies) / len(self._checkout_latencies) * 1000

            utilization = 0.0
            if self.max_size > 0:
                utilization = self._active / self.max_size

            return PoolStats(
                pool_name=self.pool_name,
                pool_type=self.pool_type,
                active=self._active,
                idle=self._idle,
                max_size=self.max_size,
                wait_queue=self._wait_queue,
                checkouts_total=self._checkouts_total,
                errors_total=self._errors_total,
                avg_checkout_latency_ms=avg_latency,
                utilization=utilization,
            )

    def is_healthy(self) -> bool:
        """Check if pool is healthy."""
        with self._lock:
            if self.max_size == 0:
                return True
            utilization = self._active / self.max_size
            return utilization < self.alert_threshold


# =============================================================================
# Pool Registry
# =============================================================================

_pools: dict[str, ConnectionPoolTracker] = {}
_pools_lock = threading.Lock()


def get_pool_tracker(
    pool_name: str,
    pool_type: PoolType = PoolType.DATABASE,
    **kwargs,
) -> ConnectionPoolTracker:
    """
    Get or create a pool tracker.

    Parameters
    ----------
    pool_name : str
        Name of the pool
    pool_type : PoolType
        Type of pool
    **kwargs
        Additional arguments for ConnectionPoolTracker

    Returns
    -------
    ConnectionPoolTracker
        The pool tracker
    """
    key = f"{pool_name}:{pool_type.value}"

    if key not in _pools:
        with _pools_lock:
            if key not in _pools:
                _pools[key] = ConnectionPoolTracker(
                    pool_name=pool_name,
                    pool_type=pool_type,
                    **kwargs,
                )

    return _pools[key]


def get_all_pool_stats() -> dict[str, PoolStats]:
    """Get stats for all tracked pools."""
    return {name: tracker.get_stats() for name, tracker in _pools.items()}


def check_all_pools_healthy() -> bool:
    """Check if all pools are healthy."""
    return all(tracker.is_healthy() for tracker in _pools.values())


# =============================================================================
# Wrapper for Popular Libraries
# =============================================================================


def wrap_psycopg2_pool(pool, tracker_name: str = "postgres") -> ConnectionPoolTracker:
    """
    Wrap a psycopg2 connection pool with tracking.

    Parameters
    ----------
    pool : psycopg2.pool.AbstractConnectionPool
        The psycopg2 pool
    tracker_name : str
        Name for the tracker

    Returns
    -------
    ConnectionPoolTracker
        The tracker
    """
    tracker = get_pool_tracker(tracker_name, PoolType.DATABASE)

    # Try to get pool stats
    if hasattr(pool, "_pool"):
        tracker.set_pool_size(
            idle=len(pool._pool),
            max_size=pool.maxconn if hasattr(pool, "maxconn") else 10,
        )

    return tracker


def wrap_redis_pool(pool, tracker_name: str = "redis") -> ConnectionPoolTracker:
    """
    Wrap a Redis connection pool with tracking.

    Parameters
    ----------
    pool : redis.ConnectionPool
        The Redis pool
    tracker_name : str
        Name for the tracker

    Returns
    -------
    ConnectionPoolTracker
        The tracker
    """
    tracker = get_pool_tracker(tracker_name, PoolType.CACHE)

    # Try to get pool stats
    if hasattr(pool, "_available_connections") and hasattr(pool, "_in_use_connections"):
        tracker.set_pool_size(
            idle=len(pool._available_connections),
            active=len(pool._in_use_connections),
            max_size=pool.max_connections if hasattr(pool, "max_connections") else 10,
        )

    return tracker
