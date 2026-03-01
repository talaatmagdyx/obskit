<div align="center">

# 📬 obskit-queue

**Kafka and RabbitMQ instrumentation with consumer lag monitoring, DLQ tracking, and distributed trace propagation**

---

[![PyPI](https://img.shields.io/pypi/v/obskit-queue.svg?color=blue)](https://pypi.org/project/obskit-queue/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![obskit](https://img.shields.io/badge/part%20of-obskit-blueviolet.svg)](https://github.com/talaatmagdyx/obskit)

</div>

## What it does

- **Instruments Kafka and RabbitMQ transparently** — `instrument_kafka(consumer, topic=...)` and `instrument_rabbitmq(channel, queue_name=...)` wrap the native consumer interfaces to record per-message duration metrics and error rates with zero changes to your message-handling code.
- **Propagates distributed traces across message boundaries** — `MessageTracer` injects W3C `traceparent` headers on publish and extracts them on consume, stitching producer and consumer spans into a single end-to-end trace in Jaeger or Tempo.
- **Catches queue health problems early** — `ConsumerLagTracker` monitors how far behind consumers are falling (with growth rate and estimated catch-up time), while `DLQTracker` tracks dead-letter queue depth, message age, and retry success rates — all exposed as Prometheus gauges and counters.

---

## Installation

```bash
# Core package (manual tracking only)
pip install obskit-queue

# With Kafka support
pip install "obskit-queue[kafka]"

# With RabbitMQ support
pip install "obskit-queue[rabbitmq]"

# Both
pip install "obskit-queue[kafka,rabbitmq]"
```

---

## Quick Start

```python
# --- Kafka producer with automatic trace injection ---
from kafka import KafkaProducer
from obskit.queue import instrument_kafka
from obskit.queue.tracing import MessageTracer

producer = KafkaProducer(bootstrap_servers=["kafka.internal:9092"])
tracer = MessageTracer(queue_type="kafka")

async def publish_order_placed(order: dict) -> None:
    headers = {}
    tracer.inject_context(headers)        # inject W3C traceparent

    with tracer.trace_publish(queue="order.placed", message_size=len(str(order))):
        producer.send(
            "order.placed",
            value=order,
            headers=[(k, v.encode()) for k, v in headers.items()],
        )


# --- Kafka consumer with automatic instrumentation ---
from kafka import KafkaConsumer
from obskit.queue import instrument_kafka

consumer = KafkaConsumer(
    "order.placed",
    bootstrap_servers=["kafka.internal:9092"],
    group_id="fulfillment-service",
)
instrument_kafka(consumer, topic="order.placed", group_id="fulfillment-service")

for message in consumer:                 # processing is now auto-tracked
    await handle_order_placed(message.value)
```

---

## Kafka Instrumentation

### Producer — manual tracing

```python
from obskit.queue.tracing import MessageTracer

tracer = MessageTracer(queue_type="kafka")

async def publish_payment_captured(payment: dict) -> None:
    headers: dict[str, str] = {}
    tracer.inject_context(headers)   # stamps traceparent into headers

    with tracer.trace_publish(
        queue="payment.captured",
        routing_key="payment.captured",
        message_size=len(str(payment).encode()),
        attributes={"payment.id": payment["id"], "amount": payment["total"]},
    ):
        producer.send(
            "payment.captured",
            value=payment,
            headers=[(k, v.encode()) for k, v in headers.items()],
        )
```

### Consumer — decorator approach

```python
from obskit.queue import traced_message_handler

@traced_message_handler(
    queue="payment.captured",
    queue_type="kafka",
    extract_headers=lambda msg: {
        k: v.decode() for k, v in (msg.headers or [])
    },
)
async def handle_payment_captured(message) -> None:
    payment = message.value
    await fulfillment.trigger_shipment(payment["order_id"])
    await loyalty.award_points(payment["customer_id"], payment["total"])
```

The decorator extracts the `traceparent` from message headers and creates a child span linked to the producer's span — giving you a complete producer → consumer trace.

### Consumer — context manager approach

```python
from obskit.queue.tracing import MessageTracer

tracer = MessageTracer(queue_type="kafka")

for message in consumer:
    headers = {k: v.decode() for k, v in (message.headers or [])}
    with tracer.trace_consume(
        queue="order.placed",
        headers=headers,
        message_id=str(message.offset),
        message_size=len(message.value),
    ):
        await process_order(message.value)
```

---

## RabbitMQ Instrumentation

### Channel instrumentation

```python
import pika
from obskit.queue import instrument_rabbitmq

connection = pika.BlockingConnection(
    pika.ConnectionParameters(host="rabbitmq.internal")
)
channel = connection.channel()
channel.queue_declare(queue="orders", durable=True)

# Wrap the channel — all basic_consume calls are now tracked
instrument_rabbitmq(channel, queue_name="orders")

def on_order_received(ch, method, properties, body):
    process_order(body)
    ch.basic_ack(delivery_tag=method.delivery_tag)

channel.basic_consume(queue="orders", on_message_callback=on_order_received)
channel.start_consuming()
```

### TracedMessagePublisher — publish with automatic trace injection

```python
from obskit.queue.tracing import TracedMessagePublisher

publisher = TracedMessagePublisher(channel, exchange="orders", queue_type="rabbitmq")

async def publish_order(order: dict) -> None:
    await publisher.publish(
        routing_key="orders.created",
        body=order,
        headers={"x-source": "checkout-service"},
    )
    # traceparent is injected automatically into the AMQP headers
```

---

## Consumer Lag Monitoring

`ConsumerLagTracker` records how many messages (and bytes) a consumer is behind, calculates the growth rate, and estimates time to catch up. A configurable threshold triggers warnings with a 5-minute cooldown.

```python
from obskit.consumer_lag import ConsumerLagTracker, QueueType

orders_lag = ConsumerLagTracker(
    queue_name="order.placed",
    queue_type=QueueType.KAFKA,
    consumer_group="fulfillment-service",
    lag_threshold=10_000,       # warn when more than 10 000 messages behind
    window_seconds=60,
    on_high_lag=lambda queue, lag: pagerduty.alert(f"{queue} lag={lag}"),
)

# Called from your monitoring loop (e.g., every 30 s)
async def refresh_lag_metrics() -> None:
    lag_info = await kafka_admin.get_consumer_group_offsets("fulfillment-service")
    current_lag = lag_info["order.placed"]["lag"]

    orders_lag.set_lag(messages=current_lag)

# Called after each successful message processing
orders_lag.message_consumed()
orders_lag.messages_consumed(count=10)   # batch processing

# Inspect current state
stats = orders_lag.get_stats()
print(f"Lag:          {stats.current_lag_messages:,} messages")
print(f"Growth rate:  {stats.lag_growth_rate:+.1f} msg/s")
print(f"Velocity:     {stats.consumer_velocity:.1f} msg/s")
print(f"Catch-up ETA: {stats.estimated_catch_up_seconds:.0f}s")
print(f"Falling behind: {stats.is_falling_behind}")
print(f"Healthy: {orders_lag.is_healthy()}")
```

### Prometheus metrics emitted

| Metric | Description |
|---|---|
| `consumer_lag_messages` | Current message lag (gauge) |
| `consumer_lag_bytes` | Current byte lag (gauge) |
| `consumer_lag_seconds` | Estimated catch-up time (gauge) |
| `consumer_lag_growth_rate` | Lag change rate — positive = falling behind (gauge) |
| `consumer_velocity_messages_per_second` | Consumer throughput (gauge) |
| `consumer_messages_total` | Total messages consumed (counter) |
| `consumer_lag_high_events_total` | Times lag exceeded threshold (counter) |

---

## Dead Letter Queue (DLQ) Tracking

`DLQTracker` gives you full visibility into your dead-letter queues: depth, message age, failure reasons, and reprocessing success rates.

```python
from obskit.dlq import DLQTracker, DLQReason

orders_dlq = DLQTracker(
    dlq_name="orders_dlq",
    alert_threshold=100,    # log error when DLQ exceeds 100 messages
    on_threshold_exceeded=lambda name, size: alert_ops(f"{name} has {size} dead messages"),
)

# When a message is sent to DLQ
async def handle_order_failure(message_id: str, order: dict, error: Exception) -> None:
    orders_dlq.track_message_sent(
        original_queue="order.placed",
        reason=DLQReason.HANDLER_ERROR.value,
        message_id=message_id,
        message_age_seconds=time.time() - order["created_at"],
        retry_count=order.get("retry_count", 0),
        error_message=str(error),
        order_id=order["id"],           # extra metadata
        customer_id=order["customer_id"],
    )

# When reprocessing a DLQ message
async def reprocess_dead_message(message_id: str) -> None:
    with orders_dlq.track_processing(message_id):
        order = await dlq_queue.get_message(message_id)
        await process_order(order)      # if this raises, failure is tracked

# Inspect DLQ health
stats = orders_dlq.get_stats()
print(f"DLQ size:         {stats.current_size}")
print(f"Oldest message:   {stats.oldest_message_age_seconds:.0f}s ago")
print(f"By reason:        {stats.messages_by_reason}")
print(f"Reprocess rate:   {stats.processing_success_rate:.1%}")

# List messages for triage
for msg in orders_dlq.get_messages(limit=20):
    print(f"  {msg.message_id}  reason={msg.reason}  retries={msg.retry_count}")
```

### DLQ Prometheus metrics

| Metric | Description |
|---|---|
| `dlq_messages_total` | Messages sent to DLQ (counter, labeled by `reason`) |
| `dlq_message_age_seconds` | Message age when DLQ'd (histogram) |
| `dlq_size` | Current DLQ depth (gauge) |
| `dlq_oldest_message_age_seconds` | Age of oldest DLQ message (gauge) |
| `dlq_processing_total` | Reprocessing attempts (counter, labeled by `status`) |
| `dlq_processing_latency_seconds` | Reprocessing duration (histogram) |
| `dlq_reprocessed_total` | Total reprocessed (counter, labeled by `success`) |

---

## Full Producer → Consumer Trace Flow

Here is how a single `checkout` action produces a distributed trace spanning the producer, Kafka, and the consumer:

```
[checkout-service]
  POST /checkout
  └── Span: http_server "POST /checkout"
       └── Span: publish "order.placed"   ← tracer.trace_publish()
            │   traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01
            └── [Kafka: order.placed topic]

[fulfillment-service]
  ├── Span: consume "order.placed"         ← tracer.trace_consume(headers=...)
  │    └── parent: 00-4bf92f3577b34da6...  ← linked via traceparent header
  │         ├── Span: db.reserve_inventory
  │         └── Span: http_client "POST /shipments"
```

---

## Manual Queue Tracking

For custom queue implementations not covered by the Kafka/RabbitMQ adapters:

```python
from obskit.queue import QueueTracker, track_message_processing

tracker = QueueTracker("custom-queue")

# Context manager
with tracker.track_message_processing(
    operation="process_order",
    message_id="msg-abc123",
):
    await process(message)

# Module-level convenience
async with track_message_processing("sqs-handler", queue="order-events"):
    await handle_sqs_event(record)
```

---

## Environment Variables / Configuration

| Variable | Default | Description |
|---|---|---|
| `OBSKIT_QUEUE_DEFAULT_LAG_THRESHOLD` | `10000` | Default consumer lag alert threshold |
| `OBSKIT_QUEUE_DLQ_ALERT_THRESHOLD` | `100` | Default DLQ depth alert threshold |
| `OBSKIT_QUEUE_LAG_WINDOW_SECONDS` | `60` | Window for lag growth rate calculation |

---

## Part of the obskit family

`obskit-queue` is part of the [obskit](https://github.com/talaatmagdyx/obskit) monorepo — a production-ready observability toolkit for Python microservices.

| Install only this package | Install everything |
|---|---|
| `pip install obskit-queue` | `pip install "obskit[all]"` |
