"""
Distributed Locking
===================

Distributed locks and leader election with observability.

Features:
- Redis-based distributed locks
- Leader election
- Lock metrics
- Deadlock detection

Example:
    from obskit.locking import DistributedLock, LeaderElection
    import redis

    redis_client = redis.Redis()

    # Distributed lock
    async with DistributedLock("migration_lock", redis_client):
        run_migration()

    # Leader election
    leader = LeaderElection("scheduler", redis_client)
    if leader.am_i_leader():
        run_scheduled_tasks()
"""

import asyncio
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from prometheus_client import Counter, Gauge, Histogram

from obskit.logging import get_logger

logger = get_logger(__name__)


# =============================================================================
# Prometheus Metrics
# =============================================================================

LOCK_ACQUISITIONS_TOTAL = Counter(
    "distributed_lock_acquisitions_total",
    "Total lock acquisition attempts",
    ["lock_name", "status"],
)

LOCK_HOLD_TIME = Histogram(
    "distributed_lock_hold_seconds",
    "Time lock was held",
    ["lock_name"],
    buckets=(0.1, 0.5, 1, 5, 10, 30, 60, 120, 300),
)

LOCK_WAIT_TIME = Histogram(
    "distributed_lock_wait_seconds",
    "Time waiting to acquire lock",
    ["lock_name"],
    buckets=(0.01, 0.1, 0.5, 1, 5, 10, 30),
)

LOCK_CURRENTLY_HELD = Gauge(
    "distributed_lock_held", "Whether lock is currently held (1=yes, 0=no)", ["lock_name", "holder"]
)

LEADER_ELECTION_STATUS = Gauge(
    "leader_election_is_leader",
    "Whether this instance is the leader (1=yes, 0=no)",
    ["election_name"],
)

LEADER_ELECTION_TERMS = Counter(
    "leader_election_terms_total", "Total leadership terms", ["election_name"]
)


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class LockInfo:
    """Information about a lock."""

    lock_name: str
    holder_id: str
    acquired_at: datetime
    expires_at: datetime
    ttl_seconds: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "lock_name": self.lock_name,
            "holder_id": self.holder_id,
            "acquired_at": self.acquired_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "ttl_seconds": self.ttl_seconds,
        }


# =============================================================================
# Distributed Lock
# =============================================================================


class DistributedLock:
    """
    Redis-based distributed lock with observability.

    Parameters
    ----------
    lock_name : str
        Name of the lock
    redis_client : redis.Redis
        Redis client instance
    ttl_seconds : float
        Lock TTL (auto-release time)
    retry_interval : float
        Interval between acquisition retries
    max_wait_seconds : float
        Maximum time to wait for lock
    """

    def __init__(
        self,
        lock_name: str,
        redis_client: Any,
        ttl_seconds: float = 30.0,
        retry_interval: float = 0.1,
        max_wait_seconds: float = 10.0,
    ):
        self.lock_name = lock_name
        self.redis = redis_client
        self.ttl_seconds = ttl_seconds
        self.retry_interval = retry_interval
        self.max_wait_seconds = max_wait_seconds

        self._lock_key = f"obskit:lock:{lock_name}"
        self._holder_id = f"{uuid.uuid4().hex[:8]}-{threading.current_thread().ident}"
        self._acquired = False
        self._acquired_at: datetime | None = None

    def acquire(self, blocking: bool = True) -> bool:
        """
        Acquire the lock.

        Parameters
        ----------
        blocking : bool
            Whether to block waiting for lock

        Returns
        -------
        bool
            Whether lock was acquired
        """
        start_time = time.perf_counter()

        while True:
            # Try to set lock with NX (only if not exists)
            acquired = self.redis.set(
                self._lock_key,
                self._holder_id,
                nx=True,
                ex=int(self.ttl_seconds),
            )

            if acquired:
                self._acquired = True
                self._acquired_at = datetime.utcnow()

                wait_time = time.perf_counter() - start_time

                LOCK_ACQUISITIONS_TOTAL.labels(lock_name=self.lock_name, status="success").inc()

                LOCK_WAIT_TIME.labels(lock_name=self.lock_name).observe(wait_time)

                LOCK_CURRENTLY_HELD.labels(lock_name=self.lock_name, holder=self._holder_id).set(1)

                logger.debug(
                    "lock_acquired",
                    lock_name=self.lock_name,
                    holder_id=self._holder_id,
                    wait_time_seconds=wait_time,
                )

                return True

            if not blocking:
                LOCK_ACQUISITIONS_TOTAL.labels(
                    lock_name=self.lock_name, status="failed_non_blocking"
                ).inc()
                return False

            # Check timeout
            elapsed = time.perf_counter() - start_time
            if elapsed >= self.max_wait_seconds:
                LOCK_ACQUISITIONS_TOTAL.labels(lock_name=self.lock_name, status="timeout").inc()

                logger.warning(
                    "lock_acquisition_timeout",
                    lock_name=self.lock_name,
                    wait_time_seconds=elapsed,
                )
                return False

            time.sleep(self.retry_interval)

    def release(self):
        """Release the lock."""
        if not self._acquired:
            return

        # Use Lua script to ensure we only delete our own lock
        lua_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """

        try:
            self.redis.eval(lua_script, 1, self._lock_key, self._holder_id)
        except Exception as e:
            logger.error("lock_release_failed", lock_name=self.lock_name, error=str(e))

        if self._acquired_at:
            hold_time = (datetime.utcnow() - self._acquired_at).total_seconds()
            LOCK_HOLD_TIME.labels(lock_name=self.lock_name).observe(hold_time)

        LOCK_CURRENTLY_HELD.labels(lock_name=self.lock_name, holder=self._holder_id).set(0)

        self._acquired = False
        self._acquired_at = None

        logger.debug("lock_released", lock_name=self.lock_name, holder_id=self._holder_id)

    def extend(self, additional_seconds: float = None) -> bool:
        """Extend lock TTL."""
        if not self._acquired:
            return False

        ttl = additional_seconds or self.ttl_seconds

        # Only extend if we still hold the lock
        lua_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("expire", KEYS[1], ARGV[2])
        else
            return 0
        end
        """

        result = self.redis.eval(lua_script, 1, self._lock_key, self._holder_id, int(ttl))
        return bool(result)

    def is_held(self) -> bool:
        """Check if lock is currently held by anyone."""
        return self.redis.exists(self._lock_key) > 0

    def get_holder(self) -> str | None:
        """Get current lock holder."""
        holder = self.redis.get(self._lock_key)
        return holder.decode() if holder else None

    def __enter__(self) -> "DistributedLock":
        if not self.acquire():
            raise TimeoutError(f"Could not acquire lock: {self.lock_name}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
        return False

    async def acquire_async(self, blocking: bool = True) -> bool:
        """Async version of acquire."""
        start_time = time.perf_counter()

        while True:
            acquired = await asyncio.to_thread(
                self.redis.set,
                self._lock_key,
                self._holder_id,
                nx=True,
                ex=int(self.ttl_seconds),
            )

            if acquired:
                self._acquired = True
                self._acquired_at = datetime.utcnow()

                wait_time = time.perf_counter() - start_time
                LOCK_ACQUISITIONS_TOTAL.labels(lock_name=self.lock_name, status="success").inc()
                LOCK_WAIT_TIME.labels(lock_name=self.lock_name).observe(wait_time)
                LOCK_CURRENTLY_HELD.labels(lock_name=self.lock_name, holder=self._holder_id).set(1)

                return True

            if not blocking:
                return False

            elapsed = time.perf_counter() - start_time
            if elapsed >= self.max_wait_seconds:
                LOCK_ACQUISITIONS_TOTAL.labels(lock_name=self.lock_name, status="timeout").inc()
                return False

            await asyncio.sleep(self.retry_interval)

    async def release_async(self):
        """Async version of release."""
        await asyncio.to_thread(self.release)

    async def __aenter__(self) -> "DistributedLock":
        if not await self.acquire_async():
            raise TimeoutError(f"Could not acquire lock: {self.lock_name}")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.release_async()
        return False


# =============================================================================
# Leader Election
# =============================================================================


class LeaderElection:
    """
    Redis-based leader election with observability.

    Parameters
    ----------
    election_name : str
        Name of the election
    redis_client : redis.Redis
        Redis client
    ttl_seconds : float
        Leadership TTL (must renew before expiry)
    renewal_interval : float
        How often to renew leadership
    """

    def __init__(
        self,
        election_name: str,
        redis_client: Any,
        ttl_seconds: float = 30.0,
        renewal_interval: float = 10.0,
    ):
        self.election_name = election_name
        self.redis = redis_client
        self.ttl_seconds = ttl_seconds
        self.renewal_interval = renewal_interval

        self._leader_key = f"obskit:leader:{election_name}"
        self._instance_id = f"{uuid.uuid4().hex[:8]}"
        self._is_leader = False
        self._renewal_thread: threading.Thread | None = None
        self._stop_renewal = threading.Event()

    def try_become_leader(self) -> bool:
        """
        Try to become the leader.

        Returns
        -------
        bool
            Whether this instance is now the leader
        """
        acquired = self.redis.set(
            self._leader_key,
            self._instance_id,
            nx=True,
            ex=int(self.ttl_seconds),
        )

        if acquired:
            self._is_leader = True
            LEADER_ELECTION_STATUS.labels(election_name=self.election_name).set(1)
            LEADER_ELECTION_TERMS.labels(election_name=self.election_name).inc()

            logger.info(
                "became_leader",
                election_name=self.election_name,
                instance_id=self._instance_id,
            )

            return True

        # Check if we're already the leader
        current_leader = self.redis.get(self._leader_key)
        if current_leader and current_leader.decode() == self._instance_id:
            self._is_leader = True
            # Refresh TTL
            self.redis.expire(self._leader_key, int(self.ttl_seconds))
            return True

        self._is_leader = False
        LEADER_ELECTION_STATUS.labels(election_name=self.election_name).set(0)
        return False

    def am_i_leader(self) -> bool:
        """Check if this instance is the current leader."""
        current_leader = self.redis.get(self._leader_key)
        is_leader = current_leader and current_leader.decode() == self._instance_id
        self._is_leader = is_leader
        LEADER_ELECTION_STATUS.labels(election_name=self.election_name).set(1 if is_leader else 0)
        return is_leader

    def get_leader(self) -> str | None:
        """Get current leader ID."""
        leader = self.redis.get(self._leader_key)
        return leader.decode() if leader else None

    def resign(self):
        """Resign from leadership."""
        if not self._is_leader:
            return

        # Only delete if we're the leader
        lua_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """

        self.redis.eval(lua_script, 1, self._leader_key, self._instance_id)
        self._is_leader = False
        LEADER_ELECTION_STATUS.labels(election_name=self.election_name).set(0)

        logger.info(
            "resigned_leadership",
            election_name=self.election_name,
            instance_id=self._instance_id,
        )

    def start_campaign(self):
        """Start continuous leader election campaign."""
        self._stop_renewal.clear()
        self._renewal_thread = threading.Thread(target=self._campaign_loop, daemon=True)
        self._renewal_thread.start()

    def stop_campaign(self):
        """Stop leader election campaign."""
        self._stop_renewal.set()
        if self._renewal_thread:
            self._renewal_thread.join(timeout=5)
        self.resign()

    def _campaign_loop(self):
        """Background loop for leader election."""
        while not self._stop_renewal.is_set():
            try:
                self.try_become_leader()
            except Exception as e:
                logger.error("leader_election_error", error=str(e))

            self._stop_renewal.wait(self.renewal_interval)


# =============================================================================
# Factory Functions
# =============================================================================


def create_distributed_lock(
    lock_name: str,
    redis_client: Any,
    **kwargs,
) -> DistributedLock:
    """Create a distributed lock."""
    return DistributedLock(lock_name, redis_client, **kwargs)


def create_leader_election(
    election_name: str,
    redis_client: Any,
    **kwargs,
) -> LeaderElection:
    """Create a leader election."""
    return LeaderElection(election_name, redis_client, **kwargs)
