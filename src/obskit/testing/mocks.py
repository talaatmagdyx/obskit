"""
Mock Objects for Testing
========================

Mock implementations of obskit components for unit testing.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import MagicMock, patch


@dataclass
class RecordedRequest:
    """Represents a recorded metric request."""

    operation: str
    duration_seconds: float
    status: str
    error_type: str | None = None
    labels: dict[str, str] = field(default_factory=dict)


class MockMetrics:
    """
    Mock REDMetrics for testing.

    Example
    -------
    >>> mock = MockMetrics()
    >>> mock.observe_request("create_order", 0.1, "success")
    >>> mock.assert_request_recorded("create_order", status="success")
    >>> assert mock.get_request_count("create_order") == 1
    """

    def __init__(self, name: str = "test"):
        self.name = name
        self.requests: list[RecordedRequest] = []
        self._original = None

    def observe_request(
        self,
        operation: str,
        duration_seconds: float = 0.0,
        status: str = "success",
        error_type: str | None = None,
        **labels,
    ):
        """Record a request observation."""
        self.requests.append(
            RecordedRequest(
                operation=operation,
                duration_seconds=duration_seconds,
                status=status,
                error_type=error_type,
                labels=labels,
            )
        )

    def track_request(self, operation: str):
        """Context manager for tracking requests."""

        @contextmanager
        def _tracker():
            import time

            start = time.perf_counter()
            try:
                yield
                duration = time.perf_counter() - start
                self.observe_request(operation, duration, "success")
            except Exception as e:
                duration = time.perf_counter() - start
                self.observe_request(operation, duration, "failure", type(e).__name__)
                raise

        return _tracker()

    def reset(self):
        """Clear all recorded requests."""
        self.requests.clear()

    def get_requests(self, operation: str | None = None) -> list[RecordedRequest]:
        """Get recorded requests, optionally filtered by operation."""
        if operation:
            return [r for r in self.requests if r.operation == operation]
        return self.requests

    def get_request_count(
        self, operation: str | None = None, status: str | None = None
    ) -> int:
        """Get count of recorded requests."""
        requests = self.get_requests(operation)
        if status:
            requests = [r for r in requests if r.status == status]
        return len(requests)

    def assert_request_recorded(
        self,
        operation: str,
        status: str | None = None,
        min_count: int = 1,
    ):
        """Assert that a request was recorded."""
        count = self.get_request_count(operation, status)
        if count < min_count:
            recorded = [r.operation for r in self.requests]
            raise AssertionError(
                f"Expected at least {min_count} request(s) for '{operation}' "
                f"(status={status}), but found {count}. "
                f"Recorded operations: {recorded}"
            )

    def assert_no_requests(self, operation: str | None = None):
        """Assert that no requests were recorded."""
        count = self.get_request_count(operation)
        if count > 0:
            raise AssertionError(f"Expected no requests for '{operation}', but found {count}")

    @contextmanager
    def patch(self):
        """Patch REDMetrics with this mock."""
        with patch("obskit.metrics.REDMetrics", return_value=self):
            with patch("obskit.metrics.red.get_red_metrics", return_value=self):
                yield self


@dataclass
class RecordedSpan:
    """Represents a recorded trace span."""

    name: str
    attributes: dict[str, Any] = field(default_factory=dict)
    status: str = "ok"
    events: list[str] = field(default_factory=list)


class MockTracer:
    """
    Mock tracer for testing.

    Example
    -------
    >>> mock = MockTracer()
    >>> with mock.trace_span("my_operation"):
    ...     do_work()
    >>> mock.assert_span_created("my_operation")
    """

    def __init__(self):
        self.spans: list[RecordedSpan] = []
        self._current_span: RecordedSpan | None = None

    @contextmanager
    def trace_span(
        self,
        name: str,
        component: str = "",
        operation: str = "",
        attributes: dict[str, Any] | None = None,
    ):
        """Create a mock span."""
        span = RecordedSpan(
            name=name,
            attributes={
                "component": component,
                "operation": operation,
                **(attributes or {}),
            },
        )
        self.spans.append(span)
        self._current_span = span
        try:
            yield span
            span.status = "ok"
        except Exception:
            span.status = "error"
            raise
        finally:
            self._current_span = None

    def reset(self):
        """Clear recorded spans."""
        self.spans.clear()
        self._current_span = None

    def get_spans(self, name: str | None = None) -> list[RecordedSpan]:
        """Get recorded spans."""
        if name:
            return [s for s in self.spans if s.name == name]
        return self.spans

    def assert_span_created(self, name: str, min_count: int = 1):
        """Assert that a span was created."""
        count = len(self.get_spans(name))
        if count < min_count:
            recorded = [s.name for s in self.spans]
            raise AssertionError(
                f"Expected at least {min_count} span(s) named '{name}', "
                f"but found {count}. Recorded spans: {recorded}"
            )

    @contextmanager
    def patch(self):
        """Patch tracing with this mock."""
        with patch("obskit.tracing.trace_span", self.trace_span):
            with patch("obskit.tracing.get_tracer", return_value=self):
                yield self


@dataclass
class RecordedMeasurement:
    """Represents a recorded SLO measurement."""

    slo_name: str
    value: float
    success: bool


class MockSLOTracker:
    """
    Mock SLO tracker for testing.

    Example
    -------
    >>> mock = MockSLOTracker()
    >>> mock.record_measurement("availability", 1.0, success=True)
    >>> mock.assert_measurement_recorded("availability")
    """

    def __init__(self):
        self.measurements: list[RecordedMeasurement] = []
        self._slos: dict[str, dict] = {}

    def register_slo(self, name: str, **kwargs):
        """Register an SLO."""
        self._slos[name] = kwargs

    def record_measurement(self, slo_name: str, value: float = 1.0, success: bool = True):
        """Record an SLO measurement."""
        self.measurements.append(
            RecordedMeasurement(
                slo_name=slo_name,
                value=value,
                success=success,
            )
        )

    def get_status(self, slo_name: str):
        """Get mock SLO status."""
        successes = [m for m in self.measurements if m.slo_name == slo_name and m.success]
        total = [m for m in self.measurements if m.slo_name == slo_name]

        if not total:
            return None

        return MagicMock(
            current_value=len(successes) / len(total),
            target=MagicMock(target_value=0.999),
            error_budget_remaining=1.0,
            error_budget_burn_rate=0.0,
        )

    def reset(self):
        """Clear measurements."""
        self.measurements.clear()

    def assert_measurement_recorded(self, slo_name: str, min_count: int = 1):
        """Assert measurement was recorded."""
        count = len([m for m in self.measurements if m.slo_name == slo_name])
        if count < min_count:
            raise AssertionError(
                f"Expected at least {min_count} measurement(s) for '{slo_name}', but found {count}"
            )

    @contextmanager
    def patch(self):
        """Patch SLO tracker with this mock."""
        with patch("obskit.slo.get_slo_tracker", return_value=self):
            yield self


class MockHealthChecker:
    """Mock health checker for testing."""

    def __init__(self):
        self._checks: dict[str, bool] = {}
        self._liveness_checks: dict[str, Any] = {}
        self._readiness_checks: dict[str, Any] = {}

    def add_liveness_check(self, name: str):
        """Decorator to add liveness check."""

        def decorator(func):
            self._liveness_checks[name] = func
            return func

        return decorator

    def add_readiness_check(self, name: str):
        """Decorator to add readiness check."""

        def decorator(func):
            self._readiness_checks[name] = func
            return func

        return decorator

    def set_check_status(self, name: str, healthy: bool):
        """Set a check's status for testing."""
        self._checks[name] = healthy

    async def check_health(self):
        """Check all health statuses."""
        all_healthy = all(self._checks.values()) if self._checks else True
        return MagicMock(
            status="healthy" if all_healthy else "unhealthy",
            checks=self._checks,
        )


class MockCircuitBreaker:
    """
    Mock circuit breaker for testing.

    Example
    -------
    >>> mock = MockCircuitBreaker()
    >>> mock.set_state("open")  # Force circuit to be open
    >>> with mock:  # Will raise CircuitOpenError
    ...     call_external_service()
    """

    def __init__(self, name: str = "test"):
        self.name = name
        self._state = "closed"
        self._failure_count = 0
        self._success_count = 0

    def set_state(self, state: str):
        """Set circuit state ('closed', 'open', 'half_open')."""
        self._state = state

    @property
    def state(self):
        """Get current state as mock."""
        return MagicMock(name=self._state)

    @property
    def failure_count(self):
        return self._failure_count

    @property
    def success_count(self):
        return self._success_count

    def __enter__(self):
        if self._state == "open":
            from obskit import CircuitOpenError

            raise CircuitOpenError(breaker_name=self.name, time_until_retry=0.0)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self._failure_count += 1
        else:
            self._success_count += 1
        return False

    def reset(self):
        """Reset circuit breaker."""
        self._state = "closed"
        self._failure_count = 0
        self._success_count = 0


__all__ = [
    "RecordedRequest",
    "RecordedSpan",
    "RecordedMeasurement",
    "MockMetrics",
    "MockTracer",
    "MockSLOTracker",
    "MockHealthChecker",
    "MockCircuitBreaker",
]
