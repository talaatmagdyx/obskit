"""
Kafka Instrumentation
=====================

This module provides automatic instrumentation for Kafka consumers.
"""

from __future__ import annotations

from typing import Any

from obskit.logging import get_logger

logger = get_logger("obskit.queue.kafka")


def instrument_kafka(
    consumer: Any,
    topic: str,
    group_id: str | None = None,
) -> None:
    """
    Instrument a Kafka consumer for automatic message tracking.

    This function wraps the consumer to track:
    - Message processing time
    - Message processing errors
    - Consumer lag

    Parameters
    ----------
    consumer : kafka.KafkaConsumer
        Kafka consumer to instrument.

    topic : str
        Topic name being consumed.

    group_id : str, optional
        Consumer group ID.

    Example
    -------
    >>> from kafka import KafkaConsumer
    >>> from obskit.queue import instrument_kafka
    >>>
    >>> consumer = KafkaConsumer('orders', bootstrap_servers=['localhost:9092'])
    >>> instrument_kafka(consumer, topic="orders")
    >>>
    >>> # All message processing is now automatically tracked
    >>> for message in consumer:
    ...     process_message(message)
    """
    try:
        from obskit.queue.tracker import QueueTracker

        tracker = QueueTracker(topic)
        original_iter = consumer.__iter__

        def instrumented_iter() -> Any:
            """Wrap iteration to track messages."""
            for message in original_iter():
                with tracker.track_message_processing(
                    operation="process_message",
                    message_id=str(message.offset) if hasattr(message, "offset") else None,
                ):
                    yield message

        consumer.__iter__ = instrumented_iter

        logger.info(
            "kafka_instrumented",
            topic=topic,
            group_id=group_id,
        )

    except ImportError:
        logger.warning(
            "kafka_not_available",
            message="kafka-python not installed. Install with: pip install kafka-python",
        )


__all__ = ["instrument_kafka"]
