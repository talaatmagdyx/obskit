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
Metrics · Tracing · Logging · Health · Alerts · Resilience · SLO — all in one toolkit.

---

[![CI](https://github.com/talaatmagdyx/obskit/actions/workflows/ci.yml/badge.svg)](https://github.com/talaatmagdyx/obskit/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/obskit.svg?color=blue)](https://pypi.org/project/obskit/)
[![PyPI Downloads](https://img.shields.io/pypi/dm/obskit.svg)](https://pypi.org/project/obskit/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Coverage](https://codecov.io/gh/talaatmagdyx/obskit/branch/main/graph/badge.svg)](https://codecov.io/gh/talaatmagdyx/obskit)
[![Quality Gate](https://sonarcloud.io/api/project_badges/measure?project=talaatmagdyx_obskit&metric=alert_status)](https://sonarcloud.io/summary/new_code?id=talaatmagdyx_obskit)
[![Docs](https://img.shields.io/badge/docs-mkdocs-blue.svg)](https://talaatmagdyx.github.io/obskit/)

</div>

---

## Why obskit?

Most observability setups mean **wiring 5+ libraries by hand** — Prometheus, structlog, OpenTelemetry, custom health checks, circuit breakers — each with different APIs, different configs, and no automatic correlation between them.

obskit gives you **one coherent toolkit** where metrics, logs, traces, and health checks all speak to each other out of the box.

```
Without obskit                          With obskit
─────────────────────────────────────   ──────────────────────────────────────
✗ Configure prometheus_client           ✓ pip install "obskit[prometheus]"
✗ Set up structlog processors           ✓ pip install obskit  (built-in)
✗ Bootstrap OpenTelemetry SDK           ✓ pip install "obskit[otlp]"
✗ Write health endpoint from scratch    ✓ build_health_router(checks=[...])
✗ Hand-write Prometheus alert YAML      ✓ AlertRule.error_rate(metric=...) + export_yaml()
✗ Implement circuit breaker logic       ✓ pip install obskit  (built-in)
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
│  obskit.logging  ·  obskit.health  ·  obskit.alerts  ·  obskit.resilience    │
│  obskit.slo  ·  obskit.decorators  ·  obskit.db  ·  obskit.queue  ·  obskit.core │
├─────────────────────┬──────────────────┬──────────────────────────────────────┤
│  obskit[prometheus] │   obskit[otlp]   │  obskit[fastapi|flask|django]        │
│  Prometheus         │  OpenTelemetry   │  Framework middleware                 │
│  RED · USE          │  distributed     │  auto metrics + traces               │
│  Golden Signals     │  tracing (OTLP)  │  correlation IDs + access logs       │
├─────────────────────┼──────────────────┼──────────────────────────────────────┤
│  obskit[sqlalchemy] │  obskit[kafka]   │  obskit[rabbitmq]                    │
│  SQLAlchemy audit   │  Kafka consumer  │  RabbitMQ tracing                    │
│  query tracing      │  lag + DLQ       │  consumer lag tracking               │
│  N+1 detection      │  tracking        │                                      │
└─────────────────────┴──────────────────┴──────────────────────────────────────┘
```

---

## Installation

```bash
# Full stack — everything included
pip install "obskit[all]"

# Core + built-ins only (logging, health, resilience, SLO, decorators)
pip install obskit

# Add the backends you need
pip install "obskit[prometheus]"   # Prometheus metrics (RED / USE / Golden Signals)
pip install "obskit[otlp]"         # OpenTelemetry distributed tracing

# Framework middleware (pick yours)
pip install "obskit[fastapi]"      # FastAPI middleware
pip install "obskit[flask]"        # Flask middleware
pip install "obskit[django]"       # Django middleware

# Data stores & queues
pip install "obskit[sqlalchemy]"   # SQLAlchemy query audit + N+1 detection
pip install "obskit[kafka]"        # Kafka consumer lag + DLQ tracking
pip install "obskit[rabbitmq]"     # RabbitMQ tracing + consumer lag

# Combine as needed
pip install "obskit[prometheus,otlp,fastapi]"
```

---

## 5-Minute Quickstart

A complete, observable FastAPI service:

```python
from fastapi import FastAPI
from obskit.config import configure
from obskit.logging import get_logger
from obskit.metrics import REDMetrics
from obskit.tracing import setup_tracing
from obskit.health import HealthChecker
from obskit.resilience import CircuitBreaker
from obskit.middleware.fastapi import ObskitMiddleware

# ── 1. Bootstrap ──────────────────────────────────────────────────────
configure(service_name="order-service", environment="production")
setup_tracing(exporter_endpoint="http://otel-collector:4317")

# ── 2. Observability primitives ───────────────────────────────────────
logger  = get_logger(__name__)
metrics = REDMetrics("order_service")
health  = HealthChecker()
breaker = CircuitBreaker(name="payment-gw", failure_threshold=5)

# ── 3. Health checks ──────────────────────────────────────────────────
@health.add_readiness_check("database")
async def check_db():
    return await db.ping()

# ── 4. App + auto-instrumentation middleware ──────────────────────────
app = FastAPI()
app.add_middleware(ObskitMiddleware, service_name="order-service")

# ── 5. Business logic — fully instrumented ───────────────────────────
@app.post("/orders")
async def create_order(order: OrderRequest):
    with metrics.track_request("create_order"):
        logger.info("order_received", order_id=order.id, amount=order.total)

        async with breaker:                        # circuit protection
            result = await payment_service.charge(order)

        logger.info("order_confirmed", order_id=order.id)
        return result

# ── 6. Health endpoint ────────────────────────────────────────────────
@app.get("/health")
async def health_endpoint():
    return await health.check_health()
```

Every log line automatically carries `trace_id` and `span_id`.
Every metric data point is linked to its trace via exemplars.
Zero extra wiring needed.

---

## Features

### 📊 Metrics — RED / Golden Signals / USE

```python
from obskit.metrics import REDMetrics, GoldenSignals, USEMetrics, start_http_server

# RED: Rate · Errors · Duration  (per endpoint)
red = REDMetrics("order_service")
red.observe_request("create_order", duration_seconds=0.045, status="success")

# Auto-timing context manager
with red.track_request("process_payment"):
    gateway.charge(amount)

# Four Golden Signals: Latency · Traffic · Errors · Saturation
golden = GoldenSignals("order_service")
golden.observe_request("create_order", latency=0.045)
golden.set_saturation("cpu", 0.75)
golden.set_queue_depth("order_queue", 42)

# USE: Utilization · Saturation · Errors  (infrastructure)
use = USEMetrics(resource="cpu")
use.record(utilization=0.72, saturation=0.05, errors=0)

# Expose /metrics for Prometheus scraping
start_http_server(port=9090)
```

**PromQL cheat-sheet:**

```promql
# Request rate (req/s)
sum(rate(order_service_requests_total[5m])) by (operation)

# P95 latency
histogram_quantile(0.95,
  sum(rate(order_service_request_duration_seconds_bucket[5m])) by (le, operation))

# Error rate %
sum(rate(order_service_errors_total[5m]))
  / sum(rate(order_service_requests_total[5m])) * 100
```

---

### 🔍 Distributed Tracing

```python
from obskit.tracing import setup_tracing, trace_span, async_trace_span, set_baggage

# One-line setup — auto-detects FastAPI, SQLAlchemy, Redis, httpx, Celery…
setup_tracing(exporter_endpoint="http://tempo:4317", sample_rate=0.1)

# Local dev — print spans to stdout
setup_tracing(debug=True)

# Manual spans
with trace_span("process_order", attributes={"order.id": "123"}):
    result = process_order(order_id="123")

async with async_trace_span("fetch_user", attributes={"user.id": uid}):
    user = await db.get_user(uid)

# W3C Baggage — propagates across all downstream HTTP calls automatically
set_baggage("tenant_id", "acme-corp")
```

Supported auto-instrumentation: **FastAPI · SQLAlchemy · Redis · httpx · Celery · Django · Requests · gRPC · RabbitMQ**

---

### 📝 Structured Logging

```python
from obskit.logging import get_logger, log_performance, log_error

logger = get_logger(__name__)

# Structured key-value logging
logger.info("order_placed", order_id="ord-123", user_id="usr-456", total=99.99)
logger.warning("retry_attempt", attempt=2, max_attempts=3, endpoint="/payments")
logger.error("payment_failed", error="card_declined", order_id="ord-123")

# Performance logging (warns automatically if threshold exceeded)
log_performance("create_order", "OrderService", duration_ms=450, threshold_ms=200)

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

---

### 🏥 Health Checks

**Option A — `build_health_router` (FastAPI, recommended)**

One call wires `/health/live`, `/health/ready`, and `/health` — obskit owns the protocol, you own the callable:

```python
from fastapi import FastAPI
from obskit.health import HealthCheck, build_health_router

app = FastAPI()
app.include_router(
    build_health_router(
        readiness_checks=[
            # obskit doesn't import Redis/Postgres — you provide the callable
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

### 🚨 Alert Rules

Standard SRE alerting patterns as code — zero hardcoded thresholds, zero hardcoded metric names. Export directly to Prometheus / Alertmanager YAML.

```python
from obskit.alerts import AlertRule, AlertGroup, export_yaml

group = AlertGroup(
    name="order-service",
    rules=[
        AlertRule.error_rate(
            metric="http_requests_total",
            threshold=0.05,           # 5% error rate → critical
            severity="critical",
        ),
        AlertRule.latency(
            metric="http_request_duration_seconds",
            percentile=0.99,
            threshold_ms=2000,        # p99 > 2 s → warning
            severity="warning",
        ),
        AlertRule.no_traffic(
            metric="http_requests_total",
            window="10m",             # silence for 10 min → warning
        ),
        AlertRule.slo_burn(
            error_metric="http_requests_total",
            slo_target=0.999,         # 99.9% availability SLO
            burn_factor=14.4,         # page on-call if exhausted in < 2 days
            severity="critical",
        ),
        AlertRule.custom(             # raw PromQL pass-through
            name="QueueSaturation",
            expr="rabbitmq_queue_messages > 10000",
            severity="warning",
        ),
    ],
)

# Exports valid Prometheus alert-rules YAML
yaml_str = export_yaml(group, path="k8s/alerts.yaml")
```

| Factory | What it detects |
|---------|----------------|
| `AlertRule.error_rate()` | Error fraction of a counter exceeds threshold |
| `AlertRule.latency()` | Histogram percentile (p99, p95…) exceeds budget |
| `AlertRule.no_traffic()` | Service goes completely silent |
| `AlertRule.slo_burn()` | Error budget burning too fast (Google SRE multi-window) |
| `AlertRule.custom()` | Any raw PromQL expression |

---

### 🛡️ Resilience Patterns

```python
from obskit.resilience import CircuitBreaker, CircuitOpenError, retry, RateLimiter, LoadShedder

# ── Circuit Breaker ───────────────────────────────────────────────────
cb = CircuitBreaker(
    name="payment-gateway",
    failure_threshold=5,       # open after 5 consecutive failures
    recovery_timeout=30.0,     # half-open retry after 30 s
    expected_exceptions=(TimeoutError, ConnectionError),
)

try:
    result = await cb.call(gateway.charge, amount)
except CircuitOpenError:
    result = cached_fallback()

# ── Retry with Exponential Backoff ────────────────────────────────────
@retry(max_attempts=3, backoff_factor=2.0, exceptions=(TimeoutError,))
async def fetch_data():
    return await external_api.get("/data")

# ── Token-bucket Rate Limiter ─────────────────────────────────────────
limiter = RateLimiter(max_calls=100, period=1.0)   # 100 req/s

async def handle_request():
    async with limiter:
        return await process()

# ── Concurrency-based Load Shedder ────────────────────────────────────
shedder = LoadShedder(max_concurrent=50)

async def endpoint():
    async with shedder:
        return await heavy_operation()
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

---

### 🔌 Framework Middleware

One line to instrument your entire service — every request gets automatic metrics, traces, correlation IDs, and structured access logs.

```python
# FastAPI
from obskit.middleware.fastapi import ObskitMiddleware
app.add_middleware(ObskitMiddleware, service_name="my-service")

# Flask
from obskit.middleware.flask import ObskitMiddleware
ObskitMiddleware(app, service_name="my-service")

# Django — settings.py
MIDDLEWARE = ["obskit.middleware.django.ObskitMiddleware", ...]

# gRPC
from obskit.middleware.grpc import ObskitServerInterceptor
server = grpc.server(interceptors=[ObskitServerInterceptor()])
```

---

### ✨ Cross-cutting Decorators

```python
from obskit.decorators import observe, trace

# Single decorator — adds metrics + logging + tracing to any function
@observe(operation="create_order", track_metrics=True, track_tracing=True)
async def create_order(order_data: dict) -> dict:
    ...

# Tracing only
@trace(span_name="process_payment")
async def process_payment(amount: float) -> bool:
    ...
```

---

## ⚙️ Configuration

**Environment variables** (twelve-factor style):

```bash
OBSKIT_SERVICE_NAME=order-service
OBSKIT_ENVIRONMENT=production
OBSKIT_VERSION=1.4.2

OBSKIT_LOG_LEVEL=INFO
OBSKIT_LOG_FORMAT=json            # json | console

OBSKIT_TRACING_ENABLED=true
OBSKIT_OTLP_ENDPOINT=http://otel-collector:4317

OBSKIT_METRICS_PORT=9090
OBSKIT_METRICS_AUTH_ENABLED=false
```

**Programmatic** (overrides env vars):

```python
from obskit.config import configure

configure(
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
  version         3.1.0    ✓
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
Resilience
  circuit-breaker ready    ✓
```

---

## 🛠️ Development

```bash
# Clone and install all extras + dev tools
git clone https://github.com/talaatmagdyx/obskit.git
cd obskit
uv sync --all-extras

# Run all unit tests
uv run pytest tests/unit/ -q --tb=short --timeout=30 --benchmark-disable

# Run tests for a specific area
uv run pytest tests/unit/metrics/ -q --tb=short --timeout=30

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
| 📊 Metrics Guide | [RED / Golden / USE](https://talaatmagdyx.github.io/obskit/user-guide/metrics/) |
| 🏥 Health Checks | [Health Checks Guide](https://talaatmagdyx.github.io/obskit/user-guide/health-checks/) |
| 🚨 Alert Rules | [Alert Rules Guide](https://talaatmagdyx.github.io/obskit/user-guide/alerts/) |
| 📦 Package Reference | [Modules & extras](https://talaatmagdyx.github.io/obskit/packages/core/) |
| 🔄 Migration from v1 | [Migration Guide](https://talaatmagdyx.github.io/obskit/migration/from-v1/) |
| 📚 API Reference | [Full API docs](https://talaatmagdyx.github.io/obskit/reference/api/) |

---

## 🔄 Migrating from v1

```diff
- pip install obskit==1.5.0
+ pip install "obskit[all]"          # drop-in compatible — all imports unchanged

# Preferred new import paths (old paths still work)
- from obskit import configure_logging
+ from obskit.logging import get_logger

- from obskit import get_red_metrics
+ from obskit.metrics.red import REDMetrics

- from obskit import configure_tracing
+ from obskit.tracing import setup_tracing
```

See the full [Migration Guide](https://talaatmagdyx.github.io/obskit/migration/from-v1/) for details.

---

## 🤝 Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) and the [Contributing Guide](https://talaatmagdyx.github.io/obskit/contributing/).

```bash
git clone https://github.com/talaatmagdyx/obskit.git
cd obskit && uv sync --all-extras
git checkout -b feat/my-improvement
# make changes + add tests
uv run pytest tests/unit/ -q
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
