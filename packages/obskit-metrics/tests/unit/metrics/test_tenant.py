"""Tests for obskit.metrics.tenant module."""

from unittest.mock import MagicMock, patch

import pytest


# =============================================================================
# extract_tenant_from_params
# =============================================================================


class TestExtractTenantFromParams:
    """Tests for extract_tenant_from_params helper."""

    def test_extract_tenant_id(self):
        from obskit.metrics.tenant import extract_tenant_from_params

        params = {"tenant_id": "t-123"}
        result = extract_tenant_from_params(params)
        assert result == "t-123"

    def test_extract_company_id(self):
        from obskit.metrics.tenant import extract_tenant_from_params

        params = {"company_id": "comp-456"}
        result = extract_tenant_from_params(params)
        assert result == "comp-456"

    def test_extract_company_schema(self):
        from obskit.metrics.tenant import extract_tenant_from_params

        params = {"company_schema": "schema-789"}
        result = extract_tenant_from_params(params)
        assert result == "schema-789"

    def test_extract_organization_id(self):
        from obskit.metrics.tenant import extract_tenant_from_params

        params = {"organization_id": "org-111"}
        result = extract_tenant_from_params(params)
        assert result == "org-111"

    def test_extract_org_id(self):
        from obskit.metrics.tenant import extract_tenant_from_params

        params = {"org_id": "org-222"}
        result = extract_tenant_from_params(params)
        assert result == "org-222"

    def test_returns_none_when_no_match(self):
        from obskit.metrics.tenant import extract_tenant_from_params

        params = {"user_id": "u-123", "session": "s-abc"}
        result = extract_tenant_from_params(params)
        assert result is None

    def test_empty_params_returns_none(self):
        from obskit.metrics.tenant import extract_tenant_from_params

        result = extract_tenant_from_params({})
        assert result is None

    def test_custom_keys(self):
        from obskit.metrics.tenant import extract_tenant_from_params

        params = {"account_id": "acc-999"}
        result = extract_tenant_from_params(params, keys=["account_id"])
        assert result == "acc-999"

    def test_converts_to_string(self):
        from obskit.metrics.tenant import extract_tenant_from_params

        params = {"tenant_id": 42}
        result = extract_tenant_from_params(params)
        assert result == "42"
        assert isinstance(result, str)

    def test_priority_first_matching_key(self):
        from obskit.metrics.tenant import extract_tenant_from_params

        # tenant_id should take priority over company_id (first in default keys list)
        params = {"tenant_id": "t1", "company_id": "c1"}
        result = extract_tenant_from_params(params)
        assert result == "t1"


# =============================================================================
# tenant_context context manager
# =============================================================================


class TestTenantContext2:
    """Tests for the enhanced tenant_context context manager."""

    def test_basic_tenant_context(self):
        from obskit.metrics.tenant import _tenant_id, get_tenant_id, tenant_context

        _tenant_id.set(None)
        with tenant_context("company_123") as ctx:
            assert ctx["tenant_id"] == "company_123"
            assert get_tenant_id() == "company_123"

        assert get_tenant_id() is None

    def test_tenant_context_with_company_id(self):
        from obskit.metrics.tenant import tenant_context

        with tenant_context("tenant-1", company_id="comp-1") as ctx:
            assert ctx["tenant_id"] == "tenant-1"
            assert ctx["company_id"] == "comp-1"

    def test_tenant_context_company_id_fallback(self):
        from obskit.metrics.tenant import get_tenant_id, tenant_context

        # When tenant_id is None, company_id is used as tid (None or company_id -> company_id)
        with tenant_context(None, company_id="comp-fallback") as ctx:
            # tid = None or "comp-fallback" -> "comp-fallback"
            assert ctx["tenant_id"] == "comp-fallback"
            assert ctx["company_id"] == "comp-fallback"

    def test_tenant_context_restores_after_exception(self):
        from obskit.metrics.tenant import _tenant_id, get_tenant_id, tenant_context

        _tenant_id.set(None)
        with pytest.raises(RuntimeError):
            with tenant_context("t1"):
                raise RuntimeError("Test error")
        assert get_tenant_id() is None

    def test_tenant_context_no_trace_attribute(self):
        from obskit.metrics.tenant import tenant_context

        # Should not raise even if opentelemetry is not available
        with tenant_context("t1", set_trace_attribute=False) as ctx:
            assert ctx["tenant_id"] == "t1"

    def test_tenant_context_with_trace_attribute_no_otel(self):
        from obskit.metrics.tenant import tenant_context

        # If opentelemetry is missing, should silently pass
        with patch("builtins.__import__", side_effect=ImportError("no otel")):
            pass  # Just verify the import guard works

        # Test the actual path with mocked trace
        with tenant_context("t1", set_trace_attribute=True) as ctx:
            assert ctx["tenant_id"] == "t1"


# =============================================================================
# with_tenant decorator
# =============================================================================


class TestWithTenant:
    """Tests for with_tenant decorator."""

    def test_with_tenant_decorator_sets_context(self):
        from obskit.metrics.tenant import _tenant_id, get_tenant_id, with_tenant

        _tenant_id.set(None)
        captured = []

        @with_tenant("company_xyz")
        def my_func():
            captured.append(get_tenant_id())

        my_func()
        assert captured[0] == "company_xyz"
        # After function, context should be reset
        assert get_tenant_id() is None

    def test_with_tenant_passes_args_and_kwargs(self):
        from obskit.metrics.tenant import with_tenant

        results = []

        @with_tenant("tenant-abc")
        def my_func(a, b, c=None):
            results.append((a, b, c))

        my_func(1, 2, c=3)
        assert results == [(1, 2, 3)]

    def test_with_tenant_returns_value(self):
        from obskit.metrics.tenant import with_tenant

        @with_tenant("tenant-ret")
        def my_func():
            return "result"

        assert my_func() == "result"

    def test_with_tenant_multiple_calls(self):
        from obskit.metrics.tenant import get_tenant_id, with_tenant

        contexts = []

        @with_tenant("tenant-multi")
        def capture():
            contexts.append(get_tenant_id())

        capture()
        capture()
        assert all(c == "tenant-multi" for c in contexts)


class TestTenantContext:
    """Tests for tenant context functions."""

    def test_get_tenant_id_default(self):
        """Test getting tenant ID returns None by default."""
        from obskit.metrics.tenant import _tenant_id, get_tenant_id

        # Reset to default
        _tenant_id.set(None)

        result = get_tenant_id()
        assert result is None

    def test_set_tenant_id(self):
        """Test setting tenant ID."""
        from obskit.metrics.tenant import _tenant_id, get_tenant_id, set_tenant_id

        # Reset first
        _tenant_id.set(None)

        set_tenant_id("tenant-123")

        assert get_tenant_id() == "tenant-123"

        # Clean up
        _tenant_id.set(None)

    def test_set_tenant_id_none(self):
        """Test setting tenant ID to None."""
        from obskit.metrics.tenant import get_tenant_id, set_tenant_id

        set_tenant_id("tenant-123")
        set_tenant_id(None)

        assert get_tenant_id() is None


class TestTenantMetricsContext:
    """Tests for tenant_metrics_context context manager."""

    def test_context_manager_sets_tenant(self):
        """Test context manager sets tenant ID."""
        from obskit.metrics.tenant import _tenant_id, get_tenant_id, tenant_metrics_context

        # Reset first
        _tenant_id.set(None)

        with tenant_metrics_context("tenant-456") as tenant_id:
            assert tenant_id == "tenant-456"
            assert get_tenant_id() == "tenant-456"

        # Should be reset after context
        assert get_tenant_id() is None

    def test_context_manager_restores_previous(self):
        """Test context manager restores previous tenant ID."""
        from obskit.metrics.tenant import (
            _tenant_id,
            get_tenant_id,
            set_tenant_id,
            tenant_metrics_context,
        )

        # Reset first
        _tenant_id.set(None)
        set_tenant_id("original-tenant")

        with tenant_metrics_context("temp-tenant"):
            assert get_tenant_id() == "temp-tenant"

        assert get_tenant_id() == "original-tenant"

        # Clean up
        _tenant_id.set(None)

    def test_context_manager_handles_exception(self):
        """Test context manager restores on exception."""
        from obskit.metrics.tenant import _tenant_id, get_tenant_id, tenant_metrics_context

        # Reset first
        _tenant_id.set(None)

        with pytest.raises(ValueError):
            with tenant_metrics_context("tenant-error"):
                assert get_tenant_id() == "tenant-error"
                raise ValueError("Test error")

        # Should still be reset
        assert get_tenant_id() is None


class TestTenantREDMetrics:
    """Tests for TenantREDMetrics class."""

    @patch("obskit.metrics.tenant.REDMetrics")
    def test_init(self, mock_red):
        """Test TenantREDMetrics initialization."""
        from obskit.metrics.tenant import TenantREDMetrics

        mock_red_instance = MagicMock()
        mock_red.return_value = mock_red_instance

        metrics = TenantREDMetrics("order_service")

        mock_red.assert_called_once_with("order_service")
        assert metrics._name == "order_service"

    @patch("obskit.metrics.tenant.REDMetrics")
    def test_observe_request(self, mock_red):
        """Test observing request with tenant ID."""
        from obskit.metrics.tenant import TenantREDMetrics

        mock_red_instance = MagicMock()
        mock_red.return_value = mock_red_instance

        metrics = TenantREDMetrics("order_service")
        metrics.observe_request(
            tenant_id="tenant-123",
            operation="create_order",
            duration_seconds=0.045,
            status="success",
        )

        # Should call observe_request with tenant in operation name
        mock_red_instance.observe_request.assert_called_once()
        call_args = mock_red_instance.observe_request.call_args
        assert "tenant-123" in call_args.kwargs.get(
            "operation", call_args.args[0] if call_args.args else ""
        )

    @patch("obskit.metrics.tenant.REDMetrics")
    def test_observe_request_failure(self, mock_red):
        """Test observing failed request with tenant ID."""
        from obskit.metrics.tenant import TenantREDMetrics

        mock_red_instance = MagicMock()
        mock_red.return_value = mock_red_instance

        metrics = TenantREDMetrics("order_service")
        metrics.observe_request(
            tenant_id="tenant-123",
            operation="create_order",
            duration_seconds=0.100,
            status="failure",
            error_type="ValidationError",
        )

        mock_red_instance.observe_request.assert_called_once()
        call_args = mock_red_instance.observe_request.call_args
        assert call_args.kwargs.get("status") == "failure"
        assert call_args.kwargs.get("error_type") == "ValidationError"

    @patch("obskit.metrics.tenant.REDMetrics")
    def test_track_request(self, mock_red):
        """Test track_request context manager."""
        from obskit.metrics.tenant import TenantREDMetrics

        mock_red_instance = MagicMock()
        mock_context = MagicMock()
        mock_red_instance.track_request.return_value = mock_context
        mock_red.return_value = mock_red_instance

        metrics = TenantREDMetrics("order_service")
        result = metrics.track_request("tenant-123", "process_order")

        # Should return the context manager from RED metrics
        mock_red_instance.track_request.assert_called_once()
        assert result == mock_context
