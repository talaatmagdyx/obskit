<div align="center">

# 🧱 obskit-core

**The foundation every obskit package is built on — config, errors, correlation IDs, and shared interfaces**

---

[![PyPI](https://img.shields.io/pypi/v/obskit-core.svg?color=blue)](https://pypi.org/project/obskit-core/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![obskit](https://img.shields.io/badge/part%20of-obskit-blueviolet.svg)](https://github.com/talaatmagdyx/obskit)

</div>

## What it does

- **Centralised configuration** — one `ObskitSettings` object (pydantic-settings, env vars, `.env` file) powers every other obskit package with zero boilerplate.
- **Correlation ID propagation** — thread-safe and async-safe `contextvars`-backed context so every log, metric, and trace for a single request shares the same ID automatically.
- **Shared contracts** — abstract interfaces (`LoggerInterface`, `MetricsInterface`, `TracerInterface`, …) and a structured error hierarchy that every obskit package depends on.

---

## Installation

```bash
pip install obskit-core
```

`obskit-core` is a transitive dependency of every other obskit package. You rarely need to install it directly — installing `obskit-logging` or `obskit-tracing` pulls it in automatically.

---

## Quick Start

```python
from obskit.config import configure, get_settings

# Call once at application startup
configure(
    service_name="order-service",
    environment="production",
    version="1.4.2",
    log_level="INFO",
    log_format="json",
    tracing_enabled=True,
    otlp_endpoint="http://tempo:4317",
    trace_sample_rate=0.1,
)

settings = get_settings()
print(settings.service_name)   # "order-service"
print(settings.environment)    # "production"
print(settings.trace_sample_rate)  # 0.1
```

Or rely entirely on environment variables — no `configure()` call needed:

```bash
export OBSKIT_SERVICE_NAME=order-service
export OBSKIT_ENVIRONMENT=production
export OBSKIT_OTLP_ENDPOINT=http://tempo:4317
```

```python
from obskit.config import get_settings

settings = get_settings()  # reads OBSKIT_* env vars automatically
```

---

## Features

### 1. ObskitSettings — Pydantic-powered configuration

`ObskitSettings` is a `pydantic-settings` model that reads from environment variables (prefix `OBSKIT_`), a `.env` file, or programmatic kwargs — in that priority order.

```python
from obskit.config import configure, get_settings, validate_config, reset_settings

# Programmatic config (highest priority)
configure(
    service_name="payment-service",
    environment="production",
    version="2.0.0",
    tracing_enabled=True,
    otlp_endpoint="http://tempo:4317",
    trace_sample_rate=0.05,     # 5% sampling in prod
    metrics_enabled=True,
    metrics_port=9090,
    log_level="INFO",
    log_format="json",
    circuit_breaker_failure_threshold=5,
    retry_max_attempts=3,
)

# Validate before serving traffic
is_valid, errors = validate_config()
if not is_valid:
    for err in errors:
        print(f"Config problem: {err}")
    raise SystemExit(1)

# Access anywhere — thread-safe singleton
settings = get_settings()
print(f"Running {settings.service_name} v{settings.version} on :{settings.metrics_port}")

# Reset for tests
reset_settings()
```

### 2. Correlation ID context — thread-safe and async-safe

Every request gets a unique ID that flows automatically to logs, metrics, and traces without passing it manually through every function.

```python
from obskit.core.context import (
    correlation_context,
    async_correlation_context,
    set_correlation_id,
    get_correlation_id,
)

# Sync — use as a context manager
with correlation_context("req-abc-123"):
    cid = get_correlation_id()   # "req-abc-123"
    process_order()              # called functions see the same ID

# Auto-generate a UUID if you don't have one yet
with correlation_context():
    cid = get_correlation_id()   # "3f8a7b2c-1d4e-..."

# Async — child tasks inherit the correlation ID
async def handle_request(request):
    incoming_id = request.headers.get("X-Correlation-ID")
    async with async_correlation_context(incoming_id):
        # Both tasks see the same correlation_id
        await asyncio.gather(
            fetch_user(request.user_id),
            fetch_inventory(request.item_ids),
        )

# Set manually (e.g. in middleware)
set_correlation_id("req-xyz-789")
cid = get_correlation_id()   # "req-xyz-789"
```

### 3. Structured error hierarchy

obskit-core ships a set of observable errors that automatically embed `trace_id`, `span_id`, and `correlation_id` when creating structured error responses — ready to return directly from your API handlers.

```python
from obskit.errors import (
    ObservableError,
    ValidationError,
    NotFoundError,
    AuthenticationError,
    AuthorizationError,
    RateLimitError,
    ServiceUnavailableError,
    CircuitOpenError,
    create_error_response,
    ErrorResponse,
)

# Raise a domain error with an optional machine-readable code
raise ValidationError("quantity must be a positive integer", code="INVALID_QUANTITY")

# Convert any exception to a structured response dict (includes trace/correlation IDs)
try:
    result = place_order(order_data)
except Exception as exc:
    response: ErrorResponse = create_error_response(exc, include_trace_id=True)
    # response.to_dict() →
    # {
    #   "error": "quantity must be a positive integer",
    #   "error_type": "ValidationError",
    #   "code": "INVALID_QUANTITY",
    #   "trace_id": "4bf92f3577b34da6...",
    #   "correlation_id": "req-abc-123",
    #   "timestamp": "2026-03-01T10:00:00Z"
    # }
    return JSONResponse(status_code=422, content=response.to_dict())
```

### 4. Shared interfaces for dependency injection and testing

All obskit packages depend on abstract base classes rather than concrete implementations, making it trivial to swap in mock objects during testing or plug in custom backends.

```python
from obskit.interfaces import (
    LoggerInterface,
    MetricsInterface,
    TracerInterface,
    CircuitBreakerInterface,
    HealthCheckerInterface,
)
from unittest.mock import MagicMock

# Your service depends on the interface, not the concrete logger
class OrderService:
    def __init__(self, logger: LoggerInterface, metrics: MetricsInterface) -> None:
        self._log = logger
        self._metrics = metrics

    def create_order(self, order_data: dict) -> dict:
        self._log.info("creating_order", order_id=order_data["id"])
        order = self._do_create(order_data)
        self._metrics.observe_request("create_order", duration_ms=45.2)
        return order

# In tests — no real logging or metrics infrastructure needed
def test_create_order():
    mock_logger = MagicMock(spec=LoggerInterface)
    mock_metrics = MagicMock(spec=MetricsInterface)

    svc = OrderService(logger=mock_logger, metrics=mock_metrics)
    svc.create_order({"id": "ord-999", "user_id": "usr-1"})

    mock_logger.info.assert_called_once_with(
        "creating_order", order_id="ord-999"
    )
```

### 5. Config validation and test helpers

`validate_config()` catches common misconfiguration before your service starts serving traffic. `reset_settings()` gives each test a clean slate.

```python
import pytest
from obskit.config import configure, reset_settings, validate_config, get_settings

@pytest.fixture(autouse=True)
def clean_settings():
    """Ensure each test starts with fresh obskit settings."""
    yield
    reset_settings()

def test_invalid_config_detected():
    configure(tracing_enabled=True, otlp_endpoint="")  # missing endpoint

    is_valid, errors = validate_config()

    assert not is_valid
    assert any("otlp_endpoint" in e for e in errors)

def test_settings_from_env(monkeypatch):
    monkeypatch.setenv("OBSKIT_SERVICE_NAME", "user-service")
    monkeypatch.setenv("OBSKIT_ENVIRONMENT", "staging")

    settings = get_settings()
    assert settings.service_name == "user-service"
    assert settings.environment == "staging"
```

---

## Environment Variables

All variables use the `OBSKIT_` prefix and are case-insensitive.

### Service identification

| Variable | Default | Description |
|---|---|---|
| `OBSKIT_SERVICE_NAME` | `"unknown"` | Name used in all telemetry signals |
| `OBSKIT_ENVIRONMENT` | `"development"` | Deployment environment (`development`, `staging`, `production`) |
| `OBSKIT_VERSION` | `"0.0.0"` | Service version, typically injected by CI/CD |

### Tracing (OpenTelemetry)

| Variable | Default | Description |
|---|---|---|
| `OBSKIT_TRACING_ENABLED` | `true` | Enable distributed tracing |
| `OBSKIT_OTLP_ENDPOINT` | `"http://localhost:4317"` | OTLP gRPC collector URL |
| `OBSKIT_OTLP_INSECURE` | `true` | Use insecure (non-TLS) connection |
| `OBSKIT_TRACE_SAMPLE_RATE` | `1.0` | Sampling fraction 0.0–1.0 |
| `OBSKIT_TRACE_EXPORT_QUEUE_SIZE` | `2048` | Max span queue size before dropping |
| `OBSKIT_TRACE_EXPORT_BATCH_SIZE` | `512` | Max spans per export batch |
| `OBSKIT_TRACE_EXPORT_TIMEOUT` | `30.0` | Export timeout in seconds |

### Metrics (Prometheus)

| Variable | Default | Description |
|---|---|---|
| `OBSKIT_METRICS_ENABLED` | `true` | Enable Prometheus metrics |
| `OBSKIT_METRICS_PORT` | `9090` | HTTP server port for `/metrics` |
| `OBSKIT_METRICS_PATH` | `"/metrics"` | URL path for metrics endpoint |
| `OBSKIT_METRICS_METHOD` | `"red"` | Methodology: `red`, `golden`, `use`, or `all` |
| `OBSKIT_USE_HISTOGRAM` | `true` | Emit latency histograms |
| `OBSKIT_USE_SUMMARY` | `false` | Emit latency summaries (exact percentiles) |
| `OBSKIT_METRICS_SAMPLE_RATE` | `1.0` | Fraction of operations to record metrics for |
| `OBSKIT_METRICS_AUTH_ENABLED` | `false` | Require auth token on `/metrics` |
| `OBSKIT_METRICS_AUTH_TOKEN` | `""` | Token value (set via env, never hardcode) |

### Logging

| Variable | Default | Description |
|---|---|---|
| `OBSKIT_LOG_LEVEL` | `"INFO"` | Minimum level: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `OBSKIT_LOG_FORMAT` | `"json"` | Output format: `json` (prod) or `console` (dev) |
| `OBSKIT_LOG_INCLUDE_TIMESTAMP` | `true` | Add ISO 8601 timestamp to each entry |
| `OBSKIT_LOG_SAMPLE_RATE` | `1.0` | Fraction of non-error logs to emit |
| `OBSKIT_LOGGING_BACKEND` | `"structlog"` | Backend: `structlog`, `loguru`, or `auto` |

### Resilience

| Variable | Default | Description |
|---|---|---|
| `OBSKIT_CIRCUIT_BREAKER_FAILURE_THRESHOLD` | `5` | Consecutive failures before circuit opens |
| `OBSKIT_CIRCUIT_BREAKER_RECOVERY_TIMEOUT` | `30.0` | Seconds to wait before testing recovery |
| `OBSKIT_CIRCUIT_BREAKER_HALF_OPEN_REQUESTS` | `3` | Test requests allowed in half-open state |
| `OBSKIT_RETRY_MAX_ATTEMPTS` | `3` | Maximum total attempts (including first) |
| `OBSKIT_RETRY_BASE_DELAY` | `1.0` | Base delay in seconds for exponential backoff |
| `OBSKIT_RETRY_MAX_DELAY` | `60.0` | Cap on exponential backoff delay |
| `OBSKIT_RETRY_EXPONENTIAL_BASE` | `2.0` | Base for backoff calculation |
| `OBSKIT_RATE_LIMIT_REQUESTS` | `100` | Max requests per window |
| `OBSKIT_RATE_LIMIT_WINDOW_SECONDS` | `60.0` | Window size in seconds |

### Health checks

| Variable | Default | Description |
|---|---|---|
| `OBSKIT_HEALTH_CHECK_TIMEOUT` | `5.0` | Timeout for each individual health check |

### Internal

| Variable | Default | Description |
|---|---|---|
| `OBSKIT_ASYNC_METRIC_QUEUE_SIZE` | `10000` | Max async metric queue depth before dropping |
| `OBSKIT_ENABLE_SELF_METRICS` | `true` | Expose obskit's own internal metrics |

---

## 🧩 Part of the obskit family

`obskit-core` is part of the [obskit](https://github.com/talaatmagdyx/obskit) monorepo — a production-ready observability toolkit for Python microservices.

| Install only this package | Install everything |
|---|---|
| `pip install obskit-core` | `pip install "obskit[all]"` |
