"""Unit tests for Secrets Detection."""

from obskit.secrets_detector import (
    DetectionResult,
    SecretsDetector,
    SecretType,
    get_secrets_detector,
    redact_secrets,
    scan_for_secrets,
)


class TestSecretsDetector:
    """Tests for SecretsDetector."""

    def test_detect_api_key(self):
        """Test API key detection."""
        detector = SecretsDetector()

        result = detector.scan("api_key=sk-1234567890abcdefghijk")

        assert result.has_secrets is True
        assert SecretType.API_KEY in result.detected_types

    def test_detect_password(self):
        """Test password detection."""
        detector = SecretsDetector()

        result = detector.scan("password=mysecretpassword123")

        assert result.has_secrets is True
        assert SecretType.PASSWORD in result.detected_types

    def test_detect_jwt(self):
        """Test JWT detection."""
        detector = SecretsDetector()

        jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.Gv7McwToTHqgz_q1P3IzfQ"
        result = detector.scan(f"token: {jwt}")

        assert result.has_secrets is True
        assert SecretType.JWT in result.detected_types

    def test_detect_aws_key(self):
        """Test AWS key detection."""
        detector = SecretsDetector()

        result = detector.scan("AKIAIOSFODNN7EXAMPLE")

        assert result.has_secrets is True
        assert SecretType.AWS_KEY in result.detected_types

    def test_detect_credit_card(self):
        """Test credit card detection."""
        detector = SecretsDetector()

        result = detector.scan("card: 4111111111111111")

        assert result.has_secrets is True
        assert SecretType.CREDIT_CARD in result.detected_types

    def test_no_secrets(self):
        """Test clean text detection."""
        detector = SecretsDetector()

        result = detector.scan("This is a normal message with no secrets")

        assert result.has_secrets is False
        assert len(result.detected_types) == 0

    def test_redact_secrets(self):
        """Test secret redaction."""
        detector = SecretsDetector()

        text = "api_key=sk-verysecretapikey12345"
        redacted = detector.redact(text)

        assert "sk-verysecret" not in redacted
        assert "[REDACTED]" in redacted

    def test_scan_and_redact(self):
        """Test combined scan and redact."""
        detector = SecretsDetector()

        text = "password=secret123"
        redacted, result = detector.scan_and_redact(text)

        assert result.has_secrets is True
        assert "secret123" not in redacted

    def test_is_safe(self):
        """Test safety check."""
        detector = SecretsDetector()

        assert detector.is_safe("normal text") is True
        assert detector.is_safe("password=secret") is False

    def test_custom_pattern(self):
        """Test adding custom pattern."""
        detector = SecretsDetector(use_defaults=False)

        detector.add_pattern(
            name="Custom Token",
            pattern=r"CUSTOM-[A-Z0-9]{16}",
            secret_type=SecretType.CUSTOM,
        )

        result = detector.scan("token: CUSTOM-ABCD1234EFGH5678")

        assert result.has_secrets is True
        assert SecretType.CUSTOM in result.detected_types

    def test_multiple_secrets(self):
        """Test detecting multiple secrets."""
        detector = SecretsDetector()

        text = """
        api_key=sk-1234567890abcdefghijk
        password=mypassword123
        """

        result = detector.scan(text)

        assert result.has_secrets is True
        assert len(result.detected_types) >= 2


class TestDetectionResult:
    """Tests for DetectionResult."""

    def test_to_dict(self):
        """Test DetectionResult serialization."""
        result = DetectionResult(
            has_secrets=True,
            detected_types=[SecretType.API_KEY],
            detections=[
                {
                    "pattern_name": "API Key",
                    "secret_type": "api_key",
                }
            ],
        )

        data = result.to_dict()
        assert data["has_secrets"] is True
        assert "api_key" in data["detected_types"]


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_redact_secrets_function(self):
        """Test global redact_secrets function."""
        text = "password=secretpassword123"
        redacted = redact_secrets(text)

        assert "secretpassword" not in redacted

    def test_scan_for_secrets_function(self):
        """Test global scan_for_secrets function."""
        result = scan_for_secrets("api_key=sk-12345678901234567890")

        assert result.has_secrets is True


class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_secrets_detector(self):
        """Test global detector singleton."""
        detector1 = get_secrets_detector()
        detector2 = get_secrets_detector()
        assert detector1 is detector2
