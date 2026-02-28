"""
Schema Validation Metrics.

Track data validation errors in a structured way.
"""

import functools
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar

from prometheus_client import Counter, Histogram

from .logging import get_logger

logger = get_logger(__name__)

# Metrics
VALIDATION_TOTAL = Counter("validation_total", "Total validations performed", ["schema", "status"])

VALIDATION_ERRORS = Counter(
    "validation_errors_total", "Total validation errors", ["schema", "field", "error_type"]
)

VALIDATION_DURATION = Histogram(
    "validation_duration_seconds",
    "Validation duration",
    ["schema"],
    buckets=[0.0001, 0.0005, 0.001, 0.005, 0.01, 0.025, 0.05, 0.1],
)

F = TypeVar("F", bound=Callable[..., Any])


@dataclass
class ValidationError:
    """Represents a single validation error."""

    field: str
    error_type: str
    message: str
    value: Any = None
    expected: Any = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "error_type": self.error_type,
            "message": self.message,
            "value": repr(self.value) if self.value is not None else None,
            "expected": self.expected,
        }


@dataclass
class ValidationResult:
    """Result of a validation operation."""

    valid: bool
    schema_name: str
    errors: list[ValidationError] = field(default_factory=list)
    warnings: list[ValidationError] = field(default_factory=list)
    data: Any = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "schema_name": self.schema_name,
            "errors": [e.to_dict() for e in self.errors],
            "warnings": [w.to_dict() for w in self.warnings],
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
        }


class ValidationTracker:
    """
    Tracks data validation with metrics.

    Example:
        tracker = ValidationTracker("api_requests")

        # Validate data
        result = tracker.validate(data, validate_user_input)
        if not result.valid:
            logger.error("Validation failed", errors=result.errors)

        # Or use decorator
        @tracker.validated
        def process_data(data: dict):
            # data is pre-validated
            pass

        # Get validation stats
        stats = tracker.get_stats()
    """

    def __init__(self, schema_name: str):
        """
        Initialize validation tracker.

        Args:
            schema_name: Schema name for metrics
        """
        self.schema_name = schema_name
        self._total_validations = 0
        self._successful_validations = 0
        self._failed_validations = 0
        self._errors_by_field: dict[str, int] = defaultdict(int)
        self._errors_by_type: dict[str, int] = defaultdict(int)

    def validate(
        self,
        data: Any,
        validator: Callable[[Any], bool | dict | list] | None = None,
        schema: Any | None = None,
        raise_on_error: bool = False,
    ) -> ValidationResult:
        """
        Validate data and track results.

        Args:
            data: Data to validate
            validator: Validation function (returns bool, dict with errors, or list of errors)
            schema: Schema object (pydantic, jsonschema, etc.)
            raise_on_error: Raise exception on validation failure

        Returns:
            ValidationResult
        """
        import time

        start_time = time.time()

        result = ValidationResult(valid=True, schema_name=self.schema_name, data=data)

        try:
            if validator:
                validation_output = validator(data)
                result = self._process_validator_output(validation_output, result)
            elif schema:
                result = self._validate_with_schema(data, schema, result)
            else:
                # No validation - just pass through
                pass

        except Exception as e:
            result.valid = False
            result.errors.append(
                ValidationError(field="_schema", error_type="validation_exception", message=str(e))
            )

        # Record metrics
        duration = time.time() - start_time
        VALIDATION_DURATION.labels(schema=self.schema_name).observe(duration)

        self._total_validations += 1
        status = "success" if result.valid else "failure"
        VALIDATION_TOTAL.labels(schema=self.schema_name, status=status).inc()

        if result.valid:
            self._successful_validations += 1
        else:
            self._failed_validations += 1

            for error in result.errors:
                VALIDATION_ERRORS.labels(
                    schema=self.schema_name, field=error.field, error_type=error.error_type
                ).inc()

                self._errors_by_field[error.field] += 1
                self._errors_by_type[error.error_type] += 1

            logger.warning(
                "validation_failed",
                schema=self.schema_name,
                error_count=len(result.errors),
                errors=[e.to_dict() for e in result.errors[:5]],  # Limit to first 5
            )

        if raise_on_error and not result.valid:
            raise ValidationException(result)

        return result

    def _process_validator_output(
        self, output: bool | dict | list, result: ValidationResult
    ) -> ValidationResult:
        """Process output from custom validator."""
        if isinstance(output, bool):
            result.valid = output
            if not output:
                result.errors.append(
                    ValidationError(
                        field="_root",
                        error_type="validation_failed",
                        message="Validation returned False",
                    )
                )

        elif isinstance(output, dict):
            # Expect {"valid": bool, "errors": [...]}
            result.valid = output.get("valid", True)
            for error in output.get("errors", []):
                if isinstance(error, dict):
                    result.errors.append(ValidationError(**error))
                elif isinstance(error, str):
                    result.errors.append(
                        ValidationError(field="_root", error_type="error", message=error)
                    )

        elif isinstance(output, list):
            # List of error messages/dicts
            result.valid = len(output) == 0
            for error in output:
                if isinstance(error, dict):
                    result.errors.append(ValidationError(**error))
                elif isinstance(error, str):
                    result.errors.append(
                        ValidationError(field="_root", error_type="error", message=error)
                    )

        return result

    def _validate_with_schema(
        self, data: Any, schema: Any, result: ValidationResult
    ) -> ValidationResult:
        """Validate using schema object."""
        # Try pydantic
        if hasattr(schema, "model_validate") or hasattr(schema, "parse_obj"):
            return self._validate_pydantic(data, schema, result)

        # Try jsonschema
        if isinstance(schema, dict) and ("type" in schema or "properties" in schema):
            return self._validate_jsonschema(data, schema, result)

        # Unknown schema type
        logger.warning("unknown_schema_type", schema_type=type(schema).__name__)
        return result

    def _validate_pydantic(
        self, data: Any, schema: Any, result: ValidationResult
    ) -> ValidationResult:
        """Validate using Pydantic model."""
        try:
            # Pydantic v2
            if hasattr(schema, "model_validate"):
                schema.model_validate(data)
            # Pydantic v1
            else:
                schema.parse_obj(data)

            result.valid = True

        except Exception as e:
            result.valid = False

            # Extract errors from Pydantic validation error
            if hasattr(e, "errors"):
                for err in e.errors():
                    loc = ".".join(str(part) for part in err.get("loc", []))
                    result.errors.append(
                        ValidationError(
                            field=loc or "_root",
                            error_type=err.get("type", "validation_error"),
                            message=err.get("msg", str(e)),
                            value=err.get("input"),
                            expected=err.get("ctx", {}).get("expected"),
                        )
                    )
            else:
                result.errors.append(
                    ValidationError(field="_root", error_type="pydantic_error", message=str(e))
                )

        return result

    def _validate_jsonschema(
        self, data: Any, schema: dict, result: ValidationResult
    ) -> ValidationResult:
        """Validate using JSON Schema."""
        try:
            import jsonschema

            validator = jsonschema.Draft7Validator(schema)
            errors = list(validator.iter_errors(data))

            if errors:
                result.valid = False
                for error in errors:
                    path = ".".join(str(p) for p in error.absolute_path)
                    result.errors.append(
                        ValidationError(
                            field=path or "_root",
                            error_type=error.validator,
                            message=error.message,
                            value=error.instance,
                            expected=error.schema.get("type"),
                        )
                    )
            else:
                result.valid = True

        except ImportError:
            logger.warning("jsonschema not installed")
            result.valid = True
        except Exception as e:
            result.valid = False
            result.errors.append(
                ValidationError(field="_root", error_type="jsonschema_error", message=str(e))
            )

        return result

    def validated(
        self,
        validator: Callable | None = None,
        schema: Any | None = None,
        data_arg: str = "data",
        raise_on_error: bool = True,
    ) -> Callable[[F], F]:
        """
        Decorator to validate function input.

        Args:
            validator: Custom validator function
            schema: Schema to validate against
            data_arg: Name of the data argument
            raise_on_error: Raise exception on validation failure
        """

        def decorator(func: F) -> F:
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                # Extract data from arguments
                data = kwargs.get(data_arg)
                if data is None and args:
                    import inspect

                    sig = inspect.signature(func)
                    params = list(sig.parameters.keys())
                    if data_arg in params:
                        idx = params.index(data_arg)
                        if idx < len(args):
                            data = args[idx]

                if data is not None:
                    self.validate(
                        data, validator=validator, schema=schema, raise_on_error=raise_on_error
                    )

                return func(*args, **kwargs)

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                data = kwargs.get(data_arg)
                if data is None and args:
                    import inspect

                    sig = inspect.signature(func)
                    params = list(sig.parameters.keys())
                    if data_arg in params:
                        idx = params.index(data_arg)
                        if idx < len(args):
                            data = args[idx]

                if data is not None:
                    self.validate(
                        data, validator=validator, schema=schema, raise_on_error=raise_on_error
                    )

                return await func(*args, **kwargs)

            import asyncio

            if asyncio.iscoroutinefunction(func):
                return async_wrapper  # type: ignore
            return wrapper  # type: ignore

        return decorator

    def get_stats(self) -> dict[str, Any]:
        """Get validation statistics."""
        return {
            "schema_name": self.schema_name,
            "total_validations": self._total_validations,
            "successful_validations": self._successful_validations,
            "failed_validations": self._failed_validations,
            "success_rate": (
                self._successful_validations / self._total_validations
                if self._total_validations > 0
                else 1.0
            ),
            "errors_by_field": dict(self._errors_by_field),
            "errors_by_type": dict(self._errors_by_type),
        }


class ValidationException(Exception):
    """Exception raised on validation failure."""

    def __init__(self, result: ValidationResult):
        self.result = result
        super().__init__(f"Validation failed: {len(result.errors)} error(s)")

    def to_dict(self) -> dict[str, Any]:
        return self.result.to_dict()


# Convenience functions
def validate_required(data: dict, fields: list[str]) -> list[ValidationError]:
    """Validate that required fields are present."""
    errors = []
    for field_name in fields:
        if field_name not in data or data[field_name] is None:
            errors.append(
                ValidationError(
                    field=field_name, error_type="required", message=f"Field '{field_name}' is required"
                )
            )
    return errors


def validate_type(data: dict, field_types: dict[str, type]) -> list[ValidationError]:
    """Validate field types."""
    errors = []
    for field_name, expected_type in field_types.items():
        if field_name in data:
            if not isinstance(data[field_name], expected_type):
                errors.append(
                    ValidationError(
                        field=field_name,
                        error_type="type_error",
                        message=f"Expected {expected_type.__name__}, got {type(data[field_name]).__name__}",
                        value=data[field_name],
                        expected=expected_type.__name__,
                    )
                )
    return errors


def validate_range(data: dict, field_ranges: dict[str, tuple]) -> list[ValidationError]:
    """Validate numeric field ranges."""
    errors = []
    for field_name, (min_val, max_val) in field_ranges.items():
        if field_name in data:
            value = data[field_name]
            if isinstance(value, (int, float)):
                if min_val is not None and value < min_val:
                    errors.append(
                        ValidationError(
                            field=field_name,
                            error_type="range_error",
                            message=f"Value {value} is less than minimum {min_val}",
                            value=value,
                            expected=f">= {min_val}",
                        )
                    )
                if max_val is not None and value > max_val:
                    errors.append(
                        ValidationError(
                            field=field_name,
                            error_type="range_error",
                            message=f"Value {value} is greater than maximum {max_val}",
                            value=value,
                            expected=f"<= {max_val}",
                        )
                    )
    return errors


__all__ = [
    "ValidationTracker",
    "ValidationResult",
    "ValidationError",
    "ValidationException",
    "validate_required",
    "validate_type",
    "validate_range",
    "VALIDATION_TOTAL",
    "VALIDATION_ERRORS",
    "VALIDATION_DURATION",
]
