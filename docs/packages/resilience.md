# Resilience Instrumentation

obskit provides Prometheus metrics for circuit breakers and rate limiters so failures, state transitions, and rate-limit hits become visible in dashboards without modifying your business logic.

---

## Circuit Breaker Metrics

### `instrument_pybreaker` — pybreaker integration

*New in v1.8.0.* Attach obskit metrics to any [pybreaker](https://github.com/danielfm/pybreaker) `CircuitBreaker` instance:

```python
import pybreaker
from obskit import instrument_pybreaker

breaker = pybreaker.CircuitBreaker(fail_max=5, reset_timeout=60)
instrument_pybreaker(breaker, name="payments-api")
```

That's it — no other code changes needed.  The listener is registered with `breaker.add_listener` and starts recording metrics immediately.

### `instrument_circuit_breaker` — generic breaker

Any object with an `add_listener(listener)` method works:

```python
from obskit.resilience.circuit_breaker import instrument_circuit_breaker

listener = instrument_circuit_breaker(my_breaker, name="twitter-api")
```

### Emitted metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `circuit_breaker_state{name}` | Gauge | `name` | Current state: 0=closed, 1=open, 2=half-open |
| `circuit_breaker_calls_total{name,outcome}` | Counter | `name`, `outcome` | Total calls — `outcome` is `success` or `failure` |
| `circuit_breaker_failures_total{name}` | Counter | `name` | Failed calls |
| `circuit_breaker_transitions_total{name,from_state,to_state}` | Counter | `name`, `from_state`, `to_state` | State transitions |

### Manual recording

The `ObskitCircuitBreakerListener` also exposes standalone helpers for custom integration:

```python
from obskit.resilience.circuit_breaker import ObskitCircuitBreakerListener

listener = ObskitCircuitBreakerListener("custom-breaker")

# Record outcomes
listener.record_success()
listener.record_failure(exc=RuntimeError("timeout"))

# Record a state change (also updates the transitions counter)
listener.record_state_change("open")
listener.record_state_change("half_open")
listener.record_state_change("closed")
```

### Grafana alert example

```promql
# Alert when any circuit breaker has been open for > 2 minutes
circuit_breaker_state > 0
  unless on(name) (circuit_breaker_state offset 2m == 0)
```

---

## Rate Limiter Metrics

### `instrument_rate_limiter`

*New in v1.8.0.* Wrap any object that has `check()` and/or `record_limit()` methods:

```python
from obskit import instrument_rate_limiter

instr = instrument_rate_limiter(my_rate_limiter, platform="twitter")
```

After instrumentation:

- `my_rate_limiter.check(...)` — if it raises any exception, the hits counter is incremented and the exception is re-raised.  If the exception carries a `retry_after` or `reset_after` attribute, the reset gauge is updated.
- `my_rate_limiter.record_limit(...)` — the recorded counter is incremented, the original return value is preserved.

### Emitted metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `rate_limit_hits_total{platform}` | Counter | `platform` | Exceptions raised by `check()` (rate-limited calls) |
| `rate_limit_recorded_total{platform}` | Counter | `platform` | Calls to `record_limit()` |
| `rate_limit_reset_seconds{platform}` | Gauge | `platform` | Seconds until the rate limit resets (`retry_after` / `reset_after`) |

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `limiter` | required | Any object with `check()` and/or `record_limit()` methods |
| `platform` | `"default"` | Label value for the `platform` dimension in all metrics |

### Example with tweepy

```python
import tweepy
from obskit import instrument_rate_limiter

client = tweepy.Client(bearer_token="...")
instr = instrument_rate_limiter(client, platform="twitter")

# client.check() / client.record_limit() are now instrumented
```

### Grafana alert example

```promql
# Alert when Twitter rate-limit hits spike
rate(rate_limit_hits_total{platform="twitter"}[5m]) > 5
```

---

---

## Retry Metrics

### `instrument_tenacity` — tenacity retry instrumentation

*New in v1.9.0.* Attach Prometheus metrics to any [tenacity](https://tenacity.readthedocs.io/) retry decorator.  Two usage patterns are supported:

**With the `retry()` shorthand (tenacity 9.x recommended pattern):**

```python
from tenacity import retry, retry_if_exception_type, stop_after_attempt
from tenacity import wait_exponential_jitter
from obskit import instrument_tenacity

platform_retry = instrument_tenacity(
    retry(
        retry=retry_if_exception_type(IOError),
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=0.5, max=8, jitter=2),
        before_sleep=_log_retry,   # existing callback is preserved
        reraise=True,
    ),
    name="platform_http",
)

@platform_retry
async def call_api():
    ...
```

**With a `Retrying`/`AsyncRetrying` instance (use with `.wraps`):**

```python
import tenacity
from obskit import instrument_tenacity

platform_retry = instrument_tenacity(
    tenacity.AsyncRetrying(
        retry=tenacity.retry_if_exception_type(IOError),
        stop=tenacity.stop_after_attempt(3),
        wait=tenacity.wait_exponential_jitter(initial=0.5, max=8),
        reraise=True,
    ),
    name="platform_http",
)

@platform_retry.wraps
async def call_api():
    ...
```

`instrument_tenacity` detects which form is passed and handles both transparently.

### Emitted metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `retry_attempts_total{name, attempt_number}` | Counter | `name`, `attempt_number` | Incremented before each sleep between retries. `attempt_number` is the 1-based index of the attempt that just failed. |
| `retry_exhausted_total{name}` | Counter | `name` | Incremented when the stop condition is reached on a failed attempt — all retries exhausted. |

### How the counters relate

For a `stop_after_attempt(3)` retry that always fails:

| Attempt | `retry_attempts_total` (attempt_number) | `retry_exhausted_total` |
|---------|----------------------------------------|------------------------|
| 1 fails → retry scheduled | `"1"` +1 | — |
| 2 fails → retry scheduled | `"2"` +1 | — |
| 3 fails → stop condition met | — | +1 |

The last failure is captured by `retry_exhausted_total` instead of `retry_attempts_total` because tenacity does not sleep before re-raising.

### Parameters

| Parameter | Description |
|-----------|-------------|
| `retry_obj` | Either a `tenacity.Retrying` / `tenacity.AsyncRetrying` instance **or** the decorator factory returned by `tenacity.retry(...)` (a plain callable in tenacity 9.x). Both forms are supported. |
| `name` | Label value used in all metric series. Use a human-readable name such as `"twitter_api"` or `"payments_http"`. |

### Preserving existing hooks

Any `before_sleep` or `after` hook already on the retry object is called before the metrics hook fires — existing logging callbacks are not replaced:

```python
import tenacity
from obskit import instrument_tenacity

def log_retry(retry_state):
    print(f"Retry #{retry_state.attempt_number}")

retry_obj = tenacity.AsyncRetrying(
    stop=tenacity.stop_after_attempt(5),
    before_sleep=log_retry,   # ← preserved
)
instrument_tenacity(retry_obj, name="my_service")
```

### Grafana alert example

```promql
# Alert when any service is exhausting retries
rate(retry_exhausted_total[5m]) > 0
```

---

## API Reference

::: obskit.integrations.resilience.pybreaker.instrument_pybreaker
::: obskit.integrations.resilience.tenacity.instrument_tenacity
::: obskit.integrations.resilience.rate_limiter.instrument_rate_limiter
::: obskit.resilience.circuit_breaker.ObskitCircuitBreakerListener
::: obskit.resilience.circuit_breaker.instrument_circuit_breaker
