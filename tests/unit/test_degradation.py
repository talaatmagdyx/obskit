"""Unit tests for Graceful Degradation Manager."""

import pytest
from obskit.degradation import (
    DegradationManager,
    DegradationLevel,
    DegradationState,
    Feature,
    get_degradation_manager,
)


class TestDegradationManager:
    """Tests for DegradationManager."""

    def test_register_feature(self):
        """Test registering a degradable feature."""
        manager = DegradationManager("test-service")
        
        manager.register_feature(
            name="recommendations",
            priority=50,
            degradation_threshold=60,
        )
        
        feature = manager.get_feature("recommendations")
        assert feature is not None
        assert feature.priority == 50

    def test_is_enabled_default(self):
        """Test feature is enabled by default."""
        manager = DegradationManager("test-service")
        manager.register_feature("test-feature")
        
        assert manager.is_enabled("test-feature") is True

    def test_is_enabled_unknown_feature(self):
        """Test unknown feature returns True."""
        manager = DegradationManager("test-service")
        
        assert manager.is_enabled("unknown") is True

    def test_set_level_degrades_features(self):
        """Test setting level degrades appropriate features."""
        manager = DegradationManager("test-service")
        
        manager.register_feature("low-priority", priority=80, degradation_threshold=30)
        manager.register_feature("high-priority", priority=20, degradation_threshold=80)
        
        # Set medium degradation level
        manager.set_level(DegradationLevel.MEDIUM)  # 50
        
        # Low priority should be degraded (threshold 30 < level 50)
        assert manager.is_enabled("low-priority") is False
        # High priority should still be enabled (threshold 80 > level 50)
        assert manager.is_enabled("high-priority") is True

    def test_set_level_restores_features(self):
        """Test lowering level restores features."""
        manager = DegradationManager("test-service")
        manager.register_feature("test", degradation_threshold=50)
        
        # Degrade
        manager.set_level(DegradationLevel.HIGH)
        assert manager.is_enabled("test") is False
        
        # Restore
        manager.set_level(DegradationLevel.NONE)
        assert manager.is_enabled("test") is True

    def test_degrade_feature_manually(self):
        """Test manually degrading a feature."""
        manager = DegradationManager("test-service")
        manager.register_feature("manual-test")
        
        manager.degrade_feature("manual-test", reason="Testing")
        
        assert manager.is_enabled("manual-test") is False

    def test_restore_feature_manually(self):
        """Test manually restoring a feature."""
        manager = DegradationManager("test-service")
        manager.register_feature("restore-test")
        
        manager.degrade_feature("restore-test")
        manager.restore_feature("restore-test")
        
        assert manager.is_enabled("restore-test") is True

    def test_execute_with_fallback(self):
        """Test execute_with_fallback."""
        manager = DegradationManager("test-service")
        manager.register_feature("fallback-test")
        
        # Primary should execute
        result = manager.execute_with_fallback(
            "fallback-test",
            primary=lambda: "primary",
            fallback=lambda: "fallback",
        )
        assert result == "primary"
        
        # Degrade and fallback should execute
        manager.degrade_feature("fallback-test")
        result = manager.execute_with_fallback(
            "fallback-test",
            primary=lambda: "primary",
            fallback=lambda: "fallback",
        )
        assert result == "fallback"

    def test_evaluate_metrics_auto_degrade(self):
        """Test automatic degradation based on metrics."""
        manager = DegradationManager("test-service", auto_degrade=True)
        manager.register_feature("auto-test", degradation_threshold=50)
        
        # High error rate should trigger degradation
        manager.evaluate_metrics(error_rate=0.5)
        
        state = manager.get_state()
        assert state.level != DegradationLevel.NONE

    def test_feature_dependencies(self):
        """Test feature dependency checking."""
        manager = DegradationManager("test-service")
        
        manager.register_feature("base")
        manager.register_feature("dependent", dependencies=["base"])
        
        # Degrade base
        manager.degrade_feature("base")
        
        # Dependent should also be disabled
        assert manager.is_enabled("dependent") is False

    def test_get_state(self):
        """Test getting degradation state."""
        manager = DegradationManager("test-service")
        manager.register_feature("active")
        manager.register_feature("degraded")
        manager.degrade_feature("degraded")
        
        state = manager.get_state()
        
        assert "active" in state.active_features
        assert "degraded" in state.degraded_features

    def test_reset(self):
        """Test resetting all features."""
        manager = DegradationManager("test-service")
        manager.register_feature("test1")
        manager.register_feature("test2")
        
        manager.set_level(DegradationLevel.CRITICAL)
        manager.reset()
        
        assert manager.is_enabled("test1") is True
        assert manager.is_enabled("test2") is True


class TestFeature:
    """Tests for Feature."""

    def test_to_dict(self):
        """Test Feature serialization."""
        feature = Feature(
            name="test",
            priority=50,
            enabled=True,
            degradation_threshold=60,
        )
        
        data = feature.to_dict()
        assert data["name"] == "test"
        assert data["priority"] == 50
        assert data["enabled"] is True


class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_degradation_manager(self):
        """Test manager singleton per service."""
        manager1 = get_degradation_manager("service1")
        manager2 = get_degradation_manager("service1")
        manager3 = get_degradation_manager("service2")
        
        assert manager1 is manager2
        assert manager1 is not manager3
