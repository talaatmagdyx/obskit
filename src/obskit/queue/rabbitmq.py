"""
RabbitMQ Instrumentation
========================

This module provides automatic instrumentation for RabbitMQ consumers.
"""

from __future__ import annotations

from typing import Any

from obskit.logging import get_logger

logger = get_logger("obskit.queue.rabbitmq")


def instrument_rabbitmq(
    channel: Any,
    queue_name: str,
    consumer_tag: str | None = None,
) -> None:
    """
    Instrument a RabbitMQ channel for automatic message tracking.

    This function wraps the consume method to track:
    - Message processing time
    - Message processing errors
    - Queue depth

    Parameters
    ----------
    channel : pika.channel.Channel
        RabbitMQ channel to instrument.

    queue_name : str
        Name of the queue being consumed.

    consumer_tag : str, optional
        Consumer tag for identification.

    Example
    -------
    >>> import pika
    >>> from obskit.queue import instrument_rabbitmq
    >>>
    >>> connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
    >>> channel = connection.channel()
    >>>
    >>> instrument_rabbitmq(channel, queue_name="orders")
    >>>
    >>> # All message processing is now automatically tracked
    >>> channel.basic_consume(queue='orders', on_message_callback=callback)
    """
    try:
        from obskit.queue.tracker import QueueTracker

        tracker = QueueTracker(queue_name)
        original_consume = channel.basic_consume

        def instrumented_consume(*args: Any, **kwargs: Any) -> Any:
            """Wrap consume to track messages."""
            callback = kwargs.get("on_message_callback") or (args[0] if args else None)

            if callback:

                def tracked_callback(ch: Any, method: Any, properties: Any, body: Any) -> None:
                    """Tracked message callback."""
                    with tracker.track_message_processing(
                        operation="process_message",
                        message_id=properties.message_id
                        if hasattr(properties, "message_id")
                        else None,
                    ):
                        callback(ch, method, properties, body)

                kwargs["on_message_callback"] = tracked_callback

            return original_consume(*args, **kwargs)

        channel.basic_consume = instrumented_consume

        logger.info(
            "rabbitmq_instrumented",
            queue=queue_name,
            consumer_tag=consumer_tag,
        )

    except ImportError:
        logger.warning(
            "pika_not_available",
            message="pika (RabbitMQ client) not installed. Install with: pip install pika",
        )


__all__ = ["instrument_rabbitmq"]
