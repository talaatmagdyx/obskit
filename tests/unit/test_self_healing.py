"""Unit tests for Self-Healing Triggers."""

import pytest
import time
from obskit.self_healing import (
    SelfHealingEngine,
    HealingTrigger,
    HealingResult,
    HealingEvent,
    get_self_healing_engine,
)


class TestSelfHealingEngine:
    """Tests for SelfHealingEngine."""

    def test_register_trigger(self):
        """Test registering a healing trigger."""
        engine = SelfHealingEngine()
        
        engine.register_trigger(
            name="test-trigger",
            condition=lambda: False,
            action=lambda: True,
            description="Test trigger",
        )
        
        trigger = engine.get_trigger("test-trigger")
        assert trigger is not None
        assert trigger.description == "Test trigger"

    def test_evaluate_no_trigger(self):
        """Test evaluation when condition is false."""
        engine = SelfHealingEngine()
        
        engine.register_trigger(
            name="no-fire",
            condition=lambda: False,
            action=lambda: True,
        )
        
        events = engine.evaluate()
        assert len(events) == 0

    def test_evaluate_triggers_action(self):
        """Test evaluation triggers action when condition is true."""
        action_called = []
        
        engine = SelfHealingEngine()
        
        engine.register_trigger(
            name="fire-trigger",
            condition=lambda: True,
            action=lambda: (action_called.append(1), True)[1],
        )
        
        events = engine.evaluate()
        
        assert len(events) == 1
        assert events[0].result == HealingResult.SUCCESS
        assert len(action_called) == 1

    def test_dry_run_mode(self):
        """Test dry run mode doesn't execute action."""
        action_called = []
        
        engine = SelfHealingEngine(dry_run=True)
        
        engine.register_trigger(
            name="dry-run-test",
            condition=lambda: True,
            action=lambda: (action_called.append(1), True)[1],
        )
        
        events = engine.evaluate()
        
        assert len(events) == 1
        assert events[0].result == HealingResult.SKIPPED
        assert len(action_called) == 0

    def test_cooldown_period(self):
        """Test cooldown between executions."""
        engine = SelfHealingEngine()
        
        engine.register_trigger(
            name="cooldown-test",
            condition=lambda: True,
            action=lambda: True,
            cooldown_minutes=1,  # 1 minute cooldown
        )
        
        # First execution
        events1 = engine.evaluate()
        assert len(events1) == 1
        
        # Second execution should be blocked by cooldown
        events2 = engine.evaluate()
        assert len(events2) == 0

    def test_hourly_limit(self):
        """Test hourly execution limit."""
        engine = SelfHealingEngine()
        
        # Counter to track calls
        call_count = [0]
        
        engine.register_trigger(
            name="limit-test",
            condition=lambda: True,
            action=lambda: (call_count.__setitem__(0, call_count[0] + 1), True)[1],
            cooldown_minutes=0,  # No cooldown
            max_executions_per_hour=2,
        )
        
        # Execute 3 times
        for _ in range(3):
            engine.evaluate()
        
        # Should only execute twice due to limit
        assert call_count[0] == 2

    def test_action_failure(self):
        """Test handling of action failure."""
        engine = SelfHealingEngine()
        
        engine.register_trigger(
            name="fail-test",
            condition=lambda: True,
            action=lambda: False,  # Returns False = failure
        )
        
        events = engine.evaluate()
        
        assert len(events) == 1
        assert events[0].result == HealingResult.FAILED

    def test_action_exception(self):
        """Test handling of action exception."""
        engine = SelfHealingEngine()
        
        def failing_action():
            raise RuntimeError("Action failed!")
        
        engine.register_trigger(
            name="exception-test",
            condition=lambda: True,
            action=failing_action,
        )
        
        events = engine.evaluate()
        
        assert len(events) == 1
        assert events[0].result == HealingResult.FAILED
        assert "Action failed!" in events[0].error

    def test_disabled_engine(self):
        """Test disabled engine doesn't evaluate."""
        engine = SelfHealingEngine(enabled=False)
        
        engine.register_trigger(
            name="disabled-test",
            condition=lambda: True,
            action=lambda: True,
        )
        
        events = engine.evaluate()
        assert len(events) == 0

    def test_enable_disable_trigger(self):
        """Test enabling/disabling individual triggers."""
        engine = SelfHealingEngine()
        
        engine.register_trigger(
            name="toggle-test",
            condition=lambda: True,
            action=lambda: True,
            cooldown_minutes=0,
        )
        
        # Disable
        engine.disable_trigger("toggle-test")
        events = engine.evaluate()
        assert len(events) == 0
        
        # Enable
        engine.enable_trigger("toggle-test")
        events = engine.evaluate()
        assert len(events) == 1

    def test_get_events(self):
        """Test getting recent events."""
        engine = SelfHealingEngine()
        
        engine.register_trigger(
            name="events-test",
            condition=lambda: True,
            action=lambda: True,
            cooldown_minutes=0,
        )
        
        # Need to reset hourly counter
        engine._hourly_executions["events-test"] = []
        engine.evaluate()
        
        events = engine.get_events()
        assert len(events) >= 1


class TestHealingTrigger:
    """Tests for HealingTrigger."""

    def test_is_in_cooldown(self):
        """Test cooldown check."""
        from datetime import datetime
        
        trigger = HealingTrigger(
            name="test",
            condition=lambda: True,
            action=lambda: True,
            cooldown_minutes=5,
            last_execution=datetime.utcnow(),
        )
        
        assert trigger.is_in_cooldown() is True

    def test_to_dict(self):
        """Test HealingTrigger serialization."""
        trigger = HealingTrigger(
            name="test",
            condition=lambda: True,
            action=lambda: True,
            description="Test trigger",
        )
        
        data = trigger.to_dict()
        assert data["name"] == "test"
        assert data["description"] == "Test trigger"


class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_self_healing_engine(self):
        """Test global engine singleton."""
        engine1 = get_self_healing_engine()
        engine2 = get_self_healing_engine()
        assert engine1 is engine2
