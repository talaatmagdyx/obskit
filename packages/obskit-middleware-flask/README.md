<div align="center">

# 🌶️ obskit-middleware-flask

**Drop-in Flask middleware for automatic correlation IDs, RED metrics, and distributed tracing on every request**

---

[![PyPI](https://img.shields.io/pypi/v/obskit-middleware-flask.svg?color=blue)](https://pypi.org/project/obskit-middleware-flask/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![obskit](https://img.shields.io/badge/part%20of-obskit-blueviolet.svg)](https://github.com/talaatmagdyx/obskit)

</div>

## What it does

- **WSGI-level instrumentation** — wraps your Flask app with `ObskitFlaskMiddleware(app)` and every route immediately gets correlation ID propagation, RED metrics, structured access logs, and distributed tracing — no blueprint changes, no decorators required
- **Flask-native context** — the correlation ID is stored on Flask's `g` object and made available as `g._obskit_correlation_id`, so you can forward it to downstream services from any view or helper function without any extra imports
- **Application factory compatible** — supports Flask's `init_app()` pattern for deferred initialization, making it compatible with large codebases that create the `app` object separately from where middleware is registered

---

## Installation

```bash
pip install obskit-middleware-flask
```

To add distributed tracing export:

```bash
pip install "obskit-middleware-flask" "obskit-tracing[opentelemetry]"
```

---

## Quick Start

```python
from flask import Flask
from obskit.middleware.flask import ObskitFlaskMiddleware

app = Flask(__name__)
ObskitFlaskMiddleware(app)  # one line — done


@app.route("/orders/<order_id>")
def get_order(order_id):
    return {"order_id": order_id, "status": "confirmed"}
```

After this change, every request produces structured log output:

```
{"event": "request_started",  "method": "GET", "path": "/orders/ord-892", "correlation_id": "a1b2c3d4-...", "client_ip": "10.0.0.5"}
{"event": "request_completed","method": "GET", "path": "/orders/ord-892", "status_code": 200, "duration_ms": 3.1, "correlation_id": "a1b2c3d4-..."}
```

And the response always carries:

```
X-Correlation-ID: a1b2c3d4-9f2e-4c81-b7a3-d8e6f0c1a234
```

---

## WSGI vs ASGI — Why Flask is Different

Flask is a **WSGI** framework, not an ASGI framework like FastAPI. This matters for observability:

- WSGI is synchronous — each request runs in its own thread
- There is no `async with` context manager for request scope
- Observability hooks must use Flask's `before_request` / `after_request` / `teardown_request` lifecycle signals

`ObskitFlaskMiddleware` uses exactly these hooks, which means it integrates cleanly with Flask's threading model and works correctly under Gunicorn with multiple workers. No monkey-patching, no event loop assumptions.

---

## Features

### Application Factory Pattern

Large Flask applications typically build the app object in a factory function. The middleware fully supports this with `init_app()`:

```python
# extensions.py
from obskit.middleware.flask import ObskitFlaskMiddleware

obskit = ObskitFlaskMiddleware()  # no app yet


# app.py
from flask import Flask
from extensions import obskit


def create_app(config: dict) -> Flask:
    app = Flask(__name__)
    app.config.update(config)

    obskit.init_app(app)  # attach middleware here

    from routes.orders import orders_bp
    from routes.payments import payments_bp
    app.register_blueprint(orders_bp)
    app.register_blueprint(payments_bp)

    return app
```

### Correlation ID in Request Context

The correlation ID is available anywhere in the request lifecycle via Flask's `g` object, and via obskit's context helper:

```python
from flask import Flask, g, jsonify
from obskit.middleware.flask import ObskitFlaskMiddleware
from obskit.core.context import get_correlation_id
from obskit.logging import get_logger

app = Flask(__name__)
ObskitFlaskMiddleware(app)

logger = get_logger(__name__)


@app.post("/orders")
def create_order():
    cid = get_correlation_id()          # from obskit context
    cid_g = g._obskit_correlation_id   # also available on g

    logger.info("order_creating", correlation_id=cid, amount=149.99)

    # Forward to a downstream payment service
    import httpx
    resp = httpx.post(
        "http://payment-service/charge",
        json={"amount": 149.99},
        headers={"X-Correlation-ID": cid},  # propagate downstream
    )

    return jsonify({"order_id": "ord-789", "payment_status": resp.json()["status"]})
```

### Blueprint Compatibility

The middleware operates at the application level, not the blueprint level. All blueprints registered with the app are automatically instrumented — no per-blueprint configuration needed:

```python
from flask import Flask, Blueprint
from obskit.middleware.flask import ObskitFlaskMiddleware

app = Flask(__name__)
ObskitFlaskMiddleware(app)

orders_bp = Blueprint("orders", __name__, url_prefix="/orders")
payments_bp = Blueprint("payments", __name__, url_prefix="/payments")
inventory_bp = Blueprint("inventory", __name__, url_prefix="/inventory")


@orders_bp.get("/<order_id>")
def get_order(order_id: str):
    return {"order_id": order_id}  # automatically instrumented


@payments_bp.post("/charge")
def charge():
    return {"status": "ok"}  # automatically instrumented


@inventory_bp.get("/stock")
def get_stock():
    return {"sku": "WIDGET-001", "quantity": 42}  # automatically instrumented


app.register_blueprint(orders_bp)
app.register_blueprint(payments_bp)
app.register_blueprint(inventory_bp)
```

### Excluding Health and Metrics Paths

Kubernetes liveness/readiness probes and Prometheus scrape endpoints should not generate access logs or latency measurements. Exclude them by path prefix:

```python
ObskitFlaskMiddleware(
    app,
    exclude_paths=[
        "/health",
        "/ready",
        "/live",
        "/metrics",
        "/_internal",
    ],
)
```

### Selective Instrumentation

All three observability pillars can be toggled independently:

```python
ObskitFlaskMiddleware(
    app,
    track_metrics=True,   # RED metrics for Prometheus
    track_logging=True,   # Structured JSON access logs
    track_tracing=True,   # OpenTelemetry span propagation
)
```

### Distributed Tracing

When `obskit-tracing` is installed and configured, the middleware extracts W3C `traceparent` / `tracestate` headers from incoming requests and injects them into the response. Outgoing requests made with instrumented clients will be linked to the same trace:

```python
from flask import Flask
from obskit.middleware.flask import ObskitFlaskMiddleware
from obskit.tracing import setup_tracing

setup_tracing(service_name="order-service", exporter_endpoint="http://tempo:4317")

app = Flask(__name__)
ObskitFlaskMiddleware(app)
```

---

## What Every Request Gets

| Signal | Detail | Where it goes |
|--------|--------|---------------|
| `X-Correlation-ID` header | Generated UUID or forwarded from client | Response headers + `g._obskit_correlation_id` |
| `request_started` log | method, path, operation, client_ip | Loki / stdout |
| `request_completed` log | status_code, duration_ms, correlation_id | Loki / stdout |
| `requests_total` counter | Incremented with operation and status labels | Prometheus |
| `request_duration_seconds` histogram | Full latency distribution | Prometheus |
| `traceparent` propagation | Extracted from request headers | Distributed trace graph |
| Error log on exception | error, error_type, duration_ms | Loki / stdout |

---

## Configuration Reference

```python
ObskitFlaskMiddleware(
    app,
    exclude_paths=["/health", "/ready", "/live", "/metrics"],  # default
    track_metrics=True,   # default
    track_logging=True,   # default
    track_tracing=True,   # default
)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `app` | `Flask \| None` | `None` | Flask app; omit to use `init_app()` later |
| `exclude_paths` | `list[str]` | `["/health", "/ready", "/live", "/metrics"]` | Path prefixes skipped entirely |
| `track_metrics` | `bool` | `True` | Record RED metrics in Prometheus |
| `track_logging` | `bool` | `True` | Emit structured access logs |
| `track_tracing` | `bool` | `True` | Extract and propagate OTel trace context |

---

## Complete Example: Order Service

```python
from flask import Flask, jsonify, request
from obskit.middleware.flask import ObskitFlaskMiddleware
from obskit.tracing import setup_tracing
from obskit.logging import get_logger
from obskit.metrics import start_http_server
from obskit.core.context import get_correlation_id

logger = get_logger(__name__)


def create_app() -> Flask:
    setup_tracing(service_name="order-service", exporter_endpoint="http://tempo:4317")
    start_http_server(9090)

    app = Flask(__name__)

    ObskitFlaskMiddleware(
        app,
        exclude_paths=["/health", "/metrics"],
    )

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})  # not instrumented

    @app.post("/orders")
    def create_order():
        body = request.get_json()
        logger.info("order_creating", customer_id=body["customer_id"], total=body["total"])
        # ... business logic ...
        return jsonify({"order_id": "ord-456", "status": "pending", "correlation_id": get_correlation_id()})

    @app.get("/orders/<order_id>")
    def get_order(order_id: str):
        if order_id == "missing":
            return jsonify({"error": "not found"}), 404
            # → automatically records HTTP404 error metric
        return jsonify({"order_id": order_id, "status": "confirmed"})

    return app


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=8000)
```

---

## 🧩 Part of the obskit family

`obskit-middleware-flask` is part of the [obskit](https://github.com/talaatmagdyx/obskit) monorepo — a production-ready observability toolkit for Python microservices.

| Install only this package | Install everything |
|---|---|
| `pip install obskit-middleware-flask` | `pip install "obskit[all]"` |
