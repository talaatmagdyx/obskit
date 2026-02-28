"""
Tests for obskit.memory module.

Tests cover:
- MemoryStats, GCStats, ObjectStats dataclasses
- MemoryTracker: collect_memory, collect_gc, collect_objects, collect
- MemoryTracker: register_gc_callbacks, force_gc
- start_memory_tracking, stop_memory_tracking, get_memory_tracker
- _init_metrics lazy initialization
"""

import gc
import sys
import threading
import time
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from obskit.memory import (
    GCStats,
    MemoryStats,
    MemoryTracker,
    ObjectStats,
    get_memory_tracker,
    start_memory_tracking,
    stop_memory_tracking,
)


# =============================================================================
# MemoryStats dataclass
# =============================================================================


class TestMemoryStats:
    def test_default_values(self):
        stats = MemoryStats()
        assert stats.rss_bytes == 0
        assert stats.vms_bytes == 0
        assert stats.heap_bytes == 0
        assert stats.rss_mb == 0.0
        assert stats.vms_mb == 0.0
        assert stats.heap_mb == 0.0
        assert stats.percent == 0.0

    def test_to_dict(self):
        stats = MemoryStats(
            rss_bytes=1024 * 1024,
            vms_bytes=2 * 1024 * 1024,
            heap_bytes=512 * 1024,
            rss_mb=1.0,
            vms_mb=2.0,
            heap_mb=0.5,
            percent=5.5,
        )
        d = stats.to_dict()
        assert d["rss_bytes"] == 1024 * 1024
        assert d["vms_bytes"] == 2 * 1024 * 1024
        assert d["heap_bytes"] == 512 * 1024
        assert d["rss_mb"] == 1.0
        assert d["vms_mb"] == 2.0
        assert d["heap_mb"] == 0.5
        assert d["percent"] == 5.5
        assert "timestamp" in d

    def test_timestamp_auto_populated(self):
        before = datetime.utcnow()
        stats = MemoryStats()
        after = datetime.utcnow()
        assert before <= stats.timestamp <= after


# =============================================================================
# GCStats dataclass
# =============================================================================


class TestGCStats:
    def test_default_values(self):
        stats = GCStats()
        assert stats.collections == {}
        assert stats.collected == {}
        assert stats.uncollectable == 0
        assert stats.thresholds == (700, 10, 10)

    def test_to_dict(self):
        stats = GCStats(
            collections={0: 100, 1: 10, 2: 1},
            collected={0: 500, 1: 50, 2: 5},
            uncollectable=0,
        )
        d = stats.to_dict()
        assert d["collections"] == {0: 100, 1: 10, 2: 1}
        assert d["collected"] == {0: 500, 1: 50, 2: 5}
        assert d["uncollectable"] == 0
        assert "timestamp" in d


# =============================================================================
# ObjectStats dataclass
# =============================================================================


class TestObjectStats:
    def test_default_values(self):
        stats = ObjectStats()
        assert stats.total_objects == 0
        assert stats.by_type == {}
        assert stats.top_types == []

    def test_to_dict(self):
        stats = ObjectStats(
            total_objects=1000,
            by_type={"list": 200, "dict": 150},
            top_types=[("list", 200), ("dict", 150)],
        )
        d = stats.to_dict()
        assert d["total_objects"] == 1000
        assert d["by_type"]["list"] == 200
        assert "timestamp" in d


# =============================================================================
# MemoryTracker
# =============================================================================


class TestMemoryTrackerInit:
    def test_default_initialization(self):
        tracker = MemoryTracker()
        assert tracker.track_objects is False
        assert tracker.top_object_types == 10
        assert tracker._gc_callbacks_registered is False

    def test_custom_initialization(self):
        tracker = MemoryTracker(track_objects=True, top_object_types=5)
        assert tracker.track_objects is True
        assert tracker.top_object_types == 5


class TestMemoryTrackerCollectMemory:
    def test_collect_memory_returns_stats(self):
        tracker = MemoryTracker()
        stats = tracker.collect_memory()
        assert isinstance(stats, MemoryStats)

    def test_collect_memory_has_heap_bytes(self):
        tracker = MemoryTracker()
        stats = tracker.collect_memory()
        # heap_bytes is always collected via sys.getsizeof
        assert stats.heap_bytes >= 0
        assert stats.heap_mb >= 0.0

    @patch("obskit.memory.HAS_PSUTIL", True)
    def test_collect_memory_with_psutil(self):
        mock_process = MagicMock()
        mock_mem_info = MagicMock()
        mock_mem_info.rss = 100 * 1024 * 1024  # 100 MB
        mock_mem_info.vms = 200 * 1024 * 1024  # 200 MB
        mock_process.memory_info.return_value = mock_mem_info
        mock_process.memory_percent.return_value = 5.0

        with patch("obskit.memory.psutil") as mock_psutil:
            mock_psutil.Process.return_value = mock_process
            tracker = MemoryTracker()
            stats = tracker.collect_memory()

        assert stats.rss_bytes == 100 * 1024 * 1024
        assert stats.vms_bytes == 200 * 1024 * 1024
        assert stats.rss_mb == pytest.approx(100.0, rel=0.01)
        assert stats.vms_mb == pytest.approx(200.0, rel=0.01)
        assert stats.percent == 5.0

    @patch("obskit.memory.HAS_PSUTIL", False)
    def test_collect_memory_without_psutil(self):
        tracker = MemoryTracker()
        stats = tracker.collect_memory()
        # Without psutil, rss_bytes and vms_bytes stay at 0
        assert stats.rss_bytes == 0
        assert stats.vms_bytes == 0


class TestMemoryTrackerCollectGC:
    def test_collect_gc_returns_stats(self):
        tracker = MemoryTracker()
        stats = tracker.collect_gc()
        assert isinstance(stats, GCStats)

    def test_collect_gc_has_generations(self):
        tracker = MemoryTracker()
        stats = tracker.collect_gc()
        # Python has 3 GC generations
        assert 0 in stats.collections
        assert 1 in stats.collections
        assert 2 in stats.collections

    def test_collect_gc_uncollectable(self):
        tracker = MemoryTracker()
        stats = tracker.collect_gc()
        # gc.garbage should usually be empty
        assert stats.uncollectable >= 0

    def test_collect_gc_thresholds(self):
        tracker = MemoryTracker()
        stats = tracker.collect_gc()
        assert stats.thresholds == gc.get_threshold()


class TestMemoryTrackerCollectObjects:
    def test_collect_objects_when_disabled(self):
        tracker = MemoryTracker(track_objects=False)
        stats = tracker.collect_objects()
        assert isinstance(stats, ObjectStats)
        assert stats.total_objects == 0

    def test_collect_objects_when_enabled(self):
        tracker = MemoryTracker(track_objects=True, top_object_types=5)
        stats = tracker.collect_objects()
        assert stats.total_objects > 0
        assert len(stats.top_types) <= 5
        assert isinstance(stats.by_type, dict)


class TestMemoryTrackerCollect:
    def test_collect_returns_dict(self):
        tracker = MemoryTracker()
        result = tracker.collect()
        assert isinstance(result, dict)
        assert "memory" in result
        assert "gc" in result
        assert "objects" in result

    def test_collect_objects_key_is_none_when_disabled(self):
        tracker = MemoryTracker(track_objects=False)
        result = tracker.collect()
        assert result["objects"] is None

    def test_collect_objects_key_is_dict_when_enabled(self):
        tracker = MemoryTracker(track_objects=True)
        result = tracker.collect()
        assert result["objects"] is not None
        assert isinstance(result["objects"], dict)

    def test_collect_memory_is_dict(self):
        tracker = MemoryTracker()
        result = tracker.collect()
        assert isinstance(result["memory"], dict)
        assert "heap_bytes" in result["memory"]

    def test_collect_gc_is_dict(self):
        tracker = MemoryTracker()
        result = tracker.collect()
        assert isinstance(result["gc"], dict)
        assert "collections" in result["gc"]


class TestMemoryTrackerRegisterGCCallbacks:
    def test_register_once(self):
        tracker = MemoryTracker()
        assert tracker._gc_callbacks_registered is False
        tracker.register_gc_callbacks()
        assert tracker._gc_callbacks_registered is True

    def test_register_twice_no_duplicate(self):
        tracker = MemoryTracker()
        before_count = len(gc.callbacks)
        tracker.register_gc_callbacks()
        after_first = len(gc.callbacks)
        tracker.register_gc_callbacks()  # Second call should be no-op
        after_second = len(gc.callbacks)
        assert after_first == after_second
        # Cleanup: remove the callback we added
        if len(gc.callbacks) > before_count:
            gc.callbacks.pop()


class TestMemoryTrackerForceGC:
    def test_force_gc_returns_dict(self):
        tracker = MemoryTracker()
        result = tracker.force_gc()
        assert isinstance(result, dict)
        assert 0 in result
        assert 1 in result
        assert 2 in result

    def test_force_gc_returns_non_negative(self):
        tracker = MemoryTracker()
        result = tracker.force_gc()
        for gen, count in result.items():
            assert count >= 0


# =============================================================================
# Background tracking
# =============================================================================


class TestMemoryTracking:
    def setup_method(self):
        # Make sure tracking is stopped before each test
        stop_memory_tracking()
        import obskit.memory as module
        module._background_tracker = None

    def teardown_method(self):
        stop_memory_tracking()

    def test_start_tracking_creates_thread(self):
        import obskit.memory as module
        start_memory_tracking(interval_seconds=100.0)
        assert module._background_tracker is not None
        assert module._background_tracker.is_alive()

    def test_start_tracking_second_call_is_noop(self):
        import obskit.memory as module
        start_memory_tracking(interval_seconds=100.0)
        first_thread = module._background_tracker
        start_memory_tracking(interval_seconds=100.0)
        # Should be the same thread
        assert module._background_tracker is first_thread

    def test_stop_tracking(self):
        import obskit.memory as module
        start_memory_tracking(interval_seconds=100.0)
        stop_memory_tracking()
        # Wait a moment for thread to stop
        time.sleep(0.1)
        # Thread should be done or stopping
        assert module._stop_tracking.is_set()

    def test_start_with_callback(self):
        callback_called = threading.Event()

        def on_high_memory(stats):
            callback_called.set()

        # Mock memory to return high percent
        with patch("obskit.memory.HAS_PSUTIL", True):
            with patch("obskit.memory.psutil") as mock_psutil:
                mock_process = MagicMock()
                mock_mem = MagicMock()
                mock_mem.rss = 100
                mock_mem.vms = 200
                mock_process.memory_info.return_value = mock_mem
                mock_process.memory_percent.return_value = 95.0  # > threshold
                mock_psutil.Process.return_value = mock_process

                start_memory_tracking(
                    interval_seconds=0.05,
                    on_high_memory=on_high_memory,
                    high_memory_threshold_percent=90.0,
                )
                callback_called.wait(timeout=1.0)

        stop_memory_tracking()
        assert callback_called.is_set()


# =============================================================================
# get_memory_tracker factory
# =============================================================================


class TestGetMemoryTracker:
    def test_returns_memory_tracker_instance(self):
        tracker = get_memory_tracker()
        assert isinstance(tracker, MemoryTracker)

    def test_returns_new_instance_each_time(self):
        t1 = get_memory_tracker()
        t2 = get_memory_tracker()
        # Each call creates new instance
        assert t1 is not t2


# =============================================================================
# _init_metrics
# =============================================================================


class TestInitMetrics:
    def test_init_metrics_sets_flag(self):
        from obskit.memory import _init_metrics
        import obskit.memory as module
        # After calling, should be marked initialized
        _init_metrics()
        assert module._metrics_initialized is True

    def test_init_metrics_idempotent(self):
        from obskit.memory import _init_metrics
        # Should not raise even if called multiple times
        _init_metrics()
        _init_metrics()
