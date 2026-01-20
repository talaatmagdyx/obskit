"""Unit tests for performance budgets."""

import time

import pytest

from obskit.budgets import (
    BudgetManager,
    BudgetStatus,
    PerformanceBudget,
    budget,
    get_budget_manager,
)


class TestBudgetStatus:
    """Tests for BudgetStatus dataclass."""

    def test_init(self):
        """Test default initialization."""
        status = BudgetStatus(name="test", healthy=True)
        assert status.name == "test"
        assert status.healthy is True
        assert status.violations == []
        assert status.utilization == {}

    def test_to_dict(self):
        """Test conversion to dictionary."""
        status = BudgetStatus(
            name="test",
            healthy=False,
            violations=["latency_p95_ms: 600 (threshold: <= 500)"],
            utilization={"latency_p95_ms": 120.0},
        )

        data = status.to_dict()
        assert data["name"] == "test"
        assert data["healthy"] is False
        assert len(data["violations"]) == 1
        assert data["utilization"]["latency_p95_ms"] == 120.0


class TestPerformanceBudget:
    """Tests for PerformanceBudget class."""

    def test_init_defaults(self):
        """Test initialization with defaults."""
        budget = PerformanceBudget(name="test")
        assert budget.name == "test"
        assert budget.window_seconds == 60

    def test_init_with_thresholds(self):
        """Test initialization with custom thresholds."""
        budget = PerformanceBudget(
            name="api",
            latency_p50_ms=100,
            latency_p95_ms=500,
            latency_p99_ms=1000,
            error_rate_percent=1.0,
            throughput_min_rps=10,
        )

        assert budget.latency_p50_ms == 100
        assert budget.latency_p95_ms == 500
        assert budget.latency_p99_ms == 1000
        assert budget.error_rate_percent == 1.0
        assert budget.throughput_min_rps == 10

    def test_record_latency(self):
        """Test recording latency."""
        budget = PerformanceBudget(name="test")

        budget.record_latency(100)
        budget.record_latency(200)
        budget.record_latency(150)

        metrics = budget.get_current_metrics()
        assert metrics["latency_p50_ms"] is not None

    def test_record_error(self):
        """Test recording errors."""
        budget = PerformanceBudget(name="test")

        budget.record_latency(100)
        budget.record_latency(100)
        budget.record_error()

        metrics = budget.get_current_metrics()
        assert metrics["error_rate_percent"] > 0

    def test_record_success(self):
        """Test recording success."""
        budget = PerformanceBudget(name="test")

        budget.record_success(100)
        budget.record_success(200)

        metrics = budget.get_current_metrics()
        assert metrics["latency_max_ms"] == 200

    def test_check_violations_none(self):
        """Test check_violations returns empty when within budget."""
        budget = PerformanceBudget(name="test", latency_p95_ms=500, error_rate_percent=5.0)

        # All successful, low latency
        for _ in range(20):
            budget.record_success(100)

        violations = budget.check_violations()
        assert len(violations) == 0

    def test_check_violations_latency_exceeded(self):
        """Test check_violations detects latency threshold breach."""
        budget = PerformanceBudget(name="test", latency_p95_ms=100)

        # High latency requests
        for i in range(20):
            budget.record_success(200 + i * 10)

        violations = budget.check_violations()
        # Should have latency violation
        assert any("latency" in v.lower() for v in violations)

    def test_check_violations_error_rate_exceeded(self):
        """Test check_violations detects error rate threshold breach."""
        budget = PerformanceBudget(name="test", error_rate_percent=5.0)

        # High error rate (50%)
        for _i in range(10):
            budget.record_success(100)
        for _i in range(10):
            budget.record_error()

        violations = budget.check_violations()
        assert any("error" in v.lower() for v in violations)

    def test_is_exceeded(self):
        """Test is_exceeded helper method."""
        budget = PerformanceBudget(name="test", latency_p95_ms=100)

        # Within budget
        for _ in range(20):
            budget.record_success(50)

        assert budget.is_exceeded() is False

        # Exceed budget
        for _ in range(20):
            budget.record_success(500)

        assert budget.is_exceeded() is True

    def test_get_status(self):
        """Test get_status returns BudgetStatus."""
        budget = PerformanceBudget(name="test", latency_p95_ms=500)

        for _ in range(10):
            budget.record_success(100)

        status = budget.get_status()
        assert isinstance(status, BudgetStatus)
        assert status.name == "test"
        assert status.healthy is True

    def test_enforce_decorator(self):
        """Test enforce decorator tracks function execution."""
        budget = PerformanceBudget(name="test", latency_p95_ms=1000)

        @budget.enforce
        def fast_function():
            return "result"

        result = fast_function()
        assert result == "result"

        # Latency should be recorded
        _metrics = budget.get_current_metrics()  # Verify metrics are available
        assert len(budget._latencies) > 0

    def test_enforce_decorator_records_error(self):
        """Test enforce decorator records errors."""
        budget = PerformanceBudget(name="test", error_rate_percent=50)

        @budget.enforce
        def failing_function():
            raise ValueError("Test error")

        with pytest.raises(ValueError):
            failing_function()

        # Error should be recorded
        assert len(budget._errors) == 1

    @pytest.mark.asyncio
    async def test_enforce_async_decorator(self):
        """Test enforce decorator works with async functions."""
        budget = PerformanceBudget(name="test", latency_p95_ms=1000)

        @budget.enforce
        async def async_function():
            return "async_result"

        result = await async_function()
        assert result == "async_result"

    def test_on_violation_callback(self):
        """Test on_violation callback is called."""
        violations_received = []

        def on_violation(name, metric, value):
            violations_received.append((name, metric, value))

        budget = PerformanceBudget(name="test", latency_p95_ms=100, on_violation=on_violation)

        # Exceed threshold
        for _ in range(20):
            budget.record_success(500)

        budget.check_violations()

        assert len(violations_received) > 0

    def test_window_cleanup(self):
        """Test old data is cleaned up outside window."""
        budget = PerformanceBudget(
            name="test",
            window_seconds=1,  # 1 second window
        )

        budget.record_success(100)

        # Wait for window to expire
        time.sleep(1.5)

        budget._cleanup_old_data()

        # Old data should be removed
        assert len(budget._latencies) == 0


class TestBudgetManager:
    """Tests for BudgetManager class."""

    def test_register(self):
        """Test registering a budget."""
        manager = BudgetManager()
        budget = PerformanceBudget(name="api")

        manager.register(budget)

        assert manager.get("api") is budget

    def test_get(self):
        """Test getting a budget by name."""
        manager = BudgetManager()
        budget = PerformanceBudget(name="api")
        manager.register(budget)

        assert manager.get("api") is budget
        assert manager.get("nonexistent") is None

    def test_check_all(self):
        """Test checking all budgets."""
        manager = BudgetManager()

        budget1 = PerformanceBudget(name="api", latency_p95_ms=500)
        budget2 = PerformanceBudget(name="db", latency_p95_ms=100)

        manager.register(budget1)
        manager.register(budget2)

        # Record some data
        budget1.record_success(100)
        budget2.record_success(50)

        statuses = manager.check_all()

        assert "api" in statuses
        assert "db" in statuses
        assert isinstance(statuses["api"], BudgetStatus)

    def test_is_any_exceeded(self):
        """Test checking if any budget is exceeded."""
        manager = BudgetManager()

        budget1 = PerformanceBudget(name="api", latency_p95_ms=500)
        budget2 = PerformanceBudget(name="db", latency_p95_ms=100)

        manager.register(budget1)
        manager.register(budget2)

        # All within budget
        for _ in range(10):
            budget1.record_success(100)
            budget2.record_success(50)

        assert manager.is_any_exceeded() is False

        # Exceed db budget
        for _ in range(10):
            budget2.record_success(500)

        assert manager.is_any_exceeded() is True

    def test_get_exceeded_budgets(self):
        """Test getting list of exceeded budgets."""
        manager = BudgetManager()

        budget1 = PerformanceBudget(name="api", latency_p95_ms=500)
        budget2 = PerformanceBudget(name="db", latency_p95_ms=100)

        manager.register(budget1)
        manager.register(budget2)

        # Only exceed db budget
        for _ in range(10):
            budget1.record_success(100)
            budget2.record_success(500)

        exceeded = manager.get_exceeded_budgets()
        assert "db" in exceeded
        assert "api" not in exceeded


class TestBudgetDecorator:
    """Tests for budget decorator."""

    def test_decorator(self):
        """Test budget decorator applies enforcement."""
        test_budget = PerformanceBudget(name="decorator_test", latency_p95_ms=1000)

        @budget(test_budget)
        def decorated_function():
            return "result"

        result = decorated_function()
        assert result == "result"


class TestGetBudgetManager:
    """Tests for get_budget_manager function."""

    def test_returns_singleton(self):
        """Test get_budget_manager returns singleton instance."""
        manager1 = get_budget_manager()
        manager2 = get_budget_manager()

        assert manager1 is manager2
