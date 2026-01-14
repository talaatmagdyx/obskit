"""
Health Check Module for obskit
===============================

This module provides Kubernetes-style health check endpoints for your
services: readiness, liveness, and general health.

Health Check Types
------------------

**Liveness (/live, /livez)**
    "Is the process alive?"

    - Should return true if the process is running
    - Failure triggers pod restart in Kubernetes
    - Should NOT check external dependencies
    - Keep this check simple and fast

**Readiness (/ready, /readyz)**
    "Is the service ready to accept traffic?"

    - Should check all dependencies (DB, cache, etc.)
    - Failure removes pod from load balancer
    - Safe to have more complex checks
    - Use during startup and when dependencies fail

**Health (/health, /healthz)**
    "What's the overall status?"

    - Combines liveness and readiness
    - Provides detailed status for dashboards
    - May include component-level health

Why Separate Liveness and Readiness?
------------------------------------
Consider a web service that connects to a database:

1. Service starts → Not ready (DB connecting) → Not live (starting up)
2. DB connected → Ready → Live
3. DB disconnects → Not ready → Still live (don't restart!)
4. Process hangs → Still not ready → Not live (restart)

Separating these prevents unnecessary restarts when external
dependencies have issues.

Quick Start
-----------
.. code-block:: python

    from obskit.health import HealthChecker, create_health_response

    # Create health checker
    checker = HealthChecker()

    # Add readiness checks (dependencies)
    @checker.add_readiness_check("database")
    async def check_database():
        return await db.ping()

    @checker.add_readiness_check("redis")
    async def check_redis():
        return await redis.ping()

    # Add liveness check (optional, usually just "am I running?")
    @checker.add_liveness_check("memory")
    async def check_memory():
        import psutil
        return psutil.virtual_memory().percent < 95

    # Use in your API endpoints
    async def health_endpoint():
        result = await checker.check_health()
        return create_health_response(result)

    async def ready_endpoint():
        result = await checker.check_readiness()
        return create_health_response(result)

    async def live_endpoint():
        result = await checker.check_liveness()
        return create_health_response(result)

Kubernetes Configuration
------------------------
.. code-block:: yaml

    apiVersion: v1
    kind: Pod
    spec:
      containers:
        - name: my-service
          livenessProbe:
            httpGet:
              path: /live
              port: 8080
            initialDelaySeconds: 5
            periodSeconds: 10
            failureThreshold: 3
          readinessProbe:
            httpGet:
              path: /ready
              port: 8080
            initialDelaySeconds: 5
            periodSeconds: 5
            failureThreshold: 3

Example - FastAPI Integration
-----------------------------
.. code-block:: python

    from fastapi import FastAPI, Response
    from obskit.health import HealthChecker, create_health_response

    app = FastAPI()
    checker = HealthChecker()

    @checker.add_readiness_check("database")
    async def check_db():
        # Returns True if healthy, False otherwise
        return await database.is_connected()

    @app.get("/health")
    async def health():
        result = await checker.check_health()
        return create_health_response(result)

    @app.get("/ready")
    async def ready():
        result = await checker.check_readiness()
        status_code = 200 if result.healthy else 503
        return Response(
            content=result.to_json(),
            status_code=status_code,
            media_type="application/json",
        )

    @app.get("/live")
    async def live():
        result = await checker.check_liveness()
        status_code = 200 if result.healthy else 503
        return Response(
            content=result.to_json(),
            status_code=status_code,
            media_type="application/json",
        )

Example Response
----------------
.. code-block:: json

    {
        "status": "healthy",
        "checks": {
            "database": {
                "status": "healthy",
                "duration_ms": 12.5
            },
            "redis": {
                "status": "healthy",
                "duration_ms": 2.3
            }
        },
        "service": "order-service",
        "version": "1.2.3",
        "timestamp": "2024-01-15T10:30:45.123Z"
    }

See Also
--------
obskit.metrics : Record health check metrics
obskit.resilience : Circuit breakers for unhealthy dependencies
"""

from obskit.health.checker import (
    HealthCheck,
    HealthChecker,
    HealthResult,
    LivenessCheck,
    ReadinessCheck,
    create_health_response,
    get_health_checker,
)
from obskit.health.checks import (
    create_disk_check,
    create_http_check,
    create_memory_check,
    create_redis_check,
    create_redis_cluster_check,
)

__all__ = [
    # ==========================================================================
    # Health Checker
    # ==========================================================================
    # Main health checker class
    "HealthChecker",
    # Result from health checks
    "HealthResult",
    # ==========================================================================
    # Check Types
    # ==========================================================================
    # Base health check
    "HealthCheck",
    # Readiness check (dependencies)
    "ReadinessCheck",
    # Liveness check (process alive)
    "LivenessCheck",
    # ==========================================================================
    # Response Helpers
    # ==========================================================================
    # Create HTTP response from health result
    "create_health_response",
    # ==========================================================================
    # Singleton Access
    # ==========================================================================
    # Get global health checker instance
    "get_health_checker",
    # ==========================================================================
    # Built-in Health Checks
    # ==========================================================================
    # Redis connectivity check
    "create_redis_check",
    # Redis cluster check
    "create_redis_cluster_check",
    # Memory utilization check
    "create_memory_check",
    # Disk space check
    "create_disk_check",
    # HTTP endpoint check
    "create_http_check",
]
