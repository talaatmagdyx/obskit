# Advanced Resilience (v1.3.0)

obskit v1.3.0 introduces advanced resilience patterns for production systems.

## Chaos Engineering

Inject failures to test system resilience.

### Setup

```python
from obskit import (
    ChaosEngine,
    get_chaos_engine,
    enable_chaos,
    disable_chaos,
    InjectionType
)

# Get the chaos engine
chaos = get_chaos_engine()
```

### Latency Injection

```python
# Add latency to database calls
chaos.add_experiment(
    name="slow_database",
    injection_type=InjectionType.LATENCY,
    latency_ms=500,           # 500ms delay
    probability=0.1,          # 10% of requests
    duration_minutes=30       # Run for 30 minutes
)

# Use in your code
async def query_database():
    if chaos.should_inject("slow_database"):
        await asyncio.sleep(chaos.get_latency("slow_database") / 1000)
    return await db.execute(query)
```

### Error Injection

```python
# Inject errors into payment processing
chaos.add_experiment(
    name="payment_failure",
    injection_type=InjectionType.ERROR,
    probability=0.05,
    error_class=PaymentError,
    error_message="Simulated payment failure"
)

# Decorator usage
from obskit import chaos_injection

@chaos_injection("payment_failure")
async def process_payment(amount):
    return await payment_gateway.charge(amount)
```

### Enable/Disable Chaos

```python
# Enable chaos experiments (only in non-production!)
if os.getenv("CHAOS_ENABLED") == "true":
    enable_chaos()

# Disable when done
disable_chaos()
```

## Graceful Degradation

Automatically disable features under load.

### Setup

```python
from obskit import (
    DegradationManager,
    DegradationLevel,
    get_degradation_manager
)

degradation = get_degradation_manager()
```

### Register Features

```python
# Priority: lower = more important (degrade last)
degradation.register_feature(
    name="recommendations",
    priority=2,
    fallback=lambda: cached_recommendations(),
    degradation_threshold=50  # Disable at 50% degradation
)

degradation.register_feature(
    name="analytics",
    priority=1,  # Less important
    fallback=lambda: None,
    degradation_threshold=25  # Disable earlier
)

degradation.register_feature(
    name="search_suggestions",
    priority=3,  # Most important non-core feature
    fallback=lambda: [],
    degradation_threshold=75
)
```

### Use in Code

```python
async def get_product_page(product_id: str):
    product = await get_product(product_id)  # Always runs
    
    # Check if recommendations are enabled
    if degradation.is_enabled("recommendations"):
        product.recommendations = await get_recommendations(product_id)
    else:
        product.recommendations = degradation.get_fallback("recommendations")()
    
    # Check analytics
    if degradation.is_enabled("analytics"):
        await track_page_view(product_id)
    
    return product
```

### Set Degradation Level

```python
# Manual degradation
degradation.set_level(DegradationLevel.MEDIUM)  # 50%

# Automatic degradation based on metrics
degradation.auto_degrade(
    metric_name="cpu_usage",
    threshold=0.8,  # When CPU > 80%
    level=DegradationLevel.HIGH
)

# Degradation levels
# - NONE (0%) - All features enabled
# - LOW (25%) - Priority 1 features disabled
# - MEDIUM (50%) - Priority 1-2 features disabled
# - HIGH (75%) - Priority 1-3 features disabled
# - CRITICAL (100%) - Only core functionality
```

## Self-Healing

Automatic remediation for common issues.

### Setup

```python
from obskit import (
    SelfHealingEngine,
    HealingResult,
    get_self_healing_engine
)

healer = get_self_healing_engine()
```

### Register Healing Triggers

```python
# Restart worker on high error rate
healer.register_trigger(
    name="high_error_rate",
    condition=lambda: get_error_rate() > 0.5,  # 50% error rate
    action=restart_worker,
    cooldown_minutes=5,
    max_executions_per_hour=3,
    description="Restart worker when error rate exceeds 50%"
)

# Reset connection pool when exhausted
healer.register_trigger(
    name="connection_pool_exhausted",
    condition=lambda: connection_pool.available == 0,
    action=reset_connection_pool,
    cooldown_minutes=2,
    max_executions_per_hour=6
)

# Clear cache on memory pressure
healer.register_trigger(
    name="memory_pressure",
    condition=lambda: get_memory_usage() > 0.9,  # 90% memory
    action=clear_application_cache,
    cooldown_minutes=10,
    max_executions_per_hour=2
)
```

### Evaluate Triggers

```python
# Manual evaluation
results = healer.evaluate()
for trigger_name, result in results.items():
    if result == HealingResult.SUCCESS:
        logger.info(f"Healing action executed: {trigger_name}")
    elif result == HealingResult.COOLDOWN:
        logger.debug(f"Trigger in cooldown: {trigger_name}")

# Continuous evaluation (background task)
healer.start_evaluation_loop(interval_seconds=30)
```

## Load Shedding

Gracefully reject requests under load.

### Setup

```python
from obskit import (
    LoadShedder,
    Priority,
    SheddingConfig,
    get_load_shedder
)

shedder = LoadShedder(
    config=SheddingConfig(
        max_concurrent=1000,   # Max concurrent requests
        high_water_mark=0.8,   # Start shedding at 80%
        low_water_mark=0.6     # Stop shedding at 60%
    )
)
```

### Check Before Processing

```python
from fastapi import FastAPI, HTTPException

app = FastAPI()

@app.post("/api/orders")
async def create_order(order: OrderCreate):
    # Check if we should accept this request
    if not shedder.should_accept(priority=Priority.HIGH):
        raise HTTPException(
            status_code=503,
            detail="Service temporarily unavailable",
            headers={"Retry-After": "5"}
        )
    
    with shedder.track():
        return await process_order(order)

@app.get("/api/recommendations")
async def get_recommendations():
    # Low priority - shed first
    if not shedder.should_accept(priority=Priority.LOW):
        return {"recommendations": [], "cached": True}
    
    with shedder.track():
        return await compute_recommendations()
```

### Priority Levels

```python
# Priority levels (shed LOW first, HIGH last)
Priority.LOW      # Non-critical features
Priority.NORMAL   # Standard requests
Priority.HIGH     # Important operations
Priority.CRITICAL # Never shed (auth, health checks)
```

## Failover Coordinator

Manage primary/backup failover.

### Setup

```python
from obskit import (
    FailoverCoordinator,
    FailoverState,
    get_failover_coordinator
)

failover = get_failover_coordinator()
```

### Register Primary and Backup

```python
# Register primary
failover.register_primary(
    name="primary_db",
    health_check=lambda: primary_db.ping(),
    endpoint="db-primary:5432"
)

# Register backup(s)
failover.register_backup(
    name="backup_db_1",
    health_check=lambda: backup_db_1.ping(),
    endpoint="db-backup-1:5432",
    priority=1  # First backup to try
)

failover.register_backup(
    name="backup_db_2",
    health_check=lambda: backup_db_2.ping(),
    endpoint="db-backup-2:5432",
    priority=2  # Second backup
)
```

### Get Active Endpoint

```python
# Get currently active endpoint
active = failover.get_active_endpoint()
connection = connect_to(active)
```

### Enable Auto-Failover

```python
# Automatic failover based on health
failover.enable_auto_failover(
    check_interval_seconds=10,
    failure_threshold=3  # Failover after 3 failed health checks
)
```

### Manual Failover

```python
# Trigger manual failover (e.g., for maintenance)
failover.trigger_failover(reason="maintenance")

# Failback to primary when ready
failover.trigger_failback()
```

## Best Practices

### 1. Start Conservative

```python
# Start with conservative thresholds
chaos.add_experiment(
    name="test_latency",
    probability=0.01,  # Start with 1%
    latency_ms=100
)

# Gradually increase
chaos.update_experiment("test_latency", probability=0.1)
```

### 2. Monitor Everything

```python
# All these features emit Prometheus metrics
# chaos_injections_total
# degradation_level
# self_healing_actions_executed_total
# load_shedder_requests_rejected_total
# failover_state
```

### 3. Have Kill Switches

```python
# Environment-based kill switches
if os.getenv("CHAOS_ENABLED") != "true":
    chaos.disable_all()

if os.getenv("SELF_HEALING_ENABLED") != "true":
    healer.disable_all()
```

### 4. Test in Staging First

```python
# Only enable chaos in specific environments
if environment in ["staging", "chaos-testing"]:
    enable_chaos()
```

## Next Steps

- [Debugging & Analysis](debugging.md) - Flame graphs, root cause analysis
- [Infrastructure Monitoring](infrastructure.md) - Pool metrics, DLQ tracking
- [Complete Feature Reference](../features/complete-reference.md) - All features
