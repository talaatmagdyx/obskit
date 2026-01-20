"""Unit tests for Deployment Tracking."""

from obskit.deployment import (
    Deployment,
    DeploymentStatus,
    DeploymentTracker,
    DeploymentType,
    get_deployment_tracker,
)


class TestDeploymentTracker:
    """Tests for DeploymentTracker."""

    def test_start_canary(self):
        """Test starting a canary deployment."""
        tracker = DeploymentTracker()

        tracker.start_canary(
            version="v2.0.0",
            traffic_percent=10.0,
            baseline_version="v1.0.0",
        )

        deployment = tracker.get_deployment("v2.0.0")

        assert deployment is not None
        assert deployment.deployment_type == DeploymentType.CANARY
        assert deployment.traffic_percent == 10.0

    def test_start_blue_green(self):
        """Test starting a blue-green deployment."""
        tracker = DeploymentTracker()

        tracker.start_blue_green(
            new_version="v3.0.0",
            old_version="v2.0.0",
        )

        deployment = tracker.get_deployment("v3.0.0")

        assert deployment is not None
        assert deployment.deployment_type == DeploymentType.BLUE_GREEN
        assert deployment.status == DeploymentStatus.PENDING

    def test_record_request(self):
        """Test recording requests to deployment."""
        tracker = DeploymentTracker()

        tracker.start_canary("v1.1.0", traffic_percent=50)

        # Record successful requests
        for _ in range(8):
            tracker.record_request("v1.1.0", latency_ms=100.0, success=True)

        # Record failed requests
        for _ in range(2):
            tracker.record_request("v1.1.0", latency_ms=200.0, success=False)

        deployment = tracker.get_deployment("v1.1.0")

        assert deployment.metrics.requests_total == 10
        assert deployment.metrics.errors_total == 2
        assert deployment.metrics.error_rate == 0.2

    def test_is_canary_healthy(self):
        """Test canary health check."""
        tracker = DeploymentTracker(
            error_rate_threshold=0.1,
            min_requests_for_decision=10,
        )

        tracker.start_canary("healthy-v1", traffic_percent=10)

        # Record healthy requests
        for _ in range(15):
            tracker.record_request("healthy-v1", latency_ms=50.0, success=True)

        assert tracker.is_canary_healthy("healthy-v1") is True

    def test_is_canary_unhealthy(self):
        """Test unhealthy canary detection."""
        tracker = DeploymentTracker(
            error_rate_threshold=0.1,
            min_requests_for_decision=10,
        )

        tracker.start_canary("unhealthy-v1", traffic_percent=10)

        # Record many failures
        for _ in range(5):
            tracker.record_request("unhealthy-v1", latency_ms=50.0, success=True)
        for _ in range(10):
            tracker.record_request("unhealthy-v1", latency_ms=100.0, success=False)

        assert tracker.is_canary_healthy("unhealthy-v1") is False

    def test_increase_traffic(self):
        """Test increasing traffic to deployment."""
        tracker = DeploymentTracker()

        tracker.start_canary("traffic-test", traffic_percent=10)
        tracker.increase_traffic("traffic-test", 50)

        deployment = tracker.get_deployment("traffic-test")

        assert deployment.traffic_percent == 50
        assert deployment.status == DeploymentStatus.CANARY  # Still canary at 50%

    def test_increase_traffic_full(self):
        """Test increasing traffic to 100%."""
        tracker = DeploymentTracker()

        tracker.start_canary("full-traffic", traffic_percent=10)
        tracker.increase_traffic("full-traffic", 100)

        deployment = tracker.get_deployment("full-traffic")

        assert deployment.traffic_percent == 100
        assert deployment.status == DeploymentStatus.FULL

    def test_rollback(self):
        """Test rolling back deployment."""
        tracker = DeploymentTracker()

        tracker.start_canary("rollback-test", traffic_percent=50)
        tracker.rollback("rollback-test", reason="High error rate")

        deployment = tracker.get_deployment("rollback-test")

        assert deployment.status == DeploymentStatus.ROLLED_BACK
        assert deployment.traffic_percent == 0

    def test_complete_deployment(self):
        """Test completing deployment."""
        tracker = DeploymentTracker()

        tracker.start_canary("complete-test", traffic_percent=10)
        tracker.complete_deployment("complete-test")

        deployment = tracker.get_deployment("complete-test")

        assert deployment.status == DeploymentStatus.COMPLETED
        assert deployment.completed_at is not None

    def test_get_active_deployments(self):
        """Test getting active deployments."""
        tracker = DeploymentTracker()

        tracker.start_canary("active-1", traffic_percent=10)
        tracker.start_canary("active-2", traffic_percent=20)
        tracker.start_canary("completed", traffic_percent=100)
        tracker.complete_deployment("completed")

        active = tracker.get_active_deployments()

        assert len(active) == 2
        assert not any(d.version == "completed" for d in active)

    def test_set_baseline_metrics(self):
        """Test setting baseline metrics for comparison."""
        tracker = DeploymentTracker()

        tracker.set_baseline_metrics(
            version="v1.0.0",
            error_rate=0.01,
            latency_p50=50.0,
            latency_p99=200.0,
        )

        # Start canary with comparison
        tracker.start_canary("v1.1.0", baseline_version="v1.0.0")

        deployment = tracker.get_deployment("v1.1.0")
        assert deployment.baseline_version == "v1.0.0"


class TestDeployment:
    """Tests for Deployment."""

    def test_to_dict(self):
        """Test Deployment serialization."""
        from obskit.deployment import DeploymentMetrics

        deployment = Deployment(
            version="v1.0.0",
            deployment_type=DeploymentType.CANARY,
            status=DeploymentStatus.CANARY,
            traffic_percent=25.0,
            metrics=DeploymentMetrics(version="v1.0.0"),
        )

        data = deployment.to_dict()
        assert data["version"] == "v1.0.0"
        assert data["deployment_type"] == "canary"
        assert data["traffic_percent"] == 25.0


class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_deployment_tracker(self):
        """Test global tracker singleton."""
        tracker1 = get_deployment_tracker()
        tracker2 = get_deployment_tracker()
        assert tracker1 is tracker2
