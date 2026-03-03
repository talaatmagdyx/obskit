# Utility Modules

Specialized observability utilities for infrastructure, reliability, and operations. Each is independent — import only what you need.

---

## Connection Pool Metrics

`obskit.pools` — track utilization, checkout latency, and exhaustion for any connection pool.

```python
from obskit.pools import ConnectionPoolTracker, PoolType, get_pool_tracker
```

```python
# Get or create (singleton per name)
tracker = get_pool_tracker("postgres", pool_type=PoolType.DATABASE, max_size=20)

# Update pool state (call after fetching stats from your pool library)
tracker.set_pool_size(active=5, idle=12, max_size=20, wait_queue=0)

# Track a connection checkout
with tracker.track_checkout():
    conn = pool.getconn()
    cursor = conn.cursor()
    cursor.execute(query)

# Manual start/end (for callbacks)
start = tracker.track_checkout_start()
# ... get connection ...
tracker.track_checkout_end(start, success=True)

# Track errors
tracker.track_error("connection_timeout")

stats = tracker.get_stats()   # PoolStats dataclass
healthy = tracker.is_healthy()
```

**PoolType values:** `DATABASE`, `CACHE`, `QUEUE`, `HTTP`, `CUSTOM`

```python
# Multi-pool overview
from obskit.pools import get_all_pool_stats, check_all_pools_healthy

all_stats = get_all_pool_stats()
is_ok = check_all_pools_healthy()
```

!!! tip "Connecting to your pool library"
    obskit does not introspect pool internals. Call `set_pool_size()` manually with data from your library's public API (e.g. `pool.status()` for psycopg2, `client.connection_pool.max_connections` for redis-py).

**Metrics:** `pool_connections_active`, `pool_connections_idle`, `pool_connections_max`, `pool_utilization_ratio`, `pool_checkout_total`, `pool_checkout_latency_seconds`, `pool_errors_total`, `pool_wait_queue_size`, `pool_exhausted_total`

---

## Distributed Locking & Leader Election

`obskit.locking` — Redis-backed distributed locks and leader election with full observability. Requires `pip install "obskit[redis]"`.

```python
from obskit.locking import DistributedLock, LeaderElection, create_distributed_lock
```

### DistributedLock

```python
lock = create_distributed_lock(
    "process_report",
    redis_client=redis_client,
    ttl_seconds=30.0,
    max_wait_seconds=10.0,
)

# Sync context manager
with lock:
    generate_report()

# Async context manager
async with lock:
    await generate_report_async()

# Manual
acquired = lock.acquire(blocking=True)
if acquired:
    try:
        do_work()
    finally:
        lock.release()

# Extend TTL during long operations
lock.extend(additional_seconds=30.0)

# Inspect
lock.is_held()        # bool
lock.get_holder()     # str | None — returns holder's instance ID
```

### LeaderElection

```python
from obskit.locking import LeaderElection

election = LeaderElection(
    "scheduler",
    redis_client=redis_client,
    ttl_seconds=30.0,
    renewal_interval=10.0,   # renew leadership every 10s
)

# One-shot attempt
if election.try_become_leader():
    run_scheduler_tasks()

# Campaign loop (background thread)
election.start_campaign()   # keeps trying to become / stay leader
# ...
election.resign()
election.stop_campaign()

election.am_i_leader()      # bool
election.get_leader()       # str | None — current leader's ID
```

**Metrics:** `lock_acquisitions_total`, `lock_hold_time_seconds`, `lock_wait_time_seconds`, `lock_currently_held`, `leader_election_status`, `leader_election_terms_total`

---

## Tenant Quota Enforcement

`obskit.quota` — track and enforce per-tenant resource limits with burst support.

```python
from obskit.quota import QuotaTracker, QuotaPeriod, get_quota_tracker
```

```python
tracker = get_quota_tracker("api_requests", default_limit=10_000, default_period=QuotaPeriod.HOUR)

# Set per-tenant limits
tracker.set_limit(
    tenant_id="acme",
    resource="requests",
    limit=50_000,
    period=QuotaPeriod.HOUR,
    burst_limit=60_000,       # allow temporary burst
    soft_limit_percent=80.0,  # warn at 80%
)

# In request handler
allowed = tracker.check_and_increment("acme", resource="requests", allow_burst=True)
if not allowed:
    return Response(status=429, headers={"Retry-After": "3600"})

# Inspect
usage = tracker.get_usage("acme", "requests")
print(f"{usage.usage_percent:.1f}% used, {usage.remaining} remaining")

over = tracker.is_over_quota("acme", "requests")
report = tracker.get_report("acme")

# Reset (e.g. on period rollover)
tracker.reset_usage("acme")
```

**QuotaPeriod values:** `SECOND`, `MINUTE`, `HOUR`, `DAY`, `MONTH`

**Metrics:** `quota_usage`, `quota_limit`, `quota_usage_percent`, `quota_exceeded_total`, `quota_requests_total`

---

## Performance Budgets

`obskit.budgets` — enforce latency and error-rate constraints in code, not just dashboards.

```python
from obskit.budgets import PerformanceBudget, BudgetManager, budget, get_budget_manager
```

```python
# Define a budget
order_budget = PerformanceBudget(
    name="create_order",
    latency_p95_ms=200.0,
    latency_p99_ms=500.0,
    error_rate_percent=1.0,
    window_seconds=60,
    on_violation=lambda name, metric, value: alert(name, metric, value),
)

# Record observations
order_budget.record_success(latency_ms=45.2)
order_budget.record_error()

# Check
violations = order_budget.check_violations()  # list[str]
exceeded = order_budget.is_exceeded()
status = order_budget.get_status()            # BudgetStatus dataclass

# Enforce as decorator — raises if budget exceeded before call
@order_budget.enforce
def create_order(data):
    ...
```

### BudgetManager

```python
mgr = get_budget_manager()
mgr.register(order_budget)
mgr.register(PerformanceBudget("list_orders", latency_p95_ms=100.0))

all_statuses = mgr.check_all()
exceeded_names = mgr.get_exceeded_budgets()

# @budget decorator shorthand
@budget(order_budget)
def create_order(data):
    ...
```

**Metrics:** `budget_violations_total`, `budget_status`, `budget_utilization`

---

## Business KPI Metrics

`obskit.business` — track revenue, conversions, and engagement alongside technical metrics.

```python
from obskit.business import BusinessMetrics, FunnelTracker
```

```python
biz = BusinessMetrics("my-service")

# Events
biz.track_event("email_sent", tenant_id="acme", channel="smtp", count=1)

# Revenue
biz.track_revenue("subscription", amount=99.0, currency="USD", tenant_id="acme")

# Conversions
biz.track_conversion("onboarding", tenant_id="acme", stage="completed")

# Engagement (timed)
with biz.track_engagement("view_dashboard", tenant_id="acme", user_id="u-123"):
    render_dashboard()

# Active users
biz.track_active_user(tenant_id="acme", user_id="u-123", period="daily")

# Feature usage
biz.track_feature_usage("bulk_export", tenant_id="acme", count=1)

# Arbitrary gauge
biz.set_value("active_subscriptions", value=1547, tenant_id="acme")
```

### FunnelTracker

```python
funnel = FunnelTracker("onboarding", stages=["signup", "verify", "profile", "done"])

funnel.enter(user_id="u-123")
funnel.progress(user_id="u-123", stage="verify")
funnel.progress(user_id="u-123", stage="profile")
funnel.complete(user_id="u-123")
# or
funnel.drop(user_id="u-456", reason="no_verify_email")

rates = funnel.get_conversion_rates()
# {"signup→verify": 0.72, "verify→profile": 0.88, ...}
```

**Metrics:** `business_events_total`, `business_revenue_total`, `business_conversions_total`, `business_engagement_duration_seconds`, `business_value`, `active_users`, `feature_usage_total`

---

## Latency Breakdown

`obskit.breakdown` — identify which phase of an operation takes the most time.

```python
from obskit.breakdown import LatencyBreakdown, track_breakdown
```

```python
with LatencyBreakdown("process_order", alert_bottleneck_percent=70.0) as bd:
    with bd.phase("validate"):
        validate(data)
    with bd.phase("db_write"):
        save_to_db(data)
    with bd.phase("notify"):
        send_email(data)

summary = bd.get_summary()
# BreakdownSummary(operation="process_order", total_ms=123.4,
#   bottleneck="db_write", phases=[...])

waterfall = bd.get_waterfall_data()
# [{"phase": "validate", "duration_ms": 2.1, "percent": 1.7}, ...]
```

**Metrics:** `breakdown_phase_duration_seconds`, `breakdown_total_duration_seconds`, `breakdown_phase_percent`

---

## Hot Path Detection

`obskit.hot_path` — automatically identify the most-called, highest-impact code paths.

```python
from obskit.hot_path import HotPathDetector, track_path, get_hot_path_detector
```

```python
detector = get_hot_path_detector(
    hot_path_threshold=100,    # paths called > 100x are "hot"
    impact_threshold=1000.0,   # paths with impact score > 1000
    window_minutes=60,
)

# As context manager
with detector.track("orders.create", caller="api.post_order"):
    create_order(data)

# As decorator
@track_path("orders.list", detector=detector)
def list_orders(tenant_id: str):
    ...

# Inspect
hot_paths = detector.get_hot_paths(limit=10)
for path in hot_paths:
    print(f"{path.path}: {path.call_count} calls, impact={path.impact_score:.0f}")

stats = detector.get_path_stats("orders.create")
call_graph = detector.get_call_graph()   # {caller: {callee: count}}
```

**Metrics:** `hot_path_calls_total`, `hot_path_latency_seconds`, `hot_path_impact`

---

## Error Fingerprinting

`obskit.fingerprint` — automatically group similar exceptions to reduce noise.

```python
from obskit.fingerprint import ErrorFingerprinter, get_error_fingerprinter
```

```python
fp = get_error_fingerprinter("my-service")

try:
    process()
except Exception as e:
    group = fp.record_error(e, component="order_processor", operation="create")
    print(f"Error group: {group.fingerprint}")
    print(f"Occurrences: {group.count}")
    print(f"First seen: {group.first_seen}")

# Inspect
top_errors = fp.get_top_errors(limit=10)
recent = fp.get_recent_errors(limit=5)
group = fp.get_group(fingerprint="abc123")
all_groups = fp.get_all_groups()
```

```python
# Convenience functions (global fingerprinter)
from obskit.fingerprint import get_fingerprint, get_error_group

fingerprint_str = get_fingerprint(exception)
group = get_error_group(exception, component="api")
```

**Metrics:** `error_groups_total`, `error_occurrences_total`, `error_group_size`

---

## Query Plan Analyzer

`obskit.query_analyzer` — parse and track database query execution plans for optimization.

```python
from obskit.query_analyzer import QueryAnalyzer, get_query_analyzer
```

```python
analyzer = get_query_analyzer(
    "postgres",
    slow_query_threshold_ms=100.0,
    high_cost_threshold=1000.0,
)

# Analyze a query (with optional EXPLAIN output and actual timing)
analysis = analyzer.analyze(
    query="SELECT * FROM orders WHERE tenant_id = $1",
    explain_output=explain_text,   # from EXPLAIN ANALYZE
    actual_time_ms=45.2,
)

print(f"Query type: {analysis.query_type.name}")
print(f"Has seq scan: {analysis.has_sequential_scan}")
print(f"Missing index: {analysis.missing_index_hint}")
print(f"Estimated cost: {analysis.estimated_cost}")

# Retrieve slow queries seen so far
slow = analyzer.get_slow_queries(limit=10)
past = analyzer.get_analysis(query_hash="abc123")
```

**Metrics:** `queries_analyzed_total`, `query_plan_cost`, `slow_queries_total`, `missing_index_detected_total`

---

## Service Dependency Graph

`obskit.dependency_graph` — track and visualize runtime service dependencies.

```python
from obskit.dependency_graph import DependencyGraph, DependencyType, HealthStatus, get_dependency_graph
```

```python
graph = get_dependency_graph("order-service")

# Register dependencies
graph.add_dependency("postgres",  DependencyType.DATABASE,  endpoint="postgres:5432", is_critical=True)
graph.add_dependency("redis",     DependencyType.CACHE,     endpoint="redis:6379")
graph.add_dependency("rabbitmq",  DependencyType.QUEUE,     endpoint="rabbitmq:5672", is_critical=True)
graph.add_dependency("email-api", DependencyType.HTTP,      endpoint="https://api.mailservice.com")

# Record each call (automatically tracks health + latency)
graph.record_call("postgres", latency_ms=12.4, success=True)
graph.record_call("redis",    latency_ms=0.8,  success=True)

# Manual health override
graph.update_health("email-api", HealthStatus.DEGRADED, latency_ms=450.0)

# Inspect
unhealthy = graph.get_unhealthy_dependencies()
critical_path = graph.get_critical_path()   # list of critical dep names
ok = graph.is_healthy()

# Dashboard / visualization data
viz = graph.get_visualization_data()
# GraphVisualization with .nodes, .edges, .to_dict()
```

**DependencyType values:** `DATABASE`, `CACHE`, `QUEUE`, `HTTP`, `GRPC`, `CUSTOM`

**Metrics:** `dependency_status`, `dependency_latency_seconds`, `dependency_calls_total`, `dependency_count`

---

## Circuit Breaker Dashboard

`obskit.circuit_dashboard` — export all circuit breaker states for a unified dashboard.

```python
from obskit.circuit_dashboard import (
    get_circuit_dashboard, register_circuit_breaker, get_all_circuit_states
)
```

```python
# Register breakers from obskit.resilience
from obskit.resilience import CircuitBreaker

db_breaker = CircuitBreaker("postgres")
mq_breaker = CircuitBreaker("rabbitmq")

register_circuit_breaker("postgres",  db_breaker, dependency_type="database")
register_circuit_breaker("rabbitmq",  mq_breaker, dependency_type="queue")

# Dashboard snapshot
dashboard = get_circuit_dashboard()
data = dashboard.get_all_states()
# DashboardData with .services, .total, .open_count, .to_dict()

open_breakers = dashboard.get_open_breakers()   # list of names
all_healthy   = dashboard.is_all_healthy()

status = dashboard.get_breaker_status("postgres")
# CircuitBreakerStatus(name, state, failure_count, ...)

# Global helper
all_states = get_all_circuit_states()
```

**Metrics:** `circuit_state`, `circuit_failures_total`, `circuit_success_count`

---

## Alert Deduplication

`obskit.alert_dedup` — suppress duplicate alerts to prevent on-call fatigue.

```python
from obskit.alert_dedup import AlertDeduplicator, get_alert_deduplicator, should_alert
```

```python
dedup = get_alert_deduplicator(
    window_minutes=15,
    max_alerts_per_window=3,
    severity_cooldowns={"critical": 5, "warning": 30},   # minutes
)

# In your alert logic
if dedup.should_alert("high_error_rate", severity="critical"):
    send_pagerduty_alert(...)

# Programmatic suppression (e.g. during maintenance)
dedup.add_suppression("high_error_rate", duration_minutes=60, severity="warning")
dedup.clear_suppression("high_error_rate")

active    = dedup.get_active_alerts()      # list[AlertRecord]
suppressed = dedup.get_suppressed_alerts() # dict[key, datetime]
dedup.cleanup()  # purge expired entries
```

```python
# Convenience (uses global deduplicator)
from obskit.alert_dedup import should_alert

if should_alert("db_connection_error", severity="critical"):
    notify_ops()
```

**Metrics:** `alerts_total`, `alerts_deduplicated_total`, `alerts_active`, `alert_group_size`

---

## External API SLA Tracking

`obskit.external` — track SLA compliance of third-party APIs you depend on.

```python
from obskit.external import ExternalAPISLATracker, get_external_api_tracker, get_all_api_compliance
```

```python
tracker = get_external_api_tracker(
    "openai",
    expected_availability=0.999,
    expected_latency_p95_ms=2000,
    expected_latency_p99_ms=5000,
    expected_error_rate_percent=0.5,
    window_seconds=3600,
    on_sla_breach=lambda api, metric, value: alert_vendor_sla(api, metric, value),
)

# Track via context manager
with tracker.track_call(method="POST"):
    response = openai.chat.completions.create(...)

# Manual recording
tracker.record_call(
    latency_seconds=1.2,
    success=response.status_code == 200,
    method="POST",
    status_code=response.status_code,
)

# Update expected SLA (e.g. after vendor SLA change)
tracker.set_expected_sla(latency_p95_ms=3000)

# Compliance report
report = tracker.get_compliance_report()
print(f"Availability: {report.current_availability:.3%}")
print(f"P95 latency: {report.p95_latency_ms:.0f}ms")
print(f"SLA compliant: {report.is_compliant}")

# All vendors at once
all_reports = get_all_api_compliance()
```

**Metrics:** `external_api_requests_total`, `external_api_latency_seconds`, `external_api_errors_total`, `external_api_availability`, `external_api_latency_p95`, `external_api_sla_compliant`, `external_api_sla_breaches_total`
