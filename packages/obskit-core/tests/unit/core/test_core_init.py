"""Tests for obskit.core.__init__ lazy loading via __getattr__."""

from __future__ import annotations

import pytest
import obskit.core as core_module


class TestCoreGetattr:
    """Test lazy loading through __getattr__ in obskit.core."""

    def test_lazy_batch_context_batch_job_context(self):
        attr = core_module.__getattr__("batch_job_context")
        from obskit.core.batch_context import batch_job_context
        assert attr is batch_job_context

    def test_lazy_batch_context_capture_context(self):
        attr = core_module.__getattr__("capture_context")
        from obskit.core.batch_context import capture_context
        assert attr is capture_context

    def test_lazy_batch_context_create_task_with_context(self):
        attr = core_module.__getattr__("create_task_with_context")
        from obskit.core.batch_context import create_task_with_context
        assert attr is create_task_with_context

    def test_lazy_batch_context_get_batch_job_context(self):
        attr = core_module.__getattr__("get_batch_job_context")
        from obskit.core.batch_context import get_batch_job_context
        assert attr is get_batch_job_context

    def test_lazy_batch_context_propagate_to_executor(self):
        attr = core_module.__getattr__("propagate_to_executor")
        from obskit.core.batch_context import propagate_to_executor
        assert attr is propagate_to_executor

    def test_lazy_batch_context_propagate_to_task(self):
        attr = core_module.__getattr__("propagate_to_task")
        from obskit.core.batch_context import propagate_to_task
        assert attr is propagate_to_task

    def test_lazy_batch_context_restore_context(self):
        attr = core_module.__getattr__("restore_context")
        from obskit.core.batch_context import restore_context
        assert attr is restore_context

    def test_lazy_deprecation_deprecated(self):
        attr = core_module.__getattr__("deprecated")
        from obskit.core.deprecation import deprecated
        assert attr is deprecated

    def test_lazy_deprecation_deprecated_class(self):
        attr = core_module.__getattr__("deprecated_class")
        from obskit.core.deprecation import deprecated_class
        assert attr is deprecated_class

    def test_lazy_deprecation_deprecated_parameter(self):
        attr = core_module.__getattr__("deprecated_parameter")
        from obskit.core.deprecation import deprecated_parameter
        assert attr is deprecated_parameter

    def test_lazy_deprecation_warn_deprecated(self):
        attr = core_module.__getattr__("warn_deprecated")
        from obskit.core.deprecation import warn_deprecated
        assert attr is warn_deprecated

    def test_lazy_deprecation_obskit_deprecation_warning(self):
        attr = core_module.__getattr__("ObskitDeprecationWarning")
        from obskit.core.deprecation import ObskitDeprecationWarning
        assert attr is ObskitDeprecationWarning

    def test_lazy_errors_obskit_error(self):
        attr = core_module.__getattr__("ObskitError")
        from obskit.core.errors import ObskitError
        assert attr is ObskitError

    def test_lazy_errors_configuration_error(self):
        attr = core_module.__getattr__("ConfigurationError")
        from obskit.core.errors import ConfigurationError
        assert attr is ConfigurationError

    def test_lazy_errors_config_file_not_found(self):
        attr = core_module.__getattr__("ConfigFileNotFoundError")
        from obskit.core.errors import ConfigFileNotFoundError
        assert attr is ConfigFileNotFoundError

    def test_lazy_errors_config_validation_error(self):
        attr = core_module.__getattr__("ConfigValidationError")
        from obskit.core.errors import ConfigValidationError
        assert attr is ConfigValidationError

    def test_lazy_errors_circuit_breaker_error(self):
        attr = core_module.__getattr__("CircuitBreakerError")
        from obskit.core.errors import CircuitBreakerError
        assert attr is CircuitBreakerError

    def test_lazy_errors_circuit_open_error(self):
        attr = core_module.__getattr__("CircuitOpenError")
        from obskit.core.errors import CircuitOpenError
        assert attr is CircuitOpenError

    def test_lazy_errors_retry_error(self):
        attr = core_module.__getattr__("RetryError")
        from obskit.core.errors import RetryError
        assert attr is RetryError

    def test_lazy_errors_rate_limit_error(self):
        attr = core_module.__getattr__("RateLimitError")
        from obskit.core.errors import RateLimitError
        assert attr is RateLimitError

    def test_lazy_errors_rate_limit_exceeded(self):
        attr = core_module.__getattr__("RateLimitExceeded")
        from obskit.core.errors import RateLimitExceeded
        assert attr is RateLimitExceeded

    def test_lazy_errors_health_check_error(self):
        attr = core_module.__getattr__("HealthCheckError")
        from obskit.core.errors import HealthCheckError
        assert attr is HealthCheckError

    def test_lazy_errors_metrics_error(self):
        attr = core_module.__getattr__("MetricsError")
        from obskit.core.errors import MetricsError
        assert attr is MetricsError

    def test_lazy_errors_tracing_error(self):
        attr = core_module.__getattr__("TracingError")
        from obskit.core.errors import TracingError
        assert attr is TracingError

    def test_lazy_errors_slo_error(self):
        attr = core_module.__getattr__("SLOError")
        from obskit.core.errors import SLOError
        assert attr is SLOError

    def test_unknown_attribute_raises_attribute_error(self):
        with pytest.raises(AttributeError, match="module .* has no attribute"):
            core_module.__getattr__("nonexistent_attribute_xyz")

    def test_module_level_access(self):
        _ = core_module.batch_job_context
        _ = core_module.deprecated
        _ = core_module.ObskitError
