# Metrics Guide

obskit provides three metrics methodologies: **RED**, **Golden Signals**, and **USE**.
This guide explains how to implement each.

## RED Method

The RED method tracks **R**ate, **E**rrors, and **D**uration for request-driven services.

### Basic Usage

```python
from obskit import get_red_metrics

# Get or create RED metrics for your service
metrics = get_red_metrics(service_name="user_service")

# Track a request using context manager
with metrics.track_request(endpoint="/api/users", method="GET"):
    users = database.get_users()
    return users

# Or with explicit status
with metrics.track_request(endpoint="/api/users", method="POST") as ctx:
    try:
        user = create_user(data)
        ctx.set_status("success")
    except ValidationError:
        ctx.set_status("error")
        raise
```

### Decorator Usage

```python
@metrics.track(endpoint="/api/orders", method="POST")
def create_order(order_data: dict) -> Order:
    return Order.create(**order_data)

# Async support
@metrics.track(endpoint="/api/orders", method="GET")
async def get_orders() -> list[Order]:
    return await Order.list()
```

### What Gets Recorded

| Metric Name | Type | Labels | Description |
|-------------|------|--------|-------------|
| `{service}_requests_total` | Counter | endpoint, method, status | Total requests |
| `{service}_request_duration_seconds` | Histogram | endpoint, method | Request duration |
| `{service}_requests_in_progress` | Gauge | endpoint, method | Current active requests |

### Prometheus Output

```text
# HELP user_service_requests_total Total number of requests
# TYPE user_service_requests_total counter
user_service_requests_total{endpoint="/api/users",method="GET",status="success"} 1523
user_service_requests_total{endpoint="/api/users",method="GET",status="error"} 12

# HELP user_service_request_duration_seconds Request duration in seconds
# TYPE user_service_request_duration_seconds histogram
user_service_request_duration_seconds_bucket{endpoint="/api/users",method="GET",le="0.01"} 1200
user_service_request_duration_seconds_bucket{endpoint="/api/users",method="GET",le="0.1"} 1500
user_service_request_duration_seconds_bucket{endpoint="/api/users",method="GET",le="1.0"} 1520
```

## Golden Signals

For services where saturation is important.

### Basic Usage

```python
from obskit.metrics import GoldenSignals

signals = GoldenSignals(service_name="order_service")

# Track latency and traffic (like RED)
with signals.track_request(endpoint="/orders"):
    process_order()

# Additionally track saturation
signals.set_saturation("queue_depth", pending_orders.count())
signals.set_saturation("memory_percent", psutil.virtual_memory().percent / 100)
```

### Saturation Examples

```python
# Database connection pool
signals.set_saturation("db_pool", active_connections / max_connections)

# Worker threads
signals.set_saturation("workers", busy_workers / total_workers)

# Request queue
signals.set_saturation("request_queue", queue.qsize() / queue.maxsize)
```

## USE Method

For monitoring resources like databases, caches, and infrastructure.

### Basic Usage

```python
from obskit.metrics import USEMetrics

# Monitor a database connection pool
db_pool = USEMetrics(resource_name="postgres_pool")

# Utilization: what fraction of the resource is busy
db_pool.set_utilization(active_connections / max_connections)

# Saturation: work waiting to be processed
db_pool.set_saturation(waiting_connections)

# Errors: error events
db_pool.increment_errors()
```

### Common USE Patterns

```python
# CPU monitoring
cpu = USEMetrics(resource_name="cpu")
cpu.set_utilization(psutil.cpu_percent() / 100)
cpu.set_saturation(os.getloadavg()[0])  # 1-min load average

# Memory monitoring
memory = USEMetrics(resource_name="memory")
mem = psutil.virtual_memory()
memory.set_utilization(mem.percent / 100)
memory.set_saturation(mem.available)  # bytes available

# Disk monitoring
disk = USEMetrics(resource_name="disk")
disk_usage = psutil.disk_usage("/")
disk.set_utilization(disk_usage.percent / 100)
```

## Metrics Sampling

For high-throughput services, record only a sample of metrics.

### Configuration

```python
from obskit import configure
from obskit.config import ObskitSettings

# Configure 10% sampling
settings = ObskitSettings(
    metrics_sample_rate=0.1,  # 10% of requests
)

metrics = get_red_metrics(
    service_name="high_traffic_service",
    sample_rate=0.1,
)
```

### Per-Request Sampling

```python
import random

# Sample only some requests
if random.random() < 0.1:  # 10% sampling
    with metrics.track_request(...):
        process()
else:
    process()  # No metrics overhead
```

## Custom Histogram Buckets

Customize latency buckets for your service's characteristics.

```python
from obskit.metrics import REDMetrics

# For a fast API (most responses < 100ms)
fast_api_metrics = REDMetrics(
    service_name="fast_api",
    duration_buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
)

# For batch processing (responses in seconds to minutes)
batch_metrics = REDMetrics(
    service_name="batch_processor",
    duration_buckets=[1, 5, 10, 30, 60, 120, 300, 600],
)
```

## Tenant Metrics

For multi-tenant applications.

```python
from obskit.metrics import TenantREDMetrics

metrics = TenantREDMetrics(service_name="saas_api")

# Track per-tenant
with metrics.track_request(
    endpoint="/api/data",
    method="GET",
    tenant_id="acme_corp",
):
    data = get_tenant_data()
```

### Prometheus Output

```text
saas_api_requests_total{endpoint="/api/data",method="GET",tenant_id="acme_corp",status="success"} 500
saas_api_requests_total{endpoint="/api/data",method="GET",tenant_id="globex",status="success"} 1200
```

## Async Metrics Recording

For ultra-high-throughput services, record metrics asynchronously.

```python
from obskit.metrics import AsyncREDMetrics

# Creates background worker for metric updates
async_metrics = AsyncREDMetrics(service_name="high_throughput")

# Metrics are queued and recorded in background
async_metrics.observe_request(
    endpoint="/api/events",
    method="POST",
    status="success",
    duration=0.005,
)
```

## Exporting Metrics

### HTTP Server

```python
from obskit import start_http_server

# Start Prometheus metrics server
start_http_server(port=9090)
# Metrics available at http://localhost:9090/metrics
```

### Push Gateway

```python
from prometheus_client import push_to_gateway

# For batch jobs that don't run continuously
push_to_gateway(
    "http://pushgateway:9091",
    job="batch_job",
    registry=get_registry(),
)
```

## Best Practices

### 1. Use Consistent Naming

```python
# Good: snake_case, includes service name
metrics = get_red_metrics(service_name="user_service")

# Bad: inconsistent naming
metrics = get_red_metrics(service_name="UserService")
```

### 2. Limit Cardinality

```python
# Good: bounded set of values
endpoint = normalize_endpoint(request.path)  # "/users/{id}" not "/users/12345"

# Bad: unbounded cardinality
endpoint = request.path  # Creates new time series for each user ID
```

### 3. Track What Matters

```python
# Good: business-meaningful metrics
with metrics.track_request(endpoint="/orders", method="POST"):
    create_order()

# Avoid: internal implementation details
with metrics.track_request(endpoint="/internal/cache/refresh"):
    refresh_cache()  # This is noise, not signal
```

## Next Steps

- **[Tracing Guide](tracing.md)** - Add distributed tracing
- **[SLO Tracking](slo.md)** - Define reliability targets
- **[Performance Guide](../performance/index.md)** - Optimize metrics collection

