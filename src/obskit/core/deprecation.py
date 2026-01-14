"""
Deprecation Warnings Utility
============================

This module provides utilities for deprecating API elements with clear
warnings and migration paths.

Example
-------
>>> from obskit.core.deprecation import deprecated, deprecated_parameter
>>>
>>> @deprecated("1.2.0", "2.0.0", alternative="new_function")
... def old_function():
...     pass
>>>
>>> @deprecated_parameter("old_param", "1.2.0", alternative="new_param")
... def function_with_old_param(new_param=None, old_param=None):
...     pass
"""

from __future__ import annotations

import functools
import warnings
from collections.abc import Callable
from typing import Any, ParamSpec, TypeVar

P = ParamSpec("P")
T = TypeVar("T")


class ObskitDeprecationWarning(DeprecationWarning):
    """
    Custom deprecation warning for obskit.

    This warning is always shown by default (not filtered like standard
    DeprecationWarning) to ensure users are aware of upcoming changes.
    """

    pass


# Ensure our deprecation warnings are always shown
warnings.filterwarnings("default", category=ObskitDeprecationWarning)


def deprecated(
    deprecated_in: str,
    removed_in: str,
    alternative: str | None = None,
    reason: str | None = None,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """
    Decorator to mark a function or class as deprecated.

    Parameters
    ----------
    deprecated_in : str
        Version in which the feature was deprecated.
    removed_in : str
        Version in which the feature will be removed.
    alternative : str, optional
        Name of the alternative function/class to use.
    reason : str, optional
        Additional explanation for the deprecation.

    Returns
    -------
    Callable
        Decorator function.

    Example
    -------
    >>> @deprecated("1.2.0", "2.0.0", alternative="new_function")
    ... def old_function():
    ...     '''Old function that does something.'''
    ...     return "old"
    >>>
    >>> old_function()  # Raises ObskitDeprecationWarning
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        message_parts = [
            f"{func.__qualname__} is deprecated since version {deprecated_in}",
            f"and will be removed in version {removed_in}.",
        ]

        if alternative:
            message_parts.append(f"Use {alternative} instead.")

        if reason:
            message_parts.append(f"Reason: {reason}")

        message = " ".join(message_parts)

        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            warnings.warn(message, ObskitDeprecationWarning, stacklevel=2)
            return func(*args, **kwargs)

        # Update docstring
        doc = func.__doc__ or ""
        deprecation_note = f"""
.. deprecated:: {deprecated_in}
   Will be removed in {removed_in}.{f" Use {alternative} instead." if alternative else ""}
"""
        wrapper.__doc__ = deprecation_note + doc

        return wrapper

    return decorator


def deprecated_parameter(
    param_name: str,
    deprecated_in: str,
    removed_in: str | None = None,
    alternative: str | None = None,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """
    Decorator to mark a function parameter as deprecated.

    Parameters
    ----------
    param_name : str
        Name of the deprecated parameter.
    deprecated_in : str
        Version in which the parameter was deprecated.
    removed_in : str, optional
        Version in which the parameter will be removed.
    alternative : str, optional
        Name of the alternative parameter to use.

    Returns
    -------
    Callable
        Decorator function.

    Example
    -------
    >>> @deprecated_parameter("old_name", "1.2.0", alternative="new_name")
    ... def my_function(new_name=None, old_name=None):
    ...     value = new_name or old_name
    ...     return value
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            if param_name in kwargs and kwargs[param_name] is not None:
                message_parts = [
                    f"Parameter '{param_name}' is deprecated since version {deprecated_in}",
                ]

                if removed_in:
                    message_parts.append(f"and will be removed in version {removed_in}")

                if alternative:
                    message_parts.append(f". Use '{alternative}' instead.")
                else:
                    message_parts.append(".")

                message = " ".join(message_parts)
                warnings.warn(message, ObskitDeprecationWarning, stacklevel=2)

            return func(*args, **kwargs)

        return wrapper

    return decorator


def deprecated_class(
    deprecated_in: str,
    removed_in: str,
    alternative: str | None = None,
    reason: str | None = None,
) -> Callable[[type[T]], type[T]]:
    """
    Decorator to mark a class as deprecated.

    Parameters
    ----------
    deprecated_in : str
        Version in which the class was deprecated.
    removed_in : str
        Version in which the class will be removed.
    alternative : str, optional
        Name of the alternative class to use.
    reason : str, optional
        Additional explanation for the deprecation.

    Returns
    -------
    Callable
        Decorator function.
    """

    def decorator(cls: type[T]) -> type[T]:
        original_init = cls.__init__

        message_parts = [
            f"{cls.__qualname__} is deprecated since version {deprecated_in}",
            f"and will be removed in version {removed_in}.",
        ]

        if alternative:
            message_parts.append(f"Use {alternative} instead.")

        if reason:
            message_parts.append(f"Reason: {reason}")

        message = " ".join(message_parts)

        @functools.wraps(original_init)
        def new_init(self: Any, *args: Any, **kwargs: Any) -> None:
            warnings.warn(message, ObskitDeprecationWarning, stacklevel=2)
            original_init(self, *args, **kwargs)

        cls.__init__ = new_init  # type: ignore[method-assign]

        # Update docstring
        doc = cls.__doc__ or ""
        deprecation_note = f"""
.. deprecated:: {deprecated_in}
   Will be removed in {removed_in}.{f" Use {alternative} instead." if alternative else ""}
"""
        cls.__doc__ = deprecation_note + doc

        return cls

    return decorator


def warn_deprecated(
    feature: str,
    deprecated_in: str,
    removed_in: str,
    alternative: str | None = None,
    stacklevel: int = 2,
) -> None:
    """
    Issue a deprecation warning manually.

    Use this for deprecating behavior that can't be decorated.

    Parameters
    ----------
    feature : str
        Description of the deprecated feature.
    deprecated_in : str
        Version in which the feature was deprecated.
    removed_in : str
        Version in which the feature will be removed.
    alternative : str, optional
        Description of the alternative approach.
    stacklevel : int, default=2
        Stack level for the warning.

    Example
    -------
    >>> if use_old_behavior:
    ...     warn_deprecated(
    ...         "Using X without Y",
    ...         deprecated_in="1.2.0",
    ...         removed_in="2.0.0",
    ...         alternative="Always specify Y parameter",
    ...     )
    """
    message_parts = [
        f"{feature} is deprecated since version {deprecated_in}",
        f"and will be removed in version {removed_in}.",
    ]

    if alternative:
        message_parts.append(alternative)

    message = " ".join(message_parts)
    warnings.warn(message, ObskitDeprecationWarning, stacklevel=stacklevel + 1)
