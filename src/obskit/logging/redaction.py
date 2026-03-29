"""Sensitive field redaction for structured log events.

Provides a structlog processor that replaces the values of configurable
sensitive fields (e.g. passwords, tokens, secrets) with a redaction
placeholder before they are rendered or shipped to a log aggregator.

Usage
-----
Add :func:`make_redaction_processor` to your structlog processor chain::

    from obskit.logging.redaction import make_redaction_processor

    processors = [
        make_redaction_processor(),          # default sensitive fields
        structlog.processors.JSONRenderer(),
    ]

Custom fields::

    processor = make_redaction_processor(
        fields={"password", "token", "ssn", "credit_card"},
        placeholder="[REDACTED]",
    )

The processor performs **case-insensitive substring matching**: a log field
named ``access_token`` will be redacted even if only ``token`` is listed.

Default sensitive field patterns
---------------------------------
``password``, ``passwd``, ``secret``, ``token``, ``api_key``, ``apikey``,
``auth``, ``credential``, ``private_key``, ``access_key``, ``bearer``
"""

from __future__ import annotations

from typing import Any

from structlog.types import EventDict, WrappedLogger

# Fields whose *names* match any of these substrings (case-insensitive) will
# have their values replaced with the redaction placeholder.
DEFAULT_SENSITIVE_FIELDS: frozenset[str] = frozenset(
    {
        "password",
        "passwd",
        "secret",
        "token",
        "api_key",
        "apikey",
        "auth",
        "credential",
        "private_key",
        "access_key",
        "bearer",
    }
)

_DEFAULT_PLACEHOLDER = "[REDACTED]"


def make_redaction_processor(
    fields: set[str] | frozenset[str] | None = None,
    placeholder: str = _DEFAULT_PLACEHOLDER,
) -> Any:
    """Return a structlog processor that redacts sensitive log fields.

    Parameters
    ----------
    fields:
        Set of field-name substrings (case-insensitive) to redact.
        Defaults to :data:`DEFAULT_SENSITIVE_FIELDS`.
    placeholder:
        Replacement value written in place of the real secret.
        Defaults to ``"[REDACTED]"``.

    Returns
    -------
    Callable
        A structlog-compatible processor function.

    Example
    -------
    >>> processor = make_redaction_processor({"password", "token"})
    >>> result = processor(None, "info", {"event": "login", "password": "s3cr3t"})
    >>> result["password"]
    '[REDACTED]'
    """
    _fields: frozenset[str] = (
        frozenset(f.lower() for f in fields) if fields is not None else DEFAULT_SENSITIVE_FIELDS
    )
    _placeholder = placeholder

    def _redact_value(obj: Any, depth: int = 0, _seen: frozenset[int] | None = None) -> Any:
        """Recursively redact sensitive keys inside dicts (max 10 levels deep).

        Returns a new dict at each level instead of mutating in-place,
        so the original event_dict is never modified.  Tracks object ids
        to detect circular references and stop recursion early.
        """
        if depth > 10 or not isinstance(obj, dict):
            return obj
        seen = _seen if _seen is not None else frozenset()
        obj_id = id(obj)
        if obj_id in seen:
            return "<circular>"
        seen = seen | {obj_id}
        result = {}
        for key, val in obj.items():
            key_lower = key.lower()
            if any(sensitive in key_lower for sensitive in _fields):
                result[key] = _placeholder
            elif isinstance(val, dict):
                result[key] = _redact_value(val, depth + 1, seen)
            else:
                result[key] = val
        return result

    def _redact_processor(
        logger: WrappedLogger,
        method_name: str,
        event_dict: EventDict,
    ) -> EventDict:
        return _redact_value(event_dict)  # type: ignore[no-any-return]

    _redact_processor.__name__ = "redact_sensitive_fields"
    _redact_processor.__qualname__ = "redact_sensitive_fields"
    return _redact_processor


# Convenience singleton with default settings — import directly for zero-config use.
redact_sensitive_fields = make_redaction_processor()
