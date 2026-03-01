# Resilience

Production-grade resilience primitives: circuit breakers, retries with exponential backoff, rate limiters, Redis-backed distributed circuit breakers, and adaptive retry with backpressure.

## Installation

```bash
pip install obskit
```

---

## CircuitBreaker

Implements the circuit-breaker pattern to prevent cascading failures across service dependencies. The breaker cycles through three states:

```
CLOSED ──[failure_threshold exceeded]──► OPEN
  ▲                                         │
  │                                [recovery_timeout elapsed]
  │                                         ▼
  └────[all half-open tests pass]────► HALF_OPEN
```

| State | Behaviour |
|---|---|
| `CLOSED` | All requests pass through; failures are counted |
| `OPEN` | All requests fail immediately (`CircuitOpenError`); protects the downstream |
| `HALF_OPEN` | A limited number of test requests are allowed; success closes the circuit |

### Basic usage

```python
from obskit.resilience import CircuitBreaker
from obskit.core.errors import CircuitOpenError

breaker = CircuitBreaker(
    name="payment_api",
    failure_threshold=5,        # open after 5 consecutive failures
    recovery_timeout=30.0,      # wait 30 s before half-open
    half_open_requests=3,       # allow 3 test requests in half-open
)

# Async context manager
async def process_payment(amount: float):
    async with breaker:
        return await payment_api.charge(amount)

# Async decorator
@breaker
async def process_payment(amount: float):
    return await payment_api.charge(amount)
```

### Handling CircuitOpenError

```python
from obskit.core.errors import CircuitOpenError

async def process_payment(amount: float):
    try:
        async with breaker:
            return await payment_api.charge(amount)
    except CircuitOpenError as e:
        print(f"Circuit open — retry in {e.time_until_retry:.1f}s")
        return await fallback_processor.charge(amount)
```

### Excluded exceptions

Business-logic exceptions should not count as circuit failures:

```python
breaker = CircuitBreaker(
    name="user_api",
    failure_threshold=5,
    excluded_exceptions=[ValueError, KeyError],
)

@breaker
async def get_user(user_id: str):
    user = await user_api.get(user_id)
    if not user:
        raise KeyError(f"User {user_id} not found")  # does NOT trip the circuit
    return user
```

### Monitoring circuit state

```python
# State inspection
print(breaker.state)           # CircuitState.CLOSED / .OPEN / .HALF_OPEN
print(breaker.failure_count)   # int
print(breaker.is_closed)       # bool
print(breaker.is_open)         # bool
print(breaker.is_half_open)    # bool

# Manual reset (useful in admin/test contexts)
breaker.reset()                # force close the circuit
```

### CircuitState enum

```python
from obskit.resilience.circuit_breaker import CircuitState

CircuitState.CLOSED     # normal operation
CircuitState.OPEN       # failing fast
CircuitState.HALF_OPEN  # testing recovery
```

### Configuration from ObskitSettings

```python
# All CircuitBreaker instances can inherit defaults from settings
from obskit.config import configure

configure(
    circuit_breaker_failure_threshold=10,
    circuit_breaker_recovery_timeout=60.0,
    circuit_breaker_half_open_requests=5,
)
```

---

## @retry decorator

Retries sync and async functions with exponential backoff and optional jitter. Never retries if the attempt count is exhausted — raises `RetryError` instead.

```python
from obskit.resilience import retry

@retry(max_attempts=3)
async def fetch_data():
    return await api.get("/data")
```

### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `max_attempts` | `int` | `3` | Total attempts (first try + retries) |
| `base_delay` | `float` | `1.0` | Base backoff delay in seconds |
| `max_delay` | `float` | `60.0` | Maximum delay cap in seconds |
| `exponential_base` | `float` | `2.0` | Exponent base for backoff |
| `jitter` | `bool` | `True` | Add random jitter to prevent thundering herd |
| `retry_on` | `tuple[type, ...]` | `(Exception,)` | Exception types that trigger a retry |
| `no_retry_on` | `tuple[type, ...]` | `()` | Exception types that are never retried |

### Backoff schedule (base_delay=1.0, exponential_base=2.0)

| Attempt | Delay before retry (without jitter) |
|---|---|
| 1 → 2 | 1 s |
| 2 → 3 | 2 s |
| 3 → 4 | 4 s |
| 4 → 5 | 8 s |

### Examples

```python
import httpx
from obskit.resilience import retry
from obskit.core.errors import RetryError

# Custom configuration
@retry(
    max_attempts=5,
    base_delay=0.5,
    max_delay=30.0,
    exponential_base=2.0,
    jitter=True,
)
async def fetch_data():
    return await api.get("/data")

# Retry only on network errors (not business logic errors)
@retry(
    max_attempts=3,
    retry_on=(httpx.TimeoutException, httpx.NetworkError),
    no_retry_on=(ValueError, KeyError),
)
async def process_data(data: dict):
    if "id" not in data:
        raise KeyError("id required")   # NOT retried
    return await api.process(data)

# Handle exhausted retries
try:
    result = await fetch_data()
except RetryError as e:
    print(f"Failed after {e.attempts} attempts")
    print(f"Last error: {e.last_exception}")

# Sync functions work too
@retry(max_attempts=3)
def sync_operation():
    return requests.get("https://api.example.com")
```

---

## RateLimiter — sliding window

Limits requests to `N` per time window. Blocks (async-safe) when the limit is exceeded.

```python
from obskit.resilience import RateLimiter
from obskit.core.errors import RateLimitExceeded

limiter = RateLimiter(requests=100, window_seconds=60.0)

async def handle_request():
    async with limiter:
        return await process_request()

# Or check without blocking
if await limiter.is_allowed():
    result = await process_request()
else:
    raise RateLimitExceeded("Rate limit exceeded", retry_after=limiter.retry_after)
```

### TokenBucketRateLimiter

Allows bursts up to `bucket_size` tokens, then refills at `refill_rate` tokens per second.

```python
from obskit.resilience.rate_limiter import TokenBucketRateLimiter

limiter = TokenBucketRateLimiter(
    bucket_size=10,      # maximum burst
    refill_rate=1.0,     # tokens per second
)

async def handle_request():
    async with limiter:
        return await process_request()
```

---

## DistributedCircuitBreaker

Redis-backed circuit breaker that shares state across multiple service instances. Provides faster, coordinated failure detection in horizontally scaled deployments.

```python
from obskit.resilience.distributed import DistributedCircuitBreaker

# Async Redis client
import redis.asyncio as aioredis

redis_client = aioredis.Redis(host="redis", port=6379)

breaker = DistributedCircuitBreaker(
    name="payment_api",
    redis_client=redis_client,
    failure_threshold=10,       # shared across all instances
    recovery_timeout=60.0,
)

async def process_payment(amount: float):
    async with breaker:
        return await payment_api.charge(amount)
```

```python
# Sync Redis client also supported
import redis

sync_redis = redis.Redis(host="redis", port=6379)

breaker = DistributedCircuitBreaker(
    name="payment_api",
    redis_client=sync_redis,
    failure_threshold=10,
)
```

**Key difference from `CircuitBreaker`:**

- State (failure count, open timestamp) is stored in Redis
- All instances of your service share the same circuit state
- If instance A records 5 failures, instance B will count them too
- Useful for services with `replica_count > 1`

---

## AdaptiveCircuitBreaker

Automatically adjusts failure thresholds and recovery timeouts based on observed error rates and system load.

```python
from obskit.resilience.adaptive import AdaptiveCircuitBreaker, RetryConfig

breaker = AdaptiveCircuitBreaker(
    name="external_api",
    config=RetryConfig(
        max_attempts=5,
        base_delay=1.0,
        max_delay=60.0,
    ),
)

async def call_external():
    async with breaker:
        return await external_api.call()
```

Prometheus metrics emitted by `AdaptiveCircuitBreaker`:

| Metric | Type | Labels | Description |
|---|---|---|---|
| `adaptive_retry_attempts_total` | Counter | `name`, `status` | Retry attempt count |
| `adaptive_retry_delay_seconds` | Histogram | `name` | Delay distribution |
| `adaptive_retry_error_rate` | Gauge | `name` | Current observed error rate |
| `adaptive_retry_backpressure_multiplier` | Gauge | `name` | Backpressure multiplier |
| `adaptive_retry_concurrent_requests` | Gauge | `name` | Concurrent in-flight requests |

---

## Factory function

```python
from obskit.resilience.factory import create_circuit_breaker

# Creates a CircuitBreaker with defaults from ObskitSettings
breaker = create_circuit_breaker(
    name="payment_api",
    # override specific settings:
    failure_threshold=10,
    recovery_timeout=60.0,
)
```

---

## Monitoring integration

Circuit state changes emit Prometheus metrics automatically:

| Metric | Type | Labels | Description |
|---|---|---|---|
| `circuit_breaker_state` | Gauge | `name` | 0=CLOSED, 1=OPEN, 2=HALF_OPEN |
| `circuit_breaker_failures_total` | Counter | `name` | Cumulative failure count |
| `circuit_breaker_state_changes_total` | Counter | `name`, `from_state`, `to_state` | State transition count |

```python
# Alert on open circuit breaker (Prometheus alerting rule)
# - alert: CircuitBreakerOpen
#   expr: circuit_breaker_state{name="payment_api"} == 1
#   for: 30s
#   labels:
#     severity: warning
```

---

## Combined usage

```python
from obskit.resilience import CircuitBreaker, retry, RateLimiter
from obskit.core.errors import CircuitOpenError, RetryError

# Stack circuit breaker + retry + rate limiter
breaker = CircuitBreaker("payment_api", failure_threshold=5)
limiter = RateLimiter(requests=50, window_seconds=1.0)

@retry(max_attempts=3, no_retry_on=(CircuitOpenError,))
async def charge_card(amount: float):
    async with limiter:
        async with breaker:
            return await payment_api.charge(amount)
```
