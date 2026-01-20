"""
Dependency Graph Visualizer
===========================

Track and visualize service dependencies.

Features:
- Automatic dependency detection
- Graph visualization data
- Dependency health status
- Critical path analysis

Example:
    from obskit.dependency_graph import DependencyGraph

    graph = DependencyGraph("order-service")
    graph.add_dependency("postgres", "database")
    graph.add_dependency("redis", "cache")
    graph.add_dependency("user-service", "service")

    viz_data = graph.get_visualization_data()
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

DEPENDENCY_STATUS = Gauge(
    "dependency_graph_status",
    "Dependency status (1=healthy, 0=unhealthy)",
    ["service", "dependency", "dependency_type"],
)

DEPENDENCY_LATENCY = Gauge(
    "dependency_graph_latency_ms", "Dependency latency in milliseconds", ["service", "dependency"]
)

DEPENDENCY_CALLS = Counter(
    "dependency_graph_calls_total", "Total calls to dependency", ["service", "dependency", "status"]
)

DEPENDENCY_COUNT = Gauge(
    "dependency_graph_dependencies_total",
    "Total number of dependencies",
    ["service", "dependency_type"],
)


# =============================================================================
# Enums and Data Classes
# =============================================================================


class DependencyType(Enum):
    """Types of dependencies."""

    DATABASE = "database"
    CACHE = "cache"
    MESSAGE_QUEUE = "message_queue"
    SERVICE = "service"
    EXTERNAL_API = "external_api"
    STORAGE = "storage"
    OTHER = "other"


class HealthStatus(Enum):
    """Health status of a dependency."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class DependencyNode:
    """A dependency node in the graph."""

    name: str
    dependency_type: DependencyType
    endpoint: str | None = None
    health_status: HealthStatus = HealthStatus.UNKNOWN
    latency_ms: float = 0.0
    error_rate: float = 0.0
    last_check: datetime | None = None
    total_calls: int = 0
    failed_calls: int = 0
    is_critical: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "type": self.dependency_type.value,
            "endpoint": self.endpoint,
            "health_status": self.health_status.value,
            "latency_ms": self.latency_ms,
            "error_rate": self.error_rate,
            "last_check": self.last_check.isoformat() if self.last_check else None,
            "total_calls": self.total_calls,
            "failed_calls": self.failed_calls,
            "is_critical": self.is_critical,
            "metadata": self.metadata,
        }


@dataclass
class DependencyEdge:
    """An edge between service and dependency."""

    source: str
    target: str
    weight: float = 1.0  # Call frequency
    latency_p50: float = 0.0
    latency_p99: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "weight": self.weight,
            "latency_p50": self.latency_p50,
            "latency_p99": self.latency_p99,
        }


@dataclass
class GraphVisualization:
    """Data for graph visualization."""

    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    service_name: str
    total_dependencies: int
    healthy_count: int
    unhealthy_count: int
    critical_path: list[str]
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": self.nodes,
            "edges": self.edges,
            "service_name": self.service_name,
            "total_dependencies": self.total_dependencies,
            "healthy_count": self.healthy_count,
            "unhealthy_count": self.unhealthy_count,
            "critical_path": self.critical_path,
            "timestamp": self.timestamp.isoformat(),
        }


# =============================================================================
# Dependency Graph
# =============================================================================


class DependencyGraph:
    """
    Track and visualize service dependencies.

    Parameters
    ----------
    service_name : str
        Name of this service
    auto_detect : bool
        Automatically detect dependencies from calls
    """

    def __init__(
        self,
        service_name: str,
        auto_detect: bool = True,
    ):
        self.service_name = service_name
        self.auto_detect = auto_detect

        self._dependencies: dict[str, DependencyNode] = {}
        self._edges: dict[str, DependencyEdge] = {}
        self._latency_samples: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def add_dependency(
        self,
        name: str,
        dependency_type: DependencyType | str,
        endpoint: str | None = None,
        is_critical: bool = False,
        metadata: dict[str, Any] | None = None,
    ):
        """
        Add a dependency.

        Parameters
        ----------
        name : str
            Dependency name
        dependency_type : DependencyType or str
            Type of dependency
        endpoint : str, optional
            Endpoint URL/address
        is_critical : bool
            Whether this is a critical dependency
        metadata : dict, optional
            Additional metadata
        """
        if isinstance(dependency_type, str):
            dependency_type = DependencyType(dependency_type)

        with self._lock:
            self._dependencies[name] = DependencyNode(
                name=name,
                dependency_type=dependency_type,
                endpoint=endpoint,
                is_critical=is_critical,
                metadata=metadata or {},
            )

            edge_key = f"{self.service_name}->{name}"
            self._edges[edge_key] = DependencyEdge(
                source=self.service_name,
                target=name,
            )

            self._latency_samples[name] = []

        # Update metrics
        self._update_dependency_count()

        logger.info(
            "dependency_added",
            service=self.service_name,
            dependency=name,
            type=dependency_type.value,
            is_critical=is_critical,
        )

    def remove_dependency(self, name: str):
        """Remove a dependency."""
        with self._lock:
            if name in self._dependencies:
                del self._dependencies[name]

            edge_key = f"{self.service_name}->{name}"
            if edge_key in self._edges:
                del self._edges[edge_key]

            if name in self._latency_samples:
                del self._latency_samples[name]

        self._update_dependency_count()

    def record_call(
        self,
        dependency: str,
        latency_ms: float,
        success: bool = True,
    ):
        """
        Record a call to a dependency.

        Parameters
        ----------
        dependency : str
            Dependency name
        latency_ms : float
            Call latency
        success : bool
            Whether call succeeded
        """
        with self._lock:
            # Auto-detect dependency
            if self.auto_detect and dependency not in self._dependencies:
                self.add_dependency(dependency, DependencyType.OTHER)

            if dependency not in self._dependencies:
                return

            node = self._dependencies[dependency]
            node.total_calls += 1
            node.last_check = datetime.utcnow()

            if not success:
                node.failed_calls += 1

            # Update error rate
            node.error_rate = node.failed_calls / node.total_calls if node.total_calls > 0 else 0.0

            # Update latency
            samples = self._latency_samples.get(dependency, [])
            samples.append(latency_ms)
            if len(samples) > 100:
                samples = samples[-100:]
            self._latency_samples[dependency] = samples

            node.latency_ms = sum(samples) / len(samples) if samples else 0

            # Update edge
            edge_key = f"{self.service_name}->{dependency}"
            if edge_key in self._edges:
                edge = self._edges[edge_key]
                edge.weight += 1

                sorted_samples = sorted(samples)
                if sorted_samples:
                    edge.latency_p50 = sorted_samples[len(sorted_samples) // 2]
                    edge.latency_p99 = sorted_samples[int(len(sorted_samples) * 0.99)]

            # Update health status
            if node.error_rate > 0.5:
                node.health_status = HealthStatus.UNHEALTHY
            elif node.error_rate > 0.1:
                node.health_status = HealthStatus.DEGRADED
            else:
                node.health_status = HealthStatus.HEALTHY

        # Update metrics
        DEPENDENCY_CALLS.labels(
            service=self.service_name,
            dependency=dependency,
            status="success" if success else "failure",
        ).inc()

        DEPENDENCY_LATENCY.labels(service=self.service_name, dependency=dependency).set(latency_ms)

        dep_node = self._dependencies.get(dependency)
        if dep_node:
            DEPENDENCY_STATUS.labels(
                service=self.service_name,
                dependency=dependency,
                dependency_type=dep_node.dependency_type.value,
            ).set(1 if dep_node.health_status == HealthStatus.HEALTHY else 0)

    def update_health(
        self,
        dependency: str,
        status: HealthStatus | str,
        latency_ms: float | None = None,
    ):
        """
        Update dependency health status.

        Parameters
        ----------
        dependency : str
            Dependency name
        status : HealthStatus or str
            New status
        latency_ms : float, optional
            Current latency
        """
        if isinstance(status, str):
            status = HealthStatus(status)

        with self._lock:
            if dependency not in self._dependencies:
                return

            node = self._dependencies[dependency]
            node.health_status = status
            node.last_check = datetime.utcnow()

            if latency_ms is not None:
                node.latency_ms = latency_ms

        DEPENDENCY_STATUS.labels(
            service=self.service_name,
            dependency=dependency,
            dependency_type=node.dependency_type.value,
        ).set(1 if status == HealthStatus.HEALTHY else 0)

    def _update_dependency_count(self):
        """Update dependency count metrics."""
        with self._lock:
            counts: dict[str, int] = {}
            for node in self._dependencies.values():
                dep_type = node.dependency_type.value
                counts[dep_type] = counts.get(dep_type, 0) + 1

            for dep_type, count in counts.items():
                DEPENDENCY_COUNT.labels(service=self.service_name, dependency_type=dep_type).set(
                    count
                )

    def get_dependency(self, name: str) -> DependencyNode | None:
        """Get a dependency by name."""
        with self._lock:
            return self._dependencies.get(name)

    def get_all_dependencies(self) -> list[DependencyNode]:
        """Get all dependencies."""
        with self._lock:
            return list(self._dependencies.values())

    def get_unhealthy_dependencies(self) -> list[DependencyNode]:
        """Get unhealthy dependencies."""
        with self._lock:
            return [
                dep
                for dep in self._dependencies.values()
                if dep.health_status == HealthStatus.UNHEALTHY
            ]

    def get_critical_path(self) -> list[str]:
        """Get critical dependencies (highest impact if they fail)."""
        with self._lock:
            critical = [
                (name, node.total_calls, node.is_critical)
                for name, node in self._dependencies.items()
            ]

            # Sort by critical flag first, then by call count
            critical.sort(key=lambda x: (not x[2], -x[1]))

            return [name for name, _, _ in critical[:5]]

    def get_visualization_data(self) -> GraphVisualization:
        """
        Get data for graph visualization.

        Returns
        -------
        GraphVisualization
        """
        with self._lock:
            # Create service node
            nodes = [
                {
                    "id": self.service_name,
                    "label": self.service_name,
                    "type": "service",
                    "is_root": True,
                }
            ]

            # Add dependency nodes
            healthy_count = 0
            unhealthy_count = 0

            for name, node in self._dependencies.items():
                nodes.append(
                    {
                        "id": name,
                        "label": name,
                        "type": node.dependency_type.value,
                        "health": node.health_status.value,
                        "latency_ms": node.latency_ms,
                        "error_rate": node.error_rate,
                        "is_critical": node.is_critical,
                    }
                )

                if node.health_status == HealthStatus.HEALTHY:
                    healthy_count += 1
                elif node.health_status == HealthStatus.UNHEALTHY:
                    unhealthy_count += 1

            # Create edges
            edges = [edge.to_dict() for edge in self._edges.values()]

            return GraphVisualization(
                nodes=nodes,
                edges=edges,
                service_name=self.service_name,
                total_dependencies=len(self._dependencies),
                healthy_count=healthy_count,
                unhealthy_count=unhealthy_count,
                critical_path=self.get_critical_path(),
            )

    def is_healthy(self) -> bool:
        """Check if all critical dependencies are healthy."""
        with self._lock:
            for node in self._dependencies.values():
                if node.is_critical and node.health_status == HealthStatus.UNHEALTHY:
                    return False
            return True


# =============================================================================
# Singleton
# =============================================================================

_graphs: dict[str, DependencyGraph] = {}
_graph_lock = threading.Lock()


def get_dependency_graph(service_name: str, **kwargs) -> DependencyGraph:
    """Get or create a dependency graph."""
    if service_name not in _graphs:
        with _graph_lock:
            if service_name not in _graphs:
                _graphs[service_name] = DependencyGraph(service_name, **kwargs)

    return _graphs[service_name]
