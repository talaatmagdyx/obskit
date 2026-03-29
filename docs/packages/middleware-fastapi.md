# FastAPI Middleware

Automatic per-request observability for FastAPI applications: correlation ID propagation, structured logging, RED metrics, distributed tracing, W3C Baggage header processing, and built-in `/health`, `/metrics`, and `/diagnose` routes.

## Installation

```bash
pip install "obskit[fastapi]"
```

---

## ObservabilityMiddleware

`ObskitMiddleware` is a Starlette `BaseHTTPMiddleware` subclass that wraps every request in a complete observability context.

### What it provides per request

| Feature | Details |
|---|---|
| Correlation ID | Reads `X-Correlation-ID` from the incoming request; auto-generates one if absent; echoes it in the response header |
| Structured logging | Logs request start and completion (method, path, status code, duration) using the obskit structlog pipeline |
| RED metrics | Increments `<service>_requests_total`, `<service>_errors_total`, and `<service>_request_duration_seconds` |
| Distributed tracing | Extracts `traceparent` / `tracestate` from incoming headers; starts a new root span if absent |
| W3C Baggage | Reads the `baggage:` header and restores the baggage context for the duration of the request |
| Response headers | Adds `X-Correlation-ID` and `X-Trace-Id` to every response |

### Minimal setup

```python
from fastapi import FastAPI
from obskit.middleware.fastapi import ObskitMiddleware

app = FastAPI()
app.add_middleware(ObskitMiddleware)

@app.get("/orders")
async def get_orders():
    return {"orders": []}
```

### Full setup with configuration

```python
from fastapi import FastAPI
from obskit.middleware.fastapi import ObskitMiddleware
from obskit.config import configure

app = FastAPI()

app.add_middleware(
    ObskitMiddleware,
    # Paths that bypass observability (health/metrics endpoints themselves)
    exclude_paths=["/health", "/ready", "/live", "/metrics", "/diagnose"],
    track_metrics=True,    # enable RED metrics
    track_logging=True,    # enable request/response logging
    track_tracing=True,    # enable distributed tracing
)
```

### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `exclude_paths` | `list[str]` | `["/health", "/ready", "/live", "/metrics"]` | Path prefixes excluded from observability overhead. Sub-paths are also excluded (e.g. `/health` also skips `/health/detail`) |
| `track_metrics` | `bool` | `True` | Collect RED metrics for every request |
| `track_logging` | `bool` | `True` | Emit structured log entries per request |
| `track_tracing` | `bool` | `True` | Create an OTel span per request |

---

## /health endpoint

The middleware includes a pre-built FastAPI router that mounts health-check endpoints backed by the obskit health module.

```python
from fastapi import FastAPI
from obskit.middleware.fastapi import ObskitMiddleware
from obskit.middleware.fastapi import create_health_router
from obskit.health import get_health_checker
import redis.asyncio as aioredis

app = FastAPI()
app.add_middleware(ObskitMiddleware)

checker = get_health_checker()
redis_client = aioredis.Redis(host="redis", port=6379)
checker.add_readiness_check("redis", lambda: redis_client.ping())

# Mount the health router
app.include_router(create_health_router(), prefix="")
```

**Mounted routes:**

| Route | Returns |
|---|---|
| `GET /health` | Full combined health check JSON |
| `GET /health/live` | Liveness probe |
| `GET /health/ready` | Readiness probe |

**Example response** (with `obskit[otlp]` installed):

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
    "redis": {
      "status": "healthy",
      "duration_ms": 1.23,
      "message": "Redis is connected"
    }
  }
}
```

An unhealthy response returns HTTP `503 Service Unavailable`.

---

## /metrics endpoint

Mount a Prometheus scrape endpoint alongside your application routes:

```python
from obskit.middleware.fastapi import create_metrics_router

app.include_router(create_metrics_router(), prefix="")
```

The route serves `GET /metrics` in **OpenMetrics** text format (required for exemplars). Add it to your Prometheus scrape config:

```yaml
scrape_configs:
  - job_name: "order-service"
    static_configs:
      - targets: ["order-service:8000"]
    # For exemplars (Prometheus 2.43+ auto-negotiates):
    # params:
    #   format: ["openmetrics"]
```

---

## /diagnose endpoint

Expose the obskit environment diagnostics report via HTTP — useful for platform teams and automated rollout verification:

```python
from obskit.middleware.fastapi import create_diagnose_router

app.include_router(create_diagnose_router(), prefix="")
```

`GET /diagnose` returns the same structured table as `python -m obskit.core.diagnose`:

```json
{
  "packages": [
    {"name": "obskit", "installed": true, "version": "3.3.0", "integrations": [...]},
    {"name": "obskit", "installed": true, "version": "3.3.0", "integrations": [...]}
  ],
  "python": "3.12.1",
  "executable": "/usr/local/bin/python3"
}
```

!!! warning "Security note"
    The `/diagnose` endpoint exposes internal version and package information. Restrict access to internal networks or add authentication before exposing it externally.

---

## Correlation ID validation

The middleware validates the incoming `X-Correlation-ID` header before accepting it. Only values matching `[a-zA-Z0-9\-_\.]{1,128}` are accepted. Invalid values (containing spaces, special characters, or exceeding 128 characters) are silently discarded and a fresh UUID is generated.

```
# Valid — accepted as-is
X-Correlation-ID: f47ac10b-58cc-4372-a567-0e02b2c3d479

# Invalid — discarded, new ID generated
X-Correlation-ID: invalid id with spaces!!!
```

The validated correlation ID is echoed back in the response `X-Correlation-ID` header so callers can use it for end-to-end tracing.

---

## Baggage header processing

The middleware automatically reads the W3C `baggage:` HTTP header on every incoming request and makes all baggage values available via `get_baggage()` for the lifetime of the request:

```python
# Incoming request headers:
# baggage: tenant_id=acme-corp, region=eu-west-1

from obskit.tracing import get_baggage

@app.get("/orders")
async def get_orders():
    tenant = get_baggage("tenant_id")   # "acme-corp"
    region = get_baggage("region")      # "eu-west-1"
    ...
```

The middleware also propagates baggage from parent services through the OTel context propagation chain when `track_tracing=True`.

---

## Configuration via ObskitSettings

All obskit settings are read from `ObskitSettings` at startup. The middleware does not require any direct configuration beyond `add_middleware()`:

```python
from obskit.config import configure

configure(
    service_name="order-service",
    environment="production",
    version="2.0.0",
    otlp_endpoint="http://tempo:4317",
    trace_sample_rate=0.1,
    log_level="INFO",
    log_format="json",
    metrics_enabled=True,
)
```

Relevant settings consumed by the middleware:

| Setting | Effect |
|---|---|
| `service_name` | Used as the RED metrics namespace and in log `service` field |
| `log_level` / `log_format` | Controls request log verbosity and format |
| `metrics_enabled` | Enables or disables RED metric collection |
| `tracing_enabled` | Enables or disables span creation per request |
| `otlp_endpoint` | Where spans are exported |
| `trace_sample_rate` | Fraction of requests traced |

---

## Full application example

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from obskit.config import configure
from obskit.tracing import setup_tracing
from obskit.middleware.fastapi import (
    ObskitMiddleware,
    create_health_router,
    create_metrics_router,
    create_diagnose_router,
)
from obskit.health import get_health_checker
import redis.asyncio as aioredis

checker = get_health_checker()

@asynccontextmanager
async def lifespan(app: FastAPI):
    configure(
        service_name="order-service",
        environment="production",
        version="2.0.0",
        otlp_endpoint="http://tempo:4317",
        trace_sample_rate=0.1,
    )
    setup_tracing(
        exporter_endpoint="http://tempo:4317",
        sample_rate=0.1,
        instrument=["fastapi", "sqlalchemy", "redis"],
    )

    redis_client = aioredis.Redis(host="redis", port=6379)
    checker.add_readiness_check("redis", lambda: redis_client.ping())
    yield

app = FastAPI(lifespan=lifespan)

# Add middleware BEFORE including routers
app.add_middleware(
    ObskitMiddleware,
    exclude_paths=["/health", "/metrics", "/diagnose"],
)

# Mount built-in observability routes
app.include_router(create_health_router())
app.include_router(create_metrics_router())
app.include_router(create_diagnose_router())

@app.post("/orders")
async def create_order(order: dict):
    return {"order_id": "ord-123"}
```

---

## Kubernetes probe alignment

Use the built-in health routes directly in your Kubernetes manifests:

```yaml
livenessProbe:
  httpGet:
    path: /health/live
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 15

readinessProbe:
  httpGet:
    path: /health/ready
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 10
```
