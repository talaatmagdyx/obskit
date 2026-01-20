"""
Deployment Tracking (Canary, Blue-Green, A/B)
=============================================

Track deployment metrics and health.

Features:
- Canary deployment metrics
- Blue-green tracking
- A/B test metrics
- Rollback detection

Example:
    from obskit.deployment import DeploymentTracker

    tracker = DeploymentTracker()

    # Start canary deployment
    tracker.start_canary("v2.0.0", traffic_percent=10)

    # Record metrics
    tracker.record_metric("v2.0.0", "error_rate", 0.02)

    # Check if safe to proceed
    if tracker.is_canary_healthy("v2.0.0"):
        tracker.increase_traffic("v2.0.0", 50)
"""

import threading
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

DEPLOYMENT_STATUS = Gauge(
    "deployment_status",
    "Deployment status (0=inactive, 1=canary, 2=partial, 3=full)",
    ["version", "deployment_type"],
)

DEPLOYMENT_TRAFFIC = Gauge(
    "deployment_traffic_percent", "Traffic percentage to deployment", ["version"]
)

DEPLOYMENT_ERRORS = Counter("deployment_errors_total", "Errors in deployment", ["version"])

DEPLOYMENT_REQUESTS = Counter(
    "deployment_requests_total", "Requests to deployment", ["version", "status"]
)


# =============================================================================
# Enums and Data Classes
# =============================================================================


class DeploymentType(Enum):
    """Deployment types."""

    CANARY = "canary"
    BLUE_GREEN = "blue_green"
    ROLLING = "rolling"
    AB_TEST = "ab_test"


class DeploymentStatus(Enum):
    """Deployment statuses."""

    PENDING = "pending"
    CANARY = "canary"
    PARTIAL = "partial"
    FULL = "full"
    ROLLED_BACK = "rolled_back"
    COMPLETED = "completed"


@dataclass
class DeploymentMetrics:
    """Metrics for a deployment."""

    version: str
    error_rate: float = 0.0
    latency_p50: float = 0.0
    latency_p99: float = 0.0
    requests_total: int = 0
    errors_total: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "error_rate": self.error_rate,
            "latency_p50": self.latency_p50,
            "latency_p99": self.latency_p99,
            "requests_total": self.requests_total,
            "errors_total": self.errors_total,
        }


@dataclass
class Deployment:
    """A deployment record."""

    version: str
    deployment_type: DeploymentType
    status: DeploymentStatus
    traffic_percent: float = 0.0
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None
    baseline_version: str | None = None
    metrics: DeploymentMetrics = field(default_factory=lambda: DeploymentMetrics(""))
    health_checks_passed: int = 0
    health_checks_failed: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "deployment_type": self.deployment_type.value,
            "status": self.status.value,
            "traffic_percent": self.traffic_percent,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "baseline_version": self.baseline_version,
            "metrics": self.metrics.to_dict(),
            "health_checks_passed": self.health_checks_passed,
            "health_checks_failed": self.health_checks_failed,
        }


# =============================================================================
# Deployment Tracker
# =============================================================================


class DeploymentTracker:
    """
    Track deployment health and metrics.

    Parameters
    ----------
    error_rate_threshold : float
        Max error rate for healthy deployment
    latency_increase_threshold : float
        Max latency increase ratio (1.5 = 50% increase)
    min_requests_for_decision : int
        Minimum requests before making decisions
    """

    def __init__(
        self,
        error_rate_threshold: float = 0.05,
        latency_increase_threshold: float = 1.5,
        min_requests_for_decision: int = 100,
    ):
        self.error_rate_threshold = error_rate_threshold
        self.latency_increase_threshold = latency_increase_threshold
        self.min_requests_for_decision = min_requests_for_decision

        self._deployments: dict[str, Deployment] = {}
        self._baseline_metrics: dict[str, DeploymentMetrics] = {}
        self._lock = threading.Lock()

    def start_canary(
        self,
        version: str,
        traffic_percent: float = 5.0,
        baseline_version: str | None = None,
    ):
        """
        Start a canary deployment.

        Parameters
        ----------
        version : str
            New version
        traffic_percent : float
            Initial traffic percentage
        baseline_version : str, optional
            Version to compare against
        """
        deployment = Deployment(
            version=version,
            deployment_type=DeploymentType.CANARY,
            status=DeploymentStatus.CANARY,
            traffic_percent=traffic_percent,
            baseline_version=baseline_version,
            metrics=DeploymentMetrics(version=version),
        )

        with self._lock:
            self._deployments[version] = deployment

        DEPLOYMENT_STATUS.labels(version=version, deployment_type="canary").set(1)
        DEPLOYMENT_TRAFFIC.labels(version=version).set(traffic_percent)

        logger.info(
            "canary_started",
            version=version,
            traffic_percent=traffic_percent,
        )

    def start_blue_green(
        self,
        new_version: str,
        old_version: str,
    ):
        """Start a blue-green deployment."""
        deployment = Deployment(
            version=new_version,
            deployment_type=DeploymentType.BLUE_GREEN,
            status=DeploymentStatus.PENDING,
            traffic_percent=0.0,
            baseline_version=old_version,
            metrics=DeploymentMetrics(version=new_version),
        )

        with self._lock:
            self._deployments[new_version] = deployment

        DEPLOYMENT_STATUS.labels(version=new_version, deployment_type="blue_green").set(0)

        logger.info(
            "blue_green_started",
            new_version=new_version,
            old_version=old_version,
        )

    def record_request(
        self,
        version: str,
        latency_ms: float,
        success: bool = True,
    ):
        """
        Record a request to a deployment.

        Parameters
        ----------
        version : str
            Version that handled request
        latency_ms : float
            Request latency
        success : bool
            Whether request succeeded
        """
        with self._lock:
            if version not in self._deployments:
                return

            deployment = self._deployments[version]
            deployment.metrics.requests_total += 1

            if not success:
                deployment.metrics.errors_total += 1

            # Update error rate
            deployment.metrics.error_rate = (
                deployment.metrics.errors_total / deployment.metrics.requests_total
            )

        DEPLOYMENT_REQUESTS.labels(version=version, status="success" if success else "error").inc()

        if not success:
            DEPLOYMENT_ERRORS.labels(version=version).inc()

    def record_metric(
        self,
        version: str,
        metric_name: str,
        value: float,
    ):
        """Record a custom metric for a deployment."""
        with self._lock:
            if version not in self._deployments:
                return

            deployment = self._deployments[version]

            if metric_name == "error_rate":
                deployment.metrics.error_rate = value
            elif metric_name == "latency_p50":
                deployment.metrics.latency_p50 = value
            elif metric_name == "latency_p99":
                deployment.metrics.latency_p99 = value

    def set_baseline_metrics(
        self,
        version: str,
        error_rate: float = 0.0,
        latency_p50: float = 0.0,
        latency_p99: float = 0.0,
    ):
        """Set baseline metrics for comparison."""
        metrics = DeploymentMetrics(
            version=version,
            error_rate=error_rate,
            latency_p50=latency_p50,
            latency_p99=latency_p99,
        )

        with self._lock:
            self._baseline_metrics[version] = metrics

    def is_canary_healthy(self, version: str) -> bool:
        """
        Check if canary deployment is healthy.

        Parameters
        ----------
        version : str
            Canary version

        Returns
        -------
        bool
        """
        with self._lock:
            if version not in self._deployments:
                return False

            deployment = self._deployments[version]

            # Need minimum requests
            if deployment.metrics.requests_total < self.min_requests_for_decision:
                return True  # Not enough data, assume healthy

            # Check error rate
            if deployment.metrics.error_rate > self.error_rate_threshold:
                deployment.health_checks_failed += 1
                return False

            # Compare to baseline if available
            if deployment.baseline_version:
                baseline = self._baseline_metrics.get(deployment.baseline_version)
                if baseline and baseline.latency_p99 > 0:
                    latency_ratio = deployment.metrics.latency_p99 / baseline.latency_p99
                    if latency_ratio > self.latency_increase_threshold:
                        deployment.health_checks_failed += 1
                        return False

            deployment.health_checks_passed += 1
            return True

    def increase_traffic(self, version: str, new_percent: float):
        """Increase traffic to a deployment."""
        with self._lock:
            if version not in self._deployments:
                return

            deployment = self._deployments[version]
            deployment.traffic_percent = min(100, new_percent)

            if deployment.traffic_percent >= 100:
                deployment.status = DeploymentStatus.FULL
            elif deployment.traffic_percent > 50:
                deployment.status = DeploymentStatus.PARTIAL

        DEPLOYMENT_TRAFFIC.labels(version=version).set(new_percent)

        status_val = {
            DeploymentStatus.CANARY: 1,
            DeploymentStatus.PARTIAL: 2,
            DeploymentStatus.FULL: 3,
        }.get(deployment.status, 0)

        DEPLOYMENT_STATUS.labels(
            version=version, deployment_type=deployment.deployment_type.value
        ).set(status_val)

        logger.info(
            "traffic_increased",
            version=version,
            new_percent=new_percent,
        )

    def rollback(self, version: str, reason: str = ""):
        """Rollback a deployment."""
        with self._lock:
            if version not in self._deployments:
                return

            deployment = self._deployments[version]
            deployment.status = DeploymentStatus.ROLLED_BACK
            deployment.traffic_percent = 0
            deployment.completed_at = datetime.utcnow()

        DEPLOYMENT_STATUS.labels(
            version=version, deployment_type=deployment.deployment_type.value
        ).set(0)
        DEPLOYMENT_TRAFFIC.labels(version=version).set(0)

        logger.warning(
            "deployment_rolled_back",
            version=version,
            reason=reason,
        )

    def complete_deployment(self, version: str):
        """Mark deployment as complete."""
        with self._lock:
            if version not in self._deployments:
                return

            deployment = self._deployments[version]
            deployment.status = DeploymentStatus.COMPLETED
            deployment.traffic_percent = 100
            deployment.completed_at = datetime.utcnow()

        DEPLOYMENT_STATUS.labels(
            version=version, deployment_type=deployment.deployment_type.value
        ).set(3)

        logger.info(
            "deployment_completed",
            version=version,
        )

    def get_deployment(self, version: str) -> Deployment | None:
        """Get deployment details."""
        with self._lock:
            return self._deployments.get(version)

    def get_active_deployments(self) -> list[Deployment]:
        """Get all active deployments."""
        with self._lock:
            return [
                d
                for d in self._deployments.values()
                if d.status not in (DeploymentStatus.COMPLETED, DeploymentStatus.ROLLED_BACK)
            ]


# =============================================================================
# Singleton
# =============================================================================

_tracker: DeploymentTracker | None = None
_tracker_lock = threading.Lock()


def get_deployment_tracker(**kwargs) -> DeploymentTracker:
    """Get or create the global deployment tracker."""
    global _tracker

    if _tracker is None:
        with _tracker_lock:
            if _tracker is None:
                _tracker = DeploymentTracker(**kwargs)

    return _tracker
