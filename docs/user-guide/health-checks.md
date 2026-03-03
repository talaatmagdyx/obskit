# Health Checks

obskit provides a `HealthChecker` that aggregates multiple health checks into a single response, integrates with Kubernetes liveness/readiness/startup probes, and links health status to your distributed traces.

---

## Quick Start

```python
from obskit.health import HealthChecker, create_http_check, create_tcp_check

checker = HealthChecker(service="payment-service")

# Add built-in checks
checker.add_check("postgres",     create_tcp_check(host="postgres", port=5432))
checker.add_check("redis",        create_tcp_check(host="redis",    port=6379))
checker.add_check("stripe-api",   create_http_check(url="https://api.stripe.com/healthcheck"))

# Run all checks
result = await checker.check_health()
print(result.status)       # HealthStatus.healthy
print(result.to_dict())    # Full JSON-serialisable report
```

---

## HealthChecker API

```python
from obskit.health import HealthChecker

checker = HealthChecker(
    service="payment-service",
    timeout=5.0,               # Default timeout per check (seconds)
    include_trace_id=True,     # Inject active OTel trace_id into results
)
```

### `add_check()`

```python
checker.add_check(
    name="postgres",            # Check name (appears in report)
    check_fn=my_check,          # Callable: () -> HealthResult (sync or async)
    timeout=3.0,                # Per-check timeout (overrides global default)
    critical=True,              # If True, failure → overall status = unhealthy
                                # If False, failure → overall status = degraded
    tags=["database", "core"],  # Optional tags for filtering
)
```

### `check_health()`

Runs all registered checks concurrently and returns an aggregated `HealthResult`:

```python
result = await checker.check_health()
```

- Checks run **in parallel** using `asyncio.gather`
- Each check is independently timed out
- A failed check does not cancel other checks

---

## HealthStatus

```python
from obskit.health import HealthStatus

HealthStatus.healthy    # All checks passed
HealthStatus.degraded   # Non-critical check(s) failed; service is operational
HealthStatus.unhealthy  # Critical check(s) failed; service cannot serve traffic
```

### Aggregation logic

| Critical checks | Non-critical checks | Overall status |
|---|---|---|
| All pass | All pass | `healthy` |
| All pass | Some fail | `degraded` |
| Any fail | Any state | `unhealthy` |

---

## HealthResult

```python
from obskit.health.checker import HealthResult
```

`HealthResult` is returned by both the aggregated `check_health()` and individual check functions.

### Fields

| Field | Type | Description |
|---|---|---|
| `status` | `HealthStatus` | `healthy`, `degraded`, or `unhealthy` |
| `name` | `str` | Check name |
| `message` | `str \| None` | Human-readable status detail |
| `duration_ms` | `float` | Time taken to run this check |
| `trace_id` | `str \| None` | Active OTel trace ID (when `include_trace_id=True`) |
| `checks` | `dict` | Sub-check results (top-level aggregated result only) |
| `timestamp` | `str` | ISO8601 timestamp of the check |

### `to_dict()`

Returns a fully JSON-serialisable dictionary, suitable for HTTP response bodies:

```python
result.to_dict()
```

```json
{
  "status": "healthy",
  "service": "payment-service",
  "timestamp": "2026-02-28T14:32:07.841Z",
  "duration_ms": 45.2,
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "checks": {
    "postgres": {
      "status": "healthy",
      "duration_ms": 12.1,
      "message": "Connected (pool: 8/20 active)"
    },
    "redis": {
      "status": "healthy",
      "duration_ms": 3.4
    },
    "stripe-api": {
      "status": "healthy",
      "duration_ms": 28.7
    }
  }
}
```

---

## Built-in Check Types

!!! tip "Custom checks are first-class"
    Any callable (sync or async) is a valid check. For advanced dependency checks not listed here — Redis cluster, connection pool introspection, SQLAlchemy pool stats — pass a plain callable directly:
    ```python
    HealthCheck(name="redis_pool", check=lambda: my_pool_ok())
    ```

### `create_tcp_check`

Tests a TCP connection to a host and port:

```python
from obskit.health import create_tcp_check

postgres_check = create_tcp_check(
    host="postgres",
    port=5432,
    timeout=2.0,
)
```

The check connects, verifies the connection was accepted, and closes immediately. It does not authenticate or send any data.

### `create_http_check`

Sends an HTTP GET request and checks the response status code:

```python
from obskit.health import create_http_check

stripe_check = create_http_check(
    url="https://api.stripe.com/healthcheck",
    expected_status=200,         # Fail if response code != 200
    timeout=5.0,
    headers={"Authorization": f"Bearer {STRIPE_KEY}"},
)
```

---

## Custom Check Functions

Any callable returning a `HealthResult` (sync or async) can be a check:

### Synchronous custom check

```python
from obskit.health import HealthStatus
from obskit.health.checker import HealthResult

def check_disk_space() -> HealthResult:
    import shutil
    usage = shutil.disk_usage("/data")
    utilization = usage.used / usage.total

    if utilization > 0.95:
        return HealthResult(
            status=HealthStatus.unhealthy,
            message=f"Disk {utilization:.0%} full — critical",
        )
    elif utilization > 0.80:
        return HealthResult(
            status=HealthStatus.degraded,
            message=f"Disk {utilization:.0%} full — approaching limit",
        )
    return HealthResult(
        status=HealthStatus.healthy,
        message=f"Disk {utilization:.0%} used",
    )

checker.add_check("disk_space", check_disk_space, critical=True)
```

### Asynchronous custom check

```python
import asyncpg
from obskit.health import HealthStatus
from obskit.health.checker import HealthResult

async def check_postgres_query() -> HealthResult:
    try:
        conn = await asyncpg.connect("postgresql://...")
        await conn.fetchval("SELECT 1")
        await conn.close()
        return HealthResult(status=HealthStatus.healthy, message="Query OK")
    except asyncpg.PostgresConnectionError as exc:
        return HealthResult(
            status=HealthStatus.unhealthy,
            message=f"Cannot connect: {exc}",
        )
    except asyncpg.PostgresError as exc:
        return HealthResult(
            status=HealthStatus.degraded,
            message=f"Query failed: {exc}",
        )
```

### SLO-based health check

```python
from obskit.health import HealthStatus
from obskit.health.checker import HealthResult
from obskit.slo import SLOTracker

slo = SLOTracker(name="checkout_availability", objective=0.999)

async def check_slo_health() -> HealthResult:
    report = slo.get_report()
    budget_remaining = report["budget_remaining"]

    if budget_remaining <= 0:
        return HealthResult(
            status=HealthStatus.unhealthy,
            message=f"Error budget exhausted (SLI: {report['sli']:.4%})",
        )
    elif budget_remaining < 0.1:
        return HealthResult(
            status=HealthStatus.degraded,
            message=f"Error budget at {budget_remaining:.0%} ({report['sli']:.4%} SLI)",
        )
    return HealthResult(
        status=HealthStatus.healthy,
        message=f"SLI {report['sli']:.4%} ({budget_remaining:.0%} budget remaining)",
    )

checker.add_check("slo_checkout", check_slo_health, critical=False)
```

---

## Async Health Checks

All checks run concurrently by default. For independent checks (database, cache, external APIs), this means the total health check time is the duration of the **slowest** check, not the sum of all checks.

```python
import asyncio
from obskit.health import HealthChecker, create_tcp_check

checker = HealthChecker(service="api", timeout=5.0)

checker.add_check("postgres", create_tcp_check("postgres", 5432))  # ~12ms
checker.add_check("redis",    create_tcp_check("redis",    6379))  # ~3ms
checker.add_check("opensearch", create_http_check("http://opensearch:9200/_cluster/health"))  # ~28ms

# Total time: ~28ms (slowest check), not 43ms (sum)
result = await checker.check_health()
```

---

## build_health_router — FastAPI one-liner

For FastAPI services, `build_health_router` is the fastest way to get Kubernetes-ready health endpoints. You only provide the check callables — obskit registers the routes, handles timeouts, aggregates results, and returns the correct HTTP status codes.

```python
from fastapi import FastAPI
from obskit.health import HealthCheck, build_health_router

app = FastAPI()

app.include_router(
    build_health_router(
        checks=[
            HealthCheck(name="redis",    check=lambda: redis_client.ping(), timeout=2),
            HealthCheck(name="postgres", check=lambda: db.execute("SELECT 1"), timeout=3),
        ]
    )
)
# Exposes: GET /health/live, GET /health/ready, GET /health
```

Separate liveness from readiness when the two check different things:

```python
app.include_router(
    build_health_router(
        readiness_checks=[
            # Dependency checks — failure stops traffic
            HealthCheck(name="postgres", check=lambda: db.ping(), timeout=3),
        ],
        liveness_checks=[
            # Process checks — failure triggers pod restart
            HealthCheck(name="memory", check=lambda: memory_ok(), timeout=1),
        ],
        prefix="/health",   # default
    )
)
```

See the [health package reference](../packages/health.md#build_health_router) for the full API.

---

## Kubernetes Integration

Kubernetes uses three types of probes to manage container lifecycle:

| Probe | Purpose | Failure action |
|---|---|---|
| **Liveness** | Is the process alive and not deadlocked? | Restart the container |
| **Readiness** | Is the service ready to receive traffic? | Remove from Service endpoints |
| **Startup** | Has the application finished initialising? | Wait (do not send traffic, do not restart) |

obskit makes it easy to serve different responses for each probe type.

### FastAPI health endpoint

```python
from fastapi import FastAPI, Response
from obskit.health import HealthChecker, HealthStatus, create_tcp_check, create_http_check

app = FastAPI()
checker = HealthChecker(service="payment-service")

checker.add_check("postgres", create_tcp_check("postgres", 5432), critical=True)
checker.add_check("redis",    create_tcp_check("redis",    6379), critical=True)
checker.add_check("stripe",   create_http_check("https://api.stripe.com/healthcheck"), critical=False)

@app.get("/health/live")
async def liveness():
    """Kubernetes liveness probe — is the process running?"""
    # Liveness is lightweight: just check the process is not deadlocked.
    # Do NOT check external dependencies here — a DB outage should not restart your pod.
    return {"status": "alive"}

@app.get("/health/ready")
async def readiness(response: Response):
    """Kubernetes readiness probe — can we serve traffic?"""
    result = await checker.check_health()
    if result.status == HealthStatus.unhealthy:
        response.status_code = 503
    elif result.status == HealthStatus.degraded:
        response.status_code = 207   # Multi-Status — still serving, but degraded
    return result.to_dict()

@app.get("/health/startup")
async def startup(response: Response):
    """Kubernetes startup probe — has the application initialised?"""
    result = await checker.check_health()
    if result.status != HealthStatus.healthy:
        response.status_code = 503
    return result.to_dict()
```

### Kubernetes probe configuration

```yaml
# kubernetes/deployment.yml
spec:
  containers:
    - name: payment-service
      image: payment-service:2.0.0
      livenessProbe:
        httpGet:
          path: /health/live
          port: 8000
        initialDelaySeconds: 5
        periodSeconds: 10
        failureThreshold: 3
        timeoutSeconds: 2

      readinessProbe:
        httpGet:
          path: /health/ready
          port: 8000
        initialDelaySeconds: 10
        periodSeconds: 5
        failureThreshold: 2
        successThreshold: 1
        timeoutSeconds: 5

      startupProbe:
        httpGet:
          path: /health/startup
          port: 8000
        failureThreshold: 30     # Allow up to 5 minutes to start (30 × 10s)
        periodSeconds: 10
        timeoutSeconds: 5
```

!!! warning "Liveness probe — do not check dependencies"
    The liveness probe should only verify the process is alive and not deadlocked. **Never** add database or external API checks to the liveness probe. If a database goes down, you want your pods to stop receiving traffic (readiness), not restart (liveness).

!!! tip "Startup probe prevents false liveness failures"
    Without a startup probe, Kubernetes may restart your pod if it takes more than `initialDelaySeconds` to start. Use a startup probe for applications with slow startup (large model loading, database migrations, cache warming).

---

## Timeout Handling and Error Reporting

Health checks have independent timeouts. A timed-out check is reported as `unhealthy` with a descriptive message:

```json
{
  "status": "unhealthy",
  "checks": {
    "stripe-api": {
      "status": "unhealthy",
      "message": "Check timed out after 5.0s",
      "duration_ms": 5000.1
    }
  }
}
```

Exceptions raised inside a check function are caught, logged, and converted to `unhealthy` results — they do not propagate to the caller:

```json
{
  "status": "unhealthy",
  "checks": {
    "postgres": {
      "status": "unhealthy",
      "message": "connection refused (host=postgres, port=5432)",
      "duration_ms": 0.3
    }
  }
}
```
