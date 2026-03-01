"""Tests for obskit.metrics.types module."""

from obskit.metrics.registry import reset_registry
from obskit.metrics.types import (
    Counter,
    Gauge,
    Histogram,
    Summary,
)


class TestCounter:
    """Tests for Counter class."""

    def setup_method(self):
        """Reset registry before each test."""
        reset_registry()

    def teardown_method(self):
        """Reset registry after each test."""
        reset_registry()

    def test_init(self):
        """Test counter initialization."""
        counter = Counter(
            name="test_counter",
            documentation="Test counter",
        )
        assert isinstance(counter, Counter)

    def test_init_with_labels(self):
        """Test counter with labels."""
        counter = Counter(
            name="test_counter_labels",
            documentation="Test counter",
            labelnames=["method", "status"],
        )
        assert isinstance(counter, Counter)

    def test_inc(self):
        """Test counter increment."""
        counter = Counter(
            name="test_inc",
            documentation="Test",
        )
        counter.inc()

    def test_inc_with_value(self):
        """Test counter increment with value."""
        counter = Counter(
            name="test_inc_val",
            documentation="Test",
        )
        counter.inc(5)

    def test_labels(self):
        """Test counter with labels."""
        counter = Counter(
            name="test_labels_counter",
            documentation="Test",
            labelnames=["method"],
        )
        counter.labels(method="GET").inc()


class TestGauge:
    """Tests for Gauge class."""

    def setup_method(self):
        """Reset registry before each test."""
        reset_registry()

    def teardown_method(self):
        """Reset registry after each test."""
        reset_registry()

    def test_init(self):
        """Test gauge initialization."""
        gauge = Gauge(
            name="test_gauge",
            documentation="Test gauge",
        )
        assert isinstance(gauge, Gauge)

    def test_set(self):
        """Test gauge set."""
        gauge = Gauge(
            name="test_set_gauge",
            documentation="Test",
        )
        gauge.set(42)

    def test_inc(self):
        """Test gauge increment."""
        gauge = Gauge(
            name="test_gauge_inc",
            documentation="Test",
        )
        gauge.inc()

    def test_dec(self):
        """Test gauge decrement."""
        gauge = Gauge(
            name="test_dec_gauge",
            documentation="Test",
        )
        gauge.dec()


class TestHistogram:
    """Tests for Histogram class."""

    def setup_method(self):
        """Reset registry before each test."""
        reset_registry()

    def teardown_method(self):
        """Reset registry after each test."""
        reset_registry()

    def test_init(self):
        """Test histogram initialization."""
        histogram = Histogram(
            name="test_histogram",
            documentation="Test histogram",
        )
        assert isinstance(histogram, Histogram)

    def test_init_with_buckets(self):
        """Test histogram with custom buckets."""
        histogram = Histogram(
            name="test_buckets_hist",
            documentation="Test",
            buckets=[0.1, 0.5, 1.0, 5.0],
        )
        assert isinstance(histogram, Histogram)

    def test_observe(self):
        """Test histogram observe."""
        histogram = Histogram(
            name="test_observe_hist",
            documentation="Test",
        )
        histogram.observe(0.5)


class TestSummary:
    """Tests for Summary class."""

    def setup_method(self):
        """Reset registry before each test."""
        reset_registry()

    def teardown_method(self):
        """Reset registry after each test."""
        reset_registry()

    def test_init(self):
        """Test summary initialization."""
        summary = Summary(
            name="test_summary",
            documentation="Test summary",
        )
        assert isinstance(summary, Summary)

    def test_observe(self):
        """Test summary observe."""
        summary = Summary(
            name="test_summary_observe",
            documentation="Test",
        )
        summary.observe(0.5)

    def test_init_replaces_existing(self):
        """Test summary replaces existing metric with same name."""

        # Create first summary
        summary1 = Summary(
            name="test_summary_replace",
            documentation="First summary",
        )
        summary1.observe(1.0)

        # Creating second summary with same name should unregister first
        summary2 = Summary(
            name="test_summary_replace",
            documentation="Second summary",
        )
        summary2.observe(2.0)

        # Should not raise - second summary should work
        assert isinstance(summary2, Summary)

    def test_labels(self):
        """Test summary with labels."""
        summary = Summary(
            name="test_summary_labels",
            documentation="Test",
            labelnames=["method"],
        )
        labeled = summary.labels(method="GET")
        labeled.observe(0.5)
