#!/usr/bin/env python3
"""
FastAPI Integration Example
===========================

This example shows how to integrate obskit with a FastAPI application.

Run with:
    uvicorn fastapi_example:app --reload

Endpoints:
    GET  /                  - Welcome message
    GET  /health           - Health check
    GET  /ready            - Readiness check
    GET  /live             - Liveness check
    POST /orders           - Create an order
    GET  /orders/{id}      - Get an order
    GET  /metrics          - Prometheus metrics (internal redirect)

Requirements:
    pip install fastapi uvicorn obskit[all]
"""

import asyncio
import random
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# =============================================================================
# obskit imports
# =============================================================================
from obskit import configure, get_logger, start_http_server
from obskit.core import correlation_context
from obskit.decorators import with_observability
from obskit.health import HealthChecker
from obskit.metrics import GoldenSignals, REDMetrics
from obskit.resilience import (
    CircuitBreaker,
    CircuitOpenError,
    RateLimiter,
    RateLimitExceeded,
)

# =============================================================================
# Configuration
# =============================================================================

# Configure obskit
configure(
    service_name="order-api",
    environment="development",
    version="1.0.0",
    log_level="INFO",
    log_format="console",
)

# Get logger
logger = get_logger(__name__)


# =============================================================================
# Models
# =============================================================================


class OrderCreate(BaseModel):
    """Order creation request model."""

    customer_id: str
    items: list[str]
    total: float


class OrderResponse(BaseModel):
    """Order response model."""

    id: str
    customer_id: str
    items: list[str]
    total: float
    status: str


# =============================================================================
# Metrics
# =============================================================================

red_metrics = REDMetrics("order_api")
golden_metrics = GoldenSignals("order_api")


# =============================================================================
# Health Checks
# =============================================================================

health_checker = HealthChecker()


@health_checker.add_readiness_check("database")
async def check_database():
    """Check database connection."""
    await asyncio.sleep(0.01)
    return True


@health_checker.add_readiness_check("cache", critical=False)
async def check_cache():
    """Check cache connection (non-critical)."""
    await asyncio.sleep(0.005)
    return random.random() > 0.1


@health_checker.add_liveness_check("memory")
async def check_memory():
    """Check memory usage."""
    return True


# =============================================================================
# Resilience
# =============================================================================

# Circuit breaker for external payment service
payment_breaker = CircuitBreaker(
    name="payment_service",
    failure_threshold=5,
    recovery_timeout=30.0,
)

# Rate limiter for API
api_limiter = RateLimiter(requests=100, window_seconds=60)


# =============================================================================
# Simulated Services
# =============================================================================

# In-memory order storage
orders_db: dict[str, dict[str, Any]] = {}


async def save_order(order_data: dict) -> dict:
    """Simulate saving order to database."""
    await asyncio.sleep(0.02)
    order_id = f"ord-{random.randint(10000, 99999)}"
    order = {
        "id": order_id,
        **order_data,
        "status": "pending",
    }
    orders_db[order_id] = order
    return order


async def get_order(order_id: str) -> dict | None:
    """Simulate getting order from database."""
    await asyncio.sleep(0.01)
    return orders_db.get(order_id)


async def process_payment(order_id: str, amount: float) -> dict:
    """Simulate payment processing."""
    await asyncio.sleep(random.uniform(0.1, 0.3))
    if random.random() < 0.2:
        raise TimeoutError("Payment service timeout")
    return {"success": True, "transaction_id": f"txn-{random.randint(1000, 9999)}"}


# =============================================================================
# Application Lifespan
# =============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown."""
    # Startup
    logger.info("application_starting")

    # Start metrics server
    start_http_server(port=9091)
    logger.info("metrics_server_started", port=9091)

    yield

    # Shutdown
    logger.info("application_stopping")


# =============================================================================
# FastAPI Application
# =============================================================================

app = FastAPI(
    title="Order API",
    description="Example API with obskit observability",
    version="1.0.0",
    lifespan=lifespan,
)


# =============================================================================
# Middleware
# =============================================================================


@app.middleware("http")
async def correlation_middleware(request: Request, call_next):
    """
    Add correlation ID to each request.

    Extracts X-Correlation-ID from request headers or generates a new one.
    Adds the correlation ID to response headers.
    """
    # Get correlation ID from request or generate new one
    client_correlation_id = request.headers.get("X-Correlation-ID")

    async with correlation_context(client_correlation_id) as cid:
        # Add correlation ID to request state for access in handlers
        request.state.correlation_id = cid

        # Log request start
        logger.info(
            "request_started",
            method=request.method,
            path=request.url.path,
            client_ip=request.client.host if request.client else None,
        )

        # Process request
        response = await call_next(request)

        # Add correlation ID to response
        response.headers["X-Correlation-ID"] = cid

        # Log request completion
        logger.info(
            "request_completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
        )

        return response


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """
    Apply rate limiting to API requests.

    Returns 429 Too Many Requests when limit exceeded.
    """
    # Skip rate limiting for health endpoints
    if request.url.path in ["/health", "/ready", "/live"]:
        return await call_next(request)

    try:
        async with api_limiter:
            return await call_next(request)
    except RateLimitExceeded as e:
        logger.warning(
            "rate_limit_exceeded",
            path=request.url.path,
            retry_after=e.retry_after,
        )
        return JSONResponse(
            status_code=429,
            content={
                "error": "Too Many Requests",
                "retry_after": int(e.retry_after),
            },
            headers={"Retry-After": str(int(e.retry_after))},
        )


# =============================================================================
# Health Endpoints
# =============================================================================


@app.get("/health")
async def health():
    """
    Health check endpoint.

    Returns overall service health including all checks.
    """
    result = await health_checker.check_health()
    return Response(
        content=result.to_json(),
        status_code=200 if result.healthy else 503,
        media_type="application/json",
    )


@app.get("/ready")
async def ready():
    """
    Readiness probe endpoint.

    Returns whether service is ready to accept traffic.
    Used by Kubernetes for load balancer routing.
    """
    result = await health_checker.check_readiness()
    return Response(
        content=result.to_json(),
        status_code=200 if result.healthy else 503,
        media_type="application/json",
    )


@app.get("/live")
async def live():
    """
    Liveness probe endpoint.

    Returns whether the process is alive.
    Used by Kubernetes to determine if pod should be restarted.
    """
    result = await health_checker.check_liveness()
    return Response(
        content=result.to_json(),
        status_code=200 if result.healthy else 503,
        media_type="application/json",
    )


# =============================================================================
# API Endpoints
# =============================================================================


@app.get("/")
async def root():
    """Welcome endpoint."""
    return {
        "service": "order-api",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }


@with_observability(component="OrderAPI", threshold_ms=200.0)
async def _create_order(order_data: dict) -> dict:
    """Internal order creation with observability."""
    logger.info("creating_order", customer_id=order_data["customer_id"])

    # Save order
    order = await save_order(order_data)

    # Process payment with circuit breaker
    try:
        async with payment_breaker:
            payment = await process_payment(order["id"], order["total"])
            order["status"] = "completed" if payment["success"] else "payment_failed"
    except CircuitOpenError as e:
        logger.warning(
            "payment_circuit_open",
            order_id=order["id"],
            retry_after=e.time_until_retry,
        )
        order["status"] = "payment_pending"
    except Exception as e:
        logger.error(
            "payment_failed",
            order_id=order["id"],
            error=str(e),
        )
        order["status"] = "payment_failed"

    # Update in "database"
    orders_db[order["id"]] = order

    logger.info("order_created", order_id=order["id"], status=order["status"])
    return order


@app.post("/orders", response_model=OrderResponse)
async def create_order(order: OrderCreate, request: Request):
    """
    Create a new order.

    This endpoint demonstrates:
    - Request validation with Pydantic
    - Observability decorator
    - Circuit breaker for payment
    - Structured logging
    - Correlation ID propagation
    """
    try:
        result = await _create_order(order.model_dump())
        return OrderResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(
            "order_creation_failed",
            error=str(e),
            error_type=type(e).__name__,
        )
        raise HTTPException(status_code=500, detail="Internal server error") from None


@app.get("/orders/{order_id}", response_model=OrderResponse)
async def get_order_by_id(order_id: str, request: Request):
    """
    Get an order by ID.

    Returns 404 if order not found.
    """
    logger.debug("getting_order", order_id=order_id)

    with red_metrics.track_request("get_order"):
        order = await get_order(order_id)

        if not order:
            logger.warning("order_not_found", order_id=order_id)
            raise HTTPException(status_code=404, detail="Order not found")

        return OrderResponse(**order)


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    import uvicorn

    print("\n" + "=" * 60)
    print("🚀 Starting Order API with obskit observability")
    print("=" * 60)
    print()
    print("Endpoints:")
    print("  GET  http://localhost:8000/        - Welcome")
    print("  GET  http://localhost:8000/docs    - API docs")
    print("  GET  http://localhost:8000/health  - Health check")
    print("  GET  http://localhost:8000/ready   - Readiness")
    print("  GET  http://localhost:8000/live    - Liveness")
    print("  POST http://localhost:8000/orders  - Create order")
    print("  GET  http://localhost:8000/orders/{id} - Get order")
    print()
    print("Metrics: http://localhost:9091/metrics")
    print()

    uvicorn.run(
        "fastapi_example:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
