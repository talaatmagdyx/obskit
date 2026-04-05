# Adaptive Log Sampling

`AdaptiveSampledLogger` wraps any structlog logger and automatically adjusts per-level sampling rates to stay within a target log volume — ideal for high-throughput loops like BRPOP retry workers.

## Quick Start

```python
from obskit import AdaptiveSampledLogger

logger = AdaptiveSampledLogger(
    "retry_worker",
    target_logs_per_second=50,   # aim for ≤ 50 log lines/s
)

while True:
    event = redis.brpop("retry_queue", timeout=1)
    if event:
        logger.info("event_retried", event_id=event["id"])   # throttled
        logger.warning("retry_limit_near", count=...)        # always logged
        logger.error("retry_failed", error=...)              # always logged
```

## Default sampling rates

| Level | Default rate |
|-------|-------------|
| `debug` | 1 % |
| `info` | 10 % |
| `warning` | 100 % |
| `error` | 100 % |
| `critical` | 100 % |

Rates are multiplied by the adaptive factor `target_lps / actual_lps`, then clamped to `[min_sample_rate, max_sample_rate]`.

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `name` | — | Logger name |
| `target_logs_per_second` | `100` | Target throughput |
| `min_sample_rate` | `0.001` | Floor — at least 0.1 % of messages |
| `max_sample_rate` | `1.0` | Ceiling — never exceed 100 % |
| `adjustment_interval` | `10.0` | Seconds between rate recalculations |

## Fixed-rate variant

For simpler use-cases, `SampledLogger` applies a static rate without adaptive adjustment:

```python
from obskit.logging.sampling import SampledLogger, SamplingConfig

cfg = SamplingConfig(debug_rate=0.01, info_rate=0.05)
logger = SampledLogger("my_service", config=cfg)
```

## API Reference

::: obskit.logging.sampling.AdaptiveSampledLogger
::: obskit.logging.sampling.SampledLogger
::: obskit.logging.sampling.SamplingConfig
