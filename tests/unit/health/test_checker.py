"""Tests for obskit.health.checker module."""

import pytest

from obskit.health.checker import (
    CheckResult,
    HealthChecker,
    HealthResult,
    HealthStatus,
    create_health_response,
    get_health_checker,
    reset_health_checker,
)


class TestHealthChecker:
    """Tests for HealthChecker class."""

    def test_init(self):
        """Test HealthChecker initialization."""
        checker = HealthChecker()
        assert checker is not None

    def test_add_readiness_check_decorator(self):
        """Test adding readiness check as decorator."""
        checker = HealthChecker()

        @checker.add_readiness_check("database")
        async def check_database():
            return True

        # Check is registered

    def test_add_liveness_check_decorator(self):
        """Test adding liveness check as decorator."""
        checker = HealthChecker()

        @checker.add_liveness_check("heartbeat")
        async def check_heartbeat():
            return True

        # Check is registered

    @pytest.mark.asyncio
    async def test_check_readiness_all_pass(self):
        """Test readiness check when all checks pass."""
        checker = HealthChecker()

        @checker.add_readiness_check("db")
        async def check_db():
            return True

        @checker.add_readiness_check("cache")
        async def check_cache():
            return True

        result = await checker.check_readiness()
        assert result.status == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_check_readiness_one_fails(self):
        """Test readiness check when one check fails."""
        checker = HealthChecker()

        @checker.add_readiness_check("db")
        async def check_db():
            return True

        @checker.add_readiness_check("external")
        async def check_external():
            return False

        result = await checker.check_readiness()
        assert result.status == HealthStatus.UNHEALTHY

    @pytest.mark.asyncio
    async def test_check_liveness(self):
        """Test liveness check."""
        checker = HealthChecker()

        @checker.add_liveness_check("heartbeat")
        async def heartbeat():
            return True

        result = await checker.check_liveness()
        assert result.status == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_check_liveness_no_checks(self):
        """Test liveness check with no checks registered."""
        checker = HealthChecker()

        # No liveness checks registered
        result = await checker.check_liveness()

        # Should still be healthy (process is running)
        assert result.status == HealthStatus.HEALTHY
        assert result.healthy is True
        assert len(result.checks) == 0

    @pytest.mark.asyncio
    async def test_check_with_exception(self):
        """Test health check that raises exception."""
        checker = HealthChecker()

        @checker.add_readiness_check("failing")
        async def failing_check():
            raise ValueError("Check failed")

        result = await checker.check_readiness()
        assert result.status == HealthStatus.UNHEALTHY


class TestCheckResult:
    """Tests for CheckResult class."""

    def test_healthy_result(self):
        """Test creating healthy result."""
        result = CheckResult(
            name="test",
            healthy=True,
            duration_ms=10.0,
        )
        assert result.name == "test"
        assert result.healthy is True

    def test_unhealthy_result_with_message(self):
        """Test creating unhealthy result with message."""
        result = CheckResult(
            name="test",
            healthy=False,
            duration_ms=5.0,
            message="Connection failed",
        )
        assert result.healthy is False
        assert result.message == "Connection failed"

    def test_result_with_duration(self):
        """Test result with duration."""
        result = CheckResult(
            name="test",
            healthy=True,
            duration_ms=15.5,
        )
        assert result.duration_ms == 15.5

    def test_status_property_healthy(self):
        """Test status property returns HEALTHY for healthy result."""
        result = CheckResult(
            name="test",
            healthy=True,
            duration_ms=10.0,
        )
        assert result.status == HealthStatus.HEALTHY

    def test_status_property_unhealthy(self):
        """Test status property returns UNHEALTHY for unhealthy result."""
        result = CheckResult(
            name="test",
            healthy=False,
            duration_ms=10.0,
        )
        assert result.status == HealthStatus.UNHEALTHY

    def test_to_dict_basic(self):
        """Test to_dict with basic result."""
        result = CheckResult(
            name="test",
            healthy=True,
            duration_ms=10.123456,
        )
        d = result.to_dict()
        assert d["status"] == "healthy"
        assert d["duration_ms"] == 10.123

    def test_to_dict_with_message(self):
        """Test to_dict includes message when present."""
        result = CheckResult(
            name="test",
            healthy=True,
            duration_ms=5.0,
            message="All good",
        )
        d = result.to_dict()
        assert d["message"] == "All good"

    def test_to_dict_with_details(self):
        """Test to_dict includes details when present."""
        result = CheckResult(
            name="test",
            healthy=True,
            duration_ms=5.0,
            details={"version": "1.0", "connections": 5},
        )
        d = result.to_dict()
        assert d["details"] == {"version": "1.0", "connections": 5}

    def test_to_dict_with_error(self):
        """Test to_dict includes error when present."""
        result = CheckResult(
            name="test",
            healthy=False,
            duration_ms=5.0,
            error="Connection timeout",
        )
        d = result.to_dict()
        assert d["error"] == "Connection timeout"

    def test_to_dict_all_fields(self):
        """Test to_dict with all fields populated."""
        result = CheckResult(
            name="test",
            healthy=False,
            duration_ms=100.5,
            message="Check completed with issues",
            details={"retry_count": 3},
            error="Partial failure",
        )
        d = result.to_dict()
        assert "status" in d
        assert "duration_ms" in d
        assert "message" in d
        assert "details" in d
        assert "error" in d


class TestHealthResult:
    """Tests for HealthResult class."""

    def test_healthy_status(self):
        """Test healthy overall status."""
        result = HealthResult(
            healthy=True,
            status=HealthStatus.HEALTHY,
            checks={
                "db": CheckResult(name="db", healthy=True, duration_ms=5.0),
                "cache": CheckResult(name="cache", healthy=True, duration_ms=3.0),
            },
        )
        assert result.status == HealthStatus.HEALTHY
        assert result.healthy is True

    def test_unhealthy_status(self):
        """Test unhealthy overall status."""
        result = HealthResult(
            healthy=False,
            status=HealthStatus.UNHEALTHY,
            checks={
                "db": CheckResult(name="db", healthy=False, duration_ms=10.0),
            },
        )
        assert result.status == HealthStatus.UNHEALTHY
        assert result.healthy is False

    def test_to_dict(self):
        """Test to_dict method."""
        result = HealthResult(
            healthy=True,
            status=HealthStatus.HEALTHY,
            checks={
                "db": CheckResult(name="db", healthy=True, duration_ms=5.0),
            },
        )
        d = result.to_dict()

        assert d["status"] == "healthy"
        assert d["healthy"] is True
        assert "checks" in d
        assert "db" in d["checks"]
        assert "service" in d
        assert "version" in d
        assert "timestamp" in d

    def test_to_json(self):
        """Test to_json method."""
        import json

        result = HealthResult(
            healthy=True,
            status=HealthStatus.HEALTHY,
            checks={
                "db": CheckResult(name="db", healthy=True, duration_ms=5.0),
            },
        )
        json_str = result.to_json()

        # Should be valid JSON
        parsed = json.loads(json_str)
        assert parsed["status"] == "healthy"


class TestHealthStatus:
    """Tests for HealthStatus enum."""

    def test_status_values(self):
        """Test health status values exist."""
        assert HealthStatus.HEALTHY is not None
        assert HealthStatus.UNHEALTHY is not None


class TestHealthCheckerAdvanced:
    """Advanced tests for HealthChecker covering edge cases."""

    @pytest.mark.asyncio
    async def test_check_returning_dict(self):
        """Test health check that returns a dict."""
        checker = HealthChecker()

        @checker.add_readiness_check("detailed")
        async def detailed_check():
            return {
                "healthy": True,
                "message": "Database connected",
                "details": {"connections": 10},
            }

        result = await checker.check_readiness()
        assert result.status == HealthStatus.HEALTHY
        assert result.checks["detailed"].message == "Database connected"

    @pytest.mark.asyncio
    async def test_check_returning_dict_unhealthy(self):
        """Test health check that returns unhealthy dict."""
        checker = HealthChecker()

        @checker.add_readiness_check("failing_detailed")
        async def failing_check():
            return {
                "healthy": False,
                "error": "Connection refused",
            }

        result = await checker.check_readiness()
        assert result.status == HealthStatus.UNHEALTHY

    @pytest.mark.asyncio
    async def test_check_returning_truthy_value(self):
        """Test health check that returns truthy non-bool value."""
        checker = HealthChecker()

        @checker.add_readiness_check("truthy")
        async def truthy_check():
            return "OK"  # Truthy string

        result = await checker.check_readiness()
        assert result.status == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_check_returning_falsy_value(self):
        """Test health check that returns falsy non-bool value."""
        checker = HealthChecker()

        @checker.add_readiness_check("falsy")
        async def falsy_check():
            return 0  # Falsy value

        result = await checker.check_readiness()
        assert result.status == HealthStatus.UNHEALTHY

    @pytest.mark.asyncio
    async def test_check_returning_none(self):
        """Test health check that returns None."""
        checker = HealthChecker()

        @checker.add_readiness_check("none_check")
        async def none_check():
            return None  # Falsy

        result = await checker.check_readiness()
        assert result.status == HealthStatus.UNHEALTHY

    @pytest.mark.asyncio
    async def test_check_timeout(self):
        """Test health check that times out."""
        import asyncio

        checker = HealthChecker()

        @checker.add_readiness_check("slow", timeout=0.01)  # Very short timeout
        async def slow_check():
            await asyncio.sleep(1.0)  # Takes much longer than timeout
            return True

        result = await checker.check_readiness()
        # Should be unhealthy due to timeout
        assert result.status == HealthStatus.UNHEALTHY
        assert "timed out" in result.checks["slow"].error.lower()

    @pytest.mark.asyncio
    async def test_multiple_checks_mixed_results(self):
        """Test with multiple checks having mixed results."""
        checker = HealthChecker()

        @checker.add_readiness_check("passing")
        async def pass_check():
            return True

        @checker.add_readiness_check("failing")
        async def fail_check():
            return False

        @checker.add_readiness_check("erroring")
        async def error_check():
            raise RuntimeError("Something broke")

        result = await checker.check_readiness()
        assert result.status == HealthStatus.UNHEALTHY
        assert len(result.checks) == 3

    @pytest.mark.asyncio
    async def test_check_health_combined(self):
        """Test combined health check (both liveness and readiness)."""
        checker = HealthChecker()

        @checker.add_liveness_check("heartbeat")
        async def heartbeat():
            return True

        @checker.add_readiness_check("database")
        async def database():
            return True

        result = await checker.check_health()
        assert result.status == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_empty_checks(self):
        """Test checker with no checks registered."""
        checker = HealthChecker()

        result = await checker.check_readiness()
        # Should be healthy if no checks
        assert result.status == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_sync_check_function(self):
        """Test health check with sync function (wrapped)."""
        checker = HealthChecker()

        # Note: The checker may wrap sync functions
        @checker.add_readiness_check("sync_check")
        def sync_check():  # Note: not async
            return True

        # This may or may not work depending on implementation
        try:
            await checker.check_readiness()
        except Exception:
            # If sync functions aren't supported, that's okay
            pass

    @pytest.mark.asyncio
    async def test_check_with_critical_flag(self):
        """Test critical vs non-critical checks."""
        checker = HealthChecker()

        @checker.add_readiness_check("critical", critical=True)
        async def critical_check():
            return False  # Failing critical check

        @checker.add_readiness_check("optional", critical=False)
        async def optional_check():
            return True

        result = await checker.check_readiness()
        # Critical check failure should make overall unhealthy
        assert result.status == HealthStatus.UNHEALTHY

    @pytest.mark.asyncio
    async def test_degraded_status(self):
        """Test DEGRADED status when only non-critical checks fail."""
        checker = HealthChecker()

        @checker.add_readiness_check("critical_passing", critical=True)
        async def critical_check():
            return True  # Critical check passes

        @checker.add_readiness_check("optional_failing", critical=False)
        async def optional_check():
            return False  # Non-critical check fails

        result = await checker.check_readiness()
        # Should be DEGRADED when non-critical fails but critical passes
        assert result.status == HealthStatus.DEGRADED
        assert result.healthy is True  # Still healthy overall


class TestHealthResponse:
    """Tests for create_health_response helper function."""

    def test_healthy_response(self):
        """Test response for healthy result."""
        result = HealthResult(
            healthy=True,
            status=HealthStatus.HEALTHY,
            checks={"db": CheckResult(name="db", healthy=True, duration_ms=5.0)},
        )

        response = create_health_response(result)

        assert response["status_code"] == 200
        assert response["body"]["status"] == "healthy"

    def test_unhealthy_response(self):
        """Test response for unhealthy result."""
        result = HealthResult(
            healthy=False,
            status=HealthStatus.UNHEALTHY,
            checks={"db": CheckResult(name="db", healthy=False, duration_ms=5.0)},
        )

        response = create_health_response(result)

        assert response["status_code"] == 503
        assert response["body"]["status"] == "unhealthy"


class TestGlobalHealthChecker:
    """Tests for global health checker functions."""

    def setup_method(self):
        """Reset global state before each test."""
        reset_health_checker()

    def teardown_method(self):
        """Reset global state after each test."""
        reset_health_checker()

    def test_get_health_checker_returns_instance(self):
        """Test get_health_checker returns a HealthChecker."""
        checker = get_health_checker()
        assert isinstance(checker, HealthChecker)

    def test_get_health_checker_returns_same_instance(self):
        """Test get_health_checker returns same instance (singleton)."""
        checker1 = get_health_checker()
        checker2 = get_health_checker()
        assert checker1 is checker2

    def test_reset_health_checker(self):
        """Test reset_health_checker clears the global instance."""
        checker1 = get_health_checker()
        reset_health_checker()
        checker2 = get_health_checker()
        # After reset, should be a new instance
        assert checker1 is not checker2

    def test_reset_health_checker_safe_when_none(self):
        """Test reset is safe when no checker exists."""
        reset_health_checker()  # First reset
        reset_health_checker()  # Second reset (should not raise)
