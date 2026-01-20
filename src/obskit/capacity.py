"""
Capacity Planner
================

Plan capacity needs based on growth trends.

Features:
- Growth projection
- Resource modeling
- Cost estimation
- Capacity alerts

Example:
    from obskit.capacity import CapacityPlanner

    planner = CapacityPlanner()

    # Define resources
    planner.add_resource("database_storage", current_gb=500, max_gb=1000)
    planner.add_resource("memory", current_percent=60, max_percent=85)

    # Get projections
    plan = planner.project(months_ahead=6)
    print(f"Need to add capacity by: {plan.action_required_by}")
"""

import math
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from prometheus_client import Gauge

from obskit.logging import get_logger

logger = get_logger(__name__)


# =============================================================================
# Prometheus Metrics
# =============================================================================

CAPACITY_CURRENT = Gauge("capacity_current_usage", "Current capacity usage", ["resource", "unit"])

CAPACITY_MAX = Gauge("capacity_max", "Maximum capacity", ["resource", "unit"])

CAPACITY_PERCENT = Gauge("capacity_usage_percent", "Capacity usage percentage", ["resource"])

CAPACITY_EXHAUSTION_DAYS = Gauge(
    "capacity_exhaustion_days",
    "Days until capacity exhaustion (-1 if not exhausting)",
    ["resource"],
)


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class Resource:
    """A capacity resource definition."""

    name: str
    current_value: float
    max_value: float
    unit: str = "units"
    growth_rate_per_month: float | None = None
    cost_per_unit: float = 0.0
    critical_threshold_percent: float = 85.0
    warning_threshold_percent: float = 70.0

    @property
    def usage_percent(self) -> float:
        if self.max_value == 0:
            return 100.0
        return (self.current_value / self.max_value) * 100

    @property
    def remaining(self) -> float:
        return max(0, self.max_value - self.current_value)

    @property
    def is_critical(self) -> bool:
        return self.usage_percent >= self.critical_threshold_percent

    @property
    def is_warning(self) -> bool:
        return self.usage_percent >= self.warning_threshold_percent

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "current_value": self.current_value,
            "max_value": self.max_value,
            "unit": self.unit,
            "usage_percent": self.usage_percent,
            "remaining": self.remaining,
            "growth_rate_per_month": self.growth_rate_per_month,
            "cost_per_unit": self.cost_per_unit,
            "is_critical": self.is_critical,
            "is_warning": self.is_warning,
        }


@dataclass
class GrowthDataPoint:
    """A growth data point."""

    timestamp: datetime
    value: float


@dataclass
class CapacityProjection:
    """Projection for a resource."""

    resource_name: str
    current_usage: float
    projected_usage: float
    months_ahead: int
    growth_rate_per_month: float
    days_until_warning: int | None
    days_until_critical: int | None
    days_until_exhaustion: int | None
    additional_capacity_needed: float
    estimated_cost: float
    recommendation: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "resource_name": self.resource_name,
            "current_usage": self.current_usage,
            "projected_usage": self.projected_usage,
            "months_ahead": self.months_ahead,
            "growth_rate_per_month": self.growth_rate_per_month,
            "days_until_warning": self.days_until_warning,
            "days_until_critical": self.days_until_critical,
            "days_until_exhaustion": self.days_until_exhaustion,
            "additional_capacity_needed": self.additional_capacity_needed,
            "estimated_cost": self.estimated_cost,
            "recommendation": self.recommendation,
        }


@dataclass
class CapacityPlan:
    """A capacity plan."""

    generated_at: datetime
    projection_months: int
    projections: list[CapacityProjection]
    total_estimated_cost: float
    action_required: bool
    action_required_by: datetime | None
    summary: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "projection_months": self.projection_months,
            "projections": [p.to_dict() for p in self.projections],
            "total_estimated_cost": self.total_estimated_cost,
            "action_required": self.action_required,
            "action_required_by": self.action_required_by.isoformat()
            if self.action_required_by
            else None,
            "summary": self.summary,
        }


# =============================================================================
# Capacity Planner
# =============================================================================


class CapacityPlanner:
    """
    Plan capacity needs.

    Parameters
    ----------
    default_growth_rate : float
        Default monthly growth rate (e.g., 0.05 for 5%)
    planning_buffer : float
        Buffer to add to projections (e.g., 0.2 for 20%)
    """

    def __init__(
        self,
        default_growth_rate: float = 0.05,
        planning_buffer: float = 0.2,
    ):
        self.default_growth_rate = default_growth_rate
        self.planning_buffer = planning_buffer

        self._resources: dict[str, Resource] = {}
        self._growth_data: dict[str, list[GrowthDataPoint]] = {}
        self._lock = threading.Lock()

    def add_resource(
        self,
        name: str,
        current_value: float,
        max_value: float,
        unit: str = "units",
        growth_rate_per_month: float | None = None,
        cost_per_unit: float = 0.0,
        critical_threshold: float = 85.0,
        warning_threshold: float = 70.0,
    ):
        """
        Add a resource to track.

        Parameters
        ----------
        name : str
            Resource name
        current_value : float
            Current usage
        max_value : float
            Maximum capacity
        unit : str
            Unit of measurement
        growth_rate_per_month : float, optional
            Monthly growth rate (decimal)
        cost_per_unit : float
            Cost per unit
        critical_threshold : float
            Critical threshold percentage
        warning_threshold : float
            Warning threshold percentage
        """
        resource = Resource(
            name=name,
            current_value=current_value,
            max_value=max_value,
            unit=unit,
            growth_rate_per_month=growth_rate_per_month,
            cost_per_unit=cost_per_unit,
            critical_threshold_percent=critical_threshold,
            warning_threshold_percent=warning_threshold,
        )

        with self._lock:
            self._resources[name] = resource
            if name not in self._growth_data:
                self._growth_data[name] = []

            # Record current value
            self._growth_data[name].append(
                GrowthDataPoint(
                    timestamp=datetime.utcnow(),
                    value=current_value,
                )
            )

        # Update metrics
        CAPACITY_CURRENT.labels(resource=name, unit=unit).set(current_value)
        CAPACITY_MAX.labels(resource=name, unit=unit).set(max_value)
        CAPACITY_PERCENT.labels(resource=name).set(resource.usage_percent)

        logger.info(
            "resource_added",
            name=name,
            current=current_value,
            max=max_value,
            usage_percent=resource.usage_percent,
        )

    def update_resource(self, name: str, current_value: float):
        """Update current value for a resource."""
        with self._lock:
            if name not in self._resources:
                return

            resource = self._resources[name]
            resource.current_value = current_value

            # Record data point
            self._growth_data[name].append(
                GrowthDataPoint(
                    timestamp=datetime.utcnow(),
                    value=current_value,
                )
            )

            # Trim old data (keep 1 year)
            cutoff = datetime.utcnow() - timedelta(days=365)
            self._growth_data[name] = [p for p in self._growth_data[name] if p.timestamp > cutoff]

        CAPACITY_CURRENT.labels(resource=name, unit=resource.unit).set(current_value)
        CAPACITY_PERCENT.labels(resource=name).set(resource.usage_percent)

    def calculate_growth_rate(self, name: str) -> float | None:
        """Calculate growth rate from historical data."""
        with self._lock:
            if name not in self._growth_data:
                return None

            data = self._growth_data[name]

        if len(data) < 2:
            return None

        # Calculate monthly growth rate using linear regression
        first = data[0]
        last = data[-1]

        months = (last.timestamp - first.timestamp).days / 30
        if months < 0.5:
            return None

        if first.value == 0:
            return None

        growth = (last.value - first.value) / first.value
        monthly_rate = growth / months

        return monthly_rate

    def project_resource(
        self,
        name: str,
        months_ahead: int = 6,
    ) -> CapacityProjection | None:
        """
        Project capacity for a resource.

        Parameters
        ----------
        name : str
            Resource name
        months_ahead : int
            Months to project

        Returns
        -------
        CapacityProjection or None
        """
        with self._lock:
            if name not in self._resources:
                return None

            resource = self._resources[name]

        # Get growth rate
        growth_rate = resource.growth_rate_per_month
        if growth_rate is None:
            growth_rate = self.calculate_growth_rate(name)
        if growth_rate is None:
            growth_rate = self.default_growth_rate

        # Project usage
        projected = resource.current_value * (1 + growth_rate) ** months_ahead
        projected_with_buffer = projected * (1 + self.planning_buffer)

        # Calculate days until thresholds
        days_until_warning = None
        days_until_critical = None
        days_until_exhaustion = None

        if growth_rate > 0:
            warning_value = resource.max_value * (resource.warning_threshold_percent / 100)
            critical_value = resource.max_value * (resource.critical_threshold_percent / 100)

            if resource.current_value < warning_value:
                months = math.log(warning_value / resource.current_value) / math.log(
                    1 + growth_rate
                )
                days_until_warning = int(months * 30)

            if resource.current_value < critical_value:
                months = math.log(critical_value / resource.current_value) / math.log(
                    1 + growth_rate
                )
                days_until_critical = int(months * 30)

            if resource.current_value < resource.max_value:
                months = math.log(resource.max_value / resource.current_value) / math.log(
                    1 + growth_rate
                )
                days_until_exhaustion = int(months * 30)

        # Calculate additional capacity needed
        additional_needed = max(0, projected_with_buffer - resource.max_value)

        # Estimate cost
        estimated_cost = additional_needed * resource.cost_per_unit

        # Generate recommendation
        recommendation = self._generate_recommendation(resource, projected, days_until_exhaustion)

        projection = CapacityProjection(
            resource_name=name,
            current_usage=resource.current_value,
            projected_usage=projected,
            months_ahead=months_ahead,
            growth_rate_per_month=growth_rate,
            days_until_warning=days_until_warning,
            days_until_critical=days_until_critical,
            days_until_exhaustion=days_until_exhaustion,
            additional_capacity_needed=additional_needed,
            estimated_cost=estimated_cost,
            recommendation=recommendation,
        )

        # Update metrics
        CAPACITY_EXHAUSTION_DAYS.labels(resource=name).set(
            days_until_exhaustion if days_until_exhaustion else -1
        )

        return projection

    def _generate_recommendation(
        self,
        resource: Resource,
        projected: float,
        days_until_exhaustion: int | None,
    ) -> str:
        """Generate capacity recommendation."""
        if resource.is_critical:
            return "CRITICAL: Immediate capacity expansion required"
        elif resource.is_warning:
            return "WARNING: Plan capacity expansion soon"
        elif days_until_exhaustion and days_until_exhaustion < 90:
            return f"ACTION: Capacity exhaustion in ~{days_until_exhaustion} days"
        elif days_until_exhaustion and days_until_exhaustion < 180:
            return "MONITOR: Review capacity in next quarter"
        else:
            return "OK: Capacity sufficient for projected growth"

    def project(self, months_ahead: int = 6) -> CapacityPlan:
        """
        Generate full capacity plan.

        Parameters
        ----------
        months_ahead : int
            Months to project

        Returns
        -------
        CapacityPlan
        """
        with self._lock:
            resource_names = list(self._resources.keys())

        projections = []
        total_cost = 0.0
        action_required = False
        earliest_action_date = None

        for name in resource_names:
            proj = self.project_resource(name, months_ahead)
            if proj:
                projections.append(proj)
                total_cost += proj.estimated_cost

                if proj.days_until_exhaustion and proj.days_until_exhaustion < months_ahead * 30:
                    action_required = True
                    action_date = datetime.utcnow() + timedelta(
                        days=proj.days_until_exhaustion - 30
                    )
                    if earliest_action_date is None or action_date < earliest_action_date:
                        earliest_action_date = action_date

        # Generate summary
        critical = [p for p in projections if "CRITICAL" in p.recommendation]
        warning = [p for p in projections if "WARNING" in p.recommendation]

        if critical:
            summary = f"CRITICAL: {len(critical)} resource(s) need immediate attention"
        elif warning:
            summary = f"WARNING: {len(warning)} resource(s) approaching capacity"
        elif action_required:
            summary = f"ACTION: Capacity expansion needed within {months_ahead} months"
        else:
            summary = "All resources have sufficient capacity for projected growth"

        plan = CapacityPlan(
            generated_at=datetime.utcnow(),
            projection_months=months_ahead,
            projections=projections,
            total_estimated_cost=total_cost,
            action_required=action_required,
            action_required_by=earliest_action_date,
            summary=summary,
        )

        logger.info(
            "capacity_plan_generated",
            months_ahead=months_ahead,
            resources=len(projections),
            action_required=action_required,
            total_cost=total_cost,
        )

        return plan

    def get_resource(self, name: str) -> Resource | None:
        """Get a resource."""
        with self._lock:
            return self._resources.get(name)

    def get_all_resources(self) -> list[Resource]:
        """Get all resources."""
        with self._lock:
            return list(self._resources.values())

    def get_critical_resources(self) -> list[Resource]:
        """Get resources at critical capacity."""
        with self._lock:
            return [r for r in self._resources.values() if r.is_critical]


# =============================================================================
# Singleton
# =============================================================================

_planner: CapacityPlanner | None = None
_planner_lock = threading.Lock()


def get_capacity_planner(**kwargs) -> CapacityPlanner:
    """Get or create the global capacity planner."""
    global _planner

    if _planner is None:
        with _planner_lock:
            if _planner is None:
                _planner = CapacityPlanner(**kwargs)

    return _planner
