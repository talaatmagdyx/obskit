"""
Auto-Scaling Metrics
====================

Metrics for Kubernetes HPA and custom auto-scaling.

Features:
- Custom metrics export
- Scale recommendation
- Cost-aware scaling
- Pod utilization tracking

Example:
    from obskit.autoscaling import AutoScalingMetrics

    scaling = AutoScalingMetrics("order-service")

    # Record metrics
    scaling.record_queue_depth(150)
    scaling.record_processing_rate(50)

    # Get scaling recommendation
    rec = scaling.get_recommendation()
    print(f"Scale to {rec.target_replicas} pods")
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
# Prometheus Metrics (HPA-compatible)
# =============================================================================

# Custom metrics for HPA
CUSTOM_METRIC_QUEUE_DEPTH = Gauge(
    "autoscaling_queue_depth", "Current queue depth for scaling", ["service"]
)

CUSTOM_METRIC_REQUESTS_PER_SECOND = Gauge(
    "autoscaling_requests_per_second", "Current request rate", ["service"]
)

CUSTOM_METRIC_PROCESSING_RATE = Gauge(
    "autoscaling_processing_rate", "Items processed per second", ["service"]
)

CUSTOM_METRIC_CPU_UTILIZATION = Gauge(
    "autoscaling_cpu_utilization", "CPU utilization percentage", ["service", "pod"]
)

CUSTOM_METRIC_MEMORY_UTILIZATION = Gauge(
    "autoscaling_memory_utilization", "Memory utilization percentage", ["service", "pod"]
)

# Scaling metrics
SCALING_EVENTS = Counter(
    "autoscaling_events_total", "Total scaling events", ["service", "direction"]
)

CURRENT_REPLICAS = Gauge("autoscaling_current_replicas", "Current number of replicas", ["service"])

TARGET_REPLICAS = Gauge("autoscaling_target_replicas", "Recommended target replicas", ["service"])


# =============================================================================
# Enums and Data Classes
# =============================================================================


class ScalingDirection(Enum):
    """Scaling direction."""

    UP = "up"
    DOWN = "down"
    NONE = "none"


@dataclass
class ScalingConfig:
    """Auto-scaling configuration."""

    min_replicas: int = 1
    max_replicas: int = 10
    target_cpu_utilization: float = 70.0
    target_memory_utilization: float = 80.0
    target_queue_depth_per_pod: int = 100
    scale_up_threshold: float = 0.8  # Scale up when > 80% of target
    scale_down_threshold: float = 0.3  # Scale down when < 30% of target
    cooldown_seconds: int = 300

    def to_dict(self) -> dict[str, Any]:
        return {
            "min_replicas": self.min_replicas,
            "max_replicas": self.max_replicas,
            "target_cpu_utilization": self.target_cpu_utilization,
            "target_memory_utilization": self.target_memory_utilization,
            "target_queue_depth_per_pod": self.target_queue_depth_per_pod,
            "scale_up_threshold": self.scale_up_threshold,
            "scale_down_threshold": self.scale_down_threshold,
            "cooldown_seconds": self.cooldown_seconds,
        }


@dataclass
class ScalingRecommendation:
    """Scaling recommendation."""

    current_replicas: int
    target_replicas: int
    direction: ScalingDirection
    reason: str
    confidence: float
    metrics: dict[str, float]
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "current_replicas": self.current_replicas,
            "target_replicas": self.target_replicas,
            "direction": self.direction.value,
            "reason": self.reason,
            "confidence": self.confidence,
            "metrics": self.metrics,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class PodMetrics:
    """Metrics for a single pod."""

    pod_name: str
    cpu_utilization: float = 0.0
    memory_utilization: float = 0.0
    request_count: int = 0
    last_updated: datetime = field(default_factory=datetime.utcnow)


# =============================================================================
# Auto-Scaling Metrics
# =============================================================================


class AutoScalingMetrics:
    """
    Export metrics for auto-scaling decisions.

    Parameters
    ----------
    service_name : str
        Name of the service
    config : ScalingConfig, optional
        Scaling configuration
    """

    def __init__(
        self,
        service_name: str,
        config: ScalingConfig | None = None,
    ):
        self.service_name = service_name
        self.config = config or ScalingConfig()

        self._current_replicas = 1
        self._queue_depth = 0
        self._requests_per_second = 0.0
        self._processing_rate = 0.0
        self._pod_metrics: dict[str, PodMetrics] = {}
        self._last_scaling: datetime | None = None

        self._lock = threading.Lock()

    def set_replicas(self, count: int):
        """Set current replica count."""
        with self._lock:
            self._current_replicas = count

        CURRENT_REPLICAS.labels(service=self.service_name).set(count)

    def record_queue_depth(self, depth: int):
        """
        Record current queue depth.

        Parameters
        ----------
        depth : int
            Number of items in queue
        """
        with self._lock:
            self._queue_depth = depth

        CUSTOM_METRIC_QUEUE_DEPTH.labels(service=self.service_name).set(depth)

    def record_requests_per_second(self, rps: float):
        """
        Record requests per second.

        Parameters
        ----------
        rps : float
            Requests per second
        """
        with self._lock:
            self._requests_per_second = rps

        CUSTOM_METRIC_REQUESTS_PER_SECOND.labels(service=self.service_name).set(rps)

    def record_processing_rate(self, rate: float):
        """
        Record processing rate.

        Parameters
        ----------
        rate : float
            Items processed per second
        """
        with self._lock:
            self._processing_rate = rate

        CUSTOM_METRIC_PROCESSING_RATE.labels(service=self.service_name).set(rate)

    def record_pod_metrics(
        self,
        pod_name: str,
        cpu_utilization: float,
        memory_utilization: float,
        request_count: int = 0,
    ):
        """
        Record metrics for a specific pod.

        Parameters
        ----------
        pod_name : str
            Pod name
        cpu_utilization : float
            CPU usage percentage
        memory_utilization : float
            Memory usage percentage
        request_count : int
            Requests handled
        """
        with self._lock:
            self._pod_metrics[pod_name] = PodMetrics(
                pod_name=pod_name,
                cpu_utilization=cpu_utilization,
                memory_utilization=memory_utilization,
                request_count=request_count,
            )

        CUSTOM_METRIC_CPU_UTILIZATION.labels(service=self.service_name, pod=pod_name).set(
            cpu_utilization
        )

        CUSTOM_METRIC_MEMORY_UTILIZATION.labels(service=self.service_name, pod=pod_name).set(
            memory_utilization
        )

    def get_recommendation(self) -> ScalingRecommendation:
        """
        Get scaling recommendation based on current metrics.

        Returns
        -------
        ScalingRecommendation
        """
        with self._lock:
            current = self._current_replicas
            queue_depth = self._queue_depth
            rps = self._requests_per_second
            processing_rate = self._processing_rate
            pods = dict(self._pod_metrics)

        # Calculate average utilizations
        avg_cpu = 0.0
        avg_memory = 0.0

        if pods:
            avg_cpu = sum(p.cpu_utilization for p in pods.values()) / len(pods)
            avg_memory = sum(p.memory_utilization for p in pods.values()) / len(pods)

        # Determine scaling need
        target = current
        direction = ScalingDirection.NONE
        reasons = []

        # CPU-based scaling
        if avg_cpu > self.config.target_cpu_utilization * self.config.scale_up_threshold:
            cpu_target = int(current * (avg_cpu / self.config.target_cpu_utilization))
            target = max(target, cpu_target)
            reasons.append(f"high_cpu:{avg_cpu:.1f}%")
        elif avg_cpu < self.config.target_cpu_utilization * self.config.scale_down_threshold:
            cpu_target = max(1, int(current * (avg_cpu / self.config.target_cpu_utilization)))
            target = min(target, cpu_target) if target == current else target
            reasons.append(f"low_cpu:{avg_cpu:.1f}%")

        # Queue-based scaling
        if queue_depth > 0:
            queue_target = max(1, queue_depth // self.config.target_queue_depth_per_pod)
            if queue_target > current:
                target = max(target, queue_target)
                reasons.append(f"queue_depth:{queue_depth}")

        # Processing rate vs request rate
        if rps > 0 and processing_rate > 0 and current > 0:
            demand_ratio = rps / (processing_rate * current)
            if demand_ratio > 1.2:
                demand_target = int(current * demand_ratio)
                target = max(target, demand_target)
                reasons.append(f"demand_ratio:{demand_ratio:.2f}")

        # Apply limits
        target = max(self.config.min_replicas, min(self.config.max_replicas, target))

        # Determine direction
        if target > current:
            direction = ScalingDirection.UP
        elif target < current:
            direction = ScalingDirection.DOWN

        # Check cooldown
        if self._last_scaling:
            elapsed = (datetime.utcnow() - self._last_scaling).total_seconds()
            if elapsed < self.config.cooldown_seconds:
                direction = ScalingDirection.NONE
                target = current
                reasons.append(f"cooldown:{int(self.config.cooldown_seconds - elapsed)}s")

        # Calculate confidence
        confidence = 0.5
        if pods:
            confidence += 0.3  # Have pod metrics
        if queue_depth > 0 or rps > 0:
            confidence += 0.2  # Have workload metrics

        reason = ", ".join(reasons) if reasons else "stable"

        recommendation = ScalingRecommendation(
            current_replicas=current,
            target_replicas=target,
            direction=direction,
            reason=reason,
            confidence=min(1.0, confidence),
            metrics={
                "avg_cpu": avg_cpu,
                "avg_memory": avg_memory,
                "queue_depth": queue_depth,
                "rps": rps,
                "processing_rate": processing_rate,
            },
        )

        # Update metrics
        TARGET_REPLICAS.labels(service=self.service_name).set(target)

        if direction != ScalingDirection.NONE:
            logger.info(
                "scaling_recommendation",
                service=self.service_name,
                current=current,
                target=target,
                direction=direction.value,
                reason=reason,
            )

        return recommendation

    def record_scaling_event(self, direction: ScalingDirection, new_replicas: int):
        """Record that a scaling event occurred."""
        with self._lock:
            self._last_scaling = datetime.utcnow()
            self._current_replicas = new_replicas

        SCALING_EVENTS.labels(service=self.service_name, direction=direction.value).inc()

        CURRENT_REPLICAS.labels(service=self.service_name).set(new_replicas)

        logger.info(
            "scaling_event",
            service=self.service_name,
            direction=direction.value,
            new_replicas=new_replicas,
        )

    def get_metrics_for_hpa(self) -> dict[str, float]:
        """
        Get metrics in HPA-compatible format.

        Returns
        -------
        dict
            Metrics for HPA
        """
        with self._lock:
            pods = dict(self._pod_metrics)

        avg_cpu = 0.0
        avg_memory = 0.0

        if pods:
            avg_cpu = sum(p.cpu_utilization for p in pods.values()) / len(pods)
            avg_memory = sum(p.memory_utilization for p in pods.values()) / len(pods)

        return {
            "queue_depth": self._queue_depth,
            "requests_per_second": self._requests_per_second,
            "processing_rate": self._processing_rate,
            "avg_cpu_utilization": avg_cpu,
            "avg_memory_utilization": avg_memory,
        }


# =============================================================================
# Singleton
# =============================================================================

_metrics: dict[str, AutoScalingMetrics] = {}
_metrics_lock = threading.Lock()


def get_autoscaling_metrics(service_name: str, **kwargs) -> AutoScalingMetrics:
    """Get or create auto-scaling metrics."""
    if service_name not in _metrics:
        with _metrics_lock:
            if service_name not in _metrics:
                _metrics[service_name] = AutoScalingMetrics(service_name, **kwargs)

    return _metrics[service_name]
