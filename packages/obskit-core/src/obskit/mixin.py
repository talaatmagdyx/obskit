"""
Observability Mixin Base Class
==============================

A reusable mixin class that provides comprehensive observability features
for any service class. Inherit from this mixin to get automatic:

- Structured logging with trace correlation
- RED metrics (Rate, Errors, Duration)
- Distributed tracing with spans
- SLO tracking
- Circuit breakers for dependencies
- Rate limiters for resource protection
- Health check integration

Example
-------
>>> from obskit.mixin import ObservabilityMixin
>>>
>>> class OrderService(ObservabilityMixin):
...     def __init__(self):
...         super().__init__(service_name="order_service")
...
...     def process_order(self, order_data):
...         with self.track_operation("process_order", params=order_data):
...             # Your business logic here
...             result = self._validate_and_save(order_data)
...             return result
...
...     def call_payment_api(self, payment_data):
...         # Use circuit breaker for external calls
...         with self.get_circuit_breaker("payment_api"):
...             return payment_api.charge(payment_data)
"""

from __future__ import annotations

import threading
import time
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from obskit.health import HealthChecker, get_health_checker
from obskit.logging import get_logger, log_error
from obskit.metrics import GoldenSignals, REDMetrics, USEMetrics
from obskit.metrics.tenant import TenantREDMetrics, set_tenant_id
from obskit.resilience import CircuitBreaker, RateLimiter, TokenBucketRateLimiter
from obskit.slo import SLOTracker, get_slo_tracker
from obskit.tracing import trace_span

# Module-level registries for circuit breakers and rate limiters
_circuit_breakers: dict[str, CircuitBreaker] = {}
_circuit_breaker_lock = threading.Lock()
_rate_limiters: dict[str, RateLimiter] = {}
_rate_limiter_lock = threading.Lock()


class ObservabilityMixin:
    """
    Base mixin class providing comprehensive observability features.

    Features:
    - Automatic logging with trace correlation
    - RED metrics (Rate, Errors, Duration)
    - Golden Signals (Latency, Traffic, Errors, Saturation)
    - USE metrics for resources
    - Tenant-aware metrics for multi-tenant apps
    - Distributed tracing with OpenTelemetry
    - SLO tracking with error budgets
    - Circuit breakers for external dependencies
    - Rate limiters for resource protection

    Usage:
        class MyService(ObservabilityMixin):
            def __init__(self):
                super().__init__(service_name="my_service")

            def process(self, data):
                with self.track_operation("process", params=data):
                    return self._do_work(data)
    """

    _logger = None
    _metrics: REDMetrics | None = None
    _golden_signals: GoldenSignals | None = None
    _use_metrics: USEMetrics | None = None
    _tenant_metrics: TenantREDMetrics | None = None
    _slo_tracker: SLOTracker | None = None
    _health_checker: HealthChecker | None = None
    _service_name: str = "service"
    _initialized: bool = False

    def __init__(self, service_name: str = "service", **kwargs):
        """
        Initialize the observability mixin.

        Parameters
        ----------
        service_name : str
            Name of the service for metrics and logging.
        **kwargs
            Additional arguments passed to parent class.
        """
        super().__init__(**kwargs)
        self._service_name = service_name
        self._initialize_observability()

    def _initialize_observability(self):
        """Initialize all observability components."""
        if self._initialized:
            return

        self._logger = get_logger(self.__class__.__module__)
        self._metrics = REDMetrics(name=self._service_name)
        self._golden_signals = GoldenSignals(name=self._service_name)
        self._use_metrics = USEMetrics(name=f"{self._service_name}_resources")
        self._tenant_metrics = TenantREDMetrics(name=f"{self._service_name}_tenant")
        self._slo_tracker = get_slo_tracker()
        self._health_checker = get_health_checker()
        self._initialized = True

    # =========================================================================
    # Properties - Access to Observability Components
    # =========================================================================

    @property
    def logger(self):
        """Get the logger for this component."""
        if self._logger is None:
            self._logger = get_logger(self.__class__.__module__)
        return self._logger

    @property
    def metrics(self) -> REDMetrics:
        """Get RED metrics instance."""
        if self._metrics is None:
            self._metrics = REDMetrics(name=self._service_name)
        return self._metrics

    @property
    def golden_signals(self) -> GoldenSignals:
        """Get Golden Signals metrics instance."""
        if self._golden_signals is None:
            self._golden_signals = GoldenSignals(name=self._service_name)
        return self._golden_signals

    @property
    def use_metrics(self) -> USEMetrics:
        """Get USE metrics instance."""
        if self._use_metrics is None:
            self._use_metrics = USEMetrics(name=f"{self._service_name}_resources")
        return self._use_metrics

    @property
    def tenant_metrics(self) -> TenantREDMetrics:
        """Get tenant-aware metrics instance."""
        if self._tenant_metrics is None:
            self._tenant_metrics = TenantREDMetrics(name=f"{self._service_name}_tenant")
        return self._tenant_metrics

    @property
    def slo_tracker(self) -> SLOTracker:
        """Get SLO tracker instance."""
        if self._slo_tracker is None:
            self._slo_tracker = get_slo_tracker()
        return self._slo_tracker

    @property
    def health_checker(self) -> HealthChecker:
        """Get health checker instance."""
        if self._health_checker is None:
            self._health_checker = get_health_checker()
        return self._health_checker

    # =========================================================================
    # Operation Tracking
    # =========================================================================

    @contextmanager
    def track_operation(
        self,
        operation_name: str,
        params: dict[str, Any] | None = None,
        component: str | None = None,
        tenant_id: str | None = None,
        slo_name: str | None = None,
        slow_threshold_ms: float = 5000.0,
        enable_tracing: bool = True,
        enable_metrics: bool = True,
        enable_slo: bool = True,
        enable_slow_alert: bool = False,
    ) -> Generator[None, None, None]:
        """
        Track an operation with full observability.

        This context manager provides:
        - Distributed tracing with span
        - RED metrics recording
        - SLO measurement
        - Slow operation detection
        - Tenant-aware metrics

        Parameters
        ----------
        operation_name : str
            Name of the operation being tracked.
        params : dict, optional
            Operation parameters (for extracting tenant_id, etc.).
        component : str, optional
            Component name (defaults to service_name).
        tenant_id : str, optional
            Tenant ID for multi-tenant metrics.
        slo_name : str, optional
            SLO name for latency tracking.
        slow_threshold_ms : float, optional
            Threshold for slow operation detection (default: 5000ms).
        enable_tracing : bool, optional
            Whether to create tracing span (default: True).
        enable_metrics : bool, optional
            Whether to record metrics (default: True).
        enable_slo : bool, optional
            Whether to record SLO measurement (default: True).
        enable_slow_alert : bool, optional
            Whether to log slow operation warnings (default: False).

        Example
        -------
        >>> with self.track_operation("process_order", params={"order_id": 123}):
        ...     result = self.process(order_data)
        """
        start_time = time.perf_counter()
        comp = component or self._service_name
        class_name = self.__class__.__name__
        full_operation = f"{class_name}.{operation_name}"

        # Extract tenant_id from params if not provided
        if tenant_id is None and params:
            tenant_id = (
                params.get("tenant_id") or params.get("company_id") or params.get("company_schema")
            )

        # Set tenant context
        if tenant_id:
            set_tenant_id(str(tenant_id))

        # Build span attributes
        attributes = {
            "operation": operation_name,
            "component": comp,
            "class": class_name,
        }
        if tenant_id:
            attributes["tenant.id"] = str(tenant_id)
        if params:
            # Add safe params (avoid PII)
            for key in ["page_name", "routing_key", "data_source", "operation_type"]:
                if key in params:
                    attributes[key] = str(params[key])

        # Create tracing span
        span_context = None
        if enable_tracing:
            try:
                span_context = trace_span(
                    name=f"{comp}.{operation_name}",
                    component=comp,
                    operation=operation_name,
                    attributes=attributes,
                )
            except Exception:
                pass  # Tracing unavailable - continue without span

        try:
            # Enter span
            if span_context:
                span_context.__enter__()

            self.logger.debug(
                "operation_started",
                operation=operation_name,
                component=comp,
                tenant_id=tenant_id,
            )

            yield

            # Success path
            duration = time.perf_counter() - start_time
            duration_ms = duration * 1000

            # Record metrics
            if enable_metrics:
                self.metrics.observe_request(
                    operation=full_operation,
                    duration_seconds=duration,
                    status="success",
                )
                if tenant_id:
                    self.tenant_metrics.observe_request(
                        operation=full_operation,
                        duration_seconds=duration,
                        status="success",
                    )

            # Record SLO
            if enable_slo and slo_name and self.slo_tracker:
                try:
                    self.slo_tracker.record_measurement(slo_name, value=duration, success=True)
                except Exception:
                    pass  # SLO tracking failure should not affect business logic

            # Check slow operation
            if enable_slow_alert and duration_ms > slow_threshold_ms:
                self.logger.warning(
                    "slow_operation_detected",
                    operation=operation_name,
                    component=comp,
                    duration_ms=round(duration_ms, 2),
                    threshold_ms=slow_threshold_ms,
                    tenant_id=tenant_id,
                )
            else:
                self.logger.debug(
                    "operation_completed",
                    operation=operation_name,
                    component=comp,
                    duration_ms=round(duration_ms, 2),
                    tenant_id=tenant_id,
                )

        except Exception as e:
            duration = time.perf_counter() - start_time

            # Record error metrics
            if enable_metrics:
                self.metrics.observe_request(
                    operation=full_operation,
                    duration_seconds=duration,
                    status="failure",
                    error_type=type(e).__name__,
                )

            # Record SLO failure
            if enable_slo and slo_name and self.slo_tracker:
                try:
                    self.slo_tracker.record_measurement(slo_name, value=duration, success=False)
                except Exception:
                    pass  # SLO tracking failure should not affect error propagation

            log_error(
                error=e,
                component=comp,
                operation=operation_name,
                context={"tenant_id": tenant_id, "duration_ms": round(duration * 1000, 2)},
            )
            raise

        finally:
            # Exit span
            if span_context:
                try:
                    span_context.__exit__(None, None, None)
                except Exception:
                    pass  # Span cleanup failure should not affect application

    # =========================================================================
    # Resilience - Circuit Breakers
    # =========================================================================

    def get_circuit_breaker(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_requests: int = 1,
    ) -> CircuitBreaker:
        """
        Get or create a circuit breaker for a dependency.

        Parameters
        ----------
        name : str
            Name of the dependency.
        failure_threshold : int
            Failures before opening (default: 5).
        recovery_timeout : float
            Seconds before trying recovery (default: 30).
        half_open_requests : int
            Requests allowed in half-open state (default: 1).

        Returns
        -------
        CircuitBreaker
            Circuit breaker instance.

        Example
        -------
        >>> with self.get_circuit_breaker("payment_api"):
        ...     result = payment_api.charge(amount)
        """
        full_name = f"{self._service_name}.{name}"

        if full_name not in _circuit_breakers:
            with _circuit_breaker_lock:
                if full_name not in _circuit_breakers:
                    _circuit_breakers[full_name] = CircuitBreaker(
                        name=full_name,
                        failure_threshold=failure_threshold,
                        recovery_timeout=recovery_timeout,
                        half_open_requests=half_open_requests,
                    )
                    self.logger.info(
                        "circuit_breaker_created",
                        name=full_name,
                        failure_threshold=failure_threshold,
                        recovery_timeout=recovery_timeout,
                    )
        return _circuit_breakers[full_name]

    # =========================================================================
    # Resilience - Rate Limiters
    # =========================================================================

    def get_rate_limiter(
        self,
        name: str,
        requests_per_minute: int = 100,
    ) -> RateLimiter:
        """
        Get or create a rate limiter.

        Parameters
        ----------
        name : str
            Name of the rate limiter.
        requests_per_minute : int
            Maximum requests per minute (default: 100).

        Returns
        -------
        RateLimiter
            Rate limiter instance.

        Example
        -------
        >>> limiter = self.get_rate_limiter("api_calls", 1000)
        >>> if limiter.acquire():
        ...     make_api_call()
        """
        full_name = f"{self._service_name}.{name}"

        if full_name not in _rate_limiters:
            with _rate_limiter_lock:
                if full_name not in _rate_limiters:
                    _rate_limiters[full_name] = TokenBucketRateLimiter(
                        bucket_size=requests_per_minute,
                        refill_rate=requests_per_minute / 60.0,
                    )
                    self.logger.info(
                        "rate_limiter_created",
                        name=full_name,
                        requests_per_minute=requests_per_minute,
                    )
        return _rate_limiters[full_name]

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def set_saturation(self, resource: str, value: float):
        """Set resource saturation level (0.0 to 1.0)."""
        self.use_metrics.set_saturation(resource, value)
        self.golden_signals.set_saturation(resource, value)

    def set_queue_depth(self, queue_name: str, depth: int):
        """Set queue depth for saturation monitoring."""
        self.golden_signals.set_queue_depth(queue_name, depth)

    def get_slo_status(self, slo_name: str) -> dict[str, Any] | None:
        """Get status of a specific SLO."""
        if not self.slo_tracker:
            return None
        try:
            status = self.slo_tracker.get_status(slo_name)
            if status:
                return {
                    "current_value": status.current_value,
                    "target_value": status.target.target_value,
                    "error_budget_remaining": status.error_budget_remaining,
                    "burn_rate": status.error_budget_burn_rate,
                }
        except Exception:
            pass  # SLO status check failure - return None as fallback
        return None


# Convenience function to create mixin instances
def create_service_mixin(service_name: str) -> ObservabilityMixin:
    """
    Create a standalone observability mixin instance.

    Use this when you can't inherit from ObservabilityMixin.

    Example
    -------
    >>> obs = create_service_mixin("my_service")
    >>> with obs.track_operation("process"):
    ...     do_work()
    """

    class StandaloneMixin(ObservabilityMixin):
        pass

    return StandaloneMixin(service_name=service_name)


__all__ = ["ObservabilityMixin", "create_service_mixin"]
