# obskit-health

Kubernetes-ready health checking with liveness and readiness probes, optional trace context in responses, built-in checks for common dependencies, and a standalone HTTP server.

## Installation

```bash
pip install obskit
```

---

## Overview

obskit-health provides a structured health-checking API that maps directly to Kubernetes probe endpoints:

| Endpoint | Probe type | Meaning |
|---|---|---|
| `GET /health` | Combined | All registered checks |
| `GET /health/live` | Liveness | Is the process alive? (restart if unhealthy) |
| `GET /health/ready` | Readiness | Can the process serve traffic? |
| `GET /healthz` | Liveness alias | Kubernetes conventional alias |
| `GET /readyz` | Readiness alias | Kubernetes conventional alias |
| `GET /livez` | Liveness alias | Kubernetes conventional alias |

---

## HealthStatus

```python
from obskit.core.types import HealthStatus

HealthStatus.HEALTHY    # "healthy"   — all checks passed
HealthStatus.DEGRADED   # "degraded"  — some non-critical checks failed
HealthStatus.UNHEALTHY  # "unhealthy" — one or more critical checks failed
```

---

## HealthChecker

Central registry for health check functions. The global singleton is returned by `get_health_checker()`.

```python
from obskit.health import HealthChecker, get_health_checker

# Use the global singleton (recommended)
checker = get_health_checker()

# Or create an isolated instance (useful in tests)
checker = HealthChecker()
```

### add_check / add_readiness_check / add_liveness_check

```python
# A check function returns bool, or a dict with a "healthy" key
async def check_database() -> bool:
    try:
        await db.execute("SELECT 1")
        return True
    except Exception:
        return False

async def check_cache() -> dict:
    ok = await redis.ping()
    return {
        "healthy": ok,
        "message": "Redis is connected" if ok else "Redis ping failed",
        "details": {"host": "redis:6379"},
    }

# Register as a general check
checker.add_check("database", check_database)

# Register as readiness-only (traffic routing checks)
checker.add_readiness_check("cache", check_cache)

# Register as liveness-only (process health checks)
checker.add_liveness_check("memory", check_memory)
```

!!! note "Sync functions"
    Sync check functions are also accepted. The checker wraps them with `asyncio.get_event_loop().run_in_executor()` internally.

### check_health / check_readiness / check_liveness

```python
# Run all registered checks
result = await checker.check_health()

# Run readiness checks only
result = await checker.check_readiness()

# Run liveness checks only
result = await checker.check_liveness()
```

---

## HealthResult

The return type from all `check_*` methods.

```python
from obskit.health.checker import HealthResult

result: HealthResult = await checker.check_health()

print(result.healthy)     # True / False
print(result.status)      # HealthStatus.HEALTHY / .DEGRADED / .UNHEALTHY
print(result.service)     # "order-service"
print(result.version)     # "2.0.0"
print(result.timestamp)   # datetime (UTC)

# Inspect individual checks
for name, check_result in result.checks.items():
    print(f"{name}: healthy={check_result.healthy}")
    print(f"  duration_ms={check_result.duration_ms}")
    print(f"  message={check_result.message}")
    print(f"  error={check_result.error}")
```

### to_dict — JSON serialization

```python
payload = result.to_dict()
```

When `obskit-tracing[opentelemetry]` is installed and the health endpoint is served inside an instrumented request, `trace_id` and `span_id` are automatically included in the response:

```json
{
  "status": "healthy",
  "healthy": true,
  "service": "order-service",
  "version": "2.0.0",
  "timestamp": "2026-02-28T10:00:00.000000+00:00",
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "span_id":  "00f067aa0ba902b7",
  "checks": {
    "database": {
      "status": "healthy",
      "duration_ms": 3.142,
      "message": "Database is connected"
    },
    "cache": {
      "status": "healthy",
      "duration_ms": 1.057,
      "message": "Redis is connected",
      "details": {"host": "redis:6379"}
    }
  }
}
```

---

## CheckResult

```python
from obskit.health.checker import CheckResult

# Individual check result attributes:
check.name           # str  — name of the check
check.healthy        # bool
check.duration_ms    # float — how long the check took
check.message        # str | None — human-readable message
check.details        # dict — arbitrary extra data
check.error          # str | None — error message if unhealthy
check.status         # HealthStatus — derived from healthy

check.to_dict()      # JSON-serialisable dict
```

---

## Built-in checks

### Redis check

```python
from obskit.health.checks import create_redis_check
import redis
import redis.asyncio as aioredis

# Sync client
redis_client = redis.Redis(host="redis", port=6379)
checker.add_readiness_check("redis", create_redis_check(redis_client, timeout=5.0))

# Async client
async_redis = aioredis.Redis(host="redis", port=6379)
checker.add_readiness_check("redis", create_redis_check(async_redis, timeout=5.0))
```

### HTTP check

```python
from obskit.health.checks import create_http_check

# Passes if the URL returns HTTP 2xx within the timeout
http_check = create_http_check(
    url="http://upstream-service/health",
    timeout=5.0,
)
checker.add_readiness_check("upstream_service", http_check)
```

### TCP check

```python
from obskit.health.checks import create_tcp_check

# Passes if a TCP connection can be established
tcp_check = create_tcp_check(host="postgres", port=5432, timeout=5.0)
checker.add_readiness_check("postgres_port", tcp_check)
```

### Memory check

```python
from obskit.health.checks import create_memory_check

# Fails if resident memory usage exceeds the threshold
mem_check = create_memory_check(threshold_percent=90)
checker.add_liveness_check("memory", mem_check)
```

### Disk check

```python
from obskit.health.checks import create_disk_check

# Fails if disk usage exceeds the threshold
disk_check = create_disk_check(path="/", threshold_percent=85)
checker.add_liveness_check("disk", disk_check)
```

---

## Async check functions

All check functions can be async:

```python
import asyncio

async def check_database() -> dict:
    start = asyncio.get_event_loop().time()
    try:
        await db.execute("SELECT 1")
        return {
            "healthy": True,
            "message": "Database responding",
            "details": {"latency_ms": (asyncio.get_event_loop().time() - start) * 1000},
        }
    except Exception as e:
        return {
            "healthy": False,
            "message": "Database unreachable",
            "error": str(e),
        }

checker.add_readiness_check("database", check_database)
```

---

## Timeout

Checks that exceed `ObskitSettings.health_check_timeout` (default `5.0` seconds) are automatically cancelled and reported as unhealthy.

```python
from obskit.config import configure
configure(health_check_timeout=10.0)   # increase per-check timeout
```

---

## HTTP health server

A standalone HTTP server built on `http.server` — zero external dependencies.

```python
from obskit.health.server import start_health_server, stop_health_server

# Start on port 8888 (default: 8080)
start_health_server(port=8888)

# Endpoints automatically served:
# GET /health       → combined health check JSON
# GET /health/live  → liveness probe
# GET /health/ready → readiness probe
# GET /healthz      → liveness alias
# GET /readyz       → readiness alias
# GET /livez        → liveness alias

# Graceful stop
stop_health_server()
```

The server runs on a background daemon thread and does not block the main event loop.

---

## Kubernetes probe configuration

```yaml
# Deployment manifest excerpt
spec:
  containers:
    - name: order-service
      ports:
        - containerPort: 8080
          name: app
        - containerPort: 8888
          name: health
      livenessProbe:
        httpGet:
          path: /health/live
          port: health
        initialDelaySeconds: 10
        periodSeconds: 15
        failureThreshold: 3
      readinessProbe:
        httpGet:
          path: /health/ready
          port: health
        initialDelaySeconds: 5
        periodSeconds: 10
        failureThreshold: 3
```

---

## Integration with tracing

When `obskit-tracing[opentelemetry]` is installed, the active OTel span's `trace_id` and `span_id` are automatically added to every `/health` JSON response. This requires no additional configuration.

```python
from obskit.health.checker import _OTEL_AVAILABLE

if _OTEL_AVAILABLE:
    print("trace_id will appear in /health responses")
```

---

## Integration with SLO

```python
from obskit.health import get_health_checker
from obskit.slo.tracker import SLOTracker

slo = SLOTracker()
checker = get_health_checker()

async def check_slo_compliance():
    status = slo.get_status("api_availability")
    if status is None:
        return {"healthy": True, "message": "No SLO registered"}

    return {
        "healthy": status.compliance,
        "message": f"SLO compliance: {status.current_value:.3%}",
        "details": {
            "target": status.target.target_value,
            "current": status.current_value,
            "error_budget_remaining": status.error_budget_remaining,
        },
    }

checker.add_check("slo_api_availability", check_slo_compliance)
```

---

## Full example

```python
from contextlib import asynccontextmanager
import redis.asyncio as aioredis
from fastapi import FastAPI
from obskit.health import get_health_checker
from obskit.health.checks import create_redis_check, create_http_check
from obskit.health.server import start_health_server, stop_health_server

checker = get_health_checker()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Register checks
    redis_client = aioredis.Redis(host="redis", port=6379)
    checker.add_readiness_check("redis", create_redis_check(redis_client))
    checker.add_readiness_check(
        "upstream",
        create_http_check("http://upstream/health"),
    )

    # Start standalone health server for Kubernetes probes
    start_health_server(port=8888)
    yield
    stop_health_server()

app = FastAPI(lifespan=lifespan)

@app.get("/health")
async def health():
    result = await checker.check_health()
    status_code = 200 if result.healthy else 503
    from fastapi.responses import JSONResponse
    return JSONResponse(result.to_dict(), status_code=status_code)
```
