# API Reference

Complete reference for all public APIs across all obskit packages.
APIs are stable across minor versions within a major version (SemVer).

!!! tip "Finding the right API"
    - **New to obskit?** Start with [`configure_observability()`](#configure_observability) (v1.0.0+)
      or [`configure()`](#configure) (legacy, still supported).
    - **Adding metrics?** See [`REDMetrics`](#redmetrics) for request metrics.
    - **Tracing?** See [`setup_tracing()`](#setup_tracing) and [`trace_span()`](#trace_span).
    - **Health checks?** See [`HealthChecker`](#healthchecker).
    - **Framework instrumentation?** See [`instrument_fastapi()`](#instrument_fastapi),
      [`instrument_flask()`](#instrument_flask), [`instrument_django()`](#instrument_django).
    - **Diagnosing issues?** See [`collect_diagnostics()`](#collect_diagnostics).

---

## obskit.config

**Package:** `obskit`
**Install:** `pip install obskit`

### configure()

```python
from obskit.config import configure
```

Configure all obskit packages at application startup.  Must be called before
any other obskit API.

```python
configure(
    service_name="order-service",
    environment="production",          # development | staging | production
    version="1.2.3",
    log_level="INFO",                  # DEBUG | INFO | WARNING | ERROR | CRITICAL
    log_format="json",                 # json | console
    metrics_enabled=True,
    tracing_enabled=True,
    otlp_endpoint="http://tempo:4317",
    trace_sample_rate=0.1,             # 0.0–1.0
)
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `service_name` | `str` | `"unknown"` | Identifies this service in traces, metrics, and logs |
| `environment` | `str` | `"development"` | Deployment environment |
| `version` | `str` | `"0.0.0"` | Service version (added to OTel resource) |
| `log_level` | `str` | `"INFO"` | Minimum log level |
| `log_format` | `str` | `"json"` | Output format (`json` or `console`) |
| `metrics_enabled` | `bool` | `True` | Enable Prometheus metrics |
| `tracing_enabled` | `bool` | `True` | Enable OpenTelemetry tracing |
| `otlp_endpoint` | `str` | `"http://localhost:4317"` | OTLP collector endpoint |
| `trace_sample_rate` | `float` | `1.0` | Fraction of traces to sample |

### get_settings()

```python
from obskit.config import get_settings

settings = get_settings()
print(settings.service_name)
print(settings.otlp_endpoint)
```

Returns the current `ObskitSettings` singleton.  Thread-safe; initialised
lazily on first call if `configure()` has not been called.

### ObskitSettings

```python
from obskit.config import ObskitSettings
```

Pydantic-Settings model.  All fields can be set via `OBSKIT_*` environment
variables.  See the [Configuration Reference](configuration.md) for the full
field list.

---

## obskit — Unified API (v1.0.0+)

**Package:** `obskit`
**Install:** `pip install obskit`

The unified API provides a single entry point that configures logging, tracing,
and metrics in one call.  The legacy `configure()` + `setup_tracing()` +
`configure_logging()` sequence still works and is not deprecated.

### configure_observability()

```python
from obskit import configure_observability
```

One-call setup that replaces the previous multi-step initialisation.  Returns
an [`Observability`](#observability) handle.

```python
obs = configure_observability(
    service_name="order-service",
    environment="production",
    version="1.0.0",
    tracing_enabled=True,
    otlp_endpoint="http://tempo:4317",
    trace_sample_rate=0.1,
    log_level="INFO",
    log_format="json",
    metrics_enabled=True,
)

logger = obs.logger(__name__)
logger.info("ready")
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `service_name` | `str` | `"unknown"` | Identifies this service in traces, metrics, and logs |
| `environment` | `str` | `"development"` | Deployment environment |
| `version` | `str` | `"0.0.0"` | Service version |
| `log_level` | `str` | `"INFO"` | Minimum log level |
| `log_format` | `str` | `"json"` | `json` or `console` |
| `metrics_enabled` | `bool` | `True` | Enable Prometheus metrics |
| `tracing_enabled` | `bool` | `True` | Enable OpenTelemetry tracing |
| `otlp_endpoint` | `str` | `"http://localhost:4317"` | OTLP collector endpoint |
| `trace_sample_rate` | `float` | `1.0` | Fraction of traces to sample |

### Observability

```python
from obskit import configure_observability

obs = configure_observability(service_name="my-service")
```

Returned by `configure_observability()`.  Provides access to all subsystems.

| Attribute / Method | Type | Description |
|---|---|---|
| `obs.tracer` | OTel `Tracer` | The configured OpenTelemetry tracer |
| `obs.metrics` | Metrics registry handle | Access to the Prometheus metrics registry |
| `obs.logger(name)` | `BoundLogger` | Returns a structlog logger with trace injection |
| `obs.config` | `ObservabilityConfig` | Frozen snapshot of the active configuration |
| `await obs.shutdown()` | coroutine | Flush pending spans / metrics and release resources |

### ObservabilityConfig

```python
from obskit import configure_observability

obs = configure_observability(service_name="my-service")
cfg = obs.config

print(cfg.service_name)   # "my-service"
print(cfg.environment)    # "development"
```

Frozen dataclass that exposes the effective configuration.  Read-only after
creation.

### get_observability()

```python
from obskit import get_observability

obs = get_observability()
# Returns the Observability instance created by configure_observability(),
# or None if configure_observability() has not been called yet.
```

Retrieve the current `Observability` singleton from anywhere in the
application.  Useful in modules that cannot receive the handle directly.

### reset_observability()

```python
from obskit import reset_observability

reset_observability()
```

Tear down the current `Observability` instance and reset global state.
Primarily used in test fixtures.

### instrument_fastapi()

```python
from obskit import instrument_fastapi

app = FastAPI()
instrument_fastapi(
    app,
    exclude_paths={"/health/live", "/health/ready", "/metrics"},
)
```

Attach `ObskitMiddleware` (raw ASGI) to a FastAPI application.  Automatically
records RED metrics, creates trace spans for every request, and propagates
correlation IDs.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `app` | `FastAPI` | required | The FastAPI application instance |
| `exclude_paths` | `set[str]` | `set()` | Paths to exclude from tracing and metrics |

### instrument_flask()

```python
from obskit import instrument_flask

app = Flask(__name__)
instrument_flask(
    app,
    exclude_paths={"/health/live", "/health/ready", "/metrics"},
)
```

Wrap a Flask application's WSGI callable with `ObskitFlaskMiddleware`.
Provides the same RED metrics, tracing, and correlation ID propagation as
`instrument_fastapi()`.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `app` | `Flask` | required | The Flask application instance |
| `exclude_paths` | `set[str]` | `set()` | Paths to exclude from tracing and metrics |

### instrument_django()

```python
from obskit import instrument_django

instrument_django()
```

Install obskit middleware into the Django middleware stack.  Call this in your
Django `settings.py` or `AppConfig.ready()` method.  The middleware is
inserted at the outermost position automatically.

---

## obskit.logging

**Package:** `obskit`
**Install:** `pip install obskit`

### get_logger()

```python
from obskit.logging import get_logger

logger = get_logger(__name__)
logger.info("order_created", order_id="ord-123", total=99.99)
logger.warning("inventory_low", sku="SKU-001", remaining=3)
logger.error("payment_failed", order_id="ord-456", reason="card_declined")
```

Returns a structlog `BoundLogger` pre-configured with:

- Service name, environment, and version from `ObskitSettings`.
- Trace ID and span ID injected automatically when a span is active.
- JSON or console output per `log_format` setting.
- Correlation ID from the current context.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `name` | `str` | required | Logger name (use `__name__`) |

### is_trace_correlation_available()

```python
from obskit.logging import is_trace_correlation_available

if is_trace_correlation_available():
    print("opentelemetry-sdk is installed; trace_id will appear in logs")
```

Returns `True` when `opentelemetry-api` is installed and a tracer provider is
configured.  Always safe to call — returns `False` gracefully when OTel is not
installed.

### get_trace_context()

```python
from obskit.logging import get_trace_context

ctx = get_trace_context()
# {"trace_id": "4bf92f3577b34da6...", "span_id": "00f067aa0ba902b7"}
# or {} when no span is active
```

Returns a dictionary with the current `trace_id` and `span_id` suitable for
inclusion in log records or API responses.

---

## obskit.metrics

**Package:** `obskit[prometheus]`
**Install:** `pip install "obskit[prometheus]"`

### REDMetrics

```python
from obskit.metrics import REDMetrics
```

Implements the RED Method (Rate, Errors, Duration) for service endpoints.

```python
red = REDMetrics("order_service")

# Record a completed request
red.record_request(
    endpoint="/api/orders",
    method="POST",
    status="success",          # "success" or "error"
    duration=0.045,            # seconds
)
```

**Prometheus metrics created:**

| Metric | Type | Labels |
|---|---|---|
| `{name}_requests_total` | Counter | `endpoint`, `method`, `status` |
| `{name}_request_duration_seconds` | Histogram | `endpoint`, `method` |
| `{name}_errors_total` | Counter | `endpoint`, `method`, `error_type` |

### GoldenSignals

```python
from obskit.metrics import GoldenSignals
```

Implements Google SRE's Four Golden Signals (Latency, Traffic, Errors, Saturation).

```python
golden = GoldenSignals("payment_service")

golden.observe_request("charge", duration_seconds=0.042)
golden.set_saturation("cpu", 0.78)          # 0.0–1.0
golden.set_queue_depth("payment_queue", 156)
```

### USEMetrics

```python
from obskit.metrics import USEMetrics
```

Implements Brendan Gregg's USE Method (Utilization, Saturation, Errors) for
infrastructure resources.

```python
cpu = USEMetrics("server_cpu")
cpu.set_utilization("cpu", 0.65)            # 0.0–1.0
cpu.set_saturation("cpu", queue_depth=3)
cpu.record_error("cpu", "thermal_throttle")
```

### TenantMetrics

```python
from obskit.metrics import TenantMetrics
```

Per-tenant request metrics with automatic cardinality protection.

```python
tenant_metrics = TenantMetrics("api_service", max_tenants=500)
tenant_metrics.record_request("acme-corp", "/api/orders", duration=0.032)
```

### CardinalityGuard

```python
from obskit.metrics.cardinality import CardinalityGuard
```

Prevents Prometheus OOM by capping the number of unique label values.

```python
guard = CardinalityGuard(max_cardinality=500)
safe_label = guard.safe_label("user_id", user_id)
# Returns user_id if within budget, "__overflow__" otherwise
```

### observe_with_exemplar()

```python
from obskit.metrics.exemplar import observe_with_exemplar
```

Observe a Prometheus Histogram or Summary with the current OTel trace ID as
an exemplar (enables "jump from metric to trace" in Grafana).

```python
from prometheus_client import Histogram
from obskit.metrics.exemplar import observe_with_exemplar

LATENCY = Histogram("request_duration_seconds", "Latency", ["endpoint"])

observe_with_exemplar(LATENCY.labels(endpoint="/api/orders"), duration=0.042)
# Adds {"trace_id": "4bf92f3577b34da6..."} exemplar automatically
```

### get_trace_exemplar()

```python
from obskit.metrics.exemplar import get_trace_exemplar

exemplar = get_trace_exemplar()
# {"trace_id": "4bf92f3577b34da6a3ce929d0e0e4736"} or {}
```

Returns the current OTel trace ID formatted as a Prometheus exemplar dict.

### is_exemplar_available()

```python
from obskit.metrics.exemplar import is_exemplar_available

if is_exemplar_available():
    print("OTel SDK installed; exemplars will be attached to observations")
```

---

## obskit.tracing

**Package:** `obskit[otlp]`
**Install:** `pip install "obskit[otlp]"`

### setup_tracing()

```python
from obskit.tracing import setup_tracing
```

Configure OpenTelemetry tracing.  Call once at application startup, before
creating routes or importing framework code.

```python
setup_tracing(
    exporter_endpoint="http://tempo:4317",   # OTLP gRPC endpoint
    sample_rate=0.1,                         # 10% sampling
    debug=False,                             # True = print spans to stdout
    instrument=["fastapi", "sqlalchemy"],    # explicit list; [] = no auto
    resource_attributes={"k8s.pod.name": os.environ.get("POD_NAME", "")},
)
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `exporter_endpoint` | `str \| None` | from settings | OTLP collector endpoint |
| `sample_rate` | `float` | from settings | 0.0–1.0 |
| `debug` | `bool` | `False` | Print spans to stdout (development) |
| `instrument` | `list[str] \| None` | `None` (auto-detect) | Instrumentors to apply |
| `resource_attributes` | `dict` | `{}` | Extra OTel resource attributes |

### trace_span()

```python
from obskit.tracing import trace_span

with trace_span("my_operation", attributes={"key": "value"}) as span:
    result = do_work()
    span.set_attribute("result.count", len(result))
```

Synchronous context manager that creates and manages an OTel span.  Automatically
records exceptions and sets error status.

### async_trace_span()

```python
from obskit.tracing import async_trace_span

async with async_trace_span("fetch_data", attributes={"table": "orders"}) as span:
    data = await db.query("SELECT * FROM orders")
    span.set_attribute("rows.returned", len(data))
```

Async context manager equivalent of `trace_span()`.

### set_baggage() / get_baggage() / clear_baggage()

```python
from obskit.tracing import set_baggage, get_baggage, clear_baggage

set_baggage("tenant_id", "acme-corp")
tenant = get_baggage("tenant_id")    # "acme-corp"
clear_baggage("tenant_id")
```

W3C Baggage propagation.  Baggage values are propagated across service boundaries
via HTTP headers (`baggage: tenant_id=acme-corp`).

### get_current_trace_id() / get_current_span_id()

```python
from obskit.tracing import get_current_trace_id, get_current_span_id

trace_id = get_current_trace_id()    # "4bf92f3577b34da6a3ce929d0e0e4736" or None
span_id  = get_current_span_id()    # "00f067aa0ba902b7" or None
```

---

## obskit.health

**Package:** `obskit`
**Install:** `pip install obskit`

### HealthChecker

```python
from obskit.health import HealthChecker

checker = HealthChecker()

# Add a check (called on every /health request)
async def check_database() -> bool:
    return await db.ping()

checker.add_check("database", check_database)
checker.add_check("redis", lambda: redis_client.ping())

# Run all checks
result = await checker.run_checks()
print(result.status)    # HealthStatus.HEALTHY | DEGRADED | UNHEALTHY
```

### HealthResult

```python
from obskit.health import HealthResult, HealthStatus

result: HealthResult
result.status          # HealthStatus enum
result.checks          # dict[str, bool]
result.trace_id        # str | None — OTel trace ID for correlation
result.duration_ms     # float — total check duration
```

### HealthStatus

```python
from obskit.health import HealthStatus

HealthStatus.HEALTHY    # all checks passed
HealthStatus.DEGRADED   # some checks failed (non-critical)
HealthStatus.UNHEALTHY  # critical checks failed
```

### create_http_check()

```python
from obskit.health import create_http_check

# Returns a coroutine that GETs the URL and returns True if status < 400
db_check = create_http_check("http://postgres-sidecar:5432/health")
checker.add_check("postgres", db_check)
```

### create_tcp_check()

```python
from obskit.health import create_tcp_check

# Returns a coroutine that opens a TCP connection and returns True on success
redis_check = create_tcp_check(host="redis", port=6379, timeout=2.0)
checker.add_check("redis", redis_check)
```

---

## obskit.slo

**Package:** `obskit[slo]`
**Install:** `pip install "obskit[slo]"`

### SLOTracker

```python
from obskit.slo import SLOTracker, SLOType

tracker = SLOTracker()
tracker.register_slo(
    name="api_availability",
    slo_type=SLOType.AVAILABILITY,
    target_value=0.999,            # 99.9%
    window_seconds=3600,           # 1-hour rolling window
)

# Record measurements
tracker.record_measurement("api_availability", value=1.0, success=True)
tracker.record_measurement("api_availability", value=0.0, success=False)

# Check status
status = tracker.get_status("api_availability")
print(f"Current: {status.current_value:.4%}")
print(f"Budget remaining: {status.error_budget_remaining:.4%}")
```

### SLOType

```python
from obskit.slo import SLOType

SLOType.AVAILABILITY   # % of successful requests
SLOType.LATENCY        # % of requests under threshold
SLOType.ERROR_RATE     # % of failed requests (inverted)
SLOType.THROUGHPUT     # requests per second
```

### with_slo_tracking() / with_slo_tracking_sync()

```python
from obskit.slo import with_slo_tracking, with_slo_tracking_sync

@with_slo_tracking("api_availability")
async def handle_order():
    return await process_order()

@with_slo_tracking_sync("api_availability")
def handle_order_sync():
    return process_order()
```

Decorator that records a measurement on each call.  Marks as `success=True` when
the function returns normally, `success=False` when an exception propagates.

---

## obskit.core.diagnose

**Package:** `obskit`
**Install:** `pip install obskit`

### collect_diagnostics()

```python
from obskit.core.diagnose import collect_diagnostics

info = collect_diagnostics()
# Returns list[PackageInfo] — one per obskit package
for pkg in info:
    print(f"{pkg.name}: {pkg.version} {'✓' if pkg.installed else '✗'}")
    for integration in pkg.integrations:
        print(f"  {integration.label}: {'✓' if integration.available else '✗'}")
```

### run_diagnostics()

```python
from obskit.core.diagnose import run_diagnostics

# Prints a formatted diagnostics table to stdout
run_diagnostics()
```

Or from the command line:

```bash
python -m obskit.core.diagnose
```

### PackageInfo

```python
from obskit.core.diagnose import PackageInfo

pkg: PackageInfo
pkg.name        # "obskit"
pkg.installed   # True | False
pkg.version     # "2.0.0" | None
pkg.integrations  # list[IntegrationInfo]
```

### IntegrationInfo

```python
from obskit.core.diagnose import IntegrationInfo

integration: IntegrationInfo
integration.label      # "opentelemetry-sdk"
integration.available  # True | False
integration.detail     # "1.23.0" | None | error message
```
