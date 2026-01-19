# Quick Start Guide

Get obskit running in your production service in 5 minutes.

---

## Installation

```bash
# Full installation (recommended)
pip install obskit[all]

# Or minimal with specific features
pip install obskit[metrics,tracing,fastapi]
```

---

## FastAPI - Complete Example

```python
# app.py
from fastapi import FastAPI
from contextlib import asynccontextmanager
import os

from obskit import configure, shutdown, get_logger
from obskit.middleware.fastapi import ObskitMiddleware
from obskit.health import HealthChecker, create_health_response
from obskit.metrics import start_http_server

# =============================================================================
# 1. Configure obskit (do this FIRST)
# =============================================================================
configure(
    service_name=os.getenv("SERVICE_NAME", "my-api"),
    environment=os.getenv("ENVIRONMENT", "production"),
    version=os.getenv("VERSION", "1.0.0"),
    
    # Security (REQUIRED in production)
    metrics_auth_enabled=True,
    metrics_auth_token=os.getenv("METRICS_AUTH_TOKEN"),
    metrics_rate_limit_enabled=True,
    
    # Observability
    log_level="INFO",
    log_format="json",
    metrics_enabled=True,
    tracing_enabled=True,
    otlp_endpoint=os.getenv("OTLP_ENDPOINT", "http://jaeger:4317"),
    
    # Sampling (for high-traffic)
    metrics_sample_rate=0.1,
    trace_sample_rate=0.1,
)

# =============================================================================
# 2. Get logger
# =============================================================================
logger = get_logger(__name__)

# =============================================================================
# 3. Set up health checker
# =============================================================================
health_checker = HealthChecker()

# Add your dependency checks
@health_checker.add_readiness_check("database")
async def check_database():
    # Replace with your actual check
    return True

# =============================================================================
# 4. Create FastAPI app with lifecycle
# =============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("application_starting")
    start_http_server(port=9090)
    yield
    # Shutdown
    logger.info("application_stopping")
    shutdown()

app = FastAPI(title="My API", lifespan=lifespan)

# =============================================================================
# 5. Add observability middleware
# =============================================================================
app.add_middleware(
    ObskitMiddleware,
    excluded_paths=["/health", "/ready", "/live", "/metrics"],
)

# =============================================================================
# 6. Health endpoints
# =============================================================================
@app.get("/health")
async def health():
    result = await health_checker.check_health()
    return create_health_response(result)

@app.get("/ready")
async def ready():
    result = await health_checker.check_readiness()
    return create_health_response(result)

@app.get("/live")
async def live():
    result = await health_checker.check_liveness()
    return create_health_response(result)

# =============================================================================
# 7. Your business endpoints
# =============================================================================
@app.get("/api/orders/{order_id}")
async def get_order(order_id: str):
    logger.info("fetching_order", order_id=order_id)
    return {"order_id": order_id, "status": "completed"}

@app.post("/api/orders")
async def create_order(data: dict):
    logger.info("creating_order", data=data)
    return {"order_id": "new-123", "status": "created"}
```

---

## Flask - Complete Example

```python
# app.py
from flask import Flask, jsonify
import os

from obskit import configure, shutdown, get_logger
from obskit.middleware.flask import ObskitFlaskMiddleware
from obskit.health import HealthChecker, create_health_response
from obskit.metrics import start_http_server
import atexit

# Configure obskit
configure(
    service_name=os.getenv("SERVICE_NAME", "my-flask-api"),
    environment="production",
    metrics_auth_enabled=True,
    metrics_auth_token=os.getenv("METRICS_AUTH_TOKEN"),
)

logger = get_logger(__name__)
app = Flask(__name__)

# Add middleware
ObskitFlaskMiddleware(
    app,
    excluded_paths=["/health", "/ready", "/live"],
)

# Health checker
health_checker = HealthChecker()

@health_checker.add_readiness_check("database")
async def check_database():
    return True

# Health endpoints
@app.route("/health")
async def health():
    result = await health_checker.check_health()
    response = create_health_response(result)
    return jsonify(response)

@app.route("/ready")
async def ready():
    result = await health_checker.check_readiness()
    response = create_health_response(result)
    return jsonify(response)

# Business endpoints
@app.route("/api/orders/<order_id>")
def get_order(order_id):
    logger.info("fetching_order", order_id=order_id)
    return jsonify({"order_id": order_id})

# Startup
start_http_server(port=9090)

# Cleanup on shutdown
atexit.register(shutdown)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
```

---

## Environment Variables

Set these in production:

```bash
# Required
export SERVICE_NAME="my-service"
export ENVIRONMENT="production"
export METRICS_AUTH_TOKEN="$(openssl rand -base64 32)"

# Optional
export OTLP_ENDPOINT="http://jaeger:4317"
export VERSION="1.0.0"
```

---

## Verify It Works

```bash
# Start your service
uvicorn app:app --host 0.0.0.0 --port 8080

# Check health
curl http://localhost:8080/health

# Check metrics (with auth)
curl -H "Authorization: Bearer $METRICS_AUTH_TOKEN" http://localhost:9090/metrics

# Make a request and see logs
curl http://localhost:8080/api/orders/123
```

---

## What You Get

After setup, you automatically get:

| Feature | Endpoint/Output |
|---------|-----------------|
| Prometheus metrics | `http://localhost:9090/metrics` |
| Structured JSON logs | stdout |
| Health checks | `/health`, `/ready`, `/live` |
| Request tracing | OTLP export to Jaeger |
| Correlation IDs | Automatic propagation |
| Error tracking | Automatic in metrics |

---

## Next Steps

1. **[Configuration Reference](02_CONFIGURATION.md)** - All 40+ settings
2. **[Metrics Guide](03_METRICS.md)** - RED, Golden Signals, USE
3. **[Health Checks](04_HEALTH_CHECKS.md)** - Built-in checks
4. **[Resilience](05_RESILIENCE.md)** - Circuit breaker, retry
5. **[Security](07_SECURITY.md)** - Auth, rate limiting, PII
