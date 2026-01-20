"""Unit tests for Runbook Integration."""

from obskit.runbook import (
    Runbook,
    RunbookExecution,
    RunbookManager,
    RunbookStatus,
    get_runbook_manager,
)


class TestRunbookManager:
    """Tests for RunbookManager."""

    def test_register_runbook(self):
        """Test registering a runbook."""
        manager = RunbookManager()

        manager.register(
            runbook_id="high-memory",
            title="High Memory Usage",
            steps=["Check memory usage", "Identify memory hogs", "Restart service"],
            description="Handle high memory alerts",
            alert_patterns=["HighMemory*"],
        )

        runbook = manager.get_runbook("high-memory")
        assert runbook is not None
        assert runbook.title == "High Memory Usage"
        assert len(runbook.steps) == 3

    def test_register_with_detailed_steps(self):
        """Test registering with detailed step objects."""
        manager = RunbookManager()

        manager.register(
            runbook_id="db-issue",
            title="Database Issue",
            steps=[
                {
                    "title": "Check Connection",
                    "description": "Verify database connectivity",
                    "command": "psql -c 'SELECT 1'",
                    "expected_outcome": "Returns 1",
                },
                {
                    "title": "Check Slow Queries",
                    "description": "Look for slow queries",
                    "command": "SELECT * FROM pg_stat_activity",
                },
            ],
        )

        runbook = manager.get_runbook("db-issue")
        assert len(runbook.steps) == 2
        assert runbook.steps[0].command == "psql -c 'SELECT 1'"

    def test_get_for_alert(self):
        """Test finding runbook for an alert."""
        manager = RunbookManager()

        manager.register(
            runbook_id="memory-rb",
            title="Memory Runbook",
            steps=["Step 1"],
            alert_patterns=["HighMemory*", "OOMKill*"],
        )

        runbook = manager.get_for_alert("HighMemoryUsage")
        assert runbook is not None
        assert runbook.runbook_id == "memory-rb"

        runbook = manager.get_for_alert("OOMKillDetected")
        assert runbook is not None

    def test_search_by_query(self):
        """Test searching runbooks by text."""
        manager = RunbookManager()

        manager.register(
            runbook_id="rb1",
            title="Database Recovery",
            steps=["Step"],
            description="Recover from database failures",
        )
        manager.register(
            runbook_id="rb2",
            title="Network Issue",
            steps=["Step"],
        )

        results = manager.search(query="database")
        assert len(results) == 1
        assert results[0].runbook_id == "rb1"

    def test_search_by_tags(self):
        """Test searching runbooks by tags."""
        manager = RunbookManager()

        manager.register(
            runbook_id="rb1",
            title="Runbook 1",
            steps=["Step"],
            tags=["database", "critical"],
        )
        manager.register(
            runbook_id="rb2",
            title="Runbook 2",
            steps=["Step"],
            tags=["network"],
        )

        results = manager.search(tags=["database"])
        assert len(results) == 1

    def test_start_execution(self):
        """Test starting runbook execution."""
        manager = RunbookManager()

        manager.register(
            runbook_id="test-rb",
            title="Test Runbook",
            steps=["Step 1", "Step 2"],
        )

        execution = manager.start_execution(
            runbook_id="test-rb",
            alert_name="TestAlert",
            executor="user@example.com",
        )

        assert execution is not None
        assert execution.runbook_id == "test-rb"
        assert execution.status == RunbookStatus.IN_PROGRESS
        assert execution.current_step == 1

    def test_update_execution(self):
        """Test updating execution progress."""
        manager = RunbookManager()

        manager.register(
            runbook_id="progress-rb",
            title="Progress Runbook",
            steps=["Step 1", "Step 2", "Step 3"],
        )

        execution = manager.start_execution("progress-rb")

        manager.update_execution(
            execution.execution_id,
            current_step=2,
            step_note="Completed step 1 successfully",
        )

        updated = manager.get_execution(execution.execution_id)
        assert updated.current_step == 2
        assert "Completed" in updated.step_notes.get(2, "")

    def test_complete_execution(self):
        """Test completing execution."""
        manager = RunbookManager()

        manager.register(
            runbook_id="complete-rb",
            title="Complete Runbook",
            steps=["Step 1"],
        )

        execution = manager.start_execution("complete-rb")

        manager.complete_execution(
            execution.execution_id,
            resolved=True,
            notes="Issue fixed",
        )

        completed = manager.get_execution(execution.execution_id)
        assert completed.status == RunbookStatus.COMPLETED
        assert completed.resolved_issue is True

    def test_fail_execution(self):
        """Test failing execution."""
        manager = RunbookManager()

        manager.register(
            runbook_id="fail-rb",
            title="Fail Runbook",
            steps=["Step 1"],
        )

        execution = manager.start_execution("fail-rb")

        manager.fail_execution(execution.execution_id, "Step failed")

        failed = manager.get_execution(execution.execution_id)
        assert failed.status == RunbookStatus.FAILED

    def test_escalate_execution(self):
        """Test escalating execution."""
        manager = RunbookManager()

        manager.register(
            runbook_id="escalate-rb",
            title="Escalate Runbook",
            steps=["Step 1"],
        )

        execution = manager.start_execution("escalate-rb")

        manager.escalate_execution(execution.execution_id, "Need expert help")

        escalated = manager.get_execution(execution.execution_id)
        assert escalated.status == RunbookStatus.ESCALATED

    def test_get_recent_executions(self):
        """Test getting recent executions."""
        manager = RunbookManager()

        manager.register(
            runbook_id="recent-rb",
            title="Recent Runbook",
            steps=["Step 1"],
        )

        for _i in range(5):
            manager.start_execution("recent-rb")

        recent = manager.get_recent_executions(limit=3)
        assert len(recent) == 3


class TestRunbook:
    """Tests for Runbook."""

    def test_to_dict(self):
        """Test Runbook serialization."""
        from obskit.runbook import RunbookStep

        runbook = Runbook(
            runbook_id="test",
            title="Test Runbook",
            description="Description",
            steps=[RunbookStep(1, "Step 1", "Do something")],
            alert_patterns=["Alert*"],
        )

        data = runbook.to_dict()
        assert data["runbook_id"] == "test"
        assert len(data["steps"]) == 1


class TestRunbookExecution:
    """Tests for RunbookExecution."""

    def test_duration_calculation(self):
        """Test duration calculation."""
        from datetime import datetime, timedelta

        execution = RunbookExecution(
            execution_id="exec-1",
            runbook_id="rb-1",
            started_at=datetime.utcnow() - timedelta(minutes=30),
            completed_at=datetime.utcnow(),
        )

        assert execution.duration_seconds is not None
        assert execution.duration_seconds > 1700  # ~30 minutes


class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_runbook_manager(self):
        """Test global manager singleton."""
        manager1 = get_runbook_manager()
        manager2 = get_runbook_manager()
        assert manager1 is manager2
