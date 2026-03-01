# API Reference

Complete reference for all public APIs across all obskit packages.
APIs are stable across minor versions within a major version (SemVer).

!!! tip "Finding the right API"
    - **New to obskit?** Start with [`configure()`](#configure) and
      [`get_logger()`](#get_logger).
    - **Adding metrics?** See [`REDMetrics`](#redmetrics) for request metrics,
      [`GoldenSignals`](#goldensignals) for comprehensive monitoring.
    - **Tracing?** See [`setup_tracing()`](#setup_tracing) and [`trace_span()`](#trace_span).
    - **Health checks?** See [`HealthChecker`](#healthchecker).
    - **Circuit breaker?** See [`CircuitBreaker`](#circuitbreaker).
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

## obskit.resilience

**Package:** `obskit`
**Install:** `pip install obskit`

### CircuitBreaker

```python
from obskit.resilience import CircuitBreaker, CircuitState

breaker = CircuitBreaker(
    name="payment_api",
    failure_threshold=5,       # open after 5 failures
    recovery_timeout=30.0,     # wait 30s before half-open
    half_open_requests=3,      # test with 3 requests
)

# Async context manager
async with breaker:
    await call_payment_api()

# Sync context manager
with breaker:
    call_payment_api_sync()

# Check state
print(breaker.state)    # CircuitState.CLOSED | OPEN | HALF_OPEN
```

### CircuitState

```python
from obskit.resilience import CircuitState

CircuitState.CLOSED      # normal operation
CircuitState.OPEN        # fast-fail; no calls to downstream
CircuitState.HALF_OPEN   # testing recovery
```

### retry() / async_retry()

```python
from obskit.resilience import retry, async_retry

@retry(max_attempts=3, base_delay=1.0, max_delay=60.0, exponential_base=2.0)
def fetch_data():
    return requests.get("http://api/data").json()

@async_retry(max_attempts=3, base_delay=0.5)
async def async_fetch():
    return await httpx.get("http://api/data")
```

### RateLimiter

```python
from obskit.resilience import RateLimiter

limiter = RateLimiter(requests=100, window_seconds=60.0)

async def handle_request():
    if not await limiter.acquire():
        raise TooManyRequestsError("Rate limit exceeded")
    return await process()
```

---

## obskit.slo

**Package:** `obskit`
**Install:** `pip install obskit`

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
