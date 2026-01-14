"""SLO tracker implementation."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from obskit.logging import get_logger
from obskit.slo.types import SLOMeasurement, SLOStatus, SLOTarget, SLOType

logger = get_logger(__name__)


class SLOTracker:
    """Tracks SLO compliance and error budgets.

    Example:
        >>> tracker = SLOTracker()
        >>> tracker.register_slo(
        ...     name="api_availability",
        ...     slo_type=SLOType.AVAILABILITY,
        ...     target_value=0.999,
        ... )
        >>> tracker.record_measurement("api_availability", 1.0, success=True)
        >>> status = tracker.get_status("api_availability")
    """

    def __init__(self) -> None:
        """Initialize SLO tracker."""
        self._targets: dict[str, SLOTarget] = {}
        self._measurements: dict[str, list[SLOMeasurement]] = {}

    def register_slo(
        self,
        name: str,
        slo_type: SLOType,
        target_value: float,
        window_seconds: int = 86400,
        percentile: int | None = None,
    ) -> None:
        """Register an SLO target.

        Args:
            name: Unique name for this SLO.
            slo_type: Type of SLO.
            target_value: Target value (e.g., 0.999 for 99.9%).
            window_seconds: Time window for calculation.
            percentile: For latency SLOs, the percentile.
        """
        target = SLOTarget(
            slo_type=slo_type,
            target_value=target_value,
            window_seconds=window_seconds,
            percentile=percentile,
        )
        self._targets[name] = target
        self._measurements[name] = []

        logger.info(
            "slo_registered",
            slo_name=name,
            slo_type=slo_type.value,
            target_value=target_value,
            window_seconds=window_seconds,
        )

    def record_measurement(
        self,
        name: str,
        value: float,
        success: bool = True,
    ) -> None:
        """Record an SLO measurement.

        Args:
            name: SLO name.
            value: Measurement value.
            success: Whether the operation was successful.
        """
        if name not in self._targets:
            logger.warning("slo_not_registered", slo_name=name)
            return

        measurement = SLOMeasurement(
            timestamp=datetime.now(),
            value=value,
            success=success,
        )
        self._measurements[name].append(measurement)

        # Clean old measurements
        target = self._targets[name]
        cutoff = datetime.now() - timedelta(seconds=target.window_seconds)
        self._measurements[name] = [m for m in self._measurements[name] if m.timestamp >= cutoff]

    def get_status(self, name: str) -> SLOStatus | None:
        """Get current SLO status.

        Args:
            name: SLO name.

        Returns:
            SLOStatus or None if not registered.
        """
        if name not in self._targets:
            return None

        target = self._targets[name]
        measurements = self._measurements.get(name, [])

        window_end = datetime.now()
        window_start = window_end - timedelta(seconds=target.window_seconds)

        if not measurements:
            return SLOStatus(
                slo_type=target.slo_type,
                target=target,
                current_value=1.0 if target.slo_type == SLOType.AVAILABILITY else 0.0,
                compliance=True,
                error_budget_remaining=1.0,
                error_budget_burn_rate=0.0,
                window_start=window_start,
                window_end=window_end,
                measurement_count=0,
            )

        # Calculate current value
        current_value = self._calculate_value(target, measurements)

        # Check compliance
        compliance = self._check_compliance(target, current_value)

        # Calculate error budget
        budget_remaining, burn_rate = self._calculate_error_budget(target, current_value)

        return SLOStatus(
            slo_type=target.slo_type,
            target=target,
            current_value=current_value,
            compliance=compliance,
            error_budget_remaining=budget_remaining,
            error_budget_burn_rate=burn_rate,
            window_start=window_start,
            window_end=window_end,
            measurement_count=len(measurements),
        )

    def _calculate_value(
        self,
        target: SLOTarget,
        measurements: list[SLOMeasurement],
    ) -> float:
        """Calculate current SLO value."""
        if not measurements:  # pragma: no cover
            return 0.0

        if target.slo_type == SLOType.AVAILABILITY:
            success_count = sum(1 for m in measurements if m.success)
            return success_count / len(measurements)

        elif target.slo_type == SLOType.ERROR_RATE:
            error_count = sum(1 for m in measurements if not m.success)
            return error_count / len(measurements)

        elif target.slo_type == SLOType.LATENCY:
            values = sorted([m.value for m in measurements])
            if target.percentile:
                index = int(len(values) * target.percentile / 100)
                return values[min(index, len(values) - 1)]
            return sum(values) / len(values)  # pragma: no cover

        else:  # THROUGHPUT
            if len(measurements) < 2:
                return 0.0
            time_span = (measurements[-1].timestamp - measurements[0].timestamp).total_seconds()
            return len(measurements) / time_span if time_span > 0 else 0.0

    def _check_compliance(self, target: SLOTarget, current_value: float) -> bool:
        """Check if current value meets SLO target."""
        if target.slo_type == SLOType.ERROR_RATE or target.slo_type == SLOType.LATENCY:
            return current_value <= target.target_value
        else:
            return current_value >= target.target_value

    def _calculate_error_budget(
        self,
        target: SLOTarget,
        current_value: float,
    ) -> tuple[float, float]:
        """Calculate error budget remaining and burn rate."""
        if target.slo_type == SLOType.AVAILABILITY:
            error_budget = 1.0 - target.target_value
            error_budget_used = 1.0 - current_value
            remaining = max(0.0, error_budget - error_budget_used)
            burn_rate = error_budget_used / error_budget if error_budget > 0 else 0.0
            return remaining, burn_rate

        elif target.slo_type == SLOType.ERROR_RATE:
            error_budget = target.target_value
            error_budget_used = current_value
            remaining = max(0.0, error_budget - error_budget_used)
            burn_rate = error_budget_used / error_budget if error_budget > 0 else 0.0
            return remaining, burn_rate

        # For latency and throughput, error budget is less meaningful
        return 1.0, 0.0

    def get_all_status(self) -> dict[str, SLOStatus]:
        """Get status for all registered SLOs.

        Returns:
            Dictionary mapping SLO names to their status.
        """
        return {
            name: status for name in self._targets if (status := self.get_status(name)) is not None
        }

    def to_dict(self) -> dict[str, Any]:
        """Export all SLO status as dictionary."""
        return {name: status.to_dict() for name, status in self.get_all_status().items()}


# Global SLO tracker
_slo_tracker: SLOTracker | None = None


def get_slo_tracker() -> SLOTracker:
    """Get global SLO tracker instance."""
    global _slo_tracker
    if _slo_tracker is None:
        _slo_tracker = SLOTracker()
    return _slo_tracker


def track_slo(
    name: str,
    value: float = 1.0,
    success: bool = True,
) -> None:
    """Track SLO measurement using global tracker.

    Args:
        name: SLO name.
        value: Measurement value.
        success: Whether operation was successful.
    """
    tracker = get_slo_tracker()
    tracker.record_measurement(name, value, success)


def reset_slo_tracker() -> None:
    """Reset global SLO tracker (for testing)."""
    global _slo_tracker
    _slo_tracker = None
