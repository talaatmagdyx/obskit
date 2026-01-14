# Your First Observable App

Build a complete FastAPI application with full observability.

## Project Structure

```
my-service/
├── main.py
├── requirements.txt
└── docker-compose.yml
```

## requirements.txt

```text
fastapi>=0.109.0
uvicorn>=0.27.0
obskit[all]>=0.1.0
```

## main.py

```python
"""
A fully observable FastAPI service using obskit.
"""
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
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


# =============================================================================
# Configuration
# =============================================================================

SERVICE_NAME = "user-service"
METRICS_PORT = 9090

# Configure logging
logger = configure_logging(
    service_name=SERVICE_NAME,
    log_level="INFO",
)

# Configure tracing (optional - needs OTLP collector)
# configure_tracing(
#     service_name=SERVICE_NAME,
#     otlp_endpoint="http://jaeger:4317",
# )

# Configure metrics
metrics = get_red_metrics(service_name=SERVICE_NAME)

# Configure health checks
health = get_health_checker()

# Circuit breaker for external calls
external_api_breaker = CircuitBreaker(
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


# =============================================================================
# Simulated Database
# =============================================================================

USERS_DB: dict[int, User] = {
    1: User(id=1, name="Alice", email="alice@example.com"),
    2: User(id=2, name="Bob", email="bob@example.com"),
}


async def check_database() -> bool:
    """Simulated database health check."""
    await asyncio.sleep(0.01)  # Simulate DB ping
    return True


# =============================================================================
# External Service (Simulated)
# =============================================================================

@retry_async(max_attempts=3, base_delay=0.1)
async def call_external_api(user_id: int) -> dict:
    """Call external service with retry and circuit breaker."""
    async with external_api_breaker:
        # Simulate external API call
        await asyncio.sleep(0.05)
        return {"validated": True, "user_id": user_id}


# =============================================================================
# Application Lifecycle
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle manager."""
    # Startup
    logger.info("Starting service", service=SERVICE_NAME)
    
    # Register health checks
    health.add_liveness_check("basic", lambda: True)
    health.add_readiness_check("database", check_database)
    
    # Start metrics server
    start_http_server(port=METRICS_PORT)
    logger.info("Metrics server started", port=METRICS_PORT)
    
    yield
    
    # Shutdown
    logger.info("Shutting down service")


# =============================================================================
# FastAPI Application
# =============================================================================

app = FastAPI(
    title=SERVICE_NAME,
    version="1.0.0",
    lifespan=lifespan,
)

# Add observability middleware
app.add_middleware(ObskitMiddleware, metrics=metrics)


# =============================================================================
# Endpoints
# =============================================================================

@app.get("/health")
async def health_check():
    """Liveness probe."""
    return {"status": "healthy"}


@app.get("/ready")
async def readiness_check():
    """Readiness probe."""
    status = await health.check_readiness()
    if status.status.value != "healthy":
        raise HTTPException(status_code=503, detail=status.checks)
    return {"status": "ready", "checks": status.checks}


@app.get("/users", response_model=list[User])
async def list_users():
    """List all users."""
    logger.info("Listing users", count=len(USERS_DB))
    return list(USERS_DB.values())


@app.get("/users/{user_id}", response_model=User)
async def get_user(user_id: int):
    """Get a specific user."""
    if user_id not in USERS_DB:
        logger.warning("User not found", user_id=user_id)
        raise HTTPException(status_code=404, detail="User not found")
    
    # Call external API with circuit breaker
    try:
        validation = await call_external_api(user_id)
        logger.info("User validated", user_id=user_id, validation=validation)
    except Exception as e:
        logger.error("Validation failed", user_id=user_id, error=str(e))
    
    return USERS_DB[user_id]


@app.post("/users", response_model=User, status_code=201)
async def create_user(request: CreateUserRequest):
    """Create a new user."""
    new_id = max(USERS_DB.keys()) + 1
    user = User(id=new_id, **request.model_dump())
    USERS_DB[new_id] = user
    
    logger.info("User created", user_id=new_id, name=request.name)
    return user


# =============================================================================
# Run with: uvicorn main:app --reload
# =============================================================================
```

## docker-compose.yml

```yaml
version: "3.8"

services:
  app:
    build: .
    ports:
      - "8000:8000"
      - "9090:9090"
    environment:
      - OBSKIT_SERVICE_NAME=user-service
      - OBSKIT_LOG_LEVEL=INFO

  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9091:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    depends_on:
      - prometheus
```

## Running the Application

```bash
# Install dependencies
pip install -r requirements.txt

# Run the application
uvicorn main:app --reload

# Test endpoints
curl http://localhost:8000/users
curl http://localhost:8000/health
curl http://localhost:9090/metrics
```

## What You Get

1. **Structured Logs**: JSON-formatted logs with correlation IDs
2. **RED Metrics**: Request rate, error rate, and duration
3. **Health Checks**: Kubernetes-compatible liveness and readiness probes
4. **Circuit Breaker**: Automatic failure detection for external calls
5. **Automatic Retries**: Resilient external service calls

## Next Steps

- **[Concepts](../user-guide/concepts.md)** - Understand observability theory
- **[Kubernetes Deployment](../examples/kubernetes.md)** - Deploy to production
- **[Helm Chart](../examples/helm.md)** - Use the obskit Helm chart

