"""
Request Context Middleware
==========================

Middleware for automatic context propagation in web frameworks.

Supports:
- ASGI (FastAPI, Starlette, etc.)
- WSGI (Flask, Django, etc.)

Example
-------
>>> # FastAPI
>>> from fastapi import FastAPI
>>> from obskit.middleware import ASGIMiddleware
>>>
>>> app = FastAPI()
>>> app.add_middleware(ASGIMiddleware, service_name="my-service")
>>>
>>> # Flask
>>> from flask import Flask
>>> from obskit.middleware import WSGIMiddleware
>>>
>>> app = Flask(__name__)
>>> app.wsgi_app = WSGIMiddleware(app.wsgi_app, service_name="my-service")
>>>
>>> # Extract/inject context manually
>>> from obskit.middleware import extract_context_from_headers, inject_context_to_headers
>>>
>>> context = extract_context_from_headers(request.headers)
>>> outgoing_headers = inject_context_to_headers()
"""

from obskit.middleware.base import (
    CORRELATION_ID_HEADERS,
    TENANT_ID_HEADERS,
    ASGIMiddleware,
    BaseMiddleware,
    WSGIMiddleware,
    extract_context_from_headers,
    inject_context_to_headers,
)

# Alias for convenience
ObskitMiddleware = ASGIMiddleware

__all__ = [
    # Functions
    "extract_context_from_headers",
    "inject_context_to_headers",
    # Middleware classes
    "BaseMiddleware",
    "ASGIMiddleware",
    "WSGIMiddleware",
    "ObskitMiddleware",
    # Constants
    "CORRELATION_ID_HEADERS",
    "TENANT_ID_HEADERS",
]
