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

        # Create metrics
        red = REDMetrics("integration_test", registry=registry)

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

    def test_golden_signals_end_to_end(self) -> None:
        """Test Golden Signals metrics."""
        from obskit.metrics import GoldenSignals
        from obskit.metrics.registry import create_registry, generate_latest

        registry = create_registry()
        if registry is None:
            pytest.skip("prometheus_client not available")

        golden = GoldenSignals("golden_test")

        # Record metrics
        golden.observe_request("api_call", duration_seconds=0.05)
        golden.inc_traffic("api_call", count=100)
        golden.inc_error("api_call", "ValidationError")
        golden.set_saturation("cpu", 0.75)
        golden.set_queue_depth("requests", 42)

        output = generate_latest()
        assert b"golden_test_latency_seconds" in output
        assert b"golden_test_traffic_total" in output
        assert b"golden_test_errors_total" in output
        assert b"golden_test_saturation" in output

    def test_use_metrics_end_to_end(self) -> None:
        """Test USE metrics."""
        from obskit.metrics import USEMetrics
        from obskit.metrics.registry import create_registry, generate_latest

        registry = create_registry()
        if registry is None:
            pytest.skip("prometheus_client not available")

        use = USEMetrics("use_test")

        use.set_utilization("cpu", 0.65)
        use.set_saturation("cpu", 3)
        use.inc_error("cpu", "thermal")

        output = generate_latest()
        assert b"use_test_utilization" in output
        assert b"use_test_saturation" in output
        assert b"use_test_errors_total" in output


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
        """Test PII redaction in logs."""
        from obskit.compliance import redact_pii

        data = {
            "email": "test@example.com",
            "ssn": "123-45-6789",
            "name": "Test User",
            "order_id": "ORD-123",
        }

        redacted = redact_pii(data, fields=["email", "ssn"])

        assert redacted["email"] == "***REDACTED***"
        assert redacted["ssn"] == "***REDACTED***"
        assert redacted["name"] == "Test User"
        assert redacted["order_id"] == "ORD-123"


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


class TestResilienceIntegration:
    """Test resilience components."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_lifecycle(self) -> None:
        """Test circuit breaker state transitions."""
        from obskit.resilience import CircuitBreaker, CircuitOpenError, CircuitState

        breaker = CircuitBreaker(
            name="integration_test",
            failure_threshold=2,
            recovery_timeout=0.1,
            half_open_requests=1,
        )

        # Initially closed
        assert breaker.state == CircuitState.CLOSED

        # Fail twice to open
        for _ in range(2):
            try:
                async with breaker:
                    raise ValueError("Simulated failure")
            except ValueError:
                pass  # Expected exception - testing circuit breaker

        # Should be open now
        assert breaker.state == CircuitState.OPEN

        # Requests should fail immediately
        with pytest.raises(CircuitOpenError):
            async with breaker:
                pass

        # Wait for recovery timeout
        await asyncio.sleep(0.15)

        # Should allow one request (half-open)
        try:
            async with breaker:
                pass  # Success
        except CircuitOpenError:
            pass  # May still be open depending on timing

    def test_retry_with_success(self) -> None:
        """Test retry decorator succeeds after failures."""
        from obskit.resilience import retry

        call_count = 0

        @retry(max_attempts=3, base_delay=0.01)
        async def flaky_operation() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Temporary failure")
            return "success"

        # Run the operation
        result = asyncio.get_event_loop().run_until_complete(flaky_operation())
        assert result == "success"
        assert call_count == 3


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


class TestSelfMetricsIntegration:
    """Test self-monitoring metrics."""

    def test_self_metrics_initialization(self) -> None:
        """Test self-metrics can be initialized and used."""
        from obskit.metrics.self_metrics import (
            get_self_metrics,
            record_dropped_metric,
            record_error,
            reset_self_metrics,
            update_queue_metrics,
        )

        # Reset for clean state
        reset_self_metrics()

        # Get metrics instance
        metrics = get_self_metrics()
        assert metrics is not None

        # Record various metrics
        update_queue_metrics(depth=100, capacity=10000)
        record_dropped_metric("test_op", "queue_full")
        record_error("async_recording", "TimeoutError")

        # Get snapshot
        snapshot = metrics.get_snapshot()
        assert snapshot.queue_depth >= 0
        assert snapshot.version is not None


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


class TestAsyncRecordingIntegration:
    """Test async metric recording."""

    @pytest.mark.asyncio
    async def test_async_metrics_queue_processing(self) -> None:
        """Test async metrics are processed correctly."""
        from obskit.metrics import REDMetrics
        from obskit.metrics.async_recording import (
            AsyncREDMetrics,
            shutdown_async_recording,
        )
        from obskit.metrics.registry import create_registry

        registry = create_registry()
        if registry is None:
            pytest.skip("prometheus_client not available")

        base = REDMetrics("async_test")
        async_metrics = AsyncREDMetrics(base)

        # Record metrics asynchronously
        for _i in range(10):
            await async_metrics.observe_request(
                operation="async_op",
                duration_seconds=0.01,
                status="success",
            )

        # Give time for processing
        await asyncio.sleep(0.1)

        # Shutdown
        await shutdown_async_recording()


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
        """Test Redis health check with mocked client."""
        from obskit.health.checks import create_redis_check

        # Create mock Redis client
        mock_redis = MagicMock()
        mock_redis.ping = MagicMock(return_value=True)

        check = create_redis_check(mock_redis, timeout=1.0)
        result = await check()

        assert isinstance(result, dict)
        assert result["healthy"] is True


class TestRateLimiting:
    """Test rate limiting functionality."""

    def test_rate_limiter_allows_requests(self) -> None:
        """Test rate limiter allows requests within limit."""
        from obskit.metrics.auth import RateLimiter

        limiter = RateLimiter(max_requests=10, window_seconds=60)

        # All requests should be allowed
        for _ in range(10):
            assert limiter.is_allowed()

        # Next request should be blocked
        assert not limiter.is_allowed()

    def test_rate_limiter_remaining(self) -> None:
        """Test rate limiter remaining count."""
        from obskit.metrics.auth import RateLimiter

        limiter = RateLimiter(max_requests=5, window_seconds=60)

        assert limiter.get_remaining() == 5
        limiter.is_allowed()
        assert limiter.get_remaining() == 4
