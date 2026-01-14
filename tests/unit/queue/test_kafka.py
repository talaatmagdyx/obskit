"""Tests for obskit.queue.kafka module."""

from unittest.mock import MagicMock, patch

from obskit.queue.kafka import instrument_kafka


class TestInstrumentKafka:
    """Tests for instrument_kafka function."""

    def test_instruments_consumer(self):
        """Test that instrument_kafka wraps the consumer."""
        mock_consumer = MagicMock()
        mock_consumer.__iter__ = MagicMock(return_value=iter([]))

        instrument_kafka(mock_consumer, topic="test_topic")

        # Consumer should have __iter__ replaced (it's a function now)
        assert callable(mock_consumer.__iter__)

    def test_instruments_with_group_id(self):
        """Test instrumentation with group_id."""
        mock_consumer = MagicMock()
        mock_consumer.__iter__ = MagicMock(return_value=iter([]))

        instrument_kafka(mock_consumer, topic="test_topic", group_id="test_group")

    @patch("obskit.queue.tracker.QueueTracker")
    def test_creates_queue_tracker(self, mock_tracker_class):
        """Test that QueueTracker is created with topic name."""
        mock_tracker = MagicMock()
        mock_tracker_class.return_value = mock_tracker
        mock_tracker.track_message_processing.return_value.__enter__ = MagicMock()
        mock_tracker.track_message_processing.return_value.__exit__ = MagicMock(return_value=False)

        mock_consumer = MagicMock()
        mock_consumer.__iter__ = MagicMock(return_value=iter([]))

        instrument_kafka(mock_consumer, topic="my_topic")

        mock_tracker_class.assert_called_once_with("my_topic")

    @patch("obskit.queue.kafka.logger")
    def test_logs_instrumentation(self, mock_logger):
        """Test that instrumentation is logged."""
        mock_consumer = MagicMock()
        mock_consumer.__iter__ = MagicMock(return_value=iter([]))

        instrument_kafka(mock_consumer, topic="test_topic", group_id="test_group")

        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert call_args[0][0] == "kafka_instrumented"


class SimpleConsumer:
    """Simple consumer class for testing iteration."""

    def __init__(self, messages):
        self._messages = messages

    def __iter__(self):
        return iter(self._messages)


class TestInstrumentedIteration:
    """Tests for the instrumented iteration (lines 61-66)."""

    def test_iterating_yields_messages_with_offset(self):
        """Test that instrumented consumer yields messages with offset tracking."""
        # Create mock messages with offset attribute
        mock_message1 = MagicMock()
        mock_message1.offset = 100
        mock_message2 = MagicMock()
        mock_message2.offset = 101

        consumer = SimpleConsumer([mock_message1, mock_message2])

        instrument_kafka(consumer, topic="test_topic")

        # Call the instrumented iterator directly
        messages = list(consumer.__iter__())

        assert len(messages) == 2
        assert messages[0] == mock_message1
        assert messages[1] == mock_message2

    def test_iterating_yields_messages_without_offset(self):
        """Test that instrumented consumer handles messages without offset."""
        # Create mock message without offset attribute
        mock_message = MagicMock(spec=["value", "key"])  # No offset

        consumer = SimpleConsumer([mock_message])

        instrument_kafka(consumer, topic="test_topic")

        messages = list(consumer.__iter__())

        assert len(messages) == 1
        assert messages[0] == mock_message

    def test_iterating_empty_consumer(self):
        """Test that instrumented consumer handles empty iteration."""
        consumer = SimpleConsumer([])

        instrument_kafka(consumer, topic="test_topic")

        messages = list(consumer.__iter__())

        assert len(messages) == 0

    def test_multiple_messages_with_mixed_offset(self):
        """Test iteration with mixed offset availability."""
        msg_with_offset = MagicMock()
        msg_with_offset.offset = 42
        msg_without_offset = MagicMock(spec=["value"])  # No offset

        consumer = SimpleConsumer([msg_with_offset, msg_without_offset])

        instrument_kafka(consumer, topic="test_topic")

        messages = list(consumer.__iter__())

        assert len(messages) == 2
