"""Unit tests for schema validation metrics."""

import pytest

from obskit.validation import (
    ValidationError,
    ValidationException,
    ValidationResult,
    ValidationTracker,
    validate_range,
    validate_required,
    validate_type,
)


class TestValidationError:
    """Tests for ValidationError dataclass."""

    def test_init(self):
        """Test initialization."""
        error = ValidationError(field="email", error_type="format", message="Invalid email format")

        assert error.field == "email"
        assert error.error_type == "format"
        assert error.message == "Invalid email format"

    def test_init_with_all_fields(self):
        """Test initialization with all fields."""
        error = ValidationError(
            field="age",
            error_type="range",
            message="Age must be positive",
            value=-5,
            expected=">= 0",
        )

        assert error.value == -5
        assert error.expected == ">= 0"

    def test_to_dict(self):
        """Test conversion to dictionary."""
        error = ValidationError(
            field="name",
            error_type="required",
            message="Name is required",
            value=None,
            expected="non-null",
        )

        data = error.to_dict()

        assert data["field"] == "name"
        assert data["error_type"] == "required"
        assert data["message"] == "Name is required"


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_init_valid(self):
        """Test valid result initialization."""
        result = ValidationResult(valid=True, schema_name="user_input")

        assert result.valid is True
        assert result.schema_name == "user_input"
        assert result.errors == []
        assert result.warnings == []

    def test_init_invalid(self):
        """Test invalid result with errors."""
        errors = [ValidationError(field="email", error_type="format", message="Invalid")]

        result = ValidationResult(valid=False, schema_name="user_input", errors=errors)

        assert result.valid is False
        assert len(result.errors) == 1

    def test_to_dict(self):
        """Test conversion to dictionary."""
        result = ValidationResult(
            valid=False,
            schema_name="user_input",
            errors=[ValidationError(field="name", error_type="required", message="Required")],
        )

        data = result.to_dict()

        assert data["valid"] is False
        assert data["schema_name"] == "user_input"
        assert data["error_count"] == 1
        assert data["warning_count"] == 0


class TestValidationTracker:
    """Tests for ValidationTracker class."""

    def test_init(self):
        """Test tracker initialization."""
        tracker = ValidationTracker("api_requests")

        assert tracker.schema_name == "api_requests"
        assert tracker._total_validations == 0

    def test_validate_with_bool_validator_success(self):
        """Test validation with bool-returning validator."""
        tracker = ValidationTracker("test")

        def validator(data):
            return data.get("name") is not None

        result = tracker.validate({"name": "John"}, validator=validator)

        assert result.valid is True

    def test_validate_with_bool_validator_failure(self):
        """Test validation with bool-returning validator failure."""
        tracker = ValidationTracker("test")

        def validator(data):
            return data.get("name") is not None

        result = tracker.validate({}, validator=validator)

        assert result.valid is False

    def test_validate_with_dict_validator(self):
        """Test validation with dict-returning validator."""
        tracker = ValidationTracker("test")

        def validator(data):
            errors = []
            if not data.get("name"):
                errors.append(
                    {"field": "name", "error_type": "required", "message": "Name is required"}
                )
            return {"valid": len(errors) == 0, "errors": errors}

        result = tracker.validate({}, validator=validator)

        assert result.valid is False
        assert len(result.errors) == 1
        assert result.errors[0].field == "name"

    def test_validate_with_list_validator(self):
        """Test validation with list-returning validator."""
        tracker = ValidationTracker("test")

        def validator(data):
            errors = []
            if not data.get("name"):
                errors.append("Name is required")
            if not data.get("email"):
                errors.append("Email is required")
            return errors

        result = tracker.validate({}, validator=validator)

        assert result.valid is False
        assert len(result.errors) == 2

    def test_validate_raises_on_error(self):
        """Test validation raises exception when configured."""
        tracker = ValidationTracker("test")

        def validator(data):
            return False

        with pytest.raises(ValidationException):
            tracker.validate({}, validator=validator, raise_on_error=True)

    def test_validate_no_raise_by_default(self):
        """Test validation doesn't raise by default."""
        tracker = ValidationTracker("test")

        def validator(data):
            return False

        result = tracker.validate({}, validator=validator)

        assert result.valid is False  # No exception raised

    def test_validate_handles_validator_exception(self):
        """Test validation handles validator exceptions."""
        tracker = ValidationTracker("test")

        def failing_validator(data):
            raise ValueError("Validator crashed")

        result = tracker.validate({}, validator=failing_validator)

        assert result.valid is False
        assert "Validator crashed" in result.errors[0].message

    def test_get_stats(self):
        """Test getting validation statistics."""
        tracker = ValidationTracker("test")

        tracker.validate({"name": "John"}, validator=lambda d: True)
        tracker.validate({}, validator=lambda d: False)
        tracker.validate({}, validator=lambda d: False)

        stats = tracker.get_stats()

        assert stats["schema_name"] == "test"
        assert stats["total_validations"] == 3
        assert stats["successful_validations"] == 1
        assert stats["failed_validations"] == 2
        assert stats["success_rate"] < 1.0

    def test_validated_decorator(self):
        """Test @validated decorator."""
        tracker = ValidationTracker("test")

        def validator(data):
            return data.get("valid", False)

        @tracker.validated(validator=validator, raise_on_error=False)
        def process_data(data):
            return "processed"

        result = process_data({"valid": True})
        assert result == "processed"

    def test_validated_decorator_raises(self):
        """Test @validated decorator raises on invalid data."""
        tracker = ValidationTracker("test")

        def validator(data):
            return False

        @tracker.validated(validator=validator, raise_on_error=True)
        def process_data(data):
            return "processed"

        with pytest.raises(ValidationException):
            process_data({"invalid": True})


class TestValidationException:
    """Tests for ValidationException class."""

    def test_init(self):
        """Test exception initialization."""
        result = ValidationResult(
            valid=False,
            schema_name="test",
            errors=[ValidationError(field="name", error_type="required", message="Required")],
        )

        exc = ValidationException(result)

        assert exc.result is result
        assert "1 error" in str(exc)

    def test_to_dict(self):
        """Test exception to_dict method."""
        result = ValidationResult(
            valid=False,
            schema_name="test",
            errors=[ValidationError(field="name", error_type="required", message="Required")],
        )

        exc = ValidationException(result)
        data = exc.to_dict()

        assert data["valid"] is False
        assert data["error_count"] == 1


class TestValidationHelpers:
    """Tests for validation helper functions."""

    def test_validate_required_all_present(self):
        """Test validate_required with all fields present."""
        data = {"name": "John", "email": "john@example.com"}

        errors = validate_required(data, ["name", "email"])

        assert len(errors) == 0

    def test_validate_required_missing_fields(self):
        """Test validate_required with missing fields."""
        data = {"name": "John"}

        errors = validate_required(data, ["name", "email", "phone"])

        assert len(errors) == 2
        fields = [e.field for e in errors]
        assert "email" in fields
        assert "phone" in fields

    def test_validate_required_none_values(self):
        """Test validate_required treats None as missing."""
        data = {"name": "John", "email": None}

        errors = validate_required(data, ["name", "email"])

        assert len(errors) == 1
        assert errors[0].field == "email"

    def test_validate_type_correct_types(self):
        """Test validate_type with correct types."""
        data = {"name": "John", "age": 30, "active": True}

        errors = validate_type(data, {"name": str, "age": int, "active": bool})

        assert len(errors) == 0

    def test_validate_type_wrong_types(self):
        """Test validate_type with wrong types."""
        data = {"name": 123, "age": "thirty"}

        errors = validate_type(data, {"name": str, "age": int})

        assert len(errors) == 2

    def test_validate_type_missing_fields_not_error(self):
        """Test validate_type ignores missing fields."""
        data = {"name": "John"}

        errors = validate_type(
            data,
            {
                "name": str,
                "age": int,  # Not in data
            },
        )

        assert len(errors) == 0

    def test_validate_range_within_range(self):
        """Test validate_range with values in range."""
        data = {"age": 25, "score": 85}

        errors = validate_range(data, {"age": (18, 100), "score": (0, 100)})

        assert len(errors) == 0

    def test_validate_range_below_minimum(self):
        """Test validate_range with value below minimum."""
        data = {"age": 15}

        errors = validate_range(data, {"age": (18, 100)})

        assert len(errors) == 1
        assert "less than minimum" in errors[0].message.lower()

    def test_validate_range_above_maximum(self):
        """Test validate_range with value above maximum."""
        data = {"score": 150}

        errors = validate_range(data, {"score": (0, 100)})

        assert len(errors) == 1
        assert "greater than maximum" in errors[0].message.lower()

    def test_validate_range_none_bounds(self):
        """Test validate_range with None bounds (no limit)."""
        data = {"value": 1000000}

        # Only minimum, no maximum
        errors = validate_range(data, {"value": (0, None)})

        assert len(errors) == 0

    def test_validate_range_non_numeric_ignored(self):
        """Test validate_range ignores non-numeric values."""
        data = {"name": "John", "age": 25}

        errors = validate_range(
            data,
            {
                "name": (0, 100),  # String, ignored
                "age": (18, 100),
            },
        )

        assert len(errors) == 0
