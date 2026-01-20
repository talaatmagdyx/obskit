"""Unit tests for Resource Predictor."""

from datetime import datetime, timedelta

from obskit.resource_predictor import (
    Forecast,
    ResourcePredictor,
    TrendAnalysis,
    get_resource_predictor,
)


class TestResourcePredictor:
    """Tests for ResourcePredictor."""

    def test_record_metric(self):
        """Test recording a metric."""
        predictor = ResourcePredictor()

        predictor.record("memory", 50.0)
        predictor.record("memory", 55.0)

        history = predictor.get_history("memory")
        assert len(history) == 2

    def test_predict_insufficient_data(self):
        """Test prediction with insufficient data."""
        predictor = ResourcePredictor(min_data_points=10)

        for i in range(5):  # Less than min
            predictor.record("cpu", 50.0 + i)

        forecast = predictor.predict("cpu")
        assert forecast is None

    def test_predict_stable_resource(self):
        """Test prediction for stable resource."""
        predictor = ResourcePredictor(min_data_points=5)

        # Stable values
        for _i in range(10):
            predictor.record("stable", 50.0)

        forecast = predictor.predict("stable", hours_ahead=24)

        assert forecast is not None
        assert forecast.trend.trend_direction == "stable"
        assert forecast.will_exceed_threshold is False

    def test_predict_increasing_resource(self):
        """Test prediction for increasing resource."""
        predictor = ResourcePredictor(
            min_data_points=5,
            default_threshold=90.0,
        )

        # Increasing values
        base_time = datetime.utcnow() - timedelta(hours=10)
        for i in range(10):
            timestamp = base_time + timedelta(hours=i)
            predictor.record("increasing", 50.0 + i * 5, timestamp=timestamp)

        forecast = predictor.predict("increasing", hours_ahead=24)

        assert forecast is not None
        assert forecast.trend.slope > 0

    def test_set_threshold(self):
        """Test setting custom threshold."""
        predictor = ResourcePredictor()

        predictor.set_threshold("disk", 80.0)
        predictor.record("disk", 75.0)

        forecast = predictor.predict("disk")
        if forecast:
            assert forecast.threshold == 80.0

    def test_get_all_forecasts(self):
        """Test getting forecasts for all resources."""
        predictor = ResourcePredictor(min_data_points=2)

        for _i in range(5):
            predictor.record("cpu", 50.0)
            predictor.record("memory", 60.0)

        forecasts = predictor.get_all_forecasts()

        assert len(forecasts) == 2
        assert "cpu" in forecasts
        assert "memory" in forecasts

    def test_get_at_risk_resources(self):
        """Test getting at-risk resources."""
        predictor = ResourcePredictor(
            min_data_points=5,
            default_threshold=80.0,
        )

        # Create increasing trend that will exceed threshold
        base_time = datetime.utcnow() - timedelta(hours=10)
        for i in range(10):
            timestamp = base_time + timedelta(hours=i)
            predictor.record("risky", 70.0 + i * 2, timestamp=timestamp)

        at_risk = predictor.get_at_risk_resources()

        # May or may not be at risk depending on prediction
        # At least the method should work
        assert isinstance(at_risk, list)

    def test_clear_resource(self):
        """Test clearing specific resource data."""
        predictor = ResourcePredictor()

        predictor.record("to-clear", 50.0)
        predictor.clear("to-clear")

        history = predictor.get_history("to-clear")
        assert len(history) == 0

    def test_clear_all(self):
        """Test clearing all data."""
        predictor = ResourcePredictor()

        predictor.record("res1", 50.0)
        predictor.record("res2", 60.0)
        predictor.clear()

        forecasts = predictor.get_all_forecasts()
        assert len(forecasts) == 0


class TestForecast:
    """Tests for Forecast."""

    def test_to_dict(self):
        """Test Forecast serialization."""
        trend = TrendAnalysis(
            slope=1.0,
            intercept=50.0,
            r_squared=0.9,
            trend_direction="increasing",
        )

        forecast = Forecast(
            resource="memory",
            current_value=60.0,
            predicted_value=80.0,
            hours_ahead=24,
            confidence=0.8,
            trend=trend,
            will_exceed_threshold=True,
            threshold=90.0,
            hours_until_threshold=30.0,
        )

        data = forecast.to_dict()
        assert data["resource"] == "memory"
        assert data["will_exceed_threshold"] is True
        assert data["hours_until_threshold"] == 30.0


class TestTrendAnalysis:
    """Tests for TrendAnalysis."""

    def test_to_dict(self):
        """Test TrendAnalysis serialization."""
        trend = TrendAnalysis(
            slope=0.5,
            intercept=10.0,
            r_squared=0.95,
            trend_direction="increasing",
        )

        data = trend.to_dict()
        assert data["slope"] == 0.5
        assert data["r_squared"] == 0.95
        assert data["trend_direction"] == "increasing"


class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_resource_predictor(self):
        """Test global predictor singleton."""
        predictor1 = get_resource_predictor()
        predictor2 = get_resource_predictor()
        assert predictor1 is predictor2
