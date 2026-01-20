"""
Latency Breakdown
=================

Track where time is spent within an operation.

Features:
- Phase-by-phase timing
- Percentage breakdown
- Waterfall visualization data
- Bottleneck detection

Example:
    from obskit.breakdown import LatencyBreakdown

    with LatencyBreakdown("widget_processing") as breakdown:
        with breakdown.phase("query_build"):
            build_query()
        with breakdown.phase("db_execute"):
            execute_query()
        with breakdown.phase("transform"):
            transform_data()

    print(breakdown.get_summary())
"""

import threading
import time
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from prometheus_client import Gauge, Histogram

from obskit.logging import get_logger

logger = get_logger(__name__)


# =============================================================================
# Prometheus Metrics
# =============================================================================

BREAKDOWN_PHASE_DURATION = Histogram(
    "latency_breakdown_phase_seconds",
    "Duration of each phase",
    ["operation", "phase"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)

BREAKDOWN_TOTAL_DURATION = Histogram(
    "latency_breakdown_total_seconds",
    "Total operation duration",
    ["operation"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60),
)

BREAKDOWN_PHASE_PERCENT = Gauge(
    "latency_breakdown_phase_percent", "Percentage of time spent in phase", ["operation", "phase"]
)


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class PhaseRecord:
    """Record of a single phase."""

    name: str
    start_time: float
    end_time: float | None = None
    duration_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "duration_seconds": self.duration_seconds,
            "duration_ms": self.duration_seconds * 1000,
        }


@dataclass
class BreakdownSummary:
    """Summary of latency breakdown."""

    operation: str
    total_duration_seconds: float
    phases: list[PhaseRecord]
    phase_percentages: dict[str, float]
    bottleneck: str | None = None
    bottleneck_percent: float = 0.0
    unaccounted_seconds: float = 0.0
    unaccounted_percent: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "operation": self.operation,
            "total_duration_seconds": self.total_duration_seconds,
            "total_duration_ms": self.total_duration_seconds * 1000,
            "phases": [p.to_dict() for p in self.phases],
            "phase_percentages": self.phase_percentages,
            "bottleneck": self.bottleneck,
            "bottleneck_percent": self.bottleneck_percent,
            "unaccounted_seconds": self.unaccounted_seconds,
            "unaccounted_percent": self.unaccounted_percent,
            "timestamp": self.timestamp.isoformat(),
        }


# =============================================================================
# Latency Breakdown
# =============================================================================


class LatencyBreakdown:
    """
    Track latency breakdown across phases.

    Parameters
    ----------
    operation : str
        Name of the operation being tracked
    log_breakdown : bool
        Whether to log the breakdown on completion
    alert_bottleneck_percent : float
        Alert if any phase exceeds this percentage
    """

    def __init__(
        self,
        operation: str,
        log_breakdown: bool = True,
        alert_bottleneck_percent: float = 80.0,
    ):
        self.operation = operation
        self.log_breakdown = log_breakdown
        self.alert_bottleneck_percent = alert_bottleneck_percent

        self._phases: list[PhaseRecord] = []
        self._start_time: float | None = None
        self._end_time: float | None = None
        self._current_phase: PhaseRecord | None = None
        self._lock = threading.Lock()

    def __enter__(self) -> "LatencyBreakdown":
        """Start tracking."""
        self._start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Finish tracking and record metrics."""
        self._end_time = time.perf_counter()

        # Close any open phase
        if self._current_phase and self._current_phase.end_time is None:
            self._current_phase.end_time = self._end_time
            self._current_phase.duration_seconds = (
                self._current_phase.end_time - self._current_phase.start_time
            )

        total_duration = self._end_time - self._start_time

        # Record total duration
        BREAKDOWN_TOTAL_DURATION.labels(operation=self.operation).observe(total_duration)

        # Record phase metrics
        for phase in self._phases:
            BREAKDOWN_PHASE_DURATION.labels(operation=self.operation, phase=phase.name).observe(
                phase.duration_seconds
            )

            if total_duration > 0:
                percent = (phase.duration_seconds / total_duration) * 100
                BREAKDOWN_PHASE_PERCENT.labels(operation=self.operation, phase=phase.name).set(
                    percent
                )

        # Log breakdown
        if self.log_breakdown:
            summary = self.get_summary()

            log_data = {
                "operation": self.operation,
                "total_ms": total_duration * 1000,
                "phases": {p.name: p.duration_seconds * 1000 for p in self._phases},
                "bottleneck": summary.bottleneck,
                "bottleneck_percent": summary.bottleneck_percent,
            }

            if summary.bottleneck_percent >= self.alert_bottleneck_percent:
                logger.warning("latency_breakdown_bottleneck", **log_data)
            else:
                logger.debug("latency_breakdown", **log_data)

        return False

    @contextmanager
    def phase(self, name: str) -> Generator[None, None, None]:
        """
        Track a phase within the operation.

        Parameters
        ----------
        name : str
            Name of the phase
        """
        # Close previous phase if any
        with self._lock:
            if self._current_phase and self._current_phase.end_time is None:
                self._current_phase.end_time = time.perf_counter()
                self._current_phase.duration_seconds = (
                    self._current_phase.end_time - self._current_phase.start_time
                )

            # Start new phase
            phase_record = PhaseRecord(
                name=name,
                start_time=time.perf_counter(),
            )
            self._phases.append(phase_record)
            self._current_phase = phase_record

        try:
            yield
        finally:
            with self._lock:
                phase_record.end_time = time.perf_counter()
                phase_record.duration_seconds = phase_record.end_time - phase_record.start_time

    def record_phase(self, name: str, duration_seconds: float):
        """
        Manually record a phase duration.

        Parameters
        ----------
        name : str
            Phase name
        duration_seconds : float
            Duration in seconds
        """
        with self._lock:
            phase_record = PhaseRecord(
                name=name,
                start_time=0,
                end_time=duration_seconds,
                duration_seconds=duration_seconds,
            )
            self._phases.append(phase_record)

    def get_summary(self) -> BreakdownSummary:
        """
        Get breakdown summary.

        Returns
        -------
        BreakdownSummary
            Summary of the breakdown
        """
        with self._lock:
            if self._start_time is None:
                return BreakdownSummary(
                    operation=self.operation,
                    total_duration_seconds=0,
                    phases=[],
                    phase_percentages={},
                )

            end_time = self._end_time or time.perf_counter()
            total_duration = end_time - self._start_time

            # Calculate percentages
            phase_percentages = {}
            bottleneck = None
            bottleneck_percent = 0.0
            accounted_time = 0.0

            for phase in self._phases:
                accounted_time += phase.duration_seconds

                if total_duration > 0:
                    percent = (phase.duration_seconds / total_duration) * 100
                    phase_percentages[phase.name] = percent

                    if percent > bottleneck_percent:
                        bottleneck = phase.name
                        bottleneck_percent = percent

            unaccounted = max(0, total_duration - accounted_time)
            unaccounted_percent = (unaccounted / total_duration * 100) if total_duration > 0 else 0

            return BreakdownSummary(
                operation=self.operation,
                total_duration_seconds=total_duration,
                phases=list(self._phases),
                phase_percentages=phase_percentages,
                bottleneck=bottleneck,
                bottleneck_percent=bottleneck_percent,
                unaccounted_seconds=unaccounted,
                unaccounted_percent=unaccounted_percent,
            )

    def get_waterfall_data(self) -> list[dict[str, Any]]:
        """
        Get data for waterfall visualization.

        Returns
        -------
        list
            List of phase data for visualization
        """
        if self._start_time is None:
            return []

        waterfall = []
        for phase in self._phases:
            waterfall.append(
                {
                    "name": phase.name,
                    "start_offset_ms": (phase.start_time - self._start_time) * 1000,
                    "duration_ms": phase.duration_seconds * 1000,
                    "end_offset_ms": (phase.start_time - self._start_time + phase.duration_seconds)
                    * 1000,
                }
            )

        return waterfall


# =============================================================================
# Factory Function
# =============================================================================


def track_breakdown(operation: str, **kwargs) -> LatencyBreakdown:
    """
    Create a new latency breakdown tracker.

    Parameters
    ----------
    operation : str
        Operation name
    **kwargs
        Additional LatencyBreakdown options

    Returns
    -------
    LatencyBreakdown
        New breakdown tracker
    """
    return LatencyBreakdown(operation, **kwargs)
