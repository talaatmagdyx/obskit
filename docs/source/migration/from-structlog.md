# Migrating from structlog

This guide shows how to migrate from raw structlog to obskit's logging.

## Before: Raw structlog

```python
# logging_config.py
import structlog
import logging
import sys

def configure_logging():
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

# Usage
logger = structlog.get_logger()

def process_order(order_id):
    log = logger.bind(order_id=order_id)
    log.info("processing_started")
    
    try:
        result = do_work()
        log.info("processing_complete", result=result)
    except Exception as e:
        log.exception("processing_failed", error=str(e))
        raise
```

## After: obskit

```python
# main.py
from obskit import configure, get_logger

configure(
    service_name="my-service",
    log_level="INFO",
    log_format="json",
)

logger = get_logger()

def process_order(order_id):
    log = logger.bind(order_id=order_id)
    log.info("processing_started")
    
    try:
        result = do_work()
        log.info("processing_complete", result=result)
    except Exception as e:
        log.exception("processing_failed", error=str(e))
        raise
```

## Step-by-Step Migration

### Step 1: Install obskit

```bash
pip install obskit
```

### Step 2: Replace configuration

**Before:**
```python
import structlog
import logging

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
)
```

**After:**
```python
from obskit import configure

configure(
    service_name="my-service",
    log_level="INFO",
    log_format="json",  # or "console" for development
)
```

### Step 3: Replace logger imports

**Before:**
```python
import structlog
logger = structlog.get_logger(__name__)
```

**After:**
```python
from obskit import get_logger
logger = get_logger(__name__)
```

### Step 4: Logging API remains the same!

```python
# This code works with both structlog and obskit
logger.info("event_name", key="value")
logger.bind(user_id="123").info("user_action")
logger.exception("error_occurred")
```

## Feature Mapping

| structlog | obskit |
|-----------|--------|
| `structlog.configure()` | `obskit.configure()` |
| `structlog.get_logger()` | `obskit.get_logger()` |
| `logger.bind()` | `logger.bind()` (same!) |
| `logger.info/error/etc` | `logger.info/error/etc` (same!) |
| `merge_contextvars` | Automatic |
| `TimeStamper` | Automatic |
| `JSONRenderer` | `log_format="json"` |
| `ConsoleRenderer` | `log_format="console"` |

## Benefits After Migration

1. **Same API**: structlog's API is preserved
2. **Automatic correlation IDs**: Added to every log entry
3. **Service context**: Service name, version, environment in logs
4. **Unified configuration**: With metrics and tracing
5. **Development mode**: Easy console output switching

## New Features Available

### Automatic Correlation IDs

```python
from obskit import get_logger
from obskit.core.context import correlation_context

logger = get_logger()

with correlation_context("request-123"):
    logger.info("processing")  # correlation_id automatically included
```

### Performance Logging

```python
from obskit.logging import log_performance

log_performance(
    operation="database_query",
    duration_ms=45.2,
    threshold_ms=100.0,  # Warn if exceeded
)
```

### Error Logging with Context

```python
from obskit.logging import log_error

try:
    risky_operation()
except Exception as e:
    log_error(
        error=e,
        component="PaymentService",
        operation="charge",
        context={"amount": 99.99},
    )
```

## Using loguru Instead

If you prefer loguru over structlog:

```python
from obskit import configure

configure(
    service_name="my-service",
    logging_backend="loguru",  # Use loguru instead of structlog
)
```

Then install the loguru extra:

```bash
pip install obskit[loguru]
```

## Keeping structlog Direct Access

obskit uses structlog under the hood, so you can still access it:

```python
from obskit import configure, get_logger
import structlog

configure(service_name="my-service")

# Both work
obskit_logger = get_logger()
structlog_logger = structlog.get_logger()

# Use structlog's advanced features
structlog_logger.bind(custom_processor_data={"complex": "value"})
```

