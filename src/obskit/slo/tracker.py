"""SLO tracker implementation."""

from __future__ import annotations

import asyncio
import functools
import math
import threading
import time
from collections import deque
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any, ParamSpec, TypeVar, cast

from obskit.logging import get_logger
from obskit.slo.types import SLOMeasurement, SLOStatus, SLOTarget, SLOType

P = ParamSpec("P")
T = TypeVar("T")

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

    # Hard cap on measurements per SLO regardless of window size or RPS.
    # Prevents unbounded memory at pathological configurations (e.g. 24 h window
    # at 10 K RPS = 864 M items without this guard).  At this cap the oldest
    # measurements are automatically evicted by the deque, so accuracy degrades
    # gracefully rather than OOM-killing the process.
    _MAX_MEASUREMENTS: int = 1_000_000

    def __init__(self) -> None:
        """Initialize SLO tracker."""
        self._targets: dict[str, SLOTarget] = {}
        self._measurements: dict[str, deque[SLOMeasurement]] = {}
        # Incremental counters for O(1) AVAILABILITY and ERROR_RATE reads.
        # Updated under _lock on every record_measurement (append +1, eviction -1).
        self._success_counts: dict[str, int] = {}
        self._total_counts: dict[str, int] = {}
        # Protects all mutations to _targets and _measurements under concurrent access.
        self._lock = threading.Lock()

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
        with self._lock:
            self._targets[name] = target
            self._measurements[name] = deque(maxlen=self._MAX_MEASUREMENTS)
            self._success_counts[name] = 0
            self._total_counts[name] = 0

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
        with self._lock:
            if name not in self._targets:
                logger.warning("slo_not_registered", slo_name=name)
                return

            target = self._targets[name]
            _is_counter = target.slo_type in (SLOType.AVAILABILITY, SLOType.ERROR_RATE)

            measurement = SLOMeasurement(
                timestamp=datetime.now(UTC),
                value=value,
                success=success,
            )
            buf = self._measurements[name]

            # When the deque is at maxlen, appending implicitly evicts buf[0].
            # Decrement counters here to keep them consistent.
            if _is_counter and len(buf) == self._MAX_MEASUREMENTS:  # pragma: no cover
                _auto_evicted = buf[0]
                self._total_counts[name] -= 1
                if _auto_evicted.success:
                    self._success_counts[name] -= 1

            buf.append(measurement)

            if _is_counter:
                self._total_counts[name] += 1
                if success:
                    self._success_counts[name] += 1

            # Warn at 80 % capacity so operators can tune window_seconds or
            # reduce RPS before silent eviction degrades SLO accuracy.
            # Log every 10 000 measurements to avoid flooding.
            buf_len = len(buf)
            _warn_threshold = int(self._MAX_MEASUREMENTS * 0.8)
            if buf_len >= _warn_threshold and buf_len % 10_000 == 0:  # pragma: no cover
                logger.warning(  # pragma: no cover
                    "slo_measurement_buffer_near_capacity",
                    slo_name=name,
                    current_size=buf_len,
                    max_size=self._MAX_MEASUREMENTS,
                    utilization_pct=round(buf_len / self._MAX_MEASUREMENTS * 100, 1),
                )

            # Evict expired entries from the front of the deque.  Measurements
            # are appended in chronological order, so stale entries always sit
            # at the head.  popleft() is O(1) and we only iterate expired items,
            # making the overall cost O(k) per insert rather than O(n).
            cutoff = datetime.now(UTC) - timedelta(seconds=target.window_seconds)
            while buf and buf[0].timestamp < cutoff:
                evicted = buf.popleft()
                if _is_counter:
                    self._total_counts[name] -= 1
                    if evicted.success:
                        self._success_counts[name] -= 1

    def get_status(self, name: str) -> SLOStatus | None:
        """Get current SLO status.

        Args:
            name: SLO name.

        Returns:
            SLOStatus or None if not registered.
        """
        with self._lock:
            if name not in self._targets:
                return None
            target = self._targets[name]
            _is_counter = target.slo_type in (SLOType.AVAILABILITY, SLOType.ERROR_RATE)
            if _is_counter:
                # O(1) fast path — snapshot counters without copying the deque.
                _total = self._total_counts[name]
                _success = self._success_counts[name]
            else:
                # Copy the deque inside the lock to prevent RuntimeError from
                # concurrent record_measurement() modifying the deque during
                # list(). CPython's deque C-iterator raises RuntimeError if the
                # deque is mutated mid-iteration, even under the GIL.
                measurements = list(self._measurements[name])

        window_end = datetime.now(UTC)
        window_start = window_end - timedelta(seconds=target.window_seconds)

        if _is_counter:
            # AVAILABILITY / ERROR_RATE: O(1) read from pre-maintained counters.
            measurement_count = _total
            if _total == 0:
                current_value = 1.0 if target.slo_type == SLOType.AVAILABILITY else 0.0
            elif target.slo_type == SLOType.AVAILABILITY:
                current_value = _success / _total
            else:  # ERROR_RATE
                current_value = (_total - _success) / _total
        else:
            # measurements already copied under lock above.
            measurement_count = len(measurements)
            if not measurements:
                return SLOStatus(
                    slo_type=target.slo_type,
                    target=target,
                    current_value=0.0,
                    compliance=True,
                    error_budget_remaining=1.0,
                    error_budget_burn_rate=0.0,
                    window_start=window_start,
                    window_end=window_end,
                    measurement_count=0,
                )
            current_value = self._calculate_value(target, measurements)

        compliance = self._check_compliance(target, current_value)
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
            measurement_count=measurement_count,
        )

    def _calculate_value(
        self,
        target: SLOTarget,
        measurements: list[SLOMeasurement] | deque[SLOMeasurement],
    ) -> float:
        """Calculate current SLO value for LATENCY and THROUGHPUT types.

        AVAILABILITY and ERROR_RATE are handled via O(1) incremental counters
        in get_status and never reach this method.
        """
        if not measurements:  # pragma: no cover
            return 0.0

        if target.slo_type == SLOType.LATENCY:
            values = [m.value for m in measurements]
            # Bound sort cost for very large windows.  At 1 M measurements a
            # full sort takes ~160 ms and allocates ~8 MB.  Reservoir-sampling
            # 10 K values introduces ≤1 % percentile error for smooth
            # distributions — acceptable for operational SLO reads.
            _MAX_SORT = 10_000
            if len(values) > _MAX_SORT:
                import random as _rnd  # noqa: PLC0415

                values = _rnd.sample(values, _MAX_SORT)  # NOSONAR
            values.sort()
            if target.percentile:
                # Nearest-rank percentile (0-indexed).
                # ceil(n * P / 100) gives the 1-indexed rank; subtract 1 for
                # 0-indexed access and clamp to [0, n-1].
                raw_index = math.ceil(len(values) * target.percentile / 100) - 1
                index = max(0, min(raw_index, len(values) - 1))
                return values[index]
            return sum(values) / len(values)  # pragma: no cover

        # THROUGHPUT
        if len(measurements) < 2:
            return 0.0
        time_span = (measurements[-1].timestamp - measurements[0].timestamp).total_seconds()
        return len(measurements) / time_span if time_span > 0 else 0.0

    def _check_compliance(self, target: SLOTarget, current_value: float) -> bool:
        """Check if current value meets SLO target."""
        if target.slo_type == SLOType.ERROR_RATE or target.slo_type == SLOType.LATENCY:
            return current_value <= target.target_value
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

        if target.slo_type == SLOType.ERROR_RATE:
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
        # Snapshot keys under lock to avoid RuntimeError if register_slo()
        # is called concurrently (dict size change during iteration).
        with self._lock:
            names = list(self._targets)
        return {name: status for name in names if (status := self.get_status(name)) is not None}

    def to_dict(self) -> dict[str, Any]:
        """Export all SLO status as dictionary."""
        return {name: status.to_dict() for name, status in self.get_all_status().items()}


# Global SLO tracker
_slo_tracker: SLOTracker | None = None
_slo_tracker_lock = threading.Lock()


def get_slo_tracker() -> SLOTracker:
    """Get global SLO tracker instance."""
    global _slo_tracker
    if _slo_tracker is None:
        with _slo_tracker_lock:
            if _slo_tracker is None:  # pragma: no branch
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
    with _slo_tracker_lock:
        _slo_tracker = None


def with_slo_tracking(
    slo_name: str,
    track_latency: bool = False,
    latency_slo_name: str | None = None,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """
    Decorator to automatically track SLO measurements.

    Automatically records success/failure based on whether the function
    raises an exception. Can also track latency.

    Works with both sync and async functions.

    Parameters
    ----------
    slo_name : str
        Name of the availability/error SLO to track.
    track_latency : bool, default=False
        Whether to also track latency SLO.
    latency_slo_name : str, optional
        Name of the latency SLO. Defaults to "{slo_name}_latency".

    Returns
    -------
    Callable
        Decorated function with SLO tracking.

    Example
    -------
    >>> @with_slo_tracking("api_availability")
    ... def handle_request():
    ...     return process()
    ...
    >>> @with_slo_tracking("email_processing", track_latency=True)
    ... async def process_email():
    ...     return await send_email()
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        latency_name = latency_slo_name or f"{slo_name}_latency"

        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
                start_time = time.perf_counter()
                success = False
                try:
                    result = await func(*args, **kwargs)
                    success = True
                    return cast(T, result)
                finally:
                    duration_seconds = time.perf_counter() - start_time
                    # Record availability/error SLO
                    track_slo(slo_name, value=1.0, success=success)
                    # Record latency SLO if enabled
                    if track_latency:
                        track_slo(latency_name, value=duration_seconds, success=success)

            return async_wrapper  # type: ignore[return-value]

        @functools.wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            start_time = time.perf_counter()
            success = False
            try:
                result = func(*args, **kwargs)
                success = True
                return result
            finally:
                duration_seconds = time.perf_counter() - start_time
                # Record availability/error SLO
                track_slo(slo_name, value=1.0, success=success)
                # Record latency SLO if enabled
                if track_latency:
                    track_slo(latency_name, value=duration_seconds, success=success)

        return sync_wrapper

    return decorator


def with_slo_tracking_sync(
    slo_name: str,
    track_latency: bool = False,
    latency_slo_name: str | None = None,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """
    Decorator to track SLO measurements for synchronous functions.

    This is an explicit sync version of with_slo_tracking().

    Parameters
    ----------
    slo_name : str
        Name of the availability/error SLO to track.
    track_latency : bool, default=False
        Whether to also track latency SLO.
    latency_slo_name : str, optional
        Name of the latency SLO.

    Example
    -------
    >>> @with_slo_tracking_sync("email_processing", track_latency=True)
    ... def process_message(mail, tracker):
    ...     # Process mail
    ...     return result
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        latency_name = latency_slo_name or f"{slo_name}_latency"

        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            start_time = time.perf_counter()
            success = False
            try:
                result = func(*args, **kwargs)
                success = True
                return result
            finally:
                duration_seconds = time.perf_counter() - start_time
                # Record availability/error SLO
                track_slo(slo_name, value=1.0, success=success)
                # Record latency SLO if enabled
                if track_latency:
                    track_slo(latency_name, value=duration_seconds, success=success)

        return wrapper

    return decorator
