"""Coverage tests for obskit.queue.tracing missing lines."""

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from obskit.queue.tracing import MessageTracer, TracedMessagePublisher, traced_message_handler


class TestTracePubishAttributes:
    """Cover tracing.py:120 — attributes branch in trace_publish."""

    def test_trace_publish_with_attributes(self):
        """Cover line 120: span_attributes.update(attributes)."""
        tracer = MessageTracer()
        extra = {"custom.attr": "value", "env": "test"}
        with tracer.trace_publish(queue="my_queue", attributes=extra):
            pass  # Success path — attributes merged into span


class TestTraceConsumeAttributes:
    """Cover tracing.py:174 — attributes branch in trace_consume."""

    def test_trace_consume_with_attributes(self):
        """Cover line 174: span_attributes.update(attributes)."""
        tracer = MessageTracer()
        extra = {"custom.attr": "value"}
        with tracer.trace_consume(queue="my_queue", attributes=extra):
            pass  # Success path — attributes merged into span


class TestTracedMessageHandlerExtractHeadersException:
    """Cover tracing.py:227-228 and 237-240 — except Exception: pass branches."""

    @pytest.mark.asyncio
    async def test_async_wrapper_extract_headers_raises(self):
        """Cover lines 227-228: except Exception: pass in async_wrapper."""

        def bad_extractor(msg):
            raise RuntimeError("extraction failed")

        @traced_message_handler(queue="test_queue", extract_headers=bad_extractor)
        async def handle(msg):
            return "ok"

        # Despite extract_headers raising, handler should still run
        result = await handle({"body": "data"})
        assert result == "ok"

    def test_sync_wrapper_extract_headers_raises(self):
        """Cover lines 237-240: except Exception: pass in sync_wrapper."""

        def bad_extractor(msg):
            raise ValueError("cannot extract")

        @traced_message_handler(queue="test_queue", extract_headers=bad_extractor)
        def handle(msg):
            return "done"

        result = handle("raw_message")
        assert result == "done"


class TestTracedMessagePublisherBodyTypes:
    """Cover tracing.py:303-306 — str and bytes body branches."""

    @pytest.mark.asyncio
    async def test_publish_str_body(self):
        """Cover lines 303-304: isinstance(body, str) branch — body.encode()."""
        mock_channel = MagicMock()
        mock_channel.basic_publish = MagicMock()

        publisher = TracedMessagePublisher(channel=mock_channel, exchange="ex")
        await publisher.publish(routing_key="rk", body="plain string body")

        mock_channel.basic_publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_bytes_body(self):
        """Cover lines 305-306: else branch — body_bytes = body (already bytes)."""
        mock_channel = MagicMock()
        mock_channel.basic_publish = MagicMock()

        publisher = TracedMessagePublisher(channel=mock_channel, exchange="ex")
        await publisher.publish(routing_key="rk", body=b"\x00\x01\x02 bytes")

        mock_channel.basic_publish.assert_called_once()


class TestTracedMessagePublisherChannelTypes:
    """Cover tracing.py:326-335 — aio_pika style and unknown channel branches."""

    @pytest.mark.asyncio
    async def test_publish_aio_pika_style(self):
        """Cover lines 326-333: elif hasattr(self.channel, 'default_exchange') branch."""
        mock_exchange = AsyncMock()
        mock_channel = MagicMock(spec=["default_exchange"])
        mock_channel.default_exchange = mock_exchange

        mock_aio_pika = MagicMock()
        mock_message_obj = MagicMock()
        mock_aio_pika.Message.return_value = mock_message_obj

        publisher = TracedMessagePublisher(channel=mock_channel, exchange="")

        with patch.dict(sys.modules, {"aio_pika": mock_aio_pika}):
            await publisher.publish(routing_key="rk", body={"key": "val"})

        mock_exchange.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_unknown_channel_type(self):
        """Cover lines 334-335: else branch — logger.warning for unknown channel."""
        # Channel with neither basic_publish nor default_exchange
        mock_channel = MagicMock(spec=["some_other_attr"])

        publisher = TracedMessagePublisher(channel=mock_channel)

        with patch("obskit.queue.tracing.logger") as mock_logger:
            await publisher.publish(routing_key="rk", body={"key": "val"})

        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args
        assert call_args[0][0] == "Unknown channel type, publishing without trace context"
