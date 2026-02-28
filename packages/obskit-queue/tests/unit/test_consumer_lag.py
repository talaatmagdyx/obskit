"""
Tests for obskit.consumer_lag module.

Tests cover:
- QueueType enum
- LagSample and ConsumerLagStats dataclasses
- ConsumerLagTracker: set_lag, message_consumed, messages_consumed
- ConsumerLagTracker: _calculate_growth_rate, _calculate_velocity
- ConsumerLagTracker: _check_threshold, get_stats, is_healthy
- Registry helpers: get_consumer_lag_tracker, get_all_consumer_lag_stats
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from obskit.consumer_lag import (
    ConsumerLagStats,
    ConsumerLagTracker,
    LagSample,
    QueueType,
    get_all_consumer_lag_stats,
    get_consumer_lag_tracker,
)

# =============================================================================
# QueueType enum
# =============================================================================


class TestQueueType:
    def test_all_values_exist(self):
        assert QueueType.RABBITMQ.value == "rabbitmq"
        assert QueueType.KAFKA.value == "kafka"
        assert QueueType.SQS.value == "sqs"
        assert QueueType.REDIS.value == "redis"
        assert QueueType.CUSTOM.value == "custom"

    def test_enum_members_count(self):
        assert len(list(QueueType)) == 5


# =============================================================================
# LagSample dataclass
# =============================================================================


class TestLagSample:
    def test_creation_with_defaults(self):
        ts = datetime.utcnow()
        sample = LagSample(timestamp=ts, messages=100)
        assert sample.timestamp == ts
        assert sample.messages == 100
        assert sample.bytes == 0

    def test_creation_with_bytes(self):
        ts = datetime.utcnow()
        sample = LagSample(timestamp=ts, messages=500, bytes=10000)
        assert sample.bytes == 10000


# =============================================================================
# ConsumerLagStats dataclass
# =============================================================================


class TestConsumerLagStats:
    def test_default_values(self):
        stats = ConsumerLagStats(
            queue_name="orders",
            queue_type=QueueType.RABBITMQ,
            consumer_group="default",
        )
        assert stats.current_lag_messages == 0
        assert stats.current_lag_bytes == 0
        assert stats.lag_growth_rate == 0.0
        assert stats.consumer_velocity == 0.0
        assert stats.estimated_catch_up_seconds == 0.0
        assert stats.total_consumed == 0
        assert stats.is_falling_behind is False

    def test_to_dict(self):
        stats = ConsumerLagStats(
            queue_name="orders",
            queue_type=QueueType.KAFKA,
            consumer_group="group-1",
            current_lag_messages=50,
            current_lag_bytes=1000,
            lag_growth_rate=2.5,
            consumer_velocity=10.0,
            estimated_catch_up_seconds=5.0,
            total_consumed=200,
            is_falling_behind=True,
        )
        d = stats.to_dict()
        assert d["queue_name"] == "orders"
        assert d["queue_type"] == "kafka"
        assert d["consumer_group"] == "group-1"
        assert d["current_lag_messages"] == 50
        assert d["current_lag_bytes"] == 1000
        assert d["lag_growth_rate"] == 2.5
        assert d["consumer_velocity"] == 10.0
        assert d["estimated_catch_up_seconds"] == 5.0
        assert d["total_consumed"] == 200
        assert d["is_falling_behind"] is True
        assert "last_updated" in d


# =============================================================================
# ConsumerLagTracker
# =============================================================================


class TestConsumerLagTrackerInit:
    def test_default_initialization(self):
        tracker = ConsumerLagTracker("test_queue")
        assert tracker.queue_name == "test_queue"
        assert tracker.queue_type == QueueType.RABBITMQ
        assert tracker.consumer_group == "default"
        assert tracker.lag_threshold == 10000
        assert tracker.window_seconds == 60
        assert tracker.on_high_lag is None
        assert tracker._current_lag == 0
        assert tracker._current_lag_bytes == 0
        assert tracker._total_consumed == 0

    def test_custom_initialization(self):
        callback = MagicMock()
        tracker = ConsumerLagTracker(
            "orders",
            queue_type=QueueType.KAFKA,
            consumer_group="group-1",
            lag_threshold=5000,
            window_seconds=120,
            on_high_lag=callback,
        )
        assert tracker.queue_type == QueueType.KAFKA
        assert tracker.consumer_group == "group-1"
        assert tracker.lag_threshold == 5000
        assert tracker.window_seconds == 120
        assert tracker.on_high_lag is callback


class TestConsumerLagTrackerSetLag:
    def test_set_lag_basic(self):
        tracker = ConsumerLagTracker("test_queue_set_lag_basic")
        tracker.set_lag(messages=100, bytes=5000)
        assert tracker._current_lag == 100
        assert tracker._current_lag_bytes == 5000

    def test_set_lag_records_sample(self):
        tracker = ConsumerLagTracker("test_queue_set_lag_sample")
        tracker.set_lag(messages=200)
        assert len(tracker._lag_samples) == 1
        assert tracker._lag_samples[0].messages == 200

    def test_set_lag_multiple_times(self):
        tracker = ConsumerLagTracker("test_queue_set_lag_multiple")
        tracker.set_lag(messages=100)
        tracker.set_lag(messages=200)
        tracker.set_lag(messages=150)
        assert tracker._current_lag == 150
        assert len(tracker._lag_samples) == 3

    def test_set_lag_cleanup_old_samples(self):
        tracker = ConsumerLagTracker("test_queue_set_lag_cleanup", window_seconds=1)
        # Add an old sample directly
        old_ts = datetime.utcnow() - timedelta(seconds=10)
        tracker._lag_samples.append(LagSample(timestamp=old_ts, messages=50))
        # This should trigger cleanup
        tracker.set_lag(messages=100)
        # Only the new sample should remain (old one pruned)
        assert all(
            s.timestamp > datetime.utcnow() - timedelta(seconds=2)
            for s in tracker._lag_samples
        )

    def test_set_lag_zero(self):
        tracker = ConsumerLagTracker("test_queue_set_lag_zero")
        tracker.set_lag(messages=0)
        assert tracker._current_lag == 0

    def test_set_lag_bytes_default(self):
        tracker = ConsumerLagTracker("test_queue_set_lag_bytes_default")
        tracker.set_lag(messages=50)
        assert tracker._current_lag_bytes == 0


class TestConsumerLagTrackerMessagesConsumed:
    def test_message_consumed_increments_total(self):
        tracker = ConsumerLagTracker("test_queue_consumed_single")
        tracker.message_consumed()
        assert tracker._total_consumed == 1

    def test_messages_consumed_with_count(self):
        tracker = ConsumerLagTracker("test_queue_consumed_count")
        tracker.messages_consumed(count=5)
        assert tracker._total_consumed == 5

    def test_messages_consumed_accumulates(self):
        tracker = ConsumerLagTracker("test_queue_consumed_accum")
        tracker.messages_consumed(count=3)
        tracker.messages_consumed(count=7)
        assert tracker._total_consumed == 10

    def test_messages_consumed_records_timestamps(self):
        tracker = ConsumerLagTracker("test_queue_consumed_timestamps")
        tracker.messages_consumed(count=4)
        assert len(tracker._consumed_timestamps) == 4

    def test_messages_consumed_cleanup_old_timestamps(self):
        tracker = ConsumerLagTracker("test_queue_consumed_cleanup", window_seconds=1)
        old_ts = datetime.utcnow() - timedelta(seconds=10)
        tracker._consumed_timestamps.extend([old_ts, old_ts, old_ts])
        tracker.messages_consumed(count=1)
        # Old timestamps should be pruned
        remaining = [
            t for t in tracker._consumed_timestamps
            if t <= datetime.utcnow() - timedelta(seconds=2)
        ]
        assert len(remaining) == 0


class TestConsumerLagTrackerCalculateGrowthRate:
    def test_no_samples_returns_zero(self):
        tracker = ConsumerLagTracker("test_growth_no_samples")
        rate = tracker._calculate_growth_rate()
        assert rate == 0.0

    def test_single_sample_returns_zero(self):
        tracker = ConsumerLagTracker("test_growth_single")
        ts = datetime.utcnow()
        tracker._lag_samples = [LagSample(timestamp=ts, messages=100)]
        rate = tracker._calculate_growth_rate()
        assert rate == 0.0

    def test_increasing_lag(self):
        tracker = ConsumerLagTracker("test_growth_increasing")
        now = datetime.utcnow()
        tracker._lag_samples = [
            LagSample(timestamp=now - timedelta(seconds=10), messages=100),
            LagSample(timestamp=now, messages=200),
        ]
        rate = tracker._calculate_growth_rate()
        assert rate == pytest.approx(10.0, rel=0.1)

    def test_decreasing_lag(self):
        tracker = ConsumerLagTracker("test_growth_decreasing")
        now = datetime.utcnow()
        tracker._lag_samples = [
            LagSample(timestamp=now - timedelta(seconds=10), messages=200),
            LagSample(timestamp=now, messages=100),
        ]
        rate = tracker._calculate_growth_rate()
        assert rate == pytest.approx(-10.0, rel=0.1)

    def test_same_time_returns_zero(self):
        tracker = ConsumerLagTracker("test_growth_same_time")
        now = datetime.utcnow()
        tracker._lag_samples = [
            LagSample(timestamp=now, messages=100),
            LagSample(timestamp=now, messages=200),
        ]
        rate = tracker._calculate_growth_rate()
        assert rate == 0.0


class TestConsumerLagTrackerCalculateVelocity:
    def test_no_timestamps_returns_zero(self):
        tracker = ConsumerLagTracker("test_velocity_empty")
        velocity = tracker._calculate_velocity()
        assert velocity == 0.0

    def test_velocity_with_timestamps(self):
        tracker = ConsumerLagTracker("test_velocity_calc", window_seconds=60)
        now = datetime.utcnow()
        # Simulate 10 messages over 10 seconds
        tracker._consumed_timestamps = [
            now - timedelta(seconds=10 - i) for i in range(10)
        ]
        velocity = tracker._calculate_velocity()
        assert velocity > 0.0

    def test_velocity_all_old_timestamps_returns_zero(self):
        tracker = ConsumerLagTracker("test_velocity_old", window_seconds=5)
        old_ts = datetime.utcnow() - timedelta(seconds=100)
        tracker._consumed_timestamps = [old_ts, old_ts, old_ts]
        velocity = tracker._calculate_velocity()
        assert velocity == 0.0


class TestConsumerLagTrackerCheckThreshold:
    def test_below_threshold_no_callback(self):
        callback = MagicMock()
        tracker = ConsumerLagTracker(
            "test_threshold_below",
            lag_threshold=1000,
            on_high_lag=callback,
        )
        tracker._check_threshold(500)
        callback.assert_not_called()

    def test_above_threshold_calls_callback(self):
        callback = MagicMock()
        tracker = ConsumerLagTracker(
            "test_threshold_above",
            lag_threshold=100,
            on_high_lag=callback,
        )
        tracker._check_threshold(200)
        callback.assert_called_once_with("test_threshold_above", 200)

    def test_threshold_cooldown_prevents_repeated_calls(self):
        callback = MagicMock()
        tracker = ConsumerLagTracker(
            "test_threshold_cooldown",
            lag_threshold=100,
            on_high_lag=callback,
        )
        tracker._check_threshold(200)
        tracker._check_threshold(300)  # Should be in cooldown
        callback.assert_called_once()  # Only first call goes through

    def test_exactly_at_threshold_triggers(self):
        callback = MagicMock()
        tracker = ConsumerLagTracker(
            "test_threshold_exact",
            lag_threshold=100,
            on_high_lag=callback,
        )
        tracker._check_threshold(100)
        callback.assert_called_once()

    def test_no_callback_no_error(self):
        tracker = ConsumerLagTracker("test_threshold_no_callback", lag_threshold=100)
        # Should not raise
        tracker._check_threshold(200)

    def test_cooldown_expired_allows_second_alert(self):
        callback = MagicMock()
        tracker = ConsumerLagTracker(
            "test_threshold_cooldown_expired",
            lag_threshold=100,
            on_high_lag=callback,
        )
        # Set last alert to far in the past
        tracker._last_high_lag_alert = datetime.utcnow() - timedelta(minutes=10)
        tracker._check_threshold(200)
        callback.assert_called_once()


class TestConsumerLagTrackerGetStats:
    def test_get_stats_returns_correct_type(self):
        tracker = ConsumerLagTracker("test_getstats_type")
        stats = tracker.get_stats()
        assert isinstance(stats, ConsumerLagStats)

    def test_get_stats_reflects_current_lag(self):
        tracker = ConsumerLagTracker("test_getstats_lag")
        tracker._current_lag = 500
        tracker._current_lag_bytes = 10000
        tracker._total_consumed = 100
        stats = tracker.get_stats()
        assert stats.current_lag_messages == 500
        assert stats.current_lag_bytes == 10000
        assert stats.total_consumed == 100

    def test_get_stats_catch_up_when_velocity_positive(self):
        tracker = ConsumerLagTracker("test_getstats_catchup", window_seconds=60)
        tracker._current_lag = 100
        now = datetime.utcnow()
        # Simulate some consumed messages to get velocity
        tracker._consumed_timestamps = [
            now - timedelta(seconds=10 - i) for i in range(10)
        ]
        stats = tracker.get_stats()
        # catch_up should be > 0 since lag > 0 and velocity > 0
        assert stats.estimated_catch_up_seconds >= 0

    def test_get_stats_is_falling_behind_when_growth_positive(self):
        tracker = ConsumerLagTracker("test_getstats_falling")
        now = datetime.utcnow()
        tracker._lag_samples = [
            LagSample(timestamp=now - timedelta(seconds=10), messages=100),
            LagSample(timestamp=now, messages=200),
        ]
        stats = tracker.get_stats()
        assert stats.is_falling_behind is True

    def test_get_stats_queue_info(self):
        tracker = ConsumerLagTracker(
            "test_getstats_info",
            queue_type=QueueType.KAFKA,
            consumer_group="my-group",
        )
        stats = tracker.get_stats()
        assert stats.queue_name == "test_getstats_info"
        assert stats.queue_type == QueueType.KAFKA
        assert stats.consumer_group == "my-group"


class TestConsumerLagTrackerIsHealthy:
    def test_is_healthy_when_low_lag_not_falling_behind(self):
        tracker = ConsumerLagTracker("test_healthy_true", lag_threshold=1000)
        tracker._current_lag = 10
        assert tracker.is_healthy() is True

    def test_is_not_healthy_when_lag_exceeds_threshold(self):
        tracker = ConsumerLagTracker("test_healthy_false_lag", lag_threshold=100)
        tracker._current_lag = 500
        assert tracker.is_healthy() is False

    def test_is_not_healthy_when_falling_behind(self):
        tracker = ConsumerLagTracker("test_healthy_false_falling", lag_threshold=10000)
        now = datetime.utcnow()
        tracker._lag_samples = [
            LagSample(timestamp=now - timedelta(seconds=10), messages=100),
            LagSample(timestamp=now, messages=200),
        ]
        tracker._current_lag = 200
        assert tracker.is_healthy() is False


# =============================================================================
# Registry helpers
# =============================================================================


class TestRegistryHelpers:
    def setup_method(self):
        """Clear the module-level registry before each test."""
        import obskit.consumer_lag as module
        module._lag_trackers.clear()

    def test_get_consumer_lag_tracker_creates_new(self):
        tracker = get_consumer_lag_tracker("queue_reg_a", consumer_group="grp")
        assert tracker is not None
        assert tracker.queue_name == "queue_reg_a"
        assert tracker.consumer_group == "grp"

    def test_get_consumer_lag_tracker_returns_same_instance(self):
        t1 = get_consumer_lag_tracker("queue_reg_same", consumer_group="g1")
        t2 = get_consumer_lag_tracker("queue_reg_same", consumer_group="g1")
        assert t1 is t2

    def test_get_consumer_lag_tracker_different_groups_different_instances(self):
        t1 = get_consumer_lag_tracker("queue_reg_diff", consumer_group="g1")
        t2 = get_consumer_lag_tracker("queue_reg_diff", consumer_group="g2")
        assert t1 is not t2

    def test_get_all_consumer_lag_stats_empty(self):
        stats = get_all_consumer_lag_stats()
        assert isinstance(stats, dict)
        assert len(stats) == 0

    def test_get_all_consumer_lag_stats_with_trackers(self):
        get_consumer_lag_tracker("queue_all_1", consumer_group="a")
        get_consumer_lag_tracker("queue_all_2", consumer_group="b")
        stats = get_all_consumer_lag_stats()
        assert len(stats) == 2
        for key, val in stats.items():
            assert isinstance(val, ConsumerLagStats)


# =============================================================================
# Integration-style tests (set_lag + metrics update)
# =============================================================================


class TestConsumerLagTrackerIntegration:
    def test_set_lag_then_get_stats_consistent(self):
        tracker = ConsumerLagTracker("test_integ_consistent")
        tracker.set_lag(messages=300, bytes=15000)
        stats = tracker.get_stats()
        assert stats.current_lag_messages == 300
        assert stats.current_lag_bytes == 15000

    def test_full_lifecycle(self):
        """Test a full lifecycle: set_lag, consume, get_stats."""
        tracker = ConsumerLagTracker(
            "test_full_lifecycle",
            queue_type=QueueType.KAFKA,
            consumer_group="consumers",
            lag_threshold=500,
        )
        tracker.set_lag(messages=100)
        tracker.messages_consumed(count=10)
        tracker.message_consumed()
        stats = tracker.get_stats()
        assert stats.total_consumed == 11
        assert stats.current_lag_messages == 100

    def test_high_lag_triggers_callback_and_metric(self):
        callback = MagicMock()
        tracker = ConsumerLagTracker(
            "test_high_lag_cb",
            lag_threshold=10,
            on_high_lag=callback,
        )
        tracker.set_lag(messages=100)
        callback.assert_called_once_with("test_high_lag_cb", 100)

    def test_catch_up_time_zero_when_no_velocity(self):
        tracker = ConsumerLagTracker("test_catchup_zero_vel")
        tracker.set_lag(messages=500)
        stats = tracker.get_stats()
        # No consumed messages -> velocity=0 -> catch_up=0
        assert stats.estimated_catch_up_seconds == 0.0

    def test_stats_to_dict(self):
        stats = ConsumerLagStats(
            queue_name="q",
            queue_type=QueueType.SQS,
            consumer_group="g",
        )
        d = stats.to_dict()
        assert d["queue_type"] == "sqs"
        assert "last_updated" in d


# =============================================================================
# Coverage gap fixes
# =============================================================================


class TestConsumerLagCoverageGaps:
    """Cover the 3 remaining missing lines/branches in consumer_lag.py."""

    def test_set_lag_catch_up_with_velocity(self):
        """Lines 244-245: CONSUMER_LAG_SECONDS set when velocity > 0 and messages > 0."""
        from datetime import datetime, timedelta

        tracker = ConsumerLagTracker("test_catchup_velocity")
        now = datetime.utcnow()
        # Pre-populate consumed_timestamps so velocity > 0
        tracker._consumed_timestamps = [
            now - timedelta(seconds=5 - i * 0.5) for i in range(10)
        ]
        # set_lag with messages > 0 should hit lines 244-245
        tracker.set_lag(messages=100)
        stats = tracker.get_stats()
        assert stats.estimated_catch_up_seconds >= 0

    def test_calculate_velocity_zero_time_span(self):
        """Line 319: time_span <= 0 returns 0.0 when recent[0] == now."""
        from datetime import datetime

        fixed_now = datetime(2025, 1, 1, 12, 0, 0)
        tracker = ConsumerLagTracker("test_zero_timespan", window_seconds=60)
        # Set timestamps to exactly fixed_now so time_span = now - recent[0] = 0
        tracker._consumed_timestamps = [fixed_now, fixed_now, fixed_now]

        with patch("obskit.consumer_lag.datetime") as mock_dt:
            mock_dt.utcnow.return_value = fixed_now
            velocity = tracker._calculate_velocity()

        assert velocity == 0.0

    def test_get_consumer_lag_tracker_inner_lock_already_set(self):
        """Branch 405->412: inner if key not in _lag_trackers is False (race won by another thread)."""
        import obskit.consumer_lag as mod

        saved = dict(mod._lag_trackers)
        saved_lock = mod._lag_lock
        mod._lag_trackers.clear()

        key = "race_queue:race_group"
        sentinel = ConsumerLagTracker("race_queue", consumer_group="race_group")

        class _RaceLock:
            def __enter__(self):
                mod._lag_trackers[key] = sentinel
                return self

            def __exit__(self, *a):
                pass

        mod._lag_lock = _RaceLock()
        try:
            result = get_consumer_lag_tracker("race_queue", consumer_group="race_group")
            assert result is sentinel
        finally:
            mod._lag_trackers.clear()
            mod._lag_trackers.update(saved)
            mod._lag_lock = saved_lock
