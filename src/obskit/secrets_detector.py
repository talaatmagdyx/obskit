"""
Secrets Detection
=================

Detect secrets and sensitive data in logs and traces.

Features:
- Pattern-based detection
- Automatic redaction
- Alert on detection
- Compliance support

Example:
    from obskit.secrets_detector import SecretsDetector

    detector = SecretsDetector()

    # Check for secrets
    result = detector.scan("API key: sk-1234567890abcdef")
    if result.has_secrets:
        print(f"Found secrets: {result.detected_types}")

    # Redact secrets
    safe_text = detector.redact("password=mypassword123")
"""

from __future__ import annotations

import re
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from prometheus_client import Counter

from obskit.logging import get_logger

logger = get_logger(__name__)


# =============================================================================
# Prometheus Metrics
# =============================================================================

SECRETS_DETECTED = Counter(
    "secrets_detector_detected_total", "Total secrets detected", ["secret_type", "source"]
)

SECRETS_REDACTED = Counter(
    "secrets_detector_redacted_total", "Total secrets redacted", ["secret_type"]
)


# =============================================================================
# Enums and Data Classes
# =============================================================================


class SecretType(Enum):
    """Types of secrets that can be detected."""

    API_KEY = "api_key"
    PASSWORD = "password"
    TOKEN = "token"
    JWT = "jwt"
    AWS_KEY = "aws_key"
    PRIVATE_KEY = "private_key"
    CREDIT_CARD = "credit_card"
    SSN = "ssn"
    EMAIL = "email"
    PHONE = "phone"
    IP_ADDRESS = "ip_address"
    CUSTOM = "custom"


@dataclass
class SecretPattern:
    """Pattern for detecting secrets."""

    name: str
    secret_type: SecretType
    pattern: re.Pattern[str]
    severity: str = "high"
    redact_with: str = "[REDACTED]"


@dataclass
class DetectionResult:
    """Result of secrets scan."""

    has_secrets: bool
    detected_types: list[SecretType]
    detections: list[dict[str, Any]]
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "has_secrets": self.has_secrets,
            "detected_types": [t.value for t in self.detected_types],
            "detections": self.detections,
            "timestamp": self.timestamp.isoformat(),
        }


# =============================================================================
# Default Patterns
# =============================================================================

DEFAULT_PATTERNS = [
    # API Keys
    SecretPattern(
        name="Generic API Key",
        secret_type=SecretType.API_KEY,
        pattern=re.compile(r'(?i)(api[_-]?key|apikey)\s*[:=]\s*["\']?([a-zA-Z0-9_-]{20,})["\']?'),
    ),
    SecretPattern(
        name="OpenAI API Key",
        secret_type=SecretType.API_KEY,
        pattern=re.compile(r"sk-[a-zA-Z0-9]{48}"),
    ),
    SecretPattern(
        name="Stripe API Key",
        secret_type=SecretType.API_KEY,
        pattern=re.compile(r"sk_(?:live|test)_[a-zA-Z0-9]{24,}"),
    ),
    # Passwords
    SecretPattern(
        name="Password in URL",
        secret_type=SecretType.PASSWORD,
        pattern=re.compile(r"(?i)://[^:]+:([^@]+)@"),
    ),
    SecretPattern(
        name="Password Parameter",
        secret_type=SecretType.PASSWORD,
        pattern=re.compile(r'(?i)(password|passwd|pwd)\s*[:=]\s*["\']?([^\s"\']+)["\']?'),
    ),
    # Tokens
    SecretPattern(
        name="Bearer Token",
        secret_type=SecretType.TOKEN,
        pattern=re.compile(r"(?i)bearer\s+([a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+)"),
    ),
    SecretPattern(
        name="Generic Token",
        secret_type=SecretType.TOKEN,
        pattern=re.compile(
            r'(?i)(token|auth_token|access_token)\s*[:=]\s*["\']?([a-zA-Z0-9_-]{20,})["\']?'
        ),
    ),
    # JWT
    SecretPattern(
        name="JWT Token",
        secret_type=SecretType.JWT,
        pattern=re.compile(r"eyJ[a-zA-Z0-9_-]+\.eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+"),
    ),
    # AWS
    SecretPattern(
        name="AWS Access Key",
        secret_type=SecretType.AWS_KEY,
        pattern=re.compile(r"AKIA[0-9A-Z]{16}"),
    ),
    SecretPattern(
        name="AWS Secret Key",
        secret_type=SecretType.AWS_KEY,
        pattern=re.compile(
            r'(?i)(aws_secret|secret_key)\s*[:=]\s*["\']?([a-zA-Z0-9/+=]{40})["\']?'
        ),
    ),
    # Private Keys
    SecretPattern(
        name="Private Key",
        secret_type=SecretType.PRIVATE_KEY,
        pattern=re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"),
    ),
    # Credit Card
    SecretPattern(
        name="Credit Card",
        secret_type=SecretType.CREDIT_CARD,
        pattern=re.compile(
            r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12})\b"
        ),
        severity="critical",
    ),
    # SSN
    SecretPattern(
        name="Social Security Number",
        secret_type=SecretType.SSN,
        pattern=re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
        severity="critical",
    ),
    # Email (for PII detection)
    SecretPattern(
        name="Email Address",
        secret_type=SecretType.EMAIL,
        pattern=re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b"),
        severity="medium",
    ),
    # Phone
    SecretPattern(
        name="Phone Number",
        secret_type=SecretType.PHONE,
        pattern=re.compile(r"\b(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b"),
        severity="medium",
    ),
]


# =============================================================================
# Secrets Detector
# =============================================================================


class SecretsDetector:
    """
    Detect and redact secrets in text.

    Parameters
    ----------
    patterns : list, optional
        Custom patterns to use
    use_defaults : bool
        Include default patterns
    on_detection : callable, optional
        Callback when secret is detected
    auto_redact : bool
        Automatically redact detected secrets
    """

    def __init__(
        self,
        patterns: list[SecretPattern] | None = None,
        use_defaults: bool = True,
        on_detection: Callable[[SecretType, str], None] | None = None,
        auto_redact: bool = False,
    ):
        self.on_detection = on_detection
        self.auto_redact = auto_redact

        self._patterns: list[SecretPattern] = []
        if use_defaults:
            self._patterns.extend(DEFAULT_PATTERNS)
        if patterns:
            self._patterns.extend(patterns)

        self._lock = threading.Lock()

    def add_pattern(
        self,
        name: str,
        pattern: str,
        secret_type: SecretType = SecretType.CUSTOM,
        severity: str = "high",
        redact_with: str = "[REDACTED]",
    ):
        """
        Add a custom pattern.

        Parameters
        ----------
        name : str
            Pattern name
        pattern : str
            Regex pattern
        secret_type : SecretType
            Type of secret
        severity : str
            Severity level
        redact_with : str
            Redaction string
        """
        secret_pattern = SecretPattern(
            name=name,
            secret_type=secret_type,
            pattern=re.compile(pattern),
            severity=severity,
            redact_with=redact_with,
        )

        with self._lock:
            self._patterns.append(secret_pattern)

    def scan(
        self,
        text: str,
        source: str = "unknown",
    ) -> DetectionResult:
        """
        Scan text for secrets.

        Parameters
        ----------
        text : str
            Text to scan
        source : str
            Source identifier (for metrics)

        Returns
        -------
        DetectionResult
        """
        detections = []
        detected_types: set[SecretType] = set()

        with self._lock:
            patterns = list(self._patterns)

        for pattern in patterns:
            matches = pattern.pattern.findall(text)

            for match in matches:
                # Handle groups
                if isinstance(match, tuple):
                    match = match[0] if match else ""

                detected_types.add(pattern.secret_type)

                detections.append(
                    {
                        "pattern_name": pattern.name,
                        "secret_type": pattern.secret_type.value,
                        "severity": pattern.severity,
                        "preview": self._safe_preview(match),
                    }
                )

                SECRETS_DETECTED.labels(secret_type=pattern.secret_type.value, source=source).inc()

                if self.on_detection:
                    self.on_detection(pattern.secret_type, source)

        if detections:
            logger.warning(
                "secrets_detected",
                count=len(detections),
                types=[t.value for t in detected_types],
                source=source,
            )

        return DetectionResult(
            has_secrets=bool(detections),
            detected_types=list(detected_types),
            detections=detections,
        )

    def _safe_preview(self, secret: str, max_len: int = 4) -> str:
        """Create safe preview of secret for logging."""
        if len(secret) <= max_len:
            return "*" * len(secret)
        return secret[:max_len] + "*" * (len(secret) - max_len)

    def redact(
        self,
        text: str,
        replacement: str = "[REDACTED]",
    ) -> str:
        """
        Redact secrets from text.

        Parameters
        ----------
        text : str
            Text to redact
        replacement : str
            Replacement string

        Returns
        -------
        str
            Redacted text
        """
        result = text

        with self._lock:
            patterns = list(self._patterns)

        for pattern in patterns:
            # Find all matches
            matches = list(pattern.pattern.finditer(result))

            # Replace from end to preserve positions
            for match in reversed(matches):
                redact_str = pattern.redact_with or replacement
                result = result[: match.start()] + redact_str + result[match.end() :]

                SECRETS_REDACTED.labels(secret_type=pattern.secret_type.value).inc()

        return result

    def scan_and_redact(
        self,
        text: str,
        source: str = "unknown",
    ) -> tuple[str, DetectionResult]:
        """
        Scan for secrets and redact them.

        Parameters
        ----------
        text : str
            Text to process
        source : str
            Source identifier

        Returns
        -------
        tuple
            (redacted_text, detection_result)
        """
        result = self.scan(text, source)
        redacted = self.redact(text) if result.has_secrets else text
        return redacted, result

    def is_safe(self, text: str) -> bool:
        """Check if text is safe (no secrets)."""
        result = self.scan(text)
        return not result.has_secrets

    def get_patterns(self) -> list[SecretPattern]:
        """Get all patterns."""
        with self._lock:
            return list(self._patterns)


# =============================================================================
# Singleton
# =============================================================================

_detector: SecretsDetector | None = None
_detector_lock = threading.Lock()


def get_secrets_detector(**kwargs) -> SecretsDetector:
    """Get or create the global secrets detector."""
    global _detector

    if _detector is None:
        with _detector_lock:
            if _detector is None:
                _detector = SecretsDetector(**kwargs)

    return _detector


def redact_secrets(text: str) -> str:
    """Quick helper to redact secrets."""
    return get_secrets_detector().redact(text)


def scan_for_secrets(text: str) -> DetectionResult:
    """Quick helper to scan for secrets."""
    return get_secrets_detector().scan(text)
