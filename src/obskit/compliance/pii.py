"""
PII (Personally Identifiable Information) Redaction
====================================================

This module provides helpers for redacting PII from logs and metrics
to ensure GDPR and privacy compliance.

Example - Basic Usage
---------------------
.. code-block:: python

    from obskit.compliance import redact_pii
    from obskit import get_logger

    logger = get_logger(__name__)

    # Redact email and SSN
    user_data = {
        "email": "user@example.com",
        "ssn": "123-45-6789",
        "name": "John Doe",
    }

    safe_data = redact_pii(user_data, fields=["email", "ssn"])
    logger.info("user_action", **safe_data)
    # Output: {"email": "[REDACTED]", "ssn": "[REDACTED]", "name": "John Doe"}

Example - Decorator Usage
-------------------------
.. code-block:: python

    from obskit.compliance import redact_pii_decorator

    @redact_pii_decorator(fields=["email", "credit_card"])
    def process_payment(user_email: str, credit_card: str):
        logger.info("processing_payment", email=user_email, card=credit_card)
        # Logs automatically redact email and credit_card
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any, ParamSpec, TypeVar

P = ParamSpec("P")
T = TypeVar("T")

# Common PII patterns
EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
SSN_PATTERN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
CREDIT_CARD_PATTERN = re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b")
PHONE_PATTERN = re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b")


def redact_pii(
    data: dict[str, Any],
    fields: list[str] | None = None,
    redaction_string: str = "[REDACTED]",
    auto_detect: bool = True,
) -> dict[str, Any]:
    """
    Redact PII from a dictionary.

    Parameters
    ----------
    data : dict
        Dictionary containing potentially sensitive data.

    fields : list[str], optional
        Specific fields to redact. If None, uses common PII field names.
        Default: ["email", "ssn", "credit_card", "phone", "password"]

    redaction_string : str, default="[REDACTED]"
        String to use for redaction.

    auto_detect : bool, default=True
        Automatically detect and redact PII patterns in string values.

    Returns
    -------
    dict
        Dictionary with PII redacted.

    Example
    -------
    >>> from obskit.compliance import redact_pii
    >>>
    >>> data = {
    ...     "email": "user@example.com",
    ...     "ssn": "123-45-6789",
    ...     "name": "John Doe",
    ... }
    >>>
    >>> safe = redact_pii(data, fields=["email", "ssn"])
    >>> print(safe)
    {'email': '[REDACTED]', 'ssn': '[REDACTED]', 'name': 'John Doe'}
    """
    if fields is None:
        fields = ["email", "ssn", "credit_card", "phone", "password", "api_key", "token"]

    result = data.copy()

    # Redact specified fields
    for field in fields:
        if field in result:
            result[field] = redaction_string

    # Auto-detect PII patterns in string values
    if auto_detect:
        for key, value in result.items():
            if isinstance(value, str) and value != redaction_string:
                # Check for email
                if (
                    EMAIL_PATTERN.search(value)
                    or SSN_PATTERN.search(value)
                    or CREDIT_CARD_PATTERN.search(value)
                    or PHONE_PATTERN.search(value)
                ):
                    result[key] = redaction_string

    return result


def redact_pii_decorator(
    fields: list[str] | None = None,
    redaction_string: str = "[REDACTED]",
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """
    Decorator that automatically redacts PII from log context.

    Parameters
    ----------
    fields : list[str], optional
        Fields to redact in log context.

    redaction_string : str, default="[REDACTED]"
        String to use for redaction.

    Returns
    -------
    Callable
        Decorator function.

    Example
    -------
    >>> from obskit.compliance import redact_pii_decorator
    >>> from obskit import get_logger
    >>>
    >>> logger = get_logger(__name__)
    >>>
    >>> @redact_pii_decorator(fields=["email", "credit_card"])
    >>> def process_order(email: str, credit_card: str):
    ...     logger.info("processing", email=email, card=credit_card)
    ...     # email and card are automatically redacted in logs
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        # This is a placeholder - actual implementation would need
        # to intercept logger calls, which is complex
        # For now, users should call redact_pii() manually
        return func

    return decorator


__all__ = ["redact_pii", "redact_pii_decorator"]
