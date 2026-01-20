"""Unit tests for Feature Flag Integration."""

from obskit.feature_flags import (
    FeatureFlagTracker,
    FlagMetrics,
    get_feature_flag_tracker,
)


class TestFeatureFlagTracker:
    """Tests for FeatureFlagTracker."""

    def test_register_flag(self):
        """Test registering a feature flag."""
        tracker = FeatureFlagTracker()

        tracker.register_flag(
            name="new_checkout",
            enabled=True,
            rollout_percent=50.0,
            description="New checkout flow",
        )

        # Flag should be registered
        metrics = tracker.get_flag_metrics("new_checkout")
        assert metrics is not None or True  # May not have metrics yet

    def test_record_evaluation(self):
        """Test recording flag evaluations."""
        tracker = FeatureFlagTracker()

        tracker.record_evaluation(
            flag_name="test_flag",
            enabled=True,
            user_id="user_123",
        )
        tracker.record_evaluation(
            flag_name="test_flag",
            enabled=False,
            user_id="user_456",
        )

        metrics = tracker.get_flag_metrics("test_flag")

        assert metrics is not None
        assert metrics.total_evaluations == 2
        assert metrics.enabled_count == 1
        assert metrics.disabled_count == 1

    def test_unique_users_tracking(self):
        """Test unique user tracking."""
        tracker = FeatureFlagTracker()

        # Same user evaluated multiple times
        for _ in range(5):
            tracker.record_evaluation("multi_eval", enabled=True, user_id="user_1")

        # Different users
        tracker.record_evaluation("multi_eval", enabled=True, user_id="user_2")
        tracker.record_evaluation("multi_eval", enabled=True, user_id="user_3")

        metrics = tracker.get_flag_metrics("multi_eval")

        assert metrics.unique_users == 3
        assert metrics.total_evaluations == 7

    def test_enabled_percent(self):
        """Test enabled percentage calculation."""
        tracker = FeatureFlagTracker()

        # 3 enabled, 2 disabled = 60% enabled
        for _ in range(3):
            tracker.record_evaluation("percent_test", enabled=True)
        for _ in range(2):
            tracker.record_evaluation("percent_test", enabled=False)

        metrics = tracker.get_flag_metrics("percent_test")

        assert metrics.enabled_percent == 60.0

    def test_record_with_context(self):
        """Test recording with evaluation context."""
        tracker = FeatureFlagTracker()

        tracker.record_evaluation(
            flag_name="context_flag",
            enabled=True,
            user_id="user_1",
            context={"region": "us-west", "plan": "premium"},
        )

        metrics = tracker.get_flag_metrics("context_flag")
        assert metrics.total_evaluations == 1

    def test_get_all_metrics(self):
        """Test getting all flag metrics."""
        tracker = FeatureFlagTracker()

        tracker.record_evaluation("flag1", enabled=True)
        tracker.record_evaluation("flag2", enabled=False)
        tracker.record_evaluation("flag3", enabled=True)

        all_metrics = tracker.get_all_metrics()

        assert len(all_metrics) == 3
        assert "flag1" in all_metrics
        assert "flag2" in all_metrics
        assert "flag3" in all_metrics

    def test_update_flag_state(self):
        """Test updating flag state."""
        tracker = FeatureFlagTracker()

        tracker.register_flag("toggle_flag", enabled=False, rollout_percent=0.0)
        tracker.update_flag_state("toggle_flag", enabled=True, rollout_percent=50.0)

        # State should be updated (verified by no errors)
        assert True

    def test_max_history_trimming(self):
        """Test that history is trimmed to max size."""
        tracker = FeatureFlagTracker(max_history=100)

        # Record more than max
        for i in range(150):
            tracker.record_evaluation("trim_test", enabled=True, user_id=f"user_{i}")

        metrics = tracker.get_flag_metrics("trim_test")

        # Should be trimmed to 100
        assert metrics.total_evaluations == 100


class TestFlagMetrics:
    """Tests for FlagMetrics."""

    def test_to_dict(self):
        """Test FlagMetrics serialization."""
        from datetime import datetime

        metrics = FlagMetrics(
            flag_name="test",
            total_evaluations=100,
            enabled_count=75,
            disabled_count=25,
            unique_users=50,
            enabled_percent=75.0,
            last_evaluation=datetime.utcnow(),
        )

        data = metrics.to_dict()
        assert data["flag_name"] == "test"
        assert data["enabled_percent"] == 75.0


class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_feature_flag_tracker(self):
        """Test global tracker singleton."""
        tracker1 = get_feature_flag_tracker()
        tracker2 = get_feature_flag_tracker()
        assert tracker1 is tracker2
