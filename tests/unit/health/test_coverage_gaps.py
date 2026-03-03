"""
Targeted tests to achieve 100% line/branch coverage for obskit-health.
"""
from __future__ import annotations

import asyncio
import sys
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from obskit.health.aggregator import (
    AggregatedHealth,
    DependencyHealth,
    DependencyHealthAggregator,
    DependencyType,
    HealthStatus,
    check_postgres,
    check_rabbitmq,
    check_redis,
)


def make_async_redis_mock(return_value=True):
    """Create a redis mock whose .ping has __await__ so is_async=True."""
    redis = MagicMock()
    redis.ping.__await__ = True  # is_async check in checks.py
    return redis


# =============================================================================
# aggregator.py — lines 199->exit, 203, 227->230, 244-245, 264-265, 297->300,
#                 339-340, 427-435, 440-448, 453-460
# =============================================================================


class TestAggregatorMissingBranches:

    def test_remove_dependency_not_exists(self):
        """
        Branch 199->exit: 'if name in self._dependencies:' is False.
        """
        aggregator = DependencyHealthAggregator()
        aggregator.remove_dependency("nonexistent_dep")  # Should not raise

    def test_remove_dependency_with_cached_health(self):
        """
        Line 203: Cached health is also removed when dependency is removed.
        """
        aggregator = DependencyHealthAggregator()

        async def check_func():  # NOSONAR
            return True

        aggregator.add_dependency("cached_dep_x", check_func)
        aggregator._cached_health["cached_dep_x"] = DependencyHealth(
            name="cached_dep_x", healthy=True
        )
        aggregator.remove_dependency("cached_dep_x")
        assert "cached_dep_x" not in aggregator._dependencies
        assert "cached_dep_x" not in aggregator._cached_health

    @pytest.mark.asyncio
    async def test_check_with_expired_cache(self):
        """
        Branch 227->230: Cache exists but is expired. Check re-runs.
        """
        aggregator = DependencyHealthAggregator(cache_seconds=100)
        call_count = [0]

        async def counting_check():  # NOSONAR
            call_count[0] += 1
            return True

        aggregator.add_dependency("expire_dep", counting_check)

        await aggregator.check("expire_dep")
        assert call_count[0] == 1

        # Expire the cache
        aggregator._cached_health["expire_dep"].last_check = time.time() - 200

        await aggregator.check("expire_dep")
        assert call_count[0] == 2

    @pytest.mark.asyncio
    async def test_check_sync_function_runs_in_executor(self):
        """
        Lines 244-245: Sync check function runs in executor.
        """
        aggregator = DependencyHealthAggregator()

        def sync_check():
            return True

        aggregator.add_dependency("sync_dep", sync_check)
        health = await aggregator.check("sync_dep")
        assert health.healthy is True

    @pytest.mark.asyncio
    async def test_check_result_not_bool_not_dict_truthy(self):
        """
        Lines 264-265: Result is neither bool nor dict — truthy.
        """
        aggregator = DependencyHealthAggregator()

        async def string_check():  # NOSONAR
            return "OK"

        aggregator.add_dependency("string_dep", string_check)
        health = await aggregator.check("string_dep")
        assert health.healthy is True
        assert health.status == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_check_result_not_bool_not_dict_falsy(self):
        """
        Lines 264-265: Result is neither bool nor dict — falsy.
        """
        aggregator = DependencyHealthAggregator()

        async def none_check():  # NOSONAR
            return None

        aggregator.add_dependency("none_dep", none_check)
        health = await aggregator.check("none_dep")
        assert health.healthy is False
        assert health.status == HealthStatus.UNHEALTHY

    @pytest.mark.asyncio
    async def test_check_zero_latency_skips_metric(self):
        """
        Branch 297->300: health.latency_ms is 0 (falsy) -> DEPENDENCY_LATENCY not set.
        We mock time.time() to return same value before and after check, giving latency=0.
        """
        aggregator = DependencyHealthAggregator()

        async def fast_check():  # NOSONAR
            return True

        aggregator.add_dependency("zero_lat_dep", fast_check)

        # Patch time.time to return the same value each call -> latency = 0.0
        with patch("obskit.health.aggregator.time") as mock_time:
            mock_time.time.return_value = 1000.0
            health = await aggregator.check("zero_lat_dep")

        # latency_ms = 0.0 which is falsy -> branch 297->300
        assert health.latency_ms == pytest.approx(0.0)

    @pytest.mark.asyncio
    async def test_check_all_all_healthy(self):
        """
        Lines 338-340: critical_healthy=True AND unhealthy_count=0 -> HEALTHY.
        """
        aggregator = DependencyHealthAggregator(critical_dependencies=["dep1"])

        async def healthy():  # NOSONAR
            return True

        aggregator.add_dependency("dep1", healthy, critical=True)
        aggregator.add_dependency("dep2", healthy)

        result = await aggregator.check_all()
        assert result.healthy is True
        assert result.status == HealthStatus.HEALTHY


class TestCheckPostgres:

    @pytest.mark.asyncio
    async def test_check_postgres_success(self):
        """Lines 427-433: Success path with mocked asyncpg."""
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=1)
        mock_conn.close = AsyncMock()

        mock_asyncpg = MagicMock()
        mock_asyncpg.connect = AsyncMock(return_value=mock_conn)

        with patch.dict(sys.modules, {"asyncpg": mock_asyncpg}):
            result = await check_postgres("postgresql://localhost/test")

        assert result["healthy"] is True
        assert result["details"]["connected"] is True

    @pytest.mark.asyncio
    async def test_check_postgres_failure(self):
        """Lines 434-435: Exception path."""
        mock_asyncpg = MagicMock()
        mock_asyncpg.connect = AsyncMock(side_effect=Exception("Connection refused"))

        with patch.dict(sys.modules, {"asyncpg": mock_asyncpg}):
            result = await check_postgres("postgresql://localhost/test")

        assert result["healthy"] is False
        assert "error" in result


class TestCheckRedis:

    @pytest.mark.asyncio
    async def test_check_redis_success(self):
        """Lines 440-446: Success path with mocked aioredis."""
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(return_value=True)
        mock_redis.close = AsyncMock()

        mock_aioredis = MagicMock()
        mock_aioredis.from_url = AsyncMock(return_value=mock_redis)

        with patch.dict(sys.modules, {"aioredis": mock_aioredis}):
            result = await check_redis("localhost", 6379)

        assert result["healthy"] is True
        assert result["details"]["connected"] is True

    @pytest.mark.asyncio
    async def test_check_redis_failure(self):
        """Lines 447-448: Exception path."""
        mock_aioredis = MagicMock()
        mock_aioredis.from_url = AsyncMock(side_effect=Exception("Redis failed"))

        with patch.dict(sys.modules, {"aioredis": mock_aioredis}):
            result = await check_redis("localhost")

        assert result["healthy"] is False
        assert "error" in result


class TestCheckRabbitMQ:

    @pytest.mark.asyncio
    async def test_check_rabbitmq_success(self):
        """Lines 453-458: Success path with mocked aio_pika."""
        mock_conn = AsyncMock()
        mock_conn.close = AsyncMock()

        mock_aio_pika = MagicMock()
        mock_aio_pika.connect_robust = AsyncMock(return_value=mock_conn)

        with patch.dict(sys.modules, {"aio_pika": mock_aio_pika}):
            result = await check_rabbitmq("amqp://localhost")

        assert result["healthy"] is True
        assert result["details"]["connected"] is True

    @pytest.mark.asyncio
    async def test_check_rabbitmq_failure(self):
        """Lines 459-460: Exception path."""
        mock_aio_pika = MagicMock()
        mock_aio_pika.connect_robust = AsyncMock(side_effect=Exception("Connection refused"))

        with patch.dict(sys.modules, {"aio_pika": mock_aio_pika}):
            result = await check_rabbitmq("amqp://localhost")

        assert result["healthy"] is False
        assert "error" in result


# =============================================================================
# checks.py — lines 159, 170->186, 172, 469->473, 491
# =============================================================================


class TestServerMissingBranches:

    def setup_method(self):
        from obskit.health.server import stop_health_server
        stop_health_server()

    def teardown_method(self):
        from obskit.health.server import stop_health_server
        stop_health_server()

    def test_start_health_server_exception_cleans_up(self):
        """Lines 247-250: Exception during start clears _health_server and re-raises."""
        import obskit.health.server as server_module
        from obskit.health.server import start_health_server

        with patch("obskit.health.server.HTTPServer", side_effect=OSError("Port in use")):
            with pytest.raises(OSError):
                start_health_server(port=19999, host="127.0.0.1")

        assert server_module._health_server is None

    def test_stop_health_server_exception_still_cleans_up(self):
        """Lines 275-276: Exception during shutdown is logged, cleanup still happens."""
        import obskit.health.server as server_module
        from obskit.health.server import stop_health_server

        mock_server = MagicMock()
        mock_server.shutdown.side_effect = RuntimeError("Shutdown failed")
        server_module._health_server = mock_server

        stop_health_server()
        assert server_module._health_server is None

    def test_stop_health_server_thread_join_called(self):
        """Line 271: Thread.join() is called when thread is alive."""
        import obskit.health.server as server_module
        from obskit.health.server import stop_health_server

        mock_server = MagicMock()
        mock_server.shutdown = MagicMock()

        mock_thread = MagicMock()
        mock_thread.is_alive.return_value = True
        mock_thread.join = MagicMock()

        server_module._health_server = mock_server
        server_module._health_server_thread = mock_thread

        stop_health_server()
        mock_thread.join.assert_called_once_with(timeout=5.0)
        assert server_module._health_server is None


# =============================================================================
# slo_check.py — lines 315-316
# =============================================================================


class TestSLOCheckMissingBranches:

    def test_get_slo_health_status_tracker_slos_access_raises(self):
        """
        Lines 315-316: Accessing tracker._slos raises Exception -> slo_names=[].
        """
        from obskit.health.slo_check import get_slo_health_status

        mock_tracker = MagicMock()
        type(mock_tracker)._slos = property(
            lambda self: (_ for _ in ()).throw(Exception("Access denied"))
        )

        with patch("obskit.health.slo_check.get_slo_tracker", return_value=mock_tracker):
            result = get_slo_health_status(slo_names=None)

        assert result is not None
        assert isinstance(result, dict)
