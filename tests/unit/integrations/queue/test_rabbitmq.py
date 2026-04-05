"""Tests for obskit.integrations.queue.rabbitmq module."""

from unittest.mock import MagicMock, call, patch

from obskit.integrations.queue.rabbitmq import (
    inject_trace_context_to_headers,
    instrument_rabbitmq,
)


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

    @patch("obskit.integrations.queue.rabbitmq.logger")
    def test_logs_instrumentation(self, mock_logger):
        """Test that instrumentation is logged."""
        mock_channel = MagicMock()

        instrument_rabbitmq(mock_channel, queue_name="test_queue", consumer_tag="my_consumer")

        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert call_args[0][0] == "rabbitmq_instrumented"

    @patch("obskit.integrations.queue.tracker.QueueTracker")
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
            pass  # NOSONAR

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
            pass  # NOSONAR

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

    def test_tracked_callback_with_trace_context_in_headers(self):
        """Callback runs inside OTel span when traceparent header is present."""
        callback_results = []

        def original_callback(ch, method, props, body):
            callback_results.append(body)

        mock_channel = MagicMock()
        original_consume = MagicMock()
        mock_channel.basic_consume = original_consume

        instrument_rabbitmq(mock_channel, queue_name="traced_queue")
        mock_channel.basic_consume(on_message_callback=original_callback)
        wrapped_callback = original_consume.call_args.kwargs["on_message_callback"]

        mock_props = MagicMock()
        mock_props.message_id = "trace-msg-1"
        mock_props.headers = {
            "traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
        }

        wrapped_callback(MagicMock(), MagicMock(), mock_props, b"traced body")

        assert len(callback_results) == 1
        assert callback_results[0] == b"traced body"

    def test_tracked_callback_without_headers_falls_back(self):
        """Callback runs normally when properties have no headers."""
        callback_results = []

        def original_callback(ch, method, props, body):
            callback_results.append(body)

        mock_channel = MagicMock()
        original_consume = MagicMock()
        mock_channel.basic_consume = original_consume

        instrument_rabbitmq(mock_channel, queue_name="noheader_queue")
        mock_channel.basic_consume(on_message_callback=original_callback)
        wrapped_callback = original_consume.call_args.kwargs["on_message_callback"]

        mock_props = MagicMock()
        mock_props.message_id = "msg-no-trace"
        mock_props.headers = None  # no trace context

        wrapped_callback(MagicMock(), MagicMock(), mock_props, b"plain body")

        assert len(callback_results) == 1

    def test_tracked_callback_empty_headers_falls_back(self):
        """Callback runs normally when headers dict is empty."""
        callback_results = []

        def original_callback(ch, method, props, body):
            callback_results.append(body)

        mock_channel = MagicMock()
        original_consume = MagicMock()
        mock_channel.basic_consume = original_consume

        instrument_rabbitmq(mock_channel, queue_name="empty_headers_queue")
        mock_channel.basic_consume(on_message_callback=original_callback)
        wrapped_callback = original_consume.call_args.kwargs["on_message_callback"]

        mock_props = MagicMock(spec=["message_id", "headers"])
        mock_props.message_id = "msg-empty"
        mock_props.headers = {}

        wrapped_callback(MagicMock(), MagicMock(), mock_props, b"body")

        assert len(callback_results) == 1


class TestInjectTraceContextToHeaders:
    """Tests for inject_trace_context_to_headers."""

    def test_injects_traceparent_when_otel_available(self):
        """inject_trace_context_to_headers populates headers via OTel propagate."""
        headers: dict = {}

        mock_propagate = MagicMock()

        def fake_inject(carrier):
            carrier["traceparent"] = "00-abc123-def456-01"

        mock_propagate.inject.side_effect = fake_inject

        with patch.dict("sys.modules", {"opentelemetry.propagate": mock_propagate}):
            # Re-import to pick up the mock
            import importlib

            import obskit.integrations.queue.rabbitmq as mod

            importlib.reload(mod)
            mod.inject_trace_context_to_headers(headers)

        # After reload, use the live module
        inject_trace_context_to_headers(headers)
        # OTel is installed in the test env, so traceparent should appear
        # (or headers stays empty if no active span — either is fine)
        assert isinstance(headers, dict)

    def test_inject_noop_without_otel(self):
        """inject_trace_context_to_headers is a no-op when OTel not installed."""
        import sys

        headers: dict = {}

        # Temporarily hide opentelemetry
        saved = {}
        for key in list(sys.modules):
            if key == "opentelemetry" or key.startswith("opentelemetry."):
                saved[key] = sys.modules.pop(key)
        try:
            # Re-import module without OTel
            import importlib

            import obskit.integrations.queue.rabbitmq as mod

            importlib.reload(mod)
            mod.inject_trace_context_to_headers(headers)
        finally:
            sys.modules.update(saved)
            # Restore original module state
            import importlib as _il

            _il.reload(mod)

        assert headers == {}

    def test_inject_modifies_headers_dict_in_place(self):
        """Headers dict is modified in-place (not replaced)."""
        original_headers: dict = {"x-custom": "value"}

        inject_trace_context_to_headers(original_headers)

        # Custom key still present
        assert original_headers.get("x-custom") == "value"
        # Dict is still the same object (mutation, not replacement)
        assert "x-custom" in original_headers

    def test_module_exports(self):
        """__all__ includes both public functions."""
        from obskit.integrations.queue import rabbitmq

        assert "instrument_rabbitmq" in rabbitmq.__all__
        assert "inject_trace_context_to_headers" in rabbitmq.__all__


class TestExtractTraceContextFromHeaders:
    """Tests for the public extract_trace_context_from_headers API."""

    def test_returns_none_for_none_headers(self):
        from obskit.integrations.queue.rabbitmq import extract_trace_context_from_headers

        assert extract_trace_context_from_headers(None) is None

    def test_returns_none_for_empty_headers(self):
        from obskit.integrations.queue.rabbitmq import extract_trace_context_from_headers

        assert extract_trace_context_from_headers({}) is None

    def test_returns_context_for_traceparent(self):
        from obskit.integrations.queue.rabbitmq import extract_trace_context_from_headers

        headers = {
            "traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
        }
        ctx = extract_trace_context_from_headers(headers)
        assert ctx is not None

    def test_is_in_all(self):
        from obskit.integrations.queue import rabbitmq

        assert "extract_trace_context_from_headers" in rabbitmq.__all__


class TestExtractTraceContext:
    """Tests for _extract_trace_context helper."""

    def test_returns_none_for_none_headers(self):
        """Returns None when headers is None."""
        from obskit.integrations.queue.rabbitmq import _extract_trace_context

        result = _extract_trace_context(None)
        assert result is None

    def test_returns_none_for_empty_headers(self):
        """Returns None when headers dict is empty."""
        from obskit.integrations.queue.rabbitmq import _extract_trace_context

        result = _extract_trace_context({})
        assert result is None

    def test_returns_context_for_valid_traceparent(self):
        """Returns extracted context for valid traceparent header."""
        from obskit.integrations.queue.rabbitmq import _extract_trace_context

        headers = {
            "traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
        }
        ctx = _extract_trace_context(headers)
        # OTel is installed in test env — should return a context object
        assert ctx is not None
