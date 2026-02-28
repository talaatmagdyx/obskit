"""Tests for built-in health check functions."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestRedisCheck:
    """Tests for Redis health check."""

    @pytest.mark.asyncio
    async def test_redis_check_success_sync_client(self) -> None:
        """Test Redis check with successful sync client via executor."""
        from concurrent.futures import ThreadPoolExecutor

        from obskit.health.checks import create_redis_check

        # Create a real sync mock that will work in executor
        mock_client = MagicMock()
        mock_client.ping = MagicMock(return_value=True)

        # Remove async attributes to ensure sync path
        if hasattr(mock_client, "__aenter__"):
            delattr(mock_client, "__aenter__")

        # Use a real executor
        with ThreadPoolExecutor(max_workers=1):
            # Patch get_event_loop to use a real loop with the executor
            check = create_redis_check(mock_client, timeout=1.0)
            result = await check()

        assert result["healthy"] is True
        assert "message" in result

    @pytest.mark.asyncio
    async def test_redis_check_success_async_client(self) -> None:
        """Test Redis check with successful async client."""
        from obskit.health.checks import create_redis_check

        mock_client = MagicMock()
        mock_client.ping = AsyncMock(return_value=True)

        check = create_redis_check(mock_client, timeout=1.0)
        result = await check()

        assert result["healthy"] is True
        assert "message" in result

    @pytest.mark.asyncio
    async def test_redis_check_failure(self) -> None:
        """Test Redis check with failed ping."""
        from obskit.health.checks import create_redis_check

        mock_client = MagicMock()
        mock_client.ping = MagicMock(return_value=False)

        check = create_redis_check(mock_client, timeout=1.0)
        result = await check()

        assert result["healthy"] is False

    @pytest.mark.asyncio
    async def test_redis_check_exception(self) -> None:
        """Test Redis check with exception."""
        from obskit.health.checks import create_redis_check

        mock_client = MagicMock()
        mock_client.ping = MagicMock(side_effect=ConnectionError("Connection refused"))

        check = create_redis_check(mock_client, timeout=1.0)
        result = await check()

        assert result["healthy"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_redis_check_timeout(self) -> None:
        """Test Redis check with timeout."""

        from obskit.health.checks import create_redis_check

        async def slow_ping() -> bool:
            await asyncio.sleep(10)
            return True

        mock_client = MagicMock()
        mock_client.ping = slow_ping

        check = create_redis_check(mock_client, timeout=0.01)
        result = await check()

        assert result["healthy"] is False
        # Message should contain "timed out"
        assert "timed out" in result["message"].lower()


class TestRedisClusterCheck:
    """Tests for Redis Cluster health check."""

    @pytest.mark.asyncio
    async def test_redis_cluster_check_success(self) -> None:
        """Test Redis cluster check success."""
        from obskit.health.checks import create_redis_cluster_check

        mock_client = MagicMock()
        mock_client.ping = MagicMock(return_value=True)

        check = create_redis_cluster_check(mock_client, timeout=1.0)
        result = await check()

        assert result["healthy"] is True

    @pytest.mark.asyncio
    async def test_redis_cluster_check_with_cluster_info(self) -> None:
        """Test Redis cluster check with cluster info."""
        from obskit.health.checks import create_redis_cluster_check

        mock_client = MagicMock()
        mock_client.ping = MagicMock(return_value=True)
        mock_client.cluster_info = MagicMock(
            return_value={
                "cluster_state": "ok",
                "cluster_slots_assigned": 16384,
            }
        )

        check = create_redis_cluster_check(mock_client, timeout=1.0)
        result = await check()

        assert result["healthy"] is True

    @pytest.mark.asyncio
    async def test_redis_cluster_check_failure(self) -> None:
        """Test Redis cluster check failure."""
        from obskit.health.checks import create_redis_cluster_check

        mock_client = MagicMock()
        mock_client.ping = MagicMock(side_effect=ConnectionError("Connection refused"))

        check = create_redis_cluster_check(mock_client, timeout=1.0)
        result = await check()

        assert result["healthy"] is False


class TestMemoryCheck:
    """Tests for memory health check."""

    @pytest.mark.asyncio
    async def test_memory_check_healthy(self) -> None:
        """Test memory check when healthy."""
        from obskit.health.checks import create_memory_check

        with patch("psutil.virtual_memory") as mock_mem:
            mock_mem.return_value = MagicMock(
                percent=50.0,
                available=8 * 1024 * 1024 * 1024,  # 8 GB
                total=16 * 1024 * 1024 * 1024,  # 16 GB
            )

            check = create_memory_check(threshold_percent=90)
            result = await check()

            assert result["healthy"] is True
            assert result["usage_percent"] == 50.0

    @pytest.mark.asyncio
    async def test_memory_check_unhealthy(self) -> None:
        """Test memory check when unhealthy."""
        from obskit.health.checks import create_memory_check

        with patch("psutil.virtual_memory") as mock_mem:
            mock_mem.return_value = MagicMock(
                percent=95.0,
                available=1 * 1024 * 1024 * 1024,  # 1 GB
                total=16 * 1024 * 1024 * 1024,  # 16 GB
            )

            check = create_memory_check(threshold_percent=90)
            result = await check()

            assert result["healthy"] is False
            assert result["usage_percent"] == 95.0

    @pytest.mark.asyncio
    async def test_memory_check_exception(self) -> None:
        """Test memory check with exception."""
        from obskit.health.checks import create_memory_check

        with patch("psutil.virtual_memory", side_effect=Exception("Error")):
            check = create_memory_check()
            result = await check()

            assert result["healthy"] is False
            assert "error" in result


class TestDiskCheck:
    """Tests for disk health check."""

    @pytest.mark.asyncio
    async def test_disk_check_healthy(self) -> None:
        """Test disk check when healthy."""
        from obskit.health.checks import create_disk_check

        with patch("psutil.disk_usage") as mock_disk:
            mock_disk.return_value = MagicMock(
                percent=50.0,
                free=500 * 1024 * 1024 * 1024,  # 500 GB
                total=1024 * 1024 * 1024 * 1024,  # 1 TB
            )

            check = create_disk_check(path="/", threshold_percent=90)
            result = await check()

            assert result["healthy"] is True
            assert result["path"] == "/"

    @pytest.mark.asyncio
    async def test_disk_check_unhealthy(self) -> None:
        """Test disk check when unhealthy."""
        from obskit.health.checks import create_disk_check

        with patch("psutil.disk_usage") as mock_disk:
            mock_disk.return_value = MagicMock(
                percent=95.0,
                free=50 * 1024 * 1024 * 1024,  # 50 GB
                total=1024 * 1024 * 1024 * 1024,  # 1 TB
            )

            check = create_disk_check(path="/data", threshold_percent=90)
            result = await check()

            assert result["healthy"] is False

    @pytest.mark.asyncio
    async def test_disk_check_exception(self) -> None:
        """Test disk check with exception."""
        from obskit.health.checks import create_disk_check

        with patch("psutil.disk_usage", side_effect=FileNotFoundError("Path not found")):
            check = create_disk_check(path="/nonexistent")
            result = await check()

            assert result["healthy"] is False


class TestHttpCheck:
    """Tests for HTTP health check."""

    @pytest.mark.asyncio
    async def test_http_check_success(self) -> None:
        """Test HTTP check success."""
        from obskit.health.checks import create_http_check

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200

            mock_context = AsyncMock()
            mock_context.__aenter__ = AsyncMock(return_value=mock_context)
            mock_context.__aexit__ = AsyncMock(return_value=None)
            mock_context.get = AsyncMock(return_value=mock_response)

            mock_client.return_value = mock_context

            check = create_http_check("https://example.com/health", timeout=5.0)
            result = await check()

            assert result["healthy"] is True
            assert result["status_code"] == 200

    @pytest.mark.asyncio
    async def test_http_check_wrong_status(self) -> None:
        """Test HTTP check with wrong status code."""
        from obskit.health.checks import create_http_check

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 500

            mock_context = AsyncMock()
            mock_context.__aenter__ = AsyncMock(return_value=mock_context)
            mock_context.__aexit__ = AsyncMock(return_value=None)
            mock_context.get = AsyncMock(return_value=mock_response)

            mock_client.return_value = mock_context

            check = create_http_check(
                "https://example.com/health",
                timeout=5.0,
                expected_status=200,
            )
            result = await check()

            assert result["healthy"] is False

    @pytest.mark.asyncio
    async def test_http_check_exception(self) -> None:
        """Test HTTP check with exception."""
        from obskit.health.checks import create_http_check

        with patch("httpx.AsyncClient") as mock_client:
            mock_context = AsyncMock()
            mock_context.__aenter__ = AsyncMock(return_value=mock_context)
            mock_context.__aexit__ = AsyncMock(return_value=None)
            mock_context.get = AsyncMock(side_effect=ConnectionError("Connection refused"))

            mock_client.return_value = mock_context

            check = create_http_check("https://example.com/health")
            result = await check()

            assert result["healthy"] is False
            assert "error" in result
