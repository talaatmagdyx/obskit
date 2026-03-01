"""
SLO Prometheus Metrics Integration
====================================

This module provides Prometheus metrics for SLO tracking, enabling
SLO-based alerting in Prometheus.

Example - Basic Usage
---------------------
.. code-block:: python

    from obskit.slo import get_slo_tracker
    from obskit.slo.prometheus import expose_slo_metrics

    tracker = get_slo_tracker()
    tracker.register_slo(
        name="api_availability",
        slo_type=SLOType.AVAILABILITY,
        target_value=0.999,
    )

    # Expose SLO metrics to Prometheus
    expose_slo_metrics(tracker)

    # Now Prometheus can alert on SLO violations:
    # - slo_compliance{name="api_availability"} < 1
    # - slo_error_budget_remaining{name="api_availability"} < 0.1
"""

from __future__ import annotations

from obskit.logging import get_logger
from obskit.slo.tracker import SLOTracker

logger = get_logger("obskit.slo.prometheus")

try:
    from prometheus_client import Gauge

    PROMETHEUS_AVAILABLE = True
except ImportError:  # pragma: no cover
    PROMETHEUS_AVAILABLE = False
    Gauge = None  # type: ignore[assignment, misc]

# Global SLO metrics
_slo_metrics: dict[str, Gauge] | None = None


def expose_slo_metrics(tracker: SLOTracker) -> None:
    """
    Expose SLO metrics to Prometheus.

    Creates Prometheus metrics for:
    - SLO compliance (0 or 1)
    - Error budget remaining (0.0 to 1.0)
    - Error budget burn rate (0.0+)
    - Current SLO value

    Parameters
    ----------
    tracker : SLOTracker
        The SLO tracker instance to expose metrics for.

    Example
    -------
    >>> from obskit.slo import get_slo_tracker
    >>> from obskit.slo.prometheus import expose_slo_metrics
    >>>
    >>> tracker = get_slo_tracker()
    >>> expose_slo_metrics(tracker)
    >>>
    >>> # Metrics are now available in Prometheus:
    >>> # - slo_compliance{name="api_availability"} 1
    >>> # - slo_error_budget_remaining{name="api_availability"} 0.95
    >>> # - slo_error_budget_burn_rate{name="api_availability"} 0.05
    >>> # - slo_current_value{name="api_availability"} 0.9995
    """
    global _slo_metrics

    if not PROMETHEUS_AVAILABLE:  # pragma: no cover
        logger.warning(
            "prometheus_not_available",
            message="Cannot expose SLO metrics: prometheus_client not installed",
        )
        return

    if _slo_metrics is None:
        from obskit.metrics.registry import get_registry

        registry = get_registry()

        _slo_metrics = {
            "compliance": Gauge(
                name="slo_compliance",
                documentation="SLO compliance status (1=compliant, 0=violated)",
                labelnames=["name"],
                registry=registry,
            ),
            "error_budget_remaining": Gauge(
                name="slo_error_budget_remaining",
                documentation="Remaining error budget (0.0 to 1.0)",
                labelnames=["name"],
                registry=registry,
            ),
            "error_budget_burn_rate": Gauge(
                name="slo_error_budget_burn_rate",
                documentation="Error budget burn rate (0.0+)",
                labelnames=["name"],
                registry=registry,
            ),
            "current_value": Gauge(
                name="slo_current_value",
                documentation="Current SLO value",
                labelnames=["name"],
                registry=registry,
            ),
        }

    # Update metrics from tracker
    all_status = tracker.get_all_status()

    for name, status in all_status.items():
        _slo_metrics["compliance"].labels(name=name).set(1.0 if status.compliance else 0.0)
        _slo_metrics["error_budget_remaining"].labels(name=name).set(status.error_budget_remaining)
        _slo_metrics["error_budget_burn_rate"].labels(name=name).set(status.error_budget_burn_rate)
        _slo_metrics["current_value"].labels(name=name).set(status.current_value)


def update_slo_metrics(tracker: SLOTracker) -> None:
    """
    Update SLO metrics (call periodically).

    This function should be called periodically (e.g., every 30 seconds)
    to update SLO metrics in Prometheus.

    Parameters
    ----------
    tracker : SLOTracker
        The SLO tracker instance.

    Example
    -------
    >>> import asyncio
    >>> from obskit.slo import get_slo_tracker
    >>> from obskit.slo.prometheus import expose_slo_metrics, update_slo_metrics
    >>>
    >>> tracker = get_slo_tracker()
    >>> expose_slo_metrics(tracker)
    >>>
    >>> async def update_metrics_periodically():
    ...     while True:
    ...         update_slo_metrics(tracker)
    ...         await asyncio.sleep(30)
    """
    if _slo_metrics is None:
        expose_slo_metrics(tracker)
        return

    expose_slo_metrics(tracker)  # Re-expose to update values


__all__ = ["expose_slo_metrics", "update_slo_metrics"]
