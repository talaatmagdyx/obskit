"""Unit tests for dependency health aggregator."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from obskit.health.aggregator import (
    AggregatedHealth,
    DependencyHealth,
    DependencyHealthAggregator,
    DependencyType,
    HealthStatus,
    check_http,
)


class TestHealthStatus:
    """Tests for HealthStatus enum."""

    def test_values(self):
        """Test enum values exist."""
        assert HealthStatus.HEALTHY.value == "healthy"
        assert HealthStatus.DEGRADED.value == "degraded"
        assert HealthStatus.UNHEALTHY.value == "unhealthy"
        assert HealthStatus.UNKNOWN.value == "unknown"


class TestDependencyType:
    """Tests for DependencyType enum."""

    def test_values(self):
        """Test enum values exist."""
        assert DependencyType.DATABASE.value == "database"
        assert DependencyType.CACHE.value == "cache"
        assert DependencyType.QUEUE.value == "queue"
        assert DependencyType.API.value == "api"
        assert DependencyType.STORAGE.value == "storage"
        assert DependencyType.CUSTOM.value == "custom"


class TestDependencyHealth:
    """Tests for DependencyHealth dataclass."""

    def test_init_defaults(self):
        """Test default values."""
        health = DependencyHealth(name="test", healthy=True)
        assert health.name == "test"
        assert health.healthy is True
        assert health.status == HealthStatus.UNKNOWN
        assert health.latency_ms is None
        assert health.error is None
        assert health.details == {}

    def test_to_dict(self):
        """Test conversion to dictionary."""
        health = DependencyHealth(
            name="postgres",
            healthy=True,
            status=HealthStatus.HEALTHY,
            latency_ms=15.5,
            details={"version": "14.0"},
        )

        data = health.to_dict()

        assert data["name"] == "postgres"
        assert data["healthy"] is True
        assert data["status"] == "healthy"
        assert data["latency_ms"] == pytest.approx(15.5)
        assert data["details"]["version"] == "14.0"


class TestAggregatedHealth:
    """Tests for AggregatedHealth dataclass."""

    def test_init(self):
        """Test initialization."""
        deps = {
            "postgres": DependencyHealth(name="postgres", healthy=True),
            "redis": DependencyHealth(name="redis", healthy=True),
        }

        aggregated = AggregatedHealth(
            healthy=True,
            status=HealthStatus.HEALTHY,
            dependencies=deps,
            healthy_count=2,
            unhealthy_count=0,
            degraded_count=0,
            total_latency_ms=25.0,
        )

        assert aggregated.healthy is True
        assert len(aggregated.dependencies) == 2

    def test_to_dict(self):
        """Test conversion to dictionary."""
        deps = {"postgres": DependencyHealth(name="postgres", healthy=True)}

        aggregated = AggregatedHealth(
            healthy=True,
            status=HealthStatus.HEALTHY,
            dependencies=deps,
            healthy_count=1,
            unhealthy_count=0,
            degraded_count=0,
            total_latency_ms=15.0,
        )

        data = aggregated.to_dict()

        assert data["healthy"] is True
        assert data["status"] == "healthy"
        assert "postgres" in data["dependencies"]


class TestDependencyHealthAggregator:
    """Tests for DependencyHealthAggregator class."""

    def test_init_defaults(self):
        """Test default initialization."""
        aggregator = DependencyHealthAggregator()
        assert aggregator.service_name == "default"
        assert aggregator.timeout_seconds == pytest.approx(5.0)
        assert aggregator.cache_seconds == pytest.approx(5.0)

    def test_init_with_options(self):
        """Test initialization with options."""
        aggregator = DependencyHealthAggregator(
            service_name="my-service",
            timeout_seconds=10.0,
            cache_seconds=30.0,
            critical_dependencies=["postgres"],
        )

        assert aggregator.service_name == "my-service"
        assert aggregator.timeout_seconds == pytest.approx(10.0)
        assert "postgres" in aggregator.critical_dependencies

    def test_add_dependency(self):
        """Test adding a dependency."""
        aggregator = DependencyHealthAggregator()

        async def check_db():  # NOSONAR
            return True

        aggregator.add_dependency(
            name="postgres", check_func=check_db, type=DependencyType.DATABASE, critical=True
        )

        assert "postgres" in aggregator._dependencies
        assert "postgres" in aggregator.critical_dependencies

    def test_remove_dependency(self):
        """Test removing a dependency."""
        aggregator = DependencyHealthAggregator()

        async def check_db():  # NOSONAR
            return True

        aggregator.add_dependency("postgres", check_db)
        aggregator.remove_dependency("postgres")

        assert "postgres" not in aggregator._dependencies

    @pytest.mark.asyncio
    async def test_check_healthy_dependency(self):
        """Test checking a healthy dependency."""
        aggregator = DependencyHealthAggregator()

        async def check_healthy():  # NOSONAR
            return True

        aggregator.add_dependency("healthy_dep", check_healthy)

        health = await aggregator.check("healthy_dep")

        assert health.healthy is True
        assert health.status == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_check_unhealthy_dependency(self):
        """Test checking an unhealthy dependency."""
        aggregator = DependencyHealthAggregator()

        async def check_unhealthy():  # NOSONAR
            return False

        aggregator.add_dependency("unhealthy_dep", check_unhealthy)

        health = await aggregator.check("unhealthy_dep")

        assert health.healthy is False
        assert health.status == HealthStatus.UNHEALTHY

    @pytest.mark.asyncio
    async def test_check_dependency_with_dict_result(self):
        """Test checking dependency returning dict result."""
        aggregator = DependencyHealthAggregator()

        async def check_with_details():  # NOSONAR
            return {"healthy": True, "status": "healthy", "details": {"connections": 5}}

        aggregator.add_dependency("detailed_dep", check_with_details)

        health = await aggregator.check("detailed_dep")

        assert health.healthy is True
        assert health.details["connections"] == 5

    @pytest.mark.asyncio
    async def test_check_dependency_timeout(self):
        """Test dependency check timeout."""
        aggregator = DependencyHealthAggregator(timeout_seconds=0.1)

        async def slow_check():
            await asyncio.sleep(1.0)
            return True

        aggregator.add_dependency("slow_dep", slow_check)

        health = await aggregator.check("slow_dep", use_cache=False)

        assert health.healthy is False
        assert "timed out" in health.error.lower()

    @pytest.mark.asyncio
    async def test_check_dependency_exception(self):
        """Test dependency check handles exceptions."""
        aggregator = DependencyHealthAggregator()

        async def failing_check():
            raise ConnectionError("Connection refused")

        aggregator.add_dependency("failing_dep", failing_check)

        health = await aggregator.check("failing_dep")

        assert health.healthy is False
        assert "Connection refused" in health.error

    @pytest.mark.asyncio
    async def test_check_nonexistent_dependency(self):
        """Test checking a non-existent dependency."""
        aggregator = DependencyHealthAggregator()

        health = await aggregator.check("nonexistent")

        assert health.healthy is False
        assert "not registered" in health.error.lower()

    @pytest.mark.asyncio
    async def test_check_uses_cache(self):
        """Test check uses cached results."""
        aggregator = DependencyHealthAggregator(cache_seconds=60)
        call_count = 0

        async def counting_check():  # NOSONAR
            nonlocal call_count
            call_count += 1
            return True

        aggregator.add_dependency("cached_dep", counting_check)

        await aggregator.check("cached_dep")
        await aggregator.check("cached_dep")
        await aggregator.check("cached_dep")

        # Should only call once due to caching
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_check_all(self):
        """Test checking all dependencies."""
        aggregator = DependencyHealthAggregator()

        async def healthy_check():  # NOSONAR
            return True

        async def unhealthy_check():  # NOSONAR
            return False

        aggregator.add_dependency("dep1", healthy_check)
        aggregator.add_dependency("dep2", unhealthy_check)

        result = await aggregator.check_all()

        assert isinstance(result, AggregatedHealth)
        assert result.healthy_count == 1
        assert result.unhealthy_count == 1

    @pytest.mark.asyncio
    async def test_check_all_critical_healthy(self):
        """Test overall health when critical deps are healthy."""
        aggregator = DependencyHealthAggregator(critical_dependencies=["postgres"])

        async def healthy():  # NOSONAR
            return True

        async def unhealthy():  # NOSONAR
            return False

        aggregator.add_dependency("postgres", healthy, critical=True)
        aggregator.add_dependency("cache", unhealthy)

        result = await aggregator.check_all()

        # Overall healthy because critical (postgres) is healthy
        assert result.healthy is True
        assert result.status == HealthStatus.DEGRADED

    @pytest.mark.asyncio
    async def test_check_all_critical_unhealthy(self):
        """Test overall health when critical deps are unhealthy."""
        aggregator = DependencyHealthAggregator(critical_dependencies=["postgres"])

        async def unhealthy():  # NOSONAR
            return False

        aggregator.add_dependency("postgres", unhealthy, critical=True)

        result = await aggregator.check_all()

        # Overall unhealthy because critical is unhealthy
        assert result.healthy is False
        assert result.status == HealthStatus.UNHEALTHY

    @pytest.mark.asyncio
    async def test_wait_for_healthy(self):
        """Test waiting for dependencies to become healthy."""
        aggregator = DependencyHealthAggregator()
        healthy_after = 2
        call_count = 0

        async def eventually_healthy():  # NOSONAR
            nonlocal call_count
            call_count += 1
            return call_count >= healthy_after

        aggregator.add_dependency("dep", eventually_healthy, critical=True)

        result = await aggregator.wait_for_healthy(timeout_seconds=5.0, check_interval=0.1)

        assert result is True
        assert call_count >= healthy_after

    @pytest.mark.asyncio
    async def test_wait_for_healthy_timeout(self):
        """Test wait_for_healthy times out."""
        aggregator = DependencyHealthAggregator()

        async def always_unhealthy():  # NOSONAR
            return False

        aggregator.add_dependency("dep", always_unhealthy, critical=True)

        result = await aggregator.wait_for_healthy(timeout_seconds=0.3, check_interval=0.1)

        assert result is False

    def test_get_cached_health(self):
        """Test getting cached health result."""
        aggregator = DependencyHealthAggregator()

        # Initially None
        assert aggregator.get_cached_health() is None


class TestCheckHttp:
    """Tests for check_http helper function."""

    @pytest.mark.asyncio
    async def test_check_http_success(self):
        """Test successful HTTP check."""
        mock_response = MagicMock()
        mock_response.status = 200

        # session.get(url) is used as `async with session.get(...) as response:`
        # so its return value must be an async context manager.
        mock_get_ctx = MagicMock()
        mock_get_ctx.__aenter__ = AsyncMock(return_value=mock_response)
        mock_get_ctx.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.get.return_value = mock_get_ctx

        # aiohttp.ClientSession() is used as `async with aiohttp.ClientSession() as session:`
        mock_session_ctx = MagicMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=mock_session_ctx):
            result = await check_http("http://example.com/health")

        assert result["healthy"] is True
        assert result["details"]["status_code"] == 200

    @pytest.mark.asyncio
    async def test_check_http_failure(self):
        """Test failed HTTP check."""
        mock_session = MagicMock()
        mock_session.get.side_effect = Exception("Connection refused")

        mock_session_ctx = MagicMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=mock_session_ctx):
            result = await check_http("http://example.com/health")

        assert result["healthy"] is False
        assert "Connection refused" in result["error"]
