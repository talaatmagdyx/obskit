"""Additional coverage tests for audit.py."""
from __future__ import annotations

from datetime import datetime, timedelta

import obskit.audit as module
from obskit.audit import (
    AuditAction,
    AuditEntry,
    AuditQuery,
    AuditResult,
    AuditTrail,
    get_audit_trail,
)


class TestAuditTrailCoverage:
    def test_record_with_string_result_converts_to_enum(self):
        """Line 223: string result is converted to AuditResult enum."""
        audit = AuditTrail("cov-service-1")
        entry = audit.record(
            action=AuditAction.CREATE,
            actor="user:1",
            resource="doc:1",
            result="success",
        )
        assert entry.result == AuditResult.SUCCESS

    def test_record_trims_entries_when_over_10000(self):
        """Line 253: trim entries when >10000."""
        audit = AuditTrail("cov-service-trim")
        for i in range(10001):
            entry = AuditEntry(
                entry_id=f"e-{i}",
                timestamp=datetime.utcnow(),
                service="cov-service-trim",
                action="read",
                actor="u:1",
                resource="r:1",
                resource_type="doc",
                result=AuditResult.SUCCESS,
            )
            entry.hash = f"hash-{i}"
            audit._entries.append(entry)
        assert len(audit._entries) > 10000
        audit.record(action=AuditAction.READ, actor="user:1", resource="doc:1")
        assert len(audit._entries) <= 10000

    def test_record_with_sensitive_resource_type(self):
        """Lines 261-263: sensitive resource type increments metric."""
        audit = AuditTrail("cov-service-sensitive")
        audit.sensitive_resources = {"secret"}
        entry = audit.record(
            action=AuditAction.READ,
            actor="user:1",
            resource="secret:key",
            resource_type="secret",
        )
        assert entry is not None

    def test_record_with_storage_callback(self):
        """Lines 267-268: storage callback is called."""
        stored = []
        audit = AuditTrail("cov-service-cb", storage_callback=stored.append)
        audit.record(action=AuditAction.CREATE, actor="user:1", resource="doc:1")
        assert len(stored) == 1

    def test_record_with_storage_callback_exception(self):
        """Lines 269-270: exception in storage callback is caught."""
        def failing_callback(entry):
            raise RuntimeError("storage error")
        audit = AuditTrail("cov-service-cb-fail", storage_callback=failing_callback)
        entry = audit.record(action=AuditAction.CREATE, actor="user:1", resource="doc:1")
        assert entry is not None

    def test_verify_chain_empty_returns_true(self):
        """Line 300: empty chain returns (True, None)."""
        audit = AuditTrail("cov-service-empty-chain")
        is_valid, error = audit.verify_chain()
        assert is_valid is True
        assert error is None

    def test_verify_chain_tampered_entry(self):
        """Line 309: tampered hash is detected."""
        audit = AuditTrail("cov-service-tampered")
        audit.record(action=AuditAction.CREATE, actor="user:1", resource="doc:1")
        audit._entries[0].hash = "tampered-hash"
        is_valid, error = audit.verify_chain()
        assert is_valid is False
        assert error is not None

    def test_query_start_time_filter(self):
        """Line 335: start_time filter skips old entries."""
        audit = AuditTrail("cov-service-q-start")
        audit.record(action=AuditAction.CREATE, actor="user:1", resource="doc:1")
        query = AuditQuery(start_time=datetime.utcnow() + timedelta(hours=1))
        results = audit.query(query)
        assert results == []

    def test_query_end_time_filter(self):
        """Line 337: end_time filter skips future entries."""
        audit = AuditTrail("cov-service-q-end")
        audit.record(action=AuditAction.CREATE, actor="user:1", resource="doc:1")
        query = AuditQuery(end_time=datetime.utcnow() - timedelta(hours=1))
        results = audit.query(query)
        assert results == []

    def test_query_actor_filter(self):
        """Line 343: actor filter skips non-matching entries."""
        audit = AuditTrail("cov-service-q-actor")
        audit.record(action=AuditAction.CREATE, actor="user:1", resource="doc:1")
        audit.record(action=AuditAction.READ, actor="user:2", resource="doc:2")
        query = AuditQuery(actor="user:2")
        results = audit.query(query)
        assert all("user:2" in e.actor for e in results)

    def test_query_action_filter(self):
        """Line 345: action filter skips non-matching entries."""
        audit = AuditTrail("cov-service-q-action")
        audit.record(action=AuditAction.CREATE, actor="user:1", resource="doc:1")
        audit.record(action=AuditAction.READ, actor="user:1", resource="doc:1")
        query = AuditQuery(action="read")
        results = audit.query(query)
        assert all(e.action == "read" for e in results)

    def test_query_resource_filter(self):
        """Line 349: resource filter skips non-matching entries."""
        audit = AuditTrail("cov-service-q-resource")
        audit.record(action=AuditAction.CREATE, actor="user:1", resource="doc:A")
        audit.record(action=AuditAction.READ, actor="user:1", resource="doc:B")
        query = AuditQuery(resource="doc:B")
        results = audit.query(query)
        assert all("doc:B" in e.resource for e in results)

    def test_query_resource_type_filter(self):
        """Line 349: resource_type filter skips non-matching entries."""
        audit = AuditTrail("cov-service-q-rtype")
        audit.record(action=AuditAction.CREATE, actor="u:1", resource="r:1", resource_type="doc")
        audit.record(action=AuditAction.CREATE, actor="u:1", resource="r:2", resource_type="report")
        query = AuditQuery(resource_type="report")
        results = audit.query(query)
        assert all(e.resource_type == "report" for e in results)

    def test_query_result_filter(self):
        """Line 349: result filter skips non-matching entries."""
        audit = AuditTrail("cov-service-q-result")
        audit.record(action=AuditAction.CREATE, actor="u:1", resource="r:1", result=AuditResult.SUCCESS)
        audit.record(action=AuditAction.CREATE, actor="u:1", resource="r:2", result=AuditResult.FAILURE)
        query = AuditQuery(result=AuditResult.FAILURE)
        results = audit.query(query)
        assert all(e.result == AuditResult.FAILURE for e in results)

    def test_query_correlation_id_filter(self):
        """Line 349: correlation_id filter skips non-matching entries."""
        audit = AuditTrail("cov-service-q-corr")
        audit.record(action=AuditAction.CREATE, actor="u:1", resource="r:1", correlation_id="c-1")
        audit.record(action=AuditAction.CREATE, actor="u:1", resource="r:2", correlation_id="c-2")
        query = AuditQuery(correlation_id="c-1")
        results = audit.query(query)
        assert all(e.correlation_id == "c-1" for e in results)

    def test_query_limit_triggers_break(self):
        """Line 354: break when limit reached."""
        audit = AuditTrail("cov-service-q-limit")
        for i in range(10):
            audit.record(action=AuditAction.READ, actor="user:1", resource=f"doc:{i}")
        query = AuditQuery(limit=3)
        results = audit.query(query)
        assert len(results) == 3

    def test_get_denied_actions(self):
        """Lines 392-396: get_denied_actions returns DENIED entries."""
        audit = AuditTrail("cov-service-denied")
        audit.record(action=AuditAction.CREATE, actor="u:1", resource="r:1", result=AuditResult.SUCCESS)
        audit.record(action=AuditAction.DELETE, actor="u:2", resource="r:2", result=AuditResult.DENIED)
        denied = audit.get_denied_actions()
        assert len(denied) >= 1
        assert all(e.result == AuditResult.DENIED for e in denied)

    def test_get_audit_trail_singleton_inner_branch(self):
        """Line 425: inner lock branch of get_audit_trail."""
        unique_name = "__cov_trail_inner_branch__"
        module._trails.pop(unique_name, None)
        trail1 = module.get_audit_trail(unique_name)
        trail2 = module.get_audit_trail(unique_name)
        assert trail1 is trail2
        module._trails.pop(unique_name, None)
