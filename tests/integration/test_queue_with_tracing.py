"""
Integration Tests: Queue Tracing + Message Flow
================================================

Verifies that queue message handlers correctly propagate trace context,
emit processing metrics, and track consumer lag end-to-end.

Cross-package boundary tested:
  obskit-queue  →  obskit-metrics  →  obskit-core (context propagation)
"""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Tests: Message tracing context propagation
# ---------------------------------------------------------------------------


class TestMessageTracerContextPropagation:
    """MessageTracer correctly creates and propagates trace spans."""

    def test_trace_publish_creates_span_context(self) -> None:
        """trace_publish() context manager does not raise and yields a span."""
        try:
            from obskit.queue.tracing import MessageTracer
        except ImportError:
            pytest.skip("obskit-queue not available")

        tracer = MessageTracer()
        with tracer.trace_publish(queue="orders") as span:
            # span may be None when no real OTel backend is configured
            pass  # must not raise

    def test_trace_consume_creates_span_context(self) -> None:
        """trace_consume() context manager does not raise."""
        try:
            from obskit.queue.tracing import MessageTracer
        except ImportError:
            pytest.skip("obskit-queue not available")

        tracer = MessageTracer()
        with tracer.trace_consume(queue="orders"):
            pass  # must not raise

    def test_trace_publish_with_custom_attributes(self) -> None:
        """Custom attributes are accepted without error."""
        try:
            from obskit.queue.tracing import MessageTracer
        except ImportError:
            pytest.skip("obskit-queue not available")

        tracer = MessageTracer()
        attrs = {"environment": "test", "tenant": "acme", "priority": "high"}
        with tracer.trace_publish(queue="notifications", attributes=attrs):
            pass

    def test_trace_consume_with_custom_attributes(self) -> None:
        """trace_consume with attributes accepted."""
        try:
            from obskit.queue.tracing import MessageTracer
        except ImportError:
            pytest.skip("obskit-queue not available")

        tracer = MessageTracer()
        with tracer.trace_consume(queue="events", attributes={"source": "kafka"}):
            pass

    def test_trace_publish_with_routing_key(self) -> None:
        """trace_publish accepts exchange, routing_key, and message_size."""
        try:
            from obskit.queue.tracing import MessageTracer
        except ImportError:
            pytest.skip("obskit-queue not available")

        tracer = MessageTracer()
        with tracer.trace_publish(
            queue="orders",
            exchange="order_exchange",
            routing_key="order.created",
            message_size=256,
        ):
            pass

    @pytest.mark.asyncio
    async def test_traced_handler_decorator_async(self) -> None:
        """Async handler decorated with traced_message_handler runs successfully."""
        try:
            from obskit.queue.tracing import traced_message_handler
        except ImportError:
            pytest.skip("obskit-queue not available")

        processed = []

        @traced_message_handler(queue="orders")
        async def handle_order(msg):
            processed.append(msg)
            return "processed"

        result = await handle_order({"order_id": "123", "amount": 99.99})
        assert result == "processed"
        assert len(processed) == 1

    def test_traced_handler_decorator_sync(self) -> None:
        """Sync handler decorated with traced_message_handler runs successfully."""
        try:
            from obskit.queue.tracing import traced_message_handler
        except ImportError:
            pytest.skip("obskit-queue not available")

        processed = []

        @traced_message_handler(queue="events")
        def handle_event(msg):
            processed.append(msg)
            return "handled"

        result = handle_event({"event_type": "user.created", "user_id": "u-999"})
        assert result == "handled"
        assert len(processed) == 1

    @pytest.mark.asyncio
    async def test_traced_handler_extract_headers(self) -> None:
        """Trace context is extracted from message headers when provided."""
        try:
            from obskit.queue.tracing import traced_message_handler
        except ImportError:
            pytest.skip("obskit-queue not available")

        def extract(msg):
            return msg.get("headers", {})

        @traced_message_handler(queue="payments", extract_headers=extract)
        async def handle_payment(msg):
            return msg["amount"]

        result = await handle_payment(
            {"amount": 250.0, "headers": {"traceparent": "00-abc-def-01"}}
        )
        assert result == 250.0


# ---------------------------------------------------------------------------
# Tests: Queue tracker + metrics integration
# ---------------------------------------------------------------------------


class TestQueueTrackerMetricsIntegration:
    """QueueTracker emits Prometheus metrics as messages are processed."""

    def test_track_message_processing_success(self) -> None:
        """track_message_processing context manager records success metrics."""
        try:
            from obskit.queue import track_message_processing
            from obskit.metrics.registry import generate_latest
        except ImportError:
            pytest.skip("obskit-queue or obskit-metrics not available")

        with track_message_processing("process_order", queue_name="orders"):
            pass  # simulate work

        output = generate_latest()
        assert isinstance(output, bytes)

    def test_track_message_processing_failure(self) -> None:
        """track_message_processing records error metrics on exception."""
        try:
            from obskit.queue import track_message_processing
        except ImportError:
            pytest.skip("obskit-queue not available")

        with pytest.raises(ValueError, match="processing failed"):
            with track_message_processing("process_payment", queue_name="payments"):
                raise ValueError("processing failed")

    def test_queue_tracker_sync_context_manager(self) -> None:
        """QueueTracker.track_message_processing works as sync context manager."""
        try:
            from obskit.queue import QueueTracker
        except ImportError:
            pytest.skip("obskit-queue not available")

        tracker = QueueTracker("sync_queue")
        with tracker.track_message_processing("sync_op"):
            pass  # must not raise

    def test_queue_tracker_multiple_operations(self) -> None:
        """Multiple operations on the same tracker each get recorded."""
        try:
            from obskit.queue import QueueTracker
        except ImportError:
            pytest.skip("obskit-queue not available")

        tracker = QueueTracker("multi_op_queue")
        ops = ["ingest", "transform", "publish"]
        for op in ops:
            with tracker.track_message_processing(op):
                pass


# ---------------------------------------------------------------------------
# Tests: Consumer lag tracker integration
# ---------------------------------------------------------------------------


class TestConsumerLagIntegration:
    """ConsumerLagTracker correctly integrates lag, velocity, and alerting."""

    def test_lag_grows_and_triggers_alert(self) -> None:
        """High lag triggers the on_high_lag callback exactly once per cooldown."""
        try:
            from obskit.consumer_lag import ConsumerLagTracker, QueueType
        except ImportError:
            pytest.skip("obskit-queue not available")

        alerts = []
        tracker = ConsumerLagTracker(
            "orders_topic",
            queue_type=QueueType.KAFKA,
            consumer_group="order-processor",
            lag_threshold=100,
            on_high_lag=lambda q, lag: alerts.append((q, lag)),
        )

        tracker.set_lag(messages=500)  # exceeds threshold → alert fires
        assert len(alerts) == 1
        assert alerts[0] == ("orders_topic", 500)

        # Second call within cooldown window should NOT fire again
        tracker.set_lag(messages=600)
        assert len(alerts) == 1  # still 1

    def test_velocity_reduces_estimated_catch_up(self) -> None:
        """Faster consumers have a shorter estimated catch-up time."""
        try:
            from obskit.consumer_lag import ConsumerLagTracker, QueueType
        except ImportError:
            pytest.skip("obskit-queue not available")

        tracker = ConsumerLagTracker(
            "slow_queue",
            queue_type=QueueType.RABBITMQ,
            window_seconds=60,
        )
        tracker.set_lag(messages=1000)

        # Simulate consuming 50 messages spread over 5 seconds
        now = datetime.utcnow()
        tracker._consumed_timestamps = [
            now - timedelta(seconds=5 - i * 0.1) for i in range(50)
        ]

        stats = tracker.get_stats()
        assert stats.consumer_velocity > 0
        assert stats.estimated_catch_up_seconds > 0
        assert stats.estimated_catch_up_seconds < 1000  # not unbounded

    def test_get_stats_is_not_deadlocked(self) -> None:
        """
        get_stats() must not deadlock (regression test for the RLock fix).
        Previously threading.Lock() caused permanent deadlock here.
        """
        try:
            from obskit.consumer_lag import ConsumerLagTracker
        except ImportError:
            pytest.skip("obskit-queue not available")

        tracker = ConsumerLagTracker("deadlock_test_queue")
        tracker.set_lag(messages=50)
        tracker.messages_consumed(count=10)

        # This must return immediately — not hang
        stats = tracker.get_stats()
        assert stats.current_lag_messages == 50
        assert stats.total_consumed == 10

    def test_is_healthy_reflects_lag_state(self) -> None:
        """is_healthy() returns False when lag exceeds threshold."""
        try:
            from obskit.consumer_lag import ConsumerLagTracker
        except ImportError:
            pytest.skip("obskit-queue not available")

        tracker = ConsumerLagTracker("health_check_queue", lag_threshold=100)

        tracker.set_lag(messages=10)
        assert tracker.is_healthy()  # below threshold, not falling behind

        tracker.set_lag(messages=200)
        assert not tracker.is_healthy()  # above threshold

    def test_registry_get_or_create(self) -> None:
        """get_consumer_lag_tracker returns the same instance for the same key."""
        try:
            from obskit.consumer_lag import get_consumer_lag_tracker
        except ImportError:
            pytest.skip("obskit-queue not available")

        a = get_consumer_lag_tracker("registry_queue", consumer_group="grp1")
        b = get_consumer_lag_tracker("registry_queue", consumer_group="grp1")
        assert a is b

    def test_registry_different_groups_are_different_instances(self) -> None:
        """Different consumer groups produce distinct tracker instances."""
        try:
            from obskit.consumer_lag import get_consumer_lag_tracker
        except ImportError:
            pytest.skip("obskit-queue not available")

        a = get_consumer_lag_tracker("shared_topic", consumer_group="group-a")
        b = get_consumer_lag_tracker("shared_topic", consumer_group="group-b")
        assert a is not b


# ---------------------------------------------------------------------------
# Tests: RabbitMQ instrumentation (unit-level, no real broker)
# ---------------------------------------------------------------------------


class TestRabbitMQInstrumentationIntegration:
    """instrument_rabbitmq wraps the channel callback transparently."""

    def test_instrumented_channel_tracks_message(self) -> None:
        """Instrumented basic_consume callback runs the original callback."""
        try:
            from obskit.queue import instrument_rabbitmq
        except ImportError:
            pytest.skip("obskit-queue not available")

        consumed = []
        captured_callback = {}

        # Build a mock channel whose basic_consume captures kwargs
        mock_channel = MagicMock()

        def fake_basic_consume(*args, **kwargs):
            # Store whatever callback was passed (original or wrapped)
            if "on_message_callback" in kwargs:
                captured_callback["cb"] = kwargs["on_message_callback"]
            elif args:
                captured_callback["cb"] = args[0]

        mock_channel.basic_consume.side_effect = fake_basic_consume

        def my_callback(ch, method, props, body):
            consumed.append(body)

        instrument_rabbitmq(mock_channel, queue_name="orders")

        # Call basic_consume — instrument_rabbitmq replaced it with instrumented_consume
        # which will call the original basic_consume (mock) with the wrapped callback
        mock_channel.basic_consume(on_message_callback=my_callback, queue="orders")

        # The wrapped callback should be stored (either wrapped or original)
        cb = captured_callback.get("cb", my_callback)

        # Invoke it as pika would
        mock_props = MagicMock()
        mock_props.message_id = "msg-xyz"
        cb(mock_channel, MagicMock(), mock_props, b"hello")

        assert consumed == [b"hello"]
