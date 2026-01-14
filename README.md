# obskit

[![PyPI version](https://img.shields.io/pypi/v/obskit.svg)](https://pypi.org/project/obskit/)
[![PyPI Downloads](https://img.shields.io/pypi/dm/obskit.svg)](https://pypi.org/project/obskit/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Coverage: 100%](https://img.shields.io/badge/coverage-100%25-brightgreen.svg)](tests/)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Type checked: mypy](https://img.shields.io/badge/type%20checked-mypy-blue.svg)](https://mypy-lang.org/)

**Production-ready observability toolkit for Python microservices.**

obskit provides unified metrics, tracing, logging, and resilience patterns following industry best practices like RED, Golden Signals, and USE methodologies.

> 🎉 **v1.0.0 Released** - Production stable with full API stability guarantees!

## Features

- **Metrics** - RED, Golden Signals, and USE with Prometheus export, OTLP metrics, Pushgateway
- **Tracing** - OpenTelemetry-based distributed tracing
- **Logging** - Pluggable logging with structlog and loguru support
- **Health Checks** - Kubernetes-compatible liveness and readiness probes
- **Resilience** - Circuit breakers (local + Redis-backed distributed), retries, and rate limiting
- **SLO Tracking** - Error budgets, compliance monitoring, and Alertmanager integration
- **Framework Support** - FastAPI, Flask, and Django middleware
- **Production Ready** - Full type hints, 100% test coverage, comprehensive benchmarks

## Installation

```bash
# Core package
pip install obskit

# With specific features
pip install obskit[metrics]       # Prometheus metrics
pip install obskit[tracing]       # OpenTelemetry tracing
pip install obskit[loguru]        # Loguru logging backend
pip install obskit[flask]         # Flask middleware
pip install obskit[django]        # Django middleware
pip install obskit[pushgateway]   # Prometheus Pushgateway
pip install obskit[otlp-metrics]  # OTLP metrics export
pip install obskit[redis-async]   # Async Redis for distributed circuit breaker

# All features
pip install obskit[all]
```

## Quick Start

```python
from obskit import (
    configure_logging,
    get_red_metrics,
    get_health_checker,
    start_http_server,
)

# Configure structured logging
logger = configure_logging(service_name="my-service")

# Set up RED metrics
metrics = get_red_metrics(service_name="my-service")

# Track requests
with metrics.track_request(endpoint="/api/users", method="GET"):
    users = get_users()

# Health checks
health = get_health_checker()
health.add_readiness_check("database", check_database)

# Start metrics server
start_http_server(port=9090)
```

## Documentation

Full documentation is available at [obskit.readthedocs.io](https://obskit.readthedocs.io/).

- [Getting Started](https://obskit.readthedocs.io/getting-started/)
- [User Guide](https://obskit.readthedocs.io/user-guide/)
- [API Reference](https://obskit.readthedocs.io/api/)
- [Examples](https://obskit.readthedocs.io/examples/)

## Why obskit?

Modern microservices need comprehensive observability to:

- **Detect issues quickly** - Know when things go wrong before users report them
- **Debug efficiently** - Trace requests across services with correlated logs
- **Measure reliability** - Track SLOs and error budgets
- **Scale confidently** - Understand resource utilization patterns

obskit provides all of this with minimal configuration and follows proven methodologies:

| Methodology | Use Case |
|-------------|----------|
| **RED** | Request-driven services (APIs) |
| **Golden Signals** | Services with resource constraints |
| **USE** | Infrastructure and resources |

## FastAPI Example

```python
from fastapi import FastAPI
from obskit import get_red_metrics, configure_logging, start_http_server
from obskit.middleware import ObskitMiddleware

app = FastAPI()
logger = configure_logging(service_name="api")
metrics = get_red_metrics()

app.add_middleware(ObskitMiddleware)

@app.on_event("startup")
async def startup():
    start_http_server(port=9090)

@app.get("/users")
async def list_users():
    logger.info("Listing users")
    return {"users": []}
```

## Framework Support

### Flask

```python
from flask import Flask
from obskit.middleware import ObskitFlaskMiddleware

app = Flask(__name__)
ObskitFlaskMiddleware(app)
```

### Django

```python
# settings.py
MIDDLEWARE = [
    'obskit.middleware.ObskitDjangoMiddleware',
    # ... other middleware
]
```

## Resilience Patterns

```python
from obskit import CircuitBreaker, retry_async, DistributedCircuitBreaker

# Local circuit breaker
breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=30)

@retry_async(max_attempts=3, base_delay=1.0)
async def call_external_api():
    async with breaker:
        return await httpx.get("https://api.example.com")

# Distributed circuit breaker (Redis-backed, supports async)
import redis.asyncio as redis
redis_client = redis.Redis()
distributed_breaker = DistributedCircuitBreaker(
    name="payment-api",
    redis_client=redis_client,  # or sync redis.Redis()
    failure_threshold=5,
)
```

## Pluggable Logging

```python
from obskit.logging.factory import configure_logging_backend

# Use structlog (default)
configure_logging_backend(backend="structlog", service_name="my-service")

# Or use loguru
configure_logging_backend(backend="loguru", service_name="my-service")
```

## Metrics Export

```python
from obskit import OTLPMetricsExporter, PushgatewayExporter

# OTLP metrics export
otlp = OTLPMetricsExporter(endpoint="http://otel-collector:4317")
otlp.export()

# Pushgateway for batch jobs
push = PushgatewayExporter(
    gateway="http://pushgateway:9091",
    job="batch-processor"
)
push.push()
```

## Alertmanager Integration

```python
from obskit import SyncAlertmanagerWebhook

alertmanager = SyncAlertmanagerWebhook(
    alertmanager_url="http://alertmanager:9093"
)

# Send SLO alert
alertmanager.send_alert(
    alert_name="HighErrorRate",
    severity="critical",
    labels={"service": "api"},
    annotations={"summary": "Error rate exceeded 1%"}
)
```

## Verify Installation

After installation, verify everything works:

```python
# Check version
import obskit
print(f"obskit v{obskit.__version__}")

# Quick verification
from obskit import configure_logging, get_red_metrics

logger = configure_logging(service_name="test")
logger.info("obskit is working!")

metrics = get_red_metrics(service_name="test")
print("✅ obskit installed successfully!")
```

## Observability Methodologies

obskit implements three industry-standard monitoring approaches:

| Methodology | Best For | Key Metrics |
|-------------|----------|-------------|
| **RED** | Request-driven services (APIs) | Rate, Errors, Duration |
| **Golden Signals** | Services with resource constraints | Latency, Traffic, Errors, Saturation |
| **USE** | Infrastructure resources | Utilization, Saturation, Errors |

```python
from obskit.metrics import REDMetrics, GoldenSignals, USEMetrics

# RED for API services
red = REDMetrics("order_service")
red.observe_request("create_order", duration_seconds=0.045, status="success")

# Golden Signals for comprehensive monitoring
golden = GoldenSignals("order_service")
golden.observe_request("create_order", duration_seconds=0.045)
golden.set_saturation("cpu", 0.75)

# USE for infrastructure
cpu = USEMetrics("server_cpu")
cpu.set_utilization("cpu", 0.65)
```

## Development

```bash
# Clone and install
git clone https://github.com/talaatmagdyx/obskit.git
cd obskit
pip install -e ".[all,dev,docs]"

# Run tests
pytest tests/ -v --cov=src/obskit

# Run linting
ruff check src/ tests/

# Type checking
mypy src/obskit --strict

# Build documentation
cd docs && make html
```

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## Acknowledgements

obskit builds upon excellent open-source projects:
- [structlog](https://www.structlog.org/) - Structured logging
- [prometheus-client](https://github.com/prometheus/client_python) - Prometheus metrics
- [OpenTelemetry](https://opentelemetry.io/) - Distributed tracing

## License

MIT License - see [LICENSE](LICENSE) for details.

---

<p align="center">
  Made with ❤️ for the Python community
</p>
