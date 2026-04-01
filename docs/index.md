# obskit

**Production-ready observability toolkit for Python microservices.**

obskit is a single package with optional extras that brings structured logging, Prometheus metrics, OpenTelemetry tracing, and health checks to your Python services — with a consistent API and zero boilerplate.

## Features at a glance

| Feature | Extra | Install |
|---------|-------|---------|
| Structured logging + trace correlation | _(core, always included)_ | `pip install obskit` |
| Sensitive field redaction (structlog processor) | _(core, always included)_ | `pip install obskit` |
| RED metrics + exemplars | `prometheus` | `pip install "obskit[prometheus]"` |
| Distributed tracing (OTel) | `otlp` | `pip install "obskit[otlp]"` |
| FastAPI middleware | `fastapi` | `pip install "obskit[fastapi]"` |
| Flask middleware | `flask` | `pip install "obskit[flask]"` |
| Django middleware | `django` | `pip install "obskit[django]"` |
| Health check framework | `health` | `pip install "obskit[health]"` |
| Health check framework + HTTP checks | `health-http` | `pip install "obskit[health-http]"` |
| SLO tracking | `slo` | `pip install "obskit[slo]"` |
| SLO tracking + Prometheus burn-rate metrics | `slo-prometheus` | `pip install "obskit[slo-prometheus]"` |
| SQLAlchemy query tracking | `sqlalchemy` | `pip install "obskit[sqlalchemy]"` |
| psycopg2 instrumentation | `psycopg2` | `pip install "obskit[psycopg2]"` |
| psycopg3 instrumentation | `psycopg3` | `pip install "obskit[psycopg3]"` |
| All DB drivers | `db` | `pip install "obskit[db]"` |
| Kafka instrumentation | `kafka` | `pip install "obskit[kafka]"` |
| RabbitMQ instrumentation | `rabbitmq` | `pip install "obskit[rabbitmq]"` |
| gRPC server/client interceptors | `grpc` | `pip install "obskit[grpc]"` |
| All integrations (db + kafka + rabbitmq + grpc) | `integrations` | `pip install "obskit[integrations]"` |
| Everything above | `all` | `pip install "obskit[all]"` |

## Quick install

```bash
# Core only — structured logging, health checks, config
pip install obskit

# Full install — every extra included
pip install "obskit[all]"
```

## Zero-boilerplate setup

```python
from obskit import configure_observability, instrument_fastapi
from fastapi import FastAPI

app = FastAPI()

# One call at startup — configures tracing, metrics, logging
obs = configure_observability(
    service_name="order-service",
    environment="production",
    otlp_endpoint="http://tempo:4317",
    trace_sample_rate=0.1,
)

# One call to instrument your framework
instrument_fastapi(app)

log = obs.logger
log.info("order_placed", order_id="123", user_id="u-456")
# → {"event": "order_placed", "order_id": "123", "trace_id": "4bf92f...", "span_id": "00f067..."}
```

You can also use the individual APIs directly:

```python
from obskit import get_logger, configure_observability

configure_observability(service_name="my-service")
log = get_logger(__name__)
log.info("started")
```

## Why obskit?

- **Single package** — one `pip install obskit`, add extras only for what you use
- **One setup call** — `configure_observability()` sets up tracing, metrics, and logging in one shot
- **Zero import changes** — `from obskit.logging import get_logger` works regardless of which extras are installed
- **Graceful degradation** — optional integrations (OTel, Prometheus) no-op when their extra is not installed
- **100% test coverage** on all components (4,178 tests, enforced in CI)
- **PEP 561 typed** — full mypy support out of the box
