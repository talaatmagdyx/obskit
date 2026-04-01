# Flask Integration Tutorial

This tutorial adapts the Order Service from the [FastAPI example](fastapi.md) for **Flask**, demonstrating the factory pattern, Gunicorn deployment, and the key differences between the two integrations.

---

## Key Differences from FastAPI

| Aspect | FastAPI | Flask |
|---|---|---|
| Middleware | `instrument_fastapi(app)` | `instrument_flask(app)` |
| Async support | Native `async def` routes | Requires `gevent` or thread-based concurrency |
| Startup hooks | `@app.on_event("startup")` | `@app.before_first_request` or factory init |
| Request context | `Request` object injected | `flask.request` thread-local |
| Production server | `uvicorn` | `gunicorn` with `sync` or `gevent` workers |
| Type validation | Pydantic models natively | Manual validation or `flask-pydantic` extension |

---

## Project Structure

```
order-service-flask/
├── app/
│   ├── __init__.py      ← application factory
│   ├── config.py        ← Flask config (not obskit config)
│   ├── routes/
│   │   ├── orders.py
│   │   └── health.py
│   └── services/
│       └── payment.py
├── tests/
│   ├── conftest.py
│   └── test_orders.py
├── wsgi.py              ← Gunicorn entry point
├── Dockerfile
├── requirements.txt
└── .env
```

---

## Application Factory

```python
# app/__init__.py
"""
Order Service — Flask application factory with obskit observability.
"""
from __future__ import annotations

import os

# ── obskit: unified setup (v1.0.0+) ──────────────────────────────────────────
from obskit import configure_observability, instrument_flask

obs = configure_observability(
    service_name=os.getenv("OBSKIT_SERVICE_NAME", "order-service-flask"),
    environment=os.getenv("OBSKIT_ENVIRONMENT", "development"),
    version=os.getenv("OBSKIT_VERSION", "4.0.0"),
)

logger = obs.logger(__name__)

from flask import Flask


def create_app(config_object: str | None = None) -> Flask:
    """
    Flask application factory.

    Parameters
    ----------
    config_object
        Dotted import path to a Flask config class, e.g. "app.config.ProductionConfig".
        Defaults to development config.

    Returns
    -------
    Flask
        Configured Flask application with obskit middleware attached.
    """
    app = Flask(__name__, instance_relative_config=False)

    # ── Flask config ─────────────────────────────────────────────────────────
    config_object = config_object or os.getenv("FLASK_CONFIG", "app.config.DevelopmentConfig")
    app.config.from_object(config_object)

    # ── obskit WSGI middleware (v1.0.0: one-line instrumentation) ────────────
    instrument_flask(
        app,
        exclude_paths={"/health/live", "/health/ready", "/metrics"},
    )

    # ── Register blueprints ───────────────────────────────────────────────────
    from app.routes.orders import orders_bp
    from app.routes.health import health_bp

    app.register_blueprint(orders_bp)
    app.register_blueprint(health_bp)

    logger.info("flask app created", config=config_object)
    return app
```

---

## Flask Config

```python
# app/config.py
import os


class Config:
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-me")
    JSON_SORT_KEYS = False


class DevelopmentConfig(Config):
    DEBUG = True
    TESTING = False


class ProductionConfig(Config):
    DEBUG = False
    TESTING = False


class TestingConfig(Config):
    DEBUG = True
    TESTING = True
```

---

## Orders Blueprint

```python
# app/routes/orders.py
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify, abort
from opentelemetry import trace

from obskit.logging import get_logger
from obskit.metrics import counter, histogram
from obskit.slo import SLOTracker
from app.services.payment import charge_payment

orders_bp = Blueprint("orders", __name__, url_prefix="/orders")
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

# ── SLO ───────────────────────────────────────────────────────────────────────
order_slo = SLOTracker(
    name="order-creation-availability",
    target=0.999,
    window_days=30,
)

# ── Storage ───────────────────────────────────────────────────────────────────
_orders: dict[str, dict] = {}


@orders_bp.route("/", methods=["POST"])
def create_order():
    """POST /orders — create a new order."""
    body = request.get_json(force=True)
    if not body or not body.get("items"):
        abort(400, description="Request body must include 'items'")

    order_id = str(uuid.uuid4())
    items = body["items"]
    currency = body.get("currency", "USD")
    amount = sum(i["quantity"] * i["unit_price"] for i in items)

    # Enrich current span with order attributes
    span = trace.get_current_span()
    span.set_attribute("order.id", order_id)
    span.set_attribute("order.amount", amount)
    span.set_attribute("order.currency", currency)

    logger.info("creating order", order_id=order_id, amount=amount, currency=currency)

    # External payment call
    with tracer.start_as_current_span("payment.charge") as pspan:
        try:
            result = charge_payment(order_id=order_id, amount=amount, currency=currency)
            pspan.set_attribute("payment.transaction_id", result["transaction_id"])
        except Exception as exc:
            pspan.record_exception(exc)
            logger.error("payment failed", order_id=order_id, error=str(exc))
            orders_created.labels(status="payment_failed").inc()
            order_slo.record_failure()
            return jsonify({"error": "Payment processing failed"}), 502

    order = {
        "id": order_id,
        "items": items,
        "amount": amount,
        "currency": currency,
        "status": "confirmed",
        "payment_transaction_id": result["transaction_id"],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _orders[order_id] = order

    orders_created.labels(status="success").inc()
    order_value.observe(amount)
    order_slo.record_success()

    logger.info("order created", order_id=order_id, transaction_id=result["transaction_id"])
    return jsonify(order), 201


@orders_bp.route("/<order_id>", methods=["GET"])
def get_order(order_id: str):
    """GET /orders/<id> — retrieve a single order."""
    span = trace.get_current_span()
    span.set_attribute("order.id", order_id)

    order = _orders.get(order_id)
    if order is None:
        logger.warning("order not found", order_id=order_id)
        abort(404, description=f"Order {order_id!r} not found")

    return jsonify(order), 200
```

---

## Health Blueprint

```python
# app/routes/health.py
from flask import Blueprint, jsonify, current_app

from obskit.health import HealthChecker
from obskit.health.checks import DatabaseCheck, RedisCheck
from obskit.logging import get_logger

health_bp = Blueprint("health", __name__)
logger = get_logger(__name__)

# Lazily initialised health checker
_checker: HealthChecker | None = None


def _get_checker() -> HealthChecker:
    global _checker
    if _checker is None:
        import os
        _checker = HealthChecker()
        _checker.add_check(
            DatabaseCheck(
                name="postgres",
                connection_string=os.getenv(
                    "DATABASE_URL", "postgresql://user:pass@localhost:5432/orders"
                ),
                timeout=3.0,
                critical=True,
            )
        )
        _checker.add_check(
            RedisCheck(
                name="redis",
                url=os.getenv("REDIS_URL", "redis://localhost:6379"),
                timeout=2.0,
                critical=True,
            )
        )
    return _checker


@health_bp.route("/health/live")
def liveness():
    return jsonify({"status": "alive"}), 200


@health_bp.route("/health/ready")
def readiness():
    import asyncio

    checker = _get_checker()
    # Flask is synchronous; run the async check in a new event loop
    result = asyncio.run(checker.check_all())

    status_code = 200 if result.is_healthy else 503
    return jsonify({
        "status": "ready" if result.is_healthy else "unhealthy",
        "checks": result.details,
    }), status_code


@health_bp.route("/health/startup")
def startup_check():
    return jsonify({"status": "started"}), 200
```

---

---

## Gunicorn Deployment

```python
# wsgi.py — entry point for Gunicorn
from app import create_app

application = create_app("app.config.ProductionConfig")

if __name__ == "__main__":
    application.run()
```

```bash
# Start with Gunicorn (sync workers — default)
gunicorn \
  --bind 0.0.0.0:8000 \
  --workers 4 \
  --worker-class sync \
  --timeout 30 \
  --graceful-timeout 20 \
  --access-logfile - \
  --error-logfile - \
  wsgi:application

# Or with gevent workers for I/O concurrency
pip install gevent
gunicorn \
  --bind 0.0.0.0:8000 \
  --workers 4 \
  --worker-class gevent \
  --worker-connections 100 \
  wsgi:application
```

### Gunicorn config file

```python
# gunicorn.conf.py
import multiprocessing

bind = "0.0.0.0:8000"
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"     # or "gevent" for I/O-heavy services
timeout = 30
graceful_timeout = 20
keepalive = 5
loglevel = "info"
accesslog = "-"
errorlog  = "-"
# Forward access logs through Python logging (picked up by structlog)
access_log_format = '{"remote_addr":"%(h)s","method":"%(m)s","path":"%(U)s","status":%(s)s,"duration_ms":%(D)s}'
```

---

## pytest Test Examples

```python
# tests/conftest.py
import pytest
from obskit import configure_observability, reset_observability

@pytest.fixture(autouse=True)
def obskit_test_config():
    configure_observability(
        service_name="order-service-flask-test",
        environment="test",
        tracing_enabled=False,
        metrics_enabled=False,
        log_level="WARNING",
    )
    yield
    reset_observability()

@pytest.fixture()
def app():
    from app import create_app
    flask_app = create_app("app.config.TestingConfig")
    flask_app.config["TESTING"] = True
    return flask_app

@pytest.fixture()
def client(app):
    return app.test_client()
```

```python
# tests/test_orders.py
from unittest.mock import patch, MagicMock

def test_create_order_success(client):
    with patch("app.routes.orders.charge_payment",
               return_value={"transaction_id": "txn_test_001"}):
        response = client.post(
            "/orders/",
            json={"items": [{"sku": "A1", "quantity": 1, "unit_price": 10.0}]},
        )
    assert response.status_code == 201
    data = response.get_json()
    assert data["status"] == "confirmed"
    assert data["amount"] == 10.0

def test_get_order_not_found(client):
    response = client.get("/orders/nonexistent-id")
    assert response.status_code == 404

def test_health_liveness(client):
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.get_json()["status"] == "alive"
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
COPY wsgi.py gunicorn.conf.py ./

RUN adduser --disabled-password --gecos "" appuser
USER appuser

EXPOSE 8000 9090

CMD ["gunicorn", "--config", "gunicorn.conf.py", "wsgi:application"]
```

---

## Middleware Internals

The `instrument_flask()` helper (or the underlying `ObskitFlaskMiddleware`) wraps the WSGI callable:

```
HTTP Request
     │
     ▼
ObskitFlaskMiddleware.wsgi_app
     ├── Extract/create trace context (W3C traceparent)
     ├── Start HTTP span
     ├── Call Flask app (inner WSGI callable)
     │     └── Route handler → orders_bp.create_order()
     ├── Record HTTP status, duration → Prometheus counter + histogram
     └── End HTTP span → export to OTLP
     │
     ▼
HTTP Response
```

!!! note "Thread safety"
    Flask's WSGI middleware is thread-safe. Each request runs in its own thread (with `sync` workers) and OpenTelemetry's context propagation uses thread-local storage internally.
