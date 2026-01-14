"""
Example: Distributed Circuit Breaker
=====================================

This example shows how to implement distributed circuit breakers
using Redis for state sharing across multiple service instances.

Use Case:
- Multiple pods/instances of a service
- Need consistent circuit breaker state across all instances
- Prevent cascading failures in microservices
"""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass
from typing import Any

from obskit import configure, get_logger, get_red_metrics, start_http_server
from obskit.resilience import CircuitBreaker, retry_async
from obskit.resilience.circuit_breaker import CircuitState
from obskit.resilience.distributed import DistributedCircuitBreaker

# =============================================================================
# Configuration
# =============================================================================


@dataclass
class ServiceConfig:
    """Configuration for external service connection."""

    name: str
    base_url: str
    timeout_seconds: float = 5.0
    # Circuit breaker settings
    failure_threshold: int = 5
    recovery_timeout: float = 30.0
    half_open_max_calls: int = 3


# External services configuration
EXTERNAL_SERVICES = {
    "payment_gateway": ServiceConfig(
        name="payment-gateway",
        base_url="https://payments.example.com",
        timeout_seconds=10.0,
        failure_threshold=3,
        recovery_timeout=60.0,
    ),
    "inventory_service": ServiceConfig(
        name="inventory-service",
        base_url="https://inventory.internal",
        timeout_seconds=5.0,
        failure_threshold=5,
        recovery_timeout=30.0,
    ),
    "notification_service": ServiceConfig(
        name="notification-service",
        base_url="https://notifications.internal",
        timeout_seconds=3.0,
        failure_threshold=10,
        recovery_timeout=15.0,
    ),
}


# =============================================================================
# Local Circuit Breaker (Single Instance)
# =============================================================================


class LocalCircuitBreakerExample:
    """
    Example using local (in-memory) circuit breaker.

    Use when:
    - Single instance deployment
    - State doesn't need to be shared
    - Simpler setup required

    Limitation:
    - Each pod has independent state
    - In a 10-pod deployment, all 10 pods must independently
      detect failures before opening their circuits
    """

    def __init__(self, config: ServiceConfig):
        self.config = config
        self.breaker = CircuitBreaker(
            name=config.name,
            failure_threshold=config.failure_threshold,
            recovery_timeout=config.recovery_timeout,
        )
        self.logger = get_logger(f"circuit-{config.name}")
        self.metrics = get_red_metrics()

    @retry_async(max_attempts=3, base_delay=1.0, max_delay=10.0)
    async def call_service(self, endpoint: str, data: dict[str, Any]) -> dict[str, Any]:
        """Call external service with circuit breaker protection."""

        @self.breaker
        async def _call():
            self.logger.info(
                "calling_external_service",
                service=self.config.name,
                endpoint=endpoint,
            )

            # Simulate external call
            await asyncio.sleep(random.uniform(0.01, 0.1))

            # Simulate failures (20% failure rate when "service is degraded")
            if random.random() < 0.2:
                raise ConnectionError(f"Failed to connect to {self.config.name}")

            return {"status": "success", "data": data}

        with self.metrics.track_request(f"external_{self.config.name}"):
            return await _call()

    def get_status(self) -> dict[str, Any]:
        """Get circuit breaker status."""
        return {
            "name": self.config.name,
            "state": self.breaker.state.value,
            "failure_count": self.breaker.failure_count,
            "failure_threshold": self.config.failure_threshold,
            "is_available": self.breaker.state != CircuitState.OPEN,
        }


# =============================================================================
# Distributed Circuit Breaker (Multi-Instance)
# =============================================================================


class DistributedCircuitBreakerExample:
    """
    Example using Redis-backed distributed circuit breaker.

    Use when:
    - Multiple instances/pods of the service
    - Need consistent circuit breaker state across all instances
    - Want faster failure detection (any pod can open the circuit)

    Benefits:
    - Shared state across all pods
    - One pod detecting failures opens circuit for all
    - Faster recovery from failures
    - Consistent behavior regardless of which pod handles request
    """

    def __init__(self, config: ServiceConfig, redis_client: Any):
        self.config = config
        self.redis_client = redis_client
        self.breaker = DistributedCircuitBreaker(
            name=config.name,
            redis_client=redis_client,
            failure_threshold=config.failure_threshold,
            recovery_timeout=config.recovery_timeout,
        )
        self.logger = get_logger(f"distributed-circuit-{config.name}")
        self.metrics = get_red_metrics()

    async def call_service(self, endpoint: str, data: dict[str, Any]) -> dict[str, Any]:
        """Call external service with distributed circuit breaker."""

        # Check circuit state from Redis
        async with self.breaker:
            self.logger.info(
                "calling_external_service",
                service=self.config.name,
                endpoint=endpoint,
                circuit_state=self.breaker.state.value,
            )

            with self.metrics.track_request(f"external_{self.config.name}"):
                # Simulate external call
                await asyncio.sleep(random.uniform(0.01, 0.1))

                # Simulate failures
                if random.random() < 0.2:
                    raise ConnectionError(f"Failed to connect to {self.config.name}")

                return {"status": "success", "data": data}

    async def get_status(self) -> dict[str, Any]:
        """Get distributed circuit breaker status from Redis."""
        # State is fetched from Redis, consistent across all pods
        return {
            "name": self.config.name,
            "state": self.breaker.state.value,
            "failure_count": self.breaker.failure_count,
            "failure_threshold": self.config.failure_threshold,
            "is_available": self.breaker.state != CircuitState.OPEN,
            "distributed": True,
        }


# =============================================================================
# Service Client with Fallbacks
# =============================================================================


class ResilientServiceClient:
    """
    Production-ready service client with circuit breaker and fallbacks.

    Features:
    - Distributed circuit breaker
    - Automatic retries with exponential backoff
    - Fallback responses when circuit is open
    - Metrics and logging
    """

    def __init__(self, config: ServiceConfig, redis_client: Any = None):
        self.config = config
        self.logger = get_logger(f"client-{config.name}")
        self.metrics = get_red_metrics()

        # Use distributed breaker if Redis is available
        if redis_client:
            self.breaker = DistributedCircuitBreaker(
                name=config.name,
                redis_client=redis_client,
                failure_threshold=config.failure_threshold,
                recovery_timeout=config.recovery_timeout,
            )
            self.is_distributed = True
        else:
            self.breaker = CircuitBreaker(
                name=config.name,
                failure_threshold=config.failure_threshold,
                recovery_timeout=config.recovery_timeout,
            )
            self.is_distributed = False

    async def call(
        self,
        endpoint: str,
        data: dict[str, Any],
        fallback: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Call service with circuit breaker, retry, and fallback.

        Args:
            endpoint: API endpoint to call
            data: Request data
            fallback: Response to return if circuit is open

        Returns:
            Service response or fallback
        """
        try:
            if self.is_distributed:
                async with self.breaker:
                    return await self._do_call(endpoint, data)
            else:

                @self.breaker
                async def protected_call():
                    return await self._do_call(endpoint, data)

                return await protected_call()

        except Exception as e:
            # Circuit is open or call failed
            self.logger.warning(
                "service_call_failed",
                service=self.config.name,
                endpoint=endpoint,
                error=str(e),
                circuit_state=self.breaker.state.value,
            )

            if fallback is not None:
                self.logger.info(
                    "using_fallback_response",
                    service=self.config.name,
                )
                return fallback

            raise

    @retry_async(max_attempts=3, base_delay=0.5, max_delay=5.0)
    async def _do_call(self, endpoint: str, data: dict[str, Any]) -> dict[str, Any]:
        """Execute the actual service call with retry."""
        with self.metrics.track_request(f"external_{self.config.name}"):
            # Simulate HTTP call
            await asyncio.sleep(random.uniform(0.01, 0.1))

            # Simulate failures
            if random.random() < 0.15:
                raise ConnectionError(f"Connection to {self.config.name} failed")

            return {"status": "success", "endpoint": endpoint, "data": data}


# =============================================================================
# Multi-Service Orchestration
# =============================================================================


class OrderProcessor:
    """
    Example order processor using multiple circuit breakers.

    This shows how to orchestrate calls to multiple services,
    each protected by its own circuit breaker.
    """

    def __init__(self, redis_client: Any = None):
        self.logger = get_logger("order-processor")
        self.metrics = get_red_metrics()

        # Initialize clients for each service
        self.payment_client = ResilientServiceClient(
            EXTERNAL_SERVICES["payment_gateway"],
            redis_client,
        )
        self.inventory_client = ResilientServiceClient(
            EXTERNAL_SERVICES["inventory_service"],
            redis_client,
        )
        self.notification_client = ResilientServiceClient(
            EXTERNAL_SERVICES["notification_service"],
            redis_client,
        )

    async def process_order(self, order: dict[str, Any]) -> dict[str, Any]:
        """
        Process an order with resilient service calls.

        Steps:
        1. Check inventory (required)
        2. Process payment (required)
        3. Send notification (optional, has fallback)
        """
        order_id = order.get("id", "unknown")

        self.logger.info("processing_order", order_id=order_id)

        with self.metrics.track_request("process_order"):
            # Step 1: Check inventory (required)
            inventory_result = await self.inventory_client.call(
                endpoint="/check",
                data={"items": order.get("items", [])},
            )

            if inventory_result.get("status") != "success":
                return {"status": "failed", "reason": "inventory_check_failed"}

            # Step 2: Process payment (required)
            payment_result = await self.payment_client.call(
                endpoint="/charge",
                data={
                    "amount": order.get("total", 0),
                    "customer_id": order.get("customer_id"),
                },
            )

            if payment_result.get("status") != "success":
                return {"status": "failed", "reason": "payment_failed"}

            # Step 3: Send notification (optional with fallback)
            notification_result = await self.notification_client.call(
                endpoint="/send",
                data={
                    "type": "order_confirmation",
                    "order_id": order_id,
                },
                fallback={
                    "status": "queued",
                    "message": "Notification will be sent later",
                },
            )

        self.logger.info(
            "order_processed",
            order_id=order_id,
            notification_status=notification_result.get("status"),
        )

        return {
            "status": "success",
            "order_id": order_id,
            "payment": payment_result,
            "notification": notification_result,
        }

    async def get_circuit_status(self) -> dict[str, Any]:
        """Get status of all circuit breakers."""
        return {
            "payment_gateway": {
                "state": self.payment_client.breaker.state.value,
                "distributed": self.payment_client.is_distributed,
            },
            "inventory_service": {
                "state": self.inventory_client.breaker.state.value,
                "distributed": self.inventory_client.is_distributed,
            },
            "notification_service": {
                "state": self.notification_client.breaker.state.value,
                "distributed": self.notification_client.is_distributed,
            },
        }


# =============================================================================
# Demo
# =============================================================================


async def demo():
    """Run circuit breaker demo."""
    configure(service_name="circuit-breaker-demo", environment="production")
    start_http_server(port=9090)

    print("\n" + "=" * 60)
    print("Distributed Circuit Breaker Demo")
    print("=" * 60)

    # In production, you would connect to Redis:
    # import redis.asyncio as redis
    # redis_client = redis.Redis(host='localhost', port=6379)

    # For demo, we use local circuit breakers
    processor = OrderProcessor(redis_client=None)

    print("\n📡 Processing orders with circuit breaker protection...")
    print("   (Simulating 15% failure rate on external services)")

    successful = 0
    failed = 0

    for i in range(50):
        order = {
            "id": f"order-{i + 1}",
            "customer_id": "customer-123",
            "items": [{"sku": "ITEM-001", "qty": 1}],
            "total": 99.99,
        }

        try:
            result = await processor.process_order(order)
            if result["status"] == "success":
                successful += 1
            else:
                failed += 1
        except Exception as e:
            failed += 1
            print(f"   Order {order['id']} failed: {e}")

        if i % 10 == 9:
            status = await processor.get_circuit_status()
            print(f"\n   After {i + 1} orders:")
            print(f"     Success: {successful}, Failed: {failed}")
            for service, state in status.items():
                print(f"     {service}: {state['state']}")

    print("\n" + "=" * 60)
    print("Final Circuit Breaker Status")
    print("=" * 60)

    final_status = await processor.get_circuit_status()
    for service, state in final_status.items():
        icon = "🟢" if state["state"] == "closed" else "🔴" if state["state"] == "open" else "🟡"
        print(f"  {icon} {service}: {state['state']}")

    print(f"\n📊 Results: {successful} successful, {failed} failed")
    print("   Metrics available at http://localhost:9090/metrics")

    print("\n" + "=" * 60)
    print("Redis Configuration for Production")
    print("=" * 60)
    print("""
To use distributed circuit breakers in production:

1. Install redis:
   pip install redis

2. For sync code:
   import redis
   redis_client = redis.Redis(host='redis', port=6379, db=0)

   breaker = DistributedCircuitBreaker(
       name="payment-gateway",
       redis_client=redis_client,
       failure_threshold=5,
       recovery_timeout=30.0,
   )

3. For async code:
   import redis.asyncio as redis
   redis_client = redis.Redis(host='redis', port=6379, db=0)

   # Same DistributedCircuitBreaker works with async Redis

4. Docker Compose:
   services:
     redis:
       image: redis:7-alpine
       ports:
         - "6379:6379"
""")


if __name__ == "__main__":
    asyncio.run(demo())
