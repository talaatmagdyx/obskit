#!/usr/bin/env python3
"""
Example Service Implementation with obskit
==========================================
This is a complete example service that uses obskit for observability.
This service would be containerized and deployed using the Helm chart.
"""

from fastapi import FastAPI, HTTPException
import os
import asyncio

# obskit imports
from obskit import configure, shutdown, get_logger
from obskit.middleware.fastapi import ObskitMiddleware
from obskit.health import HealthChecker, create_health_response
from obskit.metrics import start_http_server, REDMetrics
from obskit.resilience import CircuitBreaker, retry_async

# Configure obskit from environment variables (set by Helm)
configure(
    service_name=os.getenv("OBSKIT_SERVICE_NAME", "order-service"),
    environment=os.getenv("OBSKIT_ENVIRONMENT", "production"),
    version=os.getenv("OBSKIT_VERSION", "1.0.0"),
    log_level=os.getenv("OBSKIT_LOG_LEVEL", "INFO"),
    log_format=os.getenv("OBSKIT_LOG_FORMAT", "json"),
    metrics_enabled=os.getenv("OBSKIT_METRICS_ENABLED", "true").lower() == "true",
    tracing_enabled=os.getenv("OBSKIT_TRACING_ENABLED", "true").lower() == "true",
)

# Get logger
logger = get_logger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Order Service",
    description="Example service using obskit",
    version=os.getenv("OBSKIT_VERSION", "1.0.0"),
)

# Add obskit middleware (automatic observability)
app.add_middleware(ObskitMiddleware)

# Health checker
checker = HealthChecker()

# Circuit breaker for external API
payment_breaker = CircuitBreaker(
    name="payment_api",
    failure_threshold=5,
    recovery_timeout=30.0,
)

# Metrics
red_metrics = REDMetrics("order_service")


# Health check endpoints
@app.get("/health")
async def health():
    """Health check endpoint."""
    result = await checker.check_health()
    return create_health_response(result)


@app.get("/ready")
async def ready():
    """Readiness check endpoint."""
    result = await checker.check_readiness()
    return create_health_response(result)


@app.get("/live")
async def live():
    """Liveness check endpoint."""
    result = await checker.check_liveness()
    return create_health_response(result)


# Business logic endpoints
@app.post("/orders")
async def create_order(order_data: dict):
    """Create a new order."""
    logger.info("creating_order", order_id=order_data.get("id"))
    
    try:
        # Track with RED metrics
        with red_metrics.track_request("create_order"):
            # Simulate order creation
            order_id = f"order-{order_data.get('id', '123')}"
            
            # Process payment with circuit breaker
            async with payment_breaker:
                payment_result = await process_payment(order_id, order_data.get("amount", 0))
            
            logger.info("order_created", order_id=order_id, payment_id=payment_result["id"])
            
            return {
                "order_id": order_id,
                "status": "created",
                "payment": payment_result,
            }
    
    except Exception as e:
        logger.error("order_creation_failed", error=str(e), error_type=type(e).__name__)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/orders/{order_id}")
async def get_order(order_id: str):
    """Get order by ID."""
    logger.info("getting_order", order_id=order_id)
    
    with red_metrics.track_request("get_order"):
        # Simulate database lookup
        await asyncio.sleep(0.1)
        
        return {
            "order_id": order_id,
            "status": "completed",
            "amount": 100.0,
        }


@retry_async(max_attempts=3, base_delay=1.0)
async def process_payment(order_id: str, amount: float) -> dict:
    """Process payment with retry."""
    logger.info("processing_payment", order_id=order_id, amount=amount)
    
    # Simulate payment processing
    await asyncio.sleep(0.2)
    
    return {
        "id": f"payment-{order_id}",
        "status": "completed",
        "amount": amount,
    }


# Startup event
@app.on_event("startup")
async def startup():
    """Startup event handler."""
    logger.info("service_starting")
    
    # Start metrics HTTP server (if not already started)
    metrics_port = int(os.getenv("OBSKIT_METRICS_PORT", "9090"))
    if os.getenv("OBSKIT_METRICS_ENABLED", "true").lower() == "true":
        start_http_server(port=metrics_port)
        logger.info("metrics_server_started", port=metrics_port)
    
    # Register health checks
    @checker.add_readiness_check("database")
    async def check_database():
        # Check database connection
        return True
    
    @checker.add_readiness_check("cache")
    async def check_cache():
        # Check cache connection
        return True
    
    logger.info("service_started")


# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown event handler."""
    logger.info("service_shutting_down")
    shutdown()


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", "8080"))
    logger.info("starting_service", port=port)
    uvicorn.run(app, host="0.0.0.0", port=port)

