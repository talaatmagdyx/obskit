"""Tests for obskit.logging.redaction — sensitive field redaction processor."""

from __future__ import annotations

import pytest

from obskit.logging.redaction import (
    DEFAULT_SENSITIVE_FIELDS,
    make_redaction_processor,
    redact_sensitive_fields,
)


class TestMakeRedactionProcessor:
    """make_redaction_processor() — factory function."""

    def test_returns_callable(self) -> None:
        """Returns a callable processor."""
        processor = make_redaction_processor()
        assert callable(processor)

    def test_processor_name(self) -> None:
        """Processor has the correct __name__."""
        processor = make_redaction_processor()
        assert processor.__name__ == "redact_sensitive_fields"

    def test_redacts_password_field(self) -> None:
        """'password' field value is replaced with placeholder."""
        processor = make_redaction_processor()
        result = processor(None, "info", {"event": "login", "password": "s3cr3t"})
        assert result["password"] == "[REDACTED]"
        assert result["event"] == "login"

    def test_redacts_token_field(self) -> None:
        """'token' field value is replaced."""
        processor = make_redaction_processor()
        result = processor(None, "info", {"event": "auth", "token": "abc123"})
        assert result["token"] == "[REDACTED]"

    def test_redacts_api_key_field(self) -> None:
        """'api_key' field value is replaced."""
        processor = make_redaction_processor()
        result = processor(None, "info", {"event": "request", "api_key": "sk-xyz"})
        assert result["api_key"] == "[REDACTED]"

    def test_case_insensitive_matching(self) -> None:
        """Field matching is case-insensitive."""
        processor = make_redaction_processor()
        result = processor(None, "info", {"Access_Token": "secret", "event": "ok"})
        assert result["Access_Token"] == "[REDACTED]"

    def test_substring_matching(self) -> None:
        """Substring match: 'access_token' contains 'token' → redacted."""
        processor = make_redaction_processor()
        result = processor(None, "info", {"access_token": "val", "event": "ok"})
        assert result["access_token"] == "[REDACTED]"

    def test_non_sensitive_fields_preserved(self) -> None:
        """Non-sensitive fields pass through unchanged."""
        processor = make_redaction_processor()
        result = processor(None, "info", {"event": "ok", "user_id": 42, "action": "read"})
        assert result["event"] == "ok"
        assert result["user_id"] == 42
        assert result["action"] == "read"

    def test_custom_fields(self) -> None:
        """Custom fields are redacted when specified."""
        processor = make_redaction_processor(fields={"ssn", "credit_card"})
        result = processor(
            None, "info", {"ssn": "123-45-6789", "event": "ok", "token": "not_redacted"}
        )
        assert result["ssn"] == "[REDACTED]"
        # "token" not in custom fields, so not redacted
        assert result["token"] == "not_redacted"

    def test_custom_placeholder(self) -> None:
        """Custom placeholder replaces default [REDACTED]."""
        processor = make_redaction_processor(placeholder="***")
        result = processor(None, "info", {"password": "secret", "event": "ok"})
        assert result["password"] == "***"

    def test_nested_dict_redaction(self) -> None:
        """Sensitive keys in nested dicts are also redacted."""
        processor = make_redaction_processor()
        event = {
            "event": "request",
            "headers": {
                "Authorization": "Bearer token123",
                "Content-Type": "application/json",
            },
        }
        result = processor(None, "info", event)
        # "Authorization" contains "auth" → redacted
        assert result["headers"]["Authorization"] == "[REDACTED]"
        assert result["headers"]["Content-Type"] == "application/json"

    def test_non_dict_value_not_recursed(self) -> None:
        """Non-dict values are passed through as-is."""
        processor = make_redaction_processor()
        result = processor(None, "info", {"event": "ok", "data": [1, 2, 3]})
        assert result["data"] == [1, 2, 3]

    def test_depth_limit_stops_recursion(self) -> None:
        """Depth > 10 stops recursion — returns obj unchanged."""
        processor = make_redaction_processor()
        # Build deeply nested dict (12 levels)
        deep: dict = {}
        current = deep
        for i in range(12):
            current["nested"] = {}
            current = current["nested"]
        current["password"] = "should_not_be_redacted_if_depth_exceeded"
        # Should not raise
        result = processor(None, "info", {"event": "ok", "deep": deep})
        assert isinstance(result, dict)

    def test_empty_event_dict(self) -> None:
        """Empty event dict returns empty dict."""
        processor = make_redaction_processor()
        result = processor(None, "info", {})
        assert result == {}

    def test_original_not_mutated(self) -> None:
        """Original event_dict is not mutated."""
        processor = make_redaction_processor()
        original = {"password": "secret", "event": "login"}
        processor(None, "info", original)
        # Original should be unchanged
        assert original["password"] == "secret"


class TestRedactSensitiveFields:
    """redact_sensitive_fields — convenience singleton."""

    def test_is_callable(self) -> None:
        """Singleton is callable."""
        assert callable(redact_sensitive_fields)

    def test_redacts_password(self) -> None:
        """Singleton redacts password field."""
        result = redact_sensitive_fields(None, "info", {"event": "ok", "password": "x"})
        assert result["password"] == "[REDACTED]"


class TestDefaultSensitiveFields:
    """DEFAULT_SENSITIVE_FIELDS constant."""

    def test_is_frozenset(self) -> None:
        assert isinstance(DEFAULT_SENSITIVE_FIELDS, frozenset)

    def test_contains_expected_patterns(self) -> None:
        for expected in ("password", "token", "api_key", "secret", "auth"):
            assert expected in DEFAULT_SENSITIVE_FIELDS


class TestNonStringKeyHandling:
    """Non-string dict keys pass through without TypeError (Fix #8)."""

    def test_integer_key_passes_through(self) -> None:
        """Integer key does not raise TypeError and value is preserved."""
        processor = make_redaction_processor()
        result = processor(None, "info", {"event": "ok", 42: "value"})
        assert result[42] == "value"

    def test_integer_key_with_sensitive_string_sibling(self) -> None:
        """Integer key coexists with a sensitive string key."""
        processor = make_redaction_processor()
        result = processor(None, "info", {"event": "ok", 1: "num", "password": "s3cr3t"})
        assert result[1] == "num"
        assert result["password"] == "[REDACTED]"


class TestListRedaction:
    """List values containing dicts are recursed into (Fix #9)."""

    def test_list_with_sensitive_dict_items_redacted(self) -> None:
        """Dicts inside a list have their sensitive keys redacted."""
        processor = make_redaction_processor()
        result = processor(
            None,
            "info",
            {"event": "ok", "users": [{"password": "s3cr3t", "name": "alice"}]},
        )
        assert result["users"][0]["password"] == "[REDACTED]"
        assert result["users"][0]["name"] == "alice"

    def test_list_with_non_dict_items_unchanged(self) -> None:
        """Non-dict items inside a list are not modified."""
        processor = make_redaction_processor()
        result = processor(None, "info", {"event": "ok", "ids": [1, "two", None]})
        assert result["ids"] == [1, "two", None]

    def test_list_mixed_dict_and_primitive(self) -> None:
        """List with both dicts and primitives: dicts redacted, primitives pass through."""
        processor = make_redaction_processor()
        result = processor(
            None,
            "info",
            {"event": "ok", "items": [{"token": "abc"}, "plain", {"name": "x"}]},
        )
        assert result["items"][0]["token"] == "[REDACTED]"
        assert result["items"][1] == "plain"
        assert result["items"][2]["name"] == "x"


class TestCircularReferenceHandling:
    """Redaction processor handles circular references safely."""

    def test_circular_reference_returns_placeholder(self) -> None:
        """Circular dict reference is replaced with '<circular>' (line 105)."""
        processor = make_redaction_processor()

        # Build a dict that references itself: d["nested"] = d
        d: dict = {}
        d["nested"] = d  # type: ignore[assignment]

        # _redact_value processes event_dict: adds id(event_dict) to seen
        # Then processes "data" → recurses into d with seen={id(event_dict)}
        # Inside d: adds id(d) to seen, processes "nested" → recurses into d again
        # Now id(d) IS in seen → returns "<circular>"
        result = processor(None, "info", {"event": "ok", "data": d})
        # result["data"] is the redacted version of d: {"nested": "<circular>"}
        assert result["data"]["nested"] == "<circular>"
