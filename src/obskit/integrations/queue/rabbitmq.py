"""
RabbitMQ Instrumentation
========================

Automatic instrumentation for RabbitMQ consumers and W3C trace-context
propagation for publishers.

Consumer instrumentation
------------------------
:func:`instrument_rabbitmq` wraps ``channel.basic_consume`` so every
incoming message is tracked via :class:`~obskit.integrations.queue.tracker.QueueTracker`
and processed inside an OTel span whose parent is extracted from the
``traceparent`` / ``tracestate`` headers embedded in the AMQP message
properties (if present).

Publisher helpers
-----------------
:func:`inject_trace_context_to_headers` injects the current W3C
``traceparent`` (and ``tracestate``) into a plain ``dict`` so you can
attach it to AMQP ``BasicProperties(headers=...)`` before publishing::

    from obskit.integrations.queue.rabbitmq import inject_trace_context_to_headers
    import pika

    headers: dict = {}
    inject_trace_context_to_headers(headers)
    props = pika.BasicProperties(headers=headers)
    channel.basic_publish(exchange="", routing_key="orders", body=body, properties=props)

Trace linking
-------------
When both publisher and consumer use obskit RabbitMQ instrumentation every
message carries a ``traceparent`` header and the consumer span is
automatically attached as a child of the publisher span, creating an
end-to-end distributed trace.
"""

from __future__ import annotations

from typing import Any

from obskit.logging import get_logger

logger = get_logger("obskit.integrations.queue.rabbitmq")


# ---------------------------------------------------------------------------
# Trace helpers
# ---------------------------------------------------------------------------


def inject_trace_context_to_headers(headers: dict[str, Any]) -> None:
    """Inject the current W3C ``traceparent`` into *headers* in-place.

    Call this before publishing to RabbitMQ so the consumer can join the
    same distributed trace.

    Parameters
    ----------
    headers : dict
        Mutable dict passed as ``BasicProperties(headers=...)``.
        Modified in-place with ``traceparent`` (and ``tracestate``) keys.

    Example
    -------
    >>> headers: dict = {}
    >>> inject_trace_context_to_headers(headers)
    >>> props = pika.BasicProperties(headers=headers)
    >>> channel.basic_publish(exchange="", routing_key="q", body=b"...", properties=props)
    """
    try:
        from opentelemetry import propagate as _propagate  # noqa: PLC0415

        _propagate.inject(headers)
    except ImportError:  # pragma: no cover
        pass  # OTel not installed — no-op  # NOSONAR


def _extract_trace_context(headers: dict[str, Any] | None) -> Any | None:
    """Extract OTel ``Context`` from AMQP message headers.

    Returns the extracted context (possibly empty) or ``None`` when OTel is
    not installed or *headers* is empty/None.
    """
    if not headers:
        return None
    try:
        from opentelemetry import propagate as _propagate  # noqa: PLC0415

        return _propagate.extract(carrier=headers)
    except ImportError:  # pragma: no cover
        return None  # NOSONAR


def extract_trace_context_from_headers(headers: dict[str, Any] | None) -> Any | None:
    """Extract the W3C trace context from AMQP message headers.

    Call this in your consumer *before* processing a message so that child
    spans are attached to the publisher's trace (end-to-end visibility in
    Jaeger / Tempo).

    Parameters
    ----------
    headers : dict | None
        ``properties.headers`` from the AMQP message.  ``None`` or empty dicts
        are safely handled — the function returns ``None`` (no context).

    Returns
    -------
    opentelemetry.context.Context | None
        Extracted OTel context, or ``None`` when no trace headers are present
        or opentelemetry-api is not installed.

    Example
    -------
    ::

        from obskit.integrations.queue.rabbitmq import extract_trace_context_from_headers
        from obskit.tracing.tracer import use_span_context

        def _on_message(ch, method, properties, body):
            ctx = extract_trace_context_from_headers(properties.headers or {})
            with use_span_context(ctx):
                route_event(body)
    """
    return _extract_trace_context(headers)


# ---------------------------------------------------------------------------
# Consumer instrumentation
# ---------------------------------------------------------------------------


def instrument_rabbitmq(
    channel: Any,
    queue_name: str,
    consumer_tag: str | None = None,
) -> None:
    """Instrument a RabbitMQ channel for automatic message tracking and tracing.

    Wraps ``channel.basic_consume`` so every incoming message is:

    1. Tracked via :class:`~obskit.integrations.queue.tracker.QueueTracker`
       (processing duration + error counts).
    2. Processed inside an OTel span whose parent is extracted from the
       ``traceparent`` / ``tracestate`` headers in the AMQP message
       properties — enabling end-to-end distributed traces when the
       publisher uses :func:`inject_trace_context_to_headers`.

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
    >>> from obskit.integrations.queue.rabbitmq import instrument_rabbitmq
    >>>
    >>> connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
    >>> channel = connection.channel()
    >>>
    >>> instrument_rabbitmq(channel, queue_name="orders")
    >>> channel.basic_consume(queue='orders', on_message_callback=callback)
    """
    try:
        from obskit.integrations.queue.tracker import QueueTracker  # noqa: PLC0415

        tracker = QueueTracker(queue_name)
        original_consume = channel.basic_consume

        def instrumented_consume(*args: Any, **kwargs: Any) -> Any:
            """Wrap consume to track messages."""
            callback = kwargs.get("on_message_callback") or (args[0] if args else None)

            if callback:

                def tracked_callback(
                    ch: Any,
                    method: Any,
                    properties: Any,
                    body: Any,
                ) -> None:
                    """Tracked message callback with W3C trace-context propagation."""
                    msg_headers: dict[str, Any] | None = (
                        properties.headers if hasattr(properties, "headers") else None
                    )
                    parent_ctx = _extract_trace_context(msg_headers)

                    msg_id: str | None = (
                        properties.message_id
                        if hasattr(properties, "message_id")
                        else None
                    )

                    if parent_ctx is not None:
                        try:
                            from opentelemetry import trace as _trace  # noqa: PLC0415
                            from opentelemetry.context import attach, detach  # noqa: PLC0415

                            token = attach(parent_ctx)
                            try:
                                tracer = _trace.get_tracer("obskit.rabbitmq")
                                with tracer.start_as_current_span(
                                    f"rabbitmq.consume.{queue_name}",
                                    attributes={
                                        "messaging.system": "rabbitmq",
                                        "messaging.destination": queue_name,
                                        "messaging.message_id": msg_id or "",
                                    },
                                ):
                                    with tracker.track_message_processing(
                                        operation="process_message",
                                        message_id=msg_id,
                                    ):
                                        callback(ch, method, properties, body)
                            finally:
                                detach(token)
                            return
                        except ImportError:  # pragma: no cover
                            pass  # NOSONAR

                    # Fallback — track without OTel span.
                    with tracker.track_message_processing(
                        operation="process_message",
                        message_id=msg_id,
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

    except ImportError:  # pragma: no cover
        logger.warning(  # pragma: no cover
            "pika_not_available",
            message="pika (RabbitMQ client) not installed. Install with: pip install pika",
        )


__all__ = [
    "instrument_rabbitmq",
    "inject_trace_context_to_headers",
    "extract_trace_context_from_headers",
]
