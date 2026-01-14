"""
HTTP Middleware Module - Framework-Specific Observability Middleware
=====================================================================

This module provides middleware for popular Python web frameworks,
automatically adding observability (metrics, logging, tracing, correlation IDs)
to all HTTP requests.

Supported Frameworks
--------------------
- **FastAPI**: Full async support with ASGI middleware
- **Flask**: WSGI middleware with extension pattern support
- **Django**: Standard Django middleware

Installation
------------
Each framework requires its specific optional dependency:

.. code-block:: bash

    # FastAPI
    pip install obskit[fastapi]

    # Flask
    pip install obskit[flask]

    # Django
    pip install obskit[django]

    # All frameworks
    pip install obskit[all]

Quick Start - FastAPI
---------------------
.. code-block:: python

    from fastapi import FastAPI
    from obskit.middleware import ObskitMiddleware

    app = FastAPI()
    app.add_middleware(ObskitMiddleware)

Quick Start - Flask
-------------------
.. code-block:: python

    from flask import Flask
    from obskit.middleware import ObskitFlaskMiddleware

    app = Flask(__name__)
    ObskitFlaskMiddleware(app)

Quick Start - Django
--------------------
.. code-block:: python

    # settings.py
    MIDDLEWARE = [
        'obskit.middleware.django.ObskitDjangoMiddleware',
        # ... other middleware
    ]
"""

__all__: list[str] = []

# FastAPI Middleware
try:
    from obskit.middleware.fastapi import ObskitMiddleware

    __all__.append("ObskitMiddleware")
except ImportError:  # pragma: no cover
    pass

# Flask Middleware
try:
    from obskit.middleware.flask import ObskitFlaskMiddleware, obskit_flask

    __all__.extend(["ObskitFlaskMiddleware", "obskit_flask"])
except ImportError:  # pragma: no cover
    pass

# Django Middleware
try:
    from obskit.middleware.django import ObskitDjangoMiddleware, get_obskit_middleware

    __all__.extend(["ObskitDjangoMiddleware", "get_obskit_middleware"])
except ImportError:  # pragma: no cover
    pass
