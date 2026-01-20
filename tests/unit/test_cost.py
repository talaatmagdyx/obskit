"""Unit tests for cost attribution metrics."""

import time

import pytest

from obskit.cost import (
    CostTracker,
    ResourceUsage,
    track_cost,
)


class TestResourceUsage:
    """Tests for ResourceUsage dataclass."""

    def test_init_defaults(self):
        """Test default values."""
        usage = ResourceUsage(tenant_id="tenant-1")

        assert usage.tenant_id == "tenant-1"
        assert usage.cpu_time_seconds == 0.0
        assert usage.memory_bytes == 0
        assert usage.api_calls == 0
        assert usage.storage_bytes == 0
        assert usage.network_bytes_in == 0
        assert usage.network_bytes_out == 0
        assert usage.cost_units == 0.0

    def test_to_dict(self):
        """Test conversion to dictionary."""
        usage = ResourceUsage(
            tenant_id="tenant-1",
            cpu_time_seconds=10.5,
            memory_bytes=1024 * 1024,
            api_calls=100,
            cost_units=5.50,
        )

        data = usage.to_dict()

        assert data["tenant_id"] == "tenant-1"
        assert data["cpu_time_seconds"] == 10.5
        assert data["memory_bytes"] == 1024 * 1024
        assert data["api_calls"] == 100
        assert data["cost_units"] == 5.50


class TestCostTracker:
    """Tests for CostTracker class."""

    def test_init_defaults(self):
        """Test default initialization."""
        tracker = CostTracker()

        assert tracker.service_name == "default"
        assert "cpu_second" in tracker.cost_rates

    def test_init_with_options(self):
        """Test initialization with custom options."""
        custom_rates = {"cpu_second": 0.0002, "api_call": 0.002}

        tracker = CostTracker(service_name="my-service", cost_rates=custom_rates)

        assert tracker.service_name == "my-service"
        assert tracker.cost_rates["cpu_second"] == 0.0002

    def test_track_cpu(self):
        """Test tracking CPU time."""
        tracker = CostTracker()

        with tracker.track_cpu(tenant_id="tenant-1", operation="process"):
            time.sleep(0.1)

        usage = tracker.get_usage("tenant-1")

        assert usage.cpu_time_seconds >= 0.1
        assert usage.cost_units > 0

    def test_track_memory_usage(self):
        """Test tracking memory usage."""
        tracker = CostTracker()

        tracker.track_memory_usage(
            tenant_id="tenant-1",
            bytes_used=1024 * 1024 * 100,  # 100 MB
            operation="widget_processing",
        )

        usage = tracker.get_usage("tenant-1")

        assert usage.memory_bytes == 1024 * 1024 * 100

    def test_track_memory_usage_keeps_max(self):
        """Test memory tracking keeps maximum value."""
        tracker = CostTracker()

        tracker.track_memory_usage(tenant_id="tenant-1", bytes_used=100)
        tracker.track_memory_usage(tenant_id="tenant-1", bytes_used=200)
        tracker.track_memory_usage(tenant_id="tenant-1", bytes_used=150)

        usage = tracker.get_usage("tenant-1")

        assert usage.memory_bytes == 200

    def test_track_api_call(self):
        """Test tracking API calls."""
        tracker = CostTracker()

        tracker.track_api_call(
            tenant_id="tenant-1", api="external_service", method="POST", cost_units=2.0
        )

        usage = tracker.get_usage("tenant-1")

        assert usage.api_calls == 1
        assert usage.cost_units > 0

    def test_track_storage(self):
        """Test tracking storage usage."""
        tracker = CostTracker()

        tracker.track_storage(
            tenant_id="tenant-1",
            bytes_stored=1024 * 1024 * 1024,  # 1 GB
            storage_type="s3",
        )

        usage = tracker.get_usage("tenant-1")

        assert usage.storage_bytes == 1024 * 1024 * 1024

    def test_track_network(self):
        """Test tracking network usage."""
        tracker = CostTracker()

        tracker.track_network(tenant_id="tenant-1", bytes_in=1024 * 1024, bytes_out=512 * 1024)

        usage = tracker.get_usage("tenant-1")

        assert usage.network_bytes_in == 1024 * 1024
        assert usage.network_bytes_out == 512 * 1024

    def test_track_custom_cost(self):
        """Test tracking custom cost units."""
        tracker = CostTracker()

        tracker.track_custom_cost(
            tenant_id="tenant-1", resource_type="widget_execution", units=10, cost_per_unit=0.05
        )

        usage = tracker.get_usage("tenant-1")

        assert usage.cost_units == 0.5  # 10 * 0.05

    def test_get_usage_new_tenant(self):
        """Test getting usage for new tenant returns empty usage."""
        tracker = CostTracker()

        usage = tracker.get_usage("new-tenant")

        assert usage.tenant_id == "new-tenant"
        assert usage.cpu_time_seconds == 0.0

    def test_get_all_usage(self):
        """Test getting usage for all tenants."""
        tracker = CostTracker()

        tracker.track_api_call(tenant_id="tenant-1", api="api1")
        tracker.track_api_call(tenant_id="tenant-2", api="api2")

        all_usage = tracker.get_all_usage()

        assert "tenant-1" in all_usage
        assert "tenant-2" in all_usage

    def test_calculate_cost(self):
        """Test cost calculation."""
        tracker = CostTracker(
            cost_rates={
                "cpu_second": 0.001,
                "api_call": 0.01,
                "storage_gb_month": 0.10,
                "network_gb": 0.05,
            }
        )

        # Add some usage
        tracker._usage["tenant-1"].cpu_time_seconds = 100
        tracker._usage["tenant-1"].api_calls = 50
        tracker._usage["tenant-1"].storage_bytes = 1024**3  # 1 GB
        tracker._usage["tenant-1"].network_bytes_in = 1024**3
        tracker._usage["tenant-1"].network_bytes_out = 1024**3

        costs = tracker.calculate_cost("tenant-1")

        assert "cpu" in costs
        assert "api_calls" in costs
        assert "storage" in costs
        assert "network" in costs
        assert "total" in costs

        assert costs["cpu"] == 0.1  # 100 * 0.001
        assert costs["api_calls"] == 0.5  # 50 * 0.01

    def test_get_usage_report_single_tenant(self):
        """Test usage report for single tenant."""
        tracker = CostTracker()

        tracker.track_api_call(tenant_id="tenant-1", api="api1")

        report = tracker.get_usage_report(tenant_id="tenant-1")

        assert report["tenant_id"] == "tenant-1"
        assert "usage" in report
        assert "estimated_cost" in report
        assert "generated_at" in report

    def test_get_usage_report_all_tenants(self):
        """Test usage report for all tenants."""
        tracker = CostTracker()

        tracker.track_api_call(tenant_id="tenant-1", api="api1")
        tracker.track_api_call(tenant_id="tenant-2", api="api2")

        report = tracker.get_usage_report()

        assert "tenants" in report
        assert "tenant-1" in report["tenants"]
        assert "tenant-2" in report["tenants"]
        assert "total_cost" in report

    def test_reset_usage_single_tenant(self):
        """Test resetting usage for single tenant."""
        tracker = CostTracker()

        tracker.track_api_call(tenant_id="tenant-1", api="api1")
        tracker.track_api_call(tenant_id="tenant-2", api="api2")

        tracker.reset_usage(tenant_id="tenant-1")

        assert "tenant-1" not in tracker._usage
        assert "tenant-2" in tracker._usage

    def test_reset_usage_all_tenants(self):
        """Test resetting usage for all tenants."""
        tracker = CostTracker()

        tracker.track_api_call(tenant_id="tenant-1", api="api1")
        tracker.track_api_call(tenant_id="tenant-2", api="api2")

        tracker.reset_usage()

        assert len(tracker._usage) == 0

    def test_export_usage_json(self):
        """Test exporting usage as JSON."""
        tracker = CostTracker()

        tracker.track_api_call(tenant_id="tenant-1", api="api1")

        export = tracker.export_usage(format="json")

        assert isinstance(export, str)
        assert "tenant-1" in export


class TestTrackCostDecorator:
    """Tests for track_cost decorator."""

    def test_decorator_tracks_cpu(self):
        """Test decorator tracks CPU time."""
        tracker = CostTracker()

        @track_cost(tracker, tenant_id_arg="customer_id")
        def process_request(customer_id: str, data: dict):
            time.sleep(0.05)
            return data

        result = process_request("tenant-1", {"key": "value"})

        assert result == {"key": "value"}

        usage = tracker.get_usage("tenant-1")
        assert usage.cpu_time_seconds >= 0.05

    def test_decorator_extracts_tenant_from_kwargs(self):
        """Test decorator extracts tenant from kwargs."""
        tracker = CostTracker()

        @track_cost(tracker, tenant_id_arg="tenant_id")
        def process(data, tenant_id=None):
            return data

        process({"data": 1}, tenant_id="kwarg-tenant")

        usage = tracker.get_usage("kwarg-tenant")
        assert usage.cpu_time_seconds > 0

    def test_decorator_uses_unknown_for_missing_tenant(self):
        """Test decorator uses 'unknown' when tenant not found."""
        tracker = CostTracker()

        @track_cost(tracker, tenant_id_arg="tenant_id")
        def process(data):
            return data

        process({"data": 1})

        usage = tracker.get_usage("unknown")
        assert usage.cpu_time_seconds > 0

    @pytest.mark.asyncio
    async def test_decorator_async(self):
        """Test decorator works with async functions."""
        tracker = CostTracker()

        @track_cost(tracker, tenant_id_arg="tenant_id")
        async def async_process(data, tenant_id=None):
            return data

        result = await async_process({"data": 1}, tenant_id="async-tenant")

        assert result == {"data": 1}

        usage = tracker.get_usage("async-tenant")
        assert usage.cpu_time_seconds > 0
