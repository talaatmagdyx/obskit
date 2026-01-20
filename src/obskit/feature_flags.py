"""
Feature Flag Integration
========================

Track feature flag usage and impact.

Features:
- Flag state tracking
- Usage metrics
- A/B test support
- Rollout tracking

Example:
    from obskit.feature_flags import FeatureFlagTracker

    flags = FeatureFlagTracker()

    # Track flag evaluation
    flags.record_evaluation("new_checkout", enabled=True, user_id="123")

    # Get metrics
    metrics = flags.get_flag_metrics("new_checkout")
"""

import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from prometheus_client import Counter, Gauge

from obskit.logging import get_logger

logger = get_logger(__name__)


# =============================================================================
# Prometheus Metrics
# =============================================================================

FLAG_EVALUATIONS = Counter(
    "feature_flag_evaluations_total", "Total feature flag evaluations", ["flag_name", "result"]
)

FLAG_ENABLED = Gauge(
    "feature_flag_enabled", "Feature flag enabled state (1=enabled, 0=disabled)", ["flag_name"]
)

FLAG_ROLLOUT_PERCENT = Gauge(
    "feature_flag_rollout_percent", "Feature flag rollout percentage", ["flag_name"]
)


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class FlagEvaluation:
    """A feature flag evaluation."""

    flag_name: str
    enabled: bool
    user_id: str | None = None
    context: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class FlagMetrics:
    """Metrics for a feature flag."""

    flag_name: str
    total_evaluations: int
    enabled_count: int
    disabled_count: int
    unique_users: int
    enabled_percent: float
    last_evaluation: datetime | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "flag_name": self.flag_name,
            "total_evaluations": self.total_evaluations,
            "enabled_count": self.enabled_count,
            "disabled_count": self.disabled_count,
            "unique_users": self.unique_users,
            "enabled_percent": self.enabled_percent,
            "last_evaluation": self.last_evaluation.isoformat() if self.last_evaluation else None,
        }


@dataclass
class FeatureFlag:
    """Feature flag definition."""

    name: str
    enabled: bool = False
    rollout_percent: float = 0.0
    description: str = ""
    owner: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)


# =============================================================================
# Feature Flag Tracker
# =============================================================================


class FeatureFlagTracker:
    """
    Track feature flag usage.

    Parameters
    ----------
    max_history : int
        Maximum evaluations to keep per flag
    """

    def __init__(self, max_history: int = 10000):
        self.max_history = max_history

        self._flags: dict[str, FeatureFlag] = {}
        self._evaluations: dict[str, list[FlagEvaluation]] = {}
        self._users_by_flag: dict[str, set] = {}
        self._lock = threading.Lock()

    def register_flag(
        self,
        name: str,
        enabled: bool = False,
        rollout_percent: float = 0.0,
        description: str = "",
        owner: str | None = None,
    ):
        """Register a feature flag."""
        flag = FeatureFlag(
            name=name,
            enabled=enabled,
            rollout_percent=rollout_percent,
            description=description,
            owner=owner,
        )

        with self._lock:
            self._flags[name] = flag
            if name not in self._evaluations:
                self._evaluations[name] = []
                self._users_by_flag[name] = set()

        FLAG_ENABLED.labels(flag_name=name).set(1 if enabled else 0)
        FLAG_ROLLOUT_PERCENT.labels(flag_name=name).set(rollout_percent)

    def record_evaluation(
        self,
        flag_name: str,
        enabled: bool,
        user_id: str | None = None,
        context: dict[str, Any] | None = None,
    ):
        """
        Record a flag evaluation.

        Parameters
        ----------
        flag_name : str
            Flag name
        enabled : bool
            Evaluation result
        user_id : str, optional
            User identifier
        context : dict, optional
            Evaluation context
        """
        evaluation = FlagEvaluation(
            flag_name=flag_name,
            enabled=enabled,
            user_id=user_id,
            context=context or {},
        )

        with self._lock:
            if flag_name not in self._evaluations:
                self._evaluations[flag_name] = []
                self._users_by_flag[flag_name] = set()

            self._evaluations[flag_name].append(evaluation)

            if user_id:
                self._users_by_flag[flag_name].add(user_id)

            # Trim history
            if len(self._evaluations[flag_name]) > self.max_history:
                self._evaluations[flag_name] = self._evaluations[flag_name][-self.max_history :]

        FLAG_EVALUATIONS.labels(
            flag_name=flag_name, result="enabled" if enabled else "disabled"
        ).inc()

    def get_flag_metrics(self, flag_name: str) -> FlagMetrics | None:
        """Get metrics for a flag."""
        with self._lock:
            if flag_name not in self._evaluations:
                return None

            evals = self._evaluations[flag_name]
            users = self._users_by_flag.get(flag_name, set())

        if not evals:
            return FlagMetrics(
                flag_name=flag_name,
                total_evaluations=0,
                enabled_count=0,
                disabled_count=0,
                unique_users=len(users),
                enabled_percent=0.0,
                last_evaluation=None,
            )

        enabled_count = sum(1 for e in evals if e.enabled)
        disabled_count = len(evals) - enabled_count

        return FlagMetrics(
            flag_name=flag_name,
            total_evaluations=len(evals),
            enabled_count=enabled_count,
            disabled_count=disabled_count,
            unique_users=len(users),
            enabled_percent=(enabled_count / len(evals)) * 100,
            last_evaluation=evals[-1].timestamp,
        )

    def get_all_metrics(self) -> dict[str, FlagMetrics]:
        """Get metrics for all flags."""
        with self._lock:
            flag_names = list(self._evaluations.keys())

        return {
            name: self.get_flag_metrics(name)
            for name in flag_names
            if self.get_flag_metrics(name) is not None
        }

    def update_flag_state(
        self, flag_name: str, enabled: bool, rollout_percent: float | None = None
    ):
        """Update flag state."""
        with self._lock:
            if flag_name in self._flags:
                self._flags[flag_name].enabled = enabled
                if rollout_percent is not None:
                    self._flags[flag_name].rollout_percent = rollout_percent

        FLAG_ENABLED.labels(flag_name=flag_name).set(1 if enabled else 0)
        if rollout_percent is not None:
            FLAG_ROLLOUT_PERCENT.labels(flag_name=flag_name).set(rollout_percent)


# =============================================================================
# Singleton
# =============================================================================

_tracker: FeatureFlagTracker | None = None
_tracker_lock = threading.Lock()


def get_feature_flag_tracker(**kwargs) -> FeatureFlagTracker:
    """Get or create the global feature flag tracker."""
    global _tracker

    if _tracker is None:
        with _tracker_lock:
            if _tracker is None:
                _tracker = FeatureFlagTracker(**kwargs)

    return _tracker
