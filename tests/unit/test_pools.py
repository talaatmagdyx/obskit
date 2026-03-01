"""Unit tests for obskit.pools — connection pool metrics tracker."""

from __future__ import annotations

import time
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from obskit.pools import (
    ConnectionPoolTracker,
    PoolStats,
    PoolType,
    check_all_pools_healthy,
    get_all_pool_stats,
    get_pool_tracker,
    wrap_psycopg2_pool,
    wrap_redis_pool,
)

# =============================================================================
# PoolType enum
# =============================================================================


class TestPoolType:
    def test_database_value(self):
        assert PoolType.DATABASE.value == "database"

    def test_cache_value(self):
        assert PoolType.CACHE.value == "cache"

    def test_queue_value(self):
        assert PoolType.QUEUE.value == "queue"

    def test_http_value(self):
        assert PoolType.HTTP.value == "http"

    def test_custom_value(self):
        assert PoolType.CUSTOM.value == "custom"


# =============================================================================
# PoolStats
# =============================================================================


class TestPoolStats:
    def test_basic_creation(self):
        stats = PoolStats(pool_name="postgres", pool_type=PoolType.DATABASE)
        assert stats.pool_name == "postgres"
        assert stats.pool_type == PoolType.DATABASE

    def test_default_values(self):
        stats = PoolStats(pool_name="db", pool_type=PoolType.DATABASE)
        assert stats.active == 0
        assert stats.idle == 0
        assert stats.max_size == 0
        assert stats.wait_queue == 0
        assert stats.checkouts_total == 0
        assert stats.errors_total == 0
        assert stats.avg_checkout_latency_ms == pytest.approx(0.0)
        assert stats.utilization == pytest.approx(0.0)

    def test_to_dict(self):
        stats = PoolStats(pool_name="redis", pool_type=PoolType.CACHE)
        d = stats.to_dict()
        assert d["pool_name"] == "redis"
        assert d["pool_type"] == "cache"
        assert "active" in d
        assert "utilization" in d
        assert "last_updated" in d


# =============================================================================
# ConnectionPoolTracker — initialization
# =============================================================================


class TestConnectionPoolTrackerInit:
    def test_basic_init(self):
        tracker = ConnectionPoolTracker("postgres", PoolType.DATABASE)
        assert tracker.pool_name == "postgres"
        assert tracker.pool_type == PoolType.DATABASE

    def test_max_size_stored(self):
        tracker = ConnectionPoolTracker("db", max_size=20)
        assert tracker.max_size == 20

    def test_alert_threshold_stored(self):
        tracker = ConnectionPoolTracker("db", alert_threshold=0.9)
        assert tracker.alert_threshold == pytest.approx(0.9)

    def test_on_exhausted_callback_stored(self):
        callback = MagicMock()
        tracker = ConnectionPoolTracker("db", on_exhausted=callback)
        assert tracker.on_exhausted is callback

    def test_initial_counters_zero(self):
        tracker = ConnectionPoolTracker("db_init")
        assert tracker._active == 0
        assert tracker._idle == 0
        assert tracker._wait_queue == 0
        assert tracker._checkouts_total == 0
        assert tracker._errors_total == 0


# =============================================================================
# ConnectionPoolTracker — set_pool_size
# =============================================================================


class TestConnectionPoolTrackerSetPoolSize:
    def test_set_active(self):
        tracker = ConnectionPoolTracker("db_active", max_size=10)
        tracker.set_pool_size(active=5)
        assert tracker._active == 5

    def test_set_idle(self):
        tracker = ConnectionPoolTracker("db_idle", max_size=10)
        tracker.set_pool_size(idle=3)
        assert tracker._idle == 3

    def test_set_max_size(self):
        tracker = ConnectionPoolTracker("db_max", max_size=10)
        tracker.set_pool_size(max_size=20)
        assert tracker.max_size == 20

    def test_set_wait_queue(self):
        tracker = ConnectionPoolTracker("db_wait", max_size=10)
        tracker.set_pool_size(wait_queue=2)
        assert tracker._wait_queue == 2

    def test_none_values_not_updated(self):
        tracker = ConnectionPoolTracker("db_none", max_size=10)
        tracker._active = 5
        tracker.set_pool_size()  # All None
        assert tracker._active == 5

    def test_high_utilization_logs_warning(self):
        mock_logger = MagicMock()
        with patch("obskit.pools.logger", mock_logger):
            tracker = ConnectionPoolTracker("db_high", max_size=10, alert_threshold=0.5)
            tracker.set_pool_size(active=8)  # 80% utilization, above 50% threshold

        mock_logger.warning.assert_called()

    def test_pool_exhausted_callback_called(self):
        callback = MagicMock()
        tracker = ConnectionPoolTracker("db_exhaust", max_size=10, on_exhausted=callback)
        tracker.set_pool_size(active=10)  # 100% utilization
        callback.assert_called_once_with("db_exhaust")

    def test_no_callback_when_not_exhausted(self):
        callback = MagicMock()
        tracker = ConnectionPoolTracker("db_no_exhaust", max_size=10, on_exhausted=callback)
        tracker.set_pool_size(active=5)
        callback.assert_not_called()

    def test_no_utilization_check_when_max_zero(self):
        tracker = ConnectionPoolTracker("db_zero", max_size=0)
        # Should not raise or divide by zero
        tracker.set_pool_size(active=5)


# =============================================================================
# ConnectionPoolTracker — track_checkout
# =============================================================================


class TestConnectionPoolTrackerTrackCheckout:
    def test_track_checkout_success(self):
        tracker = ConnectionPoolTracker("db_checkout", max_size=10)
        with tracker.track_checkout():
            pass  # Successful checkout
        assert tracker._checkouts_total == 1

    def test_track_checkout_latency_recorded(self):
        tracker = ConnectionPoolTracker("db_latency", max_size=10)
        with tracker.track_checkout():
            time.sleep(0.01)
        assert len(tracker._checkout_latencies) == 1
        assert tracker._checkout_latencies[0] > 0

    def test_track_checkout_failure_on_exception(self):
        tracker = ConnectionPoolTracker("db_fail", max_size=10)
        with pytest.raises(ValueError):
            with tracker.track_checkout():
                raise ValueError("checkout failed")
        assert tracker._checkouts_total == 1
        assert len(tracker._checkout_latencies) == 1

    def test_checkout_latencies_trimmed_at_1000(self):
        tracker = ConnectionPoolTracker("db_trim", max_size=10)
        tracker._checkout_latencies = list(range(1000))
        with tracker.track_checkout():
            pass  # NOSONAR
        assert len(tracker._checkout_latencies) == 1000

    def test_multiple_checkouts_accumulate(self):
        tracker = ConnectionPoolTracker("db_multi", max_size=10)
        for _ in range(5):
            with tracker.track_checkout():
                pass  # NOSONAR
        assert tracker._checkouts_total == 5


# =============================================================================
# ConnectionPoolTracker — track_checkout_start/end (manual)
# =============================================================================


class TestConnectionPoolTrackerManualCheckout:
    def test_track_checkout_start_returns_float(self):
        tracker = ConnectionPoolTracker("db_manual", max_size=10)
        start = tracker.track_checkout_start()
        assert isinstance(start, float)

    def test_track_checkout_end_records_checkout(self):
        tracker = ConnectionPoolTracker("db_manual_end", max_size=10)
        start = tracker.track_checkout_start()
        time.sleep(0.005)
        tracker.track_checkout_end(start, success=True)
        assert tracker._checkouts_total == 1
        assert len(tracker._checkout_latencies) == 1

    def test_track_checkout_end_success_vs_error(self):
        tracker = ConnectionPoolTracker("db_manual_status", max_size=10)
        start = tracker.track_checkout_start()
        tracker.track_checkout_end(start, success=False)
        # Just ensure no crash; actual metric recording happens via prometheus client


# =============================================================================
# ConnectionPoolTracker — track_error
# =============================================================================


class TestConnectionPoolTrackerTrackError:
    def test_track_error_increments_counter(self):
        tracker = ConnectionPoolTracker("db_errors", max_size=10)
        tracker.track_error("timeout")
        assert tracker._errors_total == 1

    def test_track_error_multiple(self):
        tracker = ConnectionPoolTracker("db_multi_errors", max_size=10)
        tracker.track_error("timeout")
        tracker.track_error("connection_refused")
        assert tracker._errors_total == 2

    def test_track_error_logs_warning(self):
        mock_logger = MagicMock()
        with patch("obskit.pools.logger", mock_logger):
            tracker = ConnectionPoolTracker("db_err_log", max_size=10)
            tracker.track_error("timeout")

        mock_logger.warning.assert_called_once()


# =============================================================================
# ConnectionPoolTracker — get_stats
# =============================================================================


class TestConnectionPoolTrackerGetStats:
    def test_get_stats_returns_pool_stats(self):
        tracker = ConnectionPoolTracker("db_get_stats", max_size=10)
        stats = tracker.get_stats()
        assert isinstance(stats, PoolStats)

    def test_get_stats_reflects_state(self):
        tracker = ConnectionPoolTracker("db_state_check", max_size=10)
        tracker.set_pool_size(active=3, idle=5)
        tracker.track_error("timeout")

        stats = tracker.get_stats()
        assert stats.active == 3
        assert stats.idle == 5
        assert stats.errors_total == 1

    def test_get_stats_calculates_avg_latency(self):
        tracker = ConnectionPoolTracker("db_latency_stats", max_size=10)
        tracker._checkout_latencies = [0.1, 0.2, 0.3]
        stats = tracker.get_stats()
        expected_avg = (0.1 + 0.2 + 0.3) / 3 * 1000
        assert stats.avg_checkout_latency_ms == pytest.approx(expected_avg, abs=0.1)

    def test_get_stats_zero_latency_when_no_checkouts(self):
        tracker = ConnectionPoolTracker("db_no_checkouts", max_size=10)
        stats = tracker.get_stats()
        assert stats.avg_checkout_latency_ms == pytest.approx(0.0)

    def test_get_stats_utilization_calculated(self):
        tracker = ConnectionPoolTracker("db_util", max_size=10)
        tracker._active = 5
        stats = tracker.get_stats()
        assert stats.utilization == pytest.approx(0.5, abs=0.01)


# =============================================================================
# ConnectionPoolTracker — is_healthy
# =============================================================================


class TestConnectionPoolTrackerIsHealthy:
    def test_healthy_when_below_threshold(self):
        tracker = ConnectionPoolTracker("db_healthy", max_size=10, alert_threshold=0.8)
        tracker._active = 5  # 50% utilization
        assert tracker.is_healthy()

    def test_unhealthy_when_at_or_above_threshold(self):
        tracker = ConnectionPoolTracker("db_unhealthy", max_size=10, alert_threshold=0.8)
        tracker._active = 9  # 90% utilization
        assert not tracker.is_healthy()

    def test_healthy_when_max_size_is_zero(self):
        tracker = ConnectionPoolTracker("db_zero_max", max_size=0)
        assert tracker.is_healthy()


# =============================================================================
# Pool registry functions
# =============================================================================


class TestGetPoolTracker:
    def test_returns_connection_pool_tracker(self):
        tracker = get_pool_tracker("test_pool_tracker", PoolType.DATABASE)
        assert isinstance(tracker, ConnectionPoolTracker)

    def test_same_instance_for_same_key(self):
        t1 = get_pool_tracker("same_pool_instance", PoolType.DATABASE)
        t2 = get_pool_tracker("same_pool_instance", PoolType.DATABASE)
        assert t1 is t2

    def test_different_instance_for_different_type(self):
        t1 = get_pool_tracker("diff_type_pool", PoolType.DATABASE)
        t2 = get_pool_tracker("diff_type_pool", PoolType.CACHE)
        assert t1 is not t2


class TestGetAllPoolStats:
    def test_returns_dict(self):
        get_pool_tracker("all_stats_pool", PoolType.DATABASE)
        stats = get_all_pool_stats()
        assert isinstance(stats, dict)

    def test_values_are_pool_stats(self):
        get_pool_tracker("all_stats_values_pool", PoolType.CACHE)
        stats = get_all_pool_stats()
        for value in stats.values():
            assert isinstance(value, PoolStats)


class TestCheckAllPoolsHealthy:
    def test_returns_bool(self):
        result = check_all_pools_healthy()
        assert isinstance(result, bool)

    def test_true_when_all_pools_healthy(self):
        # Reset pools registry for clean test
        from obskit.pools import _pools
        original = dict(_pools)
        _pools.clear()

        tracker = ConnectionPoolTracker("healthy_pool", max_size=10, alert_threshold=0.9)
        tracker._active = 2  # 20% utilization - healthy
        _pools["healthy_pool:database"] = tracker

        result = check_all_pools_healthy()
        assert result is True

        # Restore
        _pools.clear()
        _pools.update(original)

    def test_false_when_any_pool_unhealthy(self):
        from obskit.pools import _pools
        original = dict(_pools)
        _pools.clear()

        tracker = ConnectionPoolTracker("unhealthy_pool", max_size=10, alert_threshold=0.5)
        tracker._active = 8  # 80% utilization - above 50% threshold
        _pools["unhealthy_pool:database"] = tracker

        result = check_all_pools_healthy()
        assert result is False

        # Restore
        _pools.clear()
        _pools.update(original)


# =============================================================================
# Wrapper functions for popular libraries
# =============================================================================


class TestWrapPsycopg2Pool:
    def test_returns_connection_pool_tracker(self):
        mock_pool = MagicMock()
        mock_pool._pool = []
        mock_pool.maxconn = 10

        tracker = wrap_psycopg2_pool(mock_pool, tracker_name="pg_wrap_test")
        assert isinstance(tracker, ConnectionPoolTracker)

    def test_pool_size_set_from_pool_attributes(self):
        mock_pool = MagicMock()
        mock_pool._pool = ["conn1", "conn2"]  # 2 idle connections
        mock_pool.maxconn = 10

        tracker = wrap_psycopg2_pool(mock_pool, tracker_name="pg_size_test")
        assert tracker._idle == 2

    def test_without_pool_attribute(self):
        mock_pool = MagicMock(spec=[])  # No _pool attribute
        tracker = wrap_psycopg2_pool(mock_pool, tracker_name="pg_no_attr_test")
        assert isinstance(tracker, ConnectionPoolTracker)


class TestWrapRedisPool:
    def test_returns_connection_pool_tracker(self):
        mock_pool = MagicMock()
        mock_pool._available_connections = []
        mock_pool._in_use_connections = set()
        mock_pool.max_connections = 50

        tracker = wrap_redis_pool(mock_pool, tracker_name="redis_wrap_test")
        assert isinstance(tracker, ConnectionPoolTracker)
        assert tracker.pool_type == PoolType.CACHE

    def test_pool_size_set_from_redis_pool(self):
        mock_pool = MagicMock()
        mock_pool._available_connections = ["c1", "c2", "c3"]
        mock_pool._in_use_connections = {"c4", "c5"}
        mock_pool.max_connections = 20

        tracker = wrap_redis_pool(mock_pool, tracker_name="redis_size_test")
        assert tracker._idle == 3
        assert tracker._active == 2

    def test_without_redis_pool_attributes(self):
        mock_pool = MagicMock(spec=[])  # No relevant attributes
        tracker = wrap_redis_pool(mock_pool, tracker_name="redis_no_attr_test")
        assert isinstance(tracker, ConnectionPoolTracker)
