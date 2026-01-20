"""
Self-Healing Triggers
=====================

Automatic remediation for common issues.

Features:
- Automatic restarts
- Connection pool resets
- Cache clearing
- Alerting integration

Example:
    from obskit.self_healing import SelfHealingEngine

    healer = SelfHealingEngine()

    # Register healing action
    healer.register_trigger(
        "high_error_rate",
        condition=lambda: error_rate > 0.5,
        action=restart_service,
        cooldown_minutes=5
    )

    # Evaluate triggers
    healer.evaluate()
"""

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from prometheus_client import Counter, Gauge

from obskit.logging import get_logger

logger = get_logger(__name__)


# =============================================================================
# Prometheus Metrics
# =============================================================================

HEALING_TRIGGERS_EVALUATED = Counter(
    "self_healing_triggers_evaluated_total", "Total trigger evaluations", ["trigger"]
)

HEALING_ACTIONS_EXECUTED = Counter(
    "self_healing_actions_executed_total", "Total healing actions executed", ["trigger", "result"]
)

HEALING_ACTIVE_TRIGGERS = Gauge("self_healing_active_triggers", "Number of active triggers")

HEALING_COOLDOWN_ACTIVE = Gauge(
    "self_healing_cooldown_active", "Triggers currently in cooldown", ["trigger"]
)


# =============================================================================
# Enums and Data Classes
# =============================================================================


class HealingResult(Enum):
    """Result of a healing action."""

    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    COOLDOWN = "cooldown"


@dataclass
class HealingTrigger:
    """A self-healing trigger configuration."""

    name: str
    condition: Callable[[], bool]
    action: Callable[[], bool]
    cooldown_minutes: int = 5
    max_executions_per_hour: int = 3
    enabled: bool = True
    description: str = ""
    executions: int = 0
    last_execution: datetime | None = None
    last_result: HealingResult | None = None

    def is_in_cooldown(self) -> bool:
        """Check if trigger is in cooldown."""
        if not self.last_execution:
            return False

        cooldown_end = self.last_execution + timedelta(minutes=self.cooldown_minutes)
        return datetime.utcnow() < cooldown_end

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "enabled": self.enabled,
            "description": self.description,
            "cooldown_minutes": self.cooldown_minutes,
            "max_executions_per_hour": self.max_executions_per_hour,
            "executions": self.executions,
            "last_execution": self.last_execution.isoformat() if self.last_execution else None,
            "last_result": self.last_result.value if self.last_result else None,
            "is_in_cooldown": self.is_in_cooldown(),
        }


@dataclass
class HealingEvent:
    """A healing action event."""

    trigger_name: str
    result: HealingResult
    duration_ms: float
    error: str | None = None
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "trigger_name": self.trigger_name,
            "result": self.result.value,
            "duration_ms": self.duration_ms,
            "error": self.error,
            "timestamp": self.timestamp.isoformat(),
        }


# =============================================================================
# Self-Healing Engine
# =============================================================================


class SelfHealingEngine:
    """
    Automatic remediation engine.

    Parameters
    ----------
    enabled : bool
        Whether self-healing is enabled
    dry_run : bool
        Log actions without executing
    """

    def __init__(
        self,
        enabled: bool = True,
        dry_run: bool = False,
    ):
        self._enabled = enabled
        self.dry_run = dry_run

        self._triggers: dict[str, HealingTrigger] = {}
        self._events: list[HealingEvent] = []
        self._hourly_executions: dict[str, list[datetime]] = {}
        self._lock = threading.Lock()

        self._evaluation_thread: threading.Thread | None = None
        self._stop_evaluation = threading.Event()

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool):
        self._enabled = value
        logger.info("self_healing_toggled", enabled=value)

    def register_trigger(
        self,
        name: str,
        condition: Callable[[], bool],
        action: Callable[[], bool],
        cooldown_minutes: int = 5,
        max_executions_per_hour: int = 3,
        description: str = "",
    ):
        """
        Register a healing trigger.

        Parameters
        ----------
        name : str
            Trigger name
        condition : callable
            Function returning True when healing is needed
        action : callable
            Healing action function, returns True on success
        cooldown_minutes : int
            Cooldown between executions
        max_executions_per_hour : int
            Maximum executions per hour
        description : str
            Trigger description
        """
        trigger = HealingTrigger(
            name=name,
            condition=condition,
            action=action,
            cooldown_minutes=cooldown_minutes,
            max_executions_per_hour=max_executions_per_hour,
            description=description,
        )

        with self._lock:
            self._triggers[name] = trigger
            self._hourly_executions[name] = []

        HEALING_ACTIVE_TRIGGERS.set(len(self._triggers))

        logger.info(
            "healing_trigger_registered",
            name=name,
            description=description,
        )

    def unregister_trigger(self, name: str):
        """Unregister a trigger."""
        with self._lock:
            if name in self._triggers:
                del self._triggers[name]
            if name in self._hourly_executions:
                del self._hourly_executions[name]

        HEALING_ACTIVE_TRIGGERS.set(len(self._triggers))

    def evaluate(self, trigger_name: str | None = None) -> list[HealingEvent]:
        """
        Evaluate triggers and execute actions if needed.

        Parameters
        ----------
        trigger_name : str, optional
            Specific trigger to evaluate (all if None)

        Returns
        -------
        list
            List of healing events
        """
        if not self._enabled:
            return []

        events = []

        with self._lock:
            triggers = (
                [self._triggers[trigger_name]] if trigger_name else list(self._triggers.values())
            )

        for trigger in triggers:
            if not trigger.enabled:
                continue

            event = self._evaluate_trigger(trigger)
            if event:
                events.append(event)

        return events

    def _evaluate_trigger(self, trigger: HealingTrigger) -> HealingEvent | None:
        """Evaluate a single trigger."""
        HEALING_TRIGGERS_EVALUATED.labels(trigger=trigger.name).inc()

        # Check cooldown
        if trigger.is_in_cooldown():
            HEALING_COOLDOWN_ACTIVE.labels(trigger=trigger.name).set(1)
            return None

        HEALING_COOLDOWN_ACTIVE.labels(trigger=trigger.name).set(0)

        # Check hourly limit
        with self._lock:
            hour_ago = datetime.utcnow() - timedelta(hours=1)
            recent_executions = [
                t for t in self._hourly_executions.get(trigger.name, []) if t > hour_ago
            ]
            self._hourly_executions[trigger.name] = recent_executions

            if len(recent_executions) >= trigger.max_executions_per_hour:
                logger.warning(
                    "healing_hourly_limit_reached",
                    trigger=trigger.name,
                    executions=len(recent_executions),
                )
                return HealingEvent(
                    trigger_name=trigger.name,
                    result=HealingResult.SKIPPED,
                    duration_ms=0,
                    error="Hourly execution limit reached",
                )

        # Evaluate condition
        try:
            should_heal = trigger.condition()
        except Exception as e:
            logger.error(
                "healing_condition_error",
                trigger=trigger.name,
                error=str(e),
            )
            return None

        if not should_heal:
            return None

        # Execute action
        logger.info(
            "healing_action_triggered",
            trigger=trigger.name,
            dry_run=self.dry_run,
        )

        if self.dry_run:
            return HealingEvent(
                trigger_name=trigger.name,
                result=HealingResult.SKIPPED,
                duration_ms=0,
                error="Dry run mode",
            )

        start_time = time.perf_counter()

        try:
            success = trigger.action()
            duration_ms = (time.perf_counter() - start_time) * 1000

            result = HealingResult.SUCCESS if success else HealingResult.FAILED

            with self._lock:
                trigger.executions += 1
                trigger.last_execution = datetime.utcnow()
                trigger.last_result = result
                self._hourly_executions[trigger.name].append(datetime.utcnow())

            event = HealingEvent(
                trigger_name=trigger.name,
                result=result,
                duration_ms=duration_ms,
            )

            with self._lock:
                self._events.append(event)
                if len(self._events) > 1000:
                    self._events = self._events[-1000:]

            HEALING_ACTIONS_EXECUTED.labels(trigger=trigger.name, result=result.value).inc()

            logger.info(
                "healing_action_completed",
                trigger=trigger.name,
                result=result.value,
                duration_ms=duration_ms,
            )

            return event

        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000

            with self._lock:
                trigger.last_execution = datetime.utcnow()
                trigger.last_result = HealingResult.FAILED

            event = HealingEvent(
                trigger_name=trigger.name,
                result=HealingResult.FAILED,
                duration_ms=duration_ms,
                error=str(e),
            )

            with self._lock:
                self._events.append(event)

            HEALING_ACTIONS_EXECUTED.labels(trigger=trigger.name, result="failed").inc()

            logger.error(
                "healing_action_failed",
                trigger=trigger.name,
                error=str(e),
            )

            return event

    def start_evaluation_loop(self, interval_seconds: float = 30.0):
        """Start background evaluation loop."""
        if self._evaluation_thread and self._evaluation_thread.is_alive():
            return

        self._stop_evaluation.clear()
        self._evaluation_thread = threading.Thread(
            target=self._evaluation_loop, args=(interval_seconds,), daemon=True
        )
        self._evaluation_thread.start()

        logger.info("self_healing_loop_started", interval=interval_seconds)

    def stop_evaluation_loop(self):
        """Stop background evaluation loop."""
        self._stop_evaluation.set()
        if self._evaluation_thread:
            self._evaluation_thread.join(timeout=5)

        logger.info("self_healing_loop_stopped")

    def _evaluation_loop(self, interval: float):
        """Background evaluation loop."""
        while not self._stop_evaluation.is_set():
            try:
                self.evaluate()
            except Exception as e:
                logger.error("self_healing_loop_error", error=str(e))

            self._stop_evaluation.wait(interval)

    def get_trigger(self, name: str) -> HealingTrigger | None:
        """Get a trigger by name."""
        with self._lock:
            return self._triggers.get(name)

    def get_all_triggers(self) -> list[HealingTrigger]:
        """Get all triggers."""
        with self._lock:
            return list(self._triggers.values())

    def get_events(self, limit: int = 20) -> list[HealingEvent]:
        """Get recent healing events."""
        with self._lock:
            return list(reversed(self._events[-limit:]))

    def enable_trigger(self, name: str):
        """Enable a specific trigger."""
        with self._lock:
            if name in self._triggers:
                self._triggers[name].enabled = True

    def disable_trigger(self, name: str):
        """Disable a specific trigger."""
        with self._lock:
            if name in self._triggers:
                self._triggers[name].enabled = False


# =============================================================================
# Common Healing Actions
# =============================================================================


def create_connection_pool_reset_action(pool_reset_func: Callable):
    """Create a healing action to reset connection pool."""

    def action():
        try:
            pool_reset_func()
            return True
        except Exception:
            return False

    return action


def create_cache_clear_action(cache_clear_func: Callable):
    """Create a healing action to clear cache."""

    def action():
        try:
            cache_clear_func()
            return True
        except Exception:
            return False

    return action


# =============================================================================
# Singleton
# =============================================================================

_engine: SelfHealingEngine | None = None
_engine_lock = threading.Lock()


def get_self_healing_engine(**kwargs) -> SelfHealingEngine:
    """Get or create the global self-healing engine."""
    global _engine

    if _engine is None:
        with _engine_lock:
            if _engine is None:
                _engine = SelfHealingEngine(**kwargs)

    return _engine
