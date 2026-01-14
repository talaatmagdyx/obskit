#!/usr/bin/env python3
"""
Example Service - Complete obskit Demonstration
===============================================

This example demonstrates all obskit features in a realistic service context.
Run this file to see obskit in action:

    python example_service.py

Features Demonstrated
---------------------
1. Configuration via environment variables
2. Structured logging with correlation IDs
3. RED metrics (Rate, Errors, Duration)
4. Four Golden Signals
5. USE Method for infrastructure
6. Health checks (readiness, liveness)
7. Circuit breaker for external APIs
8. Retry with exponential backoff
9. Rate limiting
10. Context propagation

Requirements
------------
Install obskit with all dependencies:

    pip install obskit[all]

Or for development:

    cd obskit
    pip install -e ".[all]"
"""

import asyncio
import random
from dataclasses import dataclass

# =============================================================================
# obskit imports
# =============================================================================
# Core
from obskit import configure, get_logger, start_http_server
from obskit.core import correlation_context

# Decorators
from obskit.decorators import track_metrics_only, track_operation, with_observability

# Health
from obskit.health import HealthChecker

# Metrics
from obskit.metrics import GoldenSignals, REDMetrics, USEMetrics

# Resilience
from obskit.resilience import (
    CircuitBreaker,
    CircuitOpenError,
    RateLimiter,
    RateLimitExceeded,
    RetryError,
    retry,
)

# =============================================================================
# Configuration
# =============================================================================

# Configure obskit at startup
configure(
    service_name="example-order-service",
    environment="development",
    version="1.0.0",
    log_level="DEBUG",
    log_format="console",  # Use "json" for production
    # Resilience settings
    circuit_breaker_failure_threshold=3,
    circuit_breaker_recovery_timeout=10.0,
    retry_max_attempts=3,
    retry_base_delay=0.5,
    rate_limit_requests=10,
    rate_limit_window_seconds=10,
)

# Get logger
logger = get_logger(__name__)

# =============================================================================
# Metrics Setup
# =============================================================================

# RED metrics for our service
red_metrics = REDMetrics("order_service")

# Golden Signals for comprehensive monitoring
golden_metrics = GoldenSignals("order_service")

# USE metrics for infrastructure
cpu_metrics = USEMetrics("system_cpu")
memory_metrics = USEMetrics("system_memory")

# =============================================================================
# Health Checks
# =============================================================================

health_checker = HealthChecker()


@health_checker.add_readiness_check("database")
async def check_database():
    """Check database connectivity."""
    # Simulate database check
    await asyncio.sleep(0.01)
    return random.random() > 0.1  # 90% healthy


@health_checker.add_readiness_check("redis", critical=False)
async def check_redis():
    """Check Redis connectivity (non-critical)."""
    await asyncio.sleep(0.005)
    return random.random() > 0.2  # 80% healthy


@health_checker.add_liveness_check("memory")
async def check_memory():
    """Check memory usage."""
    # Simulate memory check
    return True  # Always healthy for demo


# =============================================================================
# Resilience Patterns
# =============================================================================

# Circuit breaker for payment API
payment_circuit = CircuitBreaker(
    name="payment_api",
    failure_threshold=3,
    recovery_timeout=10.0,
)

# Rate limiter for API calls
api_rate_limiter = RateLimiter(requests=10, window_seconds=10)


# =============================================================================
# Domain Objects
# =============================================================================


@dataclass
class Order:
    """Example order domain object."""

    id: str
    customer_id: str
    items: list[str]
    total: float
    status: str = "pending"


# =============================================================================
# Simulated External Services
# =============================================================================


async def simulate_database_call(duration: float = 0.05, fail_rate: float = 0.1):
    """Simulate a database call."""
    await asyncio.sleep(duration)
    if random.random() < fail_rate:
        raise ConnectionError("Database connection failed")
    return True


async def simulate_payment_api(amount: float, fail_rate: float = 0.3):
    """Simulate payment API call (intentionally flaky for demo)."""
    await asyncio.sleep(random.uniform(0.1, 0.3))
    if random.random() < fail_rate:
        raise TimeoutError("Payment API timeout")
    return {"success": True, "transaction_id": f"txn-{random.randint(1000, 9999)}"}


async def simulate_notification_service():
    """Simulate notification service."""
    await asyncio.sleep(0.02)
    return True


# =============================================================================
# Service Functions with Observability
# =============================================================================


@with_observability(
    component="OrderService",
    operation="create_order",
    threshold_ms=200.0,
)
async def create_order(order_data: dict) -> Order:
    """
    Create a new order.

    This function demonstrates the @with_observability decorator which:
    1. Logs operation start/completion/failure
    2. Records RED metrics
    3. Warns if duration exceeds threshold
    4. Propagates correlation IDs
    """
    logger.info("creating_order", order_data=order_data)

    # Validate
    if not order_data.get("customer_id"):
        raise ValueError("customer_id is required")

    # Simulate database insert
    await simulate_database_call()

    order = Order(
        id=f"ord-{random.randint(1000, 9999)}",
        customer_id=order_data["customer_id"],
        items=order_data.get("items", []),
        total=order_data.get("total", 0.0),
    )

    logger.info("order_created", order_id=order.id)
    return order


@track_operation(component="OrderService")
async def validate_order(order: Order) -> bool:
    """
    Validate an order.

    Uses @track_operation for lightweight logging without metrics.
    Good for internal helper functions.
    """
    logger.debug("validating_order", order_id=order.id)
    await asyncio.sleep(0.01)
    return order.total > 0 and len(order.items) > 0


@track_metrics_only(component="CacheService")
async def get_cached_price(item_id: str) -> float:
    """
    Get cached price for an item.

    Uses @track_metrics_only for high-frequency operations.
    Records metrics without logging to avoid noise.
    """
    await asyncio.sleep(0.005)
    return random.uniform(10.0, 100.0)


@retry(max_attempts=3, base_delay=0.5, retry_on=(TimeoutError,))
async def process_payment_with_retry(order: Order) -> dict:
    """
    Process payment with automatic retry.

    Uses @retry decorator with exponential backoff.
    Only retries on TimeoutError, not on other exceptions.
    """
    logger.info("processing_payment", order_id=order.id, amount=order.total)
    return await simulate_payment_api(order.total, fail_rate=0.3)


async def process_payment_with_circuit_breaker(order: Order) -> dict:
    """
    Process payment with circuit breaker protection.

    The circuit breaker prevents cascading failures when
    the payment API is down.
    """
    try:
        async with payment_circuit:
            return await simulate_payment_api(order.total, fail_rate=0.5)
    except CircuitOpenError as e:
        logger.warning(
            "payment_circuit_open",
            breaker=e.breaker_name,
            retry_after=e.time_until_retry,
        )
        # Use fallback
        return {"success": False, "error": "Payment service unavailable"}


async def process_with_rate_limit():
    """
    Process request with rate limiting.

    Prevents overwhelming downstream services.
    """
    try:
        async with api_rate_limiter:
            await asyncio.sleep(0.01)
            return {"success": True}
    except RateLimitExceeded as e:
        logger.warning(
            "rate_limit_exceeded",
            limit=e.limit,
            retry_after=e.retry_after,
        )
        return {"success": False, "error": "Rate limit exceeded"}


# =============================================================================
# Business Logic Functions
# =============================================================================


async def process_complete_order(order_data: dict) -> dict:
    """
    Process a complete order flow demonstrating all features.
    """
    async with correlation_context() as correlation_id:
        logger.info(
            "order_flow_started",
            correlation_id=correlation_id,
            customer_id=order_data.get("customer_id"),
        )

        try:
            # Step 1: Create order
            order = await create_order(order_data)

            # Step 2: Validate
            is_valid = await validate_order(order)
            if not is_valid:
                raise ValueError("Order validation failed")

            # Step 3: Get prices (high-frequency, metrics only)
            prices = []
            for item in order.items[:3]:  # Limit for demo
                price = await get_cached_price(item)
                prices.append(price)

            # Step 4: Process payment with circuit breaker
            payment_result = await process_payment_with_circuit_breaker(order)

            if payment_result.get("success"):
                order.status = "completed"
                logger.info(
                    "order_flow_completed",
                    order_id=order.id,
                    status=order.status,
                )
            else:
                order.status = "payment_failed"
                logger.warning(
                    "order_payment_failed",
                    order_id=order.id,
                    error=payment_result.get("error"),
                )

            return {
                "order": order,
                "payment": payment_result,
                "correlation_id": correlation_id,
            }

        except Exception as e:
            logger.error(
                "order_flow_failed",
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True,
            )
            raise


# =============================================================================
# Infrastructure Monitoring
# =============================================================================


async def collect_infrastructure_metrics():
    """
    Collect USE metrics for infrastructure.

    In production, you'd use psutil or similar.
    """
    # Simulate CPU metrics
    cpu_utilization = random.uniform(0.3, 0.8)
    cpu_saturation = random.uniform(0, 5)

    cpu_metrics.set_utilization("cpu", cpu_utilization)
    cpu_metrics.set_saturation("cpu", cpu_saturation)

    # Simulate memory metrics
    memory_utilization = random.uniform(0.4, 0.7)
    memory_saturation = random.uniform(0, 0.2)

    memory_metrics.set_utilization("memory", memory_utilization)
    memory_metrics.set_saturation("memory", memory_saturation)

    # Update Golden Signals saturation
    golden_metrics.set_saturation("cpu", cpu_utilization)
    golden_metrics.set_saturation("memory", memory_utilization)


# =============================================================================
# Demo Runner
# =============================================================================


async def run_demo():
    """Run the demonstration."""

    print("\n" + "=" * 60)
    print("🔭 obskit Example Service Demo")
    print("=" * 60 + "\n")

    # Start metrics server
    print("📊 Starting metrics server on port 9090...")
    try:
        start_http_server(port=9090)
        print("   Metrics available at: http://localhost:9090/metrics\n")
    except Exception as e:
        print(f"   Could not start metrics server: {e}\n")

    # ==========================================================================
    # Demo 1: Basic Order Processing
    # ==========================================================================
    print("-" * 60)
    print("1. Basic Order Processing (with observability decorator)")
    print("-" * 60)

    try:
        result = await process_complete_order(
            {
                "customer_id": "cust-123",
                "items": ["widget", "gadget", "gizmo"],
                "total": 99.99,
            }
        )
        print(f"   ✓ Order created: {result['order'].id}")
        print(f"   ✓ Status: {result['order'].status}")
        print(f"   ✓ Correlation ID: {result['correlation_id']}")
    except Exception as e:
        print(f"   ✗ Error: {e}")

    print()

    # ==========================================================================
    # Demo 2: Retry with Backoff
    # ==========================================================================
    print("-" * 60)
    print("2. Retry with Exponential Backoff")
    print("-" * 60)

    order = Order(id="ord-retry", customer_id="cust-456", items=["test"], total=50.0)
    try:
        result = await process_payment_with_retry(order)
        print(f"   ✓ Payment succeeded: {result}")
    except RetryError as e:
        print(f"   ✗ All retries exhausted after {e.attempts} attempts")
    except Exception as e:
        print(f"   ✗ Error: {e}")

    print()

    # ==========================================================================
    # Demo 3: Circuit Breaker
    # ==========================================================================
    print("-" * 60)
    print("3. Circuit Breaker Pattern")
    print("-" * 60)
    print(f"   Initial state: {payment_circuit.state.value}")

    for i in range(7):
        order = Order(id=f"ord-cb-{i}", customer_id="cust-789", items=["test"], total=25.0)
        result = await process_payment_with_circuit_breaker(order)
        status = "success" if result.get("success") else "failed"
        print(f"   Request {i + 1}: {status} | Circuit: {payment_circuit.state.value}")

    print()

    # ==========================================================================
    # Demo 4: Rate Limiting
    # ==========================================================================
    print("-" * 60)
    print("4. Rate Limiting")
    print("-" * 60)

    successes = 0
    failures = 0
    for _ in range(15):
        result = await process_with_rate_limit()
        if result.get("success"):
            successes += 1
        else:
            failures += 1

    print(f"   Successes: {successes}, Rate limited: {failures}")
    print()

    # ==========================================================================
    # Demo 5: Health Checks
    # ==========================================================================
    print("-" * 60)
    print("5. Health Checks")
    print("-" * 60)

    health_result = await health_checker.check_health()
    print(f"   Overall status: {health_result.status.value}")
    for name, check in health_result.checks.items():
        status_icon = "✓" if check.healthy else "✗"
        print(f"   {status_icon} {name}: {check.status.value} ({check.duration_ms:.1f}ms)")

    print()

    # ==========================================================================
    # Demo 6: Infrastructure Metrics
    # ==========================================================================
    print("-" * 60)
    print("6. Infrastructure Metrics (USE Method)")
    print("-" * 60)

    await collect_infrastructure_metrics()
    print("   CPU utilization set")
    print("   Memory utilization set")
    print("   Golden Signals saturation updated")

    print()

    # ==========================================================================
    # Summary
    # ==========================================================================
    print("=" * 60)
    print("Demo Complete!")
    print("=" * 60)
    print()
    print("To explore the metrics:")
    print("  1. Visit http://localhost:9090/metrics")
    print("  2. Look for metrics like:")
    print("     - order_service_requests_total")
    print("     - order_service_request_duration_seconds")
    print("     - order_service_errors_total")
    print("     - system_cpu_utilization")
    print()
    print("To run with Docker (Prometheus + Grafana):")
    print("  cd docker && docker-compose up -d")
    print()


if __name__ == "__main__":
    asyncio.run(run_demo())
