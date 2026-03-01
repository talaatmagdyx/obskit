"""Tests for obskit.queue.tracker module."""

import uuid

import pytest

from obskit.queue.tracker import QueueTracker, track_message_processing


class TestQueueTracker:
    """Tests for QueueTracker class."""

    def test_init(self):
        """Test QueueTracker initialization."""
        tracker = QueueTracker(queue_name="test_queue")
        assert isinstance(tracker, QueueTracker)

    def test_track_message_processing_context(self):
        """Test track_message_processing context manager."""
        tracker = QueueTracker(queue_name=f"test_{uuid.uuid4().hex[:8]}")

        with tracker.track_message_processing(operation="process"):
            pass  # Simulated processing

    def test_track_message_with_error(self):
        """Test tracking with error."""
        tracker = QueueTracker(queue_name=f"test_{uuid.uuid4().hex[:8]}")

        with pytest.raises(ValueError):
            with tracker.track_message_processing(operation="process"):
                raise ValueError("Processing failed")

    def test_set_queue_depth(self):
        """Test setting queue depth."""
        tracker = QueueTracker(queue_name=f"test_{uuid.uuid4().hex[:8]}")
        tracker.set_queue_depth(10)


class TestTrackMessageProcessingFunction:
    """Tests for track_message_processing function."""

    def test_track_message_processing(self):
        """Test track_message_processing as context manager."""
        with track_message_processing(operation="consume", queue_name="test"):
            pass  # Simulated processing

    def test_track_with_error(self):
        """Test track with error."""
        with pytest.raises(ValueError):
            with track_message_processing(operation="consume", queue_name="test"):
                raise ValueError("Error")
