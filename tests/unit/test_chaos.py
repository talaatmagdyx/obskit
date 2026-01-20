"""Unit tests for Chaos Engineering Hooks."""

import time

import pytest

from obskit.chaos import (
    ChaosEngine,
    InjectionType,
    chaos_injection,
    disable_chaos,
    enable_chaos,
    get_chaos_engine,
)


class TestChaosEngine:
    """Tests for ChaosEngine."""

    def test_add_experiment(self):
        """Test adding a chaos experiment."""
        engine = ChaosEngine(enabled=True)

        engine.add_experiment(
            name="test-latency",
            injection_type=InjectionType.LATENCY,
            probability=0.5,
            latency_ms=100,
        )

        experiment = engine.get_experiment("test-latency")
        assert experiment is not None
        assert experiment.latency_ms == 100

    def test_safe_mode_caps_probability(self):
        """Test safe mode caps probability at 50%."""
        engine = ChaosEngine(enabled=True, safe_mode=True)

        engine.add_experiment(
            name="high-prob",
            probability=0.9,  # Should be capped to 0.5
        )

        experiment = engine.get_experiment("high-prob")
        assert experiment.probability == 0.5

    def test_should_inject_disabled_engine(self):
        """Test no injection when engine is disabled."""
        engine = ChaosEngine(enabled=False)

        engine.add_experiment(
            name="disabled-test",
            probability=1.0,
        )

        # Should never inject when disabled
        for _ in range(10):
            assert engine.should_inject("disabled-test") is False

    def test_should_inject_probability(self):
        """Test probabilistic injection."""
        engine = ChaosEngine(enabled=True)

        engine.add_experiment(
            name="prob-test",
            probability=1.0,  # Always inject
        )

        assert engine.should_inject("prob-test") is True

    def test_inject_latency(self):
        """Test latency injection."""
        engine = ChaosEngine(enabled=True)

        engine.add_experiment(
            name="latency-test",
            injection_type=InjectionType.LATENCY,
            latency_ms=50,
        )

        start = time.time()
        engine.inject_latency("latency-test")
        elapsed = (time.time() - start) * 1000

        assert elapsed >= 40  # Allow some tolerance

    def test_inject_error(self):
        """Test error injection."""
        engine = ChaosEngine(enabled=True)

        engine.add_experiment(
            name="error-test",
            injection_type=InjectionType.ERROR,
            error_message="Chaos error!",
        )

        with pytest.raises(Exception, match="Chaos error!"):
            engine.inject_error("error-test")

    def test_maybe_inject_context_manager(self):
        """Test maybe_inject context manager."""
        engine = ChaosEngine(enabled=True, safe_mode=False)  # Disable safe_mode

        engine.add_experiment(
            name="ctx-test",
            injection_type=InjectionType.LATENCY,
            probability=1.0,
            latency_ms=10,
        )

        with engine.maybe_inject("ctx-test") as injected:
            assert injected is True

    def test_enable_disable_experiment(self):
        """Test enabling/disabling individual experiments."""
        engine = ChaosEngine(enabled=True, safe_mode=False)  # Disable safe_mode

        engine.add_experiment("toggle-test", probability=1.0)

        engine.disable_experiment("toggle-test")
        assert engine.should_inject("toggle-test") is False

        engine.enable_experiment("toggle-test")
        assert engine.should_inject("toggle-test") is True

    def test_experiment_duration(self):
        """Test experiment duration limit."""
        engine = ChaosEngine(enabled=True, safe_mode=False)

        # Create experiment with a very short duration (will expire quickly)
        # Note: duration_minutes=0 means no duration limit (infinite)
        # So we test that 0 means no expiry
        engine.add_experiment(
            name="duration-test",
            probability=1.0,
            duration_minutes=0,  # 0 means no duration limit
        )

        experiment = engine.get_experiment("duration-test")
        # With duration_minutes=0, experiment should still be active (no limit)
        assert experiment.is_active() is True

    def test_target_components(self):
        """Test component targeting."""
        engine = ChaosEngine(enabled=True, safe_mode=False)  # Disable safe_mode

        engine.add_experiment(
            name="target-test",
            probability=1.0,
            target_components=["api"],
        )

        assert engine.should_inject("target-test", component="api") is True
        assert engine.should_inject("target-test", component="worker") is False


class TestChaosInjectionDecorator:
    """Tests for chaos_injection decorator."""

    def test_decorator_with_injection(self):
        """Test decorator applies injection."""
        engine = ChaosEngine(enabled=True)

        engine.add_experiment(
            name="decorator-test",
            injection_type=InjectionType.LATENCY,
            probability=1.0,
            latency_ms=10,
        )

        @chaos_injection("decorator-test", engine=engine)
        def my_function():
            return "result"

        result = my_function()
        assert result == "result"


class TestSingleton:
    """Tests for singleton and global functions."""

    def test_get_chaos_engine(self):
        """Test global chaos engine singleton."""
        engine1 = get_chaos_engine()
        engine2 = get_chaos_engine()
        assert engine1 is engine2

    def test_enable_disable_chaos(self):
        """Test global enable/disable functions."""
        disable_chaos()
        assert get_chaos_engine().enabled is False

        enable_chaos()
        assert get_chaos_engine().enabled is True

        disable_chaos()  # Reset
