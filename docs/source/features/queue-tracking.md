# Queue Tracking with Business Context

obskit provides comprehensive queue message tracking with support for business context, enabling rich observability for message-driven architectures.

## Features

- **RED metrics** for queue operations (Rate, Errors, Duration)
- **Business context** tracking (tenant_id, correlation_id)
- **Message lifecycle** tracking (received, processed, acked, nacked)
- **Queue depth** monitoring via Golden Signals

## Quick Start

### Basic Usage

```python
from obskit import QueueTracker

tracker = QueueTracker("orders_queue")

with tracker.track_message_processing("process_order", message_id="msg-123"):
    # Process the message
    process_order(order)
```

### With Business Context

```python
from obskit import QueueTracker, MessageContext

tracker = QueueTracker("email_queue")

# Create context with business data
ctx = MessageContext(
    message_id="msg-123",
    correlation_id="corr-456",
    tenant_id="company-789",
    redelivered=False,
)

with tracker.track_message("process_email", ctx) as context:
    # Enrich context during processing
    context.extra["email_type"] = "marketing"
    context.extra["recipient_count"] = len(email.recipients)
    
    # Process the email
    send_email(email)
```

## MessageContext

The `MessageContext` dataclass carries business context through message processing:

```python
from obskit import MessageContext

ctx = MessageContext(
    message_id="msg-123",           # Unique message identifier
    correlation_id="corr-456",      # Request correlation ID
    tenant_id="tenant-789",         # Multi-tenant identifier
    redelivered=False,              # Whether message was redelivered
    message_age_ms=50.5,            # Age since published
    delivery_tag=42,                # Broker delivery tag
    extra={                         # Additional business fields
        "order_id": "order-123",
        "customer": "john@example.com",
    },
)
```

### Converting to Dict

```python
# to_dict() filters out None values
data = ctx.to_dict()
# {'message_id': 'msg-123', 'correlation_id': 'corr-456', ...}
```

### Enriching During Processing

```python
with tracker.track_message("process", ctx) as context:
    # Add fields as you process
    context.extra["processed_items"] = 42
    context.extra["total_bytes"] = 1024
```

## Tracking Methods

### track_message() - Full Context Tracking

```python
ctx = MessageContext(message_id="123", tenant_id="company")

with tracker.track_message("process_order", ctx) as context:
    # Automatically logs:
    # - queue_message_started (with context)
    # - queue_message_completed (with duration, context)
    # Or on failure:
    # - queue_message_failed (with error, duration, context)
    process(message)
```

### track_message_processing() - Simple Tracking

```python
# Simpler API without full context
with tracker.track_message_processing("process", message_id="123"):
    process(message)
```

### track_message_received()

Log when a message is received from the queue:

```python
tracker.track_message_received(
    message_size_bytes=1024,
    redelivered=False,
    message_age_ms=50.5,
    delivery_tag=42,
    custom_field="value",  # Extra fields via **kwargs
)
```

### track_message_acked()

Log when a message is acknowledged:

```python
tracker.track_message_acked(delivery_tag=42)
```

### track_message_nacked()

Log when a message is negatively acknowledged:

```python
tracker.track_message_nacked(
    delivery_tag=42,
    requeue=True,              # Will the message be requeued?
    reason="Validation failed",
)
```

### set_queue_depth()

Update queue depth metrics:

```python
# Call periodically to track queue backlog
tracker.set_queue_depth(100)
```

## Prometheus Metrics

Queue tracking exports the following metrics:

```promql
# Messages received (by queue, redelivered status)
obskit_queue_messages_received_total{queue="orders", redelivered="false"}

# Messages acknowledged
obskit_queue_messages_acked_total{queue="orders"}

# Messages negatively acknowledged (by requeue status)
obskit_queue_messages_nacked_total{queue="orders", requeue="true"}

# Processing duration (via RED metrics)
obskit_request_duration_seconds{operation="orders.process_order"}

# Request count (via RED metrics)
obskit_requests_total{operation="orders.process_order", status="success"}

# Queue depth (via Golden Signals)
obskit_queue_depth{queue="orders"}
```

## Integration with RabbitMQ

```python
import pika
from obskit import QueueTracker, MessageContext

tracker = QueueTracker("orders")

def callback(ch, method, properties, body):
    # Track message receipt
    tracker.track_message_received(
        message_size_bytes=len(body),
        redelivered=method.redelivered,
        delivery_tag=method.delivery_tag,
    )
    
    # Create context from message properties
    ctx = MessageContext(
        message_id=properties.message_id,
        correlation_id=properties.correlation_id,
        redelivered=method.redelivered,
        delivery_tag=method.delivery_tag,
    )
    
    try:
        with tracker.track_message("process", ctx) as context:
            # Extract tenant from message
            order = json.loads(body)
            context.extra["tenant_id"] = order.get("tenant_id")
            
            # Process the order
            process_order(order)
        
        # Acknowledge on success
        ch.basic_ack(delivery_tag=method.delivery_tag)
        tracker.track_message_acked(method.delivery_tag)
        
    except Exception as e:
        # Nack and requeue on failure
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
        tracker.track_message_nacked(
            delivery_tag=method.delivery_tag,
            requeue=True,
            reason=str(e),
        )

# Set up consumer
channel.basic_consume(queue='orders', on_message_callback=callback)
```

## Convenience Function

For simple use cases:

```python
from obskit import track_message_processing

with track_message_processing("process", queue_name="orders", message_id="123"):
    process(message)
```

## Best Practices

### 1. Always Include Business Context

```python
# Good: Rich context for debugging
ctx = MessageContext(
    message_id=msg.id,
    correlation_id=headers.get("x-correlation-id"),
    tenant_id=payload.get("company_id"),
)

# Bad: No context
with tracker.track_message_processing("process"):
    ...
```

### 2. Track Full Message Lifecycle

```python
# Track receipt
tracker.track_message_received(...)

# Track processing
with tracker.track_message("process", ctx):
    ...

# Track acknowledgment
tracker.track_message_acked(...)
```

### 3. Monitor Redeliveries

```python
if method.redelivered:
    logger.warning(
        "message_redelivered",
        message_id=ctx.message_id,
        delivery_tag=method.delivery_tag,
    )
```

### 4. Update Queue Depth Periodically

```python
import threading

def monitor_queue_depth():
    while True:
        depth = channel.queue_declare(queue='orders', passive=True).method.message_count
        tracker.set_queue_depth(depth)
        time.sleep(30)

threading.Thread(target=monitor_queue_depth, daemon=True).start()
```

## Alerting Examples

```yaml
# Alert on high redelivery rate
- alert: HighMessageRedeliveryRate
  expr: |
    rate(obskit_queue_messages_received_total{redelivered="true"}[5m])
    / rate(obskit_queue_messages_received_total[5m])
    > 0.1
  labels:
    severity: warning
  annotations:
    summary: "High message redelivery rate on {{ $labels.queue }}"

# Alert on growing queue depth
- alert: QueueBacklogGrowing
  expr: obskit_queue_depth > 1000
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "Queue {{ $labels.queue }} backlog is growing"

# Alert on high nack rate
- alert: HighNackRate
  expr: |
    rate(obskit_queue_messages_nacked_total[5m])
    / rate(obskit_queue_messages_received_total[5m])
    > 0.05
  labels:
    severity: warning
```

## API Reference

```python
# Main classes
from obskit import QueueTracker, MessageContext

# Convenience function
from obskit import track_message_processing
```
