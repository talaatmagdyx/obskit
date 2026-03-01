"""Unit tests for obskit.core.errors — structured error codes."""

from __future__ import annotations

import pytest

from obskit.core.errors import (
    ERROR_CODES,
    CircuitBreakerError,
    CircuitHalfOpenError,
    CircuitOpenError,
    ConfigFileNotFoundError,
    ConfigurationError,
    ConfigValidationError,
    HealthCheckError,
    HealthCheckFailedError,
    HealthCheckTimeoutError,
    MetricsError,
    MetricsExportError,
    MetricsQueueFullError,
    ObskitError,
    RateLimitError,
    RateLimitExceeded,
    RetryError,
    SLOBudgetExhaustedError,
    SLOError,
    SLONotFoundError,
    TracingError,
    TracingExportError,
    TracingNotConfiguredError,
    get_error_class,
)

# =============================================================================
# ObskitError
# =============================================================================


class TestObskitError:
    def test_basic_init(self):
        err = ObskitError("Something went wrong")
        assert err.message == "Something went wrong"
        assert err.code == "OBSKIT_UNKNOWN"
        assert err.details == {}
        assert str(err) == "Something went wrong"

    def test_init_with_custom_code(self):
        err = ObskitError("msg", code="MY_CODE")
        assert err.code == "MY_CODE"

    def test_init_with_details(self):
        err = ObskitError("msg", details={"key": "value"})
        assert err.details == {"key": "value"}

    def test_init_without_code_keeps_class_default(self):
        err = ObskitError("msg", code=None)
        assert err.code == "OBSKIT_UNKNOWN"

    def test_to_dict(self):
        err = ObskitError("oops", code="OBSKIT_UNKNOWN", details={"a": 1})
        d = err.to_dict()
        assert d["code"] == "OBSKIT_UNKNOWN"
        assert d["message"] == "oops"
        assert d["details"] == {"a": 1}

    def test_to_dict_empty_details(self):
        err = ObskitError("msg")
        d = err.to_dict()
        assert d["details"] == {}

    def test_is_exception(self):
        with pytest.raises(ObskitError):
            raise ObskitError("test")

    def test_inheritance(self):
        err = ObskitError("x")
        assert isinstance(err, Exception)


# =============================================================================
# Configuration Errors
# =============================================================================


class TestConfigurationError:
    def test_default_code(self):
        err = ConfigurationError("bad config")
        assert err.code == "OBSKIT_CONFIG_ERROR"

    def test_is_obskit_error(self):
        err = ConfigurationError("bad config")
        assert isinstance(err, ObskitError)

    def test_message_preserved(self):
        err = ConfigurationError("config problem")
        assert err.message == "config problem"

    def test_to_dict(self):
        err = ConfigurationError("x")
        d = err.to_dict()
        assert d["code"] == "OBSKIT_CONFIG_ERROR"


class TestConfigFileNotFoundError:
    def test_default_code(self):
        err = ConfigFileNotFoundError("file missing")
        assert err.code == "OBSKIT_CONFIG_FILE_NOT_FOUND"

    def test_is_configuration_error(self):
        err = ConfigFileNotFoundError("file missing")
        assert isinstance(err, ConfigurationError)


class TestConfigValidationError:
    def test_default_code(self):
        err = ConfigValidationError("invalid value")
        assert err.code == "OBSKIT_CONFIG_VALIDATION_ERROR"

    def test_is_configuration_error(self):
        err = ConfigValidationError("invalid")
        assert isinstance(err, ConfigurationError)


# =============================================================================
# Circuit Breaker Errors
# =============================================================================


class TestCircuitBreakerError:
    def test_default_code(self):
        err = CircuitBreakerError("circuit error")
        assert err.code == "OBSKIT_CIRCUIT_ERROR"

    def test_breaker_name_in_details(self):
        err = CircuitBreakerError("circuit error", breaker_name="payment_api")
        assert err.breaker_name == "payment_api"
        assert err.details["breaker_name"] == "payment_api"

    def test_default_breaker_name(self):
        err = CircuitBreakerError("circuit error")
        assert err.breaker_name == "unknown"

    def test_is_obskit_error(self):
        err = CircuitBreakerError("x")
        assert isinstance(err, ObskitError)

    def test_custom_code_override(self):
        err = CircuitBreakerError("x", code="CUSTOM_CODE")
        assert err.code == "CUSTOM_CODE"

    def test_merges_details_with_breaker_name(self):
        err = CircuitBreakerError("x", breaker_name="svc", details={"foo": "bar"})
        assert err.details["foo"] == "bar"
        assert err.details["breaker_name"] == "svc"


class TestCircuitOpenError:
    def test_default_code(self):
        err = CircuitOpenError("my_breaker", 5.5)
        assert err.code == "OBSKIT_CIRCUIT_OPEN"

    def test_attributes(self):
        err = CircuitOpenError("my_breaker", 5.5)
        assert err.breaker_name == "my_breaker"
        assert err.time_until_retry == pytest.approx(5.5)

    def test_message_format(self):
        err = CircuitOpenError("my_breaker", 10.0)
        assert "my_breaker" in err.message
        assert "10.0" in err.message

    def test_details_include_time(self):
        err = CircuitOpenError("svc", 3.2)
        assert err.details["time_until_retry"] == pytest.approx(3.2)

    def test_is_circuit_breaker_error(self):
        err = CircuitOpenError("svc", 1.0)
        assert isinstance(err, CircuitBreakerError)


class TestCircuitHalfOpenError:
    def test_default_code(self):
        err = CircuitHalfOpenError("half open")
        assert err.code == "OBSKIT_CIRCUIT_HALF_OPEN"

    def test_is_circuit_breaker_error(self):
        err = CircuitHalfOpenError("half open")
        assert isinstance(err, CircuitBreakerError)


# =============================================================================
# Retry Errors
# =============================================================================


class TestRetryError:
    def test_default_code(self):
        err = RetryError("retries exhausted")
        assert err.code == "OBSKIT_RETRY_EXHAUSTED"

    def test_attempts_stored(self):
        err = RetryError("exhausted", attempts=5)
        assert err.attempts == 5
        assert err.details["attempts"] == 5

    def test_last_exception_stored(self):
        cause = ValueError("original error")
        err = RetryError("exhausted", attempts=3, last_exception=cause)
        assert err.last_exception is cause
        assert "original error" in err.details["last_error"]
        assert err.details["last_error_type"] == "ValueError"

    def test_no_last_exception(self):
        err = RetryError("exhausted")
        assert err.last_exception is None
        assert "last_error" not in err.details

    def test_is_obskit_error(self):
        err = RetryError("x")
        assert isinstance(err, ObskitError)


# =============================================================================
# Rate Limit Errors
# =============================================================================


class TestRateLimitError:
    def test_default_code(self):
        err = RateLimitError("rate limit")
        assert err.code == "OBSKIT_RATE_LIMIT_ERROR"

    def test_is_obskit_error(self):
        err = RateLimitError("rate limit")
        assert isinstance(err, ObskitError)


class TestRateLimitExceeded:
    def test_default_code(self):
        err = RateLimitExceeded()
        assert err.code == "OBSKIT_RATE_LIMIT_EXCEEDED"

    def test_default_message(self):
        err = RateLimitExceeded()
        assert err.message == "Rate limit exceeded"

    def test_limit_and_window_stored(self):
        err = RateLimitExceeded(limit=100, window_seconds=60.0)
        assert err.limit == 100
        assert err.window_seconds == pytest.approx(60.0)
        assert err.details["limit"] == 100
        assert err.details["window_seconds"] == pytest.approx(60.0)

    def test_retry_after_in_details_when_set(self):
        err = RateLimitExceeded(retry_after=30.0)
        assert err.retry_after == pytest.approx(30.0)
        assert err.details["retry_after"] == pytest.approx(30.0)

    def test_retry_after_absent_when_none(self):
        err = RateLimitExceeded()
        assert err.retry_after is None
        assert "retry_after" not in err.details

    def test_is_rate_limit_error(self):
        err = RateLimitExceeded()
        assert isinstance(err, RateLimitError)


# =============================================================================
# Health Check Errors
# =============================================================================


class TestHealthCheckError:
    def test_default_code(self):
        err = HealthCheckError("health check failed")
        assert err.code == "OBSKIT_HEALTH_ERROR"

    def test_is_obskit_error(self):
        err = HealthCheckError("x")
        assert isinstance(err, ObskitError)


class TestHealthCheckTimeoutError:
    def test_default_code(self):
        err = HealthCheckTimeoutError("timeout")
        assert err.code == "OBSKIT_HEALTH_TIMEOUT"

    def test_is_health_check_error(self):
        err = HealthCheckTimeoutError("timeout")
        assert isinstance(err, HealthCheckError)


class TestHealthCheckFailedError:
    def test_default_code(self):
        err = HealthCheckFailedError("failed")
        assert err.code == "OBSKIT_HEALTH_FAILED"

    def test_is_health_check_error(self):
        err = HealthCheckFailedError("failed")
        assert isinstance(err, HealthCheckError)


# =============================================================================
# Metrics Errors
# =============================================================================


class TestMetricsError:
    def test_default_code(self):
        err = MetricsError("metrics error")
        assert err.code == "OBSKIT_METRICS_ERROR"

    def test_is_obskit_error(self):
        err = MetricsError("x")
        assert isinstance(err, ObskitError)


class TestMetricsQueueFullError:
    def test_default_code(self):
        err = MetricsQueueFullError("queue full")
        assert err.code == "OBSKIT_METRICS_QUEUE_FULL"

    def test_is_metrics_error(self):
        err = MetricsQueueFullError("x")
        assert isinstance(err, MetricsError)


class TestMetricsExportError:
    def test_default_code(self):
        err = MetricsExportError("export failed")
        assert err.code == "OBSKIT_METRICS_EXPORT_ERROR"

    def test_is_metrics_error(self):
        err = MetricsExportError("x")
        assert isinstance(err, MetricsError)


# =============================================================================
# Tracing Errors
# =============================================================================


class TestTracingError:
    def test_default_code(self):
        err = TracingError("tracing error")
        assert err.code == "OBSKIT_TRACE_ERROR"

    def test_is_obskit_error(self):
        err = TracingError("x")
        assert isinstance(err, ObskitError)


class TestTracingExportError:
    def test_default_code(self):
        err = TracingExportError("export failed")
        assert err.code == "OBSKIT_TRACE_EXPORT_ERROR"

    def test_is_tracing_error(self):
        err = TracingExportError("x")
        assert isinstance(err, TracingError)


class TestTracingNotConfiguredError:
    def test_default_code(self):
        err = TracingNotConfiguredError("not configured")
        assert err.code == "OBSKIT_TRACE_NOT_CONFIGURED"

    def test_is_tracing_error(self):
        err = TracingNotConfiguredError("x")
        assert isinstance(err, TracingError)


# =============================================================================
# SLO Errors
# =============================================================================


class TestSLOError:
    def test_default_code(self):
        err = SLOError("slo error")
        assert err.code == "OBSKIT_SLO_ERROR"

    def test_is_obskit_error(self):
        err = SLOError("x")
        assert isinstance(err, ObskitError)


class TestSLONotFoundError:
    def test_default_code(self):
        err = SLONotFoundError("not found")
        assert err.code == "OBSKIT_SLO_NOT_FOUND"

    def test_is_slo_error(self):
        err = SLONotFoundError("x")
        assert isinstance(err, SLOError)


class TestSLOBudgetExhaustedError:
    def test_default_code(self):
        err = SLOBudgetExhaustedError("budget exhausted")
        assert err.code == "OBSKIT_SLO_BUDGET_EXHAUSTED"

    def test_is_slo_error(self):
        err = SLOBudgetExhaustedError("x")
        assert isinstance(err, SLOError)


# =============================================================================
# ERROR_CODES registry and get_error_class
# =============================================================================


class TestErrorRegistry:
    def test_registry_contains_all_codes(self):
        expected_codes = [
            "OBSKIT_UNKNOWN",
            "OBSKIT_CONFIG_ERROR",
            "OBSKIT_CONFIG_FILE_NOT_FOUND",
            "OBSKIT_CONFIG_VALIDATION_ERROR",
            "OBSKIT_CIRCUIT_ERROR",
            "OBSKIT_CIRCUIT_OPEN",
            "OBSKIT_CIRCUIT_HALF_OPEN",
            "OBSKIT_RETRY_EXHAUSTED",
            "OBSKIT_RATE_LIMIT_ERROR",
            "OBSKIT_RATE_LIMIT_EXCEEDED",
            "OBSKIT_HEALTH_ERROR",
            "OBSKIT_HEALTH_TIMEOUT",
            "OBSKIT_HEALTH_FAILED",
            "OBSKIT_METRICS_ERROR",
            "OBSKIT_METRICS_QUEUE_FULL",
            "OBSKIT_METRICS_EXPORT_ERROR",
            "OBSKIT_TRACE_ERROR",
            "OBSKIT_TRACE_EXPORT_ERROR",
            "OBSKIT_TRACE_NOT_CONFIGURED",
            "OBSKIT_SLO_ERROR",
            "OBSKIT_SLO_NOT_FOUND",
            "OBSKIT_SLO_BUDGET_EXHAUSTED",
        ]
        for code in expected_codes:
            assert code in ERROR_CODES, f"Missing error code: {code}"

    def test_get_error_class_known_code(self):
        cls = get_error_class("OBSKIT_CONFIG_ERROR")
        assert cls is ConfigurationError

    def test_get_error_class_unknown_code_returns_base(self):
        cls = get_error_class("NONEXISTENT_CODE")
        assert cls is ObskitError

    def test_get_error_class_circuit_open(self):
        cls = get_error_class("OBSKIT_CIRCUIT_OPEN")
        assert cls is CircuitOpenError

    def test_get_error_class_slo_not_found(self):
        cls = get_error_class("OBSKIT_SLO_NOT_FOUND")
        assert cls is SLONotFoundError

    def test_all_registry_values_are_subclasses_of_obskit_error(self):
        for code, cls in ERROR_CODES.items():
            assert issubclass(cls, ObskitError), f"{code}: {cls} is not a subclass of ObskitError"
