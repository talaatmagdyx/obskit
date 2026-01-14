"""SLO (Service Level Objective) tracking module.

Provides SLO tracking and error budget calculation for measuring
service reliability against targets.

Example:
    >>> from obskit.slo import SLOTracker, SLOType
    >>>
    >>> tracker = SLOTracker()
    >>> tracker.register_slo(
    ...     name="api_availability",
    ...     slo_type=SLOType.AVAILABILITY,
    ...     target_value=0.999,  # 99.9% availability
    ... )
    >>>
    >>> # Record measurements
    >>> tracker.record_measurement("api_availability", value=1.0, success=True)
    >>>
    >>> # Check status
    >>> status = tracker.get_status("api_availability")
    >>> print(f"Error budget remaining: {status.error_budget_remaining:.2%}")
"""

from obskit.slo.tracker import SLOTracker, get_slo_tracker, track_slo
from obskit.slo.types import SLOMeasurement, SLOStatus, SLOTarget, SLOType

__all__ = [
    "SLOTracker",
    "SLOType",
    "SLOTarget",
    "SLOMeasurement",
    "SLOStatus",
    "get_slo_tracker",
    "track_slo",
]
