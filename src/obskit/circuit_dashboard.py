"""
Circuit Breaker Dashboard Data
==============================

Export circuit breaker state for dashboards.

Features:
- State export (closed, open, half-open)
- Failure counts
- Recovery timeline
- Health status

Example:
    from obskit.circuit_dashboard import CircuitBreakerDashboard

    dashboard = CircuitBreakerDashboard()
    dashboard.register_breaker("postgres", pg_circuit_breaker)

    # Get dashboard data
    data = dashboard.get_all_states()
"""

import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from prometheus_client import Gauge

from obskit.logging import get_logger

logger = get_logger(__name__)


# =============================================================================
# Prometheus Metrics
# =============================================================================

CIRCUIT_STATE = Gauge(
    "circuit_breaker_state",
    "Circuit breaker state (0=closed, 1=open, 2=half-open)",
    ["breaker_name", "dependency_type"],
)

CIRCUIT_FAILURES = Gauge(
    "circuit_breaker_failures", "Current failure count", ["breaker_name", "dependency_type"]
)

CIRCUIT_SUCCESS_COUNT = Gauge(
    "circuit_breaker_successes",
    "Success count in half-open state",
    ["breaker_name", "dependency_type"],
)


# =============================================================================
# Enums and Data Classes
# =============================================================================


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreakerStatus:
    """Status of a circuit breaker."""

    name: str
    dependency_type: str
    state: CircuitState
    failure_count: int
    success_count: int
    failure_threshold: int
    recovery_timeout: float
    last_failure_time: datetime | None = None
    last_state_change: datetime | None = None
    time_until_recovery: float = 0.0
    is_healthy: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "dependency_type": self.dependency_type,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
            "last_failure_time": self.last_failure_time.isoformat()
            if self.last_failure_time
            else None,
            "last_state_change": self.last_state_change.isoformat()
            if self.last_state_change
            else None,
            "time_until_recovery": self.time_until_recovery,
            "is_healthy": self.is_healthy,
        }


@dataclass
class DashboardData:
    """Complete dashboard data."""

    breakers: list[CircuitBreakerStatus]
    total_breakers: int
    healthy_breakers: int
    open_breakers: int
    half_open_breakers: int
    overall_health: bool
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "breakers": [b.to_dict() for b in self.breakers],
            "total_breakers": self.total_breakers,
            "healthy_breakers": self.healthy_breakers,
            "open_breakers": self.open_breakers,
            "half_open_breakers": self.half_open_breakers,
            "overall_health": self.overall_health,
            "timestamp": self.timestamp.isoformat(),
        }


# =============================================================================
# Circuit Breaker Dashboard
# =============================================================================


class CircuitBreakerDashboard:
    """
    Dashboard for circuit breaker status.

    Collects and exports circuit breaker states for monitoring.
    """

    def __init__(self):
        self._breakers: dict[str, Any] = {}  # name -> circuit breaker instance
        self._dependency_types: dict[str, str] = {}  # name -> type
        self._lock = threading.Lock()

    def register_breaker(
        self,
        name: str,
        breaker: Any,
        dependency_type: str = "external",
    ):
        """
        Register a circuit breaker for monitoring.

        Parameters
        ----------
        name : str
            Breaker name
        breaker : CircuitBreaker
            The circuit breaker instance
        dependency_type : str
            Type of dependency (database, cache, api, etc.)
        """
        with self._lock:
            self._breakers[name] = breaker
            self._dependency_types[name] = dependency_type

        logger.info(
            "circuit_breaker_registered",
            name=name,
            dependency_type=dependency_type,
        )

    def unregister_breaker(self, name: str):
        """Unregister a circuit breaker."""
        with self._lock:
            if name in self._breakers:
                del self._breakers[name]
            if name in self._dependency_types:
                del self._dependency_types[name]

    def get_breaker_status(self, name: str) -> CircuitBreakerStatus | None:
        """
        Get status of a specific breaker.

        Parameters
        ----------
        name : str
            Breaker name

        Returns
        -------
        CircuitBreakerStatus or None
        """
        with self._lock:
            if name not in self._breakers:
                return None

            breaker = self._breakers[name]
            dep_type = self._dependency_types.get(name, "external")

            return self._extract_status(name, breaker, dep_type)

    def _extract_status(
        self,
        name: str,
        breaker: Any,
        dependency_type: str,
    ) -> CircuitBreakerStatus:
        """Extract status from a circuit breaker."""
        # Handle different circuit breaker implementations
        state = CircuitState.CLOSED
        failure_count = 0
        success_count = 0
        failure_threshold = 5
        recovery_timeout = 30.0
        last_failure_time = None
        last_state_change = None
        time_until_recovery = 0.0

        # Try to get state
        if hasattr(breaker, "state"):
            state_val = breaker.state
            if isinstance(state_val, str):
                state = CircuitState(state_val.lower().replace("-", "_"))
            elif hasattr(state_val, "value"):
                state = CircuitState(state_val.value.lower().replace("-", "_"))
        elif hasattr(breaker, "_state"):
            state_str = str(breaker._state).lower()
            if "open" in state_str and "half" not in state_str:
                state = CircuitState.OPEN
            elif "half" in state_str:
                state = CircuitState.HALF_OPEN
            else:
                state = CircuitState.CLOSED

        # Try to get failure count
        if hasattr(breaker, "failure_count"):
            failure_count = breaker.failure_count
        elif hasattr(breaker, "_failure_count"):
            failure_count = breaker._failure_count

        # Try to get success count
        if hasattr(breaker, "success_count"):
            success_count = breaker.success_count
        elif hasattr(breaker, "_success_count"):
            success_count = breaker._success_count

        # Try to get threshold
        if hasattr(breaker, "failure_threshold"):
            failure_threshold = breaker.failure_threshold
        elif hasattr(breaker, "_failure_threshold"):
            failure_threshold = breaker._failure_threshold

        # Try to get recovery timeout
        if hasattr(breaker, "recovery_timeout"):
            recovery_timeout = breaker.recovery_timeout
        elif hasattr(breaker, "_recovery_timeout"):
            recovery_timeout = breaker._recovery_timeout

        # Try to get timestamps
        if hasattr(breaker, "last_failure_time"):
            last_failure_time = breaker.last_failure_time
        elif hasattr(breaker, "_last_failure_time"):
            last_failure_time = breaker._last_failure_time

        if hasattr(breaker, "opened_at"):
            last_state_change = breaker.opened_at
        elif hasattr(breaker, "_opened_at"):
            last_state_change = breaker._opened_at

        # Calculate time until recovery
        if state == CircuitState.OPEN and last_state_change:
            elapsed = (datetime.utcnow() - last_state_change).total_seconds()
            time_until_recovery = max(0, recovery_timeout - elapsed)

        is_healthy = state == CircuitState.CLOSED

        # Update Prometheus metrics
        state_value = {"closed": 0, "open": 1, "half_open": 2}[state.value]
        CIRCUIT_STATE.labels(breaker_name=name, dependency_type=dependency_type).set(state_value)

        CIRCUIT_FAILURES.labels(breaker_name=name, dependency_type=dependency_type).set(
            failure_count
        )

        CIRCUIT_SUCCESS_COUNT.labels(breaker_name=name, dependency_type=dependency_type).set(
            success_count
        )

        return CircuitBreakerStatus(
            name=name,
            dependency_type=dependency_type,
            state=state,
            failure_count=failure_count,
            success_count=success_count,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            last_failure_time=last_failure_time,
            last_state_change=last_state_change,
            time_until_recovery=time_until_recovery,
            is_healthy=is_healthy,
        )

    def get_all_states(self) -> DashboardData:
        """
        Get status of all registered breakers.

        Returns
        -------
        DashboardData
            Complete dashboard data
        """
        with self._lock:
            breakers = []

            for name, breaker in self._breakers.items():
                dep_type = self._dependency_types.get(name, "external")
                status = self._extract_status(name, breaker, dep_type)
                breakers.append(status)

            total = len(breakers)
            healthy = sum(1 for b in breakers if b.is_healthy)
            open_count = sum(1 for b in breakers if b.state == CircuitState.OPEN)
            half_open = sum(1 for b in breakers if b.state == CircuitState.HALF_OPEN)

            return DashboardData(
                breakers=breakers,
                total_breakers=total,
                healthy_breakers=healthy,
                open_breakers=open_count,
                half_open_breakers=half_open,
                overall_health=(open_count == 0),
            )

    def is_all_healthy(self) -> bool:
        """Check if all circuit breakers are healthy."""
        return self.get_all_states().overall_health

    def get_open_breakers(self) -> list[str]:
        """Get list of open circuit breaker names."""
        data = self.get_all_states()
        return [b.name for b in data.breakers if b.state == CircuitState.OPEN]


# =============================================================================
# Singleton Instance
# =============================================================================

_dashboard: CircuitBreakerDashboard | None = None
_dashboard_lock = threading.Lock()


def get_circuit_dashboard() -> CircuitBreakerDashboard:
    """Get the global circuit breaker dashboard."""
    global _dashboard

    if _dashboard is None:
        with _dashboard_lock:
            if _dashboard is None:
                _dashboard = CircuitBreakerDashboard()

    return _dashboard


def register_circuit_breaker(
    name: str,
    breaker: Any,
    dependency_type: str = "external",
):
    """Register a circuit breaker with the global dashboard."""
    get_circuit_dashboard().register_breaker(name, breaker, dependency_type)


def get_all_circuit_states() -> DashboardData:
    """Get all circuit breaker states from global dashboard."""
    return get_circuit_dashboard().get_all_states()
