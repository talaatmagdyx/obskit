"""
Adaptive Sampling
=================

Dynamically adjust trace and log sampling rates.

Features:
- Load-based sampling
- Error-biased sampling
- Head/tail-based sampling
- Cost optimization

Example:
    from obskit.adaptive_sampling import AdaptiveSampler

    sampler = AdaptiveSampler(
        base_rate=0.1,
        min_rate=0.01,
        max_rate=1.0
    )

    if sampler.should_sample(operation="process_order", has_error=False):
        record_trace()
"""

import random
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from prometheus_client import Counter, Gauge

from obskit.logging import get_logger

logger = get_logger(__name__)


# =============================================================================
# Prometheus Metrics
# =============================================================================

SAMPLING_DECISIONS = Counter(
    "adaptive_sampling_decisions_total", "Total sampling decisions", ["decision", "reason"]
)

SAMPLING_RATE = Gauge("adaptive_sampling_rate", "Current sampling rate", ["sampler"])

SAMPLING_LOAD = Gauge("adaptive_sampling_load", "Current load factor", ["sampler"])


# =============================================================================
# Enums and Data Classes
# =============================================================================


class SamplingStrategy(Enum):
    """Sampling strategies."""

    PROBABILISTIC = "probabilistic"
    RATE_LIMITING = "rate_limiting"
    ALWAYS = "always"
    NEVER = "never"


class SamplingDecision(Enum):
    """Sampling decision result."""

    SAMPLE = "sample"
    DROP = "drop"


@dataclass
class SamplingConfig:
    """Sampling configuration."""

    base_rate: float = 0.1
    min_rate: float = 0.01
    max_rate: float = 1.0
    error_boost_factor: float = 10.0
    slow_boost_factor: float = 5.0
    slow_threshold_ms: float = 1000.0
    rate_limit_per_second: int = 100

    def to_dict(self) -> dict[str, Any]:
        return {
            "base_rate": self.base_rate,
            "min_rate": self.min_rate,
            "max_rate": self.max_rate,
            "error_boost_factor": self.error_boost_factor,
            "slow_boost_factor": self.slow_boost_factor,
            "slow_threshold_ms": self.slow_threshold_ms,
            "rate_limit_per_second": self.rate_limit_per_second,
        }


@dataclass
class SamplingStats:
    """Sampling statistics."""

    sampler_name: str
    current_rate: float
    samples_taken: int
    samples_dropped: int
    load_factor: float
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def sample_ratio(self) -> float:
        total = self.samples_taken + self.samples_dropped
        return self.samples_taken / total if total > 0 else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "sampler_name": self.sampler_name,
            "current_rate": self.current_rate,
            "samples_taken": self.samples_taken,
            "samples_dropped": self.samples_dropped,
            "sample_ratio": self.sample_ratio,
            "load_factor": self.load_factor,
            "timestamp": self.timestamp.isoformat(),
        }


# =============================================================================
# Adaptive Sampler
# =============================================================================


class AdaptiveSampler:
    """
    Adaptive sampling for traces and logs.

    Parameters
    ----------
    name : str
        Sampler name
    base_rate : float
        Base sampling rate (0-1)
    min_rate : float
        Minimum sampling rate
    max_rate : float
        Maximum sampling rate
    adapt_interval_seconds : float
        Interval for rate adaptation
    """

    def __init__(
        self,
        name: str = "default",
        base_rate: float = 0.1,
        min_rate: float = 0.01,
        max_rate: float = 1.0,
        adapt_interval_seconds: float = 60.0,
    ):
        self.name = name
        self.config = SamplingConfig(
            base_rate=base_rate,
            min_rate=min_rate,
            max_rate=max_rate,
        )
        self.adapt_interval = adapt_interval_seconds

        self._current_rate = base_rate
        self._load_factor = 1.0
        self._samples_taken = 0
        self._samples_dropped = 0

        # Rate limiting
        self._rate_limit_tokens = self.config.rate_limit_per_second
        self._last_token_refill = time.time()

        # Operation-specific rates
        self._operation_rates: dict[str, float] = {}

        # Metrics tracking
        self._request_count = 0
        self._error_count = 0
        self._last_adaptation = datetime.utcnow()

        self._lock = threading.Lock()

    def should_sample(
        self,
        operation: str | None = None,
        has_error: bool = False,
        latency_ms: float | None = None,
        priority: bool = False,
        attributes: dict[str, Any] | None = None,
    ) -> bool:
        """
        Decide whether to sample.

        Parameters
        ----------
        operation : str, optional
            Operation name
        has_error : bool
            Whether this is an error
        latency_ms : float, optional
            Operation latency
        priority : bool
            High priority (always sample)
        attributes : dict, optional
            Additional attributes

        Returns
        -------
        bool
            Whether to sample
        """
        # Always sample priority items
        if priority:
            self._record_decision(SamplingDecision.SAMPLE, "priority")
            return True

        # Check rate limiting
        if not self._check_rate_limit():
            self._record_decision(SamplingDecision.DROP, "rate_limited")
            return False

        # Calculate effective rate
        effective_rate = self._calculate_effective_rate(
            operation=operation,
            has_error=has_error,
            latency_ms=latency_ms,
        )

        # Probabilistic decision
        should_sample = random.random() < effective_rate

        with self._lock:
            self._request_count += 1
            if has_error:
                self._error_count += 1

            if should_sample:
                self._samples_taken += 1
            else:
                self._samples_dropped += 1

        reason = "sampled" if should_sample else "dropped"
        self._record_decision(
            SamplingDecision.SAMPLE if should_sample else SamplingDecision.DROP, reason
        )

        # Periodically adapt rate
        self._maybe_adapt()

        return should_sample

    def _calculate_effective_rate(
        self,
        operation: str | None,
        has_error: bool,
        latency_ms: float | None,
    ) -> float:
        """Calculate effective sampling rate."""
        rate = self._current_rate

        # Operation-specific rate
        if operation and operation in self._operation_rates:
            rate = self._operation_rates[operation]

        # Boost for errors
        if has_error:
            rate = min(self.config.max_rate, rate * self.config.error_boost_factor)

        # Boost for slow requests
        if latency_ms and latency_ms > self.config.slow_threshold_ms:
            rate = min(self.config.max_rate, rate * self.config.slow_boost_factor)

        return rate

    def _check_rate_limit(self) -> bool:
        """Check and consume rate limit token."""
        with self._lock:
            now = time.time()
            elapsed = now - self._last_token_refill

            # Refill tokens
            if elapsed > 1.0:
                tokens_to_add = int(elapsed) * self.config.rate_limit_per_second
                self._rate_limit_tokens = min(
                    self.config.rate_limit_per_second, self._rate_limit_tokens + tokens_to_add
                )
                self._last_token_refill = now

            # Check token
            if self._rate_limit_tokens > 0:
                self._rate_limit_tokens -= 1
                return True

            return False

    def _maybe_adapt(self):
        """Adapt sampling rate based on load."""
        now = datetime.utcnow()
        elapsed = (now - self._last_adaptation).total_seconds()

        if elapsed < self.adapt_interval:
            return

        with self._lock:
            self._last_adaptation = now

            # Calculate load factor based on request rate
            if self._request_count > 0:
                expected_samples = self._request_count * self.config.base_rate
                actual_samples = self._samples_taken

                # Adjust based on sample ratio
                if expected_samples > 0:
                    self._load_factor = actual_samples / expected_samples
                else:
                    self._load_factor = 1.0

                # Adjust rate
                if self._load_factor > 1.5:
                    # Too many samples, reduce rate
                    self._current_rate = max(self.config.min_rate, self._current_rate * 0.8)
                elif self._load_factor < 0.5 and self._request_count > 100:
                    # Not enough samples, increase rate
                    self._current_rate = min(self.config.max_rate, self._current_rate * 1.2)

                # Error rate adjustment
                error_rate = self._error_count / self._request_count
                if error_rate > 0.1:
                    # High error rate, sample more
                    self._current_rate = min(self.config.max_rate, self._current_rate * 1.5)

            # Reset counters
            self._request_count = 0
            self._error_count = 0

        SAMPLING_RATE.labels(sampler=self.name).set(self._current_rate)
        SAMPLING_LOAD.labels(sampler=self.name).set(self._load_factor)

    def _record_decision(self, decision: SamplingDecision, reason: str):
        """Record sampling decision."""
        SAMPLING_DECISIONS.labels(decision=decision.value, reason=reason).inc()

    def set_operation_rate(self, operation: str, rate: float):
        """Set sampling rate for specific operation."""
        with self._lock:
            self._operation_rates[operation] = min(
                self.config.max_rate, max(self.config.min_rate, rate)
            )

    def set_rate(self, rate: float):
        """Manually set sampling rate."""
        with self._lock:
            self._current_rate = min(self.config.max_rate, max(self.config.min_rate, rate))

        SAMPLING_RATE.labels(sampler=self.name).set(self._current_rate)

    def get_rate(self) -> float:
        """Get current sampling rate."""
        with self._lock:
            return self._current_rate

    def get_stats(self) -> SamplingStats:
        """Get sampling statistics."""
        with self._lock:
            return SamplingStats(
                sampler_name=self.name,
                current_rate=self._current_rate,
                samples_taken=self._samples_taken,
                samples_dropped=self._samples_dropped,
                load_factor=self._load_factor,
            )

    def reset_stats(self):
        """Reset statistics."""
        with self._lock:
            self._samples_taken = 0
            self._samples_dropped = 0


# =============================================================================
# Singleton
# =============================================================================

_samplers: dict[str, AdaptiveSampler] = {}
_sampler_lock = threading.Lock()


def get_adaptive_sampler(name: str = "default", **kwargs) -> AdaptiveSampler:
    """Get or create an adaptive sampler."""
    if name not in _samplers:
        with _sampler_lock:
            if name not in _samplers:
                _samplers[name] = AdaptiveSampler(name=name, **kwargs)

    return _samplers[name]
