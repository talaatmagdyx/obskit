"""Unit tests for business metrics helpers."""

import time
from datetime import datetime
import pytest

from obskit.business import (
    BusinessMetrics,
    BusinessEvent,
    FunnelTracker,
    BUSINESS_EVENTS,
    BUSINESS_REVENUE,
    BUSINESS_CONVERSIONS,
    BUSINESS_ENGAGEMENT,
    BUSINESS_VALUE,
    ACTIVE_USERS,
    FEATURE_USAGE,
)


class TestBusinessEvent:
    """Tests for BusinessEvent dataclass."""
    
    def test_init_defaults(self):
        """Test default values."""
        event = BusinessEvent(
            event_type="test_event",
            tenant_id="123"
        )
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
            metadata={"product_id": "prod-456"}
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
            extra_field="extra_value"
        )
        # Event should be stored internally
        assert len(metrics._events) == 1
        assert metrics._events[0].event_type == "message_sent"
    
    def test_track_revenue(self):
        """Test tracking revenue."""
        metrics = BusinessMetrics("test_service")
        metrics.track_revenue(
            revenue_type="subscription",
            amount=99.99,
            currency="USD",
            tenant_id="123"
        )
        # Revenue tracking should work without errors
    
    def test_track_conversion(self):
        """Test tracking conversions."""
        metrics = BusinessMetrics("test_service")
        metrics.track_conversion(
            funnel="signup_to_paid",
            tenant_id="123",
            stage="completed"
        )
        # Conversion tracking should work without errors
    
    def test_track_engagement(self):
        """Test tracking engagement duration."""
        metrics = BusinessMetrics("test_service")
        
        with metrics.track_engagement(
            action="dashboard_view",
            tenant_id="123",
            user_id="user-456"
        ):
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
        metrics.track_feature_usage(
            feature="advanced_analytics",
            tenant_id="123",
            count=5
        )
        # Feature usage should be recorded
    
    def test_set_value(self):
        """Test setting business value metric."""
        metrics = BusinessMetrics("test_service")
        metrics.set_value(
            metric="customer_satisfaction",
            value=4.5,
            tenant_id="123"
        )
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
            stages=["signup", "email_verified", "profile_complete", "first_action"]
        )
        assert funnel.funnel_name == "onboarding"
        assert len(funnel.stages) == 4
    
    def test_enter(self):
        """Test user entering funnel."""
        funnel = FunnelTracker(
            funnel_name="onboarding",
            stages=["signup", "verify", "complete"]
        )
        
        funnel.enter("user-1")
        assert funnel._user_stages["user-1"] == 0
    
    def test_enter_at_stage(self):
        """Test user entering at specific stage."""
        funnel = FunnelTracker(
            funnel_name="onboarding",
            stages=["signup", "verify", "complete"]
        )
        
        funnel.enter("user-1", stage="verify")
        assert funnel._user_stages["user-1"] == 1
    
    def test_progress(self):
        """Test user progressing through funnel."""
        funnel = FunnelTracker(
            funnel_name="onboarding",
            stages=["signup", "verify", "complete"]
        )
        
        funnel.enter("user-1")
        funnel.progress("user-1", "verify")
        
        assert funnel._user_stages["user-1"] == 1
    
    def test_progress_skips_backward(self):
        """Test progress doesn't go backward."""
        funnel = FunnelTracker(
            funnel_name="onboarding",
            stages=["signup", "verify", "complete"]
        )
        
        funnel.enter("user-1")
        funnel.progress("user-1", "complete")  # Skip to complete
        funnel.progress("user-1", "verify")  # Try to go back
        
        assert funnel._user_stages["user-1"] == 2  # Still at complete
    
    def test_complete(self):
        """Test user completing funnel."""
        funnel = FunnelTracker(
            funnel_name="onboarding",
            stages=["signup", "verify", "complete"]
        )
        
        funnel.enter("user-1")
        funnel.complete("user-1")
        
        assert funnel._user_stages["user-1"] == 2
    
    def test_drop(self):
        """Test user dropping from funnel."""
        funnel = FunnelTracker(
            funnel_name="onboarding",
            stages=["signup", "verify", "complete"]
        )
        
        funnel.enter("user-1")
        funnel.progress("user-1", "verify")
        funnel.drop("user-1", reason="abandoned")
        
        assert "user-1" not in funnel._user_stages
    
    def test_get_conversion_rates(self):
        """Test getting conversion rates."""
        funnel = FunnelTracker(
            funnel_name="onboarding",
            stages=["signup", "verify", "complete"]
        )
        
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
