"""
Tests for obskit.fingerprint module.

Tests cover:
- ErrorGroup and FingerprintResult dataclasses
- ErrorFingerprinter: get_fingerprint, _normalize_message, _create_stack_signature
- ErrorFingerprinter: _detect_component, record_error, get_group, get_all_groups
- ErrorFingerprinter: get_top_errors, get_recent_errors, clear, max_groups eviction
- Singleton helpers: get_error_fingerprinter, get_error_group, get_fingerprint
"""

import traceback
from datetime import datetime, timezone, UTC
from unittest.mock import MagicMock, patch

import pytest

from obskit.fingerprint import (
    ErrorFingerprinter,
    ErrorGroup,
    FingerprintResult,
    get_error_fingerprinter,
    get_error_group,
    get_fingerprint,
)

# =============================================================================
# ErrorGroup dataclass
# =============================================================================


class TestErrorGroup:
    def test_default_values(self):
        group = ErrorGroup(
            fingerprint="abc123",
            error_type="ValueError",
            message_template="Invalid value <NUM>",
        )
        assert group.fingerprint == "abc123"
        assert group.error_type == "ValueError"
        assert group.message_template == "Invalid value <NUM>"
        assert group.component is None
        assert group.count == 0
        assert group.sample_stack_trace is None
        assert group.affected_operations == set()

    def test_to_dict(self):
        group = ErrorGroup(
            fingerprint="fp001",
            error_type="KeyError",
            message_template="Key '<VAR>'",
            component="service",
            count=5,
            sample_stack_trace="Traceback...",
        )
        group.affected_operations.add("process_order")
        d = group.to_dict()
        assert d["fingerprint"] == "fp001"
        assert d["error_type"] == "KeyError"
        assert d["component"] == "service"
        assert d["count"] == 5
        assert "process_order" in d["affected_operations"]
        assert "first_seen" in d
        assert "last_seen" in d


# =============================================================================
# FingerprintResult dataclass
# =============================================================================


class TestFingerprintResult:
    def test_to_dict(self):
        result = FingerprintResult(
            fingerprint="fp-abc",
            error_type="TypeError",
            message_template="Type error: <VAR>",
            stack_signature="module.py:func:42",
            component="handler",
        )
        d = result.to_dict()
        assert d["fingerprint"] == "fp-abc"
        assert d["error_type"] == "TypeError"
        assert d["message_template"] == "Type error: <VAR>"
        assert d["stack_signature"] == "module.py:func:42"
        assert d["component"] == "handler"

    def test_to_dict_no_component(self):
        result = FingerprintResult(
            fingerprint="fp-xyz",
            error_type="OSError",
            message_template="OS error",
            stack_signature="no_stack",
        )
        d = result.to_dict()
        assert d["component"] is None


# =============================================================================
# ErrorFingerprinter initialization
# =============================================================================


class TestErrorFingerprinterInit:
    def test_default_initialization(self):
        fp = ErrorFingerprinter()
        assert fp.service_name == "default"
        assert fp.normalize_paths is True
        assert fp.normalize_numbers is True
        assert fp.max_groups == 1000
        assert fp._groups == {}

    def test_custom_initialization(self):
        fp = ErrorFingerprinter(
            service_name="my-service",
            normalize_paths=False,
            normalize_numbers=False,
            max_groups=50,
        )
        assert fp.service_name == "my-service"
        assert fp.normalize_paths is False
        assert fp.normalize_numbers is False
        assert fp.max_groups == 50


# =============================================================================
# ErrorFingerprinter._normalize_message
# =============================================================================


class TestNormalizeMessage:
    def setup_method(self):
        self.fp = ErrorFingerprinter()

    def test_normalize_numbers(self):
        result = self.fp._normalize_message("Error on line 42 with value 100")
        assert "<NUM>" in result
        assert "42" not in result
        assert "100" not in result

    def test_normalize_uuid(self):
        msg = "User 550e8400-e29b-41d4-a716-446655440000 not found"
        result = self.fp._normalize_message(msg)
        assert "<UUID>" in result
        assert "550e8400" not in result

    def test_normalize_hex(self):
        msg = "Memory address 0x7f3a4b2c"
        result = self.fp._normalize_message(msg)
        assert "<HEX>" in result

    def test_normalize_ip(self):
        msg = "Connection refused from 192.168.1.100"
        result = self.fp._normalize_message(msg)
        assert "<IP>" in result
        assert "192.168.1.100" not in result

    def test_normalize_paths(self):
        msg = "File not found: /usr/local/bin/python3"
        result = self.fp._normalize_message(msg)
        assert "<PATH>" in result

    def test_normalize_single_quotes(self):
        msg = "Key 'user_id' is invalid"
        result = self.fp._normalize_message(msg)
        assert "'<VAR>'" in result

    def test_normalize_double_quotes(self):
        msg = 'Value "some_value" not found'
        result = self.fp._normalize_message(msg)
        assert '"<VAR>"' in result

    def test_no_normalization_when_disabled(self):
        fp = ErrorFingerprinter(normalize_numbers=False, normalize_paths=False)
        msg = "Error on line 42 at /some/path"
        result = fp._normalize_message(msg)
        # Should still normalize quotes but not numbers/paths
        assert "42" in result

    def test_empty_message(self):
        result = self.fp._normalize_message("")
        assert result == ""


# =============================================================================
# ErrorFingerprinter._create_stack_signature
# =============================================================================


class TestCreateStackSignature:
    def setup_method(self):
        self.fp = ErrorFingerprinter()

    def test_empty_traceback_returns_no_stack(self):
        result = self.fp._create_stack_signature([])
        assert result == "no_stack"

    def test_single_frame(self):
        # Create a real traceback by raising an exception
        try:
            raise ValueError("test")
        except ValueError as e:
            tb = traceback.extract_tb(e.__traceback__)

        sig = self.fp._create_stack_signature(tb)
        assert ":" in sig  # should be filename:func:line format

    def test_max_frames_respected(self):
        try:
            raise ValueError("test")
        except ValueError as e:
            tb = traceback.extract_tb(e.__traceback__)

        sig = self.fp._create_stack_signature(tb, max_frames=2)
        # Result is pipe-separated, so should have at most 2 parts
        parts = sig.split("|")
        assert len(parts) <= 2

    def test_skips_site_packages(self):
        """Test that site-packages frames are skipped if possible."""
        from unittest.mock import MagicMock

        # Create fake frames
        frame1 = MagicMock()
        frame1.filename = "/usr/local/lib/python3.11/site-packages/requests/api.py"
        frame1.name = "get"
        frame1.lineno = 75

        frame2 = MagicMock()
        frame2.filename = "/app/myservice/handler.py"
        frame2.name = "handle"
        frame2.lineno = 42

        sig = self.fp._create_stack_signature([frame1, frame2])
        # handler.py should be in the signature
        assert "handler.py" in sig


# =============================================================================
# ErrorFingerprinter._detect_component
# =============================================================================


class TestDetectComponent:
    def setup_method(self):
        self.fp = ErrorFingerprinter()

    def test_empty_traceback_returns_none(self):
        result = self.fp._detect_component([])
        assert result is None

    def _make_frame(self, filename, func="func", lineno=1):
        frame = MagicMock()
        frame.filename = filename
        frame.name = func
        frame.lineno = lineno
        return frame

    def test_detects_controller(self):
        frame = self._make_frame("/app/orders/controller.py")
        assert self.fp._detect_component([frame]) == "controller"

    def test_detects_service(self):
        frame = self._make_frame("/app/orders/service.py")
        assert self.fp._detect_component([frame]) == "service"

    def test_detects_handler(self):
        frame = self._make_frame("/app/events/handler.py")
        assert self.fp._detect_component([frame]) == "handler"

    def test_detects_middleware(self):
        frame = self._make_frame("/app/auth/middleware.py")
        assert self.fp._detect_component([frame]) == "middleware"

    def test_detects_widget(self):
        frame = self._make_frame("/app/ui/widget.py")
        assert self.fp._detect_component([frame]) == "widget"

    def test_detects_page(self):
        frame = self._make_frame("/app/views/page.py")
        assert self.fp._detect_component([frame]) == "page"

    def test_detects_query_builder(self):
        frame = self._make_frame("/app/db/query.py")
        assert self.fp._detect_component([frame]) == "query_builder"

    def test_unknown_component_returns_none(self):
        frame = self._make_frame("/app/utils/helper.py")
        assert self.fp._detect_component([frame]) is None


# =============================================================================
# ErrorFingerprinter.get_fingerprint
# =============================================================================


class TestGetFingerprint:
    def setup_method(self):
        self.fp = ErrorFingerprinter()

    def test_returns_fingerprint_result(self):
        try:
            raise ValueError("test error")
        except ValueError as e:
            result = self.fp.get_fingerprint(e)

        assert isinstance(result, FingerprintResult)
        assert result.fingerprint is not None
        assert len(result.fingerprint) == 12  # md5[:12]
        assert result.error_type == "ValueError"

    def test_same_exception_same_fingerprint(self):
        # Fingerprints include stack info - create exception without traceback
        # so both produce the same "no_stack" signature
        e1 = ValueError("same error message")
        e2 = ValueError("same error message")
        fp1 = self.fp.get_fingerprint(e1)
        fp2 = self.fp.get_fingerprint(e2)
        assert fp1.fingerprint == fp2.fingerprint

    def test_different_messages_different_fingerprints(self):
        e1 = ValueError("error A for fp test unique message")
        e2 = ValueError("error B for fp test different abc xyz 123")
        fp1 = self.fp.get_fingerprint(e1)
        fp2 = self.fp.get_fingerprint(e2)
        assert fp1.fingerprint != fp2.fingerprint

    def test_exception_without_traceback(self):
        e = ValueError("no traceback")
        result = self.fp.get_fingerprint(e)
        assert result.stack_signature == "no_stack"

    def test_component_passed_explicitly(self):
        e = ValueError("test")
        result = self.fp.get_fingerprint(e, component="api")
        assert result.component == "api"

    def test_error_type_captured(self):
        e = KeyError("missing_key")
        result = self.fp.get_fingerprint(e)
        assert result.error_type == "KeyError"


# =============================================================================
# ErrorFingerprinter.record_error
# =============================================================================


class TestRecordError:
    def setup_method(self):
        self.fp = ErrorFingerprinter(service_name="test-svc")

    def test_record_error_returns_group(self):
        try:
            raise ValueError("test record")
        except ValueError as e:
            group = self.fp.record_error(e)

        assert isinstance(group, ErrorGroup)
        assert group.count == 1

    def test_record_same_error_increments_count(self):
        for _ in range(5):
            try:
                raise ValueError("repeated error")
            except ValueError as e:
                group = self.fp.record_error(e)

        assert group.count == 5

    def test_record_error_with_operation(self):
        try:
            raise ValueError("op error")
        except ValueError as e:
            group = self.fp.record_error(e, operation="process_order")

        assert "process_order" in group.affected_operations

    def test_record_error_with_component(self):
        try:
            raise ValueError("comp error")
        except ValueError as e:
            group = self.fp.record_error(e, component="api_gateway")

        assert group.component == "api_gateway"

    def test_max_groups_eviction(self):
        fp = ErrorFingerprinter(max_groups=2)
        # Fill up to max groups with unique errors (no traceback so fingerprint is based on message)
        errors = [
            ValueError("unique error message one only once xyz abc"),
            KeyError("another unique error two abc def ghi jkl"),
            TypeError("type error three xyz abc mno pqr"),
        ]
        for e in errors:
            fp.record_error(e)

        # Should not exceed max_groups (eviction happens before add)
        assert len(fp._groups) <= 2

    def test_record_error_updates_last_seen(self):
        before = datetime.now(UTC)
        try:
            raise ValueError("timestamp check")
        except ValueError as e:
            group = self.fp.record_error(e)
        after = datetime.now(UTC)
        assert before <= group.last_seen <= after


# =============================================================================
# ErrorFingerprinter query methods
# =============================================================================


class TestErrorFingerprinterQueries:
    def setup_method(self):
        self.fp = ErrorFingerprinter(service_name="query-test")
        # Populate some groups
        for i in range(3):
            try:
                raise ValueError(f"error {i} query test unique abc")
            except ValueError as e:
                for _ in range(i + 1):
                    self.fp.record_error(e)

    def test_get_group_by_fingerprint(self):
        groups = self.fp.get_all_groups()
        assert len(groups) >= 1
        fp = groups[0].fingerprint
        found = self.fp.get_group(fp)
        assert found is not None
        assert found.fingerprint == fp

    def test_get_group_nonexistent_returns_none(self):
        result = self.fp.get_group("nonexistent_fp")
        assert result is None

    def test_get_all_groups(self):
        groups = self.fp.get_all_groups()
        assert isinstance(groups, list)
        assert len(groups) >= 1

    def test_get_top_errors_sorted_by_count(self):
        top = self.fp.get_top_errors(limit=3)
        assert len(top) >= 1
        for a, b in zip(top, top[1:], strict=False):
            assert a.count >= b.count

    def test_get_top_errors_limit(self):
        top = self.fp.get_top_errors(limit=1)
        assert len(top) <= 1

    def test_get_recent_errors_sorted_by_last_seen(self):
        recent = self.fp.get_recent_errors(limit=3)
        assert len(recent) >= 1
        for a, b in zip(recent, recent[1:], strict=False):
            assert a.last_seen >= b.last_seen

    def test_clear(self):
        assert len(self.fp._groups) > 0
        self.fp.clear()
        assert len(self.fp._groups) == 0


# =============================================================================
# Singleton helpers
# =============================================================================


class TestSingletonHelpers:
    def setup_method(self):
        # Reset the global fingerprinter before each test
        import obskit.fingerprint as module

        module._fingerprinter = None

    def test_get_error_fingerprinter_creates_instance(self):
        fp = get_error_fingerprinter("my-service")
        assert isinstance(fp, ErrorFingerprinter)
        assert fp.service_name == "my-service"

    def test_get_error_fingerprinter_returns_same_instance(self):
        fp1 = get_error_fingerprinter("svc")
        fp2 = get_error_fingerprinter("svc")
        assert fp1 is fp2

    def test_get_error_group_returns_group(self):
        try:
            raise ValueError("helper test")
        except ValueError as e:
            group = get_error_group(e)
        assert isinstance(group, ErrorGroup)

    def test_get_fingerprint_returns_string(self):
        e = ValueError("fingerprint helper")
        fp = get_fingerprint(e)
        assert isinstance(fp, str)
        assert len(fp) == 12
