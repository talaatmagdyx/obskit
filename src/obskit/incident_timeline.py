"""
Incident Timeline Builder
=========================

Build incident timelines from events.

Features:
- Automatic event correlation
- Timeline visualization data
- Impact analysis
- Post-mortem support

Example:
    from obskit.incident_timeline import IncidentTimeline

    timeline = IncidentTimeline("INC-001")

    timeline.add_event("Alert fired", category="alert")
    timeline.add_event("Runbook started", category="action")
    timeline.add_event("Service restarted", category="mitigation")
    timeline.add_event("Issue resolved", category="resolution")

    report = timeline.generate_report()
"""

import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from prometheus_client import Counter, Gauge, Histogram

from obskit.logging import get_logger

logger = get_logger(__name__)


# =============================================================================
# Prometheus Metrics
# =============================================================================

INCIDENTS_TOTAL = Counter("incidents_total", "Total incidents created", ["severity"])

INCIDENT_DURATION = Histogram(
    "incident_duration_seconds",
    "Incident duration (detection to resolution)",
    ["severity"],
    buckets=(300, 600, 1800, 3600, 7200, 14400, 28800, 86400),
)

INCIDENT_TTR = Histogram(
    "incident_time_to_resolution_seconds",
    "Time to resolution",
    ["severity"],
    buckets=(300, 600, 1800, 3600, 7200, 14400),
)

INCIDENTS_ACTIVE = Gauge("incidents_active", "Currently active incidents")


# =============================================================================
# Enums and Data Classes
# =============================================================================


class IncidentStatus(Enum):
    """Incident statuses."""

    DETECTED = "detected"
    INVESTIGATING = "investigating"
    IDENTIFIED = "identified"
    MITIGATING = "mitigating"
    RESOLVED = "resolved"
    POSTMORTEM = "postmortem"
    CLOSED = "closed"


class EventCategory(Enum):
    """Event categories."""

    ALERT = "alert"
    METRIC = "metric"
    LOG = "log"
    ACTION = "action"
    COMMUNICATION = "communication"
    DEPLOYMENT = "deployment"
    CONFIGURATION = "configuration"
    MITIGATION = "mitigation"
    RESOLUTION = "resolution"
    OTHER = "other"


@dataclass
class TimelineEvent:
    """An event in the incident timeline."""

    event_id: str
    timestamp: datetime
    description: str
    category: EventCategory
    actor: str | None = None
    impact: str | None = None
    source: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "description": self.description,
            "category": self.category.value,
            "actor": self.actor,
            "impact": self.impact,
            "source": self.source,
            "metadata": self.metadata,
        }


@dataclass
class Incident:
    """An incident record."""

    incident_id: str
    title: str
    severity: str
    status: IncidentStatus
    created_at: datetime
    detected_at: datetime | None = None
    identified_at: datetime | None = None
    mitigated_at: datetime | None = None
    resolved_at: datetime | None = None
    closed_at: datetime | None = None
    description: str = ""
    impact: str = ""
    root_cause: str = ""
    resolution: str = ""
    affected_services: list[str] = field(default_factory=list)
    affected_customers: int = 0
    events: list[TimelineEvent] = field(default_factory=list)
    responders: list[str] = field(default_factory=list)

    @property
    def time_to_detect(self) -> timedelta | None:
        if self.detected_at:
            return self.detected_at - self.created_at
        return None

    @property
    def time_to_mitigate(self) -> timedelta | None:
        if self.mitigated_at and self.detected_at:
            return self.mitigated_at - self.detected_at
        return None

    @property
    def time_to_resolve(self) -> timedelta | None:
        if self.resolved_at and self.detected_at:
            return self.resolved_at - self.detected_at
        return None

    @property
    def total_duration(self) -> timedelta | None:
        end_time = self.resolved_at or self.closed_at or datetime.utcnow()
        return end_time - self.created_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "title": self.title,
            "severity": self.severity,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "detected_at": self.detected_at.isoformat() if self.detected_at else None,
            "identified_at": self.identified_at.isoformat() if self.identified_at else None,
            "mitigated_at": self.mitigated_at.isoformat() if self.mitigated_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "description": self.description,
            "impact": self.impact,
            "root_cause": self.root_cause,
            "resolution": self.resolution,
            "affected_services": self.affected_services,
            "affected_customers": self.affected_customers,
            "events_count": len(self.events),
            "responders": self.responders,
            "time_to_detect_seconds": self.time_to_detect.total_seconds()
            if self.time_to_detect
            else None,
            "time_to_mitigate_seconds": self.time_to_mitigate.total_seconds()
            if self.time_to_mitigate
            else None,
            "time_to_resolve_seconds": self.time_to_resolve.total_seconds()
            if self.time_to_resolve
            else None,
        }


# =============================================================================
# Incident Timeline
# =============================================================================


class IncidentTimeline:
    """
    Build and manage incident timelines.

    Parameters
    ----------
    incident_id : str
        Unique incident identifier
    title : str
        Incident title
    severity : str
        Severity level
    """

    def __init__(
        self,
        incident_id: str,
        title: str = "Incident",
        severity: str = "medium",
    ):
        self.incident = Incident(
            incident_id=incident_id,
            title=title,
            severity=severity,
            status=IncidentStatus.DETECTED,
            created_at=datetime.utcnow(),
            detected_at=datetime.utcnow(),
        )

        self._event_counter = 0
        self._lock = threading.Lock()

        INCIDENTS_TOTAL.labels(severity=severity).inc()
        INCIDENTS_ACTIVE.inc()

        logger.info(
            "incident_created",
            incident_id=incident_id,
            title=title,
            severity=severity,
        )

    def add_event(
        self,
        description: str,
        category: EventCategory | str = EventCategory.OTHER,
        actor: str | None = None,
        impact: str | None = None,
        source: str | None = None,
        timestamp: datetime | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TimelineEvent:
        """
        Add an event to the timeline.

        Parameters
        ----------
        description : str
            Event description
        category : EventCategory or str
            Event category
        actor : str, optional
            Who triggered the event
        impact : str, optional
            Impact description
        source : str, optional
            Event source
        timestamp : datetime, optional
            Event time (defaults to now)
        metadata : dict, optional
            Additional data

        Returns
        -------
        TimelineEvent
        """
        if isinstance(category, str):
            category = EventCategory(category)

        with self._lock:
            self._event_counter += 1
            event_id = f"{self.incident.incident_id}-event-{self._event_counter}"

            event = TimelineEvent(
                event_id=event_id,
                timestamp=timestamp or datetime.utcnow(),
                description=description,
                category=category,
                actor=actor,
                impact=impact,
                source=source,
                metadata=metadata or {},
            )

            self.incident.events.append(event)

            # Sort events by timestamp
            self.incident.events.sort(key=lambda e: e.timestamp)

        logger.debug(
            "incident_event_added",
            incident_id=self.incident.incident_id,
            event_id=event_id,
            category=category.value,
        )

        return event

    def update_status(self, status: IncidentStatus | str, notes: str = ""):
        """
        Update incident status.

        Parameters
        ----------
        status : IncidentStatus or str
            New status
        notes : str
            Status change notes
        """
        if isinstance(status, str):
            status = IncidentStatus(status)

        now = datetime.utcnow()

        with self._lock:
            old_status = self.incident.status
            self.incident.status = status

            # Track key timestamps
            if status == IncidentStatus.IDENTIFIED and not self.incident.identified_at:
                self.incident.identified_at = now
            elif status == IncidentStatus.MITIGATING and not self.incident.mitigated_at:
                self.incident.mitigated_at = now
            elif status == IncidentStatus.RESOLVED and not self.incident.resolved_at:
                self.incident.resolved_at = now
                INCIDENTS_ACTIVE.dec()

                # Record metrics
                if self.incident.time_to_resolve:
                    INCIDENT_TTR.labels(severity=self.incident.severity).observe(
                        self.incident.time_to_resolve.total_seconds()
                    )

                if self.incident.total_duration:
                    INCIDENT_DURATION.labels(severity=self.incident.severity).observe(
                        self.incident.total_duration.total_seconds()
                    )

            elif status == IncidentStatus.CLOSED and not self.incident.closed_at:
                self.incident.closed_at = now

        # Add status change event
        self.add_event(
            description=f"Status changed: {old_status.value} → {status.value}. {notes}",
            category=EventCategory.ACTION,
        )

        logger.info(
            "incident_status_updated",
            incident_id=self.incident.incident_id,
            old_status=old_status.value,
            new_status=status.value,
        )

    def add_responder(self, responder: str):
        """Add a responder to the incident."""
        with self._lock:
            if responder not in self.incident.responders:
                self.incident.responders.append(responder)

        self.add_event(
            description=f"Responder joined: {responder}",
            category=EventCategory.COMMUNICATION,
            actor=responder,
        )

    def add_affected_service(self, service: str):
        """Add an affected service."""
        with self._lock:
            if service not in self.incident.affected_services:
                self.incident.affected_services.append(service)

    def set_root_cause(self, root_cause: str):
        """Set the root cause."""
        with self._lock:
            self.incident.root_cause = root_cause

        self.add_event(
            description=f"Root cause identified: {root_cause}",
            category=EventCategory.ACTION,
        )

    def set_resolution(self, resolution: str):
        """Set the resolution."""
        with self._lock:
            self.incident.resolution = resolution

        self.add_event(
            description=f"Resolution: {resolution}",
            category=EventCategory.RESOLUTION,
        )

    def get_timeline(self) -> list[TimelineEvent]:
        """Get the event timeline."""
        with self._lock:
            return list(self.incident.events)

    def get_timeline_by_category(
        self,
        category: EventCategory,
    ) -> list[TimelineEvent]:
        """Get events filtered by category."""
        with self._lock:
            return [e for e in self.incident.events if e.category == category]

    def generate_report(self) -> dict[str, Any]:
        """
        Generate incident report.

        Returns
        -------
        dict
            Incident report
        """
        with self._lock:
            incident_data = self.incident.to_dict()

            # Add timeline
            incident_data["timeline"] = [e.to_dict() for e in self.incident.events]

            # Add summary
            incident_data["summary"] = {
                "total_events": len(self.incident.events),
                "events_by_category": {},
                "responder_count": len(self.incident.responders),
                "services_affected": len(self.incident.affected_services),
            }

            for event in self.incident.events:
                cat = event.category.value
                incident_data["summary"]["events_by_category"][cat] = (
                    incident_data["summary"]["events_by_category"].get(cat, 0) + 1
                )

        return incident_data

    def generate_postmortem(self) -> dict[str, Any]:
        """
        Generate post-mortem document structure.

        Returns
        -------
        dict
            Post-mortem structure
        """
        report = self.generate_report()

        return {
            "incident_id": self.incident.incident_id,
            "title": self.incident.title,
            "date": self.incident.created_at.strftime("%Y-%m-%d"),
            "severity": self.incident.severity,
            "duration": str(self.incident.total_duration)
            if self.incident.total_duration
            else "Ongoing",
            "impact": self.incident.impact,
            "summary": f"Incident affecting {', '.join(self.incident.affected_services) or 'unknown services'}",
            "timeline": report["timeline"],
            "root_cause": self.incident.root_cause,
            "resolution": self.incident.resolution,
            "lessons_learned": [],  # To be filled
            "action_items": [],  # To be filled
            "metrics": {
                "time_to_detect": str(self.incident.time_to_detect)
                if self.incident.time_to_detect
                else None,
                "time_to_mitigate": str(self.incident.time_to_mitigate)
                if self.incident.time_to_mitigate
                else None,
                "time_to_resolve": str(self.incident.time_to_resolve)
                if self.incident.time_to_resolve
                else None,
            },
            "responders": self.incident.responders,
        }


# =============================================================================
# Incident Manager (Singleton)
# =============================================================================


class IncidentManager:
    """Manage multiple incidents."""

    def __init__(self):
        self._incidents: dict[str, IncidentTimeline] = {}
        self._lock = threading.Lock()

    def create_incident(
        self,
        incident_id: str,
        title: str,
        severity: str = "medium",
    ) -> IncidentTimeline:
        """Create a new incident."""
        timeline = IncidentTimeline(incident_id, title, severity)

        with self._lock:
            self._incidents[incident_id] = timeline

        return timeline

    def get_incident(self, incident_id: str) -> IncidentTimeline | None:
        """Get an incident by ID."""
        with self._lock:
            return self._incidents.get(incident_id)

    def get_active_incidents(self) -> list[IncidentTimeline]:
        """Get all active incidents."""
        with self._lock:
            return [
                i
                for i in self._incidents.values()
                if i.incident.status not in (IncidentStatus.RESOLVED, IncidentStatus.CLOSED)
            ]

    def get_all_incidents(self) -> list[IncidentTimeline]:
        """Get all incidents."""
        with self._lock:
            return list(self._incidents.values())


_manager: IncidentManager | None = None
_manager_lock = threading.Lock()


def get_incident_manager() -> IncidentManager:
    """Get the global incident manager."""
    global _manager

    if _manager is None:
        with _manager_lock:
            if _manager is None:
                _manager = IncidentManager()

    return _manager
