"""
Dependency Health Aggregator.

Provides single view of all dependencies' health status.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from prometheus_client import Counter, Gauge

from ..logging import get_logger

logger = get_logger(__name__)

# Metrics
DEPENDENCY_HEALTH = Gauge(
    "dependency_health_status",
    "Dependency health status (1=healthy, 0=unhealthy)",
    ["dependency", "type"],
)

DEPENDENCY_LATENCY = Gauge(
    "dependency_health_latency_seconds", "Dependency health check latency", ["dependency"]
)

DEPENDENCY_CHECK_TOTAL = Counter(
    "dependency_health_checks_total", "Total dependency health checks", ["dependency", "status"]
)

OVERALL_HEALTH = Gauge(
    "service_overall_health",
    "Overall service health (1=healthy, 0=degraded, -1=unhealthy)",
    ["service"],
)


class HealthStatus(Enum):
    """Health status values."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class DependencyType(Enum):
    """Types of dependencies."""

    DATABASE = "database"
    CACHE = "cache"
    QUEUE = "queue"
    API = "api"
    STORAGE = "storage"
    CUSTOM = "custom"


@dataclass
class DependencyHealth:
    """Health status of a single dependency."""

    name: str
    healthy: bool
    status: HealthStatus = HealthStatus.UNKNOWN
    latency_ms: float | None = None
    error: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    last_check: float = 0.0
    consecutive_failures: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "healthy": self.healthy,
            "status": self.status.value,
            "latency_ms": self.latency_ms,
            "error": self.error,
            "details": self.details,
            "last_check": self.last_check,
            "consecutive_failures": self.consecutive_failures,
        }


@dataclass
class AggregatedHealth:
    """Aggregated health status of all dependencies."""

    healthy: bool
    status: HealthStatus
    dependencies: dict[str, DependencyHealth]
    healthy_count: int
    unhealthy_count: int
    degraded_count: int
    total_latency_ms: float
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "healthy": self.healthy,
            "status": self.status.value,
            "dependencies": {name: dep.to_dict() for name, dep in self.dependencies.items()},
            "healthy_count": self.healthy_count,
            "unhealthy_count": self.unhealthy_count,
            "degraded_count": self.degraded_count,
            "total_latency_ms": self.total_latency_ms,
            "timestamp": self.timestamp,
        }


HealthCheckFunc = (
    Callable[[], bool]
    | Callable[[], Coroutine[Any, Any, bool]]
    | Callable[[], dict[str, Any]]
    | Callable[[], Coroutine[Any, Any, dict[str, Any]]]
)


class DependencyHealthAggregator:
    """
    Aggregates health status of all dependencies.

    Example:
        aggregator = DependencyHealthAggregator(service_name="my-service")

        # Add dependencies
        aggregator.add_dependency("postgres", check_postgres, type=DependencyType.DATABASE)
        aggregator.add_dependency("rabbitmq", check_rabbitmq, type=DependencyType.QUEUE)
        aggregator.add_dependency("redis", check_redis, type=DependencyType.CACHE)

        # Check all
        health = await aggregator.check_all()
        print(health.to_dict())

        # Check specific dependency
        db_health = await aggregator.check("postgres")
    """

    def __init__(
        self,
        service_name: str = "default",
        timeout_seconds: float = 5.0,
        cache_seconds: float = 5.0,
        critical_dependencies: list[str] | None = None,
    ):
        """
        Initialize health aggregator.

        Args:
            service_name: Service name for metrics
            timeout_seconds: Timeout for health checks
            cache_seconds: Cache health check results for this duration
            critical_dependencies: Dependencies that must be healthy for service to be healthy
        """
        self.service_name = service_name
        self.timeout_seconds = timeout_seconds
        self.cache_seconds = cache_seconds
        self.critical_dependencies = set(critical_dependencies or [])

        self._dependencies: dict[str, tuple] = {}  # name -> (check_func, type)
        self._cached_health: dict[str, DependencyHealth] = {}
        self._last_aggregated: AggregatedHealth | None = None

    def add_dependency(
        self,
        name: str,
        check_func: HealthCheckFunc,
        type: DependencyType = DependencyType.CUSTOM,
        critical: bool = False,
        timeout_seconds: float | None = None,
    ):
        """
        Add a dependency to track.

        Args:
            name: Dependency name
            check_func: Function that returns bool or dict with health info
            type: Type of dependency
            critical: If True, adds to critical dependencies
            timeout_seconds: Custom timeout for this dependency
        """
        self._dependencies[name] = (check_func, type, timeout_seconds)

        if critical:
            self.critical_dependencies.add(name)

        # Initialize metrics
        DEPENDENCY_HEALTH.labels(dependency=name, type=type.value).set(0)

        logger.info("dependency_registered", dependency=name, type=type.value, critical=critical)

    def remove_dependency(self, name: str):
        """Remove a dependency."""
        if name in self._dependencies:
            del self._dependencies[name]
            self.critical_dependencies.discard(name)
            if name in self._cached_health:
                del self._cached_health[name]

    async def check(self, name: str, use_cache: bool = True) -> DependencyHealth:
        """
        Check health of a specific dependency.

        Args:
            name: Dependency name
            use_cache: Use cached result if available

        Returns:
            DependencyHealth object
        """
        if name not in self._dependencies:
            return DependencyHealth(
                name=name,
                healthy=False,
                status=HealthStatus.UNKNOWN,
                error="Dependency not registered",
            )

        # Check cache
        if use_cache and name in self._cached_health:
            cached = self._cached_health[name]
            if time.time() - cached.last_check < self.cache_seconds:
                return cached

        check_func, dep_type, custom_timeout = self._dependencies[name]
        timeout = custom_timeout or self.timeout_seconds

        start_time = time.time()
        health = DependencyHealth(
            name=name, healthy=False, status=HealthStatus.UNKNOWN, last_check=start_time
        )

        try:
            # Run check with timeout
            if asyncio.iscoroutinefunction(check_func):
                result = await asyncio.wait_for(check_func(), timeout=timeout)
            else:
                # Run sync function in executor
                loop = asyncio.get_event_loop()
                result = await asyncio.wait_for(
                    loop.run_in_executor(None, check_func), timeout=timeout
                )

            latency_ms = (time.time() - start_time) * 1000
            health.latency_ms = latency_ms

            # Parse result
            if isinstance(result, bool):
                health.healthy = result
                health.status = HealthStatus.HEALTHY if result else HealthStatus.UNHEALTHY
            elif isinstance(result, dict):
                health.healthy = result.get("healthy", False)
                health.status = HealthStatus(
                    result.get("status", "healthy" if health.healthy else "unhealthy")
                )
                health.details = result.get("details", {})
                health.error = result.get("error")
            else:
                health.healthy = bool(result)
                health.status = HealthStatus.HEALTHY if health.healthy else HealthStatus.UNHEALTHY

            # Reset consecutive failures on success
            if health.healthy:
                health.consecutive_failures = 0
            else:
                prev = self._cached_health.get(name)
                health.consecutive_failures = (prev.consecutive_failures + 1) if prev else 1

        except TimeoutError:
            health.healthy = False
            health.status = HealthStatus.UNHEALTHY
            health.error = f"Health check timed out after {timeout}s"
            health.latency_ms = timeout * 1000
            prev = self._cached_health.get(name)
            health.consecutive_failures = (prev.consecutive_failures + 1) if prev else 1

        except Exception as e:
            health.healthy = False
            health.status = HealthStatus.UNHEALTHY
            health.error = str(e)
            health.latency_ms = (time.time() - start_time) * 1000
            prev = self._cached_health.get(name)
            health.consecutive_failures = (prev.consecutive_failures + 1) if prev else 1

            logger.warning("dependency_check_failed", dependency=name, error=str(e))

        # Update metrics
        DEPENDENCY_HEALTH.labels(dependency=name, type=dep_type.value).set(
            1 if health.healthy else 0
        )

        if health.latency_ms:
            DEPENDENCY_LATENCY.labels(dependency=name).set(health.latency_ms / 1000)

        DEPENDENCY_CHECK_TOTAL.labels(
            dependency=name, status="healthy" if health.healthy else "unhealthy"
        ).inc()

        # Cache result
        self._cached_health[name] = health

        return health

    async def check_all(self, use_cache: bool = True) -> AggregatedHealth:
        """
        Check health of all dependencies.

        Args:
            use_cache: Use cached results if available

        Returns:
            AggregatedHealth object
        """
        # Run all checks in parallel
        tasks = {name: self.check(name, use_cache) for name in self._dependencies}

        results = {}
        for name, task in tasks.items():
            results[name] = await task

        # Aggregate results
        healthy_count = sum(1 for h in results.values() if h.healthy)
        unhealthy_count = sum(1 for h in results.values() if not h.healthy)
        degraded_count = sum(1 for h in results.values() if h.status == HealthStatus.DEGRADED)
        total_latency = sum(h.latency_ms or 0 for h in results.values())

        # Determine overall status
        critical_healthy = all(
            results.get(name, DependencyHealth(name=name, healthy=False)).healthy
            for name in self.critical_dependencies
        )

        if critical_healthy and unhealthy_count == 0:
            overall_status = HealthStatus.HEALTHY
            overall_healthy = True
        elif critical_healthy:
            overall_status = HealthStatus.DEGRADED
            overall_healthy = True
        else:
            overall_status = HealthStatus.UNHEALTHY
            overall_healthy = False

        aggregated = AggregatedHealth(
            healthy=overall_healthy,
            status=overall_status,
            dependencies=results,
            healthy_count=healthy_count,
            unhealthy_count=unhealthy_count,
            degraded_count=degraded_count,
            total_latency_ms=total_latency,
        )

        # Update overall health metric
        status_value = 1 if overall_healthy else (-1 if not critical_healthy else 0)
        OVERALL_HEALTH.labels(service=self.service_name).set(status_value)

        self._last_aggregated = aggregated

        logger.info(
            "health_check_complete",
            service=self.service_name,
            status=overall_status.value,
            healthy_count=healthy_count,
            unhealthy_count=unhealthy_count,
            total_latency_ms=total_latency,
        )

        return aggregated

    def get_cached_health(self) -> AggregatedHealth | None:
        """Get the last aggregated health check result."""
        return self._last_aggregated

    async def wait_for_healthy(
        self,
        timeout_seconds: float = 60.0,
        check_interval: float = 1.0,
        dependencies: list[str] | None = None,
    ) -> bool:
        """
        Wait until specified dependencies are healthy.

        Args:
            timeout_seconds: Maximum time to wait
            check_interval: Time between checks
            dependencies: Dependencies to wait for (defaults to critical)

        Returns:
            True if all dependencies became healthy
        """
        deps_to_check = set(dependencies or self.critical_dependencies)
        start_time = time.time()

        while time.time() - start_time < timeout_seconds:
            all_healthy = True

            for name in deps_to_check:
                health = await self.check(name, use_cache=False)
                if not health.healthy:
                    all_healthy = False
                    break

            if all_healthy:
                logger.info(
                    "dependencies_healthy",
                    dependencies=list(deps_to_check),
                    wait_time=time.time() - start_time,
                )
                return True

            await asyncio.sleep(check_interval)

        logger.warning(
            "dependencies_wait_timeout", dependencies=list(deps_to_check), timeout=timeout_seconds
        )
        return False


# Common health check helpers
async def check_postgres(connection_string: str) -> dict[str, Any]:
    """Check PostgreSQL connection."""
    try:
        import asyncpg

        conn = await asyncpg.connect(connection_string, timeout=5)
        result = await conn.fetchval("SELECT 1")
        await conn.close()
        return {"healthy": result == 1, "details": {"connected": True}}
    except Exception as e:
        return {"healthy": False, "error": str(e)}


async def check_redis(host: str, port: int = 6379) -> dict[str, Any]:
    """Check Redis connection."""
    try:
        import aioredis

        redis = await aioredis.from_url(f"redis://{host}:{port}", socket_timeout=5)
        result = await redis.ping()
        await redis.close()
        return {"healthy": result, "details": {"connected": True}}
    except Exception as e:
        return {"healthy": False, "error": str(e)}


async def check_rabbitmq(url: str) -> dict[str, Any]:
    """Check RabbitMQ connection."""
    try:
        import aio_pika

        connection = await aio_pika.connect_robust(url, timeout=5)
        await connection.close()
        return {"healthy": True, "details": {"connected": True}}
    except Exception as e:
        return {"healthy": False, "error": str(e)}


async def check_http(url: str, expected_status: int = 200) -> dict[str, Any]:
    """Check HTTP endpoint."""
    try:
        import aiohttp

        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                healthy = response.status == expected_status
                return {"healthy": healthy, "details": {"status_code": response.status}}
    except Exception as e:
        return {"healthy": False, "error": str(e)}


__all__ = [
    "DependencyHealthAggregator",
    "DependencyHealth",
    "AggregatedHealth",
    "HealthStatus",
    "DependencyType",
    "check_postgres",
    "check_redis",
    "check_rabbitmq",
    "check_http",
    "DEPENDENCY_HEALTH",
    "DEPENDENCY_LATENCY",
    "DEPENDENCY_CHECK_TOTAL",
    "OVERALL_HEALTH",
]
