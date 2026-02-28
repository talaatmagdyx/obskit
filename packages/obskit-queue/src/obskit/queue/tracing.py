"""
Async Message Tracing for RabbitMQ, Kafka, and SQS.

Provides automatic trace context propagation across message queues.
"""

import functools
import json
import time
from collections.abc import Callable
from contextlib import contextmanager
from typing import Any, TypeVar

from opentelemetry import trace
from opentelemetry.trace import SpanKind, Status, StatusCode
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from prometheus_client import Counter, Histogram

from ..logging import get_logger

logger = get_logger(__name__)

# Metrics
MESSAGE_COUNTER = Counter(
    "queue_messages_total", "Total messages processed", ["queue", "operation", "status"]
)

MESSAGE_LATENCY = Histogram(
    "queue_message_latency_seconds",
    "Message processing latency",
    ["queue", "operation"],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

MESSAGE_SIZE = Histogram(
    "queue_message_size_bytes",
    "Message size in bytes",
    ["queue", "operation"],
    buckets=[100, 500, 1000, 5000, 10000, 50000, 100000, 500000, 1000000],
)

F = TypeVar("F", bound=Callable[..., Any])
_propagator = TraceContextTextMapPropagator()


class MessageTracer:
    """
    Traces messages across queue systems.

    Supports RabbitMQ, Kafka, and SQS with automatic trace context propagation.
    """

    def __init__(self, queue_type: str = "rabbitmq"):
        """
        Initialize message tracer.

        Args:
            queue_type: Type of queue system (rabbitmq, kafka, sqs)
        """
        self.queue_type = queue_type
        self.tracer = trace.get_tracer(__name__)

    def inject_context(self, headers: dict[str, str] | None = None) -> dict[str, str]:
        """
        Inject trace context into message headers.

        Args:
            headers: Existing headers dict (will be modified in place)

        Returns:
            Headers dict with trace context
        """
        if headers is None:
            headers = {}
        _propagator.inject(headers)
        return headers

    def extract_context(self, headers: dict[str, str]) -> trace.SpanContext | None:
        """
        Extract trace context from message headers.

        Args:
            headers: Message headers

        Returns:
            Extracted span context or None
        """
        ctx = _propagator.extract(headers)
        return trace.get_current_span(ctx).get_span_context()

    @contextmanager
    def trace_publish(
        self,
        queue: str,
        exchange: str | None = None,
        routing_key: str | None = None,
        message_size: int | None = None,
        attributes: dict[str, Any] | None = None,
    ):
        """
        Context manager for tracing message publishing.

        Args:
            queue: Queue/topic name
            exchange: Exchange name (RabbitMQ)
            routing_key: Routing key
            message_size: Size of message in bytes
            attributes: Additional span attributes
        """
        span_attributes = {
            "messaging.system": self.queue_type,
            "messaging.destination": queue,
            "messaging.operation": "publish",
        }
        if exchange:
            span_attributes["messaging.rabbitmq.exchange"] = exchange
        if routing_key:
            span_attributes["messaging.rabbitmq.routing_key"] = routing_key
        if attributes:
            span_attributes.update(attributes)

        start_time = time.time()
        status = "success"

        with self.tracer.start_as_current_span(
            f"publish {queue}", kind=SpanKind.PRODUCER, attributes=span_attributes
        ) as span:
            try:
                yield span
            except Exception as e:
                status = "error"
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise
            finally:
                duration = time.time() - start_time
                MESSAGE_COUNTER.labels(queue=queue, operation="publish", status=status).inc()
                MESSAGE_LATENCY.labels(queue=queue, operation="publish").observe(duration)
                if message_size:
                    MESSAGE_SIZE.labels(queue=queue, operation="publish").observe(message_size)

    @contextmanager
    def trace_consume(
        self,
        queue: str,
        headers: dict[str, str] | None = None,
        message_id: str | None = None,
        message_size: int | None = None,
        attributes: dict[str, Any] | None = None,
    ):
        """
        Context manager for tracing message consumption.

        Args:
            queue: Queue/topic name
            headers: Message headers (for trace context extraction)
            message_id: Message ID
            message_size: Size of message in bytes
            attributes: Additional span attributes
        """
        # Extract parent context from headers
        ctx = None
        if headers:
            ctx = _propagator.extract(headers)

        span_attributes = {
            "messaging.system": self.queue_type,
            "messaging.destination": queue,
            "messaging.operation": "receive",
        }
        if message_id:
            span_attributes["messaging.message_id"] = message_id
        if attributes:
            span_attributes.update(attributes)

        start_time = time.time()
        status = "success"

        with self.tracer.start_as_current_span(
            f"consume {queue}", context=ctx, kind=SpanKind.CONSUMER, attributes=span_attributes
        ) as span:
            try:
                yield span
            except Exception as e:
                status = "error"
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise
            finally:
                duration = time.time() - start_time
                MESSAGE_COUNTER.labels(queue=queue, operation="consume", status=status).inc()
                MESSAGE_LATENCY.labels(queue=queue, operation="consume").observe(duration)
                if message_size:
                    MESSAGE_SIZE.labels(queue=queue, operation="consume").observe(message_size)


def traced_message_handler(
    queue: str,
    queue_type: str = "rabbitmq",
    extract_headers: Callable[[Any], dict[str, str]] | None = None,
) -> Callable[[F], F]:
    """
    Decorator for tracing message handlers.

    Args:
        queue: Queue/topic name
        queue_type: Type of queue system
        extract_headers: Function to extract headers from message

    Returns:
        Decorated function

    Example:
        @traced_message_handler(queue="my_queue")
        async def handle_message(message):
            process(message)
    """
    tracer = MessageTracer(queue_type)

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            headers = {}
            if extract_headers and args:
                try:
                    headers = extract_headers(args[0])
                except Exception:
                    pass  # Header extraction failed - continue without trace context

            with tracer.trace_consume(queue=queue, headers=headers):
                return await func(*args, **kwargs)

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            headers = {}
            if extract_headers and args:
                try:
                    headers = extract_headers(args[0])
                except Exception:
                    pass  # Header extraction failed - continue without trace context

            with tracer.trace_consume(queue=queue, headers=headers):
                return func(*args, **kwargs)

        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return sync_wrapper  # type: ignore

    return decorator


class TracedMessagePublisher:
    """
    Publisher with automatic trace context injection.

    Example:
        publisher = TracedMessagePublisher(channel, exchange="my_exchange")
        await publisher.publish(routing_key="key", body={"data": "value"})
    """

    def __init__(self, channel: Any, exchange: str = "", queue_type: str = "rabbitmq"):
        """
        Initialize traced publisher.

        Args:
            channel: Queue channel/connection
            exchange: Default exchange name
            queue_type: Type of queue system
        """
        self.channel = channel
        self.exchange = exchange
        self.tracer = MessageTracer(queue_type)

    async def publish(
        self,
        routing_key: str,
        body: dict | str | bytes,
        exchange: str | None = None,
        headers: dict[str, str] | None = None,
        **kwargs,
    ):
        """
        Publish message with trace context.

        Args:
            routing_key: Routing key
            body: Message body
            exchange: Override exchange
            headers: Additional headers
            **kwargs: Additional publish arguments
        """
        exchange = exchange or self.exchange
        headers = headers or {}

        # Inject trace context
        self.tracer.inject_context(headers)

        # Serialize body if needed
        if isinstance(body, dict):
            body_bytes = json.dumps(body).encode()
        elif isinstance(body, str):
            body_bytes = body.encode()
        else:
            body_bytes = body

        with self.tracer.trace_publish(
            queue=routing_key,
            exchange=exchange,
            routing_key=routing_key,
            message_size=len(body_bytes),
        ):
            # Support both pika and aio_pika style
            if hasattr(self.channel, "basic_publish"):
                # pika style
                import pika

                self.channel.basic_publish(
                    exchange=exchange,
                    routing_key=routing_key,
                    body=body_bytes,
                    properties=pika.BasicProperties(headers=headers),
                    **kwargs,
                )
            elif hasattr(self.channel, "default_exchange"):
                # aio_pika style
                import aio_pika

                message = aio_pika.Message(body=body_bytes, headers=headers)
                await self.channel.default_exchange.publish(
                    message, routing_key=routing_key, **kwargs
                )
            else:
                logger.warning("Unknown channel type, publishing without trace context")


# Convenience instances
def get_message_tracer(queue_type: str = "rabbitmq") -> MessageTracer:
    """Get a message tracer instance."""
    return MessageTracer(queue_type)


__all__ = [
    "MessageTracer",
    "TracedMessagePublisher",
    "traced_message_handler",
    "get_message_tracer",
    "MESSAGE_COUNTER",
    "MESSAGE_LATENCY",
    "MESSAGE_SIZE",
]
