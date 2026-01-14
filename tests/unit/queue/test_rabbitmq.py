"""Tests for obskit.queue.rabbitmq module."""

from unittest.mock import MagicMock, patch

from obskit.queue.rabbitmq import instrument_rabbitmq


class TestInstrumentRabbitmq:
    """Tests for instrument_rabbitmq function."""

    def test_instruments_channel(self):
        """Test that instrument_rabbitmq wraps the channel."""
        mock_channel = MagicMock()
        original_consume = mock_channel.basic_consume

        instrument_rabbitmq(mock_channel, queue_name="test_queue")

        # basic_consume should be wrapped
        assert mock_channel.basic_consume != original_consume

    def test_instruments_with_consumer_tag(self):
        """Test instrumentation with consumer_tag."""
        mock_channel = MagicMock()

        instrument_rabbitmq(mock_channel, queue_name="test_queue", consumer_tag="test_consumer")

    @patch("obskit.queue.rabbitmq.logger")
    def test_logs_instrumentation(self, mock_logger):
        """Test that instrumentation is logged."""
        mock_channel = MagicMock()

        instrument_rabbitmq(mock_channel, queue_name="test_queue", consumer_tag="my_consumer")

        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert call_args[0][0] == "rabbitmq_instrumented"

    @patch("obskit.queue.tracker.QueueTracker")
    def test_creates_queue_tracker(self, mock_tracker_class):
        """Test that QueueTracker is created with queue name."""
        mock_tracker = MagicMock()
        mock_tracker_class.return_value = mock_tracker

        mock_channel = MagicMock()

        instrument_rabbitmq(mock_channel, queue_name="my_queue")

        mock_tracker_class.assert_called_once_with("my_queue")


class TestInstrumentedConsume:
    """Tests for instrumented basic_consume behavior."""

    def test_consume_preserves_return_value(self):
        """Test that consume preserves original return value."""
        mock_channel = MagicMock()
        original_consume = MagicMock(return_value="consumer_tag_123")
        mock_channel.basic_consume = original_consume

        instrument_rabbitmq(mock_channel, queue_name="test_queue")

        result = mock_channel.basic_consume(queue="test_queue")

        assert result == "consumer_tag_123"

    def test_consume_without_callback(self):
        """Test consume without callback passes through."""
        mock_channel = MagicMock()
        original_consume = MagicMock()
        mock_channel.basic_consume = original_consume

        instrument_rabbitmq(mock_channel, queue_name="test_queue")

        # Call without callback
        mock_channel.basic_consume(queue="test_queue")

        original_consume.assert_called_once()

    def test_consume_with_callback_in_kwargs(self):
        """Test consume wraps callback from kwargs."""
        mock_channel = MagicMock()
        original_consume = MagicMock()
        mock_channel.basic_consume = original_consume

        instrument_rabbitmq(mock_channel, queue_name="test_queue")

        def my_callback(ch, method, props, body):
            pass

        mock_channel.basic_consume(on_message_callback=my_callback)

        # Verify callback was wrapped
        call_kwargs = original_consume.call_args.kwargs
        assert "on_message_callback" in call_kwargs
        # The callback should be wrapped (different function)
        assert call_kwargs["on_message_callback"] != my_callback

    def test_consume_with_callback_in_args(self):
        """Test consume wraps callback from args."""
        mock_channel = MagicMock()
        original_consume = MagicMock()
        mock_channel.basic_consume = original_consume

        instrument_rabbitmq(mock_channel, queue_name="test_queue")

        def my_callback(ch, method, props, body):
            pass

        # Pass callback as positional arg
        mock_channel.basic_consume(my_callback)

        original_consume.assert_called_once()


class TestTrackedCallback:
    """Tests for the tracked_callback function (lines 68-74)."""

    def test_tracked_callback_invokes_original_with_message_id(self):
        """Test that tracked callback invokes original and tracks with message_id."""
        callback_results = []

        def original_callback(ch, method, props, body):
            callback_results.append({"ch": ch, "method": method, "props": props, "body": body})

        mock_channel = MagicMock()
        original_consume = MagicMock()
        mock_channel.basic_consume = original_consume

        instrument_rabbitmq(mock_channel, queue_name="test_queue")

        # Register the callback via basic_consume
        mock_channel.basic_consume(on_message_callback=original_callback)

        # Get the wrapped callback
        wrapped_callback = original_consume.call_args.kwargs["on_message_callback"]

        # Simulate message delivery with message_id
        mock_ch = MagicMock()
        mock_method = MagicMock()
        mock_props = MagicMock()
        mock_props.message_id = "msg-12345"
        mock_body = b"test message body"

        # Invoke the wrapped callback
        wrapped_callback(mock_ch, mock_method, mock_props, mock_body)

        # Verify original callback was invoked
        assert len(callback_results) == 1
        assert callback_results[0]["body"] == mock_body
        assert callback_results[0]["props"] == mock_props

    def test_tracked_callback_invokes_original_without_message_id(self):
        """Test that tracked callback works without message_id."""
        callback_results = []

        def original_callback(ch, method, props, body):
            callback_results.append(body)

        mock_channel = MagicMock()
        original_consume = MagicMock()
        mock_channel.basic_consume = original_consume

        instrument_rabbitmq(mock_channel, queue_name="test_queue")

        mock_channel.basic_consume(on_message_callback=original_callback)

        wrapped_callback = original_consume.call_args.kwargs["on_message_callback"]

        # Simulate message delivery without message_id attribute
        mock_ch = MagicMock()
        mock_method = MagicMock()
        mock_props = MagicMock(spec=["content_type"])  # No message_id
        mock_body = b"test body"

        wrapped_callback(mock_ch, mock_method, mock_props, mock_body)

        assert len(callback_results) == 1
        assert callback_results[0] == mock_body

    def test_tracked_callback_with_multiple_messages(self):
        """Test tracked callback handles multiple message deliveries."""
        message_count = []

        def original_callback(ch, method, props, body):
            message_count.append(1)

        mock_channel = MagicMock()
        original_consume = MagicMock()
        mock_channel.basic_consume = original_consume

        instrument_rabbitmq(mock_channel, queue_name="test_queue")

        mock_channel.basic_consume(on_message_callback=original_callback)

        wrapped_callback = original_consume.call_args.kwargs["on_message_callback"]

        # Simulate multiple message deliveries
        for i in range(5):
            mock_props = MagicMock()
            mock_props.message_id = f"msg-{i}"
            wrapped_callback(MagicMock(), MagicMock(), mock_props, f"body-{i}".encode())

        assert len(message_count) == 5
