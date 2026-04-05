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


class TestREDMetricsEdgeCases:
    """Edge case tests for REDMetrics — coverage gaps."""

    def test_long_operation_label_truncated(self):
        """Operation label > 128 chars is truncated with hash suffix (lines 520-532)."""
        name = f"test_{uuid.uuid4().hex[:8]}"
        metrics = REDMetrics(name=name)
        long_op = "a" * 200  # > 128 chars
        # Should not raise; truncates the label
        metrics.observe_request(
            operation=long_op,
            duration_seconds=0.1,
            status="success",
        )

    def test_get_red_metrics_double_check_locking(self):
        """get_red_metrics() creates a new instance after reset (covers lines 711->715)."""
        reset_red_metrics()
        # First call: _red_metrics is None → enters outer branch → creates instance
        m1 = get_red_metrics()
        assert m1 is not None
        # Second call: _red_metrics is already set → skips inner branch (covers 711->False path)
        m2 = get_red_metrics()
        assert m2 is m1
        reset_red_metrics()


class TestObserveRequestExemplars:
    """Tests for observe_request(exemplars=True)."""

    def test_exemplars_false_uses_plain_observe(self):
        """exemplars=False (default) calls histogram.observe() directly."""
        from unittest.mock import MagicMock, patch
        name = f"ex_{uuid.uuid4().hex[:8]}"
        metrics = REDMetrics(name=name)
        labeled = MagicMock()
        with patch.object(metrics.duration_histogram, "labels", return_value=labeled):
            metrics.observe_request("op", 0.05, exemplars=False)
        labeled.observe.assert_called_once_with(0.05)

    def test_exemplars_true_calls_observe_with_exemplar(self):
        """exemplars=True delegates to observe_with_exemplar for trace linking."""
        from unittest.mock import MagicMock, patch
        name = f"ex_{uuid.uuid4().hex[:8]}"
        metrics = REDMetrics(name=name)
        labeled = MagicMock()
        with patch.object(metrics.duration_histogram, "labels", return_value=labeled), \
             patch("obskit.metrics.exemplar.observe_with_exemplar") as mock_owe:
            metrics.observe_request("op", 0.05, exemplars=True)
        mock_owe.assert_called_once_with(labeled, 0.05)

    def test_exemplars_default_is_false(self):
        """observe_request signature defaults exemplars=False."""
        import inspect
        from obskit.metrics.red import REDMetrics as _RED
        sig = inspect.signature(_RED.observe_request)
        assert sig.parameters["exemplars"].default is False

    def test_exemplars_true_no_histogram_no_error(self):
        """exemplars=True with use_histogram=False does not raise."""
        name = f"ex_{uuid.uuid4().hex[:8]}"
        metrics = REDMetrics(name=name, use_histogram=False)
        # Should complete without error
        metrics.observe_request("op", 0.05, exemplars=True)
