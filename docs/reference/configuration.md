# Configuration Reference

obskit is configured through a single `ObskitSettings` object backed by
[pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/).
All settings can be provided via:

1. **Environment variables** — prefix `OBSKIT_` (recommended for production)
2. **`configure()` call** — programmatic, at application startup
3. **`.env` file** — for local development

Settings are read in the order above; environment variables override `.env` files,
which override code-level defaults.

---

## Quick Start

```python
from obskit.config import configure

configure(
    service_name="order-service",
    environment="production",
    version="1.2.3",
    log_level="INFO",
    log_format="json",
    metrics_enabled=True,
    tracing_enabled=True,
    otlp_endpoint="http://tempo:4317",
    trace_sample_rate=0.1,
)
```

Or via environment variables:

```bash
export OBSKIT_SERVICE_NAME=order-service
export OBSKIT_ENVIRONMENT=production
export OBSKIT_VERSION=1.2.3
export OBSKIT_LOG_LEVEL=INFO
export OBSKIT_LOG_FORMAT=json
export OBSKIT_OTLP_ENDPOINT=http://tempo:4317
export OBSKIT_TRACE_SAMPLE_RATE=0.1
```

---

## Service Identity

| Field | Env Var | Type | Default | Description |
|---|---|---|---|---|
| `service_name` | `OBSKIT_SERVICE_NAME` | `str` | `"unknown"` | Human-readable service identifier.  Appears in traces, metrics labels, and log records. Set this; the default triggers a validation warning. |
| `environment` | `OBSKIT_ENVIRONMENT` | `str` | `"development"` | Deployment environment.  Validated values: `development`, `staging`, `production`.  Custom values are allowed but warn. |
| `version` | `OBSKIT_VERSION` | `str` | `"0.0.0"` | Service version.  Injected as an OTel resource attribute (`service.version`) and a Prometheus label. |

**Validation rules:**

- `service_name == "unknown"` → `validate_config()` returns a warning.
- `environment == "production"` and `otlp_insecure=True` → warning: "Using insecure OTLP in production".
- `environment` not in `{development, staging, production}` → info: "Non-standard environment".

---

## Tracing

| Field | Env Var | Type | Default | Description |
|---|---|---|---|---|
| `tracing_enabled` | `OBSKIT_TRACING_ENABLED` | `bool` | `True` | Master switch for OpenTelemetry tracing.  When `False`, `setup_tracing()` installs a no-op `TracerProvider`. |
| `otlp_endpoint` | `OBSKIT_OTLP_ENDPOINT` | `str` | `"http://localhost:4317"` | OTLP gRPC collector endpoint (e.g., Grafana Tempo, Jaeger, OpenTelemetry Collector).  Include port; do not include a path. |
| `otlp_insecure` | `OBSKIT_OTLP_INSECURE` | `bool` | `True` | Skip TLS verification.  Set to `False` for production with a trusted CA or mTLS. |
| `trace_sample_rate` | `OBSKIT_TRACE_SAMPLE_RATE` | `float` | `1.0` | Fraction of traces to sample.  Range: 0.0–1.0.  Example: `0.1` = sample 10% of requests. For `>1 000 req/s`, set ≤ `0.01`. |
| `trace_export_queue_size` | `OBSKIT_TRACE_EXPORT_QUEUE_SIZE` | `int` | `2048` | Maximum spans buffered in the `BatchSpanProcessor` queue.  Increase if you see "Queue is full, dropping spans" warnings. |
| `trace_export_batch_size` | `OBSKIT_TRACE_EXPORT_BATCH_SIZE` | `int` | `512` | Number of spans per OTLP export batch.  Larger batches are more efficient but increase memory. |
| `trace_export_timeout` | `OBSKIT_TRACE_EXPORT_TIMEOUT` | `float` | `30.0` | Seconds before an OTLP export attempt times out.  Reduce for faster span queue drain during shutdown. |

---

## Metrics

| Field | Env Var | Type | Default | Description |
|---|---|---|---|---|
| `metrics_enabled` | `OBSKIT_METRICS_ENABLED` | `bool` | `True` | Master switch for Prometheus metrics.  When `False`, all `REDMetrics`, `GoldenSignals`, and `USEMetrics` calls are no-ops. |
| `metrics_port` | `OBSKIT_METRICS_PORT` | `int` | `9090` | Port for the Prometheus `/metrics` HTTP server.  Only used when `start_health_server()` is called explicitly. |
| `metrics_path` | `OBSKIT_METRICS_PATH` | `str` | `"/metrics"` | URL path for the metrics endpoint. |
| `metrics_method` | `OBSKIT_METRICS_METHOD` | `str` | `"red"` | Default metrics methodology: `red`, `golden`, `use`, or `all`. |
| `use_histogram` | `OBSKIT_USE_HISTOGRAM` | `bool` | `True` | Use `Histogram` for latency observations.  Histograms are aggregatable across instances; recommended for multi-pod deployments. |
| `use_summary` | `OBSKIT_USE_SUMMARY` | `bool` | `False` | Use `Summary` for percentile observations.  Summaries cannot be aggregated across instances.  Not recommended for Kubernetes. |
| `metrics_sample_rate` | `OBSKIT_METRICS_SAMPLE_RATE` | `float` | `1.0` | Fraction of operations recorded as metrics.  Example: `0.1` = sample 10% of operations.  Note: Prometheus counters are approximate at sample rates < 1.0. |
| `metrics_auth_enabled` | `OBSKIT_METRICS_AUTH_ENABLED` | `bool` | `False` | Require a bearer token on `/metrics` requests. |
| `metrics_auth_token` | `OBSKIT_METRICS_AUTH_TOKEN` | `str` | `""` | Bearer token value.  Required when `metrics_auth_enabled=True`.  Do not commit this value; use an environment variable. |
| `metrics_rate_limit_enabled` | `OBSKIT_METRICS_RATE_LIMIT_ENABLED` | `bool` | `False` | Enable rate limiting on the `/metrics` endpoint to protect against aggressive scrapers. |
| `metrics_rate_limit_requests` | `OBSKIT_METRICS_RATE_LIMIT_REQUESTS` | `int` | `60` | Maximum scrape requests per minute when rate limiting is enabled. |
| `enable_self_metrics` | `OBSKIT_ENABLE_SELF_METRICS` | `bool` | `False` | Expose obskit-internal performance metrics (queue depth, error rates).  Useful for debugging obskit itself. |
| `async_metric_queue_size` | `OBSKIT_ASYNC_METRIC_QUEUE_SIZE` | `int` | `10000` | Capacity of the async metric recording queue.  Increase if `AsyncMetricRecorder` drops records. |

---

## Logging

| Field | Env Var | Type | Default | Description |
|---|---|---|---|---|
| `log_level` | `OBSKIT_LOG_LEVEL` | `str` | `"INFO"` | Minimum log level.  Values: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. |
| `log_format` | `OBSKIT_LOG_FORMAT` | `str` | `"json"` | Output format.  `"json"` for production (machine-readable); `"console"` for local development (coloured, human-readable). |
| `log_include_timestamp` | `OBSKIT_LOG_INCLUDE_TIMESTAMP` | `bool` | `True` | Include ISO-8601 timestamp in log records.  Disable when your log aggregator adds its own timestamp to avoid duplication. |
| `logging_backend` | `OBSKIT_LOGGING_BACKEND` | `str` | `"auto"` | Logging backend: `"structlog"` (default), `"loguru"`, or `"auto"` (detects installed backend). |
| `log_sample_rate` | `OBSKIT_LOG_SAMPLE_RATE` | `float` | `1.0` | Fraction of log records to emit.  Example: `0.01` = 1% sampling for high-throughput paths.  Always emits `ERROR` and `CRITICAL` regardless. |

---

## Health Checks

| Field | Env Var | Type | Default | Description |
|---|---|---|---|---|
| `health_check_timeout` | `OBSKIT_HEALTH_CHECK_TIMEOUT` | `float` | `5.0` | Seconds before an individual health check is considered failed.  Keep below your readiness probe `periodSeconds`. |

---

## Circuit Breaker

| Field | Env Var | Type | Default | Description |
|---|---|---|---|---|
| `circuit_breaker_failure_threshold` | `OBSKIT_CIRCUIT_BREAKER_FAILURE_THRESHOLD` | `int` | `5` | Number of consecutive failures before the circuit opens.  Lower = faster failure detection but more false positives.  Higher = slower detection but fewer false positives. |
| `circuit_breaker_recovery_timeout` | `OBSKIT_CIRCUIT_BREAKER_RECOVERY_TIMEOUT` | `float` | `30.0` | Seconds the circuit stays open before entering HALF_OPEN.  Too short = unnecessary load on recovering service.  Too long = extended outage. |
| `circuit_breaker_half_open_requests` | `OBSKIT_CIRCUIT_BREAKER_HALF_OPEN_REQUESTS` | `int` | `3` | Number of test requests sent in HALF_OPEN state.  If all succeed, the circuit closes. |

---

## Retry

| Field | Env Var | Type | Default | Description |
|---|---|---|---|---|
| `retry_max_attempts` | `OBSKIT_RETRY_MAX_ATTEMPTS` | `int` | `3` | Total call attempts (including the first try).  Setting to `1` disables retries. |
| `retry_base_delay` | `OBSKIT_RETRY_BASE_DELAY` | `float` | `1.0` | Initial delay in seconds between retries.  Actual delay = `base_delay × exponential_base ^ attempt`. |
| `retry_max_delay` | `OBSKIT_RETRY_MAX_DELAY` | `float` | `60.0` | Maximum delay cap in seconds.  Prevents exponential backoff from growing unbounded. |
| `retry_exponential_base` | `OBSKIT_RETRY_EXPONENTIAL_BASE` | `float` | `2.0` | Exponential growth factor.  `2.0` = delays double each attempt: 1s, 2s, 4s, 8s… |

**Example retry schedule** (`base_delay=1.0`, `exponential_base=2.0`, `max_delay=60.0`):

| Attempt | Delay before attempt |
|---|---|
| 1 | 0 (first try) |
| 2 | 1.0 s |
| 3 | 2.0 s |
| 4 | 4.0 s (if `max_attempts≥4`) |
| 5 | 8.0 s |

---

## Rate Limiting

| Field | Env Var | Type | Default | Description |
|---|---|---|---|---|
| `rate_limit_requests` | `OBSKIT_RATE_LIMIT_REQUESTS` | `int` | `100` | Maximum requests per window.  Example: 100 requests per 60 seconds ≈ 1.67 req/s. |
| `rate_limit_window_seconds` | `OBSKIT_RATE_LIMIT_WINDOW_SECONDS` | `float` | `60.0` | Sliding window duration in seconds. |

---

## Example: Minimal Production .env

```bash
# .env (gitignored — do not commit)
OBSKIT_SERVICE_NAME=order-service
OBSKIT_ENVIRONMENT=production
OBSKIT_VERSION=2.1.0

OBSKIT_LOG_LEVEL=INFO
OBSKIT_LOG_FORMAT=json

OBSKIT_TRACING_ENABLED=true
OBSKIT_OTLP_ENDPOINT=http://otel-collector:4317
OBSKIT_OTLP_INSECURE=false
OBSKIT_TRACE_SAMPLE_RATE=0.05

OBSKIT_METRICS_ENABLED=true
OBSKIT_METRICS_AUTH_ENABLED=true
OBSKIT_METRICS_AUTH_TOKEN=your-secret-token-here

OBSKIT_CIRCUIT_BREAKER_FAILURE_THRESHOLD=5
OBSKIT_CIRCUIT_BREAKER_RECOVERY_TIMEOUT=30.0
OBSKIT_RETRY_MAX_ATTEMPTS=3
```

---

## Validation

```python
from obskit.config import validate_config

is_valid, errors = validate_config()
if not is_valid:
    for error in errors:
        print(f"CONFIG ERROR: {error}")
    sys.exit(1)
```

Call `validate_config()` at startup to catch configuration errors before serving
traffic.  Returns `(True, [])` when all required settings are present and consistent.
