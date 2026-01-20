"""
Tenant Quota Tracking
=====================

Track usage against tenant limits.

Features:
- Usage tracking per tenant
- Quota limit enforcement
- Usage reporting
- Overage alerting

Example:
    from obskit.quota import QuotaTracker

    quota = QuotaTracker("api_requests")
    quota.set_limit("tenant-123", requests_per_hour=10000)

    if quota.check_and_increment("tenant-123"):
        process_request()
    else:
        return quota_exceeded()
"""

import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from prometheus_client import Counter, Gauge

from obskit.logging import get_logger

logger = get_logger(__name__)


# =============================================================================
# Prometheus Metrics
# =============================================================================

QUOTA_USAGE = Gauge("quota_usage", "Current quota usage", ["quota_name", "tenant_id", "resource"])

QUOTA_LIMIT = Gauge("quota_limit", "Quota limit", ["quota_name", "tenant_id", "resource"])

QUOTA_USAGE_PERCENT = Gauge(
    "quota_usage_percent", "Quota usage percentage", ["quota_name", "tenant_id", "resource"]
)

QUOTA_EXCEEDED_TOTAL = Counter(
    "quota_exceeded_total", "Times quota was exceeded", ["quota_name", "tenant_id", "resource"]
)

QUOTA_REQUESTS_TOTAL = Counter(
    "quota_requests_total", "Total quota check requests", ["quota_name", "tenant_id", "status"]
)


# =============================================================================
# Enums and Data Classes
# =============================================================================


class QuotaPeriod(Enum):
    """Quota period types."""

    MINUTE = 60
    HOUR = 3600
    DAY = 86400
    MONTH = 2592000  # 30 days


@dataclass
class QuotaLimit:
    """Definition of a quota limit."""

    resource: str
    limit: int
    period: QuotaPeriod
    burst_limit: int | None = None  # Allow short bursts
    soft_limit_percent: float = 80.0  # Warning threshold


@dataclass
class TenantUsage:
    """Usage tracking for a tenant."""

    tenant_id: str
    resource: str
    current_usage: int = 0
    limit: int = 0
    period_start: datetime = field(default_factory=datetime.utcnow)
    period: QuotaPeriod = QuotaPeriod.HOUR
    exceeded_count: int = 0
    last_exceeded: datetime | None = None

    @property
    def usage_percent(self) -> float:
        if self.limit == 0:
            return 0.0
        return (self.current_usage / self.limit) * 100

    @property
    def remaining(self) -> int:
        return max(0, self.limit - self.current_usage)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "resource": self.resource,
            "current_usage": self.current_usage,
            "limit": self.limit,
            "usage_percent": self.usage_percent,
            "remaining": self.remaining,
            "period": self.period.name,
            "period_start": self.period_start.isoformat(),
            "exceeded_count": self.exceeded_count,
            "last_exceeded": self.last_exceeded.isoformat() if self.last_exceeded else None,
        }


@dataclass
class QuotaReport:
    """Quota usage report."""

    quota_name: str
    tenant_id: str
    usages: list[TenantUsage]
    total_exceeded: int
    is_over_quota: bool
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "quota_name": self.quota_name,
            "tenant_id": self.tenant_id,
            "usages": [u.to_dict() for u in self.usages],
            "total_exceeded": self.total_exceeded,
            "is_over_quota": self.is_over_quota,
            "timestamp": self.timestamp.isoformat(),
        }


# =============================================================================
# Quota Tracker
# =============================================================================


class QuotaTracker:
    """
    Track quota usage per tenant.

    Parameters
    ----------
    quota_name : str
        Name of the quota tracker
    default_limit : int
        Default limit for new tenants
    default_period : QuotaPeriod
        Default period for quota
    on_exceeded : callable, optional
        Callback when quota is exceeded
    on_warning : callable, optional
        Callback when soft limit is reached
    """

    def __init__(
        self,
        quota_name: str,
        default_limit: int = 10000,
        default_period: QuotaPeriod = QuotaPeriod.HOUR,
        on_exceeded: Callable[[str, str, TenantUsage], None] | None = None,
        on_warning: Callable[[str, str, TenantUsage], None] | None = None,
    ):
        self.quota_name = quota_name
        self.default_limit = default_limit
        self.default_period = default_period
        self.on_exceeded = on_exceeded
        self.on_warning = on_warning

        self._limits: dict[str, dict[str, QuotaLimit]] = {}  # tenant_id -> resource -> limit
        self._usage: dict[str, dict[str, TenantUsage]] = {}  # tenant_id -> resource -> usage
        self._lock = threading.Lock()
        self._warned: dict[str, datetime] = {}  # Track warning cooldown

    def set_limit(
        self,
        tenant_id: str,
        resource: str = "requests",
        limit: int | None = None,
        period: QuotaPeriod | None = None,
        burst_limit: int | None = None,
        soft_limit_percent: float = 80.0,
    ):
        """
        Set quota limit for a tenant.

        Parameters
        ----------
        tenant_id : str
            Tenant identifier
        resource : str
            Resource type (e.g., "requests", "storage", "api_calls")
        limit : int
            Usage limit
        period : QuotaPeriod
            Quota period
        burst_limit : int, optional
            Allow bursts up to this limit
        soft_limit_percent : float
            Percentage for soft limit warning
        """
        quota_limit = QuotaLimit(
            resource=resource,
            limit=limit or self.default_limit,
            period=period or self.default_period,
            burst_limit=burst_limit,
            soft_limit_percent=soft_limit_percent,
        )

        with self._lock:
            if tenant_id not in self._limits:
                self._limits[tenant_id] = {}
            self._limits[tenant_id][resource] = quota_limit

        QUOTA_LIMIT.labels(quota_name=self.quota_name, tenant_id=tenant_id, resource=resource).set(
            quota_limit.limit
        )

        logger.info(
            "quota_limit_set",
            quota_name=self.quota_name,
            tenant_id=tenant_id,
            resource=resource,
            limit=quota_limit.limit,
            period=quota_limit.period.name,
        )

    def check_and_increment(
        self,
        tenant_id: str,
        resource: str = "requests",
        amount: int = 1,
        allow_burst: bool = True,
    ) -> bool:
        """
        Check quota and increment if allowed.

        Parameters
        ----------
        tenant_id : str
            Tenant identifier
        resource : str
            Resource type
        amount : int
            Amount to increment
        allow_burst : bool
            Allow burst if configured

        Returns
        -------
        bool
            Whether the request is allowed
        """
        with self._lock:
            usage = self._get_or_create_usage(tenant_id, resource)
            limit_config = self._limits.get(tenant_id, {}).get(resource)

            # Reset if period expired
            self._maybe_reset_period(usage)

            # Get effective limit
            limit = usage.limit
            if allow_burst and limit_config and limit_config.burst_limit:
                limit = limit_config.burst_limit

            # Check if would exceed
            new_usage = usage.current_usage + amount

            if new_usage > limit:
                usage.exceeded_count += 1
                usage.last_exceeded = datetime.utcnow()

                QUOTA_EXCEEDED_TOTAL.labels(
                    quota_name=self.quota_name, tenant_id=tenant_id, resource=resource
                ).inc()

                QUOTA_REQUESTS_TOTAL.labels(
                    quota_name=self.quota_name, tenant_id=tenant_id, status="exceeded"
                ).inc()

                logger.warning(
                    "quota_exceeded",
                    quota_name=self.quota_name,
                    tenant_id=tenant_id,
                    resource=resource,
                    current_usage=usage.current_usage,
                    limit=limit,
                )

                if self.on_exceeded:
                    self.on_exceeded(tenant_id, resource, usage)

                return False

            # Increment usage
            usage.current_usage = new_usage

            self._update_metrics(tenant_id, resource, usage)

            QUOTA_REQUESTS_TOTAL.labels(
                quota_name=self.quota_name, tenant_id=tenant_id, status="allowed"
            ).inc()

            # Check soft limit for warning
            if limit_config:
                soft_limit = limit * (limit_config.soft_limit_percent / 100)
                if usage.current_usage >= soft_limit:
                    self._maybe_warn(tenant_id, resource, usage)

            return True

    def get_usage(
        self,
        tenant_id: str,
        resource: str = "requests",
    ) -> TenantUsage | None:
        """Get current usage for a tenant."""
        with self._lock:
            if tenant_id in self._usage and resource in self._usage[tenant_id]:
                usage = self._usage[tenant_id][resource]
                self._maybe_reset_period(usage)
                return usage
            return None

    def get_remaining(
        self,
        tenant_id: str,
        resource: str = "requests",
    ) -> int:
        """Get remaining quota for a tenant."""
        usage = self.get_usage(tenant_id, resource)
        if usage:
            return usage.remaining
        return self.default_limit

    def is_over_quota(
        self,
        tenant_id: str,
        resource: str = "requests",
    ) -> bool:
        """Check if tenant is over quota."""
        usage = self.get_usage(tenant_id, resource)
        if usage:
            return usage.current_usage >= usage.limit
        return False

    def get_report(self, tenant_id: str) -> QuotaReport:
        """Get full quota report for a tenant."""
        with self._lock:
            usages = []
            total_exceeded = 0
            is_over = False

            if tenant_id in self._usage:
                for _resource, usage in self._usage[tenant_id].items():
                    self._maybe_reset_period(usage)
                    usages.append(usage)
                    total_exceeded += usage.exceeded_count
                    if usage.current_usage >= usage.limit:
                        is_over = True

            return QuotaReport(
                quota_name=self.quota_name,
                tenant_id=tenant_id,
                usages=usages,
                total_exceeded=total_exceeded,
                is_over_quota=is_over,
            )

    def reset_usage(
        self,
        tenant_id: str,
        resource: str | None = None,
    ):
        """Reset usage for a tenant."""
        with self._lock:
            if tenant_id in self._usage:
                if resource:
                    if resource in self._usage[tenant_id]:
                        self._usage[tenant_id][resource].current_usage = 0
                        self._usage[tenant_id][resource].period_start = datetime.utcnow()
                else:
                    for r in self._usage[tenant_id]:
                        self._usage[tenant_id][r].current_usage = 0
                        self._usage[tenant_id][r].period_start = datetime.utcnow()

    def _get_or_create_usage(
        self,
        tenant_id: str,
        resource: str,
    ) -> TenantUsage:
        """Get or create usage tracking for tenant."""
        if tenant_id not in self._usage:
            self._usage[tenant_id] = {}

        if resource not in self._usage[tenant_id]:
            limit_config = self._limits.get(tenant_id, {}).get(resource)
            limit = limit_config.limit if limit_config else self.default_limit
            period = limit_config.period if limit_config else self.default_period

            self._usage[tenant_id][resource] = TenantUsage(
                tenant_id=tenant_id,
                resource=resource,
                limit=limit,
                period=period,
            )

        return self._usage[tenant_id][resource]

    def _maybe_reset_period(self, usage: TenantUsage):
        """Reset usage if period has expired."""
        now = datetime.utcnow()
        period_duration = timedelta(seconds=usage.period.value)

        if now - usage.period_start >= period_duration:
            usage.current_usage = 0
            usage.period_start = now

    def _update_metrics(
        self,
        tenant_id: str,
        resource: str,
        usage: TenantUsage,
    ):
        """Update Prometheus metrics."""
        QUOTA_USAGE.labels(quota_name=self.quota_name, tenant_id=tenant_id, resource=resource).set(
            usage.current_usage
        )

        QUOTA_USAGE_PERCENT.labels(
            quota_name=self.quota_name, tenant_id=tenant_id, resource=resource
        ).set(usage.usage_percent)

    def _maybe_warn(
        self,
        tenant_id: str,
        resource: str,
        usage: TenantUsage,
    ):
        """Maybe send soft limit warning."""
        warn_key = f"{tenant_id}:{resource}"
        now = datetime.utcnow()

        # Cooldown of 5 minutes between warnings
        if warn_key in self._warned:
            if now - self._warned[warn_key] < timedelta(minutes=5):
                return

        self._warned[warn_key] = now

        logger.warning(
            "quota_soft_limit_reached",
            quota_name=self.quota_name,
            tenant_id=tenant_id,
            resource=resource,
            usage_percent=usage.usage_percent,
        )

        if self.on_warning:
            self.on_warning(tenant_id, resource, usage)


# =============================================================================
# Factory
# =============================================================================

_trackers: dict[str, QuotaTracker] = {}
_trackers_lock = threading.Lock()


def get_quota_tracker(quota_name: str, **kwargs) -> QuotaTracker:
    """Get or create a quota tracker."""
    if quota_name not in _trackers:
        with _trackers_lock:
            if quota_name not in _trackers:
                _trackers[quota_name] = QuotaTracker(quota_name, **kwargs)

    return _trackers[quota_name]
