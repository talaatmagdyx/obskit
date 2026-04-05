# RabbitMQ Distributed Tracing

obskit propagates W3C trace context across RabbitMQ message boundaries so publisher and consumer spans appear as a single end-to-end trace in Tempo/Jaeger.

## Publisher — inject trace context

Call `inject_trace_context_to_headers` before publishing.  The current span's `traceparent` is written into the headers dict you pass to `BasicProperties`.

```python
import pika
from obskit import inject_trace_context_to_headers

headers: dict = {}
inject_trace_context_to_headers(headers)   # writes "traceparent" key

props = pika.BasicProperties(
    content_type="application/json",
    headers=headers,
)
channel.basic_publish(
    exchange="",
    routing_key="orders",
    body=payload,
    properties=props,
)
```

## Consumer — extract trace context automatically

`instrument_rabbitmq` wraps `basic_consume` so every delivered message is:

1. Processed inside a child OTel span (`rabbitmq.consume.<queue_name>`).
2. Automatically linked to the publisher's span via the `traceparent` header.

```python
from obskit.integrations.queue.rabbitmq import instrument_rabbitmq

instrument_rabbitmq(channel, queue_name="orders")

def handle_order(ch, method, properties, body):
    # Active span is a child of the publisher span
    process_order(body)

channel.basic_consume(queue="orders", on_message_callback=handle_order)
channel.start_consuming()
```

## Manual context extraction with `use_span_context`

*New in v1.8.0.* If you process messages outside `instrument_rabbitmq` (e.g. in a custom async consumer), use `extract_trace_context_from_headers` and `use_span_context` to re-parent your spans under the publisher's trace manually:

```python
from obskit import extract_trace_context_from_headers, use_span_context
from obskit.tracing import async_trace_span

async def on_message(message):
    headers = message.properties.headers or {}
    ctx = extract_trace_context_from_headers(headers)

    with use_span_context(ctx):
        async with async_trace_span("orders.process"):
            # This span is a child of the publisher's span
            await process_order(message.body)
```

`use_span_context` is a sync context manager — use it around `async with` blocks or regular `with` blocks.  When `ctx` is `None` (no `traceparent` header found), it is a no-op and a fresh root span is created.

## Span attributes

The consumer span carries these attributes:

| Attribute | Value |
|-----------|-------|
| `messaging.system` | `"rabbitmq"` |
| `messaging.destination` | `<queue_name>` |
| `messaging.message_id` | Value of `properties.message_id` |

## Without OTel installed

Both helpers degrade gracefully:

- `inject_trace_context_to_headers` — no-op; headers dict is left unchanged.
- Consumer callback — runs normally without a span; QueueTracker metrics still collected.

## API Reference

::: obskit.integrations.queue.rabbitmq.inject_trace_context_to_headers
::: obskit.integrations.queue.rabbitmq.extract_trace_context_from_headers
::: obskit.integrations.queue.rabbitmq.instrument_rabbitmq
