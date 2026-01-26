"""
Business Metrics Helpers.

Provides utilities for tracking business KPIs alongside technical metrics.
"""

import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from prometheus_client import Counter, Gauge, Histogram

from .logging import get_logger

logger = get_logger(__name__)

# Metrics
BUSINESS_EVENTS = Counter(
    "business_events_total", "Total business events", ["service", "event", "tenant_id", "channel"]
)

BUSINESS_REVENUE = Counter(
    "business_revenue_total", "Total revenue", ["service", "type", "currency", "tenant_id"]
)

BUSINESS_CONVERSIONS = Counter(
    "business_conversions_total", "Total conversions", ["service", "funnel", "stage", "tenant_id"]
)

BUSINESS_ENGAGEMENT = Histogram(
    "business_engagement_duration_seconds",
    "User engagement duration",
    ["service", "action", "tenant_id"],
    buckets=[1, 5, 10, 30, 60, 120, 300, 600, 1800, 3600],
)

BUSINESS_VALUE = Gauge(
    "business_value_current", "Current business value metric", ["service", "metric", "tenant_id"]
)

ACTIVE_USERS = Gauge(
    "business_active_users", "Number of active users", ["service", "period", "tenant_id"]
)

FEATURE_USAGE = Counter(
    "business_feature_usage_total", "Feature usage count", ["service", "feature", "tenant_id"]
)


@dataclass
class BusinessEvent:
    """Represents a business event."""

    event_type: str
    tenant_id: str
    channel: str | None = None
    value: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


class BusinessMetrics:
    """
    Tracks business KPIs and events.

    Example:
        metrics = BusinessMetrics("engagement")

        # Track events
        metrics.track_event("message_sent", tenant_id="123", channel="twitter")

        # Track revenue
        metrics.track_revenue("subscription", amount=99.99, currency="USD", tenant_id="123")

        # Track conversions
        metrics.track_conversion("signup_to_paid", tenant_id="123")

        # Track engagement time
        with metrics.track_engagement("dashboard_view", tenant_id="123"):
            # User activity
            pass
    """

    def __init__(self, service_name: str):
        """
        Initialize business metrics.

        Args:
            service_name: Service name for metric labels
        """
        self.service_name = service_name
        self._events: list[BusinessEvent] = []
        self._active_users: dict[str, set] = {}

    def track_event(
        self,
        event: str,
        tenant_id: str = "default",
        channel: str | None = None,
        value: float | None = None,
        count: int = 1,
        **metadata,
    ):
        """
        Track a business event.

        Args:
            event: Event type/name
            tenant_id: Tenant/customer ID
            channel: Channel (twitter, email, etc.)
            value: Optional numeric value
            count: Number of events
            **metadata: Additional event metadata
        """
        BUSINESS_EVENTS.labels(
            service=self.service_name, event=event, tenant_id=tenant_id, channel=channel or "none"
        ).inc(count)

        business_event = BusinessEvent(
            event_type=event, tenant_id=tenant_id, channel=channel, value=value, metadata=metadata
        )
        self._events.append(business_event)

        logger.info(
            "business_event_tracked",
            service=self.service_name,
            event_type=event,
            tenant_id=tenant_id,
            channel=channel,
            value=value,
            **metadata,
        )

    def track_revenue(
        self,
        revenue_type: str,
        amount: float,
        currency: str = "USD",
        tenant_id: str = "default",
        **metadata,
    ):
        """
        Track revenue.

        Args:
            revenue_type: Type of revenue (subscription, one_time, etc.)
            amount: Revenue amount
            currency: Currency code
            tenant_id: Tenant/customer ID
            **metadata: Additional metadata
        """
        BUSINESS_REVENUE.labels(
            service=self.service_name, type=revenue_type, currency=currency, tenant_id=tenant_id
        ).inc(amount)

        logger.info(
            "business_revenue",
            service=self.service_name,
            revenue_type=revenue_type,
            amount=amount,
            currency=currency,
            tenant_id=tenant_id,
            **metadata,
        )

    def track_conversion(
        self, funnel: str, tenant_id: str = "default", stage: str = "completed", **metadata
    ):
        """
        Track conversion events.

        Args:
            funnel: Conversion funnel name
            tenant_id: Tenant/customer ID
            stage: Funnel stage
            **metadata: Additional metadata
        """
        BUSINESS_CONVERSIONS.labels(
            service=self.service_name, funnel=funnel, stage=stage, tenant_id=tenant_id
        ).inc()

        logger.info(
            "business_conversion",
            service=self.service_name,
            funnel=funnel,
            stage=stage,
            tenant_id=tenant_id,
            **metadata,
        )

    @contextmanager
    def track_engagement(
        self, action: str, tenant_id: str = "default", user_id: str | None = None
    ):
        """
        Track user engagement duration.

        Args:
            action: Action being performed
            tenant_id: Tenant/customer ID
            user_id: Optional user ID for active user tracking
        """
        start_time = time.time()

        # Track active user
        if user_id:
            self.track_active_user(tenant_id, user_id)

        try:
            yield
        finally:
            duration = time.time() - start_time
            BUSINESS_ENGAGEMENT.labels(
                service=self.service_name, action=action, tenant_id=tenant_id
            ).observe(duration)

    def track_active_user(self, tenant_id: str, user_id: str, period: str = "daily"):
        """
        Track active user.

        Args:
            tenant_id: Tenant/customer ID
            user_id: User ID
            period: Time period (daily, weekly, monthly)
        """
        key = f"{tenant_id}:{period}"
        if key not in self._active_users:
            self._active_users[key] = set()

        self._active_users[key].add(user_id)

        ACTIVE_USERS.labels(service=self.service_name, period=period, tenant_id=tenant_id).set(
            len(self._active_users[key])
        )

    def track_feature_usage(
        self, feature: str, tenant_id: str = "default", count: int = 1, **metadata
    ):
        """
        Track feature usage.

        Args:
            feature: Feature name
            tenant_id: Tenant/customer ID
            count: Usage count
            **metadata: Additional metadata
        """
        FEATURE_USAGE.labels(service=self.service_name, feature=feature, tenant_id=tenant_id).inc(
            count
        )

        logger.debug(
            "feature_usage",
            service=self.service_name,
            feature=feature,
            tenant_id=tenant_id,
            count=count,
        )

    def set_value(self, metric: str, value: float, tenant_id: str = "default"):
        """
        Set a business value metric.

        Args:
            metric: Metric name
            value: Metric value
            tenant_id: Tenant/customer ID
        """
        BUSINESS_VALUE.labels(service=self.service_name, metric=metric, tenant_id=tenant_id).set(
            value
        )

    def reset_active_users(self, period: str = "daily"):
        """Reset active users for a period."""
        keys_to_reset = [k for k in self._active_users if k.endswith(f":{period}")]
        for key in keys_to_reset:
            self._active_users[key] = set()
            tenant_id = key.split(":")[0]
            ACTIVE_USERS.labels(service=self.service_name, period=period, tenant_id=tenant_id).set(
                0
            )

    def get_recent_events(
        self,
        event_type: str | None = None,
        tenant_id: str | None = None,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[BusinessEvent]:
        """
        Get recent business events.

        Args:
            event_type: Filter by event type
            tenant_id: Filter by tenant
            since: Filter events since this time
            limit: Maximum events to return
        """
        events = self._events

        if event_type:
            events = [e for e in events if e.event_type == event_type]
        if tenant_id:
            events = [e for e in events if e.tenant_id == tenant_id]
        if since:
            events = [e for e in events if e.timestamp >= since]

        return events[-limit:]


class FunnelTracker:
    """
    Tracks multi-stage conversion funnels.

    Example:
        funnel = FunnelTracker("onboarding", ["signup", "email_verified", "profile_complete", "first_action"])

        funnel.enter("user123", "signup")
        funnel.progress("user123", "email_verified")
        funnel.progress("user123", "profile_complete")
        funnel.complete("user123")
    """

    def __init__(self, funnel_name: str, stages: list[str], service_name: str = "default"):
        """
        Initialize funnel tracker.

        Args:
            funnel_name: Name of the funnel
            stages: Ordered list of funnel stages
            service_name: Service name for metrics
        """
        self.funnel_name = funnel_name
        self.stages = stages
        self.service_name = service_name
        self._user_stages: dict[str, int] = {}

        # Initialize stage counters
        for stage in stages:
            BUSINESS_CONVERSIONS.labels(
                service=service_name, funnel=funnel_name, stage=stage, tenant_id="all"
            )

    def enter(self, user_id: str, stage: str | None = None, tenant_id: str = "default"):
        """User enters the funnel."""
        stage = stage or self.stages[0]
        stage_index = self.stages.index(stage)
        self._user_stages[user_id] = stage_index

        BUSINESS_CONVERSIONS.labels(
            service=self.service_name, funnel=self.funnel_name, stage=stage, tenant_id=tenant_id
        ).inc()

        logger.info(
            "funnel_enter",
            funnel=self.funnel_name,
            user_id=user_id,
            stage=stage,
            tenant_id=tenant_id,
        )

    def progress(self, user_id: str, stage: str, tenant_id: str = "default"):
        """User progresses to a stage."""
        if user_id not in self._user_stages:
            self.enter(user_id, self.stages[0], tenant_id)

        stage_index = self.stages.index(stage)
        current_stage = self._user_stages.get(user_id, 0)

        if stage_index > current_stage:
            self._user_stages[user_id] = stage_index

            BUSINESS_CONVERSIONS.labels(
                service=self.service_name, funnel=self.funnel_name, stage=stage, tenant_id=tenant_id
            ).inc()

            logger.info(
                "funnel_progress",
                funnel=self.funnel_name,
                user_id=user_id,
                stage=stage,
                tenant_id=tenant_id,
            )

    def complete(self, user_id: str, tenant_id: str = "default"):
        """User completes the funnel."""
        if user_id in self._user_stages:
            self.progress(user_id, self.stages[-1], tenant_id)

            BUSINESS_CONVERSIONS.labels(
                service=self.service_name,
                funnel=self.funnel_name,
                stage="completed",
                tenant_id=tenant_id,
            ).inc()

            logger.info(
                "funnel_complete", funnel=self.funnel_name, user_id=user_id, tenant_id=tenant_id
            )

    def drop(self, user_id: str, reason: str | None = None, tenant_id: str = "default"):
        """User drops from the funnel."""
        if user_id in self._user_stages:
            current_stage = self.stages[self._user_stages[user_id]]
            del self._user_stages[user_id]

            BUSINESS_CONVERSIONS.labels(
                service=self.service_name,
                funnel=self.funnel_name,
                stage="dropped",
                tenant_id=tenant_id,
            ).inc()

            logger.info(
                "funnel_drop",
                funnel=self.funnel_name,
                user_id=user_id,
                dropped_at=current_stage,
                reason=reason,
                tenant_id=tenant_id,
            )

    def get_conversion_rates(self) -> dict[str, float]:
        """Get conversion rates between stages."""
        stage_counts = dict.fromkeys(self.stages, 0)

        for _user_id, stage_index in self._user_stages.items():
            for i in range(stage_index + 1):
                stage_counts[self.stages[i]] += 1

        rates = {}
        for i in range(1, len(self.stages)):
            prev_stage = self.stages[i - 1]
            curr_stage = self.stages[i]
            if stage_counts[prev_stage] > 0:
                rates[f"{prev_stage}_to_{curr_stage}"] = (
                    stage_counts[curr_stage] / stage_counts[prev_stage]
                )

        return rates


__all__ = [
    "BusinessMetrics",
    "BusinessEvent",
    "FunnelTracker",
    "BUSINESS_EVENTS",
    "BUSINESS_REVENUE",
    "BUSINESS_CONVERSIONS",
    "BUSINESS_ENGAGEMENT",
    "BUSINESS_VALUE",
    "ACTIVE_USERS",
    "FEATURE_USAGE",
]
