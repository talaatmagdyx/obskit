"""
Queue Instrumentation
=====================

This module provides observability for message queues (RabbitMQ, Kafka, etc.),
including message processing metrics, queue depth tracking, and error monitoring.

Example - RabbitMQ Instrumentation
----------------------------------
.. code-block:: python

    from obskit.queue import instrument_rabbitmq
    import pika

    connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
    channel = connection.channel()

    # Instrument the channel
    instrument_rabbitmq(channel, queue_name="orders")

    # Now all message processing is automatically tracked

Example - Kafka Instrumentation
------------------------------
.. code-block:: python

    from obskit.queue import instrument_kafka
    from kafka import KafkaConsumer

    consumer = KafkaConsumer('orders', bootstrap_servers=['localhost:9092'])

    # Instrument the consumer
    instrument_kafka(consumer, topic="orders")

    # Now all message processing is automatically tracked

Example - Manual Queue Tracking
------------------------------
.. code-block:: python

    from obskit.queue import track_message_processing

    async with track_message_processing("process_order", queue="orders"):
        await process_order(message)
"""

from __future__ import annotations

from obskit.queue.tracing import (
    MESSAGE_COUNTER,
    MESSAGE_LATENCY,
    MESSAGE_SIZE,
    MessageTracer,
    TracedMessagePublisher,
    get_message_tracer,
    traced_message_handler,
)
from obskit.queue.tracker import MessageContext, QueueTracker, track_message_processing

try:
    from obskit.queue.kafka import instrument_kafka
    from obskit.queue.rabbitmq import instrument_rabbitmq

    __all__ = [
        "MessageContext",
        "QueueTracker",
        "track_message_processing",
        "instrument_rabbitmq",
        "instrument_kafka",
        # Tracing
        "MessageTracer",
        "TracedMessagePublisher",
        "traced_message_handler",
        "get_message_tracer",
        "MESSAGE_COUNTER",
        "MESSAGE_LATENCY",
        "MESSAGE_SIZE",
    ]
except ImportError:
    __all__ = [
        "MessageContext",
        "QueueTracker",
        "track_message_processing",
        # Tracing
        "MessageTracer",
        "TracedMessagePublisher",
        "traced_message_handler",
        "get_message_tracer",
        "MESSAGE_COUNTER",
        "MESSAGE_LATENCY",
        "MESSAGE_SIZE",
    ]
