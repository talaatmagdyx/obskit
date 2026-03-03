# obskit-queue

Message queue observability for RabbitMQ, Kafka, and any compatible broker.

Install the broker-specific extras:

```bash
pip install "obskit[rabbitmq]"   # pika
pip install "obskit[kafka]"      # kafka-python
pip install "obskit[prometheus]" # metrics export
```

---

## Overview

`obskit.queue` provides three layers of observability for message queues:

| Layer | What it does |
|-------|-------------|
| **QueueTracker** | RED metrics + structured logs per message |
| **MessageTracer** | Distributed trace context propagation across queues |
| **instrument_rabbitmq / instrument_kafka** | Zero-code auto-instrumentation |

---

## Quick Start

=== "QueueTracker (recommended)"

    ```python
    from obskit.queue import QueueTracker, MessageContext

    tracker = QueueTracker("orders")

    def callback(ch, method, properties, body):
        ctx = MessageContext(
            message_id=properties.message_id,
            redelivered=method.redelivered,
            tenant_id=properties.headers.get("tenant_id"),
        )
        with tracker.track_message("process_order", context=ctx) as msg_ctx:
            # process message
            result = process(body)
            # optionally enrich context
            msg_ctx.extra["order_id"] = result.order_id
    ```

=== "Auto-instrumentation — RabbitMQ"

    ```python
    from obskit.queue import instrument_rabbitmq

    # Wraps channel.consume() automatically
    instrument_rabbitmq(channel, queue_name="orders")
    ```

=== "Auto-instrumentation — Kafka"

    ```python
    from obskit.queue import instrument_kafka

    instrument_kafka(consumer, topic="orders", group_id="order-workers")
    ```

=== "Distributed Tracing"

    ```python
    from obskit.queue import MessageTracer

    tracer = MessageTracer(queue_type="rabbitmq")

    # Publisher: inject context into headers
    with tracer.trace_publish(queue="orders", message_size=len(body)):
        headers = tracer.inject_context()
        channel.basic_publish(exchange="", routing_key="orders",
                              body=body, properties=pika.BasicProperties(headers=headers))

    # Consumer: extract context from headers
    def on_message(ch, method, properties, body):
        with tracer.trace_consume(queue="orders", headers=dict(properties.headers or {})):
            process(body)
    ```

---

## QueueTracker

```python
from obskit.queue import QueueTracker

tracker = QueueTracker("orders")
```

### `track_message(operation, context=None)`

Full-featured context manager. Yields a mutable `MessageContext`, records metrics and logs on exit.

```python
with tracker.track_message("process_order") as ctx:
    ctx.tenant_id = extract_tenant(body)
    do_work(body)
```

### `track_message_processing(operation, message_id=None)`

Lightweight context manager — metrics only, no business context.

```python
with tracker.track_message_processing("process_order", message_id="abc-123"):
    do_work(body)
```

### `set_queue_depth(depth)`

Update the queue depth gauge (call after polling broker stats).

```python
tracker.set_queue_depth(queue.method.message_count)
```

### Manual tracking helpers

```python
tracker.track_message_received(
    message_size_bytes=len(body),
    redelivered=method.redelivered,
    message_age_ms=age_ms,
    delivery_tag=method.delivery_tag,
)

tracker.track_message_acked(delivery_tag=method.delivery_tag)

tracker.track_message_nacked(
    delivery_tag=method.delivery_tag,
    requeue=True,
    reason="processing_failed",
)
```

---

## MessageContext

Dataclass for passing business context through message processing.

```python
from obskit.queue import MessageContext

ctx = MessageContext(
    message_id="msg-001",
    correlation_id="corr-123",
    tenant_id="acme",
    redelivered=False,
    message_age_ms=45.2,
    delivery_tag=7,
    extra={"order_id": "ord-999"},
)
```

| Field | Type | Description |
|-------|------|-------------|
| `message_id` | `str \| None` | Broker message ID |
| `correlation_id` | `str \| None` | Cross-service correlation ID |
| `tenant_id` | `str \| None` | Tenant identifier |
| `redelivered` | `bool` | Whether this is a retry |
| `message_age_ms` | `float \| None` | Time since publish |
| `delivery_tag` | `int \| None` | Broker delivery tag |
| `extra` | `dict` | Free-form fields for logging |

---

## MessageTracer

Propagates OpenTelemetry trace context across queue boundaries.

```python
from obskit.queue import MessageTracer, TracedMessagePublisher, traced_message_handler

tracer = MessageTracer(queue_type="rabbitmq")  # or "kafka", "sqs"
```

### `inject_context(headers=None) → dict`

Inject the current span context into a headers dict.

```python
headers = tracer.inject_context(existing_headers)
```

### `extract_context(headers) → SpanContext | None`

Extract and restore span context from incoming headers.

### `trace_publish(queue, exchange=None, routing_key=None, message_size=None)`

Context manager — creates a publish span with messaging attributes.

### `trace_consume(queue, headers=None, message_id=None, message_size=None)`

Context manager — creates a consume span, restoring upstream trace if present.

### `TracedMessagePublisher`

Async publisher wrapper that injects trace context automatically:

```python
publisher = TracedMessagePublisher(channel, exchange="events")
await publisher.publish(routing_key="orders", body={"id": 1})
```

### `@traced_message_handler`

Decorator that wraps a consumer function with trace context extraction:

```python
@traced_message_handler(queue="orders", queue_type="rabbitmq",
                        extract_headers=lambda msg: msg.properties.headers)
async def handle_order(message):
    ...
```

---

## Auto-instrumentation

### `instrument_rabbitmq(channel, queue_name, consumer_tag=None)`

Wraps `channel.basic_consume()` to automatically track message processing time, errors, and queue depth. Requires `pip install "obskit[rabbitmq]"`.

```python
from obskit.queue import instrument_rabbitmq

instrument_rabbitmq(channel, queue_name="orders")
channel.start_consuming()
```

### `instrument_kafka(consumer, topic, group_id=None)`

Wraps the poll loop to track per-message processing time, errors, and consumer lag. Requires `pip install "obskit[kafka]"`.

```python
from obskit.queue import instrument_kafka

instrument_kafka(consumer, topic="orders", group_id="workers")
for message in consumer:
    process(message)
```

---

## Prometheus Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `queue_messages_total` | Counter | `queue`, `operation`, `status` | Total messages processed |
| `queue_message_latency_seconds` | Histogram | `queue`, `operation` | Processing latency |
| `queue_message_size_bytes` | Histogram | `queue`, `operation` | Message size distribution |
| `obskit_queue_messages_received_total` | Counter | `queue`, `redelivered` | Messages received |
| `obskit_queue_messages_acked_total` | Counter | `queue` | Messages acknowledged |
| `obskit_queue_messages_nacked_total` | Counter | `queue`, `requeue` | Messages nack'd |

---

## Convenience Function

```python
from obskit.queue import track_message_processing

# Stateless — creates a temporary QueueTracker internally
with track_message_processing("process_order", queue_name="orders", message_id="abc"):
    do_work()
```

---

## See Also

- [`obskit.consumer_lag`](advanced.md#consumer-lag-tracking) — lag metrics and catch-up estimation
- [`obskit.dlq`](advanced.md#dead-letter-queue-dlq-tracking) — dead-letter queue monitoring
- [Resilience](resilience.md) — retry + circuit breaker for message handlers
