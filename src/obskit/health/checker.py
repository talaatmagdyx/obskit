"""
Health Checker Implementation
=============================

This module implements the health checking system with support for
readiness, liveness, and general health endpoints.

Architecture
------------
.. code-block:: text

    HealthChecker
    ├── Readiness Checks
    │   ├── database: check_database()
    │   ├── redis: check_redis()
    │   └── ...
    └── Liveness Checks
        ├── memory: check_memory()
        └── ...

    check_health() = all checks
    check_readiness() = readiness checks only
    check_liveness() = liveness checks only

Check Functions
---------------
Health check functions should:

1. Return True for healthy, False for unhealthy
2. Raise an exception if check fails (treated as unhealthy)
3. Complete within the configured timeout
4. Be async (or sync, will be wrapped)

Example:

.. code-block:: python

    async def check_database() -> bool:
        try:
            await db.execute("SELECT 1")
            return True
        except Exception:
            return False
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from obskit.config import get_settings
from obskit.core.types import HealthStatus

# Type alias for check functions
# Can return bool (simple) or dict (detailed)
CheckFunction = Callable[[], Awaitable[bool | dict[str, Any]]]


@dataclass
class CheckResult:
    """
    Result of a single health check.

    Attributes
    ----------
    name : str
        Name of the check.
    healthy : bool
        Whether the check passed.
    duration_ms : float
        How long the check took.
    message : str, optional
        Additional information.
    details : dict, optional
        Extra details from the check.
    error : str, optional
        Error message if check failed.
    """

    name: str
    healthy: bool
    duration_ms: float
    message: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    @property
    def status(self) -> HealthStatus:
        """Get status as HealthStatus enum."""
        return HealthStatus.HEALTHY if self.healthy else HealthStatus.UNHEALTHY

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result: dict[str, Any] = {
            "status": self.status.value,
            "duration_ms": round(self.duration_ms, 3),
        }
        if self.message:
            result["message"] = self.message
        if self.details:
            result["details"] = self.details
        if self.error:
            result["error"] = self.error
        return result


@dataclass
class HealthResult:
    """
    Aggregated health check result.

    Contains results from all health checks and the overall status.

    Attributes
    ----------
    healthy : bool
        True if ALL checks passed.
    status : HealthStatus
        Overall status (healthy, unhealthy, degraded).
    checks : dict
        Individual check results by name.
    timestamp : datetime
        When the health check was performed.
    service : str
        Service name from configuration.
    version : str
        Service version from configuration.

    Example
    -------
    >>> result = await checker.check_health()
    >>> print(result.healthy)  # True/False
    >>> print(result.status)   # HealthStatus.HEALTHY
    >>> print(result.checks)   # {"database": CheckResult(...), ...}
    """

    healthy: bool
    status: HealthStatus
    checks: dict[str, CheckResult]
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    service: str = ""
    version: str = ""

    def to_dict(self) -> dict[str, Any]:
        """
        Convert to dictionary for JSON serialization.

        Returns
        -------
        dict
            JSON-serializable dictionary.

        Example
        -------
        >>> result = await checker.check_health()
        >>> data = result.to_dict()
        >>> print(json.dumps(data, indent=2))
        """
        return {
            "status": self.status.value,
            "healthy": self.healthy,
            "checks": {name: check.to_dict() for name, check in self.checks.items()},
            "service": self.service,
            "version": self.version,
            "timestamp": self.timestamp.isoformat(),
        }

    def to_json(self) -> str:
        """
        Convert to JSON string.

        Returns
        -------
        str
            JSON representation of the health result.
        """
        return json.dumps(self.to_dict())


@dataclass
class HealthCheck:
    """
    A health check definition.

    Attributes
    ----------
    name : str
        Unique name for the check.
    check_fn : CheckFunction
        Async function that performs the check.
    critical : bool
        If True, failure affects overall health status.
    timeout : float
        Maximum time allowed for the check.
    """

    name: str
    check_fn: CheckFunction
    critical: bool = True
    timeout: float = 5.0


# Aliases for semantic clarity
ReadinessCheck = HealthCheck
LivenessCheck = HealthCheck


class HealthChecker:
    """
    Health check manager with support for readiness and liveness checks.

    Manages multiple health checks and aggregates their results for
    Kubernetes-style health endpoints.

    Attributes
    ----------
    readiness_checks : list[HealthCheck]
        Checks for external dependencies.
    liveness_checks : list[HealthCheck]
        Checks for process health.

    Example - Basic Setup
    ---------------------
    >>> from obskit.health import HealthChecker
    >>>
    >>> checker = HealthChecker()
    >>>
    >>> # Add readiness check with decorator
    >>> @checker.add_readiness_check("database")
    ... async def check_database():
    ...     return await db.ping()
    >>>
    >>> # Add readiness check with function
    >>> async def check_redis():
    ...     return await redis.ping()
    >>> checker.add_readiness_check("redis")(check_redis)
    >>>
    >>> # Check health
    >>> result = await checker.check_health()
    >>> print(result.healthy)

    Example - FastAPI Integration
    -----------------------------
    >>> from fastapi import FastAPI, Response
    >>> from obskit.health import HealthChecker
    >>>
    >>> app = FastAPI()
    >>> checker = HealthChecker()
    >>>
    >>> @checker.add_readiness_check("database")
    ... async def check_db():
    ...     return await database.is_connected()
    >>>
    >>> @checker.add_readiness_check("cache", critical=False)
    ... async def check_cache():
    ...     # Non-critical: failure won't make service unhealthy
    ...     return await redis.ping()
    >>>
    >>> @app.get("/health")
    ... async def health():
    ...     result = await checker.check_health()
    ...     return Response(
    ...         content=result.to_json(),
    ...         status_code=200 if result.healthy else 503,
    ...         media_type="application/json",
    ...     )

    Example - Detailed Check Results
    --------------------------------
    >>> @checker.add_readiness_check("database")
    ... async def check_database_detailed():
    ...     '''Return detailed check information.'''
    ...     start = time.time()
    ...     try:
    ...         pool_size = await db.pool.size()
    ...         active = await db.pool.active()
    ...         return {
    ...             "healthy": True,
    ...             "details": {
    ...                 "pool_size": pool_size,
    ...                 "active_connections": active,
    ...             },
    ...         }
    ...     except Exception as e:
    ...         return {
    ...             "healthy": False,
    ...             "error": str(e),
    ...         }
    """

    def __init__(self, timeout: float | None = None) -> None:
        """
        Initialize the health checker.

        Parameters
        ----------
        timeout : float, optional
            Default timeout for health checks in seconds.
            If not provided, uses setting health_check_timeout.
        """
        settings = get_settings()

        self._timeout = timeout or settings.health_check_timeout
        self._readiness_checks: list[HealthCheck] = []
        self._liveness_checks: list[HealthCheck] = []

    def add_readiness_check(
        self,
        name: str,
        critical: bool = True,
        timeout: float | None = None,
    ) -> Callable[[CheckFunction], CheckFunction]:
        """
        Decorator to register a readiness check.

        Readiness checks verify that external dependencies are available.
        Used by Kubernetes to determine if the pod should receive traffic.

        Parameters
        ----------
        name : str
            Unique name for the check.
        critical : bool, default=True
            If True, failure makes service "unhealthy".
            If False, failure makes service "degraded".
        timeout : float, optional
            Check timeout in seconds.

        Returns
        -------
        Callable
            Decorator function.

        Example
        -------
        >>> checker = HealthChecker()
        >>>
        >>> @checker.add_readiness_check("database")
        ... async def check_database():
        ...     return await db.ping()
        >>>
        >>> @checker.add_readiness_check("cache", critical=False)
        ... async def check_cache():
        ...     # Non-critical dependency
        ...     return await redis.ping()
        """

        def decorator(fn: CheckFunction) -> CheckFunction:
            check = HealthCheck(
                name=name,
                check_fn=fn,
                critical=critical,
                timeout=timeout or self._timeout,
            )
            self._readiness_checks.append(check)
            return fn

        return decorator

    def add_liveness_check(
        self,
        name: str,
        critical: bool = True,
        timeout: float | None = None,
    ) -> Callable[[CheckFunction], CheckFunction]:
        """
        Decorator to register a liveness check.

        Liveness checks verify that the process is healthy and should
        continue running. Used by Kubernetes to determine if the pod
        should be restarted.

        Parameters
        ----------
        name : str
            Unique name for the check.
        critical : bool, default=True
            If True, failure indicates process should restart.
        timeout : float, optional
            Check timeout in seconds.

        Returns
        -------
        Callable
            Decorator function.

        Example
        -------
        >>> checker = HealthChecker()
        >>>
        >>> @checker.add_liveness_check("memory")
        ... async def check_memory():
        ...     import psutil
        ...     # Restart if memory > 95%
        ...     return psutil.virtual_memory().percent < 95
        >>>
        >>> @checker.add_liveness_check("deadlock")
        ... async def check_deadlock():
        ...     # Check for deadlock by trying to acquire a known lock
        ...     return await try_acquire_test_lock()
        """

        def decorator(fn: CheckFunction) -> CheckFunction:
            check = HealthCheck(
                name=name,
                check_fn=fn,
                critical=critical,
                timeout=timeout or self._timeout,
            )
            self._liveness_checks.append(check)
            return fn

        return decorator

    async def _run_check(self, check: HealthCheck) -> CheckResult:
        """
        Run a single health check with timeout.

        Parameters
        ----------
        check : HealthCheck
            The check to run.

        Returns
        -------
        CheckResult
            Result of the check.
        """
        start_time = time.perf_counter()

        try:
            # Run check with timeout
            result = await asyncio.wait_for(
                check.check_fn(),
                timeout=check.timeout,
            )

            duration_ms = (time.perf_counter() - start_time) * 1000

            # Handle different result types
            if isinstance(result, bool):
                return CheckResult(
                    name=check.name,
                    healthy=result,
                    duration_ms=duration_ms,
                )
            elif isinstance(result, dict):
                return CheckResult(
                    name=check.name,
                    healthy=result.get("healthy", True),
                    duration_ms=duration_ms,
                    message=result.get("message"),
                    details=result.get("details", {}),
                    error=result.get("error"),
                )
            else:
                # Treat truthy values as healthy
                return CheckResult(
                    name=check.name,
                    healthy=bool(result),
                    duration_ms=duration_ms,
                )

        except TimeoutError:
            duration_ms = (time.perf_counter() - start_time) * 1000
            return CheckResult(
                name=check.name,
                healthy=False,
                duration_ms=duration_ms,
                error=f"Check timed out after {check.timeout}s",
            )

        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            return CheckResult(
                name=check.name,
                healthy=False,
                duration_ms=duration_ms,
                error=f"{type(e).__name__}: {str(e)}",
            )

    async def _run_checks(
        self,
        checks: list[HealthCheck],
    ) -> dict[str, CheckResult]:
        """
        Run multiple health checks concurrently.

        Parameters
        ----------
        checks : list[HealthCheck]
            List of checks to run.

        Returns
        -------
        dict[str, CheckResult]
            Results keyed by check name.
        """
        if not checks:
            return {}

        # Run all checks concurrently
        tasks = [self._run_check(check) for check in checks]
        results = await asyncio.gather(*tasks)

        return {result.name: result for result in results}

    def _aggregate_results(
        self,
        results: dict[str, CheckResult],
        checks: list[HealthCheck],
    ) -> HealthResult:
        """
        Aggregate individual check results into overall health status.

        Parameters
        ----------
        results : dict[str, CheckResult]
            Individual check results.
        checks : list[HealthCheck]
            Original check definitions (for critical flag).

        Returns
        -------
        HealthResult
            Aggregated health status.
        """
        settings = get_settings()

        # Build lookup for critical flags
        critical_map = {check.name: check.critical for check in checks}

        # Determine overall status
        critical_failures = sum(
            1
            for name, result in results.items()
            if not result.healthy and critical_map.get(name, True)
        )

        non_critical_failures = sum(
            1
            for name, result in results.items()
            if not result.healthy and not critical_map.get(name, True)
        )

        if critical_failures > 0:
            status = HealthStatus.UNHEALTHY
            healthy = False
        elif non_critical_failures > 0:
            status = HealthStatus.DEGRADED
            healthy = True  # Still healthy, just degraded
        else:
            status = HealthStatus.HEALTHY
            healthy = True

        return HealthResult(
            healthy=healthy,
            status=status,
            checks=results,
            service=settings.service_name,
            version=settings.version,
        )

    async def check_readiness(self) -> HealthResult:
        """
        Run all readiness checks.

        Readiness checks verify that external dependencies are available.
        Use this endpoint to determine if the service should receive traffic.

        Returns
        -------
        HealthResult
            Aggregated readiness status.

        Example
        -------
        >>> result = await checker.check_readiness()
        >>> if result.healthy:
        ...     print("Service is ready for traffic")
        ... else:
        ...     print(f"Service not ready: {result.checks}")
        """
        results = await self._run_checks(self._readiness_checks)
        return self._aggregate_results(results, self._readiness_checks)

    async def check_liveness(self) -> HealthResult:
        """
        Run all liveness checks.

        Liveness checks verify that the process is healthy.
        Use this endpoint to determine if the process should be restarted.

        Returns
        -------
        HealthResult
            Aggregated liveness status.

        Example
        -------
        >>> result = await checker.check_liveness()
        >>> if not result.healthy:
        ...     print("Process should be restarted")
        """
        # If no liveness checks defined, always return healthy
        # (process is running, so it's alive)
        if not self._liveness_checks:
            settings = get_settings()
            return HealthResult(
                healthy=True,
                status=HealthStatus.HEALTHY,
                checks={},
                service=settings.service_name,
                version=settings.version,
            )

        results = await self._run_checks(self._liveness_checks)
        return self._aggregate_results(results, self._liveness_checks)

    async def check_health(self) -> HealthResult:
        """
        Run all health checks (readiness + liveness).

        This is the comprehensive health endpoint that checks everything.
        Use for detailed health dashboards and monitoring.

        Returns
        -------
        HealthResult
            Aggregated health status from all checks.

        Example
        -------
        >>> result = await checker.check_health()
        >>> print(f"Status: {result.status.value}")
        >>> for name, check in result.checks.items():
        ...     print(f"  {name}: {check.status.value} ({check.duration_ms}ms)")
        """
        all_checks = self._readiness_checks + self._liveness_checks
        results = await self._run_checks(all_checks)
        return self._aggregate_results(results, all_checks)


def create_health_response(result: HealthResult) -> dict[str, Any]:
    """
    Create a standardized health response dictionary.

    This helper creates a response format suitable for HTTP endpoints.

    Parameters
    ----------
    result : HealthResult
        The health check result.

    Returns
    -------
    dict
        Response dictionary with status_code and body.

    Example
    -------
    >>> result = await checker.check_health()
    >>> response = create_health_response(result)
    >>>
    >>> # Use with FastAPI
    >>> return JSONResponse(
    ...     content=response["body"],
    ...     status_code=response["status_code"],
    ... )
    """
    return {
        "status_code": 200 if result.healthy else 503,
        "body": result.to_dict(),
    }


import threading

# Global health checker for module-level usage
_health_checker: HealthChecker | None = None
_health_checker_lock = threading.Lock()


def get_health_checker() -> HealthChecker:
    """Get or create the global health checker.

    Thread Safety
    -------------
    This function is thread-safe using double-checked locking pattern.
    """
    global _health_checker

    # Double-checked locking pattern for thread safety
    if _health_checker is None:
        with _health_checker_lock:
            if _health_checker is None:  # pragma: no branch
                _health_checker = HealthChecker()

    return _health_checker


def reset_health_checker() -> None:
    """Reset the global health checker (for testing)."""
    global _health_checker
    with _health_checker_lock:
        _health_checker = None
