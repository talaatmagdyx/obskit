# Logging

Structured, production-ready logging for obskit services. Built on [structlog](https://www.structlog.org/) with automatic trace-log correlation, async ring-buffer for high-throughput paths, adaptive sampling, and OTLP export.

## Installation

```bash
pip install obskit
```

### Optional extras

```bash
# structlog backend (default, always included)
pip install obskit

# OTLP log export
pip install "obskit[otlp]"
```

---

## get_logger

The primary entry point. Returns a fully configured `structlog.BoundLogger` with automatic correlation ID injection, service metadata, trace context, and the log format set by `ObskitSettings`.

```python
from obskit.logging import get_logger

logger = get_logger(__name__)
```

### Basic usage

```python
from obskit.logging import get_logger

logger = get_logger(__name__)

# Structured key-value logging
logger.info("user_logged_in", user_id="123", ip="10.0.0.1")

# Multiple fields
logger.info(
    "order_created",
    order_id="ord-456",
    user_id="123",
    total=99.99,
    items=["widget", "gadget"],
)

# Warning and error levels
logger.warning("rate_limit_approaching", current=95, limit=100)
logger.error("payment_failed", order_id="456", reason="card_declined")
logger.critical("database_connection_lost", host="db.example.com")

# Exception with full stack trace
try:
    result = process_data(data)
except Exception:
    logger.error(
        "processing_failed",
        component="DataProcessor",
        exc_info=True,   # includes full traceback in output
    )
```

### Bound context

Use `.bind()` to create a child logger that carries fixed fields on every subsequent call — ideal for request-scoped loggers.

```python
logger = get_logger(__name__)

# Create a request-scoped logger
request_logger = logger.bind(
    request_id="req-abc",
    user_id="user-123",
    endpoint="/orders",
)

request_logger.info("processing_started")
request_logger.debug("cache_miss", key="user:123")
request_logger.info("processing_complete", duration_ms=45.2)
```

### JSON output format

With `log_format="json"` (the default), every log line is a single JSON object:

```json
{
  "event": "order_created",
  "order_id": "ord-456",
  "user_id": "123",
  "total": 99.99,
  "service": "order-service",
  "environment": "production",
  "version": "2.0.0",
  "level": "info",
  "correlation_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "span_id": "00f067aa0ba902b7",
  "timestamp": "2026-02-28T10:00:00.000000Z"
}
```

### Logging helpers

```python
from obskit.logging import log_operation, log_performance, log_error

# Log an operation result with timing
log_operation(
    operation="create_order",
    component="OrderService",
    status="success",
    duration_ms=45.2,
    order_id="ord-123",
)

# Log performance with threshold warning
log_performance(
    operation="search",
    component="SearchService",
    duration_ms=350.0,
    threshold_ms=200.0,   # triggers "slow_operation" warning if exceeded
)

# Log an exception with full context
try:
    process_payment(data)
except Exception as e:
    log_error(
        error=e,
        component="PaymentService",
        operation="process_payment",
        context={"payment_id": "pay-123", "amount": 99.99},
    )
```

---

## Trace-log correlation

When `obskit[otlp]` is installed and a span is active, every log record automatically gains `trace_id` and `span_id` fields. This enables one-click jumps from a log line in Grafana/Loki to the matching trace in Tempo.

```python
from obskit.logging.trace_correlation import (
    is_trace_correlation_available,
    get_trace_context,
    add_trace_context,   # structlog processor
)

# Check availability
if is_trace_correlation_available():
    print("OTel tracing is installed — trace links are active")

# Get the current span's IDs (returns {} when no span is active)
ctx = get_trace_context()
# {"trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
#  "span_id":  "00f067aa0ba902b7"}
```

The `add_trace_context` processor is injected into the structlog pipeline automatically when `configure_logging()` is called. To use it in a custom pipeline:

```python
import structlog
from obskit.logging.trace_correlation import add_trace_context

structlog.configure(
    processors=[
        add_trace_context,          # injects trace_id + span_id
        structlog.processors.JSONRenderer(),
    ]
)
```

!!! info "Zero-dependency fallback"
    `add_trace_context` is completely safe to include even when `opentelemetry-api` is not installed. It becomes a no-op and never adds fields to the event dict.

---

## Async ring buffer

`AsyncLogRing` is a non-blocking, best-effort log buffer for high-throughput paths. It enqueues log records in ~50 ns on the hot path and drains them on a background daemon thread.

```python
from obskit.logging.async_ring import AsyncLogRing
import structlog

ring = AsyncLogRing(
    maxsize=100_000,    # drop records when full (best-effort)
    drain_batch=500,    # records emitted per drain iteration
)

# Define the emit function (called on the background thread)
log = structlog.get_logger()
def emit(record: dict) -> None:
    log.info(record.pop("event", "log"), **record)

ring.start(emit_fn=emit)

# Hot path — non-blocking (~50 ns)
ring.enqueue({"event": "request_done", "op": "search", "duration_ms": 12})

# Monitoring
print(ring.qsize)    # approximate items in buffer
print(ring.dropped)  # cumulative dropped count

# Graceful shutdown (flushes remaining records)
ring.stop(timeout_s=5.0)
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `maxsize` | `int` | `100_000` | Buffer capacity; new records are silently dropped when full |
| `drain_batch` | `int` | `500` | Max records emitted per drain loop iteration |

---

## OTLP log export

Export structured logs to an OpenTelemetry Protocol collector alongside traces and metrics.

```python
from obskit.logging.otlp import (
    configure_otlp_logging,
    get_otlp_handler,
    shutdown_otlp_logging,
    OTLPLogHandler,
    create_otlp_log_processor,
    OTEL_LOGGING_AVAILABLE,
    OTLP_EXPORTER_AVAILABLE,
)
```

### Setup with configure_otlp_logging

```python
from obskit.logging.otlp import configure_otlp_logging

success = configure_otlp_logging(
    endpoint="http://otel-collector:4317",
    service_name="order-service",    # defaults to ObskitSettings.service_name
    insecure=True,                   # defaults to ObskitSettings.otlp_insecure
    batch_size=512,
    export_timeout_ms=30_000,
)

if not success:
    print("OTLP logging unavailable — missing opentelemetry-sdk or exporter")
```

### Attach to Python's standard logging

```python
import logging
from obskit.logging.otlp import configure_otlp_logging, get_otlp_handler

configure_otlp_logging(endpoint="http://otel-collector:4317")

handler = get_otlp_handler()
if handler:
    logging.getLogger().addHandler(handler)
    logging.getLogger().setLevel(logging.INFO)
```

### OTLPLogHandler (low-level)

```python
import logging
from obskit.logging.otlp import OTLPLogHandler

handler = OTLPLogHandler(
    endpoint="http://otel-collector:4317",
    service_name="my-service",
    insecure=True,
    batch_size=100,
    flush_interval=5.0,    # seconds
)
handler.setLevel(logging.INFO)

logger = logging.getLogger("my_app")
logger.addHandler(handler)
logger.info("Application started")
# Logs within active OTel spans automatically gain trace_id + span_id
```

### structlog OTLP processor

```python
import structlog
from obskit.logging.otlp import create_otlp_log_processor

structlog.configure(
    processors=[
        create_otlp_log_processor(),    # adds trace_id, span_id, severity_number
        structlog.processors.JSONRenderer(),
    ]
)
```

---

## Sampling

### SampledLogger

Reduces log volume while keeping full visibility for important events. Errors and `CRITICAL` messages are never sampled.

```python
from obskit.logging.sampling import SampledLogger, SamplingConfig, SamplingRule

config = SamplingConfig(
    debug_rate=0.01,       # 1% of debug logs
    info_rate=0.1,         # 10% of info logs
    warning_rate=1.0,      # all warnings
    error_rate=1.0,        # all errors
    slow_threshold_seconds=1.0,    # always log slow operations
    dedupe_window_seconds=60.0,    # suppress duplicate log lines
    always_log_first_n=3,          # always log first 3 occurrences
    always_log_events={"startup", "shutdown"},
    never_log_events={"health_probe"},
)

logger = SampledLogger("high_volume_service", config=config)
logger.info("routine_event", data="value")    # sampled at 10%
logger.error("something_failed", err="...")   # always logged
logger.info("important_event", _important=True)  # bypasses sampling

# Inspect sampling statistics
stats = logger.get_stats()
# {
#   "logger_name": "high_volume_service",
#   "total_logs": 1000,
#   "sampled": 105,
#   "dropped": 895,
#   "effective_rate": 0.105,
#   "by_level": {"sampled": {...}, "dropped": {...}},
# }
```

### AdaptiveSampledLogger

Automatically adjusts sampling rates based on observed log throughput to hit a target logs-per-second budget.

```python
from obskit.logging.sampling import AdaptiveSampledLogger

logger = AdaptiveSampledLogger(
    name="adaptive_service",
    target_logs_per_second=100,    # budget
    min_sample_rate=0.001,
    max_sample_rate=1.0,
    adjustment_interval=10.0,      # recalculate rate every 10 s
)

# Rate is automatically tuned; errors are never dropped
logger.info("high_volume_event")
logger.error("alert", severity="critical")   # always logged
```

### Global sampling statistics

```python
from obskit.logging.sampling import get_sampling_stats

stats = get_sampling_stats()
# {"high_volume_service": {"sampled": 105, "dropped": 895}, ...}
```

---

## Sensitive field redaction

`obskit.logging.redaction` provides a structlog processor that replaces the values of sensitive log fields with a placeholder before they are rendered or shipped to a log aggregator. It performs **case-insensitive substring matching** on field names — a field named `access_token` is redacted even if only `token` is listed.

### Zero-config usage

```python
import structlog
from obskit.logging.redaction import redact_sensitive_fields

structlog.configure(
    processors=[
        redact_sensitive_fields,               # default 11-field set
        structlog.processors.JSONRenderer(),
    ]
)
```

The singleton covers the default sensitive fields: `password`, `passwd`, `secret`, `token`, `api_key`, `apikey`, `auth`, `credential`, `private_key`, `access_key`, `bearer`.

### Custom fields and placeholder

```python
from obskit.logging.redaction import make_redaction_processor

processor = make_redaction_processor(
    fields={"password", "token", "ssn", "credit_card"},
    placeholder="***",
)

# Verify behaviour:
result = processor(None, "info", {"event": "login", "password": "s3cr3t", "user": "alice"})
# {"event": "login", "password": "***", "user": "alice"}
```

### Nested dict support

The processor recurses into nested dicts (up to 10 levels deep) and handles circular references safely:

```python
result = processor(None, "info", {
    "event": "api_call",
    "headers": {
        "Authorization": "Bearer tok123",   # "auth" substring → redacted
        "Content-Type": "application/json",
    },
})
# headers.Authorization → "***"
# headers.Content-Type  → preserved
```

### DEFAULT_SENSITIVE_FIELDS

```python
from obskit.logging.redaction import DEFAULT_SENSITIVE_FIELDS

# Extend the defaults
my_fields = DEFAULT_SENSITIVE_FIELDS | {"ssn", "credit_card"}
processor = make_redaction_processor(fields=my_fields)
```

---

## JSON processor pipeline

Full structlog pipeline that mirrors the default obskit configuration:

```python
import structlog
from obskit.logging.logger import (
    add_log_level,
    add_service_info,
    add_correlation_id,
)
from obskit.logging.trace_correlation import add_trace_context

structlog.configure(
    processors=[
        add_log_level,              # adds "level": "info"
        add_service_info,           # adds "service", "environment", "version"
        add_correlation_id,         # adds "correlation_id" from context
        add_trace_context,          # adds "trace_id", "span_id" if OTel span active
        structlog.processors.format_exc_info,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),   # → single JSON line per record
    ],
    wrapper_class=structlog.make_filtering_bound_logger(20),  # INFO
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)
```
