"""Unit tests for obskit.core.deprecation — deprecation warning utilities."""

from __future__ import annotations

import warnings

import pytest

from obskit.core.deprecation import (
    ObskitDeprecationWarning,
    deprecated,
    deprecated_class,
    deprecated_parameter,
    warn_deprecated,
)


# =============================================================================
# ObskitDeprecationWarning
# =============================================================================


class TestObskitDeprecationWarning:
    def test_is_deprecation_warning(self):
        assert issubclass(ObskitDeprecationWarning, DeprecationWarning)

    def test_can_be_raised(self):
        with pytest.warns(ObskitDeprecationWarning):
            warnings.warn("test warning", ObskitDeprecationWarning)


# =============================================================================
# @deprecated decorator
# =============================================================================


class TestDeprecatedDecorator:
    def test_emits_warning_on_call(self):
        @deprecated("1.0.0", "2.0.0")
        def old_func():
            return "result"

        with pytest.warns(ObskitDeprecationWarning):
            result = old_func()

        assert result == "result"

    def test_warning_message_contains_version_info(self):
        @deprecated("1.2.0", "3.0.0")
        def old_func():
            pass

        with pytest.warns(ObskitDeprecationWarning, match="1.2.0"):
            old_func()

    def test_warning_message_contains_removed_in(self):
        @deprecated("1.2.0", "3.0.0")
        def old_func():
            pass

        with pytest.warns(ObskitDeprecationWarning, match="3.0.0"):
            old_func()

    def test_warning_includes_alternative_when_provided(self):
        @deprecated("1.0.0", "2.0.0", alternative="new_func")
        def old_func():
            pass

        with pytest.warns(ObskitDeprecationWarning, match="new_func"):
            old_func()

    def test_warning_includes_reason_when_provided(self):
        @deprecated("1.0.0", "2.0.0", reason="Use the better API")
        def old_func():
            pass

        with pytest.warns(ObskitDeprecationWarning, match="Use the better API"):
            old_func()

    def test_no_alternative_in_warning_when_not_provided(self):
        @deprecated("1.0.0", "2.0.0")
        def old_func():
            pass

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            old_func()
            assert len(w) == 1
            assert "instead" not in str(w[0].message)

    def test_preserves_function_name(self):
        @deprecated("1.0.0", "2.0.0")
        def my_special_function():
            pass

        assert my_special_function.__name__ == "my_special_function"

    def test_preserves_function_return_value(self):
        @deprecated("1.0.0", "2.0.0")
        def compute():
            return 42

        with pytest.warns(ObskitDeprecationWarning):
            result = compute()

        assert result == 42

    def test_passes_arguments_through(self):
        @deprecated("1.0.0", "2.0.0")
        def add(a, b):
            return a + b

        with pytest.warns(ObskitDeprecationWarning):
            result = add(3, 4)

        assert result == 7

    def test_docstring_updated_with_deprecated_marker(self):
        @deprecated("1.0.0", "2.0.0", alternative="better_func")
        def old_func():
            """Original docstring."""
            pass

        assert "deprecated" in old_func.__doc__.lower()
        assert "1.0.0" in old_func.__doc__

    def test_docstring_original_preserved(self):
        @deprecated("1.0.0", "2.0.0")
        def old_func():
            """Original docstring."""
            pass

        assert "Original docstring" in old_func.__doc__


# =============================================================================
# @deprecated_parameter decorator
# =============================================================================


class TestDeprecatedParameterDecorator:
    def test_emits_warning_when_deprecated_param_used(self):
        @deprecated_parameter("old_name", "1.2.0", alternative="new_name")
        def func(new_name=None, old_name=None):
            return new_name or old_name

        with pytest.warns(ObskitDeprecationWarning):
            result = func(old_name="value")

        assert result == "value"

    def test_no_warning_when_deprecated_param_not_used(self):
        @deprecated_parameter("old_name", "1.2.0")
        def func(new_name=None, old_name=None):
            return new_name

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            func(new_name="value")
            obskit_warnings = [x for x in w if issubclass(x.category, ObskitDeprecationWarning)]
            assert len(obskit_warnings) == 0

    def test_no_warning_when_deprecated_param_is_none(self):
        @deprecated_parameter("old_name", "1.2.0")
        def func(new_name=None, old_name=None):
            return new_name

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            func(old_name=None)
            obskit_warnings = [x for x in w if issubclass(x.category, ObskitDeprecationWarning)]
            assert len(obskit_warnings) == 0

    def test_warning_includes_param_name(self):
        @deprecated_parameter("old_param", "1.0.0")
        def func(new_param=None, old_param=None):
            pass

        with pytest.warns(ObskitDeprecationWarning, match="old_param"):
            func(old_param="value")

    def test_warning_includes_removed_in_version(self):
        @deprecated_parameter("old_param", "1.0.0", removed_in="3.0.0")
        def func(new_param=None, old_param=None):
            pass

        with pytest.warns(ObskitDeprecationWarning, match="3.0.0"):
            func(old_param="value")

    def test_warning_includes_alternative_when_provided(self):
        @deprecated_parameter("old_param", "1.0.0", alternative="new_param")
        def func(new_param=None, old_param=None):
            pass

        with pytest.warns(ObskitDeprecationWarning, match="new_param"):
            func(old_param="value")

    def test_preserves_function_behavior(self):
        @deprecated_parameter("old_x", "1.0.0")
        def multiply(a, b, old_x=None):
            return a * b

        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            assert multiply(3, 4) == 12

    def test_no_removed_in_does_not_crash(self):
        @deprecated_parameter("old_name", "1.0.0")
        def func(new_name=None, old_name=None):
            pass

        # Should not raise when removed_in is not provided
        with pytest.warns(ObskitDeprecationWarning):
            func(old_name="value")


# =============================================================================
# @deprecated_class decorator
# =============================================================================


class TestDeprecatedClassDecorator:
    def test_emits_warning_on_instantiation(self):
        @deprecated_class("1.0.0", "2.0.0")
        class OldClass:
            pass

        with pytest.warns(ObskitDeprecationWarning):
            obj = OldClass()

        assert isinstance(obj, OldClass)

    def test_warning_contains_version_info(self):
        @deprecated_class("1.5.0", "2.5.0")
        class OldClass:
            pass

        with pytest.warns(ObskitDeprecationWarning, match="1.5.0"):
            OldClass()

    def test_warning_includes_alternative(self):
        @deprecated_class("1.0.0", "2.0.0", alternative="NewClass")
        class OldClass:
            pass

        with pytest.warns(ObskitDeprecationWarning, match="NewClass"):
            OldClass()

    def test_warning_includes_reason(self):
        @deprecated_class("1.0.0", "2.0.0", reason="Redesigned API")
        class OldClass:
            pass

        with pytest.warns(ObskitDeprecationWarning, match="Redesigned API"):
            OldClass()

    def test_class_still_works_after_deprecation(self):
        @deprecated_class("1.0.0", "2.0.0")
        class OldClass:
            def __init__(self):
                self.value = 42

        with pytest.warns(ObskitDeprecationWarning):
            obj = OldClass()

        assert obj.value == 42

    def test_original_init_called(self):
        calls = []

        @deprecated_class("1.0.0", "2.0.0")
        class OldClass:
            def __init__(self, x):
                calls.append(x)

        with pytest.warns(ObskitDeprecationWarning):
            OldClass(99)

        assert calls == [99]

    def test_docstring_updated(self):
        @deprecated_class("1.0.0", "2.0.0")
        class OldClass:
            """Original docstring."""
            pass

        assert "deprecated" in OldClass.__doc__.lower()

    def test_no_alternative_in_message_when_not_provided(self):
        @deprecated_class("1.0.0", "2.0.0")
        class OldClass:
            pass

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            OldClass()
            obskit_warnings = [x for x in w if issubclass(x.category, ObskitDeprecationWarning)]
            assert len(obskit_warnings) == 1
            assert "instead" not in str(obskit_warnings[0].message)


# =============================================================================
# warn_deprecated utility function
# =============================================================================


class TestWarnDeprecated:
    def test_emits_warning(self):
        with pytest.warns(ObskitDeprecationWarning):
            warn_deprecated("old_feature", "1.0.0", "2.0.0")

    def test_warning_contains_feature_name(self):
        with pytest.warns(ObskitDeprecationWarning, match="old_feature"):
            warn_deprecated("old_feature", "1.0.0", "2.0.0")

    def test_warning_contains_deprecated_in_version(self):
        with pytest.warns(ObskitDeprecationWarning, match="1.5.0"):
            warn_deprecated("feature", "1.5.0", "3.0.0")

    def test_warning_contains_removed_in_version(self):
        with pytest.warns(ObskitDeprecationWarning, match="3.0.0"):
            warn_deprecated("feature", "1.5.0", "3.0.0")

    def test_warning_includes_alternative_when_provided(self):
        with pytest.warns(ObskitDeprecationWarning, match="use new_feature"):
            warn_deprecated("old_feature", "1.0.0", "2.0.0", alternative="use new_feature")

    def test_no_alternative_in_message_when_not_provided(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            warn_deprecated("feature", "1.0.0", "2.0.0")
            obskit_warnings = [x for x in w if issubclass(x.category, ObskitDeprecationWarning)]
            assert len(obskit_warnings) == 1

    def test_custom_stacklevel_does_not_crash(self):
        # Should not raise regardless of stacklevel
        with pytest.warns(ObskitDeprecationWarning):
            warn_deprecated("feature", "1.0.0", "2.0.0", stacklevel=3)
