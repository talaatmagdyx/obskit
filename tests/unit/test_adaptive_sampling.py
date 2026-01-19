"""Unit tests for Adaptive Sampling."""

import pytest
from obskit.adaptive_sampling import (
    AdaptiveSampler,
    SamplingConfig,
    SamplingStats,
    get_adaptive_sampler,
)


class TestAdaptiveSampler:
    """Tests for AdaptiveSampler."""

    def test_basic_sampling(self):
        """Test basic sampling decision."""
        sampler = AdaptiveSampler(base_rate=0.5)
        
        # With 50% rate, we should get some samples
        samples = sum(1 for _ in range(100) if sampler.should_sample())
        
        # Should be roughly 50%, allow for variance
        assert 20 < samples < 80

    def test_priority_always_sampled(self):
        """Test priority requests are always sampled."""
        sampler = AdaptiveSampler(base_rate=0.0)  # 0% rate
        
        # Priority should always sample
        for _ in range(10):
            assert sampler.should_sample(priority=True) is True

    def test_error_boost(self):
        """Test error boost increases sampling."""
        sampler = AdaptiveSampler(base_rate=0.1)
        sampler.config.error_boost_factor = 10.0
        
        # Errors should have higher sampling rate
        error_samples = sum(
            1 for _ in range(100) if sampler.should_sample(has_error=True)
        )
        
        # Should be much higher than 10%
        assert error_samples > 50

    def test_slow_request_boost(self):
        """Test slow request boost."""
        sampler = AdaptiveSampler(base_rate=0.1)
        sampler.config.slow_threshold_ms = 100.0
        sampler.config.slow_boost_factor = 5.0
        
        # Slow requests should have higher sampling rate
        slow_samples = sum(
            1 for _ in range(100) if sampler.should_sample(latency_ms=500.0)
        )
        
        # Should be higher than base rate
        assert slow_samples > 30

    def test_operation_specific_rate(self):
        """Test operation-specific sampling rates."""
        sampler = AdaptiveSampler(base_rate=0.1)
        sampler.set_operation_rate("high-priority-op", 1.0)  # 100%
        
        # Operation-specific rate should apply
        samples = sum(
            1 for _ in range(10)
            if sampler.should_sample(operation="high-priority-op")
        )
        assert samples == 10

    def test_manual_rate_setting(self):
        """Test manual rate setting."""
        sampler = AdaptiveSampler(base_rate=0.5)
        
        sampler.set_rate(0.9)
        assert sampler.get_rate() == 0.9
        
        # Rate should be clamped to max
        sampler.set_rate(2.0)
        assert sampler.get_rate() == 1.0

    def test_get_stats(self):
        """Test statistics retrieval."""
        sampler = AdaptiveSampler(name="test-sampler", base_rate=0.5)
        
        # Generate some samples
        for _ in range(100):
            sampler.should_sample()
        
        stats = sampler.get_stats()
        
        assert stats.sampler_name == "test-sampler"
        assert stats.samples_taken + stats.samples_dropped == 100

    def test_reset_stats(self):
        """Test statistics reset."""
        sampler = AdaptiveSampler(base_rate=0.5)
        
        for _ in range(50):
            sampler.should_sample()
        
        sampler.reset_stats()
        stats = sampler.get_stats()
        
        assert stats.samples_taken == 0
        assert stats.samples_dropped == 0


class TestSamplingConfig:
    """Tests for SamplingConfig."""

    def test_to_dict(self):
        """Test SamplingConfig serialization."""
        config = SamplingConfig(
            base_rate=0.1,
            min_rate=0.01,
            max_rate=1.0,
        )
        
        data = config.to_dict()
        assert data["base_rate"] == 0.1
        assert data["min_rate"] == 0.01
        assert data["max_rate"] == 1.0


class TestSamplingStats:
    """Tests for SamplingStats."""

    def test_sample_ratio(self):
        """Test sample ratio calculation."""
        stats = SamplingStats(
            sampler_name="test",
            current_rate=0.5,
            samples_taken=60,
            samples_dropped=40,
            load_factor=1.0,
        )
        
        assert stats.sample_ratio == 0.6

    def test_to_dict(self):
        """Test SamplingStats serialization."""
        stats = SamplingStats(
            sampler_name="test",
            current_rate=0.5,
            samples_taken=50,
            samples_dropped=50,
            load_factor=1.0,
        )
        
        data = stats.to_dict()
        assert data["sampler_name"] == "test"
        assert data["sample_ratio"] == 0.5


class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_adaptive_sampler(self):
        """Test sampler singleton per name."""
        sampler1 = get_adaptive_sampler("sampler1")
        sampler2 = get_adaptive_sampler("sampler1")
        sampler3 = get_adaptive_sampler("sampler2")
        
        assert sampler1 is sampler2
        assert sampler1 is not sampler3
