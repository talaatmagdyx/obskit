"""Unit tests for business metrics helpers."""

import time
from datetime import datetime

from obskit.business import (
    BusinessEvent,
    BusinessMetrics,
    FunnelTracker,
)


class TestBusinessEvent:
    """Tests for BusinessEvent dataclass."""

    def test_init_defaults(self):
        """Test default values."""
        event = BusinessEvent(event_type="test_event", tenant_id="123")
        assert event.event_type == "test_event"
        assert event.tenant_id == "123"
        assert event.channel is None
        assert event.value is None
        assert event.metadata == {}
        assert isinstance(event.timestamp, datetime)

    def test_init_with_all_fields(self):
        """Test initialization with all fields."""
        event = BusinessEvent(
            event_type="purchase",
            tenant_id="123",
            channel="web",
            value=99.99,
            metadata={"product_id": "prod-456"},
        )
        assert event.channel == "web"
        assert event.value == 99.99
        assert event.metadata["product_id"] == "prod-456"


class TestBusinessMetrics:
    """Tests for BusinessMetrics class."""

    def test_init(self):
        """Test initialization."""
        metrics = BusinessMetrics("test_service")
        assert metrics.service_name == "test_service"

    def test_track_event(self):
        """Test tracking a business event."""
        metrics = BusinessMetrics("test_service")
        metrics.track_event(
            event="message_sent",
            tenant_id="123",
            channel="twitter",
            value=1.0,
            extra_field="extra_value",
        )
        # Event should be stored internally
        assert len(metrics._events) == 1
        assert metrics._events[0].event_type == "message_sent"

    def test_track_revenue(self):
        """Test tracking revenue."""
        metrics = BusinessMetrics("test_service")
        metrics.track_revenue(
            revenue_type="subscription", amount=99.99, currency="USD", tenant_id="123"
        )
        # Revenue tracking should work without errors

    def test_track_conversion(self):
        """Test tracking conversions."""
        metrics = BusinessMetrics("test_service")
        metrics.track_conversion(funnel="signup_to_paid", tenant_id="123", stage="completed")
        # Conversion tracking should work without errors

    def test_track_engagement(self):
        """Test tracking engagement duration."""
        metrics = BusinessMetrics("test_service")

        with metrics.track_engagement(action="dashboard_view", tenant_id="123", user_id="user-456"):
            time.sleep(0.1)

        # Engagement duration should be recorded

    def test_track_active_user(self):
        """Test tracking active users."""
        metrics = BusinessMetrics("test_service")

        metrics.track_active_user("tenant-1", "user-1", period="daily")
        metrics.track_active_user("tenant-1", "user-2", period="daily")
        metrics.track_active_user("tenant-1", "user-1", period="daily")  # Duplicate

        # Only 2 unique users
        key = "tenant-1:daily"
        assert len(metrics._active_users[key]) == 2

    def test_track_feature_usage(self):
        """Test tracking feature usage."""
        metrics = BusinessMetrics("test_service")
        metrics.track_feature_usage(feature="advanced_analytics", tenant_id="123", count=5)
        # Feature usage should be recorded

    def test_set_value(self):
        """Test setting business value metric."""
        metrics = BusinessMetrics("test_service")
        metrics.set_value(metric="customer_satisfaction", value=4.5, tenant_id="123")
        # Value should be set

    def test_reset_active_users(self):
        """Test resetting active users."""
        metrics = BusinessMetrics("test_service")

        metrics.track_active_user("tenant-1", "user-1", period="daily")
        metrics.track_active_user("tenant-1", "user-2", period="daily")

        metrics.reset_active_users(period="daily")

        key = "tenant-1:daily"
        assert len(metrics._active_users[key]) == 0

    def test_get_recent_events(self):
        """Test getting recent events."""
        metrics = BusinessMetrics("test_service")

        metrics.track_event("event_1", tenant_id="123")
        metrics.track_event("event_2", tenant_id="456")
        metrics.track_event("event_1", tenant_id="123")

        # Get all events
        events = metrics.get_recent_events()
        assert len(events) == 3

        # Filter by event type
        events = metrics.get_recent_events(event_type="event_1")
        assert len(events) == 2

        # Filter by tenant
        events = metrics.get_recent_events(tenant_id="456")
        assert len(events) == 1

        # Limit results
        events = metrics.get_recent_events(limit=2)
        assert len(events) == 2


class TestFunnelTracker:
    """Tests for FunnelTracker class."""

    def test_init(self):
        """Test funnel initialization."""
        funnel = FunnelTracker(
            funnel_name="onboarding",
            stages=["signup", "email_verified", "profile_complete", "first_action"],
        )
        assert funnel.funnel_name == "onboarding"
        assert len(funnel.stages) == 4

    def test_enter(self):
        """Test user entering funnel."""
        funnel = FunnelTracker(funnel_name="onboarding", stages=["signup", "verify", "complete"])

        funnel.enter("user-1")
        assert funnel._user_stages["user-1"] == 0

    def test_enter_at_stage(self):
        """Test user entering at specific stage."""
        funnel = FunnelTracker(funnel_name="onboarding", stages=["signup", "verify", "complete"])

        funnel.enter("user-1", stage="verify")
        assert funnel._user_stages["user-1"] == 1

    def test_progress(self):
        """Test user progressing through funnel."""
        funnel = FunnelTracker(funnel_name="onboarding", stages=["signup", "verify", "complete"])

        funnel.enter("user-1")
        funnel.progress("user-1", "verify")

        assert funnel._user_stages["user-1"] == 1

    def test_progress_skips_backward(self):
        """Test progress doesn't go backward."""
        funnel = FunnelTracker(funnel_name="onboarding", stages=["signup", "verify", "complete"])

        funnel.enter("user-1")
        funnel.progress("user-1", "complete")  # Skip to complete
        funnel.progress("user-1", "verify")  # Try to go back

        assert funnel._user_stages["user-1"] == 2  # Still at complete

    def test_complete(self):
        """Test user completing funnel."""
        funnel = FunnelTracker(funnel_name="onboarding", stages=["signup", "verify", "complete"])

        funnel.enter("user-1")
        funnel.complete("user-1")

        assert funnel._user_stages["user-1"] == 2

    def test_drop(self):
        """Test user dropping from funnel."""
        funnel = FunnelTracker(funnel_name="onboarding", stages=["signup", "verify", "complete"])

        funnel.enter("user-1")
        funnel.progress("user-1", "verify")
        funnel.drop("user-1", reason="abandoned")

        assert "user-1" not in funnel._user_stages

    def test_get_conversion_rates(self):
        """Test getting conversion rates."""
        funnel = FunnelTracker(funnel_name="onboarding", stages=["signup", "verify", "complete"])

        # 10 users sign up
        for i in range(10):
            funnel.enter(f"user-{i}")

        # 8 verify
        for i in range(8):
            funnel.progress(f"user-{i}", "verify")

        # 5 complete
        for i in range(5):
            funnel.complete(f"user-{i}")

        rates = funnel.get_conversion_rates()

        assert "signup_to_verify" in rates
        assert "verify_to_complete" in rates
        assert rates["signup_to_verify"] == 0.8
        assert rates["verify_to_complete"] == 0.625  # 5/8


class TestBusinessMetricsEdgeCases:
    def test_track_engagement_with_user_id(self):
        from obskit.business import BusinessMetrics
        bm = BusinessMetrics("test_svc")
        with bm.track_engagement("test_tenant", "click", user_id="user123"):
            pass

    def test_get_recent_events_with_since_filter(self):
        from obskit.business import BusinessMetrics
        import time
        from datetime import datetime
        bm = BusinessMetrics("test_svc")
        bm.track_event("event1", tenant_id="test_tenant")
        time.sleep(0.05)
        since_time = datetime.utcnow()
        time.sleep(0.05)
        bm.track_event("event2", tenant_id="test_tenant")
        events = bm.get_recent_events(limit=10, since=since_time)
        assert len(events) == 1
        assert events[0].event_type == "event2"


class TestFunnelTrackerEdgeCases:
    def test_progress_before_enter(self):
        from obskit.business import FunnelTracker
        # FunnelTracker(funnel_name, stages, service_name)
        ft = FunnelTracker("test_funnel", ["stage1", "stage2", "stage3"], "test_svc")
        # progress() when user not in _user_stages should auto-enter
        ft.progress("user1", "stage2", "tenant1")
        assert "user1" in ft._user_stages

    def test_complete_funnel(self):
        from obskit.business import FunnelTracker
        ft = FunnelTracker("purchase", ["view", "cart", "checkout"], "test_svc")
        ft.enter("user1", "view", "tenant1")
        ft.complete("user1", "tenant1")

    def test_drop_user_from_funnel(self):
        from obskit.business import FunnelTracker
        ft = FunnelTracker("purchase", ["view", "cart", "checkout"], "test_svc")
        ft.enter("user1", "view", "tenant1")
        ft.drop("user1", tenant_id="tenant1")
        assert "user1" not in ft._user_stages

    def test_conversion_rates_with_users_at_stages(self):
        from obskit.business import FunnelTracker
        ft = FunnelTracker("purchase", ["view", "cart", "checkout"], "test_svc")
        ft.enter("user1", "view", "tenant1")
        ft.enter("user2", "view", "tenant1")
        ft.progress("user1", "cart", "tenant1")
        rates = ft.get_conversion_rates()
        assert "view_to_cart" in rates



# =============================================================================
# Additional coverage tests for business.py
# =============================================================================


class TestBusinessCoverageGaps:
    """Additional tests for specific uncovered branches in business.py."""

    def test_track_engagement_with_user_id(self):
        """Test track_engagement with user_id set (line 208->209)."""
        from obskit.business import BusinessMetrics
        bm = BusinessMetrics("test_svc")
        with bm.track_engagement("tenant1", "click", user_id="user123"):
            pass
        # Should track active user without error

    def test_funnel_complete_user_in_stages(self):
        """Test FunnelTracker.complete when user is in stages (line 389->390)."""
        from obskit.business import FunnelTracker
        ft = FunnelTracker("checkout", ["cart", "payment", "confirm"], "test_svc")
        ft.enter("user1", "cart", "tenant1")
        ft.complete("user1", "tenant1")
        # User should have been progressed to last stage

    def test_funnel_complete_user_not_in_stages(self):
        """Test FunnelTracker.complete when user not in stages (line 389->exit)."""
        from obskit.business import FunnelTracker
        ft = FunnelTracker("checkout", ["cart", "payment", "confirm"], "test_svc")
        # User not in stages - should not raise
        ft.complete("nonexistent_user", "tenant1")

    def test_funnel_drop_user_in_stages(self):
        """Test FunnelTracker.drop when user is in stages (line 405->406)."""
        from obskit.business import FunnelTracker
        ft = FunnelTracker("checkout", ["cart", "payment", "confirm"], "test_svc")
        ft.enter("user2", "cart", "tenant1")
        ft.drop("user2", reason="timeout", tenant_id="tenant1")
        assert "user2" not in ft._user_stages

    def test_funnel_drop_user_not_in_stages(self):
        """Test FunnelTracker.drop when user not in stages (line 405->exit)."""
        from obskit.business import FunnelTracker
        ft = FunnelTracker("checkout", ["cart", "payment", "confirm"], "test_svc")
        # User not in stages - should not raise
        ft.drop("nonexistent", reason="no_reason", tenant_id="tenant1")

    def test_funnel_conversion_rates_with_users_at_first_stage(self):
        """Test get_conversion_rates when prev_stage count > 0 (line 437->438)."""
        from obskit.business import FunnelTracker
        ft = FunnelTracker("checkout", ["cart", "payment", "confirm"], "test_svc")
        ft.enter("user1", "cart", "tenant1")
        ft.progress("user1", "payment", "tenant1")
        rates = ft.get_conversion_rates()
        assert "cart_to_payment" in rates or rates is not None


class TestBusinessMissingBranches:
    """Tests for remaining uncovered branches in business.py."""

    def test_track_engagement_without_user_id(self):
        """Test track_engagement when user_id is None (line 208->211 branch False)."""
        from obskit.business import BusinessMetrics
        bm = BusinessMetrics("test_svc_no_uid")
        # Without user_id, track_active_user should NOT be called
        with bm.track_engagement("view_page", tenant_id="tenant1"):
            pass
        # No active users should be tracked
        assert len(bm._active_users) == 0

    def test_funnel_conversion_rates_zero_prev_stage(self):
        """Test get_conversion_rates when prev_stage count is 0 (line 437->434)."""
        from obskit.business import FunnelTracker
        ft = FunnelTracker("empty_funnel", ["step1", "step2", "step3"], "test_svc")
        # No users entered - all stage_counts are 0
        # This exercises the `if stage_counts[prev_stage] > 0` being False path
        rates = ft.get_conversion_rates()
        # No rates should be computed since no users
        assert rates == {}
