"""Additional coverage tests for adaptive_sampling.py."""
from __future__ import annotations

import time
from datetime import datetime, timedelta

import obskit.adaptive_sampling as module
from obskit.adaptive_sampling import AdaptiveSampler, SamplingConfig


class TestRateLimitCoverage:
    def test_rate_limit_exhausted_triggers_drop(self):
        """Lines 221-222: rate_limited drop path."""
        sampler = AdaptiveSampler(base_rate=1.0)
        sampler._rate_limit_tokens = 0
        sampler._last_token_refill = time.time()
        result = sampler.should_sample()
        assert result is False

    def test_check_rate_limit_token_refill(self):
        """Lines 285-289: token refill when elapsed > 1s."""
        sampler = AdaptiveSampler(base_rate=1.0)
        sampler._rate_limit_tokens = 0
        sampler._last_token_refill = time.time() - 3.0
        result = sampler._check_rate_limit()
        assert result is True

    def test_check_rate_limit_no_tokens_returns_false(self):
        """Line 296: empty token bucket returns False."""
        sampler = AdaptiveSampler(base_rate=1.0)
        sampler._rate_limit_tokens = 0
        sampler._last_token_refill = time.time()
        result = sampler._check_rate_limit()
        assert result is False


class TestMaybeAdaptCoverage:
    def test_maybe_adapt_high_error_rate(self):
        """Lines 306-339: adapt with high error rate."""
        sampler = AdaptiveSampler(base_rate=0.5, adapt_interval_seconds=0.0)
        sampler._request_count = 100
        sampler._error_count = 20
        sampler._samples_taken = 50
        sampler._last_adaptation = datetime.utcnow() - timedelta(seconds=10)
        sampler._maybe_adapt()
        assert sampler._request_count == 0
        assert sampler._error_count == 0

    def test_maybe_adapt_load_factor_high_reduces_rate(self):
        """Lines 321-323: high load_factor reduces rate."""
        sampler = AdaptiveSampler(base_rate=1.0, adapt_interval_seconds=0.0)
        sampler._current_rate = 1.0
        sampler._request_count = 10
        sampler._error_count = 0
        sampler._samples_taken = 100
        sampler._last_adaptation = datetime.utcnow() - timedelta(seconds=10)
        sampler._maybe_adapt()
        assert sampler._current_rate < 1.0

    def test_maybe_adapt_low_load_many_requests_increases_rate(self):
        """Lines 324-326: low load, many requests -> increase rate."""
        sampler = AdaptiveSampler(base_rate=0.01, adapt_interval_seconds=0.0)
        sampler._current_rate = 0.01
        sampler._request_count = 200
        sampler._error_count = 0
        sampler._samples_taken = 0
        sampler._last_adaptation = datetime.utcnow() - timedelta(seconds=10)
        sampler._maybe_adapt()
        assert sampler._current_rate > 0.01

    def test_maybe_adapt_zero_request_count_skips_inner_body(self):
        """Line 310: request_count == 0 skips inner if-block."""
        sampler = AdaptiveSampler(base_rate=0.5, adapt_interval_seconds=0.0)
        sampler._request_count = 0
        sampler._last_adaptation = datetime.utcnow() - timedelta(seconds=10)
        sampler._maybe_adapt()
        assert sampler._request_count == 0

    def test_maybe_adapt_expected_samples_zero(self):
        """Lines 317-318: expected_samples == 0 sets load_factor = 1.0."""
        sampler = AdaptiveSampler(base_rate=0.0, adapt_interval_seconds=0.0)
        sampler.config.base_rate = 0.0
        sampler._request_count = 10
        sampler._error_count = 0
        sampler._samples_taken = 5
        sampler._last_adaptation = datetime.utcnow() - timedelta(seconds=10)
        sampler._maybe_adapt()
        assert sampler._load_factor == 1.0


class TestSingletonCoverage:
    def test_get_adaptive_sampler_singleton_inner_branch(self):
        """Line 394: inner double-check locking branch."""
        unique_name = "__cov_test_inner_branch__"
        module._samplers.pop(unique_name, None)
        sampler1 = module.get_adaptive_sampler(unique_name)
        sampler2 = module.get_adaptive_sampler(unique_name)
        assert sampler1 is sampler2
        module._samplers.pop(unique_name, None)
