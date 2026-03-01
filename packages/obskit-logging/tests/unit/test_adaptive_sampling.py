"""Unit tests for Adaptive Sampling."""

from obskit.adaptive_sampling import (
    AdaptiveSampler,
    SamplingConfig,
    SamplingStats,
    get_adaptive_sampler,
)
from datetime import UTC
import pytest


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
        error_samples = sum(1 for _ in range(100) if sampler.should_sample(has_error=True))

        # Should be much higher than 10%
        assert error_samples > 50

    def test_slow_request_boost(self):
        """Test slow request boost."""
        sampler = AdaptiveSampler(base_rate=0.1)
        sampler.config.slow_threshold_ms = 100.0
        sampler.config.slow_boost_factor = 5.0

        # Slow requests should have higher sampling rate
        slow_samples = sum(1 for _ in range(100) if sampler.should_sample(latency_ms=500.0))

        # Should be higher than base rate
        assert slow_samples > 30

    def test_operation_specific_rate(self):
        """Test operation-specific sampling rates."""
        sampler = AdaptiveSampler(base_rate=0.1)
        sampler.set_operation_rate("high-priority-op", 1.0)  # 100%

        # Operation-specific rate should apply
        samples = sum(1 for _ in range(10) if sampler.should_sample(operation="high-priority-op"))
        assert samples == 10

    def test_manual_rate_setting(self):
        """Test manual rate setting."""
        sampler = AdaptiveSampler(base_rate=0.5)

        sampler.set_rate(0.9)
        assert sampler.get_rate() == pytest.approx(0.9)

        # Rate should be clamped to max
        sampler.set_rate(2.0)
        assert sampler.get_rate() == pytest.approx(1.0)

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
        assert data["base_rate"] == pytest.approx(0.1)
        assert data["min_rate"] == pytest.approx(0.01)
        assert data["max_rate"] == pytest.approx(1.0)


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

        assert stats.sample_ratio == pytest.approx(0.6)

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
        assert data["sample_ratio"] == pytest.approx(0.5)


class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_adaptive_sampler(self):
        """Test sampler singleton per name."""
        sampler1 = get_adaptive_sampler("sampler1")
        sampler2 = get_adaptive_sampler("sampler1")
        sampler3 = get_adaptive_sampler("sampler2")

        assert sampler1 is sampler2
        assert sampler1 is not sampler3


class TestAdaptiveSamplerCoverage:
    """Extra tests to cover missing lines in adaptive_sampling.py."""

    def test_rate_limit_exhausted_triggers_drop(self):
        """Test that exhausting rate limit tokens causes DROP decision (lines 221-222)."""
        import time
        sampler = AdaptiveSampler(base_rate=1.0)

        # Exhaust all tokens
        sampler._rate_limit_tokens = 0
        # Make sure no token refill happens (recent refill)
        sampler._last_token_refill = time.time()

        result = sampler.should_sample()
        assert result is False

    def test_check_rate_limit_token_refill(self):
        """Test token refill when more than 1 second has elapsed (lines 285-289)."""
        import time
        sampler = AdaptiveSampler(base_rate=1.0)

        # Force token depletion and set old refill time
        sampler._rate_limit_tokens = 0
        sampler._last_token_refill = time.time() - 3.0  # 3 seconds ago

        # Should refill tokens and succeed
        result = sampler._check_rate_limit()
        assert result is True

    def test_check_rate_limit_no_tokens_returns_false(self):
        """Test that empty token bucket returns False (line 296)."""
        import time
        sampler = AdaptiveSampler(base_rate=1.0)

        # Deplete tokens, no time elapsed
        sampler._rate_limit_tokens = 0
        sampler._last_token_refill = time.time()

        result = sampler._check_rate_limit()
        assert result is False

    def test_maybe_adapt_high_error_rate(self):
        """Test _maybe_adapt runs adaptation logic (lines 306-339)."""
        from datetime import datetime, timedelta, timezone
        sampler = AdaptiveSampler(base_rate=0.5, adapt_interval_seconds=0.0)

        # Set conditions to trigger adaptation with high error rate (>10%)
        sampler._request_count = 100
        sampler._error_count = 20  # 20% error rate > 10%, boosts rate
        sampler._samples_taken = 50  # normal load
        sampler._last_adaptation = datetime.now(UTC) - timedelta(seconds=10)

        sampler._maybe_adapt()

        # After adaptation, counters should be reset
        assert sampler._request_count == 0
        assert sampler._error_count == 0

    def test_maybe_adapt_load_factor_high_reduces_rate(self):
        """Test high load_factor triggers rate reduction (lines 321-323)."""
        from datetime import datetime, timedelta
        sampler = AdaptiveSampler(base_rate=1.0, adapt_interval_seconds=0.0)
        sampler._current_rate = 1.0

        # load_factor > 1.5 => samples_taken >> expected_samples
        sampler._request_count = 10
        sampler._error_count = 0
        sampler._samples_taken = 100  # way more than expected (10 * 1.0 = 10)
        sampler._last_adaptation = datetime.now(UTC) - timedelta(seconds=10)

        sampler._maybe_adapt()

        # Rate should have decreased
        assert sampler._current_rate < 1.0

    def test_maybe_adapt_low_load_many_requests_increases_rate(self):
        """Test low load_factor with many requests increases rate (lines 324-326)."""
        from datetime import datetime, timedelta
        sampler = AdaptiveSampler(base_rate=0.01, adapt_interval_seconds=0.0)
        sampler._current_rate = 0.01

        # load_factor < 0.5 and request_count > 100
        sampler._request_count = 200
        sampler._error_count = 0
        sampler._samples_taken = 0  # none sampled => load_factor = 0
        sampler._last_adaptation = datetime.now(UTC) - timedelta(seconds=10)

        sampler._maybe_adapt()

        # Rate should have increased
        assert sampler._current_rate > 0.01

    def test_maybe_adapt_zero_request_count_skips_body(self):
        """Test _maybe_adapt with zero requests skips inner body."""
        from datetime import datetime, timedelta
        sampler = AdaptiveSampler(base_rate=0.5, adapt_interval_seconds=0.0)

        # Zero requests
        sampler._request_count = 0
        sampler._last_adaptation = datetime.now(UTC) - timedelta(seconds=10)

        # Should run without error
        sampler._maybe_adapt()
        assert sampler._request_count == 0

    def test_get_adaptive_sampler_singleton_inner_branch(self):
        """Test get_adaptive_sampler creates new sampler in inner lock branch (line 394)."""
        import obskit.adaptive_sampling as module

        # Clear the cache so the inner branch is reached
        unique_name = "__test_inner_branch_unique__"
        module._samplers.pop(unique_name, None)

        sampler1 = module.get_adaptive_sampler(unique_name)
        sampler2 = module.get_adaptive_sampler(unique_name)

        assert sampler1 is sampler2
        # Cleanup
        module._samplers.pop(unique_name, None)
