# Merge namespace contributions from sub-packages.
from pkgutil import extend_path

__path__ = extend_path(__path__, __name__)

"""
Request Context Middleware
==========================

Middleware for automatic context propagation in web frameworks.

Recommended usage (v1.0.0+)::

    from obskit import instrument_fastapi, instrument_flask, instrument_django

    instrument_fastapi(app)   # FastAPI / Starlette
    instrument_flask(app)     # Flask
    instrument_django()       # Django

Direct usage::

    from obskit.middleware.fastapi import ObskitMiddleware
    from obskit.middleware.flask import ObskitFlaskMiddleware
    from obskit.middleware.django import ObskitDjangoMiddleware

Low-level utilities::

    from obskit.middleware.base import extract_context_from_headers, inject_context_to_headers
"""

from obskit.middleware.base import (
    CORRELATION_ID_HEADERS,
    TENANT_ID_HEADERS,
    BaseMiddleware,
    extract_context_from_headers,
    inject_context_to_headers,
)
from obskit.middleware.core import MiddlewareCore, RequestContext

__all__ = [
    # Shared core
    "MiddlewareCore",
    "RequestContext",
    # Legacy base utilities
    "extract_context_from_headers",
    "inject_context_to_headers",
    "BaseMiddleware",
    # Constants
    "CORRELATION_ID_HEADERS",
    "TENANT_ID_HEADERS",
]
