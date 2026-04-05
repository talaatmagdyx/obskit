"""
SLO-Based Health Checks
=======================

Integrate SLO compliance into health checks for Kubernetes readiness probes.

Example
-------
>>> from obskit.health.slo_check import (
...     add_slo_readiness_check,
...     SLOReadinessCheck,
...     get_slo_health_status,
... )
>>>
>>> # Add SLO-based readiness check
>>> add_slo_readiness_check(
...     slo_name="availability",
...     critical_threshold=0.1,  # Fail readiness if budget < 10%
...     warning_threshold=0.25,  # Warn if budget < 25%
... )
>>>
>>> # Or create custom check
>>> check = SLOReadinessCheck(
...     slo_name="latency_p99",
...     critical_threshold=0.05,
... )
>>> result = check.check()
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any

from obskit.health.checker import HealthChecker, get_health_checker
from obskit.logging import get_logger

if TYPE_CHECKING:
    from obskit.slo import SLOTracker

logger = get_logger("obskit.health.slo_check")


def get_slo_tracker() -> Any:
    """Lazy accessor for the global SLO tracker; raises ImportError if obskit[slo] not installed."""
    try:
        from obskit.slo import get_slo_tracker as _get  # noqa: PLC0415

        return _get()
    except ImportError as e:  # pragma: no cover
        raise ImportError(  # pragma: no cover
            "SLO health checks require obskit[slo]. "
            "Install: pip install obskit[slo]  or  obskit[slo-all]"
        ) from e


class SLOHealthStatus(Enum):
    """SLO health status levels."""

    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass
class SLOCheckResult:
    """Result of an SLO health check."""

    slo_name: str
    status: SLOHealthStatus
    healthy: bool
    error_budget_remaining: float
    current_value: float
    target_value: float
    message: str
    details: dict[str, Any] | None = None


class SLOReadinessCheck:
    """
    Health check based on SLO compliance.

    Fails readiness if error budget falls below critical threshold.

    Example
    -------
    >>> check = SLOReadinessCheck(
    ...     slo_name="availability",
    ...     critical_threshold=0.1,
    ...     warning_threshold=0.25,
    ... )
    >>> result = check.check()
    >>> if not result.healthy:
    ...     print(f"SLO failing: {result.message}")
    """

    def __init__(
        self,
        slo_name: str,
        critical_threshold: float = 0.1,
        warning_threshold: float = 0.25,
        slo_tracker: SLOTracker | None = None,
    ):
        """
        Initialize SLO readiness check.

        Parameters
        ----------
        slo_name : str
            Name of the SLO to check.
        critical_threshold : float
            Error budget threshold for critical/unhealthy (default: 0.1 = 10%).
        warning_threshold : float
            Error budget threshold for warning (default: 0.25 = 25%).
        slo_tracker : SLOTracker, optional
            SLO tracker instance (defaults to global).
        """
        self.slo_name = slo_name
        self.critical_threshold = critical_threshold
        self.warning_threshold = warning_threshold
        self._slo_tracker = slo_tracker

    @property
    def slo_tracker(self) -> SLOTracker | None:
        """Get SLO tracker lazily."""
        if self._slo_tracker is None:
            self._slo_tracker = get_slo_tracker()
        return self._slo_tracker

    def check(self) -> SLOCheckResult:
        """
        Perform the SLO health check.

        Returns
        -------
        SLOCheckResult
            Check result with status and details.
        """
        if not self.slo_tracker:
            return SLOCheckResult(
                slo_name=self.slo_name,
                status=SLOHealthStatus.UNKNOWN,
                healthy=True,  # Don't fail if tracker not available
                error_budget_remaining=1.0,
                current_value=0.0,
                target_value=0.0,
                message="SLO tracker not available",
            )

        try:
            status = self.slo_tracker.get_status(self.slo_name)

            if status is None:
                return SLOCheckResult(
                    slo_name=self.slo_name,
                    status=SLOHealthStatus.UNKNOWN,
                    healthy=True,  # Don't fail for unregistered SLO
                    error_budget_remaining=1.0,
                    current_value=0.0,
                    target_value=0.0,
                    message=f"SLO '{self.slo_name}' not registered",
                )

            budget = status.error_budget_remaining
            current = status.current_value
            target = status.target.target_value

            # Determine health status
            if budget < self.critical_threshold:
                return SLOCheckResult(
                    slo_name=self.slo_name,
                    status=SLOHealthStatus.CRITICAL,
                    healthy=False,
                    error_budget_remaining=budget,
                    current_value=current,
                    target_value=target,
                    message=f"Error budget critically low: {budget:.1%} (threshold: {self.critical_threshold:.0%})",
                    details={
                        "burn_rate": status.error_budget_burn_rate,
                        "critical_threshold": self.critical_threshold,
                        "warning_threshold": self.warning_threshold,
                    },
                )

            if budget < self.warning_threshold:
                return SLOCheckResult(
                    slo_name=self.slo_name,
                    status=SLOHealthStatus.WARNING,
                    healthy=True,  # Still healthy, just warning
                    error_budget_remaining=budget,
                    current_value=current,
                    target_value=target,
                    message=f"Error budget low: {budget:.1%} (warning: {self.warning_threshold:.0%})",
                    details={
                        "burn_rate": status.error_budget_burn_rate,
                    },
                )

            return SLOCheckResult(
                slo_name=self.slo_name,
                status=SLOHealthStatus.HEALTHY,
                healthy=True,
                error_budget_remaining=budget,
                current_value=current,
                target_value=target,
                message=f"SLO healthy: {budget:.1%} error budget remaining",
            )

        except Exception as e:
            logger.error("slo_check_failed", slo_name=self.slo_name, error=str(e))
            return SLOCheckResult(
                slo_name=self.slo_name,
                status=SLOHealthStatus.UNKNOWN,
                healthy=True,  # Don't fail on check errors
                error_budget_remaining=1.0,
                current_value=0.0,
                target_value=0.0,
                message=f"SLO check error: {str(e)}",
            )


# Registry of checks already registered with the global health checker.
# Guards add_slo_readiness_check() against repeated registration when called
# on every request (e.g. inside a /_ready handler).
_REGISTERED_SLO_CHECKS: dict[str, SLOReadinessCheck] = {}


def add_slo_readiness_check(
    slo_name: str,
    critical_threshold: float = 0.1,
    warning_threshold: float = 0.25,
    health_checker: HealthChecker | None = None,
) -> SLOReadinessCheck:
    """
    Register an SLO-based readiness check with the global health checker.

    **Idempotent** — calling this function multiple times with the same
    *slo_name* (e.g. on every ``/_ready`` request) registers the handler only
    once and returns the existing :class:`SLOReadinessCheck` on subsequent
    calls.  It is therefore safe to call per-request, but the recommended
    pattern is to call it once at startup (in the app lifespan) and use
    :func:`get_slo_readiness_check` for per-request budget checks.

    Parameters
    ----------
    slo_name : str
        Name of the SLO to check.
    critical_threshold : float
        Error budget threshold for failing readiness (default: 0.1).
    warning_threshold : float
        Error budget threshold for warning (default: 0.25).
    health_checker : HealthChecker, optional
        Health checker to add check to (defaults to global).

    Returns
    -------
    SLOReadinessCheck
        The check instance (existing one if already registered).

    Example — startup registration (recommended)
    --------------------------------------------
    >>> # In your app lifespan:
    >>> add_slo_readiness_check("availability", critical_threshold=0.1)
    >>> add_slo_readiness_check("latency_p95", critical_threshold=0.1)

    Example — per-request (also safe due to idempotency)
    -----------------------------------------------------
    >>> check = add_slo_readiness_check("availability", critical_threshold=0.1)
    >>> result = check.check()
    """
    if slo_name in _REGISTERED_SLO_CHECKS:
        return _REGISTERED_SLO_CHECKS[slo_name]

    checker = health_checker or get_health_checker()
    slo_check = SLOReadinessCheck(
        slo_name=slo_name,
        critical_threshold=critical_threshold,
        warning_threshold=warning_threshold,
    )

    # Create async check function
    async def check_slo() -> dict[str, Any] | bool:  # NOSONAR
        result = slo_check.check()
        if not result.healthy:
            return {
                "healthy": False,
                "message": result.message,
                "details": {
                    "error_budget_remaining": result.error_budget_remaining,
                    "current_value": result.current_value,
                    "target_value": result.target_value,
                },
            }
        return True

    # Register with health checker
    checker.add_readiness_check(f"slo_{slo_name}")(check_slo)

    _REGISTERED_SLO_CHECKS[slo_name] = slo_check

    logger.info(
        "slo_readiness_check_added",
        slo_name=slo_name,
        critical_threshold=critical_threshold,
        warning_threshold=warning_threshold,
    )

    return slo_check


def get_slo_readiness_check(
    slo_name: str,
    critical_threshold: float = 0.1,
    warning_threshold: float = 0.25,
) -> SLOReadinessCheck:
    """
    Return a lightweight SLO readiness check — safe to call per-request.

    Unlike :func:`add_slo_readiness_check`, this function does **not** register
    anything with the global health checker.  It creates a plain
    :class:`SLOReadinessCheck` that you can call ``.check()`` on directly.

    Use this inside per-request handlers (e.g. ``/_ready``) once the SLO has
    already been registered at startup with :func:`add_slo_readiness_check`.

    Parameters
    ----------
    slo_name : str
        Name of the SLO to check.
    critical_threshold : float
        Error budget threshold below which the check is unhealthy (default: 0.1).
    warning_threshold : float
        Error budget threshold below which the check is in warning (default: 0.25).

    Returns
    -------
    SLOReadinessCheck
        A check object whose ``.check()`` method can be called immediately.

    Example
    -------
    >>> # In a /_ready handler (called on every request):
    >>> check = get_slo_readiness_check("api_availability", critical_threshold=0.1)
    >>> if not check.check().healthy:
    ...     return JSONResponse({"ready": False}, status_code=503)
    """
    return SLOReadinessCheck(
        slo_name=slo_name,
        critical_threshold=critical_threshold,
        warning_threshold=warning_threshold,
    )


def get_slo_health_status(
    slo_names: list[str] | None = None,
    critical_threshold: float = 0.1,
    warning_threshold: float = 0.25,
) -> dict[str, Any]:
    """
    Get health status for multiple SLOs.

    Parameters
    ----------
    slo_names : list of str, optional
        SLO names to check (defaults to all registered).
    critical_threshold : float
        Threshold for critical status.
    warning_threshold : float
        Threshold for warning status.

    Returns
    -------
    dict
        Health status summary.

    Example
    -------
    >>> status = get_slo_health_status(["availability", "latency_p99"])
    >>> print(f"Overall healthy: {status['healthy']}")
    """
    tracker = get_slo_tracker()

    if not tracker:
        return {
            "healthy": True,
            "status": "unknown",
            "message": "SLO tracker not available",
            "slos": {},
        }

    # Get all SLO names if not specified
    if slo_names is None:
        try:
            slo_names = list(tracker._slos.keys()) if hasattr(tracker, "_slos") else []
        except Exception:
            slo_names = []

    results = {}
    overall_healthy = True
    overall_status = SLOHealthStatus.HEALTHY

    for name in slo_names:
        check = SLOReadinessCheck(
            slo_name=name,
            critical_threshold=critical_threshold,
            warning_threshold=warning_threshold,
            slo_tracker=tracker,
        )
        result = check.check()

        results[name] = {
            "status": result.status.value,
            "healthy": result.healthy,
            "error_budget_remaining": round(result.error_budget_remaining, 4),
            "current_value": round(result.current_value, 4),
            "target_value": round(result.target_value, 4),
            "message": result.message,
        }

        if not result.healthy:
            overall_healthy = False

        if result.status == SLOHealthStatus.CRITICAL:
            overall_status = SLOHealthStatus.CRITICAL
        elif result.status == SLOHealthStatus.WARNING and overall_status == SLOHealthStatus.HEALTHY:
            overall_status = SLOHealthStatus.WARNING

    return {
        "healthy": overall_healthy,
        "status": overall_status.value,
        "slos_checked": len(results),
        "slos": results,
    }


__all__ = [
    "SLOHealthStatus",
    "SLOCheckResult",
    "SLOReadinessCheck",
    "add_slo_readiness_check",
    "get_slo_readiness_check",
    "get_slo_health_status",
]
