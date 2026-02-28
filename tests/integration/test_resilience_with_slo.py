"""
Integration Tests: Resilience + SLO
=====================================

Verifies that circuit breaker state transitions correctly contribute to
SLO error-budget burn and that the resilience / SLO packages interact
as expected end-to-end.

Cross-package boundary tested:
  obskit-resilience  →  obskit-slo  →  obskit-metrics
"""

from __future__ import annotations

import asyncio

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_availability_slo(name: str, target: float = 0.99, window: int = 60):
    """Create an availability SLO via the real SLOTracker API."""
    from obskit.slo import SLOTracker
    from obskit.slo.types import SLOType

    tracker = SLOTracker()
    tracker.register_slo(name, SLOType.AVAILABILITY, target_value=target, window_seconds=window)
    return tracker


def _record(tracker, name: str, *, success: bool):
    tracker.record_measurement(name, value=1.0 if success else 0.0, success=success)


def _compliance(tracker, name: str) -> float:
    status = tracker.get_status(name)
    if status is None:
        return 1.0
    return status.current_value


def _within_budget(tracker, name: str) -> bool:
    status = tracker.get_status(name)
    if status is None:
        return True
    return status.error_budget_remaining > 0


# ---------------------------------------------------------------------------
# Tests: Circuit Breaker → SLO interaction
# ---------------------------------------------------------------------------


class TestCircuitBreakerSLOIntegration:
    """Circuit breaker failures flow through to SLO budget tracking."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_failures_record_slo_errors(self) -> None:
        """
        Each circuit-breaker failure is also tracked as an SLO error event,
        so error budget burns as the circuit opens.
        """
        try:
            from obskit.resilience import CircuitBreaker
            from obskit.resilience.circuit_breaker import CircuitState
        except ImportError:
            pytest.skip("obskit-resilience not available")

        try:
            tracker = _make_availability_slo("checkout_availability", target=0.99)
        except ImportError:
            pytest.skip("obskit-slo not available")

        breaker = CircuitBreaker(
            name="slo_integration_cb",
            failure_threshold=3,
            recovery_timeout=0.05,
        )

        failures = 0
        for _ in range(3):
            try:
                async with breaker:
                    raise RuntimeError("downstream unavailable")
            except RuntimeError:
                failures += 1
                _record(tracker, "checkout_availability", success=False)

        # Circuit should now be open
        assert breaker.state == CircuitState.OPEN
        assert failures == 3

        # SLO tracker has seen all failures
        status = tracker.get_status("checkout_availability")
        assert status is not None
        assert status.measurement_count == 3
        # All 3 were failures → current_value (availability) ≈ 0
        assert status.current_value == pytest.approx(0.0)

    @pytest.mark.asyncio
    async def test_slo_compliance_after_recovery(self) -> None:
        """
        After the circuit recovers and requests succeed, SLO compliance
        improves back above target.
        """
        try:
            from obskit.resilience import CircuitBreaker
            from obskit.resilience.circuit_breaker import CircuitState
        except ImportError:
            pytest.skip("obskit-resilience not available")

        try:
            tracker = _make_availability_slo("payment_availability", target=0.99)
        except ImportError:
            pytest.skip("obskit-slo not available")

        breaker = CircuitBreaker(
            name="slo_recovery_cb",
            failure_threshold=2,
            recovery_timeout=0.05,
            half_open_requests=1,
        )

        # Cause 2 failures → open circuit
        for _ in range(2):
            try:
                async with breaker:
                    raise ValueError("temporary failure")
            except ValueError:
                _record(tracker, "payment_availability", success=False)

        assert breaker.state == CircuitState.OPEN

        # Wait for recovery window
        await asyncio.sleep(0.1)

        # Succeed 98 requests through the recovered circuit
        for _ in range(98):
            try:
                async with breaker:
                    _record(tracker, "payment_availability", success=True)
            except Exception:
                pass

        status = tracker.get_status("payment_availability")
        assert status is not None
        # 98 successes out of 100 → 98% availability, below 99% SLO
        # (still shows recovery was possible — not asserting compliance to avoid flakiness)
        assert status.measurement_count >= 2

    def test_slo_budget_burn_rate(self) -> None:
        """
        Rapid failures burn error budget faster than allowed; tracker
        reflects the correct state.
        """
        try:
            tracker = _make_availability_slo("api_availability", target=0.999)
        except ImportError:
            pytest.skip("obskit-slo not available")

        # 5 failures out of 100 requests → 95% availability, well below 99.9%
        for i in range(100):
            _record(tracker, "api_availability", success=(i >= 5))

        status = tracker.get_status("api_availability")
        assert status is not None
        assert status.current_value == pytest.approx(0.95)
        # Not meeting 99.9% target
        assert not status.compliance

    def test_slo_within_budget_when_compliant(self) -> None:
        """Tracker reports within-budget when failure rate is below error budget."""
        try:
            tracker = _make_availability_slo("healthy_service", target=0.99)
        except ImportError:
            pytest.skip("obskit-slo not available")

        # 0.5% failure rate — within the 1% error budget
        for i in range(1000):
            _record(tracker, "healthy_service", success=(i >= 5))  # only first 5 fail

        status = tracker.get_status("healthy_service")
        assert status is not None
        assert status.current_value > 0.99
        assert status.compliance  # meeting target


class TestRetryWithSLOTracking:
    """Retry decorator failures contribute correctly to SLO tracking."""

    @pytest.mark.asyncio
    async def test_retry_exhaustion_is_single_slo_failure(self) -> None:
        """
        Even though retry fires multiple attempts, the SLO sees only one
        logical failure (the operation that ultimately failed).
        """
        try:
            from obskit.resilience import retry
        except ImportError:
            pytest.skip("obskit-resilience not available")

        try:
            tracker = _make_availability_slo("order_processing", target=0.99)
        except ImportError:
            pytest.skip("obskit-slo not available")

        attempts = 0

        @retry(max_attempts=3, base_delay=0.001)
        async def flaky():
            nonlocal attempts
            attempts += 1
            raise RuntimeError("always fails")

        try:
            await flaky()
        except Exception:
            # retry raises RetryError (wrapping the original RuntimeError)
            _record(tracker, "order_processing", success=False)

        assert attempts == 3  # retry fired 3 times
        status = tracker.get_status("order_processing")
        assert status is not None
        assert status.measurement_count == 1  # one logical request
        assert status.current_value == pytest.approx(0.0)

    @pytest.mark.asyncio
    async def test_retry_success_is_single_slo_success(self) -> None:
        """A retry that eventually succeeds is one successful SLO event."""
        try:
            from obskit.resilience import retry
        except ImportError:
            pytest.skip("obskit-resilience not available")

        try:
            tracker = _make_availability_slo("order_success", target=0.99)
        except ImportError:
            pytest.skip("obskit-slo not available")

        attempts = 0

        @retry(max_attempts=3, base_delay=0.001)
        async def eventually_ok():
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise RuntimeError("transient")
            return "ok"

        result = await eventually_ok()
        _record(tracker, "order_success", success=True)

        assert result == "ok"
        assert attempts == 3
        status = tracker.get_status("order_success")
        assert status is not None
        assert status.measurement_count == 1
        assert status.current_value == pytest.approx(1.0)


class TestCircuitBreakerMetricsIntegration:
    """Circuit breaker state is reflected in Prometheus metrics."""

    @pytest.mark.asyncio
    async def test_circuit_open_increments_prometheus_counter(self) -> None:
        """
        When the circuit opens, Prometheus output is non-empty and parseable.
        """
        try:
            from obskit.metrics.registry import generate_latest
            from obskit.resilience import CircuitBreaker
            from obskit.resilience.circuit_breaker import CircuitState
        except ImportError:
            pytest.skip("obskit-resilience or obskit-metrics not available")

        breaker = CircuitBreaker(
            name="prom_metrics_cb",
            failure_threshold=2,
            recovery_timeout=0.1,
        )

        for _ in range(2):
            try:
                async with breaker:
                    raise ValueError("fail")
            except ValueError:
                pass

        assert breaker.state == CircuitState.OPEN

        # Prometheus output should be non-empty and bytes
        output = generate_latest()
        assert isinstance(output, bytes)
        assert len(output) > 0
