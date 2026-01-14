# Resilience Patterns Guide

obskit provides resilience patterns to help your service handle failures gracefully:
circuit breakers, retries, and rate limiting.

## Why Resilience?

In distributed systems, failures are inevitable:

- Network timeouts
- Overloaded services
- Database unavailability
- Third-party API outages

Without resilience patterns, failures cascade:

```{mermaid}
flowchart LR
    A[Service A] --> B[Service B]
    B --> C[Service C]
    C --> D["Database (DOWN)"]
    
    D -.->|Timeout 30s| C
    C -.->|Timeout 30s| B
    B -.->|Timeout 30s| A
    A -.->|503 Error| User
```

With resilience patterns, failures are contained:

```{mermaid}
flowchart LR
    A[Service A] --> B[Service B]
    B --> CB{Circuit Breaker}
    CB -->|Open| Fallback
    CB -.->|Closed| C[Service C]
    
    Fallback --> A
    A -->|Cached Response| User
```

## Circuit Breaker

### How It Works

```{mermaid}
stateDiagram-v2
    [*] --> Closed
    
    Closed --> Open: Failures >= threshold
    Closed --> Closed: Success
    
    Open --> HalfOpen: After recovery timeout
    
    HalfOpen --> Closed: Test request succeeds
    HalfOpen --> Open: Test request fails
```

| State | Behavior |
|-------|----------|
| **Closed** | Requests pass through normally |
| **Open** | Requests fail immediately without calling downstream |
| **Half-Open** | One test request allowed to check if service recovered |

### Basic Usage

```python
from obskit import CircuitBreaker

# Create circuit breaker
breaker = CircuitBreaker(
    failure_threshold=5,    # Open after 5 failures
    recovery_timeout=30.0,  # Try again after 30 seconds
)

# Use as context manager
async def call_payment_api():
    async with breaker:
        return await payment_service.charge(amount)
```

### With Fallback

```python
from obskit.resilience import CircuitBreakerOpen

async def get_user_preferences(user_id: str) -> dict:
    try:
        async with breaker:
            return await preferences_service.get(user_id)
    except CircuitBreakerOpen:
        # Return cached/default preferences when circuit is open
        return get_cached_preferences(user_id)
```

### Decorator Usage

```python
from obskit import circuit_breaker

@circuit_breaker(failure_threshold=5, recovery_timeout=30.0)
async def call_external_api():
    return await httpx.get("https://api.example.com/data")
```

### Monitoring Circuit State

```python
breaker = CircuitBreaker(failure_threshold=5)

# Check current state
if breaker.is_open:
    logger.warning("Circuit is open, using fallback")

# Get statistics
print(f"Failure count: {breaker.failure_count}")
print(f"Success count: {breaker.success_count}")
```

## Distributed Circuit Breaker

For multi-instance deployments, share circuit state via Redis:

```python
from obskit import DistributedCircuitBreaker

breaker = DistributedCircuitBreaker(
    name="payment-api",
    redis_url="redis://localhost:6379",
    failure_threshold=10,  # Total failures across all instances
    recovery_timeout=60.0,
)

async with breaker:
    return await payment_service.charge(amount)
```

### Why Distributed?

With per-instance circuit breakers:
- Instance A opens circuit after 5 failures
- Instance B hasn't seen failures yet, keeps trying
- Instance C also keeps trying
- Slow failure detection across the cluster

With distributed circuit breakers:
- All instances share state
- Circuit opens after 10 total failures
- All instances immediately fail fast

## Retry

### Basic Usage

```python
from obskit import retry_async

@retry_async(
    max_attempts=3,
    base_delay=1.0,
    max_delay=30.0,
    exponential_base=2,
)
async def call_flaky_api():
    return await httpx.get("https://flaky-api.example.com")
```

### Retry Timing

With `base_delay=1.0` and `exponential_base=2`:

| Attempt | Delay | Total Wait |
|---------|-------|------------|
| 1 | 0s | 0s |
| 2 | 1s | 1s |
| 3 | 2s | 3s |
| 4 | 4s | 7s |
| 5 | 8s | 15s |

### Selective Retries

Only retry specific exceptions:

```python
@retry_async(
    max_attempts=3,
    retry_on=(ConnectionError, TimeoutError),
    exclude=(ValidationError, AuthenticationError),
)
async def call_api():
    return await make_request()
```

### Sync Retry

```python
from obskit import retry

@retry(max_attempts=3, base_delay=0.5)
def call_database():
    return db.execute(query)
```

### Custom Retry Logic

```python
from obskit.resilience import RetryStrategy

def should_retry(exception: Exception, attempt: int) -> bool:
    """Custom retry decision logic."""
    if isinstance(exception, RateLimitError):
        return True
    if isinstance(exception, ServerError) and attempt < 5:
        return True
    return False

@retry_async(max_attempts=5, retry_predicate=should_retry)
async def call_api():
    return await make_request()
```

## Rate Limiting

### Token Bucket

Smooth rate limiting that allows bursts:

```python
from obskit.resilience import RateLimiter

limiter = RateLimiter(
    rate=100,      # 100 requests per second sustained
    burst=20,      # Allow burst of 20 extra
)

async def handle_request():
    if not await limiter.acquire():
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    return process_request()
```

### Sliding Window

Strict limit over a time window:

```python
from obskit.resilience import SlidingWindowRateLimiter

limiter = SlidingWindowRateLimiter(
    limit=1000,       # 1000 requests
    window_seconds=60,  # per minute
)

async def handle_request():
    if not await limiter.acquire():
        return Response(status_code=429)
    
    return process_request()
```

### Per-Client Rate Limiting

```python
from obskit.resilience import RateLimiter

# Create limiter per client
client_limiters: dict[str, RateLimiter] = {}

def get_limiter(client_id: str) -> RateLimiter:
    if client_id not in client_limiters:
        client_limiters[client_id] = RateLimiter(rate=10, burst=5)
    return client_limiters[client_id]

async def handle_request(client_id: str):
    limiter = get_limiter(client_id)
    if not await limiter.acquire():
        raise HTTPException(status_code=429)
    
    return process_request()
```

## Combining Patterns

### Circuit Breaker + Retry

```python
from obskit import CircuitBreaker, retry_async
from obskit.resilience import CircuitBreakerOpen

breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=30)

@retry_async(
    max_attempts=3,
    exclude=(CircuitBreakerOpen,),  # Don't retry when circuit is open
)
async def call_api():
    async with breaker:
        return await httpx.get("https://api.example.com")
```

### Full Resilience Stack

```python
from obskit import CircuitBreaker, retry_async
from obskit.resilience import RateLimiter, CircuitBreakerOpen

# Rate limit outgoing calls
rate_limiter = RateLimiter(rate=100, burst=10)

# Circuit breaker for the API
breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=30)

@retry_async(max_attempts=3, exclude=(CircuitBreakerOpen, RateLimitError))
async def call_external_api():
    # Check rate limit first
    if not await rate_limiter.acquire():
        raise RateLimitError("Self-imposed rate limit")
    
    # Then check circuit breaker
    async with breaker:
        return await httpx.get("https://api.example.com")
```

## Best Practices

### 1. Choose Appropriate Thresholds

```python
# For critical services: be conservative
critical_breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=60)

# For non-critical: be more lenient
optional_breaker = CircuitBreaker(failure_threshold=10, recovery_timeout=30)
```

### 2. Always Have Fallbacks

```python
async def get_recommendations(user_id: str) -> list:
    try:
        async with ml_service_breaker:
            return await ml_service.recommend(user_id)
    except CircuitBreakerOpen:
        # Fallback to popular items
        return get_popular_items()
```

### 3. Monitor Circuit States

```python
# Expose metrics
from prometheus_client import Gauge

circuit_state = Gauge(
    "circuit_breaker_state",
    "Circuit breaker state (0=closed, 1=open, 2=half-open)",
    ["service"],
)

# Update on state change
circuit_state.labels(service="payment").set(1 if breaker.is_open else 0)
```

### 4. Log State Transitions

```python
breaker = CircuitBreaker(
    failure_threshold=5,
    on_open=lambda: logger.warning("Circuit opened"),
    on_close=lambda: logger.info("Circuit closed"),
)
```

## Next Steps

- **[Health Checks](health-checks.md)** - Expose application health
- **[SLO Tracking](slo.md)** - Define reliability targets
- **[Examples](../examples/fastapi.md)** - Full working examples

