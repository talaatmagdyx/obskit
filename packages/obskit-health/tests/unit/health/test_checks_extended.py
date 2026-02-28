"""
Extended tests for obskit.health.checks module.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from obskit.health.checks import (
    create_database_pool_check,
    create_disk_check,
    create_http_check,
    create_memory_check,
    create_redis_check,
    create_redis_cluster_check,
    create_redis_pool_check,
)


# =============================================================================
# create_redis_check Tests
# =============================================================================


class TestCreateRedisCheck:
    @pytest.mark.asyncio
    async def test_sync_redis_success(self):
        redis = MagicMock()
        redis.ping.return_value = True
        # Ensure sync redis detection (no __aenter__)
        del redis.__aenter__
        # patch ping to not have __await__
        check = create_redis_check(redis, timeout=5.0)
        with patch("asyncio.wait_for", new=AsyncMock(return_value=True)):
            result = await check()
        assert result["healthy"] is True
        assert "Redis is connected" in result["message"]

    @pytest.mark.asyncio
    async def test_async_redis_success(self):
        redis = MagicMock()
        redis.__aenter__ = AsyncMock()
        redis.ping = AsyncMock(return_value=True)
        check = create_redis_check(redis, timeout=5.0)
        with patch("asyncio.wait_for", new=AsyncMock(return_value=True)):
            result = await check()
        assert result["healthy"] is True

    @pytest.mark.asyncio
    async def test_redis_ping_failed(self):
        redis = MagicMock()
        redis.__aenter__ = AsyncMock()
        redis.ping = AsyncMock(return_value=False)
        check = create_redis_check(redis)
        with patch("asyncio.wait_for", new=AsyncMock(return_value=False)):
            result = await check()
        assert result["healthy"] is False
        assert "ping failed" in result["message"]

    @pytest.mark.asyncio
    async def test_redis_connection_error(self):
        redis = MagicMock()
        redis.__aenter__ = AsyncMock()
        check = create_redis_check(redis)
        with patch("asyncio.wait_for", new=AsyncMock(side_effect=ConnectionError("refused"))):
            result = await check()
        assert result["healthy"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_redis_timeout_error(self):
        redis = MagicMock()
        redis.__aenter__ = AsyncMock()
        check = create_redis_check(redis, timeout=1.0)
        with patch("asyncio.wait_for", new=AsyncMock(side_effect=TimeoutError())):
            result = await check()
        assert result["healthy"] is False
        assert "timed out" in result["message"]


# =============================================================================
# create_redis_cluster_check Tests
# =============================================================================


class TestCreateRedisClusterCheck:
    @pytest.mark.asyncio
    async def test_sync_cluster_success(self):
        redis = MagicMock()
        del redis.ping.__await__  # Make it sync
        check = create_redis_cluster_check(redis, timeout=5.0)
        with patch("asyncio.wait_for", new=AsyncMock(return_value=True)):
            result = await check()
        assert result["healthy"] is True
        assert "cluster" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_cluster_ping_failed(self):
        redis = MagicMock()
        check = create_redis_cluster_check(redis)
        with patch("asyncio.wait_for", new=AsyncMock(return_value=False)):
            result = await check()
        assert result["healthy"] is False

    @pytest.mark.asyncio
    async def test_cluster_connection_error(self):
        redis = MagicMock()
        check = create_redis_cluster_check(redis)
        with patch("asyncio.wait_for", new=AsyncMock(side_effect=Exception("Cluster down"))):
            result = await check()
        assert result["healthy"] is False
        assert "error" in result


# =============================================================================
# create_memory_check Tests
# =============================================================================


class TestCreateMemoryCheck:
    @pytest.mark.asyncio
    async def test_healthy_memory(self):
        mock_mem = MagicMock()
        mock_mem.percent = 50.0
        mock_mem.available = 4 * 1024 * 1024 * 1024  # 4 GB
        mock_mem.total = 8 * 1024 * 1024 * 1024  # 8 GB
        check = create_memory_check(threshold_percent=90.0)
        with patch("psutil.virtual_memory", return_value=mock_mem):
            result = await check()
        assert result["healthy"] is True
        assert result["usage_percent"] == 50.0

    @pytest.mark.asyncio
    async def test_unhealthy_memory(self):
        mock_mem = MagicMock()
        mock_mem.percent = 95.0
        mock_mem.available = 400 * 1024 * 1024  # 400 MB
        mock_mem.total = 8 * 1024 * 1024 * 1024  # 8 GB
        check = create_memory_check(threshold_percent=90.0)
        with patch("psutil.virtual_memory", return_value=mock_mem):
            result = await check()
        assert result["healthy"] is False

    @pytest.mark.asyncio
    async def test_memory_check_exception(self):
        check = create_memory_check()
        with patch("psutil.virtual_memory", side_effect=Exception("psutil error")):
            result = await check()
        assert result["healthy"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_memory_check_at_threshold_boundary(self):
        """Memory usage exactly at threshold should be unhealthy (not < threshold)."""
        mock_mem = MagicMock()
        mock_mem.percent = 90.0
        mock_mem.available = 0
        mock_mem.total = 100
        check = create_memory_check(threshold_percent=90.0)
        with patch("psutil.virtual_memory", return_value=mock_mem):
            result = await check()
        assert result["healthy"] is False  # 90 < 90 is False

    @pytest.mark.asyncio
    async def test_memory_check_includes_metrics(self):
        mock_mem = MagicMock()
        mock_mem.percent = 60.0
        mock_mem.available = 3 * 1024 * 1024 * 1024
        mock_mem.total = 8 * 1024 * 1024 * 1024
        check = create_memory_check()
        with patch("psutil.virtual_memory", return_value=mock_mem):
            result = await check()
        assert "available_mb" in result
        assert "total_mb" in result
        assert "threshold_percent" in result


# =============================================================================
# create_disk_check Tests
# =============================================================================


class TestCreateDiskCheck:
    @pytest.mark.asyncio
    async def test_healthy_disk(self):
        mock_disk = MagicMock()
        mock_disk.percent = 50.0
        mock_disk.free = 100 * 1024 * 1024 * 1024  # 100 GB
        mock_disk.total = 200 * 1024 * 1024 * 1024  # 200 GB
        check = create_disk_check(path="/", threshold_percent=90.0)
        with patch("psutil.disk_usage", return_value=mock_disk):
            result = await check()
        assert result["healthy"] is True
        assert result["path"] == "/"
        assert result["usage_percent"] == 50.0

    @pytest.mark.asyncio
    async def test_unhealthy_disk(self):
        mock_disk = MagicMock()
        mock_disk.percent = 95.0
        mock_disk.free = 5 * 1024 * 1024 * 1024
        mock_disk.total = 100 * 1024 * 1024 * 1024
        check = create_disk_check(path="/data", threshold_percent=90.0)
        with patch("psutil.disk_usage", return_value=mock_disk):
            result = await check()
        assert result["healthy"] is False

    @pytest.mark.asyncio
    async def test_disk_check_exception(self):
        check = create_disk_check()
        with patch("psutil.disk_usage", side_effect=Exception("No such file")):
            result = await check()
        assert result["healthy"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_disk_check_custom_path(self):
        mock_disk = MagicMock()
        mock_disk.percent = 30.0
        mock_disk.free = 700 * 1024 * 1024 * 1024
        mock_disk.total = 1000 * 1024 * 1024 * 1024
        check = create_disk_check(path="/var/data", threshold_percent=80.0)
        with patch("psutil.disk_usage", return_value=mock_disk) as mock_usage:
            result = await check()
        mock_usage.assert_called_once_with("/var/data")
        assert result["path"] == "/var/data"


# =============================================================================
# create_http_check Tests
# =============================================================================


class TestCreateHttpCheck:
    @pytest.mark.asyncio
    async def test_successful_http_check(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        check = create_http_check("http://example.com/health")
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await check()
        assert result["healthy"] is True
        assert result["status_code"] == 200

    @pytest.mark.asyncio
    async def test_wrong_status_code(self):
        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        check = create_http_check("http://example.com/health", expected_status=200)
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await check()
        assert result["healthy"] is False

    @pytest.mark.asyncio
    async def test_http_connection_error(self):
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("Connection refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        check = create_http_check("http://unreachable.example.com")
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await check()
        assert result["healthy"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_http_check_custom_expected_status(self):
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        check = create_http_check("http://api.example.com", expected_status=204)
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await check()
        assert result["healthy"] is True


# =============================================================================
# create_redis_pool_check Tests
# =============================================================================


class TestCreateRedisPoolCheck:
    @pytest.mark.asyncio
    async def test_healthy_pool(self):
        redis = MagicMock()
        pool = MagicMock()
        pool.max_connections = 100
        pool._in_use_connections = set()
        pool._available_connections = list(range(100))
        redis.connection_pool = pool
        redis.ping = MagicMock(return_value=True)

        check = create_redis_pool_check(redis, max_connections_threshold=0.9)
        with patch("asyncio.wait_for", new=AsyncMock(return_value=True)):
            result = await check()
        assert result["healthy"] is True

    @pytest.mark.asyncio
    async def test_no_connection_pool(self):
        redis = MagicMock()
        redis.connection_pool = None
        check = create_redis_pool_check(redis)
        result = await check()
        assert result["healthy"] is True
        assert "single connection mode" in result["message"]

    @pytest.mark.asyncio
    async def test_saturated_pool(self):
        redis = MagicMock()
        pool = MagicMock()
        pool.max_connections = 100
        pool._in_use_connections = set(range(95))  # 95 out of 100 = 95% used
        pool._available_connections = list(range(5))
        redis.connection_pool = pool

        check = create_redis_pool_check(redis, max_connections_threshold=0.8)
        with patch("asyncio.wait_for", new=AsyncMock(return_value=True)):
            result = await check()
        assert result["healthy"] is False

    @pytest.mark.asyncio
    async def test_pool_check_redis_unreachable(self):
        redis = MagicMock()
        pool = MagicMock()
        pool.max_connections = 10
        pool._in_use_connections = set()
        pool._available_connections = list(range(10))
        redis.connection_pool = pool

        check = create_redis_pool_check(redis)
        with patch("asyncio.wait_for", new=AsyncMock(side_effect=Exception("connection refused"))):
            result = await check()
        assert result["healthy"] is False

    @pytest.mark.asyncio
    async def test_pool_with_created_connections_attr(self):
        redis = MagicMock()
        pool = MagicMock(spec=["max_connections", "_created_connections"])
        pool.max_connections = 20
        pool._created_connections = 5

        redis.connection_pool = pool

        check = create_redis_pool_check(redis)
        with patch("asyncio.wait_for", new=AsyncMock(return_value=True)):
            result = await check()
        assert "pool_utilization" in result

    @pytest.mark.asyncio
    async def test_pool_check_exception(self):
        redis = MagicMock()
        redis.connection_pool = MagicMock()
        # Raise exception accessing pool attributes
        type(redis.connection_pool).max_connections = property(lambda self: (_ for _ in ()).throw(Exception("pool error")))

        check = create_redis_pool_check(redis)
        result = await check()
        assert result["healthy"] is False


# =============================================================================
# create_database_pool_check Tests
# =============================================================================


class TestCreateDatabasePoolCheck:
    @pytest.mark.asyncio
    async def test_healthy_db_pool(self):
        pool = MagicMock()
        pool.size.return_value = 10
        pool.checkedin.return_value = 8
        pool.checkedout.return_value = 2
        pool.overflow.return_value = 0
        pool._max_overflow = 10

        engine = MagicMock()
        engine.pool = pool

        check = create_database_pool_check(engine)
        result = await check()
        assert result["healthy"] is True
        assert "pool_size" in result

    @pytest.mark.asyncio
    async def test_saturated_db_pool(self):
        pool = MagicMock()
        pool.size.return_value = 10
        pool.checkedin.return_value = 2
        pool.checkedout.return_value = 8
        pool.overflow.return_value = 9  # 90% of max_overflow used
        pool._max_overflow = 10

        engine = MagicMock()
        engine.pool = pool

        check = create_database_pool_check(engine, max_overflow_threshold=0.8)
        result = await check()
        assert result["healthy"] is False
        assert "overflow" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_no_pool_attribute(self):
        engine = MagicMock(spec=[])
        del engine.pool

        check = create_database_pool_check(engine)
        result = await check()
        # No 'pool' attribute raises AttributeError
        assert result["healthy"] is True
        assert "not use connection pooling" in result["message"]

    @pytest.mark.asyncio
    async def test_db_pool_exception(self):
        engine = MagicMock()
        pool = MagicMock()
        pool.size.side_effect = Exception("Unexpected DB error")
        engine.pool = pool

        check = create_database_pool_check(engine)
        result = await check()
        assert result["healthy"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_zero_max_overflow(self):
        pool = MagicMock()
        pool.size.return_value = 5
        pool.checkedin.return_value = 3
        pool.checkedout.return_value = 2
        pool.overflow.return_value = 0
        pool._max_overflow = 0  # No overflow allowed

        engine = MagicMock()
        engine.pool = pool

        check = create_database_pool_check(engine)
        result = await check()
        assert result["healthy"] is True
