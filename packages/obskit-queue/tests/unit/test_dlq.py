"""
Tests for obskit.dlq module.

Tests cover:
- DLQReason enum
- DLQMessage and DLQStats dataclasses
- DLQTracker: track_message_sent, track_processing, track_message_removed
- DLQTracker: set_dlq_size, set_oldest_message_age, get_stats, get_messages
- DLQTracker: alert threshold callback
- Registry helpers: get_dlq_tracker, get_all_dlq_stats
"""

import time
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from obskit.dlq import (
    DLQMessage,
    DLQReason,
    DLQStats,
    DLQTracker,
    get_all_dlq_stats,
    get_dlq_tracker,
)


# =============================================================================
# DLQReason enum
# =============================================================================


class TestDLQReason:
    def test_all_reasons_exist(self):
        assert DLQReason.MAX_RETRIES.value == "max_retries_exceeded"
        assert DLQReason.PARSE_ERROR.value == "parse_error"
        assert DLQReason.VALIDATION_ERROR.value == "validation_error"
        assert DLQReason.HANDLER_ERROR.value == "handler_error"
        assert DLQReason.TIMEOUT.value == "timeout"
        assert DLQReason.REJECTED.value == "rejected"
        assert DLQReason.EXPIRED.value == "expired"
        assert DLQReason.UNKNOWN.value == "unknown"

    def test_enum_count(self):
        assert len(list(DLQReason)) == 8


# =============================================================================
# DLQMessage dataclass
# =============================================================================


class TestDLQMessage:
    def test_creation_with_required_fields(self):
        msg = DLQMessage(
            message_id="msg-1",
            original_queue="orders",
            reason="max_retries_exceeded",
        )
        assert msg.message_id == "msg-1"
        assert msg.original_queue == "orders"
        assert msg.reason == "max_retries_exceeded"
        assert msg.age_seconds == 0.0
        assert msg.retry_count == 0
        assert msg.error_message is None
        assert msg.metadata == {}

    def test_creation_with_all_fields(self):
        msg = DLQMessage(
            message_id="msg-2",
            original_queue="payments",
            reason="parse_error",
            age_seconds=120.5,
            retry_count=3,
            error_message="Invalid JSON",
            metadata={"key": "value"},
        )
        assert msg.age_seconds == 120.5
        assert msg.retry_count == 3
        assert msg.error_message == "Invalid JSON"
        assert msg.metadata == {"key": "value"}

    def test_to_dict(self):
        msg = DLQMessage(
            message_id="msg-3",
            original_queue="events",
            reason="handler_error",
            age_seconds=60.0,
            retry_count=2,
            error_message="DB error",
        )
        d = msg.to_dict()
        assert d["message_id"] == "msg-3"
        assert d["original_queue"] == "events"
        assert d["reason"] == "handler_error"
        assert d["age_seconds"] == 60.0
        assert d["retry_count"] == 2
        assert d["error_message"] == "DB error"
        assert "timestamp" in d
        assert "metadata" in d

    def test_timestamp_auto_populated(self):
        before = datetime.utcnow()
        msg = DLQMessage(message_id="msg-ts", original_queue="q", reason="r")
        after = datetime.utcnow()
        assert before <= msg.timestamp <= after


# =============================================================================
# DLQStats dataclass
# =============================================================================


class TestDLQStats:
    def test_default_values(self):
        stats = DLQStats(dlq_name="orders_dlq")
        assert stats.total_messages == 0
        assert stats.current_size == 0
        assert stats.oldest_message_age_seconds == 0.0
        assert stats.messages_by_reason == {}
        assert stats.messages_by_queue == {}
        assert stats.processing_success_rate == 1.0
        assert stats.avg_processing_time_seconds == 0.0

    def test_to_dict(self):
        stats = DLQStats(
            dlq_name="orders_dlq",
            total_messages=10,
            current_size=5,
            oldest_message_age_seconds=300.0,
            messages_by_reason={"parse_error": 3, "timeout": 2},
            messages_by_queue={"orders": 5},
            processing_success_rate=0.8,
            avg_processing_time_seconds=1.5,
        )
        d = stats.to_dict()
        assert d["dlq_name"] == "orders_dlq"
        assert d["total_messages"] == 10
        assert d["current_size"] == 5
        assert d["oldest_message_age_seconds"] == 300.0
        assert d["messages_by_reason"] == {"parse_error": 3, "timeout": 2}
        assert d["processing_success_rate"] == 0.8


# =============================================================================
# DLQTracker initialization
# =============================================================================


class TestDLQTrackerInit:
    def test_default_initialization(self):
        tracker = DLQTracker("orders_dlq")
        assert tracker.dlq_name == "orders_dlq"
        assert tracker.alert_threshold == 100
        assert tracker.on_threshold_exceeded is None
        assert tracker._total_messages == 0
        assert tracker._processing_success == 0
        assert tracker._processing_failure == 0

    def test_custom_initialization(self):
        callback = MagicMock()
        tracker = DLQTracker(
            "payments_dlq",
            alert_threshold=50,
            on_threshold_exceeded=callback,
        )
        assert tracker.alert_threshold == 50
        assert tracker.on_threshold_exceeded is callback


# =============================================================================
# DLQTracker track_message_sent
# =============================================================================


class TestDLQTrackerTrackMessageSent:
    def test_track_message_increments_total(self):
        tracker = DLQTracker("dlq_track_total")
        tracker.track_message_sent(original_queue="orders", reason="parse_error")
        assert tracker._total_messages == 1

    def test_track_message_adds_to_messages_dict(self):
        tracker = DLQTracker("dlq_track_dict")
        tracker.track_message_sent(
            original_queue="payments",
            reason="max_retries_exceeded",
            message_id="msg-100",
        )
        assert "msg-100" in tracker._messages

    def test_track_message_without_explicit_id(self):
        tracker = DLQTracker("dlq_track_auto_id")
        tracker.track_message_sent(original_queue="events", reason="timeout")
        assert tracker._total_messages == 1
        assert len(tracker._messages) == 1

    def test_track_multiple_messages(self):
        tracker = DLQTracker("dlq_track_multiple")
        for i in range(5):
            tracker.track_message_sent(
                original_queue="orders",
                reason="parse_error",
                message_id=f"msg-{i}",
            )
        assert tracker._total_messages == 5
        assert len(tracker._messages) == 5

    def test_track_message_with_age_and_retry(self):
        tracker = DLQTracker("dlq_track_age_retry")
        tracker.track_message_sent(
            original_queue="orders",
            reason="handler_error",
            message_id="msg-age",
            message_age_seconds=300.0,
            retry_count=3,
        )
        msg = tracker._messages["msg-age"]
        assert msg.age_seconds == 300.0
        assert msg.retry_count == 3

    def test_track_message_with_error_message(self):
        tracker = DLQTracker("dlq_track_error_msg")
        tracker.track_message_sent(
            original_queue="orders",
            reason="handler_error",
            message_id="msg-err",
            error_message="Something went wrong",
        )
        msg = tracker._messages["msg-err"]
        assert msg.error_message == "Something went wrong"

    def test_track_message_with_metadata(self):
        tracker = DLQTracker("dlq_track_metadata")
        tracker.track_message_sent(
            original_queue="orders",
            reason="handler_error",
            message_id="msg-meta",
            service="order-service",
            version="1.0",
        )
        msg = tracker._messages["msg-meta"]
        assert msg.metadata.get("service") == "order-service"
        assert msg.metadata.get("version") == "1.0"

    def test_threshold_exceeded_calls_callback(self):
        callback = MagicMock()
        tracker = DLQTracker("dlq_threshold", alert_threshold=2, on_threshold_exceeded=callback)
        tracker.track_message_sent(original_queue="q", reason="r", message_id="m1")
        tracker.track_message_sent(original_queue="q", reason="r", message_id="m2")
        callback.assert_called()

    def test_threshold_not_exceeded_no_callback(self):
        callback = MagicMock()
        tracker = DLQTracker("dlq_no_threshold", alert_threshold=10, on_threshold_exceeded=callback)
        tracker.track_message_sent(original_queue="q", reason="r", message_id="m1")
        callback.assert_not_called()

    def test_threshold_exceeded_no_callback_no_error(self):
        tracker = DLQTracker("dlq_threshold_no_cb", alert_threshold=1)
        tracker.track_message_sent(original_queue="q", reason="r", message_id="m1")
        # Should not raise


# =============================================================================
# DLQTracker track_processing
# =============================================================================


class TestDLQTrackerTrackProcessing:
    def test_successful_processing_increments_success(self):
        tracker = DLQTracker("dlq_proc_success")
        tracker.track_message_sent(
            original_queue="orders", reason="parse_error", message_id="msg-proc"
        )
        with tracker.track_processing("msg-proc"):
            pass  # Successful processing
        assert tracker._processing_success == 1
        assert tracker._processing_failure == 0

    def test_failed_processing_increments_failure(self):
        tracker = DLQTracker("dlq_proc_failure")
        tracker.track_message_sent(
            original_queue="orders", reason="parse_error", message_id="msg-proc-fail"
        )
        with pytest.raises(ValueError):
            with tracker.track_processing("msg-proc-fail"):
                raise ValueError("Processing failed")
        assert tracker._processing_failure == 1
        assert tracker._processing_success == 0

    def test_successful_processing_removes_from_messages(self):
        tracker = DLQTracker("dlq_proc_remove")
        tracker.track_message_sent(
            original_queue="orders", reason="parse_error", message_id="msg-remove"
        )
        assert "msg-remove" in tracker._messages
        with tracker.track_processing("msg-remove"):
            pass
        assert "msg-remove" not in tracker._messages

    def test_failed_processing_keeps_message(self):
        tracker = DLQTracker("dlq_proc_keep")
        tracker.track_message_sent(
            original_queue="orders", reason="parse_error", message_id="msg-keep"
        )
        with pytest.raises(RuntimeError):
            with tracker.track_processing("msg-keep"):
                raise RuntimeError("Keep me")
        # Message should still be in the dict after failure
        assert "msg-keep" in tracker._messages

    def test_processing_records_time(self):
        tracker = DLQTracker("dlq_proc_time")
        with tracker.track_processing("some-msg"):
            pass
        assert len(tracker._processing_times) == 1
        assert tracker._processing_times[0] >= 0.0

    def test_processing_times_capped_at_1000(self):
        tracker = DLQTracker("dlq_proc_cap")
        # Fill up to over 1000
        tracker._processing_times = [0.1] * 1001
        with tracker.track_processing("msg-cap"):
            pass
        # Should be trimmed back
        assert len(tracker._processing_times) <= 1001

    def test_processing_unknown_message_no_error(self):
        tracker = DLQTracker("dlq_proc_unknown")
        # Processing a message_id that doesn't exist in _messages
        with tracker.track_processing("nonexistent-msg"):
            pass
        assert tracker._processing_success == 1


# =============================================================================
# DLQTracker track_message_removed
# =============================================================================


class TestDLQTrackerTrackMessageRemoved:
    def test_removes_existing_message(self):
        tracker = DLQTracker("dlq_remove_existing")
        tracker.track_message_sent(
            original_queue="orders", reason="parse_error", message_id="msg-del"
        )
        assert "msg-del" in tracker._messages
        tracker.track_message_removed("msg-del")
        assert "msg-del" not in tracker._messages

    def test_removing_nonexistent_message_no_error(self):
        tracker = DLQTracker("dlq_remove_nonexistent")
        # Should not raise
        tracker.track_message_removed("does-not-exist")

    def test_remove_with_reason(self):
        tracker = DLQTracker("dlq_remove_reason")
        tracker.track_message_sent(
            original_queue="orders", reason="timeout", message_id="msg-reason"
        )
        tracker.track_message_removed("msg-reason", reason="expired")
        assert "msg-reason" not in tracker._messages


# =============================================================================
# DLQTracker set_dlq_size and set_oldest_message_age
# =============================================================================


class TestDLQTrackerManualSetters:
    def test_set_dlq_size(self):
        tracker = DLQTracker("dlq_set_size")
        # Should not raise
        tracker.set_dlq_size(42)

    def test_set_oldest_message_age(self):
        tracker = DLQTracker("dlq_set_age")
        # Should not raise
        tracker.set_oldest_message_age(3600.0)


# =============================================================================
# DLQTracker get_stats
# =============================================================================


class TestDLQTrackerGetStats:
    def test_get_stats_empty(self):
        tracker = DLQTracker("dlq_stats_empty")
        stats = tracker.get_stats()
        assert isinstance(stats, DLQStats)
        assert stats.total_messages == 0
        assert stats.current_size == 0
        assert stats.processing_success_rate == 1.0

    def test_get_stats_with_messages(self):
        tracker = DLQTracker("dlq_stats_with_msgs")
        tracker.track_message_sent(
            original_queue="orders", reason="parse_error", message_id="s-1"
        )
        tracker.track_message_sent(
            original_queue="orders", reason="timeout", message_id="s-2"
        )
        tracker.track_message_sent(
            original_queue="payments", reason="parse_error", message_id="s-3"
        )
        stats = tracker.get_stats()
        assert stats.total_messages == 3
        assert stats.current_size == 3
        assert stats.messages_by_reason.get("parse_error") == 2
        assert stats.messages_by_reason.get("timeout") == 1
        assert stats.messages_by_queue.get("orders") == 2
        assert stats.messages_by_queue.get("payments") == 1

    def test_get_stats_success_rate_all_success(self):
        tracker = DLQTracker("dlq_stats_success_rate")
        tracker.track_message_sent(original_queue="q", reason="r", message_id="m1")
        with tracker.track_processing("m1"):
            pass
        stats = tracker.get_stats()
        assert stats.processing_success_rate == 1.0

    def test_get_stats_success_rate_all_failure(self):
        tracker = DLQTracker("dlq_stats_failure_rate")
        tracker.track_message_sent(original_queue="q", reason="r", message_id="m1")
        with pytest.raises(Exception):
            with tracker.track_processing("m1"):
                raise Exception("fail")
        stats = tracker.get_stats()
        assert stats.processing_success_rate == 0.0

    def test_get_stats_mixed_success_failure(self):
        tracker = DLQTracker("dlq_stats_mixed_rate")
        tracker.track_message_sent(original_queue="q", reason="r", message_id="m1")
        tracker.track_message_sent(original_queue="q", reason="r", message_id="m2")
        tracker.track_message_sent(original_queue="q", reason="r", message_id="m3")

        with tracker.track_processing("m1"):
            pass
        with tracker.track_processing("m2"):
            pass
        with pytest.raises(Exception):
            with tracker.track_processing("m3"):
                raise Exception("fail")

        stats = tracker.get_stats()
        assert abs(stats.processing_success_rate - (2 / 3)) < 0.01

    def test_get_stats_avg_processing_time(self):
        tracker = DLQTracker("dlq_stats_avg_time")
        tracker._processing_times = [0.1, 0.2, 0.3]
        stats = tracker.get_stats()
        assert abs(stats.avg_processing_time_seconds - 0.2) < 0.01

    def test_get_stats_oldest_message_age(self):
        tracker = DLQTracker("dlq_stats_oldest")
        tracker.track_message_sent(original_queue="q", reason="r", message_id="m1")
        stats = tracker.get_stats()
        # Age should be >= 0
        assert stats.oldest_message_age_seconds >= 0.0

    def test_get_stats_dlq_name(self):
        tracker = DLQTracker("my_dlq_name")
        stats = tracker.get_stats()
        assert stats.dlq_name == "my_dlq_name"


# =============================================================================
# DLQTracker get_messages
# =============================================================================


class TestDLQTrackerGetMessages:
    def test_get_messages_empty(self):
        tracker = DLQTracker("dlq_getmsgs_empty")
        msgs = tracker.get_messages()
        assert msgs == []

    def test_get_messages_returns_all(self):
        tracker = DLQTracker("dlq_getmsgs_all")
        for i in range(5):
            tracker.track_message_sent(
                original_queue="q", reason="r", message_id=f"msg-{i}"
            )
        msgs = tracker.get_messages()
        assert len(msgs) == 5

    def test_get_messages_limit(self):
        tracker = DLQTracker("dlq_getmsgs_limit")
        for i in range(10):
            tracker.track_message_sent(
                original_queue="q", reason="r", message_id=f"msg-lim-{i}"
            )
        msgs = tracker.get_messages(limit=3)
        assert len(msgs) == 3

    def test_get_messages_sorted_by_timestamp(self):
        tracker = DLQTracker("dlq_getmsgs_sorted")
        tracker.track_message_sent(original_queue="q", reason="r", message_id="m-a")
        tracker.track_message_sent(original_queue="q", reason="r", message_id="m-b")
        msgs = tracker.get_messages()
        # Should be sorted by timestamp (ascending)
        for i in range(len(msgs) - 1):
            assert msgs[i].timestamp <= msgs[i + 1].timestamp

    def test_get_messages_default_limit_100(self):
        tracker = DLQTracker("dlq_getmsgs_default")
        for i in range(150):
            tracker.track_message_sent(
                original_queue="q", reason="r", message_id=f"msg-{i}"
            )
        msgs = tracker.get_messages()  # default limit=100
        assert len(msgs) == 100


# =============================================================================
# DLQTracker _update_oldest_age
# =============================================================================


class TestDLQTrackerUpdateOldestAge:
    def test_update_oldest_age_empty(self):
        tracker = DLQTracker("dlq_oldest_empty")
        # Should not raise with empty messages dict
        tracker._update_oldest_age()

    def test_update_oldest_age_with_messages(self):
        tracker = DLQTracker("dlq_oldest_msgs")
        tracker.track_message_sent(original_queue="q", reason="r", message_id="m1")
        # Should not raise
        tracker._update_oldest_age()


# =============================================================================
# Registry helpers
# =============================================================================


class TestDLQRegistryHelpers:
    def setup_method(self):
        """Clear the module-level registry before each test."""
        import obskit.dlq as module
        module._dlq_trackers.clear()

    def test_get_dlq_tracker_creates_new(self):
        tracker = get_dlq_tracker("orders_dlq_reg")
        assert tracker is not None
        assert tracker.dlq_name == "orders_dlq_reg"

    def test_get_dlq_tracker_returns_same_instance(self):
        t1 = get_dlq_tracker("payments_dlq_reg")
        t2 = get_dlq_tracker("payments_dlq_reg")
        assert t1 is t2

    def test_get_dlq_tracker_different_names(self):
        t1 = get_dlq_tracker("dlq_reg_a")
        t2 = get_dlq_tracker("dlq_reg_b")
        assert t1 is not t2

    def test_get_all_dlq_stats_empty(self):
        stats = get_all_dlq_stats()
        assert isinstance(stats, dict)
        assert len(stats) == 0

    def test_get_all_dlq_stats_with_trackers(self):
        get_dlq_tracker("dlq_all_1")
        get_dlq_tracker("dlq_all_2")
        stats = get_all_dlq_stats()
        assert len(stats) == 2
        for key, val in stats.items():
            assert isinstance(val, DLQStats)

    def test_get_dlq_tracker_with_custom_threshold(self):
        tracker = get_dlq_tracker("dlq_custom_thresh", alert_threshold=50)
        assert tracker.alert_threshold == 50


class TestGetDlqTrackerDoubleLock:
    """Cover dlq.py:417->420 — inner double-check locking branch."""

    def test_inner_lock_already_set(self):
        import obskit.dlq as dlq_mod
        from obskit.dlq import DLQTracker

        saved = dict(dlq_mod._dlq_trackers)
        saved_lock = dlq_mod._dlq_lock
        dlq_mod._dlq_trackers.clear()

        sentinel = DLQTracker("race_dlq")
        key = "race_dlq"

        class _RaceLock:
            def __enter__(self):
                dlq_mod._dlq_trackers[key] = sentinel
                return self
            def __exit__(self, *a):
                pass

        dlq_mod._dlq_lock = _RaceLock()
        try:
            result = dlq_mod.get_dlq_tracker("race_dlq")
            assert result is sentinel
        finally:
            dlq_mod._dlq_trackers.clear()
            dlq_mod._dlq_trackers.update(saved)
            dlq_mod._dlq_lock = saved_lock
