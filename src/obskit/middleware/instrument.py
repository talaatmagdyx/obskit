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
    context_extractor: Any | None = None,
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
    context_extractor : callable, optional
        Forwarded to :class:`~obskit.middleware.fastapi.ObskitMiddleware`.
        Receives decoded request headers; returns extra log-context key/value pairs.
    """
    from obskit.middleware.fastapi import ObskitMiddleware

    kwargs: dict[str, Any] = {
        "track_metrics": track_metrics,
        "track_logging": track_logging,
        "track_tracing": track_tracing,
    }
    if exclude_paths is not None:
        kwargs["exclude_paths"] = exclude_paths
    if context_extractor is not None:
        kwargs["context_extractor"] = context_extractor

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


def configure_app_observability(
    app: Any,
    *,
    exclude_paths: list[str] | None = None,
    track_metrics: bool = True,
    track_logging: bool = True,
    track_tracing: bool = True,
    metrics_path: str = "/metrics",
    context_extractor: Any | None = None,
) -> None:
    """Add :class:`~obskit.middleware.fastapi.ObskitMiddleware` and a Prometheus
    scrape endpoint to a FastAPI application in a single call.

    Equivalent to calling :func:`instrument_fastapi` and manually registering
    a ``/metrics`` route — useful when running two or more FastAPI apps (e.g.
    an API service and an upload service) that each need full observability.

    Parameters
    ----------
    app : FastAPI
        The FastAPI application to configure.
    exclude_paths : list[str], optional
        Paths excluded from middleware observability.  Defaults to the
        :class:`~obskit.middleware.core.MiddlewareCore` defaults.
    track_metrics : bool
        Enable RED metrics collection.  Default: ``True``.
    track_logging : bool
        Enable structured request/response logging.  Default: ``True``.
    track_tracing : bool
        Enable distributed tracing.  Default: ``True``.
    metrics_path : str
        URL path for the Prometheus scrape endpoint.  Default: ``"/metrics"``.
    context_extractor : callable, optional
        Forwarded to :class:`~obskit.middleware.fastapi.ObskitMiddleware`.
        Receives decoded request headers; returns extra log-context key/value pairs.

    Example
    -------
    ::

        from obskit.middleware.instrument import configure_app_observability

        upload_app = FastAPI(title="upload-service")
        configure_app_observability(upload_app, exclude_paths=["/v2/_healthy"])
        # ObskitMiddleware + GET /metrics are now registered on upload_app
    """
    instrument_fastapi(
        app,
        exclude_paths=exclude_paths,
        track_metrics=track_metrics,
        track_logging=track_logging,
        track_tracing=track_tracing,
        context_extractor=context_extractor,
    )

    from starlette.responses import Response  # noqa: PLC0415

    from obskit.metrics.registry import generate_latest  # noqa: PLC0415

    async def _metrics() -> Response:
        data = generate_latest()
        return Response(
            content=data,
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )

    app.add_api_route(metrics_path, _metrics, include_in_schema=False)
