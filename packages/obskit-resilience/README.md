# obskit-resilience

Circuit breakers, retry policies, rate limiting, load shedding, and graceful degradation for Python services.

## Install

```bash
pip install obskit-resilience
```

## Circuit breaker

```python
from obskit.resilience import CircuitBreaker, CircuitOpenError

cb = CircuitBreaker(
    name="payment-gateway",
    failure_threshold=5,
    recovery_timeout=30.0,
    expected_exceptions=(TimeoutError, ConnectionError),
)

try:
    result = await cb.call(gateway.charge, amount)
except CircuitOpenError:
    result = use_fallback()
```

## Retry with exponential backoff

```python
from obskit.resilience import retry

@retry(max_attempts=3, backoff_factor=2.0, exceptions=(TimeoutError,))
async def fetch_data():
    return await api.get("/data")
```

## Rate limiting

```python
from obskit.resilience import RateLimiter

limiter = RateLimiter(max_calls=100, period=1.0)   # 100 req/s

async def handle_request():
    async with limiter:
        return await process()
```

## Load shedding

```python
from obskit.resilience import LoadShedder

shedder = LoadShedder(max_concurrent=50)

async def endpoint():
    async with shedder:
        return await heavy_operation()
```
