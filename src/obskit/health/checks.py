"""
Built-in Health Checks
======================

This module provides pre-built health check functions for system-level
resources that have no pre-configured client.

Available Checks
----------------
- ``create_memory_check``: Memory utilization check
- ``create_disk_check``: Disk space check
- ``create_http_check``: HTTP endpoint reachability check

For dependency checks (Redis, Postgres, RabbitMQ, etc.) pass a plain
callable directly to ``HealthCheck`` — the caller already owns the client::

    HealthCheck(name="redis",    check=lambda: redis_client.ping())
    HealthCheck(name="postgres", check=lambda: db.execute("SELECT 1"))

Example - Memory Health Check
-----------------------------
.. code-block:: python

    from obskit.health.checks import create_memory_check

    # Fail if memory usage > 90%
    memory_check = create_memory_check(threshold_percent=90)
    checker.add_liveness_check("memory", memory_check)
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any


def create_memory_check(
    threshold_percent: float = 90.0,
) -> Callable[[], Awaitable[bool | dict[str, Any]]]:
    """
    Create a memory utilization health check.

    Parameters
    ----------
    threshold_percent : float
        Maximum memory usage percentage (0-100).
        Default: 90%

    Returns
    -------
    Callable
        Health check function.

    Example
    -------
    >>> from obskit.health.checks import create_memory_check
    >>>
    >>> # Fail if memory > 85%
    >>> memory_check = create_memory_check(threshold_percent=85)
    >>> checker.add_liveness_check("memory", memory_check)
    """

    async def check() -> bool | dict[str, Any]:  # NOSONAR
        try:
            import psutil

            mem = psutil.virtual_memory()
            usage_percent = mem.percent

            healthy = usage_percent < threshold_percent
            return {
                "healthy": healthy,
                "message": f"Memory: {usage_percent:.1f}% (threshold: {threshold_percent}%)",
                "usage_percent": usage_percent,
                "threshold_percent": threshold_percent,
                "available_mb": mem.available / (1024 * 1024),
                "total_mb": mem.total / (1024 * 1024),
            }

        except ImportError:  # pragma: no cover
            return {
                "healthy": True,
                "message": "psutil not installed, skipping memory check",
            }
        except Exception as e:
            return {
                "healthy": False,
                "message": f"Memory check failed: {type(e).__name__}",
                "error": str(e),
            }

    return check


def create_disk_check(
    path: str = "/",
    threshold_percent: float = 90.0,
) -> Callable[[], Awaitable[bool | dict[str, Any]]]:
    """
    Create a disk space health check.

    Parameters
    ----------
    path : str
        Path to check disk usage for.
        Default: "/" (root filesystem)
    threshold_percent : float
        Maximum disk usage percentage (0-100).
        Default: 90%

    Returns
    -------
    Callable
        Health check function.

    Example
    -------
    >>> from obskit.health.checks import create_disk_check
    >>>
    >>> # Check /data volume
    >>> disk_check = create_disk_check(path="/data", threshold_percent=80)
    >>> checker.add_readiness_check("disk", disk_check)
    """

    async def check() -> bool | dict[str, Any]:  # NOSONAR
        try:
            import psutil

            disk = psutil.disk_usage(path)
            usage_percent = disk.percent

            healthy = usage_percent < threshold_percent
            return {
                "healthy": healthy,
                "message": f"Disk ({path}): {usage_percent:.1f}% (threshold: {threshold_percent}%)",
                "path": path,
                "usage_percent": usage_percent,
                "threshold_percent": threshold_percent,
                "free_gb": disk.free / (1024 * 1024 * 1024),
                "total_gb": disk.total / (1024 * 1024 * 1024),
            }

        except ImportError:  # pragma: no cover
            return {
                "healthy": True,
                "message": "psutil not installed, skipping disk check",
            }
        except Exception as e:
            return {
                "healthy": False,
                "message": f"Disk check failed: {type(e).__name__}",
                "error": str(e),
            }

    return check


def create_http_check(
    url: str,
    timeout: float = 5.0,
    expected_status: int = 200,
) -> Callable[[], Awaitable[bool | dict[str, Any]]]:
    """
    Create an HTTP endpoint health check.

    Parameters
    ----------
    url : str
        URL to check.
    timeout : float
        Request timeout in seconds.
    expected_status : int
        Expected HTTP status code.

    Returns
    -------
    Callable
        Health check function.

    Example
    -------
    >>> from obskit.health.checks import create_http_check
    >>>
    >>> # Check external API
    >>> api_check = create_http_check(
    ...     url="https://api.example.com/health",
    ...     timeout=3.0,
    ... )
    >>> checker.add_readiness_check("external_api", api_check)
    """

    async def check() -> bool | dict[str, Any]:
        try:
            import httpx

            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(url)

                healthy = response.status_code == expected_status
                return {
                    "healthy": healthy,
                    "message": f"HTTP {response.status_code} from {url}",
                    "url": url,
                    "status_code": response.status_code,
                    "expected_status": expected_status,
                }

        except ImportError:  # pragma: no cover
            return {
                "healthy": False,
                "message": "httpx not installed",
            }
        except Exception as e:
            return {
                "healthy": False,
                "message": f"HTTP check failed: {type(e).__name__}",
                "url": url,
                "error": str(e),
            }

    return check


__all__ = [
    "create_memory_check",
    "create_disk_check",
    "create_http_check",
]
