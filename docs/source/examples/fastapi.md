# FastAPI Integration

Complete example of integrating obskit with FastAPI.

## Full Example

```python
"""
Complete FastAPI application with obskit observability.
"""
import asyncio
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import FastAPI, HTTPException, Depends, Header
from pydantic import BaseModel

from obskit import (
    configure_logging,
    configure_tracing,
    get_red_metrics,
    get_health_checker,
    start_http_server,
    CircuitBreaker,
    retry_async,
)
from obskit.middleware import ObskitMiddleware
from obskit.core import set_correlation_id, set_tenant_id


# =============================================================================
# Configuration
# =============================================================================

SERVICE_NAME = "user-service"
METRICS_PORT = 9090

# Initialize observability
logger = configure_logging(
    service_name=SERVICE_NAME,
    log_level="INFO",
    pii_redaction=True,
)

# Optional: Enable tracing
# tracer = configure_tracing(
#     service_name=SERVICE_NAME,
#     otlp_endpoint="http://jaeger:4317",
# )

metrics = get_red_metrics(service_name=SERVICE_NAME)
health = get_health_checker()

# Circuit breaker for external services
payment_breaker = CircuitBreaker(
    failure_threshold=5,
    recovery_timeout=30.0,
)


# =============================================================================
# Models
# =============================================================================

class User(BaseModel):
    id: int
    name: str
    email: str


class CreateUserRequest(BaseModel):
    name: str
    email: str


class OrderRequest(BaseModel):
    user_id: int
    amount: float


# =============================================================================
# Database (Simulated)
# =============================================================================

USERS_DB: dict[int, User] = {
    1: User(id=1, name="Alice", email="alice@example.com"),
    2: User(id=2, name="Bob", email="bob@example.com"),
}


async def check_database() -> bool:
    """Simulated database health check."""
    await asyncio.sleep(0.01)
    return True


# =============================================================================
# External Service
# =============================================================================

@retry_async(max_attempts=3, base_delay=0.5)
async def process_payment(user_id: int, amount: float) -> dict:
    """Process payment with retry and circuit breaker."""
    async with payment_breaker:
        # Simulate external API call
        await asyncio.sleep(0.1)
        logger.info("Payment processed", user_id=user_id, amount=amount)
        return {"status": "success", "transaction_id": f"txn_{user_id}_{amount}"}


# =============================================================================
# Dependencies
# =============================================================================

async def get_correlation_id(
    x_request_id: Annotated[str | None, Header()] = None,
) -> str:
    """Extract or generate correlation ID."""
    import uuid
    correlation_id = x_request_id or str(uuid.uuid4())
    set_correlation_id(correlation_id)
    return correlation_id


async def get_tenant_id(
    x_tenant_id: Annotated[str | None, Header()] = None,
) -> str | None:
    """Extract tenant ID from header."""
    if x_tenant_id:
        set_tenant_id(x_tenant_id)
    return x_tenant_id


# =============================================================================
# Lifecycle
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle manager."""
    logger.info("Starting service", service=SERVICE_NAME)
    
    # Register health checks
    health.add_liveness_check("basic", lambda: True)
    health.add_readiness_check("database", check_database)
    
    # Start metrics server
    start_http_server(port=METRICS_PORT)
    logger.info("Metrics server started", port=METRICS_PORT)
    
    yield
    
    logger.info("Shutting down service")


# =============================================================================
# Application
# =============================================================================

app = FastAPI(
    title=SERVICE_NAME,
    version="1.0.0",
    lifespan=lifespan,
)

# Add observability middleware
app.add_middleware(ObskitMiddleware, metrics=metrics)


# =============================================================================
# Health Endpoints
# =============================================================================

@app.get("/health", tags=["Health"])
async def liveness():
    """Liveness probe - is the application running?"""
    return {"status": "healthy"}


@app.get("/ready", tags=["Health"])
async def readiness():
    """Readiness probe - can the application serve traffic?"""
    result = await health.check_readiness()
    
    if result.status.value != "healthy":
        raise HTTPException(status_code=503, detail=result.checks)
    
    return {"status": "ready", "checks": result.checks}


# =============================================================================
# User Endpoints
# =============================================================================

@app.get("/users", response_model=list[User], tags=["Users"])
async def list_users(
    correlation_id: str = Depends(get_correlation_id),
    tenant_id: str | None = Depends(get_tenant_id),
):
    """List all users."""
    logger.info("Listing users", count=len(USERS_DB))
    return list(USERS_DB.values())


@app.get("/users/{user_id}", response_model=User, tags=["Users"])
async def get_user(
    user_id: int,
    correlation_id: str = Depends(get_correlation_id),
):
    """Get a specific user."""
    if user_id not in USERS_DB:
        logger.warning("User not found", user_id=user_id)
        raise HTTPException(status_code=404, detail="User not found")
    
    logger.info("User retrieved", user_id=user_id)
    return USERS_DB[user_id]


@app.post("/users", response_model=User, status_code=201, tags=["Users"])
async def create_user(
    request: CreateUserRequest,
    correlation_id: str = Depends(get_correlation_id),
):
    """Create a new user."""
    new_id = max(USERS_DB.keys()) + 1
    user = User(id=new_id, **request.model_dump())
    USERS_DB[new_id] = user
    
    logger.info("User created", user_id=new_id, name=request.name)
    return user


# =============================================================================
# Order Endpoints
# =============================================================================

@app.post("/orders", tags=["Orders"])
async def create_order(
    request: OrderRequest,
    correlation_id: str = Depends(get_correlation_id),
):
    """Create an order with payment processing."""
    if request.user_id not in USERS_DB:
        raise HTTPException(status_code=404, detail="User not found")
    
    try:
        payment_result = await process_payment(request.user_id, request.amount)
        logger.info(
            "Order created",
            user_id=request.user_id,
            amount=request.amount,
            transaction_id=payment_result["transaction_id"],
        )
        return {
            "status": "success",
            "order_id": f"ord_{request.user_id}",
            "payment": payment_result,
        }
    except Exception as e:
        logger.error(
            "Order creation failed",
            user_id=request.user_id,
            error=str(e),
        )
        raise HTTPException(status_code=500, detail="Payment processing failed")


# =============================================================================
# Run: uvicorn main:app --reload
# Metrics: http://localhost:9090/metrics
# =============================================================================
```

## Running the Example

```bash
# Install dependencies
pip install fastapi uvicorn obskit[all]

# Run the application
uvicorn main:app --reload --port 8000

# Test endpoints
curl http://localhost:8000/health
curl http://localhost:8000/users
curl -X POST http://localhost:8000/users \
  -H "Content-Type: application/json" \
  -d '{"name": "Charlie", "email": "charlie@example.com"}'

# View metrics
curl http://localhost:9090/metrics
```

## Middleware Details

The `ObskitMiddleware` automatically:

- Extracts trace context from incoming headers
- Sets correlation ID
- Records request duration and status
- Logs request start/end

```python
from obskit.middleware import ObskitMiddleware

app.add_middleware(
    ObskitMiddleware,
    metrics=metrics,
    exclude_paths=["/health", "/ready", "/metrics"],
)
```

## Custom Metrics

Add custom business metrics:

```python
from prometheus_client import Counter, Histogram
from obskit.metrics import get_registry

registry = get_registry()

orders_total = Counter(
    "orders_total",
    "Total orders by status",
    ["status"],
    registry=registry,
)

order_amount = Histogram(
    "order_amount_dollars",
    "Order amounts in dollars",
    buckets=[10, 50, 100, 500, 1000, 5000],
    registry=registry,
)

@app.post("/orders")
async def create_order(request: OrderRequest):
    try:
        result = await process_order(request)
        orders_total.labels(status="success").inc()
        order_amount.observe(request.amount)
        return result
    except Exception:
        orders_total.labels(status="error").inc()
        raise
```

## Next Steps

- **[Kubernetes Deployment](kubernetes.md)** - Deploy to production
- **[Helm Chart](helm.md)** - Use the obskit Helm chart
- **[Configuration](../config/index.md)** - All configuration options

