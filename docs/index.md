# obskit

**Production-ready observability toolkit for Python microservices.**

obskit is a single package with optional extras that brings structured logging, Prometheus metrics, OpenTelemetry tracing, and health checks to your Python services — with a consistent API and zero boilerplate.

## Features at a glance

| Feature | Extra | Install |
|---------|-------|---------|
| Structured logging + trace correlation | _(core, always included)_ | `pip install obskit` |
| Sensitive field redaction (structlog processor) | _(core, always included)_ | `pip install obskit` |
| Health check framework | _(core, always included)_ | `pip install obskit` |
| Circuit breaker / load shedding | _(core, always included)_ | `pip install obskit` |
| SLO tracking + alerting | _(core, always included)_ | `pip install obskit` |
| RED/Golden/USE metrics + exemplars | `prometheus` | `pip install "obskit[prometheus]"` |
| Distributed tracing (OTel) | `otlp` | `pip install "obskit[otlp]"` |
| FastAPI middleware | `fastapi` | `pip install "obskit[fastapi]"` |
| Flask middleware | `flask` | `pip install "obskit[flask]"` |
| Django middleware | `django` | `pip install "obskit[django]"` |
| SQLAlchemy query tracking | `sqlalchemy` | `pip install "obskit[sqlalchemy]"` |
| Kafka instrumentation | `kafka` | `pip install "obskit[kafka]"` |
| RabbitMQ instrumentation | `rabbitmq` | `pip install "obskit[rabbitmq]"` |
| Redis instrumentation | `redis` | `pip install "obskit[redis]"` |
| httpx instrumentation | `httpx` | `pip install "obskit[httpx]"` |
| Loguru adapter | `loguru` | `pip install "obskit[loguru]"` |
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
from obskit.tracing import setup_tracing
from obskit.logging import get_logger

# One call at startup — configures OTel tracing
setup_tracing(exporter_endpoint="http://tempo:4317", sample_rate=0.1)

log = get_logger(__name__)
log.info("order_placed", order_id="123", user_id="u-456")
# → {"event": "order_placed", "order_id": "123", "trace_id": "4bf92f...", "span_id": "00f067..."}
```

## Why obskit?

- **Single package** — one `pip install obskit`, add extras only for what you use
- **Zero import changes** — `from obskit.logging import get_logger` works regardless of which extras are installed
- **Graceful degradation** — optional integrations (OTel, Prometheus) no-op when their extra is not installed
- **100% test coverage** on all components (4,075 tests, enforced in CI)
- **PEP 561 typed** — full mypy support out of the box
