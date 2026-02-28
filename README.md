# obskit

[![PyPI version](https://img.shields.io/pypi/v/obskit.svg)](https://pypi.org/project/obskit/)
[![PyPI Downloads](https://img.shields.io/pypi/dm/obskit.svg)](https://pypi.org/project/obskit/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Coverage: 100%](https://img.shields.io/badge/coverage-100%25-brightgreen.svg)](https://github.com/talaatmagdyx/obskit)
[![Docs](https://img.shields.io/badge/docs-mkdocs-blue.svg)](https://talaatmagdyx.github.io/obskit/)

**obskit** is a production-ready observability toolkit for Python microservices.
It provides unified metrics, tracing, logging, and resilience patterns following industry best practices.

> **v2.0.0** — the toolkit is now a monorepo of 16 focused namespace packages.
> Install only what you need: `pip install obskit-metrics` or `pip install "obskit[all]"`.

---

## Installation

```bash
# Full installation (all packages)
pip install "obskit[all]"

# Or install only what you need
pip install obskit-core        # Config, errors, interfaces
pip install obskit-logging     # Structured logging, adaptive sampling
pip install obskit-metrics     # RED / Golden / USE metrics
pip install obskit-tracing     # OpenTelemetry tracing
pip install obskit-health      # Health checks, /health HTTP server
pip install obskit-resilience  # Circuit breaker, retry, rate limiter
pip install obskit-slo         # SLO/SLA tracking, error budgets

# Framework middleware
pip install obskit-middleware-fastapi
pip install obskit-middleware-flask
pip install obskit-middleware-django
pip install obskit-middleware-grpc
```

---

## Quick Start

```python
from obskit.logging import get_logger
from obskit.metrics.red import REDMetrics
from obskit.health import HealthChecker
from obskit.tracing import setup_tracing

# Tracing
setup_tracing(service_name="my-service", environment="production")

# Structured logging
logger = get_logger(__name__)
logger.info("order_created", order_id="123", amount=99.99)

# RED metrics (Rate, Errors, Duration)
red = REDMetrics(service="my-service")
red.record_request(endpoint="/api/orders", method="POST", status="success", duration=0.045)

# Health checks
health = HealthChecker()
health.add_readiness_check("database", check_database)
```

---

## Packages

| Package | Install | What it provides |
|---|---|---|
| `obskit-core` | `pip install obskit-core` | Config, errors, interfaces, correlation, test helpers |
| `obskit-logging` | `pip install obskit-logging` | Structured logging, adaptive sampling, OTLP export |
| `obskit-metrics` | `pip install obskit-metrics` | RED/Golden/USE metrics, exemplars, cardinality guard |
| `obskit-tracing` | `pip install obskit-tracing` | OTel setup, `trace_span`, auto-instrumentation |
| `obskit-health` | `pip install obskit-health` | Health check framework, `/health` HTTP server |
| `obskit-resilience` | `pip install obskit-resilience` | Circuit breaker, retry, rate limiter |
| `obskit-slo` | `pip install obskit-slo` | SLO/SLA tracking, error budgets, alerting |
| `obskit-decorators` | `pip install obskit-decorators` | `@with_observability` cross-cutting decorator |
| `obskit-db` | `pip install obskit-db` | SQLAlchemy instrumentation, query analyzer |
| `obskit-queue` | `pip install obskit-queue` | Kafka/RabbitMQ tracing, consumer-lag, DLQ |
| `obskit-dashboards` | `pip install obskit-dashboards` | Grafana dashboard generators |
| `obskit-middleware-fastapi` | `pip install obskit-middleware-fastapi` | FastAPI ASGI middleware |
| `obskit-middleware-flask` | `pip install obskit-middleware-flask` | Flask WSGI middleware |
| `obskit-middleware-django` | `pip install obskit-middleware-django` | Django middleware |
| `obskit-middleware-grpc` | `pip install obskit-middleware-grpc` | gRPC server/client interceptors |
| `obskit` | `pip install "obskit[all]"` | Meta-package; installs all of the above |

---

## Features

### Metrics (RED / Golden Signals / USE)

```python
from obskit.metrics.red import REDMetrics
from obskit.metrics.golden import GoldenSignals
from obskit.metrics.use import USEMetrics

# RED: Rate, Errors, Duration
red = REDMetrics(service="api")
red.record_request("/orders", "POST", status="success", duration=0.032)

# Golden Signals: Latency, Traffic, Errors, Saturation
golden = GoldenSignals(service="api")
golden.record_request(latency=0.032, error=False)

# USE: Utilization, Saturation, Errors (infrastructure)
use = USEMetrics(resource="cpu")
use.record(utilization=0.72, saturation=0.05, errors=0)
```

### Distributed Tracing

```python
from obskit.tracing import setup_tracing, trace_span

setup_tracing(service_name="my-service", otlp_endpoint="http://otel-collector:4317")

with trace_span("process_order", attributes={"order.id": "123"}):
    result = process_order(order_id="123")
```

### Structured Logging

```python
from obskit.logging import get_logger

logger = get_logger(__name__)
logger.info("payment_processed", amount=99.99, currency="USD", user_id="u-42")
logger.error("payment_failed", error="card_declined", retry_count=3)
```

### Health Checks

```python
from obskit.health import HealthChecker

health = HealthChecker()
health.add_liveness_check("process", lambda: True)
health.add_readiness_check("database", check_db_connection)
health.add_readiness_check("redis", check_redis_connection)

result = await health.run_checks()
# result.status → "healthy" | "degraded" | "unhealthy"
```

### Resilience Patterns

```python
from obskit.resilience import CircuitBreaker
from obskit.resilience.retry import async_retry
from obskit.resilience.rate_limiter import RateLimiter

# Circuit breaker (async)
breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=30)
async with breaker:
    result = await call_external_service()

# Retry with exponential backoff
@async_retry(max_attempts=3, backoff_factor=2.0)
async def fetch_data():
    return await http_client.get("/api/data")

# Rate limiting
limiter = RateLimiter(requests_per_second=100)
async with limiter:
    await handle_request()
```

### SLO Tracking

```python
from obskit.slo import SLOTracker, SLOTarget, SLOType
from obskit.slo import with_slo_tracking

tracker = SLOTracker(
    name="api-availability",
    target=SLOTarget(slo_type=SLOType.AVAILABILITY, threshold=0.999)
)

@with_slo_tracking(tracker)
async def handle_request(request):
    return await process(request)
```

### FastAPI Middleware

```python
from fastapi import FastAPI
from obskit.middleware.fastapi import ObskitMiddleware
from obskit.tracing import setup_tracing

setup_tracing(service_name="api")

app = FastAPI()
app.add_middleware(ObskitMiddleware, service_name="api")
```

---

## Configuration

obskit is configured via environment variables or `obskit.yaml`:

```bash
OBSKIT_SERVICE_NAME=my-service
OBSKIT_ENVIRONMENT=production
OBSKIT_LOG_LEVEL=INFO
OBSKIT_LOG_FORMAT=json
OBSKIT_OTLP_ENDPOINT=http://otel-collector:4317
OBSKIT_METRICS_PORT=9090
```

Or programmatically:

```python
from obskit.config import configure

configure(
    service_name="my-service",
    environment="production",
    otlp_endpoint="http://otel-collector:4317",
    metrics_auth_enabled=True,
    metrics_auth_token="your-secret-token",
)
```

---

## Diagnose CLI

Check that obskit and all optional integrations are properly installed:

```bash
python -m obskit.core.diagnose
```

```
obskit diagnostics
==================
Core
  version         2.0.0    ✓
  python          3.11.8   ✓
Logging
  structlog       23.2.0   ✓
  trace-corr      enabled  ✓
Metrics
  prometheus      0.19.0   ✓
Tracing
  opentelemetry   1.22.0   ✓
  otlp-endpoint   http://otel-collector:4317
```

---

## Documentation

Full documentation at **[talaatmagdyx.github.io/obskit](https://talaatmagdyx.github.io/obskit/)**

- [Getting Started](https://talaatmagdyx.github.io/obskit/getting-started/installation/)
- [User Guide](https://talaatmagdyx.github.io/obskit/user-guide/metrics/)
- [Package Reference](https://talaatmagdyx.github.io/obskit/packages/core/)
- [Migration from v1](https://talaatmagdyx.github.io/obskit/migration/from-v1/)
- [API Reference](https://talaatmagdyx.github.io/obskit/reference/api/)

---

## Migrating from v1

```diff
-pip install obskit==1.5.0
+pip install "obskit[all]==2.0.0"   # drop-in compatible

# Import paths (old paths still work, new paths preferred)
-from obskit import configure_logging
+from obskit.logging import get_logger

-from obskit import get_red_metrics
+from obskit.metrics.red import REDMetrics

-from obskit import configure_tracing
+from obskit.tracing import setup_tracing
```

See the [Migration Guide](https://talaatmagdyx.github.io/obskit/migration/from-v1/) for full details.

---

## Development

```bash
# Install all packages in editable mode
pip install -e packages/obskit-core \
            -e packages/obskit-logging \
            -e packages/obskit-metrics \
            -e packages/obskit-tracing \
            -e packages/obskit-health \
            -e packages/obskit-resilience \
            -e packages/obskit-slo \
            -e packages/obskit-middleware-fastapi \
            -e packages/obskit-middleware-flask \
            -e packages/obskit-middleware-django \
            -e packages/obskit-middleware-grpc \
            -e packages/obskit

# Run all tests with coverage
pytest packages/ --cov=packages --cov-report=term-missing

# Lint
ruff check .

# Type check
mypy packages/

# Build docs
mkdocs build --strict
```

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) and the [Contributing Guide](https://talaatmagdyx.github.io/obskit/contributing/).

---

## License

MIT — see [LICENSE](LICENSE).
