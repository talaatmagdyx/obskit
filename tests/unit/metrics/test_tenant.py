"""Tests for obskit.metrics.tenant module."""

from unittest.mock import MagicMock, patch

import pytest


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
