# Resilience Patterns Guide

Complete guide to circuit breakers, retry, and rate limiting.

---

## Overview

| Pattern | Purpose | Use When |
|---------|---------|----------|
| **Circuit Breaker** | Fail fast | External service unreliable |
| **Retry** | Handle transient failures | Network glitches |
| **Rate Limiting** | Protect resources | Prevent overload |

---

## Circuit Breaker

Prevents cascading failures by failing fast when downstream services are unhealthy.

### States

```
CLOSED → OPEN → HALF_OPEN → CLOSED
   ↓       ↓        ↓
Failures  Timeout   Test
exceed    expires   succeeds
threshold
```

### Basic Usage

```python
from obskit.resilience import CircuitBreaker, CircuitOpenError

breaker = CircuitBreaker(
    name="payment_api",
    failure_threshold=5,      # Open after 5 failures
    recovery_timeout=30.0,    # Wait 30s before testing
    half_open_requests=3,     # Test with 3 requests
)

# Async usage (recommended)
async def process_payment(order_id: str, amount: float):
    try:
        async with breaker:
            return await payment_api.charge(order_id, amount)
    except CircuitOpenError as e:
        # Circuit is open - fail fast
        raise PaymentUnavailableError(
            f"Payment service unavailable. Retry in {e.time_until_retry:.0f}s"
        )

# Sync usage
def process_payment_sync(order_id: str, amount: float):
    try:
        with breaker:
            return payment_api.charge(order_id, amount)
    except CircuitOpenError:
        raise PaymentUnavailableError("Service unavailable")
```

### Configuration Options

```python
breaker = CircuitBreaker(
    name="external_api",
    
    # When to open
    failure_threshold=5,      # 5 consecutive failures
    
    # Recovery
    recovery_timeout=30.0,    # Wait 30s before testing
    half_open_requests=3,     # Test with 3 requests
)
```

### Circuit State Metrics

```promql
# Circuit breaker state
circuit_breaker_state{name="payment_api"}

# Failure count
circuit_breaker_failures_total{name="payment_api"}

# Success count
circuit_breaker_successes_total{name="payment_api"}
```

---

## Distributed Circuit Breaker

Share circuit state across multiple instances via Redis.

### Setup

```python
from obskit.resilience.distributed import DistributedCircuitBreaker
import redis

# Create Redis client
redis_client = redis.Redis(
    host="redis.example.com",
    port=6379,
    password=os.getenv("REDIS_PASSWORD"),
    ssl=True,
)

# Create distributed breaker
breaker = DistributedCircuitBreaker(
    name="payment_api",
    redis_client=redis_client,
    failure_threshold=10,      # Higher for distributed
    recovery_timeout=60.0,
    half_open_requests=3,
    key_prefix="obskit:cb:",   # Redis key prefix
    ttl_seconds=3600,          # State TTL
)

# Usage is the same
async with breaker:
    result = await payment_api.charge(order_id, amount)
```

### Async Redis Client

```python
import redis.asyncio as aioredis

# Async Redis client
redis_client = aioredis.Redis(
    host="redis.example.com",
    port=6379,
)

# Works with both sync and async Redis
breaker = DistributedCircuitBreaker(
    name="payment_api",
    redis_client=redis_client,
)
```

### Benefits

| Feature | Local CB | Distributed CB |
|---------|----------|----------------|
| Instance isolation | Each instance separate | Shared state |
| Failure detection | Per-instance | Across all instances |
| Recovery sync | Per-instance | Coordinated |
| Redis dependency | No | Yes |

---

## Retry with Backoff

Handle transient failures with exponential backoff.

### Basic Usage

```python
from obskit.resilience import retry, retry_async

# Async retry
@retry_async(
    max_attempts=3,
    base_delay=1.0,
    max_delay=30.0,
    exponential=True,
    jitter=True,
)
async def fetch_data():
    return await api.get("/data")

# Sync retry
@retry(
    max_attempts=3,
    base_delay=1.0,
)
def fetch_data_sync():
    return api.get("/data")
```

### Configuration Options

```python
@retry_async(
    max_attempts=5,           # Total attempts
    base_delay=1.0,           # Initial delay (seconds)
    max_delay=60.0,           # Maximum delay cap
    exponential=True,         # Use exponential backoff
    exponential_base=2.0,     # Multiplier
    jitter=True,              # Add randomness
    retryable_exceptions=(    # Only retry these
        TimeoutError,
        ConnectionError,
    ),
)
async def call_api():
    return await api.call()
```

### Backoff Calculation

```
Attempt 1: base_delay * (base ^ 0) = 1.0s
Attempt 2: base_delay * (base ^ 1) = 2.0s
Attempt 3: base_delay * (base ^ 2) = 4.0s
Attempt 4: base_delay * (base ^ 3) = 8.0s
... capped at max_delay
```

With jitter, actual delay is `random(0, calculated_delay)`.

### RetryConfig Class

```python
from obskit.resilience import RetryConfig, retry_async

config = RetryConfig(
    max_attempts=5,
    base_delay=0.5,
    max_delay=30.0,
    exponential=True,
    jitter=True,
)

@retry_async(config=config)
async def call_api():
    return await api.call()
```

### Retry with Circuit Breaker

```python
@retry_async(max_attempts=3, retryable_exceptions=(TimeoutError,))
async def call_with_retry():
    async with breaker:
        return await api.call()
```

---

## Rate Limiting

Protect resources from overload.

### Token Bucket (Default)

Allows bursts while enforcing average rate.

```python
from obskit.resilience import RateLimiter

limiter = RateLimiter(
    name="api_calls",
    max_requests=100,     # Requests per window
    window_seconds=60,    # Window size
)

async def make_request():
    if not await limiter.acquire():
        raise RateLimitExceededError("Rate limit exceeded")
    
    return await api.call()
```

### Sliding Window

More accurate rate enforcement.

```python
from obskit.resilience import SlidingWindowRateLimiter

limiter = SlidingWindowRateLimiter(
    name="api_calls",
    max_requests=100,
    window_seconds=60,
)

async def make_request():
    if not await limiter.acquire():
        raise RateLimitExceededError("Rate limit exceeded")
    
    return await api.call()
```

### Token Bucket Rate Limiter

Classic token bucket algorithm.

```python
from obskit.resilience import TokenBucketRateLimiter

limiter = TokenBucketRateLimiter(
    name="api_calls",
    rate=100,           # Tokens per second
    capacity=1000,      # Maximum burst
)

async def make_request():
    if not await limiter.acquire():
        raise RateLimitExceededError()
    return await api.call()
```

### Rate Limiting Comparison

| Algorithm | Burst Handling | Accuracy | Use Case |
|-----------|---------------|----------|----------|
| Token Bucket | High | Approximate | APIs with bursts |
| Sliding Window | Medium | High | Strict rate limits |

---

## Combining Patterns

### Circuit Breaker + Retry

```python
from obskit.resilience import CircuitBreaker, retry_async, CircuitOpenError

breaker = CircuitBreaker(name="api", failure_threshold=5)

@retry_async(
    max_attempts=3,
    retryable_exceptions=(TimeoutError, ConnectionError),
)
async def call_with_retry_and_breaker():
    try:
        async with breaker:
            return await api.call()
    except CircuitOpenError:
        # Don't retry if circuit is open
        raise
```

### Rate Limiting + Circuit Breaker

```python
limiter = RateLimiter(max_requests=100, window_seconds=60)
breaker = CircuitBreaker(name="api", failure_threshold=5)

async def protected_call():
    # Rate limit first
    if not await limiter.acquire():
        raise RateLimitExceededError()
    
    # Then circuit breaker
    async with breaker:
        return await api.call()
```

### Full Protection Stack

```python
from obskit.resilience import (
    CircuitBreaker,
    RateLimiter,
    retry_async,
    CircuitOpenError,
    RateLimitExceeded,
)

limiter = RateLimiter(max_requests=100, window_seconds=60)
breaker = CircuitBreaker(name="external_api", failure_threshold=5)

@retry_async(max_attempts=3, retryable_exceptions=(TimeoutError,))
async def fully_protected_call(data: dict):
    """
    Protected with:
    1. Rate limiting (prevent overload)
    2. Circuit breaker (fail fast)
    3. Retry (handle transient failures)
    """
    # Rate limit
    if not await limiter.acquire():
        raise RateLimitExceeded("Rate limit exceeded")
    
    # Circuit breaker
    try:
        async with breaker:
            return await api.call(data)
    except CircuitOpenError as e:
        # Don't retry if circuit is open
        raise ServiceUnavailableError(
            f"Service unavailable. Retry in {e.time_until_retry:.0f}s"
        )
```

---

## Best Practices

### 1. Circuit Breaker Thresholds

```python
# Low-volume service
CircuitBreaker(failure_threshold=3, recovery_timeout=60)

# High-volume service
CircuitBreaker(failure_threshold=10, recovery_timeout=30)

# Distributed (higher threshold)
DistributedCircuitBreaker(failure_threshold=20, recovery_timeout=60)
```

### 2. Retry Configuration

```python
# Fast API calls
@retry_async(max_attempts=3, base_delay=0.1, max_delay=1.0)

# Slow batch operations
@retry_async(max_attempts=5, base_delay=5.0, max_delay=60.0)

# Critical operations
@retry_async(max_attempts=10, base_delay=1.0, jitter=True)
```

### 3. Rate Limiting Strategy

```python
# Per-user rate limiting
user_limiters = {}

async def get_user_limiter(user_id: str) -> RateLimiter:
    if user_id not in user_limiters:
        user_limiters[user_id] = RateLimiter(
            name=f"user_{user_id}",
            max_requests=100,
            window_seconds=60,
        )
    return user_limiters[user_id]
```

### 4. Error Handling

```python
from obskit.resilience import (
    CircuitOpenError,
    CircuitBreakerError,
    RateLimitExceeded,
    RetryError,
)

async def handle_request():
    try:
        return await protected_call()
    except CircuitOpenError as e:
        # Service temporarily unavailable
        return {"error": "Service unavailable", "retry_after": e.time_until_retry}
    except RateLimitExceeded:
        # Too many requests
        return {"error": "Rate limit exceeded"}, 429
    except RetryError:
        # All retries failed
        return {"error": "Service error"}, 500
```

---

## Monitoring

### Prometheus Metrics

```promql
# Circuit breaker open rate
rate(circuit_breaker_state_changes_total{state="open"}[5m])

# Retry attempts
histogram_quantile(0.99, rate(retry_attempts_bucket[5m]))

# Rate limit rejections
rate(rate_limit_rejected_total[5m])
```

### Alerting Rules

```yaml
groups:
- name: resilience-alerts
  rules:
  - alert: CircuitBreakerOpen
    expr: circuit_breaker_state{state="open"} == 1
    for: 1m
    labels:
      severity: warning
      
  - alert: HighRetryRate
    expr: rate(retry_attempts_total[5m]) > 10
    for: 5m
    labels:
      severity: warning
      
  - alert: RateLimitingActive
    expr: rate(rate_limit_rejected_total[5m]) > 0
    for: 1m
    labels:
      severity: info
```
