# Redis Cache Instrumentation

obskit wraps async Redis clients so every command is automatically timed and counted with Prometheus metrics — no manual instrumentation or pipeline changes required.

## Quick Start

```python
import redis.asyncio as aioredis
from obskit import instrument_redis_client

redis_client = aioredis.from_url("redis://localhost:6379", decode_responses=True)
redis_client = instrument_redis_client(redis_client, name="engagement-cache")

# All commands are now instrumented:
await redis_client.get("my-key")
await redis_client.set("my-key", "value", ex=60)
await redis_client.hgetall("hash-key")
```

The wrapper is **transparent** — every attribute on the underlying client is accessible through it.  Only `async` command methods are wrapped with instrumentation; synchronous helpers (like `.connection_pool`) pass through unchanged.

## `instrument_redis_client`

*New in v1.9.0.*

```python
from obskit import instrument_redis_client

redis_client = instrument_redis_client(redis_client, name="rate-limiter-store")
```

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `client` | required | Any async Redis client (e.g. `redis.asyncio.Redis`, `aioredis.Redis`) |
| `name` | `"default"` | Label value for the `name` dimension in all metrics. Use a logical name such as `"session-cache"` or `"rate-limiter-store"`. |

### Emitted metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `redis_commands_total{name, command, status}` | Counter | `name`, `command`, `status` | Total commands executed. `status` is `"success"` or `"error"`. |
| `redis_command_duration_seconds{name, command}` | Histogram | `name`, `command` | Round-trip latency per command. |
| `redis_command_errors_total{name, command}` | Counter | `name`, `command` | Commands that raised an exception (dedicated error counter). |

### `command` label values

The `command` label is the Redis method name as called on the client — `"get"`, `"set"`, `"hgetall"`, `"zadd"`, `"expire"`, etc.

## Connection Pool Monitoring

Call `update_pool_stats()` periodically to refresh the pool gauge:

```python
redis_client = instrument_redis_client(
    aioredis.from_url("redis://localhost:6379"),
    name="engagement-cache",
)

# In a background task or health check:
redis_client.update_pool_stats()
```

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `redis_pool_connections{name, state}` | Gauge | `name`, `state` | Pool connections by state: `"available"` or `"in_use"`. |

The gauge is not updated on every command because pool introspection differs across redis-py versions.

## Multiple Redis Clients

Use a distinct `name` per logical cache to keep metrics separate:

```python
from obskit import instrument_redis_client

session_cache = instrument_redis_client(
    aioredis.from_url("redis://sessions:6379"),
    name="session-cache",
)

rate_limiter_store = instrument_redis_client(
    aioredis.from_url("redis://ratelimit:6379"),
    name="rate-limiter-store",
)

event_retry_store = instrument_redis_client(
    aioredis.from_url("redis://events:6379"),
    name="event-retry-store",
)
```

## Legacy `instrument_redis`

`instrument_redis` (the original function name) is still available and equivalent:

```python
from obskit.integrations.cache import instrument_redis

redis_client = instrument_redis(redis_client, name="engagement-cache")
```

Prefer `instrument_redis_client` in new code — it is available at the top-level `obskit` namespace and has a more descriptive name.

## Grafana alert examples

```promql
# Alert when Redis error rate rises
rate(redis_command_errors_total[5m]) > 0.1

# P99 GET latency exceeds 50 ms
histogram_quantile(0.99,
  rate(redis_command_duration_seconds_bucket{command="get"}[5m])
) > 0.05

# Connection pool exhaustion
redis_pool_connections{state="available"} == 0
```

## API Reference

::: obskit.integrations.cache.instrument_redis_client
::: obskit.integrations.cache.InstrumentedRedis
