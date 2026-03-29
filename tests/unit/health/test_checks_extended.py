"""
Extended tests for obskit.health.checks module.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from obskit.health.checks import (
    create_disk_check,
    create_http_check,
    create_memory_check,
)

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
        assert result["usage_percent"] == pytest.approx(50.0)

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
        assert result["usage_percent"] == pytest.approx(50.0)

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
