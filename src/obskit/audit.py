"""
Audit Trail
===========

Track all significant system events for compliance.

Features:
- Immutable audit logs
- User action tracking
- Data access logging
- Compliance reporting

Example:
    from obskit.audit import AuditTrail

    audit = AuditTrail("order-service")

    # Record action
    audit.record(
        action="create_order",
        actor="user:123",
        resource="order:456",
        result="success"
    )
"""

import hashlib
import json
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from prometheus_client import Counter

from obskit.logging import get_logger

logger = get_logger(__name__)


# =============================================================================
# Prometheus Metrics
# =============================================================================

AUDIT_EVENTS_TOTAL = Counter(
    "audit_events_total", "Total audit events recorded", ["service", "action", "result"]
)

AUDIT_SENSITIVE_ACCESS = Counter(
    "audit_sensitive_access_total", "Sensitive data access events", ["service", "resource_type"]
)


# =============================================================================
# Enums and Data Classes
# =============================================================================


class AuditAction(Enum):
    """Common audit actions."""

    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    LOGIN = "login"
    LOGOUT = "logout"
    EXPORT = "export"
    CONFIGURE = "configure"
    GRANT = "grant"
    REVOKE = "revoke"
    CUSTOM = "custom"


class AuditResult(Enum):
    """Audit action results."""

    SUCCESS = "success"
    FAILURE = "failure"
    DENIED = "denied"
    ERROR = "error"


@dataclass
class AuditEntry:
    """An audit log entry."""

    entry_id: str
    timestamp: datetime
    service: str
    action: str
    actor: str  # User or system identifier
    resource: str  # Resource being accessed
    resource_type: str
    result: AuditResult
    details: dict[str, Any] = field(default_factory=dict)
    ip_address: str | None = None
    user_agent: str | None = None
    correlation_id: str | None = None
    parent_entry_id: str | None = None
    hash: str = ""  # For immutability verification

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "timestamp": self.timestamp.isoformat(),
            "service": self.service,
            "action": self.action,
            "actor": self.actor,
            "resource": self.resource,
            "resource_type": self.resource_type,
            "result": self.result.value,
            "details": self.details,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "correlation_id": self.correlation_id,
            "parent_entry_id": self.parent_entry_id,
            "hash": self.hash,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)


@dataclass
class AuditQuery:
    """Query parameters for audit search."""

    start_time: datetime | None = None
    end_time: datetime | None = None
    actor: str | None = None
    action: str | None = None
    resource: str | None = None
    resource_type: str | None = None
    result: AuditResult | None = None
    correlation_id: str | None = None
    limit: int = 100


# =============================================================================
# Audit Trail
# =============================================================================


class AuditTrail:
    """
    Audit trail for tracking system events.

    Parameters
    ----------
    service_name : str
        Name of the service
    storage_callback : callable, optional
        Function to store audit entries externally
    sensitive_resources : list, optional
        Resource types that are sensitive
    """

    def __init__(
        self,
        service_name: str,
        storage_callback: Callable[[AuditEntry], None] | None = None,
        sensitive_resources: list[str] | None = None,
    ):
        self.service_name = service_name
        self.storage_callback = storage_callback
        self.sensitive_resources = set(
            sensitive_resources or ["user", "password", "token", "secret", "key", "pii"]
        )

        self._entries: list[AuditEntry] = []
        self._entry_counter = 0
        self._last_hash = ""
        self._lock = threading.Lock()

    def record(
        self,
        action: AuditAction | str,
        actor: str,
        resource: str,
        resource_type: str = "unknown",
        result: AuditResult | str = AuditResult.SUCCESS,
        details: dict[str, Any] | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        correlation_id: str | None = None,
    ) -> AuditEntry:
        """
        Record an audit event.

        Parameters
        ----------
        action : AuditAction or str
            The action performed
        actor : str
            Who performed the action (e.g., "user:123", "system:cron")
        resource : str
            Resource identifier (e.g., "order:456")
        resource_type : str
            Type of resource
        result : AuditResult or str
            Result of the action
        details : dict, optional
            Additional details
        ip_address : str, optional
            Client IP address
        user_agent : str, optional
            Client user agent
        correlation_id : str, optional
            Correlation ID for tracing

        Returns
        -------
        AuditEntry
            The created audit entry
        """
        if isinstance(action, AuditAction):
            action = action.value
        if isinstance(result, str):
            result = AuditResult(result)

        with self._lock:
            self._entry_counter += 1
            entry_id = f"audit-{self.service_name}-{self._entry_counter}-{int(time.time() * 1000)}"

            entry = AuditEntry(
                entry_id=entry_id,
                timestamp=datetime.utcnow(),
                service=self.service_name,
                action=action,
                actor=actor,
                resource=resource,
                resource_type=resource_type,
                result=result,
                details=details or {},
                ip_address=ip_address,
                user_agent=user_agent,
                correlation_id=correlation_id,
                parent_entry_id=self._last_hash[:16] if self._last_hash else None,
            )

            # Calculate hash for immutability
            entry.hash = self._calculate_hash(entry)
            self._last_hash = entry.hash

            self._entries.append(entry)

            # Trim if too large
            if len(self._entries) > 10000:
                self._entries = self._entries[-10000:]

        # Record metrics
        AUDIT_EVENTS_TOTAL.labels(
            service=self.service_name, action=action, result=result.value
        ).inc()

        if resource_type.lower() in self.sensitive_resources:
            AUDIT_SENSITIVE_ACCESS.labels(
                service=self.service_name, resource_type=resource_type
            ).inc()

        # Store externally if callback provided
        if self.storage_callback:
            try:
                self.storage_callback(entry)
            except Exception as e:
                logger.error("audit_storage_failed", error=str(e), entry_id=entry_id)

        # Log for audit trail
        logger.info(
            "audit_event",
            entry_id=entry_id,
            action=action,
            actor=actor,
            resource=resource,
            result=result.value,
        )

        return entry

    def _calculate_hash(self, entry: AuditEntry) -> str:
        """Calculate hash for entry immutability."""
        data = f"{self._last_hash}{entry.entry_id}{entry.timestamp.isoformat()}{entry.action}{entry.actor}{entry.resource}{entry.result.value}"
        return hashlib.sha256(data.encode()).hexdigest()

    def verify_chain(self) -> tuple[bool, str | None]:
        """
        Verify the integrity of the audit chain.

        Returns
        -------
        tuple
            (is_valid, error_message)
        """
        with self._lock:
            if not self._entries:
                return True, None

            prev_hash = ""
            for entry in self._entries:
                # Recalculate expected hash
                data = f"{prev_hash}{entry.entry_id}{entry.timestamp.isoformat()}{entry.action}{entry.actor}{entry.resource}{entry.result.value}"
                expected_hash = hashlib.sha256(data.encode()).hexdigest()

                if entry.hash != expected_hash:
                    return False, f"Hash mismatch at entry {entry.entry_id}"

                prev_hash = entry.hash

        return True, None

    def query(self, query: AuditQuery) -> list[AuditEntry]:
        """
        Query audit entries.

        Parameters
        ----------
        query : AuditQuery
            Query parameters

        Returns
        -------
        list
            Matching audit entries
        """
        with self._lock:
            results = []

            for entry in reversed(self._entries):
                # Apply filters
                if query.start_time and entry.timestamp < query.start_time:
                    continue
                if query.end_time and entry.timestamp > query.end_time:
                    continue
                if query.actor and query.actor not in entry.actor:
                    continue
                if query.action and entry.action != query.action:
                    continue
                if query.resource and query.resource not in entry.resource:
                    continue
                if query.resource_type and entry.resource_type != query.resource_type:
                    continue
                if query.result and entry.result != query.result:
                    continue
                if query.correlation_id and entry.correlation_id != query.correlation_id:
                    continue

                results.append(entry)

                if len(results) >= query.limit:
                    break

            return results

    def get_actor_activity(
        self,
        actor: str,
        hours: int = 24,
    ) -> list[AuditEntry]:
        """Get recent activity for an actor."""
        query = AuditQuery(
            actor=actor,
            start_time=datetime.utcnow() - timedelta(hours=hours),
        )
        return self.query(query)

    def get_resource_history(
        self,
        resource: str,
        hours: int = 168,  # 1 week
    ) -> list[AuditEntry]:
        """Get history for a resource."""
        query = AuditQuery(
            resource=resource,
            start_time=datetime.utcnow() - timedelta(hours=hours),
        )
        return self.query(query)

    def get_failed_actions(self, hours: int = 24) -> list[AuditEntry]:
        """Get failed actions."""
        query = AuditQuery(
            result=AuditResult.FAILURE,
            start_time=datetime.utcnow() - timedelta(hours=hours),
        )
        return self.query(query)

    def get_denied_actions(self, hours: int = 24) -> list[AuditEntry]:
        """Get denied actions."""
        query = AuditQuery(
            result=AuditResult.DENIED,
            start_time=datetime.utcnow() - timedelta(hours=hours),
        )
        return self.query(query)

    def export_for_compliance(
        self,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        """Export entries for compliance reporting."""
        query = AuditQuery(
            start_time=start_time,
            end_time=end_time,
            limit=100000,
        )
        entries = self.query(query)
        return [e.to_dict() for e in entries]


# =============================================================================
# Singleton
# =============================================================================

_trails: dict[str, AuditTrail] = {}
_trail_lock = threading.Lock()


def get_audit_trail(service_name: str, **kwargs) -> AuditTrail:
    """Get or create an audit trail."""
    if service_name not in _trails:
        with _trail_lock:
            if service_name not in _trails:
                _trails[service_name] = AuditTrail(service_name, **kwargs)

    return _trails[service_name]


# Type alias for backward compatibility
