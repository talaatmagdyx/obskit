"""
Failover Coordinator
====================

Coordinate failover between primary and backup systems.

Features:
- Health-based failover
- Automatic recovery
- Failover metrics
- Multi-region support

Example:
    from obskit.failover import FailoverCoordinator

    failover = FailoverCoordinator("database")
    failover.register_primary("postgres-primary", health_check=check_primary)
    failover.register_backup("postgres-replica", health_check=check_replica)

    # Get current active endpoint
    endpoint = failover.get_active()
"""

import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from prometheus_client import Counter, Gauge

from obskit.logging import get_logger

logger = get_logger(__name__)


# =============================================================================
# Prometheus Metrics
# =============================================================================

FAILOVER_STATE = Gauge(
    "failover_state", "Failover state (0=primary, 1=backup)", ["coordinator", "resource"]
)

FAILOVER_COUNT = Counter(
    "failover_events_total", "Total failover events", ["coordinator", "direction"]
)

ENDPOINT_HEALTH = Gauge(
    "failover_endpoint_health",
    "Endpoint health status (1=healthy, 0=unhealthy)",
    ["coordinator", "endpoint", "role"],
)

RECOVERY_TIME = Gauge("failover_recovery_time_seconds", "Time in failover state", ["coordinator"])


# =============================================================================
# Enums and Data Classes
# =============================================================================


class FailoverState(Enum):
    """Failover states."""

    PRIMARY = "primary"
    FAILING_OVER = "failing_over"
    BACKUP = "backup"
    RECOVERING = "recovering"


class EndpointRole(Enum):
    """Endpoint roles."""

    PRIMARY = "primary"
    BACKUP = "backup"


@dataclass
class Endpoint:
    """A failover endpoint."""

    name: str
    role: EndpointRole
    address: str | None = None
    health_check: Callable[[], bool] | None = None
    is_healthy: bool = True
    last_check: datetime | None = None
    consecutive_failures: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "role": self.role.value,
            "address": self.address,
            "is_healthy": self.is_healthy,
            "last_check": self.last_check.isoformat() if self.last_check else None,
            "consecutive_failures": self.consecutive_failures,
            "metadata": self.metadata,
        }


@dataclass
class FailoverEvent:
    """A failover event."""

    coordinator: str
    from_endpoint: str
    to_endpoint: str
    reason: str
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "coordinator": self.coordinator,
            "from_endpoint": self.from_endpoint,
            "to_endpoint": self.to_endpoint,
            "reason": self.reason,
            "timestamp": self.timestamp.isoformat(),
        }


# =============================================================================
# Failover Coordinator
# =============================================================================


class FailoverCoordinator:
    """
    Coordinate failover between primary and backup.

    Parameters
    ----------
    name : str
        Coordinator name
    failure_threshold : int
        Consecutive failures before failover
    recovery_threshold : int
        Consecutive successes before recovery
    check_interval_seconds : float
        Health check interval
    auto_recover : bool
        Automatically recover to primary when healthy
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 3,
        recovery_threshold: int = 5,
        check_interval_seconds: float = 10.0,
        auto_recover: bool = True,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_threshold = recovery_threshold
        self.check_interval_seconds = check_interval_seconds
        self.auto_recover = auto_recover

        self._primary: Endpoint | None = None
        self._backup: Endpoint | None = None
        self._state = FailoverState.PRIMARY
        self._failover_time: datetime | None = None
        self._events: list[FailoverEvent] = []
        self._recovery_successes = 0

        self._lock = threading.Lock()
        self._check_thread: threading.Thread | None = None
        self._stop_checking = threading.Event()

    def register_primary(
        self,
        name: str,
        address: str | None = None,
        health_check: Callable[[], bool] | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        """
        Register the primary endpoint.

        Parameters
        ----------
        name : str
            Endpoint name
        address : str, optional
            Endpoint address
        health_check : callable, optional
            Function that returns bool for health
        metadata : dict, optional
            Additional metadata
        """
        with self._lock:
            self._primary = Endpoint(
                name=name,
                role=EndpointRole.PRIMARY,
                address=address,
                health_check=health_check,
                metadata=metadata or {},
            )

        ENDPOINT_HEALTH.labels(coordinator=self.name, endpoint=name, role="primary").set(1)

        logger.info(
            "primary_registered",
            coordinator=self.name,
            endpoint=name,
        )

    def register_backup(
        self,
        name: str,
        address: str | None = None,
        health_check: Callable[[], bool] | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        """
        Register a backup endpoint.

        Parameters
        ----------
        name : str
            Endpoint name
        address : str, optional
            Endpoint address
        health_check : callable, optional
            Function that returns bool for health
        metadata : dict, optional
            Additional metadata
        """
        with self._lock:
            self._backup = Endpoint(
                name=name,
                role=EndpointRole.BACKUP,
                address=address,
                health_check=health_check,
                metadata=metadata or {},
            )

        ENDPOINT_HEALTH.labels(coordinator=self.name, endpoint=name, role="backup").set(1)

        logger.info(
            "backup_registered",
            coordinator=self.name,
            endpoint=name,
        )

    def get_active(self) -> Endpoint | None:
        """
        Get the currently active endpoint.

        Returns
        -------
        Endpoint or None
        """
        with self._lock:
            if self._state in (FailoverState.PRIMARY, FailoverState.RECOVERING):
                return self._primary
            else:
                return self._backup

    def get_active_address(self) -> str | None:
        """Get the address of the active endpoint."""
        endpoint = self.get_active()
        return endpoint.address if endpoint else None

    def check_health(self):
        """Perform health checks on all endpoints."""
        with self._lock:
            primary = self._primary
            backup = self._backup

        # Check primary
        if primary and primary.health_check:
            try:
                healthy = primary.health_check()
                self._update_endpoint_health(primary, healthy)
            except Exception as e:
                logger.error("primary_health_check_failed", error=str(e))
                self._update_endpoint_health(primary, False)

        # Check backup
        if backup and backup.health_check:
            try:
                healthy = backup.health_check()
                self._update_endpoint_health(backup, healthy)
            except Exception as e:
                logger.error("backup_health_check_failed", error=str(e))
                self._update_endpoint_health(backup, False)

        # Evaluate failover/recovery
        self._evaluate_state()

    def _update_endpoint_health(self, endpoint: Endpoint, healthy: bool):
        """Update endpoint health status."""
        with self._lock:
            endpoint.last_check = datetime.utcnow()

            if healthy:
                endpoint.is_healthy = True
                endpoint.consecutive_failures = 0
            else:
                endpoint.consecutive_failures += 1
                if endpoint.consecutive_failures >= self.failure_threshold:
                    endpoint.is_healthy = False

        ENDPOINT_HEALTH.labels(
            coordinator=self.name, endpoint=endpoint.name, role=endpoint.role.value
        ).set(1 if healthy else 0)

    def _evaluate_state(self):
        """Evaluate and potentially change failover state."""
        with self._lock:
            if not self._primary:
                return

            current_state = self._state

            if current_state == FailoverState.PRIMARY:
                # Check if we need to failover
                if not self._primary.is_healthy and self._backup and self._backup.is_healthy:
                    self._do_failover()

            elif current_state == FailoverState.BACKUP:
                # Check if we can recover
                if self.auto_recover and self._primary.is_healthy:
                    self._recovery_successes += 1
                    if self._recovery_successes >= self.recovery_threshold:
                        self._do_recovery()
                else:
                    self._recovery_successes = 0

            # Update recovery time metric
            if self._failover_time:
                recovery_seconds = (datetime.utcnow() - self._failover_time).total_seconds()
                RECOVERY_TIME.labels(coordinator=self.name).set(recovery_seconds)

    def _do_failover(self):
        """Perform failover to backup."""
        self._state = FailoverState.FAILING_OVER

        event = FailoverEvent(
            coordinator=self.name,
            from_endpoint=self._primary.name if self._primary else "unknown",
            to_endpoint=self._backup.name if self._backup else "unknown",
            reason="Primary unhealthy",
        )
        self._events.append(event)

        self._state = FailoverState.BACKUP
        self._failover_time = datetime.utcnow()
        self._recovery_successes = 0

        FAILOVER_STATE.labels(
            coordinator=self.name, resource=self._primary.name if self._primary else "unknown"
        ).set(1)

        FAILOVER_COUNT.labels(coordinator=self.name, direction="to_backup").inc()

        logger.warning(
            "failover_to_backup",
            coordinator=self.name,
            from_endpoint=event.from_endpoint,
            to_endpoint=event.to_endpoint,
        )

    def _do_recovery(self):
        """Perform recovery to primary."""
        self._state = FailoverState.RECOVERING

        event = FailoverEvent(
            coordinator=self.name,
            from_endpoint=self._backup.name if self._backup else "unknown",
            to_endpoint=self._primary.name if self._primary else "unknown",
            reason="Primary recovered",
        )
        self._events.append(event)

        self._state = FailoverState.PRIMARY

        if self._failover_time:
            recovery_seconds = (datetime.utcnow() - self._failover_time).total_seconds()
            logger.info(
                "recovered_to_primary",
                coordinator=self.name,
                downtime_seconds=recovery_seconds,
            )

        self._failover_time = None
        self._recovery_successes = 0

        FAILOVER_STATE.labels(
            coordinator=self.name, resource=self._primary.name if self._primary else "unknown"
        ).set(0)

        FAILOVER_COUNT.labels(coordinator=self.name, direction="to_primary").inc()

        RECOVERY_TIME.labels(coordinator=self.name).set(0)

    def force_failover(self, reason: str = "Manual failover"):
        """Force failover to backup."""
        with self._lock:
            if self._state == FailoverState.PRIMARY and self._backup:
                event = FailoverEvent(
                    coordinator=self.name,
                    from_endpoint=self._primary.name if self._primary else "unknown",
                    to_endpoint=self._backup.name,
                    reason=reason,
                )
                self._events.append(event)

                self._state = FailoverState.BACKUP
                self._failover_time = datetime.utcnow()

                FAILOVER_STATE.labels(
                    coordinator=self.name,
                    resource=self._primary.name if self._primary else "unknown",
                ).set(1)

                FAILOVER_COUNT.labels(coordinator=self.name, direction="to_backup").inc()

                logger.warning(
                    "forced_failover",
                    coordinator=self.name,
                    reason=reason,
                )

    def force_recovery(self, reason: str = "Manual recovery"):
        """Force recovery to primary."""
        with self._lock:
            if self._state == FailoverState.BACKUP and self._primary:
                self._do_recovery()

    def start_monitoring(self):
        """Start background health monitoring."""
        if self._check_thread and self._check_thread.is_alive():
            return

        self._stop_checking.clear()
        self._check_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self._check_thread.start()

        logger.info("failover_monitoring_started", coordinator=self.name)

    def stop_monitoring(self):
        """Stop background health monitoring."""
        self._stop_checking.set()
        if self._check_thread:
            self._check_thread.join(timeout=5)

        logger.info("failover_monitoring_stopped", coordinator=self.name)

    def _monitoring_loop(self):
        """Background monitoring loop."""
        while not self._stop_checking.is_set():
            try:
                self.check_health()
            except Exception as e:
                logger.error("failover_monitoring_error", error=str(e))

            self._stop_checking.wait(self.check_interval_seconds)

    def get_state(self) -> FailoverState:
        """Get current failover state."""
        with self._lock:
            return self._state

    def get_events(self, limit: int = 10) -> list[FailoverEvent]:
        """Get recent failover events."""
        with self._lock:
            return list(reversed(self._events[-limit:]))

    def get_status(self) -> dict[str, Any]:
        """Get complete failover status."""
        with self._lock:
            return {
                "coordinator": self.name,
                "state": self._state.value,
                "primary": self._primary.to_dict() if self._primary else None,
                "backup": self._backup.to_dict() if self._backup else None,
                "failover_time": self._failover_time.isoformat() if self._failover_time else None,
                "recent_events": [e.to_dict() for e in self._events[-5:]],
            }


# =============================================================================
# Singleton
# =============================================================================

_coordinators: dict[str, FailoverCoordinator] = {}
_coordinator_lock = threading.Lock()


def get_failover_coordinator(name: str, **kwargs) -> FailoverCoordinator:
    """Get or create a failover coordinator."""
    if name not in _coordinators:
        with _coordinator_lock:
            if name not in _coordinators:
                _coordinators[name] = FailoverCoordinator(name, **kwargs)

    return _coordinators[name]
