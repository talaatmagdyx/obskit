"""
Performance Budgets.

Enforce performance constraints at code level.
"""

import functools
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar

from prometheus_client import Counter, Gauge

from .logging import get_logger

logger = get_logger(__name__)

# Metrics
BUDGET_VIOLATIONS = Counter(
    "performance_budget_violations_total",
    "Total budget violations",
    ["budget_name", "violation_type"],
)

BUDGET_STATUS = Gauge(
    "performance_budget_status", "Budget status (1=healthy, 0=violated)", ["budget_name"]
)

BUDGET_UTILIZATION = Gauge(
    "performance_budget_utilization", "Budget utilization percentage", ["budget_name", "metric"]
)

F = TypeVar("F", bound=Callable[..., Any])


@dataclass
class BudgetStatus:
    """Status of a performance budget."""

    name: str
    healthy: bool
    violations: list[str] = field(default_factory=list)
    utilization: dict[str, float] = field(default_factory=dict)
    last_checked: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "healthy": self.healthy,
            "violations": self.violations,
            "utilization": self.utilization,
            "last_checked": self.last_checked,
        }


class PerformanceBudget:
    """
    Defines and enforces performance constraints.

    Example:
        budget = PerformanceBudget(
            name="widget_execution",
            latency_p50_ms=100,
            latency_p95_ms=500,
            latency_p99_ms=1000,
            error_rate_percent=1.0,
            throughput_min_rps=10,
        )

        @budget.enforce
        async def execute_widget(params):
            # If budget is exceeded, logs warning
            pass

        # Check budget status
        if budget.is_exceeded():
            logger.warning("Budget exceeded", status=budget.get_status())
    """

    def __init__(
        self,
        name: str,
        latency_p50_ms: float | None = None,
        latency_p95_ms: float | None = None,
        latency_p99_ms: float | None = None,
        latency_max_ms: float | None = None,
        error_rate_percent: float | None = None,
        throughput_min_rps: float | None = None,
        throughput_max_rps: float | None = None,
        window_seconds: int = 60,
        on_violation: Callable[[str, str, float], None] | None = None,
    ):
        """
        Initialize performance budget.

        Args:
            name: Budget name (used in metrics)
            latency_p50_ms: 50th percentile latency threshold (ms)
            latency_p95_ms: 95th percentile latency threshold (ms)
            latency_p99_ms: 99th percentile latency threshold (ms)
            latency_max_ms: Maximum latency threshold (ms)
            error_rate_percent: Error rate threshold (%)
            throughput_min_rps: Minimum throughput (requests/second)
            throughput_max_rps: Maximum throughput (requests/second)
            window_seconds: Rolling window for calculations
            on_violation: Callback when budget is violated
        """
        self.name = name
        self.latency_p50_ms = latency_p50_ms
        self.latency_p95_ms = latency_p95_ms
        self.latency_p99_ms = latency_p99_ms
        self.latency_max_ms = latency_max_ms
        self.error_rate_percent = error_rate_percent
        self.throughput_min_rps = throughput_min_rps
        self.throughput_max_rps = throughput_max_rps
        self.window_seconds = window_seconds
        self.on_violation = on_violation

        # Rolling window data
        self._latencies: deque = deque()
        self._errors: deque = deque()
        self._requests: deque = deque()

        # Initialize metrics
        BUDGET_STATUS.labels(budget_name=name).set(1)

    def record_latency(self, latency_ms: float):
        """Record a latency measurement."""
        now = time.time()
        self._latencies.append((now, latency_ms))
        self._requests.append(now)
        self._cleanup_old_data()

    def record_error(self):
        """Record an error."""
        now = time.time()
        self._errors.append(now)
        self._requests.append(now)
        self._cleanup_old_data()

    def record_success(self, latency_ms: float):
        """Record a successful request."""
        self.record_latency(latency_ms)

    def _cleanup_old_data(self):
        """Remove data outside the window."""
        cutoff = time.time() - self.window_seconds

        while self._latencies and self._latencies[0][0] < cutoff:
            self._latencies.popleft()
        while self._errors and self._errors[0] < cutoff:
            self._errors.popleft()
        while self._requests and self._requests[0] < cutoff:
            self._requests.popleft()

    def _calculate_percentile(self, p: float) -> float | None:
        """Calculate latency percentile."""
        if not self._latencies:
            return None

        sorted_latencies = sorted(latency[1] for latency in self._latencies)
        index = int(len(sorted_latencies) * p / 100)
        index = min(index, len(sorted_latencies) - 1)
        return sorted_latencies[index]

    def get_current_metrics(self) -> dict[str, float | None]:
        """Get current metrics values."""
        self._cleanup_old_data()

        latencies = [latency[1] for latency in self._latencies]

        return {
            "latency_p50_ms": self._calculate_percentile(50),
            "latency_p95_ms": self._calculate_percentile(95),
            "latency_p99_ms": self._calculate_percentile(99),
            "latency_max_ms": max(latencies) if latencies else None,
            "error_rate_percent": (
                len(self._errors) / len(self._requests) * 100 if self._requests else 0
            ),
            "throughput_rps": (len(self._requests) / self.window_seconds if self._requests else 0),
        }

    def check_violations(self) -> list[str]:
        """Check for budget violations."""
        violations = []
        metrics = self.get_current_metrics()

        checks = [
            ("latency_p50_ms", self.latency_p50_ms, "<="),
            ("latency_p95_ms", self.latency_p95_ms, "<="),
            ("latency_p99_ms", self.latency_p99_ms, "<="),
            ("latency_max_ms", self.latency_max_ms, "<="),
            ("error_rate_percent", self.error_rate_percent, "<="),
            ("throughput_rps", self.throughput_min_rps, ">="),
        ]

        if self.throughput_max_rps:
            checks.append(("throughput_rps", self.throughput_max_rps, "<="))

        for metric_name, threshold, op in checks:
            if threshold is None:
                continue

            current = metrics.get(metric_name)
            if current is None:
                continue

            violated = False
            if op == "<=" and current > threshold:
                violated = True
            elif op == ">=" and current < threshold:
                violated = True

            if violated:
                violation = f"{metric_name}: {current:.2f} (threshold: {op} {threshold})"
                violations.append(violation)
                BUDGET_VIOLATIONS.labels(budget_name=self.name, violation_type=metric_name).inc()

                if self.on_violation:
                    self.on_violation(self.name, metric_name, current)

            # Update utilization
            if threshold > 0:
                if op == "<=":
                    utilization = current / threshold * 100
                else:
                    utilization = threshold / max(current, 0.001) * 100

                BUDGET_UTILIZATION.labels(budget_name=self.name, metric=metric_name).set(
                    min(utilization, 200)
                )  # Cap at 200%

        # Update status
        is_healthy = len(violations) == 0
        BUDGET_STATUS.labels(budget_name=self.name).set(1 if is_healthy else 0)

        return violations

    def is_exceeded(self) -> bool:
        """Check if budget is exceeded."""
        return len(self.check_violations()) > 0

    def get_status(self) -> BudgetStatus:
        """Get detailed budget status."""
        violations = self.check_violations()
        metrics = self.get_current_metrics()

        utilization = {}
        for metric, threshold in [
            ("latency_p50_ms", self.latency_p50_ms),
            ("latency_p95_ms", self.latency_p95_ms),
            ("latency_p99_ms", self.latency_p99_ms),
            ("error_rate_percent", self.error_rate_percent),
        ]:
            if threshold and metrics.get(metric) is not None:
                utilization[metric] = metrics[metric] / threshold * 100

        return BudgetStatus(
            name=self.name,
            healthy=len(violations) == 0,
            violations=violations,
            utilization=utilization,
            last_checked=time.time(),
        )

    def enforce(self, func: F) -> F:
        """
        Decorator to enforce budget on a function.

        Records latency/errors and logs warnings on violations.
        """

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                latency_ms = (time.time() - start_time) * 1000
                self.record_success(latency_ms)

                # Check and log violations
                violations = self.check_violations()
                if violations:
                    logger.warning(
                        "performance_budget_exceeded",
                        budget=self.name,
                        function=func.__name__,
                        violations=violations,
                    )

                return result
            except Exception:
                self.record_error()
                raise

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                latency_ms = (time.time() - start_time) * 1000
                self.record_success(latency_ms)

                violations = self.check_violations()
                if violations:
                    logger.warning(
                        "performance_budget_exceeded",
                        budget=self.name,
                        function=func.__name__,
                        violations=violations,
                    )

                return result
            except Exception:
                self.record_error()
                raise

        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return wrapper  # type: ignore


def budget(performance_budget: PerformanceBudget) -> Callable[[F], F]:
    """
    Decorator to apply a performance budget to a function.

    Example:
        widget_budget = PerformanceBudget(name="widget", latency_p95_ms=500)

        @budget(widget_budget)
        def process_widget():
            pass
    """
    return performance_budget.enforce


class BudgetManager:
    """
    Manages multiple performance budgets.

    Example:
        manager = BudgetManager()
        manager.register(api_budget)
        manager.register(database_budget)

        # Check all budgets
        status = manager.check_all()
    """

    def __init__(self):
        self._budgets: dict[str, PerformanceBudget] = {}

    def register(self, budget: PerformanceBudget):
        """Register a budget."""
        self._budgets[budget.name] = budget

    def get(self, name: str) -> PerformanceBudget | None:
        """Get a budget by name."""
        return self._budgets.get(name)

    def check_all(self) -> dict[str, BudgetStatus]:
        """Check all budgets and return status."""
        return {name: budget.get_status() for name, budget in self._budgets.items()}

    def is_any_exceeded(self) -> bool:
        """Check if any budget is exceeded."""
        return any(b.is_exceeded() for b in self._budgets.values())

    def get_exceeded_budgets(self) -> list[str]:
        """Get names of exceeded budgets."""
        return [name for name, budget in self._budgets.items() if budget.is_exceeded()]


# Global budget manager
_budget_manager = BudgetManager()


def get_budget_manager() -> BudgetManager:
    """Get the global budget manager."""
    return _budget_manager


__all__ = [
    "PerformanceBudget",
    "BudgetStatus",
    "BudgetManager",
    "budget",
    "get_budget_manager",
    "BUDGET_VIOLATIONS",
    "BUDGET_STATUS",
    "BUDGET_UTILIZATION",
]
