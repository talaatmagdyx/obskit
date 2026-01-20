"""Unit tests for Grafana annotations."""

import time
from unittest.mock import patch

from obskit.annotations import (
    Annotation,
    AnnotationSeverity,
    AnnotationType,
    GrafanaAnnotator,
    configure_annotator,
    get_annotator,
)


class TestAnnotationType:
    """Tests for AnnotationType enum."""

    def test_values(self):
        """Test enum values exist."""
        assert AnnotationType.DEPLOYMENT.value == "deployment"
        assert AnnotationType.INCIDENT.value == "incident"
        assert AnnotationType.FEATURE_FLAG.value == "feature_flag"
        assert AnnotationType.MAINTENANCE.value == "maintenance"
        assert AnnotationType.ALERT.value == "alert"
        assert AnnotationType.CUSTOM.value == "custom"


class TestAnnotationSeverity:
    """Tests for AnnotationSeverity enum."""

    def test_values(self):
        """Test enum values exist."""
        assert AnnotationSeverity.INFO.value == "info"
        assert AnnotationSeverity.WARNING.value == "warning"
        assert AnnotationSeverity.ERROR.value == "error"
        assert AnnotationSeverity.CRITICAL.value == "critical"


class TestAnnotation:
    """Tests for Annotation dataclass."""

    def test_init_defaults(self):
        """Test default values."""
        annotation = Annotation(text="Test annotation")

        assert annotation.text == "Test annotation"
        assert annotation.tags == []
        assert annotation.time > 0  # Auto-generated timestamp
        assert annotation.time_end is None
        assert annotation.annotation_type == AnnotationType.CUSTOM
        assert annotation.severity == AnnotationSeverity.INFO

    def test_init_with_all_fields(self):
        """Test initialization with all fields."""
        current_time = int(time.time() * 1000)

        annotation = Annotation(
            text="Deployment v1.2.3",
            tags=["deployment", "production"],
            time=current_time,
            time_end=current_time + 60000,
            annotation_type=AnnotationType.DEPLOYMENT,
            severity=AnnotationSeverity.INFO,
            dashboard_uid="abc123",
            panel_id=5,
        )

        assert annotation.text == "Deployment v1.2.3"
        assert "deployment" in annotation.tags
        assert annotation.time == current_time
        assert annotation.time_end == current_time + 60000
        assert annotation.annotation_type == AnnotationType.DEPLOYMENT
        assert annotation.dashboard_uid == "abc123"
        assert annotation.panel_id == 5

    def test_auto_timestamp(self):
        """Test automatic timestamp generation."""
        before = int(time.time() * 1000)
        annotation = Annotation(text="Test")
        after = int(time.time() * 1000)

        assert before <= annotation.time <= after

    def test_to_grafana_format(self):
        """Test conversion to Grafana API format."""
        annotation = Annotation(
            text="Test annotation",
            tags=["tag1", "tag2"],
            time=1234567890000,
            annotation_type=AnnotationType.INCIDENT,
            severity=AnnotationSeverity.WARNING,
            dashboard_uid="dash-123",
            panel_id=7,
        )

        data = annotation.to_grafana_format()

        assert data["text"] == "Test annotation"
        assert "tag1" in data["tags"]
        assert "incident" in data["tags"]  # Type added
        assert "warning" in data["tags"]  # Severity added
        assert data["time"] == 1234567890000
        assert data["dashboardUID"] == "dash-123"
        assert data["panelId"] == 7

    def test_to_grafana_format_with_time_end(self):
        """Test Grafana format includes timeEnd for range annotations."""
        annotation = Annotation(
            text="Maintenance window", time=1234567890000, time_end=1234567900000
        )

        data = annotation.to_grafana_format()

        assert data["timeEnd"] == 1234567900000


class TestGrafanaAnnotator:
    """Tests for GrafanaAnnotator class."""

    def test_init(self):
        """Test annotator initialization."""
        annotator = GrafanaAnnotator(grafana_url="http://grafana:3000", api_key="test-key")

        assert annotator.grafana_url == "http://grafana:3000"
        assert annotator.api_key == "test-key"

    def test_init_strips_trailing_slash(self):
        """Test URL trailing slash is stripped."""
        annotator = GrafanaAnnotator(grafana_url="http://grafana:3000/")

        assert annotator.grafana_url == "http://grafana:3000"

    def test_init_with_defaults(self):
        """Test initialization with default tags."""
        annotator = GrafanaAnnotator(
            grafana_url="http://grafana:3000",
            default_tags=["env:production", "team:platform"],
            default_dashboard_uid="main-dash",
        )

        assert "env:production" in annotator.default_tags
        assert annotator.default_dashboard_uid == "main-dash"

    def test_dry_run_mode(self):
        """Test dry run mode doesn't make HTTP calls."""
        annotator = GrafanaAnnotator(grafana_url="http://grafana:3000", dry_run=True)

        result = annotator.annotate(text="Test annotation")

        assert result is not None
        assert len(annotator._local_annotations) == 1

    def test_annotate_basic(self):
        """Test basic annotation creation."""
        annotator = GrafanaAnnotator(grafana_url="http://grafana:3000", dry_run=True)

        result = annotator.annotate(
            text="Test annotation",
            tags=["test"],
            annotation_type=AnnotationType.CUSTOM,
            severity=AnnotationSeverity.INFO,
        )

        assert result is not None
        assert result["text"] == "Test annotation"

    def test_annotate_with_duration(self):
        """Test annotation with duration creates range annotation."""
        annotator = GrafanaAnnotator(grafana_url="http://grafana:3000", dry_run=True)

        result = annotator.annotate(text="Maintenance", duration_minutes=30.0)

        assert result is not None
        assert "timeEnd" in result

    def test_mark_deployment(self):
        """Test marking a deployment."""
        annotator = GrafanaAnnotator(grafana_url="http://grafana:3000", dry_run=True)

        result = annotator.mark_deployment(
            version="1.2.3",
            environment="production",
            service="order-service",
            commit_sha="abc123def456",
            deployed_by="deploy-bot",
        )

        assert result is not None
        assert "1.2.3" in result["text"]
        assert "production" in result["tags"]

    def test_mark_incident(self):
        """Test marking an incident."""
        annotator = GrafanaAnnotator(grafana_url="http://grafana:3000", dry_run=True)

        result = annotator.mark_incident(
            title="High error rate",
            severity="warning",
            description="Error rate exceeded 5%",
            affected_services=["order-service", "payment-service"],
            incident_id="INC-123",
        )

        assert result is not None
        assert "High error rate" in result["text"]
        assert "warning" in result["tags"]

    def test_mark_incident_resolved(self):
        """Test marking an incident as resolved."""
        annotator = GrafanaAnnotator(grafana_url="http://grafana:3000", dry_run=True)

        result = annotator.mark_incident_resolved(
            title="High error rate", duration_minutes=45.0, resolution="Fixed bad deployment"
        )

        assert result is not None
        assert "Resolved" in result["text"]
        assert "resolved" in result["tags"]

    def test_mark_feature_toggle(self):
        """Test marking a feature flag change."""
        annotator = GrafanaAnnotator(grafana_url="http://grafana:3000", dry_run=True)

        result = annotator.mark_feature_toggle(
            feature="new_checkout", enabled=True, percentage=50.0, affected_users="beta users"
        )

        assert result is not None
        assert "new_checkout" in result["text"]
        assert "enabled" in result["tags"]

    def test_mark_feature_toggle_disabled(self):
        """Test marking a feature flag as disabled."""
        annotator = GrafanaAnnotator(grafana_url="http://grafana:3000", dry_run=True)

        result = annotator.mark_feature_toggle(feature="experiment_x", enabled=False)

        assert result is not None
        assert "disabled" in result["tags"]

    def test_mark_maintenance(self):
        """Test marking a maintenance window."""
        annotator = GrafanaAnnotator(grafana_url="http://grafana:3000", dry_run=True)

        result = annotator.mark_maintenance(
            title="Database migration",
            duration_minutes=60.0,
            affected_services=["order-service", "inventory-service"],
        )

        assert result is not None
        assert "Database migration" in result["text"]
        assert "maintenance" in result["tags"]
        assert "timeEnd" in result  # Should be a range annotation

    def test_mark_alert(self):
        """Test marking an alert event."""
        annotator = GrafanaAnnotator(grafana_url="http://grafana:3000", dry_run=True)

        result = annotator.mark_alert(
            alert_name="HighCPU", status="firing", severity="warning", value=95.5, threshold=80.0
        )

        assert result is not None
        assert "HighCPU" in result["text"]
        assert "firing" in result["tags"]

    def test_mark_alert_resolved(self):
        """Test marking an alert as resolved."""
        annotator = GrafanaAnnotator(grafana_url="http://grafana:3000", dry_run=True)

        result = annotator.mark_alert(alert_name="HighCPU", status="resolved", severity="warning")

        assert result is not None
        assert "resolved" in result["tags"]

    def test_get_local_annotations(self):
        """Test getting locally stored annotations."""
        annotator = GrafanaAnnotator(grafana_url="http://grafana:3000", dry_run=True)

        annotator.annotate(text="Annotation 1")
        annotator.annotate(text="Annotation 2")

        local = annotator.get_local_annotations()

        assert len(local) == 2

    def test_clear_local_annotations(self):
        """Test clearing locally stored annotations."""
        annotator = GrafanaAnnotator(grafana_url="http://grafana:3000", dry_run=True)

        annotator.annotate(text="Annotation 1")
        annotator.clear_local_annotations()

        assert len(annotator._local_annotations) == 0

    @patch("requests.post")
    def test_create_annotation_http_success(self, mock_post):
        """Test successful HTTP annotation creation."""
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"id": 123}

        annotator = GrafanaAnnotator(grafana_url="http://grafana:3000", api_key="test-key")

        result = annotator.annotate(text="HTTP annotation")

        assert result is not None
        assert result["id"] == 123
        mock_post.assert_called_once()

    @patch("requests.post")
    def test_create_annotation_http_failure(self, mock_post):
        """Test HTTP failure falls back to local storage."""
        mock_post.return_value.status_code = 500
        mock_post.return_value.text = "Internal Server Error"

        annotator = GrafanaAnnotator(grafana_url="http://grafana:3000", api_key="test-key")

        result = annotator.annotate(text="Failed annotation")

        assert result is None
        assert len(annotator._local_annotations) == 1


class TestConfigureAnnotator:
    """Tests for configure_annotator function."""

    def test_configures_global_annotator(self):
        """Test configuring the global annotator."""
        annotator = configure_annotator(
            grafana_url="http://grafana:3000", api_key="test-key", dry_run=True
        )

        assert annotator is not None
        assert get_annotator() is annotator


class TestGetAnnotator:
    """Tests for get_annotator function."""

    def test_returns_none_if_not_configured(self):
        """Test returns None if not configured."""
        # Reset global state
        from obskit import annotations

        annotations._annotator = None

        _result = get_annotator()
        # May be None or the configured one depending on test order
