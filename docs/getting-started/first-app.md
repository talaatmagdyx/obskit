# Your First Observable FastAPI App

This tutorial walks you through building a production-ready **Order Service** from scratch — a realistic FastAPI application instrumented end-to-end with obskit. By the end you will have:

- Structured JSON logs with automatic trace correlation
- Prometheus RED metrics at `/metrics`
- Distributed traces shipped to Grafana Tempo
- A `/health` endpoint returning live dependency status
- A Docker Compose observability stack (Prometheus + Grafana + Tempo)

**Time to complete:** ~20 minutes

---

## Architecture

```mermaid
graph TD
    Client -->|HTTP| OrderService
    OrderService -->|traces| Tempo
    OrderService -->|logs| Stdout
    OrderService -->|metrics scrape| Prometheus
    Prometheus -->|data source| Grafana
    Tempo -->|data source| Grafana
    Loki -->|data source| Grafana
    OrderService -->|logs| Loki
```

---

## Step 1 — Project Layout

```
order-service/
├── app/
│   ├── __init__.py
│   ├── main.py          ← FastAPI app + middleware
│   ├── settings.py      ← env-var config (Pydantic Settings)
│   ├── observability.py ← tracing + logging + metrics setup
│   ├── health.py        ← health check registration
│   └── routers/
│       └── orders.py    ← business logic
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

---

## Step 2 — Install Packages

=== "requirements.txt"

    ```text
    "obskit[prometheus,otlp,fastapi]>=1.0.0"

    # Web framework
    fastapi==0.115.0
    uvicorn[standard]==0.30.0

    # Database (for the example)
    sqlalchemy==2.0.36
    asyncpg==0.29.0
    ```

=== "pip install"

    ```bash
    pip install \
      "obskit[prometheus,otlp,fastapi]>=1.0.0" \
      "fastapi==0.115.0" \
      "uvicorn[standard]==0.30.0"
    ```

=== "uv (fast)"

    ```bash
    uv pip install \
      "obskit[prometheus,otlp,fastapi]>=1.0.0" \
      "fastapi==0.115.0" \
      "uvicorn[standard]==0.30.0"
    ```

---

## Step 3 — Configure Settings

All obskit configuration is read from environment variables. We use Pydantic Settings to centralise non-obskit config alongside it.

```python title="app/settings.py"
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings — populated from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Service identity (also read by obskit automatically)
    service_name: str = "order-service"
    environment: str = "development"
    version: str = "4.0.0"

    # Database
    database_url: str = "postgresql+asyncpg://postgres:secret@localhost:5432/orders"

    # obskit tracing
    otlp_endpoint: str = "http://tempo:4317"
    trace_sample_rate: float = 0.1

    # obskit logging
    log_level: str = "INFO"
    log_format: str = "json"


settings = Settings()
```

```dotenv title=".env (development)"
SERVICE_NAME=order-service
ENVIRONMENT=development
VERSION=1.0.0

OBSKIT_SERVICE_NAME=order-service
OBSKIT_ENVIRONMENT=development
OBSKIT_VERSION=1.0.0

OBSKIT_OTLP_ENDPOINT=http://localhost:4317
OBSKIT_TRACE_SAMPLE_RATE=1.0

OBSKIT_LOG_LEVEL=DEBUG
OBSKIT_LOG_FORMAT=console

DATABASE_URL=postgresql+asyncpg://postgres:secret@localhost:5432/orders
```

---

## Step 4 — Set Up Observability

With obskit v1.0.0+, a single `configure_observability()` call replaces the separate `setup_tracing()`, `get_logger()`, and `REDMetrics` setup. The returned `Observability` object holds references to all configured components.

=== "v1.0.0+ (recommended)"

    ```python title="app/observability.py"
    """
    Centralised observability bootstrap.

    Import this module at the TOP of main.py, before any framework imports.
    """
    from __future__ import annotations

    from obskit import configure_observability

    from app.settings import settings

    # One call configures tracing, logging, and metrics.
    # Must run before FastAPI / SQLAlchemy / Redis are imported.
    obs = configure_observability(
        service_name=settings.service_name,
        environment=settings.environment,
        version=settings.version,
        otlp_endpoint=settings.otlp_endpoint,
        trace_sample_rate=settings.trace_sample_rate,
        debug=(settings.environment == "development"),
    )

    # Convenience aliases — import these from this module wherever needed.
    log = obs.logger
    red = obs.metrics

    log.info(
        "observability_initialized",
        service=settings.service_name,
        version=settings.version,
        environment=settings.environment,
        otlp_endpoint=settings.otlp_endpoint,
    )

    # Also expose individual Prometheus instruments for fine-grained use
    from prometheus_client import Counter, Histogram  # noqa: E402

    ORDER_CREATED = Counter(
        "orders_created_total",
        "Number of orders successfully created",
        ["payment_method"],
    )

    ORDER_VALUE = Histogram(
        "order_value_dollars",
        "Distribution of order values in USD",
        ["payment_method"],
        buckets=[5, 10, 25, 50, 100, 250, 500, 1000],
    )
    ```

=== "Individual modules (all versions)"

    !!! warning "Import order matters for tracing"
        `setup_tracing()` **must** be called before FastAPI (and SQLAlchemy, Redis, httpx) are imported. obskit auto-patches those libraries at import time. Create `observability.py` and import it at the very top of `main.py`, before `from fastapi import FastAPI`.

    ```python title="app/observability.py"
    """
    Centralised observability bootstrap.

    Import this module at the TOP of main.py, before any framework imports.
    """
    from __future__ import annotations

    import logging

    from obskit.logging import get_logger
    from obskit.metrics import observe_with_exemplar  # noqa: F401 — re-exported for convenience
    from obskit.metrics.red import REDMetrics
    from obskit.tracing import setup_tracing

    from app.settings import settings

    # ── 1. Tracing ──────────────────────────────────────────────────────────────
    # Must run before FastAPI / SQLAlchemy / Redis are imported.
    setup_tracing(
        exporter_endpoint=settings.otlp_endpoint,
        sample_rate=settings.trace_sample_rate,
        # Auto-instrument everything detected in the environment
        instrument=["fastapi", "sqlalchemy", "redis", "httpx"],
        debug=(settings.environment == "development"),
    )

    # ── 2. Logging ──────────────────────────────────────────────────────────────
    # get_logger() reads OBSKIT_LOG_LEVEL and OBSKIT_LOG_FORMAT automatically.
    log = get_logger(__name__)
    log.info(
        "observability_initialized",
        service=settings.service_name,
        version=settings.version,
        environment=settings.environment,
        otlp_endpoint=settings.otlp_endpoint,
    )

    # ── 3. Metrics ──────────────────────────────────────────────────────────────
    # Singleton RED metrics — import `red` from this module wherever needed.
    red = REDMetrics(service=settings.service_name)

    # Also expose individual Prometheus instruments for fine-grained use
    from prometheus_client import Counter, Histogram  # noqa: E402

    ORDER_CREATED = Counter(
        "orders_created_total",
        "Number of orders successfully created",
        ["payment_method"],
    )

    ORDER_VALUE = Histogram(
        "order_value_dollars",
        "Distribution of order values in USD",
        ["payment_method"],
        buckets=[5, 10, 25, 50, 100, 250, 500, 1000],
    )
    ```

---

## Step 5 — Health Checks

```python title="app/health.py"
"""Health check registration for the Order Service."""
from __future__ import annotations

import httpx
from obskit.health import HealthChecker, create_http_check

from app.settings import settings

checker = HealthChecker()  # reads OBSKIT_SERVICE_NAME / OBSKIT_VERSION from env


# ── Dependency checks ────────────────────────────────────────────────────────

checker.add_check("postgres", create_http_check("http://postgres:5432/ping"))
checker.add_check("redis",    create_http_check("http://redis:6379/ping"))


@checker.add_readiness_check("payments_api")
async def check_payments_api() -> bool:
    """Verify the Stripe payment gateway is reachable."""
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get("https://api.stripe.com/v1/ping")
        return resp.status_code < 500
    except Exception:
        return False


@checker.add_liveness_check("self")
async def check_self() -> bool:
    """Trivial liveness probe — always true while the process is running."""
    return True
```

---

## Step 6 — Business Logic (Orders Router)

```python title="app/routers/orders.py"
"""Order management endpoints with full observability."""
from __future__ import annotations

import time
import uuid

from fastapi import APIRouter, HTTPException, status
from obskit.logging import get_logger
from obskit.tracing import async_trace_span
from pydantic import BaseModel

from app.observability import ORDER_CREATED, ORDER_VALUE, observe_with_exemplar, red

router = APIRouter(prefix="/orders", tags=["orders"])
log = get_logger(__name__)


class CreateOrderRequest(BaseModel):
    user_id: str
    items: list[dict]
    payment_method: str = "card"
    total_usd: float


class OrderResponse(BaseModel):
    order_id: str
    status: str
    total_usd: float


@router.post("/", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order(payload: CreateOrderRequest) -> OrderResponse:
    """Create a new order and charge the payment method."""
    order_id = f"ord-{uuid.uuid4().hex[:8]}"
    start = time.perf_counter()

    log.info(
        "order_creation_started",
        order_id=order_id,
        user_id=payload.user_id,
        item_count=len(payload.items),
        total_usd=payload.total_usd,
        payment_method=payload.payment_method,
    )

    try:
        async with async_trace_span(
            "charge_payment",
            attributes={
                "order_id": order_id,
                "payment_method": payload.payment_method,
                "amount_usd": payload.total_usd,
            },
        ):
            # Simulate payment charge
            charged = await _charge_payment(
                order_id=order_id,
                amount=payload.total_usd,
                method=payload.payment_method,
            )

        duration = time.perf_counter() - start

        # Record RED metrics (exemplar auto-attaches trace_id)
        red.record_request(
            endpoint="/orders",
            method="POST",
            status=201,
            duration=duration,
        )

        # Record business metrics with exemplar
        observe_with_exemplar(
            ORDER_VALUE.labels(payment_method=payload.payment_method),
            payload.total_usd,
        )
        ORDER_CREATED.labels(payment_method=payload.payment_method).inc()

        log.info(
            "order_created",
            order_id=order_id,
            user_id=payload.user_id,
            total_usd=payload.total_usd,
            duration_ms=round(duration * 1000, 2),
        )

        return OrderResponse(
            order_id=order_id,
            status="confirmed",
            total_usd=payload.total_usd,
        )

    except PaymentDeclinedError as exc:
        duration = time.perf_counter() - start
        red.record_request(endpoint="/orders", method="POST", status=402, duration=duration)

        log.warning(
            "payment_declined",
            order_id=order_id,
            user_id=payload.user_id,
            reason=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={"error": "payment_declined", "reason": str(exc)},
        ) from exc


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(order_id: str) -> OrderResponse:
    """Retrieve an order by ID."""
    start = time.perf_counter()

    async with async_trace_span("fetch_order", attributes={"order_id": order_id}):
        order = await _fetch_order(order_id)

    duration = time.perf_counter() - start

    if order is None:
        red.record_request(endpoint="/orders/{id}", method="GET", status=404, duration=duration)
        log.warning("order_not_found", order_id=order_id)
        raise HTTPException(status_code=404, detail="Order not found")

    red.record_request(endpoint="/orders/{id}", method="GET", status=200, duration=duration)
    return order


# ── Internal helpers (stub implementations) ──────────────────────────────────

class PaymentDeclinedError(Exception):
    pass


async def _charge_payment(order_id: str, amount: float, method: str) -> bool:
    """Stub: call your real payment gateway here."""
    return True


async def _fetch_order(order_id: str) -> OrderResponse | None:
    """Stub: query your real database here."""
    return OrderResponse(order_id=order_id, status="confirmed", total_usd=49.99)
```

---

## Step 7 — Wire the FastAPI App

=== "v1.0.0+ (recommended)"

    With the new API, `instrument_fastapi(app)` replaces the manual `app.add_middleware(ObskitMiddleware, ...)` call. It configures correlation IDs, request logging, and RED metrics middleware in one step.

    ```python title="app/main.py"
    """
    Order Service — FastAPI entry point.

    Import order is critical:
      1. observability.py  (configure_observability MUST run before FastAPI is imported)
      2. fastapi
      3. routers
    """
    from __future__ import annotations

    # ── MUST BE FIRST: boot observability before any framework import ────────────
    import app.observability  # noqa: F401

    # ── Framework ────────────────────────────────────────────────────────────────
    from contextlib import asynccontextmanager

    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

    # ── obskit ───────────────────────────────────────────────────────────────────
    from obskit import get_observability, instrument_fastapi

    # ── App modules ──────────────────────────────────────────────────────────────
    from app.health import checker
    from app.routers import orders
    from app.settings import settings

    obs = get_observability()


    @asynccontextmanager
    async def lifespan(application: FastAPI):
        """Application lifespan: startup and graceful shutdown."""
        obs.logger.info(
            "service_starting",
            service=settings.service_name,
            version=settings.version,
            environment=settings.environment,
        )
        yield
        obs.logger.info("service_stopping", service=settings.service_name)
        obs.shutdown()


    # ── Application ──────────────────────────────────────────────────────────────
    app = FastAPI(
        title="Order Service",
        description="Example service demonstrating obskit v1.0.0 full-stack observability",
        version=settings.version,
        lifespan=lifespan,
    )

    # ── Middleware (adds correlation ID, auto-logs all requests, records RED metrics) ──
    instrument_fastapi(app)

    # ── Routers ──────────────────────────────────────────────────────────────────
    app.include_router(orders.router)


    # ── Observability endpoints ───────────────────────────────────────────────────
    @app.get("/health", tags=["ops"], include_in_schema=False)
    async def health_endpoint():
        """Kubernetes health check — returns service + dependency status."""
        result = await checker.check_health()
        status_code = 200 if result.is_healthy else 503
        return JSONResponse(content=result.to_dict(), status_code=status_code)


    @app.get("/metrics", tags=["ops"], include_in_schema=False)
    def metrics_endpoint():
        """Prometheus scrape endpoint."""
        return JSONResponse(
            content=generate_latest().decode(),
            media_type=CONTENT_TYPE_LATEST,
        )


    @app.get("/", tags=["ops"])
    async def root():
        return {
            "service": settings.service_name,
            "version": settings.version,
            "docs": "/docs",
            "health": "/health",
            "metrics": "/metrics",
        }
    ```

=== "Individual modules (all versions)"

    Using `ObskitMiddleware` directly gives you full control over middleware options.

    ```python title="app/main.py"
    """
    Order Service — FastAPI entry point.

    Import order is critical:
      1. observability.py  (setup_tracing MUST run before FastAPI is imported)
      2. fastapi
      3. routers
    """
    from __future__ import annotations

    # ── MUST BE FIRST: boot tracing before any framework import ─────────────────
    import app.observability  # noqa: F401

    # ── Framework ────────────────────────────────────────────────────────────────
    from contextlib import asynccontextmanager

    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

    # ── obskit ───────────────────────────────────────────────────────────────────
    from obskit.logging import get_logger
    from obskit.middleware.fastapi import ObskitMiddleware

    # ── App modules ──────────────────────────────────────────────────────────────
    from app.health import checker
    from app.routers import orders
    from app.settings import settings

    log = get_logger(__name__)


    @asynccontextmanager
    async def lifespan(application: FastAPI):
        """Application lifespan: startup and graceful shutdown."""
        log.info(
            "service_starting",
            service=settings.service_name,
            version=settings.version,
            environment=settings.environment,
        )
        yield
        log.info("service_stopping", service=settings.service_name)


    # ── Application ──────────────────────────────────────────────────────────────
    app = FastAPI(
        title="Order Service",
        description="Example service demonstrating obskit full-stack observability",
        version=settings.version,
        lifespan=lifespan,
    )

    # ── Middleware (adds correlation ID, auto-logs all requests, records RED metrics) ──
    app.add_middleware(
        ObskitMiddleware,
        exclude_paths=["/health", "/metrics", "/docs", "/openapi.json"],
        track_metrics=True,
        track_logging=True,
        track_tracing=True,
    )

    # ── Routers ──────────────────────────────────────────────────────────────────
    app.include_router(orders.router)


    # ── Observability endpoints ───────────────────────────────────────────────────
    @app.get("/health", tags=["ops"], include_in_schema=False)
    async def health_endpoint():
        """Kubernetes health check — returns service + dependency status."""
        result = await checker.check_health()
        status_code = 200 if result.is_healthy else 503
        return JSONResponse(content=result.to_dict(), status_code=status_code)


    @app.get("/metrics", tags=["ops"], include_in_schema=False)
    def metrics_endpoint():
        """Prometheus scrape endpoint."""
        return JSONResponse(
            content=generate_latest().decode(),
            media_type=CONTENT_TYPE_LATEST,
        )


    @app.get("/", tags=["ops"])
    async def root():
        return {
            "service": settings.service_name,
            "version": settings.version,
            "docs": "/docs",
            "health": "/health",
            "metrics": "/metrics",
        }
    ```

---

## Step 8 — Docker Compose Observability Stack

```yaml title="docker-compose.yml"
version: "3.9"

services:

  # ── Order Service ─────────────────────────────────────────────────────────
  order-service:
    build: .
    ports:
      - "8000:8000"
    environment:
      OBSKIT_SERVICE_NAME: order-service
      OBSKIT_ENVIRONMENT: production
      OBSKIT_VERSION: "1.0.0"
      OBSKIT_OTLP_ENDPOINT: http://tempo:4317
      OBSKIT_TRACE_SAMPLE_RATE: "1.0"       # 100% sampling in dev
      OBSKIT_LOG_FORMAT: json
      OBSKIT_LOG_LEVEL: INFO
      DATABASE_URL: postgresql+asyncpg://postgres:secret@postgres:5432/orders
    depends_on:
      - postgres
      - redis
      - tempo
    restart: unless-stopped

  # ── PostgreSQL ────────────────────────────────────────────────────────────
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: orders
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: secret
    ports:
      - "5432:5432"

  # ── Redis ─────────────────────────────────────────────────────────────────
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  # ── Grafana Tempo (distributed tracing) ──────────────────────────────────
  tempo:
    image: grafana/tempo:latest
    command: ["-config.file=/etc/tempo.yaml"]
    volumes:
      - ./observability/tempo.yaml:/etc/tempo.yaml
    ports:
      - "4317:4317"    # OTLP gRPC
      - "3200:3200"    # Tempo HTTP API

  # ── Prometheus (metrics) ─────────────────────────────────────────────────
  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./observability/prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"
    command:
      - --config.file=/etc/prometheus/prometheus.yml
      - --enable-feature=exemplar-storage   # enables trace exemplars

  # ── Grafana (dashboards) ──────────────────────────────────────────────────
  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      GF_AUTH_ANONYMOUS_ENABLED: "true"
      GF_AUTH_ANONYMOUS_ORG_ROLE: Admin
    volumes:
      - ./observability/grafana/provisioning:/etc/grafana/provisioning
    depends_on:
      - prometheus
      - tempo
```

=== "prometheus.yml"

    ```yaml title="observability/prometheus.yml"
    global:
      scrape_interval: 15s
      evaluation_interval: 15s

    scrape_configs:
      - job_name: "order-service"
        static_configs:
          - targets: ["order-service:8000"]
        metrics_path: /metrics
    ```

=== "tempo.yaml"

    ```yaml title="observability/tempo.yaml"
    server:
      http_listen_port: 3200

    distributor:
      receivers:
        otlp:
          protocols:
            grpc:
              endpoint: 0.0.0.0:4317

    storage:
      trace:
        backend: local
        local:
          path: /tmp/tempo/traces
    ```

---

## Step 9 — Dockerfile

```dockerfile title="Dockerfile"
FROM python:3.12-slim AS builder
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12-slim
WORKDIR /app
COPY --from=builder /install /usr/local
COPY app/ ./app/

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

---

## Step 10 — Run It

```bash
# Start the full stack
docker compose up -d

# Tail the order-service logs
docker compose logs -f order-service

# Create a test order
curl -X POST http://localhost:8000/orders/ \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "u-123",
    "items": [{"sku": "WIDGET-1", "qty": 2}],
    "payment_method": "card",
    "total_usd": 49.99
  }'

# Check health
curl http://localhost:8000/health | python -m json.tool

# View Prometheus metrics
curl http://localhost:8000/metrics | grep order

# Verify the full diagnostic
docker compose exec order-service python -m obskit.core.diagnose
```

---

## What the Outputs Look Like

=== "Structured log (JSON)"

    ```json
    {
      "event": "order_created",
      "order_id": "ord-a3f2b1c9",
      "user_id": "u-123",
      "total_usd": 49.99,
      "duration_ms": 23.4,
      "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
      "span_id": "00f067aa0ba902b7",
      "service": "order-service",
      "environment": "production",
      "level": "info",
      "timestamp": "2026-02-28T09:12:34.567Z"
    }
    ```

=== "Prometheus metrics"

    ```
    # HELP orders_created_total Number of orders successfully created
    # TYPE orders_created_total counter
    orders_created_total{payment_method="card"} 42.0

    # HELP order_value_dollars Distribution of order values in USD
    # TYPE order_value_dollars histogram
    order_value_dollars_bucket{payment_method="card",le="5.0"} 0
    order_value_dollars_bucket{payment_method="card",le="50.0"} 31
    order_value_dollars_bucket{payment_method="card",le="100.0"} 42
    order_value_dollars_bucket{payment_method="card",le="+Inf"} 42
    order_value_dollars_sum{payment_method="card"} 1847.32
    order_value_dollars_count{payment_method="card"} 42

    # HELP http_request_duration_seconds Request latency (RED method)
    # TYPE http_request_duration_seconds histogram
    http_request_duration_seconds_bucket{endpoint="/orders",method="POST",status="201",le="0.05"} 28 # {trace_id="4bf92f35"} 0.023
    http_request_duration_seconds_bucket{endpoint="/orders",method="POST",status="201",le="0.1"} 40
    ```

=== "Health check response"

    ```json
    {
      "status": "healthy",
      "service": "order-service",
      "version": "4.0.0",
      "environment": "production",
      "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
      "span_id": "00f067aa0ba902b7",
      "checks": {
        "postgres":     {"status": "healthy",   "latency_ms": 1.8},
        "redis":        {"status": "healthy",   "latency_ms": 0.6},
        "payments_api": {"status": "healthy",   "latency_ms": 44.1},
        "self":         {"status": "healthy",   "latency_ms": 0.0}
      },
      "timestamp": "2026-02-28T09:12:34.567Z"
    }
    ```

=== "Grafana views"

    Open Grafana at **http://localhost:3000** (no login in dev mode).

    | Dashboard | URL |
    |-----------|-----|
    | RED Metrics | Explore → Prometheus → `orders_created_total` |
    | Latency histogram | Explore → Prometheus → `http_request_duration_seconds` |
    | Distributed traces | Explore → Tempo → Search |
    | Exemplar drill-down | Click a histogram spike → "Query with exemplar" |

---

## Common Issues

!!! warning "traces not appearing in Tempo"
    - Confirm `OBSKIT_OTLP_ENDPOINT` points to `http://tempo:4317` (Docker network name, not `localhost`)
    - Run `docker compose exec order-service python -m obskit.core.diagnose` to check endpoint reachability
    - Set `OBSKIT_TRACE_SAMPLE_RATE=1.0` in development so 100% of traces are exported

!!! warning "No trace_id in logs"
    `trace_id` is injected only when a span is active at log time. Ensure `configure_observability()` (or `setup_tracing()`) is called before any logger is used, and that requests pass through the OTel middleware (added via `instrument_fastapi()` or `ObskitMiddleware`).

!!! warning "Exemplars not showing in Grafana"
    - Prometheus must be started with `--enable-feature=exemplar-storage`
    - The Grafana data source must have "exemplars" enabled
    - Use `observe_with_exemplar()` instead of the raw `.observe()` method

---

## Next Steps

- [Trace-Log Correlation](../guides/trace-log-correlation.md) — deep dive on how IDs flow
- [Trace Exemplars](../guides/trace-exemplars.md) — metric-to-trace drill-down in Grafana
- [Docker Compose Stack](../guides/docker-compose.md) — full observability stack configuration
- [SLO Tracking](../user-guide/slo.md) — error-budget burn-rate alerts
