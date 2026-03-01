# Migrating from raw structlog to obskit-logging

obskit-logging is built on top of structlog.  If you are already using structlog
directly, the migration is minimal — you keep your existing processor pipeline and
add obskit's trace-log correlation, OTLP export, and adaptive sampling on top.

---

## Why Migrate?

| Raw structlog | obskit-logging |
|---|---|
| Manual trace context extraction in every processor | Automatic `trace_id` / `span_id` injection when a span is active |
| Manual OTLP log export setup (50+ lines of OTel SDK) | `get_logger()` enables OTLP export via `OBSKIT_OTLP_ENDPOINT` |
| Log sampling requires a custom processor | `AdaptiveSampler` adjusts sample rate based on error rate and throughput |
| `contextvars.copy_context()` must be called manually for async safety | obskit handles context propagation automatically |
| Service name, environment, version must be added to every logger | Set once via `OBSKIT_SERVICE_NAME` / `configure()` |

obskit-logging does **not** remove structlog from your dependency tree — it depends
on it.  You can still use all structlog APIs directly.

---

## Installation

```bash
pip install obskit

# For OTLP log export
pip install obskit opentelemetry-exporter-otlp-proto-grpc
```

---

## structlog.get_logger() → obskit.logging.get_logger()

### Before

```python
import structlog

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)

logger = structlog.get_logger(__name__)
logger = logger.bind(service="order-service", environment="production")
```

### After

```python
from obskit.logging import get_logger
from obskit.config import configure

configure(
    service_name="order-service",
    environment="production",
    log_level="INFO",
    log_format="json",  # "console" for development
)

logger = get_logger(__name__)
# service_name, environment, and trace context are injected automatically
```

The obskit processor pipeline includes everything in the raw structlog example above,
plus trace context injection.

---

## Processor Pipeline Migration

### Before — custom processor chain

```python
import structlog

def add_service_context(logger, method, event_dict):
    event_dict["service"] = "order-service"
    event_dict["env"] = "production"
    return event_dict

def add_trace_context(logger, method, event_dict):
    from opentelemetry import trace
    span = trace.get_current_span()
    ctx = span.get_span_context()
    if ctx.is_valid:
        event_dict["trace_id"] = format(ctx.trace_id, "032x")
        event_dict["span_id"] = format(ctx.span_id, "016x")
    return event_dict

structlog.configure(
    processors=[
        add_service_context,
        add_trace_context,
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ]
)
```

### After — obskit handles this

```python
from obskit.logging import get_logger
from obskit.config import configure

configure(service_name="order-service", environment="production")
logger = get_logger(__name__)
# All processors applied automatically
```

### Keeping custom processors

You can inject your own processors into the obskit pipeline:

```python
from obskit.logging.factory import create_logger

def my_custom_processor(logger, method, event_dict):
    event_dict["datacenter"] = "eu-west-1"
    return event_dict

logger = create_logger(
    name=__name__,
    extra_processors=[my_custom_processor],
)
```

---

## contextvars — Automatic Context Propagation

A common pain point with raw structlog in async code is that `contextvars` context
is not automatically propagated across `asyncio.create_task()` boundaries.

### Before — manual context copy

```python
import asyncio
import contextvars
import structlog

structlog.contextvars.bind_contextvars(request_id="abc-123")

async def background_task():
    # request_id is NOT available here unless you copy context
    logger.info("background_work")  # missing request_id

# Manual fix
ctx = contextvars.copy_context()
asyncio.get_event_loop().run_in_executor(None, ctx.run, background_task)
```

### After — obskit propagates automatically

```python
from obskit.logging import get_logger
from obskit.core.context import set_correlation_id

logger = get_logger(__name__)
set_correlation_id("abc-123")

async def background_task():
    # correlation_id is available — obskit propagates it
    logger.info("background_work")  # includes correlation_id
```

obskit uses `contextvars` internally and ensures context is propagated correctly
across task boundaries, thread pool executors, and async generators.

---

## Log Sampling

### Before — no built-in sampling

```python
import random
import structlog

logger = structlog.get_logger()

def log_if_sampled(event: str, **kwargs):
    if random.random() < 0.01:  # 1% sample rate — manual
        logger.info(event, **kwargs)
```

### After — AdaptiveSampler

```python
from obskit.adaptive_sampling import AdaptiveSampler
from obskit.logging import get_logger

logger = get_logger(__name__)
sampler = AdaptiveSampler(base_rate=0.01)  # 1% baseline

# Automatically increases sample rate when error rate rises
def handle_request(endpoint: str) -> None:
    if sampler.should_sample():
        logger.info("request_handled", endpoint=endpoint)
```

The `AdaptiveSampler` increases the sample rate toward 1.0 when the error rate rises
above a configurable threshold, ensuring you always have full data during incidents.

---

## OTLP Log Export

Exporting logs via OTLP (to Grafana Loki, OpenSearch, or any OTLP-compatible
backend) requires zero additional code when `OBSKIT_OTLP_ENDPOINT` is set.

```bash
export OBSKIT_OTLP_ENDPOINT=http://collector:4317
export OBSKIT_SERVICE_NAME=order-service
```

```python
from obskit.logging import get_logger

# Logs are written to stdout AND exported via OTLP automatically
logger = get_logger(__name__)
logger.info("order_created", order_id="ord-123")
```

---

## Loguru Users

If you are using Loguru instead of structlog, obskit provides a compatibility
adapter:

```python
from obskit.logging.adapters.loguru_adapter import LoguruAdapter

adapter = LoguruAdapter()
adapter.install()  # Redirects Loguru output through obskit's pipeline

from loguru import logger
logger.info("This goes through obskit now")
```

---

## Migration Checklist

- [ ] Replace `structlog.configure(…)` with `obskit.config.configure(…)` at startup
- [ ] Replace `structlog.get_logger()` with `obskit.logging.get_logger()`
- [ ] Remove manual `add_trace_context` processor (obskit provides this)
- [ ] Remove manual `add_service_context` processor (set via `configure()`)
- [ ] Remove manual `contextvars.copy_context()` calls (obskit handles this)
- [ ] Add `AdaptiveSampler` for high-throughput log paths
- [ ] Set `OBSKIT_OTLP_ENDPOINT` if exporting logs to a backend
- [ ] Run tests and verify log output contains `trace_id` during active spans
