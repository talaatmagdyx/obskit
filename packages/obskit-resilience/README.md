<div align="center">

# 🛡️ obskit-resilience

**Circuit breakers, retry policies, rate limiting, load shedding, and graceful degradation for Python services**

---

[![PyPI](https://img.shields.io/pypi/v/obskit-resilience.svg?color=blue)](https://pypi.org/project/obskit-resilience/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![obskit](https://img.shields.io/badge/part%20of-obskit-blueviolet.svg)](https://github.com/talaatmagdyx/obskit)

</div>

## What it does

- **Prevents cascading failures** with a thread-safe `CircuitBreaker` that moves through CLOSED → OPEN → HALF-OPEN states automatically, stopping calls to a failing dependency and giving it time to recover.
- **Handles transient errors gracefully** with a `@retry` decorator that uses exponential backoff and full jitter, so retry storms never overwhelm a struggling service.
- **Protects throughput** with a sliding-window `RateLimiter` and a burst-friendly `TokenBucketRateLimiter`, plus a priority-aware `LoadShedder` that sheds low-priority traffic before your service falls over.

---

## Installation

```bash
pip install obskit-resilience
```

Redis-backed distributed locking is an optional runtime dependency:

```bash
pip install "obskit-resilience[dev]"   # includes redis[hiredis] for locking
```

---

## Quick Start

```python
import asyncio
from obskit.resilience import CircuitBreaker, CircuitOpenError, retry, RateLimiter

# One circuit breaker per downstream service
payment_cb = CircuitBreaker(
    name="payment-gateway",
    failure_threshold=5,      # open after 5 consecutive failures
    recovery_timeout=30.0,    # wait 30 s then probe with HALF-OPEN
    excluded_exceptions=(ValueError,),  # validation errors don't trip the breaker
)

# 200 req/s rate limit on this endpoint
limiter = RateLimiter(requests=200, window_seconds=1.0)


@retry(max_attempts=3, base_delay=0.5, jitter=True, retry_on=(TimeoutError, ConnectionError))
async def charge_order(order_id: str, amount: float) -> dict:
    async with limiter:
        try:
            async with payment_cb:
                return await payment_gateway.charge(order_id, amount)
        except CircuitOpenError as e:
            # Circuit is open — route to the backup processor
            return await backup_processor.charge(order_id, amount)


asyncio.run(charge_order("ord-123", 49.99))
```

---

## Circuit Breaker

The circuit breaker prevents cascading failures. When a downstream service starts failing, the breaker opens and calls fail immediately — giving the service time to recover without exhausting your thread pool or connection pool.

### State machine

```
  ┌──────────────────────────────────────────────────────────┐
  │  CLOSED  — normal operation, failures counted            │
  └────────────────────────┬─────────────────────────────────┘
                           │  failures >= failure_threshold
                           ▼
  ┌──────────────────────────────────────────────────────────┐
  │  OPEN  — all calls fail fast (CircuitOpenError)          │
  └────────────────────────┬─────────────────────────────────┘
                           │  recovery_timeout elapsed
                           ▼
  ┌──────────────────────────────────────────────────────────┐
  │  HALF-OPEN  — limited test calls allowed                 │
  │    success → CLOSED      failure → OPEN                  │
  └──────────────────────────────────────────────────────────┘
```

### As a context manager

```python
from obskit.resilience import CircuitBreaker, CircuitOpenError

inventory_cb = CircuitBreaker(
    name="inventory-service",
    failure_threshold=3,
    recovery_timeout=20.0,
    half_open_requests=2,   # how many test probes in HALF-OPEN
)

async def reserve_stock(product_id: str, qty: int) -> bool:
    try:
        async with inventory_cb:
            return await inventory_api.reserve(product_id, qty)
    except CircuitOpenError as e:
        # Graceful fallback: optimistically allow the order
        logger.warning("inventory_circuit_open", retry_in=e.time_until_retry)
        return True   # or serve from local cache
```

### As a decorator

```python
breaker = CircuitBreaker("shipping-service", failure_threshold=5)

@breaker
async def get_shipping_rates(postcode: str) -> list[dict]:
    return await shipping_api.rates(postcode)

# Multiple functions can share the same breaker — one trip affects all
@breaker
async def book_shipment(order_id: str, address: dict) -> str:
    return await shipping_api.book(order_id, address)
```

### Synchronous code

```python
from obskit.resilience import with_circuit_breaker_sync

@with_circuit_breaker_sync("legacy-erp", failure_threshold=5, recovery_timeout=60.0)
def sync_push_to_erp(order_data: dict) -> bool:
    return erp_client.push(order_data)
```

### Introspecting state

```python
breaker = CircuitBreaker("payment-gateway")

print(breaker.state)          # CircuitState.CLOSED / OPEN / HALF_OPEN
print(breaker.failure_count)  # consecutive failures
print(breaker.is_open)        # True when failing fast
print(breaker.is_half_open)   # True during probe phase

# Manual override — use after a confirmed service restart
breaker.reset()
```

---

## Retry with Exponential Backoff

The `@retry` decorator automatically retries async functions on transient failures. Full jitter spreads retries across clients to avoid the thundering herd problem.

```
Attempt 1: Immediate
Attempt 2: Wait ~0.5 s  (base_delay * 2^0 * jitter)
Attempt 3: Wait ~1.0 s  (base_delay * 2^1 * jitter)
Attempt 4: Wait ~2.0 s  (base_delay * 2^2 * jitter)
                              → RetryError raised
```

```python
from obskit.resilience import retry, RetryError
import httpx

@retry(
    max_attempts=4,
    base_delay=0.5,
    max_delay=30.0,
    exponential_base=2.0,
    jitter=True,
    retry_on=(httpx.TimeoutException, httpx.NetworkError),
    no_retry_on=(ValueError, KeyError),  # business-logic errors — never retry
)
async def fetch_product_catalog(category: str) -> list[dict]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"https://catalog.internal/v1/{category}")
        resp.raise_for_status()
        return resp.json()


try:
    catalog = await fetch_product_catalog("electronics")
except RetryError as e:
    print(f"Gave up after {e.attempts} attempts ({e.total_delay:.1f}s of delays)")
    print(f"Last error: {e.last_exception}")
```

### Synchronous functions

```python
from obskit.resilience.retry import retry_sync

@retry_sync(max_attempts=3, base_delay=1.0)
def push_to_warehouse(order: dict) -> bool:
    return warehouse_api.push(order)
```

---

## Rate Limiting

### Sliding window (default)

Counts requests in a rolling time window — the most accurate algorithm.

```python
from obskit.resilience import RateLimiter, RateLimitExceeded

# 100 requests per second per endpoint
limiter = RateLimiter(requests=100, window_seconds=1.0)

async def handle_search(query: str) -> dict:
    try:
        async with limiter:
            return await search_engine.query(query)
    except RateLimitExceeded as e:
        return {
            "error": "Too many requests",
            "retry_after": e.retry_after,
        }

# Check without consuming a slot
if not limiter.would_exceed():
    async with limiter:
        ...

# Inspect current state
print(f"Used: {limiter.current_count} / {limiter.requests}")
print(f"Remaining: {limiter.remaining}")
```

### Token bucket (burst-friendly)

Tokens refill at a fixed rate, allowing controlled bursts. Ideal when traffic is naturally spiky.

```python
from obskit.resilience import TokenBucketRateLimiter

# Allow bursts of 50, sustain at 20 req/s
checkout_limiter = TokenBucketRateLimiter(
    bucket_size=50,
    refill_rate=20.0,   # tokens per second
)

async def checkout(cart_id: str):
    async with checkout_limiter:
        return await payment_service.process(cart_id)
```

---

## Load Shedding

When your service is overwhelmed, shed low-priority traffic first — keeping critical paths (payments, order confirmations) alive.

```python
from obskit.shedding import LoadShedder, Priority

shedder = LoadShedder(
    name="order-api",
    max_queue_size=1000,
    max_latency_ms=500,
    shed_percentage=0.1,   # start shedding at 10% under load
    adaptive=True,         # auto-adjust shed rate based on queue + latency
)

async def handle_request(request_type: str) -> dict:
    priority = {
        "checkout":       Priority.CRITICAL,
        "order_status":   Priority.HIGH,
        "product_search": Priority.NORMAL,
        "recommendations":Priority.LOW,
        "analytics_ping": Priority.BACKGROUND,
    }.get(request_type, Priority.NORMAL)

    if not shedder.should_process(priority=priority):
        return {"error": "Service overloaded, please retry"}

    return await process_request(request_type)


# Monitor shedding
stats = shedder.get_stats()
print(f"Shed rate: {stats.current_shed_rate:.1%}")
print(f"Requests shed: {stats.requests_shed}")
```

---

## Graceful Degradation

Register optional features and degrade them automatically when error rates or latency spike — keeping the core shopping experience intact.

```python
from obskit.degradation import DegradationManager, DegradationLevel

degradation = DegradationManager(service_name="storefront")

# Register features in priority order (lower priority = degrade first)
degradation.register_feature(
    "product_recommendations",
    priority=10,
    fallback=lambda: [],   # return empty list when degraded
    degradation_threshold=50,
)
degradation.register_feature(
    "live_inventory_count",
    priority=20,
    fallback=lambda: "In stock",
    degradation_threshold=25,
)
degradation.register_feature(
    "checkout",
    priority=100,   # last to be degraded
    degradation_threshold=95,
)


async def render_product_page(product_id: str) -> dict:
    page = await fetch_product(product_id)

    # Adjust degradation level based on current metrics
    degradation.evaluate_metrics(
        error_rate=await get_error_rate(),
        latency_ms=await get_p95_latency_ms(),
    )

    # Use primary or fallback transparently
    page["recommendations"] = degradation.execute_with_fallback(
        "product_recommendations",
        primary=lambda: get_recommendations(product_id),
    )
    page["stock_label"] = degradation.execute_with_fallback(
        "live_inventory_count",
        primary=lambda: fetch_live_inventory(product_id),
    )

    return page


# Force degradation during a known incident
degradation.set_level(DegradationLevel.HIGH, reason="upstream-db-latency")
degradation.degrade_feature("live_inventory_count")
degradation.restore_feature("live_inventory_count")   # once resolved
```

---

## Distributed Locking

Prevent thundering herd problems — for example, when cache expires and many processes race to rebuild it — using Redis-backed distributed locks.

```python
import redis
from obskit.locking import DistributedLock, LeaderElection

redis_client = redis.Redis(host="redis.internal", port=6379)

# Distributed lock: only one instance rebuilds the cache at a time
async def get_product_catalog() -> list[dict]:
    cache_key = "catalog:all"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    async with DistributedLock("catalog-rebuild-lock", redis_client, ttl_seconds=30.0):
        # Double-check: another instance may have populated it while we waited
        cached = await cache.get(cache_key)
        if cached:
            return cached

        catalog = await db.fetch_all_products()
        await cache.set(cache_key, catalog, ttl=300)
        return catalog


# Leader election: only the leader runs the scheduled price sync job
election = LeaderElection("price-sync-scheduler", redis_client, ttl_seconds=30.0)
election.start_campaign()   # background renewal loop

if election.am_i_leader():
    await sync_prices_from_erp()
```

### Lock introspection

```python
lock = DistributedLock("inventory-lock", redis_client)
print(lock.is_held())       # True / False
print(lock.get_holder())    # holder_id string or None
lock.extend(additional_seconds=30.0)   # extend TTL before expiry
```

---

## Combining Patterns

For maximum resilience, stack the patterns. The `ResilientExecutor` convenience class chains them for you:

```python
from obskit.resilience import ResilientExecutor, BackoffStrategy

executor = ResilientExecutor(
    name="payment-gateway",
    failure_threshold=5,
    recovery_timeout=30.0,
    max_attempts=3,
    base_delay=0.5,
    strategy=BackoffStrategy.EXPONENTIAL_JITTER,
)

result = await executor.execute(payment_gateway.charge, order_id, amount)
```

Or compose manually:

```python
from obskit.resilience import CircuitBreaker, retry, RateLimiter

cb = CircuitBreaker("payment-gateway", failure_threshold=5)
limiter = RateLimiter(requests=100, window_seconds=1.0)

@retry(max_attempts=3, base_delay=0.5, retry_on=(TimeoutError,))
async def process_payment(order_id: str, amount: float) -> dict:
    async with limiter:          # 1. rate limit
        async with cb:           # 2. circuit breaker
            return await gateway.charge(order_id, amount)  # 3. actual call
```

---

## Environment Variables / Configuration

All settings fall back to environment variables when not provided directly to the constructor.

| Variable | Default | Description |
|---|---|---|
| `OBSKIT_CIRCUIT_BREAKER_FAILURE_THRESHOLD` | `5` | Failures before opening the circuit |
| `OBSKIT_CIRCUIT_BREAKER_RECOVERY_TIMEOUT` | `30.0` | Seconds before testing recovery |
| `OBSKIT_CIRCUIT_BREAKER_HALF_OPEN_REQUESTS` | `3` | Test probes in HALF-OPEN state |
| `OBSKIT_RETRY_MAX_ATTEMPTS` | `3` | Maximum retry attempts |
| `OBSKIT_RETRY_BASE_DELAY` | `1.0` | Initial retry delay in seconds |
| `OBSKIT_RETRY_MAX_DELAY` | `60.0` | Maximum retry delay cap in seconds |
| `OBSKIT_RETRY_EXPONENTIAL_BASE` | `2.0` | Exponential backoff base |
| `OBSKIT_RATE_LIMIT_REQUESTS` | `100` | Maximum requests per window |
| `OBSKIT_RATE_LIMIT_WINDOW_SECONDS` | `60.0` | Rate limit window size in seconds |

---

## Part of the obskit family

`obskit-resilience` is part of the [obskit](https://github.com/talaatmagdyx/obskit) monorepo — a production-ready observability toolkit for Python microservices.

| Install only this package | Install everything |
|---|---|
| `pip install obskit-resilience` | `pip install "obskit[all]"` |
