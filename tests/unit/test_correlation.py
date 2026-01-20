"""Unit tests for correlation ID manager."""

import pytest

from obskit.correlation import (
    CorrelatedTask,
    CorrelationManager,
    create_correlated_task,
    generate_correlation_id,
    get_correlation_id,
    get_custom_context,
    get_full_context,
    get_request_id,
    get_session_id,
    get_tenant_id,
    get_user_id,
    set_correlation_id,
    set_custom_value,
    set_request_id,
    set_session_id,
    set_tenant_id,
    set_user_id,
    with_correlation,
)


class TestCorrelationIdFunctions:
    """Tests for basic correlation ID functions."""

    def test_generate_correlation_id(self):
        """Test generating correlation IDs."""
        id1 = generate_correlation_id()
        id2 = generate_correlation_id()

        # Should be unique
        assert id1 != id2
        # Should be valid UUID format
        assert len(id1) == 36
        assert "-" in id1

    def test_set_and_get_correlation_id(self):
        """Test setting and getting correlation ID."""
        set_correlation_id("test-correlation-123")
        assert get_correlation_id() == "test-correlation-123"

    def test_set_and_get_request_id(self):
        """Test setting and getting request ID."""
        set_request_id("req-456")
        assert get_request_id() == "req-456"

    def test_set_and_get_session_id(self):
        """Test setting and getting session ID."""
        set_session_id("sess-789")
        assert get_session_id() == "sess-789"

    def test_set_and_get_tenant_id(self):
        """Test setting and getting tenant ID."""
        set_tenant_id("tenant-abc")
        assert get_tenant_id() == "tenant-abc"

    def test_set_and_get_user_id(self):
        """Test setting and getting user ID."""
        set_user_id("user-xyz")
        assert get_user_id() == "user-xyz"

    def test_custom_context(self):
        """Test custom context values."""
        set_custom_value("order_id", "order-123")
        set_custom_value("amount", 99.99)

        ctx = get_custom_context()
        assert ctx["order_id"] == "order-123"
        assert ctx["amount"] == 99.99

    def test_get_full_context(self):
        """Test getting full context."""
        set_correlation_id("corr-1")
        set_tenant_id("tenant-1")
        set_custom_value("custom_key", "custom_value")

        ctx = get_full_context()

        assert ctx["correlation_id"] == "corr-1"
        assert ctx["tenant_id"] == "tenant-1"
        assert ctx["custom_key"] == "custom_value"

    def test_full_context_excludes_none(self):
        """Test full context excludes None values."""
        set_correlation_id("corr-1")
        # Don't set other values

        ctx = get_full_context()

        # Should have correlation_id but not session_id (which is None)
        assert "correlation_id" in ctx


class TestCorrelationManager:
    """Tests for CorrelationManager class."""

    def test_new_context_generates_id(self):
        """Test new_context generates correlation ID if not provided."""
        with CorrelationManager.new_context():
            cid = get_correlation_id()
            assert cid is not None

    def test_new_context_uses_provided_id(self):
        """Test new_context uses provided correlation ID."""
        with CorrelationManager.new_context(correlation_id="custom-123"):
            assert get_correlation_id() == "custom-123"

    def test_new_context_sets_all_ids(self):
        """Test new_context sets all provided IDs."""
        with CorrelationManager.new_context(
            correlation_id="corr-1",
            request_id="req-1",
            session_id="sess-1",
            tenant_id="tenant-1",
            user_id="user-1",
        ):
            assert get_correlation_id() == "corr-1"
            assert get_request_id() == "req-1"
            assert get_session_id() == "sess-1"
            assert get_tenant_id() == "tenant-1"
            assert get_user_id() == "user-1"

    def test_new_context_with_custom_values(self):
        """Test new_context with custom values."""
        with CorrelationManager.new_context(
            correlation_id="corr-1", order_id="order-123", amount=99.99
        ):
            ctx = get_full_context()
            assert ctx["correlation_id"] == "corr-1"
            assert ctx["order_id"] == "order-123"
            assert ctx["amount"] == 99.99

    def test_capture_and_restore(self):
        """Test capturing and restoring context."""
        with CorrelationManager.new_context(
            correlation_id="original-corr", tenant_id="original-tenant"
        ):
            captured = CorrelationManager.capture()

        # Outside context, values may be different

        # Restore captured context
        with CorrelationManager.restore(captured):
            assert get_correlation_id() == "original-corr"
            assert get_tenant_id() == "original-tenant"

    def test_propagate_to_headers(self):
        """Test propagating context to HTTP headers."""
        with CorrelationManager.new_context(
            correlation_id="corr-123", request_id="req-456", tenant_id="tenant-789"
        ):
            headers = CorrelationManager.propagate_to_headers()

            assert headers["X-Correlation-ID"] == "corr-123"
            assert headers["X-Request-ID"] == "req-456"
            assert headers["X-Tenant-ID"] == "tenant-789"

    def test_propagate_to_headers_preserves_existing(self):
        """Test propagating context preserves existing headers."""
        with CorrelationManager.new_context(correlation_id="corr-123"):
            headers = {"Authorization": "Bearer token123"}
            result = CorrelationManager.propagate_to_headers(headers)

            assert result["Authorization"] == "Bearer token123"
            assert result["X-Correlation-ID"] == "corr-123"

    def test_extract_from_headers(self):
        """Test extracting context from HTTP headers."""
        headers = {
            "X-Correlation-ID": "corr-abc",
            "X-Request-ID": "req-def",
            "X-Tenant-ID": "tenant-ghi",
        }

        ctx = CorrelationManager.extract_from_headers(headers)

        assert ctx["correlation_id"] == "corr-abc"
        assert ctx["request_id"] == "req-def"
        assert ctx["tenant_id"] == "tenant-ghi"

    def test_extract_from_headers_case_insensitive(self):
        """Test extracting context is case-insensitive."""
        headers = {"x-correlation-id": "corr-lower", "X-TENANT-ID": "tenant-upper"}

        ctx = CorrelationManager.extract_from_headers(headers)

        assert ctx.get("correlation_id") == "corr-lower"

    def test_propagate_to_message(self):
        """Test propagating context to message."""
        with CorrelationManager.new_context(correlation_id="corr-123"):
            message = {"body": "data"}
            result = CorrelationManager.propagate_to_message(message)

            assert "headers" in result
            assert result["headers"]["X-Correlation-ID"] == "corr-123"

    def test_extract_from_message(self):
        """Test extracting context from message."""
        message = {
            "body": "data",
            "headers": {"X-Correlation-ID": "corr-msg", "X-Tenant-ID": "tenant-msg"},
        }

        ctx = CorrelationManager.extract_from_message(message)

        assert ctx["correlation_id"] == "corr-msg"
        assert ctx["tenant_id"] == "tenant-msg"


class TestWithCorrelationDecorator:
    """Tests for with_correlation decorator."""

    def test_generates_correlation_id(self):
        """Test decorator generates correlation ID."""

        @with_correlation()
        def my_function():
            return get_correlation_id()

        result = my_function()
        assert result is not None

    def test_preserves_existing_correlation_id(self):
        """Test decorator preserves existing correlation ID."""
        with CorrelationManager.new_context(correlation_id="existing-corr"):

            @with_correlation(generate_if_missing=False)
            def my_function():
                return get_correlation_id()

            result = my_function()
            # Should use existing
            assert result == "existing-corr"

    @pytest.mark.asyncio
    async def test_async_function(self):
        """Test decorator works with async functions."""

        @with_correlation()
        async def async_function():
            return get_correlation_id()

        result = await async_function()
        assert result is not None


class TestCorrelatedTask:
    """Tests for CorrelatedTask class."""

    @pytest.mark.asyncio
    async def test_preserves_context(self):
        """Test CorrelatedTask preserves correlation context."""

        async def inner_task():
            return get_correlation_id()

        with CorrelationManager.new_context(correlation_id="task-corr"):
            task = CorrelatedTask(inner_task())
            result = await task

        assert result == "task-corr"


class TestCreateCorrelatedTask:
    """Tests for create_correlated_task function."""

    @pytest.mark.asyncio
    async def test_creates_task_with_context(self):
        """Test create_correlated_task creates task with preserved context."""
        results = []

        async def capture_correlation():
            results.append(get_correlation_id())

        with CorrelationManager.new_context(correlation_id="captured-corr"):
            task = create_correlated_task(capture_correlation())
            await task

        assert results[0] == "captured-corr"
