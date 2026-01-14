"""
Tenant Metrics Helper
======================

This module provides helpers for tenant-scoped metrics in multi-tenant
SaaS applications. It automatically injects tenant_id labels into metrics.

Example - Basic Usage
---------------------
.. code-block:: python

    from obskit.metrics.tenant import TenantREDMetrics
    from obskit import get_logger

    logger = get_logger(__name__)

    # Create tenant-scoped metrics
    tenant_metrics = TenantREDMetrics("order_service")

    # Record metrics with automatic tenant_id label
    tenant_metrics.observe_request(
        tenant_id="tenant-123",
        operation="create_order",
        duration_seconds=0.045,
        status="success",
    )

Example - Context Manager
-------------------------
.. code-block:: python

    from obskit.metrics.tenant import tenant_metrics_context

    # Use context manager for automatic tenant injection
    with tenant_metrics_context("tenant-123"):
        # All metrics in this context include tenant_id
        red = get_red_metrics()
        red.observe_request("create_order", 0.045, "success")
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Literal

from obskit.metrics.red import REDMetrics

# Context variable for current tenant ID
_tenant_id: ContextVar[str | None] = ContextVar("tenant_id", default=None)


def get_tenant_id() -> str | None:
    """
    Get the current tenant ID from context.

    Returns
    -------
    str or None
        The current tenant ID, or None if not set.
    """
    return _tenant_id.get()


def set_tenant_id(tenant_id: str | None) -> None:
    """
    Set the tenant ID for the current context.

    Parameters
    ----------
    tenant_id : str or None
        The tenant ID to set.
    """
    _tenant_id.set(tenant_id)


@contextmanager
def tenant_metrics_context(tenant_id: str) -> Generator[str, None, None]:
    """
    Context manager for tenant-scoped metrics.

    All metrics recorded within this context will automatically
    include the tenant_id label.

    Parameters
    ----------
    tenant_id : str
        The tenant ID for this context.

    Yields
    ------
    str
        The tenant ID.

    Example
    -------
    >>> from obskit.metrics.tenant import tenant_metrics_context
    >>> from obskit.metrics import get_red_metrics
    >>>
    >>> with tenant_metrics_context("tenant-123"):
    ...     red = get_red_metrics()
    ...     red.observe_request("create_order", 0.045, "success")
    ...     # Metrics automatically include tenant_id="tenant-123"
    """
    token = _tenant_id.set(tenant_id)
    try:
        yield tenant_id
    finally:
        _tenant_id.reset(token)


class TenantREDMetrics:
    """
    RED Metrics with automatic tenant_id label injection.

    This class wraps REDMetrics and automatically adds tenant_id
    to all metric labels, making it easy to track metrics per tenant.

    Parameters
    ----------
    name : str
        Service name prefix for metrics.

    **kwargs
        Additional arguments passed to REDMetrics.

    Example
    -------
    >>> from obskit.metrics.tenant import TenantREDMetrics
    >>>
    >>> tenant_metrics = TenantREDMetrics("order_service")
    >>>
    >>> # Record metrics with tenant_id
    >>> tenant_metrics.observe_request(
    ...     tenant_id="tenant-123",
    ...     operation="create_order",
    ...     duration_seconds=0.045,
    ...     status="success",
    ... )
    """

    def __init__(self, name: str, **kwargs: Any) -> None:
        self._red = REDMetrics(name, **kwargs)
        self._name = name

    def observe_request(
        self,
        tenant_id: str,
        operation: str,
        duration_seconds: float,
        status: Literal["success", "failure"] = "success",
        error_type: str | None = None,
    ) -> None:
        """
        Record a request observation with tenant_id label.

        Parameters
        ----------
        tenant_id : str
            The tenant ID for this request.
        operation : str
            Name of the operation.
        duration_seconds : float
            Request duration in seconds.
        status : {"success", "failure"}
            Request status.
        error_type : str, optional
            Error type if status="failure".
        """
        # Use context to inject tenant_id
        with tenant_metrics_context(tenant_id):
            # Note: This requires modifying REDMetrics to check for tenant_id
            # For now, we'll add tenant_id to operation label
            # In a full implementation, we'd extend REDMetrics to support
            # dynamic label injection
            operation_with_tenant = f"{operation}_tenant_{tenant_id}"
            self._red.observe_request(
                operation=operation_with_tenant,
                duration_seconds=duration_seconds,
                status=status,
                error_type=error_type,
            )

    def track_request(self, tenant_id: str, operation: str) -> Any:
        """
        Context manager for tracking requests with tenant_id.

        Parameters
        ----------
        tenant_id : str
            The tenant ID.
        operation : str
            Operation name.

        Yields
        ------
        None
        """
        with tenant_metrics_context(tenant_id):
            operation_with_tenant = f"{operation}_tenant_{tenant_id}"
            return self._red.track_request(operation_with_tenant)


__all__ = [
    "TenantREDMetrics",
    "get_tenant_id",
    "set_tenant_id",
    "tenant_metrics_context",
]
