"""Unit tests for Incident Timeline Builder."""

from datetime import datetime

from obskit.incident_timeline import (
    EventCategory,
    IncidentManager,
    IncidentStatus,
    IncidentTimeline,
    TimelineEvent,
    get_incident_manager,
)


class TestIncidentTimeline:
    """Tests for IncidentTimeline."""

    def test_create_incident(self):
        """Test creating an incident."""
        timeline = IncidentTimeline(
            incident_id="INC-001",
            title="Service Outage",
            severity="high",
        )

        assert timeline.incident.incident_id == "INC-001"
        assert timeline.incident.title == "Service Outage"
        assert timeline.incident.status == IncidentStatus.DETECTED

    def test_add_event(self):
        """Test adding an event."""
        timeline = IncidentTimeline("INC-002", "Test Incident")

        event = timeline.add_event(
            description="Alert fired",
            category=EventCategory.ALERT,
            actor="alertmanager",
        )

        assert event.event_id is not None
        assert event.category == EventCategory.ALERT

        events = timeline.get_timeline()
        assert len(events) >= 1

    def test_add_event_with_string_category(self):
        """Test adding event with string category."""
        timeline = IncidentTimeline("INC-003", "Test")

        event = timeline.add_event(
            description="Test event",
            category="action",
        )

        assert event.category == EventCategory.ACTION

    def test_update_status(self):
        """Test updating incident status."""
        timeline = IncidentTimeline("INC-004", "Test")

        timeline.update_status(IncidentStatus.INVESTIGATING, "Starting investigation")

        assert timeline.incident.status == IncidentStatus.INVESTIGATING

        timeline.update_status(IncidentStatus.IDENTIFIED)
        assert timeline.incident.identified_at is not None

    def test_status_timestamps(self):
        """Test that status changes update timestamps."""
        timeline = IncidentTimeline("INC-005", "Test")

        timeline.update_status(IncidentStatus.IDENTIFIED)
        assert timeline.incident.identified_at is not None

        timeline.update_status(IncidentStatus.MITIGATING)
        assert timeline.incident.mitigated_at is not None

        timeline.update_status(IncidentStatus.RESOLVED)
        assert timeline.incident.resolved_at is not None

    def test_add_responder(self):
        """Test adding responders."""
        timeline = IncidentTimeline("INC-006", "Test")

        timeline.add_responder("alice@example.com")
        timeline.add_responder("bob@example.com")

        assert len(timeline.incident.responders) == 2
        assert "alice@example.com" in timeline.incident.responders

    def test_add_affected_service(self):
        """Test adding affected services."""
        timeline = IncidentTimeline("INC-007", "Test")

        timeline.add_affected_service("api-gateway")
        timeline.add_affected_service("database")

        assert len(timeline.incident.affected_services) == 2

    def test_set_root_cause(self):
        """Test setting root cause."""
        timeline = IncidentTimeline("INC-008", "Test")

        timeline.set_root_cause("Database connection pool exhausted")

        assert "connection pool" in timeline.incident.root_cause

    def test_set_resolution(self):
        """Test setting resolution."""
        timeline = IncidentTimeline("INC-009", "Test")

        timeline.set_resolution("Increased connection pool size")

        assert "connection pool" in timeline.incident.resolution

    def test_time_metrics(self):
        """Test time metric calculations."""
        timeline = IncidentTimeline("INC-010", "Test")

        timeline.update_status(IncidentStatus.IDENTIFIED)
        timeline.update_status(IncidentStatus.MITIGATING)
        timeline.update_status(IncidentStatus.RESOLVED)

        assert timeline.incident.time_to_detect is not None
        assert timeline.incident.total_duration is not None

    def test_generate_report(self):
        """Test report generation."""
        timeline = IncidentTimeline("INC-011", "Test Incident")

        timeline.add_event("Alert fired", category=EventCategory.ALERT)
        timeline.add_event("Investigation started", category=EventCategory.ACTION)
        timeline.update_status(IncidentStatus.RESOLVED)

        report = timeline.generate_report()

        assert report["incident_id"] == "INC-011"
        assert "timeline" in report
        assert "summary" in report

    def test_generate_postmortem(self):
        """Test post-mortem generation."""
        timeline = IncidentTimeline("INC-012", "Production Outage", severity="high")

        timeline.add_affected_service("api")
        timeline.set_root_cause("OOM kill")
        timeline.set_resolution("Added memory limits")
        timeline.add_responder("oncall@example.com")
        timeline.update_status(IncidentStatus.RESOLVED)

        postmortem = timeline.generate_postmortem()

        assert postmortem["incident_id"] == "INC-012"
        assert postmortem["root_cause"] == "OOM kill"
        assert "api" in postmortem["summary"]

    def test_filter_events_by_category(self):
        """Test filtering events by category."""
        timeline = IncidentTimeline("INC-013", "Test")

        timeline.add_event("Alert 1", category=EventCategory.ALERT)
        timeline.add_event("Action 1", category=EventCategory.ACTION)
        timeline.add_event("Alert 2", category=EventCategory.ALERT)

        alerts = timeline.get_timeline_by_category(EventCategory.ALERT)

        assert len(alerts) == 2


class TestIncidentManager:
    """Tests for IncidentManager."""

    def test_create_incident(self):
        """Test creating incident through manager."""
        manager = IncidentManager()

        timeline = manager.create_incident(
            incident_id="MGR-001",
            title="Test",
            severity="medium",
        )

        assert timeline is not None
        assert timeline.incident.incident_id == "MGR-001"

    def test_get_incident(self):
        """Test getting incident by ID."""
        manager = IncidentManager()

        manager.create_incident("MGR-002", "Test")

        retrieved = manager.get_incident("MGR-002")
        assert retrieved is not None

    def test_get_active_incidents(self):
        """Test getting active incidents."""
        manager = IncidentManager()

        active = manager.create_incident("MGR-003", "Active")
        assert active is not None  # Verify creation succeeded
        resolved = manager.create_incident("MGR-004", "Resolved")
        resolved.update_status(IncidentStatus.RESOLVED)

        active_list = manager.get_active_incidents()

        assert any(i.incident.incident_id == "MGR-003" for i in active_list)
        assert not any(i.incident.incident_id == "MGR-004" for i in active_list)


class TestTimelineEvent:
    """Tests for TimelineEvent."""

    def test_to_dict(self):
        """Test TimelineEvent serialization."""
        event = TimelineEvent(
            event_id="evt-1",
            timestamp=datetime.utcnow(),
            description="Test event",
            category=EventCategory.ACTION,
            actor="user@example.com",
        )

        data = event.to_dict()
        assert data["event_id"] == "evt-1"
        assert data["category"] == "action"


class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_incident_manager(self):
        """Test global manager singleton."""
        manager1 = get_incident_manager()
        manager2 = get_incident_manager()
        assert manager1 is manager2
