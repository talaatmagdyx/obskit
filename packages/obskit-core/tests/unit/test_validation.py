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


class TestValidationTrackerSchema:
    def test_validate_with_no_validator_no_schema(self):
        tracker = ValidationTracker('test')
        result = tracker.validate({'key': 'value'})
        assert result.valid is True

    def test_validate_with_schema_pydantic_v2(self):
        from unittest.mock import MagicMock
        tracker = ValidationTracker('test')
        schema = MagicMock()
        schema.model_validate = MagicMock(return_value=None)
        result = tracker.validate({'name': 'test'}, schema=schema)
        assert result.valid is True

    def test_validate_with_pydantic_v2_failure_with_errors_method(self):
        from unittest.mock import MagicMock
        tracker = ValidationTracker('test')
        schema = MagicMock()
        # Create an exception that has an errors() method (like pydantic)
        class PydanticError(Exception):
            def errors(self):
                return [{'loc': ('name',), 'type': 'missing', 'msg': 'field required', 'input': None}]
        schema.model_validate.side_effect = PydanticError('validation error')
        result = tracker.validate({}, schema=schema)
        assert result.valid is False

    def test_validate_with_pydantic_v2_failure_without_errors_method(self):
        from unittest.mock import MagicMock
        tracker = ValidationTracker('test')
        schema = MagicMock()
        plain_exc = ValueError('plain error')
        schema.model_validate.side_effect = plain_exc
        result = tracker.validate({}, schema=schema)
        assert result.valid is False
        assert 'plain error' in result.errors[0].message

    def test_validate_with_pydantic_v1_schema(self):
        from unittest.mock import MagicMock
        tracker = ValidationTracker('test')
        # v1 schema: has parse_obj but not model_validate
        schema = MagicMock(spec=['parse_obj'])
        schema.parse_obj = MagicMock(return_value=None)
        result = tracker.validate({'name': 'test'}, schema=schema)
        assert result.valid is True

    def test_validate_with_unknown_schema_type(self):
        tracker = ValidationTracker('test')
        # An object that is neither pydantic nor a dict with type/properties
        schema = object()
        result = tracker.validate({'key': 'value'}, schema=schema)
        assert result.valid is True

    def test_validate_with_jsonschema_dict_type(self):
        tracker = ValidationTracker('test')
        schema = {'type': 'object', 'properties': {'name': {'type': 'string'}}}
        try:
            import jsonschema as _js  # noqa: F401
            result = tracker.validate({'name': 'Alice'}, schema=schema)
            assert result.valid is True
        except ImportError:
            import pytest; pytest.skip('jsonschema not installed')

    def test_validate_with_jsonschema_failure(self):
        tracker = ValidationTracker('test')
        schema = {'type': 'object', 'properties': {'age': {'type': 'integer'}},
                  'required': ['age']}
        try:
            import jsonschema as _js  # noqa: F401
            result = tracker.validate({}, schema=schema)
            assert result.valid is False
        except ImportError:
            import pytest; pytest.skip('jsonschema not installed')

    def test_process_validator_output_dict_with_string_errors(self):
        tracker = ValidationTracker('test')
        def validator(data):
            return {'valid': False, 'errors': ['error message']}
        result = tracker.validate({}, validator=validator)
        assert result.valid is False
        assert result.errors[0].field == '_root'

    def test_process_validator_output_dict_with_dict_errors(self):
        tracker = ValidationTracker('test')
        def validator(data):
            return {'valid': False, 'errors': [
                {'field': 'name', 'error_type': 'required', 'message': 'Required'}
            ]}
        result = tracker.validate({}, validator=validator)
        assert result.valid is False
        assert result.errors[0].field == 'name'

    def test_process_validator_output_list_with_dict_errors(self):
        tracker = ValidationTracker('test')
        def validator(data):
            return [{'field': 'email', 'error_type': 'format', 'message': 'Bad format'}]
        result = tracker.validate({'x': 1}, validator=validator)
        assert result.valid is False
        assert result.errors[0].field == 'email'

    def test_validated_decorator_positional_args(self):
        tracker = ValidationTracker('test')
        def validator(data):
            return isinstance(data, dict)
        @tracker.validated(validator=validator, raise_on_error=False)
        def process(data):
            return 'ok'
        result = process({'key': 'value'})
        assert result == 'ok'

    def test_validated_decorator_async(self):
        import asyncio
        tracker = ValidationTracker('test')
        def validator(data):
            return True
        @tracker.validated(validator=validator, raise_on_error=False)
        async def async_process(data):
            return 'async_ok'
        result = asyncio.run(async_process({'key': 'value'}))
        assert result == 'async_ok'

    def test_validated_decorator_async_positional_arg_extraction(self):
        import asyncio
        tracker = ValidationTracker('test')
        def validator(data):
            return True
        @tracker.validated(validator=validator, data_arg='data', raise_on_error=False)
        async def async_process(data):
            return 'async_pos'
        # Call with positional arg to trigger the positional arg extraction branch
        result = asyncio.run(async_process({'key': 'value'}))
        assert result == 'async_pos'

    def test_validated_decorator_sync_positional_data_arg(self):
        tracker = ValidationTracker('test')
        def validator(d):
            return True
        @tracker.validated(validator=validator, data_arg='data', raise_on_error=False)
        def process(data):
            return 'ok'
        # Pass positional arg to trigger extraction branch
        result = process({'key': 'val'})
        assert result == 'ok'

    def test_validated_decorator_when_data_is_none_kwarg(self):
        tracker = ValidationTracker('test')
        called = []
        def validator(d):
            called.append(d); return True
        @tracker.validated(validator=validator, raise_on_error=False)
        def process(x=None):
            return 'done'
        # data kwarg is None so validation is skipped
        result = process()
        assert result == 'done'
        assert called == []

    def test_jsonschema_import_error_returns_valid(self):
        from unittest.mock import patch
        tracker = ValidationTracker('test')
        schema = {'type': 'object'}
        with patch.dict('sys.modules', {'jsonschema': None}):
            import builtins; real_import = builtins.__import__
            def _imp(name, *args, **kw):
                if name == 'jsonschema': raise ImportError('no jsonschema')
                return real_import(name, *args, **kw)
            with patch('builtins.__import__', side_effect=_imp):
                result = tracker._validate_jsonschema({'key': 'val'}, schema, ValidationResult(valid=True, schema_name='test'))
                assert result.valid is True


class TestValidationBranchCoverage:
    def test_jsonschema_general_exception(self):
        from unittest.mock import MagicMock, patch
        tracker = ValidationTracker('test')
        schema = {'type': 'object'}
        with patch('jsonschema.Draft7Validator') as mock_v:
            mock_v.side_effect = Exception('some unexpected error')
            result = tracker._validate_jsonschema({'key': 'val'}, schema, ValidationResult(valid=True, schema_name='test'))
            assert result.valid is False
            assert 'jsonschema_error' == result.errors[0].error_type

    def test_dict_validator_with_string_errors_loop(self):
        tracker = ValidationTracker('test')
        def validator(data):
            return {'valid': False, 'errors': ['error one', 'error two']}
        result = tracker.validate({}, validator=validator)
        assert len(result.errors) == 2

    def test_list_validator_with_dict_errors_loop(self):
        tracker = ValidationTracker('test')
        def validator(data):
            return [
                {'field': 'a', 'error_type': 'e', 'message': 'm'},
                {'field': 'b', 'error_type': 'e', 'message': 'm'},
            ]
        result = tracker.validate({'x': 1}, validator=validator)
        assert len(result.errors) == 2

    def test_list_validator_empty_list_is_valid(self):
        tracker = ValidationTracker('test')
        def validator(data):
            return []
        result = tracker.validate({'x': 1}, validator=validator)
        assert result.valid is True

    def test_validated_sync_no_data_kwarg_positional_not_in_params(self):
        tracker = ValidationTracker('test')
        validate_called = []
        def validator(d):
            validate_called.append(d); return True
        @tracker.validated(validator=validator, data_arg='data', raise_on_error=False)
        def process(x, y):
            return 'ok'
        result = process('a', 'b')
        assert result == 'ok'
        # data_arg='data' is not in params (x, y), so validation should be skipped
        assert validate_called == []

    def test_validated_async_no_data_kwarg_positional_not_in_params(self):
        import asyncio
        tracker = ValidationTracker('test')
        validate_called = []
        def validator(d):
            validate_called.append(d); return True
        @tracker.validated(validator=validator, data_arg='data', raise_on_error=False)
        async def async_process(x, y):
            return 'async_ok'
        result = asyncio.run(async_process('a', 'b'))
        assert result == 'async_ok'
        assert validate_called == []


class TestValidationBranchCoverage2:
    """Additional branch coverage tests for validation.py."""

    def test_dict_validator_error_is_neither_dict_nor_string(self):
        """Test dict validator output where error is neither dict nor str (line 208->205)."""
        tracker = ValidationTracker('test')
        def validator(data):
            return {'valid': False, 'errors': [42, None, 'valid_string_error']}
        result = tracker.validate({}, validator=validator)
        # Only the string error and dict errors are captured
        assert len(result.errors) == 1  # Only the string error
        assert result.errors[0].message == 'valid_string_error'

    def test_validator_output_not_bool_dict_or_list(self):
        """Test validator output that is not bool, dict, or list (line 213->224)."""
        tracker = ValidationTracker('test')
        def validator(data):
            return "unexpected_string"  # Not bool, dict, or list
        result = tracker.validate({}, validator=validator)
        # Should return a valid result since the output is unhandled
        assert result is not None

    def test_list_validator_error_is_neither_dict_nor_str(self):
        """Test list validator where error item is neither dict nor str (line 219->216)."""
        tracker = ValidationTracker('test')
        def validator(data):
            return [42, None, {'field': 'a', 'error_type': 'e', 'message': 'm'}]
        result = tracker.validate({}, validator=validator)
        # Only the dict error is captured
        assert len(result.errors) == 1

    def test_validated_sync_with_positional_data_arg(self):
        """Test sync wrapper extracts data from positional args (line 345->348)."""
        import asyncio
        tracker = ValidationTracker('test')
        validate_called = []
        def validator(d):
            validate_called.append(d); return True
        @tracker.validated(validator=validator, data_arg='data', raise_on_error=False)
        def process(data, other=None):
            return 'ok'
        # Pass data as positional arg
        result = process({'key': 'value'})
        assert result == 'ok'
        assert validate_called == [{'key': 'value'}]

    def test_validated_async_data_kwarg_present(self):
        """Test async wrapper when data is provided as kwarg (line 358->368)."""
        import asyncio
        tracker = ValidationTracker('test')
        validate_called = []
        def validator(d):
            validate_called.append(d); return True
        @tracker.validated(validator=validator, data_arg='data', raise_on_error=False)
        async def async_process(data=None):
            return 'ok'
        result = asyncio.run(async_process(data={'k': 'v'}))
        assert result == 'ok'
        assert validate_called == [{'k': 'v'}]

    def test_validated_async_with_positional_data_arg(self):
        """Test async wrapper extracts data from positional args (line 365->368)."""
        import asyncio
        tracker = ValidationTracker('test')
        validate_called = []
        def validator(d):
            validate_called.append(d); return True
        @tracker.validated(validator=validator, data_arg='data', raise_on_error=False)
        async def async_process(data, other=None):
            return 'ok'
        result = asyncio.run(async_process({'key': 'value'}))
        assert result == 'ok'
        assert validate_called == [{'key': 'value'}]

    def test_validate_range_field_present(self):
        """Test validate_range when field is present in data (line 447->446)."""
        from obskit.validation import validate_range
        data = {'price': 50.0, 'quantity': 5}
        errors = validate_range(data, {'price': (0.0, 100.0), 'quantity': (1, 10)})
        assert errors == []

    def test_validate_range_field_out_of_range(self):
        """Test validate_range when field is out of range."""
        from obskit.validation import validate_range
        data = {'price': 150.0}
        errors = validate_range(data, {'price': (0.0, 100.0)})
        assert len(errors) == 1
        assert errors[0].error_type == 'range_error'


class TestValidationBranchCoverage3:
    """Tests for remaining branch coverage in validation.py."""

    def test_validated_sync_data_arg_in_params_but_not_in_positional(self):
        """Test sync wrapper when idx >= len(args) (branch 345->348, else branch)."""
        tracker = ValidationTracker('test')
        validate_called = []
        def validator(d):
            validate_called.append(d); return True

        @tracker.validated(validator=validator, data_arg='data', raise_on_error=False)
        def process(x, data=None):  # 'data' is in params at idx=1
            return 'ok'

        # Call with only 1 positional arg - 'data' is at idx=1 but len(args)=1, so 1 < 1 is False
        result = process('some_value')  # Only x is passed as positional
        assert result == 'ok'
        # data was not extracted from positional args, and wasn't in kwargs, so no validation
        assert validate_called == []

    def test_validated_async_data_arg_in_params_but_not_in_positional(self):
        """Test async wrapper when idx >= len(args) (branch 365->368, else branch)."""
        import asyncio
        tracker = ValidationTracker('test')
        validate_called = []
        def validator(d):
            validate_called.append(d); return True

        @tracker.validated(validator=validator, data_arg='data', raise_on_error=False)
        async def async_process(x, data=None):  # 'data' is at idx=1
            return 'ok'

        result = asyncio.run(async_process('some_value'))  # Only x passed positionally
        assert result == 'ok'
        assert validate_called == []

    def test_validate_range_field_missing_from_data(self):
        """Test validate_range when field is NOT in data (branch 447->446)."""
        from obskit.validation import validate_range
        data = {'other_field': 5}  # 'price' not in data
        errors = validate_range(data, {'price': (0.0, 100.0)})
        # No errors since price is not in data
        assert errors == []
