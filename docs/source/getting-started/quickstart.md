# Quick Start

Get up and running with obskit in 5 minutes.

## 1. Install obskit

```bash
pip install obskit[all]
```

## 2. Basic Setup

```python
from obskit import (
    configure_logging,
    get_red_metrics,
    get_health_checker,
    start_http_server,
)

# Configure structured logging
logger = configure_logging(
    service_name="my-service",
    log_level="INFO",
)

# Set up RED metrics
metrics = get_red_metrics(service_name="my-service")

# Set up health checks
health = get_health_checker()
health.add_liveness_check("basic", lambda: True)

# Start metrics server
start_http_server(port=9090)

logger.info("Service started", port=9090)
```

## 3. Track Requests

```python
# Using context manager
with metrics.track_request(endpoint="/api/users", method="GET"):
    result = get_users()

# Using decorator
@metrics.track
def process_order(order_id: str):
    # Your logic here
    pass
```

## 4. Add Health Checks

```python
def check_database():
    try:
        db.execute("SELECT 1")
        return True
    except Exception:
        return False

def check_redis():
    return redis.ping()

health.add_readiness_check("database", check_database)
health.add_readiness_check("redis", check_redis)
```

## 5. View Your Metrics

Open `http://localhost:9090/metrics` to see Prometheus metrics:

```
# HELP my_service_requests_total Total requests
# TYPE my_service_requests_total counter
my_service_requests_total{endpoint="/api/users",method="GET",status="success"} 42

# HELP my_service_request_duration_seconds Request duration
# TYPE my_service_request_duration_seconds histogram
my_service_request_duration_seconds_bucket{endpoint="/api/users",le="0.1"} 40
```

## What's Next?

- **[Your First App](first-app.md)** - Build a complete FastAPI application
- **[Concepts](../user-guide/concepts.md)** - Understand the theory behind observability
- **[Metrics Guide](../user-guide/metrics.md)** - Deep dive into RED, Golden Signals, and USE

