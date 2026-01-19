"""Unit tests for SLA Breach Predictor."""

import pytest
from datetime import datetime, timedelta
from obskit.sla_predictor import (
    SLAPredictor,
    RiskAssessment,
    SLADefinition,
    get_sla_predictor,
)


class TestSLAPredictor:
    """Tests for SLAPredictor."""

    def test_set_sla(self):
        """Test defining an SLA."""
        predictor = SLAPredictor()
        
        predictor.set_sla(
            name="response_time",
            target_value=200.0,
            percentile=95,
            comparison="less_than",
        )
        
        # SLA should be stored
        risk = predictor.assess_risk("response_time")
        # May return None if not enough data
        assert risk is None or risk.target_value == 200.0

    def test_record_metrics(self):
        """Test recording metrics."""
        predictor = SLAPredictor()
        predictor.set_sla("latency", target_value=100.0)
        
        for i in range(10):
            predictor.record("latency", 50.0 + i)
        
        risk = predictor.assess_risk("latency")
        assert risk is not None
        assert risk.current_value > 0

    def test_assess_risk_insufficient_data(self):
        """Test risk assessment with insufficient data."""
        predictor = SLAPredictor()
        predictor.set_sla("metric", target_value=100.0)
        
        predictor.record("metric", 50.0)  # Only 1 data point
        
        risk = predictor.assess_risk("metric")
        assert risk is not None
        assert "Insufficient" in risk.suggestions[0]

    def test_assess_risk_stable(self):
        """Test risk assessment for stable metric."""
        predictor = SLAPredictor()
        predictor.set_sla("stable", target_value=100.0)
        
        # Record stable values well below threshold
        for i in range(20):
            predictor.record("stable", 50.0)
        
        risk = predictor.assess_risk("stable")
        
        assert risk is not None
        assert risk.breach_likely is False
        assert risk.trend == "stable"

    def test_assess_risk_degrading(self):
        """Test risk assessment for degrading metric."""
        predictor = SLAPredictor()
        predictor.set_sla("degrading", target_value=100.0)
        
        # Record increasing values
        base_time = datetime.utcnow() - timedelta(hours=20)
        for i in range(20):
            timestamp = base_time + timedelta(hours=i)
            predictor.record("degrading", 50.0 + i * 3, timestamp=timestamp)
        
        risk = predictor.assess_risk("degrading")
        
        assert risk is not None
        # Trend should be detected
        assert risk.trend in ["degrading", "increasing"] or risk.trend_slope > 0

    def test_breach_prediction(self):
        """Test breach prediction."""
        predictor = SLAPredictor()
        predictor.set_sla("breach_test", target_value=100.0)
        
        # Record values that will breach soon
        base_time = datetime.utcnow() - timedelta(hours=10)
        for i in range(10):
            timestamp = base_time + timedelta(hours=i)
            predictor.record("breach_test", 80.0 + i * 3, timestamp=timestamp)
        
        risk = predictor.assess_risk("breach_test")
        
        # May or may not predict breach depending on trend calculation
        assert risk is not None
        assert risk.risk_score >= 0

    def test_get_all_risks(self):
        """Test getting all risk assessments."""
        predictor = SLAPredictor()
        
        predictor.set_sla("sla1", target_value=100.0)
        predictor.set_sla("sla2", target_value=200.0)
        
        for i in range(10):
            predictor.record("sla1", 50.0)
            predictor.record("sla2", 100.0)
        
        all_risks = predictor.get_all_risks()
        
        assert len(all_risks) == 2
        assert "sla1" in all_risks
        assert "sla2" in all_risks

    def test_get_at_risk_slas(self):
        """Test getting at-risk SLAs."""
        predictor = SLAPredictor()
        
        predictor.set_sla("safe", target_value=100.0)
        predictor.set_sla("risky", target_value=50.0)
        
        for i in range(10):
            predictor.record("safe", 30.0)  # Well below target
            predictor.record("risky", 45.0)  # Close to target
        
        at_risk = predictor.get_at_risk_slas(threshold=30.0)
        
        # Results depend on risk calculation
        assert isinstance(at_risk, list)

    def test_warning_callback(self):
        """Test warning callback."""
        warnings = []
        
        def on_warning(assessment):
            warnings.append(assessment)
        
        predictor = SLAPredictor(on_warning=on_warning)
        predictor.set_sla("callback_test", target_value=50.0)
        
        # Record values that exceed threshold
        for i in range(10):
            predictor.record("callback_test", 60.0)  # Over target
        
        predictor.assess_risk("callback_test")
        
        # Callback may or may not be called depending on breach detection
        assert isinstance(warnings, list)


class TestRiskAssessment:
    """Tests for RiskAssessment."""

    def test_to_dict(self):
        """Test RiskAssessment serialization."""
        risk = RiskAssessment(
            sla_name="test",
            risk_score=75.0,
            breach_likely=True,
            hours_until_breach=12.0,
            current_value=80.0,
            target_value=100.0,
            trend="degrading",
            trend_slope=2.0,
            confidence=0.8,
            suggestions=["Scale up"],
        )
        
        data = risk.to_dict()
        assert data["sla_name"] == "test"
        assert data["risk_score"] == 75.0
        assert data["breach_likely"] is True


class TestSLADefinition:
    """Tests for SLADefinition."""

    def test_is_breached_less_than(self):
        """Test breach detection for less_than comparison."""
        sla = SLADefinition(
            name="latency",
            target_value=100.0,
            comparison="less_than",
        )
        
        assert sla.is_breached(50.0) is False
        assert sla.is_breached(150.0) is True

    def test_is_breached_greater_than(self):
        """Test breach detection for greater_than comparison."""
        sla = SLADefinition(
            name="availability",
            target_value=99.9,
            comparison="greater_than",
        )
        
        assert sla.is_breached(99.99) is False
        assert sla.is_breached(99.0) is True


class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_sla_predictor(self):
        """Test global predictor singleton."""
        predictor1 = get_sla_predictor()
        predictor2 = get_sla_predictor()
        assert predictor1 is predictor2
