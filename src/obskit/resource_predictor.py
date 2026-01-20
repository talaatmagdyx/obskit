"""
Resource Predictor
==================

Predict future resource needs based on trends.

Features:
- Time series analysis
- Trend detection
- Capacity forecasting
- Alert on predicted exhaustion

Example:
    from obskit.resource_predictor import ResourcePredictor

    predictor = ResourcePredictor()

    # Record metrics
    predictor.record("memory_usage", 75.0)
    predictor.record("memory_usage", 76.5)

    # Get prediction
    forecast = predictor.predict("memory_usage", hours_ahead=24)
    if forecast.will_exceed_threshold:
        alert("Memory will exceed 90% in 24 hours")
"""

import statistics
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from prometheus_client import Gauge

from obskit.logging import get_logger

logger = get_logger(__name__)


# =============================================================================
# Prometheus Metrics
# =============================================================================

PREDICTION_VALUE = Gauge(
    "resource_predictor_forecast", "Predicted resource value", ["resource", "hours_ahead"]
)

PREDICTION_EXHAUSTION_HOURS = Gauge(
    "resource_predictor_exhaustion_hours",
    "Hours until resource exhaustion (-1 if not exhausting)",
    ["resource"],
)

PREDICTION_TREND = Gauge(
    "resource_predictor_trend",
    "Trend direction (-1=decreasing, 0=stable, 1=increasing)",
    ["resource"],
)


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class DataPoint:
    """A recorded data point."""

    timestamp: datetime
    value: float


@dataclass
class TrendAnalysis:
    """Analysis of a metric's trend."""

    slope: float  # Change per hour
    intercept: float
    r_squared: float  # Goodness of fit
    trend_direction: str  # "increasing", "decreasing", "stable"

    def to_dict(self) -> dict[str, Any]:
        return {
            "slope": self.slope,
            "intercept": self.intercept,
            "r_squared": self.r_squared,
            "trend_direction": self.trend_direction,
        }


@dataclass
class Forecast:
    """A resource forecast."""

    resource: str
    current_value: float
    predicted_value: float
    hours_ahead: int
    confidence: float
    trend: TrendAnalysis
    will_exceed_threshold: bool
    threshold: float
    hours_until_threshold: float | None
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "resource": self.resource,
            "current_value": self.current_value,
            "predicted_value": self.predicted_value,
            "hours_ahead": self.hours_ahead,
            "confidence": self.confidence,
            "trend": self.trend.to_dict(),
            "will_exceed_threshold": self.will_exceed_threshold,
            "threshold": self.threshold,
            "hours_until_threshold": self.hours_until_threshold,
            "timestamp": self.timestamp.isoformat(),
        }


# =============================================================================
# Resource Predictor
# =============================================================================


class ResourcePredictor:
    """
    Predict resource usage trends.

    Parameters
    ----------
    max_history_hours : int
        Maximum hours of history to keep
    min_data_points : int
        Minimum points for prediction
    default_threshold : float
        Default warning threshold (percentage)
    """

    def __init__(
        self,
        max_history_hours: int = 168,  # 1 week
        min_data_points: int = 10,
        default_threshold: float = 90.0,
    ):
        self.max_history_hours = max_history_hours
        self.min_data_points = min_data_points
        self.default_threshold = default_threshold

        self._data: dict[str, list[DataPoint]] = {}
        self._thresholds: dict[str, float] = {}
        self._lock = threading.Lock()

    def record(self, resource: str, value: float, timestamp: datetime | None = None):
        """
        Record a resource metric.

        Parameters
        ----------
        resource : str
            Resource name
        value : float
            Current value
        timestamp : datetime, optional
            Timestamp (defaults to now)
        """
        point = DataPoint(
            timestamp=timestamp or datetime.utcnow(),
            value=value,
        )

        with self._lock:
            if resource not in self._data:
                self._data[resource] = []

            self._data[resource].append(point)

            # Trim old data
            cutoff = datetime.utcnow() - timedelta(hours=self.max_history_hours)
            self._data[resource] = [p for p in self._data[resource] if p.timestamp > cutoff]

    def set_threshold(self, resource: str, threshold: float):
        """Set warning threshold for a resource."""
        with self._lock:
            self._thresholds[resource] = threshold

    def predict(
        self,
        resource: str,
        hours_ahead: int = 24,
    ) -> Forecast | None:
        """
        Predict future resource value.

        Parameters
        ----------
        resource : str
            Resource name
        hours_ahead : int
            Hours to forecast

        Returns
        -------
        Forecast or None
        """
        with self._lock:
            if resource not in self._data:
                return None

            points = self._data[resource]
            threshold = self._thresholds.get(resource, self.default_threshold)

        if len(points) < self.min_data_points:
            return None

        # Calculate trend using linear regression
        trend = self._calculate_trend(points)

        if trend is None:
            return None

        # Current value (latest)
        current_value = points[-1].value

        # Predicted value
        predicted_value = current_value + (trend.slope * hours_ahead)

        # Check threshold
        will_exceed = predicted_value >= threshold

        # Calculate hours until threshold
        hours_until = None
        if trend.slope > 0 and current_value < threshold:
            hours_until = (threshold - current_value) / trend.slope

        # Confidence based on R-squared and data points
        confidence = trend.r_squared * min(1.0, len(points) / 100)

        forecast = Forecast(
            resource=resource,
            current_value=current_value,
            predicted_value=predicted_value,
            hours_ahead=hours_ahead,
            confidence=confidence,
            trend=trend,
            will_exceed_threshold=will_exceed,
            threshold=threshold,
            hours_until_threshold=hours_until,
        )

        # Update metrics
        PREDICTION_VALUE.labels(resource=resource, hours_ahead=str(hours_ahead)).set(
            predicted_value
        )

        PREDICTION_EXHAUSTION_HOURS.labels(resource=resource).set(
            hours_until if hours_until is not None else -1
        )

        trend_value = (
            1
            if trend.trend_direction == "increasing"
            else (-1 if trend.trend_direction == "decreasing" else 0)
        )
        PREDICTION_TREND.labels(resource=resource).set(trend_value)

        if will_exceed:
            logger.warning(
                "resource_threshold_predicted",
                resource=resource,
                predicted_value=predicted_value,
                threshold=threshold,
                hours_ahead=hours_ahead,
                hours_until_threshold=hours_until,
            )

        return forecast

    def _calculate_trend(self, points: list[DataPoint]) -> TrendAnalysis | None:
        """Calculate trend using linear regression."""
        if len(points) < 2:
            return None

        # Convert to hours since first point
        first_time = points[0].timestamp
        x = [(p.timestamp - first_time).total_seconds() / 3600 for p in points]
        y = [p.value for p in points]

        n = len(points)

        # Calculate means
        x_mean = statistics.mean(x)
        y_mean = statistics.mean(y)

        # Calculate slope and intercept
        numerator = sum((x[i] - x_mean) * (y[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))

        if denominator == 0:
            return TrendAnalysis(
                slope=0,
                intercept=y_mean,
                r_squared=0,
                trend_direction="stable",
            )

        slope = numerator / denominator
        intercept = y_mean - slope * x_mean

        # Calculate R-squared
        y_pred = [slope * x[i] + intercept for i in range(n)]
        ss_res = sum((y[i] - y_pred[i]) ** 2 for i in range(n))
        ss_tot = sum((y[i] - y_mean) ** 2 for i in range(n))

        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

        # Determine trend direction
        if abs(slope) < 0.01:  # Less than 0.01 per hour
            direction = "stable"
        elif slope > 0:
            direction = "increasing"
        else:
            direction = "decreasing"

        return TrendAnalysis(
            slope=slope,
            intercept=intercept,
            r_squared=max(0, min(1, r_squared)),
            trend_direction=direction,
        )

    def get_all_forecasts(self, hours_ahead: int = 24) -> dict[str, Forecast]:
        """Get forecasts for all tracked resources."""
        with self._lock:
            resources = list(self._data.keys())

        forecasts = {}
        for resource in resources:
            forecast = self.predict(resource, hours_ahead)
            if forecast:
                forecasts[resource] = forecast

        return forecasts

    def get_at_risk_resources(self, hours_ahead: int = 24) -> list[Forecast]:
        """Get resources that will exceed threshold."""
        forecasts = self.get_all_forecasts(hours_ahead)
        return [f for f in forecasts.values() if f.will_exceed_threshold]

    def get_history(self, resource: str, hours: int = 24) -> list[DataPoint]:
        """Get historical data points."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        with self._lock:
            if resource not in self._data:
                return []

            return [p for p in self._data[resource] if p.timestamp > cutoff]

    def clear(self, resource: str | None = None):
        """Clear data."""
        with self._lock:
            if resource:
                if resource in self._data:
                    del self._data[resource]
            else:
                self._data.clear()


# =============================================================================
# Singleton
# =============================================================================

_predictor: ResourcePredictor | None = None
_predictor_lock = threading.Lock()


def get_resource_predictor(**kwargs) -> ResourcePredictor:
    """Get or create the global resource predictor."""
    global _predictor

    if _predictor is None:
        with _predictor_lock:
            if _predictor is None:
                _predictor = ResourcePredictor(**kwargs)

    return _predictor
