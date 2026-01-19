"""Unit tests for Flame Graph Integration."""

import time
import pytest
from obskit.flamegraph import (
    FlameGraphProfiler,
    ProfileResult,
    profile_function,
    get_flamegraph_profiler,
)


class TestFlameGraphProfiler:
    """Tests for FlameGraphProfiler."""

    def test_profile_operation(self):
        """Test profiling a code block."""
        profiler = FlameGraphProfiler()
        
        with profiler.profile("test_operation"):
            # Simulate work
            total = sum(range(1000))
        
        result = profiler.get_profile("test_operation")
        assert result is not None
        assert result.operation == "test_operation"
        assert result.duration_seconds > 0
        assert result.total_calls > 0

    def test_profile_with_nested_calls(self):
        """Test profiling with nested function calls."""
        profiler = FlameGraphProfiler()
        
        def inner_func():
            return sum(range(100))
        
        def outer_func():
            return inner_func() * 2
        
        with profiler.profile("nested_test"):
            outer_func()
        
        result = profiler.get_profile("nested_test")
        assert result is not None
        assert len(result.top_functions) > 0

    def test_generate_flamegraph_data(self):
        """Test flame graph data generation."""
        profiler = FlameGraphProfiler()
        
        with profiler.profile("flamegraph_test"):
            _ = [i ** 2 for i in range(500)]
        
        data = profiler.generate_flamegraph_data("flamegraph_test")
        assert data is not None
        assert data.name == "flamegraph_test"
        assert data.value > 0

    def test_export_collapsed(self):
        """Test collapsed stack format export."""
        profiler = FlameGraphProfiler()
        
        with profiler.profile("export_test"):
            _ = list(range(1000))
        
        collapsed = profiler.export_collapsed("export_test")
        assert isinstance(collapsed, str)

    def test_multiple_profiles(self):
        """Test multiple profile operations."""
        profiler = FlameGraphProfiler()
        
        for i in range(3):
            with profiler.profile(f"operation_{i}"):
                time.sleep(0.01)
        
        all_profiles = profiler.get_all_profiles()
        assert len(all_profiles) == 3

    def test_clear_profiles(self):
        """Test clearing profiles."""
        profiler = FlameGraphProfiler()
        
        with profiler.profile("to_clear"):
            pass
        
        profiler.clear("to_clear")
        assert profiler.get_profile("to_clear") is None

    def test_profile_function_decorator(self):
        """Test profile_function decorator."""
        profiler = FlameGraphProfiler()
        
        @profile_function("decorated_func", profiler=profiler)
        def my_function():
            return sum(range(100))
        
        result = my_function()
        assert result == 4950
        
        profile = profiler.get_profile("decorated_func")
        assert profile is not None


class TestProfileResult:
    """Tests for ProfileResult."""

    def test_to_dict(self):
        """Test ProfileResult serialization."""
        from datetime import datetime
        
        result = ProfileResult(
            operation="test",
            duration_seconds=1.5,
            total_calls=100,
            top_functions=[("func1", 500.0, 50)],
            call_tree={},
        )
        
        data = result.to_dict()
        assert data["operation"] == "test"
        assert data["duration_seconds"] == 1.5
        assert data["total_calls"] == 100
        assert len(data["top_functions"]) == 1


class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_flamegraph_profiler(self):
        """Test global profiler singleton."""
        profiler1 = get_flamegraph_profiler()
        profiler2 = get_flamegraph_profiler()
        assert profiler1 is profiler2
