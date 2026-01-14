# FastAPI Integration Tutorial

Add full observability to a FastAPI application.

## Video Tutorial

<!-- Placeholder for asciinema embed -->
<div id="fastapi-demo">
<p><em>Record this tutorial: <code>asciinema rec fastapi.cast -c "bash docs/source/tutorials/scripts/fastapi.sh"</code></em></p>
</div>

## What You'll Learn

1. Adding obskit middleware to FastAPI
2. Automatic request metrics and tracing
3. Custom metrics in endpoints
4. Health check endpoints
5. Viewing metrics in Prometheus format

## Prerequisites

- Python 3.11+
- Basic FastAPI knowledge

## Step-by-Step

### 1. Install dependencies

```bash
pip install obskit[fastapi] uvicorn
```

### 2. Create the application

```python
# app.py
from fastapi import FastAPI
from obskit import configure, get_red_metrics, get_logger, start_http_server
from obskit.middleware import ObskitMiddleware
from obskit.health import get_health_checker

# Configure obskit
configure(
    service_name="fastapi-demo",
    log_format="console",
)

# Create FastAPI app
app = FastAPI(title="obskit Demo")

# Add observability middleware
app.add_middleware(ObskitMiddleware)

# Get components
metrics = get_red_metrics()
logger = get_logger()
health = get_health_checker()

# Start metrics server on port 9090
start_http_server(9090)

# Health check
@health.add_readiness_check("database")
async def check_database():
    return True  # Replace with real check

# Endpoints
@app.get("/")
async def root():
    logger.info("root_accessed")
    return {"message": "Hello, obskit!"}

@app.get("/items/{item_id}")
async def get_item(item_id: int):
    logger.info("item_requested", item_id=item_id)
    
    # Custom metrics
    with metrics.track_request("get_item_details"):
        # Simulate database call
        import asyncio
        await asyncio.sleep(0.05)
    
    return {"item_id": item_id, "name": f"Item {item_id}"}

@app.get("/health")
async def health_check():
    result = await health.check_health()
    return result.to_dict()

@app.get("/ready")
async def readiness():
    result = await health.check_readiness()
    return result.to_dict()
```

### 3. Run the application

```bash
uvicorn app:app --reload
```

### 4. Test the endpoints

In another terminal:

```bash
# Root endpoint
curl http://localhost:8000/

# Get an item
curl http://localhost:8000/items/42

# Health check
curl http://localhost:8000/health

# View metrics (Prometheus format)
curl http://localhost:9090/metrics
```

### 5. View the metrics

```bash
curl -s http://localhost:9090/metrics | grep fastapi
```

You'll see metrics like:

```
# HELP fastapi_demo_requests_total Total requests
# TYPE fastapi_demo_requests_total counter
fastapi_demo_requests_total{operation="root",status="success"} 1.0
fastapi_demo_requests_total{operation="items_item_id",status="success"} 1.0

# HELP fastapi_demo_request_duration_seconds Request duration
# TYPE fastapi_demo_request_duration_seconds histogram
fastapi_demo_request_duration_seconds_bucket{le="0.005",operation="root"} 1.0
...
```

## Script for Recording

```bash
#!/bin/bash
# FastAPI integration tutorial

clear
echo "# FastAPI + obskit Integration"
sleep 1

echo ""
echo "# Install dependencies"
pip install obskit uvicorn fastapi --quiet
echo "pip install obskit[fastapi] uvicorn"
sleep 1

# Create app.py
echo ""
echo "# Creating FastAPI app..."
cat > /tmp/app.py << 'PYEOF'
from fastapi import FastAPI
from obskit import configure, get_red_metrics, start_http_server
from obskit.middleware import ObskitMiddleware

configure(service_name="demo", log_format="console")
app = FastAPI()
app.add_middleware(ObskitMiddleware)
metrics = get_red_metrics()
start_http_server(9090)

@app.get("/")
async def root():
    return {"message": "Hello!"}

@app.get("/items/{id}")
async def get_item(id: int):
    with metrics.track_request("db_query"):
        import asyncio
        await asyncio.sleep(0.05)
    return {"id": id}
PYEOF

echo "# Start server (background)"
cd /tmp && uvicorn app:app --host 0.0.0.0 --port 8000 &
sleep 3

echo ""
echo "# Test endpoints"
curl -s http://localhost:8000/ | python -m json.tool
curl -s http://localhost:8000/items/42 | python -m json.tool

echo ""
echo "# View metrics"
curl -s http://localhost:9090/metrics | grep -E "^demo_" | head -20

echo ""
echo "# Cleanup"
pkill -f "uvicorn app:app"

echo ""
echo "# Done! Full observability in ~20 lines of code."
```

## What Gets Instrumented Automatically

With `ObskitMiddleware`, every request gets:

| Feature | Description |
|---------|-------------|
| Correlation ID | Generated or propagated from `X-Correlation-ID` header |
| Request logging | Start and completion logged with timing |
| RED metrics | Rate, Errors, Duration automatically tracked |
| Trace context | Extracted/injected for distributed tracing |
| Response headers | Correlation ID added to response |

## Next Steps

- [Flask Integration](flask-integration.md)
- [Kubernetes Deployment](kubernetes-deployment.md)
- [Performance Tuning](../performance/tuning.md)

