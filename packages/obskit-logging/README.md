<div align="center">

# 📝 obskit-logging

**Structured logging with automatic trace correlation, adaptive sampling, and zero-config OTLP export**

---

[![PyPI](https://img.shields.io/pypi/v/obskit-logging.svg?color=blue)](https://pypi.org/project/obskit-logging/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![obskit](https://img.shields.io/badge/part%20of-obskit-blueviolet.svg)](https://github.com/talaatmagdyx/obskit)

</div>

## What it does

- **Structured JSON by default** — every `logger.info()` call emits a machine-readable JSON record in production and a developer-friendly coloured output in development, with no format-switch code in your application.
- **Automatic trace and correlation injection** — when `obskit-tracing` (or any `opentelemetry-api`) is installed, `trace_id` and `span_id` are appended to every log record with zero extra code.
- **Adaptive sampling** — `AdaptiveSampledLogger` automatically throttles high-volume INFO/DEBUG logs under load while always preserving errors, slow operations, and the first few occurrences of any unique event.

---

## Installation

```bash
# Standard install (structlog backend)
pip install obskit-logging

# With loguru backend support
pip install "obskit-logging[loguru]"
```

---

## Quick Start

```python
from obskit.config import configure
from obskit.logging import get_logger

# Configure once at startup (reads OBSKIT_* env vars automatically if skipped)
configure(
    service_name="order-service",
    environment="production",
    log_level="INFO",
    log_format="json",   # "console" for local development
)

logger = get_logger(__name__)

logger.info("order_placed", order_id="ord-8821", user_id="usr-412", total=149.99)
logger.warning("payment_retry", order_id="ord-8821", attempt=2)
logger.error("payment_failed", order_id="ord-8821", reason="card_declined")
```

**Production output (JSON):**

```json
{"level": "info", "event": "order_placed", "service": "order-service", "environment": "production", "version": "1.4.2", "order_id": "ord-8821", "user_id": "usr-412", "total": 149.99, "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736", "span_id": "00f067aa0ba902b7", "correlation_id": "req-abc-def-123", "timestamp": "2026-03-01T10:00:00.123456Z"}
```

**Development output (console):**

```
2026-03-01 10:00:00 [info     ] order_placed    order_id=ord-8821 user_id=usr-412 total=149.99
```

---

## Features

### 1. get_logger() — structlog-based, zero config required

`get_logger()` returns a structlog `BoundLogger` pre-configured with the processor chain from `ObskitSettings`. Call it with `__name__` anywhere in your code — it self-configures on first use.

```python
from obskit.logging import get_logger

logger = get_logger(__name__)

# Structured key-value pairs, not string formatting
logger.debug("cache_lookup",  key="product:sku-9901", hit=False)
logger.info("inventory_reserved", product_id="sku-9901", qty=3, warehouse="eu-west-1")
logger.warning("stock_low",   product_id="sku-9901", remaining=2, threshold=5)
logger.error("checkout_failed", order_id="ord-8821", reason="out_of_stock", exc_info=True)
logger.critical("database_unreachable", host="postgres-primary.internal", retry=3)
```

Every record automatically includes: `level`, `service`, `environment`, `version`, `correlation_id`, `trace_id`, `span_id`, and `timestamp`.

### 2. Automatic trace_id and span_id injection

When `opentelemetry-api` is importable (installed via `obskit-tracing` or directly), the `add_trace_context` processor queries the active span on every log call and appends `trace_id` and `span_id`. No changes to your logging calls are needed.

```python
from obskit.tracing import setup_tracing, trace_span
from obskit.logging import get_logger, get_trace_context, is_trace_correlation_available

setup_tracing(exporter_endpoint="http://tempo:4317")
logger = get_logger(__name__)

with trace_span("process_payment", attributes={"order_id": "ord-8821"}):
    logger.info("charging_card", amount=149.99)
    # Emitted record automatically includes:
    # "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736"
    # "span_id":  "00f067aa0ba902b7"

# Check availability at runtime
if is_trace_correlation_available():
    ctx = get_trace_context()   # {"trace_id": "...", "span_id": "..."}
```

This makes log-to-trace correlation in Grafana / Datadog / Jaeger work out of the box — just configure your log datasource to use `trace_id` as the trace ID field.

### 3. logger.bind() for request-scoped context

Use `.bind()` to create a child logger that permanently carries extra fields. This is ideal for attaching request or session metadata once at the entry point of a handler, rather than repeating it on every call.

```python
from obskit.logging import get_logger

logger = get_logger(__name__)

async def handle_checkout(request):
    # Attach request-level context once
    log = logger.bind(
        request_id=request.id,
        user_id=request.user.id,
        session_id=request.session_id,
    )

    log.info("checkout_started")

    try:
        order = await create_order(request.cart)
        log.info("order_created", order_id=order.id, total=order.total)

        payment = await charge(order)
        log.info("payment_captured", payment_id=payment.id, amount=payment.amount)
    except Exception as exc:
        log.error("checkout_failed", error=str(exc), error_type=type(exc).__name__, exc_info=True)
        raise
```

Every log line in this handler automatically carries `request_id`, `user_id`, and `session_id` — no manual threading.

### 4. log_performance() and log_error() helpers

Consistent, structured helpers for the two most common observability patterns: performance tracking with threshold alerting, and rich error capture with full stack traces.

```python
import time
from obskit.logging import log_performance, log_error, log_operation

# --- Performance tracking ---
start = time.monotonic()
results = search_products(query="wireless headphones", filters={"price_max": 200})
elapsed_ms = (time.monotonic() - start) * 1000

log_performance(
    operation="product_search",
    component="CatalogService",
    duration_ms=elapsed_ms,
    threshold_ms=150.0,       # warns if over 150 ms
    query=query,
    result_count=len(results),
)
# Under 150 ms → {"event": "performance", "duration_ms": 42.3, ...}
# Over  150 ms → {"event": "slow_operation", "duration_ms": 287.1,
#                 "threshold_ms": 150.0, "exceeded_by_ms": 136.8, ...}

# --- Error capture ---
try:
    await payment_gateway.charge(amount=149.99, card_token=token)
except PaymentDeclinedError as exc:
    log_error(
        error=exc,
        component="PaymentService",
        operation="charge_card",
        context={
            "order_id": "ord-8821",
            "amount": 149.99,
            "gateway": "stripe",
        },
    )
    raise

# --- Operation lifecycle ---
log_operation(
    operation="fulfil_order",
    component="FulfillmentService",
    status="success",
    duration_ms=812.0,
    order_id="ord-8821",
    warehouse="eu-west-1",
)
```

### 5. AdaptiveSampledLogger — auto-reduces log volume under load

High-throughput services can produce millions of routine log lines per hour. `AdaptiveSampledLogger` keeps errors and slow operations at 100% while sampling down INFO/DEBUG traffic — and it deduplicates repetitive messages automatically.

```python
from obskit.logging import AdaptiveSampledLogger, SampledLogger, SamplingConfig, SamplingRule

# Fine-grained control
config = SamplingConfig(
    debug_rate=0.01,          # 1% of DEBUG logs
    info_rate=0.10,           # 10% of INFO logs
    warning_rate=1.0,         # 100% of warnings
    error_rate=1.0,           # 100% of errors (always)
    slow_threshold_seconds=1.0,   # always log ops > 1s
    dedupe_window_seconds=60.0,   # suppress duplicate messages for 60s
    always_log_first_n=3,     # always emit the first 3 occurrences of any event
    always_log_events={"order_placed", "payment_captured"},  # business-critical
)

sampled_logger = SampledLogger(name="catalog-service", config=config)

# Routine cache hits — sampled to 10%
for product_id in product_ids:
    sampled_logger.info("cache_hit", product_id=product_id)

# This will always be logged (in always_log_events set)
sampled_logger.info("order_placed", order_id="ord-8821", total=149.99)

# Errors bypass sampling entirely
sampled_logger.error("inventory_sync_failed", warehouse="eu-west-1", exc_info=True)

# Mark individual calls as important
sampled_logger.info("cache_cold_start", _important=True, duration_ms=2100)
```

### 6. Pluggable logging backends

obskit-logging ships a factory system that lets you swap the underlying logging library without touching application code.

```python
from obskit.logging import (
    configure_logging_backend,
    get_available_backends,
    register_backend,
    LoggerAdapter,
)

# See what's installed
backends = get_available_backends()   # ["structlog", "loguru"]

# Switch to loguru (requires pip install "obskit-logging[loguru]")
configure_logging_backend("loguru")

# Register a completely custom backend
class MyCloudLogger(LoggerAdapter):
    def info(self, event: str, **kwargs) -> None:
        self._send_to_cloud(level="INFO", event=event, **kwargs)

    # ... implement other levels

register_backend("cloud", MyCloudLogger)
configure_logging_backend("cloud")
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `OBSKIT_LOG_LEVEL` | `"INFO"` | Minimum level: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `OBSKIT_LOG_FORMAT` | `"json"` | Output format: `json` (production) or `console` (development) |
| `OBSKIT_LOG_INCLUDE_TIMESTAMP` | `true` | Include ISO 8601 timestamp in every record |
| `OBSKIT_LOG_SAMPLE_RATE` | `1.0` | Global non-error log sampling rate 0.0–1.0 |
| `OBSKIT_LOGGING_BACKEND` | `"structlog"` | Backend: `structlog`, `loguru`, or `auto` |
| `OBSKIT_SERVICE_NAME` | `"unknown"` | Injected as `service` field in every log record |
| `OBSKIT_ENVIRONMENT` | `"development"` | Injected as `environment` field |
| `OBSKIT_VERSION` | `"0.0.0"` | Injected as `version` field |

---

## 🧩 Part of the obskit family

`obskit-logging` is part of the [obskit](https://github.com/talaatmagdyx/obskit) monorepo — a production-ready observability toolkit for Python microservices.

| Install only this package | Install everything |
|---|---|
| `pip install obskit-logging` | `pip install "obskit[all]"` |
