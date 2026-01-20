"""
Chaos Engineering Hooks
=======================

Inject failures for testing resilience.

Features:
- Latency injection
- Error injection
- Resource exhaustion simulation
- Network partition simulation

Example:
    from obskit.chaos import ChaosEngine

    chaos = ChaosEngine()

    # Inject latency
    chaos.add_experiment("slow_database", latency_ms=500, probability=0.1)

    # In your code
    if chaos.should_inject("slow_database"):
        time.sleep(chaos.get_latency("slow_database"))
"""

import random
import threading
import time
from collections.abc import Callable, Generator
from contextlib import contextmanager
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

CHAOS_INJECTIONS = Counter(
    "chaos_injections_total", "Total chaos injections", ["experiment", "injection_type"]
)

CHAOS_EXPERIMENTS_ACTIVE = Gauge("chaos_experiments_active", "Number of active chaos experiments")

CHAOS_LATENCY_INJECTED = Counter(
    "chaos_latency_injected_ms_total", "Total latency injected in milliseconds", ["experiment"]
)


# =============================================================================
# Enums and Data Classes
# =============================================================================


class InjectionType(Enum):
    """Types of failure injection."""

    LATENCY = "latency"
    ERROR = "error"
    TIMEOUT = "timeout"
    RESOURCE = "resource"
    NETWORK = "network"


@dataclass
class ChaosExperiment:
    """A chaos experiment configuration."""

    name: str
    injection_type: InjectionType
    enabled: bool = True
    probability: float = 0.1  # 10% by default
    latency_ms: float = 0.0
    error_message: str = "Chaos injection error"
    error_class: type = Exception
    duration_minutes: int | None = None
    start_time: datetime = field(default_factory=datetime.utcnow)
    target_components: list[str] = field(default_factory=list)
    injections_count: int = 0

    def is_active(self) -> bool:
        """Check if experiment is still active."""
        if not self.enabled:
            return False

        if self.duration_minutes:
            elapsed = (datetime.utcnow() - self.start_time).total_seconds() / 60
            if elapsed > self.duration_minutes:
                return False

        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "injection_type": self.injection_type.value,
            "enabled": self.enabled,
            "probability": self.probability,
            "latency_ms": self.latency_ms,
            "error_message": self.error_message,
            "duration_minutes": self.duration_minutes,
            "start_time": self.start_time.isoformat(),
            "target_components": self.target_components,
            "injections_count": self.injections_count,
            "is_active": self.is_active(),
        }


# =============================================================================
# Chaos Engine
# =============================================================================


class ChaosEngine:
    """
    Chaos engineering injection engine.

    Parameters
    ----------
    enabled : bool
        Whether chaos injection is enabled globally
    safe_mode : bool
        Only allow experiments with < 50% probability
    """

    def __init__(
        self,
        enabled: bool = False,
        safe_mode: bool = True,
    ):
        self._enabled = enabled
        self.safe_mode = safe_mode

        self._experiments: dict[str, ChaosExperiment] = {}
        self._lock = threading.Lock()

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool):
        self._enabled = value
        logger.warning(
            "chaos_engine_toggled",
            enabled=value,
        )

    def add_experiment(
        self,
        name: str,
        injection_type: InjectionType | str = InjectionType.LATENCY,
        probability: float = 0.1,
        latency_ms: float = 100.0,
        error_message: str = "Chaos injection error",
        error_class: type = Exception,
        duration_minutes: int | None = None,
        target_components: list[str] | None = None,
    ):
        """
        Add a chaos experiment.

        Parameters
        ----------
        name : str
            Experiment name
        injection_type : InjectionType or str
            Type of injection
        probability : float
            Injection probability (0-1)
        latency_ms : float
            Latency to inject (for latency type)
        error_message : str
            Error message (for error type)
        error_class : type
            Exception class (for error type)
        duration_minutes : int, optional
            Experiment duration (None = indefinite)
        target_components : list, optional
            Target component names
        """
        if isinstance(injection_type, str):
            injection_type = InjectionType(injection_type)

        if self.safe_mode and probability > 0.5:
            logger.warning(
                "chaos_probability_capped",
                name=name,
                requested=probability,
                capped=0.5,
            )
            probability = 0.5

        experiment = ChaosExperiment(
            name=name,
            injection_type=injection_type,
            probability=probability,
            latency_ms=latency_ms,
            error_message=error_message,
            error_class=error_class,
            duration_minutes=duration_minutes,
            target_components=target_components or [],
        )

        with self._lock:
            self._experiments[name] = experiment

        self._update_active_count()

        logger.info(
            "chaos_experiment_added",
            name=name,
            type=injection_type.value,
            probability=probability,
        )

    def remove_experiment(self, name: str):
        """Remove a chaos experiment."""
        with self._lock:
            if name in self._experiments:
                del self._experiments[name]

        self._update_active_count()

    def enable_experiment(self, name: str):
        """Enable a specific experiment."""
        with self._lock:
            if name in self._experiments:
                self._experiments[name].enabled = True

        self._update_active_count()

    def disable_experiment(self, name: str):
        """Disable a specific experiment."""
        with self._lock:
            if name in self._experiments:
                self._experiments[name].enabled = False

        self._update_active_count()

    def should_inject(
        self,
        experiment_name: str,
        component: str | None = None,
    ) -> bool:
        """
        Check if failure should be injected.

        Parameters
        ----------
        experiment_name : str
            Experiment name
        component : str, optional
            Current component name

        Returns
        -------
        bool
            Whether to inject failure
        """
        if not self._enabled:
            return False

        with self._lock:
            experiment = self._experiments.get(experiment_name)
            if not experiment or not experiment.is_active():
                return False

            # Check component targeting
            if experiment.target_components and component:
                if component not in experiment.target_components:
                    return False

            # Random probability check
            if random.random() > experiment.probability:
                return False

            experiment.injections_count += 1

        CHAOS_INJECTIONS.labels(
            experiment=experiment_name, injection_type=experiment.injection_type.value
        ).inc()

        return True

    def inject_latency(self, experiment_name: str):
        """
        Inject latency for an experiment.

        Parameters
        ----------
        experiment_name : str
            Experiment name
        """
        with self._lock:
            experiment = self._experiments.get(experiment_name)
            if not experiment:
                return

            latency_ms = experiment.latency_ms

        if latency_ms > 0:
            time.sleep(latency_ms / 1000)
            CHAOS_LATENCY_INJECTED.labels(experiment=experiment_name).inc(latency_ms)

    def inject_error(self, experiment_name: str):
        """
        Inject an error for an experiment.

        Parameters
        ----------
        experiment_name : str
            Experiment name

        Raises
        ------
        Exception
            The configured error
        """
        with self._lock:
            experiment = self._experiments.get(experiment_name)
            if not experiment:
                return

            error_class = experiment.error_class
            error_message = experiment.error_message

        raise error_class(error_message)

    def get_latency(self, experiment_name: str) -> float:
        """Get the latency value for an experiment."""
        with self._lock:
            experiment = self._experiments.get(experiment_name)
            if experiment:
                return experiment.latency_ms
            return 0.0

    @contextmanager
    def maybe_inject(
        self,
        experiment_name: str,
        component: str | None = None,
    ) -> Generator[bool, None, None]:
        """
        Context manager that may inject chaos.

        Parameters
        ----------
        experiment_name : str
            Experiment name
        component : str, optional
            Component name

        Yields
        ------
        bool
            Whether injection is happening
        """
        should_inject = self.should_inject(experiment_name, component)

        if should_inject:
            with self._lock:
                experiment = self._experiments.get(experiment_name)
                if experiment:
                    injection_type = experiment.injection_type
                else:
                    injection_type = None

            if injection_type == InjectionType.LATENCY:
                self.inject_latency(experiment_name)
            elif injection_type == InjectionType.ERROR:
                self.inject_error(experiment_name)

        yield should_inject

    def get_experiment(self, name: str) -> ChaosExperiment | None:
        """Get an experiment by name."""
        with self._lock:
            return self._experiments.get(name)

    def get_all_experiments(self) -> list[ChaosExperiment]:
        """Get all experiments."""
        with self._lock:
            return list(self._experiments.values())

    def get_active_experiments(self) -> list[ChaosExperiment]:
        """Get active experiments."""
        with self._lock:
            return [e for e in self._experiments.values() if e.is_active()]

    def _update_active_count(self):
        """Update active experiments gauge."""
        with self._lock:
            count = sum(1 for e in self._experiments.values() if e.is_active())
        CHAOS_EXPERIMENTS_ACTIVE.set(count)

    def clear_all(self):
        """Remove all experiments."""
        with self._lock:
            self._experiments.clear()
        self._update_active_count()


# =============================================================================
# Decorators
# =============================================================================


def chaos_injection(
    experiment_name: str,
    engine: ChaosEngine | None = None,
    component: str | None = None,
):
    """
    Decorator to add chaos injection to a function.

    Parameters
    ----------
    experiment_name : str
        Experiment name
    engine : ChaosEngine, optional
        Chaos engine instance
    component : str, optional
        Component name
    """

    def decorator(func: Callable) -> Callable:
        chaos = engine or get_chaos_engine()

        def wrapper(*args, **kwargs):
            with chaos.maybe_inject(experiment_name, component):
                return func(*args, **kwargs)

        return wrapper

    return decorator


# =============================================================================
# Singleton
# =============================================================================

_engine: ChaosEngine | None = None
_engine_lock = threading.Lock()


def get_chaos_engine(**kwargs) -> ChaosEngine:
    """Get or create the global chaos engine."""
    global _engine

    if _engine is None:
        with _engine_lock:
            if _engine is None:
                _engine = ChaosEngine(**kwargs)

    return _engine


def enable_chaos():
    """Enable chaos injection globally."""
    get_chaos_engine().enabled = True


def disable_chaos():
    """Disable chaos injection globally."""
    get_chaos_engine().enabled = False
