"""Tests for obskit.config module."""

from obskit.config import (
    ObskitSettings,
    configure,
    get_settings,
    reset_settings,
    validate_config,
)
import pytest


class TestObskitSettings:
    """Tests for ObskitSettings class."""

    def test_default_values(self):
        """Test default settings values."""
        settings = ObskitSettings()
        assert settings.service_name == "unknown"
        assert settings.environment == "development"
        assert settings.version == "0.0.0"
        assert settings.tracing_enabled is True
        assert settings.metrics_enabled is True
        assert settings.log_level == "INFO"
        assert settings.log_format == "json"

    def test_custom_values(self):
        """Test settings with custom values."""
        settings = ObskitSettings(
            service_name="test-service",
            environment="production",
            version="1.0.0",
            log_level="DEBUG",
        )
        assert settings.service_name == "test-service"
        assert settings.environment == "production"
        assert settings.version == "1.0.0"
        assert settings.log_level == "DEBUG"

    def test_tracing_settings(self):
        """Test tracing configuration."""
        settings = ObskitSettings(
            tracing_enabled=True,
            otlp_endpoint="http://jaeger:4317",
            otlp_insecure=True,
            trace_sample_rate=0.5,
        )
        assert settings.tracing_enabled is True
        assert settings.otlp_endpoint == "http://jaeger:4317"
        assert settings.trace_sample_rate == pytest.approx(0.5)

    def test_metrics_settings(self):
        """Test metrics configuration."""
        settings = ObskitSettings(
            metrics_enabled=True,
            metrics_port=8080,
            metrics_path="/custom-metrics",
        )
        assert settings.metrics_enabled is True
        assert settings.metrics_port == 8080
        assert settings.metrics_path == "/custom-metrics"

    def test_circuit_breaker_settings(self):
        """Test circuit breaker configuration."""
        settings = ObskitSettings(
            circuit_breaker_failure_threshold=10,
            circuit_breaker_recovery_timeout=60.0,
            circuit_breaker_half_open_requests=5,
        )
        assert settings.circuit_breaker_failure_threshold == 10
        assert settings.circuit_breaker_recovery_timeout == pytest.approx(60.0)
        assert settings.circuit_breaker_half_open_requests == 5

    def test_retry_settings(self):
        """Test retry configuration."""
        settings = ObskitSettings(
            retry_max_attempts=5,
            retry_base_delay=2.0,
            retry_max_delay=120.0,
            retry_exponential_base=3.0,
        )
        assert settings.retry_max_attempts == 5
        assert settings.retry_base_delay == pytest.approx(2.0)
        assert settings.retry_max_delay == pytest.approx(120.0)
        assert settings.retry_exponential_base == pytest.approx(3.0)

    def test_rate_limit_settings(self):
        """Test rate limiting configuration."""
        settings = ObskitSettings(
            rate_limit_requests=50,
            rate_limit_window_seconds=30.0,
        )
        assert settings.rate_limit_requests == 50
        assert settings.rate_limit_window_seconds == pytest.approx(30.0)


class TestConfigure:
    """Tests for configure function."""

    def setup_method(self):
        """Reset settings before each test."""
        reset_settings()

    def teardown_method(self):
        """Reset settings after each test."""
        reset_settings()

    def test_configure_basic(self):
        """Test basic configuration."""
        settings = configure(
            service_name="my-service",
            environment="staging",
        )
        assert settings.service_name == "my-service"
        assert settings.environment == "staging"

    def test_configure_returns_settings(self):
        """Test that configure returns settings instance."""
        result = configure(service_name="test")
        assert isinstance(result, ObskitSettings)

    def test_configure_updates_get_settings(self):
        """Test that configure updates get_settings."""
        configure(service_name="updated-service")
        settings = get_settings()
        assert settings.service_name == "updated-service"

    def test_reconfigure(self):
        """Test that calling configure again updates settings."""
        configure(service_name="first")
        configure(service_name="second")
        settings = get_settings()
        assert settings.service_name == "second"


class TestGetSettings:
    """Tests for get_settings function."""

    def setup_method(self):
        """Reset settings before each test."""
        reset_settings()

    def teardown_method(self):
        """Reset settings after each test."""
        reset_settings()

    def test_get_settings_returns_defaults(self):
        """Test that get_settings returns defaults when not configured."""
        settings = get_settings()
        assert settings.service_name == "unknown"

    def test_get_settings_returns_configured(self):
        """Test that get_settings returns configured values."""
        configure(service_name="configured")
        settings = get_settings()
        assert settings.service_name == "configured"

    def test_get_settings_is_cached(self):
        """Test that get_settings returns same instance."""
        settings1 = get_settings()
        settings2 = get_settings()
        assert settings1 is settings2


class TestResetSettings:
    """Tests for reset_settings function."""

    def test_reset_clears_configuration(self):
        """Test that reset_settings clears configuration."""
        configure(service_name="to-be-reset")
        reset_settings()
        settings = get_settings()
        assert settings.service_name == "unknown"


class TestValidateConfig:
    """Tests for validate_config function."""

    def setup_method(self):
        """Reset settings before each test."""
        reset_settings()

    def teardown_method(self):
        """Reset settings after each test."""
        reset_settings()

    def test_validate_default_config_has_warnings(self):
        """Test that default config has warnings."""
        is_valid, errors = validate_config()
        assert not is_valid
        assert any("service_name" in e for e in errors)

    def test_validate_proper_config(self):
        """Test validation of proper configuration."""
        configure(
            service_name="my-service",
            environment="production",
        )
        _, errors = validate_config()
        # May have warnings about otlp_insecure in production
        assert isinstance(errors, list)

    def test_validate_invalid_otlp_endpoint(self):
        """Test validation of invalid OTLP endpoint."""
        configure(
            service_name="test",
            tracing_enabled=True,
            otlp_endpoint="invalid-endpoint",
        )
        is_valid, errors = validate_config()
        assert not is_valid
        assert any("otlp_endpoint" in e for e in errors)

    def test_validate_production_insecure_warning(self):
        """Test warning for insecure OTLP in production."""
        configure(
            service_name="test",
            environment="production",
            tracing_enabled=True,
            otlp_endpoint="http://localhost:4317",
            otlp_insecure=True,
        )
        _, errors = validate_config()
        assert any("insecure" in e.lower() for e in errors)

    def test_validate_nonstandard_environment(self):
        """Non-standard environment names emit a warning but do NOT block validation.

        Teams using 'test', 'qa', 'uat', 'canary', etc. must not be blocked.
        The check was intentionally downgraded from an error to a warning.
        """
        import warnings

        configure(
            service_name="test",
            environment="custom-env",
        )
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            is_valid, errors = validate_config()

        # Config is valid — non-standard env is no longer an error
        assert is_valid
        assert not any("environment" in e for e in errors)
        # A UserWarning mentioning the environment must have been emitted
        assert any("environment" in str(w.message).lower() for w in caught)

    def test_validate_tracing_enabled_no_endpoint(self):
        """Test validation when tracing enabled but no endpoint."""
        configure(
            service_name="test",
            tracing_enabled=True,
            otlp_endpoint="",  # Empty string means no endpoint
        )
        _, errors = validate_config()
        assert any("otlp_endpoint" in e for e in errors)

    def test_validate_metrics_enabled_with_settings(self):
        """Test metrics validation with valid port."""
        configure(
            service_name="test",
            metrics_enabled=True,
            metrics_port=9090,
        )
        _, errors = validate_config()
        # Should not have port errors
        assert not any("metrics_port" in e for e in errors)

    def test_validate_tracing_disabled(self):
        """Test validation when tracing is disabled."""
        configure(
            service_name="test",
            tracing_enabled=False,
        )
        _, errors = validate_config()
        # Should not have tracing errors when disabled
        assert not any("otlp_endpoint" in e for e in errors)

    def test_validate_metrics_disabled(self):
        """Test validation when metrics is disabled."""
        configure(
            service_name="test",
            metrics_enabled=False,
        )
        _, errors = validate_config()
        # Should not have metrics errors when disabled
        assert not any("metrics_port" in e for e in errors)

    def test_validate_fully_configured(self):
        """Test validation of fully valid configuration."""
        configure(
            service_name="my-service",
            environment="production",
            tracing_enabled=True,
            otlp_endpoint="https://collector:4317",
            otlp_insecure=False,
            metrics_enabled=True,
            metrics_port=9090,
            log_level="INFO",
            trace_sample_rate=0.5,
        )
        is_valid, errors = validate_config()
        assert is_valid
        assert len(errors) == 0


class TestConfigureEdgeCases:
    """Tests for configure() edge cases — lines 813, 832."""

    def setup_method(self):
        """Reset settings before each test."""
        from obskit.config import reset_settings

        reset_settings()

    def teardown_method(self):
        """Reset settings after each test."""
        from obskit.config import reset_settings

        reset_settings()

    def test_unknown_setting_raises_value_error(self):
        """configure() raises ValueError for unknown settings (line 813)."""
        import pytest
        from obskit.config import configure

        with pytest.raises(ValueError, match="Unknown obskit settings"):
            configure(this_does_not_exist="value")

    def test_strict_mode_raises_on_invalid_config(self):
        """configure(strict=True) raises ValueError when config is invalid (line 832)."""
        import pytest
        from obskit.config import configure

        # Invalid config: tracing_enabled=True but no endpoint → validation error
        with pytest.raises(ValueError, match="obskit configuration has"):
            configure(
                tracing_enabled=True,
                otlp_endpoint="",  # empty string → invalid
                strict=True,
            )


class TestObskitInitGetattr:
    """Tests for obskit.__init__.__getattr__ lazy imports (lines 51-56)."""

    def test_build_health_router_accessible(self):
        """obskit.build_health_router is lazily accessible via __getattr__."""
        import obskit

        # Access via module __getattr__
        fn = obskit.build_health_router
        assert callable(fn)

    def test_unknown_attribute_raises(self):
        """Accessing an unknown attribute raises AttributeError (line 56)."""
        import obskit
        import pytest

        with pytest.raises(AttributeError, match="has no attribute"):
            _ = obskit.this_does_not_exist_anywhere
