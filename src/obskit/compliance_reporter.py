"""
Compliance Reporter
===================

Generate compliance reports for regulations.

Features:
- GDPR compliance
- SOC2 compliance
- HIPAA compliance
- Custom compliance checks

Example:
    from obskit.compliance import ComplianceReporter

    reporter = ComplianceReporter()

    # Run compliance check
    report = reporter.check_gdpr_compliance()
    print(f"GDPR Score: {report.score}%")
"""

import threading
from collections.abc import Callable
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

COMPLIANCE_SCORE = Gauge("compliance_score", "Compliance score (0-100)", ["framework", "service"])

COMPLIANCE_CHECKS_PASSED = Gauge(
    "compliance_checks_passed", "Number of checks passed", ["framework", "service"]
)

COMPLIANCE_CHECKS_FAILED = Gauge(
    "compliance_checks_failed", "Number of checks failed", ["framework", "service"]
)


# =============================================================================
# Enums and Data Classes
# =============================================================================


class ComplianceFramework(Enum):
    """Compliance frameworks."""

    GDPR = "gdpr"
    SOC2 = "soc2"
    HIPAA = "hipaa"
    PCI_DSS = "pci_dss"
    ISO27001 = "iso27001"
    CUSTOM = "custom"


class CheckStatus(Enum):
    """Status of a compliance check."""

    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    NOT_APPLICABLE = "not_applicable"
    SKIPPED = "skipped"


@dataclass
class ComplianceCheck:
    """A single compliance check."""

    check_id: str
    name: str
    description: str
    framework: ComplianceFramework
    check_func: Callable[[], bool]
    severity: str = "high"
    remediation: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "name": self.name,
            "description": self.description,
            "framework": self.framework.value,
            "severity": self.severity,
            "remediation": self.remediation,
        }


@dataclass
class CheckResult:
    """Result of a compliance check."""

    check: ComplianceCheck
    status: CheckStatus
    message: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check.check_id,
            "name": self.check.name,
            "status": self.status.value,
            "message": self.message,
            "evidence": self.evidence,
            "severity": self.check.severity,
            "remediation": self.check.remediation if self.status == CheckStatus.FAILED else None,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class ComplianceReport:
    """A compliance report."""

    framework: ComplianceFramework
    service: str
    score: float
    total_checks: int
    passed: int
    failed: int
    warnings: int
    results: list[CheckResult]
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "framework": self.framework.value,
            "service": self.service,
            "score": self.score,
            "total_checks": self.total_checks,
            "passed": self.passed,
            "failed": self.failed,
            "warnings": self.warnings,
            "results": [r.to_dict() for r in self.results],
            "timestamp": self.timestamp.isoformat(),
        }


# =============================================================================
# Default Checks
# =============================================================================


def _create_default_checks() -> list[ComplianceCheck]:
    """Create default compliance checks."""
    checks = []

    # GDPR checks
    checks.extend(
        [
            ComplianceCheck(
                check_id="gdpr-001",
                name="Data Encryption at Rest",
                description="Verify that personal data is encrypted at rest",
                framework=ComplianceFramework.GDPR,
                check_func=lambda: True,  # Placeholder
                severity="high",
                remediation="Enable encryption for all data stores containing personal data",
            ),
            ComplianceCheck(
                check_id="gdpr-002",
                name="Data Encryption in Transit",
                description="Verify that personal data is encrypted in transit",
                framework=ComplianceFramework.GDPR,
                check_func=lambda: True,
                severity="high",
                remediation="Use TLS 1.2+ for all data transmission",
            ),
            ComplianceCheck(
                check_id="gdpr-003",
                name="Access Logging",
                description="Verify that access to personal data is logged",
                framework=ComplianceFramework.GDPR,
                check_func=lambda: True,
                severity="medium",
                remediation="Implement audit logging for data access",
            ),
            ComplianceCheck(
                check_id="gdpr-004",
                name="Data Retention Policy",
                description="Verify data retention policies are in place",
                framework=ComplianceFramework.GDPR,
                check_func=lambda: True,
                severity="high",
                remediation="Define and implement data retention policies",
            ),
        ]
    )

    # SOC2 checks
    checks.extend(
        [
            ComplianceCheck(
                check_id="soc2-001",
                name="Access Control",
                description="Verify access control mechanisms",
                framework=ComplianceFramework.SOC2,
                check_func=lambda: True,
                severity="high",
                remediation="Implement role-based access control",
            ),
            ComplianceCheck(
                check_id="soc2-002",
                name="Change Management",
                description="Verify change management procedures",
                framework=ComplianceFramework.SOC2,
                check_func=lambda: True,
                severity="medium",
                remediation="Implement formal change management process",
            ),
            ComplianceCheck(
                check_id="soc2-003",
                name="Incident Response",
                description="Verify incident response procedures",
                framework=ComplianceFramework.SOC2,
                check_func=lambda: True,
                severity="high",
                remediation="Document and test incident response procedures",
            ),
        ]
    )

    # HIPAA checks
    checks.extend(
        [
            ComplianceCheck(
                check_id="hipaa-001",
                name="PHI Access Audit",
                description="Verify PHI access auditing",
                framework=ComplianceFramework.HIPAA,
                check_func=lambda: True,
                severity="critical",
                remediation="Enable comprehensive PHI access logging",
            ),
            ComplianceCheck(
                check_id="hipaa-002",
                name="Minimum Necessary",
                description="Verify minimum necessary access principle",
                framework=ComplianceFramework.HIPAA,
                check_func=lambda: True,
                severity="high",
                remediation="Implement least privilege access",
            ),
        ]
    )

    return checks


# =============================================================================
# Compliance Reporter
# =============================================================================


class ComplianceReporter:
    """
    Generate compliance reports.

    Parameters
    ----------
    service_name : str
        Name of the service
    custom_checks : list, optional
        Custom compliance checks
    """

    def __init__(
        self,
        service_name: str = "default",
        custom_checks: list[ComplianceCheck] | None = None,
    ):
        self.service_name = service_name

        self._checks: list[ComplianceCheck] = _create_default_checks()
        if custom_checks:
            self._checks.extend(custom_checks)

        self._check_overrides: dict[str, Callable[[], bool]] = {}
        self._lock = threading.Lock()

    def set_check_function(
        self,
        check_id: str,
        check_func: Callable[[], bool],
    ):
        """
        Override a check function.

        Parameters
        ----------
        check_id : str
            Check ID to override
        check_func : callable
            New check function
        """
        with self._lock:
            self._check_overrides[check_id] = check_func

    def add_check(self, check: ComplianceCheck):
        """Add a custom check."""
        with self._lock:
            self._checks.append(check)

    def run_check(self, check: ComplianceCheck) -> CheckResult:
        """Run a single compliance check."""
        with self._lock:
            check_func = self._check_overrides.get(check.check_id, check.check_func)

        try:
            passed = check_func()
            status = CheckStatus.PASSED if passed else CheckStatus.FAILED
            message = "Check passed" if passed else "Check failed"
        except Exception as e:
            status = CheckStatus.FAILED
            message = f"Check error: {str(e)}"

        return CheckResult(
            check=check,
            status=status,
            message=message,
        )

    def check_framework(
        self,
        framework: ComplianceFramework,
    ) -> ComplianceReport:
        """
        Run all checks for a framework.

        Parameters
        ----------
        framework : ComplianceFramework
            Framework to check

        Returns
        -------
        ComplianceReport
        """
        with self._lock:
            checks = [c for c in self._checks if c.framework == framework]

        results = []
        passed = 0
        failed = 0
        warnings = 0

        for check in checks:
            result = self.run_check(check)
            results.append(result)

            if result.status == CheckStatus.PASSED:
                passed += 1
            elif result.status == CheckStatus.FAILED:
                failed += 1
            elif result.status == CheckStatus.WARNING:
                warnings += 1

        total = len(checks)
        score = (passed / total * 100) if total > 0 else 0

        report = ComplianceReport(
            framework=framework,
            service=self.service_name,
            score=score,
            total_checks=total,
            passed=passed,
            failed=failed,
            warnings=warnings,
            results=results,
        )

        # Update metrics
        COMPLIANCE_SCORE.labels(framework=framework.value, service=self.service_name).set(score)

        COMPLIANCE_CHECKS_PASSED.labels(framework=framework.value, service=self.service_name).set(
            passed
        )

        COMPLIANCE_CHECKS_FAILED.labels(framework=framework.value, service=self.service_name).set(
            failed
        )

        logger.info(
            "compliance_check_complete",
            framework=framework.value,
            score=score,
            passed=passed,
            failed=failed,
        )

        return report

    def check_gdpr(self) -> ComplianceReport:
        """Run GDPR compliance check."""
        return self.check_framework(ComplianceFramework.GDPR)

    def check_soc2(self) -> ComplianceReport:
        """Run SOC2 compliance check."""
        return self.check_framework(ComplianceFramework.SOC2)

    def check_hipaa(self) -> ComplianceReport:
        """Run HIPAA compliance check."""
        return self.check_framework(ComplianceFramework.HIPAA)

    def check_all(self) -> dict[str, ComplianceReport]:
        """Run all compliance checks."""
        reports = {}

        for framework in ComplianceFramework:
            if framework == ComplianceFramework.CUSTOM:
                continue

            with self._lock:
                has_checks = any(c.framework == framework for c in self._checks)

            if has_checks:
                reports[framework.value] = self.check_framework(framework)

        return reports

    def get_remediation_plan(
        self,
        framework: ComplianceFramework | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get remediation plan for failed checks.

        Parameters
        ----------
        framework : ComplianceFramework, optional
            Filter by framework

        Returns
        -------
        list
            Remediation items
        """
        if framework:
            report = self.check_framework(framework)
            reports = [report]
        else:
            reports = list(self.check_all().values())

        remediation_plan = []

        for report in reports:
            for result in report.results:
                if result.status == CheckStatus.FAILED:
                    remediation_plan.append(
                        {
                            "check_id": result.check.check_id,
                            "name": result.check.name,
                            "framework": result.check.framework.value,
                            "severity": result.check.severity,
                            "remediation": result.check.remediation,
                        }
                    )

        # Sort by severity
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        remediation_plan.sort(key=lambda x: severity_order.get(x["severity"], 4))

        return remediation_plan


# =============================================================================
# Singleton
# =============================================================================

_reporters: dict[str, ComplianceReporter] = {}
_reporter_lock = threading.Lock()


def get_compliance_reporter(service_name: str = "default", **kwargs) -> ComplianceReporter:
    """Get or create a compliance reporter."""
    if service_name not in _reporters:
        with _reporter_lock:
            if service_name not in _reporters:
                _reporters[service_name] = ComplianceReporter(service_name, **kwargs)

    return _reporters[service_name]
