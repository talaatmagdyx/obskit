<div align="center">

```
 ██████╗ ██████╗ ███████╗██╗  ██╗██╗████████╗
██╔═══██╗██╔══██╗██╔════╝██║ ██╔╝██║╚══██╔══╝
██║   ██║██████╔╝███████╗█████╔╝ ██║   ██║
██║   ██║██╔══██╗╚════██║██╔═██╗ ██║   ██║
╚██████╔╝██████╔╝███████║██║  ██╗██║   ██║
 ╚═════╝ ╚═════╝ ╚══════╝╚═╝  ╚═╝╚═╝   ╚═╝
```

**Production-ready observability for Python microservices.**
Metrics · Tracing · Logging · Health · SLO — all in one toolkit.

---

[![CI](https://github.com/talaatmagdyx/obskit/actions/workflows/ci.yml/badge.svg)](https://github.com/talaatmagdyx/obskit/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/obskit.svg?color=blue)](https://pypi.org/project/obskit/)
[![PyPI Downloads](https://img.shields.io/pypi/dm/obskit.svg)](https://pypi.org/project/obskit/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Coverage](https://codecov.io/gh/talaatmagdyx/obskit/branch/main/graph/badge.svg)](https://codecov.io/gh/talaatmagdyx/obskit)
[![Docs](https://img.shields.io/badge/docs-mkdocs-blue.svg)](https://talaatmagdyx.github.io/obskit/)

</div>

---

## Why obskit?

Most observability setups mean **wiring 5+ libraries by hand** — Prometheus, structlog, OpenTelemetry, custom health checks — each with different APIs, different configs, and no automatic correlation between them.

obskit gives you **one coherent toolkit** where metrics, logs, traces, and health checks all speak to each other out of the box.

```
Without obskit                          With obskit
─────────────────────────────────────   ──────────────────────────────────────
✗ Configure prometheus_client           ✓ pip install "obskit[prometheus]"
✗ Set up structlog processors           ✓ pip install obskit  (built-in)
✗ Bootstrap OpenTelemetry SDK           ✓ pip install "obskit[otlp]"
✗ Write health endpoint from scratch    ✓ build_health_router(checks=[...])
✗ Wire trace IDs into every log         ✓ Automatic — zero extra code
✗ Correlate metrics to traces           ✓ Automatic — exemplars built in
```

---

## Package Ecosystem

obskit is a **single unified package** with optional extras. Install only what you need.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                            pip install obskit                                 │
│                       pip install "obskit[all]"  (everything)                 │
├──────────────────────────────────────────────────────────────────────────────┤
│  Always included — no extras needed                                           │
│  logging  ·  metrics  ·  tracing  ·  health  ·  slo  ·  middleware  ·  core  │
├─────────────────────┬──────────────────┬──────────────────────────────────────┤
│  obskit[prometheus] │   obskit[otlp]   │  obskit[fastapi|flask|django]        │
│  Prometheus /metrics│  OpenTelemetry   │  Framework middleware                 │
│  RED metrics        │  distributed     │  auto metrics + traces               │
│  exemplars          │  tracing (OTLP)  │  correlation IDs + access logs       │
├─────────────────────┼──────────────────┼──────────────────────────────────────┤
│  obskit[sqlalchemy] │  obskit[kafka]   │  obskit[rabbitmq]                    │
│  SQLAlchemy OTel    │  Kafka consumer  │  RabbitMQ consumer                   │
│  auto-instrumentation│ tracing         │  tracing                             │
├─────────────────────┼──────────────────┼──────────────────────────────────────┤
│  obskit[psycopg2]   │  obskit[psycopg3]│  obskit[grpc]                        │
│  psycopg2 OTel      │  psycopg3 OTel   │  gRPC server/client                  │
│  auto-instrumentation│ sync + async    │  interceptors                        │
└─────────────────────┴──────────────────┴──────────────────────────────────────┘
```

---

## Installation

```bash
# Core — logging, metrics, tracing, health, SLO, middleware (no extra deps)
pip install obskit

# Full stack — everything included
pip install "obskit[all]"

# Observability backends
pip install "obskit[prometheus]"   # Prometheus /metrics endpoint
pip install "obskit[otlp]"         # OpenTelemetry OTLP export

# Framework middleware (pick yours)
pip install "obskit[fastapi]"      # FastAPI / Starlette
pip install "obskit[flask]"        # Flask
pip install "obskit[django]"       # Django

# SLO tracking
pip install "obskit[slo]"                # tracker only
pip install "obskit[slo-prometheus]"     # + Prometheus burn-rate export
pip install "obskit[slo-all]"            # everything SLO

# Health checks
pip install "obskit[health]"             # checker + router
pip install "obskit[health-http]"        # + HTTP reachability check (needs httpx)
pip install "obskit[health-all]"         # everything health

# Database integrations (pick your driver)
pip install "obskit[sqlalchemy]"   # SQLAlchemy OTel auto-instrumentation
pip install "obskit[psycopg2]"     # psycopg2 OTel auto-instrumentation (sync)
pip install "obskit[psycopg3]"     # psycopg3 OTel auto-instrumentation (sync + async)
pip install "obskit[db]"           # all three DB drivers

# Message queue integrations
pip install "obskit[kafka]"        # Kafka consumer instrumentation
pip install "obskit[rabbitmq]"     # RabbitMQ consumer instrumentation

# gRPC
pip install "obskit[grpc]"         # gRPC server/client interceptors

# All integrations bundled
pip install "obskit[integrations]" # db + kafka + rabbitmq + grpc

# Combine as needed
pip install "obskit[prometheus,otlp,fastapi,slo]"
```

---

## 5-Minute Quickstart

A complete, observable FastAPI service:

```python
from fastapi import FastAPI
from obskit import configure_observability, instrument_fastapi
from obskit.health import HealthChecker

# ── 1. One-call setup ────────────────────────────────────────────────
obs = configure_observability(
    service_name="order-service",
    environment="production",
    otlp_endpoint="http://otel-collector:4317",
    trace_sample_rate=0.1,
)

logger  = obs.logger
metrics = obs.metrics
health  = HealthChecker()

# ── 2. Health checks ────────────────────────────────────────────────
@health.add_readiness_check("database")
async def check_db():
    return await db.ping()

# ── 3. App + auto-instrumentation ───────────────────────────────────
app = FastAPI()
instrument_fastapi(app)

# ── 4. Business logic — fully instrumented ──────────────────────────
@app.post("/orders")
async def create_order(order: OrderRequest):
    with metrics.track_request("create_order"):
        logger.info("order_received", order_id=order.id, amount=order.total)
        result = await payment_service.charge(order)
        logger.info("order_confirmed", order_id=order.id)
        return result

# ── 5. Health endpoint ──────────────────────────────────────────────
@app.get("/health")
async def health_endpoint():
    return await health.check_health()
```

Every log line automatically carries `trace_id` and `span_id`.
Every metric data point is linked to its trace via exemplars.
Zero extra wiring needed.

---

## Features

### 📊 Metrics — RED (Rate · Errors · Duration)

```python
from obskit.metrics.red import REDMetrics, get_red_metrics
from obskit.metrics.registry import start_http_server

# RED: Rate · Errors · Duration  (per operation)
red = get_red_metrics()
red.observe_request("create_order", duration_seconds=0.045, status="success")

# Auto-timing context manager
with red.track_request("process_payment"):
    gateway.charge(amount)

# Expose /metrics for Prometheus scraping
start_http_server(port=9090)
```

**PromQL cheat-sheet:**

```promql
# Request rate (req/s)
sum(rate(obskit_requests_total[5m])) by (operation)

# P95 latency
histogram_quantile(0.95,
  sum(rate(obskit_request_duration_seconds_bucket[5m])) by (le, operation))

# Error rate %
sum(rate(obskit_errors_total[5m]))
  / sum(rate(obskit_requests_total[5m])) * 100
```

---

### 🔍 Distributed Tracing

```python
from obskit.tracing.tracer import (
    configure_tracing,
    trace_span,
    async_trace_span,
    get_tracer,
)

# Setup — send spans to Tempo / Jaeger / Grafana Cloud via OTLP
configure_tracing(
    service_name="order-service",
    otlp_endpoint="http://tempo:4317",
    sample_rate=0.1,
)

# Manual spans
with trace_span("process_order", attributes={"order.id": "123"}):
    result = process_order(order_id="123")

async with async_trace_span("fetch_user", attributes={"user.id": uid}):
    user = await db.get_user(uid)
```

W3C `traceparent` + `baggage` propagation. Auto-instruments FastAPI, Flask, Django, SQLAlchemy, httpx, and more.

---

### 📝 Structured Logging

```python
from obskit.logging import get_logger

logger = get_logger(__name__)

# Structured key-value logging
logger.info("order_placed", order_id="ord-123", user_id="usr-456", total=99.99)
logger.warning("retry_attempt", attempt=2, max_attempts=3, endpoint="/payments")
logger.error("payment_failed", error="card_declined", order_id="ord-123")

# Bind context for a request scope
req_logger = logger.bind(request_id="req-abc", tenant="acme")
req_logger.info("processing")   # all fields carry through automatically
```

**Every log line automatically includes `trace_id` and `span_id`** when a trace is active:

```json
{
  "level": "info",
  "event": "order_placed",
  "order_id": "ord-123",
  "total": 99.99,
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "span_id":  "00f067aa0ba902b7",
  "service":  "order-service",
  "timestamp": "2026-03-01T10:00:00Z"
}
```

**PII fields are automatically redacted** by the default logger — `password`, `token`, `secret`, `api_key`, `authorization`, `card_number`, and other sensitive field names are replaced with `"***REDACTED***"` before any output is written.

---

### 🏥 Health Checks

**Option A — `build_health_router` (FastAPI, recommended)**

```python
from fastapi import FastAPI
from obskit.health import HealthCheck, build_health_router

app = FastAPI()
app.include_router(
    build_health_router(
        readiness_checks=[
            HealthCheck(name="redis",    check=lambda: redis_client.ping(), timeout=2),
            HealthCheck(name="postgres", check=lambda: db.execute("SELECT 1"), timeout=3),
        ],
        liveness_checks=[
            HealthCheck(name="memory", check=lambda: psutil.virtual_memory().percent < 90),
        ],
    )
)
# GET /health/live   → 200 | 503
# GET /health/ready  → 200 | 503
# GET /health        → 200 | 503 (combined)
```

**Option B — decorator API (any framework)**

```python
from obskit.health import HealthChecker

checker = HealthChecker()

@checker.add_readiness_check("database")
async def check_db():
    return await db.ping()

@checker.add_readiness_check("cache", critical=False)   # non-critical → degraded, not unhealthy
async def check_redis():
    return await redis.ping()

result = await checker.check_health()
# result.status → "healthy" | "degraded" | "unhealthy"
```

**Kubernetes probe config:**

```yaml
livenessProbe:
  httpGet: { path: /health/live, port: 8080 }
  initialDelaySeconds: 5
  periodSeconds: 10

readinessProbe:
  httpGet: { path: /health/ready, port: 8080 }
  initialDelaySeconds: 5
  periodSeconds: 5
```

---

### 📈 SLO Tracking

```python
from obskit.slo import SLOTracker, SLOType

tracker = SLOTracker()

# Register a 99.9% availability SLO over a 30-day window
tracker.register_slo(
    name="api_availability",
    slo_type=SLOType.AVAILABILITY,
    target_value=0.999,
    window_seconds=30 * 86400,
)

# Record good / bad events
tracker.record_measurement("api_availability", value=1.0, success=True)
tracker.record_measurement("api_availability", value=0.0, success=False)

# Check current status
status = tracker.get_status("api_availability")
print(f"Budget remaining : {status.error_budget_remaining:.4f}")
print(f"Within SLO       : {status.is_within_slo}")
```

Requires `pip install "obskit[slo]"`.

---

### 🔌 Framework Middleware

One line to instrument your entire service — every request gets automatic metrics, traces, correlation IDs, and structured access logs.

```python
from obskit import instrument_fastapi, instrument_flask, instrument_django

# FastAPI / Starlette
instrument_fastapi(app)

# Flask
instrument_flask(app)

# Django — in AppConfig.ready()
MiddlewareClass = instrument_django()

# gRPC (requires obskit[grpc])
from obskit.integrations.grpc import ObskitServerInterceptor
server = grpc.server(interceptors=[ObskitServerInterceptor()])
```

---

### 🗄️ Database & Queue Integrations

```python
# SQLAlchemy — OTel auto-instrumentation
# pip install "obskit[sqlalchemy]"
from sqlalchemy import create_engine
from obskit.integrations.db.sqlalchemy import instrument_sqlalchemy

engine = create_engine("postgresql://user:pass@localhost/db")
instrument_sqlalchemy(engine, database_name="postgres")

# psycopg2 — OTel auto-instrumentation (sync)
# pip install "obskit[psycopg2]"
from obskit.integrations.db.psycopg2 import instrument_psycopg2
instrument_psycopg2(capture_parameters=False)

# psycopg3 — OTel auto-instrumentation (sync + async)
# pip install "obskit[psycopg3]"
from obskit.integrations.db.psycopg3 import instrument_psycopg3
instrument_psycopg3(capture_parameters=False)

# Kafka consumer tracing
# pip install "obskit[kafka]"
from obskit.integrations.queue.kafka import KafkaConsumerTracer

# RabbitMQ consumer tracing
# pip install "obskit[rabbitmq]"
from obskit.integrations.queue.rabbitmq import RabbitMQConsumerTracer
```

---

## ⚙️ Configuration

**Environment variables** (twelve-factor style):

```bash
OBSKIT_SERVICE_NAME=order-service
OBSKIT_ENVIRONMENT=production
OBSKIT_VERSION=1.0.0

OBSKIT_LOG_LEVEL=INFO
OBSKIT_LOG_FORMAT=json            # json | console

OBSKIT_TRACING_ENABLED=true
OBSKIT_OTLP_ENDPOINT=http://otel-collector:4317

OBSKIT_METRICS_PORT=9090
```

**Programmatic** (overrides env vars):

```python
from obskit import configure_observability

obs = configure_observability(
    service_name="order-service",
    environment="production",
    otlp_endpoint="http://otel-collector:4317",
    log_level="INFO",
    log_format="json",
)
```

**`obskit.yaml`** (optional file-based config):

```yaml
service_name: order-service
environment: production
otlp_endpoint: http://otel-collector:4317
log_level: INFO
metrics_port: 9090
```

---

## 🩺 Diagnose CLI

Verify obskit and all optional integrations are correctly installed:

```bash
python -m obskit.core.diagnose
```

```
obskit diagnostics
==================
Core
  version         1.0.0    ✓
  python          3.11.8   ✓
Logging
  structlog       23.2.0   ✓
  trace-corr      enabled  ✓
Metrics
  prometheus      0.19.0   ✓
Tracing
  opentelemetry   1.22.0   ✓
  otlp-endpoint   http://otel-collector:4317  ✓
Health
  checker         ready    ✓
```

---

## 🛠️ Development

```bash
# Clone and install all extras + dev tools
git clone https://github.com/talaatmagdyx/obskit.git
cd obskit
uv sync --all-extras

# Run all unit tests
.venv/bin/pytest tests/unit/ -q --no-cov

# Run tests for a specific area
.venv/bin/pytest tests/unit/metrics/ -q

# Lint
uv run ruff check src/

# Type check
uv run mypy src/obskit/

# Build docs
uv run mkdocs build --strict
```

---

## 📖 Documentation

Full documentation at **[talaatmagdyx.github.io/obskit](https://talaatmagdyx.github.io/obskit/)**

| Section | Link |
|---|---|
| 🚀 Getting Started | [Installation & Quick Start](https://talaatmagdyx.github.io/obskit/getting-started/installation/) |
| 📊 Metrics Guide | [RED Metrics](https://talaatmagdyx.github.io/obskit/user-guide/metrics/) |
| 🏥 Health Checks | [Health Checks Guide](https://talaatmagdyx.github.io/obskit/user-guide/health-checks/) |
| 📈 SLO Tracking | [SLO Guide](https://talaatmagdyx.github.io/obskit/user-guide/slo/) |
| 📦 Package Reference | [Modules & extras](https://talaatmagdyx.github.io/obskit/packages/core/) |
| 📚 API Reference | [Full API docs](https://talaatmagdyx.github.io/obskit/reference/api/) |

---

## 🔄 API Quick Reference

```python
from obskit import configure_observability, instrument_fastapi

# Setup everything in one call
obs = configure_observability(service_name="my-service")

# Instrument your framework
instrument_fastapi(app)       # FastAPI / Starlette
# instrument_flask(app)       # Flask
# instrument_django()         # Django

# Access subsystems
obs.tracer    # OpenTelemetry tracer
obs.metrics   # RED metrics recorder
obs.logger    # Structured logger
obs.config    # Immutable ObservabilityConfig
obs.shutdown() # Graceful shutdown
```

---

## 🤝 Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) and the [Contributing Guide](https://talaatmagdyx.github.io/obskit/contributing/).

```bash
git clone https://github.com/talaatmagdyx/obskit.git
cd obskit && uv sync --all-extras
git checkout -b feat/my-improvement
# make changes + add tests
.venv/bin/pytest tests/unit/ -q
uv run ruff check src/
git commit -m "feat: my improvement"
git push && gh pr create
```

---

## 📄 License

MIT — see [LICENSE](LICENSE).

---

<div align="center">

**[Documentation](https://talaatmagdyx.github.io/obskit/)** · **[PyPI](https://pypi.org/project/obskit/)** · **[Issues](https://github.com/talaatmagdyx/obskit/issues)** · **[Changelog](CHANGELOG.md)**

Made with ❤️ for Python microservice developers.

</div>
