"""Unit tests for Root Cause Analyzer."""

from obskit.root_cause import (
    Anomaly,
    AnomalySeverity,
    AnomalyType,
    CorrelationRule,
    RootCauseAnalyzer,
    get_root_cause_analyzer,
)


class TestRootCauseAnalyzer:
    """Tests for RootCauseAnalyzer."""

    def test_record_anomaly(self):
        """Test recording an anomaly."""
        analyzer = RootCauseAnalyzer("test-service")

        anomaly_id = analyzer.record_anomaly(
            description="High latency detected",
            component="api",
            anomaly_type=AnomalyType.LATENCY,
            severity=AnomalySeverity.HIGH,
            value=500.0,
            threshold=200.0,
        )

        assert anomaly_id is not None
        active = analyzer.get_active_anomalies()
        assert len(active) == 1

    def test_resolve_anomaly(self):
        """Test resolving an anomaly."""
        analyzer = RootCauseAnalyzer("test-service")

        anomaly_id = analyzer.record_anomaly(
            description="Test anomaly",
            component="test",
        )

        analyzer.resolve_anomaly(anomaly_id)

        active = analyzer.get_active_anomalies()
        assert len(active) == 0

    def test_analyze_no_anomalies(self):
        """Test analysis with no anomalies."""
        analyzer = RootCauseAnalyzer("test-service")

        result = analyzer.analyze()

        assert result.probable_cause is None
        assert result.confidence == 0.0

    def test_analyze_single_anomaly(self):
        """Test analysis with single anomaly."""
        analyzer = RootCauseAnalyzer("test-service")

        analyzer.record_anomaly(
            description="Database slow",
            component="postgres",
            anomaly_type=AnomalyType.LATENCY,
            severity=AnomalySeverity.HIGH,
        )

        result = analyzer.analyze()

        assert result.probable_cause is not None
        assert "postgres" in result.affected_components
        assert len(result.anomalies) == 1

    def test_analyze_with_rule_match(self):
        """Test analysis with correlation rule match."""
        analyzer = RootCauseAnalyzer("test-service")

        # Record anomalies matching the database_cascade rule
        analyzer.record_anomaly(
            description="DB errors",
            component="postgres",
            severity=AnomalySeverity.HIGH,
        )
        analyzer.record_anomaly(
            description="API errors",
            component="api",
            severity=AnomalySeverity.HIGH,
        )

        result = analyzer.analyze()

        assert result.probable_cause is not None
        assert result.confidence > 0.5
        assert len(result.suggestions) > 0

    def test_record_event(self):
        """Test recording correlated events."""
        analyzer = RootCauseAnalyzer("test-service")

        anomaly_id = analyzer.record_anomaly(
            description="Error spike",
            component="api",
        )

        analyzer.record_event(
            event_type="deployment",
            description="New version deployed",
            related_anomalies=[anomaly_id],
        )

        result = analyzer.analyze()

        # Event should be correlated
        assert len(result.timeline) > 0

    def test_impact_assessment(self):
        """Test impact assessment."""
        analyzer = RootCauseAnalyzer("test-service")

        analyzer.record_anomaly(
            description="Critical error",
            component="core",
            severity=AnomalySeverity.CRITICAL,
        )

        result = analyzer.analyze()

        assert "Critical" in result.impact_assessment

    def test_custom_rules(self):
        """Test custom correlation rules."""
        custom_rule = CorrelationRule(
            name="custom_test",
            pattern=["custom-component"],
            cause="Custom cause detected",
            suggestions=["Custom suggestion"],
        )

        analyzer = RootCauseAnalyzer(
            "test-service",
            custom_rules=[custom_rule],
        )

        analyzer.record_anomaly(
            description="Custom issue",
            component="custom-component",
        )

        result = analyzer.analyze()

        # Custom rule should match
        assert "Custom" in result.probable_cause or "custom" in str(result.suggestions).lower()


class TestAnomaly:
    """Tests for Anomaly."""

    def test_to_dict(self):
        """Test Anomaly serialization."""
        anomaly = Anomaly(
            anomaly_id="test-1",
            anomaly_type=AnomalyType.ERROR_RATE,
            component="api",
            severity=AnomalySeverity.HIGH,
            description="High error rate",
            value=0.15,
            threshold=0.05,
        )

        data = anomaly.to_dict()
        assert data["anomaly_id"] == "test-1"
        assert data["component"] == "api"
        assert data["severity"] == "high"


class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_root_cause_analyzer(self):
        """Test analyzer singleton per service."""
        analyzer1 = get_root_cause_analyzer("service1")
        analyzer2 = get_root_cause_analyzer("service1")
        analyzer3 = get_root_cause_analyzer("service2")

        assert analyzer1 is analyzer2
        assert analyzer1 is not analyzer3
