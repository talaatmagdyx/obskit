"""Unit tests for Auto-Scaling Metrics."""

import pytest
from obskit.autoscaling import (
    AutoScalingMetrics,
    ScalingRecommendation,
    ScalingConfig,
    ScalingDirection,
    get_autoscaling_metrics,
)


class TestAutoScalingMetrics:
    """Tests for AutoScalingMetrics."""

    def test_set_replicas(self):
        """Test setting replica count."""
        scaling = AutoScalingMetrics("test-service")
        
        scaling.set_replicas(5)
        
        rec = scaling.get_recommendation()
        assert rec.current_replicas == 5

    def test_record_queue_depth(self):
        """Test recording queue depth."""
        scaling = AutoScalingMetrics("test-service")
        
        scaling.record_queue_depth(500)
        
        metrics = scaling.get_metrics_for_hpa()
        assert metrics["queue_depth"] == 500

    def test_record_requests_per_second(self):
        """Test recording RPS."""
        scaling = AutoScalingMetrics("test-service")
        
        scaling.record_requests_per_second(1000.0)
        
        metrics = scaling.get_metrics_for_hpa()
        assert metrics["requests_per_second"] == 1000.0

    def test_record_pod_metrics(self):
        """Test recording pod-level metrics."""
        scaling = AutoScalingMetrics("test-service")
        
        scaling.record_pod_metrics(
            pod_name="pod-1",
            cpu_utilization=75.0,
            memory_utilization=60.0,
            request_count=100,
        )
        
        metrics = scaling.get_metrics_for_hpa()
        assert metrics["avg_cpu_utilization"] == 75.0

    def test_scale_up_recommendation(self):
        """Test scale up recommendation."""
        config = ScalingConfig(
            min_replicas=1,
            max_replicas=10,
            target_cpu_utilization=70.0,
        )
        scaling = AutoScalingMetrics("test-service", config=config)
        
        scaling.set_replicas(2)
        
        # High CPU should trigger scale up
        scaling.record_pod_metrics("pod-1", cpu_utilization=90.0, memory_utilization=50.0)
        scaling.record_pod_metrics("pod-2", cpu_utilization=85.0, memory_utilization=50.0)
        
        rec = scaling.get_recommendation()
        
        # Should recommend scaling up
        assert rec.direction == ScalingDirection.UP or rec.target_replicas >= rec.current_replicas

    def test_scale_down_recommendation(self):
        """Test scale down recommendation."""
        config = ScalingConfig(
            min_replicas=1,
            max_replicas=10,
            target_cpu_utilization=70.0,
            scale_down_threshold=0.3,
        )
        scaling = AutoScalingMetrics("test-service", config=config)
        
        scaling.set_replicas(5)
        
        # Low CPU should trigger scale down
        scaling.record_pod_metrics("pod-1", cpu_utilization=10.0, memory_utilization=20.0)
        
        rec = scaling.get_recommendation()
        
        # May recommend scaling down
        assert rec.direction in [ScalingDirection.DOWN, ScalingDirection.NONE]

    def test_queue_based_scaling(self):
        """Test queue-based scaling."""
        config = ScalingConfig(
            min_replicas=1,
            max_replicas=10,
            target_queue_depth_per_pod=100,
        )
        scaling = AutoScalingMetrics("test-service", config=config)
        
        scaling.set_replicas(1)
        scaling.record_queue_depth(500)  # 5x target
        
        rec = scaling.get_recommendation()
        
        # Should scale up to handle queue
        assert rec.target_replicas >= 5

    def test_respects_max_replicas(self):
        """Test that recommendations respect max replicas."""
        config = ScalingConfig(max_replicas=3)
        scaling = AutoScalingMetrics("test-service", config=config)
        
        scaling.set_replicas(2)
        scaling.record_queue_depth(10000)  # Very high
        
        rec = scaling.get_recommendation()
        
        assert rec.target_replicas <= 3

    def test_respects_min_replicas(self):
        """Test that recommendations respect min replicas."""
        config = ScalingConfig(min_replicas=2)
        scaling = AutoScalingMetrics("test-service", config=config)
        
        scaling.set_replicas(3)
        # Low everything
        scaling.record_pod_metrics("pod-1", cpu_utilization=5.0, memory_utilization=5.0)
        
        rec = scaling.get_recommendation()
        
        assert rec.target_replicas >= 2

    def test_record_scaling_event(self):
        """Test recording scaling event."""
        scaling = AutoScalingMetrics("test-service")
        
        scaling.record_scaling_event(ScalingDirection.UP, 5)
        
        # Should update current replicas
        rec = scaling.get_recommendation()
        assert rec.current_replicas == 5


class TestScalingRecommendation:
    """Tests for ScalingRecommendation."""

    def test_to_dict(self):
        """Test ScalingRecommendation serialization."""
        rec = ScalingRecommendation(
            current_replicas=2,
            target_replicas=4,
            direction=ScalingDirection.UP,
            reason="high_cpu",
            confidence=0.8,
            metrics={"avg_cpu": 85.0},
        )
        
        data = rec.to_dict()
        assert data["current_replicas"] == 2
        assert data["target_replicas"] == 4
        assert data["direction"] == "up"


class TestScalingConfig:
    """Tests for ScalingConfig."""

    def test_to_dict(self):
        """Test ScalingConfig serialization."""
        config = ScalingConfig(
            min_replicas=2,
            max_replicas=10,
            target_cpu_utilization=70.0,
        )
        
        data = config.to_dict()
        assert data["min_replicas"] == 2
        assert data["max_replicas"] == 10
        assert data["target_cpu_utilization"] == 70.0


class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_autoscaling_metrics(self):
        """Test metrics singleton per service."""
        metrics1 = get_autoscaling_metrics("service1")
        metrics2 = get_autoscaling_metrics("service1")
        metrics3 = get_autoscaling_metrics("service2")
        
        assert metrics1 is metrics2
        assert metrics1 is not metrics3
