"""
Root Cause Analyzer
===================

Automated root cause analysis for incidents.

Features:
- Anomaly correlation
- Timeline reconstruction
- Dependency impact analysis
- Suggested root causes

Example:
    from obskit.root_cause import RootCauseAnalyzer

    analyzer = RootCauseAnalyzer()

    # Record anomalies
    analyzer.record_anomaly("high_latency", component="api", severity="high")
    analyzer.record_anomaly("db_connection_errors", component="postgres")

    # Get analysis
    analysis = analyzer.analyze()
    print(f"Probable cause: {analysis.probable_cause}")
"""

import threading
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

ANOMALIES_DETECTED = Counter(
    "root_cause_anomalies_total", "Total anomalies detected", ["component", "severity"]
)

ANALYSIS_PERFORMED = Counter("root_cause_analysis_total", "Total root cause analyses", ["result"])

ACTIVE_ANOMALIES = Gauge("root_cause_active_anomalies", "Currently active anomalies")


# =============================================================================
# Enums and Data Classes
# =============================================================================


class AnomalySeverity(Enum):
    """Anomaly severity levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AnomalyType(Enum):
    """Types of anomalies."""

    LATENCY = "latency"
    ERROR_RATE = "error_rate"
    THROUGHPUT = "throughput"
    RESOURCE = "resource"
    DEPENDENCY = "dependency"
    CUSTOM = "custom"


@dataclass
class Anomaly:
    """An observed anomaly."""

    anomaly_id: str
    anomaly_type: AnomalyType
    component: str
    severity: AnomalySeverity
    description: str
    value: float | None = None
    threshold: float | None = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    resolved: bool = False
    resolved_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "anomaly_id": self.anomaly_id,
            "anomaly_type": self.anomaly_type.value,
            "component": self.component,
            "severity": self.severity.value,
            "description": self.description,
            "value": self.value,
            "threshold": self.threshold,
            "timestamp": self.timestamp.isoformat(),
            "resolved": self.resolved,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "metadata": self.metadata,
        }


@dataclass
class CorrelatedEvent:
    """An event correlated with anomalies."""

    event_type: str
    timestamp: datetime
    description: str
    correlation_score: float
    related_anomalies: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat(),
            "description": self.description,
            "correlation_score": self.correlation_score,
            "related_anomalies": self.related_anomalies,
        }


@dataclass
class RootCauseResult:
    """Result of root cause analysis."""

    analysis_id: str
    probable_cause: str | None
    confidence: float
    affected_components: list[str]
    anomalies: list[Anomaly]
    timeline: list[CorrelatedEvent]
    suggestions: list[str]
    impact_assessment: str
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "analysis_id": self.analysis_id,
            "probable_cause": self.probable_cause,
            "confidence": self.confidence,
            "affected_components": self.affected_components,
            "anomalies": [a.to_dict() for a in self.anomalies],
            "timeline": [e.to_dict() for e in self.timeline],
            "suggestions": self.suggestions,
            "impact_assessment": self.impact_assessment,
            "timestamp": self.timestamp.isoformat(),
        }


# =============================================================================
# Correlation Rules
# =============================================================================


@dataclass
class CorrelationRule:
    """A rule for correlating anomalies."""

    name: str
    pattern: list[str]  # Component patterns
    cause: str
    suggestions: list[str]

    def matches(self, components: set[str]) -> bool:
        """Check if components match the pattern."""
        for pattern in self.pattern:
            if not any(pattern in c for c in components):
                return False
        return True


DEFAULT_RULES = [
    CorrelationRule(
        name="database_cascade",
        pattern=["postgres", "api"],
        cause="Database connectivity issues causing API failures",
        suggestions=[
            "Check database connection pool",
            "Verify database server health",
            "Review connection timeout settings",
        ],
    ),
    CorrelationRule(
        name="cache_miss_storm",
        pattern=["redis", "database"],
        cause="Cache failures causing database overload",
        suggestions=[
            "Check Redis connectivity",
            "Review cache eviction policies",
            "Consider cache warming",
        ],
    ),
    CorrelationRule(
        name="upstream_failure",
        pattern=["external", "api"],
        cause="External dependency failure impacting API",
        suggestions=[
            "Check external service status",
            "Review circuit breaker state",
            "Consider fallback responses",
        ],
    ),
    CorrelationRule(
        name="resource_exhaustion",
        pattern=["memory", "cpu"],
        cause="Resource exhaustion causing service degradation",
        suggestions=[
            "Scale up resources",
            "Check for memory leaks",
            "Review resource limits",
        ],
    ),
]


# =============================================================================
# Root Cause Analyzer
# =============================================================================


class RootCauseAnalyzer:
    """
    Automated root cause analysis.

    Parameters
    ----------
    service_name : str
        Name of the service
    correlation_window_minutes : int
        Time window for correlating anomalies
    custom_rules : list, optional
        Custom correlation rules
    """

    def __init__(
        self,
        service_name: str = "default",
        correlation_window_minutes: int = 15,
        custom_rules: list[CorrelationRule] | None = None,
    ):
        self.service_name = service_name
        self.correlation_window_minutes = correlation_window_minutes
        self.rules = DEFAULT_RULES + (custom_rules or [])

        self._anomalies: dict[str, Anomaly] = {}
        self._events: list[CorrelatedEvent] = []
        self._analysis_counter = 0
        self._lock = threading.Lock()

    def record_anomaly(
        self,
        description: str,
        component: str,
        anomaly_type: AnomalyType | str = AnomalyType.CUSTOM,
        severity: AnomalySeverity | str = AnomalySeverity.MEDIUM,
        value: float | None = None,
        threshold: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """
        Record an anomaly.

        Parameters
        ----------
        description : str
            Anomaly description
        component : str
            Affected component
        anomaly_type : AnomalyType or str
            Type of anomaly
        severity : AnomalySeverity or str
            Severity level
        value : float, optional
            Observed value
        threshold : float, optional
            Threshold that was breached
        metadata : dict, optional
            Additional data

        Returns
        -------
        str
            Anomaly ID
        """
        if isinstance(anomaly_type, str):
            anomaly_type = AnomalyType(anomaly_type)
        if isinstance(severity, str):
            severity = AnomalySeverity(severity)

        anomaly_id = f"anomaly-{len(self._anomalies) + 1}-{int(datetime.utcnow().timestamp())}"

        anomaly = Anomaly(
            anomaly_id=anomaly_id,
            anomaly_type=anomaly_type,
            component=component,
            severity=severity,
            description=description,
            value=value,
            threshold=threshold,
            metadata=metadata or {},
        )

        with self._lock:
            self._anomalies[anomaly_id] = anomaly

        ANOMALIES_DETECTED.labels(component=component, severity=severity.value).inc()

        ACTIVE_ANOMALIES.set(len([a for a in self._anomalies.values() if not a.resolved]))

        logger.warning(
            "anomaly_detected",
            anomaly_id=anomaly_id,
            component=component,
            severity=severity.value,
            description=description,
        )

        return anomaly_id

    def resolve_anomaly(self, anomaly_id: str):
        """Mark an anomaly as resolved."""
        with self._lock:
            if anomaly_id in self._anomalies:
                self._anomalies[anomaly_id].resolved = True
                self._anomalies[anomaly_id].resolved_at = datetime.utcnow()

        ACTIVE_ANOMALIES.set(len([a for a in self._anomalies.values() if not a.resolved]))

    def record_event(
        self,
        event_type: str,
        description: str,
        related_anomalies: list[str] | None = None,
    ):
        """
        Record a correlated event.

        Parameters
        ----------
        event_type : str
            Type of event (e.g., "deployment", "config_change")
        description : str
            Event description
        related_anomalies : list, optional
            Related anomaly IDs
        """
        event = CorrelatedEvent(
            event_type=event_type,
            timestamp=datetime.utcnow(),
            description=description,
            correlation_score=0.0,
            related_anomalies=related_anomalies or [],
        )

        with self._lock:
            self._events.append(event)
            if len(self._events) > 1000:
                self._events = self._events[-1000:]

    def analyze(
        self,
        window_minutes: int | None = None,
    ) -> RootCauseResult:
        """
        Perform root cause analysis.

        Parameters
        ----------
        window_minutes : int, optional
            Analysis window (defaults to correlation_window_minutes)

        Returns
        -------
        RootCauseResult
        """
        window = window_minutes or self.correlation_window_minutes
        cutoff = datetime.utcnow() - timedelta(minutes=window)

        with self._lock:
            # Get recent anomalies
            recent_anomalies = [
                a for a in self._anomalies.values() if a.timestamp >= cutoff and not a.resolved
            ]

            # Get recent events
            recent_events = [e for e in self._events if e.timestamp >= cutoff]

            self._analysis_counter += 1
            analysis_id = f"analysis-{self._analysis_counter}"

        if not recent_anomalies:
            ANALYSIS_PERFORMED.labels(result="no_anomalies").inc()
            return RootCauseResult(
                analysis_id=analysis_id,
                probable_cause=None,
                confidence=0.0,
                affected_components=[],
                anomalies=[],
                timeline=[],
                suggestions=["No active anomalies detected"],
                impact_assessment="No impact",
            )

        # Extract affected components
        affected_components = list({a.component for a in recent_anomalies})

        # Find matching rules
        components_set = set(affected_components)
        matched_rules = [r for r in self.rules if r.matches(components_set)]

        # Determine probable cause (no pre-initialization to avoid variable redefinition)
        if matched_rules:
            # Use the first matching rule
            best_rule = matched_rules[0]
            probable_cause: str | None = best_rule.cause
            confidence = 0.7 + (len(matched_rules) - 1) * 0.1
            suggestions: list[str] = best_rule.suggestions
        elif len(recent_anomalies) == 1:
            # Heuristic analysis for single anomaly
            anomaly = recent_anomalies[0]
            probable_cause = (
                f"Isolated {anomaly.anomaly_type.value} issue in {anomaly.component}"
            )
            confidence = 0.5
            suggestions = [f"Investigate {anomaly.component} directly"]
        else:
            # Multiple anomalies, look for common patterns
            severities = [a.severity for a in recent_anomalies]
            if AnomalySeverity.CRITICAL in severities:
                critical = [
                    a for a in recent_anomalies if a.severity == AnomalySeverity.CRITICAL
                ]
                probable_cause = (
                    f"Critical issue in {critical[0].component} with cascade effects"
                )
                confidence = 0.6
                suggestions = [
                    f"Prioritize {critical[0].component}",
                    "Check downstream dependencies",
                ]
            else:
                probable_cause = "Multiple correlated issues detected"
                confidence = 0.4
                suggestions = ["Review all affected components"]

        # Correlate events
        for event in recent_events:
            correlation_score = self._calculate_event_correlation(event, recent_anomalies)
            event.correlation_score = correlation_score

            # Link related anomalies
            for anomaly in recent_anomalies:
                time_diff = abs((event.timestamp - anomaly.timestamp).total_seconds())
                if time_diff < 300:  # Within 5 minutes
                    if anomaly.anomaly_id not in event.related_anomalies:
                        event.related_anomalies.append(anomaly.anomaly_id)

        # Sort events by correlation score
        recent_events.sort(key=lambda e: e.correlation_score, reverse=True)

        # Impact assessment
        impact = self._assess_impact(recent_anomalies)

        ANALYSIS_PERFORMED.labels(result="cause_found" if probable_cause else "no_cause").inc()

        logger.info(
            "root_cause_analysis_complete",
            analysis_id=analysis_id,
            probable_cause=probable_cause,
            confidence=confidence,
            affected_components=affected_components,
            anomaly_count=len(recent_anomalies),
        )

        return RootCauseResult(
            analysis_id=analysis_id,
            probable_cause=probable_cause,
            confidence=min(confidence, 1.0),
            affected_components=affected_components,
            anomalies=recent_anomalies,
            timeline=recent_events[:20],
            suggestions=suggestions,
            impact_assessment=impact,
        )

    def _calculate_event_correlation(
        self,
        event: CorrelatedEvent,
        anomalies: list[Anomaly],
    ) -> float:
        """Calculate correlation score between event and anomalies."""
        if not anomalies:
            return 0.0

        score = 0.0

        for anomaly in anomalies:
            # Time proximity (closer = higher score)
            time_diff = abs((event.timestamp - anomaly.timestamp).total_seconds())
            if time_diff < 60:
                score += 0.5
            elif time_diff < 300:
                score += 0.3
            elif time_diff < 600:
                score += 0.1

            # Event type relevance
            if event.event_type in ["deployment", "config_change", "restart"]:
                score += 0.2

        return min(score / len(anomalies), 1.0)

    def _assess_impact(self, anomalies: list[Anomaly]) -> str:
        """Assess the impact of anomalies."""
        if not anomalies:
            return "No impact"

        critical_count = sum(1 for a in anomalies if a.severity == AnomalySeverity.CRITICAL)
        high_count = sum(1 for a in anomalies if a.severity == AnomalySeverity.HIGH)

        if critical_count > 0:
            return f"Critical: {critical_count} critical anomalies affecting service"
        elif high_count > 2:
            return f"High: Multiple high-severity issues ({high_count})"
        elif high_count > 0:
            return "Medium: Some high-severity issues detected"
        else:
            return "Low: Minor anomalies detected"

    def get_active_anomalies(self) -> list[Anomaly]:
        """Get all active (unresolved) anomalies."""
        with self._lock:
            return [a for a in self._anomalies.values() if not a.resolved]

    def clear_resolved(self, older_than_hours: int = 24):
        """Clear old resolved anomalies."""
        cutoff = datetime.utcnow() - timedelta(hours=older_than_hours)

        with self._lock:
            to_remove = [
                aid
                for aid, a in self._anomalies.items()
                if a.resolved and a.resolved_at and a.resolved_at < cutoff
            ]
            for aid in to_remove:
                del self._anomalies[aid]


# =============================================================================
# Singleton
# =============================================================================

_analyzers: dict[str, RootCauseAnalyzer] = {}
_analyzer_lock = threading.Lock()


def get_root_cause_analyzer(service_name: str = "default", **kwargs) -> RootCauseAnalyzer:
    """Get or create a root cause analyzer."""
    if service_name not in _analyzers:
        with _analyzer_lock:
            if service_name not in _analyzers:
                _analyzers[service_name] = RootCauseAnalyzer(service_name, **kwargs)

    return _analyzers[service_name]
