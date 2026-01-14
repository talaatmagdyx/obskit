# Multi-Tenancy Guide

Multi-tenant applications serve multiple customers from a single deployment.
obskit provides per-tenant observability to ensure visibility into each tenant's experience.

## Why Per-Tenant Metrics?

### The Problem

Aggregate metrics hide tenant-specific issues:

```
Overall error rate: 0.5% ✓
Overall latency p99: 150ms ✓

But hidden inside:
- Tenant A: 0.1% errors, 100ms p99 ✓
- Tenant B: 15% errors, 2000ms p99 ✗ ← Invisible!
```

Tenant B is having a terrible experience, but aggregate metrics look fine.

### The Solution

Per-tenant metrics expose individual tenant health:

```
tenant_a_error_rate: 0.1%
tenant_a_latency_p99: 100ms

tenant_b_error_rate: 15%  ← Alert triggers!
tenant_b_latency_p99: 2000ms  ← Alert triggers!
```

## Basic Usage

### Tenant RED Metrics

```python
from obskit.metrics import TenantREDMetrics

metrics = TenantREDMetrics(service_name="saas_api")

def handle_request(tenant_id: str):
    with metrics.track_request(
        endpoint="/api/data",
        method="GET",
        tenant_id=tenant_id,
    ):
        return get_tenant_data(tenant_id)
```

### Context-Based Tenant ID

```python
from obskit.metrics import tenant_metrics_context, set_tenant_id, get_tenant_id

# Set tenant ID from request context
@app.middleware("http")
async def tenant_middleware(request, call_next):
    tenant_id = request.headers.get("X-Tenant-ID")
    set_tenant_id(tenant_id)
    return await call_next(request)

# Metrics automatically use the context tenant
def process_data():
    tenant_id = get_tenant_id()
    with metrics.track_request(endpoint="/process", tenant_id=tenant_id):
        do_work()
```

## Prometheus Output

```text
# HELP saas_api_requests_total Total requests by tenant
# TYPE saas_api_requests_total counter
saas_api_requests_total{tenant_id="acme_corp",endpoint="/api/data",status="success"} 1500
saas_api_requests_total{tenant_id="acme_corp",endpoint="/api/data",status="error"} 15
saas_api_requests_total{tenant_id="globex",endpoint="/api/data",status="success"} 3200
saas_api_requests_total{tenant_id="globex",endpoint="/api/data",status="error"} 480

# HELP saas_api_request_duration_seconds Request duration by tenant
# TYPE saas_api_request_duration_seconds histogram
saas_api_request_duration_seconds_bucket{tenant_id="acme_corp",le="0.1"} 1400
saas_api_request_duration_seconds_bucket{tenant_id="globex",le="0.1"} 2800
```

## Tenant-Aware Logging

```python
from obskit import configure_logging
from obskit.core import set_tenant_id

logger = configure_logging(service_name="api")

@app.middleware("http")
async def add_tenant_context(request, call_next):
    tenant_id = get_tenant_from_request(request)
    set_tenant_id(tenant_id)
    
    # All logs automatically include tenant_id
    response = await call_next(request)
    return response

# Later in your code
logger.info("Processing order", order_id=order.id)
# Output includes: {"tenant_id": "acme_corp", "order_id": "ord_123", ...}
```

## Tenant-Aware Tracing

```python
from obskit import get_tracer

tracer = get_tracer()

def process_tenant_request(tenant_id: str):
    with tracer.start_as_current_span("process_request") as span:
        span.set_attribute("tenant.id", tenant_id)
        span.set_attribute("tenant.plan", get_tenant_plan(tenant_id))
        
        # Nested spans inherit tenant context
        with tracer.start_as_current_span("database_query"):
            query_database()
```

## Alerting

### Per-Tenant SLO Alerts

```yaml
# prometheus/alerts.yml
groups:
  - name: tenant_slos
    rules:
      - alert: TenantHighErrorRate
        expr: |
          sum by (tenant_id) (
            rate(saas_api_requests_total{status="error"}[5m])
          ) / sum by (tenant_id) (
            rate(saas_api_requests_total[5m])
          ) > 0.01
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High error rate for tenant {{ $labels.tenant_id }}"
          description: "Error rate is {{ $value | humanizePercentage }}"

      - alert: TenantHighLatency
        expr: |
          histogram_quantile(0.99,
            sum by (tenant_id, le) (
              rate(saas_api_request_duration_seconds_bucket[5m])
            )
          ) > 1.0
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High latency for tenant {{ $labels.tenant_id }}"
```

### Noisy Neighbor Detection

```yaml
- alert: NoisyNeighbor
  expr: |
    sum by (tenant_id) (rate(saas_api_requests_total[5m]))
    /
    sum(rate(saas_api_requests_total[5m]))
    > 0.5
  for: 10m
  labels:
    severity: info
  annotations:
    summary: "Tenant {{ $labels.tenant_id }} using >50% of capacity"
```

## Resource Isolation

### Per-Tenant Rate Limiting

```python
from obskit.resilience import RateLimiter

# Per-tenant rate limiters
tenant_limiters: dict[str, RateLimiter] = {}

def get_tenant_limiter(tenant_id: str, plan: str) -> RateLimiter:
    if tenant_id not in tenant_limiters:
        # Different limits based on plan
        limits = {
            "free": (10, 5),      # 10/s, burst 5
            "pro": (100, 20),     # 100/s, burst 20
            "enterprise": (1000, 100),  # 1000/s, burst 100
        }
        rate, burst = limits.get(plan, limits["free"])
        tenant_limiters[tenant_id] = RateLimiter(rate=rate, burst=burst)
    
    return tenant_limiters[tenant_id]

async def handle_request(tenant_id: str, plan: str):
    limiter = get_tenant_limiter(tenant_id, plan)
    
    if not await limiter.acquire():
        metrics.track_request(
            endpoint="/api",
            tenant_id=tenant_id,
            status="rate_limited",
        )
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
```

### Per-Tenant Circuit Breakers

```python
from obskit import CircuitBreaker

# Isolate failures per tenant
tenant_breakers: dict[str, CircuitBreaker] = {}

def get_tenant_breaker(tenant_id: str) -> CircuitBreaker:
    if tenant_id not in tenant_breakers:
        tenant_breakers[tenant_id] = CircuitBreaker(
            failure_threshold=5,
            recovery_timeout=30.0,
        )
    return tenant_breakers[tenant_id]

async def call_tenant_api(tenant_id: str):
    breaker = get_tenant_breaker(tenant_id)
    async with breaker:
        return await external_api.call(tenant_id)
```

## Dashboards

### Per-Tenant Dashboard

```python
from obskit.slo import generate_grafana_dashboard

# Generate per-tenant dashboard
dashboard = generate_grafana_dashboard(
    title="Tenant Health",
    variables=[
        {"name": "tenant_id", "query": "label_values(saas_api_requests_total, tenant_id)"},
    ],
    panels=[
        {
            "title": "Request Rate",
            "query": 'sum(rate(saas_api_requests_total{tenant_id="$tenant_id"}[5m]))',
        },
        {
            "title": "Error Rate",
            "query": '''
                sum(rate(saas_api_requests_total{tenant_id="$tenant_id",status="error"}[5m]))
                /
                sum(rate(saas_api_requests_total{tenant_id="$tenant_id"}[5m]))
            ''',
        },
        {
            "title": "P99 Latency",
            "query": '''
                histogram_quantile(0.99,
                    sum(rate(saas_api_request_duration_seconds_bucket{tenant_id="$tenant_id"}[5m])) by (le)
                )
            ''',
        },
    ],
)
```

## Best Practices

### 1. Always Include Tenant ID

```python
# Good: explicit tenant context
with metrics.track_request(endpoint="/api", tenant_id=tenant_id):
    process()

# Bad: missing tenant context
with metrics.track_request(endpoint="/api"):  # Which tenant?
    process()
```

### 2. Limit Cardinality

```python
# Good: bounded tenant IDs
tenant_id = request.headers.get("X-Tenant-ID", "unknown")

# Bad: unbounded (could be user IDs)
tenant_id = request.user_id  # Could be millions of values!
```

### 3. Plan-Based Defaults

```python
# Different SLOs for different plans
TENANT_SLOS = {
    "free": {"availability": 0.99, "latency_p99_ms": 1000},
    "pro": {"availability": 0.999, "latency_p99_ms": 500},
    "enterprise": {"availability": 0.9999, "latency_p99_ms": 200},
}

def get_tenant_slo(tenant_id: str) -> dict:
    plan = get_tenant_plan(tenant_id)
    return TENANT_SLOS[plan]
```

### 4. Tenant-Aware Error Budgets

```python
from obskit.slo import SLOTracker

# Per-tenant SLO tracking
tenant_slos: dict[str, SLOTracker] = {}

def get_tenant_slo_tracker(tenant_id: str) -> SLOTracker:
    if tenant_id not in tenant_slos:
        slo_config = get_tenant_slo(tenant_id)
        tenant_slos[tenant_id] = SLOTracker(
            name=f"{tenant_id}_availability",
            target=slo_config["availability"],
            window_days=30,
        )
    return tenant_slos[tenant_id]
```

## Common Issues

### High Cardinality

Too many tenants can cause Prometheus memory issues:

```python
# Solution: Use recording rules for aggregation
# prometheus/rules.yml
groups:
  - name: tenant_aggregations
    rules:
      - record: tenant:requests:rate5m
        expr: sum by (tenant_id) (rate(saas_api_requests_total[5m]))
```

### Missing Tenant Context

Ensure tenant ID flows through async operations:

```python
from contextvars import ContextVar

tenant_var: ContextVar[str] = ContextVar("tenant_id", default="unknown")

# Set in middleware
tenant_var.set(tenant_id)

# Automatically propagates through async/await
async def nested_function():
    current_tenant = tenant_var.get()  # Still has the tenant ID
```

## Next Steps

- **[Metrics Guide](metrics.md)** - Core metrics concepts
- **[SLO Tracking](slo.md)** - Define per-tenant SLOs
- **[Examples](../examples/fastapi.md)** - Complete multi-tenant example

