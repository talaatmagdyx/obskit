"""
High-level ``instrument_*()`` functions for framework integration.

These are the recommended way to add obskit middleware to your application:

.. code-block:: python

    from obskit import configure_observability, instrument_fastapi

    obs = configure_observability(service_name="billing-api")
    instrument_fastapi(app, obs=obs)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from obskit.core.observability import Observability


def instrument_fastapi(
    app: Any,
    *,
    obs: Observability | None = None,
    exclude_paths: list[str] | None = None,
    track_metrics: bool = True,
    track_logging: bool = True,
    track_tracing: bool = True,
) -> None:
    """Attach obskit ASGI middleware to a FastAPI / Starlette application.

    Parameters
    ----------
    app : FastAPI | Starlette
        The ASGI application.
    obs : Observability | None
        Explicit observability handle.  Falls back to the global if *None*.
    exclude_paths, track_metrics, track_logging, track_tracing
        Forwarded to :class:`~obskit.middleware.fastapi.ObskitMiddleware`.
    """
    from obskit.middleware.fastapi import ObskitMiddleware

    kwargs: dict[str, Any] = {
        "track_metrics": track_metrics,
        "track_logging": track_logging,
        "track_tracing": track_tracing,
    }
    if exclude_paths is not None:
        kwargs["exclude_paths"] = exclude_paths

    app.add_middleware(ObskitMiddleware, **kwargs)


def instrument_flask(
    app: Any,
    *,
    obs: Observability | None = None,
    exclude_paths: list[str] | None = None,
    track_metrics: bool = True,
    track_logging: bool = True,
    track_tracing: bool = True,
) -> None:
    """Attach obskit hooks to a Flask application.

    Parameters
    ----------
    app : Flask
        The Flask application.
    obs : Observability | None
        Explicit observability handle.  Falls back to the global if *None*.
    exclude_paths, track_metrics, track_logging, track_tracing
        Forwarded to :class:`~obskit.middleware.flask.ObskitFlaskMiddleware`.
    """
    from obskit.middleware.flask import ObskitFlaskMiddleware

    middleware = ObskitFlaskMiddleware(
        app=None,
        exclude_paths=exclude_paths,
        track_metrics=track_metrics,
        track_logging=track_logging,
        track_tracing=track_tracing,
    )
    middleware.init_app(app)


def instrument_django(
    *,
    obs: Observability | None = None,
    exclude_paths: list[str] | None = None,
    track_metrics: bool = True,
    track_logging: bool = True,
    track_tracing: bool = True,
) -> type:
    """Return a configured Django middleware class.

    Add the returned class to your ``MIDDLEWARE`` list in Django settings.

    Parameters
    ----------
    obs : Observability | None
        Explicit observability handle.  Falls back to the global if *None*.
    exclude_paths, track_metrics, track_logging, track_tracing
        Override the defaults read from ``settings.OBSKIT``.

    Returns
    -------
    type
        A configured :class:`~obskit.middleware.django.ObskitDjangoMiddleware`
        subclass.
    """
    from obskit.middleware.django import get_obskit_middleware

    return get_obskit_middleware(
        exclude_paths=exclude_paths,
        track_metrics=track_metrics,
        track_logging=track_logging,
        track_tracing=track_tracing,
    )
