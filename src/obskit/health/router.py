"""
build_health_router — generic FastAPI health router
====================================================

Zero knowledge of Redis, Postgres, RabbitMQ, or any dependency.
The caller provides the check callables.  obskit owns the protocol.

Usage
-----
.. code-block:: python

    from obskit.health import HealthCheck, build_health_router

    checks = [
        HealthCheck(name="redis",    check=lambda: redis.ping(),           timeout=2),
        HealthCheck(name="postgres", check=lambda: db.execute("SELECT 1"), timeout=3),
        HealthCheck(name="rabbit",   check=lambda: channel.is_open,        timeout=2),
    ]

    router = build_health_router(checks=checks)
    app.include_router(router)

Endpoints registered
--------------------
- ``GET {prefix}/live``  — liveness  (200 / 503)
- ``GET {prefix}/ready`` — readiness (200 / 503)
- ``GET {prefix}``       — combined  (200 / 503)

Splitting liveness from readiness
----------------------------------
.. code-block:: python

    router = build_health_router(
        readiness_checks=[
            HealthCheck(name="postgres", check=lambda: db.execute("SELECT 1"), timeout=3),
        ],
        liveness_checks=[
            HealthCheck(name="memory", check=lambda: psutil.virtual_memory().percent < 90),
        ],
    )

Standard response
-----------------
.. code-block:: json

    {
        "status": "healthy",
        "healthy": true,
        "checks": {
            "redis":    {"status": "healthy", "duration_ms": 1.2},
            "postgres": {"status": "healthy", "duration_ms": 4.5}
        },
        "service": "order-service",
        "version": "1.0.0",
        "timestamp": "2026-03-01T10:00:00.000000+00:00"
    }
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from obskit.health.checker import HealthCheck, HealthChecker

if TYPE_CHECKING:  # pragma: no cover
    pass


def build_health_router(
    checks: list[HealthCheck] | None = None,
    readiness_checks: list[HealthCheck] | None = None,
    liveness_checks: list[HealthCheck] | None = None,
    prefix: str = "/health",
    tags: list[str] | None = None,
    include_in_schema: bool = False,
):
    """
    Build a FastAPI ``APIRouter`` with standard health endpoints.

    obskit does **not** know what Redis, Postgres, or RabbitMQ are.
    You provide a callable — obskit handles timeouts, aggregation, and HTTP.

    Parameters
    ----------
    checks : list[HealthCheck], optional
        Shortcut: all checks are treated as **readiness** checks.
        These appear on both ``/ready`` and ``/`` (combined).
    readiness_checks : list[HealthCheck], optional
        Checks for external dependencies.
        Failure → ``/ready`` returns 503 (pod removed from load balancer).
    liveness_checks : list[HealthCheck], optional
        Checks for process health (e.g. memory, deadlock).
        Failure → ``/live`` returns 503 (pod restarted by Kubernetes).
    prefix : str
        URL prefix for all endpoints. Default: ``"/health"``.
    tags : list[str], optional
        FastAPI OpenAPI tags.
    include_in_schema : bool
        Whether to include endpoints in OpenAPI schema. Default: ``False``.

    Returns
    -------
    APIRouter
        FastAPI router with ``/live``, ``/ready``, and root endpoints.

    Raises
    ------
    ImportError
        If ``fastapi`` is not installed. Install with ``pip install obskit[fastapi]``.

    Example
    -------
    >>> from obskit.health import HealthCheck, build_health_router
    >>>
    >>> router = build_health_router(checks=[
    ...     HealthCheck(name="db",    check=lambda: db.ping(),    timeout=3),
    ...     HealthCheck(name="cache", check=lambda: cache.ping(), timeout=2),
    ... ])
    >>> app.include_router(router)
    """
    try:
        from fastapi import APIRouter
        from fastapi.responses import JSONResponse
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "fastapi is required for build_health_router. "
            "Install it with: pip install 'obskit[fastapi]'"
        ) from exc

    # Build an internal HealthChecker from the provided check lists.
    checker = HealthChecker()

    for hc in checks or []:
        checker._readiness_checks.append(hc)

    for hc in readiness_checks or []:
        checker._readiness_checks.append(hc)

    for hc in liveness_checks or []:
        checker._liveness_checks.append(hc)

    router = APIRouter(prefix=prefix, tags=tags or ["health"])

    @router.get("/live", include_in_schema=include_in_schema)
    async def liveness_endpoint() -> JSONResponse:
        """Liveness probe — is the process alive? (Kubernetes restarts on failure)"""
        result = await checker.check_liveness()
        return JSONResponse(
            content=result.to_dict(),
            status_code=200 if result.healthy else 503,
        )

    @router.get("/ready", include_in_schema=include_in_schema)
    async def readiness_endpoint() -> JSONResponse:
        """Readiness probe — are all dependencies healthy? (Pod removed from LB on failure)"""
        result = await checker.check_readiness()
        return JSONResponse(
            content=result.to_dict(),
            status_code=200 if result.healthy else 503,
        )

    @router.get("", include_in_schema=include_in_schema)
    async def health_endpoint() -> JSONResponse:
        """Combined health check — liveness + readiness."""
        result = await checker.check_health()
        return JSONResponse(
            content=result.to_dict(),
            status_code=200 if result.healthy else 503,
        )

    return router


__all__ = ["build_health_router"]
