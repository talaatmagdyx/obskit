"""
Alert Annotations and Grafana Integration.

Programmatic annotations for Grafana dashboards.
"""

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .logging import get_logger

logger = get_logger(__name__)


class AnnotationType(Enum):
    """Types of annotations."""

    DEPLOYMENT = "deployment"
    INCIDENT = "incident"
    FEATURE_FLAG = "feature_flag"
    MAINTENANCE = "maintenance"
    ALERT = "alert"
    CUSTOM = "custom"


class AnnotationSeverity(Enum):
    """Severity levels for annotations."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class Annotation:
    """Represents a Grafana annotation."""

    text: str
    tags: list[str] = field(default_factory=list)
    time: int = 0  # Unix timestamp in milliseconds
    time_end: int | None = None  # For range annotations
    annotation_type: AnnotationType = AnnotationType.CUSTOM
    severity: AnnotationSeverity = AnnotationSeverity.INFO
    dashboard_uid: str | None = None
    panel_id: int | None = None

    def __post_init__(self):
        if self.time == 0:
            self.time = int(time.time() * 1000)

    def to_grafana_format(self) -> dict[str, Any]:
        """Convert to Grafana API format."""
        data = {
            "text": self.text,
            "tags": self.tags + [self.annotation_type.value, self.severity.value],
            "time": self.time,
        }
        if self.time_end:
            data["timeEnd"] = self.time_end
        if self.dashboard_uid:
            data["dashboardUID"] = self.dashboard_uid
        if self.panel_id:
            data["panelId"] = self.panel_id
        return data


class GrafanaAnnotator:
    """
    Creates annotations in Grafana.

    Example:
        annotator = GrafanaAnnotator(
            grafana_url="http://grafana:3000",
            api_key="your-api-key"
        )

        # Mark deployment
        annotator.mark_deployment(version="1.2.3", environment="production")

        # Mark incident
        annotator.mark_incident(title="High error rate", severity="warning")

        # Mark feature toggle
        annotator.mark_feature_toggle(feature="new_widget", enabled=True)
    """

    def __init__(
        self,
        grafana_url: str,
        api_key: str | None = None,
        default_tags: list[str] | None = None,
        default_dashboard_uid: str | None = None,
        dry_run: bool = False,
    ):
        """
        Initialize Grafana annotator.

        Args:
            grafana_url: Grafana base URL
            api_key: Grafana API key
            default_tags: Default tags for all annotations
            default_dashboard_uid: Default dashboard UID
            dry_run: If True, don't actually create annotations
        """
        self.grafana_url = grafana_url.rstrip("/")
        self.api_key = api_key
        self.default_tags = default_tags or []
        self.default_dashboard_uid = default_dashboard_uid
        self.dry_run = dry_run

        # Store annotations locally for dry run or when Grafana unavailable
        self._local_annotations: list[Annotation] = []

    def _create_annotation(self, annotation: Annotation) -> dict[str, Any] | None:
        """Create annotation in Grafana."""
        if self.dry_run:
            self._local_annotations.append(annotation)
            logger.info(
                "annotation_created_dry_run",
                text=annotation.text,
                tags=annotation.tags,
                type=annotation.annotation_type.value,
            )
            return annotation.to_grafana_format()

        try:
            import requests

            headers = {
                "Content-Type": "application/json",
            }
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            data = annotation.to_grafana_format()

            response = requests.post(
                f"{self.grafana_url}/api/annotations", headers=headers, json=data, timeout=10
            )

            if response.status_code in (200, 201):
                result = response.json()
                logger.info(
                    "annotation_created",
                    annotation_id=result.get("id"),
                    text=annotation.text,
                    type=annotation.annotation_type.value,
                )
                return result
            else:
                logger.warning(
                    "annotation_creation_failed",
                    status_code=response.status_code,
                    response=response.text,
                )
                # Store locally as fallback
                self._local_annotations.append(annotation)
                return None

        except Exception as e:
            logger.warning("annotation_creation_error", error=str(e), text=annotation.text)
            self._local_annotations.append(annotation)
            return None

    def annotate(
        self,
        text: str,
        tags: list[str] | None = None,
        annotation_type: AnnotationType = AnnotationType.CUSTOM,
        severity: AnnotationSeverity = AnnotationSeverity.INFO,
        duration_minutes: float | None = None,
        dashboard_uid: str | None = None,
        panel_id: int | None = None,
    ) -> dict[str, Any] | None:
        """
        Create a custom annotation.

        Args:
            text: Annotation text
            tags: Additional tags
            annotation_type: Type of annotation
            severity: Severity level
            duration_minutes: Duration for range annotation
            dashboard_uid: Target dashboard UID
            panel_id: Target panel ID

        Returns:
            Created annotation or None
        """
        all_tags = self.default_tags + (tags or [])

        annotation = Annotation(
            text=text,
            tags=all_tags,
            annotation_type=annotation_type,
            severity=severity,
            dashboard_uid=dashboard_uid or self.default_dashboard_uid,
            panel_id=panel_id,
        )

        if duration_minutes:
            annotation.time_end = annotation.time + int(duration_minutes * 60 * 1000)

        return self._create_annotation(annotation)

    def mark_deployment(
        self,
        version: str,
        environment: str = "production",
        service: str | None = None,
        commit_sha: str | None = None,
        deployed_by: str | None = None,
        **extra,
    ) -> dict[str, Any] | None:
        """
        Mark a deployment.

        Args:
            version: Version being deployed
            environment: Target environment
            service: Service name
            commit_sha: Git commit SHA
            deployed_by: Deployer name
            **extra: Additional metadata
        """
        parts = [f"🚀 Deployment: {version}"]
        if service:
            parts.append(f"Service: {service}")
        parts.append(f"Environment: {environment}")
        if commit_sha:
            parts.append(f"Commit: {commit_sha[:8]}")
        if deployed_by:
            parts.append(f"By: {deployed_by}")
        for k, v in extra.items():
            parts.append(f"{k}: {v}")

        text = " | ".join(parts)
        tags = ["deployment", environment, version]
        if service:
            tags.append(service)

        return self.annotate(
            text=text,
            tags=tags,
            annotation_type=AnnotationType.DEPLOYMENT,
            severity=AnnotationSeverity.INFO,
        )

    def mark_incident(
        self,
        title: str,
        severity: str = "warning",
        description: str | None = None,
        affected_services: list[str] | None = None,
        incident_id: str | None = None,
        **extra,
    ) -> dict[str, Any] | None:
        """
        Mark an incident.

        Args:
            title: Incident title
            severity: Severity level (info, warning, error, critical)
            description: Incident description
            affected_services: List of affected services
            incident_id: Incident ID
            **extra: Additional metadata
        """
        emoji = {"info": "ℹ️", "warning": "⚠️", "error": "❌", "critical": "🔥"}.get(severity, "⚠️")

        parts = [f"{emoji} Incident: {title}"]
        if incident_id:
            parts.append(f"ID: {incident_id}")
        if description:
            parts.append(description)
        if affected_services:
            parts.append(f"Affected: {', '.join(affected_services)}")
        for k, v in extra.items():
            parts.append(f"{k}: {v}")

        text = " | ".join(parts)
        tags = ["incident", severity]
        if affected_services:
            tags.extend(affected_services)

        return self.annotate(
            text=text,
            tags=tags,
            annotation_type=AnnotationType.INCIDENT,
            severity=AnnotationSeverity(severity),
        )

    def mark_incident_resolved(
        self,
        title: str,
        duration_minutes: float | None = None,
        resolution: str | None = None,
        **extra,
    ) -> dict[str, Any] | None:
        """Mark an incident as resolved."""
        parts = [f"✅ Resolved: {title}"]
        if duration_minutes:
            parts.append(f"Duration: {duration_minutes:.1f}m")
        if resolution:
            parts.append(f"Resolution: {resolution}")
        for k, v in extra.items():
            parts.append(f"{k}: {v}")

        text = " | ".join(parts)
        tags = ["incident", "resolved"]

        return self.annotate(
            text=text,
            tags=tags,
            annotation_type=AnnotationType.INCIDENT,
            severity=AnnotationSeverity.INFO,
        )

    def mark_feature_toggle(
        self,
        feature: str,
        enabled: bool,
        percentage: float | None = None,
        affected_users: str | None = None,
        **extra,
    ) -> dict[str, Any] | None:
        """
        Mark a feature flag change.

        Args:
            feature: Feature name
            enabled: Whether feature is enabled
            percentage: Rollout percentage
            affected_users: Description of affected users
            **extra: Additional metadata
        """
        emoji = "🟢" if enabled else "🔴"
        status = "enabled" if enabled else "disabled"

        parts = [f"{emoji} Feature: {feature} {status}"]
        if percentage is not None:
            parts.append(f"Rollout: {percentage}%")
        if affected_users:
            parts.append(f"Users: {affected_users}")
        for k, v in extra.items():
            parts.append(f"{k}: {v}")

        text = " | ".join(parts)
        tags = ["feature_flag", feature, status]

        return self.annotate(
            text=text,
            tags=tags,
            annotation_type=AnnotationType.FEATURE_FLAG,
            severity=AnnotationSeverity.INFO,
        )

    def mark_maintenance(
        self,
        title: str,
        duration_minutes: float,
        affected_services: list[str] | None = None,
        **extra,
    ) -> dict[str, Any] | None:
        """
        Mark a maintenance window.

        Args:
            title: Maintenance title
            duration_minutes: Expected duration
            affected_services: List of affected services
            **extra: Additional metadata
        """
        parts = [f"🔧 Maintenance: {title}"]
        parts.append(f"Duration: {duration_minutes}m")
        if affected_services:
            parts.append(f"Affected: {', '.join(affected_services)}")
        for k, v in extra.items():
            parts.append(f"{k}: {v}")

        text = " | ".join(parts)
        tags = ["maintenance"]
        if affected_services:
            tags.extend(affected_services)

        return self.annotate(
            text=text,
            tags=tags,
            annotation_type=AnnotationType.MAINTENANCE,
            severity=AnnotationSeverity.WARNING,
            duration_minutes=duration_minutes,
        )

    def mark_alert(
        self,
        alert_name: str,
        status: str = "firing",
        severity: str = "warning",
        value: float | None = None,
        threshold: float | None = None,
        **extra,
    ) -> dict[str, Any] | None:
        """
        Mark an alert event.

        Args:
            alert_name: Alert name
            status: Alert status (firing, resolved)
            severity: Severity level
            value: Current value that triggered alert
            threshold: Alert threshold
            **extra: Additional metadata
        """
        emoji = "🔔" if status == "firing" else "✅"

        parts = [f"{emoji} Alert: {alert_name} ({status})"]
        if value is not None:
            parts.append(f"Value: {value}")
        if threshold is not None:
            parts.append(f"Threshold: {threshold}")
        for k, v in extra.items():
            parts.append(f"{k}: {v}")

        text = " | ".join(parts)
        tags = ["alert", alert_name, status, severity]

        return self.annotate(
            text=text,
            tags=tags,
            annotation_type=AnnotationType.ALERT,
            severity=AnnotationSeverity(severity),
        )

    def get_local_annotations(self) -> list[Annotation]:
        """Get locally stored annotations (for dry run or fallback)."""
        return self._local_annotations.copy()

    def clear_local_annotations(self):
        """Clear locally stored annotations."""
        self._local_annotations.clear()


# Global annotator instance
_annotator: GrafanaAnnotator | None = None


def configure_annotator(
    grafana_url: str, api_key: str | None = None, **kwargs
) -> GrafanaAnnotator:
    """Configure the global annotator."""
    global _annotator
    _annotator = GrafanaAnnotator(grafana_url, api_key, **kwargs)
    return _annotator


def get_annotator() -> GrafanaAnnotator | None:
    """Get the global annotator."""
    return _annotator


__all__ = [
    "GrafanaAnnotator",
    "Annotation",
    "AnnotationType",
    "AnnotationSeverity",
    "configure_annotator",
    "get_annotator",
]
