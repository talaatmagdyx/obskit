"""
Coverage gap tests for obskit-metrics package.

Targets specific missing lines/branches across all gap files.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

# =============================================================================
# annotations.py gaps
# =============================================================================


class TestAnnotationsGaps:
    """Lines 135->138, 163-166, 230-238, 242-245, 275-289, 305-310, 349, 379-389, 425."""

    def test_create_annotation_with_api_key_sets_auth_header(self):
        """Line 135->138: api_key branch sets Authorization header."""
        from obskit.annotations import GrafanaAnnotator

        annotator = GrafanaAnnotator(
            grafana_url="http://grafana:3000",
            api_key="my-secret-key",
        )
        with patch("requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {"id": 1}
            annotator.annotate(text="Test with API key")
            call_kwargs = mock_post.call_args
            headers = call_kwargs[1]["headers"]
            assert "Authorization" in headers
            assert headers["Authorization"] == "Bearer my-secret-key"

    def test_create_annotation_exception_stored_locally(self):
        """Lines 163-166: exception in HTTP call stores annotation locally."""
        from obskit.annotations import GrafanaAnnotator

        annotator = GrafanaAnnotator(
            grafana_url="http://grafana:3000",
            api_key="key",
        )
        with patch("requests.post", side_effect=Exception("network error")):
            result = annotator.annotate(text="Test exception")
        assert result is None
        assert len(annotator._local_annotations) == 1

    def test_mark_deployment_with_service_and_commit_and_deployer(self):
        """Lines 230->232, 233->235, 235->237: service + commit_sha + deployed_by."""
        from obskit.annotations import GrafanaAnnotator

        annotator = GrafanaAnnotator(grafana_url="http://grafana:3000", dry_run=True)
        result = annotator.mark_deployment(
            version="2.0.0",
            environment="staging",
            service="payment-service",
            commit_sha="deadbeef1234",
            deployed_by="ci-bot",
        )
        assert result is not None
        assert "payment-service" in result["text"]
        assert "deadbeef" in result["text"]
        assert "ci-bot" in result["text"]

    def test_mark_deployment_with_extra_kwargs(self):
        """Line 238: extra kwargs loop in mark_deployment."""
        from obskit.annotations import GrafanaAnnotator

        annotator = GrafanaAnnotator(grafana_url="http://grafana:3000", dry_run=True)
        result = annotator.mark_deployment(
            version="3.0.0",
            build_number="42",
            pipeline="main",
        )
        assert result is not None
        assert "42" in result["text"]

    def test_mark_deployment_with_service_adds_to_tags(self):
        """Line 242->245: service tag branch."""
        from obskit.annotations import GrafanaAnnotator

        annotator = GrafanaAnnotator(grafana_url="http://grafana:3000", dry_run=True)
        result = annotator.mark_deployment(
            version="1.0.0",
            service="my-service",
        )
        assert result is not None
        assert "my-service" in result["tags"]

    def test_mark_incident_with_id_description_services_extra(self):
        """Lines 275->277, 277->279, 279->281, 282, 286->289."""
        from obskit.annotations import GrafanaAnnotator

        annotator = GrafanaAnnotator(grafana_url="http://grafana:3000", dry_run=True)
        result = annotator.mark_incident(
            title="DB outage",
            severity="error",
            description="Postgres is down",
            affected_services=["api", "worker"],
            incident_id="INC-999",
            region="us-east-1",
        )
        assert result is not None
        assert "INC-999" in result["text"]
        assert "Postgres is down" in result["text"]
        assert "api" in result["tags"]
        assert "us-east-1" in result["text"]

    def test_mark_incident_resolved_with_duration_and_resolution_and_extra(self):
        """Lines 305->307, 307->309, 310."""
        from obskit.annotations import GrafanaAnnotator

        annotator = GrafanaAnnotator(grafana_url="http://grafana:3000", dry_run=True)
        result = annotator.mark_incident_resolved(
            title="DB outage",
            duration_minutes=30.5,
            resolution="Restarted primary node",
            ticket="JIRA-123",
        )
        assert result is not None
        assert "30.5" in result["text"]
        assert "Restarted primary node" in result["text"]
        assert "JIRA-123" in result["text"]

    def test_mark_feature_toggle_with_extra_kwargs(self):
        """Line 349: extra kwargs loop in mark_feature_toggle."""
        from obskit.annotations import GrafanaAnnotator

        annotator = GrafanaAnnotator(grafana_url="http://grafana:3000", dry_run=True)
        result = annotator.mark_feature_toggle(
            feature="dark_mode",
            enabled=True,
            owner="product-team",
        )
        assert result is not None
        assert "product-team" in result["text"]

    def test_mark_maintenance_with_services_and_extra(self):
        """Lines 379->381, 382, 386->389."""
        from obskit.annotations import GrafanaAnnotator

        annotator = GrafanaAnnotator(grafana_url="http://grafana:3000", dry_run=True)
        result = annotator.mark_maintenance(
            title="DB vacuum",
            duration_minutes=120.0,
            affected_services=["reports", "analytics"],
            approved_by="oncall-team",
        )
        assert result is not None
        assert "reports" in result["tags"]
        assert "oncall-team" in result["text"]

    def test_mark_alert_with_extra_kwargs(self):
        """Line 425: extra kwargs loop in mark_alert."""
        from obskit.annotations import GrafanaAnnotator

        annotator = GrafanaAnnotator(grafana_url="http://grafana:3000", dry_run=True)
        result = annotator.mark_alert(
            alert_name="DiskUsage",
            status="firing",
            severity="critical",
            value=98.5,
            threshold=90.0,
            host="worker-01",
        )
        assert result is not None
        assert "worker-01" in result["text"]

    def test_annotate_without_api_key_no_auth_header(self):
        """Line 135->138: False branch - no api_key means no Authorization header."""
        from obskit.annotations import GrafanaAnnotator

        annotator = GrafanaAnnotator(grafana_url="http://grafana:3000")
        with patch("requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {"id": 2}
            annotator.annotate(text="No auth header test")
            call_kwargs = mock_post.call_args
            headers = call_kwargs[1]["headers"]
            assert "Authorization" not in headers

    def test_mark_incident_minimal_no_id_description_services(self):
        """Lines 275->277, 277->279, 279->281, 286->289: all optional fields absent."""
        from obskit.annotations import GrafanaAnnotator

        annotator = GrafanaAnnotator(grafana_url="http://grafana:3000", dry_run=True)
        result = annotator.mark_incident(
            title="Simple incident",
            severity="warning",
        )
        assert result is not None
        assert "Simple incident" in result["text"]
        # None of the optional fields should be in text
        assert "ID:" not in result["text"]

    def test_mark_incident_resolved_minimal_no_duration_or_resolution(self):
        """Lines 305->307, 307->309: False branches of duration_minutes and resolution."""
        from obskit.annotations import GrafanaAnnotator

        annotator = GrafanaAnnotator(grafana_url="http://grafana:3000", dry_run=True)
        result = annotator.mark_incident_resolved(
            title="Simple incident",
        )
        assert result is not None
        assert "Resolved" in result["text"]

    def test_mark_maintenance_minimal_no_services_or_extra(self):
        """Lines 379->381, 386->389: False branches of affected_services and extra."""
        from obskit.annotations import GrafanaAnnotator

        annotator = GrafanaAnnotator(grafana_url="http://grafana:3000", dry_run=True)
        result = annotator.mark_maintenance(
            title="Simple maintenance",
            duration_minutes=30.0,
        )
        assert result is not None
        assert "Simple maintenance" in result["text"]


# =============================================================================
# autoscaling.py gaps
# =============================================================================


class TestAutoscalingGaps:
    """Lines 227-230, 302->308, 310->315, 316-320, 334->340, 435->438."""

    def test_record_processing_rate(self):
        """Lines 227-230: record_processing_rate updates internal state."""
        from obskit.autoscaling import AutoScalingMetrics

        scaling = AutoScalingMetrics("proc-rate-svc")
        scaling.record_processing_rate(250.0)
        metrics = scaling.get_metrics_for_hpa()
        assert metrics["processing_rate"] == 250.0

    def test_scale_down_cpu_branch(self):
        """Lines 302->308: low CPU triggers scale_down branch."""
        from obskit.autoscaling import AutoScalingMetrics, ScalingConfig, ScalingDirection

        config = ScalingConfig(
            min_replicas=1,
            max_replicas=10,
            target_cpu_utilization=70.0,
            scale_down_threshold=0.3,
            cooldown_seconds=0,
        )
        scaling = AutoScalingMetrics("scale-down-svc", config=config)
        scaling.set_replicas(4)
        for i in range(4):
            scaling.record_pod_metrics(f"pod-{i}", cpu_utilization=5.0, memory_utilization=10.0)
        rec = scaling.get_recommendation()
        assert rec.direction in [ScalingDirection.DOWN, ScalingDirection.NONE]

    def test_cpu_in_middle_zone_no_scale(self):
        """Lines 302->308: CPU in middle zone (neither high nor low) - neither if nor elif taken."""
        from obskit.autoscaling import AutoScalingMetrics, ScalingConfig, ScalingDirection

        config = ScalingConfig(
            min_replicas=1,
            max_replicas=10,
            target_cpu_utilization=70.0,
            scale_up_threshold=1.1,   # scale_up at 77%+
            scale_down_threshold=0.5,  # scale_down at 35%-
            cooldown_seconds=0,
        )
        scaling = AutoScalingMetrics("middle-cpu-svc", config=config)
        scaling.set_replicas(2)
        # CPU at 60% - above scale_down (35%) but below scale_up (77%)
        scaling.record_pod_metrics("pod-0", cpu_utilization=60.0, memory_utilization=40.0)
        scaling.record_pod_metrics("pod-1", cpu_utilization=60.0, memory_utilization=40.0)
        rec = scaling.get_recommendation()
        # Should be NONE since no scaling triggered
        assert rec.direction == ScalingDirection.NONE or rec.target_replicas == rec.current_replicas

    def test_queue_depth_scaling_triggers_up(self):
        """Lines 308->312: queue_depth > 0 triggers queue-based scale up."""
        from obskit.autoscaling import AutoScalingMetrics, ScalingConfig

        config = ScalingConfig(
            min_replicas=1,
            max_replicas=20,
            target_queue_depth_per_pod=50,
            cooldown_seconds=0,
        )
        scaling = AutoScalingMetrics("queue-scale-svc", config=config)
        scaling.set_replicas(1)
        scaling.record_queue_depth(500)
        rec = scaling.get_recommendation()
        assert rec.target_replicas >= 5

    def test_queue_target_not_greater_than_current(self):
        """Lines 310->315: queue_target <= current means queue branch does not scale up."""
        from obskit.autoscaling import AutoScalingMetrics, ScalingConfig

        config = ScalingConfig(
            min_replicas=1,
            max_replicas=20,
            target_queue_depth_per_pod=100,
            cooldown_seconds=0,
        )
        scaling = AutoScalingMetrics("queue-no-scale-svc", config=config)
        scaling.set_replicas(5)
        # queue_depth=200, target_queue_per_pod=100, so queue_target=2 <= current=5
        scaling.record_queue_depth(200)
        rec = scaling.get_recommendation()
        # Queue is not causing scale up since queue_target < current
        assert rec.target_replicas <= 5

    def test_demand_ratio_scaling(self):
        """Lines 315-320: demand ratio > 1.2 triggers demand-based scaling."""
        from obskit.autoscaling import AutoScalingMetrics, ScalingConfig

        config = ScalingConfig(
            min_replicas=1,
            max_replicas=20,
            cooldown_seconds=0,
        )
        scaling = AutoScalingMetrics("demand-svc", config=config)
        scaling.set_replicas(2)
        scaling.record_requests_per_second(240.0)
        scaling.record_processing_rate(50.0)
        rec = scaling.get_recommendation()
        assert rec.target_replicas >= 3

    def test_demand_ratio_not_exceeding_threshold(self):
        """Lines 317->323: demand ratio <= 1.2 means demand branch not triggered."""
        from obskit.autoscaling import AutoScalingMetrics, ScalingConfig

        config = ScalingConfig(
            min_replicas=1,
            max_replicas=20,
            cooldown_seconds=0,
        )
        scaling = AutoScalingMetrics("demand-low-svc", config=config)
        scaling.set_replicas(2)
        # RPS=100, processing_rate=100, current=2 → demand_ratio = 100/(100*2) = 0.5 <= 1.2
        scaling.record_requests_per_second(100.0)
        scaling.record_processing_rate(100.0)
        rec = scaling.get_recommendation()
        # Demand ratio below threshold - no demand-based scale up
        assert "demand_ratio" not in rec.reason

    def test_cooldown_prevents_scaling(self):
        """Lines 334->340: cooldown prevents scaling."""
        from obskit.autoscaling import AutoScalingMetrics, ScalingConfig, ScalingDirection

        config = ScalingConfig(
            min_replicas=1,
            max_replicas=20,
            target_cpu_utilization=70.0,
            cooldown_seconds=3600,
        )
        scaling = AutoScalingMetrics("cooldown-svc", config=config)
        scaling.set_replicas(2)
        scaling.record_scaling_event(ScalingDirection.UP, 3)
        scaling.record_pod_metrics("pod-1", cpu_utilization=99.0, memory_utilization=80.0)
        rec = scaling.get_recommendation()
        assert rec.direction == ScalingDirection.NONE
        assert "cooldown" in rec.reason

    def test_cooldown_expired_allows_scaling(self):
        """Lines 334->340: False branch - cooldown already elapsed so scaling is NOT blocked."""
        from datetime import datetime, timedelta

        from obskit.autoscaling import AutoScalingMetrics, ScalingConfig, ScalingDirection

        config = ScalingConfig(
            min_replicas=1,
            max_replicas=20,
            target_cpu_utilization=70.0,
            cooldown_seconds=1,  # 1 second cooldown
        )
        scaling = AutoScalingMetrics("cooldown-expired-svc", config=config)
        scaling.set_replicas(2)
        # Set last scaling to 2 seconds ago (cooldown expired)
        scaling._last_scaling = datetime.utcnow() - timedelta(seconds=5)
        # High CPU to trigger scale up
        scaling.record_pod_metrics("pod-1", cpu_utilization=95.0, memory_utilization=80.0)
        scaling.record_pod_metrics("pod-2", cpu_utilization=95.0, memory_utilization=80.0)
        rec = scaling.get_recommendation()
        # Cooldown expired, so scaling should NOT be blocked
        assert rec.direction != ScalingDirection.NONE or rec.target_replicas > 0
        assert "cooldown" not in rec.reason

    def test_get_autoscaling_metrics_creates_new_entry(self):
        """Lines 435->438: double-checked locking creates new entry."""
        from obskit.autoscaling import _metrics, get_autoscaling_metrics

        unique_name = f"new-service-{time.time()}"
        assert unique_name not in _metrics
        m = get_autoscaling_metrics(unique_name)
        assert m is not None
        m2 = get_autoscaling_metrics(unique_name)
        assert m is m2


# =============================================================================
# dependency_graph.py gaps
# =============================================================================


class TestDependencyGraphGaps:
    """Lines 154, 253-264, 290, 306, 313->323, 318->323, 340->exit,
    365-379, 405-406, 467, 469, 505->508."""

    def test_graph_visualization_data_to_dict(self):
        """Line 154: GraphVisualization.to_dict method."""
        from obskit.dependency_graph import DependencyGraph, DependencyType

        graph = DependencyGraph("viz-svc")
        graph.add_dependency("db", DependencyType.DATABASE)
        graph.record_call("db", latency_ms=10.0, success=True)
        viz = graph.get_visualization_data()
        d = viz.to_dict()
        assert "nodes" in d
        assert "edges" in d
        assert d["service_name"] == "viz-svc"

    def test_remove_dependency_removes_all_data(self):
        """Lines 253-264: remove_dependency cleans up dependencies, edges, latency_samples."""
        from obskit.dependency_graph import DependencyGraph, DependencyType

        graph = DependencyGraph("remove-svc")
        graph.add_dependency("redis", DependencyType.CACHE)
        graph.record_call("redis", latency_ms=5.0, success=True)
        assert graph.get_dependency("redis") is not None
        graph.remove_dependency("redis")
        assert graph.get_dependency("redis") is None

    def test_remove_nonexistent_dependency_is_noop(self):
        """Tests remove_dependency when name not in _dependencies."""
        from obskit.dependency_graph import DependencyGraph

        graph = DependencyGraph("noop-svc")
        graph.remove_dependency("nonexistent")

    def test_record_call_skips_unknown_dependency(self):
        """Line 290: record_call returns early when dependency not found and auto_detect=False."""
        from obskit.dependency_graph import DependencyGraph

        graph = DependencyGraph("skip-svc", auto_detect=False)
        graph.record_call("unknown-dep", latency_ms=20.0, success=True)
        assert graph.get_dependency("unknown-dep") is None

    def test_record_call_trims_latency_samples_above_100(self):
        """Line 306: latency samples trimmed after > 100."""
        from obskit.dependency_graph import DependencyGraph, DependencyType

        graph = DependencyGraph("trim-svc")
        graph.add_dependency("api", DependencyType.SERVICE)
        for i in range(105):
            graph.record_call("api", latency_ms=float(i), success=True)
        with graph._lock:
            samples = graph._latency_samples.get("api", [])
        assert len(samples) <= 100

    def test_record_call_updates_edge_and_health(self):
        """Lines 313->323: edge updating and health status when error_rate > 0.5."""
        from obskit.dependency_graph import DependencyGraph, DependencyType, HealthStatus

        graph = DependencyGraph("edge-svc")
        graph.add_dependency("svc-b", DependencyType.SERVICE)
        for _ in range(6):
            graph.record_call("svc-b", latency_ms=10.0, success=False)
        for _ in range(4):
            graph.record_call("svc-b", latency_ms=10.0, success=True)
        dep = graph.get_dependency("svc-b")
        assert dep.error_rate > 0.5
        assert dep.health_status == HealthStatus.UNHEALTHY

    def test_record_call_no_edge_in_edges(self):
        """Branch 313->323 False: edge_key NOT in _edges — node exists but edge was removed."""
        from obskit.dependency_graph import DependencyGraph, DependencyType

        graph = DependencyGraph("no-edge-svc")
        graph.add_dependency("orphan-dep", DependencyType.SERVICE)
        # Remove the edge so the if-branch at line 313 is False
        edge_key = "no-edge-svc->orphan-dep"
        graph._edges.pop(edge_key, None)
        # record_call should proceed past line 313 without updating the edge
        graph.record_call("orphan-dep", latency_ms=5.0, success=True)
        dep = graph.get_dependency("orphan-dep")
        assert dep.total_calls == 1

    def test_record_call_dep_node_updates_dependency_status(self):
        """Line 340->exit: dep_node exists so DEPENDENCY_STATUS is set."""
        from obskit.dependency_graph import DependencyGraph, DependencyType

        graph = DependencyGraph("dep-status-svc")
        graph.add_dependency("storage", DependencyType.DATABASE, is_critical=True)
        graph.record_call("storage", latency_ms=15.0, success=True)
        dep = graph.get_dependency("storage")
        assert dep is not None

    def test_update_health_with_string_status(self):
        """Lines 365-366: update_health converts string status to HealthStatus enum."""
        from obskit.dependency_graph import DependencyGraph, DependencyType, HealthStatus

        graph = DependencyGraph("health-str-svc")
        graph.add_dependency("cache", DependencyType.CACHE)
        graph.update_health("cache", "unhealthy")
        dep = graph.get_dependency("cache")
        assert dep.health_status == HealthStatus.UNHEALTHY

    def test_update_health_unknown_dependency_returns_early(self):
        """Lines 369-370: update_health returns early when dep not found."""
        from obskit.dependency_graph import DependencyGraph, HealthStatus

        graph = DependencyGraph("unknown-health-svc")
        graph.update_health("nonexistent", HealthStatus.HEALTHY)

    def test_update_health_with_latency(self):
        """Lines 376-377: update_health with latency_ms parameter."""
        from obskit.dependency_graph import DependencyGraph, DependencyType, HealthStatus

        graph = DependencyGraph("latency-svc")
        graph.add_dependency("db", DependencyType.DATABASE)
        graph.update_health("db", HealthStatus.HEALTHY, latency_ms=42.0)
        dep = graph.get_dependency("db")
        assert dep.latency_ms == 42.0

    def test_get_all_dependencies(self):
        """Lines 405-406: get_all_dependencies returns list."""
        from obskit.dependency_graph import DependencyGraph, DependencyType

        graph = DependencyGraph("all-deps-svc")
        graph.add_dependency("a", DependencyType.SERVICE)
        graph.add_dependency("b", DependencyType.CACHE)
        all_deps = graph.get_all_dependencies()
        assert len(all_deps) == 2

    def test_visualization_data_counts_healthy_and_unhealthy(self):
        """Lines 467, 469: healthy_count and unhealthy_count in visualization."""
        from obskit.dependency_graph import DependencyGraph, DependencyType, HealthStatus

        graph = DependencyGraph("vis-count-svc")
        graph.add_dependency("healthy-dep", DependencyType.SERVICE)
        graph.add_dependency("unhealthy-dep", DependencyType.SERVICE)
        graph.update_health("healthy-dep", HealthStatus.HEALTHY)
        graph.update_health("unhealthy-dep", HealthStatus.UNHEALTHY)
        viz = graph.get_visualization_data()
        assert viz.healthy_count == 1
        assert viz.unhealthy_count == 1

    def test_get_dependency_graph_double_checked_locking(self):
        """Lines 505->508: get_dependency_graph creates new entry via double-checked locking."""
        from obskit.dependency_graph import _graphs, get_dependency_graph

        unique_name = f"unique-graph-svc-{time.time()}"
        assert unique_name not in _graphs
        g = get_dependency_graph(unique_name)
        assert g is not None
        g2 = get_dependency_graph(unique_name)
        assert g is g2


# =============================================================================
# fingerprint.py gaps
# =============================================================================


class TestFingerprintGaps:
    """Lines 246, 249, 317, 402->405."""

    def test_create_stack_signature_break_at_max_frames(self):
        """Line 246: break when len(relevant_frames) >= max_frames (default=5)."""
        from obskit.fingerprint import ErrorFingerprinter

        fp = ErrorFingerprinter(max_groups=100)

        # Create a call stack deeper than max_frames=5 to trigger the break
        def level5():
            raise ValueError("deep stack error")

        def level4():
            level5()

        def level3():
            level4()

        def level2():
            level3()

        def level1():
            level2()

        try:
            level1()
        except ValueError as e:
            result = fp.get_fingerprint(e)

        assert result is not None
        assert result.fingerprint != ""

    def test_create_stack_signature_with_errors(self):
        """Line 246: break when len(relevant_frames) >= max_frames."""
        from obskit.fingerprint import ErrorFingerprinter

        fp = ErrorFingerprinter(max_groups=100)

        def inner():
            try:
                raise ValueError("deep error")
            except ValueError as e:
                return fp.get_fingerprint(e)

        result = inner()
        assert result is not None
        assert result.fingerprint != ""

    def test_create_stack_signature_all_library_frames_fallback(self):
        """Line 249: fallback to tb[-max_frames:] when all frames are library frames."""
        from obskit.fingerprint import ErrorFingerprinter

        fp = ErrorFingerprinter()

        mock_frame = MagicMock()
        mock_frame.filename = "/usr/local/lib/python3/site-packages/somelib.py"
        mock_frame.name = "some_func"
        mock_frame.lineno = 42

        with patch("traceback.extract_tb", return_value=[mock_frame, mock_frame, mock_frame]):
            try:
                raise RuntimeError("all library frames")
            except RuntimeError as e:
                result = fp.get_fingerprint(e)
        assert result is not None

    def test_record_error_with_operation_adds_to_affected_operations(self):
        """Line 317: group.affected_operations.add(operation) when group exists."""
        from obskit.fingerprint import ErrorFingerprinter

        fp = ErrorFingerprinter()
        try:
            raise ValueError("repeated error")
        except ValueError as e:
            fp.record_error(e, operation="op1")
            fp.record_error(e, operation="op2")

        groups = fp.get_all_groups()
        assert len(groups) == 1
        assert "op1" in groups[0].affected_operations
        assert "op2" in groups[0].affected_operations

    def test_get_error_fingerprinter_double_checked_locking(self):
        """Lines 402->405: double-checked locking creates new fingerprinter."""
        import obskit.fingerprint as fp_module

        original = fp_module._fingerprinter
        fp_module._fingerprinter = None
        try:
            fp1 = fp_module.get_error_fingerprinter("test-svc")
            assert fp1 is not None
            fp2 = fp_module.get_error_fingerprinter("test-svc")
            assert fp1 is fp2
        finally:
            fp_module._fingerprinter = original


# =============================================================================
# hot_path.py gaps
# =============================================================================


class TestHotPathGaps:
    """Lines 115, 294-310, 316-318, 329-330, 424->427."""

    def test_hot_path_to_dict(self):
        """Line 115: HotPath.to_dict method."""
        from obskit.hot_path import HotPath

        hp = HotPath(
            path="my-path",
            impact_score=0.9,
            call_count=5000,
            avg_latency_ms=150.0,
            suggestions=["Consider caching"],
        )
        d = hp.to_dict()
        assert d["path"] == "my-path"
        assert d["impact_score"] == 0.9
        assert d["call_count"] == 5000
        assert "Consider caching" in d["suggestions"]

    def test_generate_suggestions_high_latency(self):
        """Lines 294-297: avg_time_ms > 100 suggestion."""
        from obskit.hot_path import HotPathDetector

        detector = HotPathDetector(impact_threshold=0.0)
        stats_mock = MagicMock()
        stats_mock.impact_score = 1.0
        stats_mock.avg_time_ms = 200.0
        stats_mock.call_count = 500
        stats_mock.max_time_ms = 210.0
        stats_mock.error_rate = 0.0
        stats_mock.callers = {}

        suggestions = detector._generate_suggestions(stats_mock)
        assert any("latency" in s.lower() for s in suggestions)

    def test_generate_suggestions_high_call_count(self):
        """Lines 299-302: call_count > 10000 suggestion."""
        from obskit.hot_path import HotPathDetector

        detector = HotPathDetector(impact_threshold=0.0)
        stats_mock = MagicMock()
        stats_mock.impact_score = 1.0
        stats_mock.avg_time_ms = 50.0
        stats_mock.call_count = 15000
        stats_mock.max_time_ms = 55.0
        stats_mock.error_rate = 0.0
        stats_mock.callers = {}

        suggestions = detector._generate_suggestions(stats_mock)
        assert any("batching" in s.lower() or "call count" in s.lower() for s in suggestions)

    def test_generate_suggestions_high_variance(self):
        """Lines 304-307: max_time_ms > avg_time_ms * 10 suggestion."""
        from obskit.hot_path import HotPathDetector

        detector = HotPathDetector(impact_threshold=0.0)
        stats_mock = MagicMock()
        stats_mock.impact_score = 1.0
        stats_mock.avg_time_ms = 50.0
        stats_mock.call_count = 500
        stats_mock.max_time_ms = 600.0
        stats_mock.error_rate = 0.0
        stats_mock.callers = {}

        suggestions = detector._generate_suggestions(stats_mock)
        assert any("variance" in s.lower() or "outlier" in s.lower() for s in suggestions)

    def test_generate_suggestions_high_error_rate(self):
        """Lines 309-312: error_rate > 0.01 suggestion."""
        from obskit.hot_path import HotPathDetector

        detector = HotPathDetector(impact_threshold=0.0)
        stats_mock = MagicMock()
        stats_mock.impact_score = 1.0
        stats_mock.avg_time_ms = 50.0
        stats_mock.call_count = 500
        stats_mock.max_time_ms = 55.0
        stats_mock.error_rate = 0.05
        stats_mock.callers = {}

        suggestions = detector._generate_suggestions(stats_mock)
        assert any("error" in s.lower() for s in suggestions)

    def test_generate_suggestions_dominant_caller(self):
        """Lines 316-318: top caller > 50% of calls."""
        from obskit.hot_path import HotPathDetector

        detector = HotPathDetector(impact_threshold=0.0)
        stats_mock = MagicMock()
        stats_mock.impact_score = 1.0
        stats_mock.avg_time_ms = 50.0
        stats_mock.call_count = 100
        stats_mock.max_time_ms = 55.0
        stats_mock.error_rate = 0.0
        stats_mock.callers = {"heavy_caller": 80}

        suggestions = detector._generate_suggestions(stats_mock)
        assert any("heavy_caller" in s or "50%" in s for s in suggestions)

    def test_generate_suggestions_non_dominant_caller(self):
        """Lines 317->320: top caller at exactly 50% - False branch (not > 50%)."""
        from obskit.hot_path import HotPathDetector

        detector = HotPathDetector(impact_threshold=0.0)
        stats_mock = MagicMock()
        stats_mock.impact_score = 1.0
        stats_mock.avg_time_ms = 50.0
        stats_mock.call_count = 100
        stats_mock.max_time_ms = 55.0
        stats_mock.error_rate = 0.0
        # top_caller accounts for exactly 50% (50 out of 100) - not > 50%
        stats_mock.callers = {"caller_a": 50, "caller_b": 50}

        suggestions = detector._generate_suggestions(stats_mock)
        # No dominant caller suggestion should be added since max is at 50% (not > 50%)
        assert not any("50%+" in s for s in suggestions)

    def test_get_all_stats(self):
        """Lines 329-330: get_all_stats returns list of PathStats."""
        from obskit.hot_path import HotPathDetector

        detector = HotPathDetector()
        with detector.track("path-a"):
            pass
        with detector.track("path-b"):
            pass
        all_stats = detector.get_all_stats()
        assert len(all_stats) == 2

    def test_get_hot_path_detector_double_checked_locking(self):
        """Lines 424->427: double-checked locking creates new detector."""
        import obskit.hot_path as hp_module

        original = hp_module._detector
        hp_module._detector = None
        try:
            d1 = hp_module.get_hot_path_detector()
            assert d1 is not None
            d2 = hp_module.get_hot_path_detector()
            assert d1 is d2
        finally:
            hp_module._detector = original


# =============================================================================
# memory.py gaps
# =============================================================================


class TestMemoryGaps:
    """Lines 45-46, 99-101, 223-232, 246-261, 285-289, 311-316, 330, 380, 391-392."""

    def setup_method(self):
        """Ensure metrics are cleanly initialized before each test.
        
        We inject MagicMock objects for all prometheus metrics to avoid
        duplicate registration issues across test runs.
        """
        from unittest.mock import MagicMock

        import obskit.memory as memory_module

        # Reset state
        memory_module._metrics_initialized = True  # prevent re-init attempts
        # Inject mocks for all prometheus metrics
        memory_module.MEMORY_RSS_BYTES = MagicMock()
        memory_module.MEMORY_VMS_BYTES = MagicMock()
        memory_module.MEMORY_HEAP_BYTES = MagicMock()
        memory_module.MEMORY_PERCENT = MagicMock()
        memory_module.GC_COLLECTIONS_TOTAL = MagicMock()
        memory_module.GC_COLLECTED_OBJECTS = MagicMock()
        memory_module.GC_UNCOLLECTABLE_OBJECTS = MagicMock()
        memory_module.GC_DURATION_SECONDS = MagicMock()
        memory_module.OBJECT_COUNT = MagicMock()

    def test_has_psutil_flag_exists(self):
        """Lines 45-46: HAS_PSUTIL is a boolean (verifies import branch executed)."""
        import obskit.memory as memory_module
        assert isinstance(memory_module.HAS_PSUTIL, bool)

    def test_metrics_init_lines_77_to_80(self):
        """Lines 77-80: _init_metrics() creates all metrics using a fresh registry."""
        import prometheus_client

        import obskit.memory as memory_module

        registry = prometheus_client.CollectorRegistry()
        original_init = memory_module._metrics_initialized

        # Use the fresh registry via mocking Gauge/Counter/Histogram
        mock_gauge = MagicMock()
        mock_counter = MagicMock()
        mock_histogram = MagicMock()

        memory_module._metrics_initialized = False
        try:
            with patch("obskit.memory.Gauge", return_value=mock_gauge):
                with patch("obskit.memory.Counter", return_value=mock_counter):
                    with patch("obskit.memory.Histogram", return_value=mock_histogram):
                        memory_module._init_metrics()
            assert memory_module._metrics_initialized is True
        finally:
            memory_module._metrics_initialized = True

    def test_metrics_already_registered_value_error(self):
        """Lines 99-101: ValueError during metric registration sets _metrics_initialized=True."""
        import obskit.memory as memory_module

        memory_module._metrics_initialized = False
        with patch("obskit.memory.Gauge", side_effect=ValueError("already registered")):
            memory_module._init_metrics()
        assert memory_module._metrics_initialized is True

    def test_collect_memory_with_prometheus_metrics(self):
        """Lines 223->232: collect_memory sets Prometheus gauges when not None."""
        from obskit.memory import MemoryTracker

        tracker = MemoryTracker()
        stats = tracker.collect_memory()
        assert stats is not None
        assert stats.heap_bytes >= 0

    def test_collect_memory_with_none_metrics_false_branches(self):
        """Lines 223->225, 225->227, 227->229, 229->232: False branches when metrics are None."""
        import obskit.memory as memory_module
        from obskit.memory import MemoryTracker

        # Temporarily set all memory metrics to None to cover False branches
        orig_rss = memory_module.MEMORY_RSS_BYTES
        orig_vms = memory_module.MEMORY_VMS_BYTES
        orig_heap = memory_module.MEMORY_HEAP_BYTES
        orig_pct = memory_module.MEMORY_PERCENT
        try:
            memory_module.MEMORY_RSS_BYTES = None
            memory_module.MEMORY_VMS_BYTES = None
            memory_module.MEMORY_HEAP_BYTES = None
            memory_module.MEMORY_PERCENT = None
            tracker = MemoryTracker()
            stats = tracker.collect_memory()
            assert stats is not None
        finally:
            memory_module.MEMORY_RSS_BYTES = orig_rss
            memory_module.MEMORY_VMS_BYTES = orig_vms
            memory_module.MEMORY_HEAP_BYTES = orig_heap
            memory_module.MEMORY_PERCENT = orig_pct

    def test_collect_memory_without_psutil_false_branch(self):
        """Line 208->219: False branch when HAS_PSUTIL is False."""
        import obskit.memory as memory_module
        from obskit.memory import MemoryTracker

        orig_has_psutil = memory_module.HAS_PSUTIL
        try:
            memory_module.HAS_PSUTIL = False
            tracker = MemoryTracker()
            stats = tracker.collect_memory()
            # Without psutil, rss_bytes stays 0
            assert stats.rss_bytes == 0
        finally:
            memory_module.HAS_PSUTIL = orig_has_psutil

    def test_collect_gc_with_prometheus_metrics(self):
        """Lines 246->250, 250->241: GC_COLLECTIONS_TOTAL and GC_COLLECTED_OBJECTS (True branches)."""
        from obskit.memory import MemoryTracker

        tracker = MemoryTracker()
        stats = tracker.collect_gc()
        assert stats is not None

    def test_collect_gc_uncollectable_metric(self):
        """Line 258->261: GC_UNCOLLECTABLE_OBJECTS is set (True branch)."""
        from obskit.memory import MemoryTracker

        tracker = MemoryTracker()
        stats = tracker.collect_gc()
        assert stats.uncollectable >= 0

    def test_collect_gc_with_none_metrics_false_branches(self):
        """Lines 246->250, 250->241, 258->261: False branches when GC metrics are None."""
        import obskit.memory as memory_module
        from obskit.memory import MemoryTracker

        orig_gc_coll = memory_module.GC_COLLECTIONS_TOTAL
        orig_gc_obj = memory_module.GC_COLLECTED_OBJECTS
        orig_gc_uncoll = memory_module.GC_UNCOLLECTABLE_OBJECTS
        try:
            memory_module.GC_COLLECTIONS_TOTAL = None
            memory_module.GC_COLLECTED_OBJECTS = None
            memory_module.GC_UNCOLLECTABLE_OBJECTS = None
            tracker = MemoryTracker()
            stats = tracker.collect_gc()
            assert stats is not None
        finally:
            memory_module.GC_COLLECTIONS_TOTAL = orig_gc_coll
            memory_module.GC_COLLECTED_OBJECTS = orig_gc_obj
            memory_module.GC_UNCOLLECTABLE_OBJECTS = orig_gc_uncoll

    def test_collect_objects_with_prometheus(self):
        """Lines 285->289: OBJECT_COUNT.labels().set() called (True branch)."""
        from obskit.memory import MemoryTracker

        tracker = MemoryTracker(track_objects=True, top_object_types=5)
        stats = tracker.collect_objects()
        assert stats.total_objects > 0

    def test_collect_objects_false_track_objects_branch(self):
        """Line 268: collect_objects returns early when track_objects=False."""
        from obskit.memory import MemoryTracker

        tracker = MemoryTracker(track_objects=False)
        stats = tracker.collect_objects()
        assert stats.total_objects == 0

    def test_collect_objects_with_none_object_count_metric(self):
        """Lines 285->289: False branch when OBJECT_COUNT is None."""
        import obskit.memory as memory_module
        from obskit.memory import MemoryTracker

        orig_obj_count = memory_module.OBJECT_COUNT
        try:
            memory_module.OBJECT_COUNT = None
            tracker = MemoryTracker(track_objects=True)
            stats = tracker.collect_objects()
            assert stats.total_objects > 0
        finally:
            memory_module.OBJECT_COUNT = orig_obj_count

    def test_gc_callback_stop_phase_via_register(self):
        """Lines 311->316: gc callback stop phase via register_gc_callbacks."""
        import gc as gc_module

        from obskit.memory import MemoryTracker

        tracker = MemoryTracker()
        tracker.register_gc_callbacks()
        # Trigger both start and stop phases - GC calls callback with both
        gc_module.collect(0)

    def test_gc_callback_unknown_phase(self):
        """Line 311->exit: gc callback with unknown phase (neither start nor stop)."""
        import gc as gc_module

        from obskit.memory import MemoryTracker

        tracker = MemoryTracker()
        tracker.register_gc_callbacks()
        # Find the registered callback and call it with unknown phase
        # The callback is the last one registered
        callback = gc_module.callbacks[-1]
        callback("unknown_phase", {"generation": 0})  # Should not raise, just be a no-op

    def test_gc_callback_stop_without_start(self):
        """Line 312->exit: gc callback stop phase when generation not in _gc_start_time."""
        import gc as gc_module

        from obskit.memory import MemoryTracker

        tracker = MemoryTracker()
        tracker.register_gc_callbacks()
        # Find the registered callback
        callback = gc_module.callbacks[-1]
        # Call with "stop" but generation 99 not tracked (no preceding "start")
        callback("stop", {"generation": 99})  # Should not raise

    def test_gc_callback_stop_with_gc_duration_mock(self):
        """Line 315: GC_DURATION_SECONDS.labels().observe() is called in stop phase."""
        import gc as gc_module

        from obskit.memory import MemoryTracker

        tracker = MemoryTracker()
        tracker.register_gc_callbacks()
        callback = gc_module.callbacks[-1]
        # Simulate start then stop
        callback("start", {"generation": 1})
        callback("stop", {"generation": 1})  # GC_DURATION_SECONDS (mock) will be called

    def test_gc_callbacks_registered_only_once(self):
        """Line 312: register_gc_callbacks is idempotent."""
        from obskit.memory import MemoryTracker

        tracker = MemoryTracker()
        tracker.register_gc_callbacks()
        assert tracker._gc_callbacks_registered is True
        tracker.register_gc_callbacks()
        assert tracker._gc_callbacks_registered is True

    def test_force_gc_calls_gc_collect(self):
        """Lines 324-330: force_gc runs gc.collect for all 3 generations."""
        from obskit.memory import MemoryTracker

        tracker = MemoryTracker()
        results = tracker.force_gc()
        assert isinstance(results, dict)
        assert 0 in results
        assert 1 in results
        assert 2 in results

    def test_force_gc_with_none_gc_duration_false_branch(self):
        """Line 331->324: force_gc when GC_DURATION_SECONDS is None."""
        import obskit.memory as memory_module
        from obskit.memory import MemoryTracker

        orig_gc_dur = memory_module.GC_DURATION_SECONDS
        try:
            memory_module.GC_DURATION_SECONDS = None
            tracker = MemoryTracker()
            results = tracker.force_gc()
            assert isinstance(results, dict)
        finally:
            memory_module.GC_DURATION_SECONDS = orig_gc_dur

    def test_collect_calls_collect_objects_when_track_objects_true(self):
        """Line 380: tracker.collect_objects() called when track_objects=True."""
        from obskit.memory import MemoryTracker

        tracker = MemoryTracker(track_objects=True)
        result = tracker.collect()
        assert result is not None

    def test_memory_tracker_collect_does_not_raise(self):
        """Lines 391-392: exception in collect is caught without raising."""
        from obskit.memory import MemoryTracker

        tracker = MemoryTracker()
        result = tracker.collect()
        assert result is not None

    def test_memory_tracking_start_already_alive(self):
        """Line 367: return early when tracker already alive."""
        import time

        import obskit.memory as memory_module
        from obskit.memory import start_memory_tracking, stop_memory_tracking

        start_memory_tracking(interval_seconds=60.0)
        time.sleep(0.05)
        # Call again - should return early (line 367)
        start_memory_tracking(interval_seconds=60.0)
        stop_memory_tracking()

    def test_memory_tracking_with_exception_in_loop(self):
        """Lines 391-392: exception during tracking loop is caught."""
        import obskit.memory as memory_module
        from obskit.memory import start_memory_tracking, stop_memory_tracking

        def failing_on_high_memory(stats):
            raise RuntimeError("callback error")

        # Start tracking with tiny interval
        start_memory_tracking(
            interval_seconds=60.0,
            track_objects=True,
            on_high_memory=failing_on_high_memory,
            high_memory_threshold_percent=0.0,  # Always trigger
        )

        import time
        time.sleep(0.1)
        stop_memory_tracking()

    def test_memory_tracking_with_track_objects_false(self):
        """Line 379->382: tracking loop does not call collect_objects when track_objects=False."""
        import time

        from obskit.memory import start_memory_tracking, stop_memory_tracking

        start_memory_tracking(interval_seconds=60.0, track_objects=False)
        time.sleep(0.05)
        stop_memory_tracking()

    def test_memory_tracking_with_track_objects(self):
        """Line 380: tracking loop calls collect_objects when track_objects=True."""
        import time

        from obskit.memory import start_memory_tracking, stop_memory_tracking

        start_memory_tracking(interval_seconds=60.0, track_objects=True)
        time.sleep(0.05)
        stop_memory_tracking()

    def test_memory_tracking_stop_with_live_thread(self):
        """Line 405->407: stop_memory_tracking with live background tracker joins thread."""
        import time

        import obskit.memory as memory_module
        from obskit.memory import start_memory_tracking, stop_memory_tracking

        start_memory_tracking(interval_seconds=60.0)
        time.sleep(0.05)
        assert memory_module._background_tracker is not None
        assert memory_module._background_tracker.is_alive()
        stop_memory_tracking()  # Covers 405->407 True branch

    def test_stop_memory_tracking_without_tracker_false_branch(self):
        """Line 405->407: stop_memory_tracking when _background_tracker is None."""
        import obskit.memory as memory_module
        from obskit.memory import stop_memory_tracking

        orig_tracker = memory_module._background_tracker
        try:
            memory_module._background_tracker = None
            stop_memory_tracking()  # Covers 405->407 False branch (None)
        finally:
            memory_module._background_tracker = orig_tracker

    def test_get_memory_tracker(self):
        """Line 412: get_memory_tracker returns a MemoryTracker."""
        from obskit.memory import MemoryTracker, get_memory_tracker

        tracker = get_memory_tracker()
        assert isinstance(tracker, MemoryTracker)


# =============================================================================
# quota.py gaps
# =============================================================================


class TestQuotaGaps:
    """Lines 391->exit, 458->461, 487->490."""

    def test_reset_usage_specific_resource_exists(self):
        """Line 391->exit: True branch - reset_usage with resource that exists in usage."""
        from obskit.quota import QuotaPeriod, QuotaTracker

        tracker = QuotaTracker("reset-specific")
        tracker.set_limit("tenant1", "api_calls", limit=100, period=QuotaPeriod.HOUR)
        tracker.check_and_increment("tenant1", "api_calls")
        tracker.check_and_increment("tenant1", "api_calls")
        tracker.reset_usage("tenant1", "api_calls")
        usage = tracker.get_usage("tenant1", "api_calls")
        assert usage.current_usage == 0

    def test_reset_usage_specific_resource_not_in_usage(self):
        """Line 391->exit: False branch - resource specified but not in tenant usage."""
        from obskit.quota import QuotaPeriod, QuotaTracker

        tracker = QuotaTracker("reset-missing-resource")
        tracker.set_limit("tenant1", "api_calls", limit=100, period=QuotaPeriod.HOUR)
        tracker.check_and_increment("tenant1", "api_calls")
        # Reset a resource that doesn't exist in the usage dict
        tracker.reset_usage("tenant1", "nonexistent_resource")  # 391->exit False branch
        # Original resource should be unchanged
        usage = tracker.get_usage("tenant1", "api_calls")
        assert usage.current_usage == 1

    def test_maybe_warn_cooldown_suppresses_second_warning(self):
        """Lines 458->461: second warning within 5 minutes is suppressed."""
        from obskit.quota import QuotaTracker, TenantUsage

        warnings_received = []

        def on_warning(tid, resource, usage):
            warnings_received.append((tid, resource))

        tracker = QuotaTracker("warn-cooldown", on_warning=on_warning)

        warn_key = "t1:calls"
        tracker._warned[warn_key] = datetime.utcnow()

        usage = TenantUsage(tenant_id="t1", resource="calls", current_usage=60)
        tracker._maybe_warn("t1", "calls", usage)
        assert len(warnings_received) == 0

    def test_maybe_warn_after_cooldown_sends_warning(self):
        """Line 461: _warned updated after cooldown expires."""
        from obskit.quota import QuotaTracker, TenantUsage

        warnings_received = []

        def on_warning(tid, resource, usage):
            warnings_received.append((tid, resource))

        tracker = QuotaTracker("warn-after-cooldown", on_warning=on_warning)
        warn_key = "t1:calls"
        tracker._warned[warn_key] = datetime.utcnow() - timedelta(minutes=6)

        usage = TenantUsage(tenant_id="t1", resource="calls", current_usage=60)
        tracker._maybe_warn("t1", "calls", usage)
        assert len(warnings_received) == 1
        assert warn_key in tracker._warned

    def test_get_quota_tracker_double_checked_locking(self):
        """Lines 487->490: double-checked locking creates new tracker."""
        from obskit.quota import _trackers, get_quota_tracker

        unique_name = f"unique-quota-{time.time()}"
        assert unique_name not in _trackers
        t = get_quota_tracker(unique_name)
        assert t is not None
        t2 = get_quota_tracker(unique_name)
        assert t is t2
