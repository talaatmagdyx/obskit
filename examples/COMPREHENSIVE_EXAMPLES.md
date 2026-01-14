# Comprehensive Real-World Examples for Obskit

This document provides 100+ real-world examples covering beginner, intermediate, advanced, and edge case scenarios for using the `obskit` observability package.

## Table of Contents

1. [Beginner Examples (1-30)](#beginner-examples-1-30)
2. [Intermediate Examples (31-60)](#intermediate-examples-31-60)
3. [Advanced Examples (61-85)](#advanced-examples-61-85)
4. [Edge Cases & Real-World Scenarios (86-100+)](#edge-cases--real-world-scenarios-86-100)

---

## Beginner Examples (1-30)

### Example 1: Basic Configuration

```python
"""Example 1: Basic package configuration."""
from obskit import configure

# Configure the service name and environment
configure(
    service_name="user-service",
    environment="production",
    log_level="INFO"
)

# Settings are now available globally
from obskit.config import get_settings
settings = get_settings()
print(f"Service: {settings.service_name}")  # user-service
```

### Example 2: Simple Logging

```python
"""Example 2: Basic structured logging."""
from obskit import get_logger

# Get a logger for your module
logger = get_logger("user_service.api")

# Log different levels
logger.info("user_logged_in", user_id="12345", ip_address="192.168.1.1")
logger.warning("rate_limit_approaching", user_id="12345", requests=95)
logger.error("database_connection_failed", error="Connection timeout")
```

### Example 3: Basic Metrics - RED Method

```python
"""Example 3: Track request metrics using RED method."""
from obskit.metrics import REDMetrics
import time

# Create metrics instance
metrics = REDMetrics("user_api")

# Track a successful request
with metrics.track_request(operation="get_user", status="success"):
    # Your business logic here
    time.sleep(0.1)
    user = {"id": 1, "name": "John"}

# Track a failed request
try:
    with metrics.track_request(operation="create_user", status="failure"):
        raise ValueError("Invalid email")
except ValueError:
    pass
```

### Example 4: Simple Health Check

```python
"""Example 4: Basic health check endpoint."""
from obskit.health import HealthChecker
from fastapi import FastAPI

app = FastAPI()
checker = HealthChecker()

# Add a simple health check
@checker.add_readiness_check("database")
def check_database():
    # Simulate database check
    return {"healthy": True, "message": "Database connected"}

@app.get("/health")
async def health():
    result = await checker.check_health()
    return result.to_dict()
```

### Example 5: Basic Correlation ID

```python
"""Example 5: Using correlation IDs for request tracking."""
from obskit.core.context import correlation_context, get_correlation_id

# Set correlation ID for a request
with correlation_context("req-abc-123"):
    correlation_id = get_correlation_id()
    print(f"Processing request: {correlation_id}")
    
    # All logs within this context will include the correlation ID
    from obskit import get_logger
    logger = get_logger("service")
    logger.info("processing_request")  # Automatically includes correlation_id
```

### Example 6: Simple Decorator Usage

```python
"""Example 6: Using observability decorator."""
from obskit.decorators import with_observability

@with_observability(component="UserService")
async def get_user(user_id: str):
    """Get user by ID."""
    # This function is automatically:
    # - Traced (if tracing enabled)
    # - Logged (start/end)
    # - Metrics recorded (duration, success/failure)
    return {"id": user_id, "name": "John Doe"}

# Use it
user = await get_user("123")
```

### Example 7: Basic Circuit Breaker

```python
"""Example 7: Simple circuit breaker pattern."""
from obskit.resilience import CircuitBreaker
import asyncio

breaker = CircuitBreaker("external_api", failure_threshold=3)

async def call_external_api():
    async with breaker:
        # This will fail fast if circuit is open
        response = await fetch_external_service()
        return response

# Use it
try:
    result = await call_external_api()
except Exception as e:
    print(f"Service unavailable: {e}")
```

### Example 8: Simple Retry Logic

```python
"""Example 8: Automatic retry with exponential backoff."""
from obskit.resilience import retry

@retry(max_attempts=3, base_delay=0.1)
async def fetch_data():
    """Retry up to 3 times with exponential backoff."""
    response = await http_client.get("https://api.example.com/data")
    return response.json()

# Will automatically retry on failure
data = await fetch_data()
```

### Example 9: Basic Rate Limiting

```python
"""Example 9: Rate limiting to prevent overload."""
from obskit.resilience import RateLimiter

# Limit to 10 requests per minute
limiter = RateLimiter(requests=10, window_seconds=60)

async def process_request():
    # Wait if rate limit exceeded
    await limiter.acquire()
    
    # Process your request
    return process()

# Use it
result = await process_request()
```

### Example 10: Basic SLO Tracking

```python
"""Example 10: Track Service Level Objectives."""
from obskit.slo import track_slo, SLOType

# Track availability SLO (99.9% uptime)
@track_slo(
    name="api_availability",
    slo_type=SLOType.AVAILABILITY,
    target_value=0.999
)
async def handle_request():
    # Your request handling logic
    return {"status": "ok"}

# SLO compliance is automatically tracked
result = await handle_request()
```

### Example 11: Environment-Based Configuration

```python
"""Example 11: Configure based on environment."""
import os
from obskit import configure

env = os.getenv("ENVIRONMENT", "development")

if env == "production":
    configure(
        service_name="prod-service",
        log_level="WARNING",
        tracing_enabled=True,
        metrics_enabled=True
    )
elif env == "development":
    configure(
        service_name="dev-service",
        log_level="DEBUG",
        tracing_enabled=False,
        metrics_enabled=True
    )
```

### Example 12: Logging with Context

```python
"""Example 12: Add context to logs."""
from obskit import get_logger

logger = get_logger("payment_service")

# Bind context that applies to all subsequent logs
logger = logger.bind(
    user_id="12345",
    transaction_id="txn-abc"
)

logger.info("payment_initiated", amount=100.00)
logger.info("payment_processed")  # Still includes user_id and transaction_id
```

### Example 13: Track Operation Duration

```python
"""Example 13: Manually track operation duration."""
from obskit.metrics import REDMetrics
import time

metrics = REDMetrics("data_processor")

start = time.perf_counter()
# Your operation
process_data()
duration = time.perf_counter() - start

# Record manually
metrics.request_count.labels(operation="process_data", status="success").inc()
metrics.request_duration_histogram.labels(operation="process_data").observe(duration)
```

### Example 14: Error Tracking

```python
"""Example 14: Track errors separately."""
from obskit.metrics import REDMetrics

metrics = REDMetrics("api_service")

try:
    process_request()
except ValueError as e:
    # Track error
    metrics.error_count.labels(
        operation="process_request",
        error_type="ValueError"
    ).inc()
    raise
```

### Example 15: Health Check with Multiple Checks

```python
"""Example 15: Multiple health checks."""
from obskit.health import HealthChecker

checker = HealthChecker()

@checker.add_readiness_check("database")
def check_db():
    return db.is_connected()

@checker.add_readiness_check("cache")
def check_cache():
    return cache.ping()

@checker.add_readiness_check("external_api")
async def check_api():
    return await api.health_check()

# All checks must pass for readiness
result = await checker.check_health()
```

### Example 16: Basic Tracing

```python
"""Example 16: Create trace spans."""
from obskit.tracing import trace_span

with trace_span("process_order", component="OrderService"):
    # This creates a trace span
    with trace_span("validate_payment", component="PaymentService"):
        validate_payment()
    
    with trace_span("update_inventory", component="InventoryService"):
        update_inventory()
```

### Example 17: Decorator with Custom Operation Name

```python
"""Example 17: Custom operation name in decorator."""
from obskit.decorators import with_observability

@with_observability(
    component="PaymentService",
    operation="process_payment"
)
async def handle_payment(amount: float, user_id: str):
    # Operation will be tracked as "process_payment"
    return process_payment(amount, user_id)
```

### Example 18: Metrics with Custom Labels

```python
"""Example 18: Metrics with custom labels."""
from obskit.metrics import REDMetrics

metrics = REDMetrics("api")

# Record with custom labels
metrics.request_count.labels(
    operation="get_user",
    status="success"
).inc()

metrics.error_count.labels(
    operation="get_user",
    error_type="NotFoundError"
).inc()
```

### Example 19: Simple Retry with Custom Exceptions

```python
"""Example 19: Retry only on specific exceptions."""
from obskit.resilience import retry

@retry(
    max_attempts=3,
    retry_on=(ConnectionError, TimeoutError)
)
async def fetch_with_retry():
    # Only retries on ConnectionError or TimeoutError
    # Other exceptions fail immediately
    return await http_client.get("https://api.example.com")
```

### Example 20: Circuit Breaker with Excluded Exceptions

```python
"""Example 20: Don't count certain exceptions as failures."""
from obskit.resilience import CircuitBreaker

breaker = CircuitBreaker(
    "payment_gateway",
    failure_threshold=5,
    excluded_exceptions=(ValueError,)  # Validation errors don't count
)

async def process_payment(amount):
    async with breaker:
        if amount < 0:
            raise ValueError("Invalid amount")  # Doesn't count as failure
        return await gateway.charge(amount)
```

### Example 21: Rate Limiter as Context Manager

```python
"""Example 21: Rate limiter as context manager."""
from obskit.resilience import RateLimiter

limiter = RateLimiter(requests=100, window_seconds=60)

async def process_batch():
    async with limiter:
        # Automatically acquires and releases
        return await process_item()
```

### Example 22: Log Performance Thresholds

```python
"""Example 22: Log when operations exceed threshold."""
from obskit.decorators import with_observability

@with_observability(
    component="DataProcessor",
    threshold_ms=1000  # Log warning if > 1 second
)
async def process_large_dataset():
    # Will log warning if takes > 1 second
    return process_data()
```

### Example 23: Track SLO for Latency

```python
"""Example 23: Track latency SLO."""
from obskit.slo import track_slo, SLOType

@track_slo(
    name="api_latency",
    slo_type=SLOType.LATENCY,
    target_value=0.5,  # 500ms p95
    percentile=95
)
async def handle_api_request():
    return await process_request()
```

### Example 24: Multiple Metrics Methods

```python
"""Example 24: Use different metrics methodologies."""
from obskit import configure
from obskit.metrics import REDMetrics, GoldenSignals, USEMetrics

# Configure to use all methods
configure(metrics_method="all")

# Use RED for service metrics
red = REDMetrics("api")

# Use Golden Signals for comprehensive monitoring
golden = GoldenSignals("api")

# Use USE for infrastructure
use = USEMetrics("server")
```

### Example 25: Structured Logging in JSON

```python
"""Example 25: JSON formatted logs for production."""
from obskit import configure, get_logger

# Configure JSON logging
configure(
    log_format="json",
    log_level="INFO"
)

logger = get_logger("service")

# Logs are automatically JSON formatted
logger.info(
    "order_created",
    order_id="12345",
    amount=99.99,
    user_id="user-123"
)
# Output: {"event": "order_created", "order_id": "12345", ...}
```

### Example 26: Console Logging for Development

```python
"""Example 26: Human-readable console logs."""
from obskit import configure, get_logger

# Configure console logging
configure(
    log_format="console",
    log_level="DEBUG"
)

logger = get_logger("service")
logger.debug("processing_request", request_id="req-123")
# Output: [DEBUG] processing_request request_id=req-123
```

### Example 27: Track Error Rate SLO

```python
"""Example 27: Track error rate SLO."""
from obskit.slo import track_slo, SLOType

@track_slo(
    name="api_error_rate",
    slo_type=SLOType.ERROR_RATE,
    target_value=0.01  # 1% error rate
)
async def handle_request():
    try:
        return await process()
    except Exception:
        # Error is automatically tracked
        raise
```

### Example 28: Basic Metrics Server

```python
"""Example 28: Start Prometheus metrics server."""
from obskit.metrics import start_http_server

# Start metrics server on default port 9090
start_http_server()

# Metrics available at http://localhost:9090/metrics
# Prometheus can scrape from this endpoint
```

### Example 29: Reset Metrics for Testing

```python
"""Example 29: Reset metrics between tests."""
from obskit.metrics.registry import reset_registry
import pytest

@pytest.fixture
def clean_metrics():
    """Reset metrics before each test."""
    reset_registry()
    yield
    reset_registry()
```

### Example 30: Simple Correlation ID Propagation

```python
"""Example 30: Propagate correlation ID across services."""
from obskit.core.context import correlation_context, get_correlation_id
from obskit.tracing import inject_trace_context
import httpx

async def call_downstream_service():
    # Get current correlation ID
    corr_id = get_correlation_id()
    
    # Inject into headers
    headers = {}
    inject_trace_context(headers)
    headers["X-Correlation-ID"] = corr_id
    
    # Call downstream service
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://downstream.example.com/api",
            headers=headers
        )
    return response.json()
```

---

## Intermediate Examples (31-60)

### Example 31: FastAPI Integration

```python
"""Example 31: Full FastAPI integration."""
from fastapi import FastAPI, Request
from obskit import configure, get_logger
from obskit.decorators import with_observability
from obskit.core.context import correlation_context
from obskit.metrics import REDMetrics
import uuid

app = FastAPI()
configure(service_name="api-service")
logger = get_logger("api")
metrics = REDMetrics("api")

@app.middleware("http")
async def add_correlation_id(request: Request, call_next):
    # Generate or extract correlation ID
    corr_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
    
    with correlation_context(corr_id):
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = corr_id
        return response

@app.get("/users/{user_id}")
@with_observability(component="UserAPI")
async def get_user(user_id: str):
    logger.info("fetching_user", user_id=user_id)
    return {"id": user_id, "name": "John"}
```

### Example 32: Database Operation Tracking

```python
"""Example 32: Track database operations."""
from obskit.metrics import REDMetrics
from obskit.decorators import with_observability
from contextlib import contextmanager

metrics = REDMetrics("database")

@contextmanager
def track_db_operation(operation: str):
    start = time.perf_counter()
    try:
        yield
        metrics.request_count.labels(
            operation=operation,
            status="success"
        ).inc()
    except Exception as e:
        metrics.error_count.labels(
            operation=operation,
            error_type=type(e).__name__
        ).inc()
        raise
    finally:
        duration = time.perf_counter() - start
        metrics.request_duration_histogram.labels(
            operation=operation
        ).observe(duration)

# Use it
with track_db_operation("select_users"):
    users = db.query("SELECT * FROM users")
```

### Example 33: Retry with Custom Backoff

```python
"""Example 33: Custom retry configuration."""
from obskit.resilience import retry

@retry(
    max_attempts=5,
    base_delay=0.5,
    max_delay=30.0,
    exponential_base=2.0,
    jitter=True
)
async def upload_file(file_data):
    # Retries with: 0.5s, 1s, 2s, 4s, 8s (with jitter)
    return await storage.upload(file_data)
```

### Example 34: Circuit Breaker State Monitoring

```python
"""Example 34: Monitor circuit breaker state."""
from obskit.resilience import CircuitBreaker
from obskit import get_logger

logger = get_logger("service")
breaker = CircuitBreaker("external_api")

async def check_breaker_status():
    if breaker.is_open:
        logger.warning("circuit_open", breaker=breaker.name)
        return {"status": "unavailable"}
    elif breaker.is_half_open:
        logger.info("circuit_half_open", breaker=breaker.name)
        return {"status": "testing"}
    else:
        return {"status": "available"}
```

### Example 35: Golden Signals Monitoring

```python
"""Example 35: Comprehensive monitoring with Golden Signals."""
from obskit.metrics import GoldenSignals

signals = GoldenSignals("api_service")

# Track traffic (rate)
signals.request_count.labels(operation="get_user", status="success").inc()

# Track errors
signals.error_count.labels(operation="get_user", error_type="NotFound").inc()

# Track latency
with signals.track_request(operation="get_user"):
    process_request()

# Track saturation (queue depth)
signals.queue_depth.labels(operation="get_user").set(5)

# Track saturation (resource usage)
signals.saturation.labels(resource="cpu").set(0.85)
```

### Example 36: USE Method for Infrastructure

```python
"""Example 36: Monitor infrastructure with USE method."""
from obskit.metrics import USEMetrics
import psutil

metrics = USEMetrics("server")

# Track CPU utilization
cpu_percent = psutil.cpu_percent(interval=1)
metrics.set_utilization("cpu", cpu_percent / 100.0)

# Track memory utilization
memory = psutil.virtual_memory()
metrics.set_utilization("memory", memory.percent / 100.0)

# Track saturation (load average)
load_avg = psutil.getloadavg()[0]
metrics.set_saturation("cpu", load_avg / psutil.cpu_count())

# Track errors
metrics.inc_error("disk", "read_error")
```

### Example 37: SLO Error Budget Tracking

```python
"""Example 37: Monitor SLO error budget."""
from obskit.slo import SLOTracker, SLOType

tracker = SLOTracker()

# Register SLO
tracker.register_slo(
    name="api_availability",
    slo_type=SLOType.AVAILABILITY,
    target_value=0.999,  # 99.9%
    window_seconds=86400  # 24 hours
)

# Record measurements
for i in range(1000):
    success = i < 999  # 1 failure
    tracker.record_measurement("api_availability", 1.0, success)

# Check status
status = tracker.get_status("api_availability")
print(f"Compliance: {status.compliance}")
print(f"Error Budget Remaining: {status.error_budget_remaining}")
print(f"Burn Rate: {status.error_budget_burn_rate}")
```

### Example 38: Distributed Tracing

```python
"""Example 38: Distributed tracing across services."""
from obskit.tracing import trace_span, inject_trace_context, extract_trace_context
import httpx

# Service A: Start trace and inject
async def service_a():
    with trace_span("service_a_operation"):
        headers = {}
        inject_trace_context(headers)
        
        # Call Service B
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "http://service-b/api",
                headers=headers
            )

# Service B: Extract and continue trace
async def service_b(request):
    headers = dict(request.headers)
    context = extract_trace_context(headers)
    
    with trace_span("service_b_operation"):
        # Process request
        return process()
```

### Example 39: Health Check with Dependencies

```python
"""Example 39: Health checks with dependency status."""
from obskit.health import HealthChecker

checker = HealthChecker()

@checker.add_readiness_check("database")
async def check_database():
    try:
        await db.ping()
        return {
            "healthy": True,
            "details": {
                "pool_size": db.pool.size,
                "active_connections": db.pool.active
            }
        }
    except Exception as e:
        return {
            "healthy": False,
            "error": str(e)
        }

@checker.add_liveness_check("main")
def check_alive():
    return {"healthy": True}
```

### Example 40: Metrics Aggregation

```python
"""Example 40: Aggregate metrics across operations."""
from obskit.metrics import REDMetrics

metrics = REDMetrics("service")

# Track multiple operations
operations = ["create_user", "update_user", "delete_user"]

for op in operations:
    with metrics.track_request(operation=op, status="success"):
        process_operation(op)

# Query aggregated metrics in Prometheus:
# sum(rate(service_requests_total[5m])) by (operation)
```

### Example 41: Custom Log Processors

```python
"""Example 41: Add custom context to all logs."""
from obskit.logging import get_logger, configure_logging
from obskit.core.context import get_correlation_id

def add_request_context(logger, method_name, event_dict):
    """Add request context to all log entries."""
    event_dict["correlation_id"] = get_correlation_id()
    event_dict["service"] = "user-service"
    return event_dict

# Configure with custom processor
configure_logging(processors=[add_request_context])
logger = get_logger("service")
```

### Example 42: Circuit Breaker with Monitoring

```python
"""Example 42: Monitor circuit breaker metrics."""
from obskit.resilience import CircuitBreaker
from obskit.metrics import Gauge

breaker = CircuitBreaker("payment_gateway")
state_gauge = Gauge("circuit_breaker_state", "Circuit breaker state", ["breaker"])

async def monitor_breaker():
    state = 0 if breaker.is_closed else (1 if breaker.is_half_open else 2)
    state_gauge.labels(breaker=breaker.name).set(state)
```

### Example 43: Rate Limiter with Burst

```python
"""Example 43: Rate limiter with burst capacity."""
from obskit.resilience import TokenBucketRateLimiter

# Allow bursts up to 20, refill at 10/second
limiter = TokenBucketRateLimiter(
    bucket_size=20,
    refill_rate=10.0
)

async def handle_burst_traffic():
    # Can handle up to 20 requests immediately
    # Then limited to 10/second
    async with limiter:
        return await process_request()
```

### Example 44: SLO with Multiple Targets

```python
"""Example 44: Track multiple SLOs."""
from obskit.slo import SLOTracker, SLOType

tracker = SLOTracker()

# Availability SLO
tracker.register_slo(
    name="api_availability",
    slo_type=SLOType.AVAILABILITY,
    target_value=0.999
)

# Latency SLO
tracker.register_slo(
    name="api_latency",
    slo_type=SLOType.LATENCY,
    target_value=0.5,  # 500ms
    percentile=95
)

# Error Rate SLO
tracker.register_slo(
    name="api_error_rate",
    slo_type=SLOType.ERROR_RATE,
    target_value=0.01  # 1%
)
```

### Example 45: Async Operation Tracking

```python
"""Example 45: Track async operations."""
from obskit.decorators import with_observability
import asyncio

@with_observability(component="DataProcessor")
async def process_batch(items):
    results = []
    for item in items:
        result = await process_item(item)
        results.append(result)
    return results

# Tracked as single operation
results = await process_batch([1, 2, 3, 4, 5])
```

### Example 46: Error Classification

```python
"""Example 46: Classify errors by type."""
from obskit.metrics import REDMetrics

metrics = REDMetrics("api")

try:
    process_request()
except ValueError as e:
    metrics.error_count.labels(
        operation="process_request",
        error_type="ValidationError"
    ).inc()
except ConnectionError as e:
    metrics.error_count.labels(
        operation="process_request",
        error_type="ConnectionError"
    ).inc()
except Exception as e:
    metrics.error_count.labels(
        operation="process_request",
        error_type="UnknownError"
    ).inc()
```

### Example 47: Metrics with Histogram Buckets

```python
"""Example 47: Custom histogram buckets."""
from obskit.metrics import REDMetrics

# Custom buckets for API latency
custom_buckets = [0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0, 10.0]

metrics = REDMetrics("api", custom_buckets=custom_buckets)

# Record latency
with metrics.track_request(operation="api_call"):
    await api_call()
```

### Example 48: Health Check with Timeout

```python
"""Example 48: Health checks with timeout."""
from obskit.health import HealthChecker
import asyncio

checker = HealthChecker()

@checker.add_readiness_check("external_api")
async def check_api_with_timeout():
    try:
        # Timeout after 2 seconds
        result = await asyncio.wait_for(
            api.health_check(),
            timeout=2.0
        )
        return {"healthy": True}
    except asyncio.TimeoutError:
        return {"healthy": False, "error": "Timeout"}
```

### Example 49: Correlation ID in Async Context

```python
"""Example 49: Correlation ID in async operations."""
from obskit.core.context import correlation_context
import asyncio

async def process_with_correlation(corr_id: str):
    with correlation_context(corr_id):
        # All operations in this context share correlation ID
        task1 = asyncio.create_task(operation_a())
        task2 = asyncio.create_task(operation_b())
        
        results = await asyncio.gather(task1, task2)
        return results
```

### Example 50: Metrics Export

```python
"""Example 50: Export metrics for Prometheus."""
from obskit.metrics.registry import generate_latest
from fastapi import Response

@app.get("/metrics")
async def metrics_endpoint():
    """Prometheus metrics endpoint."""
    metrics_data = generate_latest()
    return Response(
        content=metrics_data,
        media_type="text/plain; version=0.0.4"
    )
```

### Example 51: Retry with Exponential Backoff

```python
"""Example 51: Exponential backoff retry."""
from obskit.resilience import retry

@retry(
    max_attempts=5,
    base_delay=0.1,
    max_delay=10.0,
    exponential_base=2.0,
    jitter=True
)
async def fetch_with_backoff():
    # Delays: ~0.1s, ~0.2s, ~0.4s, ~0.8s, ~1.6s (with jitter)
    return await http_client.get("https://api.example.com")
```

### Example 52: Circuit Breaker Recovery

```python
"""Example 52: Monitor circuit breaker recovery."""
from obskit.resilience import CircuitBreaker
import asyncio

breaker = CircuitBreaker(
    "external_service",
    failure_threshold=5,
    recovery_timeout=30.0  # 30 seconds before retry
)

async def wait_for_recovery():
    if breaker.is_open:
        # Check time until retry
        # (Would need to expose this in CircuitBreaker)
        await asyncio.sleep(30)
        
        # Circuit should transition to half-open
        if breaker.is_half_open:
            # Try one request
            try:
                async with breaker:
                    return await call_service()
            except Exception:
                # Circuit opens again
                pass
```

### Example 53: Multi-Level Logging

```python
"""Example 53: Different log levels for different contexts."""
from obskit import get_logger

# Module-level logger
module_logger = get_logger("user_service.repository")

# Function-level logger with bound context
def get_user(user_id):
    logger = module_logger.bind(user_id=user_id)
    logger.debug("fetching_user_from_db")
    
    user = db.get(user_id)
    logger.info("user_fetched", found=user is not None)
    
    return user
```

### Example 54: SLO Window Management

```python
"""Example 54: SLO with rolling window."""
from obskit.slo import SLOTracker, SLOType
from datetime import datetime, timedelta

tracker = SLOTracker()

# Register SLO with 24-hour window
tracker.register_slo(
    name="daily_availability",
    slo_type=SLOType.AVAILABILITY,
    target_value=0.999,
    window_seconds=86400  # 24 hours
)

# Record measurements throughout the day
# Old measurements automatically expire after window
```

### Example 55: Metrics with Summary

```python
"""Example 55: Use Summary for pre-calculated percentiles."""
from obskit import configure
from obskit.metrics import REDMetrics

# Enable summaries
configure(use_summary=True)

metrics = REDMetrics("api")

# Summary provides quantiles automatically
with metrics.track_request(operation="process"):
    process()
    
# Query: api_request_duration_quantiles{quantile="0.95"}
```

### Example 56: Health Check Aggregation

```python
"""Example 56: Aggregate health from multiple services."""
from obskit.health import HealthChecker

checker = HealthChecker()

@checker.add_readiness_check("all_services")
async def check_all_services():
    services = ["db", "cache", "queue", "storage"]
    results = {}
    
    for service in services:
        try:
            health = await check_service(service)
            results[service] = health
        except Exception as e:
            results[service] = {"healthy": False, "error": str(e)}
    
    all_healthy = all(r.get("healthy", False) for r in results.values())
    return {
        "healthy": all_healthy,
        "services": results
    }
```

### Example 57: Trace Context Propagation

```python
"""Example 57: Propagate trace context in async tasks."""
from obskit.tracing import trace_span, inject_trace_context
import asyncio

async def parent_operation():
    with trace_span("parent"):
        # Create child tasks that inherit trace context
        tasks = [
            child_operation(i)
            for i in range(5)
        ]
        await asyncio.gather(*tasks)

async def child_operation(index: int):
    with trace_span(f"child_{index}"):
        # This span is a child of parent span
        await process(index)
```

### Example 58: Rate Limiter Per User

```python
"""Example 58: Per-user rate limiting."""
from obskit.resilience import RateLimiter
from collections import defaultdict

# Rate limiters per user
user_limiters = defaultdict(
    lambda: RateLimiter(requests=100, window_seconds=60)
)

async def handle_user_request(user_id: str):
    limiter = user_limiters[user_id]
    
    if not await limiter.acquire():
        raise RateLimitExceeded(f"User {user_id} exceeded rate limit")
    
    return await process_request(user_id)
```

### Example 59: SLO Alerting

```python
"""Example 59: Alert when SLO is at risk."""
from obskit.slo import SLOTracker, SLOType

tracker = SLOTracker()

tracker.register_slo(
    name="api_availability",
    slo_type=SLOType.AVAILABILITY,
    target_value=0.999
)

def check_slo_health():
    status = tracker.get_status("api_availability")
    
    # Alert if error budget < 10%
    if status.error_budget_remaining < 0.1:
        send_alert("SLO error budget critical!")
    
    # Alert if burn rate > 2x
    if status.error_budget_burn_rate > 2.0:
        send_alert("SLO burn rate too high!")
```

### Example 60: Comprehensive Service Monitoring

```python
"""Example 60: Full observability stack."""
from obskit import configure, get_logger
from obskit.metrics import GoldenSignals
from obskit.decorators import with_observability
from obskit.slo import track_slo, SLOType

configure(service_name="payment-service")

logger = get_logger("payment")
metrics = GoldenSignals("payment")

@with_observability(component="PaymentService")
@track_slo(
    name="payment_availability",
    slo_type=SLOType.AVAILABILITY,
    target_value=0.999
)
async def process_payment(amount: float):
    logger.info("payment_started", amount=amount)
    
    with metrics.track_request(operation="process_payment"):
        result = await gateway.charge(amount)
        
        logger.info("payment_completed", transaction_id=result.id)
        return result
```

---

## Advanced Examples (61-85)

### Example 61: Custom Metrics Collector

```python
"""Example 61: Custom metrics beyond RED/Golden/USE."""
from obskit.metrics.types import Counter, Histogram, Gauge
from obskit.metrics.registry import get_registry

# Create custom metrics
custom_counter = Counter(
    "custom_events_total",
    "Total custom events",
    ["event_type"]
)

custom_histogram = Histogram(
    "custom_duration_seconds",
    "Custom operation duration",
    ["operation"]
)

# Use them
custom_counter.labels(event_type="user_action").inc()
custom_histogram.labels(operation="custom_op").observe(0.5)
```

### Example 62: Distributed Tracing with Baggage

```python
"""Example 62: Propagate custom context via trace baggage."""
from obskit.tracing import trace_span, inject_trace_context
from opentelemetry import baggage

async def service_a():
    with trace_span("service_a"):
        # Set baggage
        ctx = baggage.set_baggage("user_id", "12345")
        
        headers = {}
        inject_trace_context(headers)
        
        # Call service B
        await call_service_b(headers)

async def service_b(headers):
    # Extract baggage
    ctx = extract_trace_context(headers)
    user_id = baggage.get_baggage("user_id", context=ctx)
    
    with trace_span("service_b"):
        process(user_id)
```

### Example 63: Circuit Breaker with Metrics

```python
"""Example 63: Track circuit breaker state changes."""
from obskit.resilience import CircuitBreaker
from obskit.metrics.types import Counter, Gauge

breaker = CircuitBreaker("external_api")
state_changes = Counter(
    "circuit_breaker_state_changes_total",
    "Circuit breaker state changes",
    ["breaker", "from_state", "to_state"]
)
current_state = Gauge(
    "circuit_breaker_state",
    "Current circuit breaker state",
    ["breaker"]
)

# Monitor state changes
original_record_failure = breaker._record_failure

async def monitored_record_failure(self, error):
    old_state = self._state
    await original_record_failure(error)
    if self._state != old_state:
        state_changes.labels(
            breaker=self.name,
            from_state=old_state.value,
            to_state=self._state.value
        ).inc()
```

### Example 64: Advanced Retry Strategies

```python
"""Example 64: Retry with different strategies per exception."""
from obskit.resilience import retry

# Retry connection errors more aggressively
@retry(
    max_attempts=10,
    base_delay=0.1,
    retry_on=(ConnectionError,)
)
async def connect_with_retry():
    return await connect()

# Retry validation errors less aggressively
@retry(
    max_attempts=2,
    base_delay=1.0,
    retry_on=(ValueError,)
)
async def validate_with_retry():
    return await validate()
```

### Example 65: Multi-Tenant Metrics

```python
"""Example 65: Separate metrics per tenant."""
from obskit.metrics import REDMetrics
from functools import lru_cache

@lru_cache(maxsize=100)
def get_tenant_metrics(tenant_id: str):
    """Get metrics instance for tenant."""
    return REDMetrics(f"tenant_{tenant_id}")

async def handle_tenant_request(tenant_id: str, operation: str):
    metrics = get_tenant_metrics(tenant_id)
    
    with metrics.track_request(operation=operation):
        return await process_tenant_request(tenant_id)
```

### Example 66: SLO with Multiple Percentiles

```python
"""Example 66: Track multiple latency percentiles."""
from obskit.slo import SLOTracker, SLOType

tracker = SLOTracker()

# P50 latency
tracker.register_slo(
    name="api_latency_p50",
    slo_type=SLOType.LATENCY,
    target_value=0.1,
    percentile=50
)

# P95 latency
tracker.register_slo(
    name="api_latency_p95",
    slo_type=SLOType.LATENCY,
    target_value=0.5,
    percentile=95
)

# P99 latency
tracker.register_slo(
    name="api_latency_p99",
    slo_type=SLOType.LATENCY,
    target_value=1.0,
    percentile=99
)
```

### Example 67: Custom Health Check Logic

```python
"""Example 67: Complex health check with dependencies."""
from obskit.health import HealthChecker
from obskit.metrics import Gauge

checker = HealthChecker()
health_gauge = Gauge("service_health", "Service health status", ["service"])

@checker.add_readiness_check("complex")
async def complex_health_check():
    checks = {}
    
    # Check database
    try:
        db_healthy = await db.ping()
        checks["database"] = db_healthy
    except Exception as e:
        checks["database"] = False
        checks["database_error"] = str(e)
    
    # Check cache
    try:
        cache_healthy = await cache.ping()
        checks["cache"] = cache_healthy
    except Exception:
        checks["cache"] = False
    
    # Check external API
    try:
        api_healthy = await api.health_check()
        checks["api"] = api_healthy
    except Exception:
        checks["api"] = False
    
    overall_healthy = all([
        checks.get("database", False),
        checks.get("cache", False)
    ])
    
    # Update metrics
    health_gauge.labels(service="main").set(1 if overall_healthy else 0)
    
    return {
        "healthy": overall_healthy,
        "checks": checks
    }
```

### Example 68: Trace Sampling

```python
"""Example 68: Sample traces to reduce overhead."""
from obskit.tracing import trace_span
import random

def should_sample():
    """Sample 10% of traces."""
    return random.random() < 0.1

def traced_operation():
    if should_sample():
        with trace_span("operation"):
            return process()
    else:
        return process()
```

### Example 69: Metrics Aggregation Pipeline

```python
"""Example 69: Aggregate metrics from multiple sources."""
from obskit.metrics import REDMetrics
from obskit.metrics.types import Counter

# Service-level metrics
service_metrics = REDMetrics("service")

# Aggregate counter across all services
aggregate_counter = Counter(
    "all_services_requests_total",
    "Total requests across all services",
    ["operation"]
)

def record_aggregate(operation: str):
    """Record in both service and aggregate metrics."""
    service_metrics.request_count.labels(
        operation=operation,
        status="success"
    ).inc()
    
    aggregate_counter.labels(operation=operation).inc()
```

### Example 70: Circuit Breaker with Fallback

```python
"""Example 70: Circuit breaker with fallback mechanism."""
from obskit.resilience import CircuitBreaker

breaker = CircuitBreaker("primary_service")

async def call_with_fallback():
    try:
        async with breaker:
            return await primary_service.call()
    except Exception:
        # Fallback to secondary service
        return await secondary_service.call()
```

### Example 71: Rate Limiter with Priority

```python
"""Example 71: Priority-based rate limiting."""
from obskit.resilience import RateLimiter

# Different limiters for different priorities
high_priority = RateLimiter(requests=1000, window_seconds=60)
low_priority = RateLimiter(requests=100, window_seconds=60)

async def process_request(priority: str):
    limiter = high_priority if priority == "high" else low_priority
    
    if await limiter.acquire():
        return await process()
    else:
        raise RateLimitExceeded()
```

### Example 72: SLO with Alerting Rules

```python
"""Example 72: SLO-based alerting."""
from obskit.slo import SLOTracker, SLOType
from datetime import datetime

tracker = SLOTracker()

tracker.register_slo(
    name="api_availability",
    slo_type=SLOType.AVAILABILITY,
    target_value=0.999
)

def check_and_alert():
    status = tracker.get_status("api_availability")
    
    # Alert conditions
    if not status.compliance:
        send_critical_alert("SLO violated!")
    
    if status.error_budget_remaining < 0.2:
        send_warning_alert("Error budget running low")
    
    if status.error_budget_burn_rate > 5.0:
        send_critical_alert("Error budget burning too fast!")
```

### Example 73: Custom Log Formatting

```python
"""Example 73: Custom log formatter."""
from obskit.logging import configure_logging
import structlog

def custom_formatter(logger, method_name, event_dict):
    """Custom log formatter."""
    # Add timestamp
    event_dict["timestamp"] = datetime.utcnow().isoformat()
    
    # Add service name
    event_dict["service"] = "user-service"
    
    # Format error stack traces
    if "exception" in event_dict:
        event_dict["stack"] = traceback.format_exc()
    
    return event_dict

configure_logging(processors=[custom_formatter])
```

### Example 74: Metrics with Labels from Context

```python
"""Example 74: Add labels from request context."""
from obskit.metrics import REDMetrics
from obskit.core.context import get_correlation_id

metrics = REDMetrics("api")

def get_request_labels():
    """Get labels from request context."""
    return {
        "environment": os.getenv("ENVIRONMENT", "unknown"),
        "version": get_version(),
        "region": get_region()
    }

async def handle_request():
    labels = get_request_labels()
    
    with metrics.track_request(
        operation="handle_request",
        **labels
    ):
        return await process()
```

### Example 75: Distributed Tracing with Sampling

```python
"""Example 75: Trace sampling based on operation."""
from obskit.tracing import trace_span

def should_trace(operation: str):
    """Sample important operations more frequently."""
    important_ops = ["payment", "order", "checkout"]
    return operation in important_ops or random.random() < 0.1

def traced_operation(operation: str):
    if should_trace(operation):
        with trace_span(operation):
            return process()
    else:
        return process()
```

### Example 76: Circuit Breaker with Metrics Export

```python
"""Example 76: Export circuit breaker metrics."""
from obskit.resilience import CircuitBreaker
from obskit.metrics.types import Gauge, Counter

breaker = CircuitBreaker("service")

# Export state
state_gauge = Gauge(
    "circuit_breaker_state",
    "Circuit breaker state (0=closed, 1=half-open, 2=open)",
    ["breaker"]
)

# Export transitions
transition_counter = Counter(
    "circuit_breaker_transitions_total",
    "Circuit breaker state transitions",
    ["breaker", "from", "to"]
)

def update_metrics():
    state = 0 if breaker.is_closed else (1 if breaker.is_half_open else 2)
    state_gauge.labels(breaker=breaker.name).set(state)
```

### Example 77: Multi-Region Metrics

```python
"""Example 77: Track metrics per region."""
from obskit.metrics import REDMetrics
import os

region = os.getenv("AWS_REGION", "unknown")

metrics = REDMetrics(f"api_{region}")

# All metrics automatically tagged with region
with metrics.track_request(operation="api_call"):
    process()
```

### Example 78: SLO with Custom Windows

```python
"""Example 78: SLO with different time windows."""
from obskit.slo import SLOTracker, SLOType

tracker = SLOTracker()

# Hourly SLO
tracker.register_slo(
    name="hourly_availability",
    slo_type=SLOType.AVAILABILITY,
    target_value=0.99,
    window_seconds=3600  # 1 hour
)

# Daily SLO
tracker.register_slo(
    name="daily_availability",
    slo_type=SLOType.AVAILABILITY,
    target_value=0.999,
    window_seconds=86400  # 24 hours
)

# Weekly SLO
tracker.register_slo(
    name="weekly_availability",
    slo_type=SLOType.AVAILABILITY,
    target_value=0.9999,
    window_seconds=604800  # 7 days
)
```

### Example 79: Advanced Correlation ID Usage

```python
"""Example 79: Correlation ID across async boundaries."""
from obskit.core.context import correlation_context, get_correlation_id
import asyncio

async def process_with_correlation(corr_id: str):
    with correlation_context(corr_id):
        # Create tasks that inherit correlation ID
        tasks = [
            async_operation(i)
            for i in range(10)
        ]
        
        results = await asyncio.gather(*tasks)
        return results

async def async_operation(index: int):
    # Correlation ID is automatically available
    corr_id = get_correlation_id()
    logger.info("operation_started", index=index, correlation_id=corr_id)
    return await process(index)
```

### Example 80: Metrics with Custom Registry

```python
"""Example 80: Use custom Prometheus registry."""
from obskit.metrics.registry import create_registry
from obskit.metrics import REDMetrics

# Create isolated registry for testing
test_registry = create_registry()

# Use it for metrics
metrics = REDMetrics("test_service", registry=test_registry)

# Metrics isolated from production
with metrics.track_request(operation="test"):
    test_operation()
```

### Example 81: Health Check with Degraded State

```python
"""Example 81: Health check with degraded mode."""
from obskit.health import HealthChecker

checker = HealthChecker()

@checker.add_readiness_check("service")
async def check_service():
    # Check primary dependency
    primary_healthy = await check_primary()
    
    # Check secondary dependency
    secondary_healthy = await check_secondary()
    
    if primary_healthy and secondary_healthy:
        return {"healthy": True, "mode": "full"}
    elif primary_healthy:
        return {"healthy": True, "mode": "degraded"}
    else:
        return {"healthy": False, "mode": "unavailable"}
```

### Example 82: Trace with Custom Attributes

```python
"""Example 82: Add custom attributes to traces."""
from obskit.tracing import trace_span

with trace_span(
    "process_order",
    attributes={
        "order_id": "12345",
        "amount": 99.99,
        "currency": "USD",
        "payment_method": "credit_card"
    }
):
    process_order()
```

### Example 83: Rate Limiter with Dynamic Limits

```python
"""Example 83: Adjust rate limits dynamically."""
from obskit.resilience import RateLimiter

class DynamicRateLimiter:
    def __init__(self):
        self.limiter = RateLimiter(requests=100, window_seconds=60)
        self.base_requests = 100
    
    def adjust_limit(self, multiplier: float):
        """Adjust rate limit based on load."""
        new_limit = int(self.base_requests * multiplier)
        # Create new limiter with adjusted limit
        self.limiter = RateLimiter(
            requests=new_limit,
            window_seconds=60
        )
    
    async def acquire(self):
        return await self.limiter.acquire()
```

### Example 84: SLO with Error Budget Policies

```python
"""Example 84: Error budget policy enforcement."""
from obskit.slo import SLOTracker, SLOType

tracker = SLOTracker()

tracker.register_slo(
    name="api_availability",
    slo_type=SLOType.AVAILABILITY,
    target_value=0.999
)

def enforce_error_budget():
    status = tracker.get_status("api_availability")
    
    # Policy: If error budget < 5%, disable non-critical features
    if status.error_budget_remaining < 0.05:
        disable_non_critical_features()
        send_alert("Error budget critical - non-critical features disabled")
    
    # Policy: If error budget exhausted, enter maintenance mode
    if status.error_budget_remaining <= 0:
        enter_maintenance_mode()
        send_critical_alert("Error budget exhausted - maintenance mode")
```

### Example 85: Comprehensive Observability Decorator

```python
"""Example 85: Full observability with all features."""
from obskit.decorators import with_observability
from obskit.slo import track_slo, SLOType

@with_observability(
    component="PaymentService",
    operation="process_payment",
    track_metrics=True,
    track_tracing=True,
    log_start=True,
    threshold_ms=1000
)
@track_slo(
    name="payment_availability",
    slo_type=SLOType.AVAILABILITY,
    target_value=0.999
)
async def process_payment(amount: float, user_id: str):
    """Fully observable payment processing."""
    # Automatically:
    # - Traced with OpenTelemetry
    # - Metrics recorded (RED method)
    # - Logged (start/end)
    # - SLO tracked
    # - Performance warnings if > threshold
    return await gateway.charge(amount, user_id)
```

---

## Edge Cases & Real-World Scenarios (86-100+)

### Example 86: Handling Missing Dependencies

```python
"""Example 86: Graceful handling when dependencies missing."""
from obskit.metrics import REDMetrics
from obskit.metrics.registry import PROMETHEUS_AVAILABLE

if PROMETHEUS_AVAILABLE:
    metrics = REDMetrics("service")
    # Use metrics
else:
    # Fallback to logging only
    logger.warning("metrics_unavailable", message="Prometheus not installed")
```

### Example 87: High-Volume Request Handling

```python
"""Example 87: Efficient metrics for high-volume operations."""
from obskit.metrics import REDMetrics
from obskit.decorators import with_observability

# Use decorator for automatic tracking
@with_observability(component="HighVolumeService")
async def handle_high_volume_request():
    # Decorator efficiently tracks without manual code
    return await process()
```

### Example 88: Long-Running Operations

```python
"""Example 88: Track long-running background jobs."""
from obskit.metrics import Gauge
from obskit.tracing import trace_span

job_gauge = Gauge("background_jobs_running", "Running background jobs", ["job_type"])

async def long_running_job():
    job_gauge.labels(job_type="data_processing").inc()
    
    try:
        with trace_span("long_running_job"):
            await process_large_dataset()
    finally:
        job_gauge.labels(job_type="data_processing").dec()
```

### Example 89: Circuit Breaker in High Concurrency

```python
"""Example 89: Circuit breaker with many concurrent requests."""
from obskit.resilience import CircuitBreaker
import asyncio

breaker = CircuitBreaker("external_api")

async def handle_concurrent_requests(requests: list):
    # All requests share the same circuit breaker
    tasks = [
        process_with_breaker(req)
        for req in requests
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return results

async def process_with_breaker(request):
    try:
        async with breaker:
            return await process(request)
    except Exception as e:
        return {"error": str(e)}
```

### Example 90: Metrics Cardinality Management

```python
"""Example 90: Avoid high cardinality in metrics."""
from obskit.metrics import REDMetrics

metrics = REDMetrics("api")

# BAD: High cardinality (user_id can be millions)
# metrics.request_count.labels(operation="get_user", user_id=user_id).inc()

# GOOD: Low cardinality (only operation)
metrics.request_count.labels(operation="get_user", status="success").inc()

# Track user-specific metrics separately if needed
user_metrics = Counter("user_requests_total", "User requests", ["user_tier"])
user_metrics.labels(user_tier=get_user_tier(user_id)).inc()
```

### Example 91: SLO with Burst Traffic

```python
"""Example 91: Handle SLO during traffic bursts."""
from obskit.slo import SLOTracker, SLOType

tracker = SLOTracker()

tracker.register_slo(
    name="api_availability",
    slo_type=SLOType.AVAILABILITY,
    target_value=0.999,
    window_seconds=3600  # 1 hour window
)

async def handle_burst():
    # During burst, record all requests
    # SLO calculation handles burst automatically
    for request in burst_requests:
        try:
            result = await process(request)
            tracker.record_measurement("api_availability", 1.0, True)
        except Exception:
            tracker.record_measurement("api_availability", 1.0, False)
```

### Example 92: Trace Context in Threads

```python
"""Example 92: Preserve trace context across threads."""
from obskit.tracing import trace_span, inject_trace_context
from obskit.core.context import correlation_context
import threading

def process_in_thread():
    with trace_span("thread_operation"):
        # Trace context preserved
        process()

def main():
    with trace_span("main_operation"):
        # Create thread with context
        thread = threading.Thread(target=process_in_thread)
        thread.start()
        thread.join()
```

### Example 93: Health Check with Caching

```python
"""Example 93: Cache health check results."""
from obskit.health import HealthChecker
from functools import lru_cache
import time

checker = HealthChecker()
last_check = {}
check_cache_ttl = 5.0  # 5 seconds

@checker.add_readiness_check("cached")
def cached_health_check():
    now = time.time()
    
    # Return cached result if recent
    if "result" in last_check:
        if now - last_check["time"] < check_cache_ttl:
            return last_check["result"]
    
    # Perform actual check
    result = perform_expensive_check()
    last_check["result"] = result
    last_check["time"] = now
    
    return result
```

### Example 94: Metrics with Histogram vs Summary

```python
"""Example 94: Choose between histogram and summary."""
from obskit import configure
from obskit.metrics import REDMetrics

# Use histogram for aggregatable metrics (multi-instance)
configure(use_histogram=True, use_summary=False)
metrics = REDMetrics("api")

# Histogram allows aggregation across instances
# Query: histogram_quantile(0.95, rate(api_request_duration_seconds_bucket[5m]))

# Use summary for single-instance deployments
configure(use_histogram=False, use_summary=True)
metrics = REDMetrics("api")

# Summary provides exact percentiles but not aggregatable
```

### Example 95: Circuit Breaker with Half-Open Testing

```python
"""Example 95: Controlled testing in half-open state."""
from obskit.resilience import CircuitBreaker

breaker = CircuitBreaker(
    "external_service",
    failure_threshold=5,
    recovery_timeout=30.0,
    half_open_requests=3  # Allow 3 test requests
)

async def call_with_testing():
    async with breaker:
        # In half-open state, only limited requests allowed
        # If all succeed, circuit closes
        # If any fail, circuit opens again
        return await call_service()
```

### Example 96: Rate Limiter with Sliding Window

```python
"""Example 96: Sliding window rate limiter."""
from obskit.resilience import SlidingWindowRateLimiter

# Sliding window provides smoother rate limiting
limiter = SlidingWindowRateLimiter(
    requests=100,
    window_seconds=60
)

async def handle_request():
    if await limiter.acquire():
        return await process()
    else:
        raise RateLimitExceeded()
```

### Example 97: SLO with Multiple Measurement Types

```python
"""Example 97: Track different measurement types."""
from obskit.slo import SLOTracker, SLOType

tracker = SLOTracker()

# Track availability (success/failure)
tracker.register_slo(
    name="api_availability",
    slo_type=SLOType.AVAILABILITY,
    target_value=0.999
)

# Track latency (duration)
tracker.register_slo(
    name="api_latency",
    slo_type=SLOType.LATENCY,
    target_value=0.5,
    percentile=95
)

# Track error rate
tracker.register_slo(
    name="api_error_rate",
    slo_type=SLOType.ERROR_RATE,
    target_value=0.01
)

# Track throughput (requests per second)
tracker.register_slo(
    name="api_throughput",
    slo_type=SLOType.THROUGHPUT,
    target_value=1000.0
)
```

### Example 98: Correlation ID in Microservices

```python
"""Example 98: Correlation ID across microservices."""
from obskit.core.context import correlation_context, get_correlation_id
from obskit.tracing import inject_trace_context
import httpx

# Service A
async def service_a_handler(request):
    corr_id = request.headers.get("X-Correlation-ID", generate_id())
    
    with correlation_context(corr_id):
        # Call Service B
        headers = {}
        inject_trace_context(headers)
        headers["X-Correlation-ID"] = corr_id
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "http://service-b/api",
                headers=headers
            )
        
        return response.json()

# Service B
async def service_b_handler(request):
    corr_id = request.headers.get("X-Correlation-ID")
    
    with correlation_context(corr_id):
        # All logs include correlation ID
        logger.info("processing_request")
        return await process()
```

### Example 99: Metrics Export with Filtering

```python
"""Example 99: Filter metrics for export."""
from obskit.metrics.registry import generate_latest, get_registry
from prometheus_client import REGISTRY

def generate_filtered_metrics(exclude_patterns: list):
    """Generate metrics excluding certain patterns."""
    registry = get_registry()
    
    # Filter out internal metrics
    filtered = []
    for metric in registry.collect():
        if not any(pattern in metric.name for pattern in exclude_patterns):
            filtered.append(metric)
    
    return generate_latest(filtered)

# Export only public metrics
public_metrics = generate_filtered_metrics(["internal_", "debug_"])
```

### Example 100: Complete Microservice Example

```python
"""Example 100: Complete microservice with full observability."""
from fastapi import FastAPI, Request
from obskit import configure, get_logger
from obskit.decorators import with_observability
from obskit.core.context import correlation_context
from obskit.metrics import GoldenSignals
from obskit.health import HealthChecker
from obskit.slo import track_slo, SLOType
from obskit.resilience import CircuitBreaker, retry
import uuid

# Configuration
configure(
    service_name="user-service",
    environment="production",
    log_level="INFO",
    tracing_enabled=True,
    metrics_enabled=True
)

# Initialize
app = FastAPI()
logger = get_logger("user_service")
metrics = GoldenSignals("user_service")
checker = HealthChecker()
db_breaker = CircuitBreaker("database", failure_threshold=5)

# Middleware
@app.middleware("http")
async def observability_middleware(request: Request, call_next):
    corr_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
    
    with correlation_context(corr_id):
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = corr_id
        return response

# Health checks
@checker.add_readiness_check("database")
async def check_db():
    return await db.ping()

@checker.add_liveness_check("service")
def check_alive():
    return {"healthy": True}

@app.get("/health")
async def health():
    return (await checker.check_health()).to_dict()

# Business logic with full observability
@with_observability(component="UserService", operation="get_user")
@track_slo(
    name="user_api_availability",
    slo_type=SLOType.AVAILABILITY,
    target_value=0.999
)
@retry(max_attempts=3, base_delay=0.1)
async def get_user(user_id: str):
    logger.info("fetching_user", user_id=user_id)
    
    try:
        async with db_breaker:
            user = await db.get_user(user_id)
        
        logger.info("user_found", user_id=user_id)
        return user
    except Exception as e:
        logger.error("user_fetch_failed", user_id=user_id, error=str(e))
        raise

@app.get("/users/{user_id}")
async def get_user_endpoint(user_id: str):
    return await get_user(user_id)

# Metrics endpoint
@app.get("/metrics")
async def metrics_endpoint():
    from obskit.metrics.registry import generate_latest
    from fastapi import Response
    return Response(
        content=generate_latest(),
        media_type="text/plain; version=0.0.4"
    )
```

### Example 101: Error Budget Policy

```python
"""Example 101: Implement error budget policies."""
from obskit.slo import SLOTracker, SLOType

tracker = SLOTracker()

tracker.register_slo(
    name="api_availability",
    slo_type=SLOType.AVAILABILITY,
    target_value=0.999
)

def check_error_budget_policy():
    status = tracker.get_status("api_availability")
    
    # Policy 1: Alert at 50% budget remaining
    if status.error_budget_remaining < 0.5:
        send_warning("Error budget at 50%")
    
    # Policy 2: Disable features at 25%
    if status.error_budget_remaining < 0.25:
        disable_optional_features()
    
    # Policy 3: Emergency mode at 10%
    if status.error_budget_remaining < 0.1:
        enable_emergency_mode()
    
    # Policy 4: Maintenance at 0%
    if status.error_budget_remaining <= 0:
        schedule_maintenance()
```

### Example 102: Distributed Tracing with Context Propagation

```python
"""Example 102: Full distributed tracing setup."""
from obskit.tracing import (
    trace_span,
    inject_trace_context,
    extract_trace_context
)
import httpx

# Service A
async def service_a():
    with trace_span("service_a_operation") as span:
        # Add custom attributes
        span.set_attribute("user_id", "12345")
        
        # Inject context for downstream calls
        headers = {}
        inject_trace_context(headers)
        
        # Call Service B
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://service-b/process",
                headers=headers,
                json={"data": "value"}
            )
        
        return response.json()

# Service B
async def service_b(request):
    # Extract context
    headers = dict(request.headers)
    context = extract_trace_context(headers)
    
    with trace_span("service_b_operation"):
        # This span is a child of service_a_operation
        return await process(request.json())
```

---

## Summary

This comprehensive guide covers:

- **30 Beginner Examples**: Basic usage patterns for getting started
- **30 Intermediate Examples**: Real-world patterns and integrations
- **25 Advanced Examples**: Complex scenarios and optimizations
- **17+ Edge Cases**: Handling edge cases and production scenarios

Total: **102+ real-world examples** covering all aspects of the `obskit` package.

Each example is production-ready and demonstrates best practices for observability in microservices.

