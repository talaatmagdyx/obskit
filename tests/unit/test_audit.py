"""Unit tests for Audit Trail."""

from datetime import datetime, timedelta

from obskit.audit import (
    AuditAction,
    AuditEntry,
    AuditQuery,
    AuditResult,
    AuditTrail,
    get_audit_trail,
)


class TestAuditTrail:
    """Tests for AuditTrail."""

    def test_record_action(self):
        """Test recording an audit action."""
        audit = AuditTrail("test-service")

        entry = audit.record(
            action=AuditAction.CREATE,
            actor="user:123",
            resource="order:456",
            resource_type="order",
        )

        assert entry.entry_id is not None
        assert entry.action == "create"
        assert entry.actor == "user:123"

    def test_record_with_details(self):
        """Test recording with additional details."""
        audit = AuditTrail("test-service")

        entry = audit.record(
            action="custom_action",
            actor="admin:1",
            resource="config:app",
            resource_type="config",
            details={"old_value": "a", "new_value": "b"},
            ip_address="192.168.1.1",
        )

        assert entry.details["old_value"] == "a"
        assert entry.ip_address == "192.168.1.1"

    def test_record_failure(self):
        """Test recording a failed action."""
        audit = AuditTrail("test-service")

        entry = audit.record(
            action=AuditAction.DELETE,
            actor="user:456",
            resource="secret:789",
            result=AuditResult.DENIED,
        )

        assert entry.result == AuditResult.DENIED

    def test_chain_integrity(self):
        """Test audit chain integrity verification."""
        audit = AuditTrail("test-service")

        # Record several entries
        for i in range(5):
            audit.record(
                action=AuditAction.READ,
                actor=f"user:{i}",
                resource=f"doc:{i}",
            )

        is_valid, error = audit.verify_chain()
        assert is_valid is True
        assert error is None

    def test_query_by_actor(self):
        """Test querying by actor."""
        audit = AuditTrail("test-service")

        audit.record(action=AuditAction.CREATE, actor="user:1", resource="a")
        audit.record(action=AuditAction.CREATE, actor="user:2", resource="b")
        audit.record(action=AuditAction.UPDATE, actor="user:1", resource="a")

        query = AuditQuery(actor="user:1")
        results = audit.query(query)

        assert len(results) == 2
        for entry in results:
            assert "user:1" in entry.actor

    def test_query_by_action(self):
        """Test querying by action."""
        audit = AuditTrail("test-service")

        audit.record(action=AuditAction.CREATE, actor="user:1", resource="a")
        audit.record(action=AuditAction.READ, actor="user:1", resource="a")
        audit.record(action=AuditAction.UPDATE, actor="user:1", resource="a")

        query = AuditQuery(action="create")
        results = audit.query(query)

        assert len(results) == 1
        assert results[0].action == "create"

    def test_query_by_time_range(self):
        """Test querying by time range."""
        audit = AuditTrail("test-service")

        audit.record(action=AuditAction.CREATE, actor="user:1", resource="a")

        query = AuditQuery(
            start_time=datetime.utcnow() - timedelta(hours=1),
            end_time=datetime.utcnow() + timedelta(hours=1),
        )
        results = audit.query(query)

        assert len(results) >= 1

    def test_get_actor_activity(self):
        """Test getting actor activity."""
        audit = AuditTrail("test-service")

        audit.record(action=AuditAction.LOGIN, actor="user:100", resource="session:1")
        audit.record(action=AuditAction.READ, actor="user:100", resource="data:1")

        activity = audit.get_actor_activity("user:100")

        assert len(activity) == 2

    def test_get_resource_history(self):
        """Test getting resource history."""
        audit = AuditTrail("test-service")

        audit.record(action=AuditAction.CREATE, actor="user:1", resource="doc:42")
        audit.record(action=AuditAction.UPDATE, actor="user:2", resource="doc:42")
        audit.record(action=AuditAction.READ, actor="user:3", resource="doc:42")

        history = audit.get_resource_history("doc:42")

        assert len(history) == 3

    def test_get_failed_actions(self):
        """Test getting failed actions."""
        audit = AuditTrail("test-service")

        audit.record(
            action=AuditAction.CREATE, actor="user:1", resource="a", result=AuditResult.SUCCESS
        )
        audit.record(
            action=AuditAction.DELETE, actor="user:2", resource="b", result=AuditResult.FAILURE
        )

        failed = audit.get_failed_actions()

        assert len(failed) == 1
        assert failed[0].result == AuditResult.FAILURE

    def test_export_for_compliance(self):
        """Test compliance export."""
        audit = AuditTrail("test-service")

        audit.record(action=AuditAction.CREATE, actor="user:1", resource="a")
        audit.record(action=AuditAction.UPDATE, actor="user:2", resource="b")

        export = audit.export_for_compliance(
            start_time=datetime.utcnow() - timedelta(hours=1),
            end_time=datetime.utcnow() + timedelta(hours=1),
        )

        assert len(export) == 2
        assert all("entry_id" in e for e in export)


class TestAuditEntry:
    """Tests for AuditEntry."""

    def test_to_dict(self):
        """Test AuditEntry serialization."""
        entry = AuditEntry(
            entry_id="audit-1",
            timestamp=datetime.utcnow(),
            service="test",
            action="create",
            actor="user:1",
            resource="doc:1",
            resource_type="document",
            result=AuditResult.SUCCESS,
        )

        data = entry.to_dict()
        assert data["entry_id"] == "audit-1"
        assert data["action"] == "create"
        assert data["result"] == "success"

    def test_to_json(self):
        """Test AuditEntry JSON serialization."""
        entry = AuditEntry(
            entry_id="audit-1",
            timestamp=datetime.utcnow(),
            service="test",
            action="create",
            actor="user:1",
            resource="doc:1",
            resource_type="document",
            result=AuditResult.SUCCESS,
        )

        json_str = entry.to_json()
        assert "audit-1" in json_str


class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_audit_trail(self):
        """Test audit trail singleton per service."""
        audit1 = get_audit_trail("service1")
        audit2 = get_audit_trail("service1")
        audit3 = get_audit_trail("service2")

        assert audit1 is audit2
        assert audit1 is not audit3
