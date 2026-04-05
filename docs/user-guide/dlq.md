# Dead Letter Queue Tracking

`DLQTracker` records Prometheus metrics for messages that exhaust retries and land in a Dead Letter Queue (DLQ).  Use it in any background worker that routes failed messages to a DLQ.

## Quick Start

```python
from obskit import DLQTracker, DLQReason

dlq = DLQTracker("orders_dlq")

# In your retry loop — when retries are exhausted:
dlq.track_message_sent(
    original_queue="orders",
    reason=DLQReason.MAX_RETRIES.value,
    message_id="msg-abc123",
    message_age_seconds=300,
    retry_count=5,
)
```

## Metrics emitted

| Metric | Type | Labels |
|--------|------|--------|
| `dlq_messages_total` | Counter | `dlq_name`, `original_queue`, `reason` |
| `dlq_message_age_seconds` | Histogram | `dlq_name`, `original_queue` |
| `dlq_size` | Gauge | `dlq_name` |
| `dlq_oldest_message_age_seconds` | Gauge | `dlq_name` |
| `dlq_processing_total` | Counter | `dlq_name`, `status` |
| `dlq_processing_latency_seconds` | Histogram | `dlq_name` |

## DLQ Reasons

`DLQReason` is an enum with common reason codes:

| Value | Meaning |
|-------|---------|
| `MAX_RETRIES` | Message exhausted retry budget |
| `PARSE_ERROR` | Payload could not be decoded |
| `VALIDATION_ERROR` | Payload failed schema validation |
| `HANDLER_ERROR` | Business-logic exception |
| `TIMEOUT` | Handler exceeded time limit |
| `REJECTED` | Explicitly rejected by handler |
| `EXPIRED` | TTL expired before processing |
| `UNKNOWN` | Catch-all for unexpected errors |

## Tracking reprocessing

```python
with dlq.track_processing("msg-abc123"):
    reprocess(message)
# Records dlq_processing_total{status="success"} and processing latency
```

## Global registry

```python
from obskit import get_dlq_tracker

dlq = get_dlq_tracker("orders_dlq")       # creates if first call
same_dlq = get_dlq_tracker("orders_dlq")  # returns cached instance
```

## Threshold alerts

```python
def on_threshold(name, size):
    alert_pagerduty(f"DLQ {name} has {size} messages!")

dlq = DLQTracker("critical_dlq", alert_threshold=50, on_threshold_exceeded=on_threshold)
```

## API Reference

::: obskit.integrations.queue.dlq.DLQTracker
::: obskit.integrations.queue.dlq.DLQReason
::: obskit.integrations.queue.dlq.get_dlq_tracker
