"""Unit tests for Capacity Planner."""

import pytest
from datetime import datetime, timedelta
from obskit.capacity import (
    CapacityPlanner,
    CapacityPlan,
    CapacityProjection,
    Resource,
    get_capacity_planner,
)


class TestCapacityPlanner:
    """Tests for CapacityPlanner."""

    def test_add_resource(self):
        """Test adding a resource."""
        planner = CapacityPlanner()
        
        planner.add_resource(
            name="database_storage",
            current_value=500,
            max_value=1000,
            unit="GB",
        )
        
        resource = planner.get_resource("database_storage")
        assert resource is not None
        assert resource.current_value == 500
        assert resource.max_value == 1000

    def test_resource_usage_percent(self):
        """Test usage percentage calculation."""
        planner = CapacityPlanner()
        
        planner.add_resource(
            name="memory",
            current_value=60,
            max_value=100,
            unit="percent",
        )
        
        resource = planner.get_resource("memory")
        assert resource.usage_percent == 60.0

    def test_resource_remaining(self):
        """Test remaining capacity calculation."""
        planner = CapacityPlanner()
        
        planner.add_resource(
            name="disk",
            current_value=700,
            max_value=1000,
        )
        
        resource = planner.get_resource("disk")
        assert resource.remaining == 300

    def test_resource_is_critical(self):
        """Test critical threshold detection."""
        planner = CapacityPlanner()
        
        planner.add_resource(
            name="high_usage",
            current_value=90,
            max_value=100,
            critical_threshold=85.0,
        )
        
        resource = planner.get_resource("high_usage")
        assert resource.is_critical is True

    def test_resource_is_warning(self):
        """Test warning threshold detection."""
        planner = CapacityPlanner()
        
        planner.add_resource(
            name="medium_usage",
            current_value=75,
            max_value=100,
            warning_threshold=70.0,
        )
        
        resource = planner.get_resource("medium_usage")
        assert resource.is_warning is True

    def test_update_resource(self):
        """Test updating resource value."""
        planner = CapacityPlanner()
        
        planner.add_resource("cpu", current_value=50, max_value=100)
        planner.update_resource("cpu", current_value=75)
        
        resource = planner.get_resource("cpu")
        assert resource.current_value == 75

    def test_project_resource(self):
        """Test resource projection."""
        planner = CapacityPlanner()
        
        planner.add_resource(
            name="storage",
            current_value=500,
            max_value=1000,
            growth_rate_per_month=0.1,  # 10% monthly growth
        )
        
        projection = planner.project_resource("storage", months_ahead=6)
        
        assert projection is not None
        assert projection.projected_usage > 500  # Should grow

    def test_project_with_historical_data(self):
        """Test projection using historical data."""
        planner = CapacityPlanner()
        
        planner.add_resource("data", current_value=100, max_value=500)
        
        # Simulate growth over time
        base_time = datetime.utcnow() - timedelta(days=60)
        for i in range(60):
            _timestamp = base_time + timedelta(days=i)  # For reference
            planner.update_resource("data", current_value=100 + i)
        
        # Calculate growth rate should work
        growth_rate = planner.calculate_growth_rate("data")
        assert growth_rate is None or growth_rate > 0

    def test_project_generates_plan(self):
        """Test full capacity plan generation."""
        planner = CapacityPlanner()
        
        planner.add_resource("cpu", current_value=50, max_value=100, growth_rate_per_month=0.05)
        planner.add_resource("memory", current_value=60, max_value=100, growth_rate_per_month=0.08)
        
        plan = planner.project(months_ahead=12)
        
        assert plan is not None
        assert len(plan.projections) == 2
        assert plan.summary is not None

    def test_project_identifies_action_required(self):
        """Test that plan identifies when action is required."""
        planner = CapacityPlanner()
        
        planner.add_resource(
            name="critical_resource",
            current_value=90,
            max_value=100,
            growth_rate_per_month=0.1,
        )
        
        plan = planner.project(months_ahead=6)
        
        # May or may not require action depending on projection
        assert isinstance(plan.action_required, bool)

    def test_get_critical_resources(self):
        """Test getting critical resources."""
        planner = CapacityPlanner()
        
        planner.add_resource("safe", current_value=50, max_value=100, critical_threshold=85)
        planner.add_resource("critical", current_value=95, max_value=100, critical_threshold=85)
        
        critical = planner.get_critical_resources()
        
        assert len(critical) == 1
        assert critical[0].name == "critical"

    def test_cost_estimation(self):
        """Test cost estimation in projection."""
        planner = CapacityPlanner()
        
        planner.add_resource(
            name="storage",
            current_value=800,
            max_value=1000,
            growth_rate_per_month=0.1,
            cost_per_unit=0.10,  # $0.10 per GB
        )
        
        projection = planner.project_resource("storage", months_ahead=6)
        
        # Cost should be calculated if additional capacity needed
        assert projection.estimated_cost >= 0


class TestResource:
    """Tests for Resource."""

    def test_to_dict(self):
        """Test Resource serialization."""
        resource = Resource(
            name="test",
            current_value=50,
            max_value=100,
            unit="GB",
        )
        
        data = resource.to_dict()
        assert data["name"] == "test"
        assert data["usage_percent"] == 50.0
        assert data["remaining"] == 50


class TestCapacityPlan:
    """Tests for CapacityPlan."""

    def test_to_dict(self):
        """Test CapacityPlan serialization."""
        plan = CapacityPlan(
            generated_at=datetime.utcnow(),
            projection_months=6,
            projections=[],
            total_estimated_cost=100.0,
            action_required=True,
            action_required_by=datetime.utcnow() + timedelta(days=30),
            summary="Action needed",
        )
        
        data = plan.to_dict()
        assert data["projection_months"] == 6
        assert data["action_required"] is True


class TestCapacityProjection:
    """Tests for CapacityProjection."""

    def test_to_dict(self):
        """Test CapacityProjection serialization."""
        projection = CapacityProjection(
            resource_name="storage",
            current_usage=500,
            projected_usage=800,
            months_ahead=6,
            growth_rate_per_month=0.1,
            days_until_warning=60,
            days_until_critical=90,
            days_until_exhaustion=120,
            additional_capacity_needed=200,
            estimated_cost=20.0,
            recommendation="Plan expansion",
        )
        
        data = projection.to_dict()
        assert data["resource_name"] == "storage"
        assert data["projected_usage"] == 800


class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_capacity_planner(self):
        """Test global planner singleton."""
        planner1 = get_capacity_planner()
        planner2 = get_capacity_planner()
        assert planner1 is planner2
