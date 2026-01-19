"""Unit tests for Dependency Graph Visualizer."""

import pytest
from obskit.dependency_graph import (
    DependencyGraph,
    DependencyNode,
    DependencyType,
    HealthStatus,
    get_dependency_graph,
)


class TestDependencyGraph:
    """Tests for DependencyGraph."""

    def test_add_dependency(self):
        """Test adding a dependency."""
        graph = DependencyGraph("test-service")
        
        graph.add_dependency("postgres", DependencyType.DATABASE)
        
        dep = graph.get_dependency("postgres")
        assert dep is not None
        assert dep.name == "postgres"
        assert dep.dependency_type == DependencyType.DATABASE

    def test_add_dependency_with_string_type(self):
        """Test adding dependency with string type."""
        graph = DependencyGraph("test-service")
        
        graph.add_dependency("redis", "cache")
        
        dep = graph.get_dependency("redis")
        assert dep.dependency_type == DependencyType.CACHE

    def test_record_call(self):
        """Test recording dependency calls."""
        graph = DependencyGraph("test-service")
        graph.add_dependency("api", DependencyType.SERVICE)
        
        graph.record_call("api", latency_ms=50.0, success=True)
        graph.record_call("api", latency_ms=100.0, success=True)
        graph.record_call("api", latency_ms=150.0, success=False)
        
        dep = graph.get_dependency("api")
        assert dep.total_calls == 3
        assert dep.failed_calls == 1
        assert dep.error_rate > 0

    def test_auto_detect_dependency(self):
        """Test auto-detection of dependencies."""
        graph = DependencyGraph("test-service", auto_detect=True)
        
        graph.record_call("unknown-service", latency_ms=100.0)
        
        dep = graph.get_dependency("unknown-service")
        assert dep is not None
        assert dep.dependency_type == DependencyType.OTHER

    def test_health_status_update(self):
        """Test health status updates based on calls."""
        graph = DependencyGraph("test-service")
        graph.add_dependency("database", DependencyType.DATABASE)
        
        # Record many failures
        for _ in range(10):
            graph.record_call("database", latency_ms=100.0, success=False)
        
        dep = graph.get_dependency("database")
        assert dep.health_status == HealthStatus.UNHEALTHY

    def test_get_unhealthy_dependencies(self):
        """Test getting unhealthy dependencies."""
        graph = DependencyGraph("test-service")
        graph.add_dependency("healthy", DependencyType.SERVICE)
        graph.add_dependency("unhealthy", DependencyType.SERVICE)
        
        graph.record_call("healthy", 50.0, success=True)
        for _ in range(10):
            graph.record_call("unhealthy", 100.0, success=False)
        
        unhealthy = graph.get_unhealthy_dependencies()
        assert len(unhealthy) == 1
        assert unhealthy[0].name == "unhealthy"

    def test_critical_path(self):
        """Test critical path detection."""
        graph = DependencyGraph("test-service")
        graph.add_dependency("critical-db", DependencyType.DATABASE, is_critical=True)
        graph.add_dependency("optional-cache", DependencyType.CACHE)
        
        for _ in range(100):
            graph.record_call("critical-db", 10.0)
        for _ in range(10):
            graph.record_call("optional-cache", 5.0)
        
        critical_path = graph.get_critical_path()
        assert "critical-db" in critical_path

    def test_visualization_data(self):
        """Test visualization data generation."""
        graph = DependencyGraph("test-service")
        graph.add_dependency("postgres", DependencyType.DATABASE)
        graph.add_dependency("redis", DependencyType.CACHE)
        
        viz = graph.get_visualization_data()
        
        assert viz.service_name == "test-service"
        assert viz.total_dependencies == 2
        assert len(viz.nodes) == 3  # Service + 2 dependencies
        assert len(viz.edges) == 2

    def test_is_healthy(self):
        """Test overall health check."""
        graph = DependencyGraph("test-service")
        graph.add_dependency("critical", DependencyType.DATABASE, is_critical=True)
        
        graph.record_call("critical", 50.0, success=True)
        assert graph.is_healthy() is True
        
        for _ in range(10):
            graph.record_call("critical", 100.0, success=False)
        assert graph.is_healthy() is False


class TestDependencyNode:
    """Tests for DependencyNode."""

    def test_to_dict(self):
        """Test DependencyNode serialization."""
        node = DependencyNode(
            name="test",
            dependency_type=DependencyType.DATABASE,
            health_status=HealthStatus.HEALTHY,
        )
        
        data = node.to_dict()
        assert data["name"] == "test"
        assert data["type"] == "database"
        assert data["health_status"] == "healthy"


class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_dependency_graph(self):
        """Test dependency graph singleton per service."""
        graph1 = get_dependency_graph("service1")
        graph2 = get_dependency_graph("service1")
        graph3 = get_dependency_graph("service2")
        
        assert graph1 is graph2
        assert graph1 is not graph3
