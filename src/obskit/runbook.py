"""
Runbook Integration
===================

Link alerts to runbooks for quick remediation.

Features:
- Runbook catalog
- Alert-to-runbook mapping
- Execution tracking
- Effectiveness metrics

Example:
    from obskit.runbook import RunbookManager

    runbooks = RunbookManager()

    # Register a runbook
    runbooks.register(
        "high-memory",
        title="High Memory Usage",
        steps=["Check memory hogs", "Restart service", "Scale up"],
        alert_patterns=["HighMemory*"]
    )

    # Get runbook for alert
    runbook = runbooks.get_for_alert("HighMemoryUsage")
"""

import fnmatch
import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from prometheus_client import Counter, Gauge, Histogram

from obskit.logging import get_logger

logger = get_logger(__name__)


# =============================================================================
# Prometheus Metrics
# =============================================================================

RUNBOOK_EXECUTIONS = Counter(
    "runbook_executions_total", "Total runbook executions", ["runbook_id", "result"]
)

RUNBOOK_DURATION = Histogram(
    "runbook_execution_duration_seconds",
    "Runbook execution duration",
    ["runbook_id"],
    buckets=(60, 300, 600, 1800, 3600, 7200),
)

RUNBOOK_EFFECTIVENESS = Gauge(
    "runbook_effectiveness_percent", "Runbook effectiveness (success rate)", ["runbook_id"]
)


# =============================================================================
# Enums and Data Classes
# =============================================================================


class RunbookStatus(Enum):
    """Runbook execution status."""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ESCALATED = "escalated"


@dataclass
class RunbookStep:
    """A step in a runbook."""

    step_number: int
    title: str
    description: str
    command: str | None = None
    expected_outcome: str | None = None
    rollback: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_number": self.step_number,
            "title": self.title,
            "description": self.description,
            "command": self.command,
            "expected_outcome": self.expected_outcome,
            "rollback": self.rollback,
        }


@dataclass
class Runbook:
    """A runbook definition."""

    runbook_id: str
    title: str
    description: str
    steps: list[RunbookStep]
    alert_patterns: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    owner: str | None = None
    severity: str = "medium"
    estimated_duration_minutes: int = 30
    requires_approval: bool = False
    external_link: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "runbook_id": self.runbook_id,
            "title": self.title,
            "description": self.description,
            "steps": [s.to_dict() for s in self.steps],
            "alert_patterns": self.alert_patterns,
            "tags": self.tags,
            "owner": self.owner,
            "severity": self.severity,
            "estimated_duration_minutes": self.estimated_duration_minutes,
            "requires_approval": self.requires_approval,
            "external_link": self.external_link,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class RunbookExecution:
    """A runbook execution record."""

    execution_id: str
    runbook_id: str
    alert_name: str | None = None
    executor: str | None = None
    status: RunbookStatus = RunbookStatus.NOT_STARTED
    started_at: datetime | None = None
    completed_at: datetime | None = None
    current_step: int = 0
    step_notes: dict[int, str] = field(default_factory=dict)
    result_notes: str = ""
    resolved_issue: bool = False

    @property
    def duration_seconds(self) -> float | None:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "runbook_id": self.runbook_id,
            "alert_name": self.alert_name,
            "executor": self.executor,
            "status": self.status.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "current_step": self.current_step,
            "duration_seconds": self.duration_seconds,
            "resolved_issue": self.resolved_issue,
        }


# =============================================================================
# Runbook Manager
# =============================================================================


class RunbookManager:
    """
    Manage runbooks and their execution.

    Parameters
    ----------
    default_runbook_link : str, optional
        Default link template for external runbooks
    """

    def __init__(
        self,
        default_runbook_link: str | None = None,
    ):
        self.default_runbook_link = default_runbook_link

        self._runbooks: dict[str, Runbook] = {}
        self._executions: dict[str, RunbookExecution] = {}
        self._execution_counter = 0
        self._lock = threading.Lock()

    def register(
        self,
        runbook_id: str,
        title: str,
        steps: list[str | dict[str, Any]],
        description: str = "",
        alert_patterns: list[str] | None = None,
        tags: list[str] | None = None,
        owner: str | None = None,
        severity: str = "medium",
        estimated_duration_minutes: int = 30,
        requires_approval: bool = False,
        external_link: str | None = None,
    ):
        """
        Register a runbook.

        Parameters
        ----------
        runbook_id : str
            Unique runbook ID
        title : str
            Runbook title
        steps : list
            List of steps (strings or dicts)
        description : str
            Runbook description
        alert_patterns : list, optional
            Alert name patterns to match
        tags : list, optional
            Tags for categorization
        owner : str, optional
            Owner/team
        severity : str
            Severity level
        estimated_duration_minutes : int
            Estimated time to complete
        requires_approval : bool
            Whether approval is needed
        external_link : str, optional
            Link to external documentation
        """
        # Convert steps to RunbookStep objects
        step_objects = []
        for i, step in enumerate(steps, 1):
            if isinstance(step, str):
                step_objects.append(
                    RunbookStep(
                        step_number=i,
                        title=f"Step {i}",
                        description=step,
                    )
                )
            else:
                step_objects.append(
                    RunbookStep(
                        step_number=i,
                        title=step.get("title", f"Step {i}"),
                        description=step.get("description", ""),
                        command=step.get("command"),
                        expected_outcome=step.get("expected_outcome"),
                        rollback=step.get("rollback"),
                    )
                )

        runbook = Runbook(
            runbook_id=runbook_id,
            title=title,
            description=description,
            steps=step_objects,
            alert_patterns=alert_patterns or [],
            tags=tags or [],
            owner=owner,
            severity=severity,
            estimated_duration_minutes=estimated_duration_minutes,
            requires_approval=requires_approval,
            external_link=external_link,
        )

        with self._lock:
            self._runbooks[runbook_id] = runbook

        logger.info(
            "runbook_registered",
            runbook_id=runbook_id,
            title=title,
            steps_count=len(step_objects),
        )

    def get_runbook(self, runbook_id: str) -> Runbook | None:
        """Get a runbook by ID."""
        with self._lock:
            return self._runbooks.get(runbook_id)

    def get_for_alert(self, alert_name: str) -> Runbook | None:
        """
        Find a runbook for an alert.

        Parameters
        ----------
        alert_name : str
            Name of the alert

        Returns
        -------
        Runbook or None
        """
        with self._lock:
            for runbook in self._runbooks.values():
                for pattern in runbook.alert_patterns:
                    if fnmatch.fnmatch(alert_name, pattern):
                        return runbook
        return None

    def search(
        self,
        query: str | None = None,
        tags: list[str] | None = None,
        severity: str | None = None,
    ) -> list[Runbook]:
        """
        Search runbooks.

        Parameters
        ----------
        query : str, optional
            Text search in title/description
        tags : list, optional
            Filter by tags
        severity : str, optional
            Filter by severity

        Returns
        -------
        list
            Matching runbooks
        """
        with self._lock:
            results = list(self._runbooks.values())

        if query:
            query_lower = query.lower()
            results = [
                r
                for r in results
                if query_lower in r.title.lower() or query_lower in r.description.lower()
            ]

        if tags:
            results = [r for r in results if any(t in r.tags for t in tags)]

        if severity:
            results = [r for r in results if r.severity == severity]

        return results

    def start_execution(
        self,
        runbook_id: str,
        alert_name: str | None = None,
        executor: str | None = None,
    ) -> RunbookExecution | None:
        """
        Start a runbook execution.

        Parameters
        ----------
        runbook_id : str
            Runbook to execute
        alert_name : str, optional
            Triggering alert
        executor : str, optional
            Person executing

        Returns
        -------
        RunbookExecution or None
        """
        with self._lock:
            if runbook_id not in self._runbooks:
                return None

            self._execution_counter += 1
            execution_id = f"exec-{runbook_id}-{self._execution_counter}"

            execution = RunbookExecution(
                execution_id=execution_id,
                runbook_id=runbook_id,
                alert_name=alert_name,
                executor=executor,
                status=RunbookStatus.IN_PROGRESS,
                started_at=datetime.utcnow(),
                current_step=1,
            )

            self._executions[execution_id] = execution

        logger.info(
            "runbook_execution_started",
            execution_id=execution_id,
            runbook_id=runbook_id,
            executor=executor,
        )

        return execution

    def update_execution(
        self,
        execution_id: str,
        current_step: int | None = None,
        step_note: str | None = None,
    ):
        """Update execution progress."""
        with self._lock:
            if execution_id not in self._executions:
                return

            execution = self._executions[execution_id]

            if current_step:
                execution.current_step = current_step

            if step_note:
                execution.step_notes[execution.current_step] = step_note

    def complete_execution(
        self,
        execution_id: str,
        resolved: bool = True,
        notes: str = "",
    ):
        """
        Complete a runbook execution.

        Parameters
        ----------
        execution_id : str
            Execution ID
        resolved : bool
            Whether issue was resolved
        notes : str
            Result notes
        """
        with self._lock:
            if execution_id not in self._executions:
                return

            execution = self._executions[execution_id]
            execution.status = RunbookStatus.COMPLETED
            execution.completed_at = datetime.utcnow()
            execution.resolved_issue = resolved
            execution.result_notes = notes

        # Record metrics
        RUNBOOK_EXECUTIONS.labels(
            runbook_id=execution.runbook_id, result="resolved" if resolved else "unresolved"
        ).inc()

        if execution.duration_seconds:
            RUNBOOK_DURATION.labels(runbook_id=execution.runbook_id).observe(
                execution.duration_seconds
            )

        # Update effectiveness
        self._update_effectiveness(execution.runbook_id)

        logger.info(
            "runbook_execution_completed",
            execution_id=execution_id,
            runbook_id=execution.runbook_id,
            resolved=resolved,
            duration_seconds=execution.duration_seconds,
        )

    def fail_execution(
        self,
        execution_id: str,
        reason: str = "",
    ):
        """Mark execution as failed."""
        with self._lock:
            if execution_id not in self._executions:
                return

            execution = self._executions[execution_id]
            execution.status = RunbookStatus.FAILED
            execution.completed_at = datetime.utcnow()
            execution.result_notes = reason

        RUNBOOK_EXECUTIONS.labels(runbook_id=execution.runbook_id, result="failed").inc()

        self._update_effectiveness(execution.runbook_id)

    def escalate_execution(
        self,
        execution_id: str,
        reason: str = "",
    ):
        """Escalate execution."""
        with self._lock:
            if execution_id not in self._executions:
                return

            execution = self._executions[execution_id]
            execution.status = RunbookStatus.ESCALATED
            execution.result_notes = reason

        RUNBOOK_EXECUTIONS.labels(runbook_id=execution.runbook_id, result="escalated").inc()

    def _update_effectiveness(self, runbook_id: str):
        """Update effectiveness metric for a runbook."""
        with self._lock:
            executions = [
                e
                for e in self._executions.values()
                if e.runbook_id == runbook_id and e.status == RunbookStatus.COMPLETED
            ]

        if executions:
            resolved = sum(1 for e in executions if e.resolved_issue)
            effectiveness = (resolved / len(executions)) * 100

            RUNBOOK_EFFECTIVENESS.labels(runbook_id=runbook_id).set(effectiveness)

    def get_execution(self, execution_id: str) -> RunbookExecution | None:
        """Get an execution by ID."""
        with self._lock:
            return self._executions.get(execution_id)

    def get_recent_executions(
        self,
        runbook_id: str | None = None,
        limit: int = 20,
    ) -> list[RunbookExecution]:
        """Get recent executions."""
        with self._lock:
            executions = list(self._executions.values())

        if runbook_id:
            executions = [e for e in executions if e.runbook_id == runbook_id]

        executions.sort(key=lambda e: e.started_at or datetime.min, reverse=True)
        return executions[:limit]


# =============================================================================
# Singleton
# =============================================================================

_manager: RunbookManager | None = None
_manager_lock = threading.Lock()


def get_runbook_manager(**kwargs) -> RunbookManager:
    """Get or create the global runbook manager."""
    global _manager

    if _manager is None:
        with _manager_lock:
            if _manager is None:
                _manager = RunbookManager(**kwargs)

    return _manager
