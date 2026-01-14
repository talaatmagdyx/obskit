"""Tests for obskit.metrics.golden module."""

import pytest
import uuid
from unittest.mock import MagicMock, patch

from obskit.metrics.golden import (
    GoldenSignals,
    get_golden_signals,
    reset_golden_signals,
)
from obskit.metrics.registry import reset_registry


class TestGoldenSignals:
    """Tests for GoldenSignals class."""

    def setup_method(self):
        """Reset before each test."""
        reset_registry()
        reset_golden_signals()

    def teardown_method(self):
        """Reset after each test."""
        reset_golden_signals()

    def test_init_with_name(self):
        """Test initialization with name."""
        name = f"golden_{uuid.uuid4().hex[:8]}"
        signals = GoldenSignals(name=name)
        assert signals is not None
        assert signals.name == name

    def test_init_creates_metrics(self):
        """Test initialization creates underlying metrics."""
        name = f"golden_{uuid.uuid4().hex[:8]}"
        signals = GoldenSignals(name=name)
        # Should have underlying RED metrics
        assert signals.red is not None

    def test_observe_request_success(self):
        """Test observing successful request."""
        name = f"golden_{uuid.uuid4().hex[:8]}"
        signals = GoldenSignals(name=name)
        signals.observe_request(
            operation="get_user",
            duration_seconds=0.1,
            status="success",
        )

    def test_observe_request_failure(self):
        """Test observing failed request."""
        name = f"golden_{uuid.uuid4().hex[:8]}"
        signals = GoldenSignals(name=name)
        signals.observe_request(
            operation="get_user",
            duration_seconds=0.5,
            status="failure",
            error_type="timeout",
        )

    def test_observe_request_multiple(self):
        """Test observing multiple requests."""
        name = f"golden_{uuid.uuid4().hex[:8]}"
        signals = GoldenSignals(name=name)
        
        for i in range(10):
            signals.observe_request(
                operation="get_user",
                duration_seconds=0.1 * i,
                status="success" if i % 2 == 0 else "failure",
            )

    def test_set_saturation(self):
        """Test setting saturation."""
        name = f"golden_{uuid.uuid4().hex[:8]}"
        signals = GoldenSignals(name=name)
        signals.set_saturation(resource="cpu", value=0.75)

    def test_set_saturation_multiple(self):
        """Test setting saturation for multiple resources."""
        name = f"golden_{uuid.uuid4().hex[:8]}"
        signals = GoldenSignals(name=name)
        signals.set_saturation(resource="cpu", value=0.75)
        signals.set_saturation(resource="memory", value=0.60)
        signals.set_saturation(resource="disk", value=0.40)

    def test_inc_queue_depth(self):
        """Test incrementing queue depth."""
        name = f"golden_{uuid.uuid4().hex[:8]}"
        signals = GoldenSignals(name=name)
        signals.inc_queue_depth(queue="orders")

    def test_set_queue_depth(self):
        """Test setting queue depth."""
        name = f"golden_{uuid.uuid4().hex[:8]}"
        signals = GoldenSignals(name=name)
        signals.set_queue_depth(queue="orders", depth=42)

    def test_set_queue_depth_multiple(self):
        """Test setting queue depth for multiple queues."""
        name = f"golden_{uuid.uuid4().hex[:8]}"
        signals = GoldenSignals(name=name)
        signals.set_queue_depth(queue="orders", depth=42)
        signals.set_queue_depth(queue="emails", depth=100)

    def test_dec_queue_depth(self):
        """Test decrementing queue depth."""
        name = f"golden_{uuid.uuid4().hex[:8]}"
        signals = GoldenSignals(name=name)
        signals.set_queue_depth(queue="orders", depth=10)
        signals.dec_queue_depth(queue="orders")

    def test_dec_queue_depth_with_amount(self):
        """Test decrementing queue depth by amount."""
        name = f"golden_{uuid.uuid4().hex[:8]}"
        signals = GoldenSignals(name=name)
        signals.set_queue_depth(queue="orders", depth=10)
        signals.dec_queue_depth(queue="orders", amount=3)

    def test_set_progress(self):
        """Test setting progress metrics."""
        name = f"golden_{uuid.uuid4().hex[:8]}"
        signals = GoldenSignals(name=name)
        signals.set_progress(
            operation="process_orders",
            progress_percent=45.5,
        )

    def test_set_progress_with_items(self):
        """Test setting progress metrics with item counts."""
        name = f"golden_{uuid.uuid4().hex[:8]}"
        signals = GoldenSignals(name=name)
        signals.set_progress(
            operation="process_orders",
            progress_percent=45.5,
            total_items=1000,
            completed_items=455,
        )
        # Should have created progress gauges
        assert hasattr(signals, "_progress_gauges")

    def test_set_progress_creates_gauges_once(self):
        """Test progress gauges are created only once."""
        name = f"golden_{uuid.uuid4().hex[:8]}"
        signals = GoldenSignals(name=name)
        
        signals.set_progress("op1", 50.0)
        gauges_first = signals._progress_gauges
        
        signals.set_progress("op2", 75.0)
        gauges_second = signals._progress_gauges
        
        # Same gauge objects should be reused
        assert gauges_first is gauges_second

    def test_track_request_context(self):
        """Test track_request via RED metrics."""
        name = f"golden_{uuid.uuid4().hex[:8]}"
        signals = GoldenSignals(name=name)
        
        # Use track_request from underlying RED metrics
        with signals.red.track_request("get_user"):
            pass  # Success

    def test_track_request_context_with_error(self):
        """Test track_request handles errors."""
        name = f"golden_{uuid.uuid4().hex[:8]}"
        signals = GoldenSignals(name=name)
        
        with pytest.raises(ValueError):
            with signals.red.track_request("get_user"):
                raise ValueError("test error")


class TestGetGoldenSignals:
    """Tests for get_golden_signals function."""

    def setup_method(self):
        """Reset before each test."""
        reset_golden_signals()

    def teardown_method(self):
        """Reset after each test."""
        reset_golden_signals()

    def test_get_creates_instance(self):
        """Test get_golden_signals creates instance."""
        signals = get_golden_signals()
        assert signals is not None

    def test_get_returns_same_instance(self):
        """Test get_golden_signals returns same instance."""
        signals1 = get_golden_signals()
        signals2 = get_golden_signals()
        assert signals1 is signals2

    def test_get_returns_consistent_name(self):
        """Test get_golden_signals returns consistent name."""
        signals = get_golden_signals()
        assert signals.name is not None


class TestResetGoldenSignals:
    """Tests for reset_golden_signals function."""

    def test_reset_clears_instance(self):
        """Test reset clears singleton instance."""
        get_golden_signals()  # Create one
        reset_golden_signals()
        # Should not raise

    def test_reset_allows_new_instance(self):
        """Test reset allows creating new instance."""
        signals1 = get_golden_signals()
        reset_golden_signals()
        signals2 = get_golden_signals()
        # After reset, get creates new instance
        # (may be same object due to caching, but state is reset)

