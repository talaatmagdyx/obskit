# obskit Complete Feature Reference

**Version:** 1.3.0  
**Last Updated:** 2026-01-19  
**Total Features:** 52+

---

## Table of Contents

1. [Core Observability](#1-core-observability)
   - [Metrics (RED, Golden Signals, USE)](#11-metrics)
   - [Logging](#12-logging)
   - [Tracing](#13-tracing)
2. [Health & Resilience](#2-health--resilience)
   - [Health Checks](#21-health-checks)
   - [Circuit Breaker](#22-circuit-breaker)
   - [Retry & Rate Limiting](#23-retry--rate-limiting)
   - [Load Shedding](#24-load-shedding)
3. [SLO & Error Budgets](#3-slo--error-budgets)
4. [Framework Integration](#4-framework-integration)
5. [Advanced Resilience](#5-advanced-resilience)
6. [Debugging & Analysis](#6-debugging--analysis)
7. [Infrastructure Monitoring](#7-infrastructure-monitoring)
8. [Security & Compliance](#8-security--compliance)
9. [Operations & Incident Management](#9-operations--incident-management)
10. [Testing Utilities](#10-testing-utilities)

---

## 1. Core Observability

### 1.1 Metrics

obskit implements three industry-standard metrics methodologies:

#### RED Metrics (Request-driven)

Rate, Errors, Duration - ideal for API services.

```python
from obskit.metrics import REDMetrics, get_red_metrics

# Quick initialization
metrics = get_red_metrics(service_name="order-service")

# Detailed initialization
red = REDMetrics(
    service_name="order-service",
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

# Track requests
red.observe_request(
    operation="create_order",
    duration_seconds=0.045,
    status="success"
)

# Track with context manager
with red.track_request(endpoint="/api/orders", method="POST") as tracker:
    result = create_order(order_data)
    if result.error:
        tracker.mark_error()
```

#### Golden Signals

Latency, Traffic, Errors, Saturation - for comprehensive monitoring.

```python
from obskit.metrics import GoldenSignals

golden = GoldenSignals("order-service")

# Observe requests
golden.observe_request("create_order", duration_seconds=0.045)
golden.observe_error("create_order", error_type="validation")

# Track saturation
golden.set_saturation("cpu", 0.75)  # 75% CPU
golden.set_saturation("memory", 0.60)  # 60% memory
golden.set_queue_depth("order_queue", 42)

# Track traffic
golden.inc_traffic("api_calls", 1)
```

#### USE Metrics (Infrastructure)

Utilization, Saturation, Errors - for infrastructure monitoring.

```python
from obskit.metrics import USEMetrics

# CPU metrics
cpu = USEMetrics("server_cpu")
cpu.set_utilization("cpu", 0.65)   # 65% busy
cpu.set_saturation("cpu", 3)       # 3 processes waiting
cpu.inc_error("cpu", "thermal")    # Thermal throttling

# Memory metrics
memory = USEMetrics("server_memory")
memory.set_utilization("heap", 0.80)
memory.set_saturation("swap", 0.15)

# Network metrics
network = USEMetrics("network_io")
network.set_utilization("eth0_tx", 0.45)
network.set_utilization("eth0_rx", 0.30)
```

#### Async Metrics

Thread-safe async metrics recording.

```python
from obskit.metrics import AsyncREDMetrics
import asyncio

async_metrics = AsyncREDMetrics("async-service", buffer_size=1000)

async def process_request():
    await async_metrics.observe_request(
        operation="fetch_data",
        duration_seconds=0.123,
        status="success"
    )

# Flush periodically
await async_metrics.flush()
```

#### Tenant Metrics

Multi-tenant metrics with tenant isolation.

```python
from obskit.metrics import TenantREDMetrics, tenant_context, tenant_metrics_context

tenant_metrics = TenantREDMetrics("api-service")

# Set tenant context
with tenant_context("tenant-123"):
    tenant_metrics.observe_request(
        operation="list_users",
        duration_seconds=0.05,
        status="success"
    )

# Or use context manager
async with tenant_metrics_context("tenant-456"):
    # All metrics tagged with tenant_id="tenant-456"
    await process_tenant_request()
```

#### Metrics Export

```python
from obskit import start_http_server, OTLPMetricsExporter, PushgatewayExporter

# Prometheus HTTP server
start_http_server(port=9090)

# OTLP export (to OpenTelemetry Collector)
otlp = OTLPMetricsExporter(
    endpoint="http://otel-collector:4317",
    service_name="my-service"
)
otlp.start_periodic_export(interval_seconds=15)

# Pushgateway (for batch jobs)
push = PushgatewayExporter(
    gateway="http://pushgateway:9091",
    job="batch-processor",
    instance="worker-1"
)
push.push()  # Push current metrics
```

#### Metrics Presets

```python
from obskit.metrics import (
    DEFAULT_BUCKETS,
    FAST_SERVICE_BUCKETS,    # [0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25]
    API_SERVICE_BUCKETS,     # [0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5]
    DATABASE_SERVICE_BUCKETS, # [0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0]
    BATCH_SERVICE_BUCKETS     # [0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 120.0]
)
```

---

### 1.2 Logging

#### Structured Logging

```python
from obskit import get_logger, configure_logging

# Configure at startup
logger = configure_logging(
    service_name="order-service",
    log_level="INFO",
    log_format="json",
    add_trace_id=True
)

# Get logger instance
logger = get_logger(__name__)

# Structured logging
logger.info("order_created", 
    order_id="ord-123",
    customer_id="cust-456",
    amount=99.99,
    currency="USD"
)

logger.error("payment_failed",
    order_id="ord-123",
    error_code="INSUFFICIENT_FUNDS",
    exc_info=True
)
```

#### Logging Adapters (Pluggable Backends)

```python
from obskit.logging.adapters import StructlogAdapter, LoguruAdapter
from obskit.logging.factory import get_logger_from_factory, configure_logging_backend

# Use structlog (default)
configure_logging_backend(backend="structlog", service_name="my-service")

# Use loguru
configure_logging_backend(backend="loguru", service_name="my-service")

# Get logger from factory
logger = get_logger_from_factory(__name__)
```

#### Dynamic Log Level

```python
from obskit.logging import set_log_level, get_log_level

# Get current level
current_level = get_log_level()  # "INFO"

# Change at runtime (useful for debugging)
set_log_level("DEBUG")

# Revert back
set_log_level("INFO")
```

#### PII Redaction

```python
from obskit import redact_pii

# Automatically redact sensitive data
data = {
    "email": "user@example.com",
    "phone": "+1-555-123-4567",
    "ssn": "123-45-6789",
    "credit_card": "4111-1111-1111-1111"
}

safe_data = redact_pii(data)
# {
#     "email": "[REDACTED:email]",
#     "phone": "[REDACTED:phone]",
#     "ssn": "[REDACTED:ssn]",
#     "credit_card": "[REDACTED:credit_card]"
# }
```

---

### 1.3 Tracing

#### Distributed Tracing

```python
from obskit.tracing import trace_context, inject_trace_context, extract_trace_context

# Create trace context
with trace_context("process_order", attributes={"order_id": "123"}) as span:
    # Add events
    span.add_event("validation_complete")
    
    # Propagate to external service
    headers = inject_trace_context({})
    response = await client.post(url, headers=headers)
    
    # Extract from incoming request
    ctx = extract_trace_context(request.headers)
```

#### Context Propagation

```python
from obskit import (
    get_correlation_id,
    set_correlation_id,
    correlation_context,
    generate_correlation_id
)

# Set correlation ID
correlation_id = generate_correlation_id()
set_correlation_id(correlation_id)

# Use context manager
with correlation_context(correlation_id="req-12345"):
    # All operations within this block share the correlation ID
    process_request()
    
# Get current correlation ID
current_id = get_correlation_id()
```

#### Batch Context Propagation

```python
from obskit import (
    batch_job_context,
    capture_context,
    restore_context,
    propagate_to_executor,
    create_task_with_context
)
import asyncio
from concurrent.futures import ThreadPoolExecutor

# Batch job context
with batch_job_context(job_name="nightly-sync", batch_id="batch-001"):
    process_batch()

# Propagate to thread pool
executor = ThreadPoolExecutor(max_workers=4)
ctx = capture_context()

def worker(item):
    with restore_context(ctx):
        # Context (correlation ID, etc.) is restored
        process_item(item)

# Wrap executor
wrapped_executor = propagate_to_executor(executor)

# Async task with context
task = create_task_with_context(process_async())
```

---

## 2. Health & Resilience

### 2.1 Health Checks

```python
from obskit.health import (
    HealthChecker,
    get_health_checker,
    create_health_response,
    start_health_server
)

# Get or create health checker
health = get_health_checker()

# Add readiness checks
@health.add_readiness_check("database")
async def check_database():
    return await db.ping()

@health.add_readiness_check("redis")
async def check_redis():
    return await redis.ping()

@health.add_readiness_check("external_api")
async def check_external_api():
    response = await httpx.get("https://api.example.com/health")
    return response.status_code == 200

# Add liveness check
@health.add_liveness_check("memory")
def check_memory():
    import psutil
    return psutil.virtual_memory().percent < 90

# Check health
result = await health.check_health()
print(result.status)  # "healthy" or "unhealthy"
print(result.checks)  # Individual check results

# Create HTTP response
response = create_health_response(result)

# Start standalone health server
start_health_server(port=8080)
```

#### SLO-Based Health Checks

```python
from obskit.health import add_slo_readiness_check, get_slo_health_status, SLOReadinessCheck

# Add SLO-based readiness check
add_slo_readiness_check(
    name="api_slo",
    slo_tracker=slo_tracker,
    min_error_budget_percent=10.0  # Unhealthy if budget < 10%
)

# Get SLO health status
status = get_slo_health_status()
```

#### HTTP Health Server

```python
from obskit.health import (
    start_health_server,
    stop_health_server,
    is_health_server_running,
    register_health_endpoint
)

# Start server
start_health_server(port=8080)

# Register custom endpoint
register_health_endpoint("/custom-health", custom_check_handler)

# Check if running
if is_health_server_running():
    print("Health server is active")

# Stop server
stop_health_server()
```

---

### 2.2 Circuit Breaker

#### Local Circuit Breaker

```python
from obskit import CircuitBreaker
from obskit.resilience import get_circuit_breaker, CircuitBreakerPreset

# Basic usage
breaker = CircuitBreaker(
    name="external_api",
    failure_threshold=5,
    recovery_timeout=30.0,
    half_open_max_calls=3
)

# Use as context manager
async with breaker:
    response = await external_api.call()

# Use as decorator
@breaker
async def call_api():
    return await client.get("/data")

# Get preset circuit breaker
fast_breaker = get_circuit_breaker("payment_api", preset=CircuitBreakerPreset.AGGRESSIVE)
slow_breaker = get_circuit_breaker("batch_api", preset=CircuitBreakerPreset.RELAXED)

# Manual control
if breaker.allow_request():
    try:
        result = await api_call()
        breaker.record_success()
    except Exception as e:
        breaker.record_failure()
        raise
```

#### Distributed Circuit Breaker (Redis-backed)

```python
from obskit import DistributedCircuitBreaker
import redis.asyncio as redis

# Async Redis
redis_client = redis.Redis(host="localhost", port=6379)

distributed_breaker = DistributedCircuitBreaker(
    name="payment-api",
    redis_client=redis_client,
    failure_threshold=5,
    recovery_timeout=30.0,
    half_open_max_calls=3,
    key_prefix="obskit:cb:"
)

# Use same as local circuit breaker
async with distributed_breaker:
    response = await payment_api.process()

# Sync Redis also supported
import redis
sync_redis = redis.Redis(host="localhost", port=6379)
sync_breaker = DistributedCircuitBreaker(
    name="inventory-api",
    redis_client=sync_redis,
    failure_threshold=3
)
```

#### Circuit Breaker Dashboard

```python
from obskit import (
    CircuitBreakerDashboard,
    get_circuit_dashboard,
    register_circuit_breaker,
    get_all_circuit_states
)

# Get dashboard
dashboard = get_circuit_dashboard()

# Register circuit breakers
register_circuit_breaker(payment_breaker)
register_circuit_breaker(inventory_breaker)

# Get all states
states = get_all_circuit_states()
for name, status in states.items():
    print(f"{name}: {status.state} (failures: {status.failure_count})")

# Get dashboard data (for UI)
data = dashboard.get_dashboard_data()
```

---

### 2.3 Retry & Rate Limiting

#### Retry with Backoff

```python
from obskit import retry, retry_async, RetryConfig

# Simple retry decorator
@retry(max_attempts=3, base_delay=1.0, max_delay=30.0)
def fetch_data():
    return api.get("/data")

# Async retry
@retry_async(max_attempts=3, base_delay=1.0, jitter=True)
async def fetch_data_async():
    return await client.get("/data")

# Retry with config
config = RetryConfig(
    max_attempts=5,
    base_delay=0.5,
    max_delay=60.0,
    exponential_base=2,
    jitter=True,
    retry_on=(ConnectionError, TimeoutError)
)

@retry_async(config=config)
async def resilient_call():
    return await service.call()
```

#### Rate Limiting

```python
from obskit import (
    RateLimiter,
    TokenBucketRateLimiter,
    SlidingWindowRateLimiter,
    get_rate_limiter,
    RateLimiterPreset
)

# Simple rate limiter (100 requests per minute)
limiter = RateLimiter(requests=100, window_seconds=60)

if limiter.acquire():
    process_request()
else:
    raise RateLimitExceeded("Too many requests")

# Token bucket (for bursty traffic)
bucket = TokenBucketRateLimiter(
    bucket_size=100,
    refill_rate=10  # 10 tokens per second
)

# Sliding window (more accurate)
sliding = SlidingWindowRateLimiter(
    requests=1000,
    window_seconds=60
)

# Get preset rate limiter
strict = get_rate_limiter("api", preset=RateLimiterPreset.STRICT)
relaxed = get_rate_limiter("batch", preset=RateLimiterPreset.RELAXED)
```

#### Combined Resilience

```python
from obskit import (
    ResilientExecutor,
    resilient_call,
    with_resilience,
    BackoffStrategy
)

# Resilient executor (retry + circuit breaker)
executor = ResilientExecutor(
    name="external_api",
    max_retries=3,
    circuit_failure_threshold=5,
    backoff_strategy=BackoffStrategy.EXPONENTIAL
)

result = await executor.execute(api_call)

# Decorator
@with_resilience(
    max_retries=3,
    circuit_breaker="api_breaker",
    rate_limit=100
)
async def call_external_api():
    return await client.get("/data")

# Functional call
result = await resilient_call(
    api_call,
    max_retries=3,
    timeout=5.0
)
```

---

### 2.4 Load Shedding

```python
from obskit import LoadShedder, Priority, SheddingConfig, get_load_shedder

# Create load shedder
shedder = LoadShedder(
    config=SheddingConfig(
        max_concurrent=1000,
        high_water_mark=0.8,
        low_water_mark=0.6
    )
)

# Or get global instance
shedder = get_load_shedder()

# Check if request should be accepted
if shedder.should_accept(priority=Priority.HIGH):
    with shedder.track():
        process_request()
else:
    return {"error": "Server busy", "retry_after": 5}

# Decorator for automatic shedding
@shedder.shed(priority=Priority.LOW, fallback=lambda: {"cached": True})
async def non_critical_endpoint():
    return await expensive_computation()
```

---

## 3. SLO & Error Budgets

### SLO Tracking

```python
from obskit.slo import SLOTracker, SLODefinition, expose_slo_metrics, update_slo_metrics

# Define SLO
slo = SLODefinition(
    name="api_availability",
    target=0.999,  # 99.9%
    window_days=30,
    description="API should be available 99.9% of the time"
)

# Create tracker
tracker = SLOTracker(slo)

# Record events
tracker.record_event(success=True)
tracker.record_event(success=False, error_type="timeout")

# Check status
status = tracker.get_status()
print(f"Current SLI: {status.current_sli:.4f}")
print(f"Error Budget: {status.error_budget_remaining:.2%}")
print(f"Budget Status: {status.budget_status}")

# Expose to Prometheus
expose_slo_metrics(tracker)
update_slo_metrics()
```

### Alertmanager Integration

```python
from obskit import AlertmanagerWebhook, SyncAlertmanagerWebhook

# Async webhook
alertmanager = AlertmanagerWebhook(
    alertmanager_url="http://alertmanager:9093",
    default_labels={"team": "platform"}
)

# Send alert
await alertmanager.send_alert(
    alert_name="HighErrorRate",
    severity="critical",
    labels={"service": "api", "slo": "availability"},
    annotations={
        "summary": "Error rate exceeded SLO threshold",
        "runbook": "https://runbooks.example.com/high-error-rate"
    }
)

# Sync webhook
sync_am = SyncAlertmanagerWebhook(alertmanager_url="http://alertmanager:9093")
sync_am.send_alert(alert_name="LowErrorBudget", severity="warning")
```

---

## 4. Framework Integration

### FastAPI Middleware

```python
from fastapi import FastAPI
from obskit.middleware import ObskitMiddleware

app = FastAPI()
app.add_middleware(
    ObskitMiddleware,
    service_name="api-service",
    exclude_paths=["/health", "/metrics"]
)

@app.get("/users")
async def list_users():
    # Automatically tracked with RED metrics, tracing, correlation IDs
    return {"users": []}
```

### Flask Middleware

```python
from flask import Flask
from obskit.middleware import ObskitFlaskMiddleware

app = Flask(__name__)
ObskitFlaskMiddleware(
    app,
    service_name="flask-api",
    exclude_paths=["/health"]
)

@app.route("/orders")
def list_orders():
    return {"orders": []}
```

### Django Middleware

```python
# settings.py
MIDDLEWARE = [
    'obskit.middleware.ObskitDjangoMiddleware',
    'django.middleware.security.SecurityMiddleware',
    # ... other middleware
]

OBSKIT_CONFIG = {
    "service_name": "django-api",
    "exclude_paths": ["/health/", "/admin/"],
}
```

### gRPC Middleware

```python
from obskit.middleware.grpc import ObskitGrpcInterceptor

# Server interceptor
interceptor = ObskitGrpcInterceptor(service_name="grpc-service")
server = grpc.aio.server(interceptors=[interceptor])

# The interceptor automatically:
# - Records RED metrics for each RPC
# - Propagates trace context
# - Adds correlation IDs
```

---

## 5. Advanced Resilience

### 5.1 Chaos Engineering

```python
from obskit import (
    ChaosEngine,
    ChaosExperiment,
    InjectionType,
    chaos_injection,
    get_chaos_engine,
    enable_chaos,
    disable_chaos
)

# Get chaos engine
chaos = get_chaos_engine()

# Add experiment
chaos.add_experiment(
    name="slow_database",
    injection_type=InjectionType.LATENCY,
    latency_ms=500,
    probability=0.1,  # 10% of requests
    duration_minutes=30
)

# Add error injection
chaos.add_experiment(
    name="payment_failure",
    injection_type=InjectionType.ERROR,
    probability=0.05,
    error_class=PaymentError,
    error_message="Simulated payment failure"
)

# Use in code
@chaos_injection("slow_database")
async def query_database():
    return await db.query(...)

# Enable/disable globally
enable_chaos()  # Enable all experiments
disable_chaos()  # Disable all experiments

# Check if should inject
if chaos.should_inject("slow_database"):
    await asyncio.sleep(chaos.get_latency("slow_database"))
```

### 5.2 Graceful Degradation

```python
from obskit import (
    DegradationManager,
    DegradationLevel,
    Feature,
    get_degradation_manager
)

# Get degradation manager
degradation = get_degradation_manager()

# Register features with priorities (lower = more important)
degradation.register_feature(
    name="recommendations",
    priority=2,
    fallback=lambda: cached_recommendations(),
    degradation_threshold=50
)

degradation.register_feature(
    name="analytics",
    priority=1,  # Less important, degrade first
    fallback=lambda: None,
    degradation_threshold=25
)

# Set degradation level (0-100)
degradation.set_level(DegradationLevel.MEDIUM)  # 50%

# Check if feature is enabled
if degradation.is_enabled("recommendations"):
    result = get_recommendations()
else:
    result = degradation.get_fallback("recommendations")()

# Automatic degradation based on load
degradation.auto_degrade(
    metric_name="cpu_usage",
    threshold=0.8,
    level=DegradationLevel.HIGH
)
```

### 5.3 Self-Healing

```python
from obskit import (
    SelfHealingEngine,
    HealingTrigger,
    HealingResult,
    get_self_healing_engine
)

# Get self-healing engine
healer = get_self_healing_engine()

# Register healing trigger
healer.register_trigger(
    name="high_error_rate",
    condition=lambda: error_rate > 0.5,
    action=restart_worker,
    cooldown_minutes=5,
    max_executions_per_hour=3,
    description="Restart worker when error rate exceeds 50%"
)

healer.register_trigger(
    name="connection_pool_exhausted",
    condition=lambda: pool.available == 0,
    action=reset_connection_pool,
    cooldown_minutes=2
)

# Evaluate all triggers
results = healer.evaluate()
for trigger_name, result in results.items():
    if result == HealingResult.SUCCESS:
        logger.info(f"Healing action executed: {trigger_name}")

# Run continuous evaluation
healer.start_evaluation_loop(interval_seconds=30)
```

### 5.4 Failover Coordinator

```python
from obskit import (
    FailoverCoordinator,
    FailoverState,
    FailoverEvent,
    get_failover_coordinator
)

# Get failover coordinator
failover = get_failover_coordinator()

# Register primary and backup
failover.register_primary(
    name="primary_db",
    health_check=primary_health_check,
    endpoint="db-primary:5432"
)

failover.register_backup(
    name="backup_db",
    health_check=backup_health_check,
    endpoint="db-backup:5432",
    priority=1
)

# Get current active endpoint
active = failover.get_active_endpoint()

# Manual failover
failover.trigger_failover(reason="maintenance")

# Automatic failover based on health
failover.enable_auto_failover(
    check_interval_seconds=10,
    failure_threshold=3
)
```

---

## 6. Debugging & Analysis

### 6.1 Flame Graph Profiler

```python
from obskit import (
    FlameGraphProfiler,
    ProfileResult,
    profile_function,
    get_flamegraph_profiler
)

# Get profiler
profiler = get_flamegraph_profiler()

# Profile a section
with profiler.profile("order_processing") as profile:
    process_orders()

# Get results
result = profiler.get_result("order_processing")
print(f"Duration: {result.duration_seconds}s")
print(f"Total calls: {result.total_calls}")
for func, time_ms, calls in result.top_functions[:10]:
    print(f"  {func}: {time_ms:.2f}ms ({calls} calls)")

# Export flame graph
profiler.export_svg("order_processing.svg")
profiler.export_json("order_processing.json")

# Decorator
@profile_function
def expensive_computation():
    # Function will be profiled
    pass
```

### 6.2 Query Plan Analyzer

```python
from obskit import (
    QueryAnalyzer,
    QueryAnalysis,
    QueryType,
    get_query_analyzer
)

# Get analyzer
analyzer = get_query_analyzer()

# Analyze query
analysis = analyzer.analyze(
    query="SELECT * FROM users WHERE email = 'test@example.com'",
    explain_output=explain_result
)

print(f"Query type: {analysis.query_type}")
print(f"Estimated cost: {analysis.estimated_cost}")
print(f"Issues found:")
for issue in analysis.issues:
    print(f"  - {issue.severity}: {issue.message}")
print(f"Suggestions:")
for suggestion in analysis.suggestions:
    print(f"  - {suggestion}")

# Track slow queries automatically
analyzer.enable_slow_query_tracking(threshold_ms=100)
```

### 6.3 Dependency Graph

```python
from obskit import (
    DependencyGraph,
    DependencyNode,
    get_dependency_graph
)

# Get dependency graph
graph = get_dependency_graph()

# Register services
graph.register_service(
    name="order-service",
    dependencies=["user-service", "inventory-service", "payment-service"]
)

graph.register_service(
    name="user-service",
    dependencies=["auth-service", "database"]
)

# Visualize
visualization = graph.generate_visualization()
visualization.export_dot("dependencies.dot")
visualization.export_mermaid("dependencies.md")

# Check health propagation
health_status = graph.get_health_status()
for service, status in health_status.items():
    print(f"{service}: {status.state}")
    if status.affected_by:
        print(f"  Affected by: {status.affected_by}")
```

### 6.4 Root Cause Analyzer

```python
from obskit import (
    RootCauseAnalyzer,
    RootCauseResult,
    Anomaly,
    AnomalySeverity,
    get_root_cause_analyzer
)

# Get analyzer
rca = get_root_cause_analyzer()

# Report anomaly
rca.report_anomaly(
    service="payment-service",
    metric="error_rate",
    current_value=0.15,
    expected_value=0.01,
    severity=AnomalySeverity.HIGH
)

# Analyze root cause
result = rca.analyze(
    incident_id="INC-12345",
    affected_services=["payment-service", "order-service"],
    time_range=(start_time, end_time)
)

print(f"Root cause: {result.root_cause}")
print(f"Confidence: {result.confidence:.2%}")
print(f"Contributing factors:")
for factor in result.contributing_factors:
    print(f"  - {factor.description} ({factor.correlation:.2%})")
```

### 6.5 Error Fingerprinting

```python
from obskit import (
    ErrorFingerprinter,
    get_error_fingerprinter,
    get_fingerprint,
    get_error_group
)

# Get fingerprinter
fingerprinter = get_error_fingerprinter()

# Fingerprint an error
try:
    risky_operation()
except Exception as e:
    fingerprint = fingerprinter.fingerprint(e)
    print(f"Error fingerprint: {fingerprint.hash}")
    print(f"Error group: {fingerprint.group_id}")

# Get error group statistics
group = get_error_group(fingerprint.group_id)
print(f"Occurrences: {group.count}")
print(f"First seen: {group.first_seen}")
print(f"Last seen: {group.last_seen}")
print(f"Sample stack trace: {group.sample_stack}")
```

### 6.6 Latency Breakdown

```python
from obskit import (
    LatencyBreakdown,
    track_breakdown
)

# Track latency phases
breakdown = LatencyBreakdown("api_request")

with breakdown.phase("authentication"):
    await authenticate_user()

with breakdown.phase("authorization"):
    await check_permissions()

with breakdown.phase("database"):
    await fetch_data()

with breakdown.phase("serialization"):
    response = serialize(data)

# Get breakdown summary
summary = breakdown.get_summary()
print(f"Total: {summary.total_ms:.2f}ms")
for phase in summary.phases:
    print(f"  {phase.name}: {phase.duration_ms:.2f}ms ({phase.percentage:.1f}%)")

# Decorator
@track_breakdown("process_order")
async def process_order(order):
    # Breakdown tracked automatically
    pass
```

### 6.7 Hot Path Detector

```python
from obskit import (
    HotPathDetector,
    HotPath,
    track_path,
    get_hot_path_detector
)

# Get detector
detector = get_hot_path_detector()

# Track code paths
@track_path("order_creation")
async def create_order(order_data):
    with detector.track("validation"):
        validate(order_data)
    
    with detector.track("persistence"):
        await save_order(order_data)

# Get hot paths
hot_paths = detector.get_hot_paths(top_n=10)
for path in hot_paths:
    print(f"{path.name}: {path.total_time_ms:.2f}ms "
          f"({path.call_count} calls, avg {path.avg_time_ms:.2f}ms)")
```

---

## 7. Infrastructure Monitoring

### 7.1 Connection Pool Metrics

```python
from obskit import (
    ConnectionPoolTracker,
    PoolType,
    get_pool_tracker,
    get_all_pool_stats,
    wrap_psycopg2_pool,
    wrap_redis_pool
)

# Track database pool
db_pool = psycopg2.pool.ThreadedConnectionPool(5, 20, dsn)
tracked_db_pool = wrap_psycopg2_pool(db_pool, name="main_db")

# Track Redis pool
redis_pool = redis.ConnectionPool(max_connections=100)
tracked_redis_pool = wrap_redis_pool(redis_pool, name="cache")

# Get statistics
stats = get_all_pool_stats()
for pool_name, pool_stats in stats.items():
    print(f"{pool_name}:")
    print(f"  Size: {pool_stats.size}")
    print(f"  Used: {pool_stats.used}")
    print(f"  Available: {pool_stats.available}")
    print(f"  Wait time avg: {pool_stats.wait_time_avg_ms:.2f}ms")
```

### 7.2 Dead Letter Queue Tracking

```python
from obskit import (
    DLQTracker,
    DLQReason,
    get_dlq_tracker,
    get_all_dlq_stats
)

# Get tracker
dlq = get_dlq_tracker("order_processing")

# Record DLQ message
dlq.record_message(
    message_id="msg-12345",
    reason=DLQReason.PARSE_ERROR,
    original_queue="orders",
    error_message="Invalid JSON",
    payload_sample=payload[:1000]  # First 1000 chars
)

# Get statistics
stats = dlq.get_stats()
print(f"Total DLQ messages: {stats.total_count}")
print(f"By reason:")
for reason, count in stats.by_reason.items():
    print(f"  {reason}: {count}")
```

### 7.3 Consumer Lag Tracking

```python
from obskit import (
    ConsumerLagTracker,
    QueueType,
    get_consumer_lag_tracker,
    get_all_consumer_lag_stats
)

# Track Kafka consumer lag
kafka_lag = get_consumer_lag_tracker("orders", queue_type=QueueType.KAFKA)
kafka_lag.update_lag(
    consumer_group="order-processor",
    partition=0,
    current_offset=1000,
    end_offset=1050
)

# Track RabbitMQ queue depth
rabbitmq_lag = get_consumer_lag_tracker("notifications", queue_type=QueueType.RABBITMQ)
rabbitmq_lag.update_queue_depth(50)

# Get all stats
stats = get_all_consumer_lag_stats()
for queue, lag_stats in stats.items():
    print(f"{queue}: lag={lag_stats.lag_messages}, time={lag_stats.lag_seconds}s")
```

### 7.4 External API SLA Tracking

```python
from obskit import (
    ExternalAPISLATracker,
    SLADefinition,
    get_external_api_tracker,
    get_all_api_compliance
)

# Track external API SLA
tracker = get_external_api_tracker("payment_gateway")

# Define SLA
tracker.set_sla(SLADefinition(
    availability_target=0.999,
    latency_p99_ms=500,
    error_rate_target=0.001
))

# Record request
tracker.record_request(
    duration_ms=150,
    success=True,
    status_code=200
)

# Get compliance report
report = tracker.get_compliance_report()
print(f"Availability: {report.availability:.4f} (target: {report.sla.availability_target})")
print(f"Latency P99: {report.latency_p99_ms}ms (target: {report.sla.latency_p99_ms}ms)")
print(f"Compliant: {report.is_compliant}")
```

### 7.5 Memory & GC Metrics

```python
from obskit import (
    MemoryTracker,
    start_memory_tracking,
    stop_memory_tracking,
    get_memory_tracker
)

# Start tracking
start_memory_tracking(interval_seconds=30)

# Get current stats
tracker = get_memory_tracker()
stats = tracker.get_stats()

print(f"Heap used: {stats.heap_used_mb:.2f}MB")
print(f"Heap total: {stats.heap_total_mb:.2f}MB")
print(f"GC collections: {stats.gc_stats.collections}")
print(f"GC time: {stats.gc_stats.collection_time_ms}ms")

# Track object counts
obj_stats = tracker.get_object_stats()
for type_name, count in obj_stats.top_types[:10]:
    print(f"  {type_name}: {count}")

# Stop tracking
stop_memory_tracking()
```

### 7.6 Executor Metrics

```python
from obskit import (
    ExecutorTracker,
    TrackedExecutor,
    wrap_executor,
    create_tracked_executor,
    get_all_executor_stats
)
from concurrent.futures import ThreadPoolExecutor

# Create tracked executor
executor = create_tracked_executor(
    name="worker_pool",
    max_workers=10
)

# Or wrap existing
existing_executor = ThreadPoolExecutor(max_workers=5)
tracked = wrap_executor(existing_executor, name="legacy_pool")

# Submit tasks
future = executor.submit(process_task, data)

# Get statistics
stats = get_all_executor_stats()
for name, exec_stats in stats.items():
    print(f"{name}:")
    print(f"  Active: {exec_stats.active_count}")
    print(f"  Queued: {exec_stats.queued_count}")
    print(f"  Completed: {exec_stats.completed_count}")
    print(f"  Avg duration: {exec_stats.avg_duration_ms:.2f}ms")
```

---

## 8. Security & Compliance

### 8.1 Audit Trail

```python
from obskit import (
    AuditTrail,
    AuditEntry,
    AuditAction,
    get_audit_trail
)

# Get audit trail
audit = get_audit_trail()

# Log audit event
audit.log(
    action=AuditAction.CREATE,
    resource_type="order",
    resource_id="ord-12345",
    actor="user-789",
    details={
        "amount": 99.99,
        "items": ["item-1", "item-2"]
    },
    ip_address="192.168.1.100"
)

# Query audit trail
entries = audit.query(
    resource_type="order",
    start_time=datetime.now() - timedelta(hours=24),
    actor="user-789"
)

# Verify chain integrity
is_valid = audit.verify_chain()
```

### 8.2 Secrets Detection

```python
from obskit import (
    SecretsDetector,
    redact_secrets,
    scan_for_secrets,
    get_secrets_detector
)

# Get detector
detector = get_secrets_detector()

# Scan text for secrets
text = "API_KEY=sk-1234567890abcdef"
results = scan_for_secrets(text)
for result in results:
    print(f"Found {result.secret_type} at position {result.start_pos}")

# Redact secrets
safe_text = redact_secrets(text)
# "API_KEY=[REDACTED:api_key]"

# Scan dictionary
data = {
    "config": {
        "password": "super_secret",
        "api_key": "sk-abc123"
    }
}
safe_data = detector.redact_dict(data)
```

### 8.3 Compliance Reporter

```python
from obskit import (
    ComplianceReporter,
    ComplianceFramework,
    ComplianceCheck,
    get_compliance_reporter
)

# Get reporter
reporter = get_compliance_reporter()

# Add compliance checks
reporter.add_check(
    framework=ComplianceFramework.GDPR,
    check_name="data_encryption",
    check_function=check_encryption_at_rest,
    description="Verify all data is encrypted at rest"
)

reporter.add_check(
    framework=ComplianceFramework.SOC2,
    check_name="access_logging",
    check_function=check_access_logs,
    description="Verify access logging is enabled"
)

# Generate report
report = reporter.generate_report(framework=ComplianceFramework.GDPR)
print(f"Compliance: {report.compliance_percentage:.1f}%")
for check in report.checks:
    status = "✅" if check.passed else "❌"
    print(f"  {status} {check.name}: {check.message}")
```

---

## 9. Operations & Incident Management

### 9.1 Runbook Integration

```python
from obskit import (
    RunbookManager,
    Runbook,
    RunbookExecution,
    get_runbook_manager
)

# Get runbook manager
runbooks = get_runbook_manager()

# Register runbook
runbooks.register(
    alert_name="HighErrorRate",
    runbook=Runbook(
        url="https://runbooks.example.com/high-error-rate",
        steps=[
            "1. Check error logs",
            "2. Verify database connectivity",
            "3. Check external API status",
            "4. Escalate if not resolved"
        ],
        escalation_contacts=["oncall@example.com"]
    )
)

# Get runbook for alert
runbook = runbooks.get_for_alert("HighErrorRate")

# Track execution
execution = runbooks.start_execution("HighErrorRate", incident_id="INC-123")
execution.complete_step(0, notes="No errors in logs")
execution.complete_step(1, notes="Database healthy")
execution.mark_resolved(resolution="External API was down, now recovered")
```

### 9.2 Incident Timeline

```python
from obskit import (
    IncidentTimeline,
    IncidentManager,
    IncidentStatus,
    TimelineEvent,
    get_incident_manager
)

# Get incident manager
incidents = get_incident_manager()

# Create incident
incident = incidents.create(
    title="Payment service degradation",
    severity="high",
    affected_services=["payment-service", "order-service"]
)

# Add timeline events
incident.add_event(
    event_type="alert_fired",
    description="High error rate alert triggered",
    source="prometheus"
)

incident.add_event(
    event_type="investigation",
    description="Identified database connection pool exhaustion",
    author="oncall@example.com"
)

incident.add_event(
    event_type="mitigation",
    description="Increased connection pool size",
    author="oncall@example.com"
)

# Update status
incident.update_status(IncidentStatus.MITIGATED)
incident.update_status(IncidentStatus.RESOLVED)

# Generate post-mortem
postmortem = incident.generate_postmortem()
```

### 9.3 SLA Breach Predictor

```python
from obskit import (
    SLAPredictor,
    RiskAssessment,
    get_sla_predictor
)

# Get predictor
predictor = get_sla_predictor()

# Add SLA definitions
predictor.add_sla(
    name="api_availability",
    target=0.999,
    current_value=0.9985,
    window_hours=720  # 30 days
)

# Predict breach risk
assessment = predictor.assess_risk("api_availability")
print(f"Breach probability: {assessment.breach_probability:.2%}")
print(f"Time to breach: {assessment.time_to_breach_hours}h")
print(f"Recommendation: {assessment.recommendation}")

# Get all at-risk SLAs
at_risk = predictor.get_at_risk_slas(threshold=0.7)
for sla_name, risk in at_risk:
    print(f"⚠️ {sla_name}: {risk.breach_probability:.2%} breach risk")
```

### 9.4 Capacity Planner

```python
from obskit import (
    CapacityPlanner,
    CapacityPlan,
    CapacityProjection,
    get_capacity_planner
)

# Get planner
planner = get_capacity_planner()

# Record current usage
planner.record_usage(
    resource="cpu",
    current_usage=0.65,
    capacity=100,
    timestamp=datetime.now()
)

# Generate projection
projection = planner.project(
    resource="cpu",
    horizon_days=90
)

print(f"Current usage: {projection.current_percent:.1f}%")
print(f"Projected (30d): {projection.projected_30d_percent:.1f}%")
print(f"Projected (90d): {projection.projected_90d_percent:.1f}%")
print(f"Capacity exhaustion: {projection.exhaustion_date}")

# Get capacity plan
plan = planner.generate_plan()
for recommendation in plan.recommendations:
    print(f"📈 {recommendation.resource}: {recommendation.action}")
```

### 9.5 Alert Deduplication

```python
from obskit import (
    AlertDeduplicator,
    DeduplicationConfig,
    get_alert_deduplicator,
    should_alert
)

# Get deduplicator
dedup = get_alert_deduplicator()

# Configure
dedup.configure(DeduplicationConfig(
    window_seconds=300,  # 5 minute dedup window
    max_alerts_per_window=1,
    group_by=["alert_name", "service"]
))

# Check if should alert
if should_alert(
    alert_name="HighErrorRate",
    labels={"service": "api", "severity": "critical"}
):
    send_alert(...)
else:
    logger.debug("Alert suppressed (duplicate)")
```

### 9.6 Grafana Annotations

```python
from obskit import (
    GrafanaAnnotator,
    Annotation,
    configure_annotator,
    get_annotator
)

# Configure
configure_annotator(
    grafana_url="http://grafana:3000",
    api_key="your-api-key"
)

# Get annotator
annotator = get_annotator()

# Add annotation
annotator.add(
    title="Deployment v1.2.3",
    text="Deployed new version with performance improvements",
    tags=["deployment", "api-service"],
    dashboard_id=1
)

# Add incident annotation
annotator.add_incident(
    title="Payment service outage",
    description="Database failover in progress",
    severity="critical",
    start_time=incident_start,
    end_time=incident_end
)
```

---

## 10. Testing Utilities

### Mock Objects

```python
from obskit.testing import (
    MockMetrics,
    MockTracer,
    MockSLOTracker,
    MockHealthChecker,
    MockCircuitBreaker,
    disable_observability,
    mock_observability,
    ObskitTestContext,
    ObskitTestCase
)

# Use mock metrics in tests
def test_order_creation():
    metrics = MockMetrics()
    
    create_order(metrics=metrics)
    
    assert metrics.requests_count == 1
    assert metrics.errors_count == 0
    assert metrics.last_duration < 1.0

# Disable all observability
with disable_observability():
    # No metrics/traces/logs collected
    process_request()

# Mock entire observability stack
with mock_observability() as mocks:
    process_request()
    
    assert mocks.metrics.requests_count == 1
    assert mocks.tracer.spans_count == 1
```

### Test Context

```python
from obskit.testing import ObskitTestContext, ObskitTestCase

# Context manager
with ObskitTestContext() as ctx:
    # Observability isolated to this context
    result = process_order(order_data)
    
    assert ctx.metrics.get_count("orders_created") == 1
    assert ctx.logs.contains("order_created")

# Test case base class
class TestOrderService(ObskitTestCase):
    def test_create_order(self):
        result = self.service.create_order(data)
        
        self.assert_metric_recorded("orders_total", 1)
        self.assert_log_contains("order_created")
        self.assert_no_errors()
```

---

## Configuration Reference

### Environment Variables

```bash
# Core
OBSKIT_SERVICE_NAME=my-service
OBSKIT_ENVIRONMENT=production
OBSKIT_VERSION=1.0.0

# Logging
OBSKIT_LOG_LEVEL=INFO
OBSKIT_LOG_FORMAT=json
OBSKIT_LOG_OUTPUT=stdout

# Metrics
OBSKIT_METRICS_ENABLED=true
OBSKIT_METRICS_PORT=9090
OBSKIT_METRICS_PATH=/metrics
OBSKIT_METRICS_AUTH_ENABLED=true
OBSKIT_METRICS_AUTH_TOKEN=your-secret-token

# Tracing
OBSKIT_TRACING_ENABLED=true
OBSKIT_TRACING_SAMPLE_RATE=0.1
OBSKIT_OTLP_ENDPOINT=http://otel-collector:4317

# Health
OBSKIT_HEALTH_PORT=8080
OBSKIT_HEALTH_PATH=/health

# Resilience
OBSKIT_CIRCUIT_BREAKER_ENABLED=true
OBSKIT_RATE_LIMIT_ENABLED=true
```

### Programmatic Configuration

```python
from obskit import configure, get_settings

configure(
    service_name="my-service",
    environment="production",
    version="1.0.0",
    
    # Logging
    log_level="INFO",
    log_format="json",
    
    # Metrics
    metrics_enabled=True,
    metrics_port=9090,
    metrics_auth_enabled=True,
    metrics_auth_token="secret",
    
    # Tracing
    tracing_enabled=True,
    tracing_sample_rate=0.1,
    otlp_endpoint="http://collector:4317",
    
    # Health
    health_port=8080,
)

# Get current settings
settings = get_settings()
print(f"Service: {settings.service_name}")
```

### Configuration File

```yaml
# obskit.yaml
service_name: my-service
environment: production

logging:
  level: INFO
  format: json
  
metrics:
  enabled: true
  port: 9090
  auth:
    enabled: true
    token: ${METRICS_TOKEN}
    
tracing:
  enabled: true
  sample_rate: 0.1
  otlp_endpoint: http://collector:4317
  
resilience:
  circuit_breaker:
    failure_threshold: 5
    recovery_timeout: 30
  rate_limiter:
    requests: 1000
    window_seconds: 60
```

```python
from obskit import configure_from_file

configure_from_file("obskit.yaml")
```

---

## Best Practices

### 1. Initialize Early

```python
# main.py
from obskit import configure, start_http_server

# Configure at application startup
configure(
    service_name="my-service",
    environment=os.getenv("ENVIRONMENT", "development")
)

# Start metrics server before handling requests
start_http_server(port=9090)
```

### 2. Use Correlation IDs

```python
from obskit import correlation_context, get_correlation_id

async def handle_request(request):
    correlation_id = request.headers.get("X-Correlation-ID")
    
    with correlation_context(correlation_id=correlation_id):
        # All logs and traces within this block share the correlation ID
        result = await process_request(request)
        
    return result
```

### 3. Define SLOs

```python
from obskit.slo import SLOTracker, SLODefinition

# Define meaningful SLOs
availability_slo = SLODefinition(
    name="api_availability",
    target=0.999,
    window_days=30
)

latency_slo = SLODefinition(
    name="api_latency_p99",
    target=0.95,  # 95% of requests under threshold
    window_days=7
)

# Track and alert on SLO violations
tracker = SLOTracker(availability_slo)
if tracker.get_status().budget_remaining < 0.1:
    alert("Low error budget!")
```

### 4. Implement Circuit Breakers for External Calls

```python
from obskit import CircuitBreaker, retry_async

payment_breaker = CircuitBreaker(
    name="payment_gateway",
    failure_threshold=5,
    recovery_timeout=30
)

@retry_async(max_attempts=3)
async def process_payment(payment_data):
    async with payment_breaker:
        return await payment_gateway.charge(payment_data)
```

### 5. Use Graceful Shutdown

```python
from obskit import register_shutdown_hook, GracefulShutdown

shutdown = GracefulShutdown(timeout_seconds=30)

# Register cleanup handlers
shutdown.register(cleanup_connections)
shutdown.register(flush_metrics)
shutdown.register(close_tracing)

# Or use decorator
@register_shutdown_hook
async def cleanup():
    await db.close()
    await redis.close()
```

---

## Additional Resources

- **Quick Start**: [tech_docs/01_QUICK_START.md](../tech_docs/01_QUICK_START.md)
- **Configuration Guide**: [tech_docs/02_CONFIGURATION.md](../tech_docs/02_CONFIGURATION.md)
- **Metrics Deep Dive**: [tech_docs/03_METRICS.md](../tech_docs/03_METRICS.md)
- **Health Checks**: [tech_docs/04_HEALTH_CHECKS.md](../tech_docs/04_HEALTH_CHECKS.md)
- **Resilience Patterns**: [tech_docs/05_RESILIENCE.md](../tech_docs/05_RESILIENCE.md)
- **SLO Tracking**: [tech_docs/06_SLO_TRACKING.md](../tech_docs/06_SLO_TRACKING.md)
- **Security Hardening**: [tech_docs/07_SECURITY.md](../tech_docs/07_SECURITY.md)
- **Kubernetes Deployment**: [tech_docs/08_KUBERNETES_DEPLOYMENT.md](../tech_docs/08_KUBERNETES_DEPLOYMENT.md)
- **Troubleshooting**: [tech_docs/09_TROUBLESHOOTING.md](../tech_docs/09_TROUBLESHOOTING.md)
- **Examples**: [examples/](../examples/)

---

<p align="center">
<strong>obskit v1.3.0</strong> - Complete Observability for Python Microservices
</p>
