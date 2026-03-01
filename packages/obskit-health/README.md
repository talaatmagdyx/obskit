<div align="center">

# 🏥 obskit-health

**Kubernetes-style liveness, readiness, and health endpoints with built-in database, Redis, and HTTP checks**

---

[![PyPI](https://img.shields.io/pypi/v/obskit-health.svg?color=blue)](https://pypi.org/project/obskit-health/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![obskit](https://img.shields.io/badge/part%20of-obskit-blueviolet.svg)](https://github.com/talaatmagdyx/obskit)

</div>

## What it does

- **Aggregates health across all dependencies** — database, Redis, upstream APIs, memory, disk — into a single `healthy / degraded / unhealthy` verdict that Kubernetes probes and monitoring dashboards can act on immediately.
- **Distinguishes critical from non-critical failures** — a degraded Redis cache keeps your pod serving traffic with a 200 OK; a failed primary database pulls it out of rotation with a 503 so Kubernetes can reschedule.
- **Injects trace context automatically** when `obskit-tracing` is active, embedding `trace_id` and `span_id` in every health response so a slow health check can be correlated directly to a Grafana Tempo trace.

---

## Installation

```bash
# Core health checker (no optional dependencies)
pip install obskit-health

# With Redis support for create_redis_check()
pip install "obskit-health[redis]"

# With HTTP support for create_http_check()
pip install "obskit-health[httpx]"

# Both
pip install "obskit-health[redis,httpx]"
```

---

## Quick Start

```python
from obskit.health import HealthChecker
from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI()
checker = HealthChecker()

# Register checks with decorators
@checker.add_readiness_check("database")
async def check_database():
    await db.execute("SELECT 1")
    return True  # healthy

@checker.add_readiness_check("redis", critical=False)  # non-critical: degraded, not unhealthy
async def check_redis():
    return await redis_client.ping()

@checker.add_liveness_check("memory")
async def check_memory():
    import psutil
    return psutil.virtual_memory().percent < 95

# Wire up the three standard endpoints
@app.get("/health")
async def health():
    result = await checker.check_health()
    return JSONResponse(content=result.to_dict(), status_code=200 if result.healthy else 503)

@app.get("/ready")
async def ready():
    result = await checker.check_readiness()
    return JSONResponse(content=result.to_dict(), status_code=200 if result.healthy else 503)

@app.get("/live")
async def live():
    result = await checker.check_liveness()
    return JSONResponse(content=result.to_dict(), status_code=200 if result.healthy else 503)
```

---

## Features

### 1. HealthChecker — Decorator and Programmatic Registration

`HealthChecker` runs all registered checks concurrently using `asyncio.gather`, so a slow dependency (e.g. a database timing out after 5 s) does not block faster checks. Both async and synchronous check functions are supported.

```python
from obskit.health import HealthChecker, create_health_response

checker = HealthChecker(timeout=5.0)   # global per-check timeout

# --- Decorator style ---
@checker.add_readiness_check("orders_db", critical=True, timeout=3.0)
async def check_orders_db():
    row = await orders_db.fetchval("SELECT 1")
    return row == 1

# --- Programmatic style (useful when the check function is defined elsewhere) ---
async def check_payments_db():
    return await payments_db.ping()

checker.add_readiness_check("payments_db")(check_payments_db)

# --- Rich detail responses ---
@checker.add_readiness_check("product_cache")
async def check_product_cache():
    pool_size = redis.connection_pool.max_connections
    used = len(redis.connection_pool._in_use_connections)
    return {
        "healthy": await redis.ping(),
        "message": f"Redis OK ({used}/{pool_size} connections used)",
        "details": {"pool_utilization": used / pool_size},
    }

# --- Run everything ---
result = await checker.check_health()
# result.healthy        → True / False
# result.status         → HealthStatus.HEALTHY | DEGRADED | UNHEALTHY
# result.checks         → {"orders_db": CheckResult(...), "product_cache": CheckResult(...)}
```

### 2. Critical vs Non-Critical — Degraded vs Unhealthy

The `critical` flag lets you express the real dependency semantics of your service. A critical check failure yields `unhealthy` (HTTP 503); a non-critical failure yields `degraded` (HTTP 200, but Grafana can alert on it).

```python
checker = HealthChecker()

# CRITICAL: if the write database is down, stop accepting traffic
@checker.add_readiness_check("write_db", critical=True)
async def check_write_db():
    return await primary_db.ping()

# NON-CRITICAL: search works from a replica; degraded but still serving
@checker.add_readiness_check("search_replica", critical=False)
async def check_search():
    return await search_db.ping()

# NON-CRITICAL: recommendations service is nice-to-have
@checker.add_readiness_check("recommendations_api", critical=False)
async def check_recommendations():
    return await recommendations.health()

result = await checker.check_readiness()

match result.status.value:
    case "healthy":
        pass     # all checks passed
    case "degraded":
        pass     # non-critical checks failed, still serving traffic
    case "unhealthy":
        pass     # critical check failed, Kubernetes will remove from LB
```

### 3. Built-in Check Helpers

obskit-health ships factory functions for the most common dependency checks so you do not have to write them yourself.

```python
import redis.asyncio as aioredis
from obskit.health import HealthChecker
from obskit.health.checks import (
    create_redis_check,
    create_redis_pool_check,
    create_memory_check,
    create_disk_check,
    create_http_check,
    create_database_pool_check,
)

checker = HealthChecker()
redis_client = aioredis.Redis.from_url("redis://localhost:6379")

# Redis connectivity (sync or async client, auto-detected)
checker.add_readiness_check("cache")(
    create_redis_check(redis_client, timeout=2.0)
)

# Redis connection pool saturation check
checker.add_readiness_check("cache_pool")(
    create_redis_pool_check(redis_client, max_connections_threshold=0.85)
)

# Memory liveness (restart pod if memory > 90%)
checker.add_liveness_check("memory")(
    create_memory_check(threshold_percent=90.0)
)

# Disk space (warn before /data fills up)
checker.add_readiness_check("disk")(
    create_disk_check(path="/data", threshold_percent=85.0)
)

# Upstream HTTP health endpoint
checker.add_readiness_check("payments_api", critical=True)(
    create_http_check(
        url="https://payments.internal/health",
        timeout=3.0,
        expected_status=200,
    )
)

# SQLAlchemy connection pool
from sqlalchemy import create_engine
engine = create_engine("postgresql+asyncpg://user:pass@db/orders", pool_size=20)
checker.add_readiness_check("db_pool")(
    create_database_pool_check(engine, max_overflow_threshold=0.8)
)
```

### 4. SLO-Linked Health — Budget Breach Pulls Readiness

When `obskit-slo` is installed and an SLO enters critical breach (error budget exhausted), the standalone health server automatically reflects this in the readiness endpoint. You can also wire it manually.

```python
from obskit.health import HealthChecker
from obskit.slo import SLOTracker, SLOType

tracker = SLOTracker()
tracker.register_slo(
    name="api_availability",
    slo_type=SLOType.AVAILABILITY,
    target_value=0.999,
    window_seconds=30 * 86400,
)

checker = HealthChecker()

@checker.add_readiness_check("slo_compliance", critical=True)
async def check_slo():
    status = tracker.get_status("api_availability")
    if status is None:
        return True  # no data yet, assume healthy

    budget_ok = status.error_budget_remaining > 0.0
    return {
        "healthy": budget_ok,
        "message": f"Error budget remaining: {status.error_budget_remaining:.2%}",
        "details": {
            "is_within_slo": status.compliance,
            "burn_rate": round(status.error_budget_burn_rate, 4),
            "current_value": round(status.current_value, 6),
        },
    }
```

### 5. Standalone HTTP Health Server

No framework required. `start_health_server()` spins up a standard-library `HTTPServer` in a daemon thread and serves four endpoints out of the box.

```python
from obskit.health.server import start_health_server, stop_health_server, register_health_endpoint

# Start on port 8888 (default)
start_health_server(port=8888, host="0.0.0.0")

# Endpoints served automatically:
# GET /health        → overall status (liveness + readiness + SLO)
# GET /health/live   → liveness probe
# GET /health/ready  → readiness probe (returns 503 if SLO is critical)
# GET /health/slo    → SLO compliance detail
# GET /healthz       → alias for /health/live
# GET /readyz        → alias for /health/ready

# Register a custom endpoint alongside the built-ins
def check_feature_flags():
    return {
        "healthy": flags_client.is_connected(),
        "details": {"flag_count": flags_client.count()},
    }

register_health_endpoint("/health/flags", check_feature_flags)

# Graceful shutdown
stop_health_server()
```

### 6. Trace Context in Health Responses

When `obskit-tracing` (or any OpenTelemetry SDK) is active and a span is in scope, every health response gains `trace_id` and `span_id` fields automatically — zero configuration needed.

```python
# Assuming a tracer is active (e.g., obskit-tracing is installed and configured)

result = await checker.check_health()
payload = result.to_dict()
# {
#   "status": "healthy",
#   "healthy": true,
#   "service": "order-service",
#   "version": "2.0.0",
#   "timestamp": "2026-03-01T12:00:00.000000+00:00",
#   "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",   ← only present when a span is active
#   "span_id":  "00f067aa0ba902b7",
#   "checks": {
#     "database": {"status": "healthy", "duration_ms": 1.234},
#     "redis":    {"status": "healthy", "duration_ms": 0.891}
#   }
# }
```

---

## Health Response Format

### Healthy

```json
{
  "status": "healthy",
  "healthy": true,
  "service": "order-service",
  "version": "2.0.0",
  "timestamp": "2026-03-01T12:00:00.000000+00:00",
  "checks": {
    "database":    { "status": "healthy",   "duration_ms": 1.23 },
    "redis":       { "status": "healthy",   "duration_ms": 0.89 },
    "memory":      { "status": "healthy",   "duration_ms": 0.12,
                     "message": "Memory: 62.4% (threshold: 90%)" },
    "payments_api":{ "status": "healthy",   "duration_ms": 45.1 }
  }
}
```

### Degraded (non-critical failure)

```json
{
  "status": "degraded",
  "healthy": true,
  "checks": {
    "database":          { "status": "healthy",   "duration_ms": 1.23 },
    "recommendations_api":{ "status": "unhealthy", "duration_ms": 3002.1,
                            "error": "Check timed out after 3.0s" }
  }
}
```

### Unhealthy (critical failure, HTTP 503)

```json
{
  "status": "unhealthy",
  "healthy": false,
  "checks": {
    "write_db": { "status": "unhealthy", "duration_ms": 5001.4,
                  "error": "ConnectionRefusedError: [Errno 111] Connection refused" }
  }
}
```

---

## Kubernetes Probe Configuration

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: order-service
spec:
  template:
    spec:
      containers:
        - name: order-service
          image: order-service:2.0.0
          ports:
            - containerPort: 8080   # application traffic
            - containerPort: 8888   # health server (separate port)
          livenessProbe:
            httpGet:
              path: /health/live
              port: 8888
            initialDelaySeconds: 5
            periodSeconds: 10
            failureThreshold: 3
          readinessProbe:
            httpGet:
              path: /health/ready
              port: 8888
            initialDelaySeconds: 5
            periodSeconds: 5
            failureThreshold: 2
          startupProbe:
            httpGet:
              path: /health/live
              port: 8888
            failureThreshold: 30
            periodSeconds: 2
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `OBSKIT_SERVICE_NAME` | `"service"` | Service name included in health responses |
| `OBSKIT_VERSION` | `"0.0.0"` | Version string included in health responses |
| `OBSKIT_HEALTH_CHECK_TIMEOUT` | `5.0` | Default per-check timeout in seconds |
| `OBSKIT_HEALTH_SERVER_PORT` | `8888` | Default port for `start_health_server()` |

---

## Part of the obskit family

`obskit-health` is part of the [obskit](https://github.com/talaatmagdyx/obskit) monorepo — a production-ready observability toolkit for Python microservices.

| Install only this package | Install everything |
|---|---|
| `pip install obskit-health` | `pip install "obskit[all]"` |
