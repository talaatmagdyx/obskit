"""
Tests for obskit.shedding module — LoadShedder.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from obskit.shedding import (
    LoadShedder,
    Priority,
    SheddingConfig,
    SheddingStats,
    get_load_shedder,
)


# =============================================================================
# Priority Tests
# =============================================================================


class TestPriority:
    def test_critical_is_highest(self):
        assert Priority.CRITICAL > Priority.HIGH
        assert Priority.HIGH > Priority.NORMAL
        assert Priority.NORMAL > Priority.LOW
        assert Priority.LOW > Priority.BACKGROUND

    def test_critical_value(self):
        assert Priority.CRITICAL == 100

    def test_background_value(self):
        assert Priority.BACKGROUND == 0


# =============================================================================
# SheddingConfig Tests
# =============================================================================


class TestSheddingConfig:
    def test_defaults(self):
        config = SheddingConfig()
        assert config.max_queue_size == 1000
        assert config.max_latency_ms == 500
        assert config.min_shed_rate == 0.0
        assert config.max_shed_rate == 0.9

    def test_priority_weights_present(self):
        config = SheddingConfig()
        assert Priority.CRITICAL in config.priority_weights
        assert config.priority_weights[Priority.CRITICAL] == 0.0


# =============================================================================
# SheddingStats Tests
# =============================================================================


class TestSheddingStats:
    def test_to_dict(self):
        stats = SheddingStats(
            shedder_name="test",
            current_shed_rate=0.5,
            current_queue_size=100,
            current_latency_ms=250.0,
            load_level=0.7,
            requests_processed=500,
            requests_shed=50,
            shed_by_priority={"LOW": 30, "BACKGROUND": 20},
        )
        d = stats.to_dict()
        assert d["shedder_name"] == "test"
        assert d["current_shed_rate"] == 0.5
        assert d["requests_processed"] == 500
        assert isinstance(d["timestamp"], str)


# =============================================================================
# LoadShedder Tests
# =============================================================================


class TestLoadShedder:
    def test_init_defaults(self):
        shedder = LoadShedder()
        assert shedder.name == "default"
        assert shedder.config.max_queue_size == 1000
        assert shedder._current_shed_rate == 0.0

    def test_init_custom(self):
        shedder = LoadShedder(
            name="custom",
            max_queue_size=500,
            max_latency_ms=200,
            shed_percentage=0.2,
            adaptive=False,
        )
        assert shedder.name == "custom"
        assert shedder.base_shed_rate == 0.2
        assert shedder.adaptive is False

    def test_critical_priority_never_shed(self):
        shedder = LoadShedder(name="test_critical")
        shedder.force_shed_rate(0.99)  # Max shedding
        # Critical should always pass
        results = [shedder.should_process(Priority.CRITICAL) for _ in range(100)]
        assert all(results)

    def test_background_priority_shed_when_high_rate(self):
        shedder = LoadShedder(name="test_bg", adaptive=False)
        shedder.force_shed_rate(1.0)  # 100% shed rate
        # Background priority weight is 0.95, so effective rate is 0.95
        results = [shedder.should_process(Priority.BACKGROUND) for _ in range(50)]
        # With effective rate 0.95, most should be shed
        shed_count = results.count(False)
        assert shed_count > 30  # At least 60% shed

    def test_should_process_no_shedding(self):
        shedder = LoadShedder(name="test_no_shed", adaptive=False)
        shedder.force_shed_rate(0.0)
        result = shedder.should_process(Priority.NORMAL)
        assert result is True

    def test_should_process_with_queue_size(self):
        shedder = LoadShedder(name="test_qs", adaptive=False)
        shedder.force_shed_rate(0.0)
        result = shedder.should_process(Priority.NORMAL, queue_size=100)
        assert result is True
        assert shedder._current_queue_size == 100

    def test_should_process_with_latency(self):
        shedder = LoadShedder(name="test_lat", adaptive=False)
        shedder.force_shed_rate(0.0)
        result = shedder.should_process(Priority.NORMAL, latency_ms=200.0)
        assert result is True
        assert shedder._current_latency_ms == 200.0

    def test_on_shed_callback(self):
        shed_events = []
        shedder = LoadShedder(name="test_cb", adaptive=False, on_shed=shed_events.append)
        shedder.force_shed_rate(1.0)

        # Force shedding by using BACKGROUND priority (weight=0.95)
        # With 100% shed rate and BACKGROUND weight, should shed
        for _ in range(20):
            shedder.should_process(Priority.BACKGROUND)

        assert len(shed_events) > 0

    def test_set_queue_size(self):
        shedder = LoadShedder(name="test_sq")
        shedder.set_queue_size(500)
        assert shedder._current_queue_size == 500

    def test_record_latency(self):
        shedder = LoadShedder(name="test_rl")
        shedder.record_latency(100.0)
        shedder.record_latency(200.0)
        assert shedder._current_latency_ms == 150.0

    def test_record_latency_bounded(self):
        shedder = LoadShedder(name="test_bound")
        for i in range(110):
            shedder.record_latency(float(i))
        assert len(shedder._latency_samples) <= 100

    def test_force_shed_rate_clamps_to_max(self):
        shedder = LoadShedder(name="test_clamp")
        shedder.force_shed_rate(1.5)  # Above max of 0.9
        assert shedder._current_shed_rate <= shedder.config.max_shed_rate

    def test_force_shed_rate_clamps_to_zero(self):
        shedder = LoadShedder(name="test_clamp2")
        shedder.force_shed_rate(-0.5)
        assert shedder._current_shed_rate == 0.0

    def test_reset(self):
        shedder = LoadShedder(name="test_reset")
        shedder.force_shed_rate(0.5)
        shedder.record_latency(300.0)
        shedder.reset()
        assert shedder._current_shed_rate == 0.0
        assert shedder._latency_samples == []
        assert shedder._current_latency_ms == 0.0

    def test_get_stats(self):
        shedder = LoadShedder(name="test_stats", adaptive=False)
        shedder.force_shed_rate(0.3)
        shedder.set_queue_size(200)
        stats = shedder.get_stats()
        assert isinstance(stats, SheddingStats)
        assert stats.shedder_name == "test_stats"
        assert stats.current_shed_rate == 0.3
        assert stats.current_queue_size == 200

    def test_adaptive_shedding_high_load(self):
        """Test that adaptive shedding increases rate under high load."""
        shedder = LoadShedder(name="test_adaptive", adaptive=True)
        # Set high queue size
        shedder.set_queue_size(950)  # 95% of max 1000
        # Force evaluation by moving last_evaluation back
        shedder._last_evaluation = datetime.utcnow() - timedelta(seconds=20)
        shedder._evaluate_shed_rate()
        # Rate should have increased
        assert shedder._current_shed_rate > 0.0

    def test_adaptive_shedding_low_load(self):
        """Test that adaptive shedding decreases rate under low load."""
        shedder = LoadShedder(name="test_adaptive2", adaptive=True)
        shedder.force_shed_rate(0.5)
        shedder.set_queue_size(100)  # 10% of max 1000
        shedder._last_evaluation = datetime.utcnow() - timedelta(seconds=20)
        shedder._evaluate_shed_rate()
        # Rate should have decreased (0.5 * 0.9 = 0.45)
        assert shedder._current_shed_rate <= 0.5

    def test_adaptive_evaluation_skipped_within_window(self):
        """Test that evaluation is skipped if called too soon."""
        shedder = LoadShedder(name="test_window", adaptive=True)
        shedder._last_evaluation = datetime.utcnow()  # Just evaluated
        initial_rate = shedder._current_shed_rate
        shedder._evaluate_shed_rate()
        assert shedder._current_shed_rate == initial_rate

    def test_medium_load_maintains_rate(self):
        """Test shed rate stability under medium load (50-80%)."""
        shedder = LoadShedder(name="test_medium", adaptive=True)
        shedder.force_shed_rate(0.4)
        shedder.set_queue_size(600)  # 60% of max
        shedder._last_evaluation = datetime.utcnow() - timedelta(seconds=20)
        shedder._evaluate_shed_rate()
        assert shedder._current_shed_rate == 0.4  # Unchanged in medium range

    def test_requests_processed_counter(self):
        shedder = LoadShedder(name="test_counter", adaptive=False)
        shedder.force_shed_rate(0.0)
        for _ in range(10):
            shedder.should_process(Priority.NORMAL)
        assert shedder._requests_processed == 10

    def test_requests_shed_counter(self):
        shedder = LoadShedder(name="test_shed_count", adaptive=False)
        shedder.force_shed_rate(1.0)
        for _ in range(10):
            shedder.should_process(Priority.BACKGROUND)
        # Background weight is 0.95, so most should be shed
        assert shedder._requests_shed > 0

    def test_shed_by_priority_tracking(self):
        shedder = LoadShedder(name="test_prio_track", adaptive=False)
        shedder.force_shed_rate(1.0)
        for _ in range(10):
            shedder.should_process(Priority.LOW)
        assert "LOW" in shedder._shed_by_priority


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestGetLoadShedder:
    def test_get_load_shedder_creates_new(self):
        shedder = get_load_shedder("unique_shedder_xyz")
        assert isinstance(shedder, LoadShedder)
        assert shedder.name == "unique_shedder_xyz"

    def test_get_load_shedder_returns_same_instance(self):
        s1 = get_load_shedder("singleton_shedder_abc")
        s2 = get_load_shedder("singleton_shedder_abc")
        assert s1 is s2
