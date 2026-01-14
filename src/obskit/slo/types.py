"""SLO types and data classes."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class SLOType(Enum):
    """Types of Service Level Objectives."""

    AVAILABILITY = "availability"  # Percentage of successful requests
    LATENCY = "latency"  # Response time within threshold
    ERROR_RATE = "error_rate"  # Percentage of errors
    THROUGHPUT = "throughput"  # Requests per second


@dataclass
class SLOTarget:
    """SLO target definition.

    Attributes:
        slo_type: Type of SLO.
        target_value: Target value (e.g., 0.999 for 99.9%).
        window_seconds: Time window for calculation.
        percentile: For latency SLOs, the percentile (P50, P95, P99).
    """

    slo_type: SLOType
    target_value: float
    window_seconds: int = 86400  # 24 hours default
    percentile: int | None = None

    def __post_init__(self) -> None:
        """Validate SLO target."""
        if self.slo_type == SLOType.LATENCY and self.percentile is None:
            raise ValueError("Latency SLO requires percentile")

        if self.slo_type in (SLOType.AVAILABILITY, SLOType.ERROR_RATE):
            if not 0 <= self.target_value <= 1:
                raise ValueError("Availability/Error rate must be between 0 and 1")


@dataclass
class SLOMeasurement:
    """A single SLO measurement.

    Attributes:
        timestamp: When the measurement was taken.
        value: The measured value.
        success: Whether the operation was successful.
    """

    timestamp: datetime
    value: float
    success: bool


@dataclass
class SLOStatus:
    """Current SLO status.

    Attributes:
        slo_type: Type of SLO.
        target: The SLO target definition.
        current_value: Current measured value.
        compliance: Whether currently meeting SLO.
        error_budget_remaining: Remaining error budget (0-1).
        error_budget_burn_rate: Rate of error budget consumption.
        window_start: Start of measurement window.
        window_end: End of measurement window.
        measurement_count: Number of measurements in window.
    """

    slo_type: SLOType
    target: SLOTarget
    current_value: float
    compliance: bool
    error_budget_remaining: float
    error_budget_burn_rate: float
    window_start: datetime
    window_end: datetime
    measurement_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "slo_type": self.slo_type.value,
            "target_value": self.target.target_value,
            "current_value": round(self.current_value, 6),
            "compliance": self.compliance,
            "error_budget_remaining": round(self.error_budget_remaining, 4),
            "error_budget_burn_rate": round(self.error_budget_burn_rate, 4),
            "window_start": self.window_start.isoformat(),
            "window_end": self.window_end.isoformat(),
            "measurement_count": self.measurement_count,
        }


@dataclass
class ErrorBudget:
    """Error budget calculation result.

    Attributes:
        total_budget: Total error budget for the window.
        consumed: Amount of budget consumed.
        remaining: Amount of budget remaining.
        burn_rate: Current burn rate (consumed / elapsed time).
        time_remaining: Estimated time until budget exhausted.
    """

    total_budget: float
    consumed: float
    remaining: float = field(init=False)
    burn_rate: float = 0.0
    time_remaining_seconds: float | None = None

    def __post_init__(self) -> None:
        self.remaining = max(0, self.total_budget - self.consumed)

    @property
    def remaining_percentage(self) -> float:
        """Get remaining budget as percentage."""
        if self.total_budget == 0:
            return 0.0
        return (self.remaining / self.total_budget) * 100

    @property
    def is_exhausted(self) -> bool:
        """Check if error budget is exhausted."""
        return self.remaining <= 0
