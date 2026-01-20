"""
Smart Log Sampling.

Reduce log volume while maintaining visibility for important events.
"""

import hashlib
import random
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

import structlog

# Lazy logger initialization to avoid circular imports
_base_logger = None


def _get_logger():
    global _base_logger
    if _base_logger is None:
        from ..logging import get_logger

        _base_logger = get_logger(__name__)
    return _base_logger


# Sampling metrics tracked internally
_sampling_stats: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))


@dataclass
class SamplingRule:
    """Rule for sampling logs."""

    level: str
    sample_rate: float = 1.0  # 1.0 = 100% logged
    min_interval_seconds: float = 0.0  # Minimum time between logs
    dedupe_key: str | None = None  # Key for deduplication
    always_log_first_n: int = 0  # Always log first N occurrences


@dataclass
class SamplingConfig:
    """Configuration for log sampling."""

    # Default sample rates by level
    debug_rate: float = 0.01  # 1%
    info_rate: float = 0.1  # 10%
    warning_rate: float = 1.0  # 100%
    error_rate: float = 1.0  # 100%
    critical_rate: float = 1.0  # 100%

    # Always log slow operations (threshold in seconds)
    slow_threshold_seconds: float = 1.0

    # Dedupe similar logs within this window
    dedupe_window_seconds: float = 60.0

    # Always log first N occurrences of a unique log
    always_log_first_n: int = 3

    # Custom rules by event name
    custom_rules: dict[str, SamplingRule] = field(default_factory=dict)

    # Events to always log (bypass sampling)
    always_log_events: set[str] = field(default_factory=set)

    # Events to never log
    never_log_events: set[str] = field(default_factory=set)


class SampledLogger:
    """
    Logger with intelligent sampling.

    Reduces log volume while maintaining visibility for important events.

    Example:
        logger = SampledLogger(
            name="high_volume_service",
            config=SamplingConfig(
                debug_rate=0.01,
                info_rate=0.1,
                dedupe_window_seconds=60,
            )
        )

        # Only 10% of info logs will be emitted
        logger.info("routine_operation", data="value")

        # Errors are always logged
        logger.error("something_failed", error="details")

        # Mark as important to always log
        logger.info("important_event", _important=True)
    """

    def __init__(
        self, name: str, config: SamplingConfig | None = None, base_logger: Any | None = None
    ):
        """
        Initialize sampled logger.

        Args:
            name: Logger name
            config: Sampling configuration
            base_logger: Underlying logger (defaults to structlog)
        """
        self.name = name
        self.config = config or SamplingConfig()
        self._logger = base_logger or structlog.get_logger(name)

        # Track for deduplication
        self._recent_logs: dict[str, float] = {}  # dedupe_key -> last_logged_time
        self._occurrence_counts: dict[str, int] = defaultdict(int)

        # Track sampling stats
        self._sampled_count: dict[str, int] = defaultdict(int)
        self._dropped_count: dict[str, int] = defaultdict(int)

    def _get_sample_rate(self, level: str, event: str) -> float:
        """Get sample rate for a log level/event."""
        # Check custom rules
        if event in self.config.custom_rules:
            return self.config.custom_rules[event].sample_rate

        # Default rates by level
        rates = {
            "debug": self.config.debug_rate,
            "info": self.config.info_rate,
            "warning": self.config.warning_rate,
            "error": self.config.error_rate,
            "critical": self.config.critical_rate,
        }
        return rates.get(level, 1.0)

    def _get_dedupe_key(self, level: str, event: str, **kwargs) -> str:
        """Generate deduplication key for a log."""
        # Include level, event, and key kwargs in dedupe key
        key_parts = [level, event]

        # Add important kwargs to key
        for k in sorted(kwargs.keys()):
            if not k.startswith("_"):
                v = kwargs[k]
                if isinstance(v, (str, int, float, bool)):
                    key_parts.append(f"{k}={v}")

        key_string = "|".join(key_parts)
        return hashlib.md5(key_string.encode()).hexdigest()[:16]

    def _should_log(
        self,
        level: str,
        event: str,
        duration_seconds: float | None = None,
        important: bool = False,
        **kwargs,
    ) -> tuple:
        """
        Determine if a log should be emitted.

        Returns:
            (should_log, reason)
        """
        # Always log list
        if event in self.config.always_log_events:
            return True, "always_log_event"

        # Never log list
        if event in self.config.never_log_events:
            return False, "never_log_event"

        # Important flag bypasses sampling
        if important:
            return True, "marked_important"

        # Slow operations always logged
        if duration_seconds and duration_seconds >= self.config.slow_threshold_seconds:
            return True, "slow_operation"

        # Check occurrence count
        dedupe_key = self._get_dedupe_key(level, event, **kwargs)
        self._occurrence_counts[dedupe_key] += 1

        if self._occurrence_counts[dedupe_key] <= self.config.always_log_first_n:
            return True, "first_occurrences"

        # Check deduplication
        now = time.time()
        if dedupe_key in self._recent_logs:
            last_logged = self._recent_logs[dedupe_key]
            if now - last_logged < self.config.dedupe_window_seconds:
                return False, "deduplicated"

        # Apply sample rate
        sample_rate = self._get_sample_rate(level, event)
        if random.random() > sample_rate:
            return False, "sampled_out"

        # Log it
        self._recent_logs[dedupe_key] = now
        return True, "sampled_in"

    def _cleanup_recent(self):
        """Clean up old entries from recent logs."""
        now = time.time()
        cutoff = now - self.config.dedupe_window_seconds * 2

        keys_to_remove = [k for k, v in self._recent_logs.items() if v < cutoff]
        for k in keys_to_remove:
            del self._recent_logs[k]

    def _log(self, level: str, event: str, **kwargs):
        """Internal log method with sampling."""
        # Extract special kwargs
        duration = kwargs.pop("_duration", None)
        important = kwargs.pop("_important", False)

        should_log, reason = self._should_log(level, event, duration, important, **kwargs)

        if should_log:
            self._sampled_count[level] += 1

            # Add sampling metadata
            kwargs["_sampling_reason"] = reason

            log_method = getattr(self._logger, level)
            log_method(event, **kwargs)
        else:
            self._dropped_count[level] += 1

        # Periodic cleanup
        if random.random() < 0.01:  # 1% chance
            self._cleanup_recent()

        # Update global stats
        _sampling_stats[self.name]["sampled"] = sum(self._sampled_count.values())
        _sampling_stats[self.name]["dropped"] = sum(self._dropped_count.values())

    def debug(self, event: str, **kwargs):
        """Log debug message."""
        self._log("debug", event, **kwargs)

    def info(self, event: str, **kwargs):
        """Log info message."""
        self._log("info", event, **kwargs)

    def warning(self, event: str, **kwargs):
        """Log warning message."""
        self._log("warning", event, **kwargs)

    def error(self, event: str, **kwargs):
        """Log error message."""
        self._log("error", event, **kwargs)

    def critical(self, event: str, **kwargs):
        """Log critical message."""
        self._log("critical", event, **kwargs)

    def exception(self, event: str, **kwargs):
        """Log exception (always logged)."""
        kwargs["_important"] = True
        self._log("error", event, exc_info=True, **kwargs)

    def bind(self, **kwargs):
        """Bind context to logger."""
        bound_logger = self._logger.bind(**kwargs)
        new_sampled = SampledLogger(self.name, self.config, bound_logger)
        new_sampled._recent_logs = self._recent_logs
        new_sampled._occurrence_counts = self._occurrence_counts
        return new_sampled

    def get_stats(self) -> dict[str, Any]:
        """Get sampling statistics."""
        total_sampled = sum(self._sampled_count.values())
        total_dropped = sum(self._dropped_count.values())
        total = total_sampled + total_dropped

        return {
            "logger_name": self.name,
            "total_logs": total,
            "sampled": total_sampled,
            "dropped": total_dropped,
            "effective_rate": total_sampled / total if total > 0 else 0,
            "by_level": {
                "sampled": dict(self._sampled_count),
                "dropped": dict(self._dropped_count),
            },
        }


class AdaptiveSampledLogger(SampledLogger):
    """
    Logger with adaptive sampling based on log volume.

    Automatically adjusts sampling rates based on current load.

    Example:
        logger = AdaptiveSampledLogger(
            name="adaptive_service",
            target_logs_per_second=100,
        )

        # Sampling rate adjusts automatically based on volume
        logger.info("high_volume_event")
    """

    def __init__(
        self,
        name: str,
        target_logs_per_second: float = 100,
        min_sample_rate: float = 0.001,
        max_sample_rate: float = 1.0,
        adjustment_interval: float = 10.0,
        **kwargs,
    ):
        """
        Initialize adaptive sampled logger.

        Args:
            name: Logger name
            target_logs_per_second: Target log volume
            min_sample_rate: Minimum sample rate
            max_sample_rate: Maximum sample rate
            adjustment_interval: Seconds between rate adjustments
        """
        super().__init__(name, **kwargs)

        self.target_lps = target_logs_per_second
        self.min_rate = min_sample_rate
        self.max_rate = max_sample_rate
        self.adjustment_interval = adjustment_interval

        self._current_rate = 1.0
        self._log_count_in_window = 0
        self._window_start = time.time()

    def _maybe_adjust_rate(self):
        """Adjust sampling rate based on current volume."""
        now = time.time()
        elapsed = now - self._window_start

        if elapsed >= self.adjustment_interval:
            # Calculate current rate
            current_lps = self._log_count_in_window / elapsed

            if current_lps > 0:
                # Calculate desired rate
                desired_rate = self.target_lps / current_lps

                # Apply bounds and smoothing
                new_rate = self._current_rate * 0.7 + desired_rate * 0.3
                self._current_rate = max(self.min_rate, min(self.max_rate, new_rate))

            # Reset window
            self._log_count_in_window = 0
            self._window_start = now

            _get_logger().debug(
                "adaptive_sampling_adjusted",
                logger=self.name,
                new_rate=self._current_rate,
                current_lps=current_lps,
            )

    def _get_sample_rate(self, level: str, event: str) -> float:
        """Get adaptive sample rate."""
        base_rate = super()._get_sample_rate(level, event)
        return base_rate * self._current_rate

    def _log(self, level: str, event: str, **kwargs):
        """Log with adaptive sampling."""
        self._log_count_in_window += 1
        self._maybe_adjust_rate()
        super()._log(level, event, **kwargs)


def get_sampling_stats() -> dict[str, dict[str, int]]:
    """Get global sampling statistics for all loggers."""
    return dict(_sampling_stats)


__all__ = [
    "SampledLogger",
    "AdaptiveSampledLogger",
    "SamplingConfig",
    "SamplingRule",
    "get_sampling_stats",
]
