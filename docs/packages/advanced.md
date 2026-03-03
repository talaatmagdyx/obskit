# Advanced Modules

Production-grade observability for specific infrastructure concerns. Each module is independent — import only what you need.

---

## Cache Instrumentation

`obskit.cache` — track hit rates, latency, and memory usage for any cache.

```python
from obskit.cache import CacheTracker, RedisCacheTracker, cached
```

### CacheTracker

```python
tracker = CacheTracker("user_cache", window_size=1000)
```

**Context managers:**

```python
# Recommended: track_get marks hit or miss explicitly
with tracker.track_get(key) as ctx:
    value = local_cache.get(key)
    if value is not None:
        ctx.hit(value, size_bytes=len(value))
    else:
        value = fetch_from_db(key)
        ctx.miss()

# track_operation: for set / delete / other operations
with tracker.track_operation("set", key):
    cache.set(key, value)
```

**Direct recording:**

```python
tracker.record_hit(key, size_bytes=512)
tracker.record_miss(key)
tracker.record_set(key, size_bytes=512)
tracker.record_delete(key)
tracker.record_error("get", error=e, key=key)
tracker.update_size(items=1500, memory_bytes=50_000_000)

stats = tracker.get_stats()   # CacheStats dataclass
```

### RedisCacheTracker

Extends `CacheTracker` with automatic Redis INFO stats sync:

```python
tracker = RedisCacheTracker("session_cache", redis_client=redis_client)
tracker.sync_stats()  # pulls keyspace_hits / keyspace_misses from Redis INFO
```

### `@cached` decorator

```python
@cached(tracker, ttl=300, key_prefix="user:")
async def get_user(user_id: str) -> User:
    return await db.find_user(user_id)
```

**Metrics:** `cache_requests_total`, `cache_request_latency_seconds`, `cache_size_items`, `cache_memory_bytes`, `cache_hit_rate`

---

## Cost Attribution

`obskit.cost` — track resource consumption per tenant for billing and cost allocation.

```python
from obskit.cost import CostTracker, track_cost
```

### CostTracker

```python
cost = CostTracker("my-service", cost_rates={
    "cpu_second": 0.001,
    "api_call":   0.0005,
    "storage_gb": 0.02,
})
```

| Method | What it tracks |
|--------|---------------|
| `track_cpu(tenant_id, operation)` | CPU time as context manager |
| `track_memory_usage(tenant_id, bytes_used, operation)` | Memory snapshot |
| `track_api_call(tenant_id, api, method, cost_units=1)` | External API call |
| `track_storage(tenant_id, bytes_stored, storage_type)` | Storage written |
| `track_network(tenant_id, bytes_in, bytes_out)` | Network transfer |
| `track_custom_cost(tenant_id, resource_type, units, cost_per_unit)` | Arbitrary cost |

```python
with cost.track_cpu("acme", "process_email"):
    do_work()

cost.track_api_call("acme", api="openai", method="chat.completions")
cost.track_storage("acme", bytes_stored=1_500_000, storage_type="s3")

usage = cost.get_usage("acme")
report = cost.get_usage_report("acme")
total = cost.calculate_cost("acme", period="monthly")
```

### `@track_cost` decorator

```python
@track_cost(tracker=cost, tenant_id_arg="tenant_id", operation_arg="op")
def process(tenant_id: str, op: str = "default"):
    ...
```

**Metrics:** `*_cost_cpu_time_seconds`, `*_cost_memory_bytes`, `*_cost_api_calls_total`, `*_cost_storage_bytes_total`, `*_cost_network_bytes_total`, `*_cost_units_total`

---

## Batch Processing

`obskit.batch` — track progress, success rate, and duration for batch jobs.

```python
from obskit.batch import BatchTracker, BatchContext, track_batch
```

### BatchTracker

```python
tracker = BatchTracker("nightly_email_send")
```

```python
# Context manager — yields BatchContext
with tracker.track_batch(batch_size=500) as ctx:
    for item in items:
        try:
            process(item)
            ctx.record_success()
        except Exception as e:
            ctx.record_failure(error=str(e))

result = ctx.get_result()
# BatchResult(total_items=500, successful_items=498, failed_items=2, ...)
print(result.success_rate)  # 0.996
```

```python
# Async batch with concurrency
await tracker.process_batch_async(
    items=items,
    processor=async_process,
    concurrency=20,
)
```

### `@track_batch` decorator

```python
@track_batch("import_users", batch_size=1000)
def import_users(items: list[dict]) -> None:
    ...
```

**Metrics:** `batch_operations_total`, `batch_items_total`, `batch_duration_seconds`, `batch_size`, `batch_success_rate`, `batch_in_progress`

---

## Memory & GC Tracking

`obskit.memory` — monitor Python process memory and garbage collector stats.

```python
from obskit.memory import start_memory_tracking, stop_memory_tracking, MemoryTracker
```

### Background tracking

```python
# Start tracking every 30s; alert callback at 85% memory
start_memory_tracking(
    interval_seconds=30,
    track_objects=False,
    high_memory_threshold_percent=85.0,
    on_high_memory=lambda stats: alert_ops(stats),
)

# On shutdown
stop_memory_tracking()
```

### Manual snapshots

```python
from obskit.memory import get_memory_tracker

tracker = get_memory_tracker()

mem  = tracker.collect_memory()   # MemoryStats
gc   = tracker.collect_gc()       # GCStats
objs = tracker.collect_objects()  # ObjectStats (slow — use sparingly)
all_ = tracker.collect()          # dict of all three

print(f"RSS: {mem.rss_mb:.1f} MB  ({mem.percent:.1f}%)")
print(f"GC gen0 collections: {gc.collections[0]}")
```

**Metrics:** `process_memory_rss_bytes`, `process_memory_vms_bytes`, `python_memory_heap_bytes`, `process_memory_percent`, `python_gc_collections_total` (gauge), `python_gc_collected_objects_total` (gauge), `python_gc_uncollectable_objects`, `python_objects_count`

---

## Validation Metrics

`obskit.validation` — track schema validation errors with structured metrics.

```python
from obskit.validation import ValidationTracker, ValidationException
```

### ValidationTracker

```python
tracker = ValidationTracker("order_schema")
```

```python
# With Pydantic model
result = tracker.validate(data, schema=OrderModel)
if not result.valid:
    for error in result.errors:
        print(f"{error.field}: {error.message}")

# Raise on invalid
result = tracker.validate(data, schema=OrderModel, raise_on_error=True)
```

```python
# @validated decorator
@tracker.validated(schema=OrderModel)
def create_order(data: dict) -> Order:
    return Order(**data)
```

### Helper validators

```python
from obskit.validation import validate_required, validate_type, validate_range

errors = validate_required(data, fields=["tenant_id", "amount"])
errors = validate_type(data, field_types={"amount": float, "count": int})
errors = validate_range(data, field_ranges={"amount": (0, 10_000), "count": (1, 100)})
```

**Metrics:** `validation_total`, `validation_errors_total`, `validation_duration_seconds`

---

## Thread/Process Pool Executor

`obskit.executor` — wrap `ThreadPoolExecutor` / `ProcessPoolExecutor` with utilization metrics.

```python
from obskit.executor import create_tracked_executor, wrap_executor
```

```python
# Create a new tracked executor
executor = create_tracked_executor("email_sender", max_workers=10)

future = executor.submit(send_email, msg)
executor.map(send_email, messages)

stats = executor.tracker.get_stats()
# ExecutorStats(active_tasks=3, utilization=0.3, avg_task_latency_ms=45.2, ...)
```

```python
# Wrap an existing executor
from concurrent.futures import ThreadPoolExecutor
raw = ThreadPoolExecutor(max_workers=20)
tracked = wrap_executor(raw, name="workers", max_workers=20)
```

**Metrics:** `executor_tasks_submitted_total`, `executor_tasks_completed_total`, `executor_tasks_active`, `executor_queue_size`, `executor_utilization_ratio`, `executor_task_latency_seconds`, `executor_saturation_events_total`

---

## Consumer Lag Tracking

`obskit.consumer_lag` — detect when consumers fall behind producers.

```python
from obskit.consumer_lag import ConsumerLagTracker, QueueType, get_consumer_lag_tracker
```

```python
lag_tracker = get_consumer_lag_tracker(
    "orders",
    consumer_group="order-workers",
    queue_type=QueueType.RABBITMQ,
    lag_threshold=1000,       # warn when lag > 1000 messages
    on_high_lag=lambda t, name, stats: alert(name, stats),
)

# Call after fetching queue depth from broker
lag_tracker.set_lag(messages=queue_depth, bytes=queue_bytes)

# Call for each consumed message
lag_tracker.message_consumed()          # single
lag_tracker.messages_consumed(count=5)  # batch

stats = lag_tracker.get_stats()
print(f"Lag: {stats.current_lag_messages} | Falling behind: {stats.is_falling_behind}")
print(f"Catch-up in: {stats.estimated_catch_up_seconds:.0f}s")
```

**Metrics:** `consumer_lag_messages`, `consumer_lag_bytes`, `consumer_lag_seconds`, `consumer_lag_growth_rate`, `consumer_velocity`, `consumer_messages_total`, `consumer_lag_high_events_total`

---

## Dead Letter Queue (DLQ) Tracking

`obskit.dlq` — monitor dead-letter queues and reprocessing.

```python
from obskit.dlq import DLQTracker, DLQReason, get_dlq_tracker
```

```python
dlq = get_dlq_tracker(
    "orders.dlq",
    alert_threshold=100,     # alert when DLQ > 100 messages
    on_threshold_exceeded=lambda name, stats: page_on_call(name),
)

# When sending a message to DLQ
dlq.track_message_sent(
    original_queue="orders",
    reason=DLQReason.MAX_RETRIES,
    message_id="msg-001",
    retry_count=5,
    error_message="Connection timeout",
)

# Current DLQ size (from broker stats)
dlq.set_dlq_size(size=47)
dlq.set_oldest_message_age(age_seconds=3600)

# When reprocessing
with dlq.track_processing("msg-001"):
    reprocess(message)

# Stats and report
stats = dlq.get_stats()
messages = dlq.get_messages(limit=20)
```

**DLQReason values:** `MAX_RETRIES`, `PARSE_ERROR`, `VALIDATION_ERROR`, `HANDLER_ERROR`, `TIMEOUT`, `REJECTED`, `EXPIRED`, `UNKNOWN`

**Metrics:** `dlq_messages_total`, `dlq_message_age_seconds`, `dlq_size`, `dlq_oldest_message_age_seconds`, `dlq_processing_total`, `dlq_processing_latency_seconds`, `dlq_reprocessed_total`

---

## SLA Breach Prediction

`obskit.sla_predictor` — predict SLA breaches before they happen using trend analysis.

```python
from obskit.sla_predictor import get_sla_predictor
```

```python
predictor = get_sla_predictor()

# Define SLA
predictor.set_sla(
    name="api_latency",
    metric_name="p99_latency_ms",
    threshold=500.0,
    comparison="less_than",    # breach when > 500ms
    window_minutes=60,
)

# Record measurements (call this frequently, e.g. every minute)
predictor.record(sla_name="api_latency", value=current_p99_ms)

# Assess risk
risk = predictor.assess_risk("api_latency")
print(f"Risk score: {risk.risk_score:.2f}")
print(f"Predicted breach in: {risk.predicted_breach_hours:.1f}h")
print(f"Suggestions: {risk.suggestions}")

# All at-risk SLAs
at_risk = predictor.get_at_risk_slas(risk_threshold=0.7)
```

**Metrics:** `sla_risk_score`, `sla_predicted_breach_hours`, `sla_current_value`, `sla_breach_alerts_total`

---

## Load Shedding

`obskit.shedding` — gracefully drop low-priority requests under high load.

```python
from obskit.shedding import LoadShedder, SheddingConfig, Priority, get_load_shedder
```

```python
shedder = get_load_shedder("api_gateway", config=SheddingConfig(
    max_queue_size=500,
    max_latency_ms=200.0,
    min_shed_rate=0.0,
    max_shed_rate=0.8,
))

# In each request handler
if not shedder.should_process(priority=Priority.NORMAL):
    return Response(status=503, body="Service temporarily overloaded")

# Update shedder with real-time signals
shedder.set_queue_size(current_queue_depth)
shedder.record_latency(request_latency_ms)
```

**Priority levels:** `CRITICAL=100`, `HIGH=75`, `NORMAL=50`, `LOW=25`, `BACKGROUND=0`

**Metrics:** `shedder_requests_total`, `shedder_shed_rate`, `shedder_queue_size`, `shedder_latency_ms`, `shedder_load_level`

---

## Feature Degradation

`obskit.degradation` — manage graceful degradation of features under load or dependency failures.

```python
from obskit.degradation import DegradationManager, DegradationLevel, get_degradation_manager
```

```python
mgr = get_degradation_manager("my-service")

# Register features with fallbacks
mgr.register_feature(
    name="recommendations",
    fallback=lambda: [],          # return empty list when degraded
    degradation_threshold=0.5,    # degrade at 50% load
)

mgr.register_feature("full_search", fallback=lambda q: basic_search(q))

# Check and execute with automatic fallback
result = await mgr.execute_with_fallback("recommendations", get_recommendations)

# Manual control
mgr.degrade_feature("recommendations", reason="ML service down")
mgr.restore_feature("recommendations")
mgr.set_level(DegradationLevel.HIGH)  # degrade all registered features

state = mgr.get_state()
print(f"Level: {state.level.name}")
print(f"Degraded features: {state.degraded_features}")
```

**Levels:** `NONE`, `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`

**Metrics:** `feature_state`, `degradation_level`, `degradation_events_total`, `fallback_calls_total`

---

## Audit Trail

`obskit.audit` — immutable, hash-chained audit logs for compliance.

```python
from obskit.audit import AuditTrail, AuditAction, AuditResult, get_audit_trail
```

```python
trail = get_audit_trail("my-service")

# Record an event
trail.record(
    actor_id="user-123",
    actor_type="user",
    action=AuditAction.UPDATE,
    resource_type="order",
    resource_id="ord-456",
    result=AuditResult.SUCCESS,
    tenant_id="acme",
    metadata={"old_status": "pending", "new_status": "confirmed"},
    sensitive=False,
)

# Query
entries = trail.query(actor_id="user-123", action=AuditAction.UPDATE)
history = trail.get_resource_history("order", "ord-456")
failures = trail.get_failed_actions(since=datetime.now() - timedelta(hours=24))

# Verify tamper-proof chain
is_valid = trail.verify_chain()

# Export for compliance (JSON)
report = trail.export_for_compliance(start=start_dt, end=end_dt)
```

**AuditAction values:** `CREATE`, `READ`, `UPDATE`, `DELETE`, `LOGIN`, `LOGOUT`, `EXPORT`, `CONFIGURE`, `GRANT`, `REVOKE`, `CUSTOM`

**Metrics:** `audit_events_total`, `audit_sensitive_access_total`

---

## Kubernetes Auto-scaling Metrics

`obskit.autoscaling` — export custom metrics for Kubernetes HPA.

```python
from obskit.autoscaling import AutoScalingMetrics, get_autoscaling_metrics
```

```python
scaler = get_autoscaling_metrics("worker-service")

# Report current signals (call periodically)
scaler.record_queue_depth(depth=queue_depth)
scaler.record_requests_per_second(rps=current_rps)
scaler.record_processing_rate(rate=items_per_second)
scaler.set_replicas(current=3, target=5)

# Per-pod metrics
scaler.record_pod_metrics(pod_id="pod-abc", cpu_percent=65.0, memory_percent=40.0)

# Get scaling recommendation
rec = scaler.get_recommendation()
print(f"Direction: {rec.direction.name}")
print(f"Suggested replicas: {rec.suggested_replicas}")
print(f"Reason: {rec.reason}")

# Get dict for HPA external metrics
metrics = scaler.get_metrics_for_hpa()
```

**Metrics:** `custom_metric_queue_depth`, `custom_metric_requests_per_second`, `custom_metric_error_rate`, `hpa_scaling_events_total`, `hpa_current_replicas`, `hpa_target_replicas`

---

## Endpoint Failover

`obskit.failover` — automatic failover between primary and backup endpoints.

```python
from obskit.failover import FailoverCoordinator, get_failover_coordinator
```

```python
coordinator = get_failover_coordinator("postgres")

coordinator.register_primary(
    address="postgres-primary:5432",
    health_check=lambda: check_db(primary_conn),
)
coordinator.register_backup(
    address="postgres-replica:5432",
    health_check=lambda: check_db(replica_conn),
)

# Start background health monitoring
coordinator.start_monitoring(interval_seconds=10)

# Get active endpoint
address = coordinator.get_active_address()
conn = create_connection(address)

# Manual override
coordinator.force_failover(reason="Planned maintenance")
coordinator.force_recovery()

status = coordinator.get_status()
events = coordinator.get_events(limit=10)
```

**States:** `PRIMARY`, `FAILING_OVER`, `BACKUP`, `RECOVERING`

**Metrics:** `failover_state`, `failover_count_total`, `endpoint_health`, `recovery_time_seconds`

---

## Adaptive Sampling

`obskit.adaptive_sampling` — dynamically adjust trace/log sampling rates based on load.

```python
from obskit.adaptive_sampling import AdaptiveSampler, SamplingStrategy, get_adaptive_sampler
```

```python
sampler = get_adaptive_sampler("api", config=SamplingConfig(
    base_rate=0.1,             # 10% baseline
    strategy=SamplingStrategy.PROBABILISTIC,
    min_rate=0.01,             # never below 1%
    max_rate=1.0,              # never above 100%
    error_boost=True,          # always sample errors
    error_sample_rate=1.0,
    rate_limit_per_second=100,
))

# Per request — also set per-operation rates
if sampler.should_sample(operation="create_order", is_error=False):
    tracer.start_span("create_order")

# Override for specific operations
sampler.set_operation_rate("slow_query", rate=1.0)  # always sample slow queries
sampler.set_rate(0.05)  # reduce global rate under high load

stats = sampler.get_stats()
print(f"Sample ratio: {stats.sample_ratio:.1%}")
```

**Strategies:** `PROBABILISTIC`, `RATE_LIMITING`, `ALWAYS`, `NEVER`

**Metrics:** `sampling_decisions_total`, `sampling_rate`, `sampling_load`
