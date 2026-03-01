"""Unit tests for Hot Path Detector."""

import time

from obskit.hot_path import (
    HotPathDetector,
    PathStats,
    get_hot_path_detector,
    track_path,
)
import pytest


class TestHotPathDetector:
    """Tests for HotPathDetector."""

    def test_track_basic(self):
        """Test basic path tracking."""
        detector = HotPathDetector()

        with detector.track("test-path"):
            time.sleep(0.01)

        stats = detector.get_path_stats("test-path")
        assert stats is not None
        assert stats.call_count == 1
        assert stats.total_time_ms > 0

    def test_track_multiple_calls(self):
        """Test multiple calls to same path."""
        detector = HotPathDetector()

        for _ in range(5):
            with detector.track("multi-call"):
                time.sleep(0.01)

        stats = detector.get_path_stats("multi-call")
        assert stats.call_count == 5

    def test_track_with_error(self):
        """Test tracking with errors."""
        detector = HotPathDetector()

        try:
            with detector.track("error-path"):
                raise ValueError("Test error")
        except ValueError:
            pass  # Expected exception - testing error tracking

        stats = detector.get_path_stats("error-path")
        assert stats.error_count == 1

    def test_nested_tracking(self):
        """Test nested path tracking."""
        detector = HotPathDetector()

        with detector.track("outer"):
            with detector.track("inner"):
                time.sleep(0.01)

        inner_stats = detector.get_path_stats("inner")
        assert inner_stats is not None
        # Inner path should have outer as caller
        assert "outer" in inner_stats.callers

    def test_get_hot_paths(self):
        """Test getting hot paths."""
        detector = HotPathDetector(hot_path_threshold=5)

        # Cold path (not enough calls)
        for _ in range(3):
            with detector.track("cold"):
                pass  # NOSONAR

        # Hot path
        for _ in range(10):
            with detector.track("hot"):
                time.sleep(0.001)

        hot_paths = detector.get_hot_paths()

        assert len(hot_paths) >= 1
        hot_names = [p.path for p in hot_paths]
        assert "hot" in hot_names

    def test_impact_score(self):
        """Test impact score calculation."""
        detector = HotPathDetector()

        for _ in range(100):
            with detector.track("high-impact"):
                time.sleep(0.001)

        stats = detector.get_path_stats("high-impact")
        assert stats.impact_score > 0

    def test_record_manual(self):
        """Test manual recording."""
        detector = HotPathDetector()

        detector.record(
            path="manual-path",
            duration_ms=50.0,
            has_error=False,
            caller="test-caller",
        )

        stats = detector.get_path_stats("manual-path")
        assert stats.call_count == 1
        assert stats.total_time_ms == pytest.approx(50.0)

    def test_get_call_graph(self):
        """Test call graph generation."""
        detector = HotPathDetector()

        with detector.track("parent"):
            with detector.track("child"):
                pass  # NOSONAR

        graph = detector.get_call_graph()

        assert "child" in graph
        assert "parent" in graph["child"]

    def test_get_summary(self):
        """Test summary generation."""
        detector = HotPathDetector()

        with detector.track("path1"):
            pass  # NOSONAR
        with detector.track("path2"):
            pass  # NOSONAR

        summary = detector.get_summary()

        assert summary["total_paths"] == 2
        assert summary["total_calls"] == 2

    def test_clear(self):
        """Test clearing statistics."""
        detector = HotPathDetector()

        with detector.track("to-clear"):
            pass  # NOSONAR

        detector.clear()

        stats = detector.get_path_stats("to-clear")
        assert stats is None


class TestPathStats:
    """Tests for PathStats."""

    def test_avg_time_ms(self):
        """Test average time calculation."""
        stats = PathStats(
            path="test",
            call_count=10,
            total_time_ms=1000.0,
        )

        assert stats.avg_time_ms == pytest.approx(100.0)

    def test_error_rate(self):
        """Test error rate calculation."""
        stats = PathStats(
            path="test",
            call_count=100,
            error_count=25,
        )

        assert stats.error_rate == pytest.approx(0.25)

    def test_to_dict(self):
        """Test PathStats serialization."""
        stats = PathStats(
            path="test",
            call_count=50,
            total_time_ms=500.0,
        )

        data = stats.to_dict()
        assert data["path"] == "test"
        assert data["avg_time_ms"] == pytest.approx(10.0)


class TestTrackPathDecorator:
    """Tests for track_path decorator."""

    def test_decorator(self):
        """Test decorator functionality."""
        detector = HotPathDetector()

        @track_path("decorated-function", detector=detector)
        def my_function():
            return 42

        result = my_function()
        assert result == 42

        stats = detector.get_path_stats("decorated-function")
        assert stats.call_count == 1


class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_hot_path_detector(self):
        """Test global detector singleton."""
        detector1 = get_hot_path_detector()
        detector2 = get_hot_path_detector()
        assert detector1 is detector2
