# Logging

obskit provides structured, JSON-first logging built on [structlog](https://www.structlog.org/). Every log line is a Python dict that becomes a JSON object — fully queryable in Loki, Elasticsearch, or any log aggregator. Trace IDs are injected automatically when an OpenTelemetry span is active.

---

## Quick Start

```python
from obskit.logging import get_logger

log = get_logger(__name__)

log.info("user.registered", user_id="u_abc123", plan="pro")
log.warning("payment.retry", attempt=2, max_attempts=3, error="timeout")
log.error("payment.failed", user_id="u_abc123", amount=9900, error="card_declined")
```

JSON output (production):
```json
{"timestamp": "2026-02-28T14:32:07.841Z", "level": "info",    "event": "user.registered",  "user_id": "u_abc123", "plan": "pro",    "service": "payment-service", "trace_id": "4bf92f35...", "span_id": "00f067aa..."}
{"timestamp": "2026-02-28T14:32:08.102Z", "level": "warning", "event": "payment.retry",     "attempt": 2, "max_attempts": 3, "error": "timeout",                               "trace_id": "4bf92f35..."}
{"timestamp": "2026-02-28T14:32:09.214Z", "level": "error",   "event": "payment.failed",    "user_id": "u_abc123", "amount": 9900, "error": "card_declined",                   "trace_id": "4bf92f35..."}
```

---

## `get_logger()` API

```python
from obskit.logging import get_logger

log = get_logger(
    name=__name__,          # Logger name (appears in log lines as 'logger')
    service="my-service",   # Optional — defaults to OTEL_SERVICE_NAME env var
)
```

The returned logger is a structlog `BoundLogger` with obskit's processor pipeline pre-configured. It exposes the standard log-level methods:

| Method | Severity | When to use |
|---|---|---|
| `log.debug(event, **kw)` | 10 | Diagnostic detail for developers; never enable in production by default |
| `log.info(event, **kw)` | 20 | Significant business events — user actions, state transitions |
| `log.warning(event, **kw)` | 30 | Recoverable problems — retries, degraded mode, deprecated usage |
| `log.error(event, **kw)` | 40 | Errors requiring attention — request failed, data inconsistency |
| `log.critical(event, **kw)` | 50 | System-level failures — process should restart or page on-call |

---

## Structlog Processor Pipeline

obskit configures structlog with the following processor chain. Understanding the pipeline helps when you need to customise it.

```
get_logger(event, **kw)
         │
         ▼
┌─────────────────────────────────┐
│ 1. add_log_level               │  Adds "level": "info"
│ 2. add_timestamp               │  Adds "timestamp": ISO8601
│ 3. add_service_context         │  Adds "service", "logger"
│ 4. inject_trace_context        │  Adds "trace_id", "span_id" (if OTel active)
│ 5. pii_redaction_processor     │  Redacts configured PII fields
│ 6. sampling_processor          │  Drops debug/info under load (if enabled)
│ 7. JSONRenderer / ConsoleRenderer │ Serialises to JSON or coloured console
└─────────────────────────────────┘
         │
         ▼
  stdout (JSON) → Loki / log aggregator
```

### Custom processors

You can inject custom processors into the pipeline:

```python
from obskit.logging import get_logger, configure_logging
import structlog

def add_request_id(logger, method, event_dict):
    """Add the current request ID from a context variable."""
    from my_app.context import request_id_var
    event_dict["request_id"] = request_id_var.get(None)
    return event_dict

configure_logging(
    extra_processors=[add_request_id],
    position="before_render",   # Insert before the JSON renderer
)

log = get_logger(__name__)
```

---

## Automatic Trace-Log Correlation

When an OpenTelemetry span is active (created by `trace_span()`, auto-instrumentation, or any OTel-compatible framework), obskit's `inject_trace_context` processor automatically adds `trace_id` and `span_id` to every log line.

```python
from obskit.tracing import trace_span
from obskit.logging import get_logger

log = get_logger(__name__)

with trace_span("process_order") as span:
    log.info("order.processing_started", order_id="ord_123")
    # Output includes: "trace_id": "4bf92f35...", "span_id": "00f067aa..."

    result = process(order)
    log.info("order.processing_complete", order_id="ord_123", item_count=3)
    # Same trace_id, different span_id (if nested spans exist)
```

This is the foundation of **trace-log correlation** in Grafana. Loki can parse `trace_id` from log lines and surface a direct link to the corresponding Grafana Tempo trace.

### Grafana Loki derived field

Configure Loki to extract `trace_id` from log lines:

```yaml
# grafana/provisioning/datasources/loki.yml
jsonData:
  derivedFields:
    - name: TraceID
      matcherRegex: '"trace_id":"([a-f0-9]+)"'
      url: "http://grafana:3000/explore?datasource=tempo&query=${__value.raw}"
      datasourceUid: tempo
```

---

## Log Levels and When to Use Each

### `debug`

Reserve debug for information that is only useful during development or deep troubleshooting. **Never enable debug in production without rate-limiting** — it can generate millions of log lines per second.

```python
log.debug("cache.lookup", key="user:u_abc123", ttl_remaining=287)
log.debug("db.query_plan", sql="SELECT ...", plan="Seq Scan on users")
```

### `info`

Use info for significant, **expected** events that represent meaningful state transitions. Think "what would a business analyst want to know happened?"

```python
log.info("user.registered", user_id="u_abc123", plan="pro", referral_code="SAVE20")
log.info("payment.succeeded", payment_id="pay_abc", amount=9900, currency="USD")
log.info("job.completed", job_id="job_xyz", records_processed=10482, duration_s=47.2)
```

### `warning`

Use warning for recoverable problems or situations approaching a limit. The system handled it, but a human should know.

```python
log.warning("payment.retry", attempt=2, max_attempts=3, error="gateway_timeout")
log.warning("cache.miss_rate_high", miss_rate=0.87, threshold=0.5)
log.warning("rate_limit.approaching", usage=0.92, endpoint="/api/ingest")
```

### `error`

Use error when a request or operation **failed** and the system could not recover automatically.

```python
log.error("payment.failed",
          payment_id="pay_abc",
          error="insufficient_funds",
          user_id="u_abc123",
          exc_info=True)  # Attaches the current exception stacktrace
```

### `critical`

Use critical only for system-level failures that require immediate human intervention — typically caught in a top-level exception handler.

```python
try:
    start_application()
except Exception:
    log.critical("startup.failed", exc_info=True)
    sys.exit(1)
```

---

## Context Binding

`log.bind()` returns a new logger with permanent context attached. All subsequent log calls on the bound logger include that context.

```python
from obskit.logging import get_logger

log = get_logger(__name__)

# Bind per-request context (e.g., in middleware)
request_log = log.bind(
    request_id="req_abc123",
    user_id="u_xyz789",
    tenant_id="tenant_abc",
)

# All calls on request_log include the bound fields:
request_log.info("request.received", method="POST", path="/checkout")
request_log.info("request.completed", status_code=200, duration_ms=142)
```

### Binding in FastAPI middleware

```python
from fastapi import Request
from obskit.logging import get_logger
import structlog

log = get_logger(__name__)

async def logging_middleware(request: Request, call_next):
    bound_log = log.bind(
        request_id=request.headers.get("X-Request-ID", "-"),
        method=request.method,
        path=request.url.path,
        client_ip=request.client.host,
    )
    structlog.contextvars.bind_contextvars(
        request_id=request.headers.get("X-Request-ID", "-"),
    )
    response = await call_next(request)
    bound_log.info("request.completed", status_code=response.status_code)
    structlog.contextvars.clear_contextvars()
    return response
```

### `structlog.contextvars` for async context

In async code, use `structlog.contextvars` to bind context that flows through the entire request — including into third-party libraries that call `get_logger()` internally:

```python
import structlog

# At request start:
structlog.contextvars.bind_contextvars(tenant_id="tenant_abc", request_id="req_123")

# Anywhere in the call chain:
log = structlog.get_logger()
log.info("some.event")
# Output includes: "tenant_id": "tenant_abc", "request_id": "req_123"

# At request end:
structlog.contextvars.clear_contextvars()
```

---

## Structured Field Naming Conventions

Consistent field names make logs searchable and allow shared dashboards across services.

| Field | Type | Example | Notes |
|---|---|---|---|
| `event` | `str` | `"payment.charged"` | `noun.verb` format, dot-separated namespacing |
| `user_id` | `str` | `"u_abc123"` | Always use internal ID, never email/name |
| `tenant_id` | `str` | `"tenant_abc"` | Multi-tenant context |
| `request_id` | `str` | `"req_xyz"` | Per-request correlation ID |
| `duration_ms` | `float` | `142.7` | Duration in milliseconds |
| `error` | `str` | `"gateway_timeout"` | Machine-readable error code |
| `error_message` | `str` | `"Connection timed out"` | Human-readable message |
| `exc_info` | `bool` | `True` | Attach current exception stacktrace |
| `status_code` | `int` | `200` | HTTP/gRPC status code |
| `amount` | `int` | `9900` | Monetary amounts in smallest unit (cents) |
| `currency` | `str` | `"USD"` | ISO 4217 currency code |

!!! tip "Event naming: noun.verb"
    Use `noun.verb` format for events: `payment.charged`, `user.created`, `order.shipped`. This makes events searchable and self-documenting. Avoid vague events like `"success"` or `"error"` — use `"payment.charge_succeeded"` and `"payment.charge_failed"`.

---

## Async Ring Buffer

Under high load, synchronous I/O for logging (writing to stdout, sending to a log aggregator) can become a bottleneck. obskit provides an **async ring buffer** that decouples log record creation from I/O.

```python
from obskit.logging import configure_logging

configure_logging(
    async_buffer=True,
    buffer_size=10_000,      # Maximum queued log records before dropping
    drop_on_overflow=True,   # Drop oldest records; never block the application
)
```

The ring buffer runs in a background thread. Your application threads enqueue log records without blocking, and the background thread drains the queue and writes to the configured sink.

!!! warning "Ring buffer and process shutdown"
    The ring buffer may lose log records on abrupt process termination (SIGKILL). obskit registers a `SIGTERM` handler that flushes the buffer before shutdown. Always give your containers a graceful shutdown window (`terminationGracePeriodSeconds: 30`).

---

## OTLP Log Export (Grafana Loki)

In addition to stdout, obskit can ship logs directly to an OTLP-compatible log backend:

```python
from obskit.logging import configure_logging

configure_logging(
    otlp_endpoint="http://otel-collector:4317",
    resource_attributes={
        "service.name": "payment-service",
        "service.version": "2.0.0",
        "deployment.environment": "production",
    },
)
```

The OTLP log exporter sends structured log records to the OTel Collector, which forwards them to Loki (or any OTLP-compatible log backend).

### OTel Collector → Loki pipeline

```yaml
# otel-collector-config.yml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317

exporters:
  loki:
    endpoint: http://loki:3100/loki/api/v1/push
    labels:
      attributes:
        service.name: "service_name"
        deployment.environment: "environment"

service:
  pipelines:
    logs:
      receivers: [otlp]
      exporters: [loki]
```

---

## Dynamic Log Level Changes

Changing the log level at runtime without restarting the process:

```python
from obskit.logging.dynamic import set_log_level

# Temporarily enable debug logging for a specific logger
set_log_level("obskit.metrics", level="DEBUG")

# Or globally:
set_log_level(level="DEBUG")

# Reset to configured default:
set_log_level(level=None)
```

This is useful during incident investigation — you can lower the log level temporarily to gather more context without redeploying.

### Via HTTP endpoint (optional)

```python
from fastapi import FastAPI
from obskit.logging.dynamic import DynamicLogLevelRouter

app = FastAPI()
app.include_router(DynamicLogLevelRouter(), prefix="/admin")

# PUT /admin/log-level  {"level": "DEBUG", "logger": "obskit.metrics"}
# GET /admin/log-level  → {"level": "INFO", "logger": "root"}
```

!!! danger "Protect the log level endpoint"
    The dynamic log level endpoint must be protected by authentication. Debug-level logging can expose sensitive data and degrade performance. Restrict access to internal networks or admin users only.

---

## Sampling Under High Load

When request volume is very high, logging every event may be prohibitively expensive. obskit supports **log sampling** that probabilistically drops low-severity log lines while always preserving errors.

```python
from obskit.logging import configure_logging

configure_logging(
    sampling={
        "debug": 0.01,     # Log 1% of debug messages
        "info": 0.1,       # Log 10% of info messages
        "warning": 1.0,    # Log all warnings
        "error": 1.0,      # Always log errors
        "critical": 1.0,   # Always log critical
    }
)
```

Sampling is applied **per log level** and is deterministic within a trace — if the first log line of a trace is sampled in, all subsequent log lines for that trace are also sampled in (trace-consistent sampling).

---

## Sensitive Field Redaction

obskit ships a built-in structlog processor (`obskit.logging.redaction`) that automatically redacts sensitive fields before any log line is written or exported.

### Zero-config (recommended)

```python
import structlog
from obskit.logging.redaction import redact_sensitive_fields

structlog.configure(
    processors=[
        redact_sensitive_fields,          # covers the default 11-field set
        structlog.processors.JSONRenderer(),
    ]
)
```

The default set covers: `password`, `passwd`, `secret`, `token`, `api_key`, `apikey`, `auth`, `credential`, `private_key`, `access_key`, `bearer`.
Matching is **case-insensitive substring** — `Authorization`, `access_token`, and `bearer_token` are all caught.

### Custom fields

```python
from obskit.logging.redaction import make_redaction_processor, DEFAULT_SENSITIVE_FIELDS

processor = make_redaction_processor(
    fields=DEFAULT_SENSITIVE_FIELDS | {"ssn", "credit_card", "dob"},
    placeholder="[REDACTED]",
)
```

### configure_logging PII fields

For the high-level API, pass `pii_fields` directly:

```python
from obskit.logging import configure_logging

configure_logging(
    pii_fields=["email", "phone", "credit_card", "ssn", "password", "token"],
    pii_patterns=[
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",  # Email
        r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b",               # Credit card
    ],
    pii_replacement="[REDACTED]",
)
```

See the [PII guide](pii.md) for full compliance and audit-logging details.

---

## JSON vs Console Output

=== "Production (JSON)"
    ```python
    from obskit.logging import configure_logging
    configure_logging(renderer="json")
    ```
    Output:
    ```json
    {"timestamp": "2026-02-28T14:32:07.841Z", "level": "info", "event": "payment.charged", "amount": 9900}
    ```

=== "Development (coloured console)"
    ```python
    from obskit.logging import configure_logging
    configure_logging(renderer="console")
    ```
    Output:
    ```
    2026-02-28 14:32:07 [info     ] payment.charged    amount=9900 currency=USD
    ```

=== "Auto-detect"
    ```python
    from obskit.logging import configure_logging
    import sys
    configure_logging(
        renderer="console" if sys.stderr.isatty() else "json"
    )
    ```
    Uses coloured console when running in a terminal, JSON in production (where stdout is not a TTY).

The auto-detect pattern is the recommended default — it works correctly in both development and Kubernetes environments without environment-specific configuration.

---

## Complete Configuration Reference

```python
from obskit.logging import configure_logging

configure_logging(
    # Output format
    renderer="json",                    # "json" | "console"
    timestamp_format="iso",             # "iso" | "unix" | "unix_ms"

    # Log level
    level="INFO",                       # DEBUG | INFO | WARNING | ERROR | CRITICAL

    # Trace correlation
    inject_trace_context=True,          # Add trace_id/span_id from OTel

    # Service metadata (added to every log line)
    service_name="payment-service",     # Defaults to OTEL_SERVICE_NAME
    service_version="2.0.0",

    # Async ring buffer
    async_buffer=False,
    buffer_size=10_000,
    drop_on_overflow=True,

    # OTLP export
    otlp_endpoint=None,                 # e.g., "http://otel-collector:4317"
    resource_attributes={},

    # Sampling
    sampling=None,                      # Dict of level → rate

    # PII
    pii_fields=[],
    pii_patterns=[],
    pii_replacement="[REDACTED]",

    # Custom processors
    extra_processors=[],
)
```
