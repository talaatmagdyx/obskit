"""
Example: RED, Golden Signals, and USE Methodologies
====================================================

This example shows how to implement all three observability
methodologies using obskit for comprehensive monitoring.

Methodologies:
- RED: Rate, Errors, Duration (for services/APIs)
- Golden Signals: Latency, Traffic, Errors, Saturation (for services)
- USE: Utilization, Saturation, Errors (for resources/infrastructure)
"""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass
from typing import Any

from obskit import configure, get_logger, start_http_server
from obskit.metrics import GoldenSignals, REDMetrics, USEMetrics

# =============================================================================
# Setup
# =============================================================================


def setup():
    """Initialize obskit."""
    configure(
        service_name="methodology-demo",
        environment="production",
    )
    start_http_server(port=9090)


# =============================================================================
# RED Method - For Service Endpoints
# =============================================================================


class OrderService:
    """
    Example service using RED method.

    RED is best for:
    - API endpoints
    - Microservices
    - Request-driven workloads

    Metrics:
    - Rate: Requests per second
    - Errors: Failed requests
    - Duration: Response time
    """

    def __init__(self):
        self.metrics = REDMetrics(
            name="order_service",
            # Custom latency buckets for your SLOs
            histogram_buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5),
        )
        self.logger = get_logger("order-service")

    async def create_order(self, order_data: dict[str, Any]) -> dict[str, Any]:
        """Create an order - tracked with RED metrics."""
        with self.metrics.track_request("create_order"):
            # Simulate processing
            await asyncio.sleep(random.uniform(0.01, 0.1))

            # Simulate occasional failures
            if random.random() < 0.05:
                raise ValueError("Payment declined")

            return {"id": "order-123", "status": "created"}

    async def get_order(self, order_id: str) -> dict[str, Any]:
        """Get order details - tracked with RED metrics."""
        with self.metrics.track_request("get_order"):
            await asyncio.sleep(random.uniform(0.005, 0.05))
            return {"id": order_id, "status": "completed"}

    async def list_orders(self, user_id: str) -> list[dict[str, Any]]:
        """List user orders - tracked with RED metrics."""
        with self.metrics.track_request("list_orders"):
            await asyncio.sleep(random.uniform(0.02, 0.15))
            return [{"id": f"order-{i}"} for i in range(10)]

    def get_prometheus_queries(self) -> dict[str, str]:
        """Example PromQL queries for RED dashboards."""
        return {
            "request_rate": "sum(rate(order_service_requests_total[5m])) by (operation)",
            "error_rate": """
                sum(rate(order_service_errors_total[5m])) by (operation)
                /
                sum(rate(order_service_requests_total[5m])) by (operation)
            """,
            "p50_latency": """
                histogram_quantile(0.50,
                    sum(rate(order_service_request_duration_seconds_bucket[5m])) by (le, operation)
                )
            """,
            "p95_latency": """
                histogram_quantile(0.95,
                    sum(rate(order_service_request_duration_seconds_bucket[5m])) by (le, operation)
                )
            """,
            "p99_latency": """
                histogram_quantile(0.99,
                    sum(rate(order_service_request_duration_seconds_bucket[5m])) by (le, operation)
                )
            """,
        }


# =============================================================================
# Golden Signals - For Complete Service Monitoring
# =============================================================================


class PaymentGateway:
    """
    Example service using Golden Signals.

    Golden Signals (from Google SRE book) are best for:
    - Services requiring capacity planning
    - Services with resource constraints
    - Complete service health monitoring

    Signals:
    - Latency: Time to serve requests
    - Traffic: Demand on the system
    - Errors: Rate of failed requests
    - Saturation: How "full" the service is
    """

    def __init__(self, max_concurrent: int = 100):
        self.metrics = GoldenSignals(
            name="payment_gateway",
        )
        self.logger = get_logger("payment-gateway")
        self.max_concurrent = max_concurrent
        self.current_connections = 0

    async def process_payment(self, payment_data: dict[str, Any]) -> dict[str, Any]:
        """Process a payment with Golden Signals tracking."""
        # Track saturation (concurrent requests)
        self.current_connections += 1
        self.metrics.set_saturation("connections", self.current_connections / self.max_concurrent)

        try:
            # Track request with latency, traffic, and errors
            with self.metrics.track_request("process_payment"):
                # Simulate payment processing
                await asyncio.sleep(random.uniform(0.1, 0.5))

                # Simulate failures
                if random.random() < 0.02:
                    raise ConnectionError("Payment gateway timeout")

                return {"status": "success", "transaction_id": "txn-456"}
        finally:
            self.current_connections -= 1
            self.metrics.set_saturation(
                "connections", self.current_connections / self.max_concurrent
            )

    def update_queue_depth(self, depth: int):
        """Track queue saturation."""
        self.metrics.set_queue_depth("payment_queue", depth)

    def get_prometheus_queries(self) -> dict[str, str]:
        """Example PromQL queries for Golden Signals dashboards."""
        return {
            # Latency
            "latency_p99": """
                histogram_quantile(0.99,
                    sum(rate(payment_gateway_request_duration_seconds_bucket[5m])) by (le)
                )
            """,
            # Traffic
            "traffic_rps": "sum(rate(payment_gateway_requests_total[5m]))",
            # Errors
            "error_percentage": """
                100 * sum(rate(payment_gateway_errors_total[5m]))
                /
                sum(rate(payment_gateway_requests_total[5m]))
            """,
            # Saturation
            "saturation": 'payment_gateway_saturation_ratio{resource="connections"}',
            "queue_depth": 'payment_gateway_queue_depth{queue="payment_queue"}',
        }


# =============================================================================
# USE Method - For Infrastructure/Resources
# =============================================================================


@dataclass
class ResourceMetrics:
    """Simulated resource metrics."""

    cpu_percent: float
    memory_percent: float
    disk_io_percent: float
    network_percent: float
    cpu_queue: int
    disk_queue: int


class InfrastructureMonitor:
    """
    Example infrastructure monitoring using USE method.

    USE (from Brendan Gregg) is best for:
    - CPU monitoring
    - Memory monitoring
    - Disk I/O
    - Network interfaces
    - Any hardware/infrastructure resource

    Metrics:
    - Utilization: % time resource was busy
    - Saturation: Work queued/waiting
    - Errors: Error events
    """

    def __init__(self):
        self.cpu_metrics = USEMetrics(name="server_cpu")
        self.memory_metrics = USEMetrics(name="server_memory")
        self.disk_metrics = USEMetrics(name="server_disk")
        self.network_metrics = USEMetrics(name="server_network")
        self.logger = get_logger("infra-monitor")

    def update_metrics(self, resources: ResourceMetrics):
        """Update all infrastructure metrics."""
        # CPU
        self.cpu_metrics.set_utilization("cpu", resources.cpu_percent / 100)
        self.cpu_metrics.set_saturation("cpu", resources.cpu_queue)

        # Memory
        self.memory_metrics.set_utilization("memory", resources.memory_percent / 100)
        # Memory doesn't typically have saturation (it's either available or not)

        # Disk
        self.disk_metrics.set_utilization("disk", resources.disk_io_percent / 100)
        self.disk_metrics.set_saturation("disk", resources.disk_queue)

        # Network
        self.network_metrics.set_utilization("network", resources.network_percent / 100)

    def record_error(self, resource: str, error_type: str):
        """Record a resource error."""
        if resource == "cpu":
            self.cpu_metrics.record_error("cpu", error_type)
        elif resource == "disk":
            self.disk_metrics.record_error("disk", error_type)
        elif resource == "network":
            self.network_metrics.record_error("network", error_type)

    async def collect_metrics(self):
        """Simulate collecting infrastructure metrics."""
        while True:
            # Simulate resource usage
            resources = ResourceMetrics(
                cpu_percent=random.uniform(20, 80),
                memory_percent=random.uniform(40, 70),
                disk_io_percent=random.uniform(10, 50),
                network_percent=random.uniform(5, 30),
                cpu_queue=random.randint(0, 5),
                disk_queue=random.randint(0, 10),
            )

            self.update_metrics(resources)

            # Simulate occasional errors
            if random.random() < 0.01:
                self.record_error("disk", "io_error")

            await asyncio.sleep(5)  # Collect every 5 seconds

    def get_prometheus_queries(self) -> dict[str, str]:
        """Example PromQL queries for USE dashboards."""
        return {
            # CPU
            "cpu_utilization": 'server_cpu_utilization_ratio{resource="cpu"}',
            "cpu_saturation": 'server_cpu_saturation{resource="cpu"}',
            "cpu_errors": "rate(server_cpu_errors_total[5m])",
            # Memory
            "memory_utilization": 'server_memory_utilization_ratio{resource="memory"}',
            # Disk
            "disk_utilization": 'server_disk_utilization_ratio{resource="disk"}',
            "disk_saturation": 'server_disk_saturation{resource="disk"}',
            "disk_errors": "rate(server_disk_errors_total[5m])",
            # Network
            "network_utilization": 'server_network_utilization_ratio{resource="network"}',
        }


# =============================================================================
# Combined Dashboard Example
# =============================================================================


def get_grafana_dashboard_json() -> dict[str, Any]:
    """
    Example Grafana dashboard configuration combining all methodologies.
    """
    return {
        "title": "Unified Observability Dashboard",
        "rows": [
            {
                "title": "RED Method - Order Service",
                "panels": [
                    {"title": "Request Rate", "type": "graph"},
                    {"title": "Error Rate", "type": "graph"},
                    {"title": "Latency (p50, p95, p99)", "type": "graph"},
                ],
            },
            {
                "title": "Golden Signals - Payment Gateway",
                "panels": [
                    {"title": "Latency Distribution", "type": "heatmap"},
                    {"title": "Traffic (RPS)", "type": "graph"},
                    {"title": "Error Rate", "type": "stat"},
                    {"title": "Saturation", "type": "gauge"},
                ],
            },
            {
                "title": "USE Method - Infrastructure",
                "panels": [
                    {"title": "CPU Utilization", "type": "gauge"},
                    {"title": "Memory Utilization", "type": "gauge"},
                    {"title": "Disk I/O + Queue", "type": "graph"},
                    {"title": "Resource Errors", "type": "table"},
                ],
            },
        ],
    }


# =============================================================================
# Demo
# =============================================================================


async def demo():
    """Run a demo of all three methodologies."""
    setup()

    print("\n" + "=" * 60)
    print("RED, Golden Signals, and USE Methodologies Demo")
    print("=" * 60)

    # Initialize services
    order_service = OrderService()
    payment_gateway = PaymentGateway(max_concurrent=100)
    infra_monitor = InfrastructureMonitor()

    # Start infrastructure monitoring in background
    asyncio.create_task(infra_monitor.collect_metrics())

    print("\n📊 Metrics available at http://localhost:9090/metrics")
    print("\nSimulating traffic...")

    # Simulate traffic
    for i in range(100):
        try:
            # RED - Order Service
            if random.random() < 0.3:
                await order_service.create_order({"item": "product-1"})
            elif random.random() < 0.5:
                await order_service.get_order(f"order-{i}")
            else:
                await order_service.list_orders("user-123")

            # Golden Signals - Payment Gateway
            if random.random() < 0.2:
                payment_gateway.update_queue_depth(random.randint(0, 20))
                await payment_gateway.process_payment({"amount": 99.99})

        except Exception as e:
            print(f"  Expected error: {e}")

        if i % 20 == 0:
            print(f"  Processed {i + 1} operations...")

    print("\n✅ Demo complete!")
    print("\nExample PromQL Queries:")
    print("-" * 40)

    print("\nRED Method:")
    for name, query in order_service.get_prometheus_queries().items():
        print(f"  {name}:")
        print(f"    {query.strip()}")

    print("\nGolden Signals:")
    for name, query in payment_gateway.get_prometheus_queries().items():
        print(f"  {name}:")
        print(f"    {query.strip()}")

    print("\nUSE Method:")
    for name, query in infra_monitor.get_prometheus_queries().items():
        print(f"  {name}:")
        print(f"    {query.strip()}")


if __name__ == "__main__":
    asyncio.run(demo())
