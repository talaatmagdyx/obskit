# FastAPI Integration Tutorial

Build a production-ready **Order Service** with full observability in under 30 minutes. By the end you will have:

- Distributed traces flowing to **Grafana Tempo**
- RED metrics scraped by **Prometheus** and visualised in **Grafana**
- Structured JSON logs shipped to **Loki** with automatic `trace_id` injection
- Health checks compatible with Kubernetes probes
- SLO tracking from day one

---

## Project Structure

```
order-service/
├── app/
│   ├── __init__.py
│   ├── main.py          ← application entry point
│   ├── routers/
│   │   ├── orders.py
│   │   └── health.py
│   ├── services/
│   │   └── payment.py   ← external call to payment API
│   └── models.py
├── tests/
│   ├── conftest.py
│   └── test_orders.py
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── .env
```

---

## Dependencies

```text
# requirements.txt
fastapi>=0.111.0
uvicorn[standard]>=0.29.0
httpx>=0.27.0
pydantic>=2.0.0

"obskit[prometheus,otlp,fastapi]>=1.0.0"
fastapi>=0.100.0
uvicorn[standard]>=0.30.0
```

---

## Application Entry Point

```python
# app/main.py
"""
Order Service — production-ready FastAPI app with full obskit observability.
"""
from __future__ import annotations

import os
import asyncio

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

# ── obskit: unified setup (v1.0.0+) ──────────────────────────────────────────
from obskit import configure_observability
from obskit.health import HealthChecker
from obskit.health.checks import DatabaseCheck, RedisCheck

# configure_observability() replaces the old configure() + setup_tracing() +
# configure_logging() sequence.  It returns an Observability handle with
# .tracer, .metrics, .logger, .config, and .shutdown().
obs = configure_observability(
    service_name=os.getenv("OBSKIT_SERVICE_NAME", "order-service"),
    environment=os.getenv("OBSKIT_ENVIRONMENT", "development"),
    version=os.getenv("OBSKIT_VERSION", "4.0.0"),
    tracing_enabled=True,
    otlp_endpoint=os.getenv("OBSKIT_OTLP_ENDPOINT", "http://localhost:4317"),
)

logger = obs.logger(__name__)

# ── FastAPI application ───────────────────────────────────────────────────────
app = FastAPI(
    title="Order Service",
    description="Production-ready order management with full observability",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── Middleware (v1.0.0: use instrument_fastapi for one-line setup) ────────────
from obskit import instrument_fastapi

instrument_fastapi(
    app,
    exclude_paths={"/health/live", "/health/ready", "/metrics", "/docs", "/redoc"},
)
# instrument_fastapi() attaches ObskitMiddleware (raw ASGI) under the hood.

# ── Health checker ────────────────────────────────────────────────────────────
health_checker = HealthChecker()
health_checker.add_check(
    DatabaseCheck(
        name="postgres",
        connection_string=os.getenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/orders"),
        timeout=3.0,
        critical=True,
    )
)
health_checker.add_check(
    RedisCheck(
        name="redis",
        url=os.getenv("REDIS_URL", "redis://localhost:6379"),
        timeout=2.0,
        critical=True,
    )
)

# ── Routers ───────────────────────────────────────────────────────────────────
from app.routers.orders import router as orders_router
from app.routers.health import router as health_router

app.include_router(orders_router, prefix="/orders", tags=["orders"])
app.include_router(health_router, tags=["health"])

# ── Lifecycle ─────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def on_startup():
    logger.info("order-service starting", version="1.0.0")
    logger.info("observability ready", config=str(obs.config))

@app.on_event("shutdown")
async def on_shutdown():
    logger.info("order-service shutting down — flushing telemetry")
    await obs.shutdown()

# ── Diagnose endpoint ─────────────────────────────────────────────────────────
@app.get("/diagnose", include_in_schema=False)
async def diagnose():
    """obskit diagnostic snapshot — restrict to internal network in production."""
    from obskit import get_observability
    o = get_observability()
    cfg = o.config
    return {
        "service": cfg.service_name,
        "environment": cfg.environment,
        "version": cfg.version,
        "tracing_enabled": cfg.tracing_enabled,
        "otlp_endpoint": cfg.otlp_endpoint,
    }
```

---

## Orders Router

```python
# app/routers/orders.py
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from opentelemetry import trace

from obskit.logging import get_logger
from obskit.metrics import counter, histogram
from obskit.slo import SLOTracker
from app.models import OrderCreate, OrderResponse
from app.services.payment import charge_payment

router = APIRouter()
logger = get_logger(__name__)
tracer = trace.get_tracer(__name__)

# ── Metrics ───────────────────────────────────────────────────────────────────
orders_created = counter(
    name="orders_created_total",
    documentation="Total number of orders created",
    labels=["status"],
)
order_value = histogram(
    name="order_value_dollars",
    documentation="Distribution of order values in USD",
    buckets=[1, 5, 10, 25, 50, 100, 250, 500, 1000],
)

# ── SLO tracking ─────────────────────────────────────────────────────────────
order_slo = SLOTracker(
    name="order-creation-availability",
    target=0.999,   # 99.9 % success rate
    window_days=30,
)

# ── In-memory store (replace with your DB layer) ──────────────────────────────
_orders: dict[str, dict] = {}


@router.post("/", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order(body: OrderCreate):
    """
    Create a new order and charge the payment method.

    Traces: every request creates a span with order_id, amount attributes.
    Logs  : structured events at each step with trace_id injected automatically.
    Metrics: orders_created_total counter, order_value_dollars histogram.
    SLO   : tracks success/failure against 99.9 % availability target.
    """
    order_id = str(uuid.uuid4())

    # Add order-level attributes to the current span (created by middleware)
    span = trace.get_current_span()
    span.set_attribute("order.id", order_id)
    span.set_attribute("order.amount", body.amount)
    span.set_attribute("order.currency", body.currency)
    span.set_attribute("order.item_count", len(body.items))

    logger.info(
        "creating order",
        order_id=order_id,
        amount=body.amount,
        currency=body.currency,
        item_count=len(body.items),
    )

    # ── Payment processing (external call) ───────────────────────────────────
    with tracer.start_as_current_span("payment.charge") as payment_span:
        try:
            payment_result = await charge_payment(
                order_id=order_id,
                amount=body.amount,
                currency=body.currency,
            )
            payment_span.set_attribute("payment.transaction_id", payment_result["transaction_id"])
            payment_span.set_attribute("payment.status", "success")
        except Exception as exc:
            payment_span.record_exception(exc)
            payment_span.set_attribute("payment.status", "failed")
            logger.error("payment failed", order_id=order_id, error=str(exc))
            orders_created.labels(status="payment_failed").inc()
            order_slo.record_failure()
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Payment processing failed",
            )

    # ── Persist order ─────────────────────────────────────────────────────────
    order = {
        "id": order_id,
        "items": body.items,
        "amount": body.amount,
        "currency": body.currency,
        "status": "confirmed",
        "payment_transaction_id": payment_result["transaction_id"],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _orders[order_id] = order

    # ── Record metrics ────────────────────────────────────────────────────────
    orders_created.labels(status="success").inc()
    order_value.observe(body.amount)
    order_slo.record_success()

    logger.info(
        "order created",
        order_id=order_id,
        transaction_id=payment_result["transaction_id"],
        amount=body.amount,
    )

    return OrderResponse(**order)


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(order_id: str):
    """Retrieve an order by ID."""
    span = trace.get_current_span()
    span.set_attribute("order.id", order_id)

    logger.info("fetching order", order_id=order_id)

    order = _orders.get(order_id)
    if order is None:
        logger.warning("order not found", order_id=order_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order {order_id!r} not found",
        )

    return OrderResponse(**order)
```

---

## Health Router

```python
# app/routers/health.py
from fastapi import APIRouter, Response
from obskit.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)

# Import health_checker from main (avoids circular import in production code)
def _get_checker():
    from app.main import health_checker
    return health_checker


@router.get("/health/live", tags=["health"])
async def liveness():
    """Kubernetes liveness probe — returns 200 if the process is alive."""
    return {"status": "alive"}


@router.get("/health/ready", tags=["health"])
async def readiness(response: Response):
    """
    Kubernetes readiness probe — returns 200 only when all dependencies are healthy.
    Returns 503 when any critical dependency is unreachable.
    """
    checker = _get_checker()
    result = await checker.check_all()

    if not result.is_healthy:
        response.status_code = 503
        logger.warning("readiness check failed", details=result.details)

    return {
        "status": "ready" if result.is_healthy else "unhealthy",
        "checks": result.details,
    }


@router.get("/health/startup", tags=["health"])
async def startup_check():
    """
    Kubernetes startup probe — confirms the app has fully initialised.
    Use with failureThreshold=30, periodSeconds=3 (90 s total window).
    """
    return {"status": "started"}
```

---

## Models

```python
# app/models.py
from pydantic import BaseModel, Field
from typing import List

class OrderItem(BaseModel):
    sku: str
    quantity: int = Field(ge=1)
    unit_price: float = Field(ge=0.0)

class OrderCreate(BaseModel):
    items: List[OrderItem] = Field(min_length=1)
    currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")

    @property
    def amount(self) -> float:
        return sum(i.quantity * i.unit_price for i in self.items)

class OrderResponse(BaseModel):
    id: str
    items: List[OrderItem]
    amount: float
    currency: str
    status: str
    payment_transaction_id: str
    created_at: str
```

---

## Payment Service

```python
# app/services/payment.py
"""
External payment API integration.
"""
from __future__ import annotations

import httpx
from obskit.logging import get_logger

logger = get_logger(__name__)

PAYMENT_API_URL = "https://api.payments.example.com/v1/charge"


async def charge_payment(
    order_id: str,
    amount: float,
    currency: str,
) -> dict:
    """Call the external payment gateway."""
    logger.info("charging payment", order_id=order_id, amount=amount, currency=currency)

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            PAYMENT_API_URL,
            json={
                "order_id": order_id,
                "amount": amount,
                "currency": currency,
            },
            headers={"Authorization": "Bearer <token-from-secret>"},
        )
        response.raise_for_status()
        data = response.json()

    logger.info(
        "payment succeeded",
        order_id=order_id,
        transaction_id=data["transaction_id"],
    )
    return data
```

---

## Trace–Log Correlation in Action

When a request comes in, the middleware creates a span. Every `logger.info()` call inside that request automatically injects `trace_id` and `span_id`:

```json
{
  "timestamp": "2026-02-28T10:30:01.234Z",
  "level": "info",
  "event": "creating order",
  "order_id": "3f2c1a9b-...",
  "amount": 99.95,
  "currency": "USD",
  "service": "order-service",
  "environment": "production",
  "version": "4.0.0",
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "span_id": "00f067aa0ba902b7"
}
```

In Grafana, you can click the `trace_id` in a Loki log line and jump directly to the corresponding Tempo trace.

---

## pytest Test Examples

```python
# tests/conftest.py
import pytest
from fastapi.testclient import TestClient
from obskit import configure_observability, reset_observability

@pytest.fixture(autouse=True)
def obskit_test_config():
    configure_observability(
        service_name="order-service-test",
        environment="test",
        tracing_enabled=False,
        metrics_enabled=False,
        log_level="WARNING",
    )
    yield
    reset_observability()

@pytest.fixture()
def client():
    from app.main import app
    with TestClient(app) as c:
        yield c
```

```python
# tests/test_orders.py
from unittest.mock import AsyncMock, patch
import pytest

@pytest.fixture
def mock_payment():
    """Mock the payment gateway to avoid network calls."""
    with patch(
        "app.services.payment.charge_payment",
        new=AsyncMock(return_value={"transaction_id": "txn_test_001"}),
    ) as m:
        yield m


def test_create_order_success(client, mock_payment):
    response = client.post(
        "/orders/",
        json={
            "items": [{"sku": "WIDGET-1", "quantity": 2, "unit_price": 9.99}],
            "currency": "USD",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "confirmed"
    assert data["amount"] == pytest.approx(19.98)
    assert "id" in data
    mock_payment.assert_called_once()


def test_get_order_not_found(client):
    response = client.get("/orders/does-not-exist")
    assert response.status_code == 404


def test_create_order_payment_failure(client):
    from unittest.mock import AsyncMock, patch
    with patch(
        "app.services.payment.charge_payment",
        new=AsyncMock(side_effect=Exception("gateway timeout")),
    ):
        response = client.post(
            "/orders/",
            json={
                "items": [{"sku": "WIDGET-1", "quantity": 1, "unit_price": 5.0}],
            },
        )
    assert response.status_code == 502


def test_health_liveness(client):
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "alive"
```

---

## Docker Compose for Local Development

```yaml
# docker-compose.yml
version: "3.9"

services:
  order-service:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8000:8000"    # FastAPI
      - "9090:9090"    # Prometheus metrics
    environment:
      OBSKIT_SERVICE_NAME: order-service
      OBSKIT_ENVIRONMENT: development
      OBSKIT_VERSION: "1.0.0-dev"
      OBSKIT_TRACING_ENABLED: "true"
      OBSKIT_OTLP_ENDPOINT: http://tempo:4317
      OBSKIT_OTLP_INSECURE: "true"
      OBSKIT_TRACE_SAMPLE_RATE: "1.0"
      OBSKIT_METRICS_ENABLED: "true"
      OBSKIT_METRICS_PORT: "9090"
      OBSKIT_LOG_LEVEL: DEBUG
      OBSKIT_LOG_FORMAT: console    # human-readable in dev
      DATABASE_URL: postgresql://user:pass@postgres:5432/orders
      REDIS_URL: redis://redis:6379
    depends_on:
      - postgres
      - redis
      - tempo

  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: user
      POSTGRES_PASSWORD: pass
      POSTGRES_DB: orders
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  # ── Observability stack ────────────────────────────────────────────────────
  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./docker/prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9091:9090"
    command:
      - "--config.file=/etc/prometheus/prometheus.yml"
      - "--storage.tsdb.retention.time=7d"

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      GF_SECURITY_ADMIN_PASSWORD: admin
      GF_FEATURE_TOGGLES_ENABLE: traceqlEditor
    volumes:
      - ./docker/grafana/provisioning:/etc/grafana/provisioning

  tempo:
    image: grafana/tempo:latest
    command: ["-config.file=/etc/tempo.yaml"]
    volumes:
      - ./docker/tempo.yaml:/etc/tempo.yaml
    ports:
      - "4317:4317"   # OTLP gRPC
      - "3200:3200"   # HTTP API

  loki:
    image: grafana/loki:latest
    command: ["-config.file=/etc/loki/config.yaml"]
    volumes:
      - ./docker/loki.yaml:/etc/loki/config.yaml
    ports:
      - "3100:3100"

  promtail:
    image: grafana/promtail:latest
    command: ["-config.file=/etc/promtail/config.yaml"]
    volumes:
      - ./docker/promtail.yaml:/etc/promtail/config.yaml
      - /var/log:/var/log:ro
```

---

## Dockerfile

```dockerfile
# Dockerfile
FROM python:3.12-slim AS builder

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

FROM python:3.12-slim AS runtime

WORKDIR /app
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY app/ app/

# Non-root user
RUN adduser --disabled-password --gecos "" appuser
USER appuser

EXPOSE 8000 9090

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

---

## Expected Output in Grafana

After sending requests, you should see:

**Prometheus / Grafana — RED Dashboard**

```
http_requests_total{method="POST", route="/orders/", status="201"}    →  rising counter
http_request_duration_seconds_bucket{route="/orders/", le="0.1"}      →  latency histogram
orders_created_total{status="success"}                                  →  business counter
order_value_dollars_sum / order_value_dollars_count                     →  average order value
```

**Grafana Tempo — Trace View**

```
Trace: POST /orders
  ├── POST /orders (42 ms)          ← HTTP span created by middleware
  │   ├── payment.charge (35 ms)    ← manual span in orders.py
  │   └── db.insert (3 ms)          ← auto-instrumented SQLAlchemy span
```

**Loki — Log Correlation**

Click the `trace_id` link in any Loki log line to jump directly to the full trace in Tempo.

---

## Run Locally

```bash
# Start the full stack
docker-compose up -d

# Wait for services to be healthy
docker-compose ps

# Create an order
curl -s -X POST http://localhost:8000/orders/ \
  -H "Content-Type: application/json" \
  -d '{"items": [{"sku": "WIDGET-1", "quantity": 2, "unit_price": 9.99}]}' \
  | python -m json.tool

# View metrics
curl -s http://localhost:9090/metrics | grep orders

# Open Grafana
open http://localhost:3000   # admin / admin

# Open Tempo directly
open http://localhost:3200
```

---

## RED Metrics in Detail

The `ObskitMiddleware` automatically records three core RED metrics for every non-excluded route:

=== "Rate"

    ```promql
    # Requests per second per endpoint
    rate(http_requests_total{service="order-service"}[1m])
    ```

=== "Errors"

    ```promql
    # Error ratio per endpoint
    sum(rate(http_requests_total{service="order-service", status=~"5.."}[5m]))
    /
    sum(rate(http_requests_total{service="order-service"}[5m]))
    ```

=== "Duration"

    ```promql
    # p99 latency per endpoint
    histogram_quantile(0.99,
      sum(rate(http_request_duration_seconds_bucket{service="order-service"}[5m])) by (le, route)
    )
    ```

---

!!! tip "SLO burn rate in Grafana"
    Add this PromQL query to your Grafana dashboard to see the 30-day error budget remaining:

    ```promql
    1 - (
      sum_over_time(slo_error_budget_remaining{slo="order-creation-availability"}[30d])
      / scalar(slo_target{slo="order-creation-availability"})
    )
    ```

!!! warning "Health check exclusion"
    Always exclude `/health/*` and `/metrics` from the `ObskitMiddleware` via the `exclude_paths` argument. Including them pollutes your RED metrics with high-frequency internal traffic that skews error rates and latency histograms.

!!! info "Auto-instrumentation for SQLAlchemy"
    If you use SQLAlchemy, install `opentelemetry-instrumentation-sqlalchemy` and it will automatically create spans for every SQL query, visible as child spans of your route handler spans in Tempo.

    ```bash
    pip install opentelemetry-instrumentation-sqlalchemy
    ```

    ```python
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
    SQLAlchemyInstrumentor().instrument(engine=engine)
    ```
