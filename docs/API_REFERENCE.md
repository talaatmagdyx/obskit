# obskit API Reference

Complete API documentation for all obskit modules.

## Table of Contents

- [Core Configuration](#core-configuration)
- [Logging](#logging)
- [Metrics](#metrics)
- [Tracing](#tracing)
- [Resilience](#resilience)
- [Health](#health)
- [SLO](#slo)
- [Queue](#queue)
- [Database](#database)
- [New Features](#new-features)

---

## Core Configuration

### `obskit.configure()`

Initialize obskit with all settings.

```python
from obskit import configure

configure(
    service_name="my-service",
    environment="production",
    version="1.0.0",
    log_format="json",
    log_level="info",
    otlp_endpoint="http://otel-collector:4317",
    metrics_port=9090,
    enable_tracing=True,
    enable_metrics=True,
    additional_attributes={"region": "us-east-1"}
)
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `service_name` | str | "default" | Name of the service |
| `environment` | str | "development" | Environment name |
| `version` | str | "0.0.0" | Service version |
| `log_format` | str | "console" | "json" or "console" |
| `log_level` | str | "info" | Logging level |
| `otlp_endpoint` | str | None | OpenTelemetry endpoint |
| `metrics_port` | int | 9090 | Prometheus metrics port |
| `enable_tracing` | bool | True | Enable distributed tracing |
| `enable_metrics` | bool | True | Enable metrics |

---

## Logging

### `obskit.get_logger()`

Get a structured logger.

```python
from obskit import get_logger

logger = get_logger(__name__)
logger.info("event_name", key1="value1", key2=123)
```

### `obskit.log_error()`

Log an exception with context.

```python
from obskit import log_error

try:
    process()
except Exception as e:
    log_error(
        exception=e,
        component="message_processor",
        operation="process_message",
        context={"message_id": "123"}
    )
```

### `obskit.logging.sampling.SampledLogger`

Logger with configurable sampling.

```python
from obskit.logging.sampling import SampledLogger, SamplingConfig

config = SamplingConfig(
    debug_rate=0.01,
    info_rate=0.1,
    warning_rate=1.0,
    error_rate=1.0,
    critical_rate=1.0,
    slow_threshold_seconds=1.0,
    dedupe_window_seconds=60.0,
    always_log_first_n=3,
    always_log_events={"startup", "shutdown"},
    never_log_events={"heartbeat"}
)

logger = SampledLogger("service", config=config)
```

**SamplingConfig Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `debug_rate` | float | 0.01 | Sample rate for debug logs |
| `info_rate` | float | 0.1 | Sample rate for info logs |
| `warning_rate` | float | 1.0 | Sample rate for warnings |
| `error_rate` | float | 1.0 | Sample rate for errors |
| `critical_rate` | float | 1.0 | Sample rate for critical |
| `slow_threshold_seconds` | float | 1.0 | Always log if slower |
| `dedupe_window_seconds` | float | 60.0 | Dedup window |
| `always_log_first_n` | int | 3 | Always log first N |
| `always_log_events` | Set[str] | {} | Events to always log |
| `never_log_events` | Set[str] | {} | Events to never log |

---

## Metrics

### `obskit.REDMetrics`

RED (Rate, Errors, Duration) metrics.

```python
from obskit import REDMetrics

metrics = REDMetrics(name="api_requests")

# Track a request
with metrics.track():
    process_request()

# Or manually
metrics.observe_request(
    status="success",
    latency_seconds=0.5,
    method="POST",
    endpoint="/api/users"
)
```

### `obskit.metrics.GoldenSignals`

Golden signals metrics.

```python
from obskit.metrics import GoldenSignals

signals = GoldenSignals(name="my_service")
signals.record_request(latency=0.5, status="success")
signals.set_saturation(0.75)
```

### `obskit.metrics.USEMetrics`

USE (Utilization, Saturation, Errors) metrics.

```python
from obskit.metrics import USEMetrics

use = USEMetrics(resource_name="cpu")
use.set_utilization(0.8)
use.set_saturation(0.3)
use.record_error("throttle")
```

### `obskit.metrics.tenant.TenantREDMetrics`

Tenant-aware RED metrics.

```python
from obskit.metrics.tenant import TenantREDMetrics

metrics = TenantREDMetrics(name="tenant_requests")
metrics.observe_request(tenant_id="123", status="success", latency=0.5)
```

---

## Tracing

### `obskit.tracing.trace_span()`

Create a traced span.

```python
from obskit.tracing import trace_span

with trace_span("process_message", attributes={"message_id": "123"}) as span:
    span.add_event("processing_started")
    result = process()
    span.set_attribute("result_size", len(result))
```

### `obskit.tracing.get_tracer()`

Get the configured tracer.

```python
from obskit.tracing import get_tracer

tracer = get_tracer()
with tracer.start_as_current_span("my_operation") as span:
    pass
```

### `obskit.tracing.inject_trace_context()`

Inject trace context into headers.

```python
from obskit.tracing import inject_trace_context

headers = inject_trace_context({})
response = requests.get(url, headers=headers)
```

---

## Resilience

### `obskit.resilience.CircuitBreaker`

Circuit breaker pattern.

```python
from obskit.resilience import CircuitBreaker

cb = CircuitBreaker(
    name="external_api",
    failure_threshold=5,
    recovery_timeout=30.0,
    half_open_max_calls=3
)

with cb:
    result = call_external_api()
```

### `obskit.resilience.TokenBucketRateLimiter`

Rate limiting.

```python
from obskit.resilience import TokenBucketRateLimiter

limiter = TokenBucketRateLimiter(
    name="api",
    rate=100,  # 100 requests per second
    burst=10   # Allow bursts of 10
)

if limiter.acquire():
    process_request()
else:
    raise RateLimitExceeded()
```

### `obskit.resilience.retry` / `obskit.resilience.retry_async`

Retry decorators.

```python
from obskit.resilience import retry, retry_async, RetryConfig

config = RetryConfig(
    max_attempts=3,
    delay=0.1,
    max_delay=10.0,
    backoff_multiplier=2.0,
    retryable_exceptions={ConnectionError, TimeoutError}
)

@retry(config)
def call_api():
    pass

@retry_async(config)
async def call_api_async():
    pass
```

### `obskit.resilience.adaptive.AdaptiveRetry`

Adaptive retry with backpressure.

```python
from obskit.resilience.adaptive import (
    AdaptiveRetry,
    RetryConfig,
    BackpressureStrategy
)

config = RetryConfig(
    max_retries=3,
    base_delay_seconds=0.1,
    max_delay_seconds=60.0,
    exponential_base=2.0,
    jitter_factor=0.25,
    backpressure_strategy=BackpressureStrategy.ADAPTIVE,
    error_rate_threshold=0.1,
    max_concurrent=100
)

retry = AdaptiveRetry(
    name="external_api",
    config=config,
    retryable_exceptions={ConnectionError, TimeoutError}
)

result = await retry.execute(call_api)

# Or as decorator
@retry.wrap
async def my_function():
    pass
```

**BackpressureStrategy options:**

| Strategy | Description |
|----------|-------------|
| `NONE` | No backpressure adjustment |
| `LINEAR` | Linear increase based on error rate |
| `EXPONENTIAL` | Exponential increase based on error rate |
| `ADAPTIVE` | Dynamic based on both error rate and latency |

---

## Health

### `obskit.health.HealthChecker`

Health check management.

```python
from obskit.health import HealthChecker, get_health_checker

checker = get_health_checker()

checker.add_check("database", lambda: db.ping())
checker.add_check("cache", lambda: redis.ping())

# Get health status
health = checker.check_health()
print(health.to_dict())
```

### `obskit.health.aggregator.DependencyHealthAggregator`

Aggregate dependency health.

```python
from obskit.health.aggregator import (
    DependencyHealthAggregator,
    DependencyType
)

aggregator = DependencyHealthAggregator(
    service_name="my-service",
    timeout_seconds=5.0,
    cache_seconds=5.0,
    critical_dependencies=["postgres"]
)

aggregator.add_dependency(
    name="postgres",
    check_func=check_db,
    type=DependencyType.DATABASE,
    critical=True
)

health = await aggregator.check_all()
```

**DependencyType options:**

| Type | Description |
|------|-------------|
| `DATABASE` | Database dependency |
| `CACHE` | Cache (Redis, Memcached) |
| `QUEUE` | Message queue |
| `API` | External API |
| `STORAGE` | Object storage (S3) |
| `CUSTOM` | Custom dependency |

---

## SLO

### `obskit.slo.SLOTracker`

Track SLO compliance.

```python
from obskit.slo import SLOTracker, SLOType

tracker = SLOTracker()

# Define SLOs
tracker.register_slo(
    name="availability",
    slo_type=SLOType.AVAILABILITY,
    target=0.999,
    window_seconds=3600
)

tracker.register_slo(
    name="latency_p95",
    slo_type=SLOType.LATENCY,
    target=500.0,  # ms
    window_seconds=3600
)

# Record measurements
tracker.record_measurement("availability", success=True)
tracker.record_measurement("latency_p95", value=250.0)

# Or use context manager
with tracker.track_slo("availability"):
    process()

# Check compliance
if not tracker.is_compliant("availability"):
    alert()

# Get error budget
budget = tracker.get_error_budget("availability")
print(f"Error budget remaining: {budget['remaining_percent']}%")
```

**SLOType options:**

| Type | Description |
|------|-------------|
| `AVAILABILITY` | Success rate |
| `LATENCY` | Response time percentile |
| `THROUGHPUT` | Request rate |
| `ERROR_RATE` | Error percentage |

---

## Queue

### `obskit.queue.QueueTracker`

Track queue operations.

```python
from obskit.queue import QueueTracker

tracker = QueueTracker("rabbitmq")

with tracker.track_publish("orders"):
    channel.basic_publish(...)

with tracker.track_consume("orders"):
    process_message()
```

### `obskit.queue.tracing.MessageTracer`

Trace context propagation in queues.

```python
from obskit.queue.tracing import MessageTracer, traced_message_handler

tracer = MessageTracer(queue_type="rabbitmq")

# Publishing
with tracer.trace_publish(queue="orders", message_size=100) as span:
    channel.basic_publish(
        ...,
        properties=pika.BasicProperties(
            headers=tracer.inject_context()
        )
    )

# Consuming
@traced_message_handler(queue="orders")
async def handle_message(msg):
    pass
```

---

## Database

### `obskit.db.DatabaseTracker`

Track database queries.

```python
from obskit.db import DatabaseTracker

tracker = DatabaseTracker("postgres")

with tracker.track_query(operation="select", table="users"):
    result = cursor.execute("SELECT * FROM users")
```

---

## New Features

### `obskit.batch.BatchTracker`

Track batch operations.

```python
from obskit.batch import BatchTracker

tracker = BatchTracker("widget_processing")

with tracker.track_batch(batch_size=100) as batch:
    for item in items:
        try:
            process(item)
            batch.record_success()
        except Exception as e:
            batch.record_failure(error=str(e))

result = batch.get_result()
```

### `obskit.cache.CacheTracker`

Track cache operations.

```python
from obskit.cache import CacheTracker, cached

tracker = CacheTracker("user_cache")

@cached(tracker=tracker, ttl=300, key_prefix="user")
def get_user(user_id):
    return db.fetch_user(user_id)
```

### `obskit.business.BusinessMetrics`

Track business KPIs.

```python
from obskit.business import BusinessMetrics, FunnelTracker

biz = BusinessMetrics("my-service")
biz.track_event("purchase", tenant_id="123", value=99.99)
biz.track_revenue("subscription", amount=9.99, tenant_id="123")
```

### `obskit.budgets.PerformanceBudget`

Enforce performance constraints.

```python
from obskit.budgets import PerformanceBudget

budget = PerformanceBudget(
    name="api",
    latency_p95_ms=500,
    error_rate_percent=1.0
)

@budget.enforce
def api_endpoint():
    pass
```

### `obskit.correlation.CorrelationManager`

Manage correlation IDs.

```python
from obskit.correlation import CorrelationManager

with CorrelationManager.new_context(correlation_id="123"):
    headers = CorrelationManager.propagate_to_headers()
```

### `obskit.annotations.GrafanaAnnotator`

Create Grafana annotations.

```python
from obskit.annotations import GrafanaAnnotator

annotator = GrafanaAnnotator(
    grafana_url="http://grafana:3000",
    api_key="key"
)
annotator.mark_deployment(version="1.0.0", environment="prod")
```

### `obskit.cost.CostTracker`

Track resource usage per tenant.

```python
from obskit.cost import CostTracker

tracker = CostTracker("my-service")

with tracker.track_cpu(tenant_id="123"):
    process()

report = tracker.get_usage_report(tenant_id="123")
```

### `obskit.validation.ValidationTracker`

Track validation errors.

```python
from obskit.validation import ValidationTracker

tracker = ValidationTracker("api_requests")
result = tracker.validate(data, validator=validate_func)
```

### `obskit.debug.replay.RequestCapture`

Capture and replay requests.

```python
from obskit.debug.replay import RequestCapture, FileStorage

capture = RequestCapture(
    storage=FileStorage("/var/log/captures"),
    capture_on_error=True
)

@capture.wrap
async def process(data):
    pass

# Replay
result = await capture.replay("capture-id")
```

---

## Decorators

### `@obskit.decorators.with_observability`

Full observability decorator.

```python
from obskit.decorators import with_observability

@with_observability(
    name="process_message",
    track_metrics=True,
    track_trace=True,
    log_on_error=True
)
def process_message(data):
    pass
```

### `@obskit.decorators.track_operation`

Track operation metrics.

```python
from obskit.decorators import track_operation

@track_operation("widget_processing")
async def process_widget(data):
    pass
```
