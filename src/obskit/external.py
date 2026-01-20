"""
External API SLA Tracking
=========================

Track SLA compliance of third-party APIs.

Features:
- Availability tracking
- Latency percentiles
- Error rate monitoring
- SLA breach alerting
- Compliance reporting

Example:
    from obskit.external import ExternalAPISLATracker

    api = ExternalAPISLATracker(
        "dialects_ai",
        expected_availability=0.99,
        expected_latency_p95_ms=500
    )

    with api.track_call():
        response = requests.get("https://api.example.com/endpoint")

    # Get compliance report
    report = api.get_compliance_report()
"""

import statistics
import threading
import time
from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from prometheus_client import Counter, Gauge, Histogram

from obskit.logging import get_logger

logger = get_logger(__name__)


# =============================================================================
# Prometheus Metrics
# =============================================================================

EXTERNAL_API_REQUESTS_TOTAL = Counter(
    "external_api_requests_total",
    "Total requests to external API",
    ["api_name", "method", "status"],
)

EXTERNAL_API_LATENCY = Histogram(
    "external_api_latency_seconds",
    "External API latency",
    ["api_name", "method"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30),
)

EXTERNAL_API_ERRORS_TOTAL = Counter(
    "external_api_errors_total", "Total errors from external API", ["api_name", "error_type"]
)

EXTERNAL_API_AVAILABILITY = Gauge(
    "external_api_availability", "Current availability of external API", ["api_name"]
)

EXTERNAL_API_LATENCY_P95 = Gauge(
    "external_api_latency_p95_ms", "P95 latency of external API", ["api_name"]
)

EXTERNAL_API_SLA_COMPLIANT = Gauge(
    "external_api_sla_compliant",
    "Whether API is SLA compliant (1=yes, 0=no)",
    ["api_name", "sla_type"],
)

EXTERNAL_API_SLA_BREACHES_TOTAL = Counter(
    "external_api_sla_breaches_total", "Total SLA breaches", ["api_name", "sla_type"]
)


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class SLADefinition:
    """Definition of expected SLA."""

    availability: float = 0.99  # 99%
    latency_p50_ms: float = 100
    latency_p95_ms: float = 500
    latency_p99_ms: float = 1000
    error_rate_percent: float = 1.0
    timeout_seconds: float = 30.0


@dataclass
class APICallRecord:
    """Record of a single API call."""

    timestamp: datetime
    latency_seconds: float
    success: bool
    status_code: int | None = None
    error_type: str | None = None


@dataclass
class SLAComplianceReport:
    """SLA compliance report for an API."""

    api_name: str
    window_start: datetime
    window_end: datetime
    total_requests: int
    successful_requests: int
    failed_requests: int
    availability: float
    availability_sla: float
    availability_compliant: bool
    latency_p50_ms: float
    latency_p95_ms: float
    latency_p99_ms: float
    latency_p95_sla_ms: float
    latency_compliant: bool
    error_rate_percent: float
    error_rate_sla_percent: float
    error_rate_compliant: bool
    overall_compliant: bool
    sla_breaches: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "api_name": self.api_name,
            "window_start": self.window_start.isoformat(),
            "window_end": self.window_end.isoformat(),
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "availability": self.availability,
            "availability_sla": self.availability_sla,
            "availability_compliant": self.availability_compliant,
            "latency_p50_ms": self.latency_p50_ms,
            "latency_p95_ms": self.latency_p95_ms,
            "latency_p99_ms": self.latency_p99_ms,
            "latency_p95_sla_ms": self.latency_p95_sla_ms,
            "latency_compliant": self.latency_compliant,
            "error_rate_percent": self.error_rate_percent,
            "error_rate_sla_percent": self.error_rate_sla_percent,
            "error_rate_compliant": self.error_rate_compliant,
            "overall_compliant": self.overall_compliant,
            "sla_breaches": self.sla_breaches,
        }


# =============================================================================
# External API SLA Tracker
# =============================================================================


class ExternalAPISLATracker:
    """
    Track SLA compliance for an external API.

    Parameters
    ----------
    api_name : str
        Name of the API
    expected_availability : float
        Expected availability (0-1)
    expected_latency_p95_ms : float
        Expected P95 latency in milliseconds
    expected_error_rate_percent : float
        Expected error rate percentage
    window_seconds : int
        Rolling window for calculations
    on_sla_breach : callable, optional
        Callback when SLA is breached
    """

    def __init__(
        self,
        api_name: str,
        expected_availability: float = 0.99,
        expected_latency_p95_ms: float = 500,
        expected_latency_p99_ms: float = 1000,
        expected_error_rate_percent: float = 1.0,
        window_seconds: int = 3600,
        on_sla_breach: Callable[[str, str, float], None] | None = None,
    ):
        self.api_name = api_name
        self.sla = SLADefinition(
            availability=expected_availability,
            latency_p95_ms=expected_latency_p95_ms,
            latency_p99_ms=expected_latency_p99_ms,
            error_rate_percent=expected_error_rate_percent,
        )
        self.window_seconds = window_seconds
        self.on_sla_breach = on_sla_breach

        self._records: list[APICallRecord] = []
        self._lock = threading.Lock()

        # Track recent breaches to avoid alert spam
        self._recent_breaches: dict[str, datetime] = {}
        self._breach_cooldown = timedelta(minutes=5)

    def set_expected_sla(
        self,
        availability: float | None = None,
        latency_p95_ms: float | None = None,
        latency_p99_ms: float | None = None,
        error_rate_percent: float | None = None,
    ):
        """Update expected SLA values."""
        if availability is not None:
            self.sla.availability = availability
        if latency_p95_ms is not None:
            self.sla.latency_p95_ms = latency_p95_ms
        if latency_p99_ms is not None:
            self.sla.latency_p99_ms = latency_p99_ms
        if error_rate_percent is not None:
            self.sla.error_rate_percent = error_rate_percent

    @contextmanager
    def track_call(
        self,
        method: str = "GET",
    ) -> Generator[None, None, None]:
        """
        Track an API call.

        Parameters
        ----------
        method : str
            HTTP method
        """
        start_time = time.perf_counter()
        success = True
        status_code = None
        error_type = None

        try:
            yield
        except Exception as e:
            success = False
            error_type = type(e).__name__
            raise
        finally:
            latency = time.perf_counter() - start_time

            record = APICallRecord(
                timestamp=datetime.utcnow(),
                latency_seconds=latency,
                success=success,
                status_code=status_code,
                error_type=error_type,
            )

            self._record_call(record, method)

    def record_call(
        self,
        latency_seconds: float,
        success: bool,
        method: str = "GET",
        status_code: int | None = None,
        error_type: str | None = None,
    ):
        """
        Manually record an API call.

        Parameters
        ----------
        latency_seconds : float
            Call latency
        success : bool
            Whether call succeeded
        method : str
            HTTP method
        status_code : int, optional
            HTTP status code
        error_type : str, optional
            Error type if failed
        """
        record = APICallRecord(
            timestamp=datetime.utcnow(),
            latency_seconds=latency_seconds,
            success=success,
            status_code=status_code,
            error_type=error_type,
        )

        self._record_call(record, method)

    def _record_call(self, record: APICallRecord, method: str):
        """Internal method to record a call."""
        with self._lock:
            self._records.append(record)
            self._cleanup_old_records()

        # Update metrics
        status = "success" if record.success else "error"

        EXTERNAL_API_REQUESTS_TOTAL.labels(
            api_name=self.api_name, method=method, status=status
        ).inc()

        EXTERNAL_API_LATENCY.labels(api_name=self.api_name, method=method).observe(
            record.latency_seconds
        )

        if not record.success:
            EXTERNAL_API_ERRORS_TOTAL.labels(
                api_name=self.api_name, error_type=record.error_type or "unknown"
            ).inc()

        # Update gauges
        self._update_gauges()

        # Check SLA compliance
        self._check_sla_compliance()

    def _cleanup_old_records(self):
        """Remove records outside the window."""
        cutoff = datetime.utcnow() - timedelta(seconds=self.window_seconds)
        self._records = [r for r in self._records if r.timestamp > cutoff]

    def _update_gauges(self):
        """Update gauge metrics."""
        with self._lock:
            if not self._records:
                return

            # Availability
            successful = sum(1 for r in self._records if r.success)
            availability = successful / len(self._records) if self._records else 1.0
            EXTERNAL_API_AVAILABILITY.labels(api_name=self.api_name).set(availability)

            # Latency P95
            latencies = [r.latency_seconds * 1000 for r in self._records]  # Convert to ms
            if latencies:
                p95 = (
                    statistics.quantiles(latencies, n=20)[18]
                    if len(latencies) >= 2
                    else latencies[0]
                )
                EXTERNAL_API_LATENCY_P95.labels(api_name=self.api_name).set(p95)

    def _check_sla_compliance(self):
        """Check and report SLA compliance."""
        report = self.get_compliance_report()

        # Update compliance gauges
        EXTERNAL_API_SLA_COMPLIANT.labels(api_name=self.api_name, sla_type="availability").set(
            1 if report.availability_compliant else 0
        )

        EXTERNAL_API_SLA_COMPLIANT.labels(api_name=self.api_name, sla_type="latency").set(
            1 if report.latency_compliant else 0
        )

        EXTERNAL_API_SLA_COMPLIANT.labels(api_name=self.api_name, sla_type="error_rate").set(
            1 if report.error_rate_compliant else 0
        )

        # Report breaches
        now = datetime.utcnow()

        for breach in report.sla_breaches:
            # Check cooldown
            if breach in self._recent_breaches:
                if now - self._recent_breaches[breach] < self._breach_cooldown:
                    continue

            self._recent_breaches[breach] = now

            EXTERNAL_API_SLA_BREACHES_TOTAL.labels(api_name=self.api_name, sla_type=breach).inc()

            logger.warning(
                "external_api_sla_breach",
                api_name=self.api_name,
                breach_type=breach,
                report=report.to_dict(),
            )

            if self.on_sla_breach:
                if "availability" in breach:
                    self.on_sla_breach(self.api_name, breach, report.availability)
                elif "latency" in breach:
                    self.on_sla_breach(self.api_name, breach, report.latency_p95_ms)
                elif "error" in breach:
                    self.on_sla_breach(self.api_name, breach, report.error_rate_percent)

    def get_compliance_report(self) -> SLAComplianceReport:
        """
        Get current SLA compliance report.

        Returns
        -------
        SLAComplianceReport
            Current compliance status
        """
        with self._lock:
            self._cleanup_old_records()

            now = datetime.utcnow()
            window_start = now - timedelta(seconds=self.window_seconds)

            total = len(self._records)
            successful = sum(1 for r in self._records if r.success)
            failed = total - successful

            # Availability
            availability = successful / total if total > 0 else 1.0
            availability_compliant = availability >= self.sla.availability

            # Latency
            latencies_ms = [r.latency_seconds * 1000 for r in self._records]

            if latencies_ms:
                latency_p50 = statistics.median(latencies_ms)
                sorted_latencies = sorted(latencies_ms)
                p95_idx = int(len(sorted_latencies) * 0.95)
                p99_idx = int(len(sorted_latencies) * 0.99)
                latency_p95 = sorted_latencies[min(p95_idx, len(sorted_latencies) - 1)]
                latency_p99 = sorted_latencies[min(p99_idx, len(sorted_latencies) - 1)]
            else:
                latency_p50 = 0
                latency_p95 = 0
                latency_p99 = 0

            latency_compliant = latency_p95 <= self.sla.latency_p95_ms

            # Error rate
            error_rate = (failed / total * 100) if total > 0 else 0
            error_rate_compliant = error_rate <= self.sla.error_rate_percent

            # Overall
            overall_compliant = (
                availability_compliant and latency_compliant and error_rate_compliant
            )

            # List breaches
            breaches = []
            if not availability_compliant:
                breaches.append(f"availability ({availability:.2%} < {self.sla.availability:.2%})")
            if not latency_compliant:
                breaches.append(
                    f"latency_p95 ({latency_p95:.0f}ms > {self.sla.latency_p95_ms:.0f}ms)"
                )
            if not error_rate_compliant:
                breaches.append(
                    f"error_rate ({error_rate:.2f}% > {self.sla.error_rate_percent:.2f}%)"
                )

            return SLAComplianceReport(
                api_name=self.api_name,
                window_start=window_start,
                window_end=now,
                total_requests=total,
                successful_requests=successful,
                failed_requests=failed,
                availability=availability,
                availability_sla=self.sla.availability,
                availability_compliant=availability_compliant,
                latency_p50_ms=latency_p50,
                latency_p95_ms=latency_p95,
                latency_p99_ms=latency_p99,
                latency_p95_sla_ms=self.sla.latency_p95_ms,
                latency_compliant=latency_compliant,
                error_rate_percent=error_rate,
                error_rate_sla_percent=self.sla.error_rate_percent,
                error_rate_compliant=error_rate_compliant,
                overall_compliant=overall_compliant,
                sla_breaches=breaches,
            )

    def is_compliant(self) -> bool:
        """Check if API is currently SLA compliant."""
        return self.get_compliance_report().overall_compliant


# =============================================================================
# Registry
# =============================================================================

_api_trackers: dict[str, ExternalAPISLATracker] = {}
_api_lock = threading.Lock()


def get_external_api_tracker(
    api_name: str,
    **kwargs,
) -> ExternalAPISLATracker:
    """Get or create an external API tracker."""
    if api_name not in _api_trackers:
        with _api_lock:
            if api_name not in _api_trackers:
                _api_trackers[api_name] = ExternalAPISLATracker(api_name, **kwargs)

    return _api_trackers[api_name]


def get_all_api_compliance() -> dict[str, SLAComplianceReport]:
    """Get compliance reports for all tracked APIs."""
    return {name: tracker.get_compliance_report() for name, tracker in _api_trackers.items()}
