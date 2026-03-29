"""Unit tests for Audit Trail."""

from datetime import datetime, timedelta, timezone, UTC

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
            start_time=datetime.now(UTC) - timedelta(hours=1),
            end_time=datetime.now(UTC) + timedelta(hours=1),
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
            start_time=datetime.now(UTC) - timedelta(hours=1),
            end_time=datetime.now(UTC) + timedelta(hours=1),
        )

        assert len(export) == 2
        assert all("entry_id" in e for e in export)


class TestAuditEntry:
    """Tests for AuditEntry."""

    def test_to_dict(self):
        """Test AuditEntry serialization."""
        entry = AuditEntry(
            entry_id="audit-1",
            timestamp=datetime.now(UTC),
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
            timestamp=datetime.now(UTC),
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


class TestAuditTrailCoverage:
    """Extra tests to cover missing lines in audit.py."""

    def test_record_with_string_result_converts_to_enum(self):
        """Test recording with string result converts to AuditResult enum (line 223)."""
        audit = AuditTrail("cover-service-1")

        entry = audit.record(
            action=AuditAction.CREATE,
            actor="user:1",
            resource="doc:1",
            result="success",  # string, not enum
        )

        assert entry.result == AuditResult.SUCCESS

    def test_record_trims_entries_when_over_10000(self):
        """Test that entries are trimmed when exceeding 10000 (line 253)."""
        audit = AuditTrail("cover-service-trim")

        # Manually add 10001 fake entries
        import time
        from datetime import datetime

        from obskit.audit import AuditEntry
        from obskit.audit import AuditResult as AR

        for i in range(10001):
            entry = AuditEntry(
                entry_id=f"e-{i}",
                timestamp=datetime.now(UTC),
                service="cover-service-trim",
                action="read",
                actor="u:1",
                resource="r:1",
                resource_type="doc",
                result=AR.SUCCESS,
            )
            entry.hash = f"hash-{i}"
            audit._entries.append(entry)

        assert len(audit._entries) > 10000

        # Now record one more to trigger the trim
        audit.record(
            action=AuditAction.READ,
            actor="user:1",
            resource="doc:1",
        )

        assert len(audit._entries) <= 10000

    def test_record_with_sensitive_resource_type(self):
        """Test recording with a sensitive resource type increments metric (lines 261-263)."""
        audit = AuditTrail("cover-service-sensitive")
        audit.sensitive_resources = {"secret"}

        entry = audit.record(
            action=AuditAction.READ,
            actor="user:1",
            resource="secret:key",
            resource_type="secret",
        )

        assert entry is not None

    def test_record_with_storage_callback(self):
        """Test storage callback is called (lines 267-268)."""
        stored = []

        audit = AuditTrail("cover-service-cb", storage_callback=stored.append)

        audit.record(
            action=AuditAction.CREATE,
            actor="user:1",
            resource="doc:1",
        )

        assert len(stored) == 1

    def test_record_with_storage_callback_exception(self):
        """Test storage callback exception is caught and logged (lines 269-270)."""

        def failing_callback(entry):
            raise RuntimeError("storage error")

        audit = AuditTrail("cover-service-cb-fail", storage_callback=failing_callback)

        # Should not raise, exception should be caught
        entry = audit.record(
            action=AuditAction.CREATE,
            actor="user:1",
            resource="doc:1",
        )

        assert entry is not None

    def test_verify_chain_empty_returns_true(self):
        """Test verify_chain with no entries returns (True, None) (line 300)."""
        audit = AuditTrail("cover-service-empty-chain")

        is_valid, error = audit.verify_chain()

        assert is_valid is True
        assert error is None

    def test_verify_chain_tampered_entry(self):
        """Test verify_chain detects tampered hash (line 309)."""
        audit = AuditTrail("cover-service-tampered")

        audit.record(
            action=AuditAction.CREATE,
            actor="user:1",
            resource="doc:1",
        )

        # Tamper with the hash of first entry
        audit._entries[0].hash = "tampered-hash"

        is_valid, error = audit.verify_chain()

        assert is_valid is False
        assert error is not None

    def test_query_with_all_filters(self):
        """Test query applies all filter conditions (lines 335, 337, 343, 345, 349, 354)."""
        from datetime import datetime, timedelta

        audit = AuditTrail("cover-service-query-all")

        # Add entries with varying attributes
        audit.record(
            action=AuditAction.CREATE,
            actor="user:1",
            resource="doc:1",
            resource_type="document",
            result=AuditResult.SUCCESS,
            correlation_id="corr-1",
        )
        audit.record(
            action=AuditAction.READ,
            actor="user:2",
            resource="doc:2",
            resource_type="report",
            result=AuditResult.FAILURE,
            correlation_id="corr-2",
        )

        # Query with start_time filter that excludes old entries
        query = AuditQuery(
            start_time=datetime.now(UTC) + timedelta(hours=1),  # in the future => skip all
        )
        results = audit.query(query)
        assert results == []

        # Query with end_time that excludes entries
        query = AuditQuery(
            end_time=datetime.now(UTC) - timedelta(hours=1),  # in the past => skip all
        )
        results = audit.query(query)
        assert results == []

        # Query with actor filter
        query = AuditQuery(actor="user:2")
        results = audit.query(query)
        assert all("user:2" in e.actor for e in results)

        # Query with action filter
        query = AuditQuery(action="read")
        results = audit.query(query)
        assert all(e.action == "read" for e in results)

        # Query with resource filter
        query = AuditQuery(resource="doc:2")
        results = audit.query(query)
        assert all("doc:2" in e.resource for e in results)

        # Query with resource_type filter
        query = AuditQuery(resource_type="report")
        results = audit.query(query)
        assert all(e.resource_type == "report" for e in results)

        # Query with result filter
        query = AuditQuery(result=AuditResult.FAILURE)
        results = audit.query(query)
        assert all(e.result == AuditResult.FAILURE for e in results)

        # Query with correlation_id filter
        query = AuditQuery(correlation_id="corr-1")
        results = audit.query(query)
        assert all(e.correlation_id == "corr-1" for e in results)

    def test_query_limit_triggers_break(self):
        """Test query stops at limit (line 354 break)."""
        audit = AuditTrail("cover-service-query-limit")

        for i in range(10):
            audit.record(action=AuditAction.READ, actor="user:1", resource=f"doc:{i}")

        query = AuditQuery(limit=3)
        results = audit.query(query)

        assert len(results) == 3

    def test_get_denied_actions(self):
        """Test get_denied_actions returns DENIED entries (lines 392-396)."""
        audit = AuditTrail("cover-service-denied")

        audit.record(
            action=AuditAction.CREATE, actor="user:1", resource="doc:1", result=AuditResult.SUCCESS
        )
        audit.record(
            action=AuditAction.DELETE, actor="user:2", resource="doc:2", result=AuditResult.DENIED
        )

        denied = audit.get_denied_actions()

        assert len(denied) >= 1
        assert all(e.result == AuditResult.DENIED for e in denied)

    def test_get_audit_trail_singleton_inner_branch(self):
        """Test get_audit_trail creates trail in inner lock branch (line 425)."""
        import obskit.audit as module

        unique_name = "__test_trail_inner_branch__"
        module._trails.pop(unique_name, None)

        trail1 = module.get_audit_trail(unique_name)
        trail2 = module.get_audit_trail(unique_name)

        assert trail1 is trail2
        module._trails.pop(unique_name, None)
