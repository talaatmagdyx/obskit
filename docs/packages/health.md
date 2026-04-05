# Health

Kubernetes-ready health checking with liveness and readiness probes, optional trace context in responses, built-in checks for common dependencies, and a standalone HTTP server.

## Installation

```bash
pip install "obskit[health]"
```

For HTTP reachability checks, also install the `health-http` extra:

```bash
pip install "obskit[health-http]"
```

---

## Overview

obskit provides a structured health-checking API that maps directly to Kubernetes probe endpoints:

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

When `obskit[otlp]` is installed and the health endpoint is served inside an instrumented request, `trace_id` and `span_id` are automatically included in the response:

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

obskit ships three system-level built-in checks — checks that have **no pre-configured client**. For dependency checks (Redis, Postgres, RabbitMQ, etc.) pass a plain callable directly, since the caller already owns the client:

```python
# Dependency checks — pass your own callable, zero boilerplate
checker.add_readiness_check("redis",    lambda: redis_client.ping())
checker.add_readiness_check("postgres", lambda: db.execute("SELECT 1"))
checker.add_readiness_check("rabbitmq", lambda: mq_channel.is_open)
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

---

## Kubernetes probe configuration

```yaml
# Deployment manifest excerpt
spec:
  containers:
    - name: order-service
      ports:
        - containerPort: 8000
          name: app
      livenessProbe:
        httpGet:
          path: /health/live
          port: app
        initialDelaySeconds: 10
        periodSeconds: 15
        failureThreshold: 3
      readinessProbe:
        httpGet:
          path: /health/ready
          port: app
        initialDelaySeconds: 5
        periodSeconds: 10
        failureThreshold: 3
```

---

## Integration with tracing

When `obskit[otlp]` is installed, the active OTel span's `trace_id` and `span_id` are automatically added to every `/health` JSON response. This requires no additional configuration.

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

## build_health_router

Build a FastAPI `APIRouter` with standard `/health/live`, `/health/ready`, and `/health` endpoints from a list of `HealthCheck` objects.

obskit is completely agnostic about what is being checked. **You provide the callable — obskit owns the protocol.**

```python
from obskit.health import HealthCheck, build_health_router

router = build_health_router(
    checks=[
        HealthCheck(name="redis",    check=lambda: redis_client.ping(), timeout=2),
        HealthCheck(name="postgres", check=lambda: db.execute("SELECT 1"),  timeout=3),
        HealthCheck(name="rabbit",   check=lambda: channel.is_open,         timeout=2),
    ]
)

app.include_router(router)
# Registers:
#   GET /health/live   → liveness probe  (200 / 503)
#   GET /health/ready  → readiness probe (200 / 503)
#   GET /health        → combined health (200 / 503)
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `checks` | `list[HealthCheck]` | `None` | Shortcut — all treated as readiness checks |
| `readiness_checks` | `list[HealthCheck]` | `None` | Checks for external dependencies |
| `liveness_checks` | `list[HealthCheck]` | `None` | Checks for process health (e.g. memory) |
| `prefix` | `str` | `"/health"` | URL prefix for all endpoints |
| `tags` | `list[str]` | `["health"]` | FastAPI OpenAPI tags |
| `include_in_schema` | `bool` | `False` | Include endpoints in OpenAPI schema |

### Splitting liveness from readiness

```python
router = build_health_router(
    readiness_checks=[
        # Failure → pod removed from load balancer
        HealthCheck(name="postgres", check=lambda: db.execute("SELECT 1"), timeout=3),
        HealthCheck(name="redis",    check=lambda: redis_client.ping(),    timeout=2),
    ],
    liveness_checks=[
        # Failure → pod restarted by Kubernetes
        HealthCheck(name="memory", check=lambda: psutil.virtual_memory().percent < 90),
    ],
)
```

### HealthCheck — check= syntax

The preferred parameter name is `check=`. The legacy `check_fn=` parameter is kept for backward compatibility.

```python
# Preferred (check= alias)
HealthCheck(name="redis",    check=lambda: redis_client.ping(), timeout=2)

# Async callable works too
async def check_postgres():
    return await db.execute("SELECT 1")
HealthCheck(name="postgres", check=check_postgres, timeout=3)

# Legacy (check_fn= still works)
HealthCheck(name="rabbit",   check_fn=lambda: channel.is_open, timeout=2)
```

Both sync and async callables are supported. Sync callables return their value directly; async callables are awaited with timeout enforcement.

### Response format

Every endpoint returns the same JSON shape:

```json
{
    "status": "healthy",
    "healthy": true,
    "checks": {
        "redis":    {"status": "healthy",   "duration_ms": 1.2},
        "postgres": {"status": "healthy",   "duration_ms": 4.5},
        "rabbit":   {"status": "unhealthy", "duration_ms": 0.3, "error": "..."}
    },
    "service":   "order-service",
    "version":   "1.0.0",
    "timestamp": "2026-03-01T10:00:00.000000+00:00"
}
```

---

## Full example — FastAPI with build_health_router

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from obskit.health import HealthCheck, build_health_router
from obskit.health.checks import create_memory_check, create_disk_check

# Define checks as plain callables — obskit doesn't import redis/postgres
import redis
import psycopg2

redis_client = redis.Redis(host="redis", port=6379)

checks = [
    HealthCheck(name="redis",    check=lambda: redis_client.ping(),          timeout=2),
    HealthCheck(name="postgres", check=lambda: _pg_ping(),                   timeout=3),
    HealthCheck(name="memory",   check=create_memory_check(threshold_percent=85), timeout=1),
]

def _pg_ping() -> bool:
    try:
        conn = psycopg2.connect("postgresql://user:pass@postgres:5432/db", connect_timeout=2)
        conn.close()
        return True
    except Exception:
        return False

app = FastAPI(title="Order Service")
app.include_router(build_health_router(checks=checks))
```

---

## Full example — FastAPI with HealthChecker

```python
from contextlib import asynccontextmanager
import redis.asyncio as aioredis
from fastapi import FastAPI
from obskit.health import get_health_checker
from obskit.health.checks import create_http_check
from fastapi.responses import JSONResponse

checker = get_health_checker()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Register checks — pass your own client callable directly
    redis_client = aioredis.Redis(host="redis", port=6379)
    checker.add_readiness_check("redis", lambda: redis_client.ping())
    checker.add_readiness_check(
        "upstream",
        create_http_check("http://upstream/health"),
    )
    yield

app = FastAPI(lifespan=lifespan)

@app.get("/health")
async def health():
    result = await checker.check_health()
    status_code = 200 if result.healthy else 503
    return JSONResponse(result.to_dict(), status_code=status_code)
```

---

## WorkerHealthServer — liveness probe for worker processes

*New in v2.0.0.* A minimal HTTP server for non-HTTP workers (RabbitMQ consumers, cron jobs, async pipeline workers) that do not have FastAPI or Flask. Kubernetes liveness probes can reach it even when the main worker loop is blocked or stuck in a reconnect loop.

```python
from obskit.health import WorkerHealthServer

health = WorkerHealthServer(
    port=8002,
    checks={
        "consumer": lambda: consumer.is_alive(),
        "retry_worker": lambda: retry_worker.is_running,
    },
    max_silence_seconds=120,
)
await health.start()
```

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `port` | required | TCP port to listen on (e.g. `8002`). |
| `checks` | required | `dict[str, Callable[[], bool]]` — check name → zero-argument callable. Exceptions are caught and treated as `fail`. Sync callables only. |
| `max_silence_seconds` | `None` | If set, returns 503 when `record_activity()` has not been called within this many seconds. |

### HTTP endpoints

| Path | Description |
|------|-------------|
| `GET /health` | Evaluate all checks. Returns `200` or `503`. |
| `GET /live` | Alias for `/health` — Kubernetes liveness probe. |
| `GET /ready` | Alias for `/health` — Kubernetes readiness probe. |
| Any other path | `404`. |

### Response format

```json
{
  "status": "ok",
  "checks": {
    "consumer": {"status": "ok"},
    "retry_worker": {"status": "ok"},
    "activity": {
      "status": "ok",
      "silence_seconds": 3.2,
      "threshold_seconds": 120
    }
  }
}
```

Returns `503` with `"status": "fail"` when any check fails or silence exceeds `max_silence_seconds`.

### `record_activity()`

Call after every message processed in the worker loop to reset the silence timer:

```python
async def consume():
    async for message in channel:
        await handle(message)
        health.record_activity()   # ← reset 120-second silence timer
```

### Kubernetes probe configuration

```yaml
livenessProbe:
  httpGet:
    path: /live
    port: 8002
  initialDelaySeconds: 10
  periodSeconds: 15
  failureThreshold: 3

readinessProbe:
  httpGet:
    path: /ready
    port: 8002
  initialDelaySeconds: 5
  periodSeconds: 10
```

### Stopping the server

```python
# On graceful shutdown:
health.stop()
```

### Starting from synchronous code

```python
health = WorkerHealthServer(port=8002, checks={"ok": lambda: True})
health.start_sync()   # non-async equivalent of await health.start()
```

### API Reference

::: obskit.health.server.WorkerHealthServer

