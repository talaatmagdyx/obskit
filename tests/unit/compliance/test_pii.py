"""Tests for obskit.compliance.pii module."""

from obskit.compliance.pii import (
    CREDIT_CARD_PATTERN,
    EMAIL_PATTERN,
    PHONE_PATTERN,
    SSN_PATTERN,
    redact_pii,
    redact_pii_decorator,
)


class TestPatterns:
    """Tests for PII patterns."""

    def test_email_pattern(self):
        """Test email pattern detection."""
        assert EMAIL_PATTERN.search("user@example.com")
        assert EMAIL_PATTERN.search("test.email+tag@domain.org")
        assert not EMAIL_PATTERN.search("not-an-email")

    def test_ssn_pattern(self):
        """Test SSN pattern detection."""
        assert SSN_PATTERN.search("123-45-6789")
        assert not SSN_PATTERN.search("1234567890")
        assert not SSN_PATTERN.search("123-456-789")

    def test_credit_card_pattern(self):
        """Test credit card pattern detection."""
        assert CREDIT_CARD_PATTERN.search("1234-5678-9012-3456")
        assert CREDIT_CARD_PATTERN.search("1234 5678 9012 3456")
        assert CREDIT_CARD_PATTERN.search("1234567890123456")
        assert not CREDIT_CARD_PATTERN.search("1234-5678")

    def test_phone_pattern(self):
        """Test phone pattern detection."""
        assert PHONE_PATTERN.search("123-456-7890")
        assert PHONE_PATTERN.search("123.456.7890")
        assert PHONE_PATTERN.search("1234567890")
        assert not PHONE_PATTERN.search("12-345-6789")


class TestRedactPii:
    """Tests for redact_pii function."""

    def test_redact_specified_fields(self):
        """Test redacting specified fields."""
        data = {
            "email": "user@example.com",
            "name": "John Doe",
            "phone": "123-456-7890",
        }

        result = redact_pii(data, fields=["email", "phone"], auto_detect=False)

        assert result["email"] == "[REDACTED]"
        assert result["phone"] == "[REDACTED]"
        assert result["name"] == "John Doe"

    def test_redact_default_fields(self):
        """Test redacting default PII fields."""
        data = {
            "email": "user@example.com",
            "ssn": "123-45-6789",
            "password": "secret",
            "name": "John Doe",
        }

        result = redact_pii(data, auto_detect=False)

        assert result["email"] == "[REDACTED]"
        assert result["ssn"] == "[REDACTED]"
        assert result["password"] == "[REDACTED]"
        assert result["name"] == "John Doe"

    def test_custom_redaction_string(self):
        """Test custom redaction string."""
        data = {"email": "user@example.com"}

        result = redact_pii(data, fields=["email"], redaction_string="***", auto_detect=False)

        assert result["email"] == "***"

    def test_auto_detect_email(self):
        """Test auto-detection of email patterns."""
        data = {"message": "Contact me at user@example.com"}

        result = redact_pii(data, fields=[], auto_detect=True)

        assert result["message"] == "[REDACTED]"

    def test_auto_detect_ssn(self):
        """Test auto-detection of SSN patterns."""
        data = {"note": "SSN: 123-45-6789"}

        result = redact_pii(data, fields=[], auto_detect=True)

        assert result["note"] == "[REDACTED]"

    def test_auto_detect_credit_card(self):
        """Test auto-detection of credit card patterns."""
        data = {"payment": "Card: 1234-5678-9012-3456"}

        result = redact_pii(data, fields=[], auto_detect=True)

        assert result["payment"] == "[REDACTED]"

    def test_auto_detect_phone(self):
        """Test auto-detection of phone patterns."""
        data = {"contact": "Call 555-123-4567"}

        result = redact_pii(data, fields=[], auto_detect=True)

        assert result["contact"] == "[REDACTED]"

    def test_no_auto_detect(self):
        """Test with auto_detect disabled."""
        data = {"message": "Email: user@example.com"}

        result = redact_pii(data, fields=[], auto_detect=False)

        assert result["message"] == "Email: user@example.com"

    def test_original_data_unchanged(self):
        """Test that original data is not modified."""
        data = {"email": "user@example.com"}

        redact_pii(data, fields=["email"])

        assert data["email"] == "user@example.com"

    def test_empty_data(self):
        """Test with empty dictionary."""
        data = {}

        result = redact_pii(data)

        assert result == {}

    def test_non_string_values(self):
        """Test that non-string values are not affected."""
        data = {
            "count": 42,
            "active": True,
            "items": [1, 2, 3],
        }

        result = redact_pii(data, auto_detect=True)

        assert result["count"] == 42
        assert result["active"] is True
        assert result["items"] == [1, 2, 3]

    def test_already_redacted_not_reprocessed(self):
        """Test that already redacted values are not reprocessed."""
        data = {"email": "[REDACTED]"}

        result = redact_pii(data, fields=[], auto_detect=True)

        assert result["email"] == "[REDACTED]"

    def test_auto_detect_no_pii_found(self):
        """Test auto-detection with string values that are NOT PII."""
        data = {
            "greeting": "Hello world",
            "description": "This is a normal text without any PII",
            "code": "ABC123XYZ",
        }

        result = redact_pii(data, fields=[], auto_detect=True)

        # None of these should be redacted
        assert result["greeting"] == "Hello world"
        assert result["description"] == "This is a normal text without any PII"
        assert result["code"] == "ABC123XYZ"


class TestRedactPiiDecorator:
    """Tests for redact_pii_decorator function."""

    def test_decorator_returns_function(self):
        """Test decorator returns the function."""

        @redact_pii_decorator(fields=["email"])
        def test_func():
            return "test"

        assert test_func() == "test"

    def test_decorator_with_custom_fields(self):
        """Test decorator with custom fields."""

        @redact_pii_decorator(fields=["email", "credit_card"])
        def process_payment(email, card):
            return {"email": email, "card": card}

        result = process_payment("user@example.com", "1234-5678-9012-3456")

        # Current implementation is a pass-through
        assert result["email"] == "user@example.com"

    def test_decorator_preserves_function_behavior(self):
        """Test decorator preserves original function behavior."""

        @redact_pii_decorator()
        def add_numbers(a, b):
            return a + b

        assert add_numbers(2, 3) == 5

    def test_decorator_with_custom_redaction_string(self):
        """Test decorator with custom redaction string."""

        @redact_pii_decorator(
            fields=["sensitive"],
            redaction_string="[HIDDEN]",
        )
        def get_data():
            return "data"

        assert get_data() == "data"
