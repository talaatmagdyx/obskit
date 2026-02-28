"""
Tests for obskit.locking module — DistributedLock and LeaderElection.
"""

from __future__ import annotations

import threading
import time
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from obskit.locking import (
    DistributedLock,
    LeaderElection,
    LockInfo,
    create_distributed_lock,
    create_leader_election,
)


# =============================================================================
# LockInfo Tests
# =============================================================================


class TestLockInfo:
    def test_to_dict(self):
        now = datetime.utcnow()
        info = LockInfo(
            lock_name="test_lock",
            holder_id="holder-1",
            acquired_at=now,
            expires_at=now,
            ttl_seconds=30.0,
        )
        d = info.to_dict()
        assert d["lock_name"] == "test_lock"
        assert d["holder_id"] == "holder-1"
        assert d["ttl_seconds"] == 30.0
        assert isinstance(d["acquired_at"], str)
        assert isinstance(d["expires_at"], str)


# =============================================================================
# DistributedLock Tests
# =============================================================================


class TestDistributedLock:
    def _make_redis(self, set_return=True, exists_return=1, get_return=b"test-holder"):
        redis = MagicMock()
        redis.set.return_value = set_return
        redis.exists.return_value = exists_return
        redis.get.return_value = get_return
        redis.eval.return_value = 1
        return redis

    def test_init(self):
        redis = self._make_redis()
        lock = DistributedLock("my_lock", redis, ttl_seconds=60, max_wait_seconds=5)
        assert lock.lock_name == "my_lock"
        assert lock.ttl_seconds == 60
        assert lock._acquired is False

    def test_acquire_success(self):
        redis = self._make_redis(set_return=True)
        lock = DistributedLock("test", redis)
        result = lock.acquire()
        assert result is True
        assert lock._acquired is True

    def test_acquire_non_blocking_failure(self):
        redis = self._make_redis(set_return=None)
        lock = DistributedLock("test", redis)
        result = lock.acquire(blocking=False)
        assert result is False
        assert lock._acquired is False

    def test_acquire_timeout(self):
        redis = self._make_redis(set_return=None)
        lock = DistributedLock("test", redis, max_wait_seconds=0.05, retry_interval=0.01)
        result = lock.acquire(blocking=True)
        assert result is False

    def test_release_when_not_acquired(self):
        redis = self._make_redis()
        lock = DistributedLock("test", redis)
        # Should not raise or call eval
        lock.release()
        redis.eval.assert_not_called()

    def test_release_when_acquired(self):
        redis = self._make_redis(set_return=True)
        lock = DistributedLock("test", redis)
        lock.acquire()
        lock.release()
        assert lock._acquired is False
        redis.eval.assert_called_once()

    def test_release_handles_error(self):
        redis = self._make_redis(set_return=True)
        redis.eval.side_effect = Exception("Redis error")
        lock = DistributedLock("test", redis)
        lock.acquire()
        # Should not raise
        lock.release()
        assert lock._acquired is False

    def test_extend_when_not_acquired(self):
        redis = self._make_redis()
        lock = DistributedLock("test", redis)
        result = lock.extend()
        assert result is False

    def test_extend_when_acquired(self):
        redis = self._make_redis(set_return=True)
        redis.eval.return_value = 1
        lock = DistributedLock("test", redis)
        lock.acquire()
        result = lock.extend(additional_seconds=60)
        assert result is True

    def test_extend_uses_default_ttl(self):
        redis = self._make_redis(set_return=True)
        redis.eval.return_value = 1
        lock = DistributedLock("test", redis, ttl_seconds=45)
        lock.acquire()
        lock.extend()  # Should use ttl_seconds=45
        # eval should have been called with ttl=45
        call_args = redis.eval.call_args
        assert int(call_args[0][4]) == 45

    def test_is_held_true(self):
        redis = self._make_redis(exists_return=1)
        lock = DistributedLock("test", redis)
        assert lock.is_held() is True

    def test_is_held_false(self):
        redis = self._make_redis(exists_return=0)
        lock = DistributedLock("test", redis)
        assert lock.is_held() is False

    def test_get_holder_returns_string(self):
        redis = MagicMock()
        redis.get.return_value = b"holder-abc"
        lock = DistributedLock("test", redis)
        assert lock.get_holder() == "holder-abc"

    def test_get_holder_returns_none_when_no_holder(self):
        redis = MagicMock()
        redis.get.return_value = None
        lock = DistributedLock("test", redis)
        assert lock.get_holder() is None

    def test_context_manager_success(self):
        redis = self._make_redis(set_return=True)
        redis.eval.return_value = 1
        lock = DistributedLock("test", redis)
        with lock:
            assert lock._acquired is True
        assert lock._acquired is False

    def test_context_manager_failure_raises_timeout(self):
        redis = self._make_redis(set_return=None)
        lock = DistributedLock("test", redis, max_wait_seconds=0.01, retry_interval=0.005)
        with pytest.raises(TimeoutError):
            with lock:
                pass

    def test_lock_key_format(self):
        redis = self._make_redis()
        lock = DistributedLock("migration_lock", redis)
        assert lock._lock_key == "obskit:lock:migration_lock"


# =============================================================================
# DistributedLock Async Tests
# =============================================================================


class TestDistributedLockAsync:
    def _make_async_redis(self, set_return=True):
        redis = MagicMock()
        redis.set = AsyncMock(return_value=set_return)
        redis.eval = AsyncMock(return_value=1)
        return redis

    @pytest.mark.asyncio
    async def test_acquire_async_success(self):
        redis = MagicMock()
        lock = DistributedLock("test", redis)
        with patch("obskit.locking.asyncio.to_thread", new=AsyncMock(return_value=True)):
            result = await lock.acquire_async()
        assert result is True

    @pytest.mark.asyncio
    async def test_acquire_async_non_blocking_failure(self):
        redis = MagicMock()
        lock = DistributedLock("test", redis)
        with patch("obskit.locking.asyncio.to_thread", new=AsyncMock(return_value=None)):
            result = await lock.acquire_async(blocking=False)
        assert result is False

    @pytest.mark.asyncio
    async def test_acquire_async_timeout(self):
        redis = MagicMock()
        lock = DistributedLock("test", redis, max_wait_seconds=0.01, retry_interval=0.005)
        with patch("obskit.locking.asyncio.to_thread", new=AsyncMock(return_value=None)):
            with patch("obskit.locking.asyncio.sleep", new=AsyncMock()):
                result = await lock.acquire_async(blocking=True)
        assert result is False

    @pytest.mark.asyncio
    async def test_release_async(self):
        redis = MagicMock()
        lock = DistributedLock("test", redis)
        lock._acquired = True
        lock._acquired_at = datetime.utcnow()
        with patch("obskit.locking.asyncio.to_thread", new=AsyncMock()):
            await lock.release_async()

    @pytest.mark.asyncio
    async def test_async_context_manager_success(self):
        redis = MagicMock()
        lock = DistributedLock("test", redis)
        with patch("obskit.locking.asyncio.to_thread", new=AsyncMock(return_value=True)):
            with patch.object(lock, "release", return_value=None):
                async with lock:
                    assert lock._acquired is True

    @pytest.mark.asyncio
    async def test_async_context_manager_failure_raises_timeout(self):
        redis = MagicMock()
        lock = DistributedLock("test", redis, max_wait_seconds=0.01, retry_interval=0.005)
        with patch("obskit.locking.asyncio.to_thread", new=AsyncMock(return_value=None)):
            with patch("obskit.locking.asyncio.sleep", new=AsyncMock()):
                with pytest.raises(TimeoutError):
                    async with lock:
                        pass


# =============================================================================
# LeaderElection Tests
# =============================================================================


class TestLeaderElection:
    def _make_redis(self, set_return=True, get_return=None):
        redis = MagicMock()
        redis.set.return_value = set_return
        redis.get.return_value = get_return
        redis.eval.return_value = 1
        redis.expire.return_value = True
        return redis

    def test_init(self):
        redis = self._make_redis()
        election = LeaderElection("scheduler", redis, ttl_seconds=60, renewal_interval=20)
        assert election.election_name == "scheduler"
        assert election.ttl_seconds == 60
        assert election._is_leader is False

    def test_try_become_leader_success(self):
        redis = self._make_redis(set_return=True)
        election = LeaderElection("scheduler", redis)
        result = election.try_become_leader()
        assert result is True
        assert election._is_leader is True

    def test_try_become_leader_already_leader(self):
        redis = MagicMock()
        election = LeaderElection("scheduler", redis)
        # First call fails (someone else holds it)
        redis.set.return_value = None
        # get returns our instance_id
        redis.get.return_value = election._instance_id.encode()
        redis.expire.return_value = True
        result = election.try_become_leader()
        assert result is True
        assert election._is_leader is True

    def test_try_become_leader_failure(self):
        redis = MagicMock()
        election = LeaderElection("scheduler", redis)
        redis.set.return_value = None
        redis.get.return_value = b"another-instance"
        result = election.try_become_leader()
        assert result is False
        assert election._is_leader is False

    def test_am_i_leader_true(self):
        redis = MagicMock()
        election = LeaderElection("scheduler", redis)
        redis.get.return_value = election._instance_id.encode()
        result = election.am_i_leader()
        assert result is True

    def test_am_i_leader_false(self):
        redis = MagicMock()
        redis.get.return_value = b"other-instance"
        election = LeaderElection("scheduler", redis)
        result = election.am_i_leader()
        assert result is False

    def test_am_i_leader_no_leader(self):
        redis = MagicMock()
        redis.get.return_value = None
        election = LeaderElection("scheduler", redis)
        result = election.am_i_leader()
        # When no leader set, result is falsy (None or False)
        assert not result

    def test_get_leader_returns_string(self):
        redis = MagicMock()
        redis.get.return_value = b"leader-xyz"
        election = LeaderElection("scheduler", redis)
        assert election.get_leader() == "leader-xyz"

    def test_get_leader_returns_none_when_no_leader(self):
        redis = MagicMock()
        redis.get.return_value = None
        election = LeaderElection("scheduler", redis)
        assert election.get_leader() is None

    def test_resign_when_not_leader(self):
        redis = self._make_redis()
        election = LeaderElection("scheduler", redis)
        election._is_leader = False
        election.resign()
        redis.eval.assert_not_called()

    def test_resign_when_leader(self):
        redis = self._make_redis()
        election = LeaderElection("scheduler", redis)
        election._is_leader = True
        election.resign()
        assert election._is_leader is False
        redis.eval.assert_called_once()

    def test_leader_key_format(self):
        redis = self._make_redis()
        election = LeaderElection("my_election", redis)
        assert election._leader_key == "obskit:leader:my_election"

    def test_start_and_stop_campaign(self):
        redis = MagicMock()
        redis.set.return_value = None
        redis.get.return_value = None
        redis.eval.return_value = 1
        election = LeaderElection("scheduler", redis, renewal_interval=0.05)
        election.start_campaign()
        assert election._renewal_thread is not None
        assert election._renewal_thread.is_alive()
        election.stop_campaign()
        assert not election._stop_renewal.is_set() or not election._renewal_thread.is_alive()

    def test_campaign_loop_handles_exception(self):
        redis = MagicMock()
        redis.set.side_effect = Exception("Redis down")
        redis.get.return_value = None
        election = LeaderElection("scheduler", redis, renewal_interval=0.01)
        # Should not raise even with exception in campaign loop
        election._stop_renewal.set()
        election._campaign_loop()


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestFactoryFunctions:
    def test_create_distributed_lock(self):
        redis = MagicMock()
        lock = create_distributed_lock("my_lock", redis, ttl_seconds=60)
        assert isinstance(lock, DistributedLock)
        assert lock.lock_name == "my_lock"
        assert lock.ttl_seconds == 60

    def test_create_leader_election(self):
        redis = MagicMock()
        election = create_leader_election("my_election", redis, ttl_seconds=120)
        assert isinstance(election, LeaderElection)
        assert election.election_name == "my_election"
        assert election.ttl_seconds == 120
