"""Tests for obskit.db.tracker module."""

import time
import uuid
from unittest.mock import patch

import pytest

from obskit.db.tracker import DatabaseTracker, track_query


class TestDatabaseTracker:
    """Tests for DatabaseTracker class."""

    def test_init(self):
        """Test DatabaseTracker initialization."""
        tracker = DatabaseTracker(database_name="test_db")
        assert tracker is not None
        assert tracker.database_name == "test_db"

    def test_track_query_context(self):
        """Test track_query context manager."""
        tracker = DatabaseTracker(database_name=f"test_{uuid.uuid4().hex[:8]}")

        with tracker.track_query(operation="SELECT"):
            pass  # Simulated query

    def test_track_query_with_error(self):
        """Test track_query records errors."""
        tracker = DatabaseTracker(database_name=f"test_{uuid.uuid4().hex[:8]}")

        with pytest.raises(ValueError):
            with tracker.track_query(operation="INSERT"):
                raise ValueError("Query failed")

    @patch("obskit.db.tracker.logger")
    def test_track_slow_query(self, mock_logger):
        """Test slow query detection (covers line 97)."""
        tracker = DatabaseTracker(database_name=f"test_{uuid.uuid4().hex[:8]}")

        # Use a very low threshold to trigger slow query detection
        with tracker.track_query(
            operation="SELECT",
            query="SELECT * FROM large_table",
            slow_query_threshold_ms=0.001,  # Very low threshold
        ):
            time.sleep(0.01)  # Sleep to exceed threshold

        # Check that slow query warning was logged
        mock_logger.warning.assert_called()
        call_args = mock_logger.warning.call_args
        assert call_args[0][0] == "slow_query_detected"

    @patch("obskit.db.tracker.logger")
    def test_track_fast_query_no_warning(self, mock_logger):
        """Test fast query does not trigger warning."""
        tracker = DatabaseTracker(database_name=f"test_{uuid.uuid4().hex[:8]}")

        # Use a high threshold so it won't trigger
        with tracker.track_query(
            operation="SELECT",
            query="SELECT 1",
            slow_query_threshold_ms=10000,  # High threshold
        ):
            pass  # Fast query

        # Check that debug was called, not warning
        mock_logger.debug.assert_called()


class TestTrackQueryDecorator:
    """Tests for track_query decorator function."""

    def test_track_query_function(self):
        """Test track_query as context manager function."""
        with track_query(operation="SELECT", database_name="test"):
            pass  # Simulated query

    def test_track_query_with_query(self):
        """Test track_query with query string."""
        with track_query(operation="SELECT", database_name="test", query="SELECT * FROM users"):
            pass

    def test_track_query_with_threshold(self):
        """Test track_query with slow query threshold."""
        with track_query(operation="UPDATE", database_name="test", slow_query_threshold_ms=5000.0):
            pass
