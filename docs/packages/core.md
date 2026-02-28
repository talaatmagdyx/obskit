# obskit-core

The foundational package for the obskit ecosystem. Every other obskit package depends on `obskit-core` for shared configuration, error types, interface protocols, correlation context management, and environment diagnostics.

## Installation

```bash
pip install obskit-core
```

## Package contents

| Module | Purpose |
|---|---|
| `obskit.config` | `ObskitSettings` — unified Pydantic-settings configuration |
| `obskit.core.diagnose` | Environment diagnostics CLI and API |
| `obskit.core.errors` | Structured exception hierarchy |
| `obskit.errors` | Observable error responses (HTTP-friendly) |
| `obskit.correlation` | Correlation / request / session ID management |
| `obskit.interfaces` | Abstract base classes (protocols) for metrics and logging backends |

---

## ObskitSettings

`obskit.config.ObskitSettings` is a [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) model that reads configuration from environment variables (prefixed `OBSKIT_`), a `.env` file, and programmatic overrides — in that order of priority.

```python
from obskit.config import ObskitSettings, configure, get_settings

# Lowest friction: just read from environment
settings = get_settings()

# Programmatic override (highest priority)
configure(
    service_name="order-service",
    environment="production",
    version="2.0.0",
)

# Direct construction
settings = ObskitSettings(
    service_name="order-service",
    environment="production",
)
```

### Service identification

| Env var | Field | Type | Default | Description |
|---|---|---|---|---|
| `OBSKIT_SERVICE_NAME` | `service_name` | `str` | `"unknown"` | Human-readable service name; appears in every log, metric label, and trace resource |
| `OBSKIT_ENVIRONMENT` | `environment` | `str` | `"development"` | Deployment environment (`development`, `staging`, `production`) |
| `OBSKIT_VERSION` | `version` | `str` | `"0.0.0"` | Service version, typically set from CI/CD |

### Tracing (OpenTelemetry)

| Env var | Field | Type | Default | Description |
|---|---|---|---|---|
| `OBSKIT_TRACING_ENABLED` | `tracing_enabled` | `bool` | `True` | Enable distributed tracing |
| `OBSKIT_OTLP_ENDPOINT` | `otlp_endpoint` | `str` | `"http://localhost:4317"` | OTLP collector endpoint (Tempo, Jaeger, …) |
| `OBSKIT_OTLP_INSECURE` | `otlp_insecure` | `bool` | `True` | Skip TLS verification (set `False` in production) |
| `OBSKIT_TRACE_SAMPLE_RATE` | `trace_sample_rate` | `float` | `1.0` | Sampling rate 0.0–1.0 |
| `OBSKIT_TRACE_EXPORT_QUEUE_SIZE` | `trace_export_queue_size` | `int` | `2048` | Span export queue capacity |
| `OBSKIT_TRACE_EXPORT_BATCH_SIZE` | `trace_export_batch_size` | `int` | `512` | Max spans per export batch |
| `OBSKIT_TRACE_EXPORT_TIMEOUT` | `trace_export_timeout` | `float` | `30.0` | Export timeout in seconds |

### Metrics (Prometheus)

| Env var | Field | Type | Default | Description |
|---|---|---|---|---|
| `OBSKIT_METRICS_ENABLED` | `metrics_enabled` | `bool` | `True` | Enable Prometheus metrics |
| `OBSKIT_METRICS_PORT` | `metrics_port` | `int` | `9090` | Metrics HTTP server port |
| `OBSKIT_METRICS_PATH` | `metrics_path` | `str` | `"/metrics"` | Scrape endpoint path |
| `OBSKIT_METRICS_METHOD` | `metrics_method` | `str` | `"red"` | Methodology: `red`, `golden`, `use`, or `all` |
| `OBSKIT_USE_HISTOGRAM` | `use_histogram` | `bool` | `True` | Use histograms for latency |
| `OBSKIT_USE_SUMMARY` | `use_summary` | `bool` | `False` | Use summaries for exact percentiles |

### Logging

| Env var | Field | Type | Default | Description |
|---|---|---|---|---|
| `OBSKIT_LOG_LEVEL` | `log_level` | `str` | `"INFO"` | Minimum level: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `OBSKIT_LOG_FORMAT` | `log_format` | `str` | `"json"` | Output format: `json` (production) or `console` (development) |
| `OBSKIT_LOG_INCLUDE_TIMESTAMP` | `log_include_timestamp` | `bool` | `True` | Include ISO 8601 timestamp |
| `OBSKIT_LOGGING_BACKEND` | `logging_backend` | `str` | `"structlog"` | Backend: `structlog`, `loguru`, or `auto` |
| `OBSKIT_LOG_SAMPLE_RATE` | `log_sample_rate` | `float` | `1.0` | Log sampling rate 0.0–1.0 |

### Health checks

| Env var | Field | Type | Default | Description |
|---|---|---|---|---|
| `OBSKIT_HEALTH_CHECK_TIMEOUT` | `health_check_timeout` | `float` | `5.0` | Per-check timeout in seconds |

### Circuit breaker

| Env var | Field | Type | Default | Description |
|---|---|---|---|---|
| `OBSKIT_CIRCUIT_BREAKER_FAILURE_THRESHOLD` | `circuit_breaker_failure_threshold` | `int` | `5` | Failures before opening |
| `OBSKIT_CIRCUIT_BREAKER_RECOVERY_TIMEOUT` | `circuit_breaker_recovery_timeout` | `float` | `30.0` | Seconds before half-open test |
| `OBSKIT_CIRCUIT_BREAKER_HALF_OPEN_REQUESTS` | `circuit_breaker_half_open_requests` | `int` | `3` | Test requests in half-open state |

### Retry

| Env var | Field | Type | Default | Description |
|---|---|---|---|---|
| `OBSKIT_RETRY_MAX_ATTEMPTS` | `retry_max_attempts` | `int` | `3` | Maximum attempts (including first try) |
| `OBSKIT_RETRY_BASE_DELAY` | `retry_base_delay` | `float` | `1.0` | Base delay in seconds |
| `OBSKIT_RETRY_MAX_DELAY` | `retry_max_delay` | `float` | `60.0` | Maximum delay cap in seconds |
| `OBSKIT_RETRY_EXPONENTIAL_BASE` | `retry_exponential_base` | `float` | `2.0` | Exponential backoff base |

### Rate limiting

| Env var | Field | Type | Default | Description |
|---|---|---|---|---|
| `OBSKIT_RATE_LIMIT_REQUESTS` | `rate_limit_requests` | `int` | `100` | Requests per window |
| `OBSKIT_RATE_LIMIT_WINDOW_SECONDS` | `rate_limit_window_seconds` | `float` | `60.0` | Window size in seconds |

### Configuration helpers

```python
from obskit.config import configure, get_settings, reset_settings, validate_config

# Configure at startup
configure(
    service_name="payment-gateway",
    environment="production",
    version="2.0.0",
    otlp_endpoint="http://tempo:4317",
    trace_sample_rate=0.1,
    log_level="INFO",
    log_format="json",
)

# Read anywhere in the app (cached, thread-safe)
settings = get_settings()
print(settings.service_name)    # "payment-gateway"
print(settings.trace_sample_rate)  # 0.1

# Validate configuration (returns (is_valid, list_of_errors))
ok, errors = validate_config()
if not ok:
    for err in errors:
        print(f"Config error: {err}")

# Reset to defaults — use in tests only
reset_settings()
```

### FastAPI startup example

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from obskit.config import configure

@asynccontextmanager
async def lifespan(app: FastAPI):
    configure(
        service_name="my-api",
        environment="production",
        version="2.0.0",
        otlp_endpoint="http://tempo:4317",
        trace_sample_rate=0.1,
    )
    yield

app = FastAPI(lifespan=lifespan)
```

---

## obskit.core.diagnose

A built-in diagnostics tool that reports which obskit packages are installed, their versions, and the availability of optional integrations (OpenTelemetry, Prometheus, structlog, etc.).

### Data classes

```python
from obskit.core.diagnose import PackageInfo, IntegrationInfo

# PackageInfo — one entry per obskit package
@dataclass
class PackageInfo:
    name: str                          # e.g. "obskit-tracing"
    installed: bool
    version: str | None
    integrations: list[IntegrationInfo]

# IntegrationInfo — an optional dependency within a package
@dataclass
class IntegrationInfo:
    label: str                         # e.g. "opentelemetry-api"
    available: bool
    detail: str | None                 # version string or status note
```

### Functions

```python
from obskit.core.diagnose import collect_diagnostics, run_diagnostics

# Collect structured data — useful for programmatic inspection
packages: list[PackageInfo] = collect_diagnostics()

for pkg in packages:
    print(f"{pkg.name}: installed={pkg.installed}, version={pkg.version}")
    for intg in pkg.integrations:
        print(f"  └─ {intg.label}: available={intg.available}, detail={intg.detail}")

# Print a formatted table to stdout (or any file-like object)
run_diagnostics()

# Write to a file
with open("diagnostics.txt", "w") as f:
    run_diagnostics(out=f)
```

### CLI usage

```bash
python -m obskit.core.diagnose
```

**Example output:**

```
obskit environment diagnostics
────────────────────────────────────────────────────────────────────────
Package                      Version      Status
────────────────────────────────────────────────────────────────────────
obskit-core                  2.0.0        ✅ installed
  └─ pydantic-settings        2.1.0        ✅
obskit-logging               2.0.0        ✅ installed
  └─ structlog                24.1.0       ✅
  └─ trace-correlation                     ✅ active
obskit-metrics               2.0.0        ✅ installed
  └─ prometheus-client        0.20.0       ✅
  └─ trace-exemplars                       ✅ active
obskit-tracing               2.0.0        ✅ installed
  └─ opentelemetry-api        1.24.0       ✅
  └─ opentelemetry-sdk        1.24.0       ✅
  └─ otlp-endpoint            http://tempo:4317  ✅
obskit-health                2.0.0        ✅ installed
  └─ health-tracing                        ✅ trace_id in /health responses
obskit-resilience            2.0.0        ✅ installed
obskit-slo                   2.0.0        ✅ installed
obskit-middleware-fastapi    2.0.0        ✅ installed
obskit-middleware-flask      not installed
obskit-middleware-django     not installed
obskit-middleware-grpc       not installed
obskit                       2.0.0        ✅ installed
────────────────────────────────────────────────────────────────────────
Python 3.12.1  |  /usr/local/bin/python3
```

---

## obskit.core.errors

Structured exception hierarchy. Every exception includes an `OBSKIT_*` error code for easier alerting and log querying.

### Base class

```python
from obskit.core.errors import ObskitError

try:
    raise ObskitError("Something went wrong", code="OBSKIT_UNKNOWN")
except ObskitError as e:
    print(e.code)     # "OBSKIT_UNKNOWN"
    print(e.message)  # "Something went wrong"
    print(e.details)  # {}
    print(e.to_dict())
    # {"code": "OBSKIT_UNKNOWN", "message": "...", "details": {}}
```

### Exception hierarchy

| Class | Error code | Description |
|---|---|---|
| `ObskitError` | `OBSKIT_UNKNOWN` | Base class for all obskit exceptions |
| `ConfigurationError` | `OBSKIT_CONFIG_ERROR` | Configuration loading or validation error |
| `ConfigFileNotFoundError` | `OBSKIT_CONFIG_FILE_NOT_FOUND` | Configuration file not found |
| `ConfigValidationError` | `OBSKIT_CONFIG_VALIDATION_ERROR` | Configuration validation failure |
| `CircuitBreakerError` | `OBSKIT_CIRCUIT_ERROR` | Circuit breaker base error |
| `CircuitOpenError` | `OBSKIT_CIRCUIT_OPEN` | Call attempted on open circuit |
| `CircuitHalfOpenError` | `OBSKIT_CIRCUIT_HALF_OPEN` | Half-open quota exceeded |
| `RetryError` | `OBSKIT_RETRY_EXHAUSTED` | All retry attempts exhausted |
| `RateLimitError` | `OBSKIT_RATE_LIMIT_ERROR` | Rate limiting base error |
| `RateLimitExceeded` | `OBSKIT_RATE_LIMIT_EXCEEDED` | Rate limit exceeded |
| `HealthCheckError` | `OBSKIT_HEALTH_ERROR` | Health check base error |
| `HealthCheckTimeoutError` | `OBSKIT_HEALTH_TIMEOUT` | Health check timed out |
| `HealthCheckFailedError` | `OBSKIT_HEALTH_FAILED` | Health check returned failure |
| `MetricsError` | `OBSKIT_METRICS_ERROR` | Metrics base error |
| `MetricsQueueFullError` | `OBSKIT_METRICS_QUEUE_FULL` | Async metrics queue full |
| `MetricsExportError` | `OBSKIT_METRICS_EXPORT_ERROR` | Metrics export failure |
| `TracingError` | `OBSKIT_TRACE_ERROR` | Tracing base error |
| `TracingExportError` | `OBSKIT_TRACE_EXPORT_ERROR` | Trace export failure |
| `TracingNotConfiguredError` | `OBSKIT_TRACE_NOT_CONFIGURED` | Tracing not yet configured |
| `SLOError` | `OBSKIT_SLO_ERROR` | SLO base error |
| `SLONotFoundError` | `OBSKIT_SLO_NOT_FOUND` | Named SLO not registered |
| `SLOBudgetExhaustedError` | `OBSKIT_SLO_BUDGET_EXHAUSTED` | Error budget exhausted |

```python
from obskit.core.errors import (
    CircuitOpenError,
    RetryError,
    RateLimitExceeded,
)

# CircuitOpenError carries recovery timing
try:
    async with breaker:
        await downstream_api()
except CircuitOpenError as e:
    print(e.breaker_name)       # "payment_api"
    print(e.time_until_retry)   # 25.3 (seconds)

# RetryError carries attempt metadata
except RetryError as e:
    print(e.attempts)           # 3
    print(e.last_exception)     # <TimeoutError ...>

# RateLimitExceeded carries limit details
except RateLimitExceeded as e:
    print(e.limit)              # 100
    print(e.window_seconds)     # 60.0
    print(e.retry_after)        # 12.5 (seconds)
```

### Error code lookup

```python
from obskit.core.errors import get_error_class

cls = get_error_class("OBSKIT_CIRCUIT_OPEN")
# → CircuitOpenError
```

---

## obskit.errors — Observable HTTP error responses

`obskit.errors` (note: different from `obskit.core.errors`) provides HTTP-friendly error responses with automatic trace context injection.

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
    ErrorResponse,
    create_error_response,
    format_exception,
)

# Create standardized error responses
try:
    process_request()
except Exception as e:
    response = create_error_response(e, include_trace_id=True)
    # response.trace_id is populated from the active OTel span

# Raise observable errors with extra context
raise ValidationError("Invalid email address", field="email")

# Format for JSON APIs
response = ErrorResponse(
    code="VALIDATION_ERROR",
    message="Invalid email",
    details={"field": "email"},
)
```

---

## obskit.correlation

Thread-safe and async-safe correlation context management using Python `contextvars`. Correlation IDs propagate automatically across async boundaries without any manual plumbing.

### Core functions

```python
from obskit.correlation import (
    generate_correlation_id,
    get_correlation_id,
    set_correlation_id,
    get_request_id,
    set_request_id,
    get_session_id,
    set_session_id,
    get_tenant_id,
    set_tenant_id,
    get_user_id,
    set_user_id,
    get_full_context,
)

# Generate a new UUID4 correlation ID
cid = generate_correlation_id()   # "f47ac10b-58cc-4372-a567-0e02b2c3d479"

# Store in context (returns a contextvars.Token for restoration)
token = set_correlation_id(cid)

# Retrieve from anywhere in the call stack (including async tasks)
current = get_correlation_id()    # "f47ac10b-..."

# Retrieve the full context dict (all non-None values)
ctx = get_full_context()
# {"correlation_id": "...", "request_id": "...", "tenant_id": "..."}
```

### CorrelationManager — context manager API

```python
from obskit.correlation import CorrelationManager

# Start a new request context (correlation_id auto-generated)
with CorrelationManager.new_context(
    request_id="req-001",
    tenant_id="acme-corp",
    user_id="user-42",
):
    # All logs / metrics inside here carry these IDs automatically
    await process_order(order)

# Capture and restore context (useful for task queues / thread pools)
ctx = CorrelationManager.capture()

async def background_task():
    with CorrelationManager.restore(ctx):
        await send_notification()

# HTTP header propagation
outgoing_headers = CorrelationManager.propagate_to_headers()
# {"X-Correlation-ID": "...", "X-Tenant-ID": "...", "X-Request-ID": "..."}

# Extract from incoming request headers
ctx = CorrelationManager.extract_from_headers(request.headers)
```

### @with_correlation decorator

```python
from obskit.correlation import with_correlation

@with_correlation(generate_if_missing=True)
async def handle_request(request):
    # correlation_id is always available here
    cid = get_correlation_id()
    ...
```

### create_correlated_task

```python
from obskit.correlation import create_correlated_task

# asyncio task that inherits the current correlation context
task = create_correlated_task(my_async_function())
```

---

## obskit.interfaces

Abstract base classes (protocols) that define the contracts for metrics and logging backends. Implement these to plug in custom observability backends.

### MetricsInterface

```python
from obskit.interfaces.metrics import MetricsInterface
import time
from contextlib import contextmanager

class MyMetrics(MetricsInterface):
    @property
    def name(self) -> str:
        return "my_service"

    def observe_request(
        self,
        operation: str,
        duration_seconds: float,
        status: str = "success",
        error_type: str | None = None,
    ) -> None:
        print(f"{operation}: {duration_seconds:.3f}s [{status}]")

    @contextmanager
    def track_request(self, operation: str):
        start = time.perf_counter()
        try:
            yield
            self.observe_request(operation, time.perf_counter() - start)
        except Exception as e:
            self.observe_request(
                operation,
                time.perf_counter() - start,
                "failure",
                type(e).__name__,
            )
            raise
```

**`GoldenSignalsInterface`** extends `MetricsInterface` with:

- `set_saturation(resource: str, value: float)` — saturation 0.0–1.0
- `set_queue_depth(queue_name: str, depth: int)`

**`USEMetricsInterface`** is a standalone ABC for infrastructure metrics:

- `set_utilization(resource: str, value: float)`
- `set_saturation(resource: str, value: float)`
- `inc_error(resource: str, error_type: str)`

### LoggerInterface

```python
from obskit.interfaces.logging import LoggerInterface
from typing import Any

class MyLogger(LoggerInterface):
    def debug(self, event: str, **kwargs: Any) -> None:
        print(f"[DEBUG] {event}", kwargs)

    def info(self, event: str, **kwargs: Any) -> None:
        print(f"[INFO] {event}", kwargs)

    def warning(self, event: str, **kwargs: Any) -> None:
        print(f"[WARN] {event}", kwargs)

    def error(self, event: str, **kwargs: Any) -> None:
        print(f"[ERROR] {event}", kwargs)

    def critical(self, event: str, **kwargs: Any) -> None:
        print(f"[CRIT] {event}", kwargs)

    def exception(self, event: str, **kwargs: Any) -> None:
        print(f"[EXCEPTION] {event}", kwargs)

    def bind(self, **kwargs: Any) -> "MyLogger":
        # Return a logger with bound context
        return self
```

!!! tip "Built-in adapters"
    `obskit-logging` ships structlog and loguru adapters that implement `LoggerInterface` out of the box. You only need to implement it yourself when integrating a completely custom logging backend.
