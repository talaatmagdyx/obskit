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

import re
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


class _Redactor:
    """Callable structlog processor that redacts sensitive log fields.

    Constructed by :func:`make_redaction_processor`; holds the compiled
    regex and placeholder so the nested closure depth is zero.
    """

    __name__ = "redact_sensitive_fields"
    __qualname__ = "redact_sensitive_fields"

    def __init__(self, sensitive_re: re.Pattern[str], placeholder: str) -> None:
        self._sensitive_re = sensitive_re
        self._placeholder = placeholder

    def redact_value(self, obj: Any, depth: int = 0, _seen: frozenset[int] | None = None) -> Any:
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
        result: dict[Any, Any] = {}
        for key, val in obj.items():
            # Guard against non-string keys (e.g. integer keys) that would
            # raise TypeError in _sensitive_re.search().  Non-string keys
            # are never sensitive field names, so we skip the regex check.
            if isinstance(key, str) and self._sensitive_re.search(key):
                result[key] = self._placeholder
            elif isinstance(val, dict):
                result[key] = self.redact_value(val, depth + 1, seen)
            elif isinstance(val, list):
                # Recurse into list items that are dicts so sensitive keys
                # inside e.g. {"users": [{"password": "s3cr3t"}]} are redacted.
                result[key] = [
                    self.redact_value(item, depth + 1, seen) if isinstance(item, dict) else item
                    for item in val
                ]
            else:
                result[key] = val
        return result

    def __call__(
        self,
        logger: WrappedLogger,
        method_name: str,
        event_dict: EventDict,
    ) -> EventDict:
        try:
            return self.redact_value(event_dict)  # type: ignore[no-any-return]
        except Exception:  # pragma: no cover
            # Never let a redaction failure suppress a log event.
            # Return the event_dict unmodified — PII *may* be logged, but
            # that is preferable to silently dropping the log record.
            return event_dict


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
    fields_norm: frozenset[str] = (
        frozenset(f.lower() for f in fields) if fields is not None else DEFAULT_SENSITIVE_FIELDS
    )
    # Pre-compile a single case-insensitive regex from all sensitive keywords.
    # One C-level re.search() replaces O(keywords) Python generator steps per field.
    # Sort longest first so longer patterns (e.g. "private_key") match before their
    # substrings (e.g. "key") — though with IGNORECASE substring matching this only
    # matters if keywords overlap, which they don't in DEFAULT_SENSITIVE_FIELDS.
    sensitive_re = re.compile(
        "|".join(re.escape(f) for f in sorted(fields_norm, key=len, reverse=True)),
        re.IGNORECASE,
    )
    return _Redactor(sensitive_re, placeholder)


# Convenience singleton with default settings — import directly for zero-config use.
redact_sensitive_fields = make_redaction_processor()
