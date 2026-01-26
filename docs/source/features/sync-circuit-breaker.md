# Sync Circuit Breaker

The Circuit Breaker pattern prevents cascading failures by "breaking" the circuit when a service is failing. obskit now supports **both async and sync** circuit breakers.

## When to Use Sync vs Async

| Use Case | Decorator |
|----------|-----------|
| `async def` functions | `@breaker` (async context manager) |
| Regular `def` functions | `@with_circuit_breaker_sync()` |
| Sync HTTP calls (requests) | `@with_circuit_breaker_sync()` |
| Async HTTP calls (httpx) | `@breaker` (async context manager) |

## Quick Start

### Sync Functions

```python
from obskit import with_circuit_breaker_sync
import requests

@with_circuit_breaker_sync("external_api", failure_threshold=5)
def call_external_api(endpoint: str) -> dict:
    response = requests.get(f"https://api.example.com/{endpoint}")
    response.raise_for_status()
    return response.json()

# Usage
try:
    data = call_external_api("users")
except CircuitOpenError as e:
    # Circuit is open, fail fast
    logger.warning(f"Circuit open: {e.breaker_name}")
```

### Async Functions

```python
from obskit import CircuitBreaker
import httpx

breaker = CircuitBreaker("external_api", failure_threshold=5)

@breaker
async def call_external_api(endpoint: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(f"https://api.example.com/{endpoint}")
        response.raise_for_status()
        return response.json()
```

## Using Context Managers

### Sync Context Manager

```python
from obskit import CircuitBreaker

breaker = CircuitBreaker("payment_api", failure_threshold=3)

def process_payment(amount: float) -> dict:
    with breaker:
        return payment_api.charge(amount)
```

### Async Context Manager

```python
async def process_payment(amount: float) -> dict:
    async with breaker:
        return await payment_api.charge(amount)
```

## Using call_sync()

For one-off calls without decorators:

```python
breaker = CircuitBreaker("api", failure_threshold=5)

# Call any sync function with circuit breaker protection
result = breaker.call_sync(requests.get, "https://api.example.com")
result = breaker.call_sync(my_function, arg1, arg2, kwarg1="value")
```

## Configuration

### Decorator Parameters

```python
@with_circuit_breaker_sync(
    name="my_api",              # Unique name for the circuit
    failure_threshold=5,        # Failures before opening (default: 5)
    recovery_timeout=30.0,      # Seconds before testing recovery (default: 30)
    half_open_requests=3,       # Test requests in half-open state (default: 3)
)
def my_function():
    ...
```

### CircuitBreaker Class Parameters

```python
breaker = CircuitBreaker(
    name="my_api",
    failure_threshold=5,
    recovery_timeout=30.0,
    half_open_requests=3,
    excluded_exceptions=(ValidationError,),  # Don't count these as failures
)
```

## Circuit States

```
┌─────────┐     Failures >= threshold     ┌────────┐
│ CLOSED  │ ───────────────────────────►  │  OPEN  │
│ (normal)│                               │ (fail) │
└─────────┘                               └────────┘
     ▲                                         │
     │                                         │
     │        After recovery_timeout           │
     │                                         ▼
     │       ┌───────────┐                     │
     └────── │ HALF_OPEN │ ◄───────────────────┘
  Success    │  (test)   │
             └───────────┘
                  │
                  │ Failure
                  ▼
             Back to OPEN
```

## Excluded Exceptions

Don't count certain exceptions as failures:

```python
class ValidationError(Exception):
    pass

@with_circuit_breaker_sync(
    "api",
    excluded_exceptions=(ValidationError, ValueError),
)
def my_function():
    # ValidationError won't trip the circuit
    raise ValidationError("Invalid input")
```

## Monitoring

### Check Circuit State

```python
breaker = CircuitBreaker("api")

print(f"Is closed: {breaker.is_closed}")
print(f"Is half-open: {breaker.is_half_open}")
print(f"Failure count: {breaker.failure_count}")
```

### Prometheus Metrics

obskit exports circuit breaker metrics automatically:

```promql
# Circuit breaker state changes
obskit_circuit_breaker_state{name="api"}

# Failure counts
obskit_circuit_breaker_failures_total{name="api"}

# Time spent in open state
obskit_circuit_breaker_open_seconds{name="api"}
```

## Best Practices

### 1. Use Unique Names

```python
# Good: Descriptive, unique names
@with_circuit_breaker_sync("nylas_api")
@with_circuit_breaker_sync("lumedia_api")
@with_circuit_breaker_sync("redis_cache")

# Bad: Generic names
@with_circuit_breaker_sync("api")
@with_circuit_breaker_sync("external")
```

### 2. Set Appropriate Thresholds

```python
# Critical path: Lower threshold, longer recovery
@with_circuit_breaker_sync(
    "payment_api",
    failure_threshold=3,
    recovery_timeout=60.0,
)

# Non-critical: Higher threshold, faster recovery
@with_circuit_breaker_sync(
    "analytics_api",
    failure_threshold=10,
    recovery_timeout=15.0,
)
```

### 3. Handle CircuitOpenError

```python
from obskit import CircuitOpenError

try:
    result = call_api()
except CircuitOpenError as e:
    logger.warning(
        "circuit_open",
        breaker=e.breaker_name,
        retry_after=e.time_until_retry,
    )
    # Return cached/default value
    return get_cached_value()
```

### 4. Combine with Retry

```python
from obskit import with_circuit_breaker_sync, retry

# Retry first, then circuit breaker
@with_circuit_breaker_sync("api", failure_threshold=5)
@retry(max_attempts=3, base_delay=1.0)
def call_api():
    return requests.get("https://api.example.com").json()
```

## Example: Real-World Usage

```python
from obskit import with_circuit_breaker_sync, CircuitOpenError
from obskit.logging import get_logger
import requests

logger = get_logger(__name__)

@with_circuit_breaker_sync(
    "nylas_api",
    failure_threshold=5,
    recovery_timeout=30.0,
)
def download_attachment(grant_id: str, attachment_id: str) -> bytes:
    """Download attachment from Nylas API."""
    response = requests.get(
        f"https://api.nylas.com/v3/grants/{grant_id}/attachments/{attachment_id}",
        headers={"Authorization": f"Bearer {API_KEY}"},
    )
    response.raise_for_status()
    return response.content

# Usage with fallback
def get_attachment(grant_id: str, attachment_id: str) -> bytes | None:
    try:
        return download_attachment(grant_id, attachment_id)
    except CircuitOpenError:
        logger.warning("nylas_circuit_open", grant_id=grant_id)
        return None
    except requests.RequestException as e:
        logger.error("attachment_download_failed", error=str(e))
        raise
```

## API Reference

```python
# Decorator for sync functions
from obskit import with_circuit_breaker_sync

# Main class (supports both sync and async)
from obskit import CircuitBreaker

# Errors
from obskit import CircuitOpenError, CircuitBreakerError
```
