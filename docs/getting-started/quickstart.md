# Quick Start

Get obskit v2.0.0 wired up in a fresh service in **under five minutes**. Each step is independent — copy the ones that apply to your service.

---

## Install

```bash
# Typical microservice stack
pip install "obskit[prometheus,otlp,fastapi]"
```

!!! tip "Just want one thing?"
    obskit uses optional extras. `pip install obskit` is all you need for structured logging, health checks, and resilience. Add extras only for what you need.

---

## Step 1 — Structured Logging with Trace Correlation

obskit wraps structlog under the hood and emits machine-readable JSON by default. Every log record is automatically enriched with `trace_id`, `span_id`, `service`, and `environment` when a span is active.

=== "Code"

    ```python
    from obskit.logging import get_logger

    log = get_logger(__name__)

    # Keyword arguments become top-level JSON fields
    log.info("user_logged_in", user_id="u-123", ip="10.0.0.1")
    log.warning("rate_limit_approaching", user_id="u-123", current_rpm=95, limit_rpm=100)
    log.error("payment_failed", order_id="ord-789", reason="card_declined", amount=49.99)
    ```

=== "JSON output (production)"

    ```json
    {
      "event": "user_logged_in",
      "user_id": "u-123",
      "ip": "10.0.0.1",
      "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
      "span_id": "00f067aa0ba902b7",
      "service": "order-service",
      "environment": "production",
      "level": "info",
      "timestamp": "2026-02-28T09:12:34.567Z"
    }
    ```

    ```json
    {
      "event": "rate_limit_approaching",
      "user_id": "u-123",
      "current_rpm": 95,
      "limit_rpm": 100,
      "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
      "span_id": "00f067aa0ba902b7",
      "service": "order-service",
      "environment": "production",
      "level": "warning",
      "timestamp": "2026-02-28T09:12:34.890Z"
    }
    ```

=== "Console output (development)"

    Set `OBSKIT_LOG_FORMAT=console` for a human-friendly coloured format:

    ```
    2026-02-28 09:12:34 [info     ] user_logged_in   user_id=u-123 ip=10.0.0.1 trace_id=4bf92f35...
    2026-02-28 09:12:34 [warning  ] rate_limit_approaching user_id=u-123 current_rpm=95 limit_rpm=100
    2026-02-28 09:12:34 [error    ] payment_failed   order_id=ord-789 reason=card_declined amount=49.99
    ```

### Logging Configuration

| Environment variable | Effect |
|----------------------|--------|
| `OBSKIT_LOG_LEVEL=DEBUG` | Emit debug messages |
| `OBSKIT_LOG_FORMAT=console` | Human-readable output (local dev) |
| `OBSKIT_LOG_FORMAT=json` | Machine-readable JSON (default, production) |
| `OBSKIT_SERVICE_NAME=order-service` | Sets `service` field on every record |
| `OBSKIT_ENVIRONMENT=production` | Sets `environment` field on every record |

!!! note "Trace IDs are injected automatically"
    When `obskit[otlp]` is also installed, `trace_id` and `span_id` come from the active OpenTelemetry span context. If no span is active, those fields are omitted cleanly. No manual plumbing required.

---

## Step 2 — Distributed Tracing

Call `setup_tracing()` **once** at application startup, before your framework is imported. It installs the OTel SDK and auto-patches every detected library.

=== "Basic setup"

    ```python
    from obskit.tracing import setup_tracing

    # Auto-detects FastAPI, SQLAlchemy, Redis, httpx, Celery, …
    setup_tracing(
        exporter_endpoint="http://tempo:4317",
        sample_rate=0.1,   # keep 10 % of traces in production
    )
    ```

=== "Local development"

    ```python
    from obskit.tracing import setup_tracing

    # Prints spans to stdout — no collector required
    setup_tracing(debug=True)
    ```

=== "Selective instrumentation"

    ```python
    from obskit.tracing import setup_tracing

    # Explicit list — faster startup, predictable behaviour
    setup_tracing(
        exporter_endpoint="http://tempo:4317",
        sample_rate=0.1,
        instrument=["fastapi", "sqlalchemy", "redis"],
    )
    ```

=== "Manual spans"

    ```python
    from obskit.tracing import trace_span, async_trace_span

    # Synchronous span
    with trace_span("process_order", attributes={"order_id": "ord-789", "user_id": "u-123"}):
        result = process_order(order_id="ord-789")

    # Asynchronous span
    async def fetch_user(uid: str):
        async with async_trace_span("fetch_user", attributes={"user_id": uid}):
            return await db.get_user(uid)
    ```

=== "Baggage propagation"

    ```python
    from obskit.tracing import set_baggage, get_baggage

    # Baggage flows to every downstream service in the same trace
    set_baggage("tenant_id", "acme-corp")
    set_baggage("feature_flag", "new_checkout_v2")

    tenant = get_baggage("tenant_id")   # → "acme-corp"
    ```

### span output (debug=True)

```
[obskit] SPAN  process_order
  trace_id  : 4bf92f3577b34da6a3ce929d0e0e4736
  span_id   : 00f067aa0ba902b7
  attributes: {order_id: ord-789, user_id: u-123}
  duration  : 45.3 ms
  status    : OK
```

---

## Step 3 — RED Metrics with Trace Exemplars

obskit provides a high-level `REDMetrics` class and a low-level `observe_with_exemplar()` helper that links a Prometheus data-point to the active OTel trace — enabling metric-to-trace drill-down in Grafana.

=== "REDMetrics (recommended)"

    ```python
    from obskit.metrics.red import REDMetrics

    red = REDMetrics(service="order-service")

    # Record one request — increments rate counter, error counter (if status>=400),
    # and observes duration histogram.
    red.record_request(
        endpoint="/orders",
        method="POST",
        status=200,
        duration=0.123,
    )
    ```

=== "observe_with_exemplar (low-level)"

    ```python
    from prometheus_client import Histogram, Counter
    from obskit.metrics import observe_with_exemplar

    REQUEST_DURATION = Histogram(
        "http_request_duration_seconds",
        "Request latency",
        ["method", "path", "status"],
    )

    # The exemplar carries {trace_id: "4bf92f..."} so Grafana can jump
    # from the histogram bucket straight to the matching Tempo trace.
    observe_with_exemplar(
        REQUEST_DURATION.labels(method="GET", path="/orders", status="200"),
        0.045,
    )
    ```

=== "Prometheus /metrics output"

    ```
    # HELP http_request_duration_seconds Request latency
    # TYPE http_request_duration_seconds histogram
    http_request_duration_seconds_bucket{method="GET",path="/orders",status="200",le="0.05"} 1 # {trace_id="4bf92f3577b34da6"} 0.045
    http_request_duration_seconds_bucket{method="GET",path="/orders",status="200",le="0.1"} 1
    http_request_duration_seconds_bucket{method="GET",path="/orders",status="200",le="0.25"} 1
    http_request_duration_seconds_bucket{method="GET",path="/orders",status="200",le="+Inf"} 1
    http_request_duration_seconds_sum{method="GET",path="/orders",status="200"} 0.045
    http_request_duration_seconds_count{method="GET",path="/orders",status="200"} 1
    ```

!!! tip "Exemplars require Prometheus ≥ 2.27 with `--enable-feature=exemplar-storage`"
    In Grafana Cloud and most managed Prometheus offerings this is already enabled. See the [Trace Exemplars guide](../guides/trace-exemplars.md) for Prometheus configuration details.

---

## Step 4 — Health Checks

obskit implements the Kubernetes liveness/readiness/health pattern. The `HealthChecker` reads `OBSKIT_SERVICE_NAME` and `OBSKIT_VERSION` from the environment automatically.

=== "Basic health checker"

    ```python
    import asyncio
    from obskit.health import HealthChecker, create_http_check

    checker = HealthChecker()

    # Add dependency checks (used for readiness)
    checker.add_check("database", create_http_check("http://postgres:5432/ping"))
    checker.add_check("redis",    create_http_check("http://redis:6379/ping"))
    checker.add_check("payments", create_http_check("https://api.stripe.com/v1/ping"))

    # Run all checks
    result = asyncio.run(checker.check_health())
    print(result.to_dict())
    ```

=== "JSON response"

    ```json
    {
      "status": "healthy",
      "service": "order-service",
      "version": "2.0.0",
      "environment": "production",
      "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
      "span_id": "00f067aa0ba902b7",
      "checks": {
        "database": {"status": "healthy", "latency_ms": 2.1},
        "redis":    {"status": "healthy", "latency_ms": 0.8},
        "payments": {"status": "healthy", "latency_ms": 45.2}
      },
      "timestamp": "2026-02-28T09:12:34.567Z"
    }
    ```

=== "Degraded response"

    ```json
    {
      "status": "degraded",
      "service": "order-service",
      "version": "2.0.0",
      "checks": {
        "database": {"status": "healthy", "latency_ms": 2.1},
        "redis":    {"status": "unhealthy", "error": "connection refused"},
        "payments": {"status": "healthy", "latency_ms": 45.2}
      }
    }
    ```

=== "Custom async check"

    ```python
    from obskit.health import HealthChecker

    checker = HealthChecker()

    @checker.add_readiness_check("database")
    async def check_db():
        """Returns True if the DB is reachable."""
        try:
            await db.execute("SELECT 1")
            return True
        except Exception:
            return False
    ```

!!! note "trace_id / span_id in health responses"
    When `obskit[otlp]` is active, every `/health` call is automatically wrapped in a span. The `trace_id` and `span_id` fields in the JSON response let you correlate health check results with distributed traces in Grafana.

---

## Step 5 — Run obskit diagnose

After wiring everything up, run the built-in diagnostic to confirm the full stack is operational.

=== "Command"

    ```bash
    python -m obskit.core.diagnose
    ```

=== "With environment variables"

    ```bash
    OBSKIT_SERVICE_NAME=order-service \
    OBSKIT_OTLP_ENDPOINT=http://localhost:4317 \
    OBSKIT_LOG_FORMAT=console \
      python -m obskit.core.diagnose
    ```

=== "Expected output"

    ```
    obskit v2.2.0 — Diagnostic Report
    ══════════════════════════════════════════════════════════════
      Component          Status
      ─────────────────────────────────────────────────────────
      obskit             2.2.0     OK
      prometheus         OK
      otlp               OK
      fastapi            OK

      Environment
      ─────────────────────────────────────────────────────────
      OBSKIT_SERVICE_NAME    order-service
      OBSKIT_ENVIRONMENT     development
      OBSKIT_OTLP_ENDPOINT   http://localhost:4317   (reachable)
      OBSKIT_LOG_LEVEL       INFO
      OBSKIT_LOG_FORMAT      console

      Auto-instrumentors detected: fastapi, sqlalchemy, redis, httpx
    ══════════════════════════════════════════════════════════════
      All checks passed.
    ```

!!! warning "OTLP endpoint unreachable?"
    The diagnose tool tries a gRPC health-check against `OBSKIT_OTLP_ENDPOINT`. If it times out, traces will be dropped silently (OTel's default behaviour). Start the observability stack with `docker compose up -d` or override the endpoint.

---

## Complete Minimal Example

Here is the smallest possible FastAPI service with the full observability stack wired in:

```python
# main.py
import os
os.environ.setdefault("OBSKIT_SERVICE_NAME", "demo")
os.environ.setdefault("OBSKIT_LOG_FORMAT", "console")

# 1. Tracing MUST be set up before FastAPI is imported
from obskit.tracing import setup_tracing
setup_tracing(debug=True)

from fastapi import FastAPI
from obskit.logging import get_logger
from obskit.metrics.red import REDMetrics
from obskit.health import HealthChecker
from obskit.middleware.fastapi import ObskitMiddleware

log = get_logger(__name__)
red = REDMetrics(service="demo")
checker = HealthChecker()

app = FastAPI(title="Demo")
app.add_middleware(ObskitMiddleware)


@app.get("/")
async def root():
    log.info("root_called")
    return {"hello": "world"}


@app.get("/health")
async def health():
    result = await checker.check_health()
    return result.to_dict()
```

```bash
uvicorn main:app --reload
# curl http://localhost:8000/
# curl http://localhost:8000/health
```

---

## What's Next

<div class="grid cards" markdown>

- :material-rocket-launch: **[Your First Observable App](first-app.md)**

    Build a complete Order Service with Docker Compose, Grafana, Tempo, and Prometheus.

- :material-swap-horizontal: **[Migration from v1](migration.md)**

    Upgrading an existing service? Read the breaking-changes summary and import mapping.

- :material-tune: **[Configuration Reference](../reference/configuration.md)**

    Every `OBSKIT_*` environment variable, its default, and valid values.

- :material-link: **[Trace-Log Correlation](../guides/trace-log-correlation.md)**

    How `trace_id` / `span_id` flow from spans into log records.

- :material-chart-line: **[Trace Exemplars](../guides/trace-exemplars.md)**

    Link Prometheus histogram buckets to Tempo traces for one-click drill-down.

</div>
