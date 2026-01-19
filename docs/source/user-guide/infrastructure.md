# Infrastructure Monitoring (v1.3.0)

Monitor your infrastructure components with obskit.

## Connection Pool Metrics

Track database and Redis connection pools.

### Database Pools

```python
from obskit import (
    ConnectionPoolTracker,
    get_pool_tracker,
    wrap_psycopg2_pool,
    get_all_pool_stats
)

# Wrap a psycopg2 pool
import psycopg2.pool

db_pool = psycopg2.pool.ThreadedConnectionPool(5, 20, dsn)
tracked_pool = wrap_psycopg2_pool(db_pool, name="main_db")

# Use the pool normally
conn = tracked_pool.getconn()
try:
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM users")
finally:
    tracked_pool.putconn(conn)
```

### Redis Pools

```python
from obskit import wrap_redis_pool
import redis

# Wrap a Redis pool
redis_pool = redis.ConnectionPool(max_connections=100)
tracked_redis = wrap_redis_pool(redis_pool, name="cache")
```

### View Statistics

```python
# Get all pool statistics
stats = get_all_pool_stats()

for pool_name, pool_stats in stats.items():
    print(f"{pool_name}:")
    print(f"  Size: {pool_stats.size}")
    print(f"  Used: {pool_stats.used}")
    print(f"  Available: {pool_stats.available}")
    print(f"  Wait time (avg): {pool_stats.wait_time_avg_ms:.2f}ms")
    print(f"  Utilization: {pool_stats.utilization:.1%}")
```

### Health Check Integration

```python
from obskit import check_all_pools_healthy

@health_checker.add_readiness_check("connection_pools")
async def check_pools():
    return check_all_pools_healthy(
        min_available_percent=0.2  # At least 20% available
    )
```

## Dead Letter Queue Tracking

Monitor messages that failed processing.

### Track DLQ Messages

```python
from obskit import (
    DLQTracker,
    DLQReason,
    get_dlq_tracker
)

dlq = get_dlq_tracker("order_processing")

# Record a DLQ message
dlq.record_message(
    message_id="msg-12345",
    reason=DLQReason.PARSE_ERROR,
    original_queue="orders",
    error_message="Invalid JSON: Unexpected token",
    payload_sample=payload[:1000]  # First 1000 chars
)

# DLQ reasons
# - PARSE_ERROR: Message format invalid
# - VALIDATION_ERROR: Message failed validation
# - PROCESSING_ERROR: Error during processing
# - EXPIRED: Message TTL exceeded
# - REJECTED: Explicitly rejected
# - UNKNOWN: Unknown reason
```

### View Statistics

```python
from obskit import get_all_dlq_stats

stats = dlq.get_stats()
print(f"Total DLQ messages: {stats.total_count}")
print(f"Messages today: {stats.today_count}")

print("By reason:")
for reason, count in stats.by_reason.items():
    print(f"  {reason}: {count}")

print("By queue:")
for queue, count in stats.by_queue.items():
    print(f"  {queue}: {count}")
```

## Consumer Lag Tracking

Monitor message consumer lag.

### Kafka Consumer Lag

```python
from obskit import (
    ConsumerLagTracker,
    QueueType,
    get_consumer_lag_tracker
)

kafka_lag = get_consumer_lag_tracker("orders", queue_type=QueueType.KAFKA)

# Update lag (call periodically)
kafka_lag.update_lag(
    consumer_group="order-processor",
    partition=0,
    current_offset=1000,
    end_offset=1050
)
```

### RabbitMQ Queue Depth

```python
rabbitmq_lag = get_consumer_lag_tracker("notifications", queue_type=QueueType.RABBITMQ)

# Update queue depth
rabbitmq_lag.update_queue_depth(50)  # 50 messages waiting
```

### View All Lag Statistics

```python
from obskit import get_all_consumer_lag_stats

stats = get_all_consumer_lag_stats()

for queue, lag_stats in stats.items():
    print(f"{queue}:")
    print(f"  Lag (messages): {lag_stats.lag_messages}")
    print(f"  Lag (seconds): {lag_stats.lag_seconds}s")
    print(f"  Consumer rate: {lag_stats.consume_rate}/s")
```

## External API SLA Tracking

Monitor third-party API compliance.

### Define and Track SLA

```python
from obskit import (
    ExternalAPISLATracker,
    SLADefinition,
    get_external_api_tracker
)

tracker = get_external_api_tracker("payment_gateway")

# Define SLA
tracker.set_sla(SLADefinition(
    availability_target=0.999,   # 99.9% availability
    latency_p99_ms=500,          # P99 under 500ms
    error_rate_target=0.001      # < 0.1% errors
))

# Record each request
tracker.record_request(
    duration_ms=150,
    success=True,
    status_code=200
)

# Record failures
tracker.record_request(
    duration_ms=5000,
    success=False,
    status_code=503,
    error_type="timeout"
)
```

### Get Compliance Report

```python
from obskit import get_all_api_compliance

report = tracker.get_compliance_report()

print(f"API: payment_gateway")
print(f"Availability: {report.availability:.4f} (target: {report.sla.availability_target})")
print(f"Latency P99: {report.latency_p99_ms}ms (target: {report.sla.latency_p99_ms}ms)")
print(f"Error Rate: {report.error_rate:.4f} (target: {report.sla.error_rate_target})")
print(f"Compliant: {'✅' if report.is_compliant else '❌'}")

# All APIs
all_compliance = get_all_api_compliance()
for api_name, compliance in all_compliance.items():
    status = "✅" if compliance.is_compliant else "❌"
    print(f"{api_name}: {status}")
```

## Memory & GC Metrics

Track Python memory and garbage collection.

### Start Tracking

```python
from obskit import (
    MemoryTracker,
    start_memory_tracking,
    stop_memory_tracking,
    get_memory_tracker
)

# Start background tracking
start_memory_tracking(interval_seconds=30)
```

### Get Statistics

```python
tracker = get_memory_tracker()
stats = tracker.get_stats()

print(f"Heap used: {stats.heap_used_mb:.2f}MB")
print(f"Heap total: {stats.heap_total_mb:.2f}MB")
print(f"Heap utilization: {stats.heap_utilization:.1%}")

print(f"\nGC Statistics:")
print(f"  Collections: {stats.gc_stats.collections}")
print(f"  Collection time: {stats.gc_stats.collection_time_ms}ms")
print(f"  Objects collected: {stats.gc_stats.objects_collected}")
```

### Object Statistics

```python
# Get object counts by type
obj_stats = tracker.get_object_stats()

print("Top object types by count:")
for type_name, count in obj_stats.top_types[:10]:
    print(f"  {type_name}: {count}")
```

### Stop Tracking

```python
# Stop when shutting down
stop_memory_tracking()
```

## Executor Metrics

Track ThreadPoolExecutor performance.

### Wrap Executor

```python
from obskit import (
    ExecutorTracker,
    wrap_executor,
    create_tracked_executor,
    get_all_executor_stats
)
from concurrent.futures import ThreadPoolExecutor

# Create a new tracked executor
executor = create_tracked_executor(
    name="worker_pool",
    max_workers=10
)

# Or wrap an existing one
existing = ThreadPoolExecutor(max_workers=5)
tracked = wrap_executor(existing, name="legacy_pool")
```

### Submit Tasks

```python
# Use normally
future = executor.submit(process_task, data)
result = future.result()

# Async usage
import asyncio
loop = asyncio.get_event_loop()
result = await loop.run_in_executor(executor, process_task, data)
```

### View Statistics

```python
stats = get_all_executor_stats()

for name, exec_stats in stats.items():
    print(f"{name}:")
    print(f"  Max workers: {exec_stats.max_workers}")
    print(f"  Active: {exec_stats.active_count}")
    print(f"  Queued: {exec_stats.queued_count}")
    print(f"  Completed: {exec_stats.completed_count}")
    print(f"  Failed: {exec_stats.failed_count}")
    print(f"  Avg duration: {exec_stats.avg_duration_ms:.2f}ms")
```

## Tenant Quota Tracking

Track per-tenant resource usage.

### Define Quotas

```python
from obskit import (
    QuotaTracker,
    QuotaPeriod,
    QuotaLimit,
    get_quota_tracker
)

quota = get_quota_tracker()

# Set tenant quota
quota.set_limit(
    tenant_id="tenant-123",
    resource="api_calls",
    limit=QuotaLimit(
        max_value=10000,
        period=QuotaPeriod.DAILY
    )
)

quota.set_limit(
    tenant_id="tenant-123",
    resource="storage_gb",
    limit=QuotaLimit(
        max_value=100,
        period=QuotaPeriod.MONTHLY
    )
)
```

### Track Usage

```python
# Record usage
quota.record_usage(
    tenant_id="tenant-123",
    resource="api_calls",
    amount=1
)

# Check if within quota
if quota.check_quota("tenant-123", "api_calls"):
    process_request()
else:
    raise QuotaExceededError("Daily API limit reached")
```

### Get Usage Report

```python
report = quota.get_report("tenant-123")

print(f"Tenant: {report.tenant_id}")
for resource in report.resources:
    print(f"  {resource.name}:")
    print(f"    Used: {resource.used}/{resource.limit}")
    print(f"    Remaining: {resource.remaining}")
    print(f"    Utilization: {resource.utilization:.1%}")
    print(f"    Resets at: {resource.reset_at}")
```

## Prometheus Metrics

All infrastructure features export Prometheus metrics:

```promql
# Connection pools
connection_pool_size{pool="main_db"}
connection_pool_used{pool="main_db"}
connection_pool_wait_time_seconds{pool="main_db"}

# DLQ
dlq_messages_total{queue="order_processing", reason="parse_error"}

# Consumer lag
consumer_lag_messages{queue="orders", consumer_group="order-processor"}
consumer_lag_seconds{queue="orders"}

# External API
external_api_requests_total{api="payment_gateway", status="success"}
external_api_latency_seconds{api="payment_gateway", quantile="0.99"}

# Memory
python_memory_heap_bytes
python_gc_collections_total

# Executors
executor_active_tasks{executor="worker_pool"}
executor_queued_tasks{executor="worker_pool"}
executor_task_duration_seconds{executor="worker_pool"}

# Quotas
tenant_quota_usage{tenant="tenant-123", resource="api_calls"}
tenant_quota_remaining{tenant="tenant-123", resource="api_calls"}
```

## Next Steps

- [Advanced Resilience](advanced-resilience.md) - Chaos engineering, self-healing
- [Debugging & Analysis](debugging.md) - Flame graphs, root cause analysis
- [Complete Feature Reference](../features/complete-reference.md) - All features
