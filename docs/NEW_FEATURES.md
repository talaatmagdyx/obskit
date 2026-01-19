# obskit New Features (v1.1.0)

This document describes the 13 new advanced observability features added to obskit.

## Table of Contents

1. [Async Message Tracing](#1-async-message-tracing)
2. [Batch Operation Tracking](#2-batch-operation-tracking)
3. [Cache Instrumentation](#3-cache-instrumentation)
4. [Business Metrics Helpers](#4-business-metrics-helpers)
5. [Performance Budgets](#5-performance-budgets)
6. [Correlation ID Manager](#6-correlation-id-manager)
7. [Dependency Health Aggregator](#7-dependency-health-aggregator)
8. [Smart Log Sampling](#8-smart-log-sampling)
9. [Grafana Annotations](#9-grafana-annotations)
10. [Cost Attribution Metrics](#10-cost-attribution-metrics)
11. [Schema Validation Metrics](#11-schema-validation-metrics)
12. [Adaptive Retry with Backpressure](#12-adaptive-retry-with-backpressure)
13. [Request Replay for Debugging](#13-request-replay-for-debugging)

---

## 1. Async Message Tracing

**Module:** `obskit.queue.tracing`

Provides automatic trace context propagation across message queues (RabbitMQ, Kafka, SQS).

### Classes and Functions

- `MessageTracer` - Main tracer class for message queue operations
- `TracedMessagePublisher` - Publisher with automatic trace context injection
- `@traced_message_handler` - Decorator for tracing message handlers
- `get_message_tracer()` - Factory function

### Usage

```python
from obskit.queue.tracing import MessageTracer, traced_message_handler

# Create a tracer
tracer = MessageTracer(queue_type="rabbitmq")

# Trace message publishing
with tracer.trace_publish(
    queue="orders",
    exchange="main",
    routing_key="orders.created",
    message_size=len(body)
) as span:
    channel.basic_publish(
        exchange="main",
        routing_key="orders.created",
        body=body,
        properties=pika.BasicProperties(
            headers=tracer.inject_context()  # Inject trace context
        )
    )

# Trace message consumption
@traced_message_handler(queue="orders", extract_headers=lambda m: m.headers)
async def handle_order(message):
    # Trace context automatically extracted from headers
    await process_order(message)
```

### Metrics Exported

- `queue_messages_total` - Counter for messages by queue/operation/status
- `queue_message_latency_seconds` - Histogram of message processing latency
- `queue_message_size_bytes` - Histogram of message sizes

---

## 2. Batch Operation Tracking

**Module:** `obskit.batch`

Tracks batch processing operations with detailed metrics for success/failure rates.

### Classes and Functions

- `BatchTracker` - Main class for tracking batch operations
- `BatchContext` - Context manager for individual batch tracking
- `BatchResult` - Result dataclass with success/failure counts
- `@track_batch` - Decorator for batch processing functions

### Usage

```python
from obskit.batch import BatchTracker, track_batch

# Create tracker
tracker = BatchTracker("widget_processing")

# Track a batch operation
with tracker.track_batch(batch_size=100) as batch:
    for item in items:
        try:
            process(item)
            batch.record_success()
        except Exception as e:
            batch.record_failure(error=str(e), item_id=item.id)

# Get result
result = batch.get_result()
print(f"Success rate: {result.success_rate * 100}%")

# Or use the helper method
result = tracker.process_batch(
    items=items,
    processor=process_item,
    fail_fast=False,
    on_error=lambda item, e: log_error(e)
)

# Async batch processing
result = await tracker.process_batch_async(
    items=items,
    processor=async_process_item,
    concurrency=10
)
```

### Metrics Exported

- `batch_processing_total` - Counter of batches by status
- `batch_items_total` - Counter of items by status
- `batch_processing_duration_seconds` - Histogram of batch durations
- `batch_size` - Histogram of batch sizes
- `batch_success_rate` - Gauge of current success rate
- `batch_in_progress` - Gauge of batches currently processing

---

## 3. Cache Instrumentation

**Module:** `obskit.cache`

Automatic cache hit/miss tracking with detailed metrics.

### Classes and Functions

- `CacheTracker` - Main class for cache instrumentation
- `RedisCacheTracker` - Redis-specific tracker with auto-stats sync
- `@cached` - Decorator for caching function results with tracking

### Usage

```python
from obskit.cache import CacheTracker, cached, RedisCacheTracker

# Create tracker
tracker = CacheTracker("user_cache")

# Manual tracking
with tracker.track_get("user:123") as ctx:
    value = cache.get("user:123")
    if value:
        ctx.hit(value, size_bytes=len(value))
    else:
        ctx.miss()

# Automatic caching with tracking
@cached(tracker=tracker, ttl=300, key_prefix="user")
def get_user(user_id: str):
    return db.fetch_user(user_id)

# Invalidate cache
get_user.invalidate("user-123")

# Clear all cache
get_user.clear()

# Redis-specific tracking
redis_tracker = RedisCacheTracker("redis", redis_client)
redis_tracker.sync_stats()  # Sync from Redis INFO
```

### Metrics Exported

- `cache_requests_total` - Counter by cache/operation/status
- `cache_latency_seconds` - Histogram of cache operation latency
- `cache_size_items` - Gauge of items in cache
- `cache_memory_bytes` - Gauge of cache memory usage
- `cache_hit_rate` - Gauge of rolling hit rate

---

## 4. Business Metrics Helpers

**Module:** `obskit.business`

Easy business KPI tracking alongside technical metrics.

### Classes and Functions

- `BusinessMetrics` - Main class for business metrics
- `BusinessEvent` - Dataclass for business events
- `FunnelTracker` - Multi-stage conversion funnel tracking

### Usage

```python
from obskit.business import BusinessMetrics, FunnelTracker

# Create business metrics
biz = BusinessMetrics("engagement-service")

# Track events
biz.track_event("message_sent", tenant_id="123", channel="twitter", value=1.0)

# Track revenue
biz.track_revenue("subscription", amount=99.99, currency="USD", tenant_id="123")

# Track conversions
biz.track_conversion("signup_to_paid", tenant_id="123")

# Track engagement time
with biz.track_engagement("dashboard_view", tenant_id="123", user_id="user-456"):
    # User activity
    await render_dashboard()

# Track feature usage
biz.track_feature_usage("advanced_analytics", tenant_id="123", count=5)

# Track active users
biz.track_active_user("tenant-1", "user-1", period="daily")

# Conversion funnel tracking
funnel = FunnelTracker(
    funnel_name="onboarding",
    stages=["signup", "email_verified", "profile_complete", "first_action"]
)

funnel.enter("user123", "signup")
funnel.progress("user123", "email_verified")
funnel.complete("user123")

# Get conversion rates
rates = funnel.get_conversion_rates()
print(rates)  # {"signup_to_email_verified": 0.8, ...}
```

### Metrics Exported

- `business_events_total` - Counter by service/event/tenant/channel
- `business_revenue_total` - Counter by type/currency/tenant
- `business_conversions_total` - Counter by funnel/stage/tenant
- `business_engagement_duration_seconds` - Histogram
- `business_active_users` - Gauge by period/tenant
- `business_feature_usage_total` - Counter by feature/tenant

---

## 5. Performance Budgets

**Module:** `obskit.budgets`

Enforce performance constraints at code level.

### Classes and Functions

- `PerformanceBudget` - Define and enforce performance constraints
- `BudgetStatus` - Status of a performance budget
- `BudgetManager` - Manage multiple budgets
- `@budget` - Decorator to apply budget enforcement
- `get_budget_manager()` - Get global budget manager

### Usage

```python
from obskit.budgets import PerformanceBudget, budget, get_budget_manager

# Create a performance budget
api_budget = PerformanceBudget(
    name="widget_api",
    latency_p50_ms=100,
    latency_p95_ms=500,
    latency_p99_ms=1000,
    latency_max_ms=2000,
    error_rate_percent=1.0,
    throughput_min_rps=10,
    window_seconds=60,
    on_violation=lambda name, metric, value: alert(f"{name}: {metric}={value}")
)

# Apply to function
@api_budget.enforce
async def process_widget(params):
    # If budget is exceeded, logs warning
    return await widget_service.process(params)

# Or use decorator
@budget(api_budget)
def another_function():
    pass

# Check budget status
status = api_budget.get_status()
if not status.healthy:
    print(f"Budget violated: {status.violations}")

# Manage multiple budgets
manager = get_budget_manager()
manager.register(api_budget)
manager.register(db_budget)

# Check all budgets
if manager.is_any_exceeded():
    exceeded = manager.get_exceeded_budgets()
    alert(f"Budgets exceeded: {exceeded}")
```

### Metrics Exported

- `performance_budget_violations_total` - Counter by budget/violation type
- `performance_budget_status` - Gauge (1=healthy, 0=violated)
- `performance_budget_utilization` - Gauge of budget utilization %

---

## 6. Correlation ID Manager

**Module:** `obskit.correlation`

Better correlation across async boundaries and distributed systems.

### Classes and Functions

- `CorrelationManager` - Main class for managing correlation context
- `CorrelatedTask` - Async task wrapper preserving correlation
- `generate_correlation_id()` - Generate unique ID
- `get_correlation_id()`, `set_correlation_id()` - Get/set correlation ID
- `get_full_context()` - Get all context values
- `@with_correlation` - Decorator ensuring correlation context
- `create_correlated_task()` - Create task with context preserved

### Usage

```python
from obskit.correlation import (
    CorrelationManager,
    with_correlation,
    create_correlated_task,
    get_correlation_id,
    get_tenant_id,
)

# Create new correlation context
with CorrelationManager.new_context(
    correlation_id="req-123",
    request_id="api-456",
    tenant_id="tenant-789",
    user_id="user-abc"
):
    # All code here has access to context
    print(get_correlation_id())  # "req-123"
    
    # Propagate to HTTP headers
    headers = CorrelationManager.propagate_to_headers()
    response = await client.get("/api", headers=headers)

# Extract from incoming request
ctx = CorrelationManager.extract_from_headers(request.headers)
with CorrelationManager.restore(ctx):
    await process_request()

# Ensure correlation in functions
@with_correlation()
async def handle_request(request):
    # correlation_id is automatically available
    cid = get_correlation_id()
    
# Preserve context across async boundaries
async def background_task():
    print(get_correlation_id())  # Context preserved!

task = create_correlated_task(background_task())
await task
```

---

## 7. Dependency Health Aggregator

**Module:** `obskit.health.aggregator`

Single view of all dependencies' health status.

### Classes and Functions

- `DependencyHealthAggregator` - Aggregates health of all dependencies
- `DependencyHealth` - Health status of a single dependency
- `AggregatedHealth` - Combined health status
- `HealthStatus` - Enum (HEALTHY, DEGRADED, UNHEALTHY, UNKNOWN)
- `DependencyType` - Enum (DATABASE, CACHE, QUEUE, API, etc.)
- Helper functions: `check_postgres()`, `check_redis()`, `check_rabbitmq()`, `check_http()`

### Usage

```python
from obskit.health.aggregator import (
    DependencyHealthAggregator,
    DependencyType,
    check_http,
)

# Create aggregator
aggregator = DependencyHealthAggregator(
    service_name="my-service",
    timeout_seconds=5.0,
    cache_seconds=5.0,
    critical_dependencies=["postgres"]  # Must be healthy for service to be healthy
)

# Add dependencies
async def check_db():
    return await db.ping()

aggregator.add_dependency(
    name="postgres",
    check_func=check_db,
    type=DependencyType.DATABASE,
    critical=True
)

aggregator.add_dependency(
    name="redis",
    check_func=lambda: redis.ping(),
    type=DependencyType.CACHE
)

aggregator.add_dependency(
    name="external_api",
    check_func=lambda: check_http("http://api.example.com/health"),
    type=DependencyType.API
)

# Check all dependencies
health = await aggregator.check_all()
print(health.to_dict())
# {
#   "healthy": true,
#   "status": "healthy",
#   "dependencies": {...},
#   "healthy_count": 3,
#   "unhealthy_count": 0
# }

# Wait for dependencies on startup
ready = await aggregator.wait_for_healthy(
    timeout_seconds=60.0,
    check_interval=1.0
)
if not ready:
    sys.exit(1)
```

### Metrics Exported

- `dependency_health_status` - Gauge (1=healthy, 0=unhealthy)
- `dependency_health_latency_seconds` - Gauge of check latency
- `dependency_health_checks_total` - Counter by status
- `service_overall_health` - Gauge (1=healthy, 0=degraded, -1=unhealthy)

---

## 8. Smart Log Sampling

**Module:** `obskit.logging.sampling`

Reduce log volume while maintaining visibility for important events.

### Classes and Functions

- `SampledLogger` - Logger with configurable sampling
- `AdaptiveSampledLogger` - Auto-adjusts sampling based on volume
- `SamplingConfig` - Configuration for sampling behavior
- `SamplingRule` - Per-event sampling rules
- `get_sampling_stats()` - Get global sampling statistics

### Usage

```python
from obskit.logging.sampling import (
    SampledLogger,
    AdaptiveSampledLogger,
    SamplingConfig,
)

# Create sampled logger
config = SamplingConfig(
    debug_rate=0.01,      # 1% of debug logs
    info_rate=0.1,        # 10% of info logs
    warning_rate=1.0,     # All warnings
    error_rate=1.0,       # All errors
    slow_threshold_seconds=1.0,  # Always log slow operations
    dedupe_window_seconds=60.0,  # Dedupe similar logs
    always_log_first_n=3,  # Always log first 3 occurrences
    always_log_events={"startup", "shutdown"},
    never_log_events={"heartbeat"}
)

logger = SampledLogger("high_volume_service", config=config)

# Normal logging - will be sampled
logger.info("routine_operation", data="value")

# Mark as important - bypasses sampling
logger.info("important_event", _important=True)

# Slow operation - always logged
logger.info("slow_operation", _duration=2.0)

# Adaptive logger - auto-adjusts rate
adaptive_logger = AdaptiveSampledLogger(
    name="auto_sampled",
    target_logs_per_second=100,  # Target 100 logs/sec
    min_sample_rate=0.001,
    max_sample_rate=1.0
)

# Get sampling stats
stats = logger.get_stats()
print(f"Sampled: {stats['sampled']}, Dropped: {stats['dropped']}")
```

---

## 9. Grafana Annotations

**Module:** `obskit.annotations`

Programmatic annotations for Grafana dashboards.

### Classes and Functions

- `GrafanaAnnotator` - Creates annotations in Grafana
- `Annotation` - Annotation dataclass
- `AnnotationType` - Enum (DEPLOYMENT, INCIDENT, FEATURE_FLAG, etc.)
- `AnnotationSeverity` - Enum (INFO, WARNING, ERROR, CRITICAL)
- `configure_annotator()`, `get_annotator()` - Global annotator

### Usage

```python
from obskit.annotations import (
    GrafanaAnnotator,
    AnnotationType,
    configure_annotator,
)

# Create annotator
annotator = GrafanaAnnotator(
    grafana_url="http://grafana:3000",
    api_key="your-api-key",
    default_tags=["env:production", "team:platform"],
    default_dashboard_uid="main-dashboard"
)

# Mark deployment
annotator.mark_deployment(
    version="1.2.3",
    environment="production",
    service="order-service",
    commit_sha="abc123def",
    deployed_by="deploy-bot"
)

# Mark incident
annotator.mark_incident(
    title="High error rate",
    severity="warning",
    description="Error rate exceeded 5%",
    affected_services=["order-service", "payment-service"],
    incident_id="INC-123"
)

# Mark incident resolved
annotator.mark_incident_resolved(
    title="High error rate",
    duration_minutes=45.0,
    resolution="Fixed bad deployment"
)

# Mark feature flag change
annotator.mark_feature_toggle(
    feature="new_checkout",
    enabled=True,
    percentage=50.0,
    affected_users="beta users"
)

# Mark maintenance window
annotator.mark_maintenance(
    title="Database migration",
    duration_minutes=60.0,
    affected_services=["order-service"]
)

# Mark alert
annotator.mark_alert(
    alert_name="HighCPU",
    status="firing",
    severity="warning",
    value=95.5,
    threshold=80.0
)

# Configure global annotator
configure_annotator(
    grafana_url="http://grafana:3000",
    api_key="key"
)
```

---

## 10. Cost Attribution Metrics

**Module:** `obskit.cost`

Track resource usage per tenant for billing and cost allocation.

### Classes and Functions

- `CostTracker` - Main class for cost tracking
- `ResourceUsage` - Usage dataclass
- `@track_cost` - Decorator for tracking function costs

### Usage

```python
from obskit.cost import CostTracker, track_cost

# Create tracker
tracker = CostTracker(
    service_name="engagement-service",
    cost_rates={
        "cpu_second": 0.0001,
        "memory_gb_second": 0.00001,
        "api_call": 0.001,
        "storage_gb_month": 0.02,
        "network_gb": 0.01,
    }
)

# Track CPU time
with tracker.track_cpu(tenant_id="123", operation="process_message"):
    process_message()

# Track memory usage
tracker.track_memory_usage(
    tenant_id="123",
    bytes_used=1024 * 1024 * 100,  # 100 MB
    operation="widget_processing"
)

# Track API calls
tracker.track_api_call(
    tenant_id="123",
    api="external_service",
    method="POST",
    cost_units=2.0
)

# Track storage
tracker.track_storage(tenant_id="123", bytes_stored=1024**3, storage_type="s3")

# Track network
tracker.track_network(tenant_id="123", bytes_in=1024*1024, bytes_out=512*1024)

# Use decorator
@track_cost(tracker, tenant_id_arg="customer_id")
def process_request(customer_id: str, data: dict):
    # CPU time automatically tracked
    pass

# Get usage report
report = tracker.get_usage_report(tenant_id="123")
print(report)
# {
#   "tenant_id": "123",
#   "usage": {...},
#   "estimated_cost": {"cpu": 0.1, "api_calls": 0.5, "total": 1.2}
# }

# Export all usage
json_export = tracker.export_usage(format="json")
```

### Metrics Exported

- `cost_cpu_time_seconds_total` - Counter by tenant/operation
- `cost_memory_bytes` - Histogram by tenant/operation
- `cost_api_calls_total` - Counter by tenant/api/method
- `cost_storage_bytes` - Gauge by tenant/storage_type
- `cost_network_bytes_total` - Counter by tenant/direction
- `cost_units_total` - Counter of abstract cost units

---

## 11. Schema Validation Metrics

**Module:** `obskit.validation`

Track data validation errors in a structured way.

### Classes and Functions

- `ValidationTracker` - Main class for validation tracking
- `ValidationResult` - Result of validation
- `ValidationError` - Single validation error
- `ValidationException` - Exception for validation failures
- Helper functions: `validate_required()`, `validate_type()`, `validate_range()`

### Usage

```python
from obskit.validation import (
    ValidationTracker,
    ValidationException,
    validate_required,
    validate_type,
    validate_range,
)

# Create tracker
tracker = ValidationTracker("api_requests")

# Validate with custom validator
def validate_user(data):
    errors = []
    errors.extend(validate_required(data, ["name", "email"]))
    errors.extend(validate_type(data, {"name": str, "age": int}))
    errors.extend(validate_range(data, {"age": (18, 120)}))
    return {"valid": len(errors) == 0, "errors": errors}

result = tracker.validate(user_data, validator=validate_user)
if not result.valid:
    for error in result.errors:
        print(f"{error.field}: {error.message}")

# Validate with Pydantic schema
from pydantic import BaseModel

class UserSchema(BaseModel):
    name: str
    email: str
    age: int

result = tracker.validate(user_data, schema=UserSchema)

# Raise exception on error
try:
    result = tracker.validate(data, validator=validate_user, raise_on_error=True)
except ValidationException as e:
    return {"error": e.to_dict()}

# Use decorator
@tracker.validated(validator=validate_user, raise_on_error=True)
def process_user(data: dict):
    # data is pre-validated
    pass

# Get validation stats
stats = tracker.get_stats()
print(f"Success rate: {stats['success_rate']}")
print(f"Errors by field: {stats['errors_by_field']}")
```

### Metrics Exported

- `validation_total` - Counter by schema/status
- `validation_errors_total` - Counter by schema/field/error_type
- `validation_duration_seconds` - Histogram of validation time

---

## 12. Adaptive Retry with Backpressure

**Module:** `obskit.resilience.adaptive`

Smarter retries that adapt to system load.

### Classes and Functions

- `AdaptiveRetry` - Main class for adaptive retry
- `RetryConfig` - Configuration for retry behavior
- `RetryState` - State during retry operation
- `BackpressureStrategy` - Enum (NONE, LINEAR, EXPONENTIAL, ADAPTIVE)
- `@adaptive_retry` - Decorator for adaptive retry

### Usage

```python
from obskit.resilience.adaptive import (
    AdaptiveRetry,
    RetryConfig,
    BackpressureStrategy,
    adaptive_retry,
)

# Create adaptive retry
config = RetryConfig(
    max_retries=3,
    base_delay_seconds=0.1,
    max_delay_seconds=60.0,
    exponential_base=2.0,
    jitter_factor=0.25,
    backpressure_strategy=BackpressureStrategy.ADAPTIVE,
    error_rate_threshold=0.1,  # 10% errors
    latency_threshold_seconds=1.0,
    window_size=100,
    max_concurrent=100,
)

retry = AdaptiveRetry(
    name="external_api",
    config=config,
    retryable_exceptions={ConnectionError, TimeoutError}
)

# Use directly
result = await retry.execute(call_external_api, arg1, arg2)

# Use decorator
@retry.wrap
async def call_api():
    return await external_api.call()

# Or use the decorator factory
@adaptive_retry(
    "payment_api",
    max_retries=3,
    base_delay=0.5,
    backpressure=BackpressureStrategy.ADAPTIVE
)
async def process_payment(amount: float):
    return await payment_api.charge(amount)

# Sync version
result = retry.execute_sync(sync_function)

# Get stats
stats = retry.get_stats()
print(f"Backpressure: {stats['backpressure_multiplier']}")
print(f"Error rate: {stats['error_rate']}")
```

### Backpressure Strategies

- **NONE**: No backpressure adjustment
- **LINEAR**: Multiplier = 1 + (error_rate * 10)
- **EXPONENTIAL**: Multiplier = 2^(error_rate * 10)
- **ADAPTIVE**: Combines error rate and latency, adjusts concurrency

### Metrics Exported

- `adaptive_retry_attempts_total` - Counter by status
- `adaptive_retry_delay_seconds` - Histogram of delays
- `adaptive_retry_error_rate` - Gauge of current error rate
- `adaptive_retry_backpressure_multiplier` - Gauge
- `adaptive_retry_concurrent_requests` - Gauge

---

## 13. Request Replay for Debugging

**Module:** `obskit.debug.replay`

Capture and replay failed requests for debugging.

### Classes and Functions

- `RequestCapture` - Main class for capturing requests
- `CapturedRequest` - Captured request dataclass
- `FileStorage` - Store captures to filesystem
- `MemoryStorage` - Store captures in memory (testing)

### Usage

```python
from obskit.debug.replay import (
    RequestCapture,
    FileStorage,
    MemoryStorage,
)

# Create capture with file storage
capture = RequestCapture(
    storage=FileStorage("/var/log/captures", compress=True),
    capture_on_error=True,
    capture_on_slow=True,
    slow_threshold_seconds=5.0,
    capture_sample_rate=1.0,  # Capture all
    max_arg_size=10000,  # Truncate large args
    include_traceback=True,
)

# Wrap function for automatic capture
@capture.wrap
async def process_message(data: dict):
    # On failure, request is captured
    return await do_processing(data)

# List captured requests
captures = await capture.list_captures(
    function_name="process_message",
    since=time.time() - 3600,  # Last hour
    limit=100
)
for cap in captures:
    print(f"{cap['capture_id']}: {cap['function_name']} - {cap['error_type']}")

# Replay a captured request (dry run)
result = await capture.replay("capture-abc123", dry_run=True)
print(f"Would call with args: {result['args']}")

# Actually replay
result = await capture.replay("capture-abc123")
if result["success"]:
    print(f"Replay succeeded: {result['output']}")
else:
    print(f"Replay failed: {result['error']}")

# Delete old captures
await capture.delete_capture("capture-abc123")

# Custom metadata extraction
def extract_metadata(data):
    return {"request_id": data.get("id"), "tenant": data.get("tenant_id")}

capture = RequestCapture(
    storage=FileStorage("/var/log/captures"),
    metadata_extractor=extract_metadata
)
```

### Storage Options

**FileStorage**:
- Stores captures as JSON files (optionally compressed)
- Suitable for production use
- Supports filtering and listing

**MemoryStorage**:
- Stores captures in memory
- Suitable for testing
- Auto-evicts old captures when at limit

---

## Installation

All features are included in obskit v1.1.0:

```bash
pip install obskit>=1.1.0

# Or with all optional dependencies
pip install obskit[all]>=1.1.0
```

## Quick Reference

| Feature | Import |
|---------|--------|
| Message Tracing | `from obskit.queue.tracing import MessageTracer` |
| Batch Tracking | `from obskit.batch import BatchTracker` |
| Cache Tracking | `from obskit.cache import CacheTracker` |
| Business Metrics | `from obskit.business import BusinessMetrics` |
| Performance Budgets | `from obskit.budgets import PerformanceBudget` |
| Correlation | `from obskit.correlation import CorrelationManager` |
| Health Aggregator | `from obskit.health.aggregator import DependencyHealthAggregator` |
| Log Sampling | `from obskit.logging.sampling import SampledLogger` |
| Grafana Annotations | `from obskit.annotations import GrafanaAnnotator` |
| Cost Attribution | `from obskit.cost import CostTracker` |
| Validation | `from obskit.validation import ValidationTracker` |
| Adaptive Retry | `from obskit.resilience.adaptive import AdaptiveRetry` |
| Request Replay | `from obskit.debug.replay import RequestCapture` |

Or import from main module:

```python
from obskit import (
    BatchTracker,
    CacheTracker,
    BusinessMetrics,
    PerformanceBudget,
    CorrelationManager,
    CostTracker,
    ValidationTracker,
    AdaptiveRetry,
    RequestCapture,
)
```
