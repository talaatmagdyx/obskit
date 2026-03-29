"""Tests for obskit.tracing.tracer module."""

import pytest

from obskit.tracing.tracer import (
    OPENTELEMETRY_AVAILABLE,
    configure_tracing,
    extract_trace_context,
    get_tracer,
    inject_trace_context,
    is_tracing_available,
    reset_tracing,
    shutdown_tracing,
    trace_context,
    trace_operation,
    trace_span,
)


class TestConfigureTracing:
    """Tests for configure_tracing function."""

    def setup_method(self):
        """Reset tracing before each test."""
        reset_tracing()

    def teardown_method(self):
        """Reset tracing after each test."""
        reset_tracing()

    def test_configure_basic(self):
        """Test basic tracing configuration."""
        result = configure_tracing(service_name="test-service")
        assert result is True

    def test_configure_with_endpoint(self):
        """Test configuration with OTLP endpoint."""
        result = configure_tracing(
            service_name="test-service",
            otlp_endpoint="http://localhost:4317",
        )
        assert result is True

    def test_configure_uses_settings(self):
        """Test configure uses settings when params not provided."""
        result = configure_tracing()
        assert result is True

    def test_configure_is_idempotent(self):
        """Test configure can be called multiple times."""
        configure_tracing(service_name="test1")
        configure_tracing(service_name="test2")
        # Should not raise


class TestGetTracer:
    """Tests for get_tracer function."""

    def setup_method(self):
        """Reset tracing before each test."""
        reset_tracing()
        # Pre-configure to avoid slow auto-configuration
        configure_tracing(service_name="test-tracer")

    def teardown_method(self):
        """Reset tracing after each test."""
        reset_tracing()

    def test_get_tracer_returns_tracer(self):
        """Test getting tracer returns a tracer instance."""
        tracer = get_tracer()
        # Should return a tracer (not None since opentelemetry is available)
        if OPENTELEMETRY_AVAILABLE:
            assert tracer is not None

    def test_get_tracer_is_consistent(self):
        """Test getting tracer returns consistent instance."""
        tracer1 = get_tracer()
        tracer2 = get_tracer()
        # Should return same instance
        assert tracer1 is tracer2

    def test_get_tracer_auto_configures(self):
        """Test get_tracer auto-configures if not configured."""
        reset_tracing()
        tracer = get_tracer()
        # Should have configured automatically
        if OPENTELEMETRY_AVAILABLE:
            assert tracer is not None


class TestResetTracing:
    """Tests for reset_tracing function."""

    def test_reset_clears_state(self):
        """Test that reset clears tracing state."""
        configure_tracing(service_name="test")
        reset_tracing()
        # State should be cleared

    def test_reset_is_safe_when_not_configured(self):
        """Test reset is safe when not configured."""
        reset_tracing()
        reset_tracing()  # Second call should be safe


class TestShutdownTracing:
    """Tests for shutdown_tracing function."""

    def setup_method(self):
        """Reset tracing before each test."""
        reset_tracing()

    def teardown_method(self):
        """Reset tracing after each test."""
        reset_tracing()

    def test_shutdown_succeeds(self):
        """Test that shutdown doesn't raise."""
        configure_tracing(service_name="test")
        shutdown_tracing()  # Should not raise

    def test_shutdown_safe_when_not_configured(self):
        """Test shutdown is safe when not configured."""
        reset_tracing()
        shutdown_tracing()  # Should not raise

    def test_shutdown_multiple_times(self):
        """Test shutdown can be called multiple times."""
        configure_tracing(service_name="test")
        shutdown_tracing()
        shutdown_tracing()  # Should not raise


class TestTraceSpan:
    """Tests for trace_span context manager."""

    def setup_method(self):
        """Reset tracing before each test."""
        reset_tracing()
        configure_tracing(service_name="test-span")

    def teardown_method(self):
        """Reset tracing after each test."""
        reset_tracing()

    def test_trace_span_basic(self):
        """Test trace_span with basic name."""
        with trace_span("test_operation"):
            pass  # Code runs in span

    def test_trace_span_with_attributes(self):
        """Test trace_span with attributes."""
        with trace_span(
            "test_operation",
            attributes={"key1": "value1", "key2": 123},
        ):
            pass  # NOSONAR

    def test_trace_span_with_component(self):
        """Test trace_span with component."""
        with trace_span(
            "test_operation",
            component="TestService",
        ):
            pass  # NOSONAR

    def test_trace_span_with_operation(self):
        """Test trace_span with operation."""
        with trace_span(
            "test_operation",
            operation="create",
        ):
            pass  # NOSONAR

    def test_trace_span_yields_span(self):
        """Test trace_span yields span object."""
        with trace_span("test_operation") as span:
            # Span should be available
            if OPENTELEMETRY_AVAILABLE:
                assert span is not None

    def test_trace_span_handles_exception(self):
        """Test trace_span handles exceptions."""
        with pytest.raises(ValueError):
            with trace_span("test_operation"):
                raise ValueError("Test error")


class TestTraceOperation:
    """Tests for trace_operation decorator."""

    def setup_method(self):
        """Reset tracing before each test."""
        reset_tracing()
        configure_tracing(service_name="test-decorator")

    def teardown_method(self):
        """Reset tracing after each test."""
        reset_tracing()

    def test_trace_operation_decorator(self):
        """Test trace_operation decorator."""

        @trace_operation()
        def my_function():
            return "result"

        result = my_function()
        assert result == "result"

    def test_trace_operation_with_component(self):
        """Test trace_operation with component."""

        @trace_operation(component="TestComponent")
        def my_function():
            return "result"

        result = my_function()
        assert result == "result"

    def test_trace_operation_with_operation_name(self):
        """Test trace_operation with operation name."""

        @trace_operation(operation="custom_op")
        def my_function():
            return "result"

        result = my_function()
        assert result == "result"

    def test_trace_operation_preserves_name(self):
        """Test that decorator preserves function name."""

        @trace_operation()
        def named_function():
            pass  # NOSONAR

        assert named_function.__name__ == "named_function"

    def test_trace_operation_with_args(self):
        """Test trace_operation with function arguments."""

        @trace_operation()
        def add(a, b):
            return a + b

        result = add(2, 3)
        assert result == 5

    def test_trace_operation_with_kwargs(self):
        """Test trace_operation with function kwargs."""

        @trace_operation()
        def greet(name, greeting="Hello"):
            return f"{greeting}, {name}"

        result = greet("World", greeting="Hi")
        assert result == "Hi, World"


class TestInjectExtractContext:
    """Tests for inject/extract trace context."""

    def setup_method(self):
        """Reset tracing before each test."""
        reset_tracing()
        configure_tracing(service_name="test-context")

    def teardown_method(self):
        """Reset tracing after each test."""
        reset_tracing()

    def test_inject_trace_context(self):
        """Test injecting trace context into headers."""
        headers = {}
        result = inject_trace_context(headers)
        assert result is headers

    def test_inject_trace_context_creates_headers(self):
        """Test inject creates headers if None."""
        result = inject_trace_context(None)
        assert isinstance(result, dict)

    def test_extract_trace_context(self):
        """Test extracting trace context from headers."""
        headers = {}
        extract_trace_context(headers)
        # Should return a context (possibly empty)

    def test_extract_trace_context_none_headers(self):
        """Test extract with None headers."""
        ctx = extract_trace_context(None)
        assert ctx is None

    def test_inject_then_extract(self):
        """Test round-trip of inject/extract."""
        headers = {}
        inject_trace_context(headers)
        extract_trace_context(headers)
        # Context should be extractable


class TestTraceContext:
    """Tests for trace_context context manager."""

    def setup_method(self):
        """Reset tracing before each test."""
        reset_tracing()
        configure_tracing(service_name="test-trace-context")

    def teardown_method(self):
        """Reset tracing after each test."""
        reset_tracing()

    def test_trace_context_basic(self):
        """Test trace_context context manager."""
        headers = {}
        with trace_context(headers):
            pass  # NOSONAR

    def test_trace_context_none_headers(self):
        """Test trace_context with None headers."""
        with trace_context(None) as ctx:
            assert ctx is None

    def test_trace_context_with_injected_headers(self):
        """Test trace_context with previously injected headers."""
        headers = {}
        inject_trace_context(headers)

        with trace_context(headers):
            # Should have context
            pass  # NOSONAR


class TestIsTracingAvailable:
    """Tests for is_tracing_available function."""

    def test_returns_boolean(self):
        """Test that is_tracing_available returns boolean."""
        result = is_tracing_available()
        assert isinstance(result, bool)

    def test_returns_true_when_available(self):
        """Test returns True when OpenTelemetry is available."""
        result = is_tracing_available()
        # Since we have opentelemetry installed, should be True
        assert result == OPENTELEMETRY_AVAILABLE


class TestGetTracerInnerBranch:
    """Tests covering the double-checked locking inner branch in get_tracer."""

    def setup_method(self):
        """Reset tracing before each test."""
        reset_tracing()

    def teardown_method(self):
        """Reset tracing after each test."""
        reset_tracing()

    def test_get_tracer_inner_lock_branch_already_set(self):
        """Test that get_tracer returns existing tracer when set inside lock.

        This covers the branch at line 152 where _tracer is None is False
        (the double-checked locking inner check). We simulate the race
        condition by replacing _tracer_lock so that acquiring it sets _tracer
        before the inner if-check runs.
        """
        from unittest.mock import MagicMock

        import obskit.tracing.tracer as tracer_module

        # Create a sentinel tracer to act as the already-set value
        fake_tracer = MagicMock()
        original_lock = tracer_module._tracer_lock

        class RaceConditionLock:
            """Simulates another thread setting _tracer while we wait for lock."""

            def __enter__(self):
                # Simulate another thread having set _tracer while we waited
                tracer_module._tracer = fake_tracer
                return self

            def __exit__(self, *args):
                return False

        # _tracer is None so the outer check at line 146 passes
        tracer_module._tracer = None
        # Replace lock with race-condition simulator
        tracer_module._tracer_lock = RaceConditionLock()
        try:
            result = get_tracer()
            # Should return the tracer that was set inside the lock
            assert result is fake_tracer
        finally:
            tracer_module._tracer_lock = original_lock
            reset_tracing()
