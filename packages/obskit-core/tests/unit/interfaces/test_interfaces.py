"""Tests for obskit.interfaces module."""

from abc import ABC
from contextlib import contextmanager

from obskit.interfaces import (
    CircuitBreakerInterface,
    HealthCheckerInterface,
    LoggerInterface,
    MetricsInterface,
    TracerInterface,
)
from obskit.interfaces.circuit_breaker import CircuitState
from obskit.interfaces.health_checker import HealthResultInterface, HealthStatus
from obskit.interfaces.metrics import GoldenSignalsInterface, USEMetricsInterface
from obskit.interfaces.tracer import SpanInterface


class TestCircuitBreakerInterface:
    """Tests for CircuitBreakerInterface."""

    def test_circuit_state_enum(self):
        """Test CircuitState enum values."""
        assert CircuitState.CLOSED.value == "closed"
        assert CircuitState.OPEN.value == "open"
        assert CircuitState.HALF_OPEN.value == "half_open"

    def test_is_closed_property(self):
        """Test is_closed property."""

        class TestBreaker(CircuitBreakerInterface):
            def __init__(self, state):
                self._state = state

            @property
            def name(self):
                return "test"

            @property
            def state(self):
                return self._state

            @property
            def failure_count(self):
                return 0

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return False

            def reset(self):
                pass

            def get_stats(self):
                return {}

        breaker = TestBreaker(CircuitState.CLOSED)
        assert breaker.is_closed is True
        assert breaker.is_open is False
        assert breaker.is_half_open is False

    def test_is_open_property(self):
        """Test is_open property."""

        class TestBreaker(CircuitBreakerInterface):
            def __init__(self, state):
                self._state = state

            @property
            def name(self):
                return "test"

            @property
            def state(self):
                return self._state

            @property
            def failure_count(self):
                return 0

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return False

            def reset(self):
                pass

            def get_stats(self):
                return {}

        breaker = TestBreaker(CircuitState.OPEN)
        assert breaker.is_closed is False
        assert breaker.is_open is True
        assert breaker.is_half_open is False

    def test_is_half_open_property(self):
        """Test is_half_open property."""

        class TestBreaker(CircuitBreakerInterface):
            def __init__(self, state):
                self._state = state

            @property
            def name(self):
                return "test"

            @property
            def state(self):
                return self._state

            @property
            def failure_count(self):
                return 0

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return False

            def reset(self):
                pass

            def get_stats(self):
                return {}

        breaker = TestBreaker(CircuitState.HALF_OPEN)
        assert breaker.is_closed is False
        assert breaker.is_open is False
        assert breaker.is_half_open is True


class TestHealthCheckerInterface:
    """Tests for HealthCheckerInterface."""

    def test_health_status_enum(self):
        """Test HealthStatus enum values."""
        assert HealthStatus.HEALTHY.value == "healthy"
        assert HealthStatus.UNHEALTHY.value == "unhealthy"
        assert HealthStatus.DEGRADED.value == "degraded"

    def test_interface_is_abstract(self):
        """Test that HealthCheckerInterface is abstract."""
        assert issubclass(HealthCheckerInterface, ABC)

    def test_health_result_interface_is_abstract(self):
        """Test that HealthResultInterface is abstract."""
        assert issubclass(HealthResultInterface, ABC)


class TestLoggerInterface:
    """Tests for LoggerInterface."""

    def test_interface_is_abstract(self):
        """Test that LoggerInterface is abstract."""
        assert issubclass(LoggerInterface, ABC)

    def test_msg_alias(self):
        """Test msg() is an alias for info()."""

        class TestLogger(LoggerInterface):
            def __init__(self):
                self.calls = []

            def debug(self, event, **kwargs):
                self.calls.append(("debug", event, kwargs))

            def info(self, event, **kwargs):
                self.calls.append(("info", event, kwargs))

            def warning(self, event, **kwargs):
                self.calls.append(("warning", event, kwargs))

            def error(self, event, **kwargs):
                self.calls.append(("error", event, kwargs))

            def critical(self, event, **kwargs):
                self.calls.append(("critical", event, kwargs))

            def exception(self, event, **kwargs):
                self.calls.append(("exception", event, kwargs))

            def bind(self, **kwargs):
                return self

        logger = TestLogger()
        logger.msg("test_event", key="value")

        assert len(logger.calls) == 1
        assert logger.calls[0] == ("info", "test_event", {"key": "value"})

    def test_warn_alias(self):
        """Test warn() is an alias for warning()."""

        class TestLogger(LoggerInterface):
            def __init__(self):
                self.calls = []

            def debug(self, event, **kwargs):
                self.calls.append(("debug", event, kwargs))

            def info(self, event, **kwargs):
                self.calls.append(("info", event, kwargs))

            def warning(self, event, **kwargs):
                self.calls.append(("warning", event, kwargs))

            def error(self, event, **kwargs):
                self.calls.append(("error", event, kwargs))

            def critical(self, event, **kwargs):
                self.calls.append(("critical", event, kwargs))

            def exception(self, event, **kwargs):
                self.calls.append(("exception", event, kwargs))

            def bind(self, **kwargs):
                return self

        logger = TestLogger()
        logger.warn("test_warning", key="value")

        assert len(logger.calls) == 1
        assert logger.calls[0] == ("warning", "test_warning", {"key": "value"})


class TestMetricsInterface:
    """Tests for MetricsInterface."""

    def test_interface_is_abstract(self):
        """Test that MetricsInterface is abstract."""
        assert issubclass(MetricsInterface, ABC)

    def test_inc_request_method(self):
        """Test inc_request() default implementation."""

        class TestMetrics(MetricsInterface):
            def __init__(self):
                self.calls = []

            @property
            def name(self):
                return "test"

            def observe_request(
                self, operation, duration_seconds, status="success", error_type=None
            ):
                self.calls.append((operation, duration_seconds, status, error_type))

            @contextmanager
            def track_request(self, operation):
                yield

        metrics = TestMetrics()
        metrics.inc_request("test_op", "success")

        assert len(metrics.calls) == 1
        assert metrics.calls[0] == ("test_op", 0.0, "success", None)

    def test_golden_signals_interface_is_abstract(self):
        """Test that GoldenSignalsInterface is abstract."""
        assert issubclass(GoldenSignalsInterface, ABC)

    def test_use_metrics_interface_is_abstract(self):
        """Test that USEMetricsInterface is abstract."""
        assert issubclass(USEMetricsInterface, ABC)


class TestTracerInterface:
    """Tests for TracerInterface."""

    def test_interface_is_abstract(self):
        """Test that TracerInterface is abstract."""
        assert issubclass(TracerInterface, ABC)

    def test_span_interface_is_abstract(self):
        """Test that SpanInterface is abstract."""
        assert issubclass(SpanInterface, ABC)


class TestInterfacesModule:
    """Tests for interfaces module imports."""

    def test_all_exports(self):
        """Test __all__ exports."""
        from obskit import interfaces

        assert hasattr(interfaces, "CircuitBreakerInterface")
        assert hasattr(interfaces, "HealthCheckerInterface")
        assert hasattr(interfaces, "LoggerInterface")
        assert hasattr(interfaces, "MetricsInterface")
        assert hasattr(interfaces, "TracerInterface")
