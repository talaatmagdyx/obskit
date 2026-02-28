"""
SLA Breach Predictor
====================

Predict SLA breaches before they happen.

Features:
- Trend-based prediction
- Early warning alerts
- Risk assessment
- Mitigation suggestions

Example:
    from obskit.sla_predictor import SLAPredictor

    predictor = SLAPredictor()
    predictor.set_sla("response_time", target_ms=200, percentile=95)

    # Record metrics
    predictor.record("response_time", 180)
    predictor.record("response_time", 195)

    # Check prediction
    risk = predictor.assess_risk("response_time")
    if risk.breach_likely:
        print(f"SLA breach predicted in {risk.hours_until_breach} hours")
"""

import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from prometheus_client import Counter, Gauge

from obskit.logging import get_logger

logger = get_logger(__name__)


# =============================================================================
# Prometheus Metrics
# =============================================================================

SLA_RISK_SCORE = Gauge("sla_risk_score", "SLA breach risk score (0-100)", ["sla_name"])

SLA_PREDICTED_BREACH_HOURS = Gauge(
    "sla_predicted_breach_hours", "Predicted hours until SLA breach (-1 if no breach)", ["sla_name"]
)

SLA_CURRENT_VALUE = Gauge("sla_current_value", "Current SLA metric value", ["sla_name"])

SLA_BREACH_ALERTS = Counter(
    "sla_breach_alerts_total", "Total SLA breach warnings", ["sla_name", "severity"]
)


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class SLADefinition:
    """Definition of an SLA."""

    name: str
    target_value: float
    percentile: int = 95  # P95 by default
    comparison: str = "less_than"  # or "greater_than"
    window_hours: int = 1
    description: str = ""

    def is_breached(self, value: float) -> bool:
        """Check if value breaches SLA."""
        if self.comparison == "less_than":
            return value > self.target_value
        else:
            return value < self.target_value

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "target_value": self.target_value,
            "percentile": self.percentile,
            "comparison": self.comparison,
            "window_hours": self.window_hours,
            "description": self.description,
        }


@dataclass
class RiskAssessment:
    """SLA breach risk assessment."""

    sla_name: str
    risk_score: float  # 0-100
    breach_likely: bool
    hours_until_breach: float | None
    current_value: float
    target_value: float
    trend: str  # "improving", "degrading", "stable"
    trend_slope: float
    confidence: float
    suggestions: list[str]
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sla_name": self.sla_name,
            "risk_score": self.risk_score,
            "breach_likely": self.breach_likely,
            "hours_until_breach": self.hours_until_breach,
            "current_value": self.current_value,
            "target_value": self.target_value,
            "trend": self.trend,
            "trend_slope": self.trend_slope,
            "confidence": self.confidence,
            "suggestions": self.suggestions,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class DataPoint:
    """A recorded data point."""

    timestamp: datetime
    value: float


# =============================================================================
# SLA Predictor
# =============================================================================


class SLAPredictor:
    """
    Predict SLA breaches.

    Parameters
    ----------
    warning_threshold_hours : float
        Hours before breach to trigger warning
    max_history_hours : int
        Maximum hours of data to keep
    on_warning : callable, optional
        Callback for breach warnings
    """

    def __init__(
        self,
        warning_threshold_hours: float = 4.0,
        max_history_hours: int = 168,  # 1 week
        on_warning: Callable[[RiskAssessment], None] | None = None,
    ):
        self.warning_threshold_hours = warning_threshold_hours
        self.max_history_hours = max_history_hours
        self.on_warning = on_warning

        self._slas: dict[str, SLADefinition] = {}
        self._data: dict[str, list[DataPoint]] = {}
        self._lock = threading.Lock()

    def set_sla(
        self,
        name: str,
        target_value: float,
        percentile: int = 95,
        comparison: str = "less_than",
        window_hours: int = 1,
        description: str = "",
    ):
        """
        Define an SLA.

        Parameters
        ----------
        name : str
            SLA name
        target_value : float
            Target value (e.g., 200 for 200ms latency)
        percentile : int
            Percentile to measure (e.g., 95 for P95)
        comparison : str
            "less_than" or "greater_than"
        window_hours : int
            Measurement window
        description : str
            SLA description
        """
        sla = SLADefinition(
            name=name,
            target_value=target_value,
            percentile=percentile,
            comparison=comparison,
            window_hours=window_hours,
            description=description,
        )

        with self._lock:
            self._slas[name] = sla
            if name not in self._data:
                self._data[name] = []

        logger.info(
            "sla_defined",
            name=name,
            target=target_value,
            percentile=percentile,
        )

    def record(
        self,
        sla_name: str,
        value: float,
        timestamp: datetime | None = None,
    ):
        """
        Record a metric value.

        Parameters
        ----------
        sla_name : str
            SLA name
        value : float
            Metric value
        timestamp : datetime, optional
            Observation time
        """
        point = DataPoint(
            timestamp=timestamp or datetime.utcnow(),
            value=value,
        )

        with self._lock:
            if sla_name not in self._data:
                self._data[sla_name] = []

            self._data[sla_name].append(point)

            # Trim old data
            cutoff = datetime.utcnow() - timedelta(hours=self.max_history_hours)
            self._data[sla_name] = [p for p in self._data[sla_name] if p.timestamp > cutoff]

        SLA_CURRENT_VALUE.labels(sla_name=sla_name).set(value)

    def assess_risk(self, sla_name: str) -> RiskAssessment | None:
        """
        Assess breach risk for an SLA.

        Parameters
        ----------
        sla_name : str
            SLA name

        Returns
        -------
        RiskAssessment or None
        """
        with self._lock:
            if sla_name not in self._slas:
                return None

            sla = self._slas[sla_name]
            points = self._data.get(sla_name, [])

        if len(points) < 5:
            return RiskAssessment(
                sla_name=sla_name,
                risk_score=0,
                breach_likely=False,
                hours_until_breach=None,
                current_value=points[-1].value if points else 0,
                target_value=sla.target_value,
                trend="unknown",
                trend_slope=0,
                confidence=0,
                suggestions=["Insufficient data for prediction"],
            )

        # Calculate current percentile value
        values = [p.value for p in points]
        current_percentile = self._calculate_percentile(values, sla.percentile)

        # Calculate trend
        trend_slope, trend_direction = self._calculate_trend(points)

        # Calculate risk score
        risk_score = self._calculate_risk_score(
            current_percentile, sla.target_value, trend_slope, sla.comparison
        )

        # Predict breach time
        hours_until_breach = None
        breach_likely = False

        if sla.comparison == "less_than":
            if current_percentile >= sla.target_value:
                breach_likely = True
                hours_until_breach = 0
            elif trend_slope > 0:
                remaining = sla.target_value - current_percentile
                hours_until_breach = remaining / trend_slope if trend_slope > 0.01 else None
                breach_likely = hours_until_breach is not None and hours_until_breach < 24
        else:
            if current_percentile <= sla.target_value:
                breach_likely = True
                hours_until_breach = 0
            elif trend_slope < 0:
                remaining = current_percentile - sla.target_value
                hours_until_breach = (
                    remaining / abs(trend_slope) if abs(trend_slope) > 0.01 else None
                )
                breach_likely = hours_until_breach is not None and hours_until_breach < 24

        # Generate suggestions
        suggestions = self._generate_suggestions(
            sla, current_percentile, trend_direction, breach_likely
        )

        # Calculate confidence based on data points
        confidence = min(1.0, len(points) / 100)

        assessment = RiskAssessment(
            sla_name=sla_name,
            risk_score=risk_score,
            breach_likely=breach_likely,
            hours_until_breach=hours_until_breach,
            current_value=current_percentile,
            target_value=sla.target_value,
            trend=trend_direction,
            trend_slope=trend_slope,
            confidence=confidence,
            suggestions=suggestions,
        )

        # Update metrics
        SLA_RISK_SCORE.labels(sla_name=sla_name).set(risk_score)
        SLA_PREDICTED_BREACH_HOURS.labels(sla_name=sla_name).set(
            hours_until_breach if hours_until_breach is not None else -1
        )

        # Trigger warning if needed
        if breach_likely:
            severity = "critical" if hours_until_breach and hours_until_breach < 1 else "warning"
            SLA_BREACH_ALERTS.labels(sla_name=sla_name, severity=severity).inc()

            logger.warning(
                "sla_breach_predicted",
                sla_name=sla_name,
                hours_until_breach=hours_until_breach,
                risk_score=risk_score,
                current=current_percentile,
                target=sla.target_value,
            )

            if self.on_warning:
                self.on_warning(assessment)

        return assessment

    def _calculate_percentile(self, values: list[float], percentile: int) -> float:
        """Calculate percentile of values."""
        if not values:
            return 0.0

        sorted_values = sorted(values)
        idx = int(len(sorted_values) * percentile / 100)
        idx = min(idx, len(sorted_values) - 1)
        return sorted_values[idx]

    def _calculate_trend(self, points: list[DataPoint]) -> tuple:
        """Calculate trend from data points."""
        if len(points) < 2:
            return 0.0, "stable"

        # Use last N points for trend
        recent = points[-min(100, len(points)) :]

        # Convert to hours since first point
        first_time = recent[0].timestamp
        x = [(p.timestamp - first_time).total_seconds() / 3600 for p in recent]
        y = [p.value for p in recent]

        n = len(recent)
        x_mean = sum(x) / n
        y_mean = sum(y) / n

        # Calculate slope
        numerator = sum((x[i] - x_mean) * (y[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))

        if denominator == 0:
            return 0.0, "stable"

        slope = numerator / denominator

        # Determine direction
        if abs(slope) < 0.1:
            direction = "stable"
        elif slope > 0:
            direction = "degrading"
        else:
            direction = "improving"

        return slope, direction

    def _calculate_risk_score(
        self,
        current: float,
        target: float,
        slope: float,
        comparison: str,
    ) -> float:
        """Calculate risk score (0-100)."""
        # Base score from current vs target
        if comparison == "less_than":
            ratio = current / target if target > 0 else 1
        else:
            ratio = target / current if current > 0 else 1

        base_score = min(100, max(0, ratio * 50))

        # Adjust for trend
        if comparison == "less_than":
            trend_adjustment = slope * 10 if slope > 0 else 0
        else:
            trend_adjustment = abs(slope) * 10 if slope < 0 else 0

        total_score = min(100, base_score + trend_adjustment)

        return round(total_score, 1)

    def _generate_suggestions(
        self,
        sla: SLADefinition,
        current: float,
        trend: str,
        breach_likely: bool,
    ) -> list[str]:
        """Generate mitigation suggestions."""
        suggestions = []

        if breach_likely:
            suggestions.append("URGENT: Immediate action required to prevent SLA breach")

        if trend == "degrading":
            suggestions.append("Performance is degrading - investigate recent changes")
            suggestions.append("Consider scaling up resources")
            suggestions.append("Check for increased load or traffic patterns")

        if current >= sla.target_value * 0.8:
            suggestions.append("Close to SLA threshold - proactive optimization recommended")

        if sla.name.lower() in ["latency", "response_time", "response"]:
            suggestions.append("Review database query performance")
            suggestions.append("Check cache hit rates")
            suggestions.append("Consider request optimization")

        return suggestions

    def get_all_risks(self) -> dict[str, RiskAssessment]:
        """Assess risk for all SLAs."""
        results = {}

        with self._lock:
            sla_names = list(self._slas.keys())

        for name in sla_names:
            assessment = self.assess_risk(name)
            if assessment:
                results[name] = assessment

        return results

    def get_at_risk_slas(self, threshold: float = 50.0) -> list[RiskAssessment]:
        """Get SLAs above risk threshold."""
        all_risks = self.get_all_risks()
        return [r for r in all_risks.values() if r.risk_score >= threshold]


# =============================================================================
# Singleton
# =============================================================================

_predictor: SLAPredictor | None = None
_predictor_lock = threading.Lock()


def get_sla_predictor(**kwargs) -> SLAPredictor:
    """Get or create the global SLA predictor."""
    global _predictor

    if _predictor is None:
        with _predictor_lock:
            if _predictor is None:
                _predictor = SLAPredictor(**kwargs)

    return _predictor
