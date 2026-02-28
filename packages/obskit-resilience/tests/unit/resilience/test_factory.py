"""
Tests for obskit.resilience.factory module.
"""

from __future__ import annotations

import pytest

from obskit.resilience.circuit_breaker import CircuitBreaker
from obskit.resilience.factory import (
    CircuitBreakerPreset,
    RateLimiterPreset,
    get_circuit_breaker,
    get_circuit_breaker_status,
    get_rate_limiter,
    list_circuit_breakers,
    list_rate_limiters,
    reset_circuit_breaker,
)
from obskit.resilience.rate_limiter import RateLimiter, TokenBucketRateLimiter


# =============================================================================
# CircuitBreakerPreset Tests
# =============================================================================


class TestCircuitBreakerPreset:
    def test_database_preset_values(self):
        config = CircuitBreakerPreset.DATABASE.value
        assert config["failure_threshold"] == 3
        assert config["recovery_timeout"] == 15.0

    def test_cache_preset_values(self):
        config = CircuitBreakerPreset.CACHE.value
        assert config["failure_threshold"] == 5
        assert config["recovery_timeout"] == 10.0

    def test_external_api_preset_values(self):
        config = CircuitBreakerPreset.EXTERNAL_API.value
        assert config["failure_threshold"] == 3
        assert config["recovery_timeout"] == 60.0

    def test_microservice_preset_values(self):
        config = CircuitBreakerPreset.MICROSERVICE.value
        assert config["failure_threshold"] == 5
        assert config["recovery_timeout"] == 30.0

    def test_ai_api_preset_values(self):
        config = CircuitBreakerPreset.AI_API.value
        assert config["recovery_timeout"] == 120.0

    def test_default_preset_values(self):
        config = CircuitBreakerPreset.DEFAULT.value
        assert config["failure_threshold"] == 5
        assert config["recovery_timeout"] == 30.0

    def test_all_presets_have_required_keys(self):
        required_keys = {"failure_threshold", "recovery_timeout", "half_open_requests"}
        for preset in CircuitBreakerPreset:
            assert required_keys.issubset(preset.value.keys()), f"{preset.name} missing keys"


# =============================================================================
# RateLimiterPreset Tests
# =============================================================================


class TestRateLimiterPreset:
    def test_high_throughput_preset(self):
        config = RateLimiterPreset.HIGH_THROUGHPUT.value
        assert config["requests_per_minute"] == 10000

    def test_external_api_preset(self):
        config = RateLimiterPreset.EXTERNAL_API.value
        assert config["requests_per_minute"] == 100

    def test_ai_api_preset(self):
        config = RateLimiterPreset.AI_API.value
        assert config["requests_per_minute"] == 60

    def test_all_presets_have_rpm(self):
        for preset in RateLimiterPreset:
            assert "requests_per_minute" in preset.value


# =============================================================================
# get_circuit_breaker Tests
# =============================================================================


class TestGetCircuitBreaker:
    def test_creates_circuit_breaker(self):
        cb = get_circuit_breaker("factory_test_unique_1")
        assert isinstance(cb, CircuitBreaker)

    def test_returns_same_instance_for_same_name(self):
        cb1 = get_circuit_breaker("factory_singleton_test_x")
        cb2 = get_circuit_breaker("factory_singleton_test_x")
        assert cb1 is cb2

    def test_with_database_preset(self):
        cb = get_circuit_breaker(
            "factory_db_preset_test",
            preset=CircuitBreakerPreset.DATABASE,
        )
        assert isinstance(cb, CircuitBreaker)
        assert cb._failure_threshold == 3

    def test_with_cache_preset(self):
        cb = get_circuit_breaker(
            "factory_cache_preset_test",
            preset=CircuitBreakerPreset.CACHE,
        )
        assert cb._failure_threshold == 5

    def test_custom_failure_threshold_overrides_preset(self):
        cb = get_circuit_breaker(
            "factory_override_threshold_test",
            preset=CircuitBreakerPreset.DATABASE,
            failure_threshold=10,
        )
        assert cb._failure_threshold == 10

    def test_custom_recovery_timeout_overrides_preset(self):
        cb = get_circuit_breaker(
            "factory_override_recovery_test",
            preset=CircuitBreakerPreset.DATABASE,
            recovery_timeout=120.0,
        )
        assert cb._recovery_timeout == 120.0

    def test_custom_half_open_requests_overrides(self):
        cb = get_circuit_breaker(
            "factory_override_half_open_test",
            preset=CircuitBreakerPreset.DATABASE,
            half_open_requests=5,
        )
        assert cb._half_open_requests == 5

    def test_no_preset_uses_defaults(self):
        cb = get_circuit_breaker("factory_no_preset_test_abc")
        # Should use DEFAULT preset
        assert cb._failure_threshold == 5

    def test_all_presets_create_valid_circuit_breakers(self):
        for i, preset in enumerate(CircuitBreakerPreset):
            name = f"factory_preset_test_{preset.name}_{i}"
            cb = get_circuit_breaker(name, preset=preset)
            assert isinstance(cb, CircuitBreaker)


# =============================================================================
# get_rate_limiter Tests
# =============================================================================


class TestGetRateLimiter:
    def test_creates_rate_limiter(self):
        rl = get_rate_limiter("factory_rl_unique_1")
        assert isinstance(rl, TokenBucketRateLimiter)

    def test_returns_same_instance_for_same_name(self):
        rl1 = get_rate_limiter("factory_rl_singleton_xyz")
        rl2 = get_rate_limiter("factory_rl_singleton_xyz")
        assert rl1 is rl2

    def test_with_preset(self):
        rl = get_rate_limiter(
            "factory_rl_preset_test",
            preset=RateLimiterPreset.EXTERNAL_API,
        )
        assert isinstance(rl, TokenBucketRateLimiter)

    def test_with_custom_rpm(self):
        rl = get_rate_limiter("factory_rl_custom_rpm", requests_per_minute=300)
        assert isinstance(rl, TokenBucketRateLimiter)

    def test_no_preset_uses_defaults(self):
        rl = get_rate_limiter("factory_rl_no_preset_abc123")
        assert isinstance(rl, TokenBucketRateLimiter)


# =============================================================================
# reset_circuit_breaker Tests
# =============================================================================


class TestResetCircuitBreaker:
    def test_reset_existing_breaker(self):
        cb = get_circuit_breaker("factory_reset_test_1")
        result = reset_circuit_breaker("factory_reset_test_1")
        assert result is True

    def test_reset_nonexistent_breaker(self):
        result = reset_circuit_breaker("nonexistent_breaker_abc_xyz")
        assert result is False


# =============================================================================
# get_circuit_breaker_status Tests
# =============================================================================


class TestGetCircuitBreakerStatus:
    def test_status_existing_breaker(self):
        get_circuit_breaker("factory_status_test_1")
        status = get_circuit_breaker_status("factory_status_test_1")
        assert status is not None
        assert status["name"] == "factory_status_test_1"
        assert "state" in status
        assert "failure_count" in status

    def test_status_nonexistent_breaker(self):
        result = get_circuit_breaker_status("nonexistent_cb_xyz_123")
        assert result is None


# =============================================================================
# list_circuit_breakers Tests
# =============================================================================


class TestListCircuitBreakers:
    def test_list_circuit_breakers(self):
        get_circuit_breaker("factory_list_test_1")
        result = list_circuit_breakers()
        assert isinstance(result, dict)
        assert "factory_list_test_1" in result


# =============================================================================
# list_rate_limiters Tests
# =============================================================================


class TestListRateLimiters:
    def test_list_rate_limiters(self):
        get_rate_limiter("factory_rl_list_test_1")
        result = list_rate_limiters()
        assert isinstance(result, dict)
        assert "factory_rl_list_test_1" in result
