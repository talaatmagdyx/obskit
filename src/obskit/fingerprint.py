"""
Error Fingerprinting
====================

Automatically group similar errors together.

Features:
- Exception fingerprint generation
- Error grouping
- Occurrence counting
- First/last seen tracking

Example:
    from obskit.fingerprint import ErrorFingerprinter, get_error_group

    fingerprinter = ErrorFingerprinter()

    try:
        risky_operation()
    except Exception as e:
        fingerprint = fingerprinter.get_fingerprint(e)
        group = fingerprinter.record_error(e)
        print(f"Error group: {group.fingerprint}, count: {group.count}")
"""

import hashlib
import re
import threading
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from prometheus_client import Counter, Gauge

from obskit.logging import get_logger

logger = get_logger(__name__)


# =============================================================================
# Prometheus Metrics
# =============================================================================

ERROR_GROUPS_TOTAL = Gauge("error_groups_total", "Total unique error groups", ["service"])

ERROR_OCCURRENCES_TOTAL = Counter(
    "error_occurrences_total", "Total error occurrences", ["fingerprint", "error_type", "component"]
)

ERROR_GROUP_SIZE = Gauge(
    "error_group_occurrences", "Number of occurrences in error group", ["fingerprint", "error_type"]
)


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class ErrorGroup:
    """A group of similar errors."""

    fingerprint: str
    error_type: str
    message_template: str
    component: str | None = None
    count: int = 0
    first_seen: datetime = field(default_factory=datetime.utcnow)
    last_seen: datetime = field(default_factory=datetime.utcnow)
    sample_stack_trace: str | None = None
    affected_operations: set[str] = field(default_factory=set)

    def to_dict(self) -> dict[str, Any]:
        return {
            "fingerprint": self.fingerprint,
            "error_type": self.error_type,
            "message_template": self.message_template,
            "component": self.component,
            "count": self.count,
            "first_seen": self.first_seen.isoformat(),
            "last_seen": self.last_seen.isoformat(),
            "sample_stack_trace": self.sample_stack_trace,
            "affected_operations": list(self.affected_operations),
        }


@dataclass
class FingerprintResult:
    """Result of fingerprinting an error."""

    fingerprint: str
    error_type: str
    message_template: str
    stack_signature: str
    component: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "fingerprint": self.fingerprint,
            "error_type": self.error_type,
            "message_template": self.message_template,
            "stack_signature": self.stack_signature,
            "component": self.component,
        }


# =============================================================================
# Error Fingerprinter
# =============================================================================


class ErrorFingerprinter:
    """
    Generate fingerprints for errors to group similar exceptions.

    Parameters
    ----------
    service_name : str
        Name of the service
    normalize_paths : bool
        Whether to normalize file paths
    normalize_numbers : bool
        Whether to normalize numbers in messages
    max_groups : int
        Maximum error groups to track
    """

    def __init__(
        self,
        service_name: str = "default",
        normalize_paths: bool = True,
        normalize_numbers: bool = True,
        max_groups: int = 1000,
    ):
        self.service_name = service_name
        self.normalize_paths = normalize_paths
        self.normalize_numbers = normalize_numbers
        self.max_groups = max_groups

        self._groups: dict[str, ErrorGroup] = {}
        self._lock = threading.Lock()

        # Patterns for normalization
        self._number_pattern = re.compile(r"\b\d+\b")
        self._hex_pattern = re.compile(r"0x[0-9a-fA-F]+")
        self._uuid_pattern = re.compile(
            r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
        )
        self._path_pattern = re.compile(r"/[\w/.-]+")
        self._ip_pattern = re.compile(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}")

    def get_fingerprint(
        self,
        exception: Exception,
        component: str | None = None,
    ) -> FingerprintResult:
        """
        Generate a fingerprint for an exception.

        Parameters
        ----------
        exception : Exception
            The exception to fingerprint
        component : str, optional
            Component where error occurred

        Returns
        -------
        FingerprintResult
            The fingerprint result
        """
        error_type = type(exception).__name__
        message = str(exception)

        # Get stack trace
        tb = traceback.extract_tb(exception.__traceback__) if exception.__traceback__ else []

        # Normalize message
        message_template = self._normalize_message(message)

        # Create stack signature (most relevant frames)
        stack_signature = self._create_stack_signature(tb)

        # Detect component from stack if not provided
        if not component:
            component = self._detect_component(tb)

        # Create fingerprint hash
        fingerprint_data = f"{error_type}:{message_template}:{stack_signature}"
        fingerprint = hashlib.md5(fingerprint_data.encode()).hexdigest()[:12]

        return FingerprintResult(
            fingerprint=fingerprint,
            error_type=error_type,
            message_template=message_template,
            stack_signature=stack_signature,
            component=component,
        )

    def _normalize_message(self, message: str) -> str:
        """Normalize error message by removing variable parts."""
        normalized = message

        if self.normalize_numbers:
            # Replace UUIDs
            normalized = self._uuid_pattern.sub("<UUID>", normalized)
            # Replace hex addresses
            normalized = self._hex_pattern.sub("<HEX>", normalized)
            # Replace IP addresses
            normalized = self._ip_pattern.sub("<IP>", normalized)
            # Replace numbers
            normalized = self._number_pattern.sub("<NUM>", normalized)

        if self.normalize_paths:
            # Simplify file paths
            normalized = self._path_pattern.sub("<PATH>", normalized)

        # Remove quotes around variable content
        normalized = re.sub(r"'[^']*'", "'<VAR>'", normalized)
        normalized = re.sub(r'"[^"]*"', '"<VAR>"', normalized)

        return normalized.strip()

    def _create_stack_signature(
        self,
        tb: list[traceback.FrameSummary],
        max_frames: int = 5,
    ) -> str:
        """Create a signature from stack trace."""
        if not tb:
            return "no_stack"

        # Take most relevant frames (skip library frames if possible)
        relevant_frames = []
        for frame in reversed(tb):
            # Skip common library paths
            if any(
                skip in frame.filename
                for skip in ["site-packages", "dist-packages", "/usr/lib", "Python.framework"]
            ):
                continue
            relevant_frames.append(frame)
            if len(relevant_frames) >= max_frames:
                break

        if not relevant_frames:
            relevant_frames = tb[-max_frames:]

        # Create signature from function names and line numbers
        sig_parts = []
        for frame in relevant_frames:
            # Use just filename (not full path) and function name
            filename = frame.filename.split("/")[-1]
            sig_parts.append(f"{filename}:{frame.name}:{frame.lineno}")

        return "|".join(sig_parts)

    def _detect_component(self, tb: list[traceback.FrameSummary]) -> str | None:
        """Try to detect component from stack trace."""
        if not tb:
            return None

        # Look for common patterns
        for frame in reversed(tb):
            path = frame.filename.lower()

            if "controller" in path:
                return "controller"
            elif "widget" in path:
                return "widget"
            elif "query" in path or "builder" in path:
                return "query_builder"
            elif "page" in path:
                return "page"
            elif "service" in path:
                return "service"
            elif "handler" in path:
                return "handler"
            elif "middleware" in path:
                return "middleware"

        return None

    def record_error(
        self,
        exception: Exception,
        component: str | None = None,
        operation: str | None = None,
    ) -> ErrorGroup:
        """
        Record an error and return its group.

        Parameters
        ----------
        exception : Exception
            The exception
        component : str, optional
            Component where error occurred
        operation : str, optional
            Operation that was being performed

        Returns
        -------
        ErrorGroup
            The error group
        """
        fp_result = self.get_fingerprint(exception, component)

        with self._lock:
            if fp_result.fingerprint in self._groups:
                group = self._groups[fp_result.fingerprint]
                group.count += 1
                group.last_seen = datetime.utcnow()
                if operation:
                    group.affected_operations.add(operation)
            else:
                # Check max groups
                if len(self._groups) >= self.max_groups:
                    # Remove oldest group
                    oldest_key = min(self._groups.keys(), key=lambda k: self._groups[k].last_seen)
                    del self._groups[oldest_key]

                # Create new group
                stack_trace = None
                if exception.__traceback__:
                    stack_trace = "".join(traceback.format_tb(exception.__traceback__))

                group = ErrorGroup(
                    fingerprint=fp_result.fingerprint,
                    error_type=fp_result.error_type,
                    message_template=fp_result.message_template,
                    component=fp_result.component,
                    count=1,
                    sample_stack_trace=stack_trace,
                )
                if operation:
                    group.affected_operations.add(operation)

                self._groups[fp_result.fingerprint] = group

            # Update metrics
            ERROR_GROUPS_TOTAL.labels(service=self.service_name).set(len(self._groups))

        ERROR_OCCURRENCES_TOTAL.labels(
            fingerprint=fp_result.fingerprint,
            error_type=fp_result.error_type,
            component=fp_result.component or "unknown",
        ).inc()

        ERROR_GROUP_SIZE.labels(
            fingerprint=group.fingerprint,
            error_type=group.error_type,
        ).set(group.count)

        return group

    def get_group(self, fingerprint: str) -> ErrorGroup | None:
        """Get an error group by fingerprint."""
        with self._lock:
            return self._groups.get(fingerprint)

    def get_all_groups(self) -> list[ErrorGroup]:
        """Get all error groups."""
        with self._lock:
            return list(self._groups.values())

    def get_top_errors(self, limit: int = 10) -> list[ErrorGroup]:
        """Get top errors by count."""
        with self._lock:
            sorted_groups = sorted(self._groups.values(), key=lambda g: g.count, reverse=True)
            return sorted_groups[:limit]

    def get_recent_errors(self, limit: int = 10) -> list[ErrorGroup]:
        """Get most recent error groups."""
        with self._lock:
            sorted_groups = sorted(self._groups.values(), key=lambda g: g.last_seen, reverse=True)
            return sorted_groups[:limit]

    def clear(self):
        """Clear all error groups."""
        with self._lock:
            self._groups.clear()
            ERROR_GROUPS_TOTAL.labels(service=self.service_name).set(0)


# =============================================================================
# Singleton and Helpers
# =============================================================================

_fingerprinter: ErrorFingerprinter | None = None
_fingerprinter_lock = threading.Lock()


def get_error_fingerprinter(service_name: str = "default") -> ErrorFingerprinter:
    """Get or create the global error fingerprinter."""
    global _fingerprinter

    if _fingerprinter is None:
        with _fingerprinter_lock:
            if _fingerprinter is None:
                _fingerprinter = ErrorFingerprinter(service_name=service_name)

    return _fingerprinter


def get_error_group(exception: Exception, **kwargs) -> ErrorGroup:
    """Quick helper to record an error and get its group."""
    return get_error_fingerprinter().record_error(exception, **kwargs)


def get_fingerprint(exception: Exception) -> str:
    """Quick helper to get just the fingerprint string."""
    return get_error_fingerprinter().get_fingerprint(exception).fingerprint
