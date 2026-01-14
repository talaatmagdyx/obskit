"""
Health Checker Interface - Abstract Base Class for Health Checks
=================================================================

This module defines the contract for health check implementations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable


class HealthStatus(Enum):
    """Health check status values."""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"


class HealthResultInterface(ABC):
    """Interface for health check results."""

    @property
    @abstractmethod
    def healthy(self) -> bool:
        """Whether the overall health check passed."""

    @property
    @abstractmethod
    def status(self) -> HealthStatus:
        """Overall health status."""

    @property
    @abstractmethod
    def checks(self) -> dict[str, Any]:
        """Individual check results."""

    @abstractmethod
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""

    @abstractmethod
    def to_json(self) -> str:
        """Convert to JSON string."""


class HealthCheckerInterface(ABC):
    """
    Abstract base class for health checkers.

    Health checkers provide Kubernetes-style health endpoints:
    - Liveness: Is the process alive?
    - Readiness: Is the service ready for traffic?
    - Health: Overall status

    Example
    -------
    >>> class MyHealthChecker(HealthCheckerInterface):
    ...     def add_readiness_check(self, name):
    ...         def decorator(func):
    ...             self._readiness_checks[name] = func
    ...             return func
    ...         return decorator
    ...
    ...     async def check_readiness(self):
    ...         results = {}
    ...         for name, check in self._readiness_checks.items():
    ...             results[name] = await check()
    ...         return HealthResult(results)
    """

    @abstractmethod
    def add_readiness_check(
        self, name: str
    ) -> Callable[[Callable[[], Awaitable[bool]]], Callable[[], Awaitable[bool]]]:
        """
        Decorator to add a readiness check.

        Parameters
        ----------
        name : str
            Name of the check.

        Returns
        -------
        Callable
            Decorator function.

        Example
        -------
        >>> @checker.add_readiness_check("database")
        ... async def check_database():
        ...     return await db.ping()
        """

    @abstractmethod
    def add_liveness_check(
        self, name: str
    ) -> Callable[[Callable[[], Awaitable[bool]]], Callable[[], Awaitable[bool]]]:
        """
        Decorator to add a liveness check.

        Parameters
        ----------
        name : str
            Name of the check.

        Returns
        -------
        Callable
            Decorator function.
        """

    @abstractmethod
    async def check_health(self) -> HealthResultInterface:
        """
        Run all health checks.

        Returns
        -------
        HealthResultInterface
            Combined result of all checks.
        """

    @abstractmethod
    async def check_readiness(self) -> HealthResultInterface:
        """
        Run readiness checks only.

        Returns
        -------
        HealthResultInterface
            Result of readiness checks.
        """

    @abstractmethod
    async def check_liveness(self) -> HealthResultInterface:
        """
        Run liveness checks only.

        Returns
        -------
        HealthResultInterface
            Result of liveness checks.
        """

    @abstractmethod
    def is_ready(self) -> bool:
        """
        Quick synchronous check if service is ready.

        Returns
        -------
        bool
            True if last readiness check passed.
        """

    @abstractmethod
    def is_live(self) -> bool:
        """
        Quick synchronous check if service is alive.

        Returns
        -------
        bool
            True if last liveness check passed.
        """
