"""
Cost Attribution Metrics.

Track resource usage per tenant for billing and cost allocation.
"""

import time
from collections import defaultdict
from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, TypeVar

from prometheus_client import Counter, Gauge, Histogram

# Metrics
COST_CPU_TIME = Counter(
    "cost_cpu_time_seconds_total", "CPU time consumed", ["service", "tenant_id", "operation"]
)

COST_MEMORY_USAGE = Histogram(
    "cost_memory_bytes",
    "Memory usage",
    ["service", "tenant_id", "operation"],
    buckets=[1024, 10240, 102400, 1048576, 10485760, 104857600, 1073741824],
)

COST_API_CALLS = Counter(
    "cost_api_calls_total", "External API calls", ["service", "tenant_id", "api", "method"]
)

COST_STORAGE = Gauge("cost_storage_bytes", "Storage used", ["service", "tenant_id", "storage_type"])

COST_NETWORK_BYTES = Counter(
    "cost_network_bytes_total", "Network bytes transferred", ["service", "tenant_id", "direction"]
)

COST_UNITS = Counter(
    "cost_units_total", "Abstract cost units", ["service", "tenant_id", "resource_type"]
)

F = TypeVar("F", bound=Callable[..., Any])


@dataclass
class ResourceUsage:
    """Resource usage for a tenant."""

    tenant_id: str
    cpu_time_seconds: float = 0.0
    memory_bytes: int = 0
    api_calls: int = 0
    storage_bytes: int = 0
    network_bytes_in: int = 0
    network_bytes_out: int = 0
    cost_units: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "cpu_time_seconds": self.cpu_time_seconds,
            "memory_bytes": self.memory_bytes,
            "api_calls": self.api_calls,
            "storage_bytes": self.storage_bytes,
            "network_bytes_in": self.network_bytes_in,
            "network_bytes_out": self.network_bytes_out,
            "cost_units": self.cost_units,
            "timestamp": self.timestamp.isoformat(),
        }


class CostTracker:
    """
    Tracks resource usage per tenant for cost attribution.

    Example:
        tracker = CostTracker("my-service")

        # Track compute usage
        with tracker.track_cpu(tenant_id="123", operation="process_message"):
            process_message()

        # Track API calls
        tracker.track_api_call(tenant_id="123", api="external_service", cost_units=1)

        # Track storage
        tracker.track_storage(tenant_id="123", bytes_stored=1024*1024*100)

        # Get usage report
        report = tracker.get_usage_report(tenant_id="123")
    """

    def __init__(
        self, service_name: str = "default", cost_rates: dict[str, float] | None = None
    ):
        """
        Initialize cost tracker.

        Args:
            service_name: Service name for metrics
            cost_rates: Cost rates for different resources
        """
        self.service_name = service_name
        self.cost_rates = cost_rates or {
            "cpu_second": 0.0001,
            "memory_gb_second": 0.00001,
            "api_call": 0.001,
            "storage_gb_month": 0.02,
            "network_gb": 0.01,
        }

        # Track usage in memory
        self._usage: dict[str, ResourceUsage] = defaultdict(
            lambda: ResourceUsage(tenant_id="unknown")
        )

    @contextmanager
    def track_cpu(self, tenant_id: str, operation: str = "default") -> Generator[None, None, None]:
        """
        Track CPU time for an operation.

        Args:
            tenant_id: Tenant identifier
            operation: Operation name
        """
        start_time = time.time()

        try:
            yield
        finally:
            duration = time.time() - start_time

            COST_CPU_TIME.labels(
                service=self.service_name, tenant_id=tenant_id, operation=operation
            ).inc(duration)

            self._usage[tenant_id].tenant_id = tenant_id
            self._usage[tenant_id].cpu_time_seconds += duration
            self._usage[tenant_id].cost_units += duration * self.cost_rates["cpu_second"]

    def track_memory_usage(self, tenant_id: str, bytes_used: int, operation: str = "default"):
        """
        Track memory usage.

        Args:
            tenant_id: Tenant identifier
            bytes_used: Memory used in bytes
            operation: Operation name
        """
        COST_MEMORY_USAGE.labels(
            service=self.service_name, tenant_id=tenant_id, operation=operation
        ).observe(bytes_used)

        self._usage[tenant_id].tenant_id = tenant_id
        self._usage[tenant_id].memory_bytes = max(self._usage[tenant_id].memory_bytes, bytes_used)

    def track_api_call(
        self, tenant_id: str, api: str, method: str = "GET", cost_units: float = 1.0
    ):
        """
        Track external API call.

        Args:
            tenant_id: Tenant identifier
            api: API name
            method: HTTP method
            cost_units: Cost units for this call
        """
        COST_API_CALLS.labels(
            service=self.service_name, tenant_id=tenant_id, api=api, method=method
        ).inc()

        COST_UNITS.labels(
            service=self.service_name, tenant_id=tenant_id, resource_type="api_call"
        ).inc(cost_units)

        self._usage[tenant_id].tenant_id = tenant_id
        self._usage[tenant_id].api_calls += 1
        self._usage[tenant_id].cost_units += cost_units * self.cost_rates["api_call"]

    def track_storage(self, tenant_id: str, bytes_stored: int, storage_type: str = "default"):
        """
        Track storage usage.

        Args:
            tenant_id: Tenant identifier
            bytes_stored: Bytes stored
            storage_type: Type of storage
        """
        COST_STORAGE.labels(
            service=self.service_name, tenant_id=tenant_id, storage_type=storage_type
        ).set(bytes_stored)

        self._usage[tenant_id].tenant_id = tenant_id
        self._usage[tenant_id].storage_bytes = bytes_stored

    def track_network(self, tenant_id: str, bytes_in: int = 0, bytes_out: int = 0):
        """
        Track network usage.

        Args:
            tenant_id: Tenant identifier
            bytes_in: Bytes received
            bytes_out: Bytes sent
        """
        if bytes_in > 0:
            COST_NETWORK_BYTES.labels(
                service=self.service_name, tenant_id=tenant_id, direction="in"
            ).inc(bytes_in)
            self._usage[tenant_id].network_bytes_in += bytes_in

        if bytes_out > 0:
            COST_NETWORK_BYTES.labels(
                service=self.service_name, tenant_id=tenant_id, direction="out"
            ).inc(bytes_out)
            self._usage[tenant_id].network_bytes_out += bytes_out

        self._usage[tenant_id].tenant_id = tenant_id

        # Calculate cost
        total_bytes = bytes_in + bytes_out
        gb = total_bytes / (1024**3)
        self._usage[tenant_id].cost_units += gb * self.cost_rates["network_gb"]

    def track_custom_cost(
        self,
        tenant_id: str,
        resource_type: str,
        units: float,
        cost_per_unit: float | None = None,
    ):
        """
        Track custom cost units.

        Args:
            tenant_id: Tenant identifier
            resource_type: Type of resource
            units: Number of units consumed
            cost_per_unit: Cost per unit (optional)
        """
        COST_UNITS.labels(
            service=self.service_name, tenant_id=tenant_id, resource_type=resource_type
        ).inc(units)

        self._usage[tenant_id].tenant_id = tenant_id

        if cost_per_unit:
            self._usage[tenant_id].cost_units += units * cost_per_unit

    def get_usage(self, tenant_id: str) -> ResourceUsage:
        """Get resource usage for a tenant."""
        if tenant_id in self._usage:
            return self._usage[tenant_id]
        return ResourceUsage(tenant_id=tenant_id)

    def get_all_usage(self) -> dict[str, ResourceUsage]:
        """Get resource usage for all tenants."""
        return dict(self._usage)

    def calculate_cost(
        self, tenant_id: str, period: timedelta | None = None
    ) -> dict[str, float]:
        """
        Calculate estimated cost for a tenant.

        Args:
            tenant_id: Tenant identifier
            period: Time period for calculation (default: accumulated)

        Returns:
            Cost breakdown by resource type
        """
        usage = self.get_usage(tenant_id)

        return {
            "cpu": usage.cpu_time_seconds * self.cost_rates["cpu_second"],
            "api_calls": usage.api_calls * self.cost_rates["api_call"],
            "storage": (usage.storage_bytes / (1024**3)) * self.cost_rates["storage_gb_month"],
            "network": ((usage.network_bytes_in + usage.network_bytes_out) / (1024**3))
            * self.cost_rates["network_gb"],
            "total": usage.cost_units,
        }

    def get_usage_report(self, tenant_id: str | None = None) -> dict[str, Any]:
        """
        Generate usage report.

        Args:
            tenant_id: Specific tenant (or all if None)

        Returns:
            Usage report dictionary
        """
        if tenant_id:
            usage = self.get_usage(tenant_id)
            costs = self.calculate_cost(tenant_id)
            return {
                "tenant_id": tenant_id,
                "usage": usage.to_dict(),
                "estimated_cost": costs,
                "generated_at": datetime.utcnow().isoformat(),
            }
        else:
            report = {
                "tenants": {},
                "total_cost": 0.0,
                "generated_at": datetime.utcnow().isoformat(),
            }

            for tid, usage in self._usage.items():
                costs = self.calculate_cost(tid)
                report["tenants"][tid] = {"usage": usage.to_dict(), "estimated_cost": costs}
                report["total_cost"] += costs["total"]

            return report

    def reset_usage(self, tenant_id: str | None = None):
        """
        Reset usage counters.

        Args:
            tenant_id: Specific tenant (or all if None)
        """
        if tenant_id:
            if tenant_id in self._usage:
                del self._usage[tenant_id]
        else:
            self._usage.clear()

    def export_usage(self, format: str = "json") -> str:
        """
        Export usage data.

        Args:
            format: Export format (json, csv)

        Returns:
            Formatted usage data
        """
        import json

        report = self.get_usage_report()
        return json.dumps(report, indent=2, default=str)


def track_cost(
    tracker: CostTracker, tenant_id_arg: str = "tenant_id", operation_arg: str | None = None
) -> Callable[[F], F]:
    """
    Decorator to track cost of a function.

    Example:
        tracker = CostTracker("my-service")

        @track_cost(tracker, tenant_id_arg="customer_id")
        def process_request(customer_id: str, data: dict):
            pass
    """
    import functools

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Extract tenant_id from kwargs or first arg
            tid = kwargs.get(tenant_id_arg)
            if not tid and args:
                # Try to find in args if it's the first positional arg
                import inspect

                sig = inspect.signature(func)
                params = list(sig.parameters.keys())
                if tenant_id_arg in params:
                    idx = params.index(tenant_id_arg)
                    if idx < len(args):
                        tid = args[idx]

            tid = tid or "unknown"
            operation = operation_arg or func.__name__

            with tracker.track_cpu(tenant_id=tid, operation=operation):
                return func(*args, **kwargs)

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            tid = kwargs.get(tenant_id_arg)
            if not tid and args:
                import inspect

                sig = inspect.signature(func)
                params = list(sig.parameters.keys())
                if tenant_id_arg in params:
                    idx = params.index(tenant_id_arg)
                    if idx < len(args):
                        tid = args[idx]

            tid = tid or "unknown"
            operation = operation_arg or func.__name__

            with tracker.track_cpu(tenant_id=tid, operation=operation):
                return await func(*args, **kwargs)

        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return wrapper  # type: ignore

    return decorator


__all__ = [
    "CostTracker",
    "ResourceUsage",
    "track_cost",
    "COST_CPU_TIME",
    "COST_MEMORY_USAGE",
    "COST_API_CALLS",
    "COST_STORAGE",
    "COST_NETWORK_BYTES",
    "COST_UNITS",
]
