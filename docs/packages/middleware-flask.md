# Flask Middleware

Automatic per-request observability for Flask applications. Provides the same correlation ID propagation, structured logging, RED metrics, and distributed tracing as the FastAPI middleware, using Flask's before/after request hooks.

## Installation

```bash
pip install "obskit[flask]"
```

---

## ObskitFlaskMiddleware

### What it provides per request

| Feature | Details |
|---|---|
| Correlation ID | Reads `X-Correlation-ID` header or auto-generates a UUID4; stored in Flask `g` and in obskit's context vars |
| Structured logging | Logs request start and completion (method, path, status code, duration) |
| RED metrics | Updates `<service>_requests_total`, `<service>_errors_total`, `<service>_request_duration_seconds` |
| Distributed tracing | Extracts `traceparent` / `tracestate` from incoming headers; creates a root span for the request |
| Response headers | Adds `X-Correlation-ID` and `X-Trace-Id` to every response |

### Minimal setup

```python
from flask import Flask
from obskit.middleware.flask import ObskitFlaskMiddleware
from obskit.config import configure

app = Flask(__name__)

configure(
    service_name="order-service",
    environment="production",
    otlp_endpoint="http://tempo:4317",
)

ObskitFlaskMiddleware(app)

@app.route("/orders")
def get_orders():
    return {"orders": []}
```

### Configuration

```python
ObskitFlaskMiddleware(
    app,
    exclude_paths=["/health", "/metrics"],   # skip observability for these prefixes
    track_metrics=True,
    track_logging=True,
    track_tracing=True,
)
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `app` | `Flask \| None` | `None` | Flask app; omit to use `init_app()` pattern |
| `exclude_paths` | `list[str]` | `["/health", "/metrics"]` | Path prefixes excluded from overhead |
| `track_metrics` | `bool` | `True` | Enable RED metrics |
| `track_logging` | `bool` | `True` | Enable structured request logging |
| `track_tracing` | `bool` | `True` | Enable OTel span per request |

---

## Application factory pattern

```python
from flask import Flask
from obskit.middleware.flask import ObskitFlaskMiddleware

middleware = ObskitFlaskMiddleware()   # init_app not called yet

def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__)
    if config:
        app.config.update(config)

    middleware.init_app(app)
    return app
```

---

## Accessing correlation ID in views

The correlation ID is available from two places during a request:

```python
from flask import g
from obskit.correlation import get_correlation_id

@app.route("/orders/<order_id>")
def get_order(order_id: str):
    # From Flask g object (set by middleware)
    cid = g.correlation_id

    # Or from obskit context vars (works outside request context too)
    cid = get_correlation_id()

    return {"order_id": order_id, "correlation_id": cid}
```

---

## Health endpoint

```python
from flask import Flask, jsonify
from obskit.health import get_health_checker
import redis

app = Flask(__name__)
checker = get_health_checker()

redis_client = redis.Redis(host="redis", port=6379)
checker.add_readiness_check("redis", lambda: redis_client.ping())

@app.route("/health")
def health():
    import asyncio
    result = asyncio.run(checker.check_health())
    status_code = 200 if result.healthy else 503
    return jsonify(result.to_dict()), status_code

@app.route("/health/live")
def liveness():
    import asyncio
    result = asyncio.run(checker.check_liveness())
    return jsonify(result.to_dict()), 200 if result.healthy else 503

@app.route("/health/ready")
def readiness():
    import asyncio
    result = asyncio.run(checker.check_readiness())
    return jsonify(result.to_dict()), 200 if result.healthy else 503
```

---

## Metrics endpoint

```python
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from flask import Response

@app.route("/metrics")
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)
```

---

## Using with Flask blueprints

obskit middleware applies globally to all blueprints because it hooks into `before_request` / `after_request` at the application level.

```python
from flask import Flask, Blueprint
from obskit.middleware.flask import ObskitFlaskMiddleware

orders_bp = Blueprint("orders", __name__, url_prefix="/orders")

@orders_bp.route("/")
def list_orders():
    return {"orders": []}

app = Flask(__name__)
ObskitFlaskMiddleware(app)
app.register_blueprint(orders_bp)
```

---

## Full example

```python
from flask import Flask, jsonify
from obskit.config import configure
from obskit.tracing import setup_tracing
from obskit.middleware.flask import ObskitFlaskMiddleware
from obskit.health import get_health_checker
from obskit.health.checks import create_memory_check
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from flask import Response

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
    instrument=["requests"],
)

app = Flask(__name__)
ObskitFlaskMiddleware(app, exclude_paths=["/health", "/metrics"])

checker = get_health_checker()
checker.add_liveness_check("memory", create_memory_check(threshold_percent=90))

@app.route("/health")
def health():
    import asyncio
    result = asyncio.run(checker.check_health())
    return jsonify(result.to_dict()), 200 if result.healthy else 503

@app.route("/metrics")
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)

@app.route("/orders", methods=["GET"])
def list_orders():
    return jsonify({"orders": []})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
```

---

## Kubernetes probe configuration

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

---

## Settings reference

All behaviour is driven by `ObskitSettings`. Key settings for the Flask middleware:

| Setting | Env var | Effect |
|---|---|---|
| `service_name` | `OBSKIT_SERVICE_NAME` | RED metrics namespace and log `service` field |
| `log_level` | `OBSKIT_LOG_LEVEL` | Request log verbosity |
| `log_format` | `OBSKIT_LOG_FORMAT` | `json` or `console` |
| `metrics_enabled` | `OBSKIT_METRICS_ENABLED` | Toggle metric collection |
| `tracing_enabled` | `OBSKIT_TRACING_ENABLED` | Toggle OTel span creation |
| `trace_sample_rate` | `OBSKIT_TRACE_SAMPLE_RATE` | Fraction of requests traced |
