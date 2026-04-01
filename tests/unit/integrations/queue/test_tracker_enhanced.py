"""Unit tests for enhanced QueueTracker with MessageContext."""

from __future__ import annotations

import pytest

from obskit.integrations.queue.tracker import MessageContext, QueueTracker


class TestMessageContext:
    """Tests for MessageContext dataclass."""

    def test_default_values(self):
        """Test MessageContext default values."""
        ctx = MessageContext()
        assert ctx.message_id is None
        assert ctx.correlation_id is None
        assert ctx.tenant_id is None
        assert ctx.redelivered is False
        assert ctx.message_age_ms is None
        assert ctx.delivery_tag is None
        assert ctx.extra == {}

    def test_with_values(self):
        """Test MessageContext with values."""
        ctx = MessageContext(
            message_id="msg-123",
            correlation_id="corr-456",
            tenant_id="tenant-789",
            redelivered=True,
            message_age_ms=100.5,
            delivery_tag=42,
        )
        assert ctx.message_id == "msg-123"
        assert ctx.correlation_id == "corr-456"
        assert ctx.tenant_id == "tenant-789"
        assert ctx.redelivered is True
        assert ctx.message_age_ms == pytest.approx(100.5)
        assert ctx.delivery_tag == 42

    def test_to_dict_filters_none(self):
        """Test to_dict filters out None values."""
        ctx = MessageContext(message_id="msg-123")
        d = ctx.to_dict()

        assert "message_id" in d
        assert d["message_id"] == "msg-123"
        assert "correlation_id" not in d
        assert "tenant_id" not in d

    def test_to_dict_includes_extra(self):
        """Test to_dict includes extra fields."""
        ctx = MessageContext(
            message_id="msg-123",
            extra={"order_id": "order-456", "customer": "john"},
        )
        d = ctx.to_dict()

        assert d["message_id"] == "msg-123"
        assert d["order_id"] == "order-456"
        assert d["customer"] == "john"

    def test_to_dict_with_redelivered_false(self):
        """Test to_dict includes redelivered when False."""
        ctx = MessageContext(redelivered=False)
        d = ctx.to_dict()

        assert "redelivered" in d
        assert d["redelivered"] is False


class TestQueueTrackerTrackMessage:
    """Tests for QueueTracker.track_message method."""

    def test_track_message_success(self):
        """Test track_message with successful operation."""
        tracker = QueueTracker("test_queue")
        ctx = MessageContext(message_id="msg-123")

        with tracker.track_message("process", ctx) as context:
            assert context.message_id == "msg-123"

    def test_track_message_without_context(self):
        """Test track_message without provided context."""
        tracker = QueueTracker("test_queue")

        with tracker.track_message("process") as context:
            assert isinstance(context, MessageContext)

    def test_track_message_context_is_mutable(self):
        """Test that context can be modified during processing."""
        tracker = QueueTracker("test_queue")

        with tracker.track_message("process") as context:
            context.extra["order_id"] = "order-123"
            context.extra["status"] = "completed"

        assert context.extra["order_id"] == "order-123"
        assert context.extra["status"] == "completed"

    def test_track_message_failure(self):
        """Test track_message records failure metrics."""
        tracker = QueueTracker("test_queue")
        ctx = MessageContext(message_id="msg-123")

        with pytest.raises(ValueError):
            with tracker.track_message("process", ctx):
                raise ValueError("test error")

    def test_track_message_yields_context(self):
        """Test that track_message yields the context object."""
        tracker = QueueTracker("test_queue")
        ctx = MessageContext(message_id="msg-123", tenant_id="tenant-456")

        with tracker.track_message("process", ctx) as yielded_ctx:
            assert yielded_ctx is ctx


class TestQueueTrackerReceivedTracking:
    """Tests for QueueTracker.track_message_received method."""

    def test_track_message_received_basic(self):
        """Test basic message received tracking."""
        tracker = QueueTracker("test_queue")
        # Should not raise
        tracker.track_message_received()

    def test_track_message_received_with_metadata(self):
        """Test message received with full metadata."""
        tracker = QueueTracker("test_queue")
        tracker.track_message_received(
            message_size_bytes=1024,
            redelivered=False,
            message_age_ms=50.5,
            delivery_tag=42,
        )

    def test_track_message_received_redelivered(self):
        """Test redelivered message tracking."""
        tracker = QueueTracker("test_queue")
        tracker.track_message_received(redelivered=True, delivery_tag=42)

    def test_track_message_received_with_extra(self):
        """Test message received with extra metadata."""
        tracker = QueueTracker("test_queue")
        tracker.track_message_received(
            redelivered=False,
            custom_field="custom_value",
            another_field=123,
        )


class TestQueueTrackerAckNackTracking:
    """Tests for QueueTracker ack/nack tracking methods."""

    def test_track_message_acked(self):
        """Test message acked tracking."""
        tracker = QueueTracker("test_queue")
        tracker.track_message_acked(delivery_tag=42)

    def test_track_message_acked_no_tag(self):
        """Test message acked without delivery tag."""
        tracker = QueueTracker("test_queue")
        tracker.track_message_acked()

    def test_track_message_nacked_basic(self):
        """Test basic message nacked tracking."""
        tracker = QueueTracker("test_queue")
        tracker.track_message_nacked(delivery_tag=42)

    def test_track_message_nacked_with_requeue(self):
        """Test message nacked with requeue."""
        tracker = QueueTracker("test_queue")
        tracker.track_message_nacked(delivery_tag=42, requeue=True)

    def test_track_message_nacked_with_reason(self):
        """Test message nacked with reason."""
        tracker = QueueTracker("test_queue")
        tracker.track_message_nacked(
            delivery_tag=42,
            requeue=False,
            reason="Validation failed",
        )


class TestQueueTrackerSetQueueDepth:
    """Tests for QueueTracker.set_queue_depth method."""

    def test_set_queue_depth(self):
        """Test setting queue depth."""
        tracker = QueueTracker("test_queue")
        tracker.set_queue_depth(100)

    def test_set_queue_depth_zero(self):
        """Test setting queue depth to zero."""
        tracker = QueueTracker("test_queue")
        tracker.set_queue_depth(0)


class TestQueueTrackerLegacyMethod:
    """Tests for QueueTracker legacy track_message_processing method."""

    def test_track_message_processing_success(self):
        """Test legacy track_message_processing with success."""
        tracker = QueueTracker("test_queue")

        with tracker.track_message_processing("process", "msg-123"):
            pass  # NOSONAR

    def test_track_message_processing_failure(self):
        """Test legacy track_message_processing with failure."""
        tracker = QueueTracker("test_queue")

        with pytest.raises(ValueError):
            with tracker.track_message_processing("process", "msg-123"):
                raise ValueError("test error")


class TestTrackMessageProcessingConvenience:
    """Tests for track_message_processing convenience function."""

    def test_convenience_function(self):
        """Test the convenience function."""
        from obskit.integrations.queue.tracker import track_message_processing

        with track_message_processing("process", queue_name="test"):
            pass  # NOSONAR

    def test_convenience_function_with_message_id(self):
        """Test convenience function with message ID."""
        from obskit.integrations.queue.tracker import track_message_processing

        with track_message_processing("process", "test", "msg-123"):
            pass  # NOSONAR

    def test_convenience_function_failure(self):
        """Test convenience function with failure."""
        from obskit.integrations.queue.tracker import track_message_processing

        with pytest.raises(ValueError):
            with track_message_processing("process", "test", "msg-123"):
                raise ValueError("test error")
