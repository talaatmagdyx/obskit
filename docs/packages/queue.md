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

`obskit.integrations.queue` provides three layers of observability for message queues:

| Layer | What it does |
|-------|-------------|
| **QueueTracker** | RED metrics + structured logs per message |
| **MessageTracer** | Distributed trace context propagation across queues |
| **instrument_rabbitmq / instrument_kafka** | Zero-code auto-instrumentation |

---

## Quick Start

=== "QueueTracker (recommended)"

    ```python
    from obskit.integrations.queue.rabbitmq import QueueTracker, MessageContext

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
    from obskit.integrations.queue.rabbitmq import instrument_rabbitmq

    # Wraps channel.consume() automatically
    instrument_rabbitmq(channel, queue_name="orders")
    ```

=== "Auto-instrumentation — Kafka"

    ```python
    from obskit.integrations.queue.kafka import instrument_kafka

    instrument_kafka(consumer, topic="orders", group_id="order-workers")
    ```

---

## `instrument_rabbitmq`

Wraps `channel.basic_consume()` to automatically track message processing time, errors, and queue depth. Requires `pip install "obskit[rabbitmq]"`.

```python
from obskit.integrations.queue.rabbitmq import instrument_rabbitmq

instrument_rabbitmq(channel, queue_name="orders")
channel.start_consuming()
```

---

## `instrument_kafka`

Wraps the poll loop to track per-message processing time, errors, and consumer lag. Requires `pip install "obskit[kafka]"`.

```python
from obskit.integrations.queue.kafka import instrument_kafka

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

## See Also

- [SLO Tracking](slo.md) — track message processing SLOs
