"""
Alert Deduplication
===================

Deduplicate alerts to prevent alert storms.

Features:
- Time-based deduplication
- Count-based aggregation
- Alert fingerprinting
- Suppression windows

Example:
    from obskit.alert_dedup import AlertDeduplicator

    dedup = AlertDeduplicator(window_minutes=15)

    for error in errors:
        if dedup.should_alert("high_error_rate", severity="critical"):
            send_alert()
"""

import hashlib
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

ALERTS_TOTAL = Counter("alerts_total", "Total alerts triggered", ["alert_name", "severity"])

ALERTS_DEDUPLICATED = Counter(
    "alerts_deduplicated_total", "Alerts suppressed by deduplication", ["alert_name", "severity"]
)

ALERTS_ACTIVE = Gauge("alerts_active", "Currently active alert groups", ["alert_name"])

ALERT_GROUP_SIZE = Gauge(
    "alert_group_occurrences", "Number of occurrences in alert group", ["alert_name", "severity"]
)


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class AlertRecord:
    """Record of an alert."""

    alert_name: str
    severity: str
    first_seen: datetime
    last_seen: datetime
    count: int = 1
    fingerprint: str = ""
    labels: dict[str, str] = field(default_factory=dict)
    last_sent: datetime | None = None
    suppressed_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "alert_name": self.alert_name,
            "severity": self.severity,
            "first_seen": self.first_seen.isoformat(),
            "last_seen": self.last_seen.isoformat(),
            "count": self.count,
            "fingerprint": self.fingerprint,
            "labels": self.labels,
            "last_sent": self.last_sent.isoformat() if self.last_sent else None,
            "suppressed_count": self.suppressed_count,
        }


@dataclass
class DeduplicationConfig:
    """Configuration for deduplication."""

    window_minutes: int = 15
    max_alerts_per_window: int = 3
    aggregation_key_labels: list[str] = field(default_factory=list)
    severity_cooldowns: dict[str, int] = field(
        default_factory=lambda: {
            "critical": 5,
            "warning": 15,
            "info": 60,
        }
    )


# =============================================================================
# Alert Deduplicator
# =============================================================================


class AlertDeduplicator:
    """
    Deduplicate alerts to prevent storm.

    Parameters
    ----------
    window_minutes : int
        Deduplication window
    max_alerts_per_window : int
        Maximum alerts to send per window
    severity_cooldowns : dict
        Cooldown minutes per severity
    on_aggregated : callable, optional
        Callback when alert is aggregated (not sent)
    """

    def __init__(
        self,
        window_minutes: int = 15,
        max_alerts_per_window: int = 3,
        severity_cooldowns: dict[str, int] | None = None,
        on_aggregated: Callable[[AlertRecord], None] | None = None,
    ):
        self.window_minutes = window_minutes
        self.max_alerts_per_window = max_alerts_per_window
        self.severity_cooldowns = severity_cooldowns or {
            "critical": 5,
            "warning": 15,
            "info": 60,
        }
        self.on_aggregated = on_aggregated

        self._alerts: dict[str, AlertRecord] = {}
        self._suppression_windows: dict[str, datetime] = {}
        self._lock = threading.Lock()

    def _create_fingerprint(
        self,
        alert_name: str,
        severity: str,
        labels: dict[str, str] | None = None,
    ) -> str:
        """Create fingerprint for alert grouping."""
        parts = [alert_name, severity]

        if labels:
            for key in sorted(labels.keys()):
                parts.append(f"{key}={labels[key]}")

        fingerprint_data = ":".join(parts)
        return hashlib.md5(fingerprint_data.encode()).hexdigest()[:12]

    def should_alert(
        self,
        alert_name: str,
        severity: str = "warning",
        labels: dict[str, str] | None = None,
        force: bool = False,
    ) -> bool:
        """
        Check if an alert should be sent.

        Parameters
        ----------
        alert_name : str
            Name of the alert
        severity : str
            Alert severity (critical, warning, info)
        labels : dict, optional
            Additional labels for grouping
        force : bool
            Force send regardless of deduplication

        Returns
        -------
        bool
            Whether alert should be sent
        """
        now = datetime.utcnow()
        fingerprint = self._create_fingerprint(alert_name, severity, labels)

        ALERTS_TOTAL.labels(alert_name=alert_name, severity=severity).inc()

        with self._lock:
            # Check suppression window
            if fingerprint in self._suppression_windows and not force:
                suppression_end = self._suppression_windows[fingerprint]
                if now < suppression_end:
                    # Update existing record
                    if fingerprint in self._alerts:
                        self._alerts[fingerprint].count += 1
                        self._alerts[fingerprint].last_seen = now
                        self._alerts[fingerprint].suppressed_count += 1

                        ALERT_GROUP_SIZE.labels(alert_name=alert_name, severity=severity).set(
                            self._alerts[fingerprint].count
                        )

                        if self.on_aggregated:
                            self.on_aggregated(self._alerts[fingerprint])

                    ALERTS_DEDUPLICATED.labels(alert_name=alert_name, severity=severity).inc()

                    return False

            # Check if we've exceeded max alerts in window
            if fingerprint in self._alerts:
                record = self._alerts[fingerprint]
                window_start = now - timedelta(minutes=self.window_minutes)

                if record.first_seen > window_start:
                    # Still within window
                    record.count += 1
                    record.last_seen = now

                    # Check max alerts
                    sent_count = record.count - record.suppressed_count
                    if sent_count >= self.max_alerts_per_window and not force:
                        record.suppressed_count += 1

                        ALERTS_DEDUPLICATED.labels(alert_name=alert_name, severity=severity).inc()

                        if self.on_aggregated:
                            self.on_aggregated(record)

                        return False
                else:
                    # Window expired, reset
                    record.first_seen = now
                    record.last_seen = now
                    record.count = 1
                    record.suppressed_count = 0
            else:
                # New alert
                record = AlertRecord(
                    alert_name=alert_name,
                    severity=severity,
                    first_seen=now,
                    last_seen=now,
                    fingerprint=fingerprint,
                    labels=labels or {},
                )
                self._alerts[fingerprint] = record

            # Set suppression window based on severity
            cooldown = self.severity_cooldowns.get(severity, 15)
            self._suppression_windows[fingerprint] = now + timedelta(minutes=cooldown)

            record.last_sent = now

            ALERTS_ACTIVE.labels(alert_name=alert_name).set(len(self._alerts))
            ALERT_GROUP_SIZE.labels(alert_name=alert_name, severity=severity).set(record.count)

            logger.debug(
                "alert_passed_dedup",
                alert_name=alert_name,
                severity=severity,
                fingerprint=fingerprint,
                count=record.count,
            )

            return True

    def add_suppression(
        self,
        alert_name: str,
        duration_minutes: int,
        severity: str | None = None,
        labels: dict[str, str] | None = None,
    ):
        """
        Add a suppression window for an alert.

        Parameters
        ----------
        alert_name : str
            Alert name to suppress
        duration_minutes : int
            Suppression duration
        severity : str, optional
            Severity (if not specified, suppresses all severities)
        labels : dict, optional
            Labels to match
        """
        now = datetime.utcnow()

        if severity:
            fingerprint = self._create_fingerprint(alert_name, severity, labels)
            with self._lock:
                self._suppression_windows[fingerprint] = now + timedelta(minutes=duration_minutes)
        else:
            # Suppress all severities
            for sev in ["critical", "warning", "info"]:
                fingerprint = self._create_fingerprint(alert_name, sev, labels)
                with self._lock:
                    self._suppression_windows[fingerprint] = now + timedelta(
                        minutes=duration_minutes
                    )

        logger.info(
            "alert_suppression_added",
            alert_name=alert_name,
            duration_minutes=duration_minutes,
            severity=severity,
        )

    def clear_suppression(
        self,
        alert_name: str,
        severity: str | None = None,
        labels: dict[str, str] | None = None,
    ):
        """Clear suppression for an alert."""
        if severity:
            fingerprint = self._create_fingerprint(alert_name, severity, labels)
            with self._lock:
                if fingerprint in self._suppression_windows:
                    del self._suppression_windows[fingerprint]
        else:
            for sev in ["critical", "warning", "info"]:
                fingerprint = self._create_fingerprint(alert_name, sev, labels)
                with self._lock:
                    if fingerprint in self._suppression_windows:
                        del self._suppression_windows[fingerprint]

    def get_active_alerts(self) -> list[AlertRecord]:
        """Get all active alert records."""
        now = datetime.utcnow()
        window_start = now - timedelta(minutes=self.window_minutes)

        with self._lock:
            return [record for record in self._alerts.values() if record.last_seen > window_start]

    def get_suppressed_alerts(self) -> dict[str, datetime]:
        """Get currently suppressed alerts with end times."""
        now = datetime.utcnow()

        with self._lock:
            return {
                fp: end_time for fp, end_time in self._suppression_windows.items() if end_time > now
            }

    def cleanup(self):
        """Clean up old records."""
        now = datetime.utcnow()
        window_start = now - timedelta(minutes=self.window_minutes * 2)

        with self._lock:
            # Clean old alerts
            old_fingerprints = [
                fp for fp, record in self._alerts.items() if record.last_seen < window_start
            ]
            for fp in old_fingerprints:
                del self._alerts[fp]

            # Clean expired suppressions
            expired = [fp for fp, end_time in self._suppression_windows.items() if end_time < now]
            for fp in expired:
                del self._suppression_windows[fp]


# =============================================================================
# Singleton
# =============================================================================

_deduplicator: AlertDeduplicator | None = None
_dedup_lock = threading.Lock()


def get_alert_deduplicator(**kwargs) -> AlertDeduplicator:
    """Get or create the global alert deduplicator."""
    global _deduplicator

    if _deduplicator is None:
        with _dedup_lock:
            if _deduplicator is None:
                _deduplicator = AlertDeduplicator(**kwargs)

    return _deduplicator


def should_alert(alert_name: str, **kwargs) -> bool:
    """Quick helper to check if alert should be sent."""
    return get_alert_deduplicator().should_alert(alert_name, **kwargs)
