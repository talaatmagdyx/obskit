"""
Built-in Health Checks
======================

This module provides pre-built health check functions for common
dependencies and resources.

Available Checks
----------------
- ``check_redis``: Redis connectivity check
- ``check_redis_async``: Async Redis connectivity check
- ``check_memory``: Memory utilization check
- ``check_disk``: Disk space check

Example - Redis Health Check
----------------------------
.. code-block:: python

    from obskit.health import HealthChecker
    from obskit.health.checks import create_redis_check

    checker = HealthChecker()

    # Add Redis health check
    redis_check = create_redis_check(redis_client)
    checker.add_readiness_check("redis", redis_check)

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

from obskit.logging import get_logger

logger = get_logger("obskit.health.checks")


def create_redis_check(
    redis_client: Any,
    timeout: float = 5.0,
) -> Callable[[], Awaitable[bool | dict[str, Any]]]:
    """
    Create a Redis connectivity health check.

    This check pings Redis to verify connectivity. It works with both
    sync (redis.Redis) and async (redis.asyncio.Redis) clients.

    Parameters
    ----------
    redis_client : Any
        Redis client instance (sync or async).
    timeout : float
        Timeout for the ping operation in seconds.

    Returns
    -------
    Callable
        Health check function that returns True if Redis is healthy.

    Example
    -------
    >>> import redis
    >>> from obskit.health import HealthChecker
    >>> from obskit.health.checks import create_redis_check
    >>>
    >>> redis_client = redis.Redis()
    >>> checker = HealthChecker()
    >>>
    >>> redis_check = create_redis_check(redis_client)
    >>> checker.add_readiness_check("redis", redis_check)

    Example - Async Redis
    ---------------------
    >>> import redis.asyncio as aioredis
    >>>
    >>> async_redis = aioredis.Redis()
    >>> redis_check = create_redis_check(async_redis)
    >>> checker.add_readiness_check("redis", redis_check)
    """
    import asyncio

    async def check() -> bool | dict[str, Any]:
        try:
            # Check if client is async
            is_async = hasattr(redis_client, "__aenter__") or hasattr(
                redis_client.ping, "__await__"
            )

            if is_async:
                # Async client
                result = await asyncio.wait_for(redis_client.ping(), timeout=timeout)
            else:
                # Sync client - run in executor
                loop = asyncio.get_event_loop()
                result = await asyncio.wait_for(
                    loop.run_in_executor(None, redis_client.ping),
                    timeout=timeout,
                )

            if result:
                return {"healthy": True, "message": "Redis is connected"}
            return {"healthy": False, "message": "Redis ping failed"}

        except TimeoutError:
            logger.warning("redis_health_check_timeout", timeout=timeout)
            return {"healthy": False, "message": f"Redis ping timed out ({timeout}s)"}
        except Exception as e:
            logger.warning(
                "redis_health_check_failed",
                error=str(e),
                error_type=type(e).__name__,
            )
            return {
                "healthy": False,
                "message": f"Redis error: {type(e).__name__}",
                "error": str(e),
            }

    return check


def create_redis_cluster_check(
    redis_client: Any,
    timeout: float = 5.0,
) -> Callable[[], Awaitable[bool | dict[str, Any]]]:
    """
    Create a Redis Cluster connectivity health check.

    Parameters
    ----------
    redis_client : Any
        Redis cluster client instance.
    timeout : float
        Timeout for the check in seconds.

    Returns
    -------
    Callable
        Health check function.
    """
    import asyncio

    async def check() -> bool | dict[str, Any]:
        try:
            is_async = hasattr(redis_client.ping, "__await__")

            if is_async:
                result = await asyncio.wait_for(redis_client.ping(), timeout=timeout)
            else:
                loop = asyncio.get_event_loop()
                result = await asyncio.wait_for(
                    loop.run_in_executor(None, redis_client.ping),
                    timeout=timeout,
                )

            # Get cluster info if available
            cluster_info = {}
            try:
                if hasattr(redis_client, "cluster_info"):
                    if is_async:
                        info = await redis_client.cluster_info()
                    else:
                        info = await asyncio.get_event_loop().run_in_executor(
                            None, redis_client.cluster_info
                        )
                    cluster_info = {
                        "cluster_state": info.get("cluster_state", "unknown"),
                        "cluster_slots_assigned": info.get("cluster_slots_assigned", 0),
                    }
            except (
                Exception
            ):  # pragma: no cover  # nosec B110 - intentional: cluster info is optional
                pass  # Cluster info retrieval may fail - non-critical

            if result:
                return {
                    "healthy": True,
                    "message": "Redis cluster is connected",
                    **cluster_info,
                }
            return {"healthy": False, "message": "Redis cluster ping failed"}

        except Exception as e:
            return {
                "healthy": False,
                "message": f"Redis cluster error: {type(e).__name__}",
                "error": str(e),
            }

    return check


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

    async def check() -> bool | dict[str, Any]:
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

    async def check() -> bool | dict[str, Any]:
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


def create_redis_pool_check(
    redis_client: Any,
    max_connections_threshold: float = 0.9,
    timeout: float = 5.0,
) -> Callable[[], Awaitable[bool | dict[str, Any]]]:
    """
    Create a Redis connection pool health check.

    This check monitors the Redis connection pool usage to detect
    connection exhaustion before it causes failures.

    Parameters
    ----------
    redis_client : Any
        Redis client instance with a connection pool.
    max_connections_threshold : float
        Threshold for pool usage (0.0-1.0).
        Default: 0.9 (90% - warn before pool is exhausted)
    timeout : float
        Timeout for the check in seconds.

    Returns
    -------
    Callable
        Health check function that returns pool status.

    Example
    -------
    >>> import redis
    >>> from obskit.health.checks import create_redis_pool_check
    >>>
    >>> # Create client with explicit pool size
    >>> redis_client = redis.Redis(
    ...     host="localhost",
    ...     max_connections=100,
    ... )
    >>>
    >>> pool_check = create_redis_pool_check(
    ...     redis_client,
    ...     max_connections_threshold=0.8,  # Alert at 80%
    ... )
    >>> checker.add_readiness_check("redis_pool", pool_check)

    Pool Metrics Returned
    ---------------------
    - ``max_connections``: Maximum pool size
    - ``current_connections``: Currently in-use connections
    - ``available_connections``: Available connections
    - ``pool_utilization``: Usage percentage (0.0-1.0)
    """
    import asyncio

    async def check() -> bool | dict[str, Any]:
        try:
            # Get connection pool
            pool = getattr(redis_client, "connection_pool", None)
            if pool is None:
                return {
                    "healthy": True,
                    "message": "No connection pool available (single connection mode)",
                }

            # Get pool stats - different attributes for different pool types
            max_connections = getattr(pool, "max_connections", None)

            # For BlockingConnectionPool
            if max_connections is None:
                max_connections = getattr(pool, "_max_connections", 10)

            # Count in-use connections
            # Different pool implementations store this differently
            in_use = 0

            # Check _in_use_connections (common in redis-py)
            if hasattr(pool, "_in_use_connections"):
                in_use = len(pool._in_use_connections)
            elif hasattr(pool, "in_use_connections"):
                in_use = len(pool.in_use_connections)
            elif hasattr(pool, "_created_connections"):
                in_use = pool._created_connections

            # Calculate available
            if hasattr(pool, "_available_connections"):
                available = len(pool._available_connections)
            else:
                available = max_connections - in_use if max_connections else 0

            # Calculate utilization
            if max_connections and max_connections > 0:
                utilization = in_use / max_connections
            else:
                utilization = 0.0

            # Check threshold
            healthy = utilization < max_connections_threshold

            # Also verify Redis is actually reachable
            is_async = hasattr(redis_client.ping, "__await__")
            try:
                if is_async:
                    ping_result = await asyncio.wait_for(redis_client.ping(), timeout=timeout)
                else:
                    loop = asyncio.get_event_loop()
                    ping_result = await asyncio.wait_for(
                        loop.run_in_executor(None, redis_client.ping),
                        timeout=timeout,
                    )
                redis_healthy = bool(ping_result)
            except Exception:
                redis_healthy = False
                healthy = False

            status_message = "Pool healthy" if healthy else "Pool saturation warning"
            if not redis_healthy:
                status_message = "Redis connection failed"

            return {
                "healthy": healthy and redis_healthy,
                "message": status_message,
                "max_connections": max_connections,
                "current_connections": in_use,
                "available_connections": available,
                "pool_utilization": round(utilization, 3),
                "threshold": max_connections_threshold,
                "redis_reachable": redis_healthy,
            }

        except Exception as e:
            logger.warning(
                "redis_pool_check_failed",
                error=str(e),
                error_type=type(e).__name__,
            )
            return {
                "healthy": False,
                "message": f"Pool check failed: {type(e).__name__}",
                "error": str(e),
            }

    return check


def create_database_pool_check(
    engine: Any,
    max_overflow_threshold: float = 0.8,
) -> Callable[[], Awaitable[bool | dict[str, Any]]]:
    """
    Create a SQLAlchemy database connection pool health check.

    Parameters
    ----------
    engine : Any
        SQLAlchemy engine instance.
    max_overflow_threshold : float
        Threshold for overflow usage (0.0-1.0).
        Default: 0.8 (80%)

    Returns
    -------
    Callable
        Health check function.

    Example
    -------
    >>> from sqlalchemy import create_engine
    >>> from obskit.health.checks import create_database_pool_check
    >>>
    >>> engine = create_engine("postgresql://...", pool_size=20)
    >>> db_pool_check = create_database_pool_check(engine)
    >>> checker.add_readiness_check("db_pool", db_pool_check)
    """

    async def check() -> bool | dict[str, Any]:
        try:
            pool = engine.pool

            # Get pool statistics
            pool_size = pool.size()
            checked_in = pool.checkedin()
            checked_out = pool.checkedout()
            overflow = pool.overflow()

            # Calculate metrics
            max_size = pool_size + pool._max_overflow
            current_usage = checked_out
            utilization = current_usage / max_size if max_size > 0 else 0.0

            # Check overflow usage
            if pool._max_overflow > 0:
                overflow_usage = overflow / pool._max_overflow
            else:
                overflow_usage = 0.0

            healthy = overflow_usage < max_overflow_threshold

            return {
                "healthy": healthy,
                "message": "Database pool healthy" if healthy else "Pool overflow warning",
                "pool_size": pool_size,
                "checked_in": checked_in,
                "checked_out": checked_out,
                "overflow": overflow,
                "max_overflow": pool._max_overflow,
                "pool_utilization": round(utilization, 3),
                "overflow_utilization": round(overflow_usage, 3),
                "threshold": max_overflow_threshold,
            }

        except AttributeError:
            return {
                "healthy": True,
                "message": "Engine does not use connection pooling",
            }
        except Exception as e:
            return {
                "healthy": False,
                "message": f"Database pool check failed: {type(e).__name__}",
                "error": str(e),
            }

    return check


__all__ = [
    "create_redis_check",
    "create_redis_cluster_check",
    "create_redis_pool_check",
    "create_memory_check",
    "create_disk_check",
    "create_http_check",
    "create_database_pool_check",
]
