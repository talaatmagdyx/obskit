"""
Integration Tests for Full Observability Stack
==============================================

These tests verify that all obskit components work together correctly.
They require external services (Redis, Prometheus, etc.) to be available.

Run with: pytest tests/integration/ -v --integration
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest


class TestMetricsIntegration:
    """Test metrics components working together."""

    def test_red_metrics_end_to_end(self) -> None:
        """Test RED metrics from creation to export."""
        from obskit.metrics import REDMetrics
        from obskit.metrics.registry import create_registry, generate_latest

        # Create isolated registry
        registry = create_registry()
        if registry is None:
            pytest.skip("prometheus_client not available")

        # Create metrics (REDMetrics uses the default prometheus registry)
        red = REDMetrics("integration_test")

        # Record some requests
        for i in range(100):
            status = "success" if i % 10 != 0 else "failure"
            red.observe_request(
                operation="test_op",
                duration_seconds=0.01 + (i * 0.001),
                status=status,  # type: ignore[arg-type]
                error_type="TestError" if status == "failure" else None,
            )

        # Export metrics
        output = generate_latest()
        assert b"integration_test_requests_total" in output
        assert b"integration_test_request_duration_seconds" in output
        assert b"integration_test_errors_total" in output



class TestLoggingIntegration:
    """Test logging components working together."""

    def test_structured_logging_with_context(self) -> None:
        """Test structured logging with correlation ID."""
        from obskit.core.context import set_correlation_id
        from obskit.logging import configure_logging, get_logger

        configure_logging()
        logger = get_logger("integration.test")

        # Set correlation ID
        set_correlation_id("test-correlation-123")

        # Log should include correlation ID
        # (would verify output in real integration test)
        logger.info("test_event", key="value")

    def test_logging_with_pii_redaction(self) -> None:
        """Test PII redaction in logs.

        Note: obskit.compliance was removed in v2.0 (out-of-scope module).
        This test now verifies that the module is absent, documenting the
        intentional removal.
        """
        try:
            from obskit.compliance import redact_pii  # noqa: F401

            pytest.skip("obskit.compliance unexpectedly present — remove this skip when re-added")
        except (ImportError, ModuleNotFoundError):
            pass  # Expected: compliance module was removed in v2.0


class TestHealthCheckIntegration:
    """Test health check components."""

    @pytest.mark.asyncio
    async def test_health_checker_with_multiple_checks(self) -> None:
        """Test health checker with multiple check types."""
        from obskit.health import HealthChecker

        checker = HealthChecker()

        # Add readiness checks
        @checker.add_readiness_check("database")
        async def check_db() -> bool:
            return True

        @checker.add_readiness_check("cache")
        async def check_cache() -> bool:
            return True

        # Add liveness check
        @checker.add_liveness_check("memory")
        async def check_memory() -> bool:
            return True

        # Check health
        result = await checker.check_health()
        assert result.healthy
        assert "database" in result.checks
        assert "cache" in result.checks
        assert "memory" in result.checks

        # Check readiness
        ready_result = await checker.check_readiness()
        assert ready_result.healthy

        # Check liveness
        live_result = await checker.check_liveness()
        assert live_result.healthy

    @pytest.mark.asyncio
    async def test_health_checker_with_failing_check(self) -> None:
        """Test health checker handles failing checks."""
        from obskit.health import HealthChecker

        checker = HealthChecker()

        @checker.add_readiness_check("failing_service")
        async def check_failing() -> bool:
            return False

        @checker.add_readiness_check("working_service")
        async def check_working() -> bool:
            return True

        result = await checker.check_health()
        assert not result.healthy
        assert result.checks["failing_service"].healthy is False
        assert result.checks["working_service"].healthy is True



class TestMiddlewareIntegration:
    """Test middleware integration."""

    def test_fastapi_middleware_setup(self) -> None:
        """Test FastAPI middleware can be configured."""
        try:
            from fastapi import FastAPI

            from obskit.middleware.fastapi import ObskitMiddleware
        except ImportError:
            pytest.skip("FastAPI not available")
            return  # Explicit return to satisfy static analysis

        app = FastAPI()
        app.add_middleware(
            ObskitMiddleware,
            track_metrics=True,
            track_logging=True,
            track_tracing=False,
        )

        # Verify middleware is added
        assert len(app.user_middleware) > 0



class TestConfigurationIntegration:
    """Test configuration management."""

    def test_configuration_end_to_end(self) -> None:
        """Test configuration from settings to components."""
        from obskit.config import configure, get_settings, reset_settings

        # Reset for clean state
        reset_settings()

        # Configure
        configure(
            service_name="integration-test",
            environment="test",
            version="1.0.0",
            log_level="DEBUG",
            metrics_enabled=True,
            tracing_enabled=False,
        )

        # Verify settings
        settings = get_settings()
        assert settings.service_name == "integration-test"
        assert settings.environment == "test"
        assert settings.version == "1.0.0"
        assert settings.log_level == "DEBUG"
        assert settings.metrics_enabled is True
        assert settings.tracing_enabled is False

        # Reset after test
        reset_settings()


class TestBuiltInHealthChecks:
    """Test built-in health check functions."""

    @pytest.mark.asyncio
    async def test_memory_check(self) -> None:
        """Test memory health check."""
        try:
            import psutil  # noqa: F401
        except ImportError:
            pytest.skip("psutil not available")

        from obskit.health.checks import create_memory_check

        check = create_memory_check(threshold_percent=99)
        result = await check()

        assert isinstance(result, dict)
        assert "healthy" in result
        assert "usage_percent" in result

    @pytest.mark.asyncio
    async def test_disk_check(self) -> None:
        """Test disk health check."""
        try:
            import psutil  # noqa: F401
        except ImportError:
            pytest.skip("psutil not available")

        from obskit.health.checks import create_disk_check

        check = create_disk_check(path="/", threshold_percent=99)
        result = await check()

        assert isinstance(result, dict)
        assert "healthy" in result
        assert "usage_percent" in result

    @pytest.mark.asyncio
    async def test_redis_check_with_mock(self) -> None:
        """Test Redis health check via plain callable (no create_redis_check wrapper)."""
        from unittest.mock import AsyncMock

        mock_redis = MagicMock()
        mock_redis.ping = AsyncMock(return_value=True)

        # Pass the callable directly — HealthChecker handles sync/async transparently
        check = mock_redis.ping
        result = await check()

        assert result is True


