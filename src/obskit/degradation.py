"""
Graceful Degradation Manager
============================

Manage feature degradation under load.

Features:
- Feature flags for degradation
- Load-based degradation
- Dependency-based degradation
- Degradation metrics

Example:
    from obskit.degradation import DegradationManager

    degradation = DegradationManager()
    degradation.register_feature("recommendations", priority=2)
    degradation.register_feature("analytics", priority=1)

    # Check if feature should be enabled
    if degradation.is_enabled("recommendations"):
        get_recommendations()
    else:
        return cached_recommendations()
"""

import threading
from collections.abc import Callable
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

FEATURE_STATE = Gauge(
    "degradation_feature_state", "Feature state (1=enabled, 0=degraded)", ["feature"]
)

DEGRADATION_LEVEL = Gauge("degradation_level", "Current degradation level (0-100)", ["service"])

DEGRADATION_EVENTS = Counter(
    "degradation_events_total", "Total degradation events", ["feature", "action"]
)

FALLBACK_CALLS = Counter(
    "degradation_fallback_calls_total", "Calls to fallback behavior", ["feature"]
)


# =============================================================================
# Enums and Data Classes
# =============================================================================


class DegradationLevel(Enum):
    """Degradation levels."""

    NONE = 0
    LOW = 25
    MEDIUM = 50
    HIGH = 75
    CRITICAL = 100


@dataclass
class Feature:
    """A degradable feature."""

    name: str
    priority: int  # Lower = more important, degrade last
    enabled: bool = True
    fallback: Callable | None = None
    degradation_threshold: int = 50  # Degrade at this level
    dependencies: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "priority": self.priority,
            "enabled": self.enabled,
            "degradation_threshold": self.degradation_threshold,
            "dependencies": self.dependencies,
            "metadata": self.metadata,
        }


@dataclass
class DegradationState:
    """Current degradation state."""

    level: DegradationLevel
    active_features: list[str]
    degraded_features: list[str]
    reason: str | None = None
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "level": self.level.value,
            "level_name": self.level.name,
            "active_features": self.active_features,
            "degraded_features": self.degraded_features,
            "reason": self.reason,
            "timestamp": self.timestamp.isoformat(),
        }


# =============================================================================
# Degradation Manager
# =============================================================================


class DegradationManager:
    """
    Manage graceful degradation of features.

    Parameters
    ----------
    service_name : str
        Name of the service
    auto_degrade : bool
        Automatically degrade based on metrics
    """

    def __init__(
        self,
        service_name: str = "default",
        auto_degrade: bool = True,
    ):
        self.service_name = service_name
        self.auto_degrade = auto_degrade

        self._features: dict[str, Feature] = {}
        self._current_level = DegradationLevel.NONE
        self._lock = threading.Lock()

        # Thresholds for auto-degradation
        self._error_rate_threshold = 0.1
        self._latency_threshold_ms = 1000
        self._cpu_threshold = 80
        self._memory_threshold = 85

    def register_feature(
        self,
        name: str,
        priority: int = 50,
        fallback: Callable | None = None,
        degradation_threshold: int = 50,
        dependencies: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        """
        Register a degradable feature.

        Parameters
        ----------
        name : str
            Feature name
        priority : int
            Priority (0-100, lower = more important)
        fallback : callable, optional
            Fallback function when degraded
        degradation_threshold : int
            Degrade when level exceeds this
        dependencies : list, optional
            Other features this depends on
        metadata : dict, optional
            Additional metadata
        """
        feature = Feature(
            name=name,
            priority=priority,
            fallback=fallback,
            degradation_threshold=degradation_threshold,
            dependencies=dependencies or [],
            metadata=metadata or {},
        )

        with self._lock:
            self._features[name] = feature

        FEATURE_STATE.labels(feature=name).set(1)

        logger.info(
            "feature_registered",
            feature=name,
            priority=priority,
            threshold=degradation_threshold,
        )

    def is_enabled(self, feature_name: str) -> bool:
        """
        Check if a feature is currently enabled.

        Parameters
        ----------
        feature_name : str
            Feature name

        Returns
        -------
        bool
        """
        with self._lock:
            feature = self._features.get(feature_name)
            if not feature:
                return True  # Unknown features are enabled by default

            # Check if any dependencies are disabled
            for dep in feature.dependencies:
                dep_feature = self._features.get(dep)
                if dep_feature and not dep_feature.enabled:
                    return False

            return feature.enabled

    def execute_with_fallback(
        self,
        feature_name: str,
        primary: Callable,
        fallback: Callable | None = None,
    ) -> Any:
        """
        Execute primary or fallback based on feature state.

        Parameters
        ----------
        feature_name : str
            Feature name
        primary : callable
            Primary function
        fallback : callable, optional
            Fallback function (overrides registered fallback)

        Returns
        -------
        Any
            Result from primary or fallback
        """
        if self.is_enabled(feature_name):
            return primary()

        # Use provided fallback or registered one
        with self._lock:
            feature = self._features.get(feature_name)
            fb = fallback or (feature.fallback if feature else None)

        if fb:
            FALLBACK_CALLS.labels(feature=feature_name).inc()
            return fb()

        return None

    def set_level(self, level: DegradationLevel | int, reason: str | None = None):
        """
        Set the degradation level.

        Parameters
        ----------
        level : DegradationLevel or int
            New degradation level
        reason : str, optional
            Reason for degradation
        """
        if isinstance(level, int):
            # Find closest level
            for dl in DegradationLevel:
                if dl.value >= level:
                    level = dl
                    break
            else:
                level = DegradationLevel.CRITICAL

        with self._lock:
            old_level = self._current_level
            self._current_level = level

            # Update feature states
            for feature in self._features.values():
                was_enabled = feature.enabled
                should_enable = level.value < feature.degradation_threshold

                if was_enabled and not should_enable:
                    feature.enabled = False
                    FEATURE_STATE.labels(feature=feature.name).set(0)
                    DEGRADATION_EVENTS.labels(feature=feature.name, action="degraded").inc()
                    logger.warning(
                        "feature_degraded",
                        feature=feature.name,
                        level=level.value,
                        reason=reason,
                    )
                elif not was_enabled and should_enable:
                    feature.enabled = True
                    FEATURE_STATE.labels(feature=feature.name).set(1)
                    DEGRADATION_EVENTS.labels(feature=feature.name, action="restored").inc()
                    logger.info(
                        "feature_restored",
                        feature=feature.name,
                        level=level.value,
                    )

        DEGRADATION_LEVEL.labels(service=self.service_name).set(level.value)

        if level != old_level:
            logger.info(
                "degradation_level_changed",
                old_level=old_level.value,
                new_level=level.value,
                reason=reason,
            )

    def degrade_feature(self, feature_name: str, reason: str | None = None):
        """Manually degrade a specific feature."""
        with self._lock:
            if feature_name in self._features:
                self._features[feature_name].enabled = False
                FEATURE_STATE.labels(feature=feature_name).set(0)
                DEGRADATION_EVENTS.labels(feature=feature_name, action="manual_degrade").inc()

                logger.warning(
                    "feature_manually_degraded",
                    feature=feature_name,
                    reason=reason,
                )

    def restore_feature(self, feature_name: str):
        """Manually restore a specific feature."""
        with self._lock:
            if feature_name in self._features:
                self._features[feature_name].enabled = True
                FEATURE_STATE.labels(feature=feature_name).set(1)
                DEGRADATION_EVENTS.labels(feature=feature_name, action="manual_restore").inc()

                logger.info(
                    "feature_manually_restored",
                    feature=feature_name,
                )

    def evaluate_metrics(
        self,
        error_rate: float | None = None,
        latency_ms: float | None = None,
        cpu_percent: float | None = None,
        memory_percent: float | None = None,
    ):
        """
        Evaluate metrics and adjust degradation level.

        Parameters
        ----------
        error_rate : float, optional
            Current error rate (0-1)
        latency_ms : float, optional
            Current latency in ms
        cpu_percent : float, optional
            CPU usage percentage
        memory_percent : float, optional
            Memory usage percentage
        """
        if not self.auto_degrade:
            return

        # Calculate degradation score
        score = 0
        reasons = []

        if error_rate is not None and error_rate > self._error_rate_threshold:
            score += min(50, (error_rate / self._error_rate_threshold) * 25)
            reasons.append(f"high_error_rate:{error_rate:.2%}")

        if latency_ms is not None and latency_ms > self._latency_threshold_ms:
            score += min(50, (latency_ms / self._latency_threshold_ms) * 25)
            reasons.append(f"high_latency:{latency_ms:.0f}ms")

        if cpu_percent is not None and cpu_percent > self._cpu_threshold:
            score += min(30, (cpu_percent - self._cpu_threshold) / 2)
            reasons.append(f"high_cpu:{cpu_percent:.0f}%")

        if memory_percent is not None and memory_percent > self._memory_threshold:
            score += min(30, (memory_percent - self._memory_threshold) / 2)
            reasons.append(f"high_memory:{memory_percent:.0f}%")

        # Set level based on score
        score = min(100, int(score))
        reason = ", ".join(reasons) if reasons else None

        if score >= 75:
            self.set_level(DegradationLevel.CRITICAL, reason)
        elif score >= 50:
            self.set_level(DegradationLevel.HIGH, reason)
        elif score >= 25:
            self.set_level(DegradationLevel.MEDIUM, reason)
        elif score > 0:
            self.set_level(DegradationLevel.LOW, reason)
        else:
            self.set_level(DegradationLevel.NONE)

    def get_state(self) -> DegradationState:
        """Get current degradation state."""
        with self._lock:
            active = [f.name for f in self._features.values() if f.enabled]
            degraded = [f.name for f in self._features.values() if not f.enabled]

            return DegradationState(
                level=self._current_level,
                active_features=active,
                degraded_features=degraded,
            )

    def get_feature(self, name: str) -> Feature | None:
        """Get a feature by name."""
        with self._lock:
            return self._features.get(name)

    def get_all_features(self) -> list[Feature]:
        """Get all registered features."""
        with self._lock:
            return list(self._features.values())

    def reset(self):
        """Reset all features to enabled."""
        with self._lock:
            for feature in self._features.values():
                feature.enabled = True
                FEATURE_STATE.labels(feature=feature.name).set(1)

            self._current_level = DegradationLevel.NONE

        DEGRADATION_LEVEL.labels(service=self.service_name).set(0)


# =============================================================================
# Singleton
# =============================================================================

_managers: dict[str, DegradationManager] = {}
_manager_lock = threading.Lock()


def get_degradation_manager(service_name: str = "default", **kwargs) -> DegradationManager:
    """Get or create a degradation manager."""
    if service_name not in _managers:
        with _manager_lock:
            if service_name not in _managers:
                _managers[service_name] = DegradationManager(service_name, **kwargs)

    return _managers[service_name]
