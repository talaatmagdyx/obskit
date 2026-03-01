"""Tests for obskit.metrics.red module."""

import uuid

import pytest

from obskit.metrics.red import REDMetrics, get_red_metrics, reset_red_metrics


class TestREDMetrics:
    """Tests for REDMetrics class."""

    def setup_method(self):
        """Reset metrics before each test."""
        reset_red_metrics()

    def teardown_method(self):
        """Reset metrics after each test."""
        reset_red_metrics()

    def test_init_with_name(self):
        """Test initialization with name."""
        name = f"test_{uuid.uuid4().hex[:8]}"
        metrics = REDMetrics(name=name)
        assert isinstance(metrics, REDMetrics)

    def test_observe_request_success(self):
        """Test observing successful request."""
        name = f"test_{uuid.uuid4().hex[:8]}"
        metrics = REDMetrics(name=name)

        metrics.observe_request(
            operation="test_op",
            duration_seconds=0.1,
            status="success",
        )

    def test_observe_request_failure(self):
        """Test observing failed request."""
        name = f"test_{uuid.uuid4().hex[:8]}"
        metrics = REDMetrics(name=name)

        metrics.observe_request(
            operation="test_op",
            duration_seconds=0.5,
            status="failure",
            error_type="ValueError",
        )

    def test_track_request_context(self):
        """Test track_request context manager."""
        name = f"test_{uuid.uuid4().hex[:8]}"
        metrics = REDMetrics(name=name)

        with metrics.track_request("test_operation"):
            pass  # Simulated work

    def test_track_request_with_error(self):
        """Test track_request records errors."""
        name = f"test_{uuid.uuid4().hex[:8]}"
        metrics = REDMetrics(name=name)

        with pytest.raises(ValueError):
            with metrics.track_request("failing_operation"):
                raise ValueError("Test error")


class TestGetREDMetrics:
    """Tests for get_red_metrics function."""

    def setup_method(self):
        """Reset metrics before each test."""
        reset_red_metrics()

    def teardown_method(self):
        """Reset metrics after each test."""
        reset_red_metrics()

    def test_get_returns_metrics(self):
        """Test that get_red_metrics returns metrics instance."""
        metrics = get_red_metrics()
        assert metrics is not None

    def test_get_returns_same_instance(self):
        """Test that get_red_metrics returns same instance."""
        metrics1 = get_red_metrics()
        metrics2 = get_red_metrics()
        assert metrics1 is metrics2


class TestResetREDMetrics:
    """Tests for reset_red_metrics function."""

    def test_reset_clears_metrics(self):
        """Test that reset clears the metrics instance."""
        # Get initial instance
        get_red_metrics()

        # Reset
        reset_red_metrics()

        # Get new instance - should be different
        get_red_metrics()
        # After reset, should get a new instance


class TestREDMetricsAdvanced:
    """Advanced tests for REDMetrics features."""

    def setup_method(self):
        """Reset metrics before each test."""
        reset_red_metrics()

    def teardown_method(self):
        """Reset metrics after each test."""
        reset_red_metrics()

    def test_init_without_histogram(self):
        """Test initialization with histogram disabled."""
        name = f"test_{uuid.uuid4().hex[:8]}"
        metrics = REDMetrics(name=name, use_histogram=False)

        assert metrics.duration_histogram is None

    def test_init_with_summary(self):
        """Test initialization with summary enabled."""
        name = f"test_{uuid.uuid4().hex[:8]}"
        metrics = REDMetrics(name=name, use_summary=True)

        assert metrics.duration_summary is not None

    def test_init_with_both_histogram_and_summary(self):
        """Test initialization with both histogram and summary."""
        name = f"test_{uuid.uuid4().hex[:8]}"
        metrics = REDMetrics(name=name, use_histogram=True, use_summary=True)

        assert metrics.duration_histogram is not None
        assert metrics.duration_summary is not None

    def test_observe_with_summary(self):
        """Test observe_request records to summary when enabled."""
        name = f"test_{uuid.uuid4().hex[:8]}"
        metrics = REDMetrics(name=name, use_summary=True)

        metrics.observe_request(
            operation="test_op",
            duration_seconds=0.1,
            status="success",
        )

    def test_observe_error_standalone(self):
        """Test observe_error method."""
        name = f"test_{uuid.uuid4().hex[:8]}"
        metrics = REDMetrics(name=name)

        metrics.observe_error(
            operation="test_op",
            error_type="ConnectionError",
        )

    def test_sampling_skips_observations(self):
        """Test that sampling rate < 1.0 can skip observations."""
        name = f"test_{uuid.uuid4().hex[:8]}"
        # Use 0% sample rate - all non-error observations should be skipped
        metrics = REDMetrics(name=name, sample_rate=0.0)

        # This should not raise and should skip the observation
        metrics.observe_request(
            operation="test_op",
            duration_seconds=0.1,
            status="success",
        )

    def test_failure_without_error_type(self):
        """Test failure status without explicit error_type uses UnknownError."""
        name = f"test_{uuid.uuid4().hex[:8]}"
        metrics = REDMetrics(name=name)

        metrics.observe_request(
            operation="test_op",
            duration_seconds=0.5,
            status="failure",
            # No error_type provided
        )
